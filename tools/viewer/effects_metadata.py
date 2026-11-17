"""A map's effects, sounds and lens flares for the editor (export 28; private/plans/todo/effects-and-sounds-plan.md,
Part A, stage FX1): what each one is, where it stands, where each of its values comes from, what of the map uses it,
and what the editor may do with it and why not. Read only: nothing here changes a package.

An **effect** is an `Emitter` actor (a placed particle system), a **sound** an ambient sound actor (AmbientSound and
its kin), a **flare** a `LensFlareSource`. Each record has `kind`, `id` (`<prefix><kind>:<export index>`, as a light's
`<prefix>light:<index>`), its identity (`sourcePackage`, `layer`, `actor`, `actorClass`, `component`), its pose
(`location`, `rotation`, `scale`), `listed` (in its level's actor list), `prefab` (the instance that placed it),
`referencedBy` (scene_metadata.kismet_references: what of the package's Kismet names it), `attachedTo` (what it rides
on, or None), `landingRole` (export 22's role when a landing names it), `landingActor` (whether a clear keeps it as
the landing's, native_copy.landing_actor's rule), and `can`/`why`: what the editor may do with it by its own data
(move, copy, delete, values; a sound also audition) and, for each it may not, why.

Values keep apart where they came from: `startsOnFrom`, `valuesFrom` say 'actor' (saved by the actor or its own
component or node), 'cue' (saved by a node of the cue asset a sound plays), 'archetype' (an archetype the map holds),
'class' (the class's default in the game's script packages, or the type's zero where no default saves it), 'table'
(the class's default as CLASS_DEFAULTS holds it, where the script packages can't be read) or 'unresolved' (an
archetype in a package the map doesn't hold).

`systems` ({id: record}) describes each particle system once and `waves` ({id: record}) each wave a sound reaches,
both keyed `<package>|<path>`.
"""
import hashlib
import struct
from pathlib import Path

from package import FormatError, Reader

METADATA_VERSION = 1
LEVEL = 'TheWorld.PersistentLevel'
SOUND_CLASSES = ('AmbientSound', 'AmbientSoundSimple', 'AmbientSoundSimpleToggleable', 'AmbientSoundNonLoop',
                 'AmbientSoundMovable')
# a sound whose cue and node are its own, under the actor (the 557 simple sounds of the census: plan 2.5)
SIMPLE_SOUNDS = ('AmbientSoundSimple', 'AmbientSoundSimpleToggleable', 'AmbientSoundNonLoop')
AMBIENT_NODES = ('SoundNodeAmbient', 'SoundNodeAmbientNonLoop', 'SoundNodeAmbientNonLoopToggle')
# a sound node's values, as the export names them
NODE_VALUES = (('radiusMin', 'RadiusMin', 0.0), ('radiusMax', 'RadiusMax', 0.0), ('volumeMin', 'VolumeMin', 0.0),
               ('volumeMax', 'VolumeMax', 0.0), ('pitchMin', 'PitchMin', 0.0), ('pitchMax', 'PitchMax', 0.0),
               ('attenuate', 'bAttenuate', False), ('spatialize', 'bSpatialize', False),
               ('distanceModel', 'DistanceModel', 'ATTENUATION_Linear'), ('lowPass', 'bAttenuateWithLPF', False),
               ('lowPassMin', 'LPFRadiusMin', 0.0), ('lowPassMax', 'LPFRadiusMax', 0.0))
ATTENUATION_VALUES = tuple(v for v in NODE_VALUES if not v[0].startswith(('volume', 'pitch')))
# The class defaults the starting state and a sound node's values take, as the game's script packages save them
# (Engine.upk, read 17 November 2026; the plan's 2.9): used only where those packages can't be read
CLASS_DEFAULTS = {
    'ParticleSystemComponent': {'bAutoActivate': True},
    'AmbientSound': {'bAutoPlay': True}, 'AmbientSoundSimple': {'bAutoPlay': True},
    'AmbientSoundMovable': {'bAutoPlay': True}, 'AmbientSoundSimpleToggleable': {'bAutoPlay': False},
    'SoundNodeAmbient': {'bAttenuate': True, 'bSpatialize': True, 'RadiusMin': 2000.0, 'RadiusMax': 5000.0,
                         'LPFRadiusMin': 3500.0, 'LPFRadiusMax': 7000.0, 'PitchMin': 1.0, 'PitchMax': 1.0,
                         'VolumeMin': 0.7, 'VolumeMax': 0.7},
}
# a clear keeps the landing's actors (tools/bake/native_copy.py LANDING_PREFABS, LANDING_EXTRA: the same rule)
LANDING_PREFABS = ('DGN_DropShipSoldierSpawn.Prefabs.', 'VEH_Lv1Skyranger_MOD.Prefabs.')
LANDING_EXTRA = ('ARC_Skyranger_Ground_Periphery',)
# a particle emitter's kind, from its first LOD level's type data module (none: sprites)
TYPE_DATA = {'ParticleModuleTypeDataMesh': 'mesh', 'ParticleModuleTypeDataRibbon': 'ribbon',
             'ParticleModuleTypeDataBeam2': 'beam', 'ParticleModuleTypeDataTrail2': 'trail',
             'ParticleModuleTypeDataAnimTrail': 'trail'}
PARAMETER_DISTRIBUTIONS = {'DistributionFloatParticleParameter': 'scalar', 'DistributionVectorParticleParameter': 'vector'}
# the module properties whose values are a particle's colour (a vector parameter feeding one names a colour; a
# colour scale over life multiplies one and is not a colour of its own)
COLOUR_PROPERTIES = {'ParticleModuleColor': ('StartColor',), 'ParticleModuleColor_Seeded': ('StartColor',),
                     'ParticleModuleColorOverLife': ('ColorOverLife',)}
PARAMETER_TYPES = ('PSPT_None', 'PSPT_Scalar', 'PSPT_ScalarRand', 'PSPT_Vector', 'PSPT_VectorRand', 'PSPT_Color',
                   'PSPT_Actor', 'PSPT_Material')
# which of a parameter's kinds a saved type answers (the census's PARAMETER_KINDS)
PARAMETER_KINDS = {'PSPT_Scalar': 'scalar', 'PSPT_ScalarRand': 'scalar', 'PSPT_Vector': 'vector',
                   'PSPT_VectorRand': 'vector', 'PSPT_Color': 'vector'}
ZERO = object()     # no default saves the property: it keeps its type's zero
SCRIPT_PACKAGES = ('XComGame', 'Engine', 'Core')     # piece_flags.SCRIPT_PACKAGES: where class defaults are


def short(path):
    return str(path).rsplit('.', 1)[-1]


# ---------------------------------------------------------------- where a value comes from

class Defaults:
    """An object's properties with where each came from: its own, an archetype in the map, the class's default in the
    game's script packages (XComGame, Engine and Core beside the map: piece_flags.ScriptDefaults), else CLASS_DEFAULTS.
    A placed actor saves no archetype (it is its class's default's); a component or node saves one (an import of the
    class default's subobject, or a prefab archetype's), and a class default's subobject in a script package saves none
    (it is its own class's default's)."""

    def __init__(self, p, scripts=None):
        self.p = p
        if scripts is None:
            import piece_flags
            scripts = piece_flags.ScriptDefaults.of(Path(p.path).parent)
        self.scripts = scripts or None

    def value(self, index, key, zero=None):
        """(value, source) of property `key` (its first slot) of export `index`: source 'actor', 'archetype',
        'class', 'table' or 'unresolved' (value None)."""
        p, i, seen, last = self.p, index, set(), index
        if index <= 0:
            return None, 'unresolved'
        while i > 0:
            if i in seen:
                raise FormatError('Archetype cycle')
            seen.add(i)
            item = p.properties(i)[0].get((key, 0))
            if item is not None:
                return item['value'], 'actor' if i == index else 'archetype'
            last, i = i, p.exports[i - 1]['arch']
        path = p.name(i) if i < 0 else None
        cls = p.cls(last)
        if path is not None and path.split('.')[0] not in SCRIPT_PACKAGES:
            return None, 'unresolved'       # a prefab archetype in another package
        if self.scripts:
            value = self._script(path, cls, key)
            if value is not None:
                found, v = value
                return (zero if v is ZERO else v), 'class'
        table = CLASS_DEFAULTS.get(cls)
        if table is None:
            return None, 'unresolved'
        return table.get(key, zero), 'table'

    def _script(self, path, cls, key):
        """(True, value or ZERO) from the script packages' defaults, or None where the chain can't be followed."""
        seen = set()
        while True:
            if path is None:
                path = next(('%s.Default__%s' % (n, cls) for n in ('Engine', 'XComGame', 'Core')
                             if 'Default__' + cls in self.scripts[n].by_name), None)
                if path is None:
                    return None
            pkg, _, rest = path.partition('.')
            sp = self.scripts.get(pkg)
            j = sp.by_name.get(rest) if sp else None
            if not j or (pkg, j) in seen:
                return None
            seen.add((pkg, j))
            item = sp.properties(j)[0].get((key, 0))
            if item is not None:
                return True, item['value']
            arch = sp.exports[j - 1]['arch']
            if arch < 0:
                path = sp.name(arch)
            elif arch > 0:
                path = '%s.%s' % (pkg, sp.name(arch))
            elif rest.startswith('Default__') and '.' not in rest:
                return True, ZERO           # the top of the chain: nothing saves it
            else:
                path, cls = None, sp.cls(j)  # a class default's subobject: its own class's default


# ---------------------------------------------------------------- reading a package

def level_list(p, level):
    """The exports in a level's actor list, or None when it can't be read."""
    try:
        _, end = p.properties(level)
        owner, count = struct.unpack_from('<ii', p.data, end)
        return set(struct.unpack_from('<%di' % count, p.data, end + 8)) if owner == level else None
    except (FormatError, struct.error, ValueError):
        return None


def subtree(p, index):
    out, todo = [], [index]
    while todo:
        i = todo.pop()
        out.append(i)
        todo.extend(reversed(p.children.get(i, [])))
    return out


def struct_fields(p, raw):
    """A tagged struct's fields by name (first slots), or {} where it doesn't read."""
    try:
        return {k[0]: v['value'] for k, v in p.tagged(Reader(bytes(raw))).items() if k[1] == 0}
    except (FormatError, ValueError, IndexError, struct.error, TypeError):
        return {}


def floats(raw):
    """A float array's values ([] where it doesn't read)."""
    try:
        n = struct.unpack_from('<i', raw)[0]
        if n < 0 or len(raw) != 4 + 4 * n:
            return []
        return list(struct.unpack_from('<%df' % n, raw, 4))
    except (struct.error, TypeError):
        return []


def box(raw):
    """A Box struct (Min, Max, IsValid: 25 bytes, not tagged) as dict(min, max, valid), or None."""
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != 25:
        return None
    v = struct.unpack('<6fB', raw)
    return dict(min=list(v[:3]), max=list(v[3:6]), valid=bool(v[6]))


def floor_lists(p, level, prefix=''):
    """{emitter export: [dict(building, floor)]}: the building floors whose m_aCachedEmitters name each (the effects
    that hide with that floor when the camera cuts it away: plan 2.4). `building` is building_metadata's id."""
    out = {}
    for i in p.children.get(level, []):
        if p.cls(i) != 'XComBuildingVolume':
            continue
        try:
            rows = p.structs(p.effective(i, 'Floors'))
        except (FormatError, ValueError, struct.error):
            continue
        for n, row in enumerate(rows):
            cached = row.get(('m_aCachedEmitters', 0))
            try:
                refs = p.refs(cached['value']) if cached else []
            except (FormatError, ValueError, struct.error):
                continue
            for r in refs:
                if r > 0:
                    out.setdefault(r, []).append(dict(building=prefix + str(i), floor=n))
    return out


def landing_actor(p, i):
    """Whether a clear keeps an actor as the landing's (native_copy.landing_actor: by its archetype)."""
    a = p.exports[i - 1]['arch']
    path = p.name(a) if a else ''
    return path.casefold().startswith(tuple(x.casefold() for x in LANDING_PREFABS)) or short(path) in LANDING_EXTRA


def component_pose(p, component):
    """A component's own transform under its actor: dict(translation, rotation, scale (Scale times Scale3D)), as the
    export's mesh pieces take theirs (export.Exporter.component); its box is drawn through it."""
    scale = p.effective(component, 'Scale', 1.0)
    return dict(translation=[float(v) for v in p.effective(component, 'Translation', [0.0, 0.0, 0.0])],
                rotation=[int(v) for v in p.effective(component, 'Rotation', [0, 0, 0])],
                scale=[float(v) * float(scale) for v in p.effective(component, 'Scale3D', [1.0, 1.0, 1.0])])


def attachment(p, actor):
    """What an actor rides on: dict(actor, actorClass, bone) from its Base (and BaseSkelComponent, BaseBoneName), or
    None when it saves no base or a null one."""
    base = p.own(actor, 'Base', 0) or 0
    skel = p.own(actor, 'BaseSkelComponent', 0) or 0
    if not base and not skel:
        return None
    target = base or skel
    bone = p.own(actor, 'BaseBoneName')
    return dict(actor=p.name(target), actorClass=p.cls(target) if target > 0 else None,
                bone=str(bone) if bone and bone != 'None' else None)


def parameters(p, raw, offers):
    """A ParticleSystemComponent's InstanceParameters as saved: [dict(name, type (its PSPT_ value), the fields it
    saves (scalar, scalarLow, vector, vectorLow, colour, actor, material), offered)]. `offered`: 'yes' (the system has a
    parameter distribution of that name and kind), 'otherKind' (of that name, the other kind: Firaxis's maps set a
    scalar where the distribution is a vector, plan 2.2), 'no', or 'unknown' (the system didn't resolve)."""
    out = []
    by_name = {}
    for o in offers or ():
        by_name.setdefault(o['name'], set()).add(o['kind'])
    for row in p.structs(raw) if raw else []:
        f = {k[0]: v for k, v in row.items() if k[1] == 0}
        name = f.get('Name', {}).get('value')
        kind = f.get('ParamType', {}).get('value', 'PSPT_None')
        if isinstance(kind, int):
            kind = PARAMETER_TYPES[kind] if 0 <= kind < len(PARAMETER_TYPES) else 'PSPT_None'
        record = dict(name=str(name) if name not in (None, 'None') else None, type=str(kind))
        for key, field in (('scalar', 'Scalar'), ('scalarLow', 'Scalar_Low'), ('vector', 'Vector'),
                           ('vectorLow', 'Vector_Low'), ('colour', 'Color')):
            if field in f:
                record[key] = f[field]['value']
        for key, field in (('actor', 'Actor'), ('material', 'Material')):
            ref = f.get(field, {}).get('value')
            if ref:
                record[key] = p.name(ref)
        if offers is None:
            record['offered'] = 'unknown'
        elif record['name'] in by_name and PARAMETER_KINDS.get(record['type']) in by_name[record['name']]:
            record['offered'] = 'yes'
        elif record['name'] in by_name:
            record['offered'] = 'otherKind'
        else:
            record['offered'] = 'no'
        out.append(record)
    return out


def system_record(p, index, defaults):
    """A ParticleSystem: dict(path, name, package, fingerprint (the SHA-256 of everything under it, first 16 digits),
    objects, bytes, lodLevels, emitters, offers, fixedBox). Each emitter (its first LOD level, as read): kind (sprite,
    mesh, ribbon, beam, trail), lods, cookedOut, material, loops (EmitterLoops: 0 is for ever), duration, delay, bursts
    (how many its spawn module lists), lifetime ([least, most] its lifetime table holds, or None). No "looping" or
    "plays once" is made from these (plan 2.2). Each offer: a particle parameter distribution (name, kind scalar or
    vector, module and property that read it, modes, constant, input and output ranges, colour: whether it feeds a
    particle colour). fixedBox: dict(used, min, max, valid) or None where it saves none."""
    under = subtree(p, index)
    h = hashlib.sha256()
    total = 0
    for j in under:
        e = p.exports[j - 1]
        h.update(p.cls(j).encode('latin-1') + b'\0' + p.data[e['off']:e['off'] + e['size']])
        total += e['size']
    record = dict(path=p.name(index), name=short(p.name(index)), package=p.path.stem, fingerprint=h.hexdigest()[:16],
                  objects=len(under), bytes=total, lodLevels=0, emitters=[], offers=[], fixedBox=None)

    def own(i, key, default=None):
        return defaults.value(i, key, default)[0]
    try:
        emitters = [r for r in p.refs(p.own(index, 'Emitters')) if r > 0]
    except (FormatError, ValueError, struct.error):
        emitters = []
    for em in emitters:
        try:
            lods = [r for r in p.refs(p.own(em, 'LODLevels')) if r > 0]
        except (FormatError, ValueError, struct.error):
            lods = []
        record['lodLevels'] = max(record['lodLevels'], len(lods))
        e = dict(kind=None, lods=len(lods), cookedOut=bool(p.own(em, 'bCookedOut', False)), material=None, loops=None,
                 duration=None, delay=None, bursts=0, lifetime=None)
        if lods:
            lod = lods[0]
            type_data = p.own(lod, 'TypeDataModule', 0) or 0
            e['kind'] = TYPE_DATA.get(p.cls(type_data), p.cls(type_data)) if type_data > 0 else 'sprite'
            required = p.own(lod, 'RequiredModule', 0) or 0
            if required > 0:
                material = p.own(required, 'Material', 0) or 0
                e['material'] = p.name(material) if material else None
                e['loops'] = own(required, 'EmitterLoops', 0)
                e['duration'] = own(required, 'EmitterDuration', 0.0)
                e['delay'] = own(required, 'EmitterDelay', 0.0)
            spawn = p.own(lod, 'SpawnModule', 0) or 0
            if spawn > 0:
                try:
                    e['bursts'] = len(p.structs(p.own(spawn, 'BurstList')))
                except (FormatError, ValueError, struct.error):
                    pass
            try:
                modules = [m for m in p.refs(p.own(lod, 'Modules')) if m > 0]
            except (FormatError, ValueError, struct.error):
                modules = []
            for m in modules:
                if p.cls(m).startswith('ParticleModuleLifetime'):
                    table = floats(struct_fields(p, p.own(m, 'Lifetime')).get('LookupTable'))
                    if table:
                        e['lifetime'] = [min(table), max(table)]
        record['emitters'].append(e)
    for j in under:
        kind = PARAMETER_DISTRIBUTIONS.get(p.cls(j))
        if not kind:
            continue
        name = p.own(j, 'ParameterName')
        if not name or name == 'None':
            continue
        outer = p.exports[j - 1]['outer']
        module = p.cls(outer) if outer > 0 else None
        prop = None
        if outer > 0:
            for (key, slot), item in p.properties(outer)[0].items():
                if item['kind'] == 'StructProperty' and str(item['subtype']).startswith('RawDistribution') \
                        and struct_fields(p, item['value']).get('Distribution') == j:
                    prop = key
                    break
        offer = dict(name=str(name), kind=kind, module=module, property=prop)
        if kind == 'scalar':
            offer['modes'] = [str(own(j, 'ParamMode', 'DPM_Normal'))]
            offer['constant'] = own(j, 'Constant', 0.0)
            offer['input'] = [own(j, 'MinInput', 0.0), own(j, 'MaxInput', 0.0)]
            offer['output'] = [own(j, 'MinOutput', 0.0), own(j, 'MaxOutput', 0.0)]
        else:
            props = p.properties(j)[0]
            offer['modes'] = [str(props[('ParamModes', k)]['value']) if ('ParamModes', k) in props else 'DPM_Normal'
                              for k in range(3)]
            offer['constant'] = own(j, 'Constant', [0.0, 0.0, 0.0])
            offer['input'] = [own(j, 'MinInput', [0.0, 0.0, 0.0]), own(j, 'MaxInput', [0.0, 0.0, 0.0])]
            offer['output'] = [own(j, 'MinOutput', [0.0, 0.0, 0.0]), own(j, 'MaxOutput', [0.0, 0.0, 0.0])]
        offer['colour'] = kind == 'vector' and prop in COLOUR_PROPERTIES.get(module, ())
        record['offers'].append(offer)
    record['offers'].sort(key=lambda o: (o['name'].casefold(), o['kind'], str(o['module']), str(o['property'])))
    used = defaults.value(index, 'bUseFixedRelativeBoundingBox', False)[0]
    fixed = box(p.own(index, 'FixedRelativeBoundingBox'))
    if fixed or used:
        record['fixedBox'] = dict(used=bool(used), **(fixed or dict(min=None, max=None, valid=False)))
    return record


def wave_record(p, index):
    """A SoundNodeWave: dict(path, name, package, seconds, channels, rate, size (its export's bytes), ogg (the Ogg
    stream's bytes), playable, why). Its bulk records are read by their 16-byte headers (flags, element count, size,
    offset), as the census reads them: the second is the PC's, the Ogg stream (plan 2.5). `playable` is true only
    where that record is in the export, uncompressed (flags 0, element count equal to its size) and starts as an Ogg
    stream; otherwise `why` says what it is. The stream itself is checked where it is played (FX2)."""
    e = p.exports[index - 1]
    end = e['off'] + e['size']

    def value(key):
        v = p.own(index, key)
        return v if isinstance(v, (int, float)) else None
    out = dict(path=p.name(index), name=short(p.name(index)), package=p.path.stem, seconds=value('Duration'),
               channels=value('NumChannels'), rate=value('SampleRate'), size=e['size'], ogg=None, playable=False,
               why=None)
    try:
        pos = p.properties(index)[1]
        records = []
        while pos + 16 <= end and len(records) < 5:
            flags, count, size, offset = struct.unpack_from('<IiiI', p.data, pos)
            pos += 16
            inline = not flags & 1 and size > 0
            records.append((flags, count, size, offset, pos if inline else None))
            if inline:
                if offset != pos or pos + size > end:
                    out['why'] = 'its sound data is not where its header says'
                    return out
                pos += size
    except (FormatError, struct.error) as error:
        out['why'] = 'its sound data does not read: %s' % error
        return out
    if len(records) < 2:
        out['why'] = 'it holds no PC sound data'
        return out
    flags, count, size, offset, at = records[1]
    if size <= 0:
        out['why'] = 'it holds no PC sound data'
    elif at is None:
        out['why'] = 'its PC sound data is stored outside the map'
    elif flags or count != size:
        out['why'] = 'its PC sound data is compressed'
    elif p.data[at:at + 4] != b'OggS':
        out['why'] = 'its PC sound data is not an Ogg stream'
    else:
        out.update(ogg=size, playable=True)
    return out


def sound_graph(p, cue, node):
    """(the SoundNodeWaves a sound reaches, its nodes' classes {class: count}, why it reaches none or None). `cue`:
    its audio component's SoundCue (0: none), `node`: its SoundNodeInstance (0: none). An ambient node's slots may be
    an archetype's."""
    if cue < 0:
        return [], {}, 'its cue is in another package'
    seen, found, why, classes = set(), [], [], {}

    def walk(n):
        if n < 0:
            why.append('a node or wave is in another package')
            return
        if n == 0 or n in seen:
            return
        seen.add(n)
        cls = p.cls(n)
        if cls == 'SoundNodeWave':
            found.append(n)
            return
        classes[cls] = classes.get(cls, 0) + 1
        try:
            children = p.effective(n, 'ChildNodes')
            for ref in p.refs(children) if children else []:
                walk(ref)
            if cls in AMBIENT_NODES:
                slots = p.effective(n, 'SoundSlots')
                entries = p.structs(slots) if slots else []
                if not entries:
                    why.append('its node has no sound slots')
                for slot in entries:
                    wave = slot.get(('Wave', 0))
                    if wave and wave['value']:
                        walk(wave['value'])
                    else:
                        why.append('a sound slot names no wave')
            wave = p.own(n, 'Wave', 0) if cls != 'SoundNodeWave' else 0
            if isinstance(wave, int) and wave:
                walk(wave)
        except (FormatError, ValueError, struct.error):
            why.append('a node could not be read')
    first = (p.own(cue, 'FirstNode', 0) or 0) if cue > 0 else 0
    walk(first)
    if not found and node > 0:
        walk(node)
    waves = list(dict.fromkeys(found))
    if waves:
        return waves, classes, None
    if not cue and node <= 0:
        return [], classes, 'it has no cue and no node'
    return [], classes, (why[0] if why else 'its nodes reach no wave')


# ---------------------------------------------------------------- the records

def capabilities(record, caps):
    """Set a record's `can` and `why` for the capabilities `caps` ({name: why it can't, or None}). A streamed level's
    actor, one its level's actor list doesn't hold and one that rides on another can't have any (the plan's Part A:
    the editor shows them and doesn't change them), whatever else holds. Returns the record."""
    blocked = None
    if record.get('stream'):
        blocked = 'it belongs to the stream %s, which the editor shows but doesn\'t change' % record['stream']
    elif not record.get('listed', True):
        blocked = 'it isn\'t in the level\'s actor list, so the game doesn\'t load it'
    elif record.get('attachedTo'):
        blocked = 'it rides on %s and moves with it' % short(record['attachedTo']['actor'])
    record['can'], record['why'] = {}, {}
    for cap, reason in caps.items():
        reason = blocked or reason
        record['can'][cap] = reason is None
        if reason:
            record['why'][cap] = reason
    return record


def describe(p, kismet=None, prefabs=None, landings=None, carried=None, prefix='', layer='base', stream=None,
             defaults=None, warn=None):
    """The package's effects, sounds and flares: dict(effects, sounds, flares, systems, waves), the first three
    sorted by actor. kismet: kismet_references' (computed when None); prefabs: prefab_members'; landings: export 22's
    landing_metadata (its actors' roles); carried: {effect path: dict(by, how)} (export 23's carriedBy); prefix,
    layer, stream: a streamed package's (its records' ids, `layer` 'stream', its name)."""
    import scene_metadata
    out = dict(effects=[], sounds=[], flares=[], systems={}, waves={})
    level = p.by_name.get(LEVEL)
    if level is None:
        return out
    defaults = defaults or Defaults(p)
    kismet = scene_metadata.kismet_references(p, warn) if kismet is None else kismet
    prefabs = scene_metadata.prefab_members(p, warn) if prefabs is None else prefabs
    carried = carried or {}
    roles = {}
    for landing in landings or ():
        for a in landing.get('actors') or ():
            roles[a['path']] = a['role']
        for a in (landing.get('skyranger') or {}).get('actors') or ():
            roles[a['path']] = a['role']
    listed = level_list(p, level)
    floors = floor_lists(p, level, prefix)
    actors =[i for i in p.children.get(level, []) if p.cls(i) in ('Emitter', 'LensFlareSource') + SOUND_CLASSES]
    cues = {}
    for i in actors:
        if p.cls(i) in SOUND_CLASSES:
            component = p.effective(i, 'AudioComponent', 0) or 0
            cue = p.effective(component, 'SoundCue', 0) if component > 0 else 0
            if cue:
                cues.setdefault(cue, []).append(i)

    def common(i, kind, component):
        name = p.name(i)
        location = p.effective(i, 'Location', [0.0, 0.0, 0.0])
        rotation = p.effective(i, 'Rotation', [0, 0, 0])
        draw = p.effective(i, 'DrawScale', 1.0)
        draw3 = p.effective(i, 'DrawScale3D', [1.0, 1.0, 1.0])
        record = dict(kind=kind, id='%s%s:%d' % (prefix, kind, i), actor=name, actorClass=p.cls(i),
                      component=p.name(component) if component else None, sourcePackage=p.path.stem, layer=layer,
                      stream=stream, location=[float(v) for v in location], rotation=[int(v) for v in rotation],
                      drawScale=float(draw), drawScale3D=[float(v) for v in draw3],
                      scale=[float(v) * float(draw) for v in draw3], listed=listed is None or i in listed,
                      prefab=str(prefabs[i]).rsplit('.', 1)[-1] if i in prefabs else None,
                      referencedBy=list(kismet.get(i, [])), attachedTo=attachment(p, i),
                      landingRole=roles.get(name), landingActor=landing_actor(p, i))
        return record

    def system_of(component):
        template = p.effective(component, 'Template', 0) if component > 0 else 0
        if not template:
            return None, None
        if template < 0:
            return '%s|%s' % (p.path.stem, p.name(template)), None
        key = '%s|%s' % (p.path.stem, p.name(template))
        if key not in out['systems']:
            try:
                out['systems'][key] = system_record(p, template, defaults)
            except (FormatError, ValueError, IndexError, struct.error) as error:
                if warn:
                    warn(p.name(template), 'particle system not read: %s' % error)
                out['systems'][key] = None
        return key, out['systems'][key]

    for i in actors:
        cls = p.cls(i)
        try:
            if cls == 'Emitter':
                component = p.effective(i, 'ParticleSystemComponent', 0) or 0
                record = common(i, 'effect', component if component > 0 else 0)
                key, system = system_of(component)
                template = p.effective(component, 'Template', 0) if component > 0 else 0
                record.update(template=p.name(template) if template else None, system=key,
                              hidden=bool(defaults.value(i, 'bHidden', False)[0]),
                              floors=floors.get(i, []), lit=bool(p.effective(i, 'LightEnvironment', 0)),
                              componentPose=component_pose(p, component) if component > 0 else None)
                on, source = defaults.value(component, 'bAutoActivate', False) if component > 0 else (None, 'unresolved')
                record.update(startsOn=None if on is None else bool(on), startsOnFrom=source)
                raw, source = defaults.value(component, 'InstanceParameters') if component > 0 else (None, None)
                offers = system['offers'] if system else None
                record['parameters'] = parameters(p, raw, offers) if raw else []
                record['parametersFrom'] = source if raw else None
                c = carried.get(record['actor'])
                record.update(carriedBy=c['by'] if c else None, carriedHow=c['how'] if c else None)
                capabilities(record, dict(move=None if not record['landingRole'] else 'it is the landing\'s: it moves with its zone '
                                                                              'in the Landing zones view',
                                  copy=None if template else 'it plays no particle system',
                                  delete=None if not record['landingRole'] else 'it is the landing\'s: it goes with its zone',
                                  values=None if component > 0 else 'it has no particle component'))
                out['effects'].append(record)
            elif cls in SOUND_CLASSES:
                component = p.effective(i, 'AudioComponent', 0) or 0
                record = common(i, 'sound', component if component > 0 else 0)
                cue = p.effective(component, 'SoundCue', 0) if component > 0 else 0
                node = p.effective(i, 'SoundNodeInstance', 0) or 0
                on, source = defaults.value(i, 'bAutoPlay', False)
                record.update(startsOn=None if on is None else bool(on), startsOnFrom=source)
                private = bool(cue) and cue > 0 and p.name(cue).startswith(record['actor'] + '.')
                record['cue'] = dict(path=p.name(cue), private=private, sharedBy=len(cues.get(cue, [])) - 1) if cue else None
                record['node'] = dict(path=p.name(node), nodeClass=p.cls(node)) if node > 0 else None
                waves, nodes, why = sound_graph(p, cue, node)
                record['nodes'] = nodes
                record['waves'] = []
                for w in waves:
                    if w < 0:
                        continue
                    wkey = '%s|%s' % (p.path.stem, p.name(w))
                    if wkey not in out['waves']:
                        out['waves'][wkey] = wave_record(p, w)
                    record['waves'].append(wkey)
                record['noSound'] = why
                # values: a simple sound's own node; a cue asset's one attenuation node (read only)
                values, sources, value_node = {}, {}, None
                if node > 0 and p.cls(node) in AMBIENT_NODES:
                    value_node, wanted = node, NODE_VALUES
                else:
                    attenuation = [j for j in subtree(p, cue) if p.cls(j) == 'SoundNodeAttenuation'] if cue > 0 else []
                    if len(attenuation) == 1:
                        value_node, wanted = attenuation[0], ATTENUATION_VALUES
                for key, prop, zero in wanted if value_node else ():
                    values[key], sources[key] = defaults.value(value_node, prop, zero)
                    if value_node != node and sources[key] == 'actor':
                        sources[key] = 'cue'     # saved by a node of the cue asset, not the sound's own
                record.update(values=values, valuesFrom=sources, valuesNode=p.name(value_node) if value_node else None)
                simple = cls in SIMPLE_SOUNDS and private and value_node == node and node > 0
                shared = len(cues.get(cue, [])) if cue else 0
                if simple:
                    values_why = None
                elif shared > 1:
                    values_why = 'its cue %s is shared by %d of the map\'s sounds' % (short(p.name(cue)), shared)
                elif cue and not private:
                    values_why = 'its cue %s is a game asset, not its own' % short(p.name(cue))
                else:
                    values_why = 'it has no node of its own'
                record['carriedBy'], record['carriedHow'] = None, None
                capabilities(record, dict(move=None if not record['landingRole'] else 'it is the landing\'s: it moves with its zone '
                                                                              'in the Landing zones view',
                                  copy=None if (component > 0 and cue) else 'it has no cue to copy',
                                  delete=None if not record['landingRole'] else 'it is the landing\'s: it goes with its zone',
                                  values=values_why))
                # hearing a wave changes nothing, so a stream's or a riding sound can be heard too
                if not record['waves']:
                    audition = 'No sound set' if why in ('a sound slot names no wave', 'its node has no sound slots') \
                        else (why or 'it reaches no wave')
                else:
                    audition = next((out['waves'][w]['why'] for w in record['waves'] if not out['waves'][w]['playable']), None)
                record['can']['audition'] = audition is None
                if audition:
                    record['why']['audition'] = audition
                out['sounds'].append(record)
            else:
                component = p.effective(i, 'LensFlareComp', 0) or 0
                record = common(i, 'flare', component if component > 0 else 0)
                template = p.effective(component, 'Template', 0) if component > 0 else 0
                colour = p.effective(component, 'SourceColor') if component > 0 else None
                record.update(template=p.name(template) if template else None,
                              colour=list(colour) if isinstance(colour, list) else None,
                              hidden=bool(defaults.value(i, 'bHidden', False)[0]))
                record['carriedBy'], record['carriedHow'] = None, None
                capabilities(record, dict(move=None, copy=None if template else 'it names no flare template', delete=None,
                                  values='a flare\'s template and colour aren\'t edited'))
                out['flares'].append(record)
        except (FormatError, ValueError, IndexError, struct.error) as error:
            if warn:
                warn(p.name(i), 'not read: %s' % error)
    for key in ('effects', 'sounds', 'flares'):
        out[key].sort(key=lambda r: r['actor'])
    out['systems'] = {k: v for k, v in out['systems'].items() if v is not None}
    return out
