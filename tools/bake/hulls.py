"""Convex collision hulls as the game's cooker saves them (custom geometry plan, stage M6 item 3), for shapes made from
numbers: a ramp's wedge, a block, any convex solid. Moved here from research/evidence/hull-audit.py, the audit that
found the rules, which imports it back and checks it against the install's 18,195 hulls.

hull_element(corners, faces=None) gives a KConvexElem's seven saved fields (VertexData, PermutedVertexData,
FaceTriData, EdgeDirections, FaceNormalDirections, FacePlaneData, ElemBox) in cover_blocks.convex_hull's form:
- PhysX 2.8's hull (closed source) is emulated with Stan Melax's incremental hull, the library its cooker builds on,
  for the vertex order and triangles when no faces are given;
- UE3's part (FKConvexElem::GenerateHullData) is followed: face normals and planes with its dedupe thresholds, edge
  directions in first-met order, the element box, the permuted vertices; in single precision, with the processor's
  RSQRTSS table where the game uses it.
The audit found the writer byte-exact on the cover blocks' recipe box, the farm's ramps (TornEarth's
SmallscoutRamps, ten hulls) and wedges from numbers (research/evidence/hull-audit-2026-11-18.json).

wedge(size, rise) gives a ramp's corners and faces."""
import base64
from collections import Counter, defaultdict
import math
import struct
import zlib

import numpy as np


# ---------------------------------------------------------------- the cooker's single-precision maths
F = np.float32
# Intel's RSQRTSS over [1, 4): 2048 results by the input's top 11 bits (exponent parity and 10 mantissa bits), each
# 0x3F000000 + (value << 11); stored as the first value (4094) and each next one's fall (1 to 4) less one in two bits,
# after a marker bit, zlib, base64
_RSQRT = ('eNpNju2pgzAUhhUyQATdRyEZIGAKGeAE6hJ3CoU4gGAEB7BgByq0AxTqfZP09vb9yoH8eX6O43G8jufruF6v+/OxP/fHZb9Dt8t62+Bl3'
          'aB18dviF+9X/9YcMvvJd+M0B03TeA6B3WSdG22Qcc6Ss2agwQyGhpMhoh4iMifd00kbTbDRGB2ejySqYircVYurUq2upGqxSWWrlJQlpkQwpRJoKY'
          'sQoVAhCwgvFK6CCdEUHGWisLPvurE7z5F8tIH67NxgAT2QgxN0VOIl3cMBlP5ZK63bgBosWy0TZ5KU1R/gFx7YEloiE2+yBNZwgYkuGG9iUEzd5Oy'
          'jPM/qmjMsR1lMnrGMZzXMceUZJgRHbIaPL/0C1AWn0g==')


def _rsqrt_table():
    data = zlib.decompress(base64.b64decode(_RSQRT))
    bits = bin(int.from_bytes(data, 'big'))[3:]
    values = [4094]
    for k in range(2047):
        values.append(values[-1] - int(bits[2 * k:2 * k + 2], 2) - 1)
    return [0x3F000000 + (v << 11) for v in values]


RSQRT = _rsqrt_table()


def _bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def _float(b):
    return F(struct.unpack('<f', struct.pack('<I', b))[0])


def rsqrtss(x):
    """The processor's estimate of 1/sqrt(x) for a positive normal float: the table at x scaled into [1, 4) by an even
    power of two, scaled back (RSQRTSS(4x) is RSQRTSS(x) / 2 exactly)."""
    b = _bits(x)
    e = (b >> 23) & 0xFF
    shift = (e - 127) // 2                       # x = y * 4^shift, y in [1, 4)
    y = b - (shift * 2 << 23)
    return _float(RSQRT[(y - 0x3F800000) >> 13] - (shift << 23))


def inv_sqrt(s):
    x0 = rsqrtss(s)
    return F(F(x0 * F(F(3.0) - F(F(F(s) * x0) * x0))) * F(0.5))


def sub(a, b):
    return [F(F(x) - F(y)) for x, y in zip(a, b)]


def cross(a, b):
    return [F(F(a[1] * b[2]) - F(a[2] * b[1])), F(F(a[2] * b[0]) - F(a[0] * b[2])), F(F(a[0] * b[1]) - F(a[1] * b[0]))]


def dot(a, b):
    return F(F(F(F(a[0]) * F(b[0])) + F(F(a[1]) * F(b[1]))) + F(F(a[2]) * F(b[2])))


def safe_normal(v):
    v = [F(x) for x in v]
    s = dot(v, v)
    if s == F(1.0):
        return v
    if s < F(9.99999993922529e-09):
        return [F(0.0)] * 3
    k = inv_sqrt(s)
    return [F(x * k) for x in v]


def dot87(p, n):
    """The x87 dot of the cooker's list tests: (y y + x x) + z z, in extended precision (double here)."""
    return (float(p[1]) * float(n[1]) + float(p[0]) * float(n[0])) + float(p[2]) * float(n[2])


PARALLEL = 0.0003000000142492354
PLANE_W = 0.10000000149011612
COPLANAR_EDGE = F(0.9997000098228455)


def add_dir(dirs, n):
    if not any(abs(abs(dot87(d, n)) - 1.0) < PARALLEL for d in dirs):
        dirs.append(n)


def same_plane(q, p):
    return abs(dot87(q[:3], p[:3]) - 1.0) < PARALLEL and abs(float(q[3]) - float(p[3])) < PLANE_W


# ---------------------------------------------------------------- the cooker's rules (UE3's part)
def tri_rows(face_tri):
    return [tuple(face_tri[i:i + 3]) for i in range(0, len(face_tri), 3)]


def derive(V, T):
    """(FaceNormalDirections, FacePlaneData [w, x, y, z], EdgeDirections, notes) from vertices and saved triangles, as
    GenerateHullData makes them."""
    V = [[F(x) for x in v] for v in V]
    normals, planes, tri_n, edges, seen = [], [], [], [], set()
    for a, b, c in T:
        for e in ((a, b), (b, c), (c, a)):
            if e not in seen and (e[1], e[0]) not in seen:
                seen.add(e)
                edges.append(e)
        n = safe_normal(cross(sub(V[c], V[a]), sub(V[b], V[a])))
        tri_n.append(n)
        add_dir(normals, n)
        p = n + [dot(V[a], n)]
        if not any(same_plane(q, p) for q in planes):
            planes.append(p)
    notes = Counter()
    edirs = []
    for v0, v1 in edges:
        found = [i for i, t in enumerate(T) if v0 in t and v1 in t]
        if len(found) < 2:
            notes['open edge'] += 1
            continue
        if len(found) > 2:
            notes['edge in more than two triangles'] += 1
        n1, n2 = tri_n[found[0]], tri_n[found[1]]
        if COPLANAR_EDGE > F(F(F(n2[0] * n1[0]) + F(n1[1] * n2[1])) + F(n1[2] * n2[2])):
            add_dir(edirs, safe_normal(sub(V[v0], V[v1])))
    return normals, [[p[3]] + p[:3] for p in planes], edirs, notes


def permuted(V):
    out = []
    for g in range(0, len(V), 4):
        four = [V[g + i] if g + i < len(V) else V[g] for i in range(4)]
        for a in range(3):
            out.append([four[3][a], four[0][a], four[1][a], four[2][a]])
    return out


def elem_box(V):
    return [[min(F(v[a]) for v in V) for a in range(3)], [max(F(v[a]) for v in V) for a in range(3)], 1]


def plane_ids(V, T):
    """Each saved triangle's face: the index of its plane by the cooker's plane rule."""
    planes, idx = [], []
    for a, b, c in T:
        n = safe_normal(cross(sub(V[c], V[a]), sub(V[b], V[a])))
        p = n + [dot(V[a], n)]
        hit = next((j for j, q in enumerate(planes) if same_plane(q, p)), None)
        if hit is None:
            planes.append(p)
            hit = len(planes) - 1
        idx.append(hit)
    return idx


def face_loops(V, T):
    """The saved triangles as faces: [loop], each loop counter-clockwise seen from outside, from the fan's first
    vertex (saved triangles (s, q[i+1], q[i]))."""
    pid = plane_ids([[F(x) for x in v] for v in V], T)
    loops = []
    last = None
    for (a, b, c), p in zip(T, pid):
        if loops and last == p and loops[-1][0] == a and loops[-1][-1] == c:
            loops[-1].append(b)
        else:
            loops.append([a, c, b])
        last = p
    return loops


# ---------------------------------------------------------------- PhysX's hull, emulated (Melax's incremental hull)
class _Melax:
    """StanHull's calchull over points (double precision), its surviving triangles in id order."""

    def __init__(self, points):
        self.v = [np.array(p, dtype=np.float64) for p in points]
        self.tris = []

    def new(self, a, b, c):
        t = dict(v=[a, b, c], n=[-1, -1, -1], id=len(self.tris), vmax=-1, rise=0.0)
        self.tris.append(t)
        return t

    def _slot(self, t, a, b):
        for i in range(3):
            i1 = (i + 1) % 3
            if (t['v'][i] == a and t['v'][i1] == b) or (t['v'][i] == b and t['v'][i1] == a):
                return (i + 2) % 3
        raise ValueError('not a neighbour')

    def b2bfix(self, s, t):
        for i in range(3):
            a, b = s['v'][(i + 1) % 3], s['v'][(i + 2) % 3]
            sa = s['n'][self._slot(s, a, b)]
            tb = t['n'][self._slot(t, b, a)]
            x = self.tris[sa]
            x['n'][self._slot(x, b, a)] = tb
            y = self.tris[tb]
            y['n'][self._slot(y, a, b)] = sa

    def removeb2b(self, s, t):
        self.b2bfix(s, t)
        self.tris[s['id']] = None
        self.tris[t['id']] = None

    def extrude(self, t0, v):
        t = list(t0['v'])
        n = len(self.tris)
        made = []
        for k, (p, q) in enumerate(((t[1], t[2]), (t[2], t[0]), (t[0], t[1]))):
            x = self.new(v, p, q)
            x['n'] = [t0['n'][k], n + (k + 1) % 3, n + (k + 2) % 3]
            nb = self.tris[t0['n'][k]]
            nb['n'][self._slot(nb, p, q)] = n + k
            made.append(x)
        for x in made:
            nb = self.tris[x['n'][0]]
            if self.tris[x['id']] is not None and nb is not None and v in nb['v']:
                self.removeb2b(x, nb)
        self.tris[t0['id']] = None

    def normal(self, t):
        v0, v1, v2 = (self.v[i] for i in t)
        cp = np.cross(v1 - v0, v2 - v1)
        m = np.linalg.norm(cp)
        return np.array([1.0, 0.0, 0.0]) if m == 0 else cp / m

    def above(self, t, p, eps):
        return float(np.dot(self.normal(t), p - self.v[t[0]])) > eps

    def maxdir(self, d, allow):
        m = -1
        for i, p in enumerate(self.v):
            if allow[i] and (m == -1 or np.dot(p, d) > np.dot(self.v[m], d)):
                m = i
        return m

    def maxdirsterid(self, d, allow):
        while True:
            m = self.maxdir(d, allow)
            if allow[m] == 3:
                return m
            a = np.cross(d, [0.0, 0.0, 1.0])
            b = np.cross(d, [0.0, 1.0, 0.0])
            u = a if np.linalg.norm(a) > np.linalg.norm(b) else b
            u = u / np.linalg.norm(u)
            w = np.cross(u, d)
            ma = -1
            for x in range(0, 361, 45):
                s, c = math.sin(math.radians(x)), math.cos(math.radians(x))
                mb = self.maxdir(d + (u * s + w * c) * 0.025, allow)
                if ma == m and mb == m:
                    allow[m] = 3
                    return m
                if ma != -1 and ma != mb:
                    mc = ma
                    for xx in range(x - 40, x + 1, 5):
                        s, c = math.sin(math.radians(xx)), math.cos(math.radians(xx))
                        md = self.maxdir(d + (u * s + w * c) * 0.025, allow)
                        if mc == m and md == m:
                            allow[m] = 3
                            return m
                        mc = md
                ma = mb
            allow[m] = 0

    def simplex(self, allow):
        b0 = np.array([0.01, 0.02, 1.0])
        p0 = self.maxdirsterid(b0, allow)
        p1 = self.maxdirsterid(-b0, allow)
        b0 = self.v[p0] - self.v[p1]
        if p0 == p1 or not b0.any():
            return None
        b1 = np.cross([1.0, 0.02, 0.0], b0)
        b2 = np.cross([-0.02, 1.0, 0.0], b0)
        b1 = b1 if np.linalg.norm(b1) > np.linalg.norm(b2) else b2
        b1 = b1 / np.linalg.norm(b1)
        p2 = self.maxdirsterid(b1, allow)
        if p2 in (p0, p1):
            p2 = self.maxdirsterid(-b1, allow)
        if p2 in (p0, p1):
            return None
        b2 = np.cross(self.v[p2] - self.v[p0], b0)
        b2 = b2 / np.linalg.norm(b2)
        p3 = self.maxdirsterid(b2, allow)
        if p3 in (p0, p1, p2):
            p3 = self.maxdirsterid(-b2, allow)
        if p3 in (p0, p1, p2):
            return None
        if np.dot(self.v[p3] - self.v[p0], np.cross(self.v[p1] - self.v[p0], self.v[p2] - self.v[p0])) < 0:
            p2, p3 = p3, p2
        return p0, p1, p2, p3

    def run(self):
        allow, extreme = [1] * len(self.v), [0] * len(self.v)
        pts = np.array(self.v)
        eps = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0))) * 0.001
        p = self.simplex(allow)
        if p is None:
            return None
        centre = sum(self.v[q] for q in p) / 4.0
        for (a, b, c), nb in (((2, 3, 1), (2, 3, 1)), ((3, 2, 0), (3, 2, 0)), ((0, 1, 3), (0, 1, 3)),
                              ((1, 0, 2), (1, 0, 2))):
            self.new(p[a], p[b], p[c])['n'] = list(nb)
        for q in p:
            extreme[q] = 1
        for t in self.tris:
            n = self.normal(t['v'])
            t['vmax'] = self.maxdirsterid(n, allow)
            t['rise'] = float(np.dot(n, self.v[t['vmax']] - self.v[t['v'][0]]))
        while True:
            te = None
            for t in self.tris:
                if te is None or (t is not None and te['rise'] < t['rise']):
                    te = t
            if te is None or not te['rise'] > eps:
                break
            v = te['vmax']
            extreme[v] = 1
            for j in range(len(self.tris) - 1, -1, -1):
                t = self.tris[j]
                if t is not None and self.above(t['v'], self.v[v], 0.01 * eps):
                    self.extrude(t, v)
            j = len(self.tris)
            while j:
                j -= 1
                t = self.tris[j]
                if t is None:
                    continue
                if v not in t['v']:
                    break
                a, b, c = t['v']
                if self.above(t['v'], centre, 0.01 * eps) or np.linalg.norm(
                        np.cross(self.v[b] - self.v[a], self.v[c] - self.v[b])) < eps * eps * 0.1:
                    self.extrude(self.tris[t['n'][0]], v)
                    j = len(self.tris)
            for j in range(len(self.tris) - 1, -1, -1):
                t = self.tris[j]
                if t is None:
                    continue
                if t['vmax'] >= 0:
                    break
                n = self.normal(t['v'])
                t['vmax'] = self.maxdirsterid(n, allow)
                if extreme[t['vmax']]:
                    t['vmax'] = -1
                else:
                    t['rise'] = float(np.dot(n, self.v[t['vmax']] - self.v[t['v'][0]]))
        return [list(t['v']) for t in self.tris if t is not None]


def _merge_face(raw):
    """A face's loop from its hull triangles (PhysX winding) in order: the first triangle's edges, then each next
    triangle that shares an edge (x, y) with the loop puts (v, y) in that edge's place and (x, v) at the end; the loop
    is read from the first edge."""
    edges = [(raw[0][0], raw[0][1]), (raw[0][1], raw[0][2]), (raw[0][2], raw[0][0])]
    pending = list(raw[1:])
    while pending:
        for t in pending:
            hit = None
            for i, (x, y) in enumerate(edges):
                k = next((k for k in range(3) if t[k] == y and t[(k + 1) % 3] == x), None)
                if k is not None:
                    hit = (i, x, y, t[(k + 2) % 3])
                    break
            if hit:
                i, x, y, v = hit
                edges[i] = (v, y)
                edges.append((x, v))
                pending.remove(t)
                break
        else:
            return None
    nxt = dict(edges)
    if len(nxt) != len(edges):
        return None
    loop = [edges[0][0]]
    while len(loop) < len(edges) and loop[-1] in nxt:
        loop.append(nxt[loop[-1]])
    return loop if len(loop) == len(edges) else None


def physx_hull(points):
    """(order, loops): the cooker's hull of the points as emulated: the points' indices in the saved vertex order,
    and the faces' loops in saved order (indices into that order), or (None, None)."""
    tris = _Melax([[float(x) * 0.02 for x in p] for p in points]).run()
    if tris is None:
        return None, None
    used = {}
    for t in tris:
        for v in t:
            used.setdefault(v, len(used))
    order = sorted(used, key=used.get)
    nt = [[used[v] for v in t] for t in tris]
    V = [[F(x) for x in points[i]] for i in order]
    pid = plane_ids(V, [(a, c, b) for a, b, c in nt])
    groups = defaultdict(list)
    for t, p in zip(nt, pid):
        groups[p].append(tuple(t))
    loops = []
    for p in sorted(groups):
        loop = _merge_face(groups[p])
        if loop is None:
            return order, None
        loops.append(loop)
    return order, loops


def fans(loops):
    """Saved triangles from face loops: each loop fanned from its first vertex, saved (s, q[i+1], q[i])."""
    out = []
    for loop in loops:
        for i in range(1, len(loop) - 1):
            out += [loop[0], loop[i + 1], loop[i]]
    return out


# ================================================================ the general hull writer
def cooker_vertex(v):
    """A corner as the cooker hands it to PhysX and takes it back: times 0.02, then times 50, in single precision."""
    return [F(F(F(x) * F(0.02)) * F(50.0)) for x in v]


def hull_element(corners, faces=None, round_trip=True):
    """A KConvexElem's seven saved fields for the convex polyhedron with these corners (game units), as the game's
    cooker (FKConvexElem::GenerateHullData) saves them, in cover_blocks.convex_hull's form: dict(VertexData,
    PermutedVertexData, FaceTriData, EdgeDirections, FaceNormalDirections, FacePlaneData ([w, x, y, z]), ElemBox
    [min, max, 1]), floats as Python floats of single-precision values.

    faces None: the vertex order and the triangles as the cooker's hull makes them (PhysX's, emulated: physx_hull),
    from the corners in any order. faces given: [loop of corner indices] counter-clockwise seen from outside, the
    corners kept in their order and each face fanned from its loop's first corner, faces in the given order (to copy a
    layout, such as cover_blocks' recipe box). round_trip: each corner as the cooker returns it (cooker_vertex); the
    rest of the fields are made from those values. Raises ValueError for corners that make no solid."""
    pts = [cooker_vertex(c) if round_trip else [F(x) for x in c] for c in corners]
    if faces is None:
        order, loops = physx_hull(pts)
        if order is None or loops is None:
            raise ValueError('the corners make no convex solid the hull can take')
        pts = [pts[i] for i in order]
    else:
        loops = [list(f) for f in faces]
    T = fans(loops)
    normals, planes, edges, notes = derive(pts, tri_rows(T))
    if notes['open edge']:
        raise ValueError('the faces leave the hull open')
    box = elem_box(pts)
    return dict(VertexData=[[float(x) for x in v] for v in pts],
                PermutedVertexData=[[float(x) for x in r] for r in permuted(pts)],
                FaceTriData=list(T),
                EdgeDirections=[[float(x) for x in d] for d in edges],
                FaceNormalDirections=[[float(x) for x in d] for d in normals],
                FacePlaneData=[[float(x) for x in p] for p in planes],
                ElemBox=[[float(x) for x in box[0]], [float(x) for x in box[1]], 1])


def wedge(size, rise):
    """The corners and faces of a ramp: a wedge on the box 0..size[0], 0..size[1], rising along x from 0 at x = 0 to
    `rise` at x = size[0] (a right triangular prism): ([corners], [loops counter-clockwise seen from outside])."""
    x, y = float(size[0]), float(size[1])
    c = [[0.0, 0.0, 0.0], [x, 0.0, 0.0], [x, y, 0.0], [0.0, y, 0.0], [x, 0.0, float(rise)], [x, y, float(rise)]]
    faces = [[0, 3, 2, 1], [1, 2, 5, 4], [0, 1, 4], [3, 5, 2], [0, 4, 5, 3]]
    return c, faces
