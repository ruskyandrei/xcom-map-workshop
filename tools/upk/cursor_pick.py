"""Turn the mouse cursor's pick on or off for placed level pieces of a map package (bIgnoreFor3DCursorCollision).

The mouse finds its tile by tracing a ray from the screen (XComTacticalHUD.GetMousePickActor) and skips every
XComLevelActor or XComFracLevelActor whose bIgnoreFor3DCursorCollision is set (research/native/mouse-cursor.md).
Temple Ship's arches (the KnuckleWorm_A pieces) have it set, so their tiles are floor for pathing and the grapple but
cannot be clicked (F-110). This tool flips that byte on the placed actors whose archetype matches, as a fixed-size
edit (package_edit.py), so nothing else in the package moves.

Only a placed actor that saves the property itself is changed. One that takes it from its archetype would need a
property added, which a fixed-size edit cannot do; such actors are reported and left alone.

  python cursor_pick.py <map.upk>                          list the matching pieces and their flag
  python cursor_pick.py <map.upk> --out <new.upk>           make them clickable (flag cleared)
  python cursor_pick.py <map.upk> --out <new.upk> --ignore  set the flag again
  --match <pattern>  archetype names (fnmatch, repeatable); default KnuckleWorm_A.Archetypes.*
"""
import argparse
import collections
import fnmatch
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import package_edit  # noqa: E402
import props  # noqa: E402
import upkinfo  # noqa: E402

FLAG = 'bIgnoreFor3DCursorCollision'
PIECE_CLASSES = ('XComLevelActor', 'XComFracLevelActor')
DEFAULT_MATCH = ('KnuckleWorm_A.Archetypes.*',)


def walk_tags(b, off, end, names):
    """Yield (name, type, size, value offset) for each top-level tagged property from off until 'None'."""
    def name_at(o):
        i, n = struct.unpack_from('<ii', b, o)
        s = names[i] if 0 <= i < len(names) else '?%d' % i
        return s if n == 0 else '%s_%d' % (s, n - 1)
    o = off
    while o + 8 <= end:
        pname = name_at(o)
        if pname == 'None':
            return
        if o + 24 > end:
            raise ValueError(f'property tag at {o} runs past the export')
        ptype = name_at(o + 8)
        size = struct.unpack_from('<i', b, o + 16)[0]
        o += 24
        if ptype == 'BoolProperty':
            yield pname, ptype, 1, o
            o += 1
            continue
        if ptype in ('StructProperty', 'ByteProperty'):
            o += 8  # the struct's or the enum's name
        yield pname, ptype, size, o
        o += size
    raise ValueError(f'no closing None before {end}')


def find_pieces(b, h, patterns=DEFAULT_MATCH):
    """Placed level pieces whose archetype matches: list of dicts (export, name, archetype, flag, offset).

    flag is the saved byte (0 or 1) and offset its logical place in the package, or both None when the actor does not
    save the property (it then has its archetype's value)."""
    names, imps, exps = upkinfo.tables(b, h)
    out = []
    for n, e in enumerate(exps):
        if upkinfo.clsname(e['cls'], imps, exps) not in PIECE_CLASSES or not e['arch']:
            continue
        full = upkinfo.objname(n + 1, imps, exps)
        if '.PersistentLevel.' not in full:
            continue
        arch = upkinfo.objname(e['arch'], imps, exps)
        if not any(fnmatch.fnmatchcase(arch, p) for p in patterns):
            continue
        flag = offset = None
        for pname, ptype, _size, at in walk_tags(b, props.props_start(b, e, names), e['off'] + e['size'], names):
            if pname == FLAG and ptype == 'BoolProperty':
                flag, offset = b[at], at
                break
        out.append(dict(export=n + 1, name=full, archetype=arch, flag=flag, offset=offset))
    return out


def summarise(pieces):
    """Counts per archetype: {archetype: Counter of 'set', 'clear', 'inherited'}."""
    agg = collections.defaultdict(collections.Counter)
    for p in pieces:
        agg[p['archetype']]['inherited' if p['flag'] is None else ('set' if p['flag'] else 'clear')] += 1
    return agg


def write_flag(src, dst, patterns=DEFAULT_MATCH, ignore=False):
    """Write dst: src with the flag of every matching piece that saves it set to `ignore`. Returns (report, pieces)."""
    b, h = upkinfo.load(src)
    pieces = find_pieces(b, h, patterns)
    value = 1 if ignore else 0
    edits = [(p['offset'], bytes([value])) for p in pieces if p['offset'] is not None and p['flag'] != value]
    if not edits:
        raise ValueError('nothing to change: no matching piece saves the flag with the other value')
    report = package_edit.write_edited(src, dst, edits)
    report['pieces'] = len(edits)
    return report, pieces


def print_summary(pieces):
    for arch, c in sorted(summarise(pieces).items()):
        print('  %-55s set %3d  clear %3d  inherited %3d' % (arch, c['set'], c['clear'], c['inherited']))
    print('  %d pieces' % len(pieces))


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('src')
    a.add_argument('--out', help='write the changed package here (never over src)')
    a.add_argument('--match', action='append', help='archetype name pattern (fnmatch); repeatable')
    a.add_argument('--ignore', action='store_true', help='set the flag (the mouse skips the pieces) instead of clearing')
    args = a.parse_args()
    patterns = tuple(args.match) if args.match else DEFAULT_MATCH
    if not args.out:
        b, h = upkinfo.load(args.src)
        print_summary(find_pieces(b, h, patterns))
        return
    report, _ = write_flag(args.src, args.out, patterns, args.ignore)
    print('%s: %d pieces %s, %d blocks re-encoded, file %+d bytes' % (
        args.out, report['pieces'], 'set to be ignored' if args.ignore else 'made clickable',
        report['blocksReencoded'], report['sizeChange']))
    b, h = upkinfo.load(args.out)
    print_summary(find_pieces(b, h, patterns))


if __name__ == '__main__':
    main()
