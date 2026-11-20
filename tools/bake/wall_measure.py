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
CHECK_TOLERANCE).

measure(package, what) gives a look's entry for the Build and the catalogue (the block "the recipe" says how):
dict(recipe (what frac_wall.py's general path builds from), warnings (plain words for what a made wall lacks), facts
(size, the storeys it can be made at, the sweep's verdict, inside or outside...)); ValueError for a `what` that is no
fracturing piece or mesh of the map. twin(recipe) gives dict(ok, rows, made): the wall made at its donor's length and
measured again, each key that makes the look against the recipe. The same donor always gives the same entry. No game
file is written.
"""
from collections import Counter
import math
from pathlib import Path
import re
import sys
import warnings

import numpy as np

HERE = Path(__file__).resolve().parent
for folder in ('viewer', 'upk'):
    sys.path.insert(0, str(HERE.parent / folder))
sys.path.insert(0, str(HERE))
import gen_mesh  # noqa: E402
import measure_common as mc  # noqa: E402

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
    import settings
    from package import Package
    path = (folder := settings.lwr_cooked()) and folder / (name + '.upk')
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
    path) or a mesh's full name (its placing's component then gives the materials and the lightmap), found as the slab
    and ground measurers find theirs (measure_common.find_placing: a mesh's first placing at scale 1, else its first;
    review finding 57). A fracturing mesh of the map that nothing places gives (None, None, mesh)."""
    try:
        return mc.find_placing(p, what, FRACTURING, 'FracturedStaticMeshComponent')
    except ValueError:
        pass
    i = p.by_name.get(what)
    if i and p.cls(i) == 'FracturedStaticMesh' and not placed(p, i):
        return None, None, i
    raise ValueError('%s is neither a fracturing piece nor a fracturing mesh of %s' % (what, p.path.name))


# ---------------------------------------------------------------------------------------------------- geometry
def geometry(p, mesh):
    """The mesh's LOD 0 in the wall's frame (geometry_of), read from package `p`."""
    return geometry_of(gen_mesh.read(p, mesh), p.name(mesh), p.effective(mesh, 'LightMapCoordinateIndex', 1), mesh)


def geometry_of(m, name, lm_channel=1, mesh=None):
    """A decoded fracturing mesh's LOD 0 (gen_mesh's form: a donor's, or one frac_wall.build made) in the wall's
    frame: positions, triangles (indices, slot, fragment), outward normals, areas, the texture coordinates of channel 0
    and of the lightmap channel, colours, the interior slot."""
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
    uv0 = np.array([v[2][0] for v in lod['vertices']], float)
    uv1 = np.array([v[2][lm_channel] for v in lod['vertices']], float) if 0 <= lm_channel < channels else None
    interior = m['fractured']['interior']
    return dict(m=m, mesh=mesh, name=name, turned=turned, pos=pos, idx=idx, tri=tri, slot=slot, frag=frag,
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
    """The outside triangles cut by the plane at x: dict(slot, a, b ([y, z] ends), uva, uvb, normal, tri (their
    indices)) arrays."""
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
                uva=U[rows, first], uvb=U[rows, second], tri=np.nonzero(sel)[0])


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
    with np.errstate(all='ignore'), warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)     # (heights no cut has a face at: NaN, as meant)
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


def picks_of(sw):
    """The cuts the section is taken over: the agreeing full cuts, up to PICKS of them spread along the wall (the
    reference cut among them where it agrees)."""
    picks = [k for k in range(len(sw['xs'])) if sw['basis'][k] and sw['agree'][k]] or [sw['reference']]
    if len(picks) > PICKS:
        picks = sorted({picks[round(i * (len(picks) - 1) / (PICKS - 1))] for i in range(PICKS)} | {sw['reference']}
                       & set(picks))
    return picks


def section(g, sw, centre, trims):
    """The section's corners [y, z, v] on the +y side (the median over the agreeing full cuts that have the reference
    cut's corners), the -y side's corners mirrored, and how the sides compare: 'mirror', 'mirror, other v' (the same
    outline, the trims' v differ) or 'differs'."""
    picks = picks_of(sw)
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
    return unwrap(g['idx'][mask], g['pos'][:, axes], g['uv0'][:, channel])


def unwrap(tris, coords, values):
    """unwrapped_fit's fit over the triangles `tris` (n x 3 vertex indices), by each vertex's two coordinates
    `coords` (V x 2) and its texture coordinate `values` (V)."""
    if not len(tris):
        return None
    p = coords[tris]                                     # n x 3 x 2
    val = values[tris]                                   # n x 3
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
    pv = coords[verts]
    vv = values[verts]
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
    return densities(g, ya, yb, rect, res)


def densities(g, ya, yb, rect, res):
    """lightmap's texels a unit on the main faces and the inside faces, by the rectangle `rect` (texels) and by the
    resolution `res`."""
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
    return _measure(*donor(p, what), keep_cuts=keep_cuts)[0]


def donor(p, what):
    """(geometry, context) of the donor `what` of package `p` for _measure: the context's map and actor, its
    component's materials, and how its lightmap, end insets and collision are read."""
    actor, comp, mesh = find(p, what)
    g = geometry(p, mesh)
    ctx = dict(map=p.path.stem, actor=p.name(actor).split('.')[-1] if actor else None, materials=materials_of(p, comp),
               lightmap=lambda g, ya, yb: lightmap(p, mesh, comp, g, ya, yb),
               insets=lambda g: end_insets(p, comp, g),
               collision=lambda g, centre: collision_half(p, mesh, g, centre))
    return g, ctx


def _measure(g, ctx, keep_cuts=False):
    """measure_raw's entry of the geometry `g` (geometry_of's) in its context `ctx` (donor's), and what the recipe is
    made from besides (recipe_of): (dict(entry, measured, notMeasured), state). A context with `planes` gives the main
    planes (the twin's: its recipe's, so a made wall is measured in its donor's frame)."""
    ya, yb, centre, half = ctx['planes'] if ctx.get('planes') else main_planes(g)
    pos = g['pos']
    bottom, top = float(pos[:, 2].min()), float(pos[:, 2].max())
    mats = ctx['materials']
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
    lm = ctx['lightmap'](g, ya, yb) if half else None
    inset = ctx['insets'](g)
    col = ctx['collision'](g, centre)
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
        map=ctx['map'], actor=ctx['actor'], turned=g['turned'],
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
    state = dict(sw=sw, rows=rows, trims=trims, centre=centre, half=half, bottom=bottom, top=top, fits=fits)
    return dict(entry=entry, measured=measured, notMeasured=not_measured), state


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


# ---------------------------------------------------------------------------------------------------- the recipe
# measure(package, what) gives a look's entry: dict(recipe (what frac_wall.py's general path builds from: its block
# comment says the keys), warnings (plain words for what the made wall lacks), facts (size, storeys, verdict, inside or
# outside, materials...)). Beyond measure_raw's entry it measures, over the same agreeing cuts, the slot and the texture
# of every segment of each side's outline (the cuts' segments lying on it: their slot by length, then u and v fitted
# over their triangles along the wall and up the segment, as the faces' fits are), the top's and the bottom's, and it
# puts the outline into the form the generator takes (normal_profile). Its heights are the made wall's over its
# piece's location: a donor whose bottom is above its pivot is moved down by whole levels until its bottom is in
# (-64, 0] (lift_of, lowered_by; facts and frame say how far). twin(recipe) builds the wall at its donor's
# length (frac_wall.build) and measures it again: each key that makes the look is compared with the donor's.
FACE_NEAR = 0.3         # units: an upright segment of the outline this close to the main plane is on it
ON_SEGMENT = 0.3        # units: a cut's segment whose two ends are this close to a segment of the outline lies on it
DEFAULT_LIGHTMAP = dict(density=0.196, interiorDensity=0.5)     # a donor whose lightmap isn't read: the Bar look's
JITTER, MARGIN, BLOCK = 0.3, 2, 4       # the generator's own choices (notMeasured): the Bar look's
DEFAULT_CELL = [96.0, 80.0]
WHITE = 'ffffffff'
MODELLED = "its window frames and ledges aren't made"            # the plan's words (D12)
# inside or outside wall, a guess from its name and its faces' materials (research/evidence/wall-look-audit.py's)
INSIDE_NAME = re.compile(r'Int[A-Z_]|INT|Interior|Divider|DualSplit|Inet|Kitchen|Order(Left|Right)|Vault')
OUTSIDE_NAME = re.compile(r'Ext|EXT|Facade|Core_|HighRise|North|South|East|West|Front|Rear|Entry|Main|Drive|Dine|'
                          r'Back|Gable|Strip|Crown|Addon|Garage|Store[A-Z]|Shed')
EXTERIOR_MATERIAL = re.compile(r'Brick|Concrete|Stucco|Siding|Metal|Cinder|Corrugat|Stone|Marble|EXT|Exterior|Shingle|'
                               r'Clapboard|Granite|Block', re.I)
INTERIOR_MATERIAL = re.compile(r'Interiors|Interior|INT|Plaster|Wallpaper|Paint|Wainsc|Drywall|Tile|Panel|Wood', re.I)


def side_kind(materials):
    names = ' '.join(m for m in materials if m)
    ext, inn = bool(EXTERIOR_MATERIAL.search(names)), bool(INTERIOR_MATERIAL.search(names))
    if 'UFO' in names or 'Alien' in names:
        return 'alien'
    return 'exterior' if ext and not inn else 'interior' if inn and not ext else 'mixed' if ext and inn else 'unknown'


def kind_of(name, side_a, side_b):
    """A guess at an inside or outside wall from its mesh's name and its sides' materials: (kind, why), kind 'inside',
    'outside', 'alien' (the UFOs') or 'unsure' (the wall-look audit's rule)."""
    short = name.split('.')[-1]
    ka, kb = side_kind(side_a), side_kind(side_b)
    if INSIDE_NAME.search(short):
        return 'inside', 'its name (%s)' % INSIDE_NAME.search(short).group(0)
    if 'alien' in (ka, kb):
        return 'alien', 'UFO materials'
    if {ka, kb} == {'exterior', 'interior'} or {ka, kb} == {'exterior', 'mixed'}:
        return 'outside', 'an exterior face (%s) and an interior one (%s)' % (ka, kb)
    if ka == kb == 'interior':
        return 'inside', 'both faces interior materials'
    if OUTSIDE_NAME.search(short):
        return 'outside', 'its name (%s); faces %s / %s' % (OUTSIDE_NAME.search(short).group(0), ka, kb)
    if ka == kb == 'exterior':
        return 'outside', 'both faces exterior materials (a free-standing wall)'
    return 'unsure', 'faces %s / %s' % (ka, kb)


def normal_profile(corners, bottom, top):
    """A side's corners ([y, z, ...]) as the generator takes them, and the heights it made up ([[from, to]]): from the
    bottom to the top (a first corner over the bottom carried down to it upright, a last one under the top carried up
    to it), its heights never going down (a step back down made a ledge), a run of corners at the first or the last
    height cut to the one nearest the face, repeated corners and corners inside a straight upright run dropped."""
    pts = [[round(float(c[0]), 3) + 0.0, round(min(max(float(c[1]), bottom), top), 3) + 0.0] for c in corners]
    for k in range(1, len(pts)):
        pts[k][1] = max(pts[k][1], pts[k - 1][1])
    while len(pts) > 1 and abs(pts[1][1] - pts[0][1]) < 1e-6:
        pts.pop(0)
    while len(pts) > 1 and abs(pts[-2][1] - pts[-1][1]) < 1e-6:
        pts.pop()
    made = []
    if not pts:
        return [], [[bottom, top]]
    if pts[0][1] > bottom + 0.05:
        made.append([bottom, pts[0][1]])
        pts.insert(0, [pts[0][0], bottom])
    else:
        pts[0][1] = bottom
    if pts[-1][1] < top - 0.05:
        made.append([pts[-1][1], top])
        pts.append([pts[-1][0], top])
    else:
        pts[-1][1] = top
    out = []
    for p in pts:
        if out and abs(out[-1][0] - p[0]) < 1e-3 and abs(out[-1][1] - p[1]) < 1e-3:
            continue
        if (len(out) >= 2 and abs(out[-2][0] - out[-1][0]) < 1e-6 and abs(out[-1][0] - p[0]) < 1e-6
                and out[-2][1] < out[-1][1] < p[1]):
            out[-1] = p
            continue
        out.append(p)
    return out, [[round(a, 3) + 0.0, round(b, 3) + 0.0] for a, b in made]


def outline_of(g, sw, picks, centre, side):
    """One side's outline [[y, z]] over the cuts `picks` (section's chains, cut down to their corners): of the cuts'
    outlines, those with the commonest number of corners (more corners on a tie) whose heights agree within a unit,
    each corner their median. section() takes the reference cut's number of corners instead: one cut whose outline
    stops short (a sliver of a fragment at its top) then stands for all, which this doesn't let it."""
    bottom, top = float(g['pos'][:, 2].min()), float(g['pos'][:, 2].max())
    sets = []
    for k in picks:
        corners = simplify(side_chain(cut(g, sw['xs'][k]), centre, side, bottom, top))
        if corners:
            sets.append([(float(y), float(z)) for y, z, _ in corners])
    if not sets:
        return []
    counts = Counter(len(s) for s in sets)
    n = max(counts, key=lambda c: (counts[c], c))
    group = [s for s in sets if len(s) == n]
    zs = np.median(np.array([[z for _, z in s] for s in group]), 0)
    same = [s for s in group if all(abs(z - m) < 1.0 for (_, z), m in zip(s, zs))] or group
    arr = np.array(same)
    return [[round(float(y), 3) + 0.0, round(float(z), 3) + 0.0] for y, z in np.median(arr, 0)]


def strip_uv(g, ids, centre, side, p0, p1):
    """u and v = a x + b t + c over the triangles `ids`, x along the wall and t up the outline's segment p0..p1 (0 at
    p0, 1 at p1) on the given side, as the faces' fits are made (unwrap): [[a, b, c] of u, [a, b, c] of v], or None."""
    if not len(ids):
        return None
    (y0, z0), (y1, z1) = p0, p1
    dy, dz = y1 - y0, z1 - z0
    length2 = dy * dy + dz * dz
    if length2 < 1e-9:
        return None
    ys = (g['pos'][:, 1] - centre) * side
    t = ((ys - y0) * dy + (g['pos'][:, 2] - z0) * dz) / length2
    coords = np.c_[g['pos'][:, 0], t]
    tris = g['idx'][ids]
    fu, fv = unwrap(tris, coords, g['uv0'][:, 0]), unwrap(tris, coords, g['uv0'][:, 1])
    if not fu or not fv:
        return None
    return [[round(v, 6) + 0.0 for v in fu['k']], [round(v, 6) + 0.0 for v in fv['k']]]


def strips_of(g, sw, picks, centre, half, prof, side, face_slots):
    """Each segment of one side's outline `prof` (normal_profile's): dict(slot, face, uv). Its slot is the one most of
    the cuts' segments lying on it are in (by length); a face is upright on the main plane in one of the side's face
    slots (`face_slots`: it takes them by height); any other segment its texture fitted over its triangles (strip_uv).
    A segment no cut met (one made up, or too short) takes its nearest neighbour's slot and texture."""
    n = len(prof) - 1
    P = np.array(prof, float)
    d = P[1:] - P[:-1]
    length2 = np.maximum((d ** 2).sum(1), 1e-12)
    bottom, top = prof[0][1], prof[-1][1]
    weight = [Counter() for _ in range(n)]
    tris = [set() for _ in range(n)]
    for k in picks:
        c = cut(g, sw['xs'][k])
        if not len(c['a']):
            continue
        ya, yb = (c['a'][:, 0] - centre) * side, (c['b'][:, 0] - centre) * side
        za, zb = c['a'][:, 1], c['b'][:, 1]
        nrm = c['normal']
        zm = (za + zb) / 2
        facing = nrm[:, 1] * side > 0.02
        ledge = ((np.abs(nrm[:, 2]) > 0.98) & (np.minimum(ya, yb) > 0.5)
                 & (np.abs(zm - bottom) > PLANE) & (np.abs(zm - top) > PLANE))
        sel = np.nonzero(facing | ledge)[0]
        if not len(sel):
            continue
        E = np.stack([np.c_[ya[sel], za[sel]], np.c_[yb[sel], zb[sel]]], 1)            # m x 2 ends x (y, z)
        size = np.linalg.norm(E[:, 1] - E[:, 0], axis=1)
        rel = E[:, :, None, :] - P[None, None, :-1, :]                                   # m x 2 x n x 2
        t = np.clip((rel * d[None, None]).sum(3) / length2[None, None], 0.0, 1.0)
        dist = np.linalg.norm(rel - t[..., None] * d[None, None], axis=3).max(1)        # m x n
        j = dist.argmin(1)
        ok = (dist[np.arange(len(sel)), j] <= ON_SEGMENT) & (size > 1e-3)
        for s, jj, ln in zip(sel[ok], j[ok], size[ok]):
            weight[jj][int(c['slot'][s])] += float(ln)
            tris[jj].add(int(c['tri'][s]))
    out = []
    for j in range(n):
        (y0, z0), (y1, z1) = prof[j], prof[j + 1]
        slot = min(weight[j], key=lambda s: (-weight[j][s], s)) if weight[j] else None
        on_plane = abs(y0 - y1) < 1e-3 and z1 > z0 and abs(y0 - half) < FACE_NEAR
        face = bool(on_plane and face_slots and (slot is None or slot in face_slots))
        uv = None
        if not face and slot is not None:
            ids = np.array(sorted(t for t in tris[j] if g['slot'][t] == slot), np.int64)
            uv = strip_uv(g, ids, centre, side, (y0, z0), (y1, z1))
        out.append(dict(slot=None if face else slot, face=face, uv=uv))
    for j in range(n):
        if out[j]['face'] or out[j]['slot'] is not None:
            continue
        near = [k for k in sorted(range(n), key=lambda k: (abs(k - j), k)) if out[k]['slot'] is not None]
        if near:
            out[j] = dict(slot=out[near[0]]['slot'], face=False, uv=out[near[0]]['uv'])
        else:
            out[j] = dict(slot=face_slots[0] if face_slots else (g['slots'][0] if g['slots'] else 0), face=False, uv=None)
    return out


def face_uv(fits, sides, entry):
    """Each face slot's texture on each side it is a face of: {'<slot><side>': [[a, b, c] of u, [d, e, f] of v]} (u and
    v = a x + b z + c on the face), from the faces' fits; a slot with no fit of its own on a side takes the side's
    nearest slot's, else the other side's, else the entry's repeat (faceRepeat, faceU, faceV)."""
    out = {}
    for X, slots in sides.items():
        for s in slots:
            f = fits.get('%d%s' % (s, X))
            if f:
                out['%d%s' % (s, X)] = [[float(v) for v in f['u']], [float(v) for v in f['v']]]
    for X, slots in sides.items():
        other = 'B' if X == 'A' else 'A'
        for s in slots:
            key = '%d%s' % (s, X)
            if key in out:
                continue
            mine = [out['%d%s' % (k, X)] for k in sorted(slots, key=lambda k: (abs(k - s), k)) if '%d%s' % (k, X) in out]
            theirs = out.get('%d%s' % (s, other))
            if mine or theirs:
                out[key] = mine[0] if mine else theirs
            else:
                rep = entry.get('faceRepeat') or STOREY
                v0 = (entry.get('faceV') or [None, None])[0 if X == 'A' else 1]
                out[key] = [[1.0 / rep, 0.0, float(entry.get('faceU') or 0.0)], [0.0, -1.0 / rep, float(v0 or 0.0)]]
    return dict(sorted(out.items()))


def cap_of(g, centre, z, sign):
    """The top's (sign 1) or the bottom's (-1) slot (the one most of its area is in) and texture (u and v = a x + b y
    + c, y from the centre line): dict(slot, uv), or None where the wall has no face there."""
    n = g['normal']
    tz = g['tri'][:, :, 2].mean(1)
    mask = g['outside'] & (n[:, 2] * sign > FLAT) & (np.abs(tz - z) < PLANE)
    if not mask.any():
        return None
    by = np.bincount(g['slot'][mask], weights=g['area'][mask])
    slot = int(np.argmax(by))
    m2 = mask & (g['slot'] == slot)
    coords = np.c_[g['pos'][:, 0], g['pos'][:, 1] - centre]
    fu, fv = unwrap(g['idx'][m2], coords, g['uv0'][:, 0]), unwrap(g['idx'][m2], coords, g['uv0'][:, 1])
    uv = [[round(v, 6) + 0.0 for v in fu['k']], [round(v, 6) + 0.0 for v in fv['k']]] if fu and fv else None
    return dict(slot=slot, uv=uv)


def commonest(colours):
    """A colour entry's (one value, or dict(values, commonest)) commonest value; white where the mesh has none."""
    if isinstance(colours, str):
        return colours
    if isinstance(colours, dict) and colours.get('commonest'):
        return colours['commonest'][0][0]
    return WHITE


def outside_density(g, rect):
    """dict(density, interiorDensity): texels a unit over all the outside faces by the lightmap rectangle `rect`
    (texels), and the inside faces' share of it; {} where there is no rectangle or no lightmap channel."""
    if not rect or g['uv1'] is None:
        return {}
    uv = g['uv1'][g['idx']]
    uva = 0.5 * np.abs((uv[:, 1, 0] - uv[:, 0, 0]) * (uv[:, 2, 1] - uv[:, 0, 1])
                       - (uv[:, 2, 0] - uv[:, 0, 0]) * (uv[:, 1, 1] - uv[:, 0, 1]))
    out = {}
    for name, mask in (('density', g['outside']), ('inner', ~g['outside'])):
        a = g['area'][mask].sum()
        out[name] = float(math.sqrt(uva[mask].sum() * rect[0] * rect[1] / a)) if a > 0 else None
    if not out['density']:
        return {}
    return dict(density=round(out['density'], 4),
                interiorDensity=round(out['inner'] / out['density'], 3) if out['inner'] else None)


def whole_storeys(bottom, top):
    """The storeys a wall from `bottom` to `top` stands (its top over the floor when it reaches under its pivot, else
    its height, over 192), as the wall-look audit counts them."""
    over = top if bottom < -1 else top - bottom
    return max(1, int(round(over / STOREY)))


def recipe_of(raw, state, g):
    """(recipe, made-up heights by side) from measure_raw's entry `raw`, _measure's `state` and the geometry `g`."""
    e, m = raw['entry'], raw['measured']
    half = e['half'] if e['half'] else 8.0
    bottom, top = e['bottom'], e['top']
    sw, centre = state['sw'], state['centre']
    picks = picks_of(sw)
    slots = e['slots']
    face_slots = dict(A=list(slots['sideA'] or []), B=list(slots['sideB'] or []))
    profile, made, strips = {}, {}, {}
    for X, side in (('A', 1), ('B', -1)):
        prof, mk = normal_profile(outline_of(g, sw, picks, centre, side), bottom, top)
        if len(prof) < 2:
            prof, mk = [[half, bottom], [half, top]], [[bottom, top]]
        profile[X], made[X] = prof, mk
        strips[X] = strips_of(g, sw, picks, centre, half, prof, side, face_slots[X])
    col = m['collision'] or {}
    lm = dict(e['lightmap'] or {})
    if not lm.get('density'):
        # no faces on the main planes to read it on: over all its outside faces
        lm.update(outside_density(g, (m['lightmap'] or {}).get('rect')))
    recipe = dict(
        measure=VERSION, donor=e['donor'], bottom=bottom, top=top, half=half, endInset=e['endInset'],
        profile=profile, strips=strips,
        slots=dict(sideA=face_slots['A'], sideB=face_slots['B'], interior=int(g['interior'])),
        splits=dict(A=[float(v) for v in m['storeySplits']['A']], B=[float(v) for v in m['storeySplits']['B']]),
        faceUV=face_uv(state['fits'], face_slots, e),
        caps=dict(top=cap_of(g, centre, top, 1), bottom=cap_of(g, centre, bottom, -1)),
        colours=dict(outside=commonest(e['colours']['outside']), interior=commonest(e['colours']['interior'])),
        cell=[float(v) for v in (e['cell'] or DEFAULT_CELL)], jitter=JITTER,
        collisionHalf=col.get('half') or half,
        collisionY=[float(v) for v in col['y']] if col.get('y') else [-half, half],
        lightmap=dict(density=lm.get('density') or DEFAULT_LIGHTMAP['density'],
                      interiorDensity=lm.get('interiorDensity') or DEFAULT_LIGHTMAP['interiorDensity'],
                      margin=MARGIN, block=BLOCK),
        sections=len(g['m']['lods'][0]['sections']), storeys=whole_storeys(bottom, top), storey=STOREY,
        donorLength=float(m['size'][0]), frame=dict(turned=bool(m['turned']), centre=round(float(centre), 3) + 0.0,
                                                     x=[float(v) for v in m['x']]))
    made = {X: v for X, v in made.items() if v}
    lift = lift_of(bottom)
    return lowered_by(recipe, made, lift) if lift else (recipe, made)


# a donor this far over its pivot or less is not moved down (lift_of)
LIFT_SLACK = 8.0


def lift_of(bottom):
    """How far a made wall is moved down from its donor's frame: for a donor whose bottom is above its pivot (an upper
    storey's wall placed from the ground, a wall on a raised floor), whole levels (64) until its bottom is in (-64, 0],
    so it stands on the floor it is drawn on (64 -> 0, 192 -> 0, 48 -> -16); 0 for a donor at or under its pivot, or
    over it by LIFT_SLACK or less (a supply ship crate's walls at 1.793 stay, not a level under the floor)."""
    return LEVEL * math.ceil((bottom - LIFT_SLACK) / LEVEL) if bottom > LIFT_SLACK else 0.0


def lowered_by(recipe, made, lift):
    """(recipe, made-up heights) moved `lift` down: its bottom and top, both sides' outlines, the splits, the faces'
    textures (their offsets, so each stays where it was on the wall), its storeys counted again, and the frame saying
    how far (`lowered`: painting moves the donor down as far)."""
    def z(v):
        return round(v - lift, 3) + 0.0
    out = dict(recipe, bottom=z(recipe['bottom']), top=z(recipe['top']),
               profile={X: [[y, z(h)] for y, h in c] for X, c in recipe['profile'].items()},
               splits={X: [z(s) for s in v] for X, v in recipe['splits'].items()},
               faceUV={k: [[a, b, round(c + b * lift, 6) + 0.0], [d, e, round(f + e * lift, 6) + 0.0]]
                       for k, ((a, b, c), (d, e, f)) in recipe['faceUV'].items()},
               frame=dict(recipe['frame'], lowered=lift))
    out['storeys'] = whole_storeys(out['bottom'], out['top'])
    return out, {X: [[z(a), z(b)] for a, b in v] for X, v in made.items()}


def warnings_of(raw, recipe, made):
    """What a wall made in this look lacks of its donor, in plain words."""
    sw = raw['measured']['sweep']
    out = []
    if sw['verdict'] == 'modelled':
        if sw['cornerPiece']:
            out.append('it is a corner piece: it is made as one straight wall')
        out.append(MODELLED)
    elif sw['verdict'] == 'swept, framed openings':
        out.append("the frames round its doorways and windows aren't made")
    elif sw['verdict'] == 'mostly swept':
        out.append("a detail along part of its length isn't made")
    end = sw.get('endDetail') or {}
    if end.get('cuts') and (end.get('worst') or 0) >= 1:
        out.append("the detail at its ends (a corner or a jamb) isn't made: its ends are plain")
    for X in sorted(made):
        for a, b in made[X]:
            out.append("one side's outline from %g to %g up wasn't measured: it is made straight up there" % (a, b))
    for key, k in (('top', -1), ('bottom', 0)):
        width = recipe['profile']['A'][k][0] + recipe['profile']['B'][k][0]
        if recipe['caps'][key] is None and width > 1e-3:
            out.append("its %s isn't level all along (a gable or a slope): the made wall's %s is flat" % (key, key))
    return out


def facts_of(raw, recipe, made, name):
    """The look's facts: size, heights, the storeys it can be made at, the sweep's verdict, inside or outside, its
    slots' roles and materials, how it was measured."""
    import frac_wall
    e, m = raw['entry'], raw['measured']
    rows = {r['slot']: r for r in m['slots']}
    carrier = [r['material'] for r in rows.values() if r.get('carriesFaces')]
    side_a = [rows[s]['material'] for s in recipe['slots']['sideA'] if s in rows] or carrier
    side_b = [rows[s]['material'] for s in recipe['slots']['sideB'] if s in rows] or carrier
    kind, why = kind_of(name, side_a, side_b)
    size = m['size']
    lift = recipe['frame'].get('lowered', 0.0)
    openings = m['sweep']['openings']
    if lift:
        # (the donor's openings at the heights the made wall stands at)
        openings = [dict(o, **{k: [round(v - lift, 1) + 0.0 for v in o[k]] for k in ('z', 'through') if o.get(k)})
                    for o in openings]
    return dict(
        size=dict(length=size[0], height=size[2], thickness=size[1]), bottom=recipe['bottom'], top=recipe['top'],
        **({'lowered': lift} if lift else {}),
        storeys=list(frac_wall.storeys_of(recipe)), verdict=m['sweep']['verdict'], inside=kind == 'inside', kind=kind,
        kindWhy=why, turned=m['turned'], fragments=m['fragments'], triangles=m['triangles'],
        openings=openings, agreeShare=m['sweep']['agreeShare'],
        slots=[dict(slot=r['slot'], role=r['role'], material=r['material']) for r in m['slots']],
        coloursVary=(m['colours'] or {}).get('rule') == 'varying',
        lightmapMeasured=bool(e['lightmap'] and e['lightmap'].get('density')),
        **({'madeUp': made} if made else {}))


def measure(package, what):
    """A look's entry from the donor `what` (a placed actor's or a fracturing mesh's name) of the map `package` (a
    tools/upk Package): dict(recipe, warnings, facts). The same donor always gives the same entry."""
    g, ctx = donor(package, what)
    raw, state = _measure(g, ctx)
    recipe, made = recipe_of(raw, state, g)
    return dict(recipe=recipe, warnings=warnings_of(raw, recipe, made), facts=facts_of(raw, recipe, made, g['name']))


# ---------------------------------------------------------------------------------------------------- the twin check
TWIN_TOLERANCE = dict(height=0.05, length=0.05, half=0.05, endInset=0.05, profile=0.25, split=0.5, slope=2e-4,
                      tslope=0.02, value=0.02, collision=0.05, density=0.03, interiorDensity=0.05)


def made_collision(solids, centre):
    """measure_raw's collision entry for a made wall's collision boxes `solids` ([(lo, hi)])."""
    if not solids:
        return dict(simple=True, elements=0)
    y = np.array([v for lo, hi in solids for v in (lo[1], hi[1])]) - centre
    return dict(simple=True, elements=len(solids), half=round(float(max(y.max(), -y.min())), 3),
                y=[round(float(y.min()), 3), round(float(y.max()), 3)])


def width_at(prof, z):
    """A side's y at height z on its outline [[y, z]] (the first segment over it that is not a ledge)."""
    for (ya, za), (yb, zb) in zip(prof, prof[1:]):
        if za <= z <= zb and zb > za:
            return ya + (z - za) * (yb - ya) / (zb - za)
    return prof[0][0] if z < prof[0][1] else prof[-1][0]


def surface_at(recipe, X, z, x):
    """(slot, (u, v)) of side X's face at height z and x along the wall, as frac_wall's general path makes it: a face's
    slot by height and its slot's texture, or a segment's slot and its own (its side's first face texture where it has
    none measured); (None, None) where the side has no segment over z."""
    prof = recipe['profile'][X]
    for k, ((_, za), (_, zb)) in enumerate(zip(prof, prof[1:])):
        if za <= z <= zb and zb > za:
            return segment_surface(recipe, X, k, x, z, (z - za) / (zb - za))
    return None, None


def segment_surface(recipe, X, k, x, z, t):
    """(slot, (u, v)) of side X's segment k at x along the wall, height z and t up the segment (frac_wall's Profile
    .surface)."""
    st = recipe['strips'][X][k]
    slots = recipe['slots']['side' + X]
    if st['face'] and slots:
        band = sum(1 for s in recipe['splits'][X] if s < z)
        slot = slots[min(band, len(slots) - 1)]
        fit = recipe['faceUV'].get('%d%s' % (slot, X)) or next(iter(recipe['faceUV'].values()), None)
        return slot, planar(fit, x, z)
    if st['uv']:
        return st['slot'], tuple(f[0] * x + f[1] * t + f[2] for f in st['uv'])
    fits = [v for key, v in sorted(recipe['faceUV'].items()) if key.endswith(X)] or list(recipe['faceUV'].values())
    return st['slot'], planar(fits[0] if fits else None, x, z)


def planar(fit, x, z):
    """A face texture [[a, b, c], [d, e, f]] at (x, z): (u, v) = (a x + b z + c, d x + e z + f) (frac_wall's default
    where there is none)."""
    if not fit:
        return (x / STOREY, -z / STOREY)
    return tuple(f[0] * x + f[1] * z + f[2] for f in fit)


def made_surface(c, X, z):
    """(slot, (u, v)) of the made wall's face on side X at height z in the cut `c` (cut's, at some x): the outermost of
    the cut's segments facing that side over z, its texture where it crosses z; (None, None) where none is."""
    side = 1 if X == 'A' else -1
    a, b = c['a'], c['b']
    za, zb = a[:, 1], b[:, 1]
    lo, hi = np.minimum(za, zb), np.maximum(za, zb)
    ok = np.nonzero((c['normal'][:, 1] * side > 0.02) & (lo <= z) & (z <= hi) & (hi - lo > 1e-6))[0]
    if not len(ok):
        return None, None
    s = (z - za[ok]) / (zb[ok] - za[ok])
    y = (a[ok, 0] + s * (b[ok, 0] - a[ok, 0])) * side
    k = int(np.argmax(y))
    uv = c['uva'][ok[k]] + s[k] * (c['uvb'][ok[k]] - c['uva'][ok[k]])
    return int(c['slot'][ok[k]]), (float(uv[0]), float(uv[1]))


def made_level(c, z, y, up):
    """(slot, (u, v)) of the made wall's level face at height z (a ledge, the top or the bottom: facing up, or down)
    where it crosses y (from the centre line, +y side positive) in the cut `c`; (None, None) where none is."""
    a, b = c['a'], c['b']
    lo, hi = np.minimum(a[:, 0], b[:, 0]), np.maximum(a[:, 0], b[:, 0])
    ok = np.nonzero((c['normal'][:, 2] * (1 if up else -1) > 0.98) & (np.abs(a[:, 1] - z) < 0.01)
                    & (np.abs(b[:, 1] - z) < 0.01) & (lo <= y) & (y <= hi) & (hi - lo > 1e-6))[0]
    if not len(ok):
        return None, None
    k = ok[0]
    s = (y - a[k, 0]) / (b[k, 0] - a[k, 0])
    uv = c['uva'][k] + s * (c['uvb'][k] - c['uva'][k])
    return int(c['slot'][k]), (float(uv[0]), float(uv[1]))


def _turn(value):
    """A texture coordinate's distance from the nearest whole number (islands shifted by whole numbers draw the same)."""
    return abs(value - round(value))


def same_uv(a, b):
    """Whether two texture coordinates (u, v) draw the same: equal but for whole numbers."""
    return a is not None and b is not None and all(_turn(p - q) <= TWIN_TOLERANCE['value'] for p, q in zip(a, b))


def compare_recipes(want, got, built, wall, g):
    """The twin's rows: [dict(key, ok, note)] for each key that makes the look, the donor's recipe `want` against the
    twin's measured `got`, its length and ends from the made mesh `built` of `wall`, and what its faces show read off
    the made mesh (`g`, geometry_of's) in cuts across it."""
    T = TWIN_TOLERANCE
    rows = []

    def row(key, ok, note=''):
        rows.append(dict(key=key, ok=bool(ok), note=note))
    pos = np.array(built['mesh']['lods'][0]['positions'], float)
    length = float(pos[:, 0].max() - pos[:, 0].min())
    row('length', abs(length - want['donorLength']) <= T['length'], '%g against %g' % (length, want['donorLength']))
    inset = float(pos[:, 0].min()) - float(wall['x0'])
    row('endInset', abs(inset - want['endInset']) <= T['endInset'], '%g against %g' % (inset, want['endInset']))
    for key in ('bottom', 'top'):
        row(key, abs(got[key] - want[key]) <= T['height'], '%g against %g' % (got[key], want[key]))
    row('half', abs(got['half'] - want['half']) <= T['half'], '%g against %g' % (got['half'], want['half']))
    zs = np.arange(want['bottom'] + 0.5, want['top'], 1.0)
    lo = float(pos[:, 0].min())
    xs = [round(lo + f * length, 3) + 0.37 for f in (0.1, 0.5, 0.9)]
    cuts = {x: cut(g, x) for x in xs}

    def words(bad):
        return '; '.join(bad[:3]) + (' (and %d more)' % (len(bad) - 3) if len(bad) > 3 else '')
    for X in 'AB':
        dev = max([abs(width_at(got['profile'][X], z) - width_at(want['profile'][X], z)) for z in zs] or [0.0])
        row('profile' + X, dev <= T['profile'], 'off by up to %.3g (%d corners against %d)'
            % (dev, len(got['profile'][X]), len(want['profile'][X])))
        # what each side of the made wall shows (its slot and texture, read off its mesh) at heights through every
        # segment and on every ledge, against what the recipe says
        bad = []
        prof = want['profile'][X]
        heights = sorted({round(za + f * (zb - za), 3) for (_, za), (_, zb) in zip(prof, prof[1:])
                          if zb - za >= 0.5 for f in (0.25, 0.5, 0.75)})
        # (off the heights the face slots split at, where either slot is right)
        heights = [z + 0.05 if any(abs(z - s) < 0.01 for s in want['splits'][X]) else z for z in heights]
        for z in heights:
            for x in xs:
                ws, wuv = surface_at(want, X, z, x)
                gs, guv = made_surface(cuts[x], X, z)
                if gs is None:
                    bad.append('no face at %g up' % z)
                elif ws != gs:
                    bad.append('slot %s against %s at %g up' % (gs, ws, z))
                elif not same_uv(wuv, guv):
                    bad.append('texture (%.3f, %.3f) against (%.3f, %.3f) at %g up' % (*guv, *wuv, z))
                else:
                    continue
                break
        side = 1 if X == 'A' else -1
        for k, ((ya, za), (yb, zb)) in enumerate(zip(prof, prof[1:])):
            if zb - za > 1e-6 or abs(yb - ya) < 1e-6:
                continue
            for x in xs:
                ws, wuv = segment_surface(want, X, k, x, za, 0.5)
                gs, guv = made_level(cuts[x], za, side * (ya + yb) / 2, yb < ya)
                if gs is None:
                    bad.append('no ledge at %g up' % za)
                elif ws != gs or not same_uv(wuv, guv):
                    bad.append('the ledge at %g up: slot %s against %s' % (za, gs, ws))
                else:
                    continue
                break
        row('surface' + X, not bad, words(bad))
    row('interior', got['slots']['interior'] == want['slots']['interior'],
        '%s against %s' % (got['slots']['interior'], want['slots']['interior']))
    bad = []
    for key, up in (('top', True), ('bottom', False)):
        k = -1 if up else 0
        wa, wb = want['profile']['A'][k][0], want['profile']['B'][k][0]
        if wa + wb < 1e-3:
            continue                # (an outline that closes to an edge there: no level face either way)
        w = want['caps'][key]
        for x in xs:
            gs, guv = made_level(cuts[x], want[key], (wa - wb) / 2, up)
            if w is None:
                if gs is not None:
                    bad.append('the made wall has a level %s, its donor none' % key)
                    break
            elif gs is None:
                bad.append('the made wall has no level %s' % key)
                break
            elif gs != w['slot'] or not same_uv(planar(w['uv'], x, (wa - wb) / 2), guv):
                bad.append('its %s: slot %s against %s' % (key, gs, w['slot']))
                break
    row('caps', not bad, '; '.join(bad))
    row('colours', got['colours'] == want['colours'], '%s against %s' % (got['colours'], want['colours']))
    # the fragments: about as many on the donor's solid by the twin's measured cell as by the recipe's
    L, H = want['donorLength'], want['top'] - want['bottom']
    grid = [max(1, round(L / want['cell'][0])), max(1, round(H / want['cell'][1]))]
    measured = [max(1, round(L / got['cell'][0])), max(1, round(H / got['cell'][1]))]
    row('cell', abs(measured[0] * measured[1] - grid[0] * grid[1]) <= 0.1 * grid[0] * grid[1] + 1,
        'a grid of %d x %d against %d x %d' % (*measured, *grid))
    row('collisionY', all(abs(a - b) <= T['collision'] for a, b in zip(got['collisionY'], want['collisionY'])),
        '%s against %s' % (got['collisionY'], want['collisionY']))
    lw, lg = want['lightmap'], got['lightmap']
    row('lightmap', abs(lg['density'] - lw['density']) <= T['density'] * lw['density']
        and abs(lg['interiorDensity'] - lw['interiorDensity']) <= T['interiorDensity'],
        '%g, %g against %g, %g' % (lg['density'], lg['interiorDensity'], lw['density'], lw['interiorDensity']))
    row('sections', got['sections'] == want['sections'], '%d against %d' % (got['sections'], want['sections']))
    row('storeys', got['storeys'] == want['storeys'], '%d against %d' % (got['storeys'], want['storeys']))
    return rows


def twin(recipe):
    """The twin check of a look: the wall made at its donor's length (no openings, seed 1: frac_wall.build), measured
    again with this measurer, each key that makes the look compared with the recipe's (compare_recipes). dict(ok, rows,
    made (the made wall's counts))."""
    import frac_wall
    inset = float(recipe['endInset'])
    wall = dict(x0=0.0, x1=float(recipe['donorLength']) + 2 * inset, openings=[], seed=1,
                look=dict(mesh=recipe['donor'], measure=recipe['measure'], recipe=recipe))
    built = frac_wall.build(wall)
    g = geometry_of(built['mesh'], recipe['donor'], 1)
    rect = built['lightmapRect']
    half = float(recipe['half'])
    ctx = dict(map=None, actor=None, materials={}, planes=(half, -half, 0.0, half),
               lightmap=lambda g, ya, yb: densities(g, ya, yb, rect, None),
               insets=lambda g: end_insets(None, None, g),
               collision=lambda g, centre: made_collision(built['solids'], centre))
    raw, state = _measure(g, ctx)
    again, _ = recipe_of(raw, state, g)
    rows = compare_recipes(recipe, again, built, wall, g)
    return dict(ok=all(r['ok'] for r in rows), rows=rows, made=built['counts'])
