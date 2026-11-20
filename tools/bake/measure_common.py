"""What the look measurers share (custom geometry plan, M4: slab_measure.py, ground_measure.py): finding a donor's
placing in a map, the placing's scale and lightmap, a mesh's triangles by slot with their outward normals, and the
texture's layout on a set of faces.

A texture's layout on faces is a planar map, u = a x + b y + c and v = d x + e y + f (x and y the faces' own two axes
in world units), measured robustly: each triangle's gradient of u and of v (on a sloping face, the gradient in its
plane laid flat, so a repeat keeps its true length), the area-weighted median of each coefficient, and the offsets the
area-weighted circular median (a texture repeats, so offsets are kept modulo 1). `spread` says how well the map fits:
the area-weighted 90th percentile of each vertex's distance from it, modulo 1 (0 for a texture laid evenly across
every face; more where it is laid out piece by piece)."""
import math
import struct

import numpy as np

PL = 'TheWorld.PersistentLevel.'
CONSTANT = 1e6      # a texture coordinate that repeats over more world units than this doesn't change: no gradient


def persistent(p):
    return p.by_name.get('TheWorld.PersistentLevel')


def scale_of(p, actor, comp):
    """The placing's scale (x, y, z): the actor's DrawScale and DrawScale3D times the component's Scale and Scale3D."""
    a = [v * p.effective(actor, 'DrawScale', 1) for v in p.effective(actor, 'DrawScale3D', [1, 1, 1])]
    c = [v * p.effective(comp, 'Scale', 1) for v in p.effective(comp, 'Scale3D', [1, 1, 1])]
    return [float(x * y) for x, y in zip(a, c)]


def unit_scale(scale):
    return all(abs(v - 1.0) < 1e-4 for v in scale)


def find_placing(p, what, classes, component):
    """(actor, component, mesh) of the placing `what` names in package `p`: an actor of `classes` (its name, short or
    full), or a mesh path (package.group.name) placed by one of them, its first placing at scale 1 in export order,
    else its first. ValueError when there is none, or the mesh is not in the map's own package."""
    level = persistent(p)
    actor = p.by_name.get(PL + what) or p.by_name.get(what)
    if actor and p.cls(actor) in classes:
        comp = p.effective(actor, component)
        mesh = p.effective(comp, 'StaticMesh') if comp and comp > 0 else None
        if not mesh:
            raise ValueError('%s draws no mesh' % what)
        if mesh < 0:
            raise ValueError("%s's mesh %s is not in the map's own package" % (what, p.name(mesh)))
        return actor, comp, mesh
    found = []
    for i in range(1, len(p.exports) + 1):
        if p.exports[i - 1]['outer'] != level or p.cls(i) not in classes:
            continue
        comp = p.effective(i, component)
        if not comp or comp < 0:
            continue
        mesh = p.effective(comp, 'StaticMesh')
        if mesh and mesh > 0 and p.name(mesh) == what:
            found.append((not unit_scale(scale_of(p, i, comp)), i, comp, mesh))
    if not found:
        raise ValueError('nothing in %s places %s' % (p.path.name if hasattr(p, 'path') else 'the map', what))
    _, actor, comp, mesh = min(found)
    return actor, comp, mesh


def component_light(p, comp):
    """LOD 0 of a mesh component's lighting record (research/evidence/ground-audit.py's): dict(type (0 none, 1 vertex,
    2 texture, None no record), rect [w, h] in texels for a texture one, painted (its override vertex colours: None, a
    value's hex, or 'varying n'), colours (the override colours, a list of 4 bytes, when it paints them))."""
    import lighting_records
    r = p.native(comp)
    if not r.count():
        return dict(type=None)
    lighting_records.refs(r, p)
    lighting_records.refs(r, p)
    lm = lighting_records.lightmap(r, p)
    out = dict(type=lm['type'])
    if lm['type'] == 2:
        tex = lm['slots'][0]['index']
        w, h = (p.own(tex, 'SizeX'), p.own(tex, 'SizeY')) if tex > 0 else (None, None)
        if w and h:
            out['rect'] = [round(lm['coordinateScale'][0] * w, 2), round(lm['coordinateScale'][1] * h, 2)]
    flag = r.take(1)[0]
    painted = None
    if flag:
        stride, count = r.unpack('2I')
        if count:
            _, n, raw = r.array_bytes()
            colours = [bytes(raw[4 * k:4 * k + 4]) for k in range(n)]
            values = set(colours)
            painted = next(iter(values)).hex() if len(values) == 1 else 'varying %d' % len(values)
            out['colours'] = colours
        else:
            painted = 'empty'
    out['painted'] = painted
    return out


def light_of(p, comp):
    """component_light, or dict(type='unread') when the record doesn't read."""
    try:
        return component_light(p, comp)
    except (ValueError, struct.error, IndexError):
        return dict(type='unread')


class Tris:
    """A decoded mesh's LOD 0 (gen_mesh's form) as arrays, its positions times `scale`: pos, uv0, uvlm (the lightmap
    channel, or None), colours (n x 4 bytes, or None), tris (n x 3), slot and fragment of each triangle, normal (UE3's
    outward: cross(c - a, b - a), turned over under a mirroring scale) and area."""

    def __init__(self, m, scale=(1.0, 1.0, 1.0), lm_channel=1):
        lod = m['lods'][0]
        self.scale = tuple(float(v) for v in scale)
        self.pos = np.array(lod['positions'], float).reshape(-1, 3) * np.array(self.scale)
        nv = len(self.pos)
        verts = lod['vertices'] or []
        self.uv0 = np.array([v[2][0] for v in verts], float).reshape(-1, 2) if verts else np.zeros((nv, 2))
        self.uvlm = (np.array([v[2][lm_channel] for v in verts], float).reshape(-1, 2)
                     if verts and lod['texcoords'] > lm_channel else None)
        cols = lod['colours'] or []
        self.colours = [bytes(c) for c in cols] if len(cols) >= nv and nv else None
        idx = lod['indices'][1]
        tris, slots, frags = [], [], []
        for s in lod['sections']:
            if s.get('fragments'):
                for f, (first, count) in enumerate(s['fragments']):
                    for t in range(first // 3, first // 3 + count):
                        tris.append(idx[3 * t:3 * t + 3])
                        slots.append(s['slot'])
                        frags.append(f)
            else:
                for t in range(s['first'] // 3, s['first'] // 3 + s['triangles']):
                    tris.append(idx[3 * t:3 * t + 3])
                    slots.append(s['slot'])
                    frags.append(-1)
        self.sections = len(lod['sections'])
        self.tris = np.array(tris, np.int64).reshape(-1, 3)
        self.slot = np.array(slots, int)
        self.frag = np.array(frags, int)
        a, b, c = self.pos[self.tris[:, 0]], self.pos[self.tris[:, 1]], self.pos[self.tris[:, 2]]
        cross = np.cross(c - a, b - a)
        length = np.linalg.norm(cross, axis=1)
        self.area = length / 2
        self.normal = cross / np.maximum(length, 1e-12)[:, None]
        if np.prod(np.sign(self.scale)) < 0:
            self.normal = -self.normal

    def verts(self, sel):
        return np.unique(self.tris[sel]) if sel.any() else np.zeros(0, np.int64)

    def vertex_areas(self, sel):
        """Each vertex's share of the area of the triangles `sel`: a third of each one it is a corner of."""
        w = np.zeros(len(self.pos))
        for k in range(3):
            np.add.at(w, self.tris[sel][:, k], self.area[sel] / 3)
        return w

    def commonest_colour(self, sel):
        """The commonest colour (hex) on the vertices of the triangles `sel`, or None."""
        if self.colours is None or not sel.any():
            return None
        return commonest([self.colours[v] for v in self.verts(sel)])

    def lightmap_area(self):
        """The lightmap channel's UV area over every triangle (0 without the channel)."""
        if self.uvlm is None or not len(self.tris):
            return 0.0
        t = self.uvlm[self.tris]
        return float(0.5 * np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1])
                                  - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1])).sum())


def main_colour(colours, weights):
    """The colour a painted placing mostly draws with, as hex, or None for none (D14; EXP-79 run D2): one value as it
    is; with several, the values are grouped by the layer of the blend each leans to (each byte that varies taken as
    under or over 128), the group with the most weight (`weights`, the vertices' areas; ties to the smallest) is the
    main layer, and the colour is its values' mean by weight. The commonest exact value can be a small part's: on
    URB_GasStation_EWI's dirt-and-asphalt plane 94 values paint 121 vertices, its edges' 000000ff (asphalt) the
    commonest, where the values leaning to ffffffff (dirt) hold nearly half the area."""
    if not colours:
        return None
    values = [bytes(c) for c in colours]
    if len(set(values)) == 1:
        return values[0].hex()
    varies = [len({v[k] for v in values}) > 1 for k in range(len(values[0]))]
    groups = {}
    for v, w in zip(values, weights):
        key = bytes((255 if b >= 128 else 0) if varies[k] else b for k, b in enumerate(v))
        groups.setdefault(key, []).append((v, float(w)))
    key, members = min(groups.items(), key=lambda kv: (-sum(w for _, w in kv[1]), kv[0]))
    total = sum(w for _, w in members)
    if total <= 0:
        return key.hex()
    return bytes(int(round(sum(v[k] * w for v, w in members) / total)) for k in range(len(key))).hex()


def commonest(colours):
    """The commonest of `colours` (4 bytes each) as hex, ties to the smallest; None for none."""
    if not colours:
        return None
    counts = {}
    for c in colours:
        counts[bytes(c)] = counts.get(bytes(c), 0) + 1
    return min(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0].hex()


def density(rect, lm_area, world_area):
    """Lightmap texels a world unit: the square root of the lightmap channel's UV area times the rectangle's texels over
    the mesh's world area (ground-audit.py's), or None."""
    if not rect or not lm_area or world_area <= 0:
        return None
    return math.sqrt(lm_area * rect[0] * rect[1] / world_area)


def _weighted_median(values, weights):
    order = np.argsort(values, kind='stable')
    cw = np.cumsum(weights[order])
    return float(values[order][min(np.searchsorted(cw, 0.5 * cw[-1]), len(order) - 1)])


def circular_median(values, weights, candidates=256):
    """The offset modulo 1 nearest (by the weighted sum of circular distances) to `values`: chosen among them (the
    heaviest `candidates` of them, for speed)."""
    v = np.mod(values, 1.0)
    pick = np.argsort(-weights, kind='stable')[:candidates]
    best, cost = 0.0, None
    for c in sorted(set(np.round(v[pick], 6).tolist())):
        d = np.abs(v - c)
        d = np.minimum(d, 1.0 - d)
        s = float((d * weights).sum())
        if cost is None or s < cost - 1e-12:
            best, cost = c, s
    return best


def planar_map(T, sel, axes=(0, 1)):
    """The texture's planar map on the triangles `sel` of Tris `T` over the world axes `axes` (x, y for a top):
    dict(u [a, b, c], v [d, e, f] (per world unit; c and f modulo 1), spread [u, v] (how far the vertices lie from it,
    modulo 1: see the module's words), repeat [u, v] (world units a repeat: 1 / the gradient's length), axis [u, v]
    ('+x', '-y'... the axis each mostly runs along, or 'oblique')), or None for no faces. A coordinate that doesn't
    change across the faces (a repeat longer than CONSTANT units: a trim's top drawn from one strip of its texture) has
    no gradient, its offset its value, its repeat and axis None."""
    if not sel.any():
        return None
    tris = T.tris[sel]
    w = T.area[sel]
    p0, p1, p2 = T.pos[tris[:, 0]], T.pos[tris[:, 1]], T.pos[tris[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    a11, a22, a12 = (e1 * e1).sum(1), (e2 * e2).sum(1), (e1 * e2).sum(1)
    det = a11 * a22 - a12 * a12
    ok = det > 1e-9
    if not ok.any():
        return None
    out = dict(u=None, v=None, spread=[None, None], repeat=[None, None], axis=[None, None])
    for c, name in ((0, 'u'), (1, 'v')):
        t0, t1, t2 = T.uv0[tris[:, 0], c], T.uv0[tris[:, 1], c], T.uv0[tris[:, 2], c]
        d1, d2 = t1 - t0, t2 - t0
        x = (d1 * a22 - d2 * a12) / np.where(ok, det, 1)
        y = (d2 * a11 - d1 * a12) / np.where(ok, det, 1)
        g = x[:, None] * e1 + y[:, None] * e2               # the gradient in each triangle's plane
        gl = np.linalg.norm(g, axis=1)
        flat = g[:, list(axes)]
        fl = np.linalg.norm(flat, axis=1)
        # laid flat: the gradient's direction across the two axes, its length its own (a slope's repeat kept)
        flat = np.where(fl[:, None] > 1e-12, flat * (gl / np.maximum(fl, 1e-12))[:, None], 0.0)
        live = ok & (gl > 1e-12)
        if live.any():
            ww = w[live]
            a = _weighted_median(flat[live, 0], ww)
            b = _weighted_median(flat[live, 1], ww)
        if not live.any() or math.hypot(a, b) < 1.0 / CONSTANT:
            live, ww, a, b = ok, w[ok], 0.0, 0.0
        # the offset: each vertex's value less the map, modulo 1
        verts = np.unique(tris[live])
        vw = np.zeros(len(T.pos))
        for k in range(3):
            np.add.at(vw, tris[live][:, k], ww / 3)
        vals = T.uv0[verts, c] - a * T.pos[verts, axes[0]] - b * T.pos[verts, axes[1]]
        off = circular_median(vals, vw[verts])
        d = np.abs(np.mod(vals - off, 1.0))
        d = np.minimum(d, 1.0 - d)
        order = np.argsort(d, kind='stable')
        cw = np.cumsum(vw[verts][order])
        spread = float(d[order][min(np.searchsorted(cw, 0.9 * cw[-1]), len(order) - 1)])
        length = math.hypot(a, b)
        out[name] = [a, b, off]
        out['spread'][c] = spread
        out['repeat'][c] = 1.0 / length if length > 0 else None
        if length > 0:
            k = 0 if abs(a) >= abs(b) else 1
            out['axis'][c] = (('+' if (a, b)[k] > 0 else '-') + 'xyz'[axes[k]]
                              if abs((a, b)[k]) >= 0.99 * length else 'oblique')
    if out['u'] is None or out['v'] is None:
        return None
    return out


def rounded_map(m, digits=7):
    """A planar map's [[a, b, c], [d, e, f]] rounded for a recipe (an offset of 1 is 0)."""
    def off(v):
        v = round(v % 1.0, 4)
        return 0.0 if v >= 1.0 else v
    return [[round(m['u'][0], digits) + 0.0, round(m['u'][1], digits) + 0.0, off(m['u'][2])],
            [round(m['v'][0], digits) + 0.0, round(m['v'][1], digits) + 0.0, off(m['v'][2])]]


def map_differs(a, b, drift=0.01, offset=0.01):
    """Whether two recipe maps ([[a, b, c], [d, e, f]]) differ: a coefficient by more than drifts `drift` of a repeat
    over a tile (96 units), an offset by more than `offset` modulo 1."""
    for ra, rb in zip(a, b):
        for k in range(2):
            if abs(ra[k] - rb[k]) * 96 > drift:
                return True
        d = abs((ra[2] - rb[2]) % 1.0)
        if min(d, 1.0 - d) > offset:
            return True
    return False
