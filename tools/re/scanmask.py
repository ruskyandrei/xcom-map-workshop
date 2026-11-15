import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe import PE, exe_copy, func_start
p = PE(exe_copy())
n, va, vsz, rp, rs = p.sec('.text')
t = p.b[rp:rp+rs]
# or byte [r+13Ch],10h : 80 /1 (modrm 0x88-0x8F) 3C 01 00 00 10 ; or dword: 83 /1 ... 10 or 81 /1 ... 10 00 00 00
pats = [rb'\x80[\x88-\x8b\x8d-\x8f]\x3c\x01\x00\x00\x10', rb'\x83[\x88-\x8b\x8d-\x8f]\x3c\x01\x00\x00\x10', rb'\x81[\x88-\x8b\x8d-\x8f]\x3c\x01\x00\x00\x10\x00\x00\x00']
for pt in pats:
    for m in re.finditer(pt, t):
        a = va + m.start(); print('set 0x10 at 0x%X in func 0x%X' % (a, func_start(p, a) or 0))
