# CloudCompare 2.13.2 (prefix.dev/archont561) — Host Smoke Test Report

Date: 2026-10-26 (Europe/Warsaw) · Tested autonomously on the connected host · Evidence-first

## Result summary

- **Overall result: PASS** (GUI evidence collected on a **virtual display (Xvfb)** — the host has no physical/desktop session, so per protocol this is labeled a virtual-display pass rather than a native-desktop pass)

| Field | Value |
|---|---|
| Host OS/architecture | Debian GNU/Linux 13 (trixie), kernel 6.1.158+ SMP PREEMPT_DYNAMIC, **x86_64** (linux-64 — supported platform) |
| Display availability | **No native display** — `DISPLAY`/`WAYLAND_DISPLAY` empty, no `/tmp/.X11-unix`, no desktop session. A virtual display `Xvfb :99` (1600×1000×24) with system Mesa software GL (llvmpipe/swrast) was used for GUI evidence |
| Pixi version | **0.83.0** (not preinstalled; installed isolated under `/home/user/cc-host-test/pixi-home`, `PIXI_HOME` scoped — system untouched except apt additions noted below) |
| Install result | **SUCCESS** — solver + download + link completed with no errors (~9 s). Channel `https://prefix.dev/archont561/archont561` added via `pixi workspace channel add` (this pixi version's `pixi add` has no `--channel` flag) |
| Installed package version | **cloudcompare 2.13.2, build `hb0f4dca_0`** (4.38 MiB binary tarball; env total 1.3 GB incl. qt-main 5.15.15 from conda-forge) |
| CloudCompare executable | `/home/user/cc-host-test/cloudcompare-smoke-test/.pixi/envs/default/bin/CloudCompare` (ELF x86-64, `ldd`: zero "not found") |
| ccViewer executable | `/home/user/cc-host-test/cloudcompare-smoke-test/.pixi/envs/default/bin/ccViewer` (ELF x86-64, `ldd` clean) |
| CLI test result | **PASS** — `CloudCompare -SILENT -HELP` → exit **0**, 103-line command list, 6 plugins loaded (Core I/O, CSF, EDL, HPR, LAS I/O, SSAO). Round-trip: `-SILENT -O test_cube.xyz -C_EXPORT_FMT PLY -SAVE_CLOUDS FILE roundtrip_out.ply` → exit **0**, log: "Found one cloud with 1000 points" → "saved successfully"; output PLY valid (1000 vertices, header "Created by CloudCompare v2.13.2 (Kharkiv - Oct 26 2026)") |
| CloudCompare GUI launch | **PASS (virtual display)** — main window `CloudCompare v2.13.2 (Kharkiv - Oct 26 2026) [64-bit] - [3D View 1]` opened, alive 60 s+ (well over the required 20 s), zero crash/GL/Qt-plugin errors in log |
| Point-cloud display / interaction | **PASS** — XYZ opened at launch triggered the normal "Open Ascii File" import dialog (screenshot 1); confirmed with Enter. DB Tree then showed `test_cube.xyz → test_cube - Cloud`; 3D view rendered the 1000-point cube grid (screenshot 2); console logged `3D view initialized`, `PBO for faster depth picking` (real OpenGL init via llvmpipe), `loaded successfully`. Synthetic left-drag **rotated** the camera (axis tripod orientation changed) and wheel **zoomed** (scale bar 2 → 1.5) — GUI responsive (screenshot 3) |
| ccViewer launch | **PASS** — `ccViewer test_cube.ply` opened window `ccViewer v1.41 (Oct 26 2026) [64-bit]`, cloud rendered (screenshot 4), no crash |
| Errors / blockers | **None for the package.** Cosmetic/benign only: `QSocketNotifier`/`XDG_RUNTIME_DIR`/ICC-profile/translation warnings on stderr (typical for conda Qt). Notes: (a) pixi 0.83 has no `pixi add --channel`; (b) `-C_EXPORT_FMT XYZ` is rejected ("Unhandled format specifier") — `PLY` works; (c) host needed `apt install xvfb x11-apps xdotool imagemagick` for virtual display + screenshots; (d) window-close message removed the CC window; the process lingered and was ended with SIGTERM (exit 143) — not a crash |
| Cleanup status | Xvfb stopped; both apps closed; pixi's `~/.bashrc` PATH line reverted. **Test workspace intentionally kept** at `/home/user/cc-host-test` (per instructions — delete on request). Apt packages `xvfb x11-apps xdotool imagemagick` remain installed (added solely to enable the GUI test on this headless host) |

## Evidence files

| File | Content |
|---|---|
| `logs/shot1-ascii-dialog.png` | GUI after launch, pre-import state |
| `logs/shot2-cloud-loaded.png` | DB tree + rendered cloud + console log lines |
| `logs/shot3-rotated-zoomed.png` | After rotate/zoom interaction (view visibly changed) |
| `logs/shot4-ccviewer.png` | ccViewer rendering the PLY cloud |
| `logs/cli-help.stdout.log` / `cli-roundtrip.stdout.log` | Full CLI session transcripts |
| `logs/pixi-add.log` / `channel-add.log` | Install output (no solver/download/link errors) |
| `test-data/test_cube.xyz` (1000 pts), `test_cube.ply`, `roundtrip_out.ply` | Test clouds + CLI round-trip output |

All paths are relative to `/home/user/cc-host-test/`. Working project: `cloudcompare-smoke-test/` (pixi.toml pins channel + `cloudcompare=2.13.2`).
