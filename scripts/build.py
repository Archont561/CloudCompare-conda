#!/usr/bin/env python3
"""Configure, build, install and stage CloudCompare notices with CMake/Ninja."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


@contextmanager
def qt5_stdext_workaround(dependency_prefix: Path) -> Iterator[None]:
    """Work around Qt 5.15 headers that still emit stdext checked iterators.

    conda-forge's qt-main 5.15 headers define the
    QT_MAKE_[UN]CHECKED_ARRAY_ITERATOR macros in terms of
    stdext::make_[un]checked_array_iterator unconditionally for MSVC.
    Microsoft deprecated those APIs in VS 2022 17.8 and removed them from
    the VS 2026 STL, so compiling against them on current runners fails
    with "'stdext': is not a class or namespace name". Upstream Qt fixed
    this by only using stdext for _MSC_VER < 1938 and falling back to the
    plain pointer otherwise. Apply that same fallback to the copy of
    qcompilerdetection.h in the build (host) prefix for the duration of
    this build, then restore the original file byte-for-byte (including
    timestamps) so the host prefix -- and therefore the packaged files --
    are unaffected. No-op if the installed headers are already fixed.
    """
    candidates = [
        dependency_prefix / "include" / "qt" / "QtCore" / "qcompilerdetection.h",
        dependency_prefix / "include" / "QtCore" / "qcompilerdetection.h",
    ]
    header = next((path for path in candidates if path.is_file()), None)
    if header is None:
        print("Qt qcompilerdetection.h not found; skipping stdext workaround.", flush=True)
        yield
        return

    original = header.read_bytes()
    text = original.decode("utf-8")
    if "_MSC_VER < 1938" in text:
        # Headers already restrict the stdext macros to compilers whose STL
        # still provides them; nothing to do.
        yield
        return
    patched = re.sub(
        r"(#\s*define\s+QT_MAKE_CHECKED_ARRAY_ITERATOR\(\s*x\s*,\s*N\s*\))"
        r"\s*stdext::make_checked_array_iterator\(\s*x\s*,\s*size_t\(\s*N\s*\)\s*\)",
        r"\1 (x)",
        text,
    )
    patched = re.sub(
        r"(#\s*define\s+QT_MAKE_UNCHECKED_ARRAY_ITERATOR\(\s*x\s*\))"
        r"\s*stdext::make_unchecked_array_iterator\(\s*x\s*\)",
        r"\1 (x)",
        patched,
    )
    if patched == text:
        yield
        return

    original_stat = header.stat()
    header.write_bytes(patched.encode("utf-8"))
    print(f"Applied Qt stdext checked-iterator workaround: {header}", flush=True)
    try:
        yield
    finally:
        header.write_bytes(original)
        os.utime(header, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))


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

    cpu_count = os.environ.get("CPU_COUNT") or str(os.cpu_count() or 2)
    workaround = qt5_stdext_workaround(dependency_prefix) if system == "Windows" else nullcontext()
    with workaround:
        run(configure, cwd=source, env=env)
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
