"""Read-only audit of the game's convex collision hulls, for the ramps of custom geometry stage M6 (item 3: can a
general convex hull be written byte for byte as the game's cooker saved it?).

Over every package of the install's cooked folder (or the packages named with --maps), it reads each RB_BodySetup's
AggGeom.ConvexElems: a KConvexElem saves VertexData, PermutedVertexData, FaceTriData, EdgeDirections,
FaceNormalDirections, FacePlaneData (Planes, saved W first) and ElemBox. Elements that are the same by value (the same
mesh cooked into many maps) are audited once and counted by instance too. For each element it makes the saved
fields again and compares them byte for byte:

  vertices    ElemBox and PermutedVertexData from VertexData alone;
  triangles   FaceNormalDirections, FacePlaneData and EdgeDirections from VertexData and the saved FaceTriData, by
              the cooker's own rules (below), with the cause of each difference (plane distance off by a few ulps,
              face or edge rule);
  corners     the whole element from its corners alone, in any order: the vertex order and triangle list as the
              cooker's hull (PhysX 2.8's) makes them, emulated here (below), then the rest by the cooker's rules.

The cooker, read from the game's own code (XComEW.exe, FKConvexElem::GenerateHullData at 0x8871C0, the function that
logs "FKConvexElem::GenerateHullData : Open mesh."):
- VertexData is scaled by 0.02 (0x199AA14) and cooked by PhysX 2.8 (NxCookConvexMesh with NX_CF_COMPUTE_CONVEX,
  read back through NxConvexMesh). VertexData is REPLACED by PhysX's hull vertices times 50 (0x199AA10), in PhysX's
  order, and ElemBox is their box. FaceTriData is PhysX's triangles (t0, t1, t2) saved as (t0, t2, t1).
- Per triangle (a, b, c) as saved: N = SafeNormal(cross(c - a, b - a)) in SSE single precision (the products and
  sums each rounded to float; the inverse square root rsqrtss and one Newton step, 0.5 x0 (3 - s x0 x0)); a squared
  length of exactly 1 is kept, under 1e-8 gives zero. N joins FaceNormalDirections unless a saved direction is
  parallel or opposite (| |d.N| - 1 | < 0.0003, 0x108CED0); the plane (N, W = V[a].N) joins FacePlaneData unless a
  saved plane has |d.N - 1| < 0.0003 and |dW| < 0.1 (0x108CDE0).
- The triangles' undirected edges, in the order first met (a-b, b-c, c-a of each triangle, 0x108CFB0): an edge whose
  first two triangles (0x108D110) have normals with a float dot under 0.9997 (0x1876E70) gives the direction
  SafeNormal(V[v0] - V[v1]), which joins EdgeDirections by the face-direction rule. An edge with one triangle logs
  "Open mesh" and is skipped.
- PermutedVertexData: the vertices in fours, each four as three Planes (its x, y and z values), a short last four
  padded with its first vertex; Planes are saved W first, so a four's x row is saved (x3, x0, x1, x2).
- When a mesh is loaded with no pre-cooked data (every map's), the game cooks each element from VertexData alone
  (0xD7F290); the other fields are what the engine's own collision code reads.

PhysX's hull (closed source) is emulated with Stan Melax's incremental hull (the StanHull library PhysX 2.x's cooker
grew from): the extreme-point simplex and extrusions, the surviving triangles renumbered by first use (its
BringOutYourDead step gives the vertex order), the triangles grouped into faces by the cooker's plane rule in the
order of each face's first triangle, each face's loop built by merging its triangles in order (the shared edge (x, y)
replaced in place by (v, y) and (x, v) appended, the loop read from the first edge), and each face fanned from its
loop's first vertex. The emulation runs in double precision where PhysX ran in single, so near ties can go the other
way. The rsqrtss table is an Intel processor's (2048 entries over [1, 4), checked over 300,000 random inputs on the
hardware; it reproduces the saved directions).

Below the audit, separated, is the general hull writer (hull_element): an element from any convex corners, as the
cooker would save it, in cover_blocks.convex_hull's form; and its self-check (--self-check): the box against
cover_blocks' recipe box, the farm ramp's ten hulls (TornEarth.Meshes.SmallscoutRamps), and a wedge from numbers.

Prints a summary; --output writes the JSON. Nothing is written to the game.

  python -B research/evidence/hull-audit.py [--maps CsmallScout_Farm URB_PoliceStation] [--listed-only]
      [--no-corners] [--output <file.json>] [--verbose]
  python -B research/evidence/hull-audit.py --self-check
"""
import argparse
import base64
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
import struct
import sys
import time
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for folder in ('viewer', 'upk', 'lab', 'bake'):
    sys.path.insert(0, str(ROOT / 'tools' / folder))
from package import Package, Reader  # noqa: E402

FIELDS = ('VertexData', 'PermutedVertexData', 'FaceTriData', 'EdgeDirections', 'FaceNormalDirections',
          'FacePlaneData', 'ElemBox')
FORMATS = dict(VertexData='3f', PermutedVertexData='4f', FaceTriData='i', EdgeDirections='3f',
               FaceNormalDirections='3f', FacePlaneData='4f')
FARM_RAMP = 'TornEarth.Meshes.SmallscoutRamps'
FX_BOX = 'FX_Utilities.Box_96x96x96'


# ---------------------------------------------------------------- reading
def element_fields(p, raw):
    """{field: value} of one KConvexElem's tagged properties: arrays decoded to rows (FacePlaneData as saved, [w, x,
    y, z]), ElemBox [[min], [max], valid]; and the payload bytes of each field, for a value key."""
    r = Reader(raw)
    props = p.tagged(r)
    out, key = {}, []
    for (name, _), v in props.items():
        value = v['value']
        key.append((name, bytes(value)))
        if name == 'ElemBox':
            b = struct.unpack('<6fB', value)
            out[name] = [list(b[:3]), list(b[3:6]), b[6]]
        elif name in FORMATS:
            n = struct.unpack_from('<i', value, 0)[0]
            fmt = '<' + FORMATS[name]
            size = struct.calcsize(fmt)
            rows = [list(struct.unpack_from(fmt, value, 4 + size * k)) for k in range(n)]
            out[name] = [row[0] for row in rows] if FORMATS[name] == 'i' else rows
    return out, tuple(key), r.pos


def convex_elements(p, index):
    """[(fields, key)] of an RB_BodySetup's AggGeom.ConvexElems."""
    props, _ = p.properties(index)
    agg = props.get(('AggGeom', 0))
    if agg is None:
        return []
    geom = p.tagged(Reader(agg['value']))
    ce = geom.get(('ConvexElems', 0))
    if ce is None:
        return []
    raw = ce['value']
    r = Reader(raw)
    out = []
    for _ in range(r.count()):
        fields, key, used = element_fields(p, raw[r.pos:])
        r.pos += used
        out.append((fields, key))
    return out


def inventory(paths, listed, verbose=False):
    """{key: dict(fields, instances [(package, mesh, element)], listed)} over the packages, and counts."""
    elems, counts = {}, Counter()
    t0 = time.time()
    for n, path in enumerate(paths):
        try:
            p = Package(path)
        except Exception:
            counts['packages unreadable'] += 1
            continue
        counts['packages'] += 1
        found = 0
        for i in range(1, len(p.exports) + 1):
            if p.cls(i) != 'RB_BodySetup':
                continue
            counts['body setups'] += 1
            try:
                items = convex_elements(p, i)
            except Exception:
                counts['body setups unreadable'] += 1
                continue
            outer = p.exports[i - 1]['outer']
            mesh = p.paths[outer - 1] if outer > 0 else p.paths[i - 1]
            for k, (fields, key) in enumerate(items):
                e = elems.setdefault(key, dict(fields=fields, instances=[], listed=False))
                e['instances'].append((path.stem, mesh, k))
                e['listed'] |= path.stem.lower() in listed
                found += 1
        counts['instances'] += found
        if found:
            counts['packages with convex elements'] += 1
        if verbose and n % 200 == 0:
            print('  %4d/%d %-32s %6d elements so far, %ds' % (n, len(paths), path.name, counts['instances'],
                                                             time.time() - t0), flush=True)
    return elems, counts


from hulls import (  # noqa: E402  (the writer, moved into the tools: M6 item 3)
    COPLANAR_EDGE, F, PARALLEL, PLANE_W, RSQRT, _Melax,
    _RSQRT, _bits, _float, _merge_face, _rsqrt_table, add_dir,
    cooker_vertex, cross, derive, dot, dot87, elem_box,
    face_loops, fans, hull_element, inv_sqrt, permuted, physx_hull,
    plane_ids, rsqrtss, safe_normal, same_plane, sub, tri_rows,
    wedge)


# ---------------------------------------------------------------- comparing
def packed(field, value):
    if field == 'FaceTriData':
        return struct.pack('<%di' % len(value), *value)
    if field == 'ElemBox':
        return struct.pack('<6fB', *value[0], *value[1], value[2])
    return b''.join(struct.pack('<%df' % len(r), *[float(x) for x in r]) for r in value)


def ulps(a, b):
    ia, ib = _bits(a), _bits(b)
    ia = ia if ia < 0x80000000 else 0x80000000 - ia
    ib = ib if ib < 0x80000000 else 0x80000000 - ib
    return abs(ia - ib)


def plane_cause(saved, ours):
    """Why the planes differ: their count (a face rule), or per plane the normal, or the distance by n ulps (and
    whether a double-precision distance, as an x87 build of the tool computed it, gives the saved one)."""
    if len(saved) != len(ours):
        return Counter({'plane count differs': 1}), []
    causes, offs = Counter(), []
    for s, o in zip(saved, ours):
        if packed('x', [s]) == packed('x', [o]):
            continue
        if packed('x', [s[1:]]) != packed('x', [o[1:]]):
            causes['plane normal differs'] += 1
            continue
        u = ulps(s[0], o[0])
        offs.append(u)
        causes['plane distance off by %s ulp' % (u if u <= 3 else '>3')] += 1
    return causes, offs


def audit_element(f, corners=True):
    """{check: True/False} and causes for one element's saved fields."""
    V = f['VertexData']
    T = tri_rows(f['FaceTriData'])
    res, causes = {}, Counter()
    Vf = [[F(x) for x in v] for v in V]
    res['ElemBox'] = packed('ElemBox', elem_box(Vf)) == packed('ElemBox', f['ElemBox'])
    res['PermutedVertexData'] = packed('x', permuted(Vf)) == packed('x', f['PermutedVertexData'])
    normals, planes, edges, notes = derive(V, T)
    res['FaceNormalDirections'] = packed('x', normals) == packed('x', f['FaceNormalDirections'])
    res['FacePlaneData'] = packed('x', planes) == packed('x', f['FacePlaneData'])
    res['EdgeDirections'] = packed('x', edges) == packed('x', f['EdgeDirections'])
    for k, v in notes.items():
        causes[k] += v
    for field, ours in (('FaceNormalDirections', normals), ('EdgeDirections', edges)):
        if not res[field]:
            saved = f[field]
            if len(saved) != len(ours):
                causes[field + ': count differs'] += 1
            else:
                u = max(ulps(x, y) for s, o in zip(saved, ours) for x, y in zip(s, o))
                causes[field + ': a direction off by %s ulp' % (u if u <= 3 else '>3')] += 1
    offs = []
    if not res['FacePlaneData']:
        c, offs = plane_cause(f['FacePlaneData'], planes)
        causes.update(c)
    res['vertexRoundTrip'] = all(cooker_vertex(v) == [F(x) for x in v] for v in V)
    if corners:
        order, loops = physx_hull([[F(x) for x in v] for v in V])
        res['cornersOrder'] = order == list(range(len(V)))
        if res['cornersOrder'] and loops is not None:
            res['cornersFaceTriData'] = fans(loops) == list(f['FaceTriData'])
        else:
            res['cornersFaceTriData'] = False
        res['cornersAll'] = (res['cornersFaceTriData'] and res['ElemBox'] and res['PermutedVertexData']
                             and res['FaceNormalDirections'] and res['FacePlaneData'] and res['EdgeDirections'])
    res['trianglesAll'] = (res['ElemBox'] and res['PermutedVertexData'] and res['FaceNormalDirections']
                           and res['FacePlaneData'] and res['EdgeDirections'])
    return res, causes, offs


def physx_value(x):
    """The single-precision value h nearest x / 50 with h times 50 rounding to x (PhysX's vertex before UE3 scaled
    it), else x / 50."""
    x = F(x)
    h = F(x * F(0.02))
    best = None
    for step in range(-3, 4):
        c = h
        for _ in range(abs(step)):
            c = np.nextafter(c, F(np.inf) if step > 0 else F(-np.inf))
        if F(c * F(50.0)) == x and (best is None or abs(float(c) * 50 - float(x)) < abs(float(best) * 50 - float(x))):
            best = c
    return float(best) * 50.0 if best is not None else float(x)


def x87_planes(V, T, mode='double'):
    """FacePlaneData with each distance in double precision (an x87 build of the tools), the rest as derive's. mode
    'double': from the saved vertex and normal; 'vertex': from PhysX's vertex times 50 before it was rounded to single
    precision (physx_value); 'normal': from the normal before it was rounded (the cross product times the inverse
    length, kept in a register)."""
    V = [[F(x) for x in v] for v in V]
    planes = []
    for a, b, c in T:
        cr = cross(sub(V[c], V[a]), sub(V[b], V[a]))
        n = safe_normal(cr)
        pa = [physx_value(x) for x in V[a]] if mode == 'vertex' else [float(x) for x in V[a]]
        nn = [float(x) for x in n]
        s = dot(cr, cr)
        if mode == 'normal' and s != F(1.0) and not s < F(9.99999993922529e-09):
            k = float(inv_sqrt(s))
            nn = [float(x) * k for x in cr]
        w = F(pa[0] * nn[0] + pa[1] * nn[1] + pa[2] * nn[2])
        p = n + [w]
        if not any(same_plane(q, p) for q in planes):
            planes.append(p)
    return [[p[3]] + p[:3] for p in planes]


def shape_of(f):
    """'wedge' (6 corners, 5 faces: 2 triangles, 3 quads), 'hexahedron' (8 corners, 6 quads: boxes and the farm
    ramp's sloped boxes), else '<n> corners'."""
    loops = face_loops(f['VertexData'], tri_rows(f['FaceTriData']))
    sizes = sorted(len(lp) for lp in loops)
    n = len(f['VertexData'])
    if n == 6 and sizes == [3, 3, 4, 4, 4]:
        return 'wedge'
    if n == 8 and sizes == [4] * 6:
        return 'hexahedron'
    return '%d corners' % n


def audit(elems, corners=True, verbose=False):
    tally, weighted, by_shape, by_size = Counter(), Counter(), defaultdict(Counter), defaultdict(Counter)
    causes, offs_all, samples = Counter(), Counter(), defaultdict(list)
    x87 = Counter()
    farm = []
    t0 = time.time()
    for n, (key, e) in enumerate(elems.items()):
        f = e['fields']
        res, c, offs = audit_element(f, corners)
        inst = len(e['instances'])
        shape = shape_of(f)
        size = len(f['VertexData'])
        for k, v in res.items():
            tally[k, v] += 1
            weighted[k, v] += inst
            by_shape[shape][k, v] += 1
            by_size[size][k, v] += 1
        by_shape[shape]['elements'] += 1
        by_size[size]['elements'] += 1
        causes.update(c)
        for u in offs:
            offs_all[u if u <= 3 else '>3'] += 1
        if not res['FacePlaneData']:
            T = tri_rows(f['FaceTriData'])
            alts = [x87_planes(f['VertexData'], T, m) for m in ('double', 'vertex', 'normal')]
            hits = [packed('x', alt) == packed('x', f['FacePlaneData']) for alt in alts]
            ours = derive(f['VertexData'], T)[1]
            if all(len(x) == len(f['FacePlaneData']) for x in alts + [ours]):
                for i, s in enumerate(f['FacePlaneData']):
                    if packed('x', [s]) == packed('x', [ours[i]]):
                        continue
                    got = [m for m, alt in zip(('double', 'vertex', 'normal'), alts)
                           if packed('x', [alt[i]]) == packed('x', [s])]
                    x87['plane: ' + (' / '.join(got) if got else 'no variant')] += 1
            x87['distances in double precision give the saved planes', hits[0]] += 1
            x87['distances in double precision from the unrounded PhysX vertices give the saved planes', hits[1]] += 1
            x87['distances in double precision from the unrounded normals give the saved planes', hits[2]] += 1
            x87['any of the three', any(hits)] += 1
        mesh = e['instances'][0][1]
        for k, v in res.items():
            if not v and len(samples[k]) < 12:
                samples[k].append(dict(mesh=mesh, element=e['instances'][0][2], package=e['instances'][0][0],
                                       vertices=size, causes=dict(c)))
        if mesh == FARM_RAMP:
            farm.append(dict(element=e['instances'][0][2], vertices=size, triangles=len(f['FaceTriData']) // 3,
                             planes=len(f['FacePlaneData']), edges=len(f['EdgeDirections']),
                             faceNormals=len(f['FaceNormalDirections']), shape=shape,
                             faces=sorted(len(lp) for lp in face_loops(f['VertexData'], tri_rows(f['FaceTriData']))),
                             box=[[round(x, 3) for x in f['ElemBox'][0]], [round(x, 3) for x in f['ElemBox'][1]]],
                             **{k: v for k, v in res.items()}))
        if verbose and n % 250 == 0:
            print('  %4d/%d elements audited, %ds' % (n, len(elems), time.time() - t0), flush=True)
    farm.sort(key=lambda r: r['element'])
    return dict(tally=tally, weighted=weighted, by_shape=by_shape, by_size=by_size, causes=causes,
                planeDistanceUlps=offs_all, x87=x87, samples=samples, farm=farm)


def table(counter, checks):
    out = {}
    for k in checks:
        t, fl = counter.get((k, True), 0), counter.get((k, False), 0)
        if t or fl:
            out[k] = dict(exact=t, differ=fl)
    return out


LEGEND = dict(
    ElemBox='from VertexData: its box',
    PermutedVertexData='from VertexData: the fours, padded with their first vertex, saved W first',
    FaceNormalDirections="from VertexData and the saved FaceTriData, by the cooker's rules",
    FacePlaneData="from VertexData and the saved FaceTriData, by the cooker's rules",
    EdgeDirections="from VertexData and the saved FaceTriData, by the cooker's rules",
    trianglesAll='all five fields above',
    vertexRoundTrip="VertexData unchanged by the cooker's scaling (times 0.02, times 50, single precision)",
    cornersOrder='the emulated PhysX hull, handed the corners in their saved order, gives back that order',
    cornersFaceTriData='... and the saved FaceTriData',
    cornersAll='... and every field: the element from its corners alone')

CHECKS = ('ElemBox', 'PermutedVertexData', 'FaceNormalDirections', 'FacePlaneData', 'EdgeDirections',
          'trianglesAll', 'vertexRoundTrip', 'cornersOrder', 'cornersFaceTriData', 'cornersAll')


# ---------------------------------------------------------------- self-check
def _recipe_box():
    import cover_blocks
    spec = cover_blocks.recipe(1)['bodySetup']
    lo, hi = [-48.0] * 3, [48.0] * 3
    corners = [[(lo, hi)[c[a]][a] for a in range(3)] for c in spec['corners']]
    return cover_blocks, spec, lo, hi, corners


def _same(a, b):
    return all(packed(k, a[k]) == packed(k, b[k]) for k in FIELDS)


def _diff(a, b):
    return [k for k in FIELDS if packed(k, a[k]) != packed(k, b[k])]


def self_check(verbose=True):
    """Checks of the writer; returns [(name, passed, detail)]."""
    out = []
    cover_blocks, spec, lo, hi, corners = _recipe_box()
    theirs = cover_blocks.convex_hull(lo, hi, spec)
    loops = face_loops(theirs['VertexData'], tri_rows(theirs['FaceTriData']))
    ours = hull_element(corners, loops)
    out.append(('the recipe box (96 units) with its own face loops is cover_blocks.convex_hull, field for field',
                _same(ours, theirs), _diff(ours, theirs)))
    ours2 = hull_element(theirs['VertexData'])
    out.append(('the recipe box from its corners alone, in its saved order, is cover_blocks.convex_hull, field for '
                'field', _same(ours2, theirs), _diff(ours2, theirs)))
    # a box's corners tie in the hull's extreme-point searches, which take the first point of a tie: the order the
    # corners are handed over decides the saved order, as it did for the game's own tools
    orders = []
    for seed in range(6):
        shuffled = list(corners)
        random.Random(seed).shuffle(shuffled)
        orders.append(_diff(hull_element(shuffled), theirs))
    out.append(('the recipe box from shuffled corners: %d of 6 orders give its saved layout (information: the input '
                'order decides it)' % sum(not d for d in orders), True, orders))
    # the cover blocks' other sizes: cover_blocks writes the 96-unit box's directions for every size
    sizes = []
    for lo2, hi2 in (([0, 0, -12], [96, 96, 96]), ([0, 0, 0], [192, 96, 96]), ([-48, -48, -2], [48, 48, 0]),
                     ([0, 0, 0], [96, 96, 108]), ([0, 0, 0], [288, 96, 48])):
        lo2, hi2 = [float(v) for v in lo2], [float(v) for v in hi2]
        cb = cover_blocks.convex_hull(lo2, hi2, spec)
        cc = [[(lo2, hi2)[c[a]][a] for a in range(3)] for c in spec['corners']]
        mine = hull_element(cc, face_loops(cb['VertexData'], tri_rows(cb['FaceTriData'])))
        sizes.append(dict(box=[lo2, hi2], differ=_diff(mine, cb)))
    out.append(('cover_blocks boxes of other sizes against the cooker rules (information, not a failure)', True, sizes))
    # the farm ramp's ten hulls
    import labpaths
    path, why = labpaths.install_map('CsmallScout_Farm')
    if path is None or not path.exists():
        out.append(('the farm ramp\'s hulls', None, 'skipped: ' + why))
    else:
        p = Package(path)
        mesh = p.by_name.get(FARM_RAMP)
        body = next(i for i in p.children.get(mesh, []) if p.cls(i) == 'RB_BodySetup')
        elems = [fl for fl, _ in convex_elements(p, body)]
        given = exact = 0
        detail = []
        for k, f in enumerate(elems):
            loops = face_loops(f['VertexData'], tri_rows(f['FaceTriData']))
            a = hull_element(f['VertexData'], loops, round_trip=False)
            try:
                b = hull_element(f['VertexData'], round_trip=False)
                bd = _diff(b, f)
            except ValueError as err:
                bd = [str(err)]
            given += _same(a, f)
            exact += not bd
            detail.append(dict(element=k, vertices=len(f['VertexData']), fromTriangles=_diff(a, f), fromCorners=bd))
        out.append(('the farm ramp\'s %d hulls from their vertices and face loops, field for field' % len(elems),
                    given == len(elems), detail))
        out.append(('the farm ramp\'s hulls from their corners alone, in their saved order: %d of %d exact '
                    '(information)' % (exact, len(elems)), True, [d['fromCorners'] for d in detail]))
    # a wedge from numbers
    c, faces = wedge([192, 96], 96)
    w1 = hull_element(c, faces)
    w2 = hull_element(c)
    problems = []
    for w in (w1, w2):
        V = [[F(x) for x in v] for v in w['VertexData']]
        T = tri_rows(w['FaceTriData'])
        und = Counter(tuple(sorted(e)) for t in T for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])))
        if len(T) != 8 or any(v != 2 for v in und.values()):
            problems.append('not a closed 8-triangle wedge')
        for wpl in w['FacePlaneData']:
            d = [float(dot(v, wpl[1:])) - wpl[0] for v in V]
            if max(d) > 0.01 or sum(abs(x) <= 0.01 for x in d) < 3:
                problems.append('a plane does not bound the corners')
        if len(w['FacePlaneData']) != 5 or len(w['FaceNormalDirections']) != 4 or len(w['EdgeDirections']) != 4:
            problems.append('planes %d, face directions %d, edge directions %d' % (
                len(w['FacePlaneData']), len(w['FaceNormalDirections']), len(w['EdgeDirections'])))
    out.append(('a wedge 192 x 96 rising 96, with given faces and from its corners: closed, bounded, 5 planes, '
                '4 face and 4 edge directions', not problems, problems))
    # the rsqrtss table against values the cooker saved
    unit = struct.unpack('<f', struct.pack('<f', 0.99999994))[0]
    checks = [safe_normal([96.0, 0.0, 0.0])[0] == F(unit), safe_normal([-512.0, 0, 0])[0] == F(-unit),
              safe_normal([0, -248.88052368164062, 0])[1] == F(-1.0), safe_normal([0, 0, 14.999999046325684])[2] == F(1.0)]
    out.append(('the rsqrtss table gives the saved unit lengths (0.99999994 for 96 and 512, 1 for 248.88 and 15)',
                all(checks), checks))
    if verbose:
        for name, ok, detail in out:
            print('%-6s %s' % ({True: 'ok', False: 'FAIL', None: 'skip'}[ok], name))
            if ok is not True or 'information' in name:
                print('       ', detail)
    return out


# ---------------------------------------------------------------- main
def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('--maps', nargs='*', help='package names (default: every package in the cooked folder)')
    a.add_argument('--listed-only', action='store_true', help='only the maps the install lists (the editor\'s donors)')
    a.add_argument('--no-corners', action='store_true', help='skip the from-corners emulation (faster)')
    a.add_argument('--output', type=Path)
    a.add_argument('--self-check', action='store_true')
    a.add_argument('--verbose', action='store_true')
    args = a.parse_args()
    if args.self_check:
        results = self_check()
        sys.exit(0 if all(ok is not False for _, ok, _ in results) else 1)
    import library
    import settings
    game, _ = settings.game_install(settings.load_settings())
    cooked = library.cooked_of(game)
    listed = {n.lower() for n, _, _ in library.donors(game)}
    paths = sorted(cooked.glob('*.upk'))
    if args.listed_only:
        paths = [q for q in paths if q.stem.lower() in listed]
    if args.maps:
        want = {m.casefold() for m in args.maps}
        paths = [q for q in paths if q.stem.casefold() in want]
    t0 = time.time()
    elems, counts = inventory(paths, listed, args.verbose)
    t1 = time.time()
    r = audit(elems, not args.no_corners, args.verbose)
    t2 = time.time()
    meshes = {i[1] for e in elems.values() for i in e['instances']}
    listed_elems = [e for e in elems.values() if e['listed']]
    summary = dict(
        packages=counts['packages'], packagesUnreadable=counts['packages unreadable'],
        packagesWithConvexElements=counts['packages with convex elements'], bodySetups=counts['body setups'],
        bodySetupsUnreadable=counts['body setups unreadable'], instances=counts['instances'],
        uniqueElements=len(elems), meshes=len(meshes), uniqueElementsInListedMaps=len(listed_elems),
        instancesInListedMaps=sum(1 for e in listed_elems for i in e['instances'] if i[0].lower() in listed),
        checksUnique=table(r['tally'], CHECKS), checksByInstance=table(r['weighted'], CHECKS),
        causes=dict(r['causes']), planeDistanceUlps={str(k): v for k, v in sorted(r['planeDistanceUlps'].items(),
                                                                                  key=str)},
        planesWithDoublePrecisionDistance={(k if isinstance(k, str) else '%s %s' % k): v
                                           for k, v in sorted(r['x87'].items(), key=str)},
        seconds=dict(read=round(t1 - t0), audit=round(t2 - t1)))
    result = dict(
        scope='Read-only: the convex elements (RB_BodySetup AggGeom.ConvexElems) of %d packages of the install\'s '
              'cooked folder; nothing written to the game' % counts['packages'],
        rules='research/evidence/hull-audit.py docstring: the cooker is XComEW.exe FKConvexElem::GenerateHullData '
              '(0x8871C0) over PhysX 2.8\'s hull',
        summary=summary, checks=LEGEND,
        byShape={k: dict(elements=v['elements'], **table(v, CHECKS)) for k, v in sorted(r['by_shape'].items())},
        byVertexCount={str(k): dict(elements=v['elements'], **table(v, CHECKS)) for k, v in sorted(r['by_size'].items())},
        farmRamp=r['farm'],
        samples={k: v for k, v in r['samples'].items()},
        selfCheck=[dict(check=name, passed=ok, detail=detail) for name, ok, detail in self_check(verbose=False)])
    print(json.dumps(summary, indent=1))
    print(json.dumps(result['byShape'], indent=1))
    if args.output:
        args.output.write_text(json.dumps(result, indent=1, default=str) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
