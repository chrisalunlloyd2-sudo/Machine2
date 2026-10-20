
import json, importlib.util
spec = importlib.util.spec_from_file_location('b01', r'C:\Viper\projects\py4qwhip\blocks\01_bytespace.py')
b01 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b01)
out = {}
cases = [
    ('plus2', 'load_const r0 +2\nhalt'),
    ('dashdash5', 'load_const r0 --5\nhalt'),
    ('negint', 'load_const r0 -7\nhalt'),
    ('badreg', 'load_const r0 zz\nhalt'),
    ('badreg_r9x', 'load_const r9x\nhalt'),
    ('floatlit', 'load_const r0 3.5\nhalt'),
    ('pool_plus2', 'load_const r0 1\n\nconst r0 0\n+2'),
    ('pool_minus', 'load_const r0 1\n\nconst r0 0\n-3'),
    ('biglit_const', 'load_const r0 1\n\nconst r0 0\n10000000000000000000000000000000000000000'),
]
for label, text in cases:
    try:
        p = b01.assemble(text, name='probe')
        out[label] = {'ok': True, 'pool': [[repr(v), type(v).__name__] for v in p['const_pool']]}
    except Exception as e:
        out[label] = {'ok': False, 'err': '%s: %s' % (type(e).__name__, e)}
open(r'C:\Users\viper\AppData\Local\hermes\cache\scratch\int_semantics_out.json', 'w').write(json.dumps(out, indent=1))
print('OK', len(out))
