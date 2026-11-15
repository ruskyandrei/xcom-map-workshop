import os, sys, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe import PE, exe_copy
p = PE(exe_copy())
n, va, vsz, rp, rs = p.sec('.text')
t = p.b[rp:rp+rs]
for m in re.finditer(rb'\xf7[\x80-\x83\x85-\x87]\x14\x02\x00\x00(....)', t, re.S):
    v = struct.unpack('<I', m.group(1))[0]
    if v in (0x1000, 0x2000, 0x80000):
        print(hex(v), hex(va + m.start()))
for m in re.finditer(rb'\xf6[\x80-\x83\x85-\x87]\x14\x02\x00\x00\x80', t, re.S):
    print('byte80', hex(va + m.start()))
