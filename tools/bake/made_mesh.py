"""A made piece's mesh from its polygons: the walls (frac_wall.py), slabs (frac_slab.py) and ground shapes (ground.py)
each build their faces as Faces' polygons and their fragments' records, and assemble makes the mesh (gen_mesh's form)
from them on a donor's decoded mesh: the lightmap rectangle its charts are packed into (pack_rect), each face's
vertices with their tangent frames (tangent_frame; a face with a corner on a straight run fanned from its centre,
collinear_corner) and triangles wound as UE3's front faces are, each fragment's run of triangles and its record, the
kDOP tree."""
import math
import struct

import gen_mesh


class Faces:
    """The polygons of the mesh: dict(points [(x, y, z)], normal, slot, fragment, uv0 [(u, v)], chart, cuv [(s, t)] (in
    the chart's own units), role (the texture mapping's surface it is of, uv_mapping.ROLES, or None: a wall's faces
    are 'faces'))."""

    def __init__(self):
        self.polys = []
        self.charts = {}            # id -> [width, height, density]

    def chart(self, key, width, height, density=1.0):
        self.charts.setdefault(key, [width, height, density])
        return key

    def add(self, points, normal, slot, fragment, uv0, chart, cuv, interior=False, role=None):
        if len(points) < 3:
            return
        self.polys.append(dict(points=[tuple(map(float, p)) for p in points], normal=tuple(normal), slot=slot,
                               fragment=fragment, uv0=uv0, chart=chart, cuv=cuv, interior=interior, role=role))


def poly_area3(points):
    n = [0.0, 0.0, 0.0]
    for a, b in zip(points, points[1:] + points[:1]):
        n[0] += a[1] * b[2] - a[2] * b[1]
        n[1] += a[2] * b[0] - a[0] * b[2]
        n[2] += a[0] * b[1] - a[1] * b[0]
    return 0.5 * math.sqrt(sum(v * v for v in n))


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


def assemble(faces, records, template, R, guid, slots=6, what='a mesh'):
    """The fractured mesh (gen_mesh's form) of the polygons `faces` (Faces: each with its slot, fragment, uv0, chart and
    chart coordinates, and optionally a colour for each corner, else the recipe's outside or interior colour) and the
    fragment records `records` ([dict(centre (x, y, z), neighbours, dims)]), on the donor's decoded mesh `template`,
    with the recipe `R`'s lightmap packing and colours, `slots` sections and the tail's `guid`: dict(mesh, fragments
    (their boxes), lightmapRect, counts). frac_wall.build and frac_slab.build make theirs with it. A template with no
    `fractured` (a plain static mesh's: ground.py's shapes) gives a plain mesh: one record, its sections without
    fragment runs, its collision triangles' values their slots."""
    L = R['lightmap']
    plain = template.get('fractured') is None
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
                    kdop.append(tuple(tri) + (gen_mesh.kdop_value(slot, f, 0 if plain else nfrag),))
                lo_v = base if lo_v is None else min(lo_v, base)
                hi_v = len(positions) - 1
            count = (len(indices) - start) // 3
            ranges.append((start, count) if count else (0, 0))
        sections.append(dict(material=0, collision=1, oldCollision=1, shadow=1, first=first,
                             triangles=(len(indices) - first) // 3, minVertex=lo_v or 0, maxVertex=hi_v or 0,
                             slot=slot, fragments=[] if plain else ranges, platform=0))
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
    if plain:
        mesh['fractured'] = None
    else:
        fr = dict(template['fractured'])
        fr.update(fragments=frags, core=-1, interior=R['slots'].get('interior', R.get('interior')), sourceMesh=0)
        mesh['fractured'] = fr
    boxes = []
    for f, pts in enumerate(frag_points):
        boxes.append(dict(box=[v for k in range(3) for v in (min(p[k] for p in pts), max(p[k] for p in pts))]))
    return dict(mesh=mesh, fragments=boxes, lightmapRect=list(rect),
                counts=dict(fragments=nfrag, vertices=nv, triangles=len(indices) // 3, charts=len(faces.charts)))
