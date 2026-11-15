"""comps.py <upk> <export>...: print the Components array of the given exports (read-only)."""
import os, sys, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'upk'))
import upkinfo, props
b, h = upkinfo.load(sys.argv[1])
names, imps, exps = upkinfo.tables(b, h)
want = set(sys.argv[2:])
for n, e in enumerate(exps):
    full = upkinfo.objname(n + 1, imps, exps)
    if full not in want: continue
    r = upkinfo.R(b, props.props_start(b, e, names))
    end = e['off'] + e['size']
    while r.o < end:
        i = r.i32(); r.i32(); pn = names[i]
        if pn == 'None': break
        t = names[r.i32()]; r.i32(); size = r.i32(); idx = r.i32()
        if t == 'BoolProperty': r.o += 1; continue
        if t in ('StructProperty', 'ByteProperty'): r.o += 8
        if pn == 'Components' and t == 'ArrayProperty':
            cnt = struct.unpack_from('<i', b, r.o)[0]
            refs = struct.unpack_from('<%di' % cnt, b, r.o + 4)
            print(full, 'Components:', [upkinfo.objname(x, imps, exps) for x in refs])
        r.o += size
