"""A fracturing floor or roof slab made from numbers, built the way the game's own are (custom geometry plan, stage M5;
research/evidence/slab-audit.py measured them).

A slab is made in a look (slab_looks.json: LOOKS; the first, DEFAULT_LOOK, the ComKit roof URB_Bar's roof is laid in),
and its numbers are dict(x0, x1, y0, y1 (its footprint's tile edges in the donor mesh's frame), holes [dict(x0, x1, y0,
y1)] (whole tiles left out: a stairwell, a skylight), seed (the fragments' pattern: the same slab is always the same
mesh), look). What the game's slabs are, and so these:

  shape       a flat plate between the look's bottom and top (4 thick for a roof, 2 for a storey floor), on its own
              96 grid; no faces inside: two slots, the top with the outer edges and the holes' sides (slot 0), the
              underside (slot 1); the interior index past them (2), as the donors save it
  fragments   whole tiles, a tile's two halves cut on a diagonal, or two tiles side by side (the roofs' fragments are
              groups of half tiles, 0.5 to 4 tiles: research/evidence/slab-audit-2026-11-18.json), each through the
              whole thickness, all destroyable, none a root; a record's neighbours the fragments across its inside
              edges after one entry of -1 for each of its outside faces, every dims 1, as the donors' records are
  texture     192 units a repeat on the top and the underside (the look's offsets and the underside mirrored in x);
              an edge's along it and up
  colours     each vertex the colour of the donor's nearest vertex of the same face kind, the donor's footprint
              repeated (the blend materials read the blue channel for a destruction ramp); without a donor, the look's
  collision   one box over each solid rectangle round the holes, between the look's collision heights (a roof's 2 thick
              under its drawn top, a floor's the whole plate)
  lightmap    a chart for the top, one for the underside and one for each edge line, at the look's density, packed as
              a wall's are (frac_wall.pack_rect)

build(slab, template) gives frac_wall.build's form: dict(mesh, fragments (their boxes), solids, lightmapRect, counts)."""
import hashlib
import json
import math
from pathlib import Path
import random

import frac_wall

LOOKS_FILE = Path(__file__).resolve().parent / 'slab_looks.json'
DEFAULT_LOOK = 'roof'
MAX_TILES = 16
EPS = 1e-4


def _looks():
    out = {}
    for look in json.loads(LOOKS_FILE.read_text(encoding='utf-8'))['looks']:
        out[look['id']] = dict(look, recipe=dict(look['recipe'], version=look['version'], donor=look['donor'],
                                                 role=look['role']))
    return out


LOOKS = _looks()


def look_of(slab):
    name = (slab or {}).get('look', DEFAULT_LOOK)
    if name not in LOOKS:
        raise ValueError('a slab in a look not listed in slab_looks.json: %r (they are %s)' % (name, ', '.join(LOOKS)))
    return LOOKS[name]['recipe']


def check(slab):
    """The slab's numbers checked (ValueError): a footprint of whole tiles, 1 to MAX_TILES each way; holes of whole
    tiles inside it, apart; a whole seed; a listed look. Returns its tiles (nx, ny)."""
    R = look_of(slab)
    t = R['tile']
    if not isinstance(slab, dict) or not all(isinstance(slab.get(k), (int, float)) for k in ('x0', 'x1', 'y0', 'y1')):
        raise ValueError('a slab needs its footprint, x0, x1, y0 and y1')
    nx, ny = (slab['x1'] - slab['x0']) / t, (slab['y1'] - slab['y0']) / t
    if not all(abs(n - round(n)) < EPS and 1 <= round(n) <= MAX_TILES for n in (nx, ny)):
        raise ValueError('a slab is 1 to %d whole tiles each way (it has %g by %g)' % (MAX_TILES, nx, ny))
    if not isinstance(slab.get('seed', 1), int) or isinstance(slab.get('seed', 1), bool):
        raise ValueError("a slab's seed is a whole number")
    for h in slab.get('holes') or []:
        if not (isinstance(h, dict) and all(isinstance(h.get(k), (int, float)) for k in ('x0', 'x1', 'y0', 'y1'))):
            raise ValueError('a hole needs its sides: %r' % (h,))
        if not (slab['x0'] <= h['x0'] < h['x1'] <= slab['x1'] and slab['y0'] <= h['y0'] < h['y1'] <= slab['y1']):
            raise ValueError('a hole outside its slab: %r' % (h,))
        for v, base in ((h['x0'], slab['x0']), (h['x1'], slab['x0']), (h['y0'], slab['y0']), (h['y1'], slab['y0'])):
            if abs((v - base) / t - round((v - base) / t)) > EPS:
                raise ValueError('a hole of whole tiles: %r' % (h,))
    return int(round(nx)), int(round(ny))


def tiles(slab):
    """The slab's solid tiles: {(i, j)} counted from its (x0, y0) corner, the holes' left out."""
    R = look_of(slab)
    t = R['tile']
    nx, ny = check(slab)
    out = set()
    for i in range(nx):
        for j in range(ny):
            cx, cy = slab['x0'] + (i + 0.5) * t, slab['y0'] + (j + 0.5) * t
            if not any(h['x0'] < cx < h['x1'] and h['y0'] < cy < h['y1'] for h in slab.get('holes') or []):
                out.add((i, j))
    return out


def fragments(slab):
    """The fragments' outlines: [[(x, y)] anticlockwise], from the seed: tiles in a shuffled order, each still free
    becomes two halves cut on a diagonal (the look's `split` share), or one of two tiles side by side with a free
    neighbour (its `long` share), else a whole tile. Every outline carries a corner at each tile corner on its sides, so
    neighbours' edges meet exactly."""
    R = look_of(slab)
    t = R['tile']
    solid = tiles(slab)
    rng = random.Random(slab.get('seed', 1))
    order = sorted(solid)
    rng.shuffle(order)
    taken, out = set(), []

    def at(i, j):
        return (slab['x0'] + i * t, slab['y0'] + j * t)
    for i, j in order:
        if (i, j) in taken:
            continue
        r = rng.random()
        taken.add((i, j))
        if r < R['split']:
            a, b, c, d = at(i, j), at(i + 1, j), at(i + 1, j + 1), at(i, j + 1)
            if rng.random() < 0.5:
                out += [[a, b, c], [a, c, d]]
            else:
                out += [[a, b, d], [b, c, d]]
            continue
        if r < R['split'] + R['long']:
            ways = [(1, 0), (0, 1)]
            rng.shuffle(ways)
            for di, dj in ways:
                if (i + di, j + dj) in solid and (i + di, j + dj) not in taken:
                    taken.add((i + di, j + dj))
                    if di:
                        out.append([at(i, j), at(i + 1, j), at(i + 2, j), at(i + 2, j + 1), at(i + 1, j + 1), at(i, j + 1)])
                    else:
                        out.append([at(i, j), at(i + 1, j), at(i + 1, j + 1), at(i + 1, j + 2), at(i, j + 2), at(i, j + 1)])
                    break
            else:
                out.append([at(i, j), at(i + 1, j), at(i + 1, j + 1), at(i, j + 1)])
            continue
        out.append([at(i, j), at(i + 1, j), at(i + 1, j + 1), at(i, j + 1)])
    return out


def _key(p):
    return (round(p[0], 3), round(p[1], 3))


def solids(slab):
    """The collision boxes [(lo, hi)]: the footprint cut into strips at the holes' x sides, each strip's runs clear of
    holes one box, neighbouring strips with the same runs joined; between the look's collision heights."""
    R = look_of(slab)
    z0, z1 = R['collision']
    holes = slab.get('holes') or []
    xs = sorted({slab['x0'], slab['x1']} | {h[k] for h in holes for k in ('x0', 'x1')})
    strips = []
    for a, b in zip(xs, xs[1:]):
        m = (a + b) / 2
        cut = sorted((h['y0'], h['y1']) for h in holes if h['x0'] < m < h['x1'])
        runs, y = [], slab['y0']
        for h0, h1 in cut:
            if h0 > y + EPS:
                runs.append((y, h0))
            y = max(y, h1)
        if y < slab['y1'] - EPS:
            runs.append((y, slab['y1']))
        if strips and strips[-1][2] == runs and abs(strips[-1][1] - a) < EPS:
            strips[-1][1] = b
        else:
            strips.append([a, b, runs])
    return [((a, y0, z0), (b, y1, z1)) for a, b, runs in strips for y0, y1 in runs]


class Paint:
    """The donor's vertex colours by face kind ('top', 'underside', 'edge') and place, for the new vertices: the
    nearest of the donor's vertices of that kind, with the new one's x and y brought into the donor's footprint
    (repeated)."""

    def __init__(self, template):
        self.kinds = {}
        lod = (template or {}).get('lods', [{}])[0]
        pos, verts, cols = lod.get('positions') or [], lod.get('vertices') or [], lod.get('colours') or []
        if not pos or len(cols) != len(pos):
            return
        xs, ys = [p[0] for p in pos], [p[1] for p in pos]
        self.lo, self.size = (min(xs), min(ys)), (max(max(xs) - min(xs), 1.0), max(max(ys) - min(ys), 1.0))
        for p, v, c in zip(pos, verts, cols):
            nz = (v[1][2] - 127.5) / 127.5
            kind = 'top' if nz > 0.7 else 'underside' if nz < -0.7 else 'edge'
            self.kinds.setdefault(kind, []).append((p[0], p[1], bytes(c)))

    def colour(self, kind, x, y, default):
        found = self.kinds.get(kind)
        if not found:
            return default
        x = self.lo[0] + (x - self.lo[0]) % self.size[0]
        y = self.lo[1] + (y - self.lo[1]) % self.size[1]
        return min(found, key=lambda q: (q[0] - x) ** 2 + (q[1] - y) ** 2)[2]


def default_template():
    """A slab donor's fields other than its geometry (frac_wall.default_template's, its interior index the slabs')."""
    t = frac_wall.default_template()
    t['fractured'] = dict(t['fractured'], interior=2)
    return t


def build(slab, template=None):
    """The mesh of `slab` (gen_mesh's form) on the donor's decoded mesh `template` (default_template() when None), with
    dict(fragments, solids, lightmapRect, counts)."""
    R = look_of(slab)
    check(slab)
    template = template or default_template()
    paint = Paint(template)
    rep, t = R['repeat'], R['tile']
    zb, zt = R['bottom'], R['top']
    top_slot, under_slot = R['slots']['top'], R['slots']['underside']
    default = bytes.fromhex(R['colours']['outside'])
    outlines = fragments(slab)
    # every edge's owners: an edge two fragments share is inside (no face: the game's slabs have none), else outside
    owners = {}
    for f, poly in enumerate(outlines):
        for k in range(len(poly)):
            a, b = _key(poly[k]), _key(poly[(k + 1) % len(poly)])
            owners.setdefault(frozenset((a, b)), []).append(f)
    faces = frac_wall.Faces()
    w, h = slab['x1'] - slab['x0'], slab['y1'] - slab['y0']
    faces.chart('top', w, h)
    faces.chart('underside', w, h)
    su, sv, du, dv = R['topUV']
    bu, bv, eu, ev = R['undersideUV']
    records = []
    for f, poly in enumerate(outlines):
        top = [(x, y, zt) for x, y in poly]
        faces.add(top, (0, 0, 1), top_slot, f, [(su * x / rep + du, sv * y / rep + dv) for x, y, _ in top], 'top',
                  [(x - slab['x0'], y - slab['y0']) for x, y, _ in top])
        faces.polys[-1]['colours'] = [paint.colour('top', x, y, default) for x, y, _ in top]
        under = [(x, y, zb) for x, y in reversed(poly)]
        faces.add(under, (0, 0, -1), under_slot, f, [(bu * x / rep + eu, bv * y / rep + ev) for x, y, _ in under],
                  'underside', [(x - slab['x0'], y - slab['y0']) for x, y, _ in under])
        faces.polys[-1]['colours'] = [paint.colour('underside', x, y, default) for x, y, _ in under]
        outside, across = 0, []
        for k in range(len(poly)):
            p, q = poly[k], poly[(k + 1) % len(poly)]
            shared = [g for g in owners[frozenset((_key(p), _key(q)))] if g != f]
            if shared:
                across += shared
                continue
            outside += 1
            dx, dy = q[0] - p[0], q[1] - p[1]
            ln = math.hypot(dx, dy)
            n = (dy / ln, -dx / ln, 0.0)
            along = 0 if abs(dx) >= abs(dy) else 1
            line = round(p[1 - along], 3)
            chart = faces.chart(('edge', along, line, n[1 - along] > 0), (w, h)[along], zt - zb)
            start = (slab['x0'], slab['y0'])[along]
            quad = [(p[0], p[1], zb), (q[0], q[1], zb), (q[0], q[1], zt), (p[0], p[1], zt)]
            faces.add(quad, n, top_slot, f, [(pt[along] / rep, pt[2] / rep) for pt in quad], chart,
                      [(pt[along] - start, pt[2] - zb) for pt in quad])
            faces.polys[-1]['colours'] = [paint.colour('edge', pt[0], pt[1], default) for pt in quad]
        cx = sum(x for x, _ in poly) / len(poly)
        cy = sum(y for _, y in poly) / len(poly)
        nb = [-1] * (2 + outside) + sorted(set(across))
        records.append(dict(centre=(cx, cy, (zb + zt) / 2), neighbours=nb, dims=[1.0] * len(nb)))
    guid = hashlib.md5(('frac_slab|%r' % (sorted(slab.items(), key=str),)).encode()).digest()
    out = frac_wall.assemble(faces, records, template, R, guid, slots=R['sections'], what='a slab')
    return dict(out, solids=solids(slab))


def local_box(slab):
    """The box the slab stands in, in its mesh's frame."""
    R = look_of(slab)
    return [float(slab['x0']), float(slab['x1']), float(slab['y0']), float(slab['y1']), R['bottom'], R['top']]


def mesh_name(slab):
    """A name for the slab's mesh from its numbers and its look's recipe (as frac_wall.mesh_name)."""
    digest = hashlib.sha256(repr((sorted((k, repr(v)) for k, v in look_of(slab).items()),
                                  sorted((k, repr(v)) for k, v in slab.items()))).encode()).hexdigest()
    return 'FracSlab_%dx%d_%s' % (round((slab['x1'] - slab['x0']) / 96), round((slab['y1'] - slab['y0']) / 96), digest[:10])
