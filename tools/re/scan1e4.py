import os, sys, re, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe import PE, exe_copy, func_start
p = PE(exe_copy())
n, va, vsz, rp, rs = p.sec('.text')
t = p.b[rp:rp+rs]
seen = {}
# mov r32,[r32+0x1E4] (8B modrm disp32) followed within 24 bytes by call r32 (FF D0..D7)
for m in re.finditer(rb'\x8b[\x80-\x87\x88-\x8f\x90-\x97\x98-\x9f\xa8-\xaf\xb0-\xb7\xb8-\xbf]\xe4\x01\x00\x00', t):
    i = m.start()
    if re.search(rb'\xff[\xd0-\xd7]', t[i+6:i+30]):
        a = va + i
        f = func_start(p, a)
        seen.setdefault(f, []).append(a)
for f, l in sorted(seen.items()):
    print('func 0x%08X sites %s' % (f or 0, ' '.join('0x%X' % x for x in l)))
