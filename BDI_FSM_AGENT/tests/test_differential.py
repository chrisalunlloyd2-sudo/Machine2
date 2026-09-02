from bdi_fsm.differential import deltas, integrate, derive, encode, decode, roundtrip_ok


def test_roundtrip():
    s = [0, 1, 3, 6, 10, 15, 21]  # triangular numbers
    assert roundtrip_ok(s)
    assert decode(encode(s)) == s


def test_integrate_reconstructs():
    speed = [1, 2, 3, 4, 5, 6]  # deltas
    assert integrate(speed, 0) == [0, 1, 3, 6, 10, 15, 21]


def test_derive_acceleration():
    pos = [0, 1, 4, 9, 16, 25]   # t^2
    speed = derive(pos, 1)       # 2t-1
    accel = derive(pos, 2)       # constant 2
    assert speed == [1, 3, 5, 7, 9]
    assert accel == [2, 2, 2, 2]


def test_store_speed_saves_compute():
    # store only speed (deltas) + initial; reconstruct position by integration
    pos = [0.0, 1.5, 3.0, 4.5, 6.0]
    enc = encode(pos)
    assert len(enc["deltas"]) == len(pos) - 1
    assert decode(enc) == pos
