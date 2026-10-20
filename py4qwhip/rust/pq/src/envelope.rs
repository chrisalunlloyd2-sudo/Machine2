//! envelope -- py4qwhip block 06 (byte container), Rust port.
//! Reference: ../../blocks/06_envelope.py  |  Plan: rust_plan/RUST_PORT_PLAN_20261014.md (step 4)
//! Layout: MAGIC(4)=PYQW VER(1) KIND(1) ENDCAP(8) LEN(4,big) SHA256(32) BODY(LEN)
//! KIND 0 = utf-8 source text, 1 = marshal'd code object (CPython-version-bound —
//! Rust validates kind-1 blobs structurally but does NOT decode them; that decision
//! is Alice's, plan risk #2). The ENDCAP sits OUTSIDE the checksum on purpose: it is
//! the QW-7 credential slot, tampering with it is not a checksum error.
//! Deterministic, no I/O, no timestamps. Errors mirror the Python message text.
use sha2::{Digest, Sha256};

pub const MAGIC: &[u8] = b"PYQW";
pub const VERSION: u8 = 1;
pub const KIND_SOURCE: u8 = 0;
pub const KIND_CODE: u8 = 1;
pub const HEADER_ENDCAP_RESERVED: [u8; 8] = [0; 8];
const HDR: usize = 50; // 4s + B + B + 8s + I + 32s, big-endian
const MAX_BODY: usize = 64 * 1024 * 1024;

#[derive(Debug, PartialEq)]
pub struct EnvelopeError(pub String);
fn err<T>(m: impl Into<String>) -> Result<T, EnvelopeError> {
    Err(EnvelopeError(m.into()))
}

fn sha256_hex_or_digest(body: &[u8]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(body);
    h.finalize().into()
}

/// Mirrors encode() for source text (KIND 0). Same input -> same bytes.
pub fn encode_source(text: &str, endcap: &[u8; 8]) -> Result<Vec<u8>, EnvelopeError> {
    let body = text.as_bytes();
    if body.len() > MAX_BODY {
        return err("body too large");
    }
    let mut o = Vec::with_capacity(HDR + body.len());
    o.extend_from_slice(MAGIC);
    o.push(VERSION);
    o.push(KIND_SOURCE);
    o.extend_from_slice(endcap);
    o.extend_from_slice(&(body.len() as u32).to_be_bytes());
    o.extend_from_slice(&sha256_hex_or_digest(body));
    o.extend_from_slice(body);
    Ok(o)
}

/// Mirrors inspect(): full validation, returns (kind, endcap, body).
/// The endcap is returned but deliberately NOT checksum-verified.
pub fn inspect(blob: &[u8]) -> Result<(u8, [u8; 8], &[u8]), EnvelopeError> {
    if blob.len() < HDR {
        return err("too short to be a byte-space blob");
    }
    let magic = &blob[0..4];
    if magic != MAGIC {
        return err("bad magic");
    }
    let ver = blob[4];
    if ver != VERSION {
        return err(format!("unsupported version {ver}"));
    }
    let kind = blob[5];
    if kind != KIND_SOURCE && kind != KIND_CODE {
        return err(format!("unknown kind {kind}"));
    }
    let mut endcap = [0u8; 8];
    endcap.copy_from_slice(&blob[6..14]);
    let length = u32::from_be_bytes([blob[14], blob[15], blob[16], blob[17]]) as usize;
    let body = &blob[HDR..];
    if length != body.len() || length > MAX_BODY {
        return err("length mismatch");
    }
    let digest: [u8; 32] = blob[18..50].try_into().unwrap();
    if sha256_hex_or_digest(body) != digest {
        return err("checksum mismatch (corrupt)");
    }
    Ok((kind, endcap, body))
}

/// Mirrors decode() for KIND 0 blobs (the only kind Rust decodes).
pub fn decode_source(blob: &[u8]) -> Result<String, EnvelopeError> {
    let (kind, _endcap, body) = inspect(blob)?;
    if kind != KIND_SOURCE {
        return err("body is not a code object"); // kind-1 decode stays with CPython (Alice's call)
    }
    match std::str::from_utf8(body) {
        Ok(s) => Ok(s.to_string()),
        Err(_) => err("body is not utf-8"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_and_reserved_endcap() {
        let blob = encode_source("print(\"hi\")\n", &HEADER_ENDCAP_RESERVED).unwrap();
        let (kind, endcap, body) = inspect(&blob).unwrap();
        assert_eq!(kind, KIND_SOURCE);
        assert_eq!(endcap, HEADER_ENDCAP_RESERVED);
        assert_eq!(body, b"print(\"hi\")\n");
        assert_eq!(decode_source(&blob).unwrap(), "print(\"hi\")\n");
    }

    #[test]
    fn tamper_body_caught_endcap_not() {
        let blob = encode_source("hi", &HEADER_ENDCAP_RESERVED).unwrap();
        let mut bad = blob.clone();
        bad[26] ^= 0x01; // first sha256 byte — same flip the Python selftest uses
        assert!(inspect(&bad)
            .unwrap_err()
            .0
            .contains("checksum mismatch (corrupt)"));
        let mut ec = blob.clone();
        ec[7] ^= 0x01; // endcap byte — NOT covered by the digest, by design
        let (_k, endcap, _b) = inspect(&ec).unwrap();
        assert_ne!(endcap, HEADER_ENDCAP_RESERVED);
    }
}
