#!/usr/bin/env python3
"""Export the installed Visual Studio x64 developer environment to GitHub steps.

Standard-library only on purpose: the release workflow runs this with the
runner's system Python so the exported MSVC environment is captured cleanly,
before any Pixi environment activation in later steps.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


EXCLUDED_PREFIXES = ("GITHUB_", "RUNNER_")
ENV_MARKER = "__MSVC_ENV_START__"


def capture_vcvars_env(vcvars: Path) -> list[str]:
    """Run vcvars64.bat and return the ``set`` output lines that follow it.

    The call is written to a temporary batch file instead of being passed as
    a single ``cmd /c`` list argument. subprocess list quoting on Windows
    (list2cmdline) backslash-escapes the inner quotes around the vcvars
    path, and cmd.exe treats those backslashes as literal path characters,
    so the batch file is never found. A marker line separates any vcvars
    banner output from the environment dump, and failure output is surfaced
    instead of being hidden inside a CalledProcessError traceback.
    """
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".bat",
        prefix="setup_msvc_",
        delete=False,
        encoding="utf-8",
        newline="\r\n",
    )
    batch = Path(handle.name)
    try:
        with handle:
            handle.write("@echo off\n")
            handle.write(f'call "{vcvars}"\n')
            handle.write("if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%\n")
            handle.write(f"echo {ENV_MARKER}\n")
            handle.write("set\n")
        result = subprocess.run(
            f'call "{batch}"',
            shell=True,
            capture_output=True,
            text=True,
            encoding="mbcs",
            errors="replace",
            check=False,
        )
    finally:
        batch.unlink(missing_ok=True)

    if result.returncode:
        detail = (result.stdout + result.stderr).strip()
        raise SystemExit(
            f"vcvars64.bat failed with exit code {result.returncode}:\n{detail or '(no output)'}"
        )
    lines = result.stdout.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == ENV_MARKER:
            return lines[index + 1 :]
    detail = (result.stdout + result.stderr).strip()
    raise SystemExit(f"environment marker missing from vcvars output:\n{detail or '(no output)'}")


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
        check=False,
    )
    if locate.returncode:
        detail = (locate.stdout + locate.stderr).strip()
        raise SystemExit(f"vswhere failed with exit code {locate.returncode}: {detail or '(no output)'}")
    install_path = locate.stdout.strip()
    if not install_path:
        raise SystemExit("No Visual Studio installation with the x64 C++ build tools was found")
    vcvars = Path(install_path) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
    if not vcvars.is_file():
        raise SystemExit(f"Visual Studio x64 environment script was not found: {vcvars}")

    original = {name.upper(): value for name, value in os.environ.items()}
    environment: dict[str, str] = {}
    for line in capture_vcvars_env(vcvars):
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
