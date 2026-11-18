"""A fracturing wall made from numbers, built the way one of the game's inside walls is
(private/plans/todo/custom-geometry-implementation-plan.md, section 0, stage F2).

A wall is made in a look (custom geometry plan, M4): one of the game's fracturing walls and the recipe measured on
it, listed in wall_looks.json (LOOKS; research/evidence/wall-look-measure.py measures one); a wall's numbers name
their look (`look`, left out: DEFAULT_LOOK). The first, DEFAULT_LOOK, is URB_Bar's
URB_Bar_FRAC.Meshes.URB_BarIntWallB_FRACTURED, an inside wall 560 long and 400 tall (two storeys), and RECIPE is its
recipe, what was measured on it (research/evidence/frac-wall-audit.py; findings register T-42):

  slots       0 and 1: one side's face (y = +8), the lower and the upper storey, split at z 192, and the wall's
              ends and openings' sides; 2 and 3: the other side's face (y = -8); 4: the trims (skirting, cornice, the
              top and bottom, their ends); 5: the faces inside the wall, seen once a fragment goes. The materials are
              bound by the component (its Materials and DestroyedMaterials), which the donor's clone keeps.
  section     the cross-section, from the floor at z -16 to the top at 384: a skirting from 11 proud of the centre
              line at the floor, in to 10 at z 9 and to the face (8) at z 12; the face up to 372; a cornice out to 12
              at 374, up to the top. The same on both sides.
  texture     the faces repeat every 192 units along and up (u = x / 192 + 0.5, v = 4 - z / 192 on side A; mirrored
              on side B, v = 7 - z / 192); the trims every 96 along, and across the trim set's strip as the donor
              unwraps them (the v of each corner of the section); the inside faces 0 to 1 over each face.
  colours     every vertex (B, G, R, A) 255, 255, 254, 255; an inside face's 255, 255, 255, 255.

A wall is its numbers: dict(x0, x1 (the edges of its tiles along x, in the mesh's frame: the donor's are -384 and
192), openings [dict(x0, x1, z0, z1)] (rectangles through it; a doorway's z0 is the floor, -16), seed (the cells' seed:
the same wall is always the same mesh), storeys (2, the donor's height, when left out; or 1)). A one-storey wall
(custom geometry plan, M2) stands from the floor at -16 to 192, as the game's one-storey inside walls do (URB_
PoliceStation's four, 208 tall from -16 to 192; URB_IndustrialOffice's, their cornice to 194): the donor's section with
its face and cornice ended a storey lower (the face to 180, the cornice from 180 to the top), so its top is cut as the
donor's is and not as the lower half of a tall one; its upper storey's slots are empty (shaped). Its solid stops RECIPE['endInset'] short of each end, as the game's inside
walls do (the donor's ends are -376 and 184): an end on a tile edge would reach a unit into the next tile column (the
game counts its tiles from a unit under the grid the pieces stand on), where the game's occupancy test finds it and
marks that empty tile partly occupied (EXP-67). An opening's sides stay where they are given, as the game's own
doorways have them (solid_wall). An end joined to another made wall (custom geometry plan, M3 item 2: `ends`, a style
for the x0 end and one for the x1 end, END_INSETS; left out, both 'free') stops elsewhere, as the game's walls meet
(research/native/frac-neighbours.md, research/evidence/wall-joints.py): 'free', 8 short as above (a free end, a T's
stem, which the game's inside walls stop 8 short of the wall they meet, and the wall that butts at an L); 'through', 8
past the tile edge, to the far face of the wall it meets at an L (the corner square filled, the other wall butting on
its face); 'line', on the tile edge, against the next wall end to end. build(wall) gives dict(mesh: gen_mesh's form, ready to write, but for its bodySetup and the
kdop's place, fragments: [dict(box: [x0, x1, y0, y1, z0, z1] in the mesh's frame, minZ)], solids: the collision boxes
[(lo, hi)], counts).

How it is made:
- the outline (x0..x1 by -16..384) is cut into cells: seeds on a jittered grid about RECIPE['cell'] apart from the
  fixed seed (none inside an opening), each cell the outline's part nearer its seed than any other (a Voronoi cell);
  then each opening is cut out, a cell crossing it splitting into convex pieces. Each piece is a fragment, through the
  whole thickness (a prism, where the donor's cells lean a little);
- each fragment's faces: its share of both faces (split at the storey), of every trim strip, of the top and bottom, the
  wall's ends and openings' sides that are its edges, and a face inside the wall on every edge it shares with another
  fragment; all faces convex, wound as UE3's front faces are;
- the fragment records: the seed as the centre, the bounds of its corners, the fragment across each face (or -1) with
  the shared face's area, all destroyable, none a root, the average of its outside faces' normals, EW's index -1;
- the lightmap coordinates (UV channel 1): each flat stretch (a face, a trim strip, an end, an inside face) a chart of
  its own, at the donor's density (RECIPE['lightmap']['density'] texels a unit; the inside faces at half that, as the
  donor packs them), shelf-packed with RECIPE['lightmap']['margin'] texels between into the smallest rectangle the
  tries find, its sides whole DXT1 blocks (custom geometry plan, M2: the rectangle follows the wall, so a long wall is
  lit as sharply as the donor). build gives the rectangle's size, `lightmapRect` [width, height] in texels, which the
  Build gives the copy's lightmap (frac_walls.py);
- the collision: the wall's slab (16 thick, as the donor's box) cut into boxes round the openings, one convex element
  each (cover_blocks' hull writer), so no box spans an opening.
"""
import hashlib
import json
import math
from pathlib import Path
import random
import struct

import gen_mesh

LOOKS_FILE = Path(__file__).resolve().parent / 'wall_looks.json'
DEFAULT_LOOK = 'bar-inside'


def _looks():
    """wall_looks.json's looks: {id: the look, its recipe with the look's version and donor mesh in it}."""
    out = {}
    for look in json.loads(LOOKS_FILE.read_text(encoding='utf-8'))['looks']:
        out[look['id']] = dict(look, recipe=dict(look['recipe'], version=look['version'], donor=look['donor']))
    return out


LOOKS = _looks()
# the default look's recipe: the heights (the floor at z -16, the top at 384, the storey split at 192), the face and the
# half thickness, the solid's ends this short of the wall's tile edges ('endInset': the donor's -376 and 184 for -384
# and 192; the inside walls of URB_Bar, URB_PoliceStation and URB_CommercialStreet end 8 short of theirs too), the
# section's corners bottom to top on the +y side ([y, z, the trim set's v there]), the texture repeats, the colours,
# the slots, the cells, the collision's half thickness, and the lightmap (the donor's density, texels a unit on its
# two faces as a baked Build lays them out: 0.196 on URB_Bar's XComDecoFracLevelActor_17, custom geometry plan M2;
# texels between charts; the inside faces' share of that density; the rectangle's sides in DXT1 blocks)
RECIPE = LOOKS[DEFAULT_LOOK]['recipe']
EPS = 1e-4
STOREYS = (1, 2)
# a wall end's styles: how far in from its tile edge its solid stops there (M3 item 2; the docstring), the default look's
def end_insets(R):
    """A look's (its recipe `R`) end styles' insets: a free end its endInset, 'line' on the tile edge, 'through' its half
    thickness past it."""
    return {'free': R['endInset'], 'line': 0.0, 'through': -R['half']}


END_INSETS = end_insets(RECIPE)


def look_of(wall):
    """The recipe of the wall's look (its numbers' `look`; left out, DEFAULT_LOOK). ValueError for one not listed."""
    name = (wall or {}).get('look', DEFAULT_LOOK)
    if name not in LOOKS:
        raise ValueError('a wall in a look not listed in wall_looks.json: %r (they are %s)' % (name, ', '.join(LOOKS)))
    return LOOKS[name]['recipe']


def ends_of(wall):
    """The wall's end styles (its x0 end's and its x1 end's, END_INSETS' keys): ('free', 'free') when left out."""
    ends = (wall or {}).get('ends')
    if ends is None:
        return ('free', 'free')
    if not isinstance(ends, (list, tuple)) or len(ends) != 2 or any(e not in END_INSETS for e in ends):
        raise ValueError('a wall\'s ends are two of %s (it has %r)' % (', '.join(END_INSETS), ends))
    return tuple(ends)


def shaped(wall):
    """The wall's look's recipe (look_of) for its height: as it is for two storeys (the donor's); for one, its top, the
    face's top and the section's corners above the face a storey lower."""
    base = look_of(wall)
    storeys = int((wall or {}).get('storeys', 2))
    if storeys not in STOREYS:
        raise ValueError('a wall of %r storeys (it has 1 or 2)' % (storeys,))
    if storeys == 2:
        return base
    drop = base['storey'] * (2 - storeys)
    face = base['face']
    return dict(base, top=base['top'] - drop, face=[face[0], face[1] - drop],
                section=[[y, z - drop if z > face[0] + 1e-6 else z, v] for y, z, v in base['section']])


# ---------------------------------------------------------------------------------------------------- 2D polygons
def clip(poly, n, d, tag):
    """The convex polygon `poly` ([((x, z), tag of the edge from this corner to the next)]) cut to n . p <= d, the cut
    edge tagged `tag`."""
    out = []
    count = len(poly)
    for k in range(count):
        (p, t), (q, _) = poly[k], poly[(k + 1) % count]
        dp = n[0] * p[0] + n[1] * p[1] - d
        dq = n[0] * q[0] + n[1] * q[1] - d
        if dp <= EPS and dq <= EPS:
            out.append((p, t))
        elif dp <= EPS < dq:
            s = dp / (dp - dq)
            i = (p[0] + s * (q[0] - p[0]), p[1] + s * (q[1] - p[1]))
            out.append((p, t))
            if s < 1 - 1e-9:
                out.append((i, tag))
        elif dq <= EPS < dp:
            s = dp / (dp - dq)
            j = (p[0] + s * (q[0] - p[0]), p[1] + s * (q[1] - p[1]))
            if s < 1 - 1e-9:
                out.append((j, t))
    # drop repeated corners
    clean = []
    for p, t in out:
        if clean and math.dist(clean[-1][0], p) < 1e-6:
            clean[-1] = (clean[-1][0], t)
            continue
        clean.append((p, t))
    if len(clean) > 1 and math.dist(clean[0][0], clean[-1][0]) < 1e-6:
        clean.pop()
    return clean if len(clean) >= 3 else []


def area(poly):
    pts = [p for p, _ in poly]
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))


def band(poly, z0, z1):
    """The part of `poly` between heights z0 and z1."""
    return clip(clip(poly, (0, -1), -z0, 'band'), (0, 1), z1, 'band') if poly else []


def insert_points(poly, points):
    """`poly` with the corners `points` put into the edges they lie on (each new piece keeps its edge's tag)."""
    out = []
    count = len(poly)
    for k in range(count):
        (p, t), (q, _) = poly[k], poly[(k + 1) % count]
        out.append((p, t))
        dx, dz = q[0] - p[0], q[1] - p[1]
        length2 = dx * dx + dz * dz
        on = {}
        for c in points:
            s = ((c[0] - p[0]) * dx + (c[1] - p[1]) * dz) / length2
            if 1e-6 < s < 1 - 1e-6 and abs((c[0] - p[0]) * dz - (c[1] - p[1]) * dx) / math.sqrt(length2) < 1e-4:
                on.setdefault(round(s * math.sqrt(length2), 4), (s, c))     # each point once
        for _, c in sorted(on.values()):
            if math.dist(out[-1][0], c) > 1e-6:
                out.append((c, t))
    return out


# ---------------------------------------------------------------------------------------------------- the section
def half_width(z, R=RECIPE):
    """The wall's half thickness at height z (the section's +y side)."""
    sec = R['section']
    if z <= sec[0][1]:
        return sec[0][0]
    for (ya, za, _), (yb, zb, _) in zip(sec, sec[1:]):
        if za <= z <= zb and zb > za:
            return ya + (z - za) * (yb - ya) / (zb - za)
    return sec[-1][0]


def section_v(z, R=RECIPE):
    """The trim set's v at height z on the section (its value at a corner shared by the face and a trim is the
    trim's)."""
    sec = R['section']
    for (ya, za, va), (yb, zb, vb) in zip(sec, sec[1:]):
        if za <= z <= zb and zb > za and not (ya == yb == R['half']):
            return va + (z - za) * (vb - va) / (zb - za)
    return sec[-1][2]


def bands(R=RECIPE):
    """The heights the section's slope changes at: every face is cut there, so each piece is flat and convex."""
    zs = sorted({z for _, z, _ in R['section']} | {R['bottom'], R['top']})
    return zs


# ---------------------------------------------------------------------------------------------------- cells
def solid_wall(wall):
    """The wall as it is built: its ends in from its tile edges by their styles (END_INSETS: a free end
    RECIPE['endInset']), its openings cut to what is left (an opening's own sides are kept: the game's doorways have
    them on the tile edges too)."""
    e0, e1 = ends_of(wall)
    insets = end_insets(look_of(wall))
    x0, x1 = float(wall['x0']) + insets[e0], float(wall['x1']) - insets[e1]
    openings = []
    for o in wall.get('openings') or ():
        a, b = max(float(o['x0']), x0), min(float(o['x1']), x1)
        if b - a > 1e-6:
            openings.append(dict(x0=a, x1=b, z0=float(o['z0']), z1=float(o['z1'])))
    return dict(wall, x0=x0, x1=x1, openings=openings)


def seeds(wall):
    rng = random.Random(wall.get('seed', 1))
    R = shaped(wall)
    x0, x1 = float(wall['x0']), float(wall['x1'])
    zb, zt = R['bottom'], R['top']
    nx = max(1, round((x1 - x0) / R['cell'][0]))
    nz = max(1, round((zt - zb) / R['cell'][1]))
    dx, dz = (x1 - x0) / nx, (zt - zb) / nz
    out = []
    for k in range(nz):
        for i in range(nx):
            jx, jz = rng.uniform(-1, 1) * R['jitter'], rng.uniform(-1, 1) * R['jitter']
            s = (x0 + (i + 0.5 + jx) * dx, zb + (k + 0.5 + jz) * dz)
            if any(o['x0'] - 1 < s[0] < o['x1'] + 1 and o['z0'] - 1 < s[1] < o['z1'] + 1 for o in wall.get('openings', ())):
                continue
            out.append(s)
    return out


def cut_opening(poly, o):
    """The convex pieces of `poly` outside the opening rectangle `o`: left of it, right of it, above and below it."""
    left = clip(poly, (1, 0), o['x0'], 'cut')
    right = clip(poly, (-1, 0), -o['x1'], 'cut')
    middle = clip(clip(poly, (-1, 0), -o['x0'], 'cut'), (1, 0), o['x1'], 'cut')
    above = clip(middle, (0, -1), -o['z1'], 'cut') if middle else []
    below = clip(middle, (0, 1), o['z0'], 'cut') if middle else []
    return [q for q in (left, right, above, below) if q and area(q) > 1e-3]


def cells(wall):
    """[(seed, convex polygon)] of the wall's fragments, before their faces are made."""
    x0, x1 = float(wall['x0']), float(wall['x1'])
    R = shaped(wall)
    zb, zt = R['bottom'], R['top']
    outline = [((x0, zb), 'out'), ((x1, zb), 'out'), ((x1, zt), 'out'), ((x0, zt), 'out')]
    pts = seeds(wall)
    out = []
    for i, s in enumerate(pts):
        poly = outline
        for j, t in enumerate(pts):
            if i == j or not poly:
                continue
            n = (t[0] - s[0], t[1] - s[1])
            d = (t[0] ** 2 + t[1] ** 2 - s[0] ** 2 - s[1] ** 2) / 2
            poly = clip(poly, n, d, 'cell')
        pieces = [poly] if poly else []
        for o in wall.get('openings', ()):
            pieces = [q for piece in pieces for q in cut_opening(piece, o)]
        out += [(s, q) for q in pieces]
    corners = [(o[a], o[b]) for o in wall.get('openings', ()) for a in ('x0', 'x1') for b in ('z0', 'z1')]
    # every corner of every piece, and the openings' corners, into the edges they lie on: no T-junctions
    every = corners + [p for _, q in out for p, _ in q]
    return [(s, insert_points(q, every)) for s, q in out]


def classify(wall, p, q):
    """What the edge p..q of a fragment is: 'x0' or 'x1' (a wall's end), 'zb' or 'zt' (its bottom or top), ('open',
    k) (an opening's side), or 'in' (an edge it shares with another fragment)."""
    x0, x1 = float(wall['x0']), float(wall['x1'])
    R = shaped(wall)
    zb, zt = R['bottom'], R['top']
    m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
    vertical, flat = abs(p[0] - q[0]) < 1e-5, abs(p[1] - q[1]) < 1e-5
    if vertical and abs(m[0] - x0) < 1e-4:
        return 'x0'
    if vertical and abs(m[0] - x1) < 1e-4:
        return 'x1'
    if flat and abs(m[1] - zb) < 1e-4:
        return 'zb'
    if flat and abs(m[1] - zt) < 1e-4:
        return 'zt'
    for k, o in enumerate(wall.get('openings', ())):
        inside = o['x0'] - 1e-4 <= m[0] <= o['x1'] + 1e-4 and o['z0'] - 1e-4 <= m[1] <= o['z1'] + 1e-4
        on = ((vertical and min(abs(m[0] - o['x0']), abs(m[0] - o['x1'])) < 1e-4)
              or (flat and min(abs(m[1] - o['z0']), abs(m[1] - o['z1'])) < 1e-4))
        if inside and on:
            return ('open', k)
    return 'in'


# ---------------------------------------------------------------------------------------------------- 3D faces
class Faces:
    """The polygons of the mesh: dict(points [(x, y, z)], normal, slot, fragment, uv0 [(u, v)], chart, cuv [(s, t)] (in
    the chart's own units))."""

    def __init__(self):
        self.polys = []
        self.charts = {}            # id -> [width, height, density]

    def chart(self, key, width, height, density=1.0):
        self.charts.setdefault(key, [width, height, density])
        return key

    def add(self, points, normal, slot, fragment, uv0, chart, cuv, interior=False):
        if len(points) < 3:
            return
        self.polys.append(dict(points=[tuple(map(float, p)) for p in points], normal=tuple(normal), slot=slot,
                               fragment=fragment, uv0=uv0, chart=chart, cuv=cuv, interior=interior))


def poly_area3(points):
    n = [0.0, 0.0, 0.0]
    for a, b in zip(points, points[1:] + points[:1]):
        n[0] += a[1] * b[2] - a[2] * b[1]
        n[1] += a[2] * b[0] - a[0] * b[2]
        n[2] += a[0] * b[1] - a[1] * b[0]
    return 0.5 * math.sqrt(sum(v * v for v in n))


def fragment_faces(wall, faces, f, poly):
    """All the faces of fragment `f` (its polygon `poly` in x, z) into `faces`; returns its edges that are inside the
    wall ([(p, q, outward normal (nx, nz))]) and how many of its edges are on the outline or an opening."""
    R = shaped(wall)
    x0, x1 = float(wall['x0']), float(wall['x1'])
    length = x1 - x0
    lo_face, hi_face = R['face']
    h = R['half']
    sa, sb, trim, inner = R['slots']['sideA'], R['slots']['sideB'], R['slots']['trim'], R['slots']['interior']
    rep, trep = R['faceRepeat'], R['trimRepeat']
    faces.chart('A', length, hi_face - lo_face)
    faces.chart('B', length, hi_face - lo_face)
    # both faces, split at the storey
    for z0, z1, k in ((lo_face, R['storey'], 0), (R['storey'], hi_face, 1)):
        part = band(poly, z0, z1)
        if not part:
            continue
        pts = [p for p, _ in part]
        faces.add([(x, h, z) for x, z in pts], (0, 1, 0), sa[k], f,
                  [(x / rep + R['faceU'], R['faceV'][0] - z / rep) for x, z in pts], 'A',
                  [(x - x0, z - lo_face) for x, z in pts])
        faces.add([(x, -h, z) for x, z in pts], (0, -1, 0), sb[k], f,
                  [(-x / rep + R['faceU'], R['faceV'][1] - z / rep) for x, z in pts], 'B',
                  [(x1 - x, z - lo_face) for x, z in pts])
    # the trim strips: each sloping or upright stretch of the section, on both sides, outside the face
    sec = R['section']
    for k, ((ya, za, va), (yb, zb, vb)) in enumerate(zip(sec, sec[1:])):
        if zb <= za or (ya == yb == h):
            continue
        part = band(poly, za, zb)
        if not part:
            continue
        seg = math.hypot(yb - ya, zb - za)
        for side in (1, -1):
            pts = []
            for x, z in [p for p, _ in part]:
                t = (z - za) / (zb - za)
                pts.append((x, side * (ya + t * (yb - ya)), z, t))
            normal = (0.0, side * (zb - za) / seg, -(yb - ya) / seg)
            chart = faces.chart(('trim', k, side), length, seg)
            faces.add([p[:3] for p in pts], normal, trim, f,
                      [(side * -(p[0] / trep) - side * R['trimU'], va + p[3] * (vb - va)) for p in pts], chart,
                      [(p[0] - x0, p[3] * seg) for p in pts])
    # its edges: the top and bottom, the wall's ends, the openings' sides, and the edges inside
    inside, outside = [], 0
    pts = [p for p, _ in poly]
    count = len(pts)
    for k in range(count):
        p, q = pts[k], pts[(k + 1) % count]
        kind = classify(wall, p, q)
        if math.dist(p, q) < 1e-6:
            continue
        # the outward normal of the edge in (x, z): the polygon runs anticlockwise
        dx, dz = q[0] - p[0], q[1] - p[1]
        ln = math.hypot(dx, dz)
        nx, nz = dz / ln, -dx / ln
        if kind != 'in':
            outside += 1
        if kind in ('zt', 'zb'):
            top = kind == 'zt'
            z = R['top'] if top else R['bottom']
            w = half_width(z, R)
            a, b = sorted((p[0], q[0]))
            quad = [(a, -w, z), (b, -w, z), (b, w, z), (a, w, z)]
            coef = R['topV'] if top else R['bottomV']
            chart = faces.chart(('cap', kind), length, 2 * w)
            faces.add(quad, (0, 0, 1 if top else -1), trim, f,
                      [(-x / trep, coef[0] + coef[1] * y) for x, y, _ in quad], chart,
                      [(x - x0, y + w) for x, y, _ in quad])
            continue
        if kind == 'in':
            inside.append((p, q, (nx, nz)))
            continue
        # a wall's end or an opening's side: the section across the edge
        if abs(dx) < 1e-6:          # upright: x = const, z from a to b
            c = p[0]
            a, b = sorted((p[1], q[1]))
            cuts = sorted({a, b} | {z for z in bands(R) + [R['storey']] if a < z < b})
            key = ('end', kind if isinstance(kind, str) else kind[1], round(c, 3), round(a, 3))
            wmax = max(half_width(z, R) for z in cuts)
            chart = faces.chart(key, 2 * wmax, b - a)
            for z0, z1 in zip(cuts, cuts[1:]):
                w0, w1 = half_width(z0, R), half_width(z1, R)
                quad = [(c, -w0, z0), (c, w0, z0), (c, w1, z1), (c, -w1, z1)]
                face_zone = z0 >= lo_face - 1e-6 and z1 <= hi_face + 1e-6
                if face_zone:
                    slot = sa[0] if z1 <= R['storey'] + 1e-6 else sa[1]
                    uv = [(nx * y / rep + R['faceU'], R['faceV'][0] - z / rep) for _, y, z in quad]
                else:
                    slot = trim
                    uv = [(nx * y / trep, section_v(z, R)) for _, y, z in quad]
                faces.add(quad, (nx, 0, nz), slot, f, uv, chart, [(y + wmax, z - a) for _, y, z in quad])
        else:                       # flat: an opening's lintel or sill, z = const
            z = p[1]
            a, b = sorted((p[0], q[0]))
            w = half_width(z, R)
            quad = [(a, -w, z), (b, -w, z), (b, w, z), (a, w, z)]
            face_zone = lo_face - 1e-6 <= z <= hi_face + 1e-6
            slot = (sa[0] if z < R['storey'] else sa[1]) if face_zone else trim
            chart = faces.chart(('flat', kind[1], round(z, 3), round(a, 3)), b - a, 2 * w)
            faces.add(quad, (0, 0, nz), slot, f, [(x / rep + R['faceU'], y / rep) for x, y, _ in quad], chart,
                      [(x - a, y + w) for x, y, _ in quad])
    return inside, outside


def interior_face(faces, f, p, q, normal, key, R=RECIPE):
    """The face inside the wall on the edge p..q of fragment f: the section across it, flat pieces between the
    section's bends (R: the wall's shaped recipe). Returns its area."""
    length = math.dist(p, q)
    za, zb = p[1], q[1]
    ts = {0.0, 1.0}
    if abs(zb - za) > 1e-9:
        for z in bands(R) + [R['storey']]:       # (the faces split at the storey too: no T-junction there)
            t = (z - za) / (zb - za)
            if 0 < t < 1:
                ts.add(t)
    ts = sorted(ts)
    wmax = max(half_width(za + t * (zb - za), R) for t in ts)
    chart = faces.chart(key, length, 2 * wmax, R['lightmap']['interiorDensity'])
    total = 0.0
    for t0, t1 in zip(ts, ts[1:]):
        P0 = (p[0] + t0 * (q[0] - p[0]), p[1] + t0 * (q[1] - p[1]))
        P1 = (p[0] + t1 * (q[0] - p[0]), p[1] + t1 * (q[1] - p[1]))
        w0, w1 = half_width(P0[1], R), half_width(P1[1], R)
        quad = [(P0[0], -w0, P0[1]), (P1[0], -w1, P1[1]), (P1[0], w1, P1[1]), (P0[0], w0, P0[1])]
        tt = [t0, t1, t1, t0]
        faces.add(quad, (normal[0], 0.0, normal[1]), R['slots']['interior'], f,
                  [(t, (wmax - y) / (2 * wmax)) for t, (_, y, _) in zip(tt, quad)], chart,
                  [(t * length, y + wmax) for t, (_, y, _) in zip(tt, quad)], interior=True)
        total += poly_area3(quad)
    return total


def shared(edges):
    """For each fragment's inside edges, the other fragments along them: {(fragment, edge index): [(fragment,
    overlap length)]}: edges on one line running the other way, overlapping."""
    out = {}
    for f, items in edges.items():
        for k, (p, q, n) in enumerate(items):
            d = (q[0] - p[0], q[1] - p[1])
            ln = math.hypot(*d)
            u = (d[0] / ln, d[1] / ln)
            found = []
            for g, others in edges.items():
                if g == f:
                    continue
                for (r, s, m) in others:
                    if n[0] * m[0] + n[1] * m[1] > -0.999:
                        continue
                    if abs((r[0] - p[0]) * u[1] - (r[1] - p[1]) * u[0]) > 1e-3:
                        continue
                    a = sorted(((r[0] - p[0]) * u[0] + (r[1] - p[1]) * u[1], (s[0] - p[0]) * u[0] + (s[1] - p[1]) * u[1]))
                    over = min(ln, a[1]) - max(0.0, a[0])
                    if over > 1e-3:
                        found.append((g, over))
            out[f, k] = found
    return out


# ---------------------------------------------------------------------------------------------------- the lightmap
def pack_rect(charts, density, margin, block=4):
    """{chart: (u0, v0)} and (width, height) for `charts` ({id: [w, h, chart density]}, in units) at `density`
    texels a unit: shelf-packed in texels, tallest first, `margin` texels round each, into the smallest rectangle of
    the widths tried (from the widest chart to the whole row), its sides rounded up to whole `block`s. The origins
    are in the rectangle's own 0..1."""
    order = sorted(charts, key=lambda k: (-charts[k][1] * charts[k][2], -charts[k][0] * charts[k][2], str(k)))
    sizes = {k: (charts[k][0] * density * charts[k][2] + margin, charts[k][1] * density * charts[k][2] + margin)
             for k in order}

    def place(width):
        x = y = row = 0.0
        out = {}
        for k in order:
            w, h = sizes[k]
            if x + w > width + 1e-9:
                x, y, row = 0.0, y + row, 0.0
            out[k] = (x + margin / 2, y + margin / 2)
            x += w
            row = max(row, h)
        return out, y + row
    widest = max(w for w, _ in sizes.values())
    total = sum(w for w, _ in sizes.values())
    best = None
    steps = 48
    for i in range(steps + 1):
        width = widest + (total - widest) * (i / steps) ** 2
        out, height = place(width)
        w = block * math.ceil(width / block)
        h = block * math.ceil(height / block)
        if best is None or w * h < best[1] * best[2] or (w * h == best[1] * best[2] and abs(w - h) < abs(best[1] - best[2])):
            best = (out, w, h)
    out, w, h = best
    return {k: (u / w, v / h) for k, (u, v) in out.items()}, (w, h)


# ---------------------------------------------------------------------------------------------------- collision
def solids(wall):
    """The collision boxes [(lo, hi)]: the slab (the donor's 16 thick) cut into upright strips at every opening's
    sides, each strip's stretches clear of openings one box, neighbouring strips with the same stretches joined."""
    x0, x1 = float(wall['x0']), float(wall['x1'])
    R = shaped(wall)
    zb, zt = R['bottom'], R['top']
    hy = R['collisionHalf']
    openings = wall.get('openings', ())
    xs = sorted({x0, x1} | {o[k] for o in openings for k in ('x0', 'x1') if x0 < o[k] < x1})
    strips = []
    for a, b in zip(xs, xs[1:]):
        m = (a + b) / 2
        holes = sorted((o['z0'], o['z1']) for o in openings if o['x0'] < m < o['x1'])
        runs, z = [], zb
        for h0, h1 in holes:
            if h0 > z + 1e-6:
                runs.append((z, min(h0, zt)))
            z = max(z, h1)
        if z < zt - 1e-6:
            runs.append((z, zt))
        if strips and strips[-1][2] == runs and abs(strips[-1][1] - a) < 1e-6:
            strips[-1][1] = b
        else:
            strips.append([a, b, runs])
    return [((a, -hy, z0), (b, hy, z1)) for a, b, runs in strips for z0, z1 in runs]


# ---------------------------------------------------------------------------------------------------- packing it all
def _packed(v, w):
    return bytes(max(0, min(255, int(round(x * 127.5 + 127.5)))) for x in v) + bytes([w])


def _sub(a, b):
    return [x - y for x, y in zip(a, b)]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _norm(v):
    n = math.sqrt(_dot(v, v))
    return [x / n for x in v] if n > 1e-12 else [0.0, 0.0, 0.0]


def collinear_corner(points):
    """Whether any corner of the flat polygon `points` lies on the straight line between its neighbours."""
    n = len(points)
    for k in range(n):
        a, b, c = points[k - 1], points[k], points[(k + 1) % n]
        cr = _cross(_sub(b, a), _sub(c, b))
        if math.sqrt(_dot(cr, cr)) < 1e-6 * max(1.0, math.dist(a, b) * math.dist(b, c)):
            return True
    return False


def tangent_frame(points, uvs, normal):
    """The tangent (the direction u grows along the face, made square to the normal) and the binormal's sign (1 when
    cross(normal, tangent) runs the way v grows), as UE3 keeps them."""
    p0, p1, p2 = points[0], points[1], points[2]
    e1, e2 = _sub(p1, p0), _sub(p2, p0)
    du1, dv1 = uvs[1][0] - uvs[0][0], uvs[1][1] - uvs[0][1]
    du2, dv2 = uvs[2][0] - uvs[0][0], uvs[2][1] - uvs[0][1]
    det = du1 * dv2 - du2 * dv1
    if abs(det) < 1e-12:
        t = _norm(_cross([0, 0, 1], normal)) if abs(normal[2]) < 0.9 else [1.0, 0.0, 0.0]
        return t, 1
    r = 1.0 / det
    t = [(e1[k] * dv2 - e2[k] * dv1) * r for k in range(3)]
    b = [(e2[k] * du1 - e1[k] * du2) * r for k in range(3)]
    t = _norm(_sub(t, [normal[k] * _dot(normal, t) for k in range(3)]))
    sign = 1 if _dot(_cross(normal, t), b) >= 0 else -1
    return t, sign


def default_template():
    """The fields of a mesh other than its geometry, as the donor saves them (tests/test_frac_wall.py checks them
    against the donor): gen_mesh's form with no vertices."""
    lod = dict(sections=[], positionHead=[12, 0], positionStride=12, positions=[], texcoords=2, vertexStride=16,
               fullUVs=0, vertexHead=0, vertices=[], colourHead=[4, 0], colourArray=(4, 0), colours=[], vertexCount=0,
               indices=(2, []), wireframe=(2, []), adjacency=(2, []))
    return dict(kind='fractured', bounds=(0.0,) * 7, bodySetup=0, kdop=None, version=18, optimisation=[], simplified=0,
                lods=[lod], tail=dict(lodInfo=1, thumbnail=bytes(16), source=(0, b''), crc=0, guid=bytes(16),
                                      positionsVersion=2, factors=[125.32816314697266, 808.2366333007812, 0.0, 0.0],
                                      removeDegenerates=1),
                fractured=dict(sourceMesh=0, fragments=[], core=-1, interior=5, coreScale=(0.0, 0.0, 0.0),
                               coreOffset=(0.0, 0.0, 0.0), coreRotation=(0, 0, 0), planeBias=(1.0, 1.0, 1.0),
                               versions=(3, 1)))


def build(wall, template=None):
    """The mesh of `wall` (gen_mesh's form) on the donor's decoded mesh `template` (its fields other than the
    geometry: the stream layouts, versions, the fracturing tail; default_template() when None), with dict(fragments,
    solids, counts)."""
    R = shaped(wall)
    template = template or default_template()
    wall = solid_wall(wall)
    faces = Faces()
    found = cells(wall)
    edges = {}
    outer = {}
    for f, (_, poly) in enumerate(found):
        if area(poly) < 0:
            poly = poly[::-1]
        edges[f], outer[f] = fragment_faces(wall, faces, f, poly)
    neighbours = shared(edges)
    records = []
    for f, (seed, _) in enumerate(found):
        # no fragment across the two faces and the edges on the wall's outline or an opening (as the donor's records
        # start with their outside faces), then each edge inside the wall
        nb, dims = [-1] * (2 + outer[f]), [0.0] * (2 + outer[f])
        for k, (p, q, n) in enumerate(edges[f]):
            a = interior_face(faces, f, p, q, n, ('in', f, k), R)
            across = neighbours.get((f, k)) or []
            if not across:
                nb.append(-1)
                dims.append(0.0)
            for g, over in across:
                nb.append(g)
                dims.append(a * over / math.dist(p, q))
        records.append(dict(seed=seed, neighbours=nb, dims=dims))
    for rec in records:
        rec['centre'] = (rec['seed'][0], 0.0, rec['seed'][1])
    guid = hashlib.md5(('frac_wall|%r' % (sorted(wall.items(), key=str),)).encode()).digest()
    out = assemble(faces, records, template, R, guid, slots=6, what='a wall')
    return dict(out, solids=solids(wall))


def assemble(faces, records, template, R, guid, slots=6, what='a mesh'):
    """The fractured mesh (gen_mesh's form) of the polygons `faces` (Faces: each with its slot, fragment, uv0, chart and
    chart coordinates, and optionally a colour for each corner, else the recipe's outside or interior colour) and the
    fragment records `records` ([dict(centre (x, y, z), neighbours, dims)]), on the donor's decoded mesh `template`,
    with the recipe `R`'s lightmap packing and colours, `slots` sections and the tail's `guid`: dict(mesh, fragments
    (their boxes), lightmapRect, counts). frac_wall.build and frac_slab.build make theirs with it."""
    L = R['lightmap']
    origins, rect = pack_rect(faces.charts, L['density'], L['margin'], L['block'])
    # the vertices and triangles, slot by slot and fragment by fragment
    nfrag = len(records)
    by_slot = {s: [[] for _ in range(nfrag)] for s in range(slots)}
    for poly in faces.polys:
        by_slot[poly['slot']][poly['fragment']].append(poly)
    positions, vertices, colours, indices, kdop = [], [], [], [], []
    sections = []
    out_colour, in_colour = bytes.fromhex(R['colours']['outside']), bytes.fromhex(R['colours']['interior'])
    frag_points = [[] for _ in range(nfrag)]
    ext_normal = [[0.0, 0.0, 0.0] for _ in range(nfrag)]
    for slot in range(slots):
        first = len(indices)
        ranges = []
        lo_v, hi_v = None, None
        for f in range(nfrag):
            start = len(indices)
            for poly in by_slot[slot][f]:
                pts, n = poly['points'], poly['normal']
                t, sign = tangent_frame(pts, poly['uv0'], n)
                base = len(positions)
                u0, v0 = origins[poly['chart']]
                density = faces.charts[poly['chart']][2]
                uv0s, cuvs = poly['uv0'], poly['cuv']
                if collinear_corner(pts):
                    # a corner on a straight run (where a neighbour's corner meets this edge): fanned from the centre,
                    # so no triangle is a sliver of no area. Everything here is affine on the face: the centre's
                    # values are the corners' means
                    def mean(rows):
                        return tuple(sum(r[k] for r in rows) / len(rows) for k in range(len(rows[0])))
                    pts = [mean(pts)] + list(pts)
                    uv0s, cuvs = [mean(uv0s)] + list(uv0s), [mean(cuvs)] + list(cuvs)
                    if poly.get('colours'):
                        poly = dict(poly, colours=[poly['colours'][0]] + list(poly['colours']))
                for k, (p, uv, c) in enumerate(zip(pts, uv0s, cuvs)):
                    positions.append(struct.unpack('<3f', struct.pack('<3f', *p)))
                    lm = (u0 + c[0] * L['density'] * density / rect[0], v0 + c[1] * L['density'] * density / rect[1])
                    vertices.append((_packed(t, 0x80), _packed(n, 0xFF if sign > 0 else 0x00),
                                     [tuple(uv), lm]))
                    colours.append(poly['colours'][k] if poly.get('colours')
                                   else in_colour if poly['interior'] else out_colour)
                    frag_points[f].append(p)
                if not poly['interior']:
                    a3 = poly_area3(pts)
                    for k in range(3):
                        ext_normal[f][k] += n[k] * a3
                if len(pts) > len(poly['points']):      # fanned from the centre, round the whole ring
                    fan = [(0, k, k % (len(pts) - 1) + 1) for k in range(1, len(pts))]
                else:
                    fan = [(0, k, k + 1) for k in range(1, len(pts) - 1)]
                for a, b, c in fan:
                    tri = [base + a, base + b, base + c]
                    # UE3's front faces: cross(b - a, c - a) against the outward normal
                    if _dot(_cross(_sub(pts[b], pts[a]), _sub(pts[c], pts[a])), n) > 0:
                        tri = [tri[0], tri[2], tri[1]]
                    indices += tri
                    kdop.append(tuple(tri) + (gen_mesh.kdop_value(slot, f, nfrag),))
                lo_v = base if lo_v is None else min(lo_v, base)
                hi_v = len(positions) - 1
            count = (len(indices) - start) // 3
            ranges.append((start, count) if count else (0, 0))
        sections.append(dict(material=0, collision=1, oldCollision=1, shadow=1, first=first,
                             triangles=(len(indices) - first) // 3, minVertex=lo_v or 0, maxVertex=hi_v or 0,
                             slot=slot, fragments=ranges, platform=0))
    if len(positions) > 65535:
        raise ValueError('%s of %d vertices: more than 16-bit indices hold' % (what, len(positions)))
    lod = dict(template['lods'][0])
    nv = len(positions)
    lod.update(sections=sections, positionHead=[12, nv], positionStride=12, positions=positions,
               vertexHead=nv, vertices=vertices, colourHead=[4, nv], colourArray=(4, nv), colours=colours,
               vertexCount=nv, indices=(2, indices), wireframe=(2, []), adjacency=(2, []))
    if lod['texcoords'] != 2 or lod['fullUVs']:
        raise ValueError('the template\'s vertex layout is not two half-float channels')
    frags = []
    for f, rec in enumerate(records):
        pts = frag_points[f]
        lo = [min(p[k] for p in pts) for k in range(3)]
        hi = [max(p[k] for p in pts) for k in range(3)]
        centre = [(a + b) / 2 for a, b in zip(lo, hi)]
        halfs = [(b - a) / 2 for a, b in zip(lo, hi)]
        n = ext_normal[f]
        ln = math.sqrt(_dot(n, n))
        normal = [v / ln for v in n] if ln > 1e-3 else [0.0, 1.0, 0.0]
        frags.append(dict(centre=tuple(rec['centre']), box=(0.0,) * 6 + (0,),
                          bounds=tuple(struct.unpack('<7f', struct.pack('<7f', *centre, *halfs,
                                                                        math.sqrt(_dot(halfs, halfs))))),
                          neighbours=rec['neighbours'], destroyable=1, root=0, neverSpawn=0,
                          normal=tuple(normal), dims=rec['dims'], extra=-1))
    mesh = dict(template)
    mesh.pop('at', None)
    mesh.pop('start', None)
    mesh['bounds'] = gen_mesh.bounds_of(positions)
    mesh['kdop'] = gen_mesh.kdop_tree(positions, kdop)
    mesh['lods'] = [lod]
    tail = dict(template['tail'])
    tail['guid'] = guid
    mesh['tail'] = tail
    fr = dict(template['fractured'])
    fr.update(fragments=frags, core=-1, interior=R['slots'].get('interior', R.get('interior')), sourceMesh=0)
    mesh['fractured'] = fr
    boxes = []
    for f, pts in enumerate(frag_points):
        boxes.append(dict(box=[v for k in range(3) for v in (min(p[k] for p in pts), max(p[k] for p in pts))]))
    return dict(mesh=mesh, fragments=boxes, lightmapRect=list(rect),
                counts=dict(fragments=nfrag, vertices=nv, triangles=len(indices) // 3, charts=len(faces.charts)))


def mesh_name(wall):
    """A name for the wall's mesh from its numbers and the recipe: the same wall is the same mesh in every build, and
    a changed recipe never reuses a name (the meshes are forced exports, one object per name in the game)."""
    digest = hashlib.sha256(repr((sorted((k, repr(v)) for k, v in look_of(wall).items()),
                                  sorted((k, repr(v)) for k, v in wall.items()))).encode()).hexdigest()
    return 'FracWall_%d_%s' % (round(float(wall['x1']) - float(wall['x0'])), digest[:10])
