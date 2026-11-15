"""Read-only: maps every UE3 native function of a copy of XComEW.exe to its code address.
UE3 registers each class's natives as {const char* "<Class>exec<Func>", void* Func} pairs in .data; this finds the
name strings in .rdata, the pairs pointing at them, and writes name -> address.
Usage: python natives.py <exe copy> <out.tsv>"""
import sys, re, struct
from pe import PE
p = PE(sys.argv[1])
names = {}
for m in re.finditer(rb'([AUF][A-Za-z0-9_]{1,60}?)(exec[A-Za-z0-9_]{2,80})\0', p.b):
    v = p.off2va(m.start())
    if v: names[v] = (m.group(1).decode(), m.group(2).decode())
n, dva, dvsz, drp, drs = p.sec('.data')
t = p.sec('.text')
rows = []
blob = p.b[drp:drp + drs]
for i in range(0, len(blob) - 8, 4):
    s = struct.unpack_from('<I', blob, i)[0]
    if s in names:
        f = struct.unpack_from('<I', blob, i + 4)[0]
        if t[1] <= f < t[1] + t[2]:
            rows.append((names[s][0], names[s][1][4:], f, dva + i))
with open(sys.argv[2], 'w') as o:
    o.write('class\tfunction\taddress\ttable_entry\n')
    for c, f, a, e in sorted(rows):
        o.write('%s\t%s\t0x%08X\t0x%08X\n' % (c, f, a, e))
print('%d natives mapped of %d name strings -> %s' % (len(rows), len(names), sys.argv[2]))
