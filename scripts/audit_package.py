#!/usr/bin/env python3
"""Inspect a built .conda package without installing or executing its payload."""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import yaml
import zstandard

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {".cpp", ".cxx", ".c", ".h", ".hpp", ".o", ".a", ".pyc"}
LICENSES = {
    "share/licenses/cloudcompare/CloudCompare-license.txt",
    "share/licenses/cloudcompare/CCCoreLib-LICENSE.txt",
    "share/licenses/cloudcompare/CCCoreLib-LICENSE-MIT.txt",
    "share/licenses/cloudcompare/QCustomPlot-GPL.txt",
}
EXECUTABLES = {
    "linux-64": {"bin/CloudCompare", "bin/ccViewer"},
    "win-64": {"CloudCompare/CloudCompare.exe", "ccViewer/ccViewer.exe"},
    "osx-64": {
        "CloudCompare/CloudCompare.app/Contents/MacOS/CloudCompare",
        "ccViewer/ccViewer.app/Contents/MacOS/ccViewer",
    },
    "osx-arm64": {
        "CloudCompare/CloudCompare.app/Contents/MacOS/CloudCompare",
        "ccViewer/ccViewer.app/Contents/MacOS/ccViewer",
    },
}


def normalized_name(raw_name: str) -> str:
    name = raw_name
    while name.startswith("./"):
        name = name[2:]
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe archive member path: {raw_name!r}")
    return path.as_posix()


def inspect_conda(path: Path) -> tuple[dict, set[str], dict[str, bytes]]:
    if path.suffix != ".conda":
        raise ValueError(f"Not a .conda package: {path}")
    files: set[str] = set()
    metadata: dict[str, dict] = {}
    executables: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as conda_file:
        members = conda_file.namelist()
        package_tars = [n for n in members if n.startswith("pkg-") and n.endswith(".tar.zst")]
        info_tars = [n for n in members if n.startswith("info-") and n.endswith(".tar.zst")]
        if len(package_tars) != 1 or len(info_tars) != 1:
            raise ValueError(f"Expected one package and one info tar.zst, found: {members}")
        for archive_name in package_tars + info_tars:
            with conda_file.open(archive_name) as compressed:
                reader = zstandard.ZstdDecompressor().stream_reader(compressed)
                try:
                    with tarfile.open(fileobj=reader, mode="r|") as tar:
                        for item in tar:
                            name = normalized_name(item.name)
                            if archive_name in info_tars:
                                for meta_name in ("info/index.json", "info/about.json"):
                                    if name == meta_name and item.isfile():
                                        extracted = tar.extractfile(item)
                                        if extracted is not None:
                                            metadata[meta_name] = json.loads(extracted.read())
                            elif item.isfile():
                                files.add(name)
                                if name in set().union(*EXECUTABLES.values()):
                                    payload = tar.extractfile(item)
                                    if payload is not None:
                                        executables[name] = payload.read()
                            elif item.isdir():
                                files.add(name.rstrip("/"))
                finally:
                    reader.close()
    index = metadata.get("info/index.json")
    if not index:
        raise ValueError("Conda package is missing info/index.json")
    return index, files, executables


def inspect_elf(executables: dict[str, bytes]) -> list[str]:
    readelf = shutil.which("readelf")
    if not readelf:
        raise RuntimeError("readelf was not found; install binutils in the audit environment")
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="cloudcompare-audit-") as tmp:
        for name, payload in executables.items():
            target = Path(tmp) / Path(name).name
            target.write_bytes(payload)
            header = subprocess.run([readelf, "-h", str(target)], capture_output=True, text=True, check=True).stdout
            if "ELF64" not in header or "X86-64" not in header:
                errors.append(f"{name} is not an ELF64 x86-64 executable")
            dynamic = subprocess.run([readelf, "-d", str(target)], capture_output=True, text=True, check=True).stdout
            if re.search(r"/(?:home/runner/work|tmp/conda|opt/conda/conda-bld)/", dynamic):
                errors.append(f"{name} retains a CI/build absolute path in its ELF dynamic section")
    return errors


def inspect_pe(executables: dict[str, bytes]) -> list[str]:
    errors: list[str] = []
    for name, payload in executables.items():
        if len(payload) < 64 or payload[:2] != b"MZ":
            errors.append(f"{name} does not have a valid PE DOS header")
            continue
        pe_offset = struct.unpack_from("<I", payload, 0x3C)[0]
        if pe_offset + 6 > len(payload) or payload[pe_offset : pe_offset + 4] != b"PE\0\0":
            errors.append(f"{name} does not have a valid PE signature")
            continue
        machine = struct.unpack_from("<H", payload, pe_offset + 4)[0]
        if machine != 0x8664:
            errors.append(f"{name} is not an x86-64 PE executable (machine=0x{machine:04x})")
    return errors


def inspect_macho(executables: dict[str, bytes], subdir: str) -> list[str]:
    lipo = shutil.which("lipo")
    if not lipo:
        raise RuntimeError("lipo was not found; macOS audit must run on a macOS runner")
    expected_arch = "x86_64" if subdir == "osx-64" else "arm64"
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="cloudcompare-audit-") as tmp:
        for name, payload in executables.items():
            target = Path(tmp) / Path(name).name
            target.write_bytes(payload)
            result = subprocess.run([lipo, "-info", str(target)], capture_output=True, text=True, check=True)
            if expected_arch not in result.stdout + result.stderr:
                errors.append(f"{name} is not a macOS {expected_arch} executable")
    return errors


def expected_subdir() -> str:
    if sys.platform.startswith("linux"):
        return "linux-64"
    if sys.platform == "win32":
        return "win-64"
    if sys.platform == "darwin":
        return "osx-arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "osx-64"
    raise SystemExit(f"Unsupported audit host platform: {sys.platform}/{platform.machine()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", help="audit one .conda package file")
    parser.add_argument("--package-dir", help="directory to search (defaults to output/<this platform>)")
    args = parser.parse_args()
    target_subdir = expected_subdir()
    package_dir = args.package_dir or f"output/{target_subdir}"
    if args.package:
        packages = [Path(args.package).expanduser().resolve()]
    else:
        packages = sorted((ROOT / package_dir).resolve().glob("cloudcompare-*.conda"))
    if len(packages) != 1:
        raise SystemExit(f"Expected exactly one cloudcompare-*.conda package; found {len(packages)}: {packages}")
    package_file = packages[0]
    if not package_file.is_file():
        raise SystemExit(f"Package file does not exist: {package_file}")

    recipe = yaml.safe_load((ROOT / "recipe" / "recipe.yaml").read_text(encoding="utf-8"))
    expected_version = str(recipe["context"]["version"])
    index, files, executables = inspect_conda(package_file)
    errors: list[str] = []
    if index.get("name") != "cloudcompare":
        errors.append(f"unexpected package name: {index.get('name')!r}")
    if str(index.get("version")) != expected_version:
        errors.append(f"package version {index.get('version')!r} does not match recipe {expected_version!r}")
    if index.get("subdir") != target_subdir:
        errors.append(f"package subdir must be {target_subdir}, got {index.get('subdir')!r}")

    expected_executables = EXECUTABLES.get(target_subdir, set())
    missing = sorted((LICENSES | expected_executables) - files)
    if missing:
        errors.append("missing installed files: " + ", ".join(missing))
    plugins = [
        name for name in files
        if "/plugins/" in f"/{name.lower()}/"
        and PurePosixPath(name).suffix.lower() in {".so", ".dylib", ".dll"}
    ]
    if not plugins:
        errors.append("no application/plugin shared libraries found")

    source_like = [
        name for name in files
        if PurePosixPath(name).suffix.lower() in FORBIDDEN_SUFFIXES
        or PurePosixPath(name).name in {"CMakeCache.txt", "build.ninja", "compile_commands.json"}
    ]
    if source_like:
        errors.append("unexpected source/build files in package: " + ", ".join(sorted(source_like)[:20]))

    if set(executables) != expected_executables:
        errors.append("could not read both expected application executable payloads from the Conda archive")
    elif target_subdir == "linux-64":
        errors.extend(inspect_elf(executables))
    elif target_subdir == "win-64":
        errors.extend(inspect_pe(executables))
    else:
        errors.extend(inspect_macho(executables, target_subdir))

    if errors:
        print(f"Package audit failed for {package_file}:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"Audit passed: {package_file}")
    print(f"  package: {index['name']} {index['version']} ({index['subdir']})")
    print(f"  payload files: {len(files)}; plugin binaries: {len(plugins)}")
    print("  executables match the target platform architecture")
    return 0


if __name__ == "__main__":
    sys.exit(main())
