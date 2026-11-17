"""What the page needs to draw a likeness of a particle system (export 29; the effects and sounds plan, Part J1, stage
FXV1): for each emitter's first LOD level its kind (sprites or meshes), the textures its material samples and how it
is blended, how its particles face the camera, and its numbers: the spawn rate and bursts, and each followed module's
distributions, as the baked lookup tables the game plays or as the particle parameter that feeds them.

A cooked RawDistribution struct is saved as its difference from the module class's default (the engine's script
package), so a table's shape (Op, values to an entry, floats to an entry, time scale and start) is read through the
module's archetype chain (`effects_metadata.Defaults.chain`). The floats are the least and most, then the entries:

    LookupTable = [min, max, entry 0, entry 1, ...]         each entry LookupTableChunkSize floats
    Op 1 (none): an entry is the value (1 float, or 3)      Op 2 (random), 3 (extreme): its least, then its most
    entry index = (time - LookupTableStartTime) * LookupTableTimeScale, blended to the next, held at the last

A particle parameter's distribution is kept as an object (its name, mode, constant and ranges): its value comes from
the effect's instance parameters, which the export has.

Nothing here says how sure the drawing is: an emitter the page can't draw gets `draw: None` and `why`."""
import struct

from package import FormatError
from effects_metadata import PARAMETER_DISTRIBUTIONS, floats, short, struct_fields

DRAW_VERSION = 1
P = 'ParticleModule'
# the modules the page's simulator follows (effects_preview.js); any other is named in `ignored`
FOLLOWED = frozenset(P + m for m in (
    'Lifetime', 'Lifetime_Seeded', 'Location', 'Location_Seeded', 'LocationPrimitiveBox', 'LocationPrimitiveSphere',
    'LocationPrimitiveCylinder', 'Velocity', 'Velocity_Seeded', 'VelocityOverLifetime', 'Acceleration',
    'AccelerationOverLifetime', 'Size', 'Size_Seeded', 'SizeMultiplyLife', 'SizeScale', 'Color', 'Color_Seeded',
    'ColorOverLife', 'ColorScaleOverLife', 'Rotation', 'Rotation_Seeded', 'RotationRate', 'RotationRateMultiplyLife',
    'SubUV', 'MeshRotation', 'MeshRotationRate', 'MeshRotationRateMultiplyLife', 'MeshRotationRateOverLife',
    'KillHeight'))
# modules that change nothing the drawing shows (they feed the material or sort the particles): not named as ignored
SILENT = frozenset(P + m for m in ('ParameterDynamic', 'ParameterDynamicModulator', 'CameraOffset', 'OrientationAxisLock',
                                   'MeshMaterial', 'SourceMovement', 'Required', 'Spawn'))
HOUSEKEEPING = frozenset(('LODValidity', 'bSpawnModule', 'bUpdateModule', 'bFinalUpdateModule', 'bCurvesAsColor',
                          'b3DDrawMode', 'bSupported3DDrawMode', 'bEnabled', 'bEditable', 'ModuleEditorColor',
                          'LODDuplicate', 'bSupportsRandomSeed', 'bRequiresLoopingNotification', 'RandomSeedInfo',
                          'IdenticalIgnoreProperties'))
NOT_PICTURE = frozenset('NML NRM NORM NOR NORMAL NORMALS DISTORTION REFLECTION REFL CUBE CUBEMAP'.split())
MASK_WORDS = frozenset('MASK MSK ALPHA GRADIENT GRAD OPACITY OPA'.split())
ALPHA_FORMATS = ('PF_DXT5', 'PF_DXT3', 'PF_A8R8G8B8')
# Sprite materials whose textures the name rule (pick_textures) gets wrong, by material path: {picture: a texture's
# short name, mask: one or None, opacity: 'alpha' | 'brightness', markerOnly: True (not drawn: its marker alone)}.
# Filled from the comparison with the game's own pictures (plan Part G); a change here needs DRAW_VERSION raised.
RULES = {}


def merged(defaults, p, index):
    """An object's properties through its archetype chain: {key: (package, item)} of first slots, the nearest wins."""
    out = {}
    for pkg, j in defaults.chain(index):
        try:
            props = pkg.properties(j)[0]
        except (FormatError, ValueError, IndexError, struct.error):
            continue
        for (key, slot), item in props.items():
            if slot == 0 and key not in out:
                out[key] = (pkg, item)
    return out


def table(fields, vector):
    """A distribution's table from its struct's fields (merged through the chain), or None where it isn't one this
    reads: dict(op, lock, per, chunk, scale, start, min, max, entries: [[floats]])."""
    values = floats(fields.get('LookupTable'))
    op, per = int(fields.get('Op', 1) or 0), int(fields.get('LookupTableNumElements', 1) or 0)
    width = 3 if vector else 1
    chunk = int(fields.get('LookupTableChunkSize') or width * (1 if op == 1 else 2))
    if op not in (1, 2, 3) or chunk not in (width, 2 * width) or len(values) < 2 + chunk or (len(values) - 2) % chunk:
        return None
    if (op == 1) != (chunk == width):
        return None
    body = values[2:]
    return dict(op=op, lock=int(fields.get('Type', 0) or 0), per=per, chunk=chunk,
                scale=float(fields.get('LookupTableTimeScale', 0.0) or 0.0),
                start=float(fields.get('LookupTableStartTime', 0.0) or 0.0), min=values[0], max=values[1],
                entries=[body[k:k + chunk] for k in range(0, len(body), chunk)])


def parameter(defaults, p, j, kind):
    """A particle parameter distribution's record: dict(parameter, kind, modes, constant, input, output)."""
    def own(key, zero):
        return defaults.value(j, key, zero)[0]
    name = own('ParameterName', None)
    if not name or name == 'None':
        return None
    if kind == 'scalar':
        return dict(parameter=str(name), kind=kind, modes=[str(own('ParamMode', 'DPM_Normal'))],
                    constant=own('Constant', 0.0), input=[own('MinInput', 0.0), own('MaxInput', 0.0)],
                    output=[own('MinOutput', 0.0), own('MaxOutput', 0.0)])
    props = p.properties(j)[0]
    zero = [0.0, 0.0, 0.0]
    return dict(parameter=str(name), kind=kind,
                modes=[str(props[('ParamModes', k)]['value']) if ('ParamModes', k) in props else 'DPM_Normal' for k in range(3)],
                constant=own('Constant', zero), input=[own('MinInput', zero), own('MaxInput', zero)],
                output=[own('MinOutput', zero), own('MaxOutput', zero)])


def distribution(defaults, p, index, key):
    """Property `key` of module `index` as the page reads it: dict(table) fields, a dict(parameter, ...) or
    dict(unread: why). None where the module (through its chain) has no such property."""
    fields, vector, first, kept = {}, None, True, None
    for pkg, j in defaults.chain(index):
        try:
            item = pkg.properties(j)[0].get((key, 0))
        except (FormatError, ValueError, IndexError, struct.error):
            item = None
        if item is None:
            continue
        if vector is None:
            vector = 'Vector' in str(item.get('subtype'))
        f = struct_fields(pkg, item['value'])
        if first:
            first = False
            d = f.get('Distribution') or 0
            if pkg is p and isinstance(d, int) and d > 0 and p.cls(d) in PARAMETER_DISTRIBUTIONS:
                record = parameter(defaults, p, d, PARAMETER_DISTRIBUTIONS[p.cls(d)])
                if record:
                    return record
            if pkg is p and isinstance(d, int) and d > 0:
                kept = p.cls(d)         # a distribution the cook left as an object (a curve): its table is empty
        for k, v in f.items():
            fields.setdefault(k, v)
    if vector is None:
        return None
    return table(fields, vector) or dict(unread='kept as %s' % kept if kept else 'table not read')


def plain(value):
    if isinstance(value, bool) or isinstance(value, (int, float, str)):
        return value
    if isinstance(value, (list, tuple)) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
        return list(value)
    return None


def module_record(defaults, p, index):
    """A followed module: dict(cls (without 'ParticleModule'), and each of its properties: a distribution, a number,
    a flag, a name or a vector)."""
    record = dict(cls=p.cls(index)[len(P):])
    for key, (pkg, item) in sorted(merged(defaults, p, index).items()):
        if key in HOUSEKEEPING:
            continue
        if item['kind'] == 'StructProperty' and str(item.get('subtype')).startswith('RawDistribution'):
            value = distribution(defaults, p, index, key)
        else:
            value = plain(item['value'])
        if value is not None:
            record[key] = value
    return record


def words(name):
    import re
    return {w.upper() for w in re.findall(r'[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+', name)}


def material_chain(p, material):
    chain, seen, current = [], set(), material
    while isinstance(current, int) and current > 0 and current not in seen:
        seen.add(current)
        chain.append(current)
        current = p.own(current, 'Parent', 0) or 0
    return chain


def sprite_textures(p, material, compiled_textures):
    """The textures a sprite's material draws with, in the order they are met: [(export index, parameter name or
    None)], the material's own parameters first (through its parents, the nearest's value), then its compiled
    shaders' list. Imports are left out."""
    chain = material_chain(p, material)
    named = {}
    for mat in reversed(chain):
        for c in p.children.get(mat, []):
            name, tex = p.own(c, 'ParameterName'), p.own(c, 'Texture', 0)
            if name and isinstance(tex, int) and tex:
                named[str(name)] = tex
        try:
            for row in p.structs(p.own(mat, 'TextureParameterValues')):
                name = row.get(('ParameterName', 0), {}).get('value')
                tex = row.get(('ParameterValue', 0), {}).get('value', 0)
                if name is not None and isinstance(tex, int) and tex:
                    named[str(name)] = tex
        except (FormatError, ValueError, IndexError, struct.error, TypeError):
            pass
    out, seen = [], set()
    for name, tex in named.items():
        if tex > 0 and tex not in seen and 'Texture' in p.cls(tex):
            seen.add(tex)
            out.append((tex, name))
    root = chain[-1] if chain else 0
    if root and p.cls(root) == 'Material':
        for tex in compiled_textures(p, root):
            if tex > 0 and tex not in seen:
                seen.add(tex)
                out.append((tex, None))
    return out


def pick_textures(candidates, grid=False):
    """Which of a sprite's textures is its picture and which its mask, by their names: [(key, texture name, parameter
    name, has alpha)] -> (picture key or None, mask key or None). A normal map, a distortion or a reflection is
    neither. A mask is a texture named as one (Mask, Alpha, Gradient); the picture is the first other, one named for
    sub-images first where the emitter has a grid. With no picture the mask alone shapes a plain colour."""
    usable = [c for c in candidates if not words(short(c[1])) & NOT_PICTURE and not words(c[2] or '') & NOT_PICTURE]
    is_mask = lambda c: bool((words(short(c[1])) | words(c[2] or '')) & MASK_WORDS)  # noqa: E731
    pictures = [c for c in usable if not is_mask(c)]
    masks = [c for c in usable if is_mask(c)]
    if grid:
        pictures.sort(key=lambda c: 'SUB' not in words(short(c[1])))
    picture = pictures[0][0] if pictures else None
    mask = masks[0][0] if masks else None
    return picture, mask


def emitter_draw(p, defaults, lod, exporter, compiled_textures, rules=None):
    """An emitter's first LOD level as the page draws it: (draw record or None, why not)."""
    if defaults.value(lod, 'bEnabled', True)[0] is False:
        return None, 'switched off in its system'
    type_data = p.own(lod, 'TypeDataModule', 0) or 0
    kind = 'sprite'
    if type_data > 0:
        cls = p.cls(type_data)
        if cls != P + 'TypeDataMesh':
            return None, {'ParticleModuleTypeDataRibbon': 'a ribbon', 'ParticleModuleTypeDataBeam2': 'a beam',
                          'ParticleModuleTypeDataTrail2': 'a trail'}.get(cls, short(cls))
        kind = 'mesh'
    required = p.own(lod, 'RequiredModule', 0) or 0
    if required <= 0:
        return None, 'no required module'

    def req(key, zero):
        return defaults.value(required, key, zero)[0]
    material = p.own(required, 'Material', 0) or 0
    draw = dict(kind=kind, facing=str(req('ScreenAlignment', 'PSA_Square')),
                subImages=[int(req('SubImages_Horizontal', 1) or 1), int(req('SubImages_Vertical', 1) or 1)],
                interp=str(req('InterpolationMethod', 'PSUVIM_None')), localSpace=bool(req('bUseLocalSpace', False)),
                duration=float(req('EmitterDuration', 1.0) or 0.0), loops=int(req('EmitterLoops', 0) or 0),
                delay=float(req('EmitterDelay', 0.0) or 0.0), blend='BLEND_Opaque', lit=False, twoSided=False)
    chain = material_chain(p, material)
    lighting = 'MLM_Phong'
    for mat in reversed(chain):
        draw['blend'] = str(p.own(mat, 'BlendMode', draw['blend']))
        lighting = str(p.own(mat, 'LightingModel', lighting))
        draw['twoSided'] = bool(p.own(mat, 'TwoSided', draw['twoSided']))
    draw['lit'] = lighting != 'MLM_Unlit'
    draw['material'] = p.name(material) if material else None
    if kind == 'mesh':
        mesh = p.own(type_data, 'Mesh', 0) or 0
        if mesh <= 0 or p.cls(mesh) != 'StaticMesh':
            return None, 'its mesh is in another package' if mesh < 0 else 'no mesh'
        override = material if material > 0 and defaults.value(type_data, 'bOverrideMaterial', False)[0] else 0
        key, materials = exporter.particle_mesh(mesh, override)
        if not key:
            return None, 'its mesh could not be read'
        draw.update(mesh=key, materials=materials)
    else:
        candidates = []
        for tex, name in (sprite_textures(p, material, compiled_textures) if material > 0 else []):
            key = exporter.texture(tex)
            if key:
                info = exporter.textures[key]
                candidates.append((key, p.name(tex), name, info.get('format') in ALPHA_FORMATS))
        rule = (rules or {}).get(draw['material']) or {}
        if rule.get('markerOnly'):
            return None, 'not drawn here'
        grid = draw['subImages'] != [1, 1]
        picture, mask = pick_textures(candidates, grid)
        by_name = {short(c[1]): c[0] for c in candidates}
        if rule.get('picture') in by_name:
            picture = by_name[rule['picture']]
        if 'mask' in rule:
            mask = by_name.get(rule['mask'])
        if not candidates and material <= 0:
            return None, 'its material is in another package' if material < 0 else 'no material'
        draw.update(textures=[dict(key=c[0], name=c[1], parameter=c[2], alpha=c[3]) for c in candidates],
                    picture=picture, mask=mask,
                    opacity=rule.get('opacity') or ('alpha' if picture and dict((c[0], c[3]) for c in candidates)[picture] else 'brightness'))
    spawn = p.own(lod, 'SpawnModule', 0) or 0
    draw['rate'] = distribution(defaults, p, spawn, 'Rate') if spawn > 0 else None
    draw['rateScale'] = distribution(defaults, p, spawn, 'RateScale') if spawn > 0 else None
    if draw['rate'] is None:
        draw['rate'] = distribution(defaults, p, required, 'SpawnRate')
    bursts = []
    if spawn > 0:
        try:
            for row in p.structs(p.own(spawn, 'BurstList')):
                get = lambda k, zero: row.get((k, 0), {}).get('value', zero)  # noqa: E731
                bursts.append(dict(count=int(get('Count', 0)), countLow=int(get('CountLow', -1)), time=float(get('Time', 0.0))))
        except (FormatError, ValueError, IndexError, struct.error, TypeError):
            pass
    draw['bursts'] = bursts
    try:
        modules = [m for m in p.refs(p.own(lod, 'Modules')) if m > 0]
    except (FormatError, ValueError, struct.error):
        modules = []
    draw['modules'], ignored = [], []
    for m in modules:
        cls = p.cls(m)
        if defaults.value(m, 'bEnabled', True)[0] is False:
            continue
        if cls in FOLLOWED:
            draw['modules'].append(module_record(defaults, p, m))
        elif cls not in SILENT and cls[len(P):] not in ignored:
            ignored.append(cls[len(P):])
    draw['ignored'] = ignored
    rate = draw['rate'] or {}
    silent = not bursts and 'entries' in rate and not any(any(e) for e in rate['entries'])
    if silent:
        return None, 'another emitter\'s event starts it' if any(i.startswith('EventReceiver') for i in ignored) else 'it spawns nothing'
    return draw, None


def attach(p, defaults, systems, exporter, compiled_textures, rules=None, warn=None):
    """Each system record of `systems` ({'<package>|<path>': record}) gains `draw` on its emitters (None with `why`
    where the page can't draw one). The emitters are the system's `Emitters` in order, as system_record lists them."""
    for key, record in systems.items():
        if not record:
            continue
        index = p.by_name.get(record.get('path'))
        if not index:
            continue
        try:
            emitters = [r for r in p.refs(p.own(index, 'Emitters')) if r > 0]
        except (FormatError, ValueError, struct.error):
            emitters = []
        for em, e in zip(emitters, record['emitters']):
            e['draw'], e['why'] = None, 'no level of detail left'
            try:
                lods = [r for r in p.refs(p.own(em, 'LODLevels')) if r > 0]
                if lods:
                    e['draw'], e['why'] = emitter_draw(p, defaults, lods[0], exporter, compiled_textures, rules)
            except (FormatError, ValueError, IndexError, KeyError, struct.error, OSError) as error:
                e['draw'], e['why'] = None, 'not read'
                if warn:
                    warn(record.get('path'), 'emitter draw data not read: %s' % error)
            if e['draw'] is not None:
                del e['why']
        record['drawVersion'] = DRAW_VERSION
