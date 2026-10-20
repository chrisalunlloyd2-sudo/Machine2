r"""envelope - py4qwhip block 06 (promoted from alt\envelope_claude.py 2026-10-15). Deterministic byte container for source or code objects.

Layout: MAGIC(4) VER(1) KIND(1) ENDCAP(8) LEN(4,big) SHA256(32) BODY(LEN)
KIND 0 = utf-8 source text, 1 = marshal'd code object.
ENDCAP is reserved for the QW-7 credential tag (all zero until Alice rules).
Stdlib only. Same input -> same bytes (no timestamps).
"""
import hashlib
import json
import marshal
import struct
import sys
import types

MAGIC = b"PYQW"
VERSION = 1
KIND_SOURCE, KIND_CODE = 0, 1
HEADER_ENDCAP_RESERVED = b"\x00" * 8
_HDR = struct.Struct(">4sBB8sI32s")
_MAX_BODY = 64 * 1024 * 1024


class ByteSpaceError(ValueError):
    """Raised for any malformed or corrupt byte-space blob."""


def encode(obj, endcap=HEADER_ENDCAP_RESERVED):
    if isinstance(obj, str):
        kind, body = KIND_SOURCE, obj.encode("utf-8")
    elif isinstance(obj, types.CodeType):
        kind, body = KIND_CODE, marshal.dumps(obj)
    else:
        raise ByteSpaceError("encode wants str or code object, got %s" % type(obj).__name__)
    if len(endcap) != 8:
        raise ByteSpaceError("endcap must be 8 bytes")
    if len(body) > _MAX_BODY:
        raise ByteSpaceError("body too large")
    return _HDR.pack(MAGIC, VERSION, kind, endcap, len(body), hashlib.sha256(body).digest()) + body


def inspect(blob):
    """Return (kind, endcap, body) after full validation."""
    if not isinstance(blob, (bytes, bytearray)) or len(blob) < _HDR.size:
        raise ByteSpaceError("too short to be a byte-space blob")
    magic, ver, kind, endcap, length, digest = _HDR.unpack_from(blob)
    if magic != MAGIC:
        raise ByteSpaceError("bad magic")
    if ver != VERSION:
        raise ByteSpaceError("unsupported version %d" % ver)
    if kind not in (KIND_SOURCE, KIND_CODE):
        raise ByteSpaceError("unknown kind %d" % kind)
    body = bytes(blob[_HDR.size:])
    if length != len(body) or length > _MAX_BODY:
        raise ByteSpaceError("length mismatch")
    if hashlib.sha256(body).digest() != digest:
        raise ByteSpaceError("checksum mismatch (corrupt)")
    return kind, bytes(endcap), body


def decode(blob):
    kind, _endcap, body = inspect(blob)
    if kind == KIND_SOURCE:
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ByteSpaceError("body is not utf-8") from exc
    try:
        code = marshal.loads(body)
    except Exception as exc:
        raise ByteSpaceError("body is not a code object") from exc
    if not isinstance(code, types.CodeType):
        raise ByteSpaceError("body is not a code object")
    return code


# ---------------------------------------------------- additive selftest (07)
# Block 06 shipped silent (no __main__); block 07's battery needs a printable
# verdict. Additive only: exercise the public surface, no logic changes.

def selftest() -> dict:
    checks = {}
    text = 'print("hi")\n'
    checks["roundtrip_source"] = decode(encode(text)) == text
    checks["tamper_caught"] = False
    blob = encode(text)
    bad = blob[:26] + bytes([blob[26] ^ 0x01]) + blob[27:]
    try:
        inspect(bad)
    except ByteSpaceError:
        checks["tamper_caught"] = True
    except Exception:
        checks["tamper_caught"] = False
    checks["kind_source"] = inspect(encode(text))[0] == 0
    return {"ok": all(checks.values()), "name": "envelope_additive",
            "checks": checks}


if __name__ == "__main__":
    r = selftest()
    print(json.dumps(r, default=str))
    sys.exit(0 if r["ok"] else 1)
