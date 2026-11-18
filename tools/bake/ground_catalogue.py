"""The catalogue of ground looks (custom geometry plan, M4a item 3): every ground and rock material of the install's
base maps that a ground shape can be made in, measured (ground_measure.py) on its best placing and twin-checked,
written to tools/bake/looks/ground.json for the page's picker. The Build doesn't need it (a look is its donor, measured
again where the catalogue lacks it: tools/bake/looks.py).

  python -B tools/bake/ground_catalogue.py build [--maps URB_Bar ...] [--out <file>] [--check]

Over every base map the install lists (tools/viewer/library.py donors), or those named, it reads each placed plain
piece of the persistent level (ground_measure.PLAIN) whose mesh is at least 96 across in the world, and counts the
material each slot draws (research/evidence/ground-audit.py's pass). A material is a look when it is named for ground
or rock (its setting: asphalt road, pavement, concrete, grass, dirt and mud, gravel, sand, snow, rock) and nothing
leaves it out (ground_measure.left_out over all its placings: translucent, masked overlays, decals, unlit, a third
texture channel, distant scenery, no texture lightmap; D14), with a placing the Build copies that has a texture
lightmap. Painted materials are kept, made in their donor's commonest colour (D14). One entry per material: its
placings by map, its donor (the best placing: a texture lightmap, at scale 1 where it has one, a flat top, one
section, unpainted, a plain class, outside the DLC maps, then by map and actor), the donor measured, the twin check's
verdict, a readable name. --check builds again and says whether the file is the same."""
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
import ground_measure as gm  # noqa: E402
import measure_common as mc  # noqa: E402
import slab_catalogue  # noqa: E402

CATALOGUE = HERE / 'looks' / 'ground.json'
MIN_SIDE = 96.0


def readable(path):
    """A readable name from a material's path: 'GroundForest.Materials.GroundForestDirt_A' -> 'Ground Forest Dirt A'."""
    short = path.rsplit('.', 1)[-1]
    short = re.sub(r'^(MINST|MIC|MAT|M|MI)_', '', short)
    short = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', short.replace('_', ' '))
    return re.sub(r'\s+', ' ', short).strip()


class MeshSummary:
    """What the pass needs of a mesh, read once: its slots, and per slot its up faces' height range and main level
    share (for its top's shape at a placing's scale) and its colour stream's rule."""

    def __init__(self, m, p):
        T = mc.Tris(m)
        self.sections = T.sections
        self.slots = sorted({s['slot'] for s in m['lods'][0]['sections']})
        # (its sections' own materials by name: an export index means another thing in another map)
        self.material = {s['slot']: p.name(s['material']) if s['material'] else None for s in m['lods'][0]['sections']}
        self.top = {}
        self.colours = {}
        for slot in self.slots:
            top = gm.top_of(T, slot)
            up = (T.slot == slot) & (T.normal[:, 2] >= gm.UP)
            z = T.pos[T.verts(up), 2] if up.any() else None
            self.top[slot] = (top['shape'] == 'no top', float(z.max() - z.min()) if z is not None else 0.0,
                              top['shape'] == 'mostly flat' or top['shape'] == 'flat')
            verts = T.verts(T.slot == slot)
            values = {T.colours[v] for v in verts} if T.colours else set()
            self.colours[slot] = 'none' if not values else next(iter(values)).hex() if len(values) == 1 else 'varying'

    def shape(self, slot, scale):
        """The slot's top's shape at `scale` (ground_measure.top_of's words; the main level's share taken from scale 1,
        as a uniform scale keeps it)."""
        none, zrange, mostly = self.top[slot]
        if none:
            return 'no top'
        if zrange * abs(scale[2]) <= gm.FLAT_TOP:
            return 'flat'
        return 'mostly flat' if mostly else 'uneven'


def scan(maps, log=None):
    """(placings {material: [row]}, records {material: material_record}) of the plain pieces in `maps`: a row is
    dict(map, actor, index, cls, mesh, slot, sections, scale, light (its lightmap type), painted (its painted colours'
    rule), shape (its top's), stream (its mesh's colour rule on the slot))."""
    import gen_mesh
    from package import Package
    placings, records, meshes = {}, {}, {}
    for name, _, path in maps:
        p = Package(path)
        level = mc.persistent(p)
        for i in range(1, len(p.exports) + 1):
            if p.exports[i - 1]['outer'] != level or p.cls(i) not in gm.PLAIN:
                continue
            # (the actor's own mesh component, the one the Build copies and the measurer reads: not a destroyed
            # state's or an effect's under it)
            for comp in [p.effective(i, 'StaticMeshComponent')]:
                if not comp or comp < 0 or p.cls(comp) != 'StaticMeshComponent':
                    continue
                mi = p.effective(comp, 'StaticMesh', 0)
                if not mi or mi < 0 or p.cls(mi) != 'StaticMesh':
                    continue
                scale = mc.scale_of(p, i, comp)
                size = slab_catalogue.bounds_size(p, mi)
                if not size or min(abs(size[0] * scale[0]), abs(size[1] * scale[1])) < MIN_SIDE:
                    continue
                key = p.name(mi)
                if key not in meshes:
                    try:
                        meshes[key] = MeshSummary(gen_mesh.read(p, mi), p)
                    except (ValueError, struct.error, IndexError):
                        meshes[key] = None
                ms = meshes[key]
                if ms is None:
                    continue
                light = mc.light_of(p, comp)
                over = p.refs(p.effective(comp, 'Materials')) if p.effective(comp, 'Materials') else []
                for slot in ms.slots:
                    ref = over[slot] if slot < len(over) and over[slot] else 0
                    mat = p.name(ref) if ref else ms.material.get(slot)
                    if not mat:
                        continue
                    if mat not in records:
                        index = ref or p.by_name.get(mat, 0)
                        try:
                            records[mat] = gm.material_record(p, index) if index > 0 else dict(cls='import')
                        except (ValueError, struct.error) as err:
                            records[mat] = dict(cls='unread', error=str(err)[:120])
                    placings.setdefault(mat, []).append(dict(
                        map=name, actor=p.name(i).split('.')[-1], index=i, cls=p.cls(i), mesh=key, slot=slot,
                        sections=ms.sections, scale=[round(v, 4) for v in scale], light=light.get('type'),
                        painted=light.get('painted'), shape=ms.shape(slot, scale), stream=ms.colours[slot]))
        if log:
            log('%-32s materials so far %d' % (name, len(placings)))
    return placings, records


def paint_signs(name, rec, rows):
    """The signs over all of a material's placings that it blends layers by painted colours (ground-audit.py's
    colour_signs)."""
    signs = gm.paint_signs(rec, name)
    varying = [r for r in rows if str(r['painted']).startswith('varying')]
    if len(varying) >= max(1, 0.5 * len(rows)):
        signs.append('%d of %d placings painted with varying colours' % (len(varying), len(rows)))
    if (rec.get('diffuseLayers') or 0) >= 2 and (varying or any(r['stream'] == 'varying' for r in rows)):
        signs.append('%d diffuse layers, and colours that vary on its placings' % rec['diffuseLayers'])
    return signs


def donor_of(rows):
    """The best placing to copy: one the Build copies with a texture lightmap; at scale 1, a flat top, one section,
    unpainted, a plain class, outside the DLC maps, then by map and actor. None when there is none."""
    fit = [r for r in rows if r['cls'] in gm.COPYABLE and r['light'] == 2]
    if not fit:
        return None
    return min(fit, key=lambda r: (not mc.unit_scale(r['scale']),
                                   {'flat': 0, 'mostly flat': 1}.get(r['shape'], 2), r['sections'] != 1,
                                   r['painted'] not in (None, 'empty'), r['cls'] not in ('XComLevelActor', 'StaticMeshActor'),
                                   r['map'].upper().startswith('DLC'), r['map'].casefold(), r['index']))


def chosen(placings, records):
    """{material: (its donor row, setting, the signs that it is painted)} of the materials that make ground looks."""
    out = {}
    for mat, rows in placings.items():
        rec = records[mat]
        setting = gm.setting_of(mat, rec.get('diffuse'))
        if setting is None:
            continue
        if gm.left_out(rec, mat, any(r['light'] == 2 for r in rows), sorted({r['mesh'] for r in rows})):
            continue
        donor = donor_of(rows)
        if donor is None:
            continue
        out[mat] = (donor, setting, paint_signs(mat, rec, rows))
    return out


def entry_of(p, mat, rows, donor, setting, signs):
    """The catalogue entry of the material `mat` (its placings `rows`), measured on its donor in the open package
    `p`."""
    import gen_mesh
    found = gm.measure(p, donor['actor'], mat)
    _, _, mesh = mc.find_placing(p, donor['actor'], gm.PLAIN, 'StaticMeshComponent')
    result = gm.twin(found['recipe'], gen_mesh.read(p, mesh))
    facts = {k: v for k, v in found['facts'].items() if k not in ('mesh', 'actor')}
    warnings = list(found['warnings'])
    if signs and not any('painted colours' in w for w in warnings):
        warnings.append('its material blends layers by painted colours on its placings (%s): made in its donor\'s '
                        'commonest colour (%s), so it shows one layer' % ('; '.join(signs),
                                                                          found['recipe']['colours']['outside']))
    facts['painted'] = bool(facts.get('painted') or signs)
    maps = sorted({r['map'] for r in rows}, key=str.casefold)
    facts.update(placings=len(rows), meshes=len({r['mesh'] for r in rows}),
                 onlyInSlingshot=all(m.upper().startswith('DLC1_') for m in maps))
    return dict(mesh=found['facts']['mesh'], material=mat, map=donor['map'], actor=donor['actor'],
                maps={m: sum(1 for r in rows if r['map'] == m) for m in maps}, name=readable(mat), setting=setting,
                lwrOnly=False, facts=facts, warnings=warnings, twin=gm.verdict(result), recipe=found['recipe'])


def build(game=None, names=None, log=None):
    """The catalogue (its JSON text) over the install `game`'s base maps (the settings' install when None), or the
    maps named."""
    from package import Package
    import settings
    if game is None:
        game, _ = settings.game_install(settings.load_settings())
        if game is None:
            raise ValueError('the game install is not set (python tools/viewer/viewer.py settings)')
    maps = [m for m in slab_catalogue.maps_of(game, names) if m[1] == 'base']
    placings, records = scan(maps, log)
    picked = chosen(placings, records)
    paths = {n: path for n, _, path in maps}
    by_map = {}
    for mat, (donor, _, _) in picked.items():
        by_map.setdefault(donor['map'], []).append(mat)
    looks = []
    for name in sorted(by_map, key=str.casefold):
        p = Package(paths[name])
        for mat in sorted(by_map[name]):
            donor, setting, signs = picked[mat]
            try:
                looks.append(entry_of(p, mat, placings[mat], donor, setting, signs))
            except ValueError as err:
                if log:
                    log('  %-56s not measured: %s' % (mat, err))
                continue
            if log:
                log('  %-56s %s' % (mat, looks[-1]['twin']))
    looks.sort(key=lambda e: (e['material'], e['mesh']))
    data = dict(about=(
        'Ground looks: every ground and rock material of the install\'s base maps a ground shape can be made in '
        '(custom geometry plan, M4a), one entry per material, each measured by tools/bake/ground_measure.py on its '
        'donor (`map`, `actor`: the best placing to copy, with a texture lightmap, at scale 1 where it has one) into '
        'the recipe tools/bake/ground.py builds from (a look given as {mesh, material, measure, recipe}; in world '
        'units, so a donor placed scaled gives the repeat its placing draws, and its copy stands at scale 1), with '
        'what a made piece lacks (`warnings`, plain words) and the twin check (`twin`: "ok", or what differs when a '
        'patch is built at the donor\'s size and measured again). Painted materials are made in their donor\'s '
        'commonest colour; translucent and masked overlays, decals, unlit materials, a third texture channel, distant '
        'scenery and materials with no texture lightmap are left out (D14; research/evidence/ground-audit.py). '
        '`maps`: the material\'s placings by map. `setting`: the ground audit\'s, by the material\'s name. '
        + slab_catalogue.LWR_RULE + '. Written by `python -B tools/bake/ground_catalogue.py build`; the Build doesn\'t '
        'need it.'),
        measure=gm.VERSION,
        built='<game>: its base maps, %d read (those Firaxis cooked)%s; %d materials on its plain pieces' % (
            len(maps), ', those named' if names else '', len(placings)),
        looks=looks)
    return slab_catalogue.dump(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('command', choices=['build'])
    ap.add_argument('--maps', nargs='*', help='map names (default: every base map the install lists)')
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
