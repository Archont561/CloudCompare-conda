# CloudCompare 2.13.2 linux-64 host smoke test

**Date:** 2026-10-26 (Europe/Warsaw)  
**Source:** autonomous connected-host smoke test report (`REPORT.md`)  
**Package under test:** `cloudcompare` 2.13.2, build `hb0f4dca_0`, installed from `https://prefix.dev/archont561/archont561`  
**Release:** [CloudCompare 2.13.2](https://github.com/Archont561/CloudCompare-conda/releases/tag/v2.13.2)

## Verdict

**PASS for installation, CLI use, and virtual-display GUI launch/interaction.**

The connected host had no native desktop/display session, so GUI evidence was collected under Xvfb with Mesa software OpenGL (llvmpipe/swrast). This should therefore be read as a **virtual-display pass**, not as native-desktop or hardware-GPU validation.

## Result summary

| Field | Value |
|---|---|
| Host OS/architecture | Debian GNU/Linux 13 (trixie), kernel 6.1.158+ SMP PREEMPT_DYNAMIC, **x86_64** (`linux-64`) |
| Display availability | No native display: `DISPLAY`/`WAYLAND_DISPLAY` empty, no `/tmp/.X11-unix`, no desktop session. A virtual display `Xvfb :99` (1600×1000×24) with system Mesa software GL was used for GUI evidence. |
| Pixi version | **0.83.0**, installed in an isolated test area with `PIXI_HOME` scoped to the test workspace. |
| Install result | **SUCCESS** — solver, download, and link completed with no errors in about 9 seconds. On Pixi 0.83 the channel was added with `pixi workspace channel add` because that version's `pixi add` had no `--channel` flag. |
| Installed package version | **`cloudcompare` 2.13.2, build `hb0f4dca_0`** (4.38 MiB package; environment total 1.3 GB including `qt-main` 5.15.15 from conda-forge). |
| CloudCompare executable | `cloudcompare-smoke-test/.pixi/envs/default/bin/CloudCompare` (ELF x86-64; `ldd` reported zero "not found" entries). |
| ccViewer executable | `cloudcompare-smoke-test/.pixi/envs/default/bin/ccViewer` (ELF x86-64; `ldd` clean). |
| CLI test result | **PASS** — `CloudCompare -SILENT -HELP` exited 0, printed a 103-line command list, and loaded 6 plugins: Core I/O, CSF, EDL, HPR, LAS I/O, and SSAO. |
| CLI file round-trip | **PASS** — `CloudCompare -SILENT -O test_cube.xyz -C_EXPORT_FMT PLY -SAVE_CLOUDS FILE roundtrip_out.ply` exited 0. The log reported "Found one cloud with 1000 points" and "saved successfully". The output PLY was valid, contained 1000 vertices, and had the header "Created by CloudCompare v2.13.2 (Kharkiv - Oct 26 2026)". |
| CloudCompare GUI launch | **PASS (virtual display)** — the main window `CloudCompare v2.13.2 (Kharkiv - Oct 26 2026) [64-bit] - [3D View 1]` opened, stayed alive for 60s+ (beyond the required 20s), and logged zero crash/OpenGL/Qt-plugin errors. |
| Point-cloud display / interaction | **PASS** — opening the XYZ file triggered the normal "Open Ascii File" import dialog; after confirmation, the DB Tree showed `test_cube.xyz → test_cube - Cloud`, and the 3D view rendered the 1000-point cube grid. Console output included `3D view initialized`, `PBO for faster depth picking`, and `loaded successfully`. Synthetic left-drag rotated the camera and mouse-wheel input zoomed (scale bar 2 → 1.5), showing the GUI was responsive. |
| ccViewer launch | **PASS** — `ccViewer test_cube.ply` opened `ccViewer v1.41 (Oct 26 2026) [64-bit]`, rendered the cloud, and did not crash. |
| Errors / blockers | **None for the package.** Only benign/cosmetic host-side notes were recorded: typical conda-Qt stderr warnings (`QSocketNotifier`, `XDG_RUNTIME_DIR`, ICC profile, translations); `-C_EXPORT_FMT XYZ` was rejected as an unhandled format specifier while `PLY` worked; extra host tools (`xvfb`, `x11-apps`, `xdotool`, `imagemagick`) were installed only to provide the virtual display and screenshots; after the window-close message the CloudCompare process lingered and was ended with SIGTERM (exit 143), which the tester did not classify as a crash. |
| Cleanup status | Xvfb was stopped, both applications were closed, and Pixi's temporary `~/.bashrc` PATH change was reverted. The connected-host test workspace was intentionally retained by the tester for follow-up. |

## Evidence collected on the connected host

The report lists the following evidence files in the retained connected-host workspace. They were not attached to this repository change, so they are recorded here as an inventory rather than as repository links.

| Evidence file | Content |
|---|---|
| `logs/shot1-ascii-dialog.png` | CloudCompare GUI after launch, pre-import state. |
| `logs/shot2-cloud-loaded.png` | DB Tree, rendered point cloud, and console log lines. |
| `logs/shot3-rotated-zoomed.png` | CloudCompare after rotate/zoom interaction, with the view visibly changed. |
| `logs/shot4-ccviewer.png` | ccViewer rendering the PLY cloud. |
| `logs/cli-help.stdout.log` | Full `CloudCompare -SILENT -HELP` transcript. |
| `logs/cli-roundtrip.stdout.log` | Full XYZ → PLY CLI round-trip transcript. |
| `logs/pixi-add.log` / `logs/channel-add.log` | Install output showing no solver/download/link errors. |
| `test-data/test_cube.xyz` | 1000-point test cloud used for CLI and GUI checks. |
| `test-data/test_cube.ply` / `test-data/roundtrip_out.ply` | PLY test cloud and CLI round-trip output. |

## Scope limits

- This evidence covers the **`linux-64`** package only.
- It does not validate a native desktop session, hardware GPU rendering, or the Windows/macOS packages.
- It confirms installation from the published prefix.dev channel, basic CLI operation, GUI startup under a virtual display, point-cloud rendering, basic camera interaction, and ccViewer startup.
