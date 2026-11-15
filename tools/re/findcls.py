"""findcls.py <ClassNameWithoutPrefix>: locate GetPrivateStaticClass pushes of the wide class name (read-only)."""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe import PE, exe_copy, func_start
p = PE(exe_copy())
name = sys.argv[1]
for s in p.find_str(name, wide=True):
    # wide string must be preceded by 0 wchar
    for sec, v in p.xrefs(s, '.text'):
        if p.b[p.va2off(v)-1] == 0x68:
            print('str 0x%08X push at 0x%08X func 0x%08X' % (s, v-1, func_start(p, v-1)))
