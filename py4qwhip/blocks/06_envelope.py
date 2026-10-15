"""envelope - py4qwhip block 06 (promoted from alt\envelope_claude.py 2026-10-15). Deterministic byte container for source or code objects.

Layout: MAGIC(4) VER(1) KIND(1) ENDCAP(8) LEN(4,big) SHA256(32) BODY(LEN)
KIND 0 = utf-8 source text, 1 = marshal'd code object.
ENDCAP is reserved for the QW-7 credential tag (all zero until Alice rules).
Stdlib only. Same input -> same bytes (no timestamps).
"""
import hashlib
import marshal
import struct
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
