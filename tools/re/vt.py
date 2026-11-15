"""vt.py <vtable> <off1> [off2...]: print vtable slot targets (read-only)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe import PE, exe_copy
p = PE(exe_copy())
vt = int(sys.argv[1], 16)
for a in sys.argv[2:]:
    o = int(a, 16)
    print('slot 0x%X -> 0x%08X' % (o, p.u32(vt + o)))
