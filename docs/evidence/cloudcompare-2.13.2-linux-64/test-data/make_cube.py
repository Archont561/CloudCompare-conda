#!/usr/bin/env python3
"""Generate test point clouds: a 10x10x10 point cube grid (surface of a cube shell + interior grid)."""
import random

random.seed(42)
pts = []
# Full 10x10x10 grid -> 1000 points
n = 10
for i in range(n):
    for j in range(n):
        for k in range(n):
            pts.append((i * 0.5, j * 0.5, k * 0.5))

with open("/home/user/cc-host-test/test-data/test_cube.xyz", "w") as f:
    for x, y, z in pts:
        f.write(f"{x:.3f} {y:.3f} {z:.3f}\n")

# Same cloud as binary-free PLY (no import dialog in CloudCompare)
with open("/home/user/cc-host-test/test-data/test_cube.ply", "w") as f:
    f.write("ply\nformat ascii 1.0\n")
    f.write(f"element vertex {len(pts)}\n")
    f.write("property float x\nproperty float y\nproperty float z\n")
    f.write("property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
    for x, y, z in pts:
        r = int(255 * x / 4.5)
        g = int(255 * y / 4.5)
        b = int(255 * z / 4.5)
        f.write(f"{x:.3f} {y:.3f} {z:.3f} {r} {g} {b}\n")

print(f"Wrote {len(pts)} points to test_cube.xyz and test_cube.ply")
