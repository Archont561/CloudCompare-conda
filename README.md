# CloudCompare Conda packages

[![Release workflow](https://github.com/Archont561/CloudCompare-conda/actions/workflows/release.yml/badge.svg)](https://github.com/Archont561/CloudCompare-conda/actions/workflows/release.yml)
[![Latest stable upstream release](https://img.shields.io/github/v/release/CloudCompare/CloudCompare?label=latest%20stable)](https://github.com/CloudCompare/CloudCompare/releases/latest)

Native `.conda` packages for **Linux x86-64**, **Windows x86-64**, **Intel macOS**, and **Apple Silicon**. The recipe currently pins CloudCompare **2.13.2** and builds CloudCompare, ccViewer, qLAS, qEDL, qSSAO, qCSF, and qHPR. Source: [Archont561/CloudCompare-conda](https://github.com/Archont561/CloudCompare-conda).

## Install

```console
pixi init cloudcompare-user
cd cloudcompare-user
pixi add --channel https://prefix.dev/archont561/archont561 cloudcompare
```

## Build

Build natively on the target platform with [Pixi](https://pixi.sh/):

```console
pixi install
pixi run lint
pixi run build
pixi run test
pixi run audit
```

Packages are written to `output/<platform>/`.

## Releases

Publishing starts when a matching stable GitHub Release is published. GitHub Actions builds, tests, and audits all four platforms, then the publish job—running in the GitHub Environment named `prefix`—uploads the `cloudcompare` package through prefix.dev Trusted Publishing (OIDC); no publishing token is stored in repository secrets. The daily watcher checks for newer stable upstream releases and opens a deduplicated issue—it does not publish automatically.

## Licensing

Packages include CloudCompare, CCCoreLib, and QCustomPlot license notices under `share/licenses/cloudcompare/`. The root [MIT license](LICENSE) covers only this packaging repository, not CloudCompare or its dependencies.
