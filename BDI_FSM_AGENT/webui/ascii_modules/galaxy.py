"""ASCII module #3 — rotating spiral galaxy. (2026-08-18)"""
NAME = "galaxy"
W, H = 96, 22
ARMS = 2
RMAX = 11.0


def render(frame: int) -> str:
    grid = [[" "] * W for _ in range(H)]
    cx, cy = W / 2, H / 2
    t = frame * 0.05
    for i in range(260):
        r = (i / 260) ** 0.55 * RMAX
        for arm in range(ARMS):
            a = i * 0.33 + arm * pi + t * (1.0 - r / RMAX * 0.6)
            x, y = cx + cos(a) * r, cy + sin(a) * r * 0.5
            if 0 <= x < W and 0 <= y < H:
                d = abs(r - RMAX) / RMAX  # dimmer at edge
                ch = "#*+o."[max(0, min(4, int(d * 5)))]
                grid[int(y)][int(x)] = ch
    # galactic core
    for r in range(3):
        for a in range(12):
            x, y = cx + cos(a / 12 * 2 * pi) * r, cy + sin(a / 12 * 2 * pi) * r * 0.6
            if 0 <= x < W and 0 <= y < H:
                grid[int(y)][int(x)] = "@" if r == 0 else "%"
    return "\n".join("".join(r) for r in grid)


from math import cos, pi, sin
