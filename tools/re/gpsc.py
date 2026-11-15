"""gpsc.py <va>...: class name pushed by a GetPrivateStaticClass-like function (read-only)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clsname
for a in sys.argv[1:]:
    print(a, clsname.gpsc_name(int(a, 16)))
