
import importlib.util, json, struct, hashlib
spec = importlib.util.spec_from_file_location("b06", r"C:\Viper\projects\py4qwhip\blocks\06_envelope.py")
b06 = importlib.util.module_from_spec(spec); spec.loader.exec_module(b06)

def first_inspect_err(b):
    try:
        b06.inspect(b); return None
    except b06.ByteSpaceError as e: return str(e)
    except Exception as e: return "UNEXPECTED:" + type(e).__name__

def first_decode_err(b):
    try:
        b06.decode(b); return None
    except b06.ByteSpaceError as e: return str(e)
    except Exception as e: return "UNEXPECTED:" + type(e).__name__

ok, corrupt = [], []
def add_ok(name, text, endcap):
    blob = b06.encode(text, endcap)
    kind, enc, body = b06.inspect(blob)
    assert kind == 0 and enc == endcap and body == text.encode("utf-8")
    ok.append({"name": name, "text": text, "endcap": endcap.hex(), "blob": blob.hex()})

add_ok("empty", "", b"\x00" * 8)
add_ok("hi", 'print("hi")\n', b"\x00" * 8)
add_ok("unicode", "h\u00e9llo \u2014 \u4e2d\n", bytes(range(1, 9)))
add_ok("long4096", "A" * 4096, b"QW7QW7QW")

bad = b06.encode('print("hi")\n')
def add_c(name, blob):
    corrupt.append({"name": name, "blob": blob.hex(),
                    "inspect_error": first_inspect_err(blob), "decode_error": first_decode_err(blob)})

add_c("bad_magic", b"XXXX" + bad[4:])
add_c("bad_version", bad[:4] + bytes([2]) + bad[5:])
add_c("unknown_kind", bad[:5] + bytes([5]) + bad[6:])
add_c("length_mismatch", bad[:14] + bytes([bad[14] ^ 0x01]) + bad[15:])
add_c("checksum_mismatch_body", bad[:-1] + bytes([bad[-1] ^ 0x01]))
add_c("checksum_mismatch_digest", bad[:26] + bytes([bad[26] ^ 0x01]) + bad[27:])
add_c("too_short", bad[:49])
add_c("non_utf8_body", (lambda body: struct.pack(">4sBB8sI32s", b"PYQW", 1, 0, b"\x00" * 8, len(body),
        hashlib.sha256(body).digest()) + body)(b"\xff\xfe."))
add_c("endcap_flip_not_caught", bad[:7] + bytes([bad[7] ^ 0x01]) + bad[8:])

doc = {"generated": "2026-10-16", "by": "python reference blocks/06_envelope.py (PY311)",
       "layout": "MAGIC(4)=PYQW VER(1) KIND(1) ENDCAP(8) LEN(4,big) SHA256(32) BODY(LEN)", "ok": ok, "corrupt": corrupt}
out = r"C:\Viper\projects\py4qwhip\rust_plan\envelope_golden.json"
with open(out, "w", encoding="utf-8") as f: json.dump(doc, f, indent=1)
print("ok_cases", len(ok), "corrupt", len(corrupt))
for c in corrupt: print(c["name"], "?", c["inspect_error"], "| decode:", c["decode_error"])
