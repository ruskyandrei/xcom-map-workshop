"""
Sets where placed actors stand in a map package: their saved Location and Rotation, in a copy of the map (EXP-07,
findings register F-30).

Some things the game works out only once, when the map loads, from where its actors stand. A ladder's climb links
are re-made by every tile rebuild from where the ladder stood at load, so a ladder moved later by script can't be
climbed (EXP-07 run 16). Moving the ladder in the map itself puts it there from the start.

  python bake_actor.py <map.upk> <out.upk> <actor> <x> <y> <z> [<yaw degrees>] [<actor> <x> <y> <z> [<yaw>] ...]
  python bake_actor.py show <map.upk> <actor> [...]

Only values already saved can be changed: the property sizes stay the same, so no offset inside the package moves.
An actor saved without a Rotation (yaw 0, the default) can take a new Location but no new yaw. The chunks holding the
edits are re-encoded as literal LZO1X blocks (only the changed 128 KB blocks), the chunks after them move along in
the file, and the chunk table follows. The written package is decoded again and compared byte for byte.
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkinfo, decomp, lzo1x, props, seed_tiles


def fname(names, b, o):
    i, n = struct.unpack_from('<ii', b, o)
    s = names[i] if 0 <= i < len(names) else '?%d' % i
    return s if n == 0 else '%s_%d' % (s, n - 1)


def tagged(b, e, names):
    """The export's top-level tagged properties: {name: (type, data offset, size)}."""
    out = {}
    o = props.props_start(b, e, names)
    end = e['off'] + e['size']
    while o + 8 <= end:
        pname = fname(names, b, o); o += 8
        if pname == 'None':
            break
        ptype = fname(names, b, o); o += 8
        size, idx = struct.unpack_from('<ii', b, o); o += 8
        if ptype == 'BoolProperty':
            out.setdefault(pname, (ptype, o, 1)); o += 1; continue
        if ptype in ('StructProperty', 'ByteProperty'):
            o += 8
        if idx == 0:
            out.setdefault(pname, (ptype, o, size))
        o += size
    return out


def find_actor(full, names, imps, exps, actor):
    want = 'TheWorld.PersistentLevel.' + actor
    for n, e in enumerate(exps):
        if upkinfo.objname(n + 1, imps, exps) == want:
            return e
    raise SystemExit('no %s in the map' % want)


def placement(full, names, e):
    t = tagged(full, e, names)
    loc = t.get('Location'); rot = t.get('Rotation')
    if not loc or loc[2] != 12:
        raise SystemExit('%s has no saved Location' % e['name'])
    l = struct.unpack_from('<3f', full, loc[1])
    r = struct.unpack_from('<3i', full, rot[1]) if rot and rot[2] == 12 else None
    return loc[1], l, (rot[1] if r else None), r


def rewrite(src, dst, edits):
    """Writes dst: src with edits [(uncompressed offset, bytes)] applied; re-encodes the chunks that hold them."""
    raw = open(src, 'rb').read()
    h = upkinfo.summary(raw)
    full, _ = decomp.decompress_pkg(src)
    want = bytearray(full)
    for off, data in edits:
        want[off:off + len(data)] = data
    chunks = h['chunks']
    first = chunks[0][2]
    out = bytearray(raw[:first])
    entries = []
    for ci, (uo, us, co, cs) in enumerate(chunks):
        if want[uo:uo + us] == full[uo:uo + us]:
            body = raw[co:co + cs]
        else:
            r = upkinfo.R(raw, co)
            tag, bsz, csum, usum = r.u32(), r.u32(), r.u32(), r.u32()
            nb = (usum + bsz - 1) // bsz
            blocks = [(r.u32(), r.u32()) for _ in range(nb)]
            p = r.o
            newblocks, payload = [], b''
            for k, (c, u) in enumerate(blocks):
                old = raw[p:p + c]; p += c
                part = bytes(want[uo + k * bsz:uo + k * bsz + u])
                if part == bytes(full[uo + k * bsz:uo + k * bsz + u]):
                    enc = old
                else:
                    enc = seed_tiles.lzo_literals(part)
                    if lzo1x.decompress(enc, u) != part:
                        raise ValueError('literal LZO round trip failed in chunk %d block %d' % (ci, k))
                newblocks.append((len(enc), u)); payload += enc
            body = struct.pack('<IIII', tag, bsz, sum(c for c, u in newblocks), usum)
            body += b''.join(struct.pack('<II', c, u) for c, u in newblocks) + payload
        entries.append((uo, us, len(out), len(body)))
        out += body
    if chunks[-1][2] + chunks[-1][3] != len(raw):
        raise ValueError('the last chunk does not end the file; there is data this tool would drop')
    t = seed_tiles.chunk_table_offset(raw)
    if struct.unpack_from('<I', raw, t)[0] != len(chunks):
        raise ValueError('chunk table not where expected')
    for ci, ent in enumerate(entries):
        struct.pack_into('<IIII', out, t + 4 + 16 * ci, *ent)
    open(dst, 'wb').write(out)
    # Check: the written package decodes to the intended bytes, except the chunk table, which must hold the new entries.
    got, h2 = decomp.decompress_pkg(dst)
    for ci, ent in enumerate(entries):
        struct.pack_into('<IIII', want, t + 4 + 16 * ci, *ent)
    if bytes(got) != bytes(want):
        raise ValueError('verification failed: %s does not decode to the intended bytes' % dst)
    if [tuple(c) for c in h2['chunks']] != entries:
        raise ValueError('verification failed: the chunk table was not read back as written')
    return sum(1 for (a, b2) in zip(entries, chunks) if a[3] != b2[3]), len(out) - len(raw)


def main():
    a = sys.argv[1:]
    if a and a[0] == 'show':
        path = a[1]
        raw = open(path, 'rb').read(); h = upkinfo.summary(raw); full, _ = decomp.decompress_pkg(path)
        names, imps, exps = upkinfo.tables(full, h)
        for actor in a[2:]:
            e = find_actor(full, names, imps, exps, actor)
            _, l, _, r = placement(full, names, e)
            print('%s at (%g, %g, %g) rotation %s' % (actor, l[0], l[1], l[2], r if r else 'not saved (0, 0, 0)'))
        return
    if len(a) < 6:
        raise SystemExit(__doc__)
    src, dst, rest = a[0], a[1], a[2:]
    if os.path.abspath(src) == os.path.abspath(dst):
        raise SystemExit('refusing to overwrite the input')
    raw = open(src, 'rb').read(); h = upkinfo.summary(raw); full, _ = decomp.decompress_pkg(src)
    names, imps, exps = upkinfo.tables(full, h)
    edits, lines, i = [], [], 0
    while i < len(rest):
        actor = rest[i]
        x, y, z = (float(v) for v in rest[i + 1:i + 4]); i += 4
        yaw = None
        if i < len(rest) and not rest[i].startswith(('XCom', 'Static', 'Emitter', 'Point', 'Spot')):
            yaw = float(rest[i]); i += 1
        e = find_actor(full, names, imps, exps, actor)
        loff, l, roff, r = placement(full, names, e)
        edits.append((loff, struct.pack('<3f', x, y, z)))
        msg = '%s: (%g, %g, %g) -> (%g, %g, %g)' % (actor, l[0], l[1], l[2], x, y, z)
        if yaw is not None:
            units = int(round(yaw * 65536 / 360.0))
            if r is None:
                if units % 65536:
                    raise SystemExit('%s has no saved Rotation, so its yaw (0) cannot change; pick an actor saved with one' % actor)
            else:
                edits.append((roff, struct.pack('<3i', r[0], units, r[2])))
                msg += ', yaw %d -> %d' % (r[1], units)
        lines.append(msg)
    n, grew = rewrite(src, dst, edits)
    for m in lines:
        print(m)
    print('wrote %s: %d chunk(s) re-encoded, %+d bytes; decoded again and verified' % (dst, n, grew))


if __name__ == '__main__':
    main()
