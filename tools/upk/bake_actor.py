"""
Sets where placed actors stand in a map package: their saved Location and Rotation, in a copy of the map (EXP-07,
findings register F-30).

Some things the game works out only once, when the map loads, from where its actors stand. A ladder's climb links
are re-made by every tile rebuild from where the ladder stood at load, so a ladder moved later by script can't be
climbed (EXP-07 run 16). Moving the ladder in the map itself puts it there from the start.

  python bake_actor.py <map.upk> <out.upk> <actor> <x> <y> <z> [<yaw degrees>] [<actor> <x> <y> <z> [<yaw>] ...]
  python bake_actor.py show <map.upk> <actor> [...]

Only values already saved can be changed: the property sizes stay the same, so no offset inside the package moves.
An actor saved without a Rotation (yaw 0, the default) can take a new Location but no new yaw. The edits are written
by tools/upk/package_edit.py: only the changed 128 KB blocks are re-encoded as literal LZO1X blocks, the chunks after
them move along in the file, the chunk table follows, and the written package is decoded again and compared byte for
byte.
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkinfo, decomp, package_edit, props


def tagged(b, e, names):
    """The export's top-level tagged properties: {name: (type, data offset, size)}, read by props.tags (bounded by
    the export; review finding 52)."""
    out = {}
    for pname, ptype, _, idx, o, size in props.read_tags(b, props.props_start(b, e, names), e['off'] + e['size'],
                                                         names)[0]:
        if idx == 0 or ptype == 'BoolProperty':
            out.setdefault(pname, (ptype, o, size))
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
    """Writes dst: src with edits [(uncompressed offset, bytes)] applied, by package_edit.write_edited (review finding
    52): only the changed blocks re-encoded, the chunks after them moved along, the result decoded again and checked.
    Returns (the chunks re-encoded, the file's change in size)."""
    report = package_edit.write_edited(src, dst, edits)
    return len(report['chunksReencoded']), report['sizeChange']


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
