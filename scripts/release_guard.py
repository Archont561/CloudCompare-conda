#!/usr/bin/env python3
"""Reject releases not matching the recipe or not on the default branch history."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="GitHub Release tag, such as v2.13.2")
    parser.add_argument("--check-ancestry", action="store_true", help="require tag commit to be on checked-out default branch")
    args = parser.parse_args()

    recipe = yaml.safe_load((ROOT / "recipe" / "recipe.yaml").read_text(encoding="utf-8"))
    version = str(recipe["context"]["version"])
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"recipe version must be a stable x.y.z release, got {version!r}")
    expected_tag = f"v{version}"
    if args.tag != expected_tag:
        raise SystemExit(f"release tag {args.tag!r} does not match recipe version; expected {expected_tag!r}")

    if args.check_ancestry:
        try:
            tag_commit = git("rev-parse", "--verify", f"refs/tags/{args.tag}^{{commit}}")
            head_commit = git("rev-parse", "--verify", "HEAD^{commit}")
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", tag_commit, head_commit],
                cwd=ROOT,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            raise SystemExit("release tag must resolve to a commit reachable from the checked-out default branch") from error

    print(f"Release guard passed for {args.tag} (CloudCompare {version}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
