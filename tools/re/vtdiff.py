"""vtdiff.py <vtA> <vtB> <nslots>: slots where vtables differ (read-only)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe import PE, exe_copy
p = PE(exe_copy())
a = int(sys.argv[1], 16); b = int(sys.argv[2], 16); n = int(sys.argv[3])
for i in range(n):
    x = p.u32(a + 4*i); y = p.u32(b + 4*i)
    if x != y: print('slot 0x%03X  A=0x%08X  B=0x%08X' % (4*i, x, y))
