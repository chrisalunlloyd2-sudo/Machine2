"""Hex grid + fog-of-war tests (pure, deterministic)."""
from bdi_fsm.hex_grid import (Fog, HexGrid, DIRECTIONS, distance, neighbors,
                              ring, spiral)


def test_neighbors_are_six_axial():
    n = neighbors(0, 0)
    assert len(n) == 6
    assert set(n) == set(DIRECTIONS)
    # each neighbour is distance 1 away
    for q, r in n:
        assert distance(0, 0, q, r) == 1


def test_distance_is_hex_metric():
    assert distance(0, 0, 0, 0) == 0
    assert distance(0, 0, 1, -1) == 1
    assert distance(0, 0, 2, -1) == 2
    assert distance(1, 0, -1, 1) == 2   # symmetric-ish across origin


def test_ring_and_spiral_sizes():
    assert ring((0, 0), 0) == [(0, 0)]
    assert len(ring((0, 0), 1)) == 6
    assert len(ring((0, 0), 2)) == 12
    assert len(spiral((0, 0), 2)) == 19   # 1 + 6 + 12


def test_grid_populates_fog_on_reveal():
    g = HexGrid(radius=2)
    assert g.counts()["unknown"] == 19
    g.reveal(0, 0)
    c = g.counts()
    assert c["explored"] == 1
    assert c["visible"] == 6
    assert c["unknown"] == 12
    # revealing a neighbour fills in more
    g.reveal(1, 0)
    c = g.counts()
    assert c["explored"] == 2


def test_occupy_endpoint():
    g = HexGrid(radius=1)
    g.set_fog(0, 0, Fog.OCCUPIED)
    assert g.fog(0, 0) is Fog.OCCUPIED
    assert (0, 0) in g.cells_in(Fog.OCCUPIED)


def test_snapshot_is_ordered_strings():
    g = HexGrid(radius=1)
    snap = g.snapshot()
    assert snap["0,0"] == "unknown"
    assert len(snap) == 7
