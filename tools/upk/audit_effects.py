"""Census of the effects and sounds placed in a game install's maps: for every base map and stream a DefaultMaps.ini
record names, the Emitter actors (placed particle systems), the ambient sound actors, the lens flares and a count of
the other effect actors (decals, weather, fog), with what the mission's script does to them, the particle systems and
sound waves they play, and whether tools/bake/transplant.py could bring each to another map. Read-only; made for
private/plans/todo/effects-and-sounds-plan.md.

  python -B tools/upk/audit_effects.py <game install> <out.json> [--jobs 6] [--closure] [--maps NAME ...]

Version 2 (17 November 2026; the first is effects-audit-2026-11-15.json's):
- **A copy of a map is left out.** A map the editor built keeps the package GUID of the map it grew from, so of the
  packages sharing a GUID only the oldest file (and any as old) is counted; `copiesLeftOut` says how many went. The
  first census counted one installed variant and its landing intro as Firaxis's.
- The file says what it read: `auditVersion`, `mapsListSha256` (DefaultMaps.ini's bytes) and each package's `sha256`.
- Per package it adds: which actors the level's actor list holds (`unlisted`); what a `Base` resolves to; whether
  each building floor's `m_aCachedEmitters` agrees with "the emitter stands in one of the floor's volumes"
  (`floors`); each instance parameter against what its system offers (`parametersOffered`, `parametersUnoffered`);
  why a sound resolved no wave (`noWaveWhy`); a simple sound's saved and inherited values (`node`); what the two
  carrying rules would pick (`carried`: the place rule of export 23; `prefabOrigin`: the plan's wider rule; for
  sounds, the place rule); in LWR's patches, the base map's effects and sounds named as text (`namedAsText`).
- Per particle system: everything under it, all LOD levels and every module and distribution (`objects`, `bytes`,
  `nativeClasses`), the parameters it offers (`offers`), whether its emitters loop (`lifecycle`), its LOD levels and
  its fixed box; `variants`: how many different (objects, bytes) the same path has across packages.
- Per wave: its bulk records read by their headers (`records`), not by looking for `OggS`.
- `defaults`: what Engine.upk's class defaults save for starting on (bAutoActivate, bAutoPlay).

Per package: `emitters`, `sounds`, `flares` (counts and tallies), `others` (class counts), and with --closure
`closure`: for each effect actor of a Firaxis package, transplant.closure into an empty map (how many could come,
what was refused or cut, how much comes with one). The summary adds the totals by role (base map or stream) and maker
(Firaxis: licensee 64; LWR's own patches: licensee 0), every particle system once (`systems`: its emitters, their
kinds and modules, `preview`: preview_kind) and every wave an ambient sound plays once (`waves`: size, length,
channels, bulk records).
"""
import argparse
import collections
import hashlib
import json
import multiprocessing
import os
import re
import statistics
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT_VERSION = 2
LEVEL = 'TheWorld.PersistentLevel'
SOUND_CLASSES = ('AmbientSound', 'AmbientSoundSimple', 'AmbientSoundSimpleToggleable', 'AmbientSoundNonLoop',
                 'AmbientSoundMovable')
OTHER_CLASSES = ('DecalActor', 'DecalActorMovable', 'XComRainVolume', 'XComWeatherControl', 'HeightFog',
                 'ExponentialHeightFog', 'PostProcessVolume', 'WindDirectionalSource')
CLOSURE_CLASSES = ('Emitter', 'LensFlareSource', 'DecalActor') + SOUND_CLASSES
# the mesh pieces an effect can stand on, and how near (scene_metadata.EFFECT_PIECES, EFFECT_SAME: export 23's rule)
PIECE_CLASSES = ('XComLevelActor', 'StaticMeshActor', 'XComDestructibleActor', 'XComFracLevelActor',
                 'XComInteractiveLevelActor')
SAME_PLACE = 2.0
NODE_VALUES = ('RadiusMin', 'RadiusMax', 'VolumeMin', 'VolumeMax', 'PitchMin', 'PitchMax', 'LPFRadiusMin',
               'LPFRadiusMax', 'bAttenuate', 'bSpatialize', 'bAttenuateWithLPF', 'DistanceModel')
PARAMETER_KINDS = {'PSPT_Scalar': 'scalar', 'PSPT_ScalarRand': 'scalar', 'PSPT_Vector': 'vector',
                   'PSPT_VectorRand': 'vector', 'PSPT_Color': 'vector'}
TEXT_NAME = re.compile(rb'(Emitter|AmbientSound[A-Za-z]*|LensFlareSource)_\d+')

# The particle modules a plain preview could follow (the plan's section 5): a sprite's colour, size, life, place,
# speed, turn and sub-image. A system whose emitters use only these (and, for mesh particles, MESH_MODULES) is
# `core`; one that uses any other is `beyond` and would look rougher.
CORE_MODULES = frozenset('ParticleModule' + m for m in (
    'Color', 'ColorScaleOverLife', 'ColorOverLife', 'Size', 'SizeMultiplyLife', 'SizeScale', 'Lifetime', 'Location',
    'LocationPrimitiveBox', 'LocationPrimitiveCylinder', 'LocationPrimitiveSphere', 'Velocity', 'VelocityOverLifetime',
    'Acceleration', 'AccelerationOverLifetime', 'Rotation', 'RotationRate', 'RotationRateMultiplyLife', 'SubUV',
    'CameraOffset', 'ParameterDynamic', 'ParameterDynamicModulator', 'OrientationAxisLock', 'KillHeight'))
MESH_MODULES = frozenset('ParticleModule' + m for m in (
    'MeshRotation', 'MeshRotationRate', 'MeshRotationRateMultiplyLife', 'MeshRotationRateOverLife', 'MeshMaterial'))


# --- pure functions (tests: tools/upk/tests/test_audit_effects.py) -----------------------------------------------

def preview_kind(emitters):
    """What a plain preview would make of a particle system, from its emitters ([dict(lods, typeData, modules)]):
    'empty' (no emitter has a LOD level: the cook stripped them), else 'sprites' or 'meshes' (some emitter draws
    meshes) followed by ' core' (only CORE_MODULES, and MESH_MODULES on mesh emitters) or ' beyond'."""
    live = [e for e in emitters if e.get('lods')]
    if not live:
        return 'empty'
    meshes = any(e.get('typeData') == 'ParticleModuleTypeDataMesh' for e in live)
    known = CORE_MODULES | MESH_MODULES if meshes else CORE_MODULES
    core = all(set(e.get('modules') or ()) <= known for e in live)
    return ('meshes' if meshes else 'sprites') + (' core' if core else ' beyond')


def lifecycle(emitters):
    """Whether a system's emitters go on for ever, from each live emitter's `loops` (EmitterLoops of its first LOD
    level: 0 is for ever): 'looping' (all 0), 'finite' (none 0), 'mixed', or 'empty' (no live emitter)."""
    loops = [e.get('loops') or 0 for e in emitters if e.get('lods')]
    if not loops:
        return 'empty'
    if all(n == 0 for n in loops):
        return 'looping'
    return 'finite' if all(n != 0 for n in loops) else 'mixed'


def spread(values):
    """[least, median, 90th percentile, most] of a list of numbers, or None for an empty one."""
    if not values:
        return None
    v = sorted(values)
    return [v[0], statistics.median(v), v[min(len(v) - 1, int(len(v) * 0.9))], v[-1]]


def add(total, record):
    """`record`'s counts added into `total`: numbers summed, dicts of numbers summed key by key."""
    for key, value in record.items():
        if isinstance(value, dict):
            into = total.setdefault(key, {})
            for k, n in value.items():
                into[k] = into.get(k, 0) + n
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            total[key] = total.get(key, 0) + value
    return total


def inside(point, boxes, slack=0.0):
    """Whether `point` lies in one of `boxes` ([dict(min, max)]), each side moved out by `slack`."""
    return any(all(b['min'][k] - slack <= point[k] <= b['max'][k] + slack for k in range(3)) for b in boxes if b)


def copies(found):
    """The packages of {name: record} that are copies of another: of those sharing a package GUID (`guid`), every one
    whose file (`modified`, seconds) is more than a day newer than the oldest. A map the editor built keeps the GUID
    of the map it grew from."""
    groups = collections.defaultdict(list)
    for name, r in found.items():
        if r.get('guid'):
            groups[r['guid']].append(name)
    out = set()
    for names in groups.values():
        oldest = min(found[n].get('modified') or 0 for n in names)
        out.update(n for n in names if (found[n].get('modified') or 0) - oldest > 86400)
    return out


def summarise(found):
    """The summary of {package: record}: by role and maker the packages, how many hold an emitter or a sound, and
    the summed tallies of `emitters`, `sounds`, `flares`, `floors` and `others`; `systems` and `waves`, each once,
    with the packages holding it and its `variants` (how many different sizes the path has); `placements` of each
    particle system by an Emitter; `preview` and `lifecycle`: Firaxis's emitters by their system's preview_kind and
    lifecycle; `closure` summed over the packages that have one."""
    groups, systems, waves, placed = {}, {}, {}, collections.Counter()
    preview, life, closure, sizes = collections.Counter(), collections.Counter(), {}, {}
    signatures = collections.defaultdict(set)
    for name in sorted(found, key=str.lower):
        r = found[name]
        if 'error' in r:
            continue
        maker = 'firaxis' if r['licensee'] == 64 else 'lwr'
        g = groups.setdefault(r['role'] + ' ' + maker, dict(packages=0, withEmitters=0, withSounds=0, emitters={},
                                                             sounds={}, flares={}, others={}, floors={}))
        g['packages'] += 1
        g['withEmitters'] += 1 if r['emitters'].get('count') else 0
        g['withSounds'] += 1 if r['sounds'].get('count') else 0
        for key in ('emitters', 'sounds', 'flares', 'others', 'floors'):
            add(g[key], r.get(key) or {})
        g.setdefault('perMap', {}).setdefault('emitters', []).append(r['emitters'].get('count', 0))
        g['perMap'].setdefault('sounds', []).append(r['sounds'].get('count', 0))
        if maker != 'firaxis':
            continue
        for path, s in (r.get('systems') or {}).items():
            systems.setdefault(path, dict(s, packages=0, preview=preview_kind(s['emitters']),
                                          lifecycle=lifecycle(s['emitters'])))['packages'] += 1
            signatures[path].add((s.get('objects'), s.get('bytes')))
        for path, w in (r.get('waves') or {}).items():
            waves.setdefault(path, dict(w, packages=0))['packages'] += 1
            signatures['wave ' + path].add(w.get('size'))
        for template, n in (r['emitters'].get('templates') or {}).items():
            placed[template] += n
        if r.get('closure'):
            for cls, c in r['closure'].items():
                into = closure.setdefault(cls, dict(ok=0, refused={}, cut={}))
                add(into, dict(ok=c['ok'], refused=c['refused'], cut=c['cut']))
                sizes.setdefault(cls, []).extend(c['sizes'])
    for g in groups.values():
        g['perMap'] = {k: spread(v) for k, v in g['perMap'].items()}
    for path, s in systems.items():
        s['variants'] = len(signatures[path])
    for path, w in waves.items():
        w['variants'] = len(signatures['wave ' + path])
    for template, n in placed.items():
        if template in systems:
            systems[template]['placements'] = n
            preview[systems[template]['preview']] += n
            life[systems[template]['lifecycle']] += n
    for cls, c in closure.items():
        c['objects'] = spread([s[0] for s in sizes[cls]])
        c['bytes'] = spread([s[1] for s in sizes[cls]])
    return dict(groups=groups, systems=systems, waves=waves, preview=dict(preview), lifecycle=dict(life),
                closure=closure, distinctSystems=len(systems),
                systemsPlaced=sum(1 for s in systems.values() if s.get('placements')),
                systemsWithVariants=sum(1 for s in systems.values() if s['variants'] > 1),
                systemsWithNativeData=sum(1 for s in systems.values() if s.get('native')),
                distinctWaves=len(waves), waveBytes=sum(w['size'] for w in waves.values()),
                wavesWithVariants=sum(1 for w in waves.values() if w['variants'] > 1))


# --- reading a package ---------------------------------------------------------------------------------------------

def own(p, index):
    """An export's own tagged properties by name (the first slot of each), or {} when they can't be read."""
    try:
        return {k[0]: v for k, v in p.properties(index)[0].items() if k[1] == 0}
    except Exception:  # noqa: BLE001
        return {}


def plain(value):
    return value if isinstance(value, (int, float, str, bool)) or value is None else None


def tail(p, index):
    """The bytes an export keeps after its tagged properties."""
    e = p.exports[index - 1]
    return e['off'] + e['size'] - p.properties(index)[1]


def subtree(p, index):
    out = [index]
    for c in p.children.get(index, []):
        out += subtree(p, c)
    return out


def level_list(p, level):
    """The exports in the level's actor list, or None when it can't be read."""
    try:
        _, end = p.properties(level)
        owner, count = struct.unpack_from('<ii', p.data, end)
        return set(struct.unpack_from('<%di' % count, p.data, end + 8)) if owner == level else None
    except Exception:  # noqa: BLE001
        return None


def kismet_users(p):
    """{actor export: Counter(the class of each Kismet object linked to an object variable naming it)}."""
    variables = {}
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) == 'SeqVar_Object':
            v = p.own(i, 'ObjValue', 0)
            if isinstance(v, int) and v > 0:
                variables[i] = v
    users = collections.defaultdict(collections.Counter)
    for i in range(1, len(p.exports) + 1):
        cls = p.cls(i)
        if not cls.startswith(('SeqAct', 'SeqEvent', 'SeqCond')):
            continue
        raw = p.own(i, 'VariableLinks')
        if not raw:
            continue
        try:
            for link in p.structs(raw):
                linked = link.get(('LinkedVariables', 0))
                for ref in p.refs(linked['value']) if linked else []:
                    if ref in variables:
                        users[variables[ref]][cls] += 1
        except Exception:  # noqa: BLE001
            continue
    return users


def building_floors(p, level, bounds):
    """[(building export, floor number, its floor volumes' world boxes, the exports its m_aCachedEmitters names)] of
    the level's buildings; `bounds`: scene_metadata.volume_bounds."""
    out = []
    for i in p.children.get(level, []):
        if p.cls(i) != 'XComBuildingVolume':
            continue
        try:
            floors = p.structs(p.own(i, 'Floors'))
        except Exception:  # noqa: BLE001
            continue
        for n, floor in enumerate(floors):
            try:
                volumes = floor.get(('FloorVolumes', 0))
                boxes = [bounds(p, v) for v in (p.refs(volumes['value']) if volumes else []) if v > 0]
                cached = floor.get(('m_aCachedEmitters', 0))
                listed = {r for r in (p.refs(cached['value']) if cached else []) if r > 0}
            except Exception:  # noqa: BLE001
                continue
            out.append((i, n, [b for b in boxes if b], listed))
    return out


def system_record(p, index):
    """A ParticleSystem: dict(emitters: [dict(lods, typeData, modules, material, loops)] (the first LOD level's),
    lodLevels (the most any emitter has), objects, bytes and nativeClasses {class: bytes after its properties} over
    everything under the system, native (their sum), offers: [[name, scalar | vector]] of its particle-parameter
    distributions, fixedBox (bUseFixedRelativeBoundingBox))."""
    under = subtree(p, index)
    native = collections.Counter()
    offers = set()
    for j in under:
        cls = p.cls(j)
        try:
            n = tail(p, j)
        except Exception:  # noqa: BLE001
            n = -1
        if n:
            native[cls] += n
        if cls in ('DistributionFloatParticleParameter', 'DistributionVectorParticleParameter'):
            name = (own(p, j).get('ParameterName') or {}).get('value')
            if name:
                offers.add((str(name), 'scalar' if 'Float' in cls else 'vector'))
    record, levels = [], 0
    try:
        emitters = p.refs((own(p, index).get('Emitters') or {}).get('value'))
    except Exception:  # noqa: BLE001
        emitters = []
    for em in emitters:
        if em <= 0:
            continue
        try:
            lods = [r for r in p.refs((own(p, em).get('LODLevels') or {}).get('value')) if r > 0]
        except Exception:  # noqa: BLE001
            lods = []
        levels = max(levels, len(lods))
        rec = dict(lods=len(lods), typeData=None, modules=[], material=None, loops=0)
        if lods:
            lod = own(p, lods[0])
            try:
                modules = [m for m in p.refs((lod.get('Modules') or {}).get('value')) if m > 0]
            except Exception:  # noqa: BLE001
                modules = []
            rec['modules'] = sorted({p.cls(m) for m in modules})
            type_data = (lod.get('TypeDataModule') or {}).get('value') or 0
            rec['typeData'] = p.cls(type_data) if type_data > 0 else None
            required = (lod.get('RequiredModule') or {}).get('value') or 0
            if required > 0:
                req = own(p, required)
                material = (req.get('Material') or {}).get('value') or 0
                rec['material'] = p.cls(material) if material > 0 else 'import' if material else None
                rec['loops'] = plain((req.get('EmitterLoops') or {}).get('value')) or 0
        record.append(rec)
    return dict(emitters=record, lodLevels=levels, objects=len(under),
                bytes=sum(p.exports[j - 1]['size'] for j in under), native=sum(native.values()),
                nativeClasses=dict(native), offers=sorted(list(o) for o in offers),
                fixedBox=bool((own(p, index).get('bUseFixedRelativeBoundingBox') or {}).get('value')))


def wave_record(p, index):
    """A SoundNodeWave: its size, length in seconds, channels and sample rate, and its bulk records in order, read
    by their 16-byte headers (flags, element count, size, offset): [dict(flags, count, size, inline, ogg)] (`ogg`:
    the payload starts with OggS), `unread`: bytes left that no record explains."""
    e = p.exports[index - 1]
    k = own(p, index)

    def value(key):
        return plain((k.get(key) or {}).get('value'))
    pos, end, records = p.properties(index)[1], e['off'] + e['size'], []
    while pos + 16 <= end and len(records) < 16:
        flags, count, size, offset = struct.unpack_from('<IiiI', p.data, pos)
        pos += 16
        rec = dict(flags=flags, count=count, size=size, inline=not flags & 1 and size > 0, ogg=False)
        if rec['inline']:
            if offset != pos or pos + size > end:
                rec['misplaced'] = True
                records.append(rec)
                break
            rec['ogg'] = p.data[pos:pos + 4] == b'OggS'
            pos += size
        records.append(rec)
    return dict(size=e['size'], seconds=value('Duration'), channels=value('NumChannels'), rate=value('SampleRate'),
                pcmBytes=value('RawPCMDataSize'), records=records, unread=end - pos)


def sound_waves(p, cue, node):
    """(the SoundNodeWaves an ambient sound reaches, why it reaches none or None). `cue`: its component's SoundCue
    (0: none), `node`: its SoundNodeInstance (0: none). A SoundNodeAmbient's slots may be an archetype's."""
    if cue < 0:
        return [], 'the cue is an import'
    seen, found, why = set(), [], []

    def walk(n):
        if n <= 0 or n in seen:
            if n < 0:
                why.append('a node or wave is an import')
            return
        seen.add(n)
        if p.cls(n) == 'SoundNodeWave':
            found.append(n)
            return
        for key, v in own(p, n).items():
            if v['kind'] == 'ObjectProperty' and isinstance(v['value'], int):
                walk(v['value'])
        try:
            children = p.effective(n, 'ChildNodes')
            for ref in p.refs(children) if children else []:
                walk(ref)
            slots = p.effective(n, 'SoundSlots')
            if p.cls(n) == 'SoundNodeAmbient':
                entries = p.structs(slots) if slots else []
                if not entries:
                    why.append('its node has no sound slots')
                for slot in entries:
                    wave = slot.get(('Wave', 0))
                    if wave and wave['value']:
                        walk(wave['value'])
                    else:
                        why.append('a sound slot names no wave')
        except Exception:  # noqa: BLE001
            why.append('a node could not be read')
    first = (own(p, cue).get('FirstNode') or {}).get('value') or 0 if cue > 0 else 0
    if first:
        walk(first)
    if not found and node > 0:
        walk(node)
    if found:
        return found, None
    if not cue and node <= 0:
        return [], 'no cue and no node'
    if cue > 0 and not first and node <= 0:
        return [], 'the cue has no first node'
    return [], (why[0] if why else 'its nodes reach no wave')


def closure_record(path, cooked):
    """For each CLOSURE_CLASSES actor of the package's level, transplant.closure into an empty map: {class:
    dict(ok, refused {reason: n}, cut {'A -> B': n}, sizes [(objects, bytes)])}."""
    sys.path.insert(0, str(HERE.parent / 'bake'))
    import schema as schema_module
    import transplant
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = schema_module.Schema(schema_module.build(Path(cooked)))

    class Nowhere:
        assets = {}
    donor = transplant.Donor(path, _SCHEMA)
    p, out = donor.p, {}
    for i in p.children.get(donor.level, []) if donor.level else []:
        cls = p.cls(i)
        if cls not in CLOSURE_CLASSES:
            continue
        c = out.setdefault(cls, dict(ok=0, refused={}, cut={}, sizes=[]))
        try:
            plan = transplant.closure(donor, [i], Nowhere)
        except transplant.Refused as error:
            reason = str(error).split(':', 1)[-1].strip()[:120]
            c['refused'][reason] = c['refused'].get(reason, 0) + 1
            continue
        c['ok'] += 1
        c['sizes'].append((len(plan.bring), sum(p.exports[j - 1]['size'] for j in plan.bring)))
        for by, ref in plan.cut:
            key = '%s -> %s' % (p.cls(by), p.cls(ref))
            c['cut'][key] = c['cut'].get(key, 0) + 1
    return out


_SCHEMA = None


def survey(job):
    path, closure = job
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(HERE.parent / 'viewer'))
    import package
    import scene_metadata
    name = Path(path).stem
    try:
        p = package.Package(path)
    except Exception as error:  # noqa: BLE001
        return name, dict(error=repr(error))
    out = dict(licensee=p.header['lic'], guid=p.header['guid'].hex() if isinstance(p.header.get('guid'), bytes)
               else str(p.header.get('guid') or ''), modified=int(os.path.getmtime(path)),
               sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
               emitters={}, sounds={}, flares={}, others={}, floors={}, systems={}, waves={})
    level = p.by_name.get(LEVEL)
    if level is None:
        return name, out
    if p.header['lic'] != 64:
        # one of LWR's patches: what of the base map it names as text (its Kismet finds actors by name)
        names = collections.Counter(m.group(1).decode('latin-1') for m in TEXT_NAME.finditer(p.data))
        out['namedAsText'] = dict(names)
    listed = level_list(p, level)
    users = kismet_users(p)
    floors = building_floors(p, level, scene_metadata.volume_bounds)
    in_floor = collections.defaultdict(list)
    for building, n, boxes, cached in floors:
        for r in cached:
            in_floor[r].append((building, n))
    try:
        members = scene_metadata.prefab_members(p)
    except Exception:  # noqa: BLE001
        members = {}
    prefab_at = {}
    for i in p.children.get(level, []):
        if p.cls(i) == 'PrefabInstance':
            prefab_at[p.name(i).rsplit('.', 1)[-1]] = [float(v) for v in p.effective(i, 'Location', [0.0, 0.0, 0.0])]
    pieces = [[float(v) for v in p.effective(i, 'Location', [0.0, 0.0, 0.0])] for i in p.children.get(level, [])
              if p.cls(i) in PIECE_CLASSES and (listed is None or i in listed)]

    def standing_at(point):
        return sum(1 for at in pieces if all(abs(at[k] - point[k]) <= SAME_PLACE for k in range(3)))
    systems = {}
    if p.header['lic'] == 64:
        for i in range(1, len(p.exports) + 1):
            if p.cls(i) == 'ParticleSystem':
                systems[i] = system_record(p, i)
                out['systems'][p.name(i)] = systems[i]
    em, fo = collections.Counter(), collections.Counter()
    templates, parameters, parameter_types, em_users, unoffered, bases, listed_classes = (
        collections.Counter() for _ in range(7))
    so, classes, cue_place, so_users, wave_uses, asset_cues, no_wave, node_values, cue_nodes, auto_play = (
        collections.Counter() for _ in range(10))
    fl, fl_templates, fl_users, others = (collections.Counter() for _ in range(4))
    fo['buildings'] = len({b for b, _, _, _ in floors})
    fo['floors'] = len(floors)
    fo['floorsListingEmitters'] = sum(1 for f in floors if f[3])
    for _, _, _, cached in floors:
        for r in cached:
            listed_classes[p.cls(r)] += 1
    for i in p.children.get(level, []):
        cls, e, k = p.cls(i), p.exports[i - 1], own(p, i)
        at = [float(v) for v in p.effective(i, 'Location', [0.0, 0.0, 0.0])]
        base = (k.get('Base') or {}).get('value') if 'Base' in k else None
        if cls == 'Emitter':
            em['count'] += 1
            em['unlisted'] += listed is not None and i not in listed
            component = (k.get('ParticleSystemComponent') or {}).get('value') or 0
            template = p.effective(component, 'Template', 0) if component > 0 else 0
            if template:
                templates[p.name(template)] += 1
            else:
                em['noTemplate'] += 1
            em['hidden'] += bool(p.effective(i, 'bHidden', False))
            em['startOff'] += component > 0 and p.effective(component, 'bAutoActivate', None) is False
            em['kismetNamed'] += i in users
            em['floorListed'] += i in in_floor
            em['floorListedTwice'] += len(in_floor.get(i, ())) > 1
            em['based'] += 'Base' in k
            if 'Base' in k:
                bases[p.cls(base) if isinstance(base, int) and base > 0 else 'import' if base else 'none'] += 1
            em['fromPrefab'] += bool(e['arch']) and '.Prefabs.' in p.name(e['arch'])
            em['inPrefabInstance'] += i in members
            em['scaled'] += 'DrawScale' in k or 'DrawScale3D' in k
            em['scaledUnevenly'] += 'DrawScale3D' in k and len(set(k['DrawScale3D']['value'])) > 1
            em['turned'] += 'Rotation' in k
            em['lit'] += 'LightEnvironment' in k
            em_users.update(users.get(i, {}))
            # the carrying rules: export 23's (the one piece at its place), and the plan's wider one (an effect a
            # prefab instance placed, no piece's by the first rule, whose instance stands at one piece's place)
            near = standing_at(at)
            em['carried'] += near == 1
            em['atSeveralPieces'] += near > 1
            origin = prefab_at.get(members.get(i))
            if near != 1 and origin is not None:
                around = standing_at(origin)
                em['prefabOrigin'] += around == 1
                em['prefabOriginSeveral'] += around > 1
            # the floors' lists against "the emitter stands in one of the floor's volumes"
            for building, n, boxes, cached in floors:
                within = inside(at, boxes)
                if i in cached:
                    fo['listedInside' if within else 'listedOutside'] += 1
                    fo['listedWithin16'] += not within and inside(at, boxes, 16.0)
                elif within:
                    fo['insideUnlisted'] += 1
            raw = (own(p, component).get('InstanceParameters') or {}).get('value') if component > 0 else None
            if raw:
                em['withParameters'] += 1
                offers = {tuple(o) for o in systems[template]['offers']} if template in systems else None
                try:
                    for s in p.structs(raw):
                        pname = str(s.get(('Name', 0), {}).get('value'))
                        ptype = str(s.get(('ParamType', 0), {}).get('value', 'PSPT_None'))
                        parameters[pname] += 1
                        parameter_types[ptype] += 1
                        if offers is None:
                            em['parametersUnchecked'] += 1
                        elif (pname, PARAMETER_KINDS.get(ptype)) in offers:
                            em['parametersOffered'] += 1
                        elif any(o[0] == pname for o in offers):
                            em['parametersOfferedAsOtherKind'] += 1
                        else:
                            em['parametersUnoffered'] += 1
                            unoffered[pname] += 1
                except Exception:  # noqa: BLE001
                    em['parametersUnread'] += 1
        elif cls in SOUND_CLASSES:
            so['count'] += 1
            so['unlisted'] += listed is not None and i not in listed
            classes[cls] += 1
            component = (k.get('AudioComponent') or {}).get('value') or 0
            cue = p.effective(component, 'SoundCue', 0) if component > 0 else 0
            place = 'none' if not cue else 'import' if cue < 0 else 'actor' if p.name(cue).startswith(LEVEL) else 'asset'
            cue_place[place] += 1
            if place == 'asset':
                asset_cues[p.name(cue)] += 1
                for j in subtree(p, cue):
                    cue_nodes[p.cls(j)] += 1
            so['kismetNamed'] += i in users
            so['fromPrefab'] += bool(e['arch']) and '.Prefabs.' in p.name(e['arch'])
            so['inPrefabInstance'] += i in members
            so['based'] += 'Base' in k
            near = standing_at(at)
            so['atOnePiece'] += near == 1
            so['atSeveralPieces'] += near > 1
            so_users.update(users.get(i, {}))
            auto = p.effective(i, 'bAutoPlay', None)
            auto_play['%s %s' % (cls, 'unsaved' if auto is None else auto)] += 1
            node = (k.get('SoundNodeInstance') or {}).get('value') or 0
            if node > 0:
                saved = own(p, node)
                for key in NODE_VALUES:
                    if key in saved:
                        node_values[key + ' saved'] += 1
                    elif p.effective(node, key, None) is not None:
                        node_values[key + ' inherited'] += 1
                so['nodeIsAmbientProperties'] += (k.get('AmbientProperties') or {}).get('value') == node
                first = (own(p, cue).get('FirstNode') or {}).get('value') if cue > 0 else None
                so['nodeIsCueFirstNode'] += first == node
                so['withNode'] += 1
            found, why = sound_waves(p, cue, node)
            if why:
                so['noWave'] += 1
                no_wave[why] += 1
            so['severalWaves'] += len(set(found)) > 1
            for w in set(found):
                wave_uses[p.name(w)] += 1
                out['waves'].setdefault(p.name(w), wave_record(p, w))
        elif cls == 'LensFlareSource':
            fl['count'] += 1
            fl['unlisted'] += listed is not None and i not in listed
            component = (k.get('LensFlareComp') or {}).get('value') or 0
            template = p.effective(component, 'Template', 0) if component > 0 else 0
            fl_templates[p.name(template) if template else '(none)'] += 1
            fl['kismetNamed'] += i in users
            fl['based'] += 'Base' in k
            fl['floorListed'] += i in in_floor
            fl_users.update(users.get(i, {}))
        elif cls in OTHER_CLASSES:
            others[cls] += 1
    out['emitters'] = dict(em, templates=dict(templates), parameters=dict(parameters),
                           parameterTypes=dict(parameter_types), kismetUsers=dict(em_users),
                           unofferedNames=dict(unoffered), bases=dict(bases))
    out['sounds'] = dict(so, classes=dict(classes), cue=dict(cue_place), assetCues=dict(asset_cues),
                         assetCueNodes=dict(cue_nodes), waveUses=dict(wave_uses), kismetUsers=dict(so_users),
                         noWaveWhy=dict(no_wave), node=dict(node_values), autoPlay=dict(auto_play))
    out['flares'] = dict(fl, templates=dict(fl_templates), kismetUsers=dict(fl_users))
    out['floors'] = dict(fo, listedClasses=dict(listed_classes))
    out['others'] = dict(others)
    if listed is None:
        out['levelListUnread'] = True
    if p.header['lic'] == 64 and closure:
        try:
            out['closure'] = closure_record(path, Path(path).parent)
        except Exception as error:  # noqa: BLE001
            out['closureError'] = repr(error)
    return name, out


def class_defaults(cooked):
    """What Engine.upk's class default objects save for starting on: {object: {property: value}}, own values only (a
    class that saves none takes its parent's; a bool nobody saves is false)."""
    sys.path.insert(0, str(HERE.parent / 'viewer'))
    import package
    try:
        p = package.Package(Path(cooked) / 'Engine.upk')
    except Exception as error:  # noqa: BLE001
        return dict(error=repr(error))
    out = {}
    for name in ('Emitter', 'ParticleSystemComponent', 'AudioComponent', 'Actor') + SOUND_CLASSES:
        i = p.by_name.get('Default__' + name)
        if i is None:
            out[name] = None
            continue
        k = own(p, i)
        out[name] = {key: plain(k[key]['value']) for key in ('bAutoActivate', 'bAutoPlay', 'bIsPlaying',
                                                              'bCurrentlyPlaying', 'bHidden') if key in k}
        for c in p.children.get(i, []):
            ck = own(p, c)
            saved = {key: plain(ck[key]['value']) for key in ('bAutoActivate', 'bAutoPlay') if key in ck}
            if saved or p.cls(c) in ('ParticleSystemComponent', 'AudioComponent'):
                out['%s.%s' % (name, p.cls(c))] = saved
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('install'); ap.add_argument('out')
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--closure', action='store_true', help='try transplant.closure on every effect actor (slow)')
    ap.add_argument('--maps', nargs='*', help='only these packages')
    a = ap.parse_args()
    config = Path(a.install) / 'XEW' / 'XComGame' / 'Config'
    cooked = Path(a.install) / 'XEW' / 'XComGame' / 'CookedPCConsole'
    maps_list = (config / 'DefaultMaps.ini').read_bytes()
    base, streams = set(), set()
    for line in maps_list.decode('latin-1').splitlines():
        if line.lstrip().startswith(';'):
            continue
        base.update(re.findall(r'(?<![A-Za-z])Name="([^"]+)"', line))
        streams.update(re.findall(r'MapName="([^"]+)"', line))
    files = {p.stem.lower(): p for p in cooked.glob('*.upk')}
    wanted = sorted({n.lower() for n in (a.maps or base | streams)})
    jobs = [(str(files[n]), a.closure) for n in wanted if n in files]
    with multiprocessing.get_context('spawn').Pool(a.jobs) as pool:
        found = dict(pool.imap_unordered(survey, jobs, chunksize=1))
    left_out = copies(found)
    for name in left_out:
        del found[name]
    base_low = {n.lower() for n in base}
    for name, record in found.items():
        record['role'] = 'base' if name.lower() in base_low else 'stream'
        record.pop('modified', None)
    summary = summarise(found)
    for record in found.values():       # each system and wave is in the summary once
        if record.get('systems'):
            record['systems'] = sorted(record['systems'])
        if record.get('waves'):
            record['waves'] = sorted(record['waves'])
        for c in (record.get('closure') or {}).values():
            c['objects'], c['bytes'] = spread([s[0] for s in c['sizes']]), spread([s[1] for s in c.pop('sizes')])
    missing = sorted(n for n in wanted if n not in files)
    Path(a.out).write_text(json.dumps(dict(
        auditVersion=AUDIT_VERSION, mapsListSha256=hashlib.sha256(maps_list).hexdigest(),
        scope='every base map and stream named by a live DefaultMaps.ini record' if not a.maps else 'the packages named',
        closure=a.closure, missingPackages=missing, copiesLeftOut=len(left_out), defaults=class_defaults(cooked),
        summary=summary, packages={n: found[n] for n in sorted(found, key=str.lower)}), indent=1, sort_keys=True) + '\n',
        encoding='utf-8', newline='\n')
    for group, g in sorted(summary['groups'].items()):
        print('%-15s %3d packages: %5d emitters in %d, %4d sounds in %d, %3d lens flares' % (
            group, g['packages'], g['emitters'].get('count', 0), g['withEmitters'], g['sounds'].get('count', 0),
            g['withSounds'], g['flares'].get('count', 0)))
    print('%d copies of other packages left out' % len(left_out))
    print('%d particle systems (%d placed by an emitter, %d with native data, %d of more than one size), %d waves '
          'played by ambient sounds (%.1f MB)' % (
              summary['distinctSystems'], summary['systemsPlaced'], summary['systemsWithNativeData'],
              summary['systemsWithVariants'], summary['distinctWaves'], summary['waveBytes'] / 1e6))
    print('emitters of Firaxis packages by what a plain preview would make of their system:', summary['preview'])
    print('and by whether their system loops:', summary['lifecycle'])
    for cls, c in sorted(summary['closure'].items()):
        print('closure %-28s %5d could come, %d refused, %d cut references' % (
            cls, c['ok'], sum(c['refused'].values()), sum(c['cut'].values())))
    if missing:
        print('missing packages:', ', '.join(missing))


if __name__ == '__main__':
    main()
