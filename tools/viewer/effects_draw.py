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

DRAW_VERSION = 5     # 2: a mesh emitter's own textures, and its blend from the material it is drawn with
                     # 3: a packed texture's one channel as the opacity; distortion-only emitters not drawn
                     # 4: textures told apart by their pixels (texture_traits): the colour from a picture, the shape
                     #    from a mask (`maskFrom`); `opacity` none where the mask alone shapes it
                     # 5: an added particle's grey texture its picture; a picture with an alpha shape no other mask
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
# a texture whose three channels are three pictures (T_Dust_Grainy_3Channel): one channel is the opacity, no colour
PACKED_WORDS = frozenset('CHANNEL CHANNELS PACKED 3CHANNEL'.split())
ALPHA_FORMATS = ('PF_DXT5', 'PF_DXT3', 'PF_A8R8G8B8')
# Still passed to attach() by the exporter and the library: no material's textures are picked by hand (a table of
# them was planned and never filled; review finding 63), so attach() reads nothing from it.
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


COLOUR_WORDS = frozenset('COLOR COLOUR TINT'.split())
NOT_COLOUR = frozenset('SPC SPEC SPECULAR'.split())


def material_colours(p, material):
    """A material's own colour parameters (its vector parameters named for a colour or a tint, not a specular one),
    through its parents, the nearest's value: {name: [r, g, b]}. The night smoke's are all but black (Dark_Color,
    Bright_Color: its plume is dark smoke, lit only at its foot), the fires' run from Outer_Color to Core_Color."""
    out = {}
    for mat in reversed(material_chain(p, material)):
        for c in p.children.get(mat, []):
            if p.cls(c) == 'MaterialExpressionVectorParameter':
                name, value = p.own(c, 'ParameterName'), p.own(c, 'DefaultValue')
                if name is not None and isinstance(value, list) and len(value) >= 3:
                    out[str(name)] = value[:3]
        try:
            for row in p.structs(p.own(mat, 'VectorParameterValues')):
                name = row.get(('ParameterName', 0), {}).get('value')
                value = row.get(('ParameterValue', 0), {}).get('value')
                if name is not None and isinstance(value, list) and len(value) >= 3:
                    out[str(name)] = value[:3]
        except (FormatError, ValueError, IndexError, struct.error, TypeError):
            pass
    return {name: [round(float(v), 4) for v in value] for name, value in out.items()
            if words(name) & COLOUR_WORDS and not words(name) & NOT_COLOUR}


def texture_traits(path):
    """What a particle texture holds, from its pixels (a 64-pixel copy of the PNG the export wrote): dict(grey (no
    colour to speak of: a shape, a gradient, a noise), shape (its alpha channel holds a shape: it varies by a fifth of
    its range or more), packed (pictures in its channels rather than a colour: no blue at all and red and green
    unrelated, as the fire's scrolling noise T_Roiling_Smoke_Scrolling; or a colour that is mostly blue to pink, which
    no smoke, dust or glow of the game is, as the night smoke's T_Roiling_Smoke_SubUV: its red the light from below,
    its green the light from above, its blue the density), redShare (its red channel's mean over its strongest
    channel's: whether the red holds the shape), bright (its mean brightness, 0 to 1)). The fires showed why names
    alone are not enough: their colour picture (GEN_MaterialParents' Flame) has an alpha channel that is nearly empty,
    and their shape is a grey mask (T_Fire_Licks_Large)."""
    import numpy as np
    from PIL import Image
    with Image.open(path) as image:
        image.load()
        rgba = image.convert('RGBA')
    # (colour and alpha shrunk apart: shrinking RGBA weighs the colour by the alpha, and a near-empty alpha loses it)
    rgb = np.asarray(rgba.convert('RGB').resize((64, 64)), dtype=float)
    alpha = np.asarray(rgba.getchannel('A').resize((64, 64)), dtype=float)
    top, low = rgb.max(-1), rgb.min(-1)
    grey = float((top - low).mean() / max(top.mean(), 1.0)) < 0.18
    r, g, b = rgb[..., 0].ravel(), rgb[..., 1].ravel(), rgb[..., 2].ravel()
    related = 1.0
    if r.std() > 4 and g.std() > 4:
        related = float(np.corrcoef(r, g)[0, 1])
    # the colour's hue where it has one, weighed by its brightness and how strong the colour is
    saturation = np.where(top > 8, (top - low) / np.maximum(top, 1.0), 0.0)
    weight = top / 255 * saturation
    hue = (np.degrees(np.arctan2(np.sqrt(3) * (rgb[..., 1] - rgb[..., 2]), 2 * rgb[..., 0] - rgb[..., 1] - rgb[..., 2])) + 360) % 360
    cool = float(weight[(hue >= 190) & (hue < 350)].sum() / max(float(weight.sum()), 1e-9))
    strength = float((saturation * top).sum() / max(float(top.sum()), 1e-9))
    packed = not grey and ((b.max() < 24 and related < 0.4) or (strength >= 0.2 and cool >= 0.6))
    means = rgb.reshape(-1, 3).mean(0)
    # (an alpha channel that is almost empty everywhere, as the Flame's, holds no shape however much it varies)
    shape = alpha.max() - alpha.min() >= 48 and alpha.mean() >= 8
    return dict(grey=grey, shape=bool(shape), packed=bool(packed), redShare=round(float(means[0] / max(float(means.max()), 1.0)), 3),
                bright=round(float(top.mean()) / 255, 3))


def pick_textures(candidates, grid=False, solid=False, added=False):
    """Which of an emitter's textures gives its colour and which its shape: candidates [dict(key, name, parameter,
    grey, shape, packed)] -> dict(picture (key or None), opacity ('alpha' | 'brightness' | 'none': what of the
    picture shapes it besides the mask), mask (key or None), maskFrom ('brightness' | 'alpha' | 'red')). `solid`:
    an opaque or cut-out material (a mesh: its picture is its surface, cut by an alpha shape only); `added`: an
    additive one (its particles show only their brightness).
    - A normal map, a distortion or a reflection is neither.
    - The picture is the first texture with colour (one named for sub-images first where the emitter has a grid).
      Where none has colour, an added particle's picture is its first grey texture (the police lights' round
      T_glowBit); a see-through one's a grey texture only where it holds no shape, there is another texture and no
      packed one (URB_Bar's steam: its grey T_fireyblast01 is not its look; its packed dust is). Else none: the mask
      shapes the particle's own colour.
    - A picture whose alpha holds its shape takes only a texture named as a mask besides (the moths, the lights).
    - Else the mask is the first other texture that can shape: one named as a mask (Mask, Alpha, Gradient), then a
      grey one, one whose alpha holds a shape, a packed one; with no picture, one whose alpha holds a shape, a packed
      one, a grey one (a packed gradient that fills the quad, the police lights' T_Beam_Gradient_Vertical_3Channel,
      shapes nothing round). It shapes by its alpha where that holds the shape, by its red channel where it is packed
      (by its brightness where its red is nearly empty: the blue glare T_Circle_Glare), else by its brightness.
    - A see-through picture shapes by its alpha where that holds a shape (a moth on a white card), else by its
      brightness (the flames' dark gaps). A solid picture is cut by its alpha only."""
    def named(c, which):
        return bool((words(short(c['name'])) | words(c.get('parameter') or '')) & which)
    usable = [c for c in candidates if not named(c, NOT_PICTURE)]
    packed = lambda c: c.get('packed') or named(c, PACKED_WORDS)  # noqa: E731
    colour = [c for c in usable if not c.get('grey') and not packed(c) and not named(c, MASK_WORDS)]
    if grid:
        colour.sort(key=lambda c: 'SUB' not in words(short(c['name'])))
    picture = colour[0] if colour else None
    if picture is None and not solid:
        greys = [c for c in usable if c.get('grey') and not named(c, MASK_WORDS)]
        if added:
            picture = greys[0] if greys else None
        else:
            plain = [c for c in greys if not c.get('shape')]
            picture = plain[0] if plain and len(usable) > 1 and not any(packed(c) for c in usable) else None
    rest = [c for c in usable if c is not picture]
    masks = [c for c in rest if named(c, MASK_WORDS)]
    if picture is not None and picture.get('shape'):
        order = masks
    elif picture is None:
        order = masks + [c for c in rest if c.get('shape')] + [c for c in rest if packed(c)] + [c for c in rest if c.get('grey')]
    else:
        order = masks + [c for c in rest if c.get('grey')] + [c for c in rest if c.get('shape')] + [c for c in rest if packed(c)]
    order = list({id(c): c for c in order}.values())
    if not solid and picture is None and not order and usable:
        order = usable[:1]
    mask = order[0] if order else None
    mask_from = None
    if mask is not None:
        mask_from = ('red' if mask.get('redShare', 1) >= 0.33 else 'brightness') if packed(mask) and not mask.get('grey') else 'alpha' if mask.get('shape') and (
            not mask.get('grey') or named(mask, frozenset(('ALPHA', 'OPACITY', 'OPA')))) else 'brightness'
        if mask.get('shape') and mask.get('grey') and mask_from == 'brightness' and mask.get('bright', 1) < 0.25:
            mask_from = 'alpha'     # (flat dark grey with the shape in its alpha: T_smokey)
    if picture is None:
        opacity = 'none'
    elif solid:
        opacity = 'alpha' if picture.get('shape') else 'none'
    else:
        opacity = 'alpha' if picture.get('shape') else 'brightness'
    return dict(picture=picture['key'] if picture else None, opacity=opacity,
                mask=mask['key'] if mask else None, maskFrom=mask_from)


def sends_events_only(p, lod):
    """Whether an emitter's LOD level is one that sends events and draws nothing: an event generator among its
    modules. Firaxis left the engine's default particle material on these (each fire's last emitter: one particle
    after ten seconds, a lifetime and an event generator); the game shows nothing for them."""
    try:
        modules = [m for m in p.refs(p.own(lod, 'Modules')) if m > 0]
    except (FormatError, ValueError, struct.error):
        return False
    return any(p.cls(m) == P + 'EventGenerator' for m in modules)


def emitter_draw(p, defaults, lod, exporter, compiled_textures):
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
    if kind == 'mesh':
        mesh = p.own(type_data, 'Mesh', 0) or 0
        if mesh <= 0 or p.cls(mesh) != 'StaticMesh':
            return None, 'its mesh is in another package' if mesh < 0 else 'no mesh'
        override = material if material > 0 and defaults.value(type_data, 'bOverrideMaterial', False)[0] else 0
        key, materials, own = exporter.particle_mesh(mesh, override)
        if not key:
            return None, 'its mesh could not be read'
        draw.update(mesh=key, materials=materials)
        # what it is drawn with: the emitter's material where it overrides, else the mesh's own first
        material = override or next((m for m in own if m > 0), 0)
    chain = material_chain(p, material)
    lighting = 'MLM_Phong'
    for mat in reversed(chain):
        draw['blend'] = str(p.own(mat, 'BlendMode', draw['blend']))
        lighting = str(p.own(mat, 'LightingModel', lighting))
        draw['twoSided'] = bool(p.own(mat, 'TwoSided', draw['twoSided']))
    draw['lit'] = lighting != 'MLM_Unlit'
    draw['material'] = p.name(material) if material else None
    if material and 'DISTORTION' in words(short(p.name(material))):
        return None, 'it only bends the light behind it'
    # sprites and meshes alike: the textures the material draws with
    candidates = []
    for tex, name in (sprite_textures(p, material, compiled_textures) if material > 0 else []):
        key = exporter.texture(tex)
        if key:
            info = exporter.textures[key]
            traits = info.get('traits')
            if traits is None:
                try:
                    traits = info['traits'] = texture_traits(exporter.folder / info['url'])
                except (OSError, ValueError, KeyError, AttributeError):
                    traits = info['traits'] = dict(grey=False, shape=info.get('format') in ALPHA_FORMATS, packed=False, bright=0.5)
            candidates.append(dict(key=key, name=p.name(tex), parameter=name, alpha=info.get('format') in ALPHA_FORMATS, **traits))
    grid = draw['subImages'] != [1, 1]
    solid = draw['blend'] in ('BLEND_Opaque', 'BLEND_Masked')
    picked = pick_textures(candidates, grid, solid, added=draw['blend'] == 'BLEND_Additive')
    if not candidates and material <= 0 and kind == 'sprite':
        if material < 0 and p.name(material) == 'EngineMaterials.DefaultParticle' and sends_events_only(p, lod):
            return None, 'it only sends events: nothing is seen'
        return None, 'its material is in another package' if material < 0 else 'no material'
    draw.update(textures=candidates, **picked)
    colours = material_colours(p, material) if material > 0 else {}
    if colours:
        draw['colours'] = colours
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
    where the page can't draw one). The emitters are the system's `Emitters` in order, as system_record lists them.
    `rules` is RULES, which its callers still pass: unused."""
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
                    e['draw'], e['why'] = emitter_draw(p, defaults, lods[0], exporter, compiled_textures)
            except (FormatError, ValueError, IndexError, KeyError, struct.error, OSError) as error:
                e['draw'], e['why'] = None, 'not read'
                if warn:
                    warn(record.get('path'), 'emitter draw data not read: %s' % error)
            if e['draw'] is not None:
                del e['why']
        record['drawVersion'] = DRAW_VERSION
