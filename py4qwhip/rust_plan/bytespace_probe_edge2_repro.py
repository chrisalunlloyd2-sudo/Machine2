import json, struct, importlib.util, sys
FIXTURE = r"C:\Viper\projects\py4qwhip\rust_plan\bytespace_probe_edge2.json"
spec = importlib.util.spec_from_file_location("b01", r"C:\Viper\projects\py4qwhip\blocks\01_bytespace.py")
b01 = importlib.util.module_from_spec(spec); spec.loader.exec_module(b01)
out = {}
def t(label, fn):
    try:
        out[label] = {"ok": True, "v": fn()}
    except Exception as e:
        out[label] = {"ok": False, "etype": type(e).__name__, "estr": str(e)}
t("a39_hash_nlocals_256", lambda: b01.content_hash({"magic": "PY4QW01", "version": 1, "name": "x", "nlocals": 256, "const_pool": [], "code": b"\x0e"}))
t("a40_hash_q_negoverflow", lambda: b01.content_hash({"magic": "PY4QW01", "version": 1, "name": "x", "nlocals": 2, "const_pool": [-2**63 - 1], "code": b"\x0e"}))
t("a41_hash_q_min_edge", lambda: b01.content_hash({"magic": "PY4QW01", "version": 1, "name": "x", "nlocals": 2, "const_pool": [-2**63], "code": b"\x0e"}))
t("a42_hash_q_max_edge", lambda: b01.content_hash({"magic": "PY4QW01", "version": 1, "name": "x", "nlocals": 2, "const_pool": [2**63 - 1], "code": b"\x0e"}))
t("a43_hash_namelen_big", lambda: b01.content_hash({"magic": "PY4QW01", "version": 1, "name": "x" * 70000, "nlocals": 2, "const_pool": [], "code": b"\x0e"}))
t("a44_hash_float_nan", lambda: b01.content_hash({"magic": "PY4QW01", "version": 1, "name": "x", "nlocals": 2, "const_pool": [float("nan")], "code": b"\x0e"}))
t("a45_hash_float_inf", lambda: b01.content_hash({"magic": "PY4QW01", "version": 1, "name": "x", "nlocals": 2, "const_pool": [float("inf")], "code": b"\x0e"}))
t("a46_hash_float_neg0", lambda: b01.content_hash({"magic": "PY4QW01", "version": 1, "name": "x", "nlocals": 2, "const_pool": [-0.0], "code": b"\x0e"}))
t("a47_asm_reg_neg", lambda: b01.assemble("load_const r-1, 5\nhalt\n", name="q", nlocals=4))
t("a48_asm_r_bare", lambda: b01.assemble("load_const r, 5\nhalt\n", name="q", nlocals=4))
t("a49_asm_reg_plus", lambda: b01.assemble("load_const r+2, 5\nhalt\n", name="q", nlocals=4))
t("a50_asm_reg_space", lambda: b01.assemble("load_const r 5, 5\nhalt\n", name="q", nlocals=4))
t("a51_asm_const_regword", lambda: b01.assemble("load_const r0, red\nhalt\n", name="q", nlocals=2))
t("a52_asm_const_dblq_reg", lambda: b01.assemble('load_const r0, "r7"\nhalt\n', name="q", nlocals=2))
t("a53_asm_const_empty", lambda: b01.assemble("load_const r0, ''\nhalt\n", name="q", nlocals=2)["const_pool"])
t("a54_asm_const_plus5", lambda: b01.assemble("load_const r0, +5\nhalt\n", name="q", nlocals=2)["const_pool"])
t("a55_asm_const_minusminus", lambda: b01.assemble("load_const r0, --5\nhalt\n", name="q", nlocals=2))
t("a56_asm_const_ws", lambda: b01.assemble("load_const r0, ' 5'\nhalt\n", name="q", nlocals=2)["const_pool"])
t("a57_asm_float", lambda: b01.assemble("load_const r0, 5.5\nhalt\n", name="q", nlocals=2)["const_pool"])
t("a58_asm_label_eq", lambda: b01.assemble("x :\nhalt\n", name="q", nlocals=2))
t("a59_validate_reg_eq", lambda: (b01.validate(b01.assemble("add r255, r0, r1\nhalt\n", name="q", nlocals=256)), "ok")[1])
t("a60_validate_reg_gt", lambda: b01.validate({"magic": "PY4QW01", "version": 1, "name": "x", "nlocals": 2, "const_pool": [1], "code": bytes([0x01, 0, 0, 0])}))
t("a61_validate_trunc", lambda: b01.validate({"magic": "PY4QW01", "version": 1, "name": "x", "nlocals": 2, "const_pool": [], "code": b"\x01\x00"}))
t("a62_validate_badopc", lambda: b01.validate({"magic": "PY4QW01", "version": 1, "name": "x", "nlocals": 2, "const_pool": [], "code": b"\x99"}))
t("a63_validate_jump_neg", lambda: b01.validate({"magic": "PY4QW01", "version": 1, "name": "x", "nlocals": 2, "const_pool": [], "code": b"\x09\xff\xff\x0e"}))
t("a64_pool_nan_dedupe", lambda: b01.assemble("load_const r0, 5\nhalt\n", name="q", nlocals=2, const_extra=[float("nan"), float("nan")])["const_pool"])
t("a65_int_err_repr", lambda: int("5x"))
t("a66_struct_ubyte", lambda: struct.pack("<B", 256))
fresh = json.dumps(out, default=lambda o: "<%s: %r>" % (type(o).__name__, o))
gold = open(FIXTURE, encoding="utf-8").read()
try:
    gf = json.loads(gold); ff = json.loads(fresh)
except Exception as e:
    print("PARSEFAIL", e); sys.exit(1)
mismatch = []
for k in gf:
    if k not in ff:
        mismatch.append((k, "MISSING"))
    elif json.dumps(gf[k], sort_keys=True) != json.dumps(ff[k], sort_keys=True):
        mismatch.append((k, json.dumps(gf[k], sort_keys=True)[:260] + "  ||  " + json.dumps(ff[k], sort_keys=True)[:260]))
extra = [k for k in ff if k not in gf]
print("KEYS_GOLD", len(gf), "KEYS_FRESH", len(ff), "EXTRA", extra[:5])
print("MISMATCH_COUNT", len(mismatch))
for k, d in mismatch[:8]:
    print("MM", k, d)
print("DIFF_PARSED", (not mismatch) and (not extra))
print("DIFF_STRING", fresh.strip() == gold.strip())
print("A41_FRESH", json.dumps(ff.get("a41_hash_q_min_edge")))
print("A42_FRESH", json.dumps(ff.get("a42_hash_q_max_edge")))
print("A40_FRESH", json.dumps(ff.get("a40_hash_q_negoverflow")))