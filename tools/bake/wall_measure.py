"""A fracturing wall's look measured from a donor (custom geometry plan, stage M4 item 2: "measured, not typed"): the
measurer of the walls' looks, moved here from research/evidence/wall-look-measure.py (which is now a wrapper of it).

VERSION is the measurer's version, which a request's look names (`look: {mesh, measure}`): a later measurer is a new
version, and this one stays.

It reads one FracturedStaticMesh of a map of the install (by the map and the mesh's name, or a placed actor's),
turns it into the wall's own frame (along x, its thickness along y, z up: a mesh that runs along y is turned a
quarter, (x, y) -> (y, -x)) and measures, from LOD 0:

  heights     bottom and top: the mesh's lowest and highest corners; the main faces: the plane facing +y and the
              plane facing -y that hold the most area, `half` half the distance between them, `centre` their middle
              line's offset from the mesh's y 0 (every y below is from that line)
  cuts        the mesh cut across its length by planes x = c every 4 units clear of its ends (its inside faces left
              out): each cut's outline on the +y side (the highest y of the segments facing +y at each height) and
              the -y side, sampled every unit up. Cuts within the edge zone of the wall's ends and of its openings'
              sides (its whole thickness and 2 units: mitred corners, door jambs, trims returning round an end) are
              judged apart, as end details. The others are compared with the median of those with no hole (within 1
              unit, leaving out 3 units by a hole's edge): all agree, swept (as the Bar's inside wall); all agree
              where they have faces, swept with openings; those with no hole agree and only cuts through openings
              differ, swept with framed openings; nine in ten agree, mostly swept (a local detail, with where); else
              modelled (window frames, cladding, ledges, ribs; an L piece, whose faces across x hold more than a fifth
              of those along it, is modelled too)
  section     over up to 25 agreeing cuts with no hole: the +y side's outline (the segments facing +y, and ledges
              wholly on that side but for the caps, chained bottom to top and cut down to its corners within 0.1 unit)
              as [y, z, v], v the trim set's texture v at the corner (the trim slots' segment ends there, the median
              over the cuts; null where no trim meets it). The -y side's the same way, mirrored: when it differs in
              shape or in its trims' v the entry has it as `sectionB`
  face        the z range of the +y side's straight run on its main plane
  slots       each section's role from its triangles' directions and heights: a side's face (six tenths of its area on
              that side's main plane), both sides' (a quarter on each: one material on both faces; then each side's
              face slots are those), a trim (the rest: sloping, capping and stepped faces; one that also holds a tenth
              of its area on the main planes carries the faces, one unwrap for the whole outline, as the UFOs'
              walls), the inside faces (the mesh's interior section); a side whose face slots split at one height
              gives `storey` (and `storeyB` when the -y side's split elsewhere)
  texture     u = a x + b z + c and v = d x + e z + f over each face slot's triangles on its plane, the slopes the
              median of each triangle's own gradient and the offset the commonest, then least squares with each
              vertex's whole-number shift taken off (islands shifted by whole numbers draw the same): faceRepeat
              (1 / |a| along, 1 / |e| up), faceU (c), faceV (f, per side); the trims' u = a x + c on their sloping and
              upright strips (trimRepeat, trimU as frac_wall writes them, u = -side (x / trimRepeat + trimU)); the
              top and bottom caps' v = c0 + c1 y (topV, bottomV)
  colours     the vertex colours (B, G, R, A, as hex) of the outside and of the inside faces: one value (a constant) or
              how many, with the commonest; the rule (constant or varying) is the outside faces'
  cell        the fragment grid that matches the donor: counts along and up (nx, nz) whose product is nearest the
              fragment count and whose cells' shape is nearest the fragments' median box (the cost 2 |ln(nx nz / N)| +
              |ln(cell aspect / box aspect)|), the cell (the solid's length / nx, its height / nz); the fragments'
              median box; how uneven the fragments are (the spread of their areas on the +y face)
  collision   the BodySetup's simple collision (tools/viewer/collision.py): its elements and their half thickness
  lightmap    texels a unit on the main faces: the lightmap texture coordinates' (the mesh's LightMapCoordinateIndex
              channel) area times the component's lightmap rectangle in texels (its record's coordinate scale times its
              atlas's size; the resolution when it has no record), over the faces' own area; the inside faces' against it
  endInset    how far the solid's ends stop short of the tile edges: of the level's grid (native_copy.level_grid's
              corner) for a placed actor, else of the mesh's own 96 grid; the entry takes the end that stops
              shortest (a free end, as RECIPE's: the other may meet a wall), both are under `measured`

The entry has RECIPE's keys; what it cannot measure (the cells' jitter: the donors' cells are not on a grid; the
lightmap's packing margin and block: the Build's own choices) is listed under `notMeasured` with why. Diagnostics
(each slot's areas and fits, the cuts) go under `measured`.

measure_raw(package, what) gives that entry (the research script's output). check(result, recipe) compares an entry
with a recipe key by key (the research script's --check: URB_Bar's donor against frac_wall.RECIPE, within
CHECK_TOLERANCE). No game file is written.
"""
from collections import Counter
import math
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
for folder in ('viewer', 'upk', 'lab'):
    sys.path.insert(0, str(HERE.parent / folder))
sys.path.insert(0, str(HERE))
import gen_mesh  # noqa: E402

VERSION = 1
FRACTURING = ('XComDecoFracLevelActor', 'XComFracLevelActor')
TILE, STOREY, LEVEL = 96.0, 192.0, 64.0
FLAT = 0.99         # a triangle whose normal is this close to an axis faces along it
PLANE = 0.5         # units: a face this close to a main plane is on it
STEP = 4.0          # units between cuts
END_CLEAR = 6.0     # no cut this close to an end
AGREE = 1.0         # units: cuts this close to the median agree
NEAR_EDGE = 3       # samples (units) next to a hole's edge left out of the comparison
SIMPLIFY = 0.1      # units: an outline's corner this close to the line past it is dropped
PICKS = 25          # the agreeing cuts the section's corners are taken over (spread along the wall)
BAR = ('URB_Bar', 'XComDecoFracLevelActor_17')
CHECK_TOLERANCE = {'bottom': 0.05, 'top': 0.05, 'storey': 0.5, 'face': 0.5, 'half': 0.05, 'endInset': 0.5,
                   'section_y': 0.1, 'section_z': 0.5, 'section_v': 0.01, 'faceRepeat': 1.0, 'faceV': 0.02,
                   'faceU': 0.02, 'trimRepeat': 1.0, 'trimU': 0.02, 'topV': [0.01, 0.0005], 'bottomV': [0.01, 0.0005],
                   'collisionHalf': 0.05, 'density': 0.02, 'interiorDensity': 0.1}


# ---------------------------------------------------------------------------------------------------- the donor
def install_package(name):
    import labpaths
    from package import Package
    path = labpaths.lwr_cooked(name + '.upk')
    if path is None or not path.exists():
        raise SystemExit('%s.upk is not in the configured install (python tools/viewer/viewer.py settings)' % name)
    return Package(path)


def placed(p, mesh=None):
    """[(actor, component, mesh)] of the persistent level's fracturing pieces (of mesh export `mesh` when given)."""
    level = p.by_name.get('TheWorld.PersistentLevel')
    out = []
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) not in FRACTURING or p.exports[i - 1]['outer'] != level:
            continue
        comp = p.own(i, 'FracturedStaticMeshComponent')
        if not comp or comp < 0:
            continue
        m = p.own(comp, 'StaticMesh')
        if not m or m < 0 or p.cls(m) != 'FracturedStaticMesh':
            continue
        if mesh is None or m == mesh:
            out.append((i, comp, m))
    return out


def find(p, what):
    """(actor or None, component or None, mesh) for `what`: an actor's name (XComDecoFracLevelActor_17, or its full
    path) or a mesh's full name (its first placed piece's component then gives the materials and the lightmap)."""
    for key in (what, 'TheWorld.PersistentLevel.' + what):
        i = p.by_name.get(key)
        if i and p.cls(i) in FRACTURING:
            comp = p.own(i, 'FracturedStaticMeshComponent')
            return i, comp, p.own(comp, 'StaticMesh')
    i = p.by_name.get(what)
    if i and p.cls(i) == 'FracturedStaticMesh':
        pieces = placed(p, i)
        return (pieces[0][0], pieces[0][1], i) if pieces else (None, None, i)
    raise SystemExit('%s is neither a fracturing piece nor a fracturing mesh of %s' % (what, p.path.name))


# ---------------------------------------------------------------------------------------------------- geometry
def geometry(p, mesh):
    """The mesh's LOD 0 in the wall's frame: positions, triangles (indices, slot, fragment), outward normals,
    areas, the texture coordinates of channel 0 and of the lightmap channel, colours, the interior slot."""
    m = gen_mesh.read(p, mesh)
    lod = m['lods'][0]
    pos = np.array(lod['positions'], float)
    ext = pos.max(0) - pos.min(0)
    turned = bool(ext[1] > ext[0])
    if turned:
        pos = np.c_[pos[:, 1], -pos[:, 0], pos[:, 2]]
    idx = np.array(lod['indices'][1], np.int64).reshape(-1, 3)
    slot = np.full(len(idx), -1)
    frag = np.full(len(idx), -1)
    for s in lod['sections']:
        slot[s['first'] // 3:s['first'] // 3 + s['triangles']] = s['slot']
        for f, (first, count) in enumerate(s['fragments']):
            frag[first // 3:first // 3 + count] = f
    tri = pos[idx]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = 0.5 * np.linalg.norm(cross, axis=1)
    # UE3's front faces wind clockwise seen from outside (frac_wall.build): the outward normal is -cross
    normal = -cross / np.maximum(2 * area, 1e-12)[:, None]
    channels = lod['texcoords']
    lm_channel = p.effective(mesh, 'LightMapCoordinateIndex', 1)
    uv0 = np.array([v[2][0] for v in lod['vertices']], float)
    uv1 = np.array([v[2][lm_channel] for v in lod['vertices']], float) if 0 <= lm_channel < channels else None
    interior = m['fractured']['interior']
    return dict(m=m, mesh=mesh, name=p.name(mesh), turned=turned, pos=pos, idx=idx, tri=tri, slot=slot, frag=frag,
                normal=normal, area=area, uv0=uv0, uv1=uv1, lmChannel=lm_channel, colours=lod['colours'],
                interior=interior, outside=slot != interior, fragments=len(m['fractured']['fragments']),
                slots=sorted({int(s['slot']) for s in lod['sections']}))


def weighted_plane(values, weights):
    """The value holding the most weight (0.25-unit bins), refined to the weighted mean within PLANE of it."""
    if not len(values):
        return None
    bins = np.round(values / 0.25)
    total = Counter()
    for b, w in zip(bins, weights):
        total[b] += w
    best = max(total, key=total.get) * 0.25
    near = np.abs(values - best) < PLANE
    return float(np.average(values[near], weights=weights[near]))


def main_planes(g):
    """The main faces' planes: (y of the +y face, y of the -y face, centre, half)."""
    ty = g['tri'][:, :, 1].mean(1)
    a = g['outside'] & (g['normal'][:, 1] > FLAT)
    b = g['outside'] & (g['normal'][:, 1] < -FLAT)
    ya = weighted_plane(ty[a], g['area'][a])
    yb = weighted_plane(ty[b], g['area'][b])
    if ya is None or yb is None:
        return ya, yb, 0.0, None
    return ya, yb, (ya + yb) / 2, (ya - yb) / 2


# ---------------------------------------------------------------------------------------------------- cuts
def cut(g, x):
    """The outside triangles cut by the plane at x: dict(slot, a, b ([y, z] ends), uva, uvb, normal) arrays."""
    tri = g['tri']
    d = tri[:, :, 0] - x
    pos_side = d >= 0
    n_pos = pos_side.sum(1)
    sel = g['outside'] & (n_pos > 0) & (n_pos < 3)
    t, dd, ps = tri[sel], d[sel], pos_side[sel]
    uv = g['uv0'][g['idx'][sel]]
    pts, uvs = [], []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        crossing = ps[:, i] != ps[:, j]
        s = np.where(crossing, dd[:, i] / np.where(crossing, dd[:, i] - dd[:, j], 1.0), 0.0)
        pts.append((t[:, i] + s[:, None] * (t[:, j] - t[:, i]), crossing))
        uvs.append(uv[:, i] + s[:, None] * (uv[:, j] - uv[:, i]))
    cr = np.stack([c for _, c in pts], 1)                  # n x 3: which edges cross (always two)
    P = np.stack([p for p, _ in pts], 1)
    U = np.stack(uvs, 1)
    first = np.argmax(cr, 1)
    second = 2 - np.argmax(cr[:, ::-1], 1)
    rows = np.arange(len(P))
    return dict(slot=g['slot'][sel], normal=g['normal'][sel], a=P[rows, first][:, 1:], b=P[rows, second][:, 1:],
                uva=U[rows, first], uvb=U[rows, second])


def outline(c, zs, centre):
    """The cut's outer outline sampled at heights zs: (+y side's y, -y side's y), NaN where the side has no face."""
    a, b = c['a'], c['b']
    if not len(a):                  # a cut through an opening as tall as the wall
        return np.full(len(zs), np.nan), np.full(len(zs), np.nan)
    dz = b[:, 1] - a[:, 1]
    ok = np.abs(dz) > 1e-6
    lo, hi = np.minimum(a[:, 1], b[:, 1]), np.maximum(a[:, 1], b[:, 1])
    t = (zs[None, :] - a[:, 1:2]) / np.where(ok, dz, 1.0)[:, None]
    y = a[:, 0:1] + t * (b[:, 0:1] - a[:, 0:1]) - centre
    inside = ok[:, None] & (zs[None, :] >= lo[:, None]) & (zs[None, :] <= hi[:, None])
    # each segment's side by the way it faces (a wall that leans, as the UFOs' do, crosses its middle line)
    ny = c['normal'][:, 1]
    plus = np.where(inside & (ny > 0.02)[:, None], y, -np.inf).max(0)
    minus = np.where(inside & (ny < -0.02)[:, None], y, np.inf).min(0)
    return np.where(np.isfinite(plus), plus, np.nan), np.where(np.isfinite(minus), -minus, np.nan)


def sweep(g, centre, half):
    """The cuts along the wall and how they agree: dict(xs, verdict, ...). The cuts within an edge zone of the
    wall's ends and of its openings' sides (the mesh's whole thickness and 2 units: mitred corners, door jambs, trims
    returning round an end) are judged apart, as its end details."""
    pos = g['pos']
    x0, x1 = float(pos[:, 0].min()), float(pos[:, 0].max())
    z0, z1 = float(pos[:, 2].min()), float(pos[:, 2].max())
    zs = np.arange(z0 + 0.5, z1, 1.0)
    # off whole numbers, so no cut runs along a vertex column
    xs = np.arange(x0 + END_CLEAR + 0.37, x1 - END_CLEAR, STEP)
    if len(xs) < 3:
        xs = np.linspace(x0 + 0.25 * (x1 - x0), x1 - 0.25 * (x1 - x0), 3) + 0.37
    rows = [outline(cut(g, x), zs, centre) for x in xs]
    plus = np.array([r[0] for r in rows])
    minus = np.array([r[1] for r in rows])
    defined = ~np.isnan(plus) & ~np.isnan(minus)
    cover = defined.mean(1)
    full = cover >= 0.98 * cover.max()
    holed = ~full
    # the openings: runs of holed cuts, each with the heights its cuts miss
    openings, edges = [], [x0, x1]
    k = 0
    while k < len(xs):
        if holed[k]:
            j = k
            while j + 1 < len(xs) and holed[j + 1]:
                j += 1
            gone = zs[~defined[k:j + 1].all(0)]
            through = zs[~defined[k:j + 1].any(0)]
            a = float(xs[k]) - STEP / 2 if k else x0
            b = float(xs[j]) + STEP / 2 if j < len(xs) - 1 else x1
            openings.append(dict(x=[round(a, 1), round(b, 1)],
                                 z=[round(float(gone.min()) - 0.5, 1), round(float(gone.max()) + 0.5, 1)] if len(gone) else None,
                                 through=[round(float(through.min()) - 0.5, 1), round(float(through.max()) + 0.5, 1)]
                                 if len(through) else None))
            edges += [a, b]
            k = j + 1
        else:
            k += 1
    zone = max(END_CLEAR, float(np.ptp(pos[:, 1])) + 2)
    near_edge = np.array([min(abs(x - e) for e in edges) < zone for x in xs])
    body = ~near_edge if (~near_edge).sum() >= 3 else np.ones(len(xs), bool)
    basis = full & body if (full & body).sum() >= 3 else (full if full.sum() >= 3 else np.ones(len(xs), bool))
    with np.errstate(all='ignore'):
        ref_p = np.nanmedian(np.where(basis[:, None], plus, np.nan), 0)
        ref_m = np.nanmedian(np.where(basis[:, None], minus, np.nan), 0)
    dev = []
    for k in range(len(xs)):
        ok = defined[k].copy()
        # leave out the samples next to a hole's edge (a sill or lintel's own rounding)
        holes = ~defined[k]
        if holes.any():
            near = np.convolve(holes.astype(int), np.ones(2 * NEAR_EDGE + 1, int), 'same') > 0
            ok &= ~near
        ok &= ~np.isnan(ref_p) & ~np.isnan(ref_m)
        if not ok.any():
            dev.append(float('inf'))
            continue
        dev.append(float(max(np.abs(plus[k][ok] - ref_p[ok]).max(), np.abs(minus[k][ok] - ref_m[ok]).max())))
    dev = np.array(dev)
    agree = dev < AGREE
    corner = corner_piece(g)
    share = float(agree[body].mean())
    if corner:
        verdict = 'modelled'
    elif agree[body].all():
        verdict = 'swept with openings' if openings else 'swept'
    elif agree[body & full].all():
        # the wall between its openings is swept; what differs is in the openings (frames, a door's own trims)
        verdict = 'swept, framed openings'
    elif share >= 0.9:
        verdict = 'mostly swept'
    else:
        verdict = 'modelled'
    # where the body's cuts differ, as runs along the wall
    differ = []
    for k in np.nonzero(body & ~agree)[0]:
        x = float(xs[k])
        if differ and x - differ[-1][1] <= STEP + 1e-6:
            differ[-1][1] = x
        else:
            differ.append([x, x])
    edge_bad = near_edge & ~agree
    best = int(np.argmin(np.where(basis & agree, dev, np.inf))) if (basis & agree).any() else int(np.argmin(dev))
    return dict(xs=xs, zs=zs, plus=plus, minus=minus, dev=dev, agree=agree, full=full, basis=basis,
                verdict=verdict, corner=corner, openings=openings, reference=best,
                agreeShare=round(share, 3), cuts=len(xs), holedCuts=int(holed.sum()),
                bodyCuts=int(body.sum()), edgeZone=round(zone, 1),
                differAt=[[round(a, 1), round(b, 1)] for a, b in differ],
                worst=round(float(dev[body][np.isfinite(dev[body])].max()), 2) if np.isfinite(dev[body]).any() else None,
                endDetail=dict(cuts=int(edge_bad.sum()), worst=round(float(dev[edge_bad][np.isfinite(dev[edge_bad])].max()), 2)
                               if np.isfinite(dev[edge_bad]).any() else None,
                               reach=round(max(min(abs(float(xs[k]) - e) for e in edges) for k in np.nonzero(edge_bad)[0]), 1)
                               if edge_bad.any() else 0.0))


def corner_piece(g):
    """Whether the mesh has big faces along both axes (an L or a corner piece): the outside area facing +-x is more
    than a fifth of that facing +-y."""
    n, a, out = g['normal'], g['area'], g['outside']
    along_y = a[out & (np.abs(n[:, 1]) > FLAT)].sum()
    along_x = a[out & (np.abs(n[:, 0]) > FLAT)].sum()
    return bool(along_y > 0 and along_x > 0.2 * along_y)


def flat_share(g, ya, yb):
    """The share of the outside area on the two main planes, and each side's main plane's area over length x height."""
    n, a, out = g['normal'], g['area'], g['outside']
    ty = g['tri'][:, :, 1].mean(1)
    on_a = out & (n[:, 1] > FLAT) & (np.abs(ty - ya) < PLANE)
    on_b = out & (n[:, 1] < -FLAT) & (np.abs(ty - yb) < PLANE)
    pos = g['pos']
    box = float(np.ptp(pos[:, 0]) * np.ptp(pos[:, 2]))
    total = float(a[out].sum())
    return dict(flatShare=round(float(a[on_a | on_b].sum()) / total, 3) if total else None,
                faceCoverA=round(float(a[on_a].sum()) / box, 3) if box else None,
                faceCoverB=round(float(a[on_b].sum()) / box, 3) if box else None)


# ---------------------------------------------------------------------------------------------------- the section
def side_chain(c, centre, side, bottom, top):
    """The cut's outline on one side (+1 or -1) as a path [(y from the centre, z, segment indices at each corner)]
    from bottom to top: the segments facing that way, and ledges (flat segments) wholly on that side but for the
    bottom and top caps."""
    a, b, n = c['a'], c['b'], c['normal']
    ya, yb = (a[:, 0] - centre) * side, (b[:, 0] - centre) * side
    facing = n[:, 1] * side > 0.02
    zm = (a[:, 1] + b[:, 1]) / 2
    ledge = ((np.abs(n[:, 2]) > 0.98) & (np.minimum(ya, yb) > 0.5)
             & (np.abs(zm - bottom) > PLANE) & (np.abs(zm - top) > PLANE))
    keep = np.nonzero(facing | ledge)[0]
    if not len(keep):
        return []
    # the ends merged within 0.03 units
    nodes, key_of = [], {}

    def node(y, z):
        k = (round(y / 0.03), round(z / 0.03))
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                hit = key_of.get((k[0] + dy, k[1] + dz))
                if hit is not None and abs(nodes[hit][0] - y) < 0.03 and abs(nodes[hit][1] - z) < 0.03:
                    return hit
        key_of[k] = len(nodes)
        nodes.append((y, z))
        return len(nodes) - 1
    edges = {}
    for s in keep:
        u = node(float(ya[s]), float(a[s, 1]))
        v = node(float(yb[s]), float(b[s, 1]))
        if u == v:
            continue
        edges.setdefault(u, []).append((v, s))
        edges.setdefault(v, []).append((u, s))
    if not edges:
        return []
    ends = [k for k, e in edges.items() if len(e) == 1]
    start = min(ends or edges, key=lambda k: (nodes[k][1], -nodes[k][0]))
    path, segs, seen, at, prev = [start], [[]], set(), start, None
    while True:
        nxt = [(v, s) for v, s in edges[at] if s not in seen]
        if not nxt:
            break
        # straight on where the path branches (a T-junction's sliver): the step going highest
        v, s = max(nxt, key=lambda e: (nodes[e[0]][1], nodes[e[0]][0]))
        seen.add(s)
        segs[-1].append(s)
        path.append(v)
        segs.append([s])
        at = v
    return [(nodes[k][0], nodes[k][1], segs[i]) for i, k in enumerate(path)]


def simplify(points, eps=SIMPLIFY):
    """Douglas-Peucker on [(y, z, ...)]: the corners that matter, the first and last kept."""
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        (ya, za), (yb, zb) = points[i][:2], points[j][:2]
        dy, dz = yb - ya, zb - za
        ln = math.hypot(dy, dz) or 1e-12
        far, at = 0.0, None
        for k in range(i + 1, j):
            d = abs((points[k][0] - ya) * dz - (points[k][1] - za) * dy) / ln
            if d > far:
                far, at = d, k
        if at is not None and far > eps:
            keep[at] = True
            stack += [(i, at), (at, j)]
    return [p for p, k in zip(points, keep) if k]


def corner_v(c, corner, trims):
    """The trim set's v at a corner of the outline: the trim slots' segment ends there (their median), or None."""
    y, z, segs = corner
    vs = []
    for s in segs:
        if int(c['slot'][s]) not in trims:
            continue
        for end, uv in ((c['a'][s], c['uva'][s]), (c['b'][s], c['uvb'][s])):
            if abs(end[1] - z) < 0.05:
                vs.append(float(uv[1]))
    return float(np.median(vs)) if vs else None


def section(g, sw, centre, trims):
    """The section's corners [y, z, v] on the +y side (the median over the agreeing full cuts that have the reference
    cut's corners), the -y side's corners mirrored, and how the sides compare: 'mirror', 'mirror, other v' (the same
    outline, the trims' v differ) or 'differs'."""
    picks = [k for k in range(len(sw['xs'])) if sw['basis'][k] and sw['agree'][k]] or [sw['reference']]
    if len(picks) > PICKS:
        picks = sorted({picks[round(i * (len(picks) - 1) / (PICKS - 1))] for i in range(PICKS)} | {sw['reference']}
                       & set(picks))
    bottom, top = float(g['pos'][:, 2].min()), float(g['pos'][:, 2].max())
    out = {}
    for side in (1, -1):
        sets = []
        for k in picks:
            c = cut(g, sw['xs'][k])
            corners = simplify(side_chain(c, centre, side, bottom, top))
            sets.append([(y, z, corner_v(c, p, trims)) for p, (y, z, _) in zip(corners, corners)])
        ref = sets[picks.index(sw['reference'])] if sw['reference'] in picks else sets[0]
        same = [s for s in sets if len(s) == len(ref) and all(abs(a[1] - b[1]) < 1.0 for a, b in zip(s, ref))]
        rows = []
        for i in range(len(ref)):
            ys = [s[i][0] for s in same]
            zs = [s[i][1] for s in same]
            vs = [s[i][2] for s in same if s[i][2] is not None]
            rows.append([round(float(np.median(ys)), 3), round(float(np.median(zs)), 3),
                         round(float(np.median(vs)), 4) if vs else None])
        out[side] = dict(corners=rows, cuts=len(same), of=len(sets))
    mirror = len(out[1]['corners']) == len(out[-1]['corners']) and all(
        abs(a[0] - b[0]) < 0.25 and abs(a[1] - b[1]) < 0.5 for a, b in zip(out[1]['corners'], out[-1]['corners']))
    same_v = mirror and all((a[2] is None) == (b[2] is None) and (a[2] is None or abs(a[2] - b[2]) < 0.01)
                            for a, b in zip(out[1]['corners'], out[-1]['corners']))
    return out[1], out[-1], 'mirror' if same_v else 'mirror, other v' if mirror else 'differs'


def face_run(corners, half):
    """The z range of the outline's straight upright run on the main plane (the longest), or None."""
    best = None
    for (ya, za, _), (yb, zb, _) in zip(corners, corners[1:]):
        if abs(ya - half) < 0.25 and abs(yb - half) < 0.25 and zb - za > (best[1] - best[0] if best else 0):
            best = [za, zb]
    return best


# ---------------------------------------------------------------------------------------------------- slots
def slot_roles(g, ya, yb, materials):
    """Per slot: its areas by direction, its role and heights."""
    n, a = g['normal'], g['area']
    ty = g['tri'][:, :, 1].mean(1)
    rows = {}
    for s in g['slots']:
        mask = g['slot'] == s
        total = float(a[mask].sum())
        on_a = mask & (n[:, 1] > FLAT) & (np.abs(ty - ya) < PLANE)
        on_b = mask & (n[:, 1] < -FLAT) & (np.abs(ty - yb) < PLANE)
        ends = mask & (np.abs(n[:, 0]) > FLAT)
        up = mask & (n[:, 2] > FLAT)
        down = mask & (n[:, 2] < -FLAT)
        off_a = mask & (n[:, 1] > FLAT) & ~on_a
        off_b = mask & (n[:, 1] < -FLAT) & ~on_b
        other = mask & ~(on_a | on_b | ends | up | down | off_a | off_b)
        share = {k: round(float(a[v].sum()) / total, 3) if total else 0.0 for k, v in
                 (('faceA', on_a), ('faceB', on_b), ('ends', ends), ('up', up), ('down', down), ('steppedA', off_a),
                  ('steppedB', off_b), ('sloping', other))}
        if s == g['interior']:
            role = 'interior'
        elif share['faceA'] >= 0.6:
            role = 'sideA'
        elif share['faceB'] >= 0.6:
            role = 'sideB'
        elif share['faceA'] >= 0.25 and share['faceB'] >= 0.25:
            role = 'bothSides'
        else:
            role = 'trim'
        zr = None
        # a trim slot that also holds main-plane faces carries them (one unwrap for the whole section, as the UFO
        # walls have it)
        carries = role == 'trim' and share['faceA'] + share['faceB'] >= 0.1
        plane = on_a if role == 'sideA' else on_b if role == 'sideB' else on_a | on_b
        if plane.any():
            zt = g['tri'][plane][:, :, 2]
            zr = [round(float(zt.min()), 2), round(float(zt.max()), 2)]
        rows[s] = dict(slot=int(s), role=role, triangles=int(mask.sum()), area=round(total, 1), share=share,
                       faceZ=zr, material=materials.get(s), carriesFaces=carries)
    return rows


def storey_split(rows, role):
    """A side's face slots, lowest first, and the heights they split at ([] for one slot)."""
    face = sorted((r for r in rows.values() if r['role'] == role and r['faceZ']), key=lambda r: r['faceZ'][0])
    splits = [round((lo['faceZ'][1] + hi['faceZ'][0]) / 2, 2) for lo, hi in zip(face, face[1:])]
    return [r['slot'] for r in face], splits


def materials_of(p, comp):
    """{slot: the material the component binds there} (its Materials; a slot it leaves empty says None)."""
    if not comp:
        return {}
    raw = p.own(comp, 'Materials')
    refs = p.refs(raw) if raw is not None else []
    return {k: (p.name(r) if r else None) for k, r in enumerate(refs)}


# ---------------------------------------------------------------------------------------------------- texture
def fit(points, values):
    """Least squares values = points @ k (points with a column of ones last): (k, rms)."""
    k, *_ = np.linalg.lstsq(points, values, rcond=None)
    return k, float(np.sqrt(np.mean((points @ k - values) ** 2)))


def unwrapped_fit(g, mask, axes, channel):
    """value = k0 p0 + k1 p1 + c over the triangles `mask`, p the positions' `axes` (two of x 0, y 1, z 2) and value
    the texture channel's coordinate `channel` (0 u, 1 v): the slopes from the median of each triangle's own gradient
    (so islands shifted by whole numbers, which draw the same, don't bend them), the offset the commonest (0.01
    bins), then least squares with each vertex's whole-number shift taken off. dict(k [k0, k1, c], rms, shifted (the
    share of vertices off by a whole number)) or None."""
    tris = g['idx'][mask]
    if not len(tris):
        return None
    p = g['pos'][tris][:, :, axes]                       # n x 3 x 2
    val = g['uv0'][tris][:, :, channel]                  # n x 3
    e1, e2 = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]
    det = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
    ok = np.abs(det) > 1e-3
    if ok.sum() == 0:
        return None
    d1, d2 = val[:, 1] - val[:, 0], val[:, 2] - val[:, 0]
    k0 = (d1 * e2[:, 1] - d2 * e1[:, 1])[ok] / det[ok]
    k1 = (e1[:, 0] * d2 - e2[:, 0] * d1)[ok] / det[ok]
    w = 0.5 * np.abs(det[ok])
    order0, order1 = np.argsort(k0), np.argsort(k1)
    a = float(k0[order0][np.searchsorted(np.cumsum(w[order0]), w.sum() / 2)])
    b = float(k1[order1][np.searchsorted(np.cumsum(w[order1]), w.sum() / 2)])
    verts = np.unique(tris)
    pv = g['pos'][verts][:, axes]
    vv = g['uv0'][verts, channel]
    c = vv - a * pv[:, 0] - b * pv[:, 1]
    bins = Counter(np.round(c / 0.01).astype(int))
    c0 = max(bins, key=bins.get) * 0.01
    shift = np.round(c - c0)
    k, rms = fit(np.c_[pv, np.ones(len(verts))], vv - shift)
    return dict(k=[float(v) for v in k], rms=round(rms, 4), shifted=round(float((shift != 0).mean()), 3))


def face_fits(g, rows, ya, yb, centre):
    """Per face slot and side: u = a x + b z + c and v = d x + e z + f over its triangles on its plane."""
    out = {}
    n = g['normal']
    ty = g['tri'][:, :, 1].mean(1)
    for s, r in rows.items():
        if r['role'] not in ('sideA', 'sideB', 'bothSides'):
            continue
        for side, y, sign in (('A', ya, 1), ('B', yb, -1)):
            mask = (g['slot'] == s) & (n[:, 1] * sign > FLAT) & (np.abs(ty - y) < PLANE)
            if mask.sum() < 2:
                continue
            fu, fv = unwrapped_fit(g, mask, [0, 2], 0), unwrapped_fit(g, mask, [0, 2], 1)
            if not fu or not fv:
                continue
            ku, kv = fu['k'], fv['k']
            out['%d%s' % (s, side)] = dict(slot=int(s), side=side, triangles=int(mask.sum()),
                                           u=[round(v, 6) for v in ku], v=[round(v, 6) for v in kv],
                                           rms=[fu['rms'], fv['rms']], shifted=[fu['shifted'], fv['shifted']],
                                           repeat=[round(1 / abs(ku[0]), 2) if abs(ku[0]) > 1e-9 else None,
                                                   round(1 / abs(kv[1]), 2) if abs(kv[1]) > 1e-9 else None])
    return out


def trim_fits(g, rows, centre, trims):
    """The trims' u along their sloping and upright strips per side (u = a x + c), and the caps' v across them
    (v = c0 + c1 y + c2 x) and u along them."""
    n = g['normal']
    out = {}
    pos = g['pos']
    top, bottom = float(pos[:, 2].max()), float(pos[:, 2].min())
    mask_t = np.isin(g['slot'], list(trims))
    for side, sign in (('A', 1), ('B', -1)):
        strip = mask_t & (n[:, 1] * sign > 0.05) & (np.abs(n[:, 0]) < 0.5)
        f = unwrapped_fit(g, strip, [0, 2], 0) if strip.sum() >= 2 else None
        if f:
            out['strip' + side] = dict(u=[round(f['k'][0], 6), round(f['k'][2], 4)], rms=f['rms'],
                                       shifted=f['shifted'], triangles=int(strip.sum()),
                                       repeat=round(1 / abs(f['k'][0]), 2) if abs(f['k'][0]) > 1e-9 else None)
    for name, sign, z in (('top', 1, top), ('bottom', -1, bottom)):
        cap = mask_t & (n[:, 2] * sign > FLAT) & (np.abs(g['tri'][:, :, 2].mean(1) - z) < PLANE)
        fv, fu = unwrapped_fit(g, cap, [1, 0], 1), unwrapped_fit(g, cap, [0, 1], 0)
        if not fv:
            continue
        kv = fv['k']
        # v = c0 + c1 (y - centre) + c2 x
        out[name] = dict(v=[round(kv[2] + kv[0] * centre, 5), round(kv[0], 6), round(kv[1], 6)], rmsV=fv['rms'],
                         u=[round(fu['k'][0], 6), round(fu['k'][2], 4)] if fu else None, rmsU=fu and fu['rms'])
    return out


# ---------------------------------------------------------------------------------------------------- the rest
def colours(g):
    """The outside and the inside faces' vertex colours: dict(rule, value or count, commonest)."""
    if not g['colours']:
        return dict(outside=None, interior=None, rule='none')
    out = {}
    for name, mask in (('outside', g['outside']), ('interior', ~g['outside'])):
        verts = np.unique(g['idx'][mask])
        values = Counter(bytes(g['colours'][v]).hex() for v in verts)
        if not values:
            out[name] = None
        elif len(values) == 1:
            out[name] = next(iter(values))
        else:
            out[name] = dict(values=len(values), commonest=[[k, c] for k, c in values.most_common(3)])
    # the rule is the outside faces' (the paint the blend materials read); the inside faces' are listed as they are
    out['rule'] = 'constant' if isinstance(out['outside'], str) or out['outside'] is None else 'varying'
    return out


def fragment_cells(g, ya):
    """The fragments' boxes (median, in the wall's frame), the grid that matches them and how uneven they are."""
    pos = g['pos']
    boxes = []
    for f in range(g['fragments']):
        verts = np.unique(g['idx'][g['frag'] == f])
        if len(verts):
            p = pos[verts]
            boxes.append(np.ptp(p, 0))
    boxes = np.array(boxes)
    med = np.median(boxes, 0)
    L, H = float(np.ptp(pos[:, 0])), float(np.ptp(pos[:, 2]))
    N = len(boxes)
    r = med[0] / med[2] if med[2] else 1.0
    best = None
    for nx in range(1, 80):
        for nz in range(1, 40):
            cost = 2 * abs(math.log(nx * nz / N)) + abs(math.log((L / nx) / (H / nz) / r))
            if best is None or cost < best[0]:
                best = (cost, nx, nz)
    _, nx, nz = best
    # how uneven: the spread of the fragments' areas on the +y face (std / mean)
    n = g['normal']
    ty = g['tri'][:, :, 1].mean(1)
    on = g['outside'] & (n[:, 1] > FLAT) & (np.abs(ty - ya) < PLANE)
    areas = np.bincount(g['frag'][on], weights=g['area'][on], minlength=g['fragments'])
    areas = areas[areas > 0]
    return dict(fragments=N, medianBox=[round(float(v), 1) for v in med], grid=[nx, nz],
                cell=[round(L / nx, 1), round(H / nz, 1)],
                unevenness=round(float(areas.std() / areas.mean()), 3) if len(areas) > 1 else None)


def collision_half(p, mesh, g, centre):
    import collision
    try:
        col = collision.line_collision(p, mesh)
    except Exception as err:        # noqa: BLE001 (a body setup the reader doesn't take)
        return dict(error=str(err)[:120])
    if not col.get('simple'):
        return dict(simple=False)
    pts = [np.array(e, float).reshape(-1, 3) for e in col['elements']]
    if not pts:
        return dict(simple=True, elements=0)
    allp = np.vstack(pts)
    if g['turned']:
        allp = np.c_[allp[:, 1], -allp[:, 0], allp[:, 2]]
    y = allp[:, 1] - centre
    return dict(simple=True, elements=len(pts), half=round(float(max(y.max(), -y.min())), 3),
                y=[round(float(y.min()), 3), round(float(y.max()), 3)],
                x=[round(float(allp[:, 0].min()), 2), round(float(allp[:, 0].max()), 2)],
                z=[round(float(allp[:, 2].min()), 2), round(float(allp[:, 2].max()), 2)])


def lightmap(p, mesh, comp, g, ya, yb):
    """Texels a unit on the main faces and on the inside faces, by the component's lightmap rectangle and by its
    resolution."""
    if g['uv1'] is None:
        return dict(error='no lightmap channel %d' % g['lmChannel'])
    res = None
    rect = None
    if comp:
        res = p.own(comp, 'OverriddenLightMapRes') if p.own(comp, 'bOverrideLightMapRes') else None
        try:
            import lightmap_fields
            lm = lightmap_fields.component_fields(p, comp)['lods'][0]['lightmap']
            if lm.get('type') == 2:
                tex = lm['slots'][0]['index']
                w, h = p.own(tex, 'SizeX'), p.own(tex, 'SizeY')
                rect = [lm['coordinateScale'][0] * w, lm['coordinateScale'][1] * h]
        except Exception:       # noqa: BLE001 (no record the reader takes: the resolution only)
            rect = None
    if res is None:
        res = p.effective(mesh, 'LightMapResolution', None)
    n = g['normal']
    ty = g['tri'][:, :, 1].mean(1)
    faces = g['outside'] & (((n[:, 1] > FLAT) & (np.abs(ty - ya) < PLANE)) | ((n[:, 1] < -FLAT) & (np.abs(ty - yb) < PLANE)))
    inner = ~g['outside']
    uv = g['uv1'][g['idx']]
    uva = 0.5 * np.abs((uv[:, 1, 0] - uv[:, 0, 0]) * (uv[:, 2, 1] - uv[:, 0, 1])
                       - (uv[:, 2, 0] - uv[:, 0, 0]) * (uv[:, 1, 1] - uv[:, 0, 1]))

    def density(mask, wh):
        a = g['area'][mask].sum()
        return float(math.sqrt(uva[mask].sum() * wh[0] * wh[1] / a)) if a > 0 and wh else None
    out = dict(channel=g['lmChannel'], resolution=res, rect=[round(v, 2) for v in rect] if rect else None)
    for name, wh in (('byRect', rect), ('byResolution', [res, res] if res else None)):
        f = density(faces, wh)
        i = density(inner, wh)
        out[name] = dict(faces=round(f, 4) if f else None, interior=round(i, 4) if i else None,
                         interiorRatio=round(i / f, 3) if f and i else None)
    return out


def end_insets(p, comp, g):
    """How far the solid's ends stop short of the tile edges: (low end, high end), and what grid they are of; for a
    placed piece, also its bottom against the level grid's 64-unit levels (`gridZ`, for reference only: floors stand
    16 over a level too, as URB_Bar's raised floor does, so it does not say where the floor is)."""
    pos = g['pos']
    lo, hi = float(pos[:, 0].min()), float(pos[:, 0].max())
    if comp:
        try:
            import lightmap_texels
            import native_copy
            grid = native_copy.level_grid(p)
            world = lightmap_texels.world_matrix(p, comp)
            raw = np.array(g['m']['lods'][0]['positions'], float)
            wpos = (np.c_[raw, np.ones(len(raw))] @ world.T)[:, :3]
            axis = 0 if np.ptp(wpos[:, 0]) >= np.ptp(wpos[:, 1]) else 1
            origin = grid['ox'] if axis == 0 else grid['oy']
            wlo, whi = float(wpos[:, axis].min()), float(wpos[:, axis].max())
            a = wlo - (origin + TILE * round((wlo - origin) / TILE))
            b = (origin + TILE * round((whi - origin) / TILE)) - whi
            wz = float(wpos[:, 2].min())
            level = wz - (grid['oz'] + LEVEL * round((wz - grid['oz']) / LEVEL))
            return dict(grid='level', ends=[round(a, 2) + 0.0, round(b, 2) + 0.0], tiles=round((whi - wlo + a + b) / TILE, 2),
                        gridZ=round(level, 2))
        except Exception:       # noqa: BLE001 (a map without one level volume: the mesh's own grid)
            pass
    a = lo - TILE * round(lo / TILE)
    b = TILE * round(hi / TILE) - hi
    return dict(grid='mesh', ends=[round(a, 2) + 0.0, round(b, 2) + 0.0], tiles=round((hi - lo + a + b) / TILE, 2))


# ---------------------------------------------------------------------------------------------------- the entry
def measure_raw(p, what, keep_cuts=False):
    """The look entry of the donor `what` (an actor or a mesh of package `p`): dict(entry (RECIPE's keys), measured
    (diagnostics), notMeasured)."""
    actor, comp, mesh = find(p, what)
    g = geometry(p, mesh)
    ya, yb, centre, half = main_planes(g)
    pos = g['pos']
    bottom, top = float(pos[:, 2].min()), float(pos[:, 2].max())
    mats = materials_of(p, comp)
    rows = slot_roles(g, ya if ya is not None else 1e9, yb if yb is not None else -1e9, mats)
    trims = {s for s, r in rows.items() if r['role'] == 'trim'}
    sw = sweep(g, centre, half)
    sec_a, sec_b, mirror = section(g, sw, centre, trims)
    face = face_run(sec_a['corners'], half) if half else None
    side_a, split_a = storey_split(rows, 'sideA')
    side_b, split_b = storey_split(rows, 'sideB')
    both, split_both = storey_split(rows, 'bothSides')
    if not side_a and not side_b and both:
        # one material on both faces: each side's face is the both-sides slots
        side_a, side_b, split_a, split_b = both, both, split_both, split_both
    fits = face_fits(g, rows, ya, yb, centre) if half else {}
    tfits = trim_fits(g, rows, centre, trims)
    cells = fragment_cells(g, ya) if ya is not None else None
    lm = lightmap(p, mesh, comp, g, ya, yb) if half else None
    inset = end_insets(p, comp, g)
    col = collision_half(p, mesh, g, centre)
    cols = colours(g)

    def side_fit(slots, side):
        rows_ = [fits['%d%s' % (s, side)] for s in slots if '%d%s' % (s, side) in fits]
        if not rows_:
            return None
        a = [r['u'][0] for r in rows_]
        e = [r['v'][1] for r in rows_]
        return dict(repeatAlong=round(1 / abs(float(np.median(a))), 2), repeatUp=round(1 / abs(float(np.median(e))), 2),
                    u=round(float(np.median([r['u'][2] for r in rows_])), 4),
                    v=round(float(np.median([r['v'][2] for r in rows_])), 4),
                    uSign=int(np.sign(np.median(a))), vSign=int(np.sign(np.median(e))),
                    repeats=sorted({tuple(r['repeat']) for r in rows_}))
    fa = side_fit(side_a, 'A')
    fb = side_fit(side_b, 'B')
    strip = tfits.get('stripA') or {}
    strip_b = tfits.get('stripB') or {}
    top_v = tfits.get('top', {}).get('v')
    bottom_v = tfits.get('bottom', {}).get('v')
    entry = {
        'version': 1,
        'donor': g['name'],
        'bottom': round(bottom, 3) + 0.0, 'top': round(top, 3) + 0.0,
        'storey': split_a[0] if len(split_a) == 1 else (split_a or None),
        **({'storeyB': split_b[0] if len(split_b) == 1 else (split_b or None)} if split_b != split_a else {}),
        'face': [round(face[0], 3), round(face[1], 3)] if face else None,
        'half': round(half, 3) if half else None,
        # the end that stops shortest of its tile edge (a free end, as RECIPE's; the other may be a joint's)
        'endInset': round(float(max(inset['ends'])), 2),
        'section': sec_a['corners'],
        **({'sectionB': sec_b['corners']} if mirror != 'mirror' else {}),
        'faceRepeat': (round(float(np.median([fa['repeatAlong'], fa['repeatUp']] + ([fb['repeatAlong'], fb['repeatUp']] if fb else []))), 2)
                       if fa else None),
        'faceV': [fa['v'] if fa else None, fb['v'] if fb else None],
        'faceU': fa['u'] if fa else None,
        'trimRepeat': strip.get('repeat'),
        # frac_wall writes a trim's u = -side (x / trimRepeat + trimU): side A's c is -trimU
        'trimU': round(-strip['u'][1], 4) if strip.get('u') else None,
        'topV': top_v[:2] if top_v else None, 'bottomV': bottom_v[:2] if bottom_v else None,
        'colours': {'outside': cols.get('outside'), 'interior': cols.get('interior')},
        'slots': {'sideA': side_a or None, 'sideB': side_b or None,
                  'trim': (sorted(trims)[0] if len(trims) == 1 else sorted(trims)) if trims else None,
                  'interior': g['interior']},
        'cell': cells['cell'] if cells else None,
        'collisionHalf': col.get('half'),
        'lightmap': {'density': (lm or {}).get('byRect', {}).get('faces') or (lm or {}).get('byResolution', {}).get('faces'),
                     'interiorDensity': (lm or {}).get('byRect', {}).get('interiorRatio')
                     or (lm or {}).get('byResolution', {}).get('interiorRatio')},
    }
    if both:
        entry['slots']['bothSides'] = both
    measured = dict(
        map=p.path.stem, actor=p.name(actor).split('.')[-1] if actor else None, turned=g['turned'],
        size=[round(float(v), 2) for v in np.ptp(pos, 0)], x=[round(float(pos[:, 0].min()), 2), round(float(pos[:, 0].max()), 2)],
        planes=dict(a=ya and round(ya, 3), b=yb and round(yb, 3), centre=round(centre, 3)),
        sweep=dict(verdict=sw['verdict'], cuts=sw['cuts'], bodyCuts=sw['bodyCuts'], holedCuts=sw['holedCuts'],
                   agreeShare=sw['agreeShare'], worst=sw['worst'], differAt=sw['differAt'], cornerPiece=sw['corner'],
                   openings=sw['openings'], edgeZone=sw['edgeZone'], endDetail=sw['endDetail']),
        flat=flat_share(g, ya, yb) if half else None,
        sectionB=sec_b['corners'], sectionMirrored=mirror, sectionCuts=[sec_a['cuts'], sec_a['of']],
        storeySplits=dict(A=split_a, B=split_b), slots=list(rows.values()), faceFits=fits, trimFits=tfits,
        faceSides=dict(A=fa, B=fb), stripB=strip_b, colours=cols, cells=cells, collision=col, lightmap=lm,
        endInsets=inset, fragments=g['fragments'], triangles=int(len(g['idx'])))
    if keep_cuts:
        measured['cutsAt'] = [round(float(x), 2) for x in sw['xs']]
        measured['cutDeviation'] = [None if not np.isfinite(d) else round(float(d), 2) for d in sw['dev']]
    not_measured = {
        'cell jitter': 'the donors\' cells come from the game\'s fracture tool, not a jittered grid; the generator\'s '
                       'jitter is its own choice (measured instead: the fragments\' unevenness, the spread of their '
                       'areas on the +y face)',
        'lightmap margin': 'texels between charts: how the Build packs a made wall\'s lightmap, not the donor\'s',
        'lightmap block': 'the DXT block the Build rounds a rectangle to (4): a format constant',
    }
    return dict(entry=entry, measured=measured, notMeasured=not_measured)


# ---------------------------------------------------------------------------------------------------- the check
def compare(entry, recipe):
    """Key by key: [dict(key, measured, recipe, ok, note)]."""
    T = CHECK_TOLERANCE
    out = []

    def row(key, got, want, ok, note=''):
        out.append(dict(key=key, measured=got, recipe=want, ok=bool(ok), note=note))

    def near(a, b, tol):
        return a is not None and b is not None and abs(a - b) <= tol
    for key in ('bottom', 'top', 'storey', 'half', 'faceRepeat', 'faceU', 'trimRepeat', 'trimU', 'collisionHalf',
                'endInset'):
        row(key, entry.get(key), recipe.get(key), near(entry.get(key), recipe.get(key), T[key]))
    for key in ('face', 'faceV'):
        got, want = entry.get(key), recipe.get(key)
        row(key, got, want, got is not None and len(got) == len(want) and all(near(a, b, T[key]) for a, b in zip(got, want)))
    for key in ('topV', 'bottomV'):
        got, want = entry.get(key), recipe.get(key)
        row(key, got, want, got is not None and all(near(a, b, t) for a, b, t in zip(got, want, T[key])))
    got, want = entry['section'], recipe['section']
    ok = len(got) == len(want) and all(near(a[0], b[0], T['section_y']) and near(a[1], b[1], T['section_z'])
                                       and near(a[2], b[2], T['section_v']) for a, b in zip(got, want))
    row('section', got, want, ok, '%d corners against %d' % (len(got), len(want)))
    row('colours', entry['colours'], recipe['colours'], entry['colours'] == recipe['colours'])
    row('slots', entry['slots'], recipe['slots'], all(entry['slots'].get(k) == v for k, v in recipe['slots'].items()))
    # the cell: checked by check() as the grid it gives on the donor's own solid
    row('cell', entry.get('cell'), recipe.get('cell'), False)
    lm, rl = entry['lightmap'], recipe['lightmap']
    row('lightmap.density', lm.get('density'), rl['density'], near(lm.get('density'), rl['density'], T['density']))
    row('lightmap.interiorDensity', lm.get('interiorDensity'), rl['interiorDensity'],
        near(lm.get('interiorDensity'), rl['interiorDensity'], T['interiorDensity']))
    row('version', entry['version'], recipe['version'], entry['version'] == recipe['version'])
    row('donor', entry['donor'], recipe['donor'], entry['donor'] == recipe['donor'])
    return out


def check(result, recipe):
    """compare(), with the cell checked as the grid it gives on the donor's solid."""
    rows = compare(result['entry'], recipe)
    cells = result['measured']['cells']
    size = result['measured']['size']
    L, H = size[0], size[2]
    for r in rows:
        if r['key'] == 'cell':
            want = [max(1, round(L / recipe['cell'][0])), max(1, round(H / recipe['cell'][1]))]
            r['ok'] = cells['grid'] == want
            r['note'] = ('the measured grid %d x %d (%d fragments, the donor %d); the recipe\'s cell gives %d x %d on '
                         'the donor\'s %g x %g solid' % (cells['grid'][0], cells['grid'][1], cells['grid'][0] * cells['grid'][1],
                                                         cells['fragments'], want[0], want[1], L, H))
    return rows
