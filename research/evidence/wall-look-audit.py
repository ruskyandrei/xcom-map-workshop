"""Read-only audit of which of the game's fracturing walls a generator that sweeps a cross-section along the wall
(tools/bake/frac_wall.py) can make (private/plans/done/custom-geometry-implementation-plan.md, stage M4 item 3).

Over every map the install lists (tools/viewer/library.py donors), or the maps named with --maps, it finds each
placed fracturing piece (XComDecoFracLevelActor, XComFracLevelActor) of the persistent level whose mesh is a wall:
its name holds "wall" (as research/evidence/frac-wall-audit.py counts them), or, named otherwise, it is shaped like
one (8 to 60 thick, at least 96 long and 128 tall: the ComKit cores and high rises, the offices' INT walls; not the
vehicles' sides or the diner's caps). Each wall mesh is measured once, from its first placed piece, by
research/evidence/wall-look-measure.py (which see for how), and its placings counted per map. Per mesh:

  size, storeys    length, thickness, height in the wall's frame (along x), bottom and top in the mesh's frame (z 0
                   its pivot, for most the floor it stands on: the Bar's inside wall reaches 16 under it), its top
                   over the floor (the top when it reaches under z 0, else its height) and that over 192 (storeys)
  sweep            the verdict from the cuts across its length: swept (every cut the same outline, as the Bar's
                   inside wall), swept with openings (the same between doorways and windows), swept with framed
                   openings (the wall between its openings swept, frames or trims in them), mostly swept (nine
                   cuts in ten agree: a local detail), modelled (window frames, cladding, ledges, ribs, an L piece);
                   the share of its cuts that agree, where they differ, its openings, its end details (mitres,
                   jambs), how much of its outside area is on its two main faces (flatShare)
  section          the +y side's corners [y, z, trim v] and the -y side's when they differ
  slots            each slot's role (a side's face, both sides', a trim, the inside faces), the heights its face
                   covers, the material its placings bind (and whether placings differ); whether the two sides differ
                   (materials or outline) and a guess at inside or outside wall from its name and its sides'
                   materials
  fragments        the fragments' median box and the matching cell
  colours          whether the outside faces' vertex colours vary (painted dirt) or are one value
  donor            base game or Long War Rebalance only: every donor map is cooked by Firaxis (licensee 64) and
                   listed by the install's map records; the install's own Long War packages (licensee 0) are read
                   too and none holds a fracturing mesh or piece, so every wall here is the base game's (EW)
  needs            what a generator needs beyond the Bar's recipe to make it (other heights, one slot on both sides,
                   faces in the trim's unwrap, no trims, other splits, sides that differ, painted colours, ...)

Then a shortlist per setting (bar and shop interiors, brick and concrete exteriors, the pier's metal panels, the
UFOs' walls, offices, the police station, ...), sweepable walls first by a score (the verdict, less one a need, the
placings, the Bar's own section), the recommendation for the first looks (RECOMMENDED, chosen by hand from it, and
ALTERNATES) with what was found of each, and the summary counts. The alien base and the Temple Ship have no
fracturing piece at all: the alien walls that break are the UFOs'. Prints the summary and the shortlist; --output
writes the JSON. No game file is written.

  python -B research/evidence/wall-look-audit.py [--maps URB_Bar URB_PoliceStation] [--output <file.json>] [--verbose]
"""
import argparse
from collections import Counter, defaultdict
import importlib.util
import json
import math
from pathlib import Path
import re
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
for folder in ('viewer', 'upk', 'lab', 'bake'):
    sys.path.insert(0, str(ROOT / 'tools' / folder))
_spec = importlib.util.spec_from_file_location('wall_look_measure', Path(__file__).with_name('wall-look-measure.py'))
measure_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(measure_mod)
import gen_mesh  # noqa: E402

SHAPED = dict(thin=(8.0, 60.0), length=96.0, height=128.0)
NOT_WALLS = ('VEH_', 'DinerCap', 'Railing', 'BarSign', 'BookstorePosters', 'AlienCoverDebris', 'AlienLowCover',
             'URB_ParkingGarage')
# the settings, by the wall mesh's own package (the part of its name before the first dot)
SETTINGS = {
    'URB_Bar_FRAC': 'bar interior',
    'URB_ConvenienceStore_FRAC': 'shop interiors',
    'ComKit_WallsINT_Meshes': 'shop interiors',
    'URB_CommercialRestaurant_FRAC': 'restaurant',
    'BLDG_IceCreamShop': 'shop interiors',
    'ComKit_Meshes': 'shop exteriors (brick, concrete)',
    'ComKit_WallsEXT_Meshes': 'shop exteriors (brick, concrete)',
    'URB_PoliceStationBuilding': 'police station',
    'URB_Pier_A_Building': 'pier warehouse and office (metal panels)',
    'URB_OfficePaper_FRAC': 'offices and warehouse',
    'URB_IndustrialOffice_FRAC': 'offices and warehouse',
    'URB_ResearchOutpost_FRAC': 'research outpost and sheds',
    'BLDG_TrainShed': 'research outpost and sheds',
    'URB_SmallCemetery_FRAC': 'research outpost and sheds',
    'URB_Slaughterhouse_FRAC': 'slaughterhouse and plant',
    'PortentWarehouse_FRAC': 'slaughterhouse and plant',
    'URB_TruckStop_FRAC': 'garages and warehouses',
    'URB_TireMerchant_FRAC': 'garages and warehouses',
    'URB_MilitaryAmmo_FRAC': 'garages and warehouses',
    'URB_FastFood_FRAC': 'fast food and bank',
    'BLDG_UrbBank': 'fast food and bank',
    'URB_GasStation_FRAC': 'diner and roadhouse',
    'BLDG_RoadHouse': 'diner and roadhouse',
    'URB_CemeteryGrand_FRAC': 'cemetery stone',
    'WallMarble': 'cemetery stone',
    'StonewallB': 'cemetery stone',
    'AbductorExtWall': 'UFO walls (alien)',
    'SupplyShipBody': 'UFO walls (alien)',
    'HQAslt_Wall': 'XCOM base',
    'Exalt_Wall': 'EXALT base',
    'ExaltHoloGlobe': 'EXALT base',
    'SubwayTrain': 'vehicle',
}
# the order the shortlist goes through the settings (the plan's spread first)
PRIORITY = ['bar interior', 'shop interiors', 'shop exteriors (brick, concrete)', 'pier warehouse and office (metal panels)',
            'UFO walls (alien)', 'offices and warehouse', 'police station', 'research outpost and sheds',
            'slaughterhouse and plant', 'garages and warehouses', 'XCOM base', 'EXALT base', 'restaurant',
            'fast food and bank', 'diner and roadhouse', 'cemetery stone', 'vehicle']
SCORE = {'swept': 4, 'swept with openings': 4, 'swept, framed openings': 3, 'mostly swept': 2, 'modelled': 0}
# the recommendation for the first set of looks (M4 item 3), chosen by hand from the shortlist: swept walls spread
# over the settings the plan names, then alternates. The Bar's inside wall is the look there is already.
RECOMMENDED = [
    ('URB_ConvenienceStore_FRAC.Meshes.ConvStoreIntWallA_FRACTURED', 'shop interior (convenience store)'),
    ('ComKit_WallsINT_Meshes.Walls_IntSPLIT.Wall_IntSPLIT_320A_FRACTURED', 'shop interior (ComKit, two colours)'),
    ('ComKit_Meshes.Cores.Core_384FacadeA_FRACTURED', 'brick shopfront (the Bar\'s facade)'),
    ('ComKit_Meshes.Cores.Core_256BackA_FRACTURED', 'brick over concrete, plaster inside'),
    ('URB_Slaughterhouse_FRAC.Meshes.SLHPlantWallINTC_FRACTURED', 'concrete (the plant)'),
    ('URB_Pier_A_Building.Meshes.URBPierAWH_WallMainSouth_FRACTURED', 'pier warehouse: metal panels over cinder block'),
    ('URB_Pier_A_Building.Meshes.URBPierAOfficeWallNorth_FRACTURED', 'pier office: painted metal panels'),
    ('SupplyShipBody.MeshesWall.SupplyWallAx6_FRACTURED', 'UFO: supply ship'),
    ('AbductorExtWall.Meshes.AbductorExtWallx9_FRACTURED', 'UFO: abductor'),
    ('URB_OfficePaper_FRAC.Meshes.OPOfficeINTDivide_FRACTURED', 'office interior'),
    ('URB_PoliceStationBuilding.Meshes.PoliceStationWallA_FRACTURED', 'police station'),
    ('URB_ResearchOutpost_FRAC.Meshes.ROBetaWallSouth_FRACTURED', 'striped brick, stucco inside (research outpost)'),
]
ALTERNATES = [
    ('URB_TruckStop_FRAC.Meshes.TS_WallGarageSouth_FRACTURED', 'garage: brick and tile, stucco inside (truck stop)'),
    ('Exalt_Wall.Fractured.ExaltWall_18x1Sm_A_FRC', 'EXALT base'),
    ('URB_CommercialRestaurant_FRAC.Meshes.URBComRestWallMainHigh_FRACTURED', 'cream brick, plaster inside'),
    ('URB_IndustrialOffice_FRAC.Meshes.IndustrialOfficeWall384B_FRACTURED', 'office: wainscot, one storey'),
]
INSIDE_NAME = re.compile(r'Int[A-Z_]|INT|Interior|Divider|DualSplit|Inet|Kitchen|Order(Left|Right)|Vault')
OUTSIDE_NAME = re.compile(r'Ext|EXT|Facade|Core_|HighRise|North|South|East|West|Front|Rear|Entry|Main|Drive|Dine|'
                          r'Back|Gable|Strip|Crown|Addon|Garage|Store[A-Z]|Shed')
EXTERIOR_MATERIAL = re.compile(r'Brick|Concrete|Stucco|Siding|Metal|Cinder|Corrugat|Stone|Marble|EXT|Exterior|Shingle|'
                               r'Clapboard|Granite|Block', re.I)
INTERIOR_MATERIAL = re.compile(r'Interiors|Interior|INT|Plaster|Wallpaper|Paint|Wainsc|Drywall|Tile|Panel|Wood', re.I)
RECIPE_SECTION_Y = [11.0, 11.0, 10.0, 8.0, 8.0, 12.0, 12.0]      # the Bar's corners' y (frac_wall.RECIPE['section'])


def placements(p, verbose=False):
    """[(actor, component, mesh, named)] of the persistent level's fracturing walls."""
    out = []
    for actor, comp, mesh in measure_mod.placed(p):
        name = p.name(mesh)
        if 'wall' in name.lower():
            out.append((actor, comp, mesh, True))
            continue
        if name.split('.')[0].startswith(NOT_WALLS):
            continue
        b = gen_mesh.read(p, mesh)['bounds']
        ext = [2 * b[3], 2 * b[4], 2 * b[5]]
        thin, long_ = min(ext[0], ext[1]), max(ext[0], ext[1])
        if SHAPED['thin'][0] <= thin <= SHAPED['thin'][1] and long_ >= SHAPED['length'] and ext[2] >= SHAPED['height']:
            out.append((actor, comp, mesh, False))
    return out


def side_kind(materials):
    names = ' '.join(m for m in materials if m)
    ext, inn = bool(EXTERIOR_MATERIAL.search(names)), bool(INTERIOR_MATERIAL.search(names))
    if 'UFO' in names or 'Alien' in names:
        return 'alien'
    return 'exterior' if ext and not inn else 'interior' if inn and not ext else 'mixed' if ext and inn else 'unknown'


def kind_of(name, side_a, side_b):
    """A guess at inside or outside wall: (kind, why)."""
    short = name.split('.')[-1]
    ka, kb = side_kind(side_a), side_kind(side_b)
    if INSIDE_NAME.search(short):
        return 'inside', 'its name (%s)' % INSIDE_NAME.search(short).group(0)
    if 'alien' in (ka, kb):
        return 'alien', 'UFO materials'
    if {ka, kb} == {'exterior', 'interior'} or {ka, kb} == {'exterior', 'mixed'}:
        return 'outside', 'an exterior face (%s) and an interior one (%s)' % (ka, kb)
    if ka == kb == 'interior':
        return 'inside', 'both faces interior materials'
    if OUTSIDE_NAME.search(short):
        return 'outside', 'its name (%s); faces %s / %s' % (OUTSIDE_NAME.search(short).group(0), ka, kb)
    if ka == kb == 'exterior':
        return 'outside', 'both faces exterior materials (a free-standing wall)'
    return 'unsure', 'faces %s / %s' % (ka, kb)


def needs(entry, m, recipe):
    """What a generator needs beyond the Bar's recipe to make this wall: [words]."""
    out = []
    sw = m['sweep']
    if sw['verdict'] == 'modelled':
        out.append('modelled detail: not a sweep (%s)' % ('an L or corner piece' if sw['cornerPiece'] else
                                                         'cuts differ along %d%% of it' % round(100 * (1 - sw['agreeShare']))))
    elif sw['verdict'] == 'mostly swept':
        out.append('a local detail where its cuts differ (%s)' % ', '.join('x %g..%g' % tuple(d) for d in sw['differAt'][:3]))
    elif sw['verdict'] == 'swept, framed openings':
        out.append('frames round its openings')
    end = sw.get('endDetail') or {}
    if end.get('cuts') and (end.get('worst') or 0) >= 1:
        # mitred corners, door jambs, trims returning round an end, columns by an opening (judged apart)
        out.append('detail by its ends or openings\' sides (up to %g in, %g out of line)' % (end['reach'], end['worst']))
    # heights in the mesh's own frame, whose z 0 is its pivot (the floor it stands on, for most)
    bottom, top = entry['bottom'], entry['top']
    over = top if bottom < -1 else top - bottom
    if abs(bottom - recipe['bottom']) > 0.5:
        out.append('its bottom at z %g of its frame (the Bar\'s at -16, under the floor)' % bottom)
    if min(abs(over - 384), abs(over - 192)) > 0.5:
        out.append('another height: %g over its floor (%.2f storeys)' % (over, over / 192))
    slots = entry['slots']
    if slots.get('bothSides'):
        out.append('one material on both faces (slots %s)' % slots['bothSides'])
    if slots.get('trim') is None:
        out.append('no trim slot (flat faces only)')
    rows = {r['slot']: r for r in m['slots']}
    if any(r.get('carriesFaces') for r in rows.values()):
        out.append('its faces in the trim\'s unwrap (one slot and v by the section for the whole outline)')
    if isinstance(slots.get('trim'), list):
        out.append('%d trim slots' % len(slots['trim']))
    split_a, split_b = m['storeySplits']['A'], m['storeySplits']['B']
    if split_a == split_b:
        if not split_a and slots.get('sideA'):
            out.append('one face slot a side (no split)')
        elif split_a and split_a != [192.0]:
            out.append('faces split at %s' % ', '.join('%g' % v for v in split_a))
    else:
        for side, splits in (('A', split_a), ('B', split_b)):
            if not splits and slots.get('side' + side):
                out.append('one face slot on side %s (no split)' % side)
            elif splits and splits != [192.0]:
                out.append('side %s\'s faces split at %s' % (side, ', '.join('%g' % v for v in splits)))
    if 'sectionB' in entry:
        out.append('the two sides\' outlines differ' if m['sectionMirrored'] == 'differs' else
                   'the two sides\' trims take other v')
    if m['colours'].get('rule') == 'varying':
        out.append('painted vertex colours (item 4)')
    if entry.get('endInset') is not None and abs(entry['endInset'] - recipe['endInset']) > 0.5:
        out.append('ends %g from the tile edges' % entry['endInset'])
    if entry.get('faceRepeat') and abs(entry['faceRepeat'] - recipe['faceRepeat']) > 2:
        out.append('faces repeat every %g' % entry['faceRepeat'])
    fs = m.get('faceSides') or {}
    reps = sorted({v for side in fs.values() if side for r in side.get('repeats', []) for v in r if v})
    if reps and reps[-1] > 1.03 * reps[0]:
        out.append('face slots with other repeats (%g to %g)' % (reps[0], reps[-1]))
    return out


def same_kit(entry):
    """Whether the section is the Bar's (the same corners' y; heights may differ)."""
    ys = [c[0] for c in entry['section']]
    return len(ys) == len(RECIPE_SECTION_Y) and all(abs(a - b) < 0.1 for a, b in zip(ys, RECIPE_SECTION_Y))


def record(name, named, first_map, r, placings, recipe, materials_seen):
    entry, m = r['entry'], r['measured']
    slots = m['slots']
    carrier = [s['material'] for s in slots if s.get('carriesFaces')]
    side_a = [s['material'] for s in slots if s['slot'] in (entry['slots'].get('sideA') or [])] or carrier
    side_b = [s['material'] for s in slots if s['slot'] in (entry['slots'].get('sideB') or [])] or carrier
    kind, why = kind_of(name, side_a, side_b)
    size = m['size']
    height = entry['top'] - entry['bottom']
    # its top over the floor: the top in its own frame when it reaches under z 0 (as the Bar's, 16 under the floor
    # its pivot stands on), else its height
    over = entry['top'] if entry['bottom'] < -1 else height
    sides_differ = sorted(set(side_a)) != sorted(set(side_b)) or m['sectionMirrored'] != 'mirror'
    flat = m['flat'] or {}
    rec = dict(
        mesh=name, package=name.split('.')[0], named=named, setting=SETTINGS.get(name.split('.')[0], 'other'),
        placed=dict(placings), placedTotal=sum(placings.values()), maps=len(placings), measuredOn=first_map,
        actor=m['actor'], size=dict(length=size[0], thickness=size[1], height=size[2]), turned=m['turned'],
        bottom=entry['bottom'], top=entry['top'], topOverFloor=round(over, 2),
        storeys=round(max(over, 1) / 192, 2), storeysWhole=max(1, round(over / 192)),
        sweep=m['sweep'], flatShare=flat.get('flatShare'), faceCover=[flat.get('faceCoverA'), flat.get('faceCoverB')],
        section=entry['section'], sectionB=m['sectionB'] if m['sectionMirrored'] != 'mirror' else None,
        sectionSides=m['sectionMirrored'], sameKitAsBar=same_kit(entry), face=entry['face'], half=entry['half'],
        faceSplits=m['storeySplits'],
        slots=[dict(slot=s['slot'], role=s['role'], material=s['material'], faceZ=s['faceZ'],
                    carriesFaces=s.get('carriesFaces'), triangles=s['triangles'],
                    materials=sorted(materials_seen.get(s['slot'], {s['material']}) - {None}) or None)
               for s in slots],
        materialsVary=any(len(v - {None}) > 1 for v in materials_seen.values()),
        sidesDiffer=sides_differ, kind=kind, kindWhy=why,
        fragments=m['fragments'], fragmentBox=(m['cells'] or {}).get('medianBox'), cell=(m['cells'] or {}).get('cell'),
        unevenness=(m['cells'] or {}).get('unevenness'),
        colours=m['colours'], coloursVary=m['colours'].get('rule') == 'varying',
        lightmapDensity=entry['lightmap']['density'], endInsets=m['endInsets'], collisionHalf=entry['collisionHalf'],
        baseGame=True, look=entry)
    rec['needs'] = needs(entry, m, recipe)
    rec['score'] = round(SCORE[m['sweep']['verdict']] * 10 - len(rec['needs']) + math.log(1 + rec['placedTotal'])
                         + (2 if rec['sameKitAsBar'] else 0), 2)
    return rec


def lwr_packages(cooked):
    """The install's own Long War packages (licensee 0) and those holding a fracturing mesh or piece."""
    from package import Package
    seen, holding = 0, []
    for f in sorted(cooked.glob('*.upk')):
        with f.open('rb') as fh:
            head = fh.read(8)
        if len(head) < 8 or struct.unpack_from('<HH', head, 4) != (845, 0):
            continue
        seen += 1
        try:
            p = Package(f)
        except Exception:       # noqa: BLE001 (a package the reader doesn't take is counted, not held against it)
            continue
        classes = {p.cls(i) for i in range(1, len(p.exports) + 1)}
        if classes & {'FracturedStaticMesh', 'XComFracLevelActor', 'XComDecoFracLevelActor'}:
            holding.append(f.name)
    return dict(packages=seen, holdingFracturing=holding)


def audit(maps, recipe, verbose=False):
    from package import Package
    walls, placings, materials, errors = {}, defaultdict(Counter), defaultdict(lambda: defaultdict(set)), {}
    first = {}
    licensee = Counter()
    for name, path in maps:
        t0 = time.time()
        p = Package(path)
        licensee[p.header['lic']] += 1
        for actor, comp, mesh, named in placements(p):
            key = p.name(mesh)
            placings[key][name] += 1
            for slot, mat in measure_mod.materials_of(p, comp).items():
                materials[key][slot].add(mat)
            if key in walls or key in errors:
                continue
            try:
                r = measure_mod.measure(p, p.name(actor))
            except Exception as err:        # noqa: BLE001 (one mesh the measure can't read is listed, not fatal)
                errors[key] = '%s: %s' % (type(err).__name__, err)
                continue
            walls[key] = (named, name, r)
            first[key] = name
        if verbose:
            print('%-28s %5.1fs  walls so far %d' % (name, time.time() - t0, len(walls)), flush=True)
    records = {k: record(k, named, m, r, placings[k], recipe, materials[k]) for k, (named, m, r) in walls.items()}
    return records, errors, licensee


def shortlist(records, per_setting=3):
    """Per setting, the best walls a sweep makes (by score), as [(setting, [mesh])]."""
    by = defaultdict(list)
    for k, r in records.items():
        by[r['setting']].append(r)
    out = []
    for setting in PRIORITY + sorted(set(by) - set(PRIORITY)):
        rows = sorted(by.get(setting, []), key=lambda r: -r['score'])
        if rows:
            out.append((setting, [r['mesh'] for r in rows[:per_setting]]))
    return out


def recommended(records):
    """RECOMMENDED and ALTERNATES with what the audit found of each (those it read)."""
    out = []
    for alternate, rows in ((False, RECOMMENDED), (True, ALTERNATES)):
        for mesh, label in rows:
            r = records.get(mesh)
            if r is None:
                continue
            out.append(dict(mesh=mesh, label=label, alternate=alternate, setting=r['setting'],
                            verdict=r['sweep']['verdict'], size=r['size'], topOverFloor=r['topOverFloor'],
                            storeys=r['storeys'], kind=r['kind'], sidesDiffer=r['sidesDiffer'],
                            placedTotal=r['placedTotal'], maps=sorted(r['placed']), baseGame=r['baseGame'],
                            coloursVary=r['coloursVary'], needs=r['needs']))
    return out


def summary(records, errors, licensee, lwr):
    named = [r for r in records.values() if r['named']]
    extra = [r for r in records.values() if not r['named']]

    def counts(rows):
        return dict(meshes=len(rows), placed=sum(r['placedTotal'] for r in rows),
                    verdicts=dict(Counter(r['sweep']['verdict'] for r in rows).most_common()),
                    thickness24=sum(1 for r in rows if abs(r['size']['thickness'] - 24) < 0.5),
                    inside=sum(1 for r in rows if r['kind'] == 'inside'),
                    outside=sum(1 for r in rows if r['kind'] == 'outside'),
                    coloursVary=sum(1 for r in rows if r['coloursVary']),
                    sameKitAsBar=sum(1 for r in rows if r['sameKitAsBar']),
                    packages=len({r['package'] for r in rows}))
    return dict(named=counts(named), wallShapedNotNamed=counts(extra), all=counts(list(records.values())),
                bySetting={s: dict(Counter(r['sweep']['verdict'] for r in records.values() if r['setting'] == s))
                           for s in sorted({r['setting'] for r in records.values()})},
                unread=errors, donorMapsByLicensee={str(k): v for k, v in licensee.items()}, lwrOwnPackages=lwr)


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('--maps', nargs='*', help='map names (default: every map the install lists)')
    a.add_argument('--output', type=Path)
    a.add_argument('--verbose', action='store_true')
    args = a.parse_args()
    import frac_wall
    import library
    import settings
    game, _ = settings.game_install(settings.load_settings())
    if game is None:
        raise SystemExit('the game install is not set (python tools/viewer/viewer.py settings)')
    maps = [(n, Path(path)) for n, _, path in library.donors(game)]
    if args.maps:
        want = {m.casefold() for m in args.maps}
        maps = [(n, path) for n, path in maps if n.casefold() in want]
    records, errors, licensee = audit(maps, frac_wall.RECIPE, args.verbose)
    lwr = lwr_packages(library.cooked_of(game))
    result = dict(scope='Read-only: the install\'s maps (%d), their placed fracturing walls measured by '
                        'wall-look-measure.py; nothing written to the game' % len(maps),
                  summary=summary(records, errors, licensee, lwr),
                  shortlist=[dict(setting=s, meshes=m) for s, m in shortlist(records)],
                  recommended=recommended(records),
                  walls=dict(sorted(records.items())))
    print(json.dumps(result['summary'], indent=1))
    for row in result['shortlist']:
        print('%s:' % row['setting'])
        for k in row['meshes']:
            r = records[k]
            print('   %-62s %-24s %5gx%-5gx%-5g placed %-3d %s; needs: %s' % (
                k.split('.')[-1], r['sweep']['verdict'], r['size']['length'], r['size']['thickness'], r['size']['height'],
                r['placedTotal'], r['kind'], '; '.join(r['needs']) or 'nothing'))
    if args.output:
        args.output.write_text(json.dumps(result, indent=1, default=str) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
