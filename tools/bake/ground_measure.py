"""Measures one of the game's plain pieces as the donor of a ground look for tools/bake/ground.py (custom geometry plan,
M4a item 2 and M4b item 5; grown from research/evidence/ground-audit.py, which found the install's 148 ground and rock
candidate materials and why the rest were left out).

  measure(package, what, material=None) -> entry    what: an actor (StaticMeshActor, XComLevelActor,
                                                    XComMergedLevelActor, XComOpacityFadeLevelActor) or a mesh path
                                                    placed in the map `package`; material: the one it draws to take
                                                    (left out: the material of its slot with the most area facing up)
  twin(recipe, template=None) -> dict(ok, rows)     a patch built in the recipe at the donor's size and measured again

An entry is dict(recipe, warnings, facts). A ground look is its donor's mesh and material; the recipe is what
ground.build makes a shape from (a look given as a dict, `{'mesh', 'material', 'measure', 'recipe'}`), in world units
(the placing's scale applied: a made piece stands at scale 1, so a donor placed at 4 gives the repeat its placing
draws, M4b item 5):

  material      the material's path
  slot          the donor mesh's slot that draws it, sections its section count: the made mesh has the donor's
                sections in slot order, its faces all in that slot, the others empty, so the copy's materials bind
  uv            top: the texture's planar map on the donor's top in world units (measure_common.planar_map: u = a x
                + b y + c, v = d x + e y + f, offsets modulo 1); a made shape's sides take the same repeats, u along
                each side and v down it (ground.py)
  repeat        the u repeat (world units), as today's looks name theirs
  thickness     a patch's: the donor's own height where it is a slab (MIN_PATCH to MAX_PATCH), else DEFAULT_PATCH
  colours       outside and interior: the colour the placing mostly draws the slot with (its painted colours, else
                its mesh's colour stream, else white; measure_common.main_colour: by area, each varying byte taken
                as 0 or 255): painted materials are made in it (D14)
  lightmap      density: texels a unit as the placing's lightmap has it (measure_common.density), at least
                MIN_DENSITY (a backdrop plane's is coarser than play-area ground's), else DEFAULT_DENSITY; margin 2,
                interiorDensity 1, block 4 (as today's looks)
  measured      what the twin check compares with: the donor's world size, its scale, its top's shape

Facts: material record (blend mode, root, lighting, texture channels), setting, size, scale, top shape, painted,
lightmap, repeats, and leftOut: why the material makes no ground look (D14: translucent and masked overlays draw holes;
decals, unlit, modulated, a third texture channel, distant scenery, no texture lightmap: research/evidence/
ground-audit.py's reasons), or None. Warnings say in plain words what a made piece lacks. Nothing is written."""
import re
import struct

import numpy as np

import measure_common as mc

VERSION = 1
PLAIN = ('StaticMeshActor', 'XComLevelActor', 'XComMergedLevelActor', 'XComOpacityFadeLevelActor')
COPYABLE = ('XComLevelActor', 'StaticMeshActor', 'XComOpacityFadeLevelActor')     # frac_walls.GROUND_CLASSES
UP = 0.7            # a face facing up: outward normal z at least this
LEVEL_UP = 0.98
FLAT_TOP = 4.0
MAIN_LEVEL = 2.0
MOSTLY_FLAT = 0.9
MIN_PATCH, MAX_PATCH, DEFAULT_PATCH = 2.0, 16.0, 8.0
DEFAULT_DENSITY = 0.12
MIN_DENSITY = 0.05     # a backdrop plane's lightmap is coarser than play-area ground's (ground-audit.py's donor score)
PIECEWISE = 0.02
LIGHTMAP = dict(margin=2, interiorDensity=1.0, block=4)
# (research/evidence/ground-audit.py's)
SETTINGS = [
    ('snow/ice', re.compile(r'snow|(?<![a-z])ice(?!cream)|frost|arctic|glacier', re.I)),
    ('sand', re.compile(r'sand(?!wich|bag)|beach|dune', re.I)),
    ('gravel', re.compile(r'gravel|pebble', re.I)),
    ('grass', re.compile(r'grass|lawn|turf|meadow', re.I)),
    ('dirt/mud', re.compile(r'dirt(?!y)|mud|soil|earth|(?<!mid)(?<!back)(?<!bck)(?<!fore)ground|clay|marsh|swamp|'
                            r'bog(?!ey)|silt', re.I)),
    ('rock/cliff', re.compile(r'rock(?!et)|cliff|boulder|stone|crag|mountain|canyon|gorge|quarry', re.I)),
    ('pavement/sidewalk', re.compile(r'sidewalk|pavement|paver|curb|kerb|cobble|plaza|walkway', re.I)),
    ('asphalt/road', re.compile(r'asphalt|asphault|road|street|highway|tarmac|parking|blacktop', re.I)),
    ('concrete', re.compile(r'concrete|cement|foundation', re.I)),
]
SCENERY = re.compile(r'midground|background|bckground|distant|(?<![a-z])dist(?=[A-Z])|skybox|cityscape|'
                     r'BackgroundMountains')
OWN_BLEND = re.compile(r'_BLEND$|Blend$|_VP$|(?<![A-Za-z])VP_', re.I)
PAINT_ROOT = re.compile(r'Vertex_?Paint|Vertex_?Colou?r|VPaint|(?<![A-Za-z])VP_|_VP(?![A-Za-z])|Blend', re.I)
LAYER_SWITCH = re.compile(r'Dual|Blend|Terrain|Layer|Vertex|Paint', re.I)
DIFFUSE_NAME = re.compile(r'dif|diffuse|albedo|colou?r', re.I)
NOT_DIFFUSE = re.compile(r'norm|nrm|_n$|spec|spc|mask|emis|ems|opac|opc|refl|cube|height|bump|noise', re.I)
DIFFUSE_PARAMS = ('Diffuse', 'Diffuse_Base', 'DiffuseMap', 'Diffuse Map', 'Diffuse_BaseA', 'Dif', 'DiffuseTexture')
OVERLAY_ROOT = re.compile(r'Opc|Opacity|Foliage|Patch|Decal|OpqMask|Cutout|Alpha|Grass|Leaf|Leaves', re.I)
BAD_BLEND = ('BLEND_Translucent', 'BLEND_Additive', 'BLEND_Modulate', 'BLEND_SoftMasked', 'BLEND_AlphaComposite',
             'BLEND_DitheredTranslucent')


# ---------------------------------------------------------------------------------------------------- materials
def _compiled(p, mat):
    """The FMaterial record's texture channel count (NumUserTexCoords), or None (ground-audit.py's `compiled`)."""
    try:
        r = p.native(mat)
        for _ in range(r.count()):
            n = r.i32()
            r.take(n if n >= 0 else -2 * n)
        r.take(r.count() * 8)
        r.i32()
        r.take(16)
        uvs = r.u32()
        textures = [p.name(v) for v in r.unpack('%di' % r.count())]
        flags = list(r.unpack('5i'))
    except (ValueError, struct.error):
        return None
    if uvs > 8 or any(f not in (0, 1) for f in flags):
        return None
    return dict(uvs=uvs, textures=textures)


def material_record(p, mat):
    """What a material is (ground-audit.py's material_record, the parts the verdict needs): its chain to its root, the
    root's blend mode, lighting model and two-sidedness, the compiled texture channels, its static switches, its
    diffuse-like layers and whether its root is a vertex-paint or blend material."""
    import materials as viewer_materials
    chain = [mat]
    while chain[-1] > 0 and p.cls(chain[-1]) not in ('Material', 'DecalMaterial') and len(chain) < 12:
        parent = p.own(chain[-1], 'Parent', 0)
        if not parent:
            break
        chain.append(parent)
    root = chain[-1]
    rec = dict(cls=p.cls(mat) if mat > 0 else 'import', root=p.name(root),
               rootClass=p.cls(root) if root > 0 else 'import')
    if root > 0:
        rec['blendMode'] = p.own(root, 'BlendMode', 'BLEND_Opaque')
        rec['lightingModel'] = p.own(root, 'LightingModel', 'MLM_Phong')
        rec['twoSided'] = bool(p.own(root, 'TwoSided', False))
    res = None
    for c in chain:
        if c > 0 and (p.cls(c) in ('Material', 'DecalMaterial') or p.own(c, 'bHasStaticPermutationResource', False)):
            res = _compiled(p, c)
            if res:
                break
    rec['uvs'] = res['uvs'] if res else None
    switches, textures = {}, {}
    if root > 0:
        for e in p.refs(p.own(root, 'Expressions')):
            if e <= 0 or p.own(e, 'ParameterName') is None:
                continue
            if p.cls(e) == 'MaterialExpressionStaticSwitchParameter':
                switches[p.own(e, 'ParameterName')] = bool(p.own(e, 'DefaultValue', False))
            elif p.cls(e).startswith('MaterialExpressionTextureSampleParameter'):
                tex = p.own(e, 'Texture', 0)
                textures[p.own(e, 'ParameterName')] = p.name(tex) if tex else None
    for c in reversed(chain[:-1]):
        if c > 0:
            for st in p.structs(p.own(c, 'TextureParameterValues')):
                key = st.get(('ParameterName', 0), {}).get('value')
                val = st.get(('ParameterValue', 0), {}).get('value')
                if key is not None:
                    textures[key] = p.name(val) if val else None
            try:
                switches.update(viewer_materials.static_switches(p, c))
            except (ValueError, struct.error):
                pass
    rec['switches'] = dict(sorted(switches.items()))
    diffuse = next((textures[k] for k in DIFFUSE_PARAMS if textures.get(k)), None)
    if diffuse is None:
        diffuse = next((v for k, v in sorted(textures.items())
                        if v and (DIFFUSE_NAME.search(k) or DIFFUSE_NAME.search(v.rsplit('.', 1)[-1]))
                        and not NOT_DIFFUSE.search(k) and not NOT_DIFFUSE.search(v.rsplit('.', 1)[-1])), None)
    rec['diffuse'] = diffuse.rsplit('.', 1)[-1] if diffuse else None
    layers = {v for v in (res['textures'] if res else []) if v
              and DIFFUSE_NAME.search(v.rsplit('.', 1)[-1]) and not NOT_DIFFUSE.search(v.rsplit('.', 1)[-1])}
    rec['diffuseLayers'] = len(layers)
    names = [p.name(c) for c in chain]
    rec['paintRoot'] = any(PAINT_ROOT.search(n.rsplit('.', 1)[-1]) or 'Vertex_Paint' in n for n in names[1:]) \
        or bool(PAINT_ROOT.search(rec['root']))
    return rec


def setting_of(name, diffuse=None):
    """The material's setting by its name, then its diffuse texture's (ground-audit.py's settings), or None."""
    short = name.rsplit('.', 1)[-1]
    for text in (short, name, diffuse or ''):
        for setting, rx in SETTINGS:
            if rx.search(text):
                return setting
    return None


def left_out(rec, name, textured=True, meshes=()):
    """Why the material makes no ground look (ground-audit.py's reasons, D14), as words, or []: `textured` whether a
    placing of it has a texture lightmap, `meshes` the meshes it is placed on (distant scenery by their names too)."""
    why = []
    if rec.get('rootClass') == 'DecalMaterial' or rec.get('cls') == 'DecalMaterial':
        why.append('a decal material')
    if rec.get('blendMode') in BAD_BLEND:
        why.append('%s: it draws holes or blends with what is behind it' % rec['blendMode'])
    if rec.get('lightingModel') == 'MLM_Unlit':
        why.append('unlit')
    if rec.get('blendMode') == 'BLEND_Masked' and OVERLAY_ROOT.search(rec.get('root') or ''):
        why.append('masked: a cut-out overlay, which draws holes')
    if (rec.get('uvs') or 0) >= 3:
        why.append('it samples %d texture channels (a made piece has two)' % rec['uvs'])
    if SCENERY.search(name) or any(SCENERY.search(m) for m in meshes):
        why.append('distant scenery')
    if not textured:
        why.append('no texture lightmap seen on it')
    if rec.get('cls') == 'import' or rec.get('error'):
        why.append('its material record is unread')
    return why


def paint_signs(rec, name, painted=None, stream_varies=False):
    """The signs that the material blends layers by painted colours (ground-audit.py's colour signs, for one placing:
    `painted` its painted colours' rule, 'varying n' or a value; `stream_varies` its mesh's colour stream varies)."""
    signs = []
    if rec.get('paintRoot'):
        signs.append('its root is a vertex-paint or blend material (%s)' % rec['root'].rsplit('.', 1)[-1])
    elif OWN_BLEND.search(name.rsplit('.', 1)[-1]):
        signs.append('named for a blend or vertex paint')
    switches = [k for k, v in (rec.get('switches') or {}).items() if v and LAYER_SWITCH.search(k)]
    if switches:
        signs.append('switch %s on' % ', '.join(switches))
    if (rec.get('diffuseLayers') or 0) >= 2 and (str(painted).startswith('varying') or stream_varies):
        signs.append('%d diffuse layers, and colours that vary on its placing' % rec['diffuseLayers'])
    return signs


# ---------------------------------------------------------------------------------------------------- the mesh
def top_of(T, slot):
    """The slot's top (faces facing up): dict(upArea, shape ('flat', 'mostly flat', 'uneven', 'no top'), faces (the
    triangles the texture is measured on: its level ones, else its up ones, else all of the slot's))."""
    sel = T.slot == slot
    up = sel & (T.normal[:, 2] >= UP)
    out = dict(upArea=float(T.area[up].sum()))
    if not up.any():
        out.update(shape='no top', faces=sel)
        return out
    z = T.pos[T.verts(up), 2]
    cz = T.pos[T.tris[up]].mean(1)[:, 2]
    w = T.area[up]
    bins = {}
    for bz, ww in zip(np.round(cz / 0.5), w):
        bins[float(bz)] = bins.get(float(bz), 0.0) + float(ww)
    main = max(sorted(bins), key=lambda k: bins[k]) * 0.5
    share = float(w[np.abs(cz - main) <= MAIN_LEVEL].sum() / max(w.sum(), 1e-9))
    out['shape'] = ('flat' if float(np.ptp(z)) <= FLAT_TOP else 'mostly flat' if share >= MOSTLY_FLAT else 'uneven')
    level = up & (T.normal[:, 2] >= LEVEL_UP)
    out['faces'] = level if level.any() else up
    return out


def _round(v, digits=2):
    return round(float(v), digits) + 0.0


def measure_mesh(m, slot, scale=(1.0, 1.0, 1.0), light=None, colours=None, name='', record=None, lm_channel=1):
    """The entry (the module's words) of the decoded mesh `m` (gen_mesh's form) placed at `scale`, its slot `slot`
    drawing material `name` (its material_record `record`, or None), the placing's lightmap `light` (dict(type, rect,
    painted) from measure_common.component_light) and painted colours `colours` (a list of 4 bytes a vertex, or
    None; `lm_channel` the mesh's lightmap channel)."""
    T = mc.Tris(m, scale, lm_channel)
    if not (T.slot == slot).any():
        raise ValueError('the mesh draws nothing in slot %d' % slot)
    size = [float(v) for v in T.pos.max(0) - T.pos.min(0)]
    top = top_of(T, slot)
    found = mc.planar_map(T, top['faces'], (0, 1))
    warnings = []
    if found is None:
        found = dict(u=[1 / 256.0, 0.0, 0.0], v=[0.0, 1 / 256.0, 0.0], spread=[0.0, 0.0], repeat=[256.0, 256.0],
                     axis=['+x', '+y'])
        warnings.append('its texture has no layout to measure: made at a repeat of 256')
    uv = mc.rounded_map(found)
    if max(found['spread']) > PIECEWISE:
        warnings.append('its texture is laid out piece by piece (no one repeat across it): made with one even repeat')
    if top['shape'] in ('uneven', 'no top'):
        warnings.append('its top isn\'t flat (%s): a made piece is flat-faced in its material' % top['shape'])
    # the colour it draws the slot with: its painted colours, else its mesh's stream, else white
    sel = T.slot == slot
    verts = T.verts(sel)
    weights = T.vertex_areas(sel)[verts]
    painted_rule = (light or {}).get('painted')
    if colours and len(colours) >= len(T.pos):
        colour = mc.main_colour([colours[v] for v in verts], weights)
        values = {bytes(colours[v]) for v in verts}
    elif T.colours:
        colour = mc.main_colour([T.colours[v] for v in verts], weights)
        values = {T.colours[v] for v in verts}
    else:
        colour, values = None, set()
    colour = colour or 'ffffffff'
    stream_varies = bool(T.colours) and len({T.colours[v] for v in verts}) > 1
    signs = paint_signs(record or {}, name, painted_rule, stream_varies)
    painted = bool(signs) or len(values) > 1
    if signs:
        warnings.append('its material blends layers by painted colours (%s): made in its main colour (%s), so it '
                        'shows one layer' % ('; '.join(signs), colour))
    thickness = size[2] if MIN_PATCH <= size[2] <= MAX_PATCH else DEFAULT_PATCH
    rect = (light or {}).get('rect')
    dens = mc.density(rect, T.lightmap_area(), float(T.area.sum()))
    repeat = found['repeat'][0] or found['repeat'][1] or 256.0
    recipe = dict(material=name, slot=int(slot), sections=int(T.sections), uv=dict(top=uv), repeat=_round(repeat, 1),
                  thickness=_round(thickness, 1), colours=dict(outside=colour, interior=colour),
                  lightmap=dict(density=max(MIN_DENSITY, _round(dens, 4)) if dens else DEFAULT_DENSITY, **LIGHTMAP),
                  measured=dict(size=[_round(v, 1) for v in size], scale=[_round(v, 4) for v in scale],
                                shape=top['shape']))
    facts = dict(size=[_round(v, 1) for v in size], scale=[_round(v, 4) for v in scale], shape=top['shape'],
                 thickness=_round(size[2], 1), painted=painted, colour=colour,
                 repeat=[_round(r, 1) if r else None for r in found['repeat']], axis=found['axis'],
                 spread=[_round(s, 3) for s in found['spread']],
                 lightmap=dict(type=(light or {}).get('type'), rect=rect, density=_round(dens, 4) if dens else None))
    return dict(recipe=recipe, warnings=warnings, facts=facts)


def slot_of(p, comp, mesh, material=None):
    """(slot, material export, material name) the placing draws: the slot drawing `material` (a path), or the slot
    with the most area facing up. Materials as the game binds them: the component's Materials, else the section's."""
    import gen_mesh
    m = gen_mesh.read(p, mesh)
    lod = m['lods'][0]
    over = p.refs(p.effective(comp, 'Materials')) if p.effective(comp, 'Materials') else []
    bound = {}
    for s in lod['sections']:
        ref = over[s['slot']] if s['slot'] < len(over) and over[s['slot']] else s['material']
        bound[s['slot']] = ref
    if material is not None:
        for s, ref in sorted(bound.items()):
            if ref and p.name(ref) == material:
                return s, ref, p.name(ref), m
        raise ValueError('%s draws no %s' % (p.name(mesh), material))
    T = mc.Tris(m)
    areas = {s: float(T.area[(T.slot == s) & (T.normal[:, 2] >= UP)].sum()) for s in bound}
    slot = max(sorted(areas), key=lambda s: areas[s])
    ref = bound[slot]
    return slot, ref, p.name(ref) if ref else None, m


def measure(package, what, material=None):
    """The entry of the ground donor `what` (an actor or a mesh path) placed in the map `package`, for its material
    `material` (left out: its top's)."""
    p = package
    actor, comp, mesh = mc.find_placing(p, what, PLAIN, 'StaticMeshComponent')
    if p.cls(mesh) != 'StaticMesh':
        raise ValueError('%s is no plain static mesh' % p.name(mesh))
    slot, ref, name, m = slot_of(p, comp, mesh, material)
    if not name:
        raise ValueError('%s draws no material in slot %d' % (p.name(mesh), slot))
    try:
        record = material_record(p, ref) if ref > 0 else dict(cls='import')
    except (ValueError, struct.error) as err:
        record = dict(cls=p.cls(ref), error=str(err)[:120])
    light = mc.light_of(p, comp)
    scale = mc.scale_of(p, actor, comp)
    entry = measure_mesh(m, slot, scale, light, light.get('colours'), name, record,
                         int(p.effective(mesh, 'LightMapCoordinateIndex', 1) or 1))
    why = left_out(record, name, light.get('type') == 2, (p.name(mesh),))
    if p.cls(actor) not in COPYABLE:
        why.append('its placing is an %s, which the Build doesn\'t copy' % p.cls(actor))
    if why:
        entry['warnings'].insert(0, 'left out of the ground looks: %s' % '; '.join(why))
    entry['facts'].update(mesh=p.name(mesh), actor=p.name(actor).split('.')[-1], cls=p.cls(actor), slot=slot,
                          material=name, setting=setting_of(name, record.get('diffuse')), leftOut=why or None,
                          blendMode=record.get('blendMode'), root=record.get('root'),
                          lighting=record.get('lightingModel'), uvs=record.get('uvs'),
                          twoSided=record.get('twoSided'))
    if record.get('blendMode') == 'BLEND_Masked' and not why:
        entry['warnings'].append('its material is masked (on a general root): drawn only where its opacity mask is on')
    return entry


def twin_shape(recipe):
    """The patch of the donor's size (whole tiles, 1 to ground.MAX_TILES each way) in the piece's frame."""
    import ground
    sx, sy = recipe['measured']['size'][:2]
    nx = min(ground.MAX_TILES, max(1, int(round(sx / ground.TILE))))
    ny = min(ground.MAX_TILES, max(1, int(round(sy / ground.TILE))))
    return dict(shape='patch', x0=0.0, x1=nx * ground.TILE, y0=0.0, y1=ny * ground.TILE)


def twin(recipe, template=None):
    """The twin check: a patch built in `recipe` at the donor's size (twin_shape; on the donor's decoded mesh
    `template` when given) and measured again: dict(ok, rows [dict(key, donor, twin, ok, soft)], built). It compares
    what makes the look: the slot and sections, the texture's map on the top, the colour, the patch's thickness and the
    lightmap's density (within a fifth)."""
    import ground
    shape = twin_shape(recipe)
    shape['look'] = dict(mesh='(twin)', material=recipe.get('material'), measure=VERSION, recipe=recipe)
    out = ground.build(shape, template)
    again = measure_mesh(out['mesh'], recipe['slot'], light=dict(type=2, rect=list(out['lightmapRect'])),
                         name=recipe.get('material') or '')['recipe']
    rows = []

    def row(key, a, b, ok, soft=False):
        rows.append(dict(key=key, donor=a, twin=b, ok=bool(ok), soft=soft))
    row('slot', recipe['slot'], again['slot'], recipe['slot'] == again['slot'])
    row('sections', recipe['sections'], again['sections'], recipe['sections'] == again['sections'])
    row('texture on the top', recipe['uv']['top'], again['uv']['top'], not mc.map_differs(recipe['uv']['top'],
                                                                                           again['uv']['top']))
    row('colour', recipe['colours']['outside'], again['colours']['outside'],
        recipe['colours']['outside'] == again['colours']['outside'])
    row('thickness', recipe['thickness'], _round(again['measured']['size'][2], 1),
        abs(recipe['thickness'] - again['measured']['size'][2]) <= 0.05)
    da, db = recipe['lightmap']['density'], again['lightmap']['density']
    row('lightmap density', da, db, abs(db - da) <= 0.2 * da)
    return dict(ok=all(r['ok'] for r in rows if not r['soft']), rows=rows,
                built=dict((k, v) for k, v in shape.items() if k != 'look'))


def verdict(result):
    """A twin result in a catalogue's words: 'ok', or what differs."""
    if result['ok']:
        return 'ok'
    out = []
    for r in result['rows']:
        if r['ok'] or r['soft']:
            continue
        a, b = r['donor'], r['twin']
        if isinstance(a, list):
            a, b = 'another layout', 'another'
        out.append('%s %s, made %s' % (r['key'], a, b))
    return '; '.join(out)

