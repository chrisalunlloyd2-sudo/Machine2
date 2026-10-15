"""Acceptance tests for py4qwhip block 1 (byte_space). Claude-authored contract.
Run: python -I C:\Viper\projects\py4qwhip\tests\test_byte_space.py
Loads blocks\byte_space.py by file path (no sys.path edits)."""
import importlib.util, os, sys, unittest, ast
HERE = os.path.dirname(os.path.abspath(__file__))
BLOCK = os.path.join(HERE, "..", "blocks", "06_envelope.py")
SCRIPTS = r"C:\Viper\scripts"

def load():
    spec = importlib.util.spec_from_file_location("byte_space", BLOCK)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def sample_sources(n=20):
    out = []
    for fn in sorted(os.listdir(SCRIPTS)):
        if not fn.endswith(".py"): continue
        try:
            src = open(os.path.join(SCRIPTS, fn), encoding="utf-8").read()
            for node in ast.parse(src).body:
                if isinstance(node, ast.FunctionDef):
                    seg = ast.get_source_segment(src, node)
                    if seg and len(seg) < 3000: out.append(seg)
                    break
        except Exception: continue
        if len(out) >= n: break
    return out

class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.m = load()
    def test_1_roundtrip_source(self):
        s = "def f(a, b):\n    return a + b\n"
        self.assertEqual(self.m.decode(self.m.encode(s)), s)
    def test_2_roundtrip_20_real_functions(self):
        srcs = sample_sources(20); self.assertGreaterEqual(len(srcs), 20)
        for s in srcs: self.assertEqual(self.m.decode(self.m.encode(s)), s)
    def test_3_deterministic(self):
        s = "def g(x):\n    return x * 2\n"
        self.assertEqual(self.m.encode(s), self.m.encode(s))
    def test_4_corrupt_gives_clear_error(self):
        b = bytearray(self.m.encode("def h():\n    return 1\n"))
        for i in (0, len(b) // 2, len(b) - 1):
            c = bytearray(b); c[i] ^= 0xFF
            try: self.m.decode(bytes(c))
            except Exception as e: self.assertNotIsInstance(e, (MemoryError, RecursionError))
        with self.assertRaises(Exception): self.m.decode(b"")
    def test_5_stdlib_only(self):
        src = open(BLOCK, encoding="utf-8").read()
        self.assertNotIn("sys.path", src)
        for bad in ("import requests", "import socket", "urllib"): self.assertNotIn(bad, src)
    def test_6_reserved_header_field(self):
        self.assertTrue(hasattr(self.m, "HEADER_ENDCAP_RESERVED"))

if __name__ == "__main__": unittest.main(verbosity=2)
