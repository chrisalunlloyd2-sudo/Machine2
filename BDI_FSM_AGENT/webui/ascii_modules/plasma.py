"""ASCII module #5 — smooth plasma field. (2026-08-20)"""
NAME = "plasma"
W, H = 96, 22
PALETTE = " .:-=+*#%@"  # dark -> bright


def render(frame: int) -> str:
    t = frame * 0.12
    rows = []
    for y in range(H):
        line = []
        for x in range(W):
            v = (sin(x * 0.08 + t) * 0.5 + 0.5
                 + sin(y * 0.09 - t * 0.7) * 0.5 + 0.5
                 + sin((x + y) * 0.05 + t * 0.4) * 0.5 + 0.5) / 3.0
            line.append(PALETTE[int(v * (len(PALETTE) - 1))])
        rows.append("".join(line))
    return "\n".join(rows)


from math import sin
