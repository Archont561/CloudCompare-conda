#!/usr/bin/env python3
"""Run the test suite embedded in one or more built Conda package files."""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def current_subdir() -> str:
    if sys.platform.startswith("linux"):
        return "linux-64"
    if sys.platform == "win32":
        return "win-64"
    if sys.platform == "darwin":
        return "osx-arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "osx-64"
    raise SystemExit(f"Unsupported test host platform: {sys.platform}/{platform.machine()}")


def find_packages(package: str | None, package_dir: str | None) -> list[Path]:
    if package:
        candidate = Path(package).expanduser().resolve()
        if not candidate.is_file():
            raise SystemExit(f"Package file does not exist: {candidate}")
        return [candidate]
    folder = (ROOT / (package_dir or f"output/{current_subdir()}")).resolve()
    packages = sorted(folder.glob("cloudcompare-*.conda"))
    if not packages:
        raise SystemExit(f"No CloudCompare .conda package found in {folder}; run `pixi run build` first.")
    return packages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", help="test this package file instead of searching output/")
    parser.add_argument("--package-dir", help="directory to search (defaults to output/<this platform>)")
    args = parser.parse_args()
    for package_file in find_packages(args.package, args.package_dir):
        command = ["rattler-build", "test", "--package-file", str(package_file), "--channel", "conda-forge"]
        print("+", " ".join(command), flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
