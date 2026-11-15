import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe import PE, exe_copy, func_start
p = PE(exe_copy())
for a in sys.argv[1:]:
    t = int(a, 16)
    print(a, 'calls:', [('0x%X' % c, '0x%X' % (func_start(p, c) or 0)) for c in p.calls_to(t)], 'abs:', [(s, '0x%X' % v) for s, v in p.xrefs(t)])
