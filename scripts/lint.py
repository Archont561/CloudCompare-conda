#!/usr/bin/env python3
"""Static consistency checks for the Pixi manifest, recipe and GitHub workflows."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SHA_ACTION = re.compile(r"^[^@]+@[0-9a-f]{40}$")
EXPECTED_PLATFORMS = ["linux-64", "win-64", "osx-64", "osx-arm64"]


def fail(message: str) -> None:
    raise SystemExit(f"lint error: {message}")


def load_workflow(path: Path) -> tuple[str, dict]:
    text = path.read_text(encoding="utf-8")
    return text, yaml.load(text, Loader=yaml.BaseLoader)


def check_pinned_actions(workflow_text: str, path: Path) -> None:
    for match in re.findall(r"(?m)^\s*uses:\s*([^\s#]+)", workflow_text):
        if not SHA_ACTION.fullmatch(match):
            fail(f"GitHub Action in {path.name} is not pinned to a full commit SHA: {match}")


def main() -> int:
    pixi = tomllib.loads((ROOT / "pixi.toml").read_text(encoding="utf-8"))
    recipe = yaml.safe_load((ROOT / "recipe" / "recipe.yaml").read_text(encoding="utf-8"))
    release_path = ROOT / ".github" / "workflows" / "release.yml"
    watcher_path = ROOT / ".github" / "workflows" / "check_upstream_release.yml"
    release_text, release = load_workflow(release_path)
    watcher_text, watcher = load_workflow(watcher_path)

    workspace = pixi.get("workspace", {})
    if workspace.get("channels") != ["conda-forge"]:
        fail("Pixi workspace must use only conda-forge")
    if workspace.get("platforms") != EXPECTED_PLATFORMS:
        fail(f"Pixi workspace must target exactly {EXPECTED_PLATFORMS}")
    tasks = pixi.get("tasks", {})
    if not {"lint", "build", "test", "audit"}.issubset(tasks):
        fail("Pixi tasks must include lint, build, test and audit")
    if "rattler-build" not in pixi.get("dependencies", {}):
        fail("Pixi environment must provide rattler-build")

    context = recipe.get("context", {})
    if context.get("name") != "cloudcompare" or not re.fullmatch(r"\d+\.\d+\.\d+", str(context.get("version", ""))):
        fail("recipe context must identify a stable CloudCompare x.y.z version")
    source = recipe.get("source", {})
    if source.get("rev") != "${{ upstream_rev }}" or not re.fullmatch(r"[0-9a-f]{40}", str(context.get("upstream_rev", ""))):
        fail("upstream source must be pinned to a full 40-character commit in context")
    if source.get("submodules") is not True:
        fail("upstream's required submodules must be initialized")
    if recipe.get("package", {}).get("name") != "${{ name }}":
        fail("recipe package name must derive from context")

    trigger = release.get("on", {})
    if "release" not in trigger or trigger["release"].get("types") != ["published"]:
        fail("release workflow must publish only on a published GitHub Release")
    jobs = release.get("jobs", {})
    if "build" not in jobs or "publish" not in jobs:
        fail("release workflow must separate build and publish jobs")
    build = jobs["build"]
    if "id-token" in build.get("permissions", {}):
        fail("build job must not have OIDC permission")
    if jobs["publish"].get("permissions", {}).get("id-token") != "write":
        fail("publish job must have narrowly-scoped id-token: write permission")
    if jobs["publish"].get("environment") != "prefix":
        fail("publish job must run in the 'prefix' GitHub Environment so its OIDC token carries the environment claim trusted by prefix.dev")
    if not jobs["publish"].get("needs"):
        fail("publish job must depend on the build job")
    matrix_platforms = sorted(item.get("subdir", "") for item in build.get("strategy", {}).get("matrix", {}).get("include", []))
    if matrix_platforms != sorted(EXPECTED_PLATFORMS):
        fail(f"release workflow build matrix must cover {EXPECTED_PLATFORMS}")
    if "scripts/setup_msvc.py" not in release_text:
        fail("Windows build must initialize the native MSVC environment")
    if "archont561/archont561" not in release_text:
        fail("release workflow does not target the requested prefix.dev channel")
    if "--generate-attestation" not in release_text:
        fail("publisher should generate a package attestation with trusted publishing")
    upload_version = re.search(r"(?m)^\s*rattler-build-version:\s*(\S+)\s*$", release_text)
    if not upload_version or not re.fullmatch(r"v\d+\.\d+\.\d+", upload_version.group(1)):
        fail(
            "rattler-build-action interpolates rattler-build-version directly into the GitHub "
            "release download URL, so it must be a tag with a leading 'v' (e.g. v0.68.0)"
        )
    if re.search(r"PREFIX_API_KEY|PREFIX_DEV_TOKEN|--api-key|secrets\.", release_text, re.IGNORECASE):
        fail("release workflow must not use stored prefix.dev tokens or secret-based authentication")

    watcher_trigger = watcher.get("on", {})
    if not watcher_trigger.get("schedule") or "workflow_dispatch" not in watcher_trigger:
        fail("stable-release watcher must run daily and support manual dispatch")
    watcher_jobs = watcher.get("jobs", {})
    if "check" not in watcher_jobs:
        fail("stable-release watcher must define a check job")
    watcher_permissions = watcher_jobs["check"].get("permissions", {})
    if watcher_permissions != {"contents": "read", "issues": "write"}:
        fail("stable-release watcher permissions must be limited to contents: read and issues: write")
    if "GITHUB_TOKEN: ${{ github.token }}" not in watcher_text or "check_upstream_release.py" not in watcher_text:
        fail("stable-release watcher must pass its ephemeral GitHub token to the Python issue-check script")
    watcher_script = (ROOT / "scripts" / "check_upstream_release.py").read_text(encoding="utf-8")
    for required_behavior in ("/releases/latest", "prerelease", "state=all", "MARKER_PREFIX", "issues"):
        if required_behavior not in watcher_script:
            fail(f"stable-release watcher script is missing required behavior: {required_behavior}")
    if not (ROOT / "scripts" / "setup_msvc.py").is_file():
        fail("cross-platform Windows builds require scripts/setup_msvc.py")

    check_pinned_actions(release_text, release_path)
    check_pinned_actions(watcher_text, watcher_path)
    print("Lint passed: four-platform Pixi/release matrix, pinned source recipe, OIDC publisher boundary, and least-privilege stable-release watcher are consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
