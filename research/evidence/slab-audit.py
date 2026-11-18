"""Read-only audit of the game's fracturing floors and roofs (slabs), for floors and roofs made from numbers
(private/plans/todo/custom-geometry-implementation-plan.md, stage M5, item 1, and what items 2 and 3 need).

Over every map the install lists (tools/viewer/library.py donors), or the maps named with --maps, it reads each placed
fracturing piece (XComFracLevelActor, XComDecoFracLevelActor) of the persistent level and its mesh. A slab is a mesh
named for a floor, roof, slab, deck or balcony that is wide (both sides at least 80) and flat (at most 24 thick: kind
'flat'), or has a flat top over a deeper body (at most 80: 'thick'), or is a roof whose top slopes ('pitched'); or
any mesh at most 24 thick and wide, whatever its name. Named meshes that fail the shape test are listed with why.

  meshes      per slab mesh: kind, size, thickness, triangles, fragments; each section (slot): its faces by area
              (top: facing up; underside: facing down; edges: the sides on the outline; sides: other sides; inside:
              the interior slot's, seen once a fragment goes), the materials the placed components bind to it, the
              texture repeat on each kind of face (world units per UV unit), its vertex colours; the top's vertices
              against the slab's own 96 grid and its level triangles' edges (along x, along y, a tile's diagonal);
              the fragments: sizes in tiles, rectangles or not, their level top in tiles (whole or half tiles), on
              the slab's own 96 grid or not, through the whole thickness or not, one colour each or not; the simple
              collision (its boxes against the drawn mesh); the mesh's saved properties; the top's holes and notches
              (its up faces rasterised; an empty region not on the border is a hole) and the fragments round each
              hole
  placed      per placed slab: map, actor, pose, world box against the level's piece grid (native_copy.level_grid's
              ox, oy, oz), its role (floor or roof by name; slabs over it; the building volume floors whose cached
              actors list it, with CutdownFloor; the cursor volume floor of its top and of its underside), its saved
              actor and component properties, the fragments the level designer hid (EditorPaintedVisibleFragments:
              how many, where), and the map's baked tiles a unit would stand in on it (tools/upk/wdparse.py; the
              tile level holding its top): how many have the floor bit (0x2000) and the occupied bit (0x8000), over
              shown and over hidden fragments, and how many have another flat piece's top there too
  columns     every placed fracturing piece's FragmentColumns (slabs, and walls and the rest as controls) against the
              piece-grid rule (research/native/frac-neighbours.md): cells of 96 x 96 x 192 counted from the piece's
              vertices' lowest corner less one unit, in x, then y, then z; a column for every cell the piece's box
              reaches; its FragCache the fragments whose box meets the cell (three ways: an open overlap, a closed one
              as UE3's FBox::Intersect, and a closed one leaving the hidden fragments out), each with its lowest
              corner's height (MinZ), lowest first; its box the cell cut in x and y to the listed fragments' boxes (z
              the cell's; an empty column the whole cell). Each column's inner edges also against the level's tile
              grid (tx, ty, tz)
  caches      each slab column's DestructibleCache (the props it lists: class, above, below, through or level with
              the slab, over or off its footprint, how far from the column's box, MinZ against the prop's bounds and
              location; against the rule: the props whose box overlaps the column's box) and FracActorCache (the
              pieces whose columns it lists: slab, wall or other, and where; against frac-neighbours.md's rule: a
              column lists another piece's column whose box, cut to that piece's own box grown by a unit, touches or
              overlaps its own; the listings the rule gives and the map lacks, by where)
  flags       the saved actor, component and mesh properties of floors, roofs, walls and the other fracturing pieces
              side by side, and the class defaults the game's script package saves (XComGame.upk beside the maps)

Prints a summary; --output writes the JSON (summaries, every slab mesh, every placed slab with its columns summed,
samples of columns and cache entries). No game file is written.

  python -B research/evidence/slab-audit.py [--maps URB_Bar URB_PierA] [--output <file.json>] [--verbose]
"""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
import struct
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for folder in ('viewer', 'upk', 'lab', 'bake'):
    sys.path.insert(0, str(ROOT / 'tools' / folder))
import gen_mesh  # noqa: E402
import lightmap_texels  # noqa: E402
from package import Package  # noqa: E402

FRACTURING = ('XComDecoFracLevelActor', 'XComFracLevelActor')
TILE, STOREY = 96.0, 192.0
NAMED = re.compile(r'floor|roof|slab|deck|balcon|ceiling', re.I)
WIDE, FLAT, THICK = 80.0, 24.0, 80.0
UP = 0.3            # a face whose outward normal's z is at least this faces up (at most -UP: down)
LEVEL_UP = 0.98     # a level face
RASTER = 4.0        # the top's raster cell, for holes
TOL = 0.05          # box edges equal within this
LEVEL = 64.0        # a tile level's height
PROP_CLASSES = ('XComDestructibleActor', 'XComCollectible', 'XComInteractiveLevelActor', 'XComDestructibleSkeletal')
SKIP_PROPS = {'Location', 'Rotation', 'FragmentColumns', 'VisibilityId', 'FracturedStaticMeshComponent',
              'CollisionComponent', 'StaticMesh', 'IrrelevantLights', 'EditorPaintedVisibleFragments',
              'ReplacementPrimitive', 'LightEnvironment', 'Components', 'SavedSelections', 'DrawScale3D'}


# ---------------------------------------------------------------------------------------------------- geometry
def triangles_of(m):
    """LOD 0's triangles: (index array n x 3, slot per triangle, fragment per triangle)."""
    lod = m['lods'][0]
    idx = lod['indices'][1]
    tris, slots, frags = [], [], []
    for s in lod['sections']:
        if s['fragments']:
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
    return np.array(tris, int).reshape(-1, 3), np.array(slots, int), np.array(frags, int)


def outward(pos, tris):
    """Each triangle's outward unit normal and area: UE3 winds front faces so that cross(b - a, c - a) points into
    the surface (tools/viewer/area_light_bindings.py)."""
    a, b, c = pos[tris[:, 0]], pos[tris[:, 1]], pos[tris[:, 2]]
    n = np.cross(c - a, b - a)
    length = np.linalg.norm(n, axis=1)
    return n / np.maximum(length, 1e-12)[:, None], length / 2


def unpack_normal(raw):
    return np.array([raw[k] / 127.5 - 1.0 for k in range(3)])


def boxes_of(points, groups):
    """{group: [x0, x1, y0, y1, z0, z1]} of the points (n x 3) each group's vertex indices name."""
    out = {}
    for g, verts in groups.items():
        if verts:
            pts = points[sorted(verts)]
            out[g] = [float(v) for k in range(3) for v in (pts[:, k].min(), pts[:, k].max())]
    return out


def overlaps(a, b, slack=0.0):
    """Open boxes overlapping by more than `slack` on every axis."""
    return all(min(a[2 * k + 1], b[2 * k + 1]) - max(a[2 * k], b[2 * k]) > slack for k in range(3))


def box_hits(boxes, box, slack, strict):
    """Which rows of `boxes` (n x 6) meet `box`: their overlap on every axis more than `slack` (strict) or at least
    it."""
    if not len(boxes):
        return np.zeros(0, bool)
    ok = np.ones(len(boxes), bool)
    for k in range(3):
        d = np.minimum(boxes[:, 2 * k + 1], box[2 * k + 1]) - np.maximum(boxes[:, 2 * k], box[2 * k])
        ok &= d > slack if strict else d >= slack
    return ok


def cut_columns(pieces):
    """Every piece's saved column boxes cut to its own box grown by a unit (frac-neighbours.md's rule): (boxes n x 6,
    owners n x 2: the piece and the column's index)."""
    boxes, owners = [], []
    for j, q in pieces.items():
        qb = q['box']
        grown = [qb[0] - 1, qb[1] + 1, qb[2] - 1, qb[3] + 1, qb[4] - 1, qb[5] + 1]
        for n, qc in enumerate(q['cols']):
            boxes.append([v for a in range(3) for v in (max(qc['box'][2 * a], grown[2 * a]),
                                                         min(qc['box'][2 * a + 1], grown[2 * a + 1]))])
            owners.append((j, n))
    return np.array(boxes, float).reshape(-1, 6), np.array(owners, int).reshape(-1, 2)


def same_box(a, b, tol=TOL):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def repeat(points, uvs):
    """World units per UV unit along u and v (least squares of each over the points' live axes), or None."""
    if len(points) < 3:
        return None
    live = [k for k in range(3) if np.ptp(points[:, k]) > 1e-3]
    if not live:
        return None
    a = np.c_[points[:, live], np.ones(len(points))]
    out = []
    for c in range(2):
        s, *_ = np.linalg.lstsq(a, uvs[:, c], rcond=None)
        g = float(np.linalg.norm(s[:len(live)]))
        out.append(round(1 / g, 1) if g > 1e-9 else None)
    return out


def raster_top(pos, tris, cell=RASTER):
    """The up faces' cover of the mesh's xy box, cell by cell: (grid of bools [ny, nx], x0, y0, cell)."""
    lo, hi = pos[:, :2].min(0), pos[:, :2].max(0)
    nx, ny = max(1, int(math.ceil((hi[0] - lo[0]) / cell))), max(1, int(math.ceil((hi[1] - lo[1]) / cell)))
    grid = np.zeros((ny, nx), bool)
    xs = lo[0] + (np.arange(nx) + 0.5) * cell
    ys = lo[1] + (np.arange(ny) + 0.5) * cell
    for t in tris:
        p = pos[t][:, :2]
        i0, i1 = np.searchsorted(xs, p[:, 0].min() - 1e-6), np.searchsorted(xs, p[:, 0].max() + 1e-6)
        j0, j1 = np.searchsorted(ys, p[:, 1].min() - 1e-6), np.searchsorted(ys, p[:, 1].max() + 1e-6)
        if i1 <= i0 or j1 <= j0:
            continue
        gx, gy = np.meshgrid(xs[i0:i1], ys[j0:j1])
        d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
        if abs(d) < 1e-9:
            continue
        l1 = ((p[1, 1] - p[2, 1]) * (gx - p[2, 0]) + (p[2, 0] - p[1, 0]) * (gy - p[2, 1])) / d
        l2 = ((p[2, 1] - p[0, 1]) * (gx - p[2, 0]) + (p[0, 0] - p[2, 0]) * (gy - p[2, 1])) / d
        inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (1 - l1 - l2 >= -1e-6)
        grid[j0:j1, i0:i1] |= inside
    return grid, float(lo[0]), float(lo[1]), cell


def on_grid(v, origin, period=TILE, tol=0.6):
    r = (v - origin) % period
    return min(r, period - r) <= tol


# ---------------------------------------------------------------------------------------------------- meshes
def painted_fragments(p, comp, frags):
    """(listed, hidden) fragments of a component's EditorPaintedVisibleFragments, or None when it saves none."""
    raw = p.own(comp, 'EditorPaintedVisibleFragments')
    if raw is None:
        return None
    n = struct.unpack_from('<i', raw, 0)[0]
    body = raw[4:]
    if len(body) == 4 * n:
        ints = struct.unpack('<%di' % n, body)
        values = list(ints) if all(v in (0, 1) for v in ints) else list(body)
    else:
        values = list(body)
    values = values[:frags]
    return dict(saved=len(values), hidden=[k for k, v in enumerate(values) if not v])


def mesh_record(p, mesh, m):
    """What a slab mesh is made of (in its own frame)."""
    lod = m['lods'][0]
    pos = np.array(lod['positions'], float)
    tris, slots, tfrag = triangles_of(m)
    normal, area = outward(pos, tris)
    nz = normal[:, 2]
    size = [float(np.ptp(pos[:, k])) for k in range(3)]
    lo = pos.min(0)
    frags = m['fractured']['fragments']
    interior = m['fractured']['interior']
    # the winding check: each triangle's outward normal against its first vertex's packed normal
    vn = np.array([unpack_normal(lod['vertices'][t[0]][1]) for t in tris]) if len(tris) else np.zeros((0, 3))
    agree = int(np.sum(np.einsum('ij,ij->i', vn, normal) > 0)) if len(tris) else 0
    # the outline: side faces whose centre lies on the mesh's xy box edge, or whose fragment has no neighbour there
    centre = pos[tris].mean(1)
    on_box = (np.abs(centre[:, 0] - lo[0]) < 0.6) | (np.abs(centre[:, 0] - pos[:, 0].max()) < 0.6) | \
             (np.abs(centre[:, 1] - lo[1]) < 0.6) | (np.abs(centre[:, 1] - pos[:, 1].max()) < 0.6)
    sections = []
    colours = lod['colours'] or []
    uv0 = np.array([v[2][0] for v in lod['vertices']], float) if lod['vertices'] else np.zeros((0, 2))
    for slot in sorted(set(slots.tolist())):
        sel = slots == slot
        up, down = sel & (nz >= UP), sel & (nz <= -UP)
        side = sel & (np.abs(nz) < UP)
        rec = dict(slot=int(slot), triangles=int(sel.sum()), interiorSlot=slot == interior,
                   area=dict(up=round(float(area[up].sum())), down=round(float(area[down].sum())),
                             side=round(float(area[side].sum())),
                             sideOnBox=round(float(area[side & on_box].sum()))),
                   fragments=len(set(tfrag[sel].tolist()) - {-1}))
        for name, s in (('up', up), ('down', down), ('side', side)):
            if s.any():
                verts = sorted(set(tris[s].ravel().tolist()))
                rec.setdefault('z', {})[name] = [round(float(pos[verts, 2].min()), 2), round(float(pos[verts, 2].max()), 2)]
                rec.setdefault('repeat', {})[name] = repeat(pos[verts], uv0[verts]) if len(uv0) else None
        verts = sorted(set(tris[sel].ravel().tolist()))
        if colours:
            c = Counter(bytes(colours[v]).hex() for v in verts)
            rec['colours'] = dict(distinct=len(c), common=c.most_common(3))
        faces = []
        if rec['interiorSlot']:
            faces.append('inside')
        else:
            a = rec['area']
            total = max(a['up'] + a['down'] + a['side'], 1)
            if a['up'] / total > 0.05:
                faces.append('top')
            if a['down'] / total > 0.05:
                faces.append('underside')
            if a['side'] / total > 0.002:
                faces.append('edges' if a['sideOnBox'] >= 0.5 * a['side'] else 'sides')
        rec['faces'] = '+'.join(faces)
        sections.append(rec)
    # the fragments
    groups = defaultdict(set)
    for t, f in zip(tris, tfrag):
        if f >= 0:
            groups[int(f)].update(int(v) for v in t)
    fbox = boxes_of(pos, groups)
    up_area = defaultdict(float)
    for a_, f, z_ in zip(area, tfrag, nz):
        if f >= 0 and z_ >= LEVEL_UP:
            up_area[int(f)] += float(a_)
    tiles, rect, grid, through, one_colour = Counter(), 0, 0, 0, 0
    grid_x, grid_y, whole, counts = 0, 0, 0, Counter()
    for f, b in fbox.items():
        w, h = b[1] - b[0], b[3] - b[2]
        tiles['%gx%g' % (round(2 * w / TILE) / 2, round(2 * h / TILE) / 2)] += 1
        rect += abs(up_area[f] - w * h) <= max(0.01 * w * h, 1.0)
        gx, gy = all(on_grid(v, lo[0]) for v in b[0:2]), all(on_grid(v, lo[1]) for v in b[2:4])
        grid += gx and gy
        grid_x += gx
        grid_y += gy
        n = up_area[f] / TILE ** 2          # its level top in whole tiles: a union of tiles is a whole number
        whole += n >= 0.99 and abs(n - round(n)) <= 0.01
        counts['%g' % round(n, 2)] += 1
        through += b[5] - b[4] >= size[2] - 0.5
        if colours:
            one_colour += len({bytes(colours[v]) for v in groups[f]}) == 1
    sizes = np.array([[b[1] - b[0], b[3] - b[2], b[5] - b[4]] for b in fbox.values()]) if fbox else np.zeros((0, 3))
    rec = dict(size=[round(v, 1) for v in size], thickness=round(size[2], 2), triangles=len(tris),
               vertices=len(pos), sections=sections, interiorIndex=interior, core=m['fractured']['core'],
               uvChannels=lod['texcoords'], lightmapCoordinate=p.own(mesh, 'LightMapCoordinateIndex'),
               lightMapResolution=p.own(mesh, 'LightMapResolution'),
               windingAgreesWithVertexNormals=[agree, len(tris)],
               fragments=dict(count=len(frags), withTriangles=len(fbox),
                              medianSize=[round(float(np.median(sizes[:, k])), 1) for k in range(3)] if len(sizes) else None,
                              tiles=dict(tiles.most_common(8)), rectangles=rect, onOwn96Grid=grid,
                              onOwn96GridX=grid_x, onOwn96GridY=grid_y, wholeTiles=whole,
                              topInTiles=dict(counts.most_common(6)),
                              throughThickness=through, oneColourEach=one_colour if colours else None,
                              destroyable=sum(1 for g in frags if g['destroyable']),
                              roots=sum(1 for g in frags if g['root']),
                              neverSpawn=sum(1 for g in frags if g['neverSpawn']),
                              extra=Counter(g['extra'] for g in frags).most_common(2),
                              perTile=round(len(frags) / max(size[0] * size[1] / TILE ** 2, 1e-9), 2)),
               colourValues=len({bytes(c) for c in colours}) if colours else 0)
    rec['meshProps'] = {k: v for k, v in saved_props(p, mesh, values=True).items() if k != 'BodySetup'}
    rec['collision'] = collision_record(p, mesh, pos)
    # the top's vertices against the slab's own 96 grid, and its level triangles' edges: x, y (along an axis), d
    # (a tile's diagonal) or o (other)
    level = tris[nz >= LEVEL_UP]
    if len(level):
        verts = pos[sorted(set(level.ravel().tolist()))][:, :2] - lo[:2]
        rec['topVerticesOn96Grid'] = [int(np.all(np.minimum(verts % TILE, TILE - verts % TILE) < 0.6, axis=1).sum()),
                                      len(verts)]
        shapes = Counter()
        for tri in level:
            q = pos[tri][:, :2]
            kinds = []
            for e in (q[1] - q[0], q[2] - q[1], q[0] - q[2]):
                kinds.append('x' if abs(e[1]) < 0.5 else 'y' if abs(e[0]) < 0.5
                             else 'd' if abs(abs(e[0]) - abs(e[1])) < 0.5 else 'o')
            shapes[''.join(sorted(kinds))] += 1
        rec['topTriangleEdges'] = dict(shapes.most_common(4))
    # the top: up faces rasterised; empty regions on the border are notches, others holes
    ups = tris[nz >= UP]
    if len(ups):
        top, x0, y0, cell = raster_top(pos, ups)
        rec['top'] = dict(cover=round(float(top.mean()), 4), level=round(float(area[nz >= LEVEL_UP].sum() /
                                                                              max(area[nz >= UP].sum(), 1e-9)), 3))
        rec['holes'], rec['notches'] = holes(top, x0, y0, cell, lo, fbox)
    return rec, fbox


def holes(top, x0, y0, cell, lo, fbox):
    """The top's empty regions: (holes [dict(box, size, area, rectangle (its share of its box), onGrid (its edges on
    the slab's own 96 grid), fragmentsRound (fragments whose box comes within two raster cells))], notches count and
    area)."""
    from scipy import ndimage
    labels, n = ndimage.label(~top)
    out, notches, notch_area = [], 0, 0.0
    ny, nx = top.shape
    for k in range(1, n + 1):
        js, is_ = np.nonzero(labels == k)
        a = len(js) * cell * cell
        if a < 4 * cell * cell:
            continue                            # a sliver between rasterised faces
        if js.min() == 0 or is_.min() == 0 or js.max() == ny - 1 or is_.max() == nx - 1:
            notches += 1
            notch_area += a
            continue
        box = [x0 + is_.min() * cell, x0 + (is_.max() + 1) * cell, y0 + js.min() * cell, y0 + (js.max() + 1) * cell]
        round_it = [f for f, b in fbox.items()
                    if b[0] <= box[1] + 2 * cell and b[1] >= box[0] - 2 * cell
                    and b[2] <= box[3] + 2 * cell and b[3] >= box[2] - 2 * cell]
        out.append(dict(box=[round(v, 1) for v in box], size=[round(box[1] - box[0], 1), round(box[3] - box[2], 1)],
                        area=round(a), rectangle=round(a / ((box[1] - box[0]) * (box[3] - box[2])), 3),
                        onGrid=all(on_grid(v, lo[0], tol=cell) for v in box[0:2])
                        and all(on_grid(v, lo[1], tol=cell) for v in box[2:4]),
                        fragmentsRound=len(round_it)))
    return out, dict(count=notches, area=round(notch_area))


def collision_record(p, mesh, pos):
    """The mesh's simple collision (tools/viewer/collision.py): its elements' boxes in the mesh's frame, their
    top and bottom against the mesh's, and their share of the mesh's xy box."""
    import collision
    try:
        c = collision.line_collision(p, mesh)
    except (ValueError, KeyError, struct.error) as err:
        return dict(error=str(err))
    if not c.get('simple'):
        return dict(simple=False)
    boxes = []
    for e in c['elements']:
        q = np.array(e, float).reshape(-1, 3)
        boxes.append([round(float(v), 2) for k in range(3) for v in (q[:, k].min(), q[:, k].max())])
    area = np.ptp(pos[:, 0]) * np.ptp(pos[:, 1])
    return dict(elements=len(boxes), boxes=boxes[:6],
                top=max((b[5] for b in boxes), default=None), bottom=min((b[4] for b in boxes), default=None),
                meshTop=round(float(pos[:, 2].max()), 2), meshBottom=round(float(pos[:, 2].min()), 2),
                xyShare=round(sum((b[1] - b[0]) * (b[3] - b[2]) for b in boxes) / max(area, 1e-9), 3))


def classify(name, rec):
    """(kind, why) of a mesh: 'flat', 'thick', 'pitched' or None (left out) with the reason."""
    sx, sy, sz = rec['size']
    named = bool(NAMED.search(name.rsplit('.', 1)[-1]))
    level = rec.get('top', {}).get('level', 0)
    if min(sx, sy) < WIDE:
        return None, 'narrow (%.0f): a trim, parapet or cover' % min(sx, sy)
    if sz <= FLAT:
        return 'flat', None
    if not named:
        return None, 'not named for a floor or roof and %.0f thick' % sz
    if sz <= THICK and level >= 0.8 and sz < 0.25 * min(sx, sy):
        return 'thick', None
    if 'roof' in name.lower() and level < 0.5 and rec.get('top', {}).get('cover', 0) >= 0.85 and min(sx, sy) >= 150:
        return 'pitched', None
    return None, '%.0f thick, %.0f%% of its top level' % (sz, 100 * level)


# ---------------------------------------------------------------------------------------------------- the map
def brush_box(p, volume):
    import native_copy
    try:
        lo, hi = native_copy.brush_box(p, volume)
        return [lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]]
    except (ValueError, KeyError, struct.error):
        return None


def map_context(p, level):
    """The map's building volume floors (by cached actor), floor and cursor volumes, and its props' boxes."""
    import native_copy
    cached = defaultdict(list)
    buildings = []
    cursor = []
    for i in range(1, len(p.exports) + 1):
        if p.exports[i - 1]['outer'] != level:
            continue
        cls = p.cls(i)
        if cls == 'XComBuildingVolume':
            floors = p.structs(p.own(i, 'Floors'))
            box = brush_box(p, i)
            buildings.append(dict(name=p.name(i).split('.')[-1], box=box, floors=len(floors)))
            for k, f in enumerate(floors, 1):
                vols = p.refs(f.get(('FloorVolumes', 0), {}).get('value'))
                vboxes = [brush_box(p, v) for v in vols if v > 0]
                for st in p.structs(f.get(('m_aCachedActors', 0), {}).get('value')):
                    a = st.get(('ResidentActor', 0), {}).get('value', 0)
                    cut = st.get(('CutdownFloor', 0), {}).get('value', 0)
                    cached[a].append(dict(building=buildings[-1]['name'], floor=k, floors=len(floors),
                                          cutdownFloor=cut, buildingBox=box,
                                          floorZ=[[round(b[4]), round(b[5])] for b in vboxes if b]))
        elif cls == 'XComCursorVolume':
            box = brush_box(p, i)
            if box:
                cursor.append((box, p.own(i, 'm_iFloorNumber')))
    try:
        grid = native_copy.level_grid(p)
    except (ValueError, KeyError) as err:
        grid = dict(error=str(err))
    return dict(cached=cached, buildings=buildings, cursor=cursor, grid=grid, tiles=baked_tiles(p))


def baked_tiles(p):
    """The map's baked static tile store (its XComWorldDataContainer, tools/upk/wdparse.py) as {(chunk x, y, z):
    chunk}, or None."""
    import wdparse
    found = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'XComWorldDataContainer']
    if len(found) != 1:
        return None
    e = p.exports[found[0] - 1]
    try:
        store = wdparse.parse(p.data[e['off']:e['off'] + e['size']])
    except (ValueError, KeyError, IndexError, struct.error):
        return None
    return {(c['x'], c['y'], c['z']): c for c in store['chunks']}


def tile_flags(chunks, x, y, z):
    """A tile's flag word (tools/lab/save_tiles.py's), or None outside the store."""
    import wdparse
    c = chunks.get((x - x % 3, y - y % 3, z - z % 2))
    return c['tiles'][wdparse.tile_index(x, y, z)][0] if c else None


def floor_tiles(ctx, fbox, hidden, top, others=None):
    """The baked tiles a unit would stand in on the slab (the level holding its top), each whose centre lies over a
    fragment: {'visible'|'hidden': dict(tiles, floor (bit 0x2000), occupied (0x8000), otherPiece: another flat piece
    (`others`, boxes n x 6, at most 40 tall) has its top within 4 units of the slab's over the tile's centre)}."""
    grid, chunks = ctx['grid'], ctx['tiles']
    if chunks is None or 'tx' not in grid:
        return None
    level = int((top + 1 - grid['tz']) // LEVEL)
    out = {}
    lo = [min(b[0] for b in fbox.values()), min(b[2] for b in fbox.values())]
    hi = [max(b[1] for b in fbox.values()), max(b[3] for b in fbox.values())]
    for i in range(int((lo[0] - grid['tx']) // TILE), int((hi[0] - grid['tx']) // TILE) + 1):
        for j in range(int((lo[1] - grid['ty']) // TILE), int((hi[1] - grid['ty']) // TILE) + 1):
            x, y = grid['tx'] + TILE * (i + 0.5), grid['ty'] + TILE * (j + 0.5)
            over = [f for f, b in fbox.items() if b[0] < x < b[1] and b[2] < y < b[3]]
            if not over:
                continue
            kind = 'visible' if any(f not in hidden for f in over) else 'hidden'
            f = tile_flags(chunks, i, j, level)
            if f is None:
                continue
            rec = out.setdefault(kind, Counter())
            rec['tiles'] += 1
            rec['floor'] += bool(f & 0x2000)
            rec['occupied'] += bool(f & 0x8000)
            if others is not None and len(others):
                rec['otherPiece'] += bool(np.any((others[:, 0] < x) & (others[:, 1] > x) & (others[:, 2] < y)
                                                 & (others[:, 3] > y) & (np.abs(others[:, 5] - top) <= 4)
                                                 & (others[:, 5] - others[:, 4] <= 40)))
    return {k: dict(v) for k, v in out.items()} or None


def cursor_floor(ctx, x, y, z):
    for box, n in ctx['cursor']:
        if box[0] <= x <= box[1] and box[2] <= y <= box[3] and box[4] <= z < box[5]:
            return n
    return None


def props_boxes(p, level, classes=PROP_CLASSES):
    """{actor: world box} of the map's props (destructibles, collectibles, doors; or the actors of `classes`) from
    their meshes' bounds."""
    out = {}
    for i in range(1, len(p.exports) + 1):
        if p.exports[i - 1]['outer'] != level or not p.cls(i).startswith(classes):
            continue
        comp = p.own(i, 'StaticMeshComponent') or p.own(i, 'SkeletalMeshComponent')
        if not comp or comp < 0:
            continue
        mesh = p.effective(comp, 'StaticMesh', 0) or p.effective(comp, 'SkeletalMesh', 0)
        if not mesh or mesh < 0 or p.cls(mesh) != 'StaticMesh':
            continue
        try:
            b = struct.unpack_from('<7f', p.data, p.properties(mesh)[1])
            world = lightmap_texels.world_matrix(p, comp)
        except (ValueError, struct.error):
            continue
        corners = np.array([[b[0] + sx * b[3], b[1] + sy * b[4], b[2] + sz * b[5], 1.0]
                            for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]) @ world.T
        out[i] = dict(box=[float(v) for k in range(3) for v in (corners[:, k].min(), corners[:, k].max())],
                      mesh=p.name(mesh), cls=p.cls(i))
    return out


def saved_props(p, index, values=False):
    """{property: value summary} of an export's saved tagged properties (with `values`, floats and vectors too)."""
    out = {}
    for (k, slot), v in p.properties(index)[0].items():
        if slot or k in SKIP_PROPS:
            continue
        val = v['value']
        if v['kind'] in ('BoolProperty', 'NameProperty') or (v['kind'] == 'ByteProperty' and not isinstance(val, bytes)):
            out[k] = val
        elif v['kind'] == 'ObjectProperty':
            out[k] = (p.name(val).rsplit('.', 1)[-1] if val < 0 else p.cls(val)) if val else None
        elif v['kind'] == 'IntProperty' and k in ('OverriddenLightMapRes',):
            out[k] = val
        elif k == 'Materials':
            out[k] = len(p.refs(val))
        elif values and v['kind'] in ('FloatProperty', 'IntProperty'):
            out[k] = round(val, 3) if isinstance(val, float) else val
        elif values and isinstance(val, list):
            out[k] = [round(x, 3) for x in val]
        else:
            out[k] = '(saved)'
    return out


# ---------------------------------------------------------------------------------------------------- columns
def saved_columns(p, actor):
    out = []
    for c in p.structs(p.own(actor, 'FragmentColumns')):
        b = struct.unpack('<6fB', c[('Bounds', 0)]['value'])
        frags = [(it.get(('FragIndex', 0), {}).get('value', 0), it.get(('MinZ', 0), {}).get('value', 0.0))
                 for it in p.structs(c.get(('FragCache', 0), {}).get('value'))]
        destr = [(it.get(('DestructibleActor', 0), {}).get('value', 0), it.get(('MinZ', 0), {}).get('value', 0.0))
                 for it in p.structs(c.get(('DestructibleCache', 0), {}).get('value'))]
        near = [(it.get(('FracActor', 0), {}).get('value', 0), it.get(('ColumnIndex', 0), {}).get('value', 0))
                for it in p.structs(c.get(('FracActorCache', 0), {}).get('value'))]
        out.append(dict(box=[b[0], b[3], b[1], b[4], b[2], b[5]], frags=frags, destr=destr, near=near))
    return out


def rule_columns(fbox, closed=True, skip=()):
    """The columns the piece-grid rule gives for fragment world boxes `fbox` ({fragment: box}): [dict(box, cell,
    frags (sorted indices))] in x, then y, then z. A fragment is listed when its box meets the cell's: touching counts
    when `closed` (UE3's FBox::Intersect), else only an overlap; the fragments in `skip` (hidden ones) never are."""
    lo = [min(b[2 * k] for b in fbox.values()) for k in range(3)]
    hi = [max(b[2 * k + 1] for b in fbox.values()) for k in range(3)]
    step = (TILE, TILE, STOREY)
    anchor = [v - 1.0 for v in lo]
    n = [max(1, int(math.ceil((hi[k] - anchor[k]) / step[k] - 1e-6))) for k in range(3)]
    out = []
    for i in range(n[0]):
        for j in range(n[1]):
            for s in range(n[2]):
                cell = [anchor[0] + step[0] * i, anchor[0] + step[0] * (i + 1), anchor[1] + step[1] * j,
                        anchor[1] + step[1] * (j + 1), anchor[2] + step[2] * s, anchor[2] + step[2] * (s + 1)]
                listed = sorted(f for f, b in fbox.items() if f not in skip and
                                (all(min(b[2 * q + 1], cell[2 * q + 1]) - max(b[2 * q], cell[2 * q]) >= 0
                                     for q in range(3)) if closed else overlaps(b, cell)))
                box = list(cell)
                if listed:
                    for k in range(2):
                        box[2 * k] = max(cell[2 * k], min(fbox[f][2 * k] for f in listed))
                        box[2 * k + 1] = min(cell[2 * k + 1], max(fbox[f][2 * k + 1] for f in listed))
                out.append(dict(box=box, cell=cell, frags=listed))
    return out, lo, hi


RULES = ('open', 'closed', 'closedVisible')


def column_test(saved, fbox, flo, grid, hidden=()):
    """The saved columns against the rule (three ways: fragments listed by an open overlap with the cell, by a closed
    one, and by a closed one leaving out the hidden fragments): counts, and the first difference for samples."""
    rules = {}
    for name in RULES:
        rules[name], lo, hi = rule_columns(fbox, closed=name != 'open', skip=hidden if name == 'closedVisible' else ())
    rule = rules['closedVisible']
    rec = Counter(columns=len(saved), ruleColumns=len(rule))
    rec['sameCount'] = len(saved) == len(rule)
    first = None
    for k, c in enumerate(saved):
        listed = sorted(f for f, _ in c['frags'])
        for name in RULES:
            r = rules[name][k] if k < len(rules[name]) else None
            ok_box = r is not None and same_box(c['box'], r['box'])
            ok_frags = r is not None and listed == r['frags']
            rec[name + 'Box'] += ok_box
            rec[name + 'Frags'] += ok_frags
            rec[name + 'Both'] += ok_box and ok_frags
        r = rule[k] if k < len(rule) else None
        ok = r is not None and same_box(c['box'], r['box']) and listed == r['frags']
        rec['empty'] += not listed
        rec['minZSorted'] += [z for _, z in c['frags']] == sorted(z for _, z in c['frags'])
        for f, z in c['frags']:
            if f in flo:
                rec['minZ'] += 1
                rec['minZLowest'] += abs(z - flo[f]) <= 0.02
        # the alternatives: listed by overlap with the saved box; the box cut to the piece's own box
        rec['fragBySavedBox'] += listed == sorted(f for f, b in fbox.items() if overlaps(b, c['box']))
        if r is not None and listed:
            cut = list(r['cell'])
            for a in range(2):
                cut[2 * a], cut[2 * a + 1] = max(cut[2 * a], lo[a]), min(cut[2 * a + 1], hi[a])
            rec['boxCutToPiece'] += same_box(c['box'], cut)
        # inner edges (not the piece's own ends) on the level's tile grid, and on the piece's own grid
        if 'tx' in grid:
            for a, origin in ((0, grid['tx']), (1, grid['ty'])):
                for e in c['box'][2 * a:2 * a + 2]:
                    if abs(e - lo[a]) > 0.6 and abs(e - hi[a]) > 0.6:
                        rec['innerEdges'] += 1
                        rec['innerEdgesOnLevelGrid'] += on_grid(e, origin, tol=0.05)
                        rec['innerEdgesOnPieceGrid'] += on_grid(e, lo[a] - 1.0, tol=0.05)
            rec['zOnStoreyGrid'] += on_grid(c['box'][4], grid['tz'], STOREY, tol=0.05)
            rec['zOnPieceGrid'] += on_grid(c['box'][4], lo[2] - 1.0, STOREY, tol=0.05)
        if first is None and not ok:
            first = dict(index=k, saved=dict(box=[round(v, 2) for v in c['box']], frags=listed),
                         rule=dict(box=[round(v, 2) for v in r['box']], frags=r['frags']) if r else None)
            if len(saved) != len(rule):
                first['counts'] = dict(saved=len(saved), rule=len(rule), lo=[round(v, 2) for v in lo],
                                       hi=[round(v, 2) for v in hi],
                                       savedLast=[round(v, 2) for v in saved[-1]['box']])
    return rec, first, rule, lo, hi


# ---------------------------------------------------------------------------------------------------- the audit
class Audit:
    def __init__(self):
        self.meshes = {}                 # slab meshes by name
        self.left_out = {}               # named meshes that are not slabs, with why
        self.kind_of = {}                # every placed fracturing mesh's kind: slab kind, 'wall' or 'other'
        self.placed = []
        self.columns = defaultdict(Counter)       # by piece family: slab, wall, other
        self.column_firsts = defaultdict(list)
        self.flags = defaultdict(lambda: dict(n=0, actor=defaultdict(Counter), component=defaultdict(Counter)))
        self.destr = Counter()
        self.destr_samples = []
        self.near = Counter()
        self.near_samples = []
        self.materials = defaultdict(lambda: defaultdict(Counter))
        self.mesh_flags = defaultdict(lambda: dict(n=0, props=defaultdict(Counter)))
        self.mesh_seen = set()

    def family(self, mesh_name, size=None):
        """'slab', 'wall' (named for a wall, or at least 150 tall and at most 48 thick) or 'other'."""
        kind = self.kind_of.get(mesh_name)
        if kind in ('flat', 'thick', 'pitched'):
            return 'slab'
        if 'wall' in mesh_name.lower() or (size and size[2] >= 150 and min(size[:2]) <= 48):
            return 'wall'
        return 'other'

    def run_map(self, name, path, verbose=False):
        t0 = time.time()
        p = Package(path)
        level = p.by_name.get('TheWorld.PersistentLevel')
        ctx = map_context(p, level)
        props = None
        pieces = {}
        mesh_cache = {}
        for i in range(1, len(p.exports) + 1):
            if p.cls(i) not in FRACTURING or p.exports[i - 1]['outer'] != level:
                continue
            comp = p.effective(i, 'FracturedStaticMeshComponent')
            if not comp or comp < 0:
                continue
            mesh = p.effective(comp, 'StaticMesh')
            if not mesh or mesh < 0 or p.cls(mesh) != 'FracturedStaticMesh':
                continue
            key = p.name(mesh)
            if mesh not in mesh_cache:
                m = gen_mesh.read(p, mesh)
                tris, slots, tfrag = triangles_of(m)
                groups = defaultdict(set)
                for t, f in zip(tris, tfrag):
                    if f >= 0:
                        groups[int(f)].update(int(v) for v in t)
                mesh_cache[mesh] = (m, groups)
                if key not in self.kind_of:
                    named = bool(NAMED.search(key.rsplit('.', 1)[-1]))
                    size = [2 * v for v in m['bounds'][3:6]]
                    if named or (size[2] <= FLAT + 1 and min(size[:2]) >= WIDE):
                        rec, _ = mesh_record(p, mesh, m)
                        kind, why = classify(key, rec)
                        self.kind_of[key] = kind or ('wall' if 'wall' in key.lower() else 'other')
                        if kind:
                            rec.update(kind=kind, role='roof' if 'roof' in key.lower() else 'floor', placed=0,
                                       maps=Counter())
                            self.meshes[key] = rec
                        else:
                            self.left_out[key] = dict(size=rec['size'], why=why)
                    else:
                        self.kind_of[key] = 'wall' if 'wall' in key.lower() else 'other'
            m, groups = mesh_cache[mesh]
            if key not in self.mesh_seen:
                self.mesh_seen.add(key)
                fam = self.family(key, [2 * v for v in m['bounds'][3:6]])
                if fam == 'slab':
                    fam = self.meshes[key]['role'] + ' slab'
                self.mesh_flags[fam]['n'] += 1
                for k, v in saved_props(p, mesh).items():
                    if k not in ('BodySetup', 'LightMapResolution'):
                        self.mesh_flags[fam]['props'][k][str(v)] += 1
            try:
                world = lightmap_texels.world_matrix(p, comp)
            except ValueError:
                continue
            pos = np.array(m['lods'][0]['positions'], float)
            wpos = (np.c_[pos, np.ones(len(pos))] @ world.T)[:, :3]
            fbox = boxes_of(wpos, groups)
            if not fbox:
                continue
            pieces[i] = dict(key=key, comp=comp, fbox=fbox, family=self.family(key, [2 * v for v in m['bounds'][3:6]]),
                             cols=saved_columns(p, i) if p.own(i, 'FragmentColumns') is not None else [],
                             box=[min(b[0] for b in fbox.values()), max(b[1] for b in fbox.values()),
                                  min(b[2] for b in fbox.values()), max(b[3] for b in fbox.values()),
                                  min(b[4] for b in fbox.values()), max(b[5] for b in fbox.values())],
                             rotation=p.own(i, 'Rotation', [0, 0, 0]))
        # the columns of every piece (controls) and the flags of every family
        for i, pc in pieces.items():
            fam = pc['family']
            if fam == 'slab':
                fam = '%s %s' % (self.meshes[pc['key']]['role'], 'slab')
            flo = {f: b[4] for f, b in pc['fbox'].items()}
            if pc['cols']:
                pf = painted_fragments(p, pc['comp'], len(pc['fbox']))
                pc['hidden'] = set(pf['hidden']) if pf else set()
                rec, first, rule, lo, hi = column_test(pc['cols'], pc['fbox'], flo, ctx['grid'], pc['hidden'])
                pc['rule'] = rule
                self.columns[fam].update(rec)
                self.columns[fam]['pieces'] += 1
                self.columns[fam]['piecesAllRule'] += rec['closedVisibleBoth'] == rec['columns'] and rec['sameCount']
                if first and len(self.column_firsts[fam]) < 12:
                    self.column_firsts[fam].append(dict(map=name, actor=p.name(i).split('.')[-1], mesh=pc['key'],
                                                        **first))
                pc['test'] = rec
            fl = self.flags[fam]
            fl['n'] += 1
            for k, v in saved_props(p, i).items():
                fl['actor'][k][str(v)] += 1
            for k, v in saved_props(p, pc['comp']).items():
                fl['component'][k][str(v)] += 1
            fl['actor']['(archetype)'][str(bool(p.exports[i - 1]['arch']))] += 1
        # the slabs
        near = None
        for i, pc in pieces.items():
            if pc['family'] != 'slab':
                continue
            if props is None:
                props = props_boxes(p, level)
                ids = list(props)
                near = dict(propIds=ids, propBoxes=np.array([props[a]['box'] for a in ids], float).reshape(-1, 6))
                near['cutBoxes'], near['owners'] = cut_columns(pieces)
                near['statics'] = props_boxes(p, level, ('XComLevelActor', 'StaticMeshActor', 'XComDestructibleActor'))
            self.placed.append(self.slab_record(p, name, i, pc, pieces, ctx, props, near))
        if verbose:
            print('%-28s %5.1fs  slabs so far %d' % (name, time.time() - t0, len(self.placed)), flush=True)

    def slab_record(self, p, name, i, pc, pieces, ctx, props, near):
        key, comp = pc['key'], pc['comp']
        mrec = self.meshes[key]
        mrec['placed'] += 1
        mrec['maps'][name] += 1
        mats = p.refs(p.effective(comp, 'Materials')) if p.effective(comp, 'Materials') is not None else []
        for s, ref in enumerate(mats):
            self.materials[key][s][p.name(ref) if ref else None] += 1
        box = pc['box']
        grid = ctx['grid']
        rec = dict(map=name, actor=p.name(i).split('.')[-1], cls=p.cls(i), mesh=key, kind=mrec['kind'],
                   role=mrec['role'], location=[round(v, 2) for v in p.own(i, 'Location', [0, 0, 0])],
                   rotation=pc['rotation'], box=[round(v, 2) for v in box])
        if 'ox' in grid:
            rec['onPieceGrid'] = [on_grid(box[0], grid['ox']), on_grid(box[2], grid['oy'])]
            rec['topOverLevel'] = round(box[5] - grid['oz'], 2)
        cx, cy = (box[0] + box[1]) / 2, (box[2] + box[3]) / 2
        rec['cursorFloor'] = dict(top=cursor_floor(ctx, cx, cy, box[5] + 1), under=cursor_floor(ctx, cx, cy, box[4] - 1))
        rec['buildingFloors'] = [dict(c, buildingBox=[round(v) for v in c['buildingBox']] if c['buildingBox'] else None)
                                 for c in ctx['cached'].get(i, [])]
        # slabs over it: another slab whose footprint overlaps this one's by a tile or more, above its top
        over = []
        for j, q in pieces.items():
            if j == i or q['family'] != 'slab':
                continue
            b = q['box']
            ov = max(0.0, min(b[1], box[1]) - max(b[0], box[0])) * max(0.0, min(b[3], box[3]) - max(b[2], box[2]))
            if ov >= TILE * TILE and b[4] >= box[5] - 1:
                over.append((round(b[4] - box[5], 1), q['key'].rsplit('.', 1)[-1]))
        rec['slabsOver'] = sorted(over)[:3]
        rec['actorProps'] = saved_props(p, i)
        rec['componentProps'] = saved_props(p, comp)
        others = np.array([q['box'] for j, q in pieces.items() if j != i] +
                          [b['box'] for b in near['statics'].values()], float).reshape(-1, 6)
        rec['bakedTilesOnTop'] = floor_tiles(ctx, pc['fbox'], pc.get('hidden', set()), box[5], others)
        pf = painted_fragments(p, comp, len(pc['fbox']))
        if pf is not None:
            rec['paintedFragments'] = dict(saved=pf['saved'], hidden=len(pf['hidden']))
            hb = [pc['fbox'][f] for f in pf['hidden'] if f in pc['fbox']]
            if hb:
                region = [min(b[0] for b in hb), max(b[1] for b in hb), min(b[2] for b in hb), max(b[3] for b in hb)]
                area = sum((b[1] - b[0]) * (b[3] - b[2]) for b in hb)
                rec['paintedFragments'].update(
                    region=[round(v, 1) for v in region],
                    regionFilled=round(area / max((region[1] - region[0]) * (region[3] - region[2]), 1e-9), 3),
                    shareOfSlab=round(area / max(sum((b[1] - b[0]) * (b[3] - b[2]) for b in pc['fbox'].values()),
                                                 1e-9), 3))
        if 'test' in pc:
            t = pc['test']
            rec['columns'] = {k: int(t[k]) for k in ('columns', 'ruleColumns', 'closedVisibleBoth', 'closedVisibleBox',
                                                     'closedVisibleFrags', 'openBoth', 'closedBoth', 'empty',
                                                     'innerEdges', 'innerEdgesOnLevelGrid', 'innerEdgesOnPieceGrid')}
            rec['caches'] = self.caches(p, name, i, pc, pieces, props, near)
        return rec

    @staticmethod
    def where(qb, box):
        """Where the box `qb` lies against the slab's box: 'above', 'below', 'through' (from under it to over it) or
        'level' (within its height), and 'over' or 'off' its footprint."""
        if qb[4] >= box[4] - 1 and qb[5] > box[5] + 1:
            z = 'above'
        elif qb[5] <= box[5] + 1 and qb[4] < box[4] - 1:
            z = 'below'
        elif qb[4] < box[4] - 1 and qb[5] > box[5] + 1:
            z = 'through'
        else:
            z = 'level'
        inside = min(qb[1], box[1]) - max(qb[0], box[0]) > 1 and min(qb[3], box[3]) - max(qb[2], box[2]) > 1
        return z, 'over' if inside else 'off'

    def caches(self, p, name, i, pc, pieces, props, near):
        """The slab's columns' DestructibleCache and FracActorCache against the rules; adds to the tallies."""
        box = pc['box']
        out = Counter()
        prop_ids, prop_boxes = near['propIds'], near['propBoxes']
        cut_boxes, owners = near['cutBoxes'], near['owners']
        for k, c in enumerate(pc['cols']):
            # props: the rule (a prop whose box overlaps the column's box) and where each listed one stands
            listed = {a for a, _ in c['destr']}
            want = {prop_ids[n] for n in np.flatnonzero(box_hits(prop_boxes, c['box'], 0.0, strict=True))}
            out['destrColumns'] += 1
            out['destrRule'] += listed == want
            out['destrListed'] += len(listed)
            out['destrMissed'] += len(want - listed)
            out['destrAdded'] += len(listed - want)
            for a, z in c['destr']:
                pr = props.get(a)
                if pr is None:
                    where = 'unread (%s)' % (p.cls(a) if a > 0 else 'import')
                else:
                    b = pr['box']
                    zw, fw = self.where(b, box)
                    where = '%s, %s the slab' % (zw, fw)
                    self.destr['in the column\'s box'] += overlaps(b, c['box'])
                    self.destr['minZ within 1 of the prop\'s bounds bottom'] += abs(z - b[4]) <= 1.0
                    self.destr['minZ within 1 of the prop\'s location z'] += abs(z - p.own(a, 'Location', [0, 0, 0])[2]) <= 1
                    gap = max(0.0, b[0] - c['box'][1], c['box'][0] - b[1], b[2] - c['box'][3], c['box'][2] - b[3])
                    self.destr['xy gap to the column\'s box: %s' % ('0' if gap <= 0 else '<=96' if gap <= 96 else
                                                                      '<=192' if gap <= 192 else '>192')] += 1
                self.destr['listed'] += 1
                self.destr[where] += 1
                self.destr['class ' + (pr['cls'] if pr else p.cls(a) if a > 0 else 'import')] += 1
                if len(self.destr_samples) < 40 and pr:
                    self.destr_samples.append(dict(map=name, slab=p.name(i).split('.')[-1], column=k,
                                                   prop=p.name(a).split('.')[-1], mesh=pr['mesh'], where=where,
                                                   minZ=round(z, 2), propZ=[round(pr['box'][4], 1), round(pr['box'][5], 1)],
                                                   slabZ=[round(box[4], 1), round(box[5], 1)]))
            # neighbours: frac-neighbours.md's rule
            got = set(c['near'])
            hit = box_hits(cut_boxes, c['box'], -TOL, strict=False) & (owners[:, 0] != i)
            want = {(int(a), int(n)) for a, n in owners[hit]}
            out['nearColumns'] += 1
            out['nearRule'] += got == want
            out['nearListed'] += len(got)
            out['nearMissed'] += len(want - got)
            out['nearAdded'] += len(got - want)
            out['nearSelf'] += sum(1 for a, _ in got if a == i)
            for a, n in want - got:
                q = pieces[a]
                self.near['rule only: %s %s' % (q['family'], ' '.join(self.where(q['box'], box)))] += 1
            for a, n in got:
                q = pieces.get(a)
                if q is None:
                    self.near['listed: unread %s' % (p.cls(a) if a > 0 else 'import' if a else 'None')] += 1
                    continue
                where = ' '.join(self.where(q['box'], box))
                self.near['listed: %s %s' % (q['family'], where)] += 1
                if len(self.near_samples) < 30 and q['family'] != 'slab':
                    self.near_samples.append(dict(map=name, slab=p.name(i).split('.')[-1], column=k,
                                                  piece=p.name(a).split('.')[-1], mesh=q['key'], where=where,
                                                  columnIndex=n))
        return dict(out)

    def class_defaults(self, folder):
        path = Path(folder) / 'XComGame.upk'
        if not path.exists():
            return None
        q = Package(path)
        out = {}
        for cls in FRACTURING:
            d = q.by_name.get('Default__%s' % cls)
            if not d:
                continue
            rec = dict(actor={k: str(v) for k, v in saved_props(q, d).items()})
            for child in q.children.get(d, []):
                if q.cls(child) == 'FracturedStaticMeshComponent':
                    rec['component'] = {k: str(v) for k, v in saved_props(q, child).items()}
                    rec['componentName'] = q.name(child)
            out[cls] = rec
        return out


def summary(a):
    kinds = Counter((r['kind'], r['role']) for r in a.meshes.values())
    placed = Counter((r['kind'], r['role']) for r in a.placed)
    thick = Counter(r['thickness'] for r in a.meshes.values())
    cols = {fam: {k: int(v) for k, v in c.items()} for fam, c in a.columns.items()}
    caches = Counter()
    for r in a.placed:
        caches.update(r.get('caches', {}))
    roles = defaultdict(Counter)
    for r in a.placed:
        top = [c for c in r['buildingFloors']]
        roles[r['role']]['placed'] += 1
        roles[r['role']]['in a building floor list'] += bool(top)
        roles[r['role']]['in its building\'s top floor'] += any(c['floor'] == c['floors'] for c in top)
        roles[r['role']]['with a CutdownFloor'] += any(c['cutdownFloor'] for c in top)
        roles[r['role']]['slab over it'] += bool(r['slabsOver'])
        roles[r['role']]['bPathColliding'] += bool(r['actorProps'].get('bPathColliding'))
        roles[r['role']]['bCanStepUpOn'] += bool(r['actorProps'].get('bCanStepUpOn'))
        roles[r['role']]['bIgnoreFor3DCursorCollision'] += bool(r['actorProps'].get('bIgnoreFor3DCursorCollision'))
        roles[r['role']]['bCutoutMask'] += bool(r['componentProps'].get('bCutoutMask'))
        roles[r['role']]['some fragments hidden'] += bool(r.get('paintedFragments', {}).get('hidden'))
    tiles = defaultdict(Counter)
    for r in a.placed:
        for kind, c in (r.get('bakedTilesOnTop') or {}).items():
            tiles['%s, over %s fragments' % (r['role'], kind)].update(c)
    holes = [(k, h) for k, r in a.meshes.items() for h in r.get('holes', [])]
    return dict(
        slabMeshes=len(a.meshes), byKindAndRole={'%s %s' % k: v for k, v in kinds.items()},
        placedSlabs=len(a.placed), placedByKindAndRole={'%s %s' % k: v for k, v in placed.items()},
        thicknesses=dict(sorted(thick.items())), leftOut=len(a.left_out),
        slotsLayout=dict(Counter(' | '.join('%d:%s' % (s['slot'], s['faces']) for s in r['sections'])
                                 for r in a.meshes.values()).most_common(12)),
        fragmentRectangles=[sum(r['fragments']['rectangles'] for r in a.meshes.values()),
                            sum(r['fragments']['withTriangles'] for r in a.meshes.values())],
        fragmentsOnOwnGrid=sum(r['fragments']['onOwn96Grid'] for r in a.meshes.values()),
        fragmentsThroughThickness=sum(r['fragments']['throughThickness'] for r in a.meshes.values()),
        fragmentsOfWholeTiles=sum(r['fragments']['wholeTiles'] for r in a.meshes.values()),
        topVerticesOn96Grid=[sum(r.get('topVerticesOn96Grid', [0, 0])[k] for r in a.meshes.values()) for k in range(2)],
        topTriangleEdges=dict(sum((Counter(r.get('topTriangleEdges', {})) for r in a.meshes.values()),
                                  Counter()).most_common(6)),
        collisionTopUnderDrawnTop=dict(Counter(round(r['collision']['meshTop'] - r['collision']['top'], 1)
                                               for r in a.meshes.values()
                                               if r['collision'].get('top') is not None).most_common(8)),
        collisionElements=dict(Counter(r['collision'].get('elements') for r in a.meshes.values()).most_common(8)),
        meshPropsSaved=dict(Counter(k for r in a.meshes.values() for k in r['meshProps']).most_common(12)),
        holes=dict(meshes=len({k for k, _ in holes}), holes=len(holes),
                   rectangles=int(sum(h['rectangle'] >= 0.95 for _, h in holes)),
                   onGrid=int(sum(bool(h['onGrid']) for _, h in holes)),
                   byMesh={k.rsplit('.', 1)[-1]: sum(1 for m, _ in holes if m == k) for k in {m for m, _ in holes}}),
        roles={k: dict(v) for k, v in roles.items()}, bakedTilesOnTop={k: dict(v) for k, v in tiles.items()},
        columns=cols, caches=dict(caches), destructibles=dict(a.destr), neighbours=dict(a.near))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--maps', nargs='*', help='map names (default: every map the install lists)')
    ap.add_argument('--output', type=Path)
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()
    import library
    import settings
    game, _ = settings.game_install(settings.load_settings())
    maps = [(n, Path(path)) for n, _, path in library.donors(game)]
    if args.maps:
        want = {m.casefold() for m in args.maps}
        maps = [(n, path) for n, path in maps if n.casefold() in want]
    a = Audit()
    for name, path in maps:
        a.run_map(name, path, args.verbose)
    defaults = a.class_defaults(maps[0][1].parent) if maps else None
    meshes = {}
    for k, r in sorted(a.meshes.items()):
        r = dict(r, maps=dict(r['maps']))
        for s in r['sections']:
            s['materials'] = dict(a.materials[k][s['slot']].most_common(4))
        meshes[k] = r
    flags = {fam: dict(n=f['n'], actor={k: dict(v) for k, v in sorted(f['actor'].items())},
                       component={k: dict(v) for k, v in sorted(f['component'].items())},
                       meshes=a.mesh_flags[fam]['n'],
                       mesh={k: dict(v) for k, v in sorted(a.mesh_flags[fam]['props'].items())})
             for fam, f in sorted(a.flags.items())}
    result = dict(scope='Read-only: the install\'s maps (%d), their placed fracturing pieces; nothing written to the '
                        'game' % len(maps),
                  summary=summary(a), classDefaults=defaults, flags=flags, meshes=meshes,
                  leftOut=dict(sorted(a.left_out.items())), placed=a.placed,
                  columnDifferences={k: v for k, v in a.column_firsts.items()},
                  destructibleSamples=a.destr_samples, neighbourSamples=a.near_samples)
    print(json.dumps(result['summary'], indent=1, default=str))
    if args.output:
        args.output.write_text(json.dumps(result, indent=1, default=str) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
