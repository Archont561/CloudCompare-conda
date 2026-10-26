#!/usr/bin/env python3
"""Export the installed Visual Studio x64 developer environment to GitHub steps."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


EXCLUDED_PREFIXES = ("GITHUB_", "RUNNER_")


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("setup_msvc.py is only intended for the Windows release-matrix job")

    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    vswhere = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if not vswhere.is_file():
        raise SystemExit(f"Visual Studio locator was not found: {vswhere}")
    locate = subprocess.run(
        [
            str(vswhere),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    install_path = locate.stdout.strip()
    if not install_path:
        raise SystemExit("No Visual Studio installation with the x64 C++ build tools was found")
    vcvars = Path(install_path) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
    if not vcvars.is_file():
        raise SystemExit(f"Visual Studio x64 environment script was not found: {vcvars}")

    command_line = f'call "{vcvars}" >nul && set'
    result = subprocess.run(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command_line],
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
        check=True,
    )
    original = {name.upper(): value for name, value in os.environ.items()}
    environment: dict[str, str] = {}
    for line in result.stdout.splitlines():
        name, separator, value = line.partition("=")
        if (
            separator
            and name
            and not name.upper().startswith(EXCLUDED_PREFIXES)
            and original.get(name.upper()) != value
        ):
            environment[name] = value
    environment["CC"] = "cl.exe"
    environment["CXX"] = "cl.exe"

    github_env = os.environ.get("GITHUB_ENV")
    if not github_env:
        raise SystemExit("GITHUB_ENV is missing; run this script inside a GitHub Actions job")
    with Path(github_env).open("a", encoding="utf-8", newline="\n") as output:
        for name, value in sorted(environment.items()):
            if "\n" in value or "\r" in value:
                raise SystemExit(f"Refusing to export a multi-line environment value: {name}")
            output.write(f"{name}={value}\n")
    print(f"Configured MSVC x64 from {install_path}; exported {len(environment)} variables for subsequent workflow steps.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
