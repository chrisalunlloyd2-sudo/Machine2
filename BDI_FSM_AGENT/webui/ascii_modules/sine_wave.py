"""ASCII module #1 — the classic traveling sine wave. (2026-08-16)"""
NAME = "sine_wave"
W, H = 96, 22
AMP = 8
FREQ = 0.22


def render(frame: int) -> str:
    phase = frame * 0.35
    rows = []
    for y in range(H):
        line = [" "] * W
        # main wave: travels right with phase
        for x in range(W):
            v = AMP * sin((x * FREQ) + phase) + y * 0.12
            yy = int(H / 2 + v)
            if 0 <= yy < H and yy == y:
                line[x] = "~"
        # secondary wave (cosine) offset — the echo
        for x in range(W):
            v = AMP * 0.6 * cos((x * FREQ * 1.3) + phase * 0.8) + y * 0.12
            yy = int(H / 2 + v)
            if 0 <= yy < H and yy == y:
                line[x] = "·" if line[x] == " " else "+"
        rows.append("".join(line))
    return "\n".join(rows)


from math import cos, sin
