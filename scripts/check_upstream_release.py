#!/usr/bin/env python3
"""Open one GitHub issue when a newer stable CloudCompare release exists."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "CloudCompare/CloudCompare"
MARKER_PREFIX = "<!-- cloudcompare-stable-release: "
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(value: str) -> tuple[int, int, int]:
    match = VERSION_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"not a stable three-part version: {value!r}")
    return tuple(int(part) for part in match.groups())


def recipe_version() -> str:
    recipe = (ROOT / "recipe" / "recipe.yaml").read_text(encoding="utf-8")
    match = re.search(r'^  version: "(\d+\.\d+\.\d+)"\s*$', recipe, re.MULTILINE)
    if not match:
        raise SystemExit("Could not read a stable x.y.z version from recipe/recipe.yaml")
    return match.group(1)


def api_request(url: str, *, token: str | None = None, method: str = "GET", data: dict | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cloudcompare-conda-stable-release-watcher",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
            return json.loads(payload) if payload else None, response.headers.get("Link", "")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API returned HTTP {error.code} for {url}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach GitHub API for {url}: {error}") from error


def next_link(link_header: str) -> str | None:
    for item in link_header.split(","):
        match = re.match(r'\s*<([^>]+)>\s*;\s*rel="next"', item)
        if match:
            return match.group(1)
    return None


def known_issue(api_url: str, repo: str, token: str, version: str) -> bool:
    url = f"{api_url}/repos/{repo}/issues?state=all&per_page=100"
    marker = f"{MARKER_PREFIX}v{version} -->"
    title = f"Upstream stable release available: v{version}"
    while url:
        issues, link_header = api_request(url, token=token)
        for issue in issues:
            if "pull_request" in issue:
                continue
            if issue.get("title") == title or marker in (issue.get("body") or ""):
                return True
        following = next_link(link_header)
        url = urljoin(url, following) if following else ""
    return False


def main() -> int:
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise SystemExit("GITHUB_REPOSITORY must identify the packaging repository")

    latest, _ = api_request(f"https://api.github.com/repos/{UPSTREAM}/releases/latest")
    if not latest or latest.get("draft") or latest.get("prerelease"):
        raise SystemExit("Upstream latest-release endpoint did not return a published stable release")
    tag = latest.get("tag_name", "")
    upstream_version = tag[1:] if tag.startswith("v") else tag
    current = recipe_version()
    upstream_key = parse_version(upstream_version)
    current_key = parse_version(current)
    print(f"Recipe version: {current}; latest stable upstream release: {tag}")

    if upstream_key <= current_key:
        print("No newer stable release; no issue needed.")
        return 0
    if not token:
        raise SystemExit("GITHUB_TOKEN is required to check for duplicate issues and create a new issue")
    if known_issue(api_url, repository, token, upstream_version):
        print(f"An issue for stable release {tag} already exists; skipping duplicate creation.")
        return 0

    title = f"Upstream stable release available: v{upstream_version}"
    marker = f"{MARKER_PREFIX}v{upstream_version} -->"
    body = (
        f"A newer **stable** CloudCompare release is available.\n\n"
        f"- Current recipe version: `{current}`\n"
        f"- Upstream stable release: [{tag}]({latest.get('html_url', '')})\n"
        f"- Upstream repository: https://github.com/{UPSTREAM}\n\n"
        "Review the upstream changes and update `context.version` and the full pinned "
        "`context.upstream_rev` together in `recipe/recipe.yaml`. Then run the build, "
        "package tests, and audit before preparing a packaging-repository release.\n\n"
        f"{marker}\n"
    )
    created, _ = api_request(
        f"{api_url}/repos/{repository}/issues",
        token=token,
        method="POST",
        data={"title": title, "body": body},
    )
    print(f"Created issue #{created.get('number')}: {created.get('html_url')}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from error
