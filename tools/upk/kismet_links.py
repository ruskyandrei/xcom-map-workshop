"""Prints the Kismet graph of a map package: for each sequence op, its output links (output name -> linked ops) and
its variable links (link name -> variables, with a named variable's FindVarName or a variable's VarName and value).

  python tools/upk/kismet_links.py <map.upk or .udk> [op name prefix ...]

Reads tagged properties (UE3 v845 packages, uncompressed, as tools/upk/upkinfo.py does). Written for EXP-08 F-45, the
dropship intro in CIN_DropshipIntros.
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkinfo
from props import props_start


class P:
    def __init__(s, b, names, imps, exps):
        s.b, s.names, s.imps, s.exps = b, names, imps, exps

    def name(s, o):
        i, n = struct.unpack_from('<ii', s.b, o)
        t = s.names[i] if 0 <= i < len(s.names) else '?%d' % i
        return (t if n == 0 else '%s_%d' % (t, n - 1)), o + 8

    def obj(s, ref):
        if ref == 0:
            return None
        return upkinfo.objname(ref, s.imps, s.exps).split('.')[-1] if ref > 0 else upkinfo.objname(ref, s.imps, s.exps)

    def props(s, o, end):
        """Tagged properties from o: a dict name -> (type, value offset, size, struct name)."""
        out = {}
        while o < end:
            pname, o = s.name(o)
            if pname == 'None':
                break
            ptype, o = s.name(o)
            size, idx = struct.unpack_from('<ii', s.b, o); o += 8
            sname = None
            if ptype == 'BoolProperty':
                out[pname] = (ptype, o, 1, None); o += 1; continue
            if ptype == 'StructProperty':
                sname, o = s.name(o)
            if ptype == 'ByteProperty':
                _, o = s.name(o)
            key = pname if idx == 0 else '%s[%d]' % (pname, idx)
            out[key] = (ptype, o, size, sname)
            o += size
        return out, o

    def array_of_structs(s, val):
        """The elements of an array of structs, each a props dict."""
        _, o, size, _ = val
        n = struct.unpack_from('<i', s.b, o)[0]; o += 4
        els = []
        for _ in range(n):
            d, o = s.props(o, val[1] + size)
            els.append(d)
        return els

    def str_(s, val):
        _, o, size, _ = val
        n = struct.unpack_from('<i', s.b, o)[0]
        if n > 0:
            return s.b[o + 4:o + 4 + n - 1].decode('latin-1')
        if n < 0:
            return s.b[o + 4:o + 4 - 2 * n - 2].decode('utf-16-le')
        return ''

    def objp(s, val):
        return s.obj(struct.unpack_from('<i', s.b, val[1])[0])

    def int_(s, val):
        return struct.unpack_from('<i', s.b, val[1])[0]


def main():
    path = sys.argv[1]; want = sys.argv[2:]
    b, h = upkinfo.load(path)
    names, imps, exps = upkinfo.tables(b, h)
    p = P(b, names, imps, exps)
    ops = {}
    for n, e in enumerate(exps):
        full = upkinfo.objname(n + 1, imps, exps)
        if '.Main_Sequence.' not in full and not full.endswith('Main_Sequence'):
            continue
        d, _ = p.props(props_start(b, e, names), e['off'] + e['size'])
        ops[full.split('.')[-1]] = (upkinfo.clsname(e['cls'], imps, exps), d)

    def var_desc(v):
        if v not in ops:
            return v
        cls, d = ops[v]
        bits = [v]
        if 'FindVarName' in d:
            bits.append('find ' + p.name(d['FindVarName'][1])[0])
        if 'VarName' in d:
            bits.append('name ' + p.name(d['VarName'][1])[0])
        if 'ObjValue' in d:
            bits.append('= ' + str(p.objp(d['ObjValue'])))
        if 'IntValue' in d:
            bits.append('= %d' % p.int_(d['IntValue']))
        if 'StrValue' in d:
            bits.append('= ' + repr(p.str_(d['StrValue'])))
        return ' '.join(bits)

    for op, (cls, d) in sorted(ops.items()):
        if want and not any(op.startswith(w) for w in want):
            continue
        if cls.startswith('SeqVar'):
            continue
        extra = []
        if 'ObjComment' in d:
            extra.append('comment %r' % p.str_(d['ObjComment']))
        if 'LocationValue' in d:
            extra.append('location %s' % (struct.unpack_from('<3f', b, d['LocationValue'][1]),))
        if 'EventName' in d:
            extra.append('event ' + p.name(d['EventName'][1])[0])
        print('== %s %s %s' % (cls, op, ' '.join(extra)))
        if 'StringArray' in d:
            sa = [p.str_(e['StringName']) if 'StringName' in e else '' for e in p.array_of_structs(d['StringArray'])]
        else:
            sa = None
        if 'ValueArray' in d:
            va = [str(p.int_(e['Value'])) if 'Value' in e else '?' for e in p.array_of_structs(d['ValueArray'])]
        else:
            va = None
        if 'OutputLinks' in d:
            for k, ol in enumerate(p.array_of_structs(d['OutputLinks'])):
                desc = p.str_(ol['LinkDesc']) if 'LinkDesc' in ol else str(k)
                if sa and k < len(sa):
                    desc = '%s (%s)' % (desc, sa[k])
                if va and k < len(va):
                    desc = '%s (%s)' % (desc, va[k])
                links = []
                if 'Links' in ol:
                    for l in p.array_of_structs(ol['Links']):
                        tgt = p.objp(l['LinkedOp']) if 'LinkedOp' in l else None
                        idx = p.int_(l['InputLinkIdx']) if 'InputLinkIdx' in l else 0
                        links.append('%s[%d]' % (tgt, idx))
                if links:
                    print('   out %s -> %s' % (desc, ', '.join(links)))
        if 'VariableLinks' in d:
            for vl in p.array_of_structs(d['VariableLinks']):
                desc = p.str_(vl['LinkDesc']) if 'LinkDesc' in vl else '?'
                vs = []
                if 'LinkedVariables' in vl:
                    _, o, size, _ = vl['LinkedVariables']
                    n = struct.unpack_from('<i', b, o)[0]
                    vs = [var_desc(p.obj(struct.unpack_from('<i', b, o + 4 + 4 * k)[0])) for k in range(n)]
                if vs:
                    print('   var %s: %s' % (desc, '; '.join(vs)))


if __name__ == '__main__':
    main()
