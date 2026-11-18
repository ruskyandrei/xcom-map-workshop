"""Ground shapes made from numbers (custom geometry plan, stage M6): a flat patch, a raised block and a ramp, each a
plain static mesh on its look's material, its collision one convex element.

A shape's numbers are in its piece's frame (the tool puts the piece at the shape's corner, its axes the world's):

  shape     'patch' (a flat slab whose top is the ground's level), 'block' (a box standing on the ground) or
            'ramp' (a wedge rising along +x: its low edge at x0 on the ground, its high edge at x1)
  x0, x1    its footprint along x, whole tiles (1 to MAX_TILES)
  y0, y1    its footprint along y, whole tiles
  height    a block's top or a ramp's high edge over its bottom (1 to MAX_HEIGHT); a patch's is its look's thickness
  look      the material it is drawn in (ground_looks.json; left out, the first)

A shape stands on z 0 (its bottom), a patch with its top at z 0 (it lies over the ground it covers, its plate under
it). Its faces: the top (a ramp's slope), the sides (a ramp's two triangles and its high end); no bottom. Texture
coordinates are world-planar, so the material repeats every `repeat` units on every face as on the donor's: on the
top u = x / repeat, v = y / repeat; on a side u along it, v down it. The lightmap has a chart for each face, at the
look's density. The collision is the shape's convex hull as the game's cooker saves it (hulls.py): a box for a patch
and a block, a wedge for a ramp.

A ramp's slope matters to the game (F-81): a floor tile steeper than about 10 degrees (its normal's z under 0.9848)
is sloped, and sloped tiles get no cover; past about 45 degrees it is no floor to stand on. slope() and
slope_words() say so."""
import hashlib
import json
import math
from pathlib import Path

import frac_wall
import hulls

LOOKS_FILE = Path(__file__).resolve().parent / 'ground_looks.json'
SHAPES = ('patch', 'block', 'ramp')
TILE = 96.0
MAX_TILES = 16
MAX_HEIGHT = 384.0
SLOPED = math.degrees(math.acos(0.9848))     # about 10: a steeper floor tile is sloped (F-81: no cover on it)
STEEP = 45.0                                 # past this it is no floor
EPS = 1e-4
# the recipe a look without its own takes (ground_looks.json's looks name their own)
DEFAULT_RECIPE = dict(repeat=256.0, slot=0, sections=1, thickness=8.0, colours=dict(outside='ffffffff', interior='ffffffff'),
                      lightmap=dict(density=0.12, margin=2, interiorDensity=1.0, block=4))


def _looks():
    if not LOOKS_FILE.exists():
        return {'plain': dict(id='plain', name='Plain', recipe=dict(DEFAULT_RECIPE))}
    data = json.loads(LOOKS_FILE.read_text(encoding='utf-8'))
    return {look['id']: dict(look, recipe=dict(DEFAULT_RECIPE, **look.get('recipe', {}))) for look in data['looks']}


LOOKS = _looks()
DEFAULT_LOOK = next(iter(LOOKS))


def look_of(shape):
    """The shape's look's recipe (ValueError for one not listed)."""
    look = (shape or {}).get('look', DEFAULT_LOOK)
    if look not in LOOKS:
        raise ValueError('a ground shape\'s look is one of %s (it has %r)' % (', '.join(LOOKS), look))
    return dict(LOOKS[look]['recipe'], look=look)


def check(shape):
    """The shape's numbers checked (ValueError). Returns its tiles (nx, ny)."""
    if not isinstance(shape, dict) or shape.get('shape') not in SHAPES:
        raise ValueError('a ground shape is one of %s' % ', '.join(SHAPES))
    if not all(isinstance(shape.get(k), (int, float)) and not isinstance(shape.get(k), bool) and math.isfinite(shape[k])
               for k in ('x0', 'x1', 'y0', 'y1')):
        raise ValueError('a ground shape needs its footprint, x0, x1, y0 and y1')
    look_of(shape)
    nx, ny = (shape['x1'] - shape['x0']) / TILE, (shape['y1'] - shape['y0']) / TILE
    if not all(abs(n - round(n)) < EPS and 1 <= round(n) <= MAX_TILES for n in (nx, ny)):
        raise ValueError('a ground shape is 1 to %d whole tiles each way (it has %g by %g)' % (MAX_TILES, nx, ny))
    if shape['shape'] != 'patch':
        h = shape.get('height')
        if not (isinstance(h, (int, float)) and not isinstance(h, bool) and math.isfinite(h) and 1 <= h <= MAX_HEIGHT):
            raise ValueError("a block's or ramp's height is 1 to %g (it has %r)" % (MAX_HEIGHT, h))
    return int(round(nx)), int(round(ny))


def corners_and_faces(shape):
    """The solid's corners [(x, y, z)] and its faces [[corner indices] counter-clockwise seen from outside], the
    bottom last (the mesh leaves it out; the hull keeps it)."""
    check(shape)
    x0, x1, y0, y1 = (float(shape[k]) for k in ('x0', 'x1', 'y0', 'y1'))
    if shape['shape'] == 'ramp':
        h = float(shape['height'])
        c = [(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0), (x1, y0, h), (x1, y1, h)]
        faces = [[0, 4, 5, 3], [1, 2, 5, 4], [0, 1, 4], [3, 5, 2], [0, 3, 2, 1]]
        return c, faces
    z0, z1 = (-look_of(shape)['thickness'], 0.0) if shape['shape'] == 'patch' else (0.0, float(shape['height']))
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [[4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7], [0, 3, 2, 1]]
    return c, faces


def _normal(pts):
    n = [0.0, 0.0, 0.0]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    ln = math.sqrt(sum(v * v for v in n))
    return tuple(v / ln for v in n)


def faces_of(shape):
    """The mesh's polygons (frac_wall.Faces): every face but the bottom, world-planar texture coordinates."""
    R = look_of(shape)
    corners, loops = corners_and_faces(shape)
    rep, slot = R['repeat'], R['slot']
    faces = frac_wall.Faces()
    for k, loop in enumerate(loops[:-1]):
        pts = [corners[i] for i in loop]
        n = _normal(pts)
        if abs(n[2]) > 0.5:
            # the top (or a ramp's slope): projected straight down; its chart its true size up the slope
            uv = [(x / rep, y / rep) for x, y, _ in pts]
            run = max(p[0] for p in pts) - min(p[0] for p in pts)
            rise = max(p[2] for p in pts) - min(p[2] for p in pts)
            width, depth = math.hypot(run, rise), max(p[1] for p in pts) - min(p[1] for p in pts)
            x_lo, y_lo = min(p[0] for p in pts), min(p[1] for p in pts)
            stretch = width / run if run else 1.0
            cuv = [((x - x_lo) * stretch, y - y_lo) for x, y, _ in pts]
            chart = faces.chart(('top', k), width, depth)
        else:
            # a side: u along it (the axis it runs on), v down it
            along = 0 if abs(n[1]) > abs(n[0]) else 1
            sign = 1.0 if (n[1] if along == 0 else -n[0]) < 0 else -1.0
            uv = [(sign * p[along] / rep, -p[2] / rep) for p in pts]
            a_lo, z_lo = min(p[along] for p in pts), min(p[2] for p in pts)
            cuv = [(p[along] - a_lo, p[2] - z_lo) for p in pts]
            chart = faces.chart(('side', k), max(p[along] for p in pts) - a_lo, max(p[2] for p in pts) - z_lo)
        faces.add(pts, n, slot, 0, uv, chart, cuv)
    return faces


def hull(shape):
    """The shape's collision element (hulls.hull_element's fields)."""
    corners, loops = corners_and_faces(shape)
    if shape['shape'] == 'ramp':
        return hulls.hull_element(corners)
    return None


def solids(shape):
    """The collision as frac_walls.body_setup_boxes takes it: [(lo, hi)] boxes or hull elements."""
    corners, _ = corners_and_faces(shape)
    if shape['shape'] == 'ramp':
        return [hull(shape)]
    lo = tuple(min(c[k] for c in corners) for k in range(3))
    hi = tuple(max(c[k] for c in corners) for k in range(3))
    return [(lo, hi)]


def default_template():
    """A plain static mesh's layout as the cooked ones have it, for a build with no donor read (the viewer)."""
    t = frac_wall.default_template()
    t = dict(t, fractured=None)
    return t


def dominant_colour(colours):
    """The commonest of `colours` (4 bytes each), or None for none."""
    if not colours:
        return None
    counts = {}
    for c in colours:
        counts[bytes(c)] = counts.get(bytes(c), 0) + 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def build(shape, template=None, colour=None):
    """The mesh of `shape` (gen_mesh's form, a plain static mesh) on the donor's decoded mesh `template`
    (default_template() when None), with dict(solids, lightmapRect, counts). `colour` (4 bytes): every vertex's colour,
    which the game's blend materials read (the ground's are painted: the Build gives the donor's commonest painted
    colour, so the shape shows the donor's main layer); None: the donor mesh's commonest, else the look's."""
    R = look_of(shape)
    colour = colour or dominant_colour((template or {}).get('lods', [{}])[0].get('colours'))
    if colour:
        R = dict(R, colours=dict(outside=bytes(colour).hex(), interior=bytes(colour).hex()))
    check(shape)
    template = template or default_template()
    faces = faces_of(shape)
    corners, _ = corners_and_faces(shape)
    centre = tuple((min(c[k] for c in corners) + max(c[k] for c in corners)) / 2 for k in range(3))
    records = [dict(centre=centre, neighbours=[], dims=[])]
    guid = hashlib.md5(('ground|%r' % (sorted(shape.items(), key=str),)).encode()).digest()
    R = dict(R, slots={})
    out = frac_wall.assemble(faces, records, template, R, guid, slots=R['sections'], what='a ground shape')
    return dict(out, solids=solids(shape))


def local_box(shape):
    """The box the shape stands in, in its mesh's frame."""
    corners, _ = corners_and_faces(shape)
    return [v for k in range(3) for v in (min(c[k] for c in corners), max(c[k] for c in corners))]


def mesh_name(shape):
    """A name for the shape's mesh from its numbers and its look's recipe (as frac_wall.mesh_name)."""
    digest = hashlib.sha256(repr((sorted((k, repr(v)) for k, v in look_of(shape).items()),
                                  sorted((k, repr(v)) for k, v in shape.items()))).encode()).hexdigest()
    return 'Ground_%s_%dx%d_%s' % (shape['shape'], round((shape['x1'] - shape['x0']) / TILE),
                                  round((shape['y1'] - shape['y0']) / TILE), digest[:10])


def slope(shape):
    """A ramp's slope in degrees (0 for a patch or block)."""
    if shape.get('shape') != 'ramp':
        return 0.0
    return math.degrees(math.atan2(float(shape['height']), float(shape['x1']) - float(shape['x0'])))


def slope_words(shape):
    """What the game does on the shape's top, in words ('' when it is flat)."""
    s = slope(shape)
    if s <= 0:
        return ''
    if s > STEEP:
        return 'its slope (%d degrees) is no floor: units can\'t stand on it' % round(s)
    if s > SLOPED:
        return ('its slope (%d degrees) is walked, but its tiles are sloped: a unit on it gets no cover, as on every '
                'slope of the game\'s steeper than about 10 degrees' % round(s))
    return 'its slope (%d degrees) is walked and gives cover as flat ground does' % round(s)
