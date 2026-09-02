from bdi_fsm.hdc import (Hypervector, code_signature, same_code_gate,
                         similarity_ban, CodeSignatureStore)

D = 256  # small dim for fast, deterministic tests


def test_bind_is_self_inverse():
    x = Hypervector.from_string("role", D)
    y = Hypervector.from_string("filler", D)
    bound = x.bind(y)
    recovered = bound.bind(y)  # x ^ y ^ y == x (y^2 == 1)
    assert recovered.cosine(x) == 1.0


def test_bundle_similar_to_constituents():
    a = Hypervector.from_string("aaa", D)
    b = Hypervector.from_string("bbb", D)
    c = Hypervector.from_string("ccc", D)
    bundle = Hypervector.bundle_many([a, b, c], D)
    assert bundle.cosine(a) > 0
    assert bundle.cosine(b) > 0
    assert bundle.cosine(c) > 0


def test_permute_is_orthogonal():
    x = Hypervector.from_string("seq", D)
    assert abs(x.cosine(x.permute(1))) < 0.3


def test_code_signature_similarity():
    code = "def foo(a, b):\n    return a + b\n" * 10
    same = code
    near = code.replace("foo", "bar")  # tiny edit
    diff = "class Widget:\n    pass\n" * 20
    s_same = code_signature(same, D).cosine(code_signature(code, D))
    s_near = code_signature(near, D).cosine(code_signature(code, D))
    s_diff = code_signature(diff, D).cosine(code_signature(code, D))
    assert s_same == 1.0
    assert s_near > s_diff  # near is more similar than unrelated


def test_similarity_ban_monotonic():
    assert similarity_ban(0.9) > similarity_ban(0.5) > similarity_ban(0.0)


def test_same_code_gate_fires_on_high_similarity():
    assert same_code_gate(0.9, c_miss=1000.0, c_false=1.0) is True
    assert same_code_gate(-0.5, c_miss=1000.0, c_false=1.0) is False


def test_signature_store_dedupes():
    store = CodeSignatureStore(D=D, c_miss=1000.0, c_false=1.0)
    code = "def handler(req):\n    return req.data\n" * 10
    store.add("mod_1", code)
    r = store.lookup(code)
    assert r["duplicate"] is True and r["best_id"] == "mod_1"
    other = store.lookup("class A:\n    pass\n" * 20)
    assert other["duplicate"] is False
