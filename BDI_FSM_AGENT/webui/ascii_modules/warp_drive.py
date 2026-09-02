"""ASCII module #2 — stars and galaxies, warp drive. (2026-08-17)"""
NAME = "warp_drive"
W, H = 96, 22

def _rnd(seed):
    s = seed | 0
    while True:
        s = (s * 1103515245 + 12345) & 0x7fffffff
        yield s / 0x7fffffff

_R = _rnd(4328)
STARS = [{"x": next(_R) * W, "y": next(_R) * H, "z": next(_R) + 0.1} for _ in range(60)]


def render(frame: int) -> str:
    grid = [[" "] * W for _ in range(H)]
    cx, cy = W / 2, H / 2
    for st in STARS:
        st["z"] -= 0.02
        if st["z"] <= 0.05:
            st["z"] = 1.0
            st["x"], st["y"] = next(_R) * W, next(_R) * H
        dx, dy = st["x"] - cx, st["y"] - cy
        sc = 1 / st["z"]
        px, py = cx + dx * sc, cy + dy * sc
        if not (0 <= px < W and 0 <= py < H):
            st["z"] = 1.0
            continue
        ang = atan2(dy, dx)
        ch = "-" if abs(cos(ang)) > abs(sin(ang)) else "|"
        grid[int(py)][int(px)] = "+" if st["z"] > 0.9 else ch
        if abs(dx) * sc * 0.15 > 1.4:
            px2, py2 = cx + dx * (sc - 0.4), cy + dy * (sc - 0.4)
            if 0 <= px2 < W and 0 <= py2 < H:
                grid[int(py2)][int(px2)] = ch
    # spiral galaxy overlay (two arms)
    for i in range(120):
        r = (i / 120) ** 0.6 * 10
        a = i * 0.45 + frame * 0.03
        gx, gy = cx + cos(a) * r, cy + sin(a) * r * 0.55
        if 0 <= gx < W and 0 <= gy < H:
            grid[int(gy)][int(gx)] = ".*+o"[i % 4]
    grid[int(cy)][int(cx)] = "@"
    return "\n".join("".join(r) for r in grid)


from math import atan2, cos, sin
