#!/usr/bin/env python3
"""Configure, build, install and stage CloudCompare notices with CMake/Ninja."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def main() -> None:
    system = platform.system()
    machine = platform.machine().lower()
    supported = {
        ("Linux", "x86_64"),
        ("Linux", "amd64"),
        ("Windows", "amd64"),
        ("Windows", "x86_64"),
        ("Darwin", "x86_64"),
        ("Darwin", "arm64"),
        ("Darwin", "aarch64"),
    }
    if (system, machine) not in supported:
        raise SystemExit(f"Unsupported build host: {system}/{machine}")

    source = Path(os.environ.get("SRC_DIR", Path.cwd())).resolve()
    prefix_value = os.environ.get("PREFIX")
    if not prefix_value:
        raise SystemExit("rattler-build did not provide PREFIX; refusing to install outside the package prefix.")
    prefix = Path(prefix_value).resolve()
    if not (source / "CMakeLists.txt").is_file():
        raise SystemExit(f"SRC_DIR does not look like a CloudCompare checkout: {source}")

    cmake = shutil.which("cmake")
    if not cmake:
        raise SystemExit("cmake is missing from the rattler-build environment")

    # Conda packages on Windows place headers and libraries in <prefix>/Library;
    # Linux and macOS use the prefix root. CMake installs the app into PREFIX.
    dependency_prefix = prefix / "Library" if system == "Windows" else prefix
    build_dir = source / ".conda-build"
    build_dir.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["CMAKE_PREFIX_PATH"] = str(dependency_prefix)
    env["EIGEN_ROOT_DIR"] = str(dependency_prefix / "include" / "eigen3")

    configure = [
        cmake,
        "-S",
        str(source),
        "-B",
        str(build_dir),
        "-G",
        "Ninja",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={prefix}",
        f"-DCMAKE_PREFIX_PATH={dependency_prefix}",
        f"-DEIGEN_ROOT_DIR={dependency_prefix / 'include' / 'eigen3'}",
        # Upstream's v2.13.2 CI demonstrates these options on Linux, Windows,
        # and macOS. The TBB backend is only enabled in its Linux build.
        "-DCCCORELIB_SCALAR_DOUBLE=ON",
        "-DOPTION_BUILD_CCVIEWER=ON",
        "-DPLUGIN_IO_QCORE=ON",
        "-DPLUGIN_IO_QLAS=ON",
        "-DPLUGIN_GL_QEDL=ON",
        "-DPLUGIN_GL_QSSAO=ON",
        "-DPLUGIN_STANDARD_QCSF=ON",
        "-DPLUGIN_STANDARD_QHPR=ON",
    ]
    if system == "Linux":
        configure.extend(
            [
                "-DCMAKE_INSTALL_LIBDIR=lib",
                "-DCCCORELIB_USE_TBB=ON",
            ]
        )

    run(configure, cwd=source, env=env)

    cpu_count = os.environ.get("CPU_COUNT") or str(os.cpu_count() or 2)
    run([cmake, "--build", str(build_dir), "--parallel", cpu_count], cwd=source, env=env)
    run([cmake, "--install", str(build_dir), "--config", "Release"], cwd=source, env=env)

    # Preserve notices for code compiled into the package. Contents are copied
    # verbatim from the exact upstream/submodule revisions.
    notices = {
        "license.txt": "CloudCompare-license.txt",
        "libs/qCC_db/extern/CCCoreLib/LICENSE.txt": "CCCoreLib-LICENSE.txt",
        "libs/qCC_db/extern/CCCoreLib/LICENSE-MIT.txt": "CCCoreLib-LICENSE-MIT.txt",
        "qCC/extern/QCustomPlot/GPL.txt": "QCustomPlot-GPL.txt",
    }
    license_dir = prefix / "share" / "licenses" / "cloudcompare"
    license_dir.mkdir(parents=True, exist_ok=True)
    for relative_source, name in notices.items():
        source_file = source / relative_source
        if not source_file.is_file():
            raise SystemExit(f"Required upstream license notice is missing: {source_file}")
        shutil.copy2(source_file, license_dir / name)


if __name__ == "__main__":
    main()
