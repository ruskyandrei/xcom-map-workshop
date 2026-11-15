"""fn.py <va> [maxlen] [--exe <copy>]: print start..end of function at va (read-only) as hex for dis.sh."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe import PE, exe_copy, func_end
p = PE(exe_copy())
va = int(sys.argv[1], 16)
e = func_end(p, va)
print('0x%08X 0x%08X' % (va, e))
