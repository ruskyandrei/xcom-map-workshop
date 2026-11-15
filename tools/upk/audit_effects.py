"""Census of the effects and sounds placed in a game install's maps: for every base map and stream a DefaultMaps.ini
record names, the Emitter actors (placed particle systems), the ambient sound actors, the lens flares and a count of
the other effect actors (decals, weather, fog), with what the mission's script does to them, the particle systems and
sound waves they play, and whether tools/bake/transplant.py could bring each to another map. Read-only; made for
private/plans/todo/effects-and-sounds-plan.md.

  python -B tools/upk/audit_effects.py <game install> <out.json> [--jobs 6] [--closure] [--maps NAME ...]

Per package: `emitters`, `sounds`, `flares` (counts and tallies), `others` (class counts), and with --closure
`closure`: for each effect actor of a Firaxis package, transplant.closure into an empty map (how many could come,
what was refused or cut, how much comes with one). The summary adds the totals by role (base map or stream) and maker
(Firaxis: licensee 64; LWR's own patches: licensee 0), every particle system once (`systems`: its emitters, their
kinds and modules, `preview`: preview_kind) and every wave an ambient sound plays once (`waves`: size, length,
channels, where its Ogg data starts).
"""
import argparse
import collections
import json
import multiprocessing
import re
import statistics
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEVEL = 'TheWorld.PersistentLevel'
SOUND_CLASSES = ('AmbientSound', 'AmbientSoundSimple', 'AmbientSoundSimpleToggleable', 'AmbientSoundNonLoop',
                 'AmbientSoundMovable')
OTHER_CLASSES = ('DecalActor', 'DecalActorMovable', 'XComRainVolume', 'XComWeatherControl', 'HeightFog',
                 'ExponentialHeightFog', 'PostProcessVolume', 'WindDirectionalSource')
CLOSURE_CLASSES = ('Emitter', 'LensFlareSource', 'DecalActor') + SOUND_CLASSES

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


def summarise(found):
    """The summary of {package: record}: by role and maker the packages, how many hold an emitter or a sound, and
    the summed tallies of `emitters`, `sounds`, `flares` and `others`; `systems` and `waves`, each once, with the
    packages holding it; `placements` of each particle system by an Emitter; `preview`: Firaxis's base maps'
    emitters by their system's preview_kind; `closure` summed over the packages that have one."""
    groups, systems, waves, placed = {}, {}, {}, collections.Counter()
    preview, closure, sizes = collections.Counter(), {}, {}
    for name in sorted(found, key=str.lower):
        r = found[name]
        if 'error' in r:
            continue
        maker = 'firaxis' if r['licensee'] == 64 else 'lwr'
        g = groups.setdefault(r['role'] + ' ' + maker, dict(packages=0, withEmitters=0, withSounds=0, emitters={},
                                                             sounds={}, flares={}, others={}))
        g['packages'] += 1
        g['withEmitters'] += 1 if r['emitters'].get('count') else 0
        g['withSounds'] += 1 if r['sounds'].get('count') else 0
        for key in ('emitters', 'sounds', 'flares', 'others'):
            add(g[key], r[key])
        g.setdefault('perMap', {}).setdefault('emitters', []).append(r['emitters'].get('count', 0))
        g['perMap'].setdefault('sounds', []).append(r['sounds'].get('count', 0))
        if maker != 'firaxis':
            continue
        for path, s in (r.get('systems') or {}).items():
            systems.setdefault(path, dict(s, packages=0, preview=preview_kind(s['emitters'])))['packages'] += 1
        for path, w in (r.get('waves') or {}).items():
            waves.setdefault(path, dict(w, packages=0))['packages'] += 1
        for template, n in (r['emitters'].get('templates') or {}).items():
            placed[template] += n
        if r.get('closure'):
            for cls, c in r['closure'].items():
                into = closure.setdefault(cls, dict(ok=0, refused={}, cut={}))
                add(into, dict(ok=c['ok'], refused=c['refused'], cut=c['cut']))
                sizes.setdefault(cls, []).extend(c['sizes'])
    for g in groups.values():
        g['perMap'] = {k: spread(v) for k, v in g['perMap'].items()}
    for template, n in placed.items():
        if template in systems:
            systems[template]['placements'] = n
            preview[systems[template]['preview']] += n
    for cls, c in closure.items():
        c['objects'] = spread([s[0] for s in sizes[cls]])
        c['bytes'] = spread([s[1] for s in sizes[cls]])
    return dict(groups=groups, systems=systems, waves=waves, preview=dict(preview), closure=closure,
                distinctSystems=len(systems), systemsPlaced=sum(1 for s in systems.values() if s.get('placements')),
                distinctWaves=len(waves), waveBytes=sum(w['size'] for w in waves.values()))


# --- reading a package ---------------------------------------------------------------------------------------------

def own(p, index):
    """An export's own tagged properties by name (the first slot of each), or {} when they can't be read."""
    try:
        return {k[0]: v for k, v in p.properties(index)[0].items() if k[1] == 0}
    except Exception:  # noqa: BLE001
        return {}


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


def floor_listed(p, level):
    """The exports some building floor's m_aCachedEmitters names (they hide with that floor)."""
    listed = set()
    for i in p.children.get(level, []):
        if p.cls(i) != 'XComBuildingVolume':
            continue
        try:
            for floor in p.structs(p.own(i, 'Floors')):
                cached = floor.get(('m_aCachedEmitters', 0))
                listed.update(r for r in (p.refs(cached['value']) if cached else []) if r > 0)
        except Exception:  # noqa: BLE001
            continue
    return listed


def system_record(p, index):
    """A ParticleSystem: dict(emitters: [dict(lods, typeData, modules, material)], native: bytes after its
    properties and its emitters' and first-LOD modules')."""
    def after(i):
        e = p.exports[i - 1]
        return e['off'] + e['size'] - p.properties(i)[1]
    record, native = [], after(index)
    try:
        emitters = p.refs((own(p, index).get('Emitters') or {}).get('value'))
    except Exception:  # noqa: BLE001
        emitters = []
    for em in emitters:
        if em <= 0:
            continue
        native += after(em)
        try:
            lods = [r for r in p.refs((own(p, em).get('LODLevels') or {}).get('value')) if r > 0]
        except Exception:  # noqa: BLE001
            lods = []
        rec = dict(lods=len(lods), typeData=None, modules=[], material=None)
        if lods:
            lod = own(p, lods[0])
            try:
                modules = [m for m in p.refs((lod.get('Modules') or {}).get('value')) if m > 0]
            except Exception:  # noqa: BLE001
                modules = []
            rec['modules'] = sorted({p.cls(m) for m in modules})
            native += sum(after(m) for m in modules)
            type_data = (lod.get('TypeDataModule') or {}).get('value') or 0
            rec['typeData'] = p.cls(type_data) if type_data > 0 else None
            required = (lod.get('RequiredModule') or {}).get('value') or 0
            material = (own(p, required).get('Material') or {}).get('value') if required > 0 else 0
            rec['material'] = p.cls(material) if material and material > 0 else 'import' if material else None
        record.append(rec)
    return dict(emitters=record, native=native)


def wave_record(p, index):
    """A SoundNodeWave: its size, length in seconds, channels, sample rate, and how far after its properties its
    Ogg data starts (-1: none found)."""
    e = p.exports[index - 1]
    data = p.data[e['off']:e['off'] + e['size']]
    k = own(p, index)
    at = data.find(b'OggS')

    def value(key):
        v = (k.get(key) or {}).get('value')
        return v if isinstance(v, (int, float)) else None
    return dict(size=e['size'], seconds=value('Duration'), channels=value('NumChannels'), rate=value('SampleRate'),
                oggAfterProperties=at - (p.properties(index)[1] - e['off']) if at >= 0 else -1)


def cue_waves(p, node, seen=None):
    """The SoundNodeWaves a sound node reaches: through its object properties, its ChildNodes and a
    SoundNodeAmbient's SoundSlots (an archetype's where the node saves none)."""
    seen = set() if seen is None else seen
    if node <= 0 or node in seen:
        return []
    seen.add(node)
    if p.cls(node) == 'SoundNodeWave':
        return [node]
    found = []
    for key, v in own(p, node).items():
        if v['kind'] == 'ObjectProperty' and isinstance(v['value'], int):
            found += cue_waves(p, v['value'], seen)
    try:
        for ref in p.refs(p.effective(node, 'ChildNodes')):
            found += cue_waves(p, ref, seen)
        for slot in p.structs(p.effective(node, 'SoundSlots')):
            wave = slot.get(('Wave', 0))
            if wave and wave['value'] > 0:
                found.append(wave['value'])
    except Exception:  # noqa: BLE001
        pass
    return found


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
    name = Path(path).stem
    try:
        p = package.Package(path)
    except Exception as error:  # noqa: BLE001
        return name, dict(error=repr(error))
    out = dict(licensee=p.header['lic'], emitters={}, sounds={}, flares={}, others={}, systems={}, waves={})
    level = p.by_name.get(LEVEL)
    if level is None:
        return name, out
    users, in_floor = kismet_users(p), floor_listed(p, level)
    em = collections.Counter()
    templates, parameters, parameter_types, em_users = (collections.Counter() for _ in range(4))
    so, classes, cue_place, so_users, wave_uses, asset_cues = (collections.Counter() for _ in range(6))
    fl, fl_templates, fl_users, others = (collections.Counter() for _ in range(4))
    for i in p.children.get(level, []):
        cls, e, k = p.cls(i), p.exports[i - 1], own(p, i)
        if cls == 'Emitter':
            em['count'] += 1
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
            em['based'] += 'Base' in k
            em['fromPrefab'] += bool(e['arch']) and '.Prefabs.' in p.name(e['arch'])
            em['scaled'] += 'DrawScale' in k or 'DrawScale3D' in k
            em['lit'] += 'LightEnvironment' in k
            em_users.update(users.get(i, {}))
            raw = (own(p, component).get('InstanceParameters') or {}).get('value') if component > 0 else None
            if raw:
                em['withParameters'] += 1
                try:
                    for s in p.structs(raw):
                        parameters[str(s.get(('Name', 0), {}).get('value'))] += 1
                        parameter_types[str(s.get(('ParamType', 0), {}).get('value', 'PSPT_None'))] += 1
                except Exception:  # noqa: BLE001
                    em['parametersUnread'] += 1
        elif cls in SOUND_CLASSES:
            so['count'] += 1
            classes[cls] += 1
            component = (k.get('AudioComponent') or {}).get('value') or 0
            cue = p.effective(component, 'SoundCue', 0) if component > 0 else 0
            place = 'none' if not cue else 'import' if cue < 0 else 'actor' if p.name(cue).startswith(LEVEL) else 'asset'
            cue_place[place] += 1
            if place == 'asset':
                asset_cues[p.name(cue)] += 1
            so['kismetNamed'] += i in users
            so['fromPrefab'] += bool(e['arch']) and '.Prefabs.' in p.name(e['arch'])
            so_users.update(users.get(i, {}))
            node = (k.get('SoundNodeInstance') or {}).get('value') or 0
            first = (own(p, cue).get('FirstNode') or {}).get('value') or 0 if cue > 0 else 0
            found = cue_waves(p, first) or (cue_waves(p, node) if node > 0 else [])
            so['noWave'] += not found
            for w in found:
                wave_uses[p.name(w)] += 1
                out['waves'].setdefault(p.name(w), wave_record(p, w))
        elif cls == 'LensFlareSource':
            fl['count'] += 1
            component = (k.get('LensFlareComp') or {}).get('value') or 0
            template = p.effective(component, 'Template', 0) if component > 0 else 0
            fl_templates[p.name(template) if template else '(none)'] += 1
            fl['kismetNamed'] += i in users
            fl['based'] += 'Base' in k
            fl_users.update(users.get(i, {}))
        elif cls in OTHER_CLASSES:
            others[cls] += 1
    out['emitters'] = dict(em, templates=dict(templates), parameters=dict(parameters),
                           parameterTypes=dict(parameter_types), kismetUsers=dict(em_users))
    out['sounds'] = dict(so, classes=dict(classes), cue=dict(cue_place), assetCues=dict(asset_cues),
                         waveUses=dict(wave_uses), kismetUsers=dict(so_users))
    out['flares'] = dict(fl, templates=dict(fl_templates), kismetUsers=dict(fl_users))
    out['others'] = dict(others)
    if p.header['lic'] == 64:
        for i in range(1, len(p.exports) + 1):
            if p.cls(i) == 'ParticleSystem':
                out['systems'][p.name(i)] = system_record(p, i)
        if closure:
            try:
                out['closure'] = closure_record(path, Path(path).parent)
            except Exception as error:  # noqa: BLE001
                out['closureError'] = repr(error)
    return name, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('install'); ap.add_argument('out')
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--closure', action='store_true', help='try transplant.closure on every effect actor (slow)')
    ap.add_argument('--maps', nargs='*', help='only these packages')
    a = ap.parse_args()
    config = Path(a.install) / 'XEW' / 'XComGame' / 'Config'
    base, streams = set(), set()
    for line in (config / 'DefaultMaps.ini').read_bytes().decode('latin-1').splitlines():
        if line.lstrip().startswith(';'):
            continue
        base.update(re.findall(r'(?<![A-Za-z])Name="([^"]+)"', line))
        streams.update(re.findall(r'MapName="([^"]+)"', line))
    files = {p.stem.lower(): p for p in (Path(a.install) / 'XEW' / 'XComGame' / 'CookedPCConsole').glob('*.upk')}
    wanted = sorted({n.lower() for n in (a.maps or base | streams)})
    jobs = [(str(files[n]), a.closure) for n in wanted if n in files]
    with multiprocessing.get_context('spawn').Pool(a.jobs) as pool:
        found = dict(pool.imap_unordered(survey, jobs, chunksize=1))
    base_low = {n.lower() for n in base}
    for name, record in found.items():
        record['role'] = 'base' if name.lower() in base_low else 'stream'
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
        scope='every base map and stream named by a live DefaultMaps.ini record' if not a.maps else 'the packages named',
        closure=a.closure, missingPackages=missing, summary=summary,
        packages={n: found[n] for n in sorted(found, key=str.lower)}), indent=1, sort_keys=True) + '\n',
        encoding='utf-8', newline='\n')
    for group, g in sorted(summary['groups'].items()):
        print('%-15s %3d packages: %5d emitters in %d, %4d sounds in %d, %3d lens flares' % (
            group, g['packages'], g['emitters'].get('count', 0), g['withEmitters'], g['sounds'].get('count', 0),
            g['withSounds'], g['flares'].get('count', 0)))
    print('%d particle systems (%d placed by an emitter), %d waves played by ambient sounds (%.1f MB)' % (
        summary['distinctSystems'], summary['systemsPlaced'], summary['distinctWaves'], summary['waveBytes'] / 1e6))
    print('emitters of Firaxis packages by what a plain preview would make of their system:', summary['preview'])
    for cls, c in sorted(summary['closure'].items()):
        print('closure %-28s %5d could come, %d refused, %d cut references' % (
            cls, c['ok'], sum(c['refused'].values()), sum(c['cut'].values())))
    if missing:
        print('missing packages:', ', '.join(missing))


if __name__ == '__main__':
    main()
