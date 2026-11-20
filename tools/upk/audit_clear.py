"""What clearing a map touches: a read-only survey made for private/plans/done/clear-map-plan.md (its step C0).

  python -B tools/upk/audit_clear.py --out <out.json> [--cache <cache>] [--install <game install>] [--jobs 6]
      [--maps NAME ...]

Folders default to the settings (`python tools/viewer/viewer.py settings`: cache, install).

For every map exported in the viewer cache (each map folder's newest `*-v<N>-map*/scene.json`), with the install's
package of the same name read where the export lacks something (its level's actors and Kismet records, which exports
before 37 carried as `content`, are read from the package: level_content):
- the pieces the mission's script names (`referencedBy`) and what names them, lights too;
- the map's own landings: the actors of each landing prefab (`DGN_DropShipSoldierSpawn`: the drop zone's frame, the
  evac volume, the player start, a PointInSpace, six soldier points) and of each grounded Skyranger prefab, found by
  the PrefabInstance's archetype-to-instance map, with class, place, turn, tag and which of them save a Rotation;
- LWR's `LZArray` lines for the map (`<install>\\XEW\\XComGame\\Config\\DefaultLZMutator.ini`), placed by
  XComLZMutator's offsets, and the line each own landing matches (by its six soldier points, order free);
- the ground under each landing zone (64 under StartLoc; the frame's height for an own landing) against the tile
  grid's bottom (`tileGrid`: origin, dimensions, 64 units a level);
- for a clear: the actor classes `clear_level` would take out (CLEAR_OUT), the ones it leaves (CLEAR_STAYS), the
  pieces and lights the page deletes by records, the Kismet objects, and every class on none of these, with counts;
- LWR's patch level's pieces for the map (`streams` of kind lwr);
- the ambient sounds, with the sounds their exports name.

Over every base map the install's DefaultMaps.ini names (as audit_spawns.py finds them): the own landings, the lines,
which line each landing matches and the landings no line matches; the spawn groups the native would see (the
soldier points in PrefabInstances not named "Doorway", keyed by tag, sorted by name: research/evidence/
clear-map-p0-2026-11-13.md, read 1); and where the dropship intro puts its flight for the map
(CIN_DropshipIntros' Set Location actions, read 2) against the map's grounded Skyrangers.

The JSON holds one record per map and a summary; a short summary is printed.
"""
import argparse
import collections
import json
import math
import multiprocessing
import os
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEVEL = 'TheWorld.PersistentLevel.'
LANDING_PREFAB = 'DGN_DropShipSoldierSpawn.Prefabs.SoldierSpawns_DrpshipVol'
SKYRANGER_PREFAB = 'VEH_Lv1Skyranger_MOD.Prefabs.PRE_SkyrangerGrounded'
# a landing actor's part, by its archetype's name (XComLZMutator.FindLZObjectsByArchetype and HideDropShip)
LANDING_ROLES = {'SoldierSpawns_DrpshipVol_12Arc0': 'frame', 'SoldierSpawns_DrpshipVol_Arc0': 'evac',
                 'SoldierSpawns_DrpshipVol_2Arc0': 'playerStart', 'SoldierSpawns_DrpshipVol_12Arc1': 'point',
                 'SoldierSpawns_DrpshipVol_Arc1': 'spawn1', 'SoldierSpawns_DrpshipVol_Arc2': 'spawn2',
                 'SoldierSpawns_DrpshipVol_Arc3': 'spawn3', 'SoldierSpawns_DrpshipVol_Arc4': 'spawn4',
                 'SoldierSpawns_DrpshipVol_Arc5': 'spawn5', 'SoldierSpawns_DrpshipVol_7Arc0': 'spawn6',
                 'SoldierSpawns_DrpshipVol_8Arc10': 'point2'}
LANDING_ROLES.update({'SoldierSpawns_DrpshipVol_8Arc%d' % k: 'emitter%d' % k for k in range(10)})
SKYRANGER_ROLES = {'PRE_SkyrangerGrounded_4Arc0': 'mesh', 'PRE_SkyrangerGrounded_Arc1': 'emitter',
                   'PRE_SkyrangerGrounded_Arc2': 'point', 'PRE_SkyrangerGrounded_5Arc0': 'sound'}
# not in either prefab, hidden with the Skyranger by LWR (HideDropShip)
LANDING_EXTRA_ARCHETYPES = ('ARC_Skyranger_Ground_Periphery',)

# XComLZMutator's defaultproperties: each actor's offset from a line's StartLoc, before StartDir's turn, the soldier
# points' and how far an inside zone's go back (AdjustOffsets: ESL_Inside, ESL_Alternate and ESL_NoEvacZone), as the
# editor's own reader has them (tools/viewer/spawns.py, whose 'volume' is the evac zone's here; review finding 55)
sys.path.insert(0, str(HERE.parent / 'viewer'))
import spawns as viewer_spawns  # noqa: E402
OFFSETS = {role: viewer_spawns.OFFSETS['volume' if role == 'evac' else role] for role in ('frame', 'evac', 'playerStart', 'point')}
SPAWN_OFFSETS = viewer_spawns.SOLDIERS
INSIDE_BACK = viewer_spawns.INSIDE_BACK
DIRECTIONS = ('ELZD_North', 'ELZD_East', 'ELZD_South', 'ELZD_West')
QUARTER = 16384
LEVEL_HEIGHT = 64.0
UNIT_TYPES = ('UNIT_TYPE_Soldier', 'UNIT_TYPE_Tank', 'UNIT_TYPE_Alien', 'UNIT_TYPE_AlienInUFO', 'UNIT_TYPE_Loot',
              'UNIT_TYPE_Animal', 'UNIT_TYPE_Civilian', 'UNIT_TYPE_Player', 'UNIT_TYPE_MPTeamOne',
              'UNIT_TYPE_MPTeamTwo', 'UNIT_TYPE_CovertOperative')
MATCH_EXACT = 4.0       # units: a line places the six soldier points where the landing has them
MATCH_NEAR = 48.0       # half a tile
MATCH_TILE = 144.0      # a tile and a half: the same place, a tile off

# clear_level (clear-map plan, section 7 step 1): taken out of the level's actor list on a cleared build, but never
# an actor of the landing's prefabs. Lights of these classes that a delete record names are the records' already.
CLEAR_OUT = ('XComBuildingVolume', 'XComFloorVolume', 'XComCursorVolume',
             'Emitter', 'DecalActor', 'DecalActorMovable', 'LensFlareSource',
             'PathBlockingVolume', 'GameCameraBlockingVolume', 'BlockingVolume', 'XComDamageVolume',
             'XComCoverSeed',
             'PointLight', 'PointLightMovable', 'PointLightToggleable',
             'SpotLight', 'SpotLightMovable', 'SpotLightToggleable', 'GeneratedMeshAreaLight')
# left by clear_level (section 2's "Stay" rows and what the mission, the spawns and the sky need)
CLEAR_STAYS = ('WorldInfo', 'XComLevelVolume', 'DominantDirectionalLight', 'DirectionalLight', 'SkyLight',
               'PlayerStart', 'XComSpawnPoint', 'XComSpawnPoint_Alien', 'XComAlienPod', 'XComAlienPod_Abduction',
               'XComAlienPod_Terror', 'XComAlienPod_Hunter', 'XComMeldContainerSpawnPoint', 'XComAlienPathNode',
               'XComNoSpawnVolume', 'XComAlienSpawnVolume', 'XComCapturePointVolume', 'XComWaveSystem',
               'PointInSpace', 'PrefabInstance', 'TriggerVolume', 'PostProcessVolume', 'LightmassImportanceVolume',
               'XComRebuildWorldDataVolume', 'AmbientSound', 'AmbientSoundSimple', 'AmbientSoundSimpleToggleable',
               'VisGroupActor', 'XComRainVolume', 'XComWeatherControl', 'XComSquadVisiblePoint')
# the classes of the pieces the page shows and deletes by records; an actor of one that the export does not show
# (no mesh: CsmallScout_Farm's 74 empty XComFracLevelActors) is counted apart, as `unexported`
PIECE_CLASSES = ('XComLevelActor', 'XComOpacityFadeLevelActor', 'StaticMeshActor', 'XComDestructibleActor',
                 'XComCollectible', 'XComFracLevelActor', 'XComDecoFracLevelActor', 'KAsset', 'XComInteractiveLevelActor',
                 'XComLadder', 'XComMergedLevelActor', 'FracturedStaticMeshActor', 'InterpActor', 'SkeletalMeshActor')


# --- pure functions (tests: tools/upk/tests/test_audit_clear.py) -------------------------------------------------

LINE = re.compile(r'^\s*LZArray\s*=\s*\((.*)\)\s*$')


def parse_lz_line(line):
    """One `LZArray=(...)` line of DefaultLZMutator.ini as a dict (map, kind, start, direction, missionType,
    councilType, alt, altDirection, other: fields not known here), or None for any other line (a comment too)."""
    m = LINE.match(line.rstrip('\r\n'))
    if not m:
        return None
    body = m.group(1)
    fields, depth, cur = [], 0, ''
    for ch in body:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            fields.append(cur)
            cur = ''
        else:
            cur += ch
    if cur:
        fields.append(cur)
    out = dict(map=None, kind=None, start=None, direction=None, missionType=None, councilType=None, alt=None,
               altDirection=None, other={})
    for f in fields:
        key, _, value = f.partition('=')
        key, value = key.strip(), value.strip()
        if key == 'MapName':
            out['map'] = value.strip('"')
        elif key == 'ESpawnLoc':
            out['kind'] = value
        elif key in ('StartLoc', 'AltSpawnLoc'):
            v = dict(re.findall(r'([XYZ])\s*=\s*(-?[\d.]+)', value))
            vec = [float(v.get(a, 0.0)) for a in 'XYZ']
            out['start' if key == 'StartLoc' else 'alt'] = vec
        elif key == 'StartDir':
            out['direction'] = value
        elif key == 'AltSpawnDir':
            out['altDirection'] = value
        elif key == 'MissionType':
            out['missionType'] = value
        elif key == 'CouncilType':
            out['councilType'] = value
        else:
            out['other'][key] = value
    return out if out['map'] else None


def turn(v, yaw):
    """A vector turned by a yaw in Unreal units (65536 a turn), as `vector >> rotator` turns it."""
    a = yaw * 2.0 * math.pi / 65536.0
    c, s = math.cos(a), math.sin(a)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2])


def direction_yaw(direction):
    return DIRECTIONS.index(direction) * QUARTER if direction in DIRECTIONS else 0


def zone_places(start, direction, kind='ESL_Normal', alt=None, alt_direction=None):
    """Where XComLZMutator.CalcLocations puts the landing's actors for a line: {frame, evac, playerStart, point:
    [x, y, z], spawns: six [x, y, z]}."""
    yaw = direction_yaw(direction)
    out = {role: [s + d for s, d in zip(start, turn(off, yaw))] for role, off in OFFSETS.items()}
    back = INSIDE_BACK if kind in ('ESL_Inside', 'ESL_Alternate', 'ESL_NoEvacZone') else 0.0
    if kind == 'ESL_Alternate' and alt is not None:
        base, base_yaw = alt, direction_yaw(alt_direction)
    else:
        base, base_yaw = start, yaw
    out['spawns'] = [[s + d for s, d in zip(base, turn((x, y - back, z), base_yaw))] for x, y, z in SPAWN_OFFSETS]
    return out


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def set_deviation(predicted, actual):
    """How far a set of predicted places is from a set of actual ones, order free: the largest, over both sets, of
    each place's distance to the nearest of the other set. None if either set is empty."""
    if not predicted or not actual:
        return None
    one = max(min(distance(p, a) for a in actual) for p in predicted)
    two = max(min(distance(a, p) for p in predicted) for a in actual)
    return max(one, two)


def line_deviation(landing, line):
    """Per part, how far the line's places are from a landing's actors ({role: [x, y, z]}, spawns a list): spawns,
    frame, evac, playerStart, point (None where the landing lacks the part)."""
    places = zone_places(line['start'], line['direction'], line['kind'] or 'ESL_Normal', line.get('alt'),
                         line.get('altDirection'))
    out = {'spawns': set_deviation(places['spawns'], landing.get('spawns') or [])}
    for role in OFFSETS:
        out[role] = distance(places[role], landing[role]) if landing.get(role) else None
    return out


def match_level(dev):
    """'exact' (the six points and the frame within MATCH_EXACT), 'spawns' (the six points within it), 'near' (the
    points within MATCH_NEAR), 'tile' (within MATCH_TILE), or 'none'."""
    s = dev.get('spawns')
    if s is None:
        return 'none'
    if s <= MATCH_EXACT:
        f = dev.get('frame')
        return 'exact' if f is not None and f <= MATCH_EXACT else 'spawns'
    if s <= MATCH_NEAR:
        return 'near'
    return 'tile' if s <= MATCH_TILE else 'none'


def best_line(landing, lines):
    """The line nearest a landing by its six points: (index into lines, deviations, level), or (None, None, 'none')."""
    best = (None, None, 'none')
    for k, line in enumerate(lines):
        if line.get('start') is None:
            continue
        dev = line_deviation(landing, line)
        if dev['spawns'] is None:
            continue
        if best[1] is None or dev['spawns'] < best[1]['spawns']:
            best = (k, dev, match_level(dev))
    return best


def is_kismet(cls):
    return cls.startswith('Seq') or cls in ('Sequence', 'SequenceFrame', 'SequenceFrameWrapped')


def sort_classes(actors, records=(), landing=(), out=CLEAR_OUT, stays=CLEAR_STAYS, pieces=PIECE_CLASSES):
    """Sort a map's actors for a clear. `actors`: (path, class) pairs; `records`: the paths the page deletes by records
    (pieces and lights); `landing`: the landing prefabs' actor paths (never out). Returns {group: {class: count}} for
    groups records, landing, out, stays, unexported (a piece class the page does not show), kismet, other (not an
    actor: a level volume's mesh), neither."""
    records, landing = set(records), set(landing)
    groups = {g: collections.Counter() for g in ('records', 'landing', 'out', 'stays', 'unexported', 'kismet', 'other',
                                                 'neither')}
    for path, cls in actors:
        if is_kismet(cls) or '.Main_Sequence' in path:
            g = 'kismet'
        elif path in landing:
            g = 'landing'
        elif path in records:
            g = 'records'
        elif cls in pieces:
            g = 'unexported'
        elif cls in out:
            g = 'out'
        elif cls in stays:
            g = 'stays'
        elif cls == 'StaticMesh' or path.count('.') != 2:
            g = 'other'
        else:
            g = 'neither'
        groups[g][cls] += 1
    return {g: dict(sorted(c.items())) for g, c in groups.items()}


def ground_levels(ground_z, grid_bottom):
    """How many 64-unit levels of the grid are under a ground height (may be fractional or negative)."""
    return (ground_z - grid_bottom) / LEVEL_HEIGHT


def sorted_group_keys(keys):
    """The native's order of spawn group tags: by their text, case-sensitive (FindSpawnGroup sorts the keys with the
    comparator at 0x657EE0, a wide-character compare of the names' text)."""
    return sorted(set(keys))


# --- reading a map's package -------------------------------------------------------------------------------------

def _vec(text):
    m = re.match(r'(?:Vector|Rotator)\(([^)]*)\)', text or '')
    return [float(x) for x in m.group(1).split(',')] if m else None


def read_level(path):
    """The level actors of a map package: {short name: {cls, archetype, props: {name: text}}}, the PrefabInstances'
    archetype-to-instance maps, the archetypes' saved Tag and UnitType, and each actor's sound references."""
    sys.path.insert(0, str(HERE))
    import upkinfo as U
    import props as P
    b, h = U.load(path)
    names, imps, exps = U.tables(b, h)
    children = collections.defaultdict(list)
    for n, e in enumerate(exps):
        if e['outer'] > 0:
            children[e['outer']].append(n + 1)
    actors, prefabs, archetypes = {}, {}, {}

    def values(e):
        saved, end = P.read_props(b, P.props_start(b, e, names), e['off'] + e['size'], names, imps, exps)
        return {str(p).split('[')[0].strip(): str(p).split(' = ', 1)[-1] for p in saved}, end

    for n, e in enumerate(exps):
        full = U.objname(n + 1, imps, exps)
        cls = U.clsname(e['cls'], imps, exps)
        if not full.startswith(LEVEL) or full.count('.') != 2:
            if (LANDING_PREFAB in full or SKYRANGER_PREFAB in full) and full.count('.') == 3:
                try:
                    v, _ = values(e)
                except Exception:  # noqa: BLE001
                    v = {}
                archetypes[full] = {k: v[k] for k in ('Tag', 'UnitType', 'Rotation') if k in v}
            continue
        try:
            v, end = values(e)
        except Exception as error:  # noqa: BLE001
            v, end = {'error': repr(error)}, None
        arch = U.objname(e['arch'], imps, exps) if e['arch'] else None
        name = full[len(LEVEL):]
        actors[name] = dict(cls=cls, archetype=arch, props=v, export=n + 1)
        if cls == 'XComSpawnPoint' and arch and arch not in archetypes:
            # a soldier point's tag and unit type may come from its archetype (the multiplayer prefabs' do, F-90):
            # read it where the package holds it, else mark it unknown
            if e['arch'] > 0:
                try:
                    av, _ = values(exps[e['arch'] - 1])
                except Exception:  # noqa: BLE001
                    av = {}
                archetypes[arch] = {k: av[k] for k in ('Tag', 'UnitType', 'Rotation') if k in av}
            else:
                archetypes[arch] = {'UnitType': 'unknown (archetype not in the package)'}
        if cls == 'PrefabInstance' and end is not None:
            try:
                count = struct.unpack_from('<i', b, end)[0]
                pairs = []
                if 0 <= count < 10000:
                    for k in range(count):
                        key, val = struct.unpack_from('<ii', b, end + 4 + 8 * k)
                        pairs.append((U.objname(key, imps, exps) if key else None,
                                      U.objname(val, imps, exps)[len(LEVEL):] if val > 0 else None))
                prefabs[name] = pairs
            except struct.error:
                prefabs[name] = []
        if cls.startswith('AmbientSound'):
            actors[name]['sounds'] = sound_refs(b, imps, exps, [n + 1] + children.get(n + 1, []), children)
    return dict(actors=actors, prefabs=prefabs, archetypes=archetypes)


def sound_refs(b, imps, exps, roots, children):
    """The SoundCue and SoundNodeWave imports, and the SoundNodeWave exports, named in the bytes of these exports and
    their sub-objects: a scan of every offset for an object reference to one (a survey's guess, not a parse)."""
    sys.path.insert(0, str(HERE))
    import upkinfo as U
    wanted = {}
    for k, i in enumerate(imps):
        if i['cls'] in ('SoundCue', 'SoundNodeWave'):
            wanted[-(k + 1)] = U.objname(-(k + 1), imps, exps)
    for k, e in enumerate(exps):
        # waves cooked into the map; its own sound cues (sub-objects) only lead to these, and a cue of another
        # actor's archetype is a chance match of the scan
        if U.clsname(e['cls'], imps, exps) == 'SoundNodeWave':
            wanted[k + 1] = U.objname(k + 1, imps, exps)
    todo, seen, found = list(roots), set(), set()
    while todo:
        x = todo.pop()
        if x in seen:
            continue
        seen.add(x)
        todo += children.get(x, [])
        e = exps[x - 1]
        data = b[e['off']:e['off'] + e['size']]
        for o in range(0, max(0, len(data) - 3)):
            v = struct.unpack_from('<i', data, o)[0]
            if v in wanted:
                found.add(wanted[v])
    return sorted(found)


def unit_type(props, archetype_props):
    text = props.get('UnitType') or (archetype_props or {}).get('UnitType')
    if not text:
        return 'UNIT_TYPE_Soldier'      # the class default (XComSpawnPoint.UnitType)
    return text.split('::')[-1]


def landings_of(level):
    """The map's own landings and grounded Skyrangers, from the PrefabInstances' maps."""
    actors, archetypes = level['actors'], level['archetypes']
    landings, skyrangers, doorway_groups, groups = [], [], collections.defaultdict(list), collections.OrderedDict()
    for pi, pairs in sorted(level['prefabs'].items(), key=lambda kv: actors[kv[0]]['export']):
        template = actors[pi]['props'].get('TemplatePrefab', '')
        rec = dict(prefabInstance=pi, template=template, tag=actors[pi]['props'].get('Tag'),
                   location=_vec(actors[pi]['props'].get('Location')),
                   rotation=_vec(actors[pi]['props'].get('Rotation')), actors={})
        soldier_points = []
        for arch, name in pairs:
            if name is None or name not in actors:
                continue
            a = actors[name]
            short = (arch or '').split('.')[-1]
            p = a['props']
            info = dict(actor=name, cls=a['cls'], location=_vec(p.get('Location')), rotation=_vec(p.get('Rotation')),
                        tag=p.get('Tag') or archetypes.get(arch, {}).get('Tag') or a['cls'],
                        savesRotation='Rotation' in p, savesLocation='Location' in p)
            if a['cls'] == 'XComSpawnPoint':
                info['unitType'] = unit_type(p, archetypes.get(arch))
                if info['unitType'] in UNIT_TYPES[:2]:
                    soldier_points.append(info)
            role = LANDING_ROLES.get(short) or SKYRANGER_ROLES.get(short) or short
            rec['actors'][role] = info
        if 'Doorway' not in template:
            for sp in soldier_points:
                groups.setdefault(sp['tag'], []).append(sp['actor'])
        else:
            for sp in soldier_points:
                doorway_groups[sp['tag']].append(sp['actor'])
        if template.startswith(LANDING_PREFAB):
            landings.append(rec)
        elif template.startswith(SKYRANGER_PREFAB):
            skyrangers.append(rec)
    # the native's fallback when no PrefabInstance holds a soldier point: every soldier point of the level
    fallback = collections.OrderedDict()
    if not groups:
        for name, a in actors.items():
            if a['cls'] == 'XComSpawnPoint':
                arch = a['archetype']
                if unit_type(a['props'], archetypes.get(arch)) in UNIT_TYPES[:2]:
                    tag = a['props'].get('Tag') or archetypes.get(arch, {}).get('Tag') or a['cls']
                    fallback.setdefault(tag, []).append(name)
    extra = [dict(actor=n, cls=a['cls'], archetype=a['archetype'], location=_vec(a['props'].get('Location')))
             for n, a in actors.items() if a['archetype'] and a['archetype'].split('.')[-1] in LANDING_EXTRA_ARCHETYPES]
    keys = sorted_group_keys(groups or fallback)
    native = dict(source='prefabs' if groups else ('level' if fallback else 'none'),
                  groups={k: len((groups or fallback)[k]) for k in keys}, order=keys,
                  doorwayPointsIgnored=sum(len(v) for v in doorway_groups.values()))
    return landings, skyrangers, extra, native


def landing_points(rec):
    """A landing record's parts as places for line matching: {frame, evac, playerStart, point, spawns}."""
    a = rec['actors']
    out = {role: a[role]['location'] for role in OFFSETS if role in a and a[role]['location']}
    out['spawns'] = [a['spawn%d' % k]['location'] for k in range(1, 7) if 'spawn%d' % k in a]
    return out


def level_content(path):
    """The level's actors and Kismet records of the package at `path`, [(path, class)], as the viewer's exporter reads
    them (composition.content_records) and exports before 37 wrote them into scene.json's `content`."""
    sys.path.insert(0, str(HERE.parent / 'viewer'))
    from composition import content_records
    from package import Package
    return [(r['path'], r['actorClass'] or '?') for r in content_records(Package(path))]


def survey_package(job):
    path, = job
    name = Path(path).stem
    try:
        level = read_level(path)
        landings, skyrangers, extra, native = landings_of(level)
        content = level_content(path)
    except Exception as error:  # noqa: BLE001
        return name, dict(error=repr(error))
    sounds = [dict(actor=n, cls=a['cls'], location=_vec(a['props'].get('Location')), sounds=a.get('sounds', []),
                   skyranger=bool(a['archetype'] and SKYRANGER_PREFAB in a['archetype']))
              for n, a in sorted(level['actors'].items()) if a['cls'].startswith('AmbientSound')]
    return name, dict(landings=landings, skyrangers=skyrangers, landingExtras=extra, native=native,
                      ambient=sounds, actorClasses=dict(collections.Counter(a['cls'] for a in level['actors'].values())),
                      content=content)


# --- the intro's places --------------------------------------------------------------------------------------------

def intro_anchors(intro_path):
    """Where CIN_DropshipIntros puts its flight for each map: {map: [{group, location, rotation, action}]}, group None
    for a map whose switch entry leads straight to a Set Location, else 0, 1 or 2 (a Compare Int of GroupNumber with
    1: A < B, A == B, A > B)."""
    sys.path.insert(0, str(HERE))
    import upkinfo as U
    from kismet_links import P as KP
    from props import props_start
    b, h = U.load(intro_path)
    names, imps, exps = U.tables(b, h)
    kp = KP(b, names, imps, exps)
    ops = {}
    for n, e in enumerate(exps):
        full = U.objname(n + 1, imps, exps)
        if '.Main_Sequence.' not in full:
            continue
        d, _ = kp.props(props_start(b, e, names), e['off'] + e['size'])
        ops[full.split('.')[-1]] = (U.clsname(e['cls'], imps, exps), d)

    def outputs(d):
        out = []
        if 'OutputLinks' in d:
            for ol in kp.array_of_structs(d['OutputLinks']):
                desc = kp.str_(ol['LinkDesc']) if 'LinkDesc' in ol else ''
                links = [kp.objp(l['LinkedOp']) for l in kp.array_of_structs(ol['Links'])
                         if 'LinkedOp' in l] if 'Links' in ol else []
                out.append((desc, links))
        return out

    def setloc(op):
        cls, d = ops[op]
        loc = list(struct.unpack_from('<3f', b, d['LocationValue'][1])) if 'LocationValue' in d else [0.0, 0.0, 0.0]
        rot = list(struct.unpack_from('<3i', b, d['RotationValue'][1])) if 'RotationValue' in d else [0, 0, 0]
        return dict(location=loc, rotation=rot, action=op)

    anchors = collections.defaultdict(list)
    for op, (cls, d) in ops.items():
        if cls != 'SeqCond_SwitchString' or 'StringArray' not in d:
            continue
        cases = [kp.str_(e['StringName']) if 'StringName' in e else '' for e in kp.array_of_structs(d['StringArray'])]
        for k, (_, links) in enumerate(outputs(d)):
            if k >= len(cases) or not cases[k] or cases[k] == 'Default':
                continue
            for target in links:
                tcls = ops.get(target, (None,))[0]
                if tcls == 'SeqAct_SetLocation':
                    anchors[cases[k]].append(dict(group=None, **setloc(target)))
                elif tcls == 'SeqCond_CompareInt':
                    for desc, tl in outputs(ops[target][1]):
                        group = {'A < B': 0, 'A == B': 1, 'A > B': 2}.get(desc.strip())
                        for t2 in tl:
                            if ops.get(t2, (None,))[0] == 'SeqAct_SetLocation':
                                anchors[cases[k]].append(dict(group=group, **setloc(t2)))
    return dict(anchors)


def anchor_vs_skyrangers(anchors, skyrangers):
    """Each intro place against the map's grounded Skyrangers' meshes: the nearest one, the distance (x, y), the offset
    in the Skyranger's own frame and the yaw difference."""
    meshes = [s['actors']['mesh'] for s in skyrangers if 'mesh' in s['actors'] and s['actors']['mesh']['location']]
    out = []
    for a in anchors:
        rec = dict(a)
        if meshes:
            m = min(meshes, key=lambda x: distance(x['location'][:2], a['location'][:2]))
            yaw = (m['rotation'] or [0, 0, 0])[1]
            d = [a['location'][k] - m['location'][k] for k in range(3)]
            local = turn(d, -yaw)
            rec.update(skyranger=m['actor'], distanceXY=round(distance(m['location'][:2], a['location'][:2]), 1),
                       localOffset=[round(x, 1) for x in local],
                       yawDifference=((a['rotation'][1] - yaw + 32768) % 65536) - 32768)
        out.append(rec)
    return out


# --- the export ----------------------------------------------------------------------------------------------------

def newest_export(folder):
    """A map folder's newest export: the scene.json of the `*-v<N>-map*` folder with the highest N (a plain `-map`
    folder before a suffixed one of the same N)."""
    best = None
    for s in Path(folder).glob('*-v*-map*/scene.json'):
        m = re.search(r'-v(\d+)-map', s.parent.name)
        if not m:
            continue
        key = (int(m.group(1)), s.parent.name.endswith('-map'))
        if best is None or key > best[0]:
            best = (key, s)
    return best[1] if best else None


def is_landing_piece(obj):
    arch = str(obj.get('archetype') or '').casefold()
    return arch.startswith(('dgn_dropshipsoldierspawn.', 'veh_lv1skyranger_mod.prefabs.'))


def survey_export(scene_path, package, lines):
    sc = json.loads(Path(scene_path).read_text(encoding='utf-8'))
    grid = sc.get('tileGrid') or {}
    origin, dims = grid.get('origin') or [0, 0, 0], grid.get('dimensions') or [0, 0, 0]
    bottom = origin[2]
    objects = [o for o in sc.get('objects') or [] if o.get('layer', 'base') == 'base']
    pieces = [o for o in objects if not o.get('environment') and o.get('actorClass') != 'XComLevelVolume']
    landing_pieces = [o for o in pieces if is_landing_piece(o)]
    lights = sc.get('lights') or []
    script = [dict(actor=o['actor'].split('.')[-1], cls=o.get('actorClass'), referencedBy=o['referencedBy'],
                   landing=is_landing_piece(o)) for o in pieces if o.get('referencedBy')]
    script_lights = [dict(actor=l['actor'].split('.')[-1], cls=l.get('actorClass'), role=l.get('role'),
                          referencedBy=l['referencedBy']) for l in lights if l.get('referencedBy')]
    pkg = package or {}
    content = [tuple(c) for c in pkg.get('content') or []]
    landing_paths = set()
    for rec in pkg.get('landings', []) + pkg.get('skyrangers', []):
        landing_paths.add(LEVEL + rec['prefabInstance'])
        landing_paths.update(LEVEL + a['actor'] for a in rec['actors'].values())
    landing_paths.update(LEVEL + a['actor'] for a in pkg.get('landingExtras', []))
    records = {o['actor'] for o in pieces} | {l['actor'] for l in lights if l.get('role') not in ('dominant', 'sky')
                                              and l.get('kind') not in ('directional', 'sky')}
    clear = sort_classes(content, records=records - landing_paths, landing=landing_paths)
    light_roles = collections.Counter('%s/%s' % (l.get('kind'), l.get('role')) for l in lights)
    stays_lights = sum(1 for l in lights if l.get('kind') in ('directional', 'sky') or l.get('role') in ('dominant', 'sky'))
    patch = {}
    for sname, st in (sc.get('streams') or {}).items():
        if st.get('kind') != 'lwr':
            continue
        objs = st.get('objects') or []
        patch[sname] = dict(pieces=len(objs), hidden=sum(1 for o in objs if o.get('hidden')),
                            classes=dict(collections.Counter(o.get('actorClass') for o in objs)))
    own = []
    for rec in pkg.get('landings', []):
        pts = landing_points(rec)
        k, dev, level = best_line(pts, lines)
        frame = pts.get('frame')
        own.append(dict(prefabInstance=rec['prefabInstance'], tag=rec['tag'],
                        groupTag=next((a['tag'] for r, a in rec['actors'].items() if r.startswith('spawn')), None),
                        ground=round(frame[2], 1) if frame else None,
                        levelsUnderGround=round(ground_levels(frame[2], bottom), 2) if frame else None,
                        line=k, lineMatch=level, deviation={r: (round(v, 1) if v is not None else None)
                                                            for r, v in (dev or {}).items()}))
    line_grounds = [ln['start'][2] - 64.0 for ln in lines if ln.get('start')]
    return dict(export=Path(scene_path).parent.name,
                grid=dict(origin=origin, dimensions=dims, bottom=bottom, top=bottom + LEVEL_HEIGHT * (dims[2] if dims else 0)),
                counts=dict(contentActors=sum(1 for p, c in content if not is_kismet(c) and '.Main_Sequence' not in p),
                            pieces=len(pieces), landingPieces=len(landing_pieces),
                            piecesCleared=len(pieces) - len(landing_pieces),
                            lights=len(lights), lightsKept=stays_lights, lightsCleared=len(lights) - stays_lights,
                            lightRoles=dict(light_roles)),
                scriptNamed=script, scriptNamedLights=script_lights,
                ownLandings=own, lines=len(lines),
                lineGrounds=dict(collections.Counter(line_grounds)),
                ground=dict(bottom=bottom, landings=sorted({o['ground'] for o in own if o['ground'] is not None}),
                            lines=sorted(set(line_grounds))),
                clear=clear, patch=patch)


# --- main ----------------------------------------------------------------------------------------------------------

def base_maps(install):
    config = Path(install) / 'XEW' / 'XComGame' / 'Config'
    base = set()
    for line in (config / 'DefaultMaps.ini').read_bytes().decode('latin-1').splitlines():
        if line.lstrip().startswith(';'):
            continue
        base.update(re.findall(r'(?<![A-Za-z])Name="([^"]+)"', line))
    return base


def read_lines(install):
    lz = Path(install) / 'XEW' / 'XComGame' / 'Config' / 'DefaultLZMutator.ini'
    if not lz.is_file():
        return None
    out = collections.defaultdict(list)
    for line in lz.read_bytes().decode('latin-1').splitlines():
        rec = parse_lz_line(line)
        if rec:
            out[rec['map'].lower()].append(rec)
    return out


def summarise_landing(rec):
    """A landing or Skyranger record for the JSON, places rounded."""
    def r(v):
        return [round(x, 1) for x in v] if v else v
    return dict(prefabInstance=rec['prefabInstance'], tag=rec['tag'], location=r(rec['location']),
                rotation=rec['rotation'],
                actors={role: dict(a, location=r(a['location'])) for role, a in sorted(rec['actors'].items())})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--cache', type=Path)
    ap.add_argument('--install', type=Path)
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--maps', nargs='*', help='only these exported maps (and no install-wide pass)')
    a = ap.parse_args(argv)
    if a.cache is None or a.install is None:
        sys.path.insert(0, str(HERE.parent / 'viewer'))
        import settings
        s = settings.load_settings()
        a.cache = a.cache or s.get('cache')
        a.install = a.install or s.get('install')
    cooked = Path(a.install) / 'XEW' / 'XComGame' / 'CookedPCConsole'
    files = {p.stem.lower(): p for p in cooked.glob('*.upk')}
    lines = read_lines(a.install)
    exported = {}
    for folder in sorted(Path(a.cache).iterdir(), key=lambda p: p.name.lower()):
        if folder.is_dir() and (not a.maps or folder.name in a.maps):
            s = newest_export(folder)
            if s:
                exported[folder.name] = s
    base = {n.lower(): n for n in base_maps(a.install)}
    wanted = set(n.lower() for n in exported) | (set() if a.maps else set(base))
    jobs = [(str(files[n]),) for n in sorted(wanted) if n in files]
    with multiprocessing.get_context('spawn').Pool(a.jobs) as pool:
        packages = dict(pool.imap_unordered(survey_package, jobs, chunksize=2))
    packages = {k.lower(): v for k, v in packages.items()}
    intro = cooked / 'CIN_DropshipIntros.upk'
    anchors = intro_anchors(str(intro)) if intro.is_file() else {}
    anchors_low = {k.lower(): v for k, v in anchors.items()}

    maps_out = {}
    for name, scene in exported.items():
        pkg = packages.get(name.lower())
        rec = survey_export(scene, pkg if pkg and 'error' not in pkg else None, (lines or {}).get(name.lower(), []))
        if pkg:
            rec['package'] = dict(error=pkg['error']) if 'error' in pkg else dict(
                landings=[summarise_landing(x) for x in pkg['landings']],
                skyrangers=[summarise_landing(x) for x in pkg['skyrangers']],
                landingExtras=pkg['landingExtras'], nativeGroups=pkg['native'], ambient=pkg['ambient'])
            if 'error' not in pkg:
                rec['introAnchors'] = anchor_vs_skyrangers(anchors_low.get(name.lower(), []), pkg['skyrangers'])
        else:
            rec['package'] = None
        rec['lzLines'] = [dict(start=ln['start'], direction=ln['direction'], kind=ln['kind'],
                               missionType=ln['missionType'], councilType=ln['councilType'],
                               ground=ln['start'][2] - 64.0 if ln['start'] else None,
                               levelsUnderGround=round(ground_levels(ln['start'][2] - 64.0, rec['grid']['bottom']), 2)
                               if ln['start'] else None)
                          for ln in (lines or {}).get(name.lower(), [])]
        maps_out[name] = rec

    install_out, tallies = {}, collections.Counter()
    unmatched, kinds, sky_counts, group_sources, anchor_rel = [], collections.Counter(), collections.Counter(), \
        collections.Counter(), []
    for low, name in sorted(base.items()):
        pkg = packages.get(low)
        if a.maps or pkg is None:
            continue
        if 'error' in pkg:
            install_out[name] = dict(error=pkg['error'])
            continue
        mlines = (lines or {}).get(low, [])
        kinds.update(ln['kind'] for ln in mlines)
        own = []
        for rec in pkg['landings']:
            k, dev, level = best_line(landing_points(rec), mlines)
            tallies['landings'] += 1
            tallies['landing ' + level] += 1
            if level in ('none',) and mlines:
                unmatched.append('%s %s' % (name, rec['prefabInstance']))
            saved = collections.Counter(('rotation saved' if a_['savesRotation'] else 'no rotation') + ' ' + role
                                        for role, a_ in rec['actors'].items()
                                        if role in ('frame', 'evac', 'playerStart', 'point', 'spawn1'))
            saved.update(('location saved' if a_['savesLocation'] else 'no location') + ' ' + role
                         for role, a_ in rec['actors'].items()
                         if role in ('frame', 'evac', 'playerStart', 'point', 'spawn1'))
            tallies.update(saved)
            own.append(dict(prefabInstance=rec['prefabInstance'], tag=rec['tag'],
                            groupTag=next((x['tag'] for r, x in rec['actors'].items() if r.startswith('spawn')), None),
                            parts=sorted(rec['actors']), line=k, lineMatch=level,
                            deviation={r: (round(v, 1) if v is not None else None) for r, v in (dev or {}).items()}))
        sky_counts[len(pkg['skyrangers'])] += 1
        group_sources[pkg['native']['source']] += 1
        anchors_here = anchor_vs_skyrangers(anchors_low.get(low, []), pkg['skyrangers'])
        anchor_rel += [dict(map=name, **x) for x in anchors_here]
        matched_lines = {o['line'] for o in own if o['lineMatch'] in ('exact', 'spawns') and o['line'] is not None}
        install_out[name] = dict(landings=own, skyrangers=len(pkg['skyrangers']), lines=len(mlines),
                                 linesMatchingAnOwnLanding=len(matched_lines),
                                 nativeGroups=pkg['native'], introAnchors=anchors_here,
                                 landingExtras=len(pkg['landingExtras']),
                                 ambientSounds=[dict(actor=s['actor'], cls=s['cls'], sounds=s['sounds'],
                                                     skyranger=s['skyranger']) for s in pkg['ambient']])
    landings_per_map = collections.Counter(len(v.get('landings', [])) for v in install_out.values() if 'error' not in v)
    near = [x for x in anchor_rel if 'distanceXY' in x]
    summary = dict(
        exportedMaps=len(maps_out),
        installBaseMaps=len(install_out),
        landingsPerMap=dict(sorted(landings_per_map.items())),
        skyrangersPerMap=dict(sorted(sky_counts.items())),
        landingLineMatches={k: v for k, v in sorted(tallies.items()) if k.startswith('landing')},
        landingsNoLineMatches=unmatched,
        savedRotation={k: v for k, v in sorted(tallies.items()) if 'rotation' in k},
        savedLocation={k: v for k, v in sorted(tallies.items()) if 'location' in k},
        lineKinds=dict(kinds),
        nativeGroupSource=dict(group_sources),
        nativeGroupTagSets=dict(collections.Counter(' '.join(v['nativeGroups']['order'])
                                                    for v in install_out.values() if 'nativeGroups' in v)),
        introAnchors=dict(maps=len({x['map'] for x in anchor_rel}), places=len(anchor_rel),
                          withinOneTileOfASkyranger=sum(1 for x in near if x['distanceXY'] <= 96),
                          within512=sum(1 for x in near if x['distanceXY'] <= 512),
                          farther=sorted(('%s %s %.0f' % (x['map'], x['group'], x['distanceXY'])) for x in near
                                         if x['distanceXY'] > 512)),
        clearClasses={g: dict(sum((collections.Counter(m['clear'][g]) for m in maps_out.values()),
                                  collections.Counter()).most_common())
                      for g in ('out', 'stays', 'neither', 'unexported', 'landing', 'records', 'other')})
    doc = dict(scope='clear-map plan step C0: every exported map in the viewer cache, and every base map a live '
                     'DefaultMaps.ini record names (landings, lines, native groups, intro places)',
               constants=dict(clearOut=list(CLEAR_OUT), clearStays=list(CLEAR_STAYS), offsets=OFFSETS,
                              spawnOffsets=SPAWN_OFFSETS, insideBack=INSIDE_BACK, matchExact=MATCH_EXACT,
                              matchNear=MATCH_NEAR, matchTile=MATCH_TILE, pieceClasses=list(PIECE_CLASSES)),
               summary=summary, exported=maps_out, install=install_out,
               missingPackages=sorted(n for n in wanted if n not in files))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8', newline='\n')

    print('%d exported maps, %d base maps read' % (len(maps_out), len(install_out)))
    print('%-28s %6s %5s %5s %6s %6s %5s %-24s %s' % ('map', 'pieces', 'land', 'lines', 'match', 'script', 'odd',
                                                      'ground/bottom', 'build out'))
    for name, m in maps_out.items():
        c = m['counts']
        matches = '/'.join(o['lineMatch'][0] for o in m['ownLandings']) or '-'
        odd = sum(m['clear']['neither'].values())
        out_n = sum(m['clear']['out'].values())
        print('%-28s %6d %5d %5d %6s %6d %5d %-24s %d' % (
            name[:28], c['pieces'], len(m['ownLandings']), m['lines'], matches, len(m['scriptNamed']), odd,
            '%s/%s' % (m['ground']['landings'], m['grid']['bottom']), out_n))
    print('own landings over the install: %s' % summary['landingLineMatches'])
    print('own landings no line matches (maps with lines): %d' % len(unmatched))
    print('native group sources: %s' % summary['nativeGroupSource'])
    print('intro places: %s' % {k: v for k, v in summary['introAnchors'].items() if k != 'farther'})
    print('classes on neither list: %s' % summary['clearClasses']['neither'])


if __name__ == '__main__':
    main()
