"""HEX GRID — axial hex coordinates + fog-of-war visibility.

Pure, deterministic coordinate math (no state beyond the grid's fog map).
Coordinate system is AXIAL (q, r); the cube coordinate s = -q - r is implicit.
Neighbours are the six pointy-top directions. Fog models visibility across a
cell population:

    UNKNOWN  — fogged, never visited
    VISIBLE  — adjacent to a populated cell (can be seen, not yet entered)
    EXPLORED — populated with facts (visited, acted upon)
    OCCUPIED — an agent currently occupies this cell

This is the spatial substrate for the v0.3.0 cellular mesh. Pure stdlib.
"""
from enum import Enum
from typing import Dict, List, Tuple

# pointy-top axial directions, clockwise: E, NE, NW, W, SW, SE
DIRECTIONS: List[Tuple[int, int]] = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]


class Fog(Enum):
    UNKNOWN = "unknown"
    VISIBLE = "visible"
    EXPLORED = "explored"
    OCCUPIED = "occupied"


def neighbors(q: int, r: int) -> List[Tuple[int, int]]:
    """The six axial neighbours of (q, r)."""
    return [(q + dq, r + dr) for dq, dr in DIRECTIONS]


def distance(qa: int, ra: int, qb: int, rb: int) -> int:
    """Hex (cube) distance between two axial cells."""
    dq = qa - qb
    dr = ra - rb
    return (abs(dq) + abs(dq + dr) + abs(dr)) // 2


def ring(center: Tuple[int, int], radius: int) -> List[Tuple[int, int]]:
    """All cells exactly `radius` steps from center, clockwise order."""
    q, r = center
    if radius == 0:
        return [(q, r)]
    # step to a corner of the ring, then walk all six sides
    q += radius * DIRECTIONS[4][0]
    r += radius * DIRECTIONS[4][1]
    out: List[Tuple[int, int]] = []
    for dq, dr in DIRECTIONS:
        for _ in range(radius):
            out.append((q, r))
            q += dq
            r += dr
    return out


def spiral(center: Tuple[int, int], radius: int) -> List[Tuple[int, int]]:
    """Cells in expanding rings from center — the deterministic explore order."""
    out: List[Tuple[int, int]] = []
    for r_step in range(radius + 1):
        out.extend(ring(center, r_step))
    return out


class HexGrid:
    """A fixed-radius hex grid with a fog-of-war map over its cells."""

    def __init__(self, radius: int = 3):
        self.radius = radius
        self._fog: Dict[Tuple[int, int], Fog] = {}
        for coord in spiral((0, 0), radius):
            self._fog[coord] = Fog.UNKNOWN

    def contains(self, q: int, r: int) -> bool:
        return (q, r) in self._fog

    def fog(self, q: int, r: int) -> Fog:
        return self._fog.get((q, r), Fog.UNKNOWN)

    def set_fog(self, q: int, r: int, fog: Fog) -> None:
        if (q, r) in self._fog:
            self._fog[(q, r)] = fog

    def reveal(self, q: int, r: int) -> None:
        """Mark a cell EXPLORED and reveal its UNKNOWN neighbours as VISIBLE."""
        self.set_fog(q, r, Fog.EXPLORED)
        for nq, nr in neighbors(q, r):
            if (nq, nr) in self._fog and self._fog[(nq, nr)] is Fog.UNKNOWN:
                self._fog[(nq, nr)] = Fog.VISIBLE

    def cells_in(self, fog: Fog) -> List[Tuple[int, int]]:
        return sorted(c for c, f in self._fog.items() if f is fog)

    def counts(self) -> Dict[str, int]:
        out = {f.value: 0 for f in Fog}
        for f in self._fog.values():
            out[f.value] += 1
        return out

    def snapshot(self) -> Dict[str, str]:
        """Ordered {q,r: fog} for persistence / rendering."""
        return {f"{q},{r}": f.value for (q, r), f in sorted(self._fog.items())}
