# Dump UE3 (v845) tagged properties of export objects from a package
import sys, struct, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkinfo

def read_props(b, off, end, names, imps, exps, depth=0):
    r = upkinfo.R(b, off)
    out = []
    def nm():
        i = r.i32(); n = r.i32()
        s = names[i] if 0 <= i < len(names) else '?%d' % i
        return s if n == 0 else '%s_%d' % (s, n - 1)
    while r.o < end:
        pname = nm()
        if pname == 'None':
            break
        ptype = nm(); size = r.i32(); idx = r.i32()
        start = r.o
        val = None
        if ptype == 'BoolProperty':
            val = b[r.o]; r.o += 1; size = 0; start = r.o
        elif ptype == 'StructProperty':
            sname = nm(); start = r.o
            if sname in ('Vector',) and size == 12:
                val = 'Vector' + str(struct.unpack_from('<3f', b, r.o))
            elif sname == 'Rotator' and size == 12:
                val = 'Rotator' + str(struct.unpack_from('<3i', b, r.o))
            elif sname == 'Box' and size == 25:
                val = 'Box' + str(struct.unpack_from('<6f', b, r.o))
            elif sname == 'LinearColor' and size == 16:
                val = 'LinearColor(R=%g,G=%g,B=%g,A=%g)' % struct.unpack_from('<4f', b, r.o)
            elif sname == 'Color' and size == 4:
                bb_, g_, r_, a_ = b[r.o:r.o + 4]; val = 'Color(R=%d,G=%d,B=%d,A=%d)' % (r_, g_, bb_, a_)
            else:
                val = 'struct %s (%d bytes)' % (sname, size)
        elif ptype == 'ByteProperty':
            ename = nm(); start = r.o
            if size == 8:
                i = struct.unpack_from('<i', b, r.o)[0]; val = '%s::%s' % (ename, names[i] if 0 <= i < len(names) else i)
            else:
                val = b[r.o]
        elif ptype == 'IntProperty':
            val = struct.unpack_from('<i', b, r.o)[0]
        elif ptype == 'FloatProperty':
            val = struct.unpack_from('<f', b, r.o)[0]
        elif ptype in ('ObjectProperty', 'ComponentProperty', 'ClassProperty', 'InterfaceProperty'):
            i = struct.unpack_from('<i', b, r.o)[0]; val = upkinfo.objname(i, imps, exps)
        elif ptype == 'NameProperty':
            i, n = struct.unpack_from('<ii', b, r.o); val = names[i] + ('' if n == 0 else '_%d' % (n - 1))
        elif ptype == 'StrProperty':
            rr = upkinfo.R(b, r.o); val = repr(rr.fstr())
        elif ptype == 'ArrayProperty':
            cnt = struct.unpack_from('<i', b, r.o)[0]; val = 'array[%d] (%d bytes)' % (cnt, size)
        else:
            val = '%s (%d bytes)' % (ptype, size)
        r.o = start + size
        out.append(('  ' * depth) + '%s[%d] %s = %s' % (pname, idx, ptype, val))
    return out, r.o

PROP_TYPES = {'BoolProperty', 'StructProperty', 'ByteProperty', 'IntProperty', 'FloatProperty', 'ObjectProperty',
              'ComponentProperty', 'ClassProperty', 'InterfaceProperty', 'NameProperty', 'StrProperty', 'ArrayProperty',
              'DelegateProperty', 'MapProperty'}

def props_start(b, e, names):
    """Offset of an export's first tagged property.
    v845 layout: [FStateFrame if HasStack] NetIndex, then for components TemplateOwnerClass (and TemplateName for
    templates), then the tagged properties. The component fields are found by checking which candidate offset starts
    with a valid property tag (or the closing 'None')."""
    o = e['off']
    if (e['flags'] >> 32) & 0x02000000:  # HasStack
        node = struct.unpack_from('<i', b, o)[0]
        o += 4 + 4 + 8 + 2  # Node, StateNode, ProbeMask (QWORD), LatentAction (WORD)
        if node != 0: o += 4  # code Offset
    o += 4  # NetIndex
    end = e['off'] + e['size']
    def ok(p):
        if p + 8 > end: return False
        i = struct.unpack_from('<i', b, p)[0]
        if not 0 <= i < len(names): return False
        # the closing None is the plain name (number 0). The field before a component's properties (its net index,
        # native_copy.net_index_offset) can equal None's place in the name table by chance, with the first property's
        # name after it where the number would be (URB_CommercialStreet_Terror's StaticMeshComponent_115: 2315, then
        # StaticMesh): not a terminator
        if names[i] == 'None': return struct.unpack_from('<i', b, p + 4)[0] == 0
        if p + 16 > end: return False
        # a kind's name is a plain one too (number 0). EWI_ExaltHQAssault_Stream's TriggerVolume_0.BrushComponent_15
        # reads as a tag 4 bytes early otherwise: its net index a valid name, the property's name where the number
        # would be, and that name's number, 0, the place in the name table of a kind
        t, number = struct.unpack_from('<ii', b, p + 8)
        return number == 0 and 0 <= t < len(names) and names[t] in PROP_TYPES
    for extra in (0, 4, 12):
        if ok(o + extra): return o + extra
    return o

if __name__ == '__main__':
    path = sys.argv[1]; wanted = sys.argv[2:]
    b, h = upkinfo.load(path)
    names, imps, exps = upkinfo.tables(b, h)
    for n, e in enumerate(exps):
        full = upkinfo.objname(n + 1, imps, exps)
        if any(w == full or (w.endswith('*') and full.startswith(w[:-1])) for w in wanted):
            cls = upkinfo.clsname(e['cls'], imps, exps)
            print('== %s %s (size %d)' % (cls, full, e['size']))
            props, endo = read_props(b, props_start(b, e, names), e['off'] + e['size'], names, imps, exps)
            print('\n'.join(props))
            print('  [native data after props: %d bytes]' % (e['off'] + e['size'] - endo))
