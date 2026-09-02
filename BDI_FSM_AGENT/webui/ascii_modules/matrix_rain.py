"""ASCII module #4 — the code rain. (2026-08-19)"""
NAME = "matrix_rain"
W, H = 96, 22
CHARS = "01<>/\\|_+*#@$%&="


def _rnd(seed):
    s = seed | 0
    while True:
        s = (s * 1664525 + 1013904223) & 0xffffffff
        yield s / 0xffffffff


_R = _rnd(7)
DROPS = [{"y": int(next(_R) * H), "v": 0.2 + next(_R) * 0.5, "len": 2 + int(next(_R) * 5)}
         for _ in range(40)]


def render(frame: int) -> str:
    grid = [[" "] * W for _ in range(H)]
    for d in DROPS:
        d["y"] += d["v"]
        if d["y"] - d["len"] > H:
            d["y"] = -int(next(_R) * 3)
        col = int(next(_R) * W)
        for k in range(d["len"]):
            yy = int(d["y"]) - k
            if 0 <= yy < H:
                ch = CHARS[int(next(_R) * len(CHARS))]
                grid[yy][col] = ch if k == 0 else ch.lower()
    return "\n".join("".join(r) for r in grid)


