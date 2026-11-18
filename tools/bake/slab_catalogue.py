"""The catalogue of slab looks (custom geometry plan, M4a item 3): every fracturing floor and roof of the install's
maps, measured (slab_measure.py) and twin-checked, written to tools/bake/looks/slabs.json for the page's picker. The
Build doesn't need it (a look is its donor, measured again where the catalogue lacks it: tools/bake/looks.py).

  python -B tools/bake/slab_catalogue.py build [--maps URB_Bar ...] [--out <file>] [--check]

Over every map the install lists (tools/viewer/library.py donors: base maps and streams, those Firaxis cooked), or
those named, it reads each placed fracturing piece of the persistent level; a slab is a mesh slab_measure.classify
calls one (research/evidence/slab-audit.py's rule: 55 meshes on 18 November 2026). Each slab mesh is one look: its
placings by map, its donor (the placing to copy: at scale 1 where it has one, in a base map before a stream, outside
the DLC maps where it can be, then by map name and actor), the donor measured (its recipe, warnings and facts), the
twin check's verdict, a readable name, and a setting from its top's material. --check builds again and says whether
the file is the same. The file is sorted and written the same way every time (LF)."""
import argparse
import json
from pathlib import Path
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
for folder in ('viewer', 'upk', 'lab'):
    if str(HERE.parent / folder) not in sys.path:
        sys.path.insert(0, str(HERE.parent / folder))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import measure_common as mc  # noqa: E402
import slab_measure  # noqa: E402

CATALOGUE = HERE / 'looks' / 'slabs.json'
LWR_RULE = ('lwrOnly: every map read is one Firaxis cooked (licensee 64; library.donors reads no other), so every '
            'donor is in a base-game package (Enemy Within, or its Slingshot content where the facts say so); the '
            'install offers no list of the files Long War Rebalance added, so no look is marked LWR-only (false for '
            'all)')
SETTINGS = [('gravel and asphalt', re.compile(r'gravel|asphalt|tar(?!get)', re.I)),
            ('metal', re.compile(r'metal|steel|tin(?![a-z])|corrugat|alum', re.I)),
            ('wood', re.compile(r'wood|plank|board|deck', re.I)),
            ('tiles', re.compile(r'tile', re.I)),
            ('concrete', re.compile(r'concrete|cement', re.I)),
            ('carpet', re.compile(r'carpet|rug', re.I)),
            ('shingles', re.compile(r'shingle|slate', re.I)),
            ('stone', re.compile(r'stone|marble|brick', re.I)),
            ('alien', re.compile(r'alien|ufo', re.I))]


def readable(path):
    """A readable name from a mesh's path: 'ComKit_Meshes.Roofing.Roof_BarrierSmallFloor_FRACTURED' -> 'Roof Barrier
    Small Floor'."""
    short = path.rsplit('.', 1)[-1]
    short = re.sub(r'_?FRACTURED$', '', short, flags=re.I)
    short = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', short.replace('_', ' '))
    return re.sub(r'\s+', ' ', short).strip()


def setting_of(role, material):
    """The look's setting: its role and its top material's kind ('roof: gravel and asphalt'), by the material's name."""
    short = (material or '').rsplit('.', 1)[-1]
    for words, rx in SETTINGS:
        if rx.search(short) or rx.search(material or ''):
            return '%s: %s' % (role, words)
    return '%s: other' % role


def bounds_size(p, mesh):
    """A mesh's box size (x, y, z) from its saved bounds, or None."""
    try:
        b = struct.unpack_from('<7f', p.data, p.properties(mesh)[1])
    except (ValueError, struct.error):
        return None
    return [2 * b[3], 2 * b[4], 2 * b[5]]


def maps_of(game, names=None):
    """[(name, role, path)] of the install's donor maps (library.donors), or of those named."""
    import library
    found = [(n, role, Path(path)) for n, role, path in library.donors(game)]
    if names:
        want = {m.casefold() for m in names}
        found = [m for m in found if m[0].casefold() in want]
    return found


def scan(maps, log=None):
    """{mesh: dict(kind, placings [(map, role, actor name, export, unit scale)])} of the slab meshes placed in `maps`."""
    import gen_mesh
    from package import Package
    kinds, out = {}, {}
    for name, role, path in maps:
        p = Package(path)
        level = mc.persistent(p)
        for i in range(1, len(p.exports) + 1):
            if p.exports[i - 1]['outer'] != level or p.cls(i) not in slab_measure.FRACTURING:
                continue
            comp = p.effective(i, 'FracturedStaticMeshComponent')
            if not comp or comp < 0:
                continue
            mesh = p.effective(comp, 'StaticMesh')
            if not mesh or mesh < 0 or p.cls(mesh) != 'FracturedStaticMesh':
                continue
            key = p.name(mesh)
            if key not in kinds:
                size = bounds_size(p, mesh)
                named = bool(slab_measure.NAMED.search(key.rsplit('.', 1)[-1]))
                if named or (size and size[2] <= slab_measure.FLAT + 1 and min(size[:2]) >= slab_measure.WIDE):
                    try:
                        kinds[key] = slab_measure.classify_mesh(gen_mesh.read(p, mesh), key)[0]
                    except (ValueError, struct.error, IndexError):
                        kinds[key] = None
                else:
                    kinds[key] = None
            if kinds[key]:
                rec = out.setdefault(key, dict(kind=kinds[key], placings=[]))
                rec['placings'].append((name, role, p.name(i).split('.')[-1], i,
                                        mc.unit_scale(mc.scale_of(p, i, comp))))
        if log:
            log('%-32s slabs so far %d' % (name, len(out)))
    return out


def donor_of(placings):
    """The placing to copy: at scale 1 first, a base map before a stream, outside the DLC maps, then by map and
    actor."""
    return min(placings, key=lambda q: (not q[4], q[1] != 'base', q[0].upper().startswith('DLC'), q[0].casefold(), q[3]))


def entry_of(p, key, rec):
    """The catalogue entry of the slab mesh `key` (scan's `rec`), measured on its donor in the open package `p`."""
    import gen_mesh
    name, _, actor, _, _ = donor_of(rec['placings'])
    found = slab_measure.measure(p, actor)
    _, comp, mesh = mc.find_placing(p, actor, slab_measure.FRACTURING, 'FracturedStaticMeshComponent')
    result = slab_measure.twin(found['recipe'], gen_mesh.read(p, mesh))
    over = p.refs(p.effective(comp, 'Materials')) if p.effective(comp, 'Materials') else []
    lod = gen_mesh.read(p, mesh)['lods'][0]
    materials = {}
    for s in lod['sections']:
        ref = over[s['slot']] if s['slot'] < len(over) and over[s['slot']] else s['material']
        materials[str(s['slot'])] = p.name(ref) if ref else None
    facts = {k: v for k, v in found['facts'].items() if k not in ('mesh', 'actor')}
    facts['materials'] = materials
    maps = sorted({q[0] for q in rec['placings']}, key=str.casefold)
    facts['onlyInSlingshot'] = all(m.upper().startswith('DLC1_') for m in maps)
    counts = {m: sum(1 for q in rec['placings'] if q[0] == m) for m in maps}
    top = materials.get(str(found['recipe']['slots']['top']))
    return dict(mesh=key, map=name, actor=actor, maps=counts, name=readable(key),
                setting=setting_of(found['recipe']['role'], top), lwrOnly=False, facts=facts,
                warnings=found['warnings'], twin=slab_measure.verdict(result), recipe=found['recipe'])


def build(game=None, names=None, log=None):
    """The catalogue (its JSON text) over the install `game` (the settings' when None), or the maps named."""
    from package import Package
    import settings
    if game is None:
        game, _ = settings.game_install(settings.load_settings())
        if game is None:
            raise ValueError('the game install is not set (python tools/viewer/viewer.py settings)')
    maps = maps_of(game, names)
    found = scan(maps, log)
    paths = {n: path for n, _, path in maps}
    looks = []
    by_map = {}
    for key, rec in found.items():
        by_map.setdefault(donor_of(rec['placings'])[0], []).append(key)
    for name in sorted(by_map, key=str.casefold):
        p = Package(paths[name])
        for key in sorted(by_map[name]):
            looks.append(entry_of(p, key, found[key]))
            if log:
                log('  %-48s %s' % (key.rsplit('.', 1)[-1], looks[-1]['twin']))
    looks.sort(key=lambda e: e['mesh'])
    data = dict(about=(
        'Slab looks: every fracturing floor and roof of the install\'s maps (custom geometry plan, M4a), each measured '
        'by tools/bake/slab_measure.py on its donor (`map`, `actor`: the placing to copy, at scale 1 where it has one) '
        'into the recipe tools/bake/frac_slab.py builds from (a look given as {mesh, measure, recipe}), with what a '
        'made slab lacks (`warnings`, plain words) and the twin check (`twin`: "ok", or what differs when the look is '
        'built at the donor\'s size and measured again; triangles a tile are told in the check but don\'t fail it). '
        'Pitched and thick roofs are made flat in their top\'s material (D13). `maps`: its placings by map. '
        '`setting`: its role and its top material\'s kind, by the material\'s name. ' + LWR_RULE + '. Written by '
        '`python -B tools/bake/slab_catalogue.py build`; the Build doesn\'t need it.'),
        measure=slab_measure.VERSION,
        built='<game>: the maps it lists, %d read (base maps and streams Firaxis cooked)%s' % (
            len(maps), ', those named' if names else ''),
        looks=looks)
    return dump(data)


def dump(data):
    """A catalogue's text: its fields a line each, each look's fields a line each, every value deeper on one line;
    keys sorted, LF, the same bytes for the same catalogue."""
    def one(v):
        return json.dumps(v, sort_keys=True, ensure_ascii=False)
    rows = []
    for k in sorted(data):
        if k != 'looks':
            rows.append(' %s: %s' % (one(k), one(data[k])))
            continue
        looks = ['  {\n%s\n  }' % ',\n'.join('   %s: %s' % (one(f), one(e[f])) for f in sorted(e)) for e in data[k]]
        rows.append(' %s: [\n%s\n ]' % (one(k), ',\n'.join(looks)))
    return '{\n%s\n}\n' % ',\n'.join(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('command', choices=['build'])
    ap.add_argument('--maps', nargs='*', help='map names (default: every map the install lists)')
    ap.add_argument('--out', type=Path, default=CATALOGUE)
    ap.add_argument('--check', action='store_true', help='build again and compare with the file; write nothing')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()
    text = build(names=args.maps, log=None if args.quiet else (lambda s: print(s, flush=True)))
    if args.check:
        same = args.out.exists() and args.out.read_bytes() == text.encode('utf-8')
        print('%s is %s' % (args.out.name, 'the same' if same else 'different'))
        sys.exit(0 if same else 1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding='utf-8', newline='\n')
    data = json.loads(text)
    ok = sum(1 for e in data['looks'] if e['twin'] == 'ok')
    print('%s: %d looks, the twin check ok for %d' % (args.out.name, len(data['looks']), ok))


if __name__ == '__main__':
    main()
