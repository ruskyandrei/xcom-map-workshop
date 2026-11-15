import os, sys, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe import PE, exe_copy
p = PE(exe_copy())
n, va, vsz, rp, rs = p.sec('.text')
t = p.b[rp:rp+rs]
from collections import Counter
c = Counter()
# test dword ptr [r32+0x214], imm32 : F7 /0 with modrm mod=10 reg=000 -> 0x80..0x87 (excl 0x84 sib)
for m in re.finditer(rb'\xf7[\x80-\x83\x85-\x87]\x14\x02\x00\x00(....)', t, re.S):
    c[('dword', struct.unpack('<I', m.group(1))[0])] += 1
for m in re.finditer(rb'\xf6[\x80-\x83\x85-\x87]([\x14-\x17])\x02\x00\x00(.)', t, re.S):
    c[('byte+%d' % (m.group(1)[0]-0x14), m.group(2)[0])] += 1
for k, v in sorted(c.items(), key=lambda x: -x[1])[:40]: print(k, hex(k[1]), v)
