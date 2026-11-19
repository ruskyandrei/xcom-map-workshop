"""Read-only audit of the game's ground and rock materials as donors for ground made from numbers
(private/plans/done/custom-geometry-implementation-plan.md, stage M6, item 2).

A made ground shape (a flat patch, a raised block, a ramp) is to be a copy of a donor: one of the game's own plain
(not fracturing) static mesh pieces placed in a map, its StaticMesh replaced by ours on the donor's material, lit
with a texture lightmap of its own. The material must be one the install shows on a plain mesh with a texture
lightmap (so the game ships its shader for that), with no painted colours and no third texture channel. This audit
finds those materials and a donor for each.

Over every base map the install lists (tools/viewer/library.py donors; the streams with --streams), or the maps named
with --maps, it reads each placed plain piece of the persistent level (StaticMeshActor, XComLevelActor,
XComMergedLevelActor, XComOpacityFadeLevelActor) whose StaticMeshComponent draws a StaticMesh at least 96 x 96 across
in the world (its mesh bounds times the actor's and the component's scale). For each such placing and each section
(slot) of its mesh, the material the slot draws with (the component's Materials, else the section's own) is counted.
Each mesh is read once (tools/bake/gen_mesh.py, LOD 0) and measured at each scale it is placed at:

  top          the slot's faces facing up (outward normal z at least 0.7; UE3 winds front faces so that
               cross(c - a, b - a) points out): their area, the z range of their vertices, the share of their area on
               the main level (within 2 of the area's commonest height), and the shape: flat (its top's vertices
               within 4 of each other), mostly flat (90% of its top on the main level: a sidewalk with its kerb),
               uneven, or no top; the mesh's thickness (its z size) and its xy size
  repeat       world units per texture repeat (UV unit) of channel 0 on that top: for every top triangle the gradient
               of u and of v across it, 1 / |gradient| the units a repeat; the area-weighted median of each, the spread
               (10th to 90th percentile) and the world axis u and v run along (+x, -y, ...; oblique when no axis holds
               80% of the area). Faces with a level top only (or every face of the slot when it has no top, as a
               rock's), so it is the repeat a planar mapping u = x / repeat would copy
  colours      the mesh's own colour stream on the slot's vertices: none, one value, or how many (a value is the
               stored bytes B, G, R, A in hex: ffffff00 is white with alpha 0, 0000ff00 red)
  lightmap     per placing, the component's LOD 0 record (tools/upk/audit_lighting.py's layout): a texture lightmap
               (LightMap_2D, type 2), a vertex lightmap (type 1) or none; for a texture one its rectangle in the atlas
               (coordinate scale times the atlas texture's size) and its density: texels a world unit, the square
               root of (the lightmap channel's UV area x the rectangle's texels / the mesh's world area); the mesh's
               LightMapResolution and the component's override; its painted vertex colours (OverrideVertexColors,
               the LOD record's colour stream): none, one value, or how many
  material     the Parent chain to its Material and that Material's BlendMode, TwoSided, LightingModel and usage
               flags; the compiled shader record (FMaterial, read as tools/viewer/materials.py reads it: the record
               of the instance when it has a static permutation, else the Material's): NumUserTexCoords (the number of
               texture channels the shader samples: 3 or more is a third channel) and the textures it samples; the
               texture, scalar and switch parameters down the chain; the diffuse texture and its size; how many
               diffuse layers it samples

What it cannot tell: cooking strips every material expression but the parameters, so whether a shader reads the vertex
colour is judged from signs, not read from the shader: a root named for vertex paint, vertex colour or a blend
(GEN_MaterialParents.Vertex_Paint.*, *_VP, HighwayDamage_VertexColor), a material named for a blend (A-B_BLEND), a
static switch on that mixes layers (BLDG_Enterable's DualDiffuse, ENV_Terrain's Tri_DiffuseBlend and Terrain), half
or more of its placings painted with colours that vary, or two or more diffuse layers with colours that vary on its
placings (the diffuse layers are counted from the compiled record's textures, so roughly). With signs, the colour
verdict is 'one colour' when some placing draws it with a single colour (its painted colours one value, or its
mesh's colour stream one value or none: a made mesh can copy that colour and look like that placing) and 'needs
paint' when none does; without, 'no signs'.
The shader's own UV tiling (TextureCoordinate nodes) is stripped too, so the repeat is the mesh's, which is what the
game draws when the material does not tile its coordinates (the tiling scalars a material keeps, such as TileXY, are
listed). The level designers place planes scaled (the farm's ground planes twice their size), so each material also
lists the repeats its placings draw it at.

Per material named for ground or rock (the materials not so named that are placed on a flat or mostly flat piece get
a short record under flatUnnamed: floors, roofs, rugs, UFO decks; the rest are counted):
its setting (asphalt road, pavement, concrete, grass, dirt and mud, gravel, sand, snow, rock, by its name), its
placings and maps, the actor classes, its meshes, the lightmap kinds of its placings and their densities, the repeats
it is placed at, its colour signs and verdict, its material record, the verdict (a candidate, or why not: a decal,
translucent, unlit, masked on a root made for cut-outs (opacity-masked props, foliage, patches, decals), a third
texture channel, needs paint, distant scenery, no texture lightmap seen), cautions (masked on a general root such as
the rocks' PROP_Objects, a second texture channel sampled, one colour only, two-sided, tiling scalars, no flat
placing, placed only in Slingshot's maps) and a donor: the placing that is the best copy (a texture lightmap, a flat
top, one section, one colour, unpainted, unscaled, the most placed mesh), with its actor's and component's saved
properties. Every donor map is cooked by Firaxis (licensee 64), so every material here is the base game's; maps
named DLC1_ are Slingshot's (a DLC), and the record says whether a material is placed in any other map. Prints the
summary and the candidates; --output writes the JSON (about 0.8 MB, a minute and a half for the 97 base maps). No
game file is written.

  python -B research/evidence/ground-audit.py [--maps CsmallScout_Farm URB_Bar] [--streams] [--output <file.json>]
         [--verbose]
"""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
import struct
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for folder in ('viewer', 'upk', 'lab', 'bake'):
    sys.path.insert(0, str(ROOT / 'tools' / folder))
import audit_lighting  # noqa: E402
import gen_mesh  # noqa: E402
import materials as viewer_materials  # noqa: E402
from package import Package  # noqa: E402

PLAIN = ('StaticMeshActor', 'XComLevelActor', 'XComMergedLevelActor', 'XComOpacityFadeLevelActor')
MIN_SIDE = 96.0     # a placing at least this across in x and y
UP = 0.7            # a face facing up: outward normal z at least this
LEVEL_UP = 0.98     # a level face
FLAT_TOP = 4.0      # a flat top: its up faces' vertices within this height
MAIN_LEVEL = 2.0    # the main level: up area within this of the commonest height
MOSTLY_FLAT = 0.9   # mostly flat: this share of the up area on the main level (a sidewalk with its kerb)
AXIS_SHARE = 0.8    # u or v runs along a world axis when this share of the area agrees
# the settings, by name: the material's own name first, then its full path, then its diffuse texture's
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
# distant scenery: the midground buildings, background mountains and city plates (drawn far off, at a lightmap
# density no ground has)
SCENERY = re.compile(r'midground|background|bckground|distant|(?<![a-z])dist(?=[A-Z])|skybox|cityscape|'
                     r'BackgroundMountains')
OWN_BLEND = re.compile(r'_BLEND$|Blend$|_VP$|(?<![A-Za-z])VP_', re.I)    # the material's own name (A-B_BLEND)
PAINT_ROOT = re.compile(r'Vertex_?Paint|Vertex_?Colou?r|VPaint|(?<![A-Za-z])VP_|_VP(?![A-Za-z])|Blend', re.I)
# static switches that turn on a second diffuse or a terrain blend (BLDG_Enterable's DualDiffuse, ENV_Terrain's
# Tri_DiffuseBlend and Terrain): layers mixed by something per vertex or per place
LAYER_SWITCH = re.compile(r'Dual|Blend|Terrain|Layer|Vertex|Paint', re.I)
DIFFUSE_NAME = re.compile(r'dif|diffuse|albedo|colou?r', re.I)
NOT_DIFFUSE = re.compile(r'norm|nrm|_n$|spec|spc|mask|emis|ems|opac|opc|refl|cube|height|bump|noise', re.I)
DIFFUSE_PARAMS = ('Diffuse', 'Diffuse_Base', 'DiffuseMap', 'Diffuse Map', 'Diffuse_BaseA', 'Dif', 'DiffuseTexture')
TILING = re.compile(r'til|scale|repeat|uv', re.I)
# a masked material on a root made for cut-outs (opacity-masked props, foliage, patches, decals): an overlay with holes,
# not a surface; masked materials on general roots (PROP_Objects: the rocks) are a caution only
OVERLAY_ROOT = re.compile(r'Opc|Opacity|Foliage|Patch|Decal|OpqMask|Cutout|Alpha|Grass|Leaf|Leaves', re.I)
BAD_BLEND = ('BLEND_Translucent', 'BLEND_Additive', 'BLEND_Modulate', 'BLEND_SoftMasked', 'BLEND_AlphaComposite',
             'BLEND_DitheredTranslucent')
SKIP_PROPS = {'Location', 'Rotation', 'StaticMesh', 'Materials', 'LightEnvironment', 'Components', 'IrrelevantLights',
              'CollisionComponent', 'StaticMeshComponent', 'ReplacementPrimitive', 'ShadowParent', 'LightingGuid',
              'DrawScale3D', 'DrawScale', 'Tag', 'Name', 'ObjectArchetype', 'Layer', 'Group', 'VisibilityId',
              'XComFloorComponent', 'BrushComponent', 'CachedMaxDrawDistance', 'LightmassSettings', 'Translation'}


# ---------------------------------------------------------------------------------------------------- meshes
class Mesh:
    """A StaticMesh's LOD 0 as arrays, in its own frame."""

    def __init__(self, p, index):
        m = gen_mesh.read(p, index)
        lod = m['lods'][0]
        self.name = p.name(index)
        self.pos = np.array(lod['positions'], float).reshape(-1, 3)
        nv = len(self.pos)
        self.channels = lod['texcoords']
        self.lm_channel = p.effective(index, 'LightMapCoordinateIndex', 1)
        self.lm_resolution = p.effective(index, 'LightMapResolution', None)
        self.uv0 = (np.array([v[2][0] for v in lod['vertices']], float) if self.channels else np.zeros((nv, 2)))
        self.uvlm = (np.array([v[2][self.lm_channel] for v in lod['vertices']], float)
                     if 0 <= self.lm_channel < self.channels else None)
        cols = lod['colours'] or []
        self.colours = np.frombuffer(b''.join(cols[:nv]), np.uint8).reshape(-1, 4) if len(cols) >= nv and nv else None
        idx = np.array(lod['indices'][1], np.int64).reshape(-1, 3)
        self.tris = idx
        self.slot = np.full(len(idx), -1)
        self.section_material = {}
        for s in lod['sections']:
            t0 = s['first'] // 3
            self.slot[t0:t0 + s['triangles']] = s['slot']
            self.section_material[s['slot']] = p.name(s['material']) if s['material'] else None
        self.slots = sorted(self.section_material)
        self.bounds = m['bounds']
        self._scaled = {}
        self._rules = {}

    def colour_rule(self, slot):
        if slot in self._rules:
            return self._rules[slot]
        rule = 'none'
        if self.colours is not None:
            verts = np.unique(self.tris[self.slot == slot])
            if len(verts):
                values = {bytes(c) for c in self.colours[verts]}
                rule = next(iter(values)).hex() if len(values) == 1 else 'varying %d' % len(values)
        self._rules[slot] = rule
        return rule

    def at(self, scale):
        """The measures at a scale (x, y, z factors): dict(size, thickness, area, lmArea, slots {slot: top dict})."""
        key = tuple(round(v, 4) for v in scale)
        if key in self._scaled:
            return self._scaled[key]
        pos = self.pos * np.array(key)
        a, b, c = pos[self.tris[:, 0]], pos[self.tris[:, 1]], pos[self.tris[:, 2]]
        cross = np.cross(c - a, b - a)
        length = np.linalg.norm(cross, axis=1)
        area = length / 2
        normal = cross / np.maximum(length, 1e-12)[:, None]
        # a mirroring scale turns the winding over
        if np.prod(np.sign(key)) < 0:
            normal = -normal
        out = dict(size=[round(float(np.ptp(pos[:, k])), 1) for k in range(3)] if len(pos) else [0, 0, 0],
                   area=float(area.sum()), slots={})
        out['thickness'] = out['size'][2]
        if self.uvlm is not None and len(self.tris):
            t = self.uvlm[self.tris]
            uva = 0.5 * np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1])
                               - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1]))
            out['lmArea'] = float(uva.sum())
        for slot in self.slots:
            out['slots'][slot] = self._top(pos, normal, area, slot)
        self._scaled[key] = out
        return out

    def _top(self, pos, normal, area, slot):
        sel = self.slot == slot
        up = sel & (normal[:, 2] >= UP)
        rec = dict(triangles=int(sel.sum()), area=round(float(area[sel].sum())), upArea=round(float(area[up].sum())))
        total_up = float(area[self.slot >= 0][normal[self.slot >= 0, 2] >= UP].sum()) if len(area) else 0.0
        rec['shareOfTop'] = round(float(area[up].sum()) / total_up, 3) if total_up > 0 else 0.0
        if up.any():
            verts = np.unique(self.tris[up])
            z = pos[verts, 2]
            rec['topZ'] = [round(float(z.min()), 2), round(float(z.max()), 2)]
            rec['topZRange'] = round(float(np.ptp(z)), 2)
            cz = pos[self.tris[up]].mean(1)[:, 2]
            w = area[up]
            bins = np.round(cz / 0.5)
            heights = Counter()
            for bz, ww in zip(bins, w):
                heights[bz] += ww
            main = max(heights, key=heights.get) * 0.5
            rec['mainLevel'] = round(float(main), 2)
            rec['mainLevelShare'] = round(float(w[np.abs(cz - main) <= MAIN_LEVEL].sum() / max(w.sum(), 1e-9)), 3)
            rec['level'] = round(float(area[up & (normal[:, 2] >= LEVEL_UP)].sum() / max(w.sum(), 1e-9)), 3)
            rec['flatTop'] = rec['topZRange'] <= FLAT_TOP
            rec['shape'] = ('flat' if rec['flatTop'] else 'mostly flat' if rec['mainLevelShare'] >= MOSTLY_FLAT
                            else 'uneven')
            faces = up & (normal[:, 2] >= LEVEL_UP)
            if not faces.any():
                faces = up
        else:
            rec['flatTop'] = False
            rec['shape'] = 'no top'
            faces = sel
        rec['repeat'] = repeat(pos, self.uv0, self.tris[faces], area[faces]) if faces.any() else None
        return rec


def repeat(pos, uv, tris, area):
    """World units per UV unit along u and v over triangles `tris` (area-weighted median of 1 / |gradient| each),
    their spread, and the world axis each runs along."""
    p0, p1, p2 = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    t0, t1, t2 = uv[tris[:, 0]], uv[tris[:, 1]], uv[tris[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    a11, a22, a12 = (e1 * e1).sum(1), (e2 * e2).sum(1), (e1 * e2).sum(1)
    det = a11 * a22 - a12 * a12
    ok = det > 1e-9
    out = {}
    for c, name in ((0, 'u'), (1, 'v')):
        d1, d2 = t1[:, c] - t0[:, c], t2[:, c] - t0[:, c]
        # the gradient in the triangle's plane: g = x e1 + y e2 with g . e1 = d1 and g . e2 = d2
        x = (d1 * a22 - d2 * a12) / np.where(ok, det, 1)
        y = (d2 * a11 - d1 * a12) / np.where(ok, det, 1)
        g = x[:, None] * e1 + y[:, None] * e2
        gl = np.linalg.norm(g, axis=1)
        live = ok & (gl > 1e-9)
        if not live.any():
            out[name] = None
            continue
        rep, w = 1.0 / gl[live], area[live]
        order = np.argsort(rep)
        cw = np.cumsum(w[order]) / w.sum()
        pick = lambda q: float(rep[order][min(np.searchsorted(cw, q), len(order) - 1)])  # noqa: E731
        gd = g[live] / gl[live][:, None]
        axes = Counter()
        for vec, ww in zip(gd, w):
            k = int(np.argmax(np.abs(vec)))
            axes[('+' if vec[k] > 0 else '-') + 'xyz'[k] if abs(vec[k]) >= 0.99 else 'oblique'] += ww
        axis, share = axes.most_common(1)[0]
        share /= w.sum()
        out[name] = dict(repeat=round(pick(0.5), 1), spread=[round(pick(0.1), 1), round(pick(0.9), 1)],
                         axis=axis if share >= AXIS_SHARE else 'oblique', axisShare=round(float(share), 3))
    return out


# ---------------------------------------------------------------------------------------------------- components
def component_lighting(p, comp):
    """LOD 0 of the component's lighting record: dict(type (0 none, 1 vertex, 2 texture, None no LOD record), rect,
    painted (the override vertex colours: None, a value, or 'varying n'), shadowMaps)."""
    r = p.native(comp)
    if not r.count():
        return dict(type=None)
    shadow = audit_lighting.refs(r, p)
    audit_lighting.refs(r, p)
    lm = audit_lighting.lightmap(r, p)
    out = dict(type=lm['type'], shadowMaps=len(shadow))
    if lm['type'] == 2:
        tex = lm['slots'][0]['index']
        w, h = (p.own(tex, 'SizeX'), p.own(tex, 'SizeY')) if tex > 0 else (None, None)
        if w and h:
            out['atlas'] = [w, h]
            out['rect'] = [round(lm['coordinateScale'][0] * w, 2), round(lm['coordinateScale'][1] * h, 2)]
    flag = r.take(1)[0]
    painted = None
    if flag:
        stride, count = r.unpack('2I')
        if count:
            _, n, raw = r.array_bytes()
            values = {raw[4 * k:4 * k + 4] for k in range(n)}
            painted = bytes(next(iter(values))).hex() if len(values) == 1 else 'varying %d' % len(values)
        else:
            painted = 'empty'
    out['painted'] = painted
    return out


def saved_props(p, index):
    """{property: value} of an export's own saved tagged properties (simple values; others '(saved)')."""
    out = {}
    for (k, slot), v in p.properties(index)[0].items():
        if slot or k in SKIP_PROPS:
            continue
        val = v['value']
        if v['kind'] in ('BoolProperty', 'NameProperty', 'IntProperty') or (
                v['kind'] == 'ByteProperty' and not isinstance(val, bytes)):
            out[k] = val
        elif v['kind'] == 'FloatProperty':
            out[k] = round(val, 3)
        elif v['kind'] == 'ObjectProperty':
            out[k] = (p.name(val).rsplit('.', 1)[-1] if val < 0 else p.cls(val)) if val else None
        elif isinstance(val, list):
            out[k] = [round(x, 3) for x in val]
        else:
            out[k] = '(saved)'
    return out


def scale_of(p, actor, comp):
    a = [v * p.effective(actor, 'DrawScale', 1) for v in p.effective(actor, 'DrawScale3D', [1, 1, 1])]
    c = [v * p.effective(comp, 'Scale', 1) for v in p.effective(comp, 'Scale3D', [1, 1, 1])]
    return [x * y for x, y in zip(a, c)]


# ---------------------------------------------------------------------------------------------------- materials
def compiled(p, mat):
    """The FMaterial record at the start of a Material's (or a static-permutation instance's) native data: uvs
    (NumUserTexCoords), textures (the uniform expression textures), flags; None when it doesn't read."""
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
    return dict(uvs=uvs, textures=textures, flags=flags)


def param_values(p, index, key, value_key='ParameterValue'):
    out = {}
    for st in p.structs(p.own(index, key)):
        name = st.get(('ParameterName', 0), {}).get('value')
        val = st.get((value_key, 0), {}).get('value')
        if name is not None:
            out[name] = val
    return out


def material_record(p, mat):
    """What a material is: its chain, root, root settings, compiled record, parameters, diffuse texture."""
    chain = [mat]
    while chain[-1] > 0 and p.cls(chain[-1]) not in ('Material', 'DecalMaterial') and len(chain) < 12:
        parent = p.own(chain[-1], 'Parent', 0)
        if not parent:
            break
        chain.append(parent)
    root = chain[-1]
    rec = dict(cls=p.cls(mat) if mat > 0 else 'import', chain=[p.name(c) for c in chain],
               root=p.name(root), rootClass=p.cls(root) if root > 0 else 'import')
    if root > 0:
        rec['blendMode'] = p.own(root, 'BlendMode', 'BLEND_Opaque')
        rec['lightingModel'] = p.own(root, 'LightingModel', 'MLM_Phong')
        rec['twoSided'] = bool(p.own(root, 'TwoSided', False))
        rec['usage'] = sorted(k for (k, s), v in p.properties(root)[0].items()
                              if k.startswith('bUsedWith') and v['value'])
    # the compiled record: the nearest instance with a static permutation, else the root's
    res = None
    for c in chain:
        if c > 0 and (p.cls(c) in ('Material', 'DecalMaterial') or p.own(c, 'bHasStaticPermutationResource', False)):
            res = compiled(p, c)
            if res:
                rec['compiledFrom'] = p.name(c)
                break
    rec['uvs'] = res['uvs'] if res else None
    rec['sampled'] = [t.rsplit('.', 1)[-1] for t in res['textures']] if res else None
    # parameters, the root's defaults overridden down the chain
    textures, scalars, vectors, switches = {}, {}, {}, {}
    if root > 0:
        for e in p.refs(p.own(root, 'Expressions')):
            if e <= 0:
                continue
            cls, name = p.cls(e), p.own(e, 'ParameterName')
            if name is None:
                continue
            if cls.startswith('MaterialExpressionTextureSampleParameter'):
                t = p.own(e, 'Texture', 0)
                textures[name] = p.name(t) if t else None
            elif cls == 'MaterialExpressionScalarParameter':
                scalars[name] = p.own(e, 'DefaultValue', 0.0)
            elif cls == 'MaterialExpressionVectorParameter':
                vectors[name] = p.own(e, 'DefaultValue')
            elif cls == 'MaterialExpressionStaticSwitchParameter':
                switches[name] = bool(p.own(e, 'DefaultValue', False))
    for c in reversed(chain[:-1]):
        if c <= 0:
            continue
        for k, v in param_values(p, c, 'TextureParameterValues').items():
            textures[k] = p.name(v) if v else None
        scalars.update(param_values(p, c, 'ScalarParameterValues'))
        vectors.update(param_values(p, c, 'VectorParameterValues'))
        try:
            switches.update(viewer_materials.static_switches(p, c))
        except (ValueError, struct.error):
            pass
    rec['textures'] = {k: (v.rsplit('.', 1)[-1] if v else None) for k, v in sorted(textures.items())}
    rec['scalars'] = {k: round(v, 4) for k, v in sorted(scalars.items()) if isinstance(v, float)}
    rec['tiling'] = {k: v for k, v in rec['scalars'].items() if TILING.search(k)}
    rec['switches'] = dict(sorted(switches.items()))
    diffuse = next((textures[k] for k in DIFFUSE_PARAMS if textures.get(k)), None)
    if diffuse is None:
        diffuse = next((v for k, v in sorted(textures.items())
                        if v and (DIFFUSE_NAME.search(k) or DIFFUSE_NAME.search(v.rsplit('.', 1)[-1]))
                        and not NOT_DIFFUSE.search(k) and not NOT_DIFFUSE.search(v.rsplit('.', 1)[-1])), None)
    rec['diffuse'] = diffuse.rsplit('.', 1)[-1] if diffuse else None
    t = p.by_name.get(diffuse) if diffuse else None
    rec['diffuseSize'] = [p.own(t, 'SizeX'), p.own(t, 'SizeY')] if t else None
    layers = {v for v in (res['textures'] if res else textures.values()) if v
              and DIFFUSE_NAME.search(v.rsplit('.', 1)[-1]) and not NOT_DIFFUSE.search(v.rsplit('.', 1)[-1])}
    rec['diffuseLayers'] = len(layers)
    rec['paintRoot'] = any(PAINT_ROOT.search(n.rsplit('.', 1)[-1]) or 'Vertex_Paint' in n for n in rec['chain'][1:]) \
        or bool(PAINT_ROOT.search(rec['root']))
    return rec


def setting_of(name, diffuse):
    short = name.rsplit('.', 1)[-1]
    for text in (short, name, diffuse or ''):
        for setting, rx in SETTINGS:
            if rx.search(text):
                return setting
    return None


# ---------------------------------------------------------------------------------------------------- the audit
class Audit:
    def __init__(self):
        self.meshes = {}            # mesh name -> Mesh
        self.mesh_errors = {}
        self.materials = {}         # material name -> record
        self.placings = defaultdict(list)       # material name -> [placing dict]
        self.classes = Counter()    # actor classes of the plain pieces read
        self.licensee = Counter()
        self.maps_read = []

    def mesh(self, p, index):
        name = p.name(index)
        if name not in self.meshes and name not in self.mesh_errors:
            try:
                self.meshes[name] = Mesh(p, index)
            except (ValueError, struct.error, IndexError) as err:
                self.mesh_errors[name] = '%s: %s' % (type(err).__name__, err)
        return self.meshes.get(name)

    def run_map(self, name, path, verbose=False):
        t0 = time.time()
        p = Package(path)
        self.licensee[p.header['lic']] += 1
        self.maps_read.append(name)
        level = p.by_name.get('TheWorld.PersistentLevel')
        here = []
        for i in range(1, len(p.exports) + 1):
            if p.exports[i - 1]['outer'] != level or p.cls(i) not in PLAIN:
                continue
            for comp in p.children.get(i, []):
                if p.cls(comp) != 'StaticMeshComponent':
                    continue
                mi = p.effective(comp, 'StaticMesh', 0)
                if not mi or mi < 0 or p.cls(mi) != 'StaticMesh':
                    continue
                scale = scale_of(p, i, comp)
                b = struct.unpack_from('<7f', p.data, p.properties(mi)[1])
                if min(abs(2 * b[3] * scale[0]), abs(2 * b[4] * scale[1])) < MIN_SIDE:
                    continue
                m = self.mesh(p, mi)
                if m is None:
                    continue
                self.classes[p.cls(i)] += 1
                try:
                    light = component_lighting(p, comp)
                except (ValueError, struct.error) as err:
                    light = dict(type='unread', error=str(err)[:80])
                overrides = p.refs(p.effective(comp, 'Materials')) if p.effective(comp, 'Materials') else []
                measured = m.at(scale)
                if light.get('rect') and measured.get('lmArea') and measured['area'] > 0:
                    light['density'] = round(math.sqrt(measured['lmArea'] * light['rect'][0] * light['rect'][1]
                                                       / measured['area']), 4)
                for slot in m.slots:
                    ref = overrides[slot] if slot < len(overrides) and overrides[slot] else 0
                    mat_name = p.name(ref) if ref else m.section_material.get(slot)
                    if not mat_name:
                        continue
                    if mat_name not in self.materials:
                        mat = ref or p.by_name.get(mat_name, 0)
                        try:
                            self.materials[mat_name] = material_record(p, mat) if mat > 0 else dict(cls='import')
                        except (ValueError, struct.error) as err:
                            self.materials[mat_name] = dict(cls=p.cls(mat), error=str(err)[:120])
                    row = dict(map=name, actor=p.name(i).split('.')[-1], cls=p.cls(i), mesh=m.name, slot=slot,
                               sections=len(m.slots), boundBy='component' if ref else 'mesh',
                               scale=[round(v, 4) for v in scale], light=light,
                               componentMaterials=[p.name(r).rsplit('.', 1)[-1] if r else None for r in overrides])
                    self.placings[mat_name].append(row)
                    here.append((row, i, comp))
        # the saved properties of the actor and the component, read while the package is open (the donor's go into
        # the record)
        props = {}
        for row, i, comp in here:
            if i not in props:
                props[i] = dict(actor=saved_props(p, i), component=saved_props(p, comp))
            row['props'] = props[i]
        if verbose:
            print('%-28s %5.1fs  placings %d, meshes so far %d, materials %d' % (
                name, time.time() - t0, len(here), len(self.meshes), len(self.materials)), flush=True)


def one_colour(row, meshes):
    """The one colour a placing draws its slot with (its painted colours' one value, else its mesh's colour stream's
    one value, 'none' for neither: the game's default white), or None when its colours vary."""
    painted = row['light'].get('painted')
    if painted not in (None, 'empty'):
        return None if str(painted).startswith('varying') else painted
    rule = meshes[row['mesh']].colour_rule(row['slot'])
    return None if rule.startswith('varying') else rule


def colour_signs(name, rec, rows, meshes):
    """The signs that a material reads vertex colours, and the verdict: 'no signs', 'one colour' (signs, but the game
    draws it with one colour on some placings: a made mesh can copy that colour) or 'needs paint' (signs, and every
    placing's colours vary)."""
    painted = [r for r in rows if r['light'].get('painted') not in (None, 'empty')]
    varying = [r for r in painted if str(r['light']['painted']).startswith('varying')]
    streams = Counter(meshes[r['mesh']].colour_rule(r['slot']) for r in rows)
    stream_varying = sum(v for k, v in streams.items() if k.startswith('varying'))
    plain = Counter(c for c in (one_colour(r, meshes) for r in rows) if c is not None)
    out = dict(placings=len(rows), painted=len(painted), paintedVarying=len(varying),
               meshStreams=dict(Counter({('varying' if k.startswith('varying') else k): v
                                         for k, v in streams.items()}).most_common(3)),
               meshStreamVarying=stream_varying, oneColourPlacings=sum(plain.values()),
               oneColours=dict(plain.most_common(3)), paintRoot=rec.get('paintRoot'),
               diffuseLayers=rec.get('diffuseLayers'))
    signs = []
    if rec.get('paintRoot'):
        signs.append('its root is a vertex-paint or blend material (%s)' % rec['root'].rsplit('.', 1)[-1])
    elif OWN_BLEND.search(name.rsplit('.', 1)[-1]):
        signs.append('named for a blend or vertex paint')
    switches = [k for k, v in (rec.get('switches') or {}).items() if v and LAYER_SWITCH.search(k)]
    if switches:
        signs.append('switch %s on' % ', '.join(switches))
    if len(varying) >= max(1, 0.5 * len(rows)):
        signs.append('%d of %d placings painted with varying colours' % (len(varying), len(rows)))
    if (rec.get('diffuseLayers') or 0) >= 2 and (varying or stream_varying):
        signs.append('%d diffuse layers, and colours that vary on its placings' % rec['diffuseLayers'])
    out['signs'] = signs
    out['verdict'] = 'no signs' if not signs else 'one colour' if plain else 'needs paint'
    out['needsPaint'] = out['verdict'] == 'needs paint'
    return out


def donor_score(row, mrec, meshes):
    """How good a copy a placing is: a texture lightmap, a flat top, one section, one colour, unpainted, unscaled, a
    plain class, a shallow piece, a lightmap at a play-area density (not a boundary plane's), a wide top."""
    top = mrec['slots'][row['slot']]
    s = 0.0
    s += 8 if row['light'].get('type') == 2 else 0
    s += {'flat': 5, 'mostly flat': 3.5}.get(top.get('shape'), 2 * (top.get('mainLevelShare') or 0))
    s += 2 if row['sections'] == 1 else 0
    s += 3 if one_colour(row, meshes) is not None else 0
    s += 1 if row['light'].get('painted') in (None, 'empty') else 0
    s += 1 if all(abs(v - 1) < 1e-3 for v in row['scale']) else 0
    s += 1 if row['cls'] in ('XComLevelActor', 'StaticMeshActor') else 0
    s -= 2 if mrec['thickness'] > 200 else 0
    s += 1 if (row['light'].get('density') or 0) >= 0.05 else 0
    s += min(1.0, top.get('upArea', 0) / (384.0 * 384.0))
    return s


def material_summary(name, rec, rows, audit):
    meshes = audit.meshes
    by_mesh = Counter(r['mesh'] for r in rows)
    light = Counter({2: 'texture', 1: 'vertex', 0: 'none', None: 'no LOD record'}.get(r['light'].get('type'), 'unread')
                    for r in rows)
    densities = sorted(r['light']['density'] for r in rows if r['light'].get('density'))
    maps = Counter(r['map'] for r in rows)
    colours = colour_signs(name, rec, rows, meshes)
    flat_rows = []
    repeats = Counter()         # the repeats its placings draw it at (planes are placed scaled: the farm's twice)
    for r in rows:
        mrec = meshes[r['mesh']].at(r['scale'])
        top = mrec['slots'][r['slot']]
        if top.get('shape') in ('flat', 'mostly flat') and min(mrec['size'][:2]) >= MIN_SIDE:
            flat_rows.append(r)
        rp = top.get('repeat') or {}
        if rp.get('u') and rp.get('v'):
            repeats['%g x %g' % (round(rp['u']['repeat']), round(rp['v']['repeat']))] += 1
    setting = setting_of(name, rec.get('diffuse'))
    scenery = bool(SCENERY.search(name) or any(SCENERY.search(m) for m in by_mesh))
    out = dict(material=name, setting=setting, cls=rec.get('cls'), root=rec.get('root'), chain=rec.get('chain'),
               blendMode=rec.get('blendMode'), lightingModel=rec.get('lightingModel'), twoSided=rec.get('twoSided'),
               usage=rec.get('usage'), uvs=rec.get('uvs'), compiledFrom=rec.get('compiledFrom'),
               sampled=rec.get('sampled'), textures=rec.get('textures'), diffuse=rec.get('diffuse'),
               diffuseSize=rec.get('diffuseSize'), tiling=rec.get('tiling'), switches=rec.get('switches'),
               placings=len(rows), maps=len(maps), mapNames=sorted(maps)[:8],
               onlyInSlingshot=all(m.startswith('DLC1_') for m in maps),
               actorClasses=dict(Counter(r['cls'] for r in rows).most_common()),
               lightmaps=dict(light.most_common()),
               lightmapDensity=dict(median=round(float(np.median(densities)), 4), min=densities[0],
                                    max=densities[-1]) if densities else None,
               flatTopPlacings=len(flat_rows), repeatsPlaced=dict(repeats.most_common(4)), scenery=scenery,
               colours=colours)
    if rec.get('error'):
        out['error'] = rec['error']
    mesh_rows = []
    for mesh, count in by_mesh.most_common(3):
        r0 = next(r for r in rows if r['mesh'] == mesh)
        m = meshes[mesh]
        mrec = m.at(r0['scale'])
        top = mrec['slots'][r0['slot']]
        mesh_rows.append(dict(mesh=mesh, placings=count, slot=r0['slot'], sections=len(m.slots), scale=r0['scale'],
                              size=mrec['size'], thickness=mrec['thickness'], uvChannels=m.channels,
                              lightmapChannel=m.lm_channel, lightMapResolution=m.lm_resolution,
                              colourStream=m.colour_rule(r0['slot']),
                              top={k: top.get(k) for k in ('upArea', 'shareOfTop', 'topZRange', 'mainLevelShare',
                                                           'level', 'shape')},
                              repeat=repeat_words(top.get('repeat'))))
    out['meshes'] = mesh_rows
    # the donor: the best placing
    best = max(rows, key=lambda r: (donor_score(r, meshes[r['mesh']].at(r['scale']), meshes), by_mesh[r['mesh']]))
    m = meshes[best['mesh']]
    mrec = m.at(best['scale'])
    top = mrec['slots'][best['slot']]
    out['donor'] = dict(map=best['map'], actor=best['actor'], cls=best['cls'], mesh=best['mesh'], slot=best['slot'],
                        sections=len(m.slots), componentMaterials=best['componentMaterials'],
                        boundBy=best['boundBy'], scale=best['scale'], size=mrec['size'], thickness=mrec['thickness'],
                        shape=top.get('shape'), topZRange=top.get('topZRange'),
                        mainLevelShare=top.get('mainLevelShare'), level=top.get('level'), repeat=top.get('repeat'),
                        lightmap={k: v for k, v in best['light'].items() if k != 'error'},
                        lightMapResolution=m.lm_resolution, uvChannels=m.channels, lightmapChannel=m.lm_channel,
                        colourStream=m.colour_rule(best['slot']), oneColour=one_colour(best, meshes),
                        props=best['props'])
    rep = top.get('repeat') or {}
    out['repeat'] = [rep[k]['repeat'] if rep.get(k) else None for k in ('u', 'v')]
    # the verdict
    why = []
    if rec.get('rootClass') == 'DecalMaterial' or rec.get('cls') == 'DecalMaterial':
        why.append('a decal material')
    if rec.get('blendMode') in BAD_BLEND:
        why.append('%s (not opaque)' % rec['blendMode'])
    if rec.get('lightingModel') == 'MLM_Unlit':
        why.append('unlit')
    masked = rec.get('blendMode') == 'BLEND_Masked'
    if masked and OVERLAY_ROOT.search(rec.get('root') or ''):
        why.append('masked: a cut-out overlay')
    if (rec.get('uvs') or 0) >= 3:
        why.append('samples %d texture channels (a third channel)' % rec['uvs'])
    if colours['needsPaint']:
        why.append('needs painted colours')
    if scenery:
        why.append('distant scenery')
    if not light.get('texture'):
        why.append('no texture lightmap seen')
    if rec.get('cls') == 'import' or rec.get('error'):
        why.append('material record unread')
    out['verdict'] = 'candidate' if not why else 'excluded'
    out['why'] = why
    cautions = []
    if masked and not OVERLAY_ROOT.search(rec.get('root') or ''):
        cautions.append('masked (BLEND_Masked, on a general root): drawn only where its opacity mask is on; whether '
                        'its texture has holes is not read here')
    if rec.get('uvs') == 2:
        cautions.append('samples two texture channels (the second is the lightmap channel on most meshes)')
    if colours['verdict'] == 'one colour':
        cautions.append('reads vertex colours (%s), but %d of %d placings draw it with one colour (%s): a made mesh '
                        'copies that colour' % ('; '.join(colours['signs']), colours['oneColourPlacings'], len(rows),
                                                ', '.join(colours['oneColours'])))
    elif colours['meshStreamVarying'] and not colours['needsPaint']:
        cautions.append('the colour stream varies on %d of its placings\' meshes' % colours['meshStreamVarying'])
    elif colours['paintedVarying'] and not colours['needsPaint']:
        cautions.append('%d placings carry painted colours (%d varying)'
                        % (colours['painted'], colours['paintedVarying']))
    if not flat_rows:
        cautions.append('no flat or mostly flat placing at least %g across' % MIN_SIDE)
    if out['onlyInSlingshot']:
        cautions.append('placed only in Slingshot (DLC1) maps')
    if (rec.get('diffuseLayers') or 0) >= 2 and colours['verdict'] == 'no signs':
        cautions.append('its shader samples %d diffuse-like textures' % rec['diffuseLayers'])
    if rec.get('twoSided'):
        cautions.append('two-sided')
    if rec.get('tiling'):
        cautions.append('tiling scalars %s' % rec['tiling'])
    if best['light'].get('type') != 2:
        cautions.append('its donor has no texture lightmap')
    out['cautions'] = cautions
    return out


def keep(summary):
    """Materials kept: named for ground or rock (in full), or placed on a flat or mostly flat piece (in brief)."""
    return summary['setting'] is not None or summary['flatTopPlacings'] > 0


def repeat_words(r):
    """A repeat record in words: '320.2 x 320.2 (u along +x, v along +y)'."""
    if not r or not r.get('u') or not r.get('v'):
        return None
    return '%g x %g (u along %s, v along %s)' % (r['u']['repeat'], r['v']['repeat'], r['u']['axis'], r['v']['axis'])


def brief(v):
    """The short record of a material: one that is excluded, or a candidate not named for ground or rock (floors,
    roofs, rugs, UFO decks)."""
    d = v['donor']
    return dict(setting=v['setting'], placings=v['placings'], maps=v['maps'], root=v['root'], blendMode=v['blendMode'],
                uvs=v['uvs'], lightmaps=v['lightmaps'], colours=v['colours']['verdict'], repeat=v['repeat'],
                verdict=v['verdict'], why=v['why'],
                donor=dict(map=d['map'], actor=d['actor'], mesh=d['mesh'], size=d['size'], shape=d['shape'],
                           density=d['lightmap'].get('density')))


def dump(value, depth=0, open_to=3):
    """JSON with the outer `open_to` levels one item a line and everything deeper on one line (a material's fields
    a line each)."""
    if depth >= open_to or not isinstance(value, (dict, list)) or not value:
        return json.dumps(value, default=str)
    pad, inner = ' ' * depth, ' ' * (depth + 1)
    if isinstance(value, dict):
        rows = ['%s%s: %s' % (inner, json.dumps(k), dump(v, depth + 1, open_to)) for k, v in value.items()]
        return '{\n%s\n%s}' % (',\n'.join(rows), pad)
    return '[\n%s\n%s]' % (',\n'.join(inner + dump(v, depth + 1, open_to) for v in value), pad)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--maps', nargs='*', help='map names (default: every base map the install lists)')
    ap.add_argument('--streams', action='store_true', help='read the streams too')
    ap.add_argument('--output', type=Path)
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()
    import library
    import settings
    game, _ = settings.game_install(settings.load_settings())
    if game is None:
        raise SystemExit('the game install is not set (python tools/viewer/viewer.py settings)')
    maps = [(n, Path(path)) for n, role, path in library.donors(game) if args.streams or role == 'base']
    if args.maps:
        want = {m.casefold() for m in args.maps}
        maps = [(n, path) for n, path in maps if n.casefold() in want]
    t0 = time.time()
    a = Audit()
    for name, path in maps:
        a.run_map(name, path, args.verbose)
    summaries = {k: material_summary(k, a.materials[k], rows, a) for k, rows in a.placings.items()}
    kept = {k: v for k, v in summaries.items() if keep(v)}
    candidates = sorted((v for v in kept.values() if v['verdict'] == 'candidate' and v['setting']),
                        key=lambda v: (v['setting'], -v['placings']))
    by_setting = defaultdict(list)
    for v in candidates:
        by_setting[v['setting']].append(v['material'])
    result = dict(
        scope='Read-only: %d maps of the install (%s), their placed plain static pieces at least %g x %g across; '
              'nothing written to the game' % (len(maps), 'base maps and streams' if args.streams else 'base maps',
                                                MIN_SIDE, MIN_SIDE),
        seconds=round(time.time() - t0, 1),
        summary=dict(maps=len(a.maps_read), donorMapsByLicensee={str(k): v for k, v in a.licensee.items()},
                     actorClasses=dict(a.classes.most_common()), meshes=len(a.meshes), meshesUnread=a.mesh_errors,
                     materials=len(summaries), materialsKept=len(kept),
                     keptBySetting=dict(Counter(v['setting'] or 'flat, unnamed' for v in kept.values()).most_common()),
                     candidates=len(candidates), candidatesBySetting={k: len(v) for k, v in sorted(by_setting.items())},
                     exclusions=dict(Counter(w.split(' (')[0] for v in kept.values() for w in v['why']).most_common()),
                     lightmapKinds=dict(sum((Counter(v['lightmaps']) for v in kept.values()), Counter()).most_common()),
                     uvsSampled=dict(Counter(str(v['uvs']) for v in kept.values()).most_common()),
                     otherMaterials=dict(count=len(summaries) - len(kept),
                                         placings=sum(v['placings'] for k, v in summaries.items() if k not in kept))),
        candidatesBySetting=dict(sorted(by_setting.items())),
        materials={k: v for k, v in sorted(kept.items()) if v['setting'] and v['verdict'] == 'candidate'},
        excluded={k: brief(v) for k, v in sorted(kept.items()) if v['setting'] and v['verdict'] != 'candidate'},
        flatUnnamed={k: brief(v) for k, v in sorted(kept.items()) if not v['setting'] and v['verdict'] == 'candidate'})
    print(json.dumps(result['summary'], indent=1, default=str))
    for v in candidates:
        d = v['donor']
        print('%-18s %-58s placed %4d maps %2d  repeat %-14s lm %s/%s  donor %s %s %s %s' % (
            v['setting'], v['material'], v['placings'], v['maps'], v['repeat'], d['lightmap'].get('type'),
            d['lightmap'].get('density'), d['map'], d['actor'], d['mesh'].rsplit('.', 1)[-1], d['size']))
    if args.output:
        args.output.write_text(dump(result) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
