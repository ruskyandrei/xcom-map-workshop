import os, sys, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe import PE, exe_copy, func_start
p = PE(exe_copy())
n, va, vsz, rp, rs = p.sec('.text')
t = p.b[rp:rp+rs]
fs = {}
# test byte ptr [r+13Ch],4  : F6 4x/8x 3C 01 00 00 04
for m in re.finditer(rb'\xf6[\x80-\x83\x85-\x87]\x3c\x01\x00\x00\x04', t):
    a = va + m.start(); f = func_start(p, a); fs.setdefault(f, []).append(a)
for f, l in sorted(fs.items()):
    print('0x%08X %s' % (f or 0, ' '.join('0x%X' % x for x in l)))
