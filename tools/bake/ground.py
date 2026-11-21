"""Ground shapes made from numbers (custom geometry plan, stage M6): a flat patch, a raised block and a ramp, each a
plain static mesh on its look's material, its collision one convex element.

A shape's numbers are in its piece's frame (the tool puts the piece at the shape's corner, its axes the world's):

  shape     'patch' (a flat slab whose top is the ground's level), 'block' (a box standing on the ground),
            'ramp' (a wedge rising along +x: its low edge at x0 on the ground, its high edge at x1) or 'rock' (an
            irregular convex piece within its footprint and height, from its seed: M6 item 6)
  x0, x1    its footprint along x, whole tiles (1 to MAX_TILES: one plain piece of any size the map holds, not cut as
            made walls and floors are, custom geometry editing plan B4)
  y0, y1    its footprint along y, whole tiles
  height    a block's top, a ramp's high edge or a rock's top over its bottom (1 to MAX_HEIGHT); a patch's is its
            look's thickness
  seed      a rock's: 0 to ROCK_SEEDS - 1 (each seed another rock)
  points    a rock's, once its corners have been moved in the editor (look picker and rock points plan, R1): its
            ROCK_POINTS points [[x, y, z], ...] in the piece's frame, which it is then the hull of instead of the
            seed's; each within the footprint and between 0 and its height, the first ROCK_RING (its ground ring) on
            the ground, z 0
  look      the material it is drawn in: a name (ground_looks.json; left out, the first), or a look given whole, a
            dict {'mesh' (the donor's mesh path), 'material' (its material's), 'measure' (ground_measure's VERSION),
            'recipe' (what ground_measure.measure gives, from the catalogue tools/bake/looks/ground.json or measured
            on the donor: tools/bake/looks.py resolves it)}

A shape stands on z 0 (its bottom), a patch with its top PATCH_LIFT over z 0 (it lies over the ground it covers, its
plate under it, a little over it so the two don't fight to be drawn: 3, since the construction kit's floor planes,
the blank map's, are drawn 2 over their collision, which the editor and the game's floor go by, F-137). Its faces: the top (a ramp's slope), the sides (a ramp's two triangles and its high end); no bottom. Texture
coordinates are world-planar, so the material repeats every `repeat` units on every face as on the donor's: on the
top u = x / repeat, v = y / repeat; on a side u along it, v down it. The lightmap has a chart for each face, at the
look's density. The collision is the shape's convex hull as the game's cooker saves it (hulls.py): a box for a patch
and a block, a wedge for a ramp, a rock's own hull for a rock.

A rock is the hull (hulls.physx_hull, the cooker's) of rings of points round its footprint's middle, drawn from its
seed: a ring on the ground (its flat bottom), a wider one low down, a narrower one higher, and its top, which
reaches its height. Its faces are flat, each with its own normal.

A ramp's slope matters to the game (F-81): a floor tile steeper than about 10 degrees (its normal's z under 0.9848)
is sloped, and sloped tiles get no cover; past about 45 degrees it is no floor to stand on. slope() and
slope_words() say so.

A measured recipe (it has `uv`, ground_measure's) gives the top its own planar map (u = a x + b y + c, v = d x + e y +
f, in the piece's frame, offsets modulo 1: turned, mirrored or of two repeats) and the sides the same repeats (u along
each side, v down it); its faces go in the donor's slot of its material, among the donor's sections (the others
empty), and its vertices take its colour (the one its donor mostly draws the material with,
measure_common.main_colour) unless the Build gives one.

The free form (custom geometry improvements plan, section 10.2): numbers holding `free: 1` (free_form.py) give the
shape's box whole, finite units in its frame, any size (no whole tiles, no MAX_TILES or MAX_HEIGHT): x0 < x1, y0 < y1
and z0 < z1, a patch's plate (its top and its underside: PATCH_LIFT and its look's thickness when the editor first
makes it), a block's bottom and top, a ramp's bottom and its high edge's top (it rises from z0 at x0 to z1 at x1), a
rock's bottom (its ground ring) and top; `height` is not read. Rock points lie within that box. `mapping` and `plain`
are taken and not read (stage 4's and the editor's). Each face's texture coordinates are held near 0 in whole repeats
(free_form.held): one face may span up to about 2,047 repeats of its look's texture, and a larger one is refused with
that reason (the half floats the mesh writes them in keep no place within a repeat past 1,024 from 0). Old numbers
never hold `free`, and build as they always did."""
import hashlib
import json
import math
from pathlib import Path
import random

import frac_slab
import frac_wall
import free_form
from free_form import NumbersError
import hulls
import measure_common

LOOKS_FILE = Path(__file__).resolve().parent / 'ground_looks.json'
SHAPES = ('patch', 'block', 'ramp', 'rock')
TILE = 96.0
MAX_TILES = 64
MAX_HEIGHT = 384.0
SLOPED = math.degrees(math.acos(0.9848))     # about 10: a steeper floor tile is sloped (F-81: no cover on it)
STEEP = 45.0                                 # past this it is no floor
EPS = 1e-4
PATCH_LIFT = 3.0     # a patch's top over the ground it lies on (F-137)
ROCK_SEEDS = 2 ** 31     # a rock's seed is 0 to ROCK_SEEDS - 1
ROCK_POINTS = 24     # rock_points' count: rings of 7 (on the ground), 8, 6 and 3
ROCK_RING = 7        # the first ROCK_RING of them are its ground ring, on the ground (so the rock stands flat)
# the recipe a look without its own takes (ground_looks.json's looks name their own)
DEFAULT_RECIPE = dict(repeat=256.0, slot=0, sections=1, thickness=8.0, colours=dict(outside='ffffffff', interior='ffffffff'),
                      lightmap=dict(density=0.12, margin=2, interiorDensity=1.0, block=4))


def _looks():
    data = json.loads(LOOKS_FILE.read_text(encoding='utf-8'))
    return {look['id']: dict(look, recipe=dict(DEFAULT_RECIPE, **look.get('recipe', {}))) for look in data['looks']}


LOOKS = _looks()
DEFAULT_LOOK = next(iter(LOOKS))


def look_of(shape):
    """The shape's look's recipe: a named one's (ValueError for one not listed), or a given one's (a dict with its
    resolved recipe: the module's words; ValueError without it)."""
    look = (shape or {}).get('look', DEFAULT_LOOK)
    if isinstance(look, dict):
        recipe = look.get('recipe')
        if not isinstance(recipe, dict) or not isinstance(look.get('mesh'), str):
            raise ValueError("a ground shape's look is a name or {mesh, material, measure, recipe} with its recipe "
                             "resolved (it has %r)" % (sorted(look),))
        return dict(DEFAULT_RECIPE, **recipe)
    if not isinstance(look, str) or look not in LOOKS:
        raise ValueError('a ground shape\'s look is one of %s (it has %r)' % (', '.join(LOOKS), look))
    return dict(LOOKS[look]['recipe'], look=look)


def _named(shape):
    """The shape's numbers with a given look (a dict) as its identity: its donor's mesh, material and measurer and its
    recipe in one spelling (a recipe from the catalogue and one measured again are the same look); a named one as it
    is."""
    look = shape.get('look')
    if not isinstance(look, dict):
        return shape
    return dict(shape, look='%s|%s|%s|%s' % (look.get('mesh'), look.get('material'), look.get('measure'),
                                            json.dumps(look.get('recipe'), sort_keys=True)))


def free(shape):
    """Whether the shape's numbers are in the free form (free_form.is_free)."""
    return free_form.is_free(shape)


def check_free(shape):
    """Free numbers checked (the free form's request: a NumbersError, a ValueError with its code and reason, for
    numbers without `free: 1` too): their box [x0, x1, y0, y1, z0, z1]."""
    if not free(shape):
        raise NumbersError('free', "a ground shape of the free form's request holds free: 1 (it has %r)"
                           % (sorted(shape) if isinstance(shape, dict) else shape,))
    return check(shape)


def check(shape):
    """The shape's numbers checked (ValueError). Returns its tiles (nx, ny); a free shape's box [x0, x1, y0, y1, z0,
    z1] (its refusals NumbersErrors, ValueErrors with their codes)."""
    if not isinstance(shape, dict) or shape.get('shape') not in SHAPES:
        raise ValueError('a ground shape is one of %s' % ', '.join(SHAPES))
    if free(shape):
        what = 'a ground %s' % shape['shape']
        box = free_form.extents(shape, what)
        free_form.mapping(shape, what)
        look_of(shape)
        _check_seed(shape)
        if 'points' in shape:
            if shape['shape'] != 'rock':
                raise NumbersError('points', 'only a rock has points')
            check_points(shape)
        return box
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
            raise ValueError("a block's, ramp's or rock's height is 1 to %g (it has %r)" % (MAX_HEIGHT, h))
    _check_seed(shape)
    if 'points' in shape:
        if shape['shape'] != 'rock':
            raise ValueError('only a rock has points')
        check_points(shape)
    return int(round(nx)), int(round(ny))


def _check_seed(shape):
    """A rock's seed checked (ValueError)."""
    if shape['shape'] == 'rock':
        seed = shape.get('seed')
        if not (isinstance(seed, int) and not isinstance(seed, bool) and 0 <= seed < ROCK_SEEDS):
            raise ValueError("a rock's seed is a whole number, 0 to %d (it has %r)" % (ROCK_SEEDS - 1, seed))


def check_points(shape):
    """A rock's moved points checked (ValueError): ROCK_POINTS of them, each [x, y, z] within its footprint and between
    0 and its height (a free rock's between z0 and z1), the first ROCK_RING on the ground (z 0; a free rock's z0)."""
    pts = shape['points']
    number = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)  # noqa: E731
    if not (isinstance(pts, list) and len(pts) == ROCK_POINTS
            and all(isinstance(p, (list, tuple)) and len(p) == 3 and all(number(v) for v in p) for p in pts)):
        raise ValueError("a rock's points are %d of [x, y, z]" % ROCK_POINTS)
    if free(shape):
        x0, x1, y0, y1, bottom, top = (float(shape[k]) for k in ('x0', 'x1', 'y0', 'y1', 'z0', 'z1'))
    else:
        x0, x1, y0, y1, h = (float(shape[k]) for k in ('x0', 'x1', 'y0', 'y1', 'height'))
        bottom, top = 0.0, h
    slack = 1e-3
    for i, (x, y, z) in enumerate(pts):
        if not (x0 - slack <= x <= x1 + slack and y0 - slack <= y <= y1 + slack):
            raise ValueError("a rock's point %d (%g, %g) is outside its footprint" % (i, x, y))
        if not bottom - slack <= z <= top + slack:
            raise ValueError("a rock's point %d is %g up: 0 to its height, %g" % (i, z, top) if not free(shape)
                             else "a rock's point %d is %g up: its bottom %g to its top %g" % (i, z, bottom, top))
        if i < ROCK_RING and abs(z - bottom) > slack:
            raise ValueError("a rock's point %d is of its ground ring: it stays on the ground (it is %g up)" % (i, z)
                             if not free(shape) else "a rock's point %d is of its ground ring: it stays on its bottom, "
                             "%g (it is %g up)" % (i, bottom, z))


def rock_points(shape):
    """The points a rock is the hull of: its moved `points` when it has them, else from its seed: rings round its
    footprint's middle, every point within the footprint and between 0 and its height, the highest at its height (a
    free rock's between its bottom z0, where its ground ring is, and its top z1)."""
    if shape.get('points') is not None:
        return [tuple(float(v) for v in p) for p in shape['points']]
    rng = random.Random(int(shape['seed']))
    x0, x1, y0, y1 = (float(shape[k]) for k in ('x0', 'x1', 'y0', 'y1'))
    if free(shape):
        base, top_z = float(shape['z0']), float(shape['z1'])
        h = top_z - base
    else:
        base, h = 0.0, float(shape['height'])
        top_z = h
    cx, cy, ax, ay = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    pts = []
    # (points, heights as shares of the height (None: on the ground), reach as shares of the half footprint)
    for n, z, reach in ((7, None, (0.72, 0.92)), (8, (0.25, 0.55), (0.86, 1.0)), (6, (0.62, 0.85), (0.48, 0.74)),
                        (3, (0.9, 1.0), (0.0, 0.34))):
        start = rng.uniform(0.0, 2 * math.pi)
        for k in range(n):
            t = start + 2 * math.pi * (k + rng.uniform(-0.3, 0.3)) / n
            r = rng.uniform(*reach)
            pts.append((cx + ax * r * math.cos(t), cy + ay * r * math.sin(t),
                        base if z is None else base + h * rng.uniform(*z)))
    top = max(range(len(pts)), key=lambda i: pts[i][2])
    pts[top] = (pts[top][0], pts[top][1], top_z)
    return pts


def _rock(shape):
    """A rock's corners and faces (corners_and_faces' form): the cooker's hull of rock_points, each face turned to
    face out, the bottom last."""
    points = [tuple(float(v) for v in hulls.cooker_vertex(p)) for p in rock_points(shape)]
    order, loops = hulls.physx_hull(points)
    if order is None or loops is None:
        raise ValueError('the rock\'s points make no convex solid (%s)'
                         % ('its moved points' if shape.get('points') is not None else 'seed %r' % shape['seed']))
    c = [points[i] for i in order]
    mid = tuple(sum(p[k] for p in c) / len(c) for k in range(3))
    faces = []
    for loop in loops:
        pts = [c[i] for i in loop]
        n = _normal(pts)
        centre = tuple(sum(p[k] for p in pts) / len(pts) for k in range(3))
        out = sum(n[k] * (centre[k] - mid[k]) for k in range(3))
        faces.append(list(loop) if out > 0 else list(reversed(loop)))
    bottom = min(range(len(faces)), key=lambda i: _normal([c[j] for j in faces[i]])[2])
    faces.append(faces.pop(bottom))
    return c, faces


def rock_corners(shape):
    """A rock's points (rock_points: [(x, y, z)], ROCK_POINTS of them) and the indices of those that are its hull's
    corners (the cooker's), in order: what the editor puts its blue dots on (look picker and rock points plan, R2). A
    point inside the others is no corner."""
    check(shape)
    if shape['shape'] != 'rock':
        raise ValueError('only a rock has corners to move')
    pts = rock_points(shape)
    order, _ = hulls.physx_hull([tuple(float(v) for v in hulls.cooker_vertex(p)) for p in pts])
    if order is None:
        raise ValueError('the rock\'s points make no convex solid')
    return pts, sorted(order)


def corners_and_faces(shape):
    """The solid's corners [(x, y, z)] and its faces [[corner indices] counter-clockwise seen from outside], the
    bottom last (the mesh leaves it out; the hull keeps it)."""
    check(shape)
    x0, x1, y0, y1 = (float(shape[k]) for k in ('x0', 'x1', 'y0', 'y1'))
    if shape['shape'] == 'rock':
        return _rock(shape)
    if free(shape):
        # (the box whole: a patch's plate, a block's bottom and top, a ramp from z0 at x0 up to z1 at x1)
        z0, z1 = float(shape['z0']), float(shape['z1'])
        if shape['shape'] == 'ramp':
            c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x1, y0, z1), (x1, y1, z1)]
            return c, [[0, 4, 5, 3], [1, 2, 5, 4], [0, 1, 4], [3, 5, 2], [0, 3, 2, 1]]
        c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        return c, [[4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7], [0, 3, 2, 1]]
    if shape['shape'] == 'ramp':
        h = float(shape['height'])
        c = [(x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0), (x1, y0, h), (x1, y1, h)]
        faces = [[0, 4, 5, 3], [1, 2, 5, 4], [0, 1, 4], [3, 5, 2], [0, 3, 2, 1]]
        return c, faces
    z0, z1 = ((PATCH_LIFT - look_of(shape)['thickness'], PATCH_LIFT) if shape['shape'] == 'patch'
              else (0.0, float(shape['height'])))
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
    """The mesh's polygons (frac_wall.Faces): every face but the bottom, world-planar texture coordinates (a free
    shape's held near 0 in whole repeats, free_form.held)."""
    R = look_of(shape)
    corners, loops = corners_and_faces(shape)
    held = free_form.held if free(shape) else (lambda uv, what: uv)
    rep, slot = R['repeat'], R['slot']
    top_map = R['uv']['top'] if 'uv' in R else None
    if top_map:
        # the sides' repeats: the top map's, u along each side, v down it
        rep_u = 1.0 / max(math.hypot(top_map[0][0], top_map[0][1]), 1e-9)
        rep_v = 1.0 / max(math.hypot(top_map[1][0], top_map[1][1]), 1e-9)
    faces = frac_wall.Faces()
    for k, loop in enumerate(loops[:-1]):
        pts = [corners[i] for i in loop]
        n = _normal(pts)
        if abs(n[2]) > 0.5:
            # the top (or a ramp's slope): projected straight down; its chart its true size up the slope
            uv = ([(top_map[0][0] * x + top_map[0][1] * y + top_map[0][2],
                    top_map[1][0] * x + top_map[1][1] * y + top_map[1][2]) for x, y, _ in pts] if top_map
                  else [(x / rep, y / rep) for x, y, _ in pts])
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
            uv = ([(sign * p[along] / rep_u, -p[2] / rep_v) for p in pts] if top_map
                  else [(sign * p[along] / rep, -p[2] / rep) for p in pts])
            a_lo, z_lo = min(p[along] for p in pts), min(p[2] for p in pts)
            cuv = [(p[along] - a_lo, p[2] - z_lo) for p in pts]
            chart = faces.chart(('side', k), max(p[along] for p in pts) - a_lo, max(p[2] for p in pts) - z_lo)
        faces.add(pts, n, slot, 0, held(uv, 'the %s of a ground %s' % ('top' if abs(n[2]) > 0.5 else 'side',
                                                                       shape['shape'])), chart, cuv)
    return faces


def hull(shape):
    """The shape's collision element (hulls.hull_element's fields)."""
    corners, loops = corners_and_faces(shape)
    if shape['shape'] in ('ramp', 'rock'):
        return hulls.hull_element(corners)
    return None


def solids(shape):
    """The collision as frac_walls.body_setup_boxes takes it: [(lo, hi)] boxes or hull elements."""
    corners, _ = corners_and_faces(shape)
    if shape['shape'] in ('ramp', 'rock'):
        return [hull(shape)]
    lo = tuple(min(c[k] for c in corners) for k in range(3))
    hi = tuple(max(c[k] for c in corners) for k in range(3))
    return [(lo, hi)]


def default_template():
    """A plain static mesh's layout as the cooked ones have it, for a build with no donor read (the viewer)."""
    t = frac_wall.default_template()
    t = dict(t, fractured=None)
    return t


def dominant_colour(colours, template=None):
    """The colour `colours` (4 bytes each, one a vertex of `template`'s LOD 0) mostly paint, as 4 bytes, or None for
    none: measure_common.main_colour, each vertex weighed by its share of the mesh's area (by count without a
    template)."""
    if not colours:
        return None
    weights = [1.0] * len(colours)
    if template is not None:
        T = measure_common.Tris(template)
        if len(T.pos) <= len(colours) and len(T.tris):
            weights = list(T.vertex_areas(T.slot == T.slot)) + [0.0] * (len(colours) - len(T.pos))
    return bytes.fromhex(measure_common.main_colour(colours, weights))


def build(shape, template=None, colour=None):
    """The mesh of `shape` (gen_mesh's form, a plain static mesh) on the donor's decoded mesh `template`
    (default_template() when None), with dict(solids, lightmapRect, counts). `colour` (4 bytes): every vertex's colour,
    which the game's blend materials read (the ground's are painted: the Build gives the donor's commonest painted
    colour, so the shape shows the donor's main layer); None: the donor mesh's commonest, else the look's."""
    R = look_of(shape)
    if not isinstance(shape.get('look'), dict):
        # (a look given whole carries its colour, measured on its donor's placing)
        colour = colour or dominant_colour((template or {}).get('lods', [{}])[0].get('colours'), template)
    if colour:
        R = dict(R, colours=dict(outside=bytes(colour).hex(), interior=bytes(colour).hex()))
    check(shape)
    template = frac_slab.two_channels(template or default_template())
    faces = faces_of(shape)
    corners, _ = corners_and_faces(shape)
    centre = tuple((min(c[k] for c in corners) + max(c[k] for c in corners)) / 2 for k in range(3))
    records = [dict(centre=centre, neighbours=[], dims=[])]
    guid = hashlib.md5(('ground|%r' % (sorted(_named(shape).items(), key=str),)).encode()).digest()
    R = dict(R, slots={})
    out = frac_wall.assemble(faces, records, template, R, guid, slots=R['sections'], what='a ground shape')
    return dict(out, solids=solids(shape))


def local_box(shape):
    """The box the shape stands in, in its mesh's frame (a free shape's from its numbers: [x0, x1, y0, y1, z0, z1],
    which a rock's hull stands within)."""
    if free(shape):
        return check_free(shape)
    corners, _ = corners_and_faces(shape)
    return [v for k in range(3) for v in (min(c[k] for c in corners), max(c[k] for c in corners))]


def mesh_name(shape):
    """A name for the shape's mesh from its numbers and its look's recipe (as frac_wall.mesh_name)."""
    R = look_of(shape)
    recipe = (sorted((k, repr(v)) for k, v in R.items()) if not isinstance(shape.get('look'), dict)
              else json.dumps(R, sort_keys=True))
    digest = hashlib.sha256(repr((recipe, sorted((k, repr(v)) for k, v in _named(shape).items()))).encode()).hexdigest()
    return 'Ground_%s_%dx%d_%s' % (shape['shape'], round((shape['x1'] - shape['x0']) / TILE),
                                  round((shape['y1'] - shape['y0']) / TILE), digest[:10])


def slope(shape):
    """A ramp's slope in degrees (0 for a patch or block)."""
    if shape.get('shape') != 'ramp':
        return 0.0
    rise = float(shape['z1']) - float(shape['z0']) if free(shape) else float(shape['height'])
    return math.degrees(math.atan2(rise, float(shape['x1']) - float(shape['x0'])))


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
