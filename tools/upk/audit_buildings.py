"""How the game's maps save their buildings: a read-only survey of a game install, made for
private/plans/done/prefab-library-plan.md (its stage B0).

  python -B tools/upk/audit_buildings.py <game install> <out.json> [--jobs 6] [--no-boxes]
  python -B tools/upk/audit_buildings.py <game install> <out.json> --editing [--jobs 6]   (what editing them needs)

Over every base map and streamed level a live DefaultMaps.ini record names:
- the building volumes (XComBuildingVolume): what each saves, its floors, its flags, whether it is turned or scaled;
- each floor: its floor volumes (XComFloorVolume) and their boxes, heights and FloorNumber, the pieces it lists
  (m_aCachedActors: ResidentActor and CutdownFloor), the emitters it lists;
- the pieces: which classes are listed, on how many floors, whether a piece saves a floor component of its own, and
  bCutoutMask on its main mesh component;
- the cursor volumes (XComCursorVolume), the stair volumes (XComStairVolume) and the tile grid's height;
- bCutoutMask by mesh: whether the listed pieces of one mesh all have it or all lack it;
- the listing rule (--no-boxes leaves it out): the game's editor lists a piece on every floor whose volume it
  touches with its bottom more than 20 units under the volume's top, and a piece with bCutoutMask only on the lowest
  of them, with CutdownFloor the index of the highest (research/native/building-cutaway.md, RebuildCachedActors).
  listing() is that rule; each listed piece's world box, from its mesh's vertices, is put through it and the answer
  compared with what the map saves, and again with the box let come within 2 to 64 units of a volume (the game goes
  by the piece's collision, which is a little larger than its mesh).

The JSON holds one record per package and the summary; the summary is also printed.
"""
import argparse
import collections
import json
import multiprocessing
import os
import struct
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PL = 'TheWorld.PersistentLevel'
PIECES = ('XComLevelActor', 'StaticMeshActor', 'XComDestructibleActor', 'XComFracLevelActor', 'XComDecoFracLevelActor',
          'XComInteractiveLevelActor', 'KAsset', 'XComLadder', 'XComCollectible')
FLAGS = ('IsUfo', 'IsDropShip', 'IsInside', 'm_bIsInternalBuilding', 'm_bAllowBuildingReveal')
SLACKS = (0.0, 2.0, 8.0, 16.0, 32.0, 64.0)  # how near a floor volume counts as touching it, tried in turn
MARGIN = 20.0  # the exe's constant: a piece is a floor's when its bottom is more than this under the volume's top


def paths():
    for folder in ('.', '../viewer', '../bake', '../editor'):
        sys.path.insert(0, os.path.normpath(os.path.join(HERE, folder)))


def touched(box, floors, margin=MARGIN, slack=0.0):
    """The indices of the floors a world box [x0, x1, y0, y1, z0, z1] counts for: it meets one of the floor's volume
    boxes ([x0, y0, z0, x1, y1, z1]), or comes within `slack` of it, and its bottom is more than `margin` under that
    volume's top."""
    out = []
    for k, volumes in enumerate(floors):
        for v in volumes:
            if v and box[4] < v[5] - margin and all(
                    box[2 * j] <= v[j + 3] + slack and box[2 * j + 1] >= v[j] - slack for j in range(3)):
                out.append(k)
                break
    return out


def listing(floors, mask):
    """Where the game's editor lists a piece that counts for the floors `floors` (indices, as touched() gives):
    [(floor index, CutdownFloor)]. A piece with bCutoutMask is listed on the lowest only, its CutdownFloor the index
    of the highest when that is another floor (0: none); any other piece on each, with no CutdownFloor."""
    if not floors:
        return []
    if mask and len(floors) > 1:
        return [(min(floors), max(floors))]
    return [(k, 0) for k in sorted(floors)]


def keys(props):
    return sorted(k if not s else '%s[%d]' % (k, s) for k, s in props)


def flat(box):
    return [*box['min'], *box['max']] if box else None


def count(prop):
    """The length of an array property, from its value's first four bytes."""
    return struct.unpack_from('<i', prop['value'], 0)[0] if prop else 0


def one(job):
    name, role, path, boxes = job
    paths()
    from package import Package
    import scene_metadata
    out = dict(map=name, role=role)
    try:
        p = Package(path)
    except Exception as error:  # noqa: BLE001
        return dict(out, error=str(error))
    level = p.by_name.get(PL)
    if level is None:
        return dict(out, error='no level')
    actors = p.children.get(level, [])
    out['volumes'] = {c: n for c, n in collections.Counter(p.cls(i) for i in actors).items() if 'Volume' in c}

    def main_mesh(actor):
        return next((k for k in p.children.get(actor, []) if 'MeshComponent' in p.cls(k)), None)

    def masked(actor):
        mesh = main_mesh(actor)
        try:
            return bool(p.effective(mesh, 'bCutoutMask')) if mesh else None
        except Exception:  # noqa: BLE001
            return None

    buildings, listed_volumes, residents = [], set(), {}
    geometry = {}  # building -> [floor volume boxes per floor]
    for i in actors:
        if p.cls(i) != 'XComBuildingVolume':
            continue
        try:
            props = p.properties(i)[0]
            floors = []
            for fi, row in enumerate(p.structs(p.effective(i, 'Floors'))):
                def value(key, row=row):
                    return row.get((key, 0), {}).get('value')
                refs = [r for r in p.refs(value('FloorVolumes')) if r > 0]
                listed_volumes.update(refs)
                vboxes = [flat(scene_metadata.volume_bounds(p, r)) for r in refs]
                geometry.setdefault(i, []).append(vboxes)
                entries = p.structs(value('m_aCachedActors'))
                members = []
                for e in entries:
                    ref = e.get(('ResidentActor', 0), {}).get('value', 0)
                    if ref <= 0:
                        continue
                    cut = e.get(('CutdownFloor', 0), {}).get('value', 0)
                    residents.setdefault(ref, []).append((i, fi, cut))
                    members.append((p.cls(ref), cut))
                emitters = value('m_aCachedEmitters')
                floors.append(dict(
                    keys=keys(row), volumes=len(refs), boxes=vboxes,
                    numbers=[p.effective(r, 'FloorNumber') for r in refs],
                    turned=sum(p.effective(r, 'Rotation') not in (None, [0, 0, 0]) for r in refs),
                    entryKeys=[[list(k), n] for k, n in collections.Counter(tuple(keys(e)) for e in entries).items()],
                    members=[[c, cut, n] for (c, cut), n in collections.Counter(members).items()],
                    emitters=(len(emitters) - 4) // 4 if emitters else 0,
                    centre=value('fCenterZ') is not None))
            vis = props.get(('VisGroupIdxToHideWhenOccluding', 0))
            buildings.append(dict(
                name=p.name(i).split('.')[-1], keys=keys(props), floors=floors,
                flags={k: props[(k, 0)]['value'] for k in FLAGS if (k, 0) in props},
                tag=str(props.get(('Tag', 0), {}).get('value')), box=flat(scene_metadata.volume_bounds(p, i)),
                turned=p.effective(i, 'Rotation') not in (None, [0, 0, 0]), scaled=p.effective(i, 'DrawScale3D') is not None,
                externalGroups=count(props.get(('ExternalMeshGroups', 0))),
                visGroups=(len(vis['value']) - 4) // 4 if vis else 0))
        except Exception as error:  # noqa: BLE001
            buildings.append(dict(name=p.name(i).split('.')[-1], error=repr(error)))
    out['buildings'] = buildings

    fv, unlisted = collections.Counter(), 0
    for i in actors:
        if p.cls(i) != 'XComFloorVolume':
            continue
        try:
            fv[tuple(keys(p.properties(i)[0]))] += 1
        except Exception:  # noqa: BLE001
            fv[('unreadable',)] += 1
        unlisted += i not in listed_volumes
    out['floorVolumeKeys'] = [[list(k), n] for k, n in fv.most_common(6)]
    out['floorVolumesUnlisted'] = unlisted

    pieces, by_mesh = collections.Counter(), collections.Counter()
    for i in actors:
        cls = p.cls(i)
        if cls not in PIECES:
            continue
        child = any(p.cls(k) == 'XComFloorComponent' for k in p.children.get(i, []))
        try:
            prop = p.own(i, 'FloorComponent')
            saved = isinstance(prop, int) and prop > 0
        except Exception:  # noqa: BLE001
            saved = None
        pieces[(cls, i in residents, child, saved, masked(i))] += 1
        if i in residents and masked(i) is not None:
            try:
                mesh = p.effective(main_mesh(i), 'StaticMesh', 0)
                by_mesh[(p.name(mesh) if mesh else 'none', masked(i))] += 1
            except Exception:  # noqa: BLE001
                pass
    out['pieces'] = [[*k, n] for k, n in pieces.items()]
    out['meshMask'] = [[*k, n] for k, n in by_mesh.items()]

    # each listed piece: the floors of one building it is on, and the rule's answer from its box
    lists = collections.Counter()
    rule, sweep = collections.Counter(), collections.Counter()
    misses = []
    meshes = {}
    for ref, rows in residents.items():
        mask = masked(ref)
        per = collections.defaultdict(list)
        for b, k, cut in rows:
            per[b].append((k, cut))
        for b, saved in per.items():
            saved = sorted(saved)
            lists[(str(mask), len(saved), sum(1 for _, cut in saved if cut))] += 1
            if not boxes or mask is None:
                continue
            try:
                import native_lights
                box = native_lights.mesh_box(p, main_mesh(ref), meshes)
            except Exception:  # noqa: BLE001
                rule[(str(mask), 'no box')] += 1
                continue
            for slack in SLACKS:
                sweep[(slack, listing(touched(box, geometry.get(b, []), slack=slack), mask) == saved)] += 1
            want = listing(touched(box, geometry.get(b, [])), mask)
            if want == saved:
                verdict = 'same'
            elif [k for k, _ in want] == [k for k, _ in saved]:
                verdict = 'same floors, other cutdown'
            elif not want:
                verdict = 'rule lists none'
            else:
                verdict = 'other floors'
            rule[(str(mask), verdict)] += 1
            if verdict != 'same' and len(misses) < 12:
                misses.append(dict(piece=p.name(ref).split('.')[-1], cls=p.cls(ref), mask=mask, saved=saved, rule=want,
                                   box=[round(v, 1) for v in box], floors=geometry.get(b, [])))
    out['listings'] = [[*k, n] for k, n in lists.items()]
    out['rule'] = [[*k, n] for k, n in rule.items()]
    out['ruleSlack'] = [[*k, n] for k, n in sweep.items()]
    out['ruleMisses'] = misses
    out['residentClasses'] = sorted(collections.Counter(p.cls(r) for r in residents).items())

    cursor = []
    for i in actors:
        if p.cls(i) != 'XComCursorVolume':
            continue
        try:
            cursor.append(dict(floor=p.effective(i, 'm_iFloorNumber'), stair=bool(p.effective(i, 'm_bTreatAsStair', False)),
                               turned=p.effective(i, 'Rotation') not in (None, [0, 0, 0]),
                               box=flat(scene_metadata.volume_bounds(p, i))))
        except Exception as error:  # noqa: BLE001
            cursor.append(dict(error=repr(error)))
    out['cursor'] = cursor
    lv = [i for i in actors if p.cls(i) == 'XComLevelVolume']
    out['level'] = flat(scene_metadata.volume_bounds(p, lv[0])) if lv else None
    return out


def brush_polygons(p, model):
    """A brush model's polygons, from its Polys (the polygons it was built from; the BSP's points also hold texture
    bases): [[(x, y, z)]] and the model's bounds (origin, extent), or None where they do not read."""
    try:
        _, end = p.properties(model)
        origin, extent = struct.unpack_from('<3f', p.data, end), struct.unpack_from('<3f', p.data, end + 12)
        polys = next((k for k in p.children.get(model, []) if p.cls(k) == 'Polys'), None)
        if polys is None:
            return None
        _, at = p.properties(polys)
        count, most = struct.unpack_from('<ii', p.data, at)
        if not 0 <= count <= most < 100000:
            return None
        at += 12
        out = []
        for _ in range(count):
            at += 48
            n = struct.unpack_from('<i', p.data, at)[0]
            out.append([struct.unpack_from('<3f', p.data, at + 4 + 12 * k) for k in range(n)])
            at += 4 + 12 * n + 4 + 4 + 8 + 4 + 16 + 36 + 8
        return out, (origin, extent)
    except (ValueError, struct.error):
        return None


def box_brush(p, volume):
    """Whether a volume's brush is a plain box: six polygons whose corners are the eight corners of its bounds (within
    half a unit). None for no brush, or one that does not read."""
    model = p.effective(volume, 'Brush', 0) or 0
    if model <= 0:
        return None
    read = brush_polygons(p, model)
    if read is None:
        return None
    polygons, (origin, extent) = read
    corners = set()
    for v in (v for poly in polygons for v in poly):
        corner = []
        for k in range(3):
            if abs(v[k] - (origin[k] - extent[k])) <= 0.5:
                corner.append(0)
            elif abs(v[k] - (origin[k] + extent[k])) <= 0.5:
                corner.append(1)
            else:
                return False
        corners.add(tuple(corner))
    return len(polygons) == 6 and len(corners) == 8


def editing(job):
    """What the editing of a map's own buildings depends on (private/plans/done/map-buildings-editable-plan.md, step
    E0), for one package: per building, whether its brush and its floor volumes' are plain boxes, whether the Kismet
    names it or its floor volumes, which other exports reference it or them (the level's actor list and the building's
    own Floors left out), its tag, empty floors, two volumes of one floor with the same box, and whether it is a van's
    (more than half its residents placed by one prefab that has a car body, as the compiler tells a van)."""
    name, role, path = job
    paths()
    from package import Package
    import native_copy
    import props as legacy_props
    import scene_metadata
    out = dict(map=name, role=role)
    try:
        p = Package(path)
    except Exception as error:  # noqa: BLE001
        return dict(out, error=str(error))
    level = p.by_name.get(PL)
    if level is None:
        return dict(out, error='no level')
    actors = [i for i in p.children.get(level, []) if p.exports[i - 1]['outer'] == level]
    kismet = scene_metadata.kismet_references(p)
    prefabs = scene_metadata.prefab_members(p)
    partners = set()
    for i in actors:
        try:
            if (p.effective(i, 'HidingPartner', 0) or 0) > 0:
                partners.add(i)
        except Exception:  # noqa: BLE001
            pass
    walker = native_copy.Walker(p)
    # every object reference of every export's tagged properties: target -> [(export, property)]
    referenced = collections.defaultdict(list)
    for i in range(1, len(p.exports) + 1):
        e = p.exports[i - 1]
        try:
            start = legacy_props.props_start(p.data, e, p.names)
            data = bytes(p.data[e['off']:e['off'] + e['size']])
            for prop, at in walker.refs(data, start - e['off'], len(data)):
                v = struct.unpack_from('<i', data, at)[0]
                if v > 0:
                    referenced[v].append((i, prop))
        except Exception:  # noqa: BLE001  a class whose properties do not walk
            continue
    buildings = []
    for i in actors:
        if p.cls(i) != 'XComBuildingVolume':
            continue
        try:
            rows = p.structs(p.effective(i, 'Floors'))
            floors, volumes, residents = [], [], set()
            for row in rows:
                listed = row.get(('FloorVolumes', 0), {}).get('value')
                refs = [r for r in p.refs(listed) if r > 0] if listed else []
                volumes += refs
                cached = row.get(('m_aCachedActors', 0), {}).get('value')
                residents |= {e.get(('ResidentActor', 0), {}).get('value', 0) for e in p.structs(cached)} if cached else set()
                boxes = [tuple(round(v, 1) for v in flat(scene_metadata.volume_bounds(p, r)) or []) for r in refs]
                floors.append(dict(volumes=len(refs), sameBox=len(boxes) - len(set(boxes))))
            residents.discard(0)
            mine = {i, *volumes}
            others = sorted({'%s %s' % (p.cls(src), prop.split('[')[0]) for v in mine for src, prop in referenced.get(v, [])
                             if src != i})
            by_prefab = collections.Counter(prefabs.get(r) for r in residents if prefabs.get(r))
            van = any(n * 2 > len(residents) and any(prefabs.get(a) == pf for a in partners) for pf, n in by_prefab.items())
            buildings.append(dict(
                name=p.name(i).split('.')[-1], floors=floors, tag=str(p.effective(i, 'Tag')),
                box=box_brush(p, i), volumeBoxes=[box_brush(p, v) for v in volumes],
                kismet=sorted({k for v in mine for k in kismet.get(v, [])}), references=others, van=van,
                ufo=bool(p.effective(i, 'IsUfo', False))))
        except Exception as error:  # noqa: BLE001
            buildings.append(dict(name=p.name(i).split('.')[-1], error=repr(error)))
    out['buildings'] = buildings
    return out


def summarise_editing(rows):
    bad = [[r['map'], r['error']] for r in rows if 'error' in r]
    rows = [r for r in rows if 'error' not in r]
    every = [(r['map'], r['role'], b) for r in rows for b in r['buildings']]
    B = [(m, role, b) for m, role, b in every if 'error' not in b]
    with_floors = [(m, role, b) for m, role, b in B if b['floors']]
    editable = [(m, role, b) for m, role, b in with_floors
                if role == 'base' and not b['van'] and all(f['volumes'] for f in b['floors'])]
    refs = collections.Counter(x for *_, b in with_floors for x in b['references'])
    return dict(
        packages=len(rows), unreadable=bad, buildings=len(every),
        unreadableBuildings=[[m, b['name'], b['error']] for m, _, b in every if 'error' in b][:8],
        withFloors=len(with_floors),
        inStreams=sum(1 for _, role, _ in with_floors if role == 'stream'),
        vans=[[m, b['name']] for m, role, b in with_floors if b['van']],
        withAnEmptyFloor=[[m, b['name'], [f['volumes'] for f in b['floors']]] for m, _, b in with_floors
                          if any(not f['volumes'] for f in b['floors'])],
        taggedWithFloors=table(collections.Counter(b['tag'] for *_, b in with_floors if b['tag'] != 'XComBuildingVolume')),
        floorsWithTwoVolumesOfOneBox=[[m, b['name'], k] for m, _, b in with_floors for k, f in enumerate(b['floors'])
                                      if f['sameBox']],
        buildingBrushes=table(collections.Counter(str(b['box']) for *_, b in with_floors)),
        floorVolumeBrushes=table(collections.Counter(str(v) for *_, b in with_floors for v in b['volumeBoxes'])),
        notBoxes=[[m, b['name'], b['box'], b['volumeBoxes'].count(False)] for m, _, b in with_floors
                  if b['box'] is False or False in b['volumeBoxes']][:20],
        kismetNamed=[[m, b['name'], b['kismet']] for m, _, b in with_floors if b['kismet']],
        referencedBy=table(refs),
        ufo=sum(1 for *_, b in with_floors if b['ufo']),
        editable=len(editable), editableMaps=len({m for m, _, _ in editable}))


def table(counter, top=None):
    return [[k if isinstance(k, (int, str)) else list(k), n]
            for k, n in sorted(counter.items(), key=lambda x: (-x[1], str(x[0])))[:top]]


def summarise(rows):
    bad = [[r['map'], r['error']] for r in rows if 'error' in r]
    rows = [r for r in rows if 'error' not in r]
    base = [r for r in rows if r['role'] == 'base']
    every = [(r['map'], b) for r in rows for b in r['buildings']]
    B = [(m, b) for m, b in every if 'error' not in b]
    F = [(b, k, f) for _, b in B for k, f in enumerate(b['floors'])]
    s = dict(packages=len(rows), baseMaps=len(base), unreadable=bad,
             buildings=len(every), unreadableBuildings=[[m, b['name'], b['error']] for m, b in every if 'error' in b][:8],
             packagesWithBuildings=sum(1 for r in rows if r['buildings']),
             baseMapsWithout=[r['map'] for r in base if not r['buildings']],
             floorsPerBuilding=table(collections.Counter(len(b['floors']) for _, b in B)),
             buildingKeys=table(collections.Counter(k for _, b in B for k in b['keys'])),
             buildingFlags=table(collections.Counter('%s=%s' % kv for _, b in B for kv in b['flags'].items())),
             buildingsTurned=sum(b['turned'] for _, b in B), buildingsScaled=sum(b['scaled'] for _, b in B),
             tagsOfBuildingsWithoutFloors=table(collections.Counter(b['tag'] for _, b in B if not b['floors']), 8),
             floorKeys=table(collections.Counter(k for *_, f in F for k in f['keys'])),
             volumesPerFloor=table(collections.Counter(f['volumes'] for *_, f in F)),
             floorNumberLessIndex=table(collections.Counter(
                 n - k if isinstance(n, int) else str(n) for _, k, f in F for n in f['numbers'])),
             floorVolumesTurned=sum(f['turned'] for *_, f in F),
             floorsWithSavedCentre=sum(f['centre'] for *_, f in F),
             floorsWithEmitters=sum(1 for *_, f in F if f['emitters']), emitters=sum(f['emitters'] for *_, f in F),
             floorVolumesNoBuildingLists=sum(r['floorVolumesUnlisted'] for r in rows))
    heights, gaps, entry_keys, cut = (collections.Counter() for _ in range(4))
    for _, b in B:
        spans = []
        for f in b['floors']:
            bx = [x for x in f['boxes'] if x]
            for x in bx:
                heights[round((x[5] - x[2]) / 16) * 16] += 1
            if bx:
                spans.append((min(x[2] for x in bx), max(x[5] for x in bx)))
        for (_, top), (bottom, _) in zip(spans, spans[1:]):
            gaps[round((bottom - top) / 8) * 8] += 1
    for _, k, f in F:
        for key, n in f['entryKeys']:
            entry_keys[' '.join(key)] += n
        for _, c, n in f['members']:
            cut['none' if not c else 'index %+d' % (c - k)] += n
    s.update(floorVolumeHeights=table(heights, 10), gapToNextFloor=table(gaps, 8), entryKeys=table(entry_keys),
             cutdownFloorAgainstFloorIndex=table(cut))
    ufo = [b for _, b in B if b['flags'].get('IsUfo')]
    s['ufoBuildings'] = dict(count=len(ufo), floors=table(collections.Counter(len(b['floors']) for b in ufo)),
                             members=sorted(sum(n for f in b['floors'] for *_, n in f['members']) for b in ufo))
    pieces, residents, lists, rule = (collections.Counter() for _ in range(4))
    for r in rows:
        for cls, resident, child, saved, mask, n in r['pieces']:
            if r['role'] == 'base':
                pieces[(cls, 'listed' if resident else 'not listed', 'mask' if mask else 'no mask',
                        'saves a floor component' if child or saved else 'saves none')] += n
        for c, n in r['residentClasses']:
            residents[c] += n
        for mask, floors, cuts, n in r['listings']:
            lists[('mask ' + mask, '%d floors' % floors, '%d with CutdownFloor' % cuts)] += n
        for mask, verdict, n in r['rule']:
            rule[('mask ' + mask, verdict)] += n
    sweep = collections.Counter()
    for r in rows:
        for slack, same, n in r['ruleSlack']:
            sweep[(slack, same)] += n
    s['ruleSameBySlack'] = [[slack, sweep[(slack, True)], sweep[(slack, False)]] for slack in SLACKS]
    # bCutoutMask by mesh, over the listed pieces: how far the mesh alone says whether a piece has it
    mesh = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        for name, mask, n in r['meshMask']:
            mesh[name][bool(mask)] += n
    both = {k: v for k, v in mesh.items() if v[0] and v[1]}
    s['maskByMesh'] = dict(
        meshes=len(mesh), alwaysMasked=sum(1 for v in mesh.values() if v[1] and not v[0]),
        neverMasked=sum(1 for v in mesh.values() if v[0] and not v[1]), both=len(both),
        pieces=sum(sum(v) for v in mesh.values()),
        piecesTheMajorityGetsRight=sum(max(v) for v in mesh.values()),
        mostMixed=sorted(([k, *v] for k, v in both.items()), key=lambda x: -min(x[1], x[2]))[:10])
    s.update(piecesOfBaseMaps=table(pieces), listedClasses=table(residents), listingsPerPieceAndBuilding=table(lists),
             ruleAgainstSaved=table(rule), ruleMisses=[dict(m, map=r['map']) for r in rows for m in r['ruleMisses']][:40])
    volumes, maps = collections.Counter(), collections.Counter()
    for r in rows:
        for c, n in r['volumes'].items():
            volumes[c] += n
            maps[c] += 1
    s['volumeClasses'] = [[c, n, maps[c]] for c, n in volumes.most_common()]
    C = [(r['map'], c) for r in rows for c in r['cursor'] if 'error' not in c]
    per = collections.Counter(m for m, _ in C)
    s['cursorVolumes'] = dict(
        count=len(C), maps=len(per), mapsWithFour=sum(1 for n in per.values() if n == 4),
        floors=table(collections.Counter(c['floor'] for _, c in C)), stairs=sum(c['stair'] for _, c in C),
        turned=sum(c['turned'] for _, c in C),
        heights=table(collections.Counter(round((c['box'][5] - c['box'][2]) / 16) * 16 for _, c in C if c['box']), 6))
    s['gridHeights'] = table(collections.Counter(round(r['level'][5] - r['level'][2]) for r in base if r['level']))
    return s


def show(s):
    for key, value in s.items():
        if key == 'ruleMisses':
            print('ruleMisses: %d listed in the JSON' % len(value))
        elif isinstance(value, list) and value and isinstance(value[0], (list, dict)):
            print(key + ':')
            for row in value:
                print('   ', row if isinstance(row, dict) else '  '.join(str(v) for v in row))
        else:
            print('%s: %s' % (key, value))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('game', help='the game install (the folder that holds XComGame)')
    parser.add_argument('out', help='the JSON to write')
    parser.add_argument('--jobs', type=int, default=6)
    parser.add_argument('--no-boxes', action='store_true', help="leave out the listing rule's check")
    parser.add_argument('--editing', action='store_true',
                        help="what editing the maps' own buildings depends on (editing(); the buildings plan's E0)")
    args = parser.parse_args()
    paths()
    import library
    if args.editing:
        jobs = [(n, r, str(path)) for n, r, path in library.donors(Path(args.game))]
        with multiprocessing.Pool(args.jobs) as pool:
            rows = pool.map(editing, jobs, chunksize=1)
        summary = summarise_editing(rows)
        Path(args.out).write_text(json.dumps(dict(summary=summary, packages=rows)), encoding='utf-8', newline='\n')
        show(summary)
        return
    jobs = [(n, r, str(path), not args.no_boxes) for n, r, path in library.donors(Path(args.game))]
    with multiprocessing.Pool(args.jobs) as pool:
        rows = pool.map(one, jobs, chunksize=1)
    summary = summarise(rows)
    Path(args.out).write_text(json.dumps(dict(summary=summary, packages=rows)), encoding='utf-8', newline='\n')
    show(summary)


if __name__ == '__main__':
    main()
