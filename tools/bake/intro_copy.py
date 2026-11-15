"""A variant's own dropship intro (F-45): a copy of its base map's intro stream in which the base map's name is the
variant's.

The landing intro's Kismet is in a streamed package, CIN_DropshipIntros (or CIN_FastropeIntros), not in the map.
XGBattle fires its SeqEvent_OnTacticalIntro with the map's name, and Switch String nodes pick the landing by that
exact name: for URB_Bar, the dropship goes to URB_Bar's landing. A map under a new name falls through every switch
and no landing plays. The patch's XComMapEdIntro used to rename the base map's case in the running game; a Build with
no patch needs the rename in the data instead.

The alien bases' entrance, CIN_TP05A_EnteringAlienBase, works the same way (F-76): its one switch ("Which alien base
map are we in?") picks AlienBase01's or AlienBase02's place, and a variant's name, matching neither, left cinematic
mode on with no cutscene, so the battle never started. (The exe doesn't name that stream; the copy's name keeps it
at the start all the same.)

So this copies the intro package under a new name, with every Switch String entry (`StringArray`) that names the base
map naming the variant. The variant's map record streams the copy in place of the original. The copy's name keeps
the original's as its start (CIN_DropshipIntros_<variant>): the exe recognises the intro streams by that substring
(three places, read from the exe copy on 7 November).

A project that moves the map's own landing (private/plans/done/clear-map-plan.md, section 4; F-97) also moves the
intro's flight: the dropship flies to a fixed place for each map and group, a Set Location's saved LocationValue and
RotationValue (picked by the map's switch, then on a map of several landings by a Compare Int of GroupNumber). Each
such action of the base map is moved by its landing's rigid move (`moves`: the landing's frame from its old place and
yaw to its new ones; the group a map with one landing has no Compare Int for is landing 0's). An action not found is
reported, never an error.

A base map's entry whose Set Location saves no place (F-106: `URB_StreetHurricane_Terror`'s, the one such entry in
LWR's CIN_DropshipIntros) puts the rig at (0, 0, 0), so the dropship lands in the middle of the map and stays there.
Given the map (`--map`), the copy gives such an action its landing's grounded Skyranger's place and yaw, where the
intro places of the other maps stand (F-97: the median distance from them is under two units, the yaw the same).
A landing the project moves then moves that place with it, as any other.

  python -B tools/bake/intro_copy.py <intro.upk> <copy.upk> <base map> <variant> [--report report.json]
                                     [--landing-moves moves.json] [--map <map.upk>]
"""
import argparse
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import audit_lighting as lighting  # noqa: E402
import native_copy  # noqa: E402
import package_grow  # noqa: E402
import props as legacy_props  # noqa: E402

INTROS = ('CIN_DropshipIntros', 'CIN_FastropeIntros', 'CIN_TP05A_EnteringAlienBase')


def read_fstring(b, at):
    """(text, offset after) of the FString at `at`: a length with its terminator, ANSI when positive, UTF-16 when
    negative."""
    n = struct.unpack_from('<i', b, at)[0]
    if n >= 0:
        return bytes(b[at + 4:at + 4 + max(n - 1, 0)]).decode('latin-1'), at + 4 + n
    return bytes(b[at + 4:at + 4 - 2 * n - 2]).decode('utf-16-le'), at + 4 - 2 * n


def fstring(text):
    try:
        raw = text.encode('ascii')
        return struct.pack('<i', len(raw) + 1) + raw + b'\0'
    except UnicodeEncodeError:
        raw = text.encode('utf-16-le')
        return struct.pack('<i', -(len(raw) // 2 + 1)) + raw + b'\0\0'


def switches(p, data_of=None):
    """For each Switch String: (export, its data, the StringArray value's offset and size, its entries). An entry is
    a struct whose one tagged property is the string (`StringName`): (its bytes as saved, its text)."""
    w = native_copy.Walker(p)
    out = []
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) != 'SeqCond_SwitchString':
            continue
        e = p.exports[i - 1]
        data = bytearray(data_of(i) if data_of else p.data[e['off']:e['off'] + e['size']])
        start = legacy_props.props_start(p.data, e, p.names) - e['off']
        for prop, kind, _, at, size in w.walk(bytes(data), start, len(data)):
            if prop == 'StringArray[0]' and kind == 'ArrayProperty':
                count, entries, o = struct.unpack_from('<i', data, at)[0], [], at + 4
                for _ in range(count):
                    gen, text = w.walk(bytes(data), o, at + size), None
                    try:
                        while True:
                            name, k, _, v, _ = next(gen)
                            if name == 'StringName[0]' and k == 'StrProperty':
                                text = read_fstring(data, v)[0]
                    except StopIteration as done:
                        entries.append((bytes(data[o:done.value]), text))
                        o = done.value
                out.append((i, data, at, size, entries))
                break
    return out


def same_map(text, base):
    """Whether a switch's string names the map `base`, whatever its case: CIN_DropshipIntros names the package's
    (CsmallScout_Farm), a project the record's (CSmallScout_Farm), T-17."""
    return text is not None and text.casefold() == base.casefold()


def renamed_entry(w, raw, base, variant):
    """An entry's bytes with its string `base` (whatever its case) made `variant` (the tag's size follows)."""
    raw = bytearray(raw)
    for name, kind, _, v, size in list(w.walk(bytes(raw), 0, len(raw))):
        if name == 'StringName[0]' and kind == 'StrProperty' and same_map(read_fstring(raw, v)[0], base):
            new = fstring(variant)
            struct.pack_into('<i', raw, v - 8, len(new))
            raw[v:v + size] = new
            break
    return bytes(raw)


def anchors(p, base):
    """The base map's flight places in the intro: [dict(group (None for a map with one landing, else 0, 1 or 2),
    action (its export), location, rotation)], as tools/upk/audit_clear.py intro_anchors reads them (F-97)."""
    import audit_clear
    found = audit_clear.intro_anchors(p.path)
    by_op = {name.split('.')[-1]: i for name, i in p.by_name.items() if '.Main_Sequence.' in name}
    out = []
    for case, places in found.items():
        if not same_map(case, base):
            continue
        for a in places:
            i = by_op.get(a['action'])
            if i:
                out.append(dict(a, action=i))
    return out


def missing_places(p, base, landings):
    """The base map's flight places that save no place (no LocationValue, or one at (0, 0, 0)), each given its landing's
    grounded Skyranger's place and yaw: [dict(action, group, landing, location, rotation, skyranger)]. `landings`:
    scene_metadata.landing_metadata of the map (group None is landing 0's). A place whose landing has no grounded
    Skyranger is left as it is (`skyranger` None, no location)."""
    out = []
    for a in anchors(p, base):
        saved = p.own(a['action'], 'LocationValue')
        if saved is not None and any(abs(float(v)) > 1e-3 for v in saved):
            continue
        k = a['group'] if a['group'] is not None else 0
        sky = landings[k].get('skyranger') if k < len(landings) else None
        mesh = next((x for x in (sky or {}).get('actors') or [] if x['role'] == 'mesh'), None)
        if mesh is None:
            out.append(dict(action=a['action'], group=a['group'], landing=k, location=None, rotation=None, skyranger=None))
            continue
        rotation = [int(a['rotation'][0]), int(mesh['rotation'][1]), int(a['rotation'][2])]
        out.append(dict(action=a['action'], group=a['group'], landing=k, location=[float(v) for v in mesh['location']],
                        rotation=rotation, skyranger=mesh['path'].split('.')[-1]))
    return out


def set_place(g, p, w, i, location, rotation):
    """Set Location `i`'s LocationValue and RotationValue set (added where it saves none)."""
    import native_lights
    e = p.exports[i - 1]
    data = bytearray(g.export_data(i))
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    data = native_lights.set_property(w, g, data, start, 'LocationValue', 'StructProperty', 'Vector',
                                      struct.pack('<3f', *location))
    data = native_lights.set_property(w, g, data, start, 'RotationValue', 'StructProperty', 'Rotator',
                                      struct.pack('<3i', *rotation))
    g.relocate(i, bytes(data))


def fill_places(g, p, base, landings):
    """missing_places written into the copy: the report's rows (action by name, group, landing, the place and yaw,
    the Skyranger it came from; a place left alone has `left` and why) and {action: (location, rotation)} for
    move_anchors."""
    w = native_copy.Walker(p)
    rows, filled = [], {}
    for f in missing_places(p, base, landings):
        name = p.name(f['action']).split('.')[-1]
        if f['location'] is None:
            rows.append(dict(action=name, group=f['group'], landing=f['landing'], left='its landing has no grounded Skyranger'))
            continue
        set_place(g, p, w, f['action'], f['location'], f['rotation'])
        filled[f['action']] = (f['location'], f['rotation'])
        rows.append(dict(action=name, group=f['group'], landing=f['landing'], skyranger=f['skyranger'],
                         location=[round(v, 3) for v in f['location']], rotation=f['rotation']))
    return rows, filled


def move_anchors(g, p, base, moves, filled=None):
    """Each of the base map's flight places moved by its landing's move ({index, frame: {old: [location, yaw], new:
    [location, yaw]}}): returns [dict(action, group, old, new)] and the moves no place was found for. `filled`: the
    places fill_places gave ({action: (location, rotation)}), taken as the old ones."""
    import spawns
    w = native_copy.Walker(p)
    done, places = [], anchors(p, base)
    for a in places:
        if a['action'] in (filled or {}):
            a['location'], a['rotation'] = [list(v) for v in filled[a['action']]]
    for m in moves:
        mine = [a for a in places if (a['group'] if a['group'] is not None else 0) == m['index']]
        (f0, y0), (f1, y1) = m['frame']['old'], m['frame']['new']
        for a in mine:
            d = spawns.turn([a['location'][k] - f0[k] for k in range(3)], y1 - y0)
            location = [f1[k] + d[k] for k in range(3)]
            rotation = [a['rotation'][0], a['rotation'][1] + y1 - y0, a['rotation'][2]]
            i = a['action']
            set_place(g, p, w, i, location, rotation)
            done.append(dict(action=p.name(i).split('.')[-1], group=a['group'], landing=m['index'],
                             old=dict(location=a['location'], rotation=a['rotation']),
                             new=dict(location=[round(v, 3) for v in location], rotation=rotation)))
        m['found'] = bool(mine)
    return done, [m['index'] for m in moves if not m['found']]


def rename_switches(g, p, base, variant):
    """Every Switch String entry of package `p` (grower `g`) that names `base` made `variant`: [{switch, entries,
    of}] of the switches changed."""
    w = native_copy.Walker(p)
    renamed = []
    for i, data, at, size, entries in switches(p, g.export_data):
        hits = [k for k, (_, text) in enumerate(entries) if same_map(text, base)]
        if not hits:
            continue
        payload = struct.pack('<i', len(entries)) + b''.join(
            renamed_entry(w, raw, base, variant) if same_map(text, base) else raw for raw, text in entries)
        struct.pack_into('<i', data, at - 8, len(payload))
        data[at:at + size] = payload
        g.relocate(i, bytes(data))
        renamed.append(dict(switch=p.name(i), entries=hits, of=len(entries)))
    return renamed


def make(src, dst, base, variant, moves=None, map_path=None):
    """Writes the copy; returns its report: each switch whose entries named `base`, and where. When no switch names
    `base` (the intro has no landing of its own for that map), nothing is written and `copy` is None: the variant
    streams the original, as its base map does. `moves`: the map's own landings the project moves
    (native_spawns.plan's index and frame), whose flight places move with them (report: `moved`, `notFound`).
    `map_path`: the base map's package, whose grounded Skyrangers give a place to an entry that saves none (F-106;
    report: `filled`)."""
    src, dst = Path(src), Path(dst)
    if dst.stem.lower() == src.stem.lower():
        raise ValueError('the copy needs a name of its own')
    p = lighting.Package(src)
    g = package_grow.Grower(str(src))
    renamed = rename_switches(g, p, base, variant)
    report = dict(source=str(src), copy=None, base=base, variant=variant, renamed=renamed)
    filled = {}
    if map_path and renamed:
        import scene_metadata
        from package import Package
        rows, filled = fill_places(g, p, base, scene_metadata.landing_metadata(Package(str(map_path))))
        if rows:
            report['filled'] = rows
    if moves and renamed:
        report['moved'], report['notFound'] = move_anchors(g, p, base, moves, filled)
    if renamed:
        dst.parent.mkdir(parents=True, exist_ok=True)
        g.write(str(dst))
        report['copy'] = str(dst)
    return report


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('src', type=Path, help='the intro package (CIN_DropshipIntros.upk, CIN_FastropeIntros.upk or '
                                         'CIN_TP05A_EnteringAlienBase.upk)')
    a.add_argument('dst', type=Path, help='the copy, named <intro>_<variant>.upk')
    a.add_argument('base', help='the base map, as the intro names it (URB_Bar)')
    a.add_argument('variant', help='the variant\'s map name')
    a.add_argument('--report', type=Path, help='write the report here too')
    a.add_argument('--landing-moves', type=Path, help='the map\'s own landings the project moves (native_spawns.plan)')
    a.add_argument('--map', type=Path, help='the base map\'s package: its grounded Skyrangers give a place to an entry '
                                            'that saves none (F-106)')
    args = a.parse_args(argv)
    moves = json.loads(args.landing_moves.read_text(encoding='utf-8')) if args.landing_moves else None
    report = make(args.src, args.dst, args.base, args.variant, moves, args.map)
    for r in report['renamed']:
        print(f"{r['switch']}: entry {', '.join(map(str, r['entries']))} of {r['of']} names {args.variant} "
              f"instead of {args.base}")
    for f in report.get('filled') or []:
        print(f"{f['action']} (landing {f['landing']}): " + (f"no place saved; given the grounded Skyranger's, {f['location']} yaw "
                                                            f"{f['rotation'][1]} ({f['skyranger']})" if 'left' not in f else
                                                            f"no place saved, left as it is: {f['left']}"))
    for m in report.get('moved') or []:
        print(f"{m['action']} (landing {m['landing']}): the flight moved from {m['old']['location']} to {m['new']['location']}")
    for k in report.get('notFound') or []:
        print(f'warning: no flight place of {args.base} for its landing {k}: the intro flies to the old place')
    print(f'wrote {args.dst}' if report['copy'] else
          f'no switch in {args.src.name} names {args.base}: nothing written; the variant streams {args.src.stem}')
    if args.report:
        args.report.write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
