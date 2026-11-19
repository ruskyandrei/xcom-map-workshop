"""Read-only audit of how the game's fracturing walls meet, and of what their fragment columns list of each other,
for joined made walls (private/plans/done/custom-geometry-implementation-plan.md, stage M3, item 1; F-69, F-116).

Over every map the install lists (tools/viewer/library.py donors), or the maps named with --maps, it reads each placed
fracturing piece (XComDecoFracLevelActor, XComFracLevelActor) of the persistent level: its mesh's fragments in world
space (their vertices, as frac-wall-audit.py reads them) and its FragmentColumns (each column's Bounds, FragCache and
FracActorCache).

  grid        each column's box against two grids: the level's tile grid (the corner the game counts its tiles
              from, native_copy.level_grid's tx, ty, tz) and the piece's own grid (its vertices' lowest corner less
              one unit), 96 x 96 x 192
  lists       each column's FracActorCache against the rule: column X of piece A lists column n of piece B when X's
              box touches or overlaps B_n's box cut to B's own bounds grown by one unit (closed boxes, so touching
              counts). The misses are grouped by the piece they name or come from
  runs        each piece's columns stacked into plan cells (the piece's own 96 grid), each cell thin along x, thin
              along y, a corner, a post or a block (thick: a pillar, a floor); cells of one way chained into straight
              runs (along, across centre, half thickness, heights). A run is a wall when it stands at least 150 tall,
              low (a parapet, a fence, a counter) otherwise
  joints      each wall run's end against the other runs (of any piece, its own included): an L (the other run's end
              meets it at right angles), a T (its end on the other's line inside its span: the other runs through),
              an end-to-end joint in line, an end on a block (a pillar), or free. Per joint:
              - how far each wall's solid goes past the other's centre line (the box's end, with trims; and the
                core's, from the vertices within 6 units of the wall's centre line, at mid height), and where the
                centre lines and ends lie against the piece grid (the level box's corner, ox and oy) and the game's
                tile edges (a unit under it);
              - an end's shape: the ends of its two faces (a square end has them equal, a mitre differs by about its
                thickness);
              - at an L: what fills the corner square (both walls' thickness bands crossed): the two walls, one, or
                another piece (a corner column);
              - between two pieces: which columns of each list which of the other's, how many tiles from the joint
                and storeys apart, mutual or one way, and whether the rule above gives exactly those listings.

Prints a summary; --output writes the JSON (summaries, the joints by class and kit, and a sample of joints of each
class). No game file is written.

  python -B research/evidence/wall-joints.py [--maps URB_Bar URB_PoliceStation] [--output <file.json>] [--verbose]
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
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
THIN = 48.0          # a cell this thin or thinner across is a wall's
WALL_HEIGHT = 150.0  # a run at least this tall is a wall, else low
NEAR = 24.0          # an end this close to another run's line (past its half thickness) meets it
CORE = 6.0           # the core band: vertices this close to a run's centre line
GROW = 1.0           # the list rule's growth of the other piece's bounds
SAMPLES = 6          # joints kept per class and kit in the JSON


# --------------------------------------------------------------------------------------------- reading the map
def columns_of(p, actor):
    """[dict(box [x0, x1, y0, y1, z0, z1], frags, nb [(actor export, column index)])] of a piece's FragmentColumns."""
    out = []
    for c in p.structs(p.own(actor, 'FragmentColumns')):
        b = struct.unpack('<6fB', c[('Bounds', 0)]['value'])
        frags = [it.get(('FragIndex', 0), {}).get('value', 0)
                 for it in p.structs(c.get(('FragCache', 0), {}).get('value'))]
        nb = [(e[('FracActor', 0)]['value'], e.get(('ColumnIndex', 0), {}).get('value', 0))
              for e in p.structs(c.get(('FracActorCache', 0), {}).get('value'))]
        out.append(dict(box=[b[0], b[3], b[1], b[4], b[2], b[5]], frags=frags, nb=nb))
    return out


def read_pieces(p):
    """{export: piece} for the persistent level's fracturing pieces: name, mesh, kit (the mesh's package), cols, and
    for a piece with a fracturing mesh its world vertices (verts), fragment vertex lists (fragVerts), fragment world
    boxes (fboxes) and its bounds (abox)."""
    level = p.by_name.get('TheWorld.PersistentLevel')
    pieces = {}
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) not in FRACTURING or p.exports[i - 1]['outer'] != level:
            continue
        piece = dict(name=p.name(i).split('.')[-1], cls=p.cls(i), mesh=None, kit=None, cols=columns_of(p, i), tris=None,
                     verts=None, fragVerts={}, fboxes={}, abox=None)
        pieces[i] = piece
        comp = p.own(i, 'FracturedStaticMeshComponent')
        if not comp or comp < 0:
            continue
        mesh = p.own(comp, 'StaticMesh')
        if not mesh or mesh < 0 or p.cls(mesh) != 'FracturedStaticMesh':
            continue
        try:
            m = gen_mesh.read(p, mesh)
        except gen_mesh.MeshError:
            continue
        full = p.name(mesh)
        piece['mesh'] = full.split('.')[-1]
        piece['kit'] = full.split('.')[0]
        world = lightmap_texels.world_matrix(p, comp)
        lod = m['lods'][0]
        pos = np.array(lod['positions'], float)
        w = (np.c_[pos, np.ones(len(pos))] @ world.T)[:, :3]
        idx = lod['indices'][1]
        per = defaultdict(set)
        for s in lod['sections']:
            for f, (first, count) in enumerate(s['fragments']):
                for t in range(first // 3, first // 3 + count):
                    per[f].update(idx[3 * t:3 * t + 3])
        piece['verts'] = w
        piece['tris'] = np.array(idx, dtype=np.int64).reshape(-1, 3)
        for f, vs in per.items():
            vs = np.array(sorted(vs))
            piece['fragVerts'][f] = vs
            pts = w[vs]
            piece['fboxes'][f] = [float(v) for k in range(3) for v in (pts[:, k].min(), pts[:, k].max())]
        if per:
            used = np.array(sorted(set().union(*per.values())))
            pts = w[used]
            piece['abox'] = [float(v) for k in range(3) for v in (pts[:, k].min(), pts[:, k].max())]
    return pieces


def level_grid(p):
    try:
        import native_copy
        return native_copy.level_grid(p)
    except Exception:       # no single level volume: no grid
        return None


# --------------------------------------------------------------------------------------------- column grid
def fold(v, period):
    """v folded into [-period/2, period/2)."""
    return float((v + period / 2) % period - period / 2)


def grid_record(pieces, grid, tally):
    """Counts each column boundary inside a piece's span (a column side that isn't the piece's own end) as lying on
    the piece's own grid (its bounds' low corner less one unit), on the level's tile grid, or on neither."""
    for piece in pieces.values():
        if piece['abox'] is None:
            continue
        own = [piece['abox'][0] - 1, piece['abox'][2] - 1, piece['abox'][4] - 1]
        lev = [grid['tx'], grid['ty'], grid['tz']] if grid else None
        for c in piece['cols']:
            for k in range(3):
                period = STOREY if k == 2 else TILE
                if c['box'][2 * k + 1] - c['box'][2 * k] < 40:
                    continue            # across a wall: the column's sides are its fragments', not a grid's
                for v in (c['box'][2 * k], c['box'][2 * k + 1]):
                    if abs(v - piece['abox'][2 * k]) < 0.05 or abs(v - piece['abox'][2 * k + 1]) < 0.05:
                        continue        # the piece's own end: the column is cut there
                    a = abs(fold(v - own[k], period)) < 0.05
                    b = lev is not None and abs(fold(v - lev[k], period)) < 0.05
                    tally['xyz'[k], 'own' if a else '', 'level' if b else ''] += 1


# --------------------------------------------------------------------------------------------- list rule
def rule_lists(pieces):
    """{(piece, column): set of (piece, column)} by the rule: X lists B_n when X's box touches B_n's box cut to B's
    bounds grown by GROW. Pieces without a mesh keep their columns' boxes uncut."""
    keys, boxes, cut, owner = [], [], [], []
    for i, piece in pieces.items():
        for k, c in enumerate(piece['cols']):
            keys.append((i, k))
            b = np.array(c['box'], float)
            boxes.append(b)
            if piece['abox'] is not None:
                g = np.array(piece['abox'], float) + np.array([-GROW, GROW] * 3)
                b = np.array([max(b[0], g[0]), min(b[1], g[1]), max(b[2], g[2]), min(b[3], g[3]),
                              max(b[4], g[4]), min(b[5], g[5])])
            cut.append(b)
            owner.append(i)
    if not keys:
        return {}
    boxes, cut, owner = np.array(boxes), np.array(cut), np.array(owner)
    out = {}
    for n, key in enumerate(keys):
        x = boxes[n]
        gap = np.max(np.stack([np.maximum(x[0], cut[:, 0]) - np.minimum(x[1], cut[:, 1]),
                               np.maximum(x[2], cut[:, 2]) - np.minimum(x[3], cut[:, 3]),
                               np.maximum(x[4], cut[:, 4]) - np.minimum(x[5], cut[:, 5])]), axis=0)
        hit = np.nonzero((gap <= 0) & (owner != key[0]))[0]
        out[key] = {keys[h] for h in hit}
    return out


def list_record(pieces, predicted, tally, misses):
    """Counts the columns whose lists the rule gives exactly, the listings it misses or adds (in `misses` by the
    pieces concerned), and the listings that are mutual."""
    listed_all = {(i, k): {(a, n) for a, n in c['nb']} for i, piece in pieces.items()
                  for k, c in enumerate(piece['cols'])}
    for (i, k), listed in listed_all.items():
        pred = predicted.get((i, k), set())
        tally['columns'] += 1
        tally['listings'] += len(listed)
        tally['columns exact'] += listed == pred
        tally['listed, not by the rule'] += len(listed - pred)
        tally['by the rule, not listed'] += len(pred - listed)
        name = pieces[i]['name']
        for a, n in listed - pred:
            misses[name + ' lists ' + pieces.get(a, {}).get('name', str(a))] += 1
        for a, n in pred - listed:
            misses[name + ' omits ' + pieces.get(a, {}).get('name', str(a))] += 1
        tally['listings mutual'] += sum(1 for a, n in listed if (i, k) in listed_all.get((a, n), ()))
        tally['listings naming no column'] += sum(1 for a, n in listed if (a, n) not in listed_all)


# --------------------------------------------------------------------------------------------- runs
def plan_cells(piece):
    """The piece's columns stacked into plan cells of its own grid: {(ix, iy): dict(box, z, cols)}."""
    gx, gy = piece['abox'][0] - 1, piece['abox'][2] - 1
    cells = {}
    for k, c in enumerate(piece['cols']):
        b = c['box']
        if b[1] - b[0] < 4 or b[3] - b[2] < 4:
            continue        # a sliver column (a piece 12 tiles long has a 13th column a unit long)
        key = (int(np.floor(((b[0] + b[1]) / 2 - gx) / TILE)), int(np.floor(((b[2] + b[3]) / 2 - gy) / TILE)))
        cell = cells.setdefault(key, dict(box=list(b[:4]), z=[b[4], b[5]], cols=[]))
        cell['box'] = [min(cell['box'][0], b[0]), max(cell['box'][1], b[1]),
                       min(cell['box'][2], b[2]), max(cell['box'][3], b[3])]
        cell['z'] = [min(cell['z'][0], b[4]), max(cell['z'][1], b[5])]
        cell['cols'].append(k)
    # the cells' true heights: their fragments' (a column's box is a whole storey)
    for cell in cells.values():
        zs = [z for k in cell['cols'] for f in piece['cols'][k]['frags'] if f in piece['fboxes']
              for z in piece['fboxes'][f][4:6]]
        if zs:
            cell['z'] = [max(cell['z'][0], min(zs)), min(cell['z'][1], max(zs))]
    return cells


def label_cells(cells):
    for cell in cells.values():
        dx, dy = cell['box'][1] - cell['box'][0], cell['box'][3] - cell['box'][2]
        if dy <= THIN and dx >= 1.5 * dy:
            cell['way'] = 'x'
        elif dx <= THIN and dy >= 1.5 * dx:
            cell['way'] = 'y'
        elif max(dx, dy) <= THIN:
            cell['way'] = '?'
        else:
            cell['way'] = 'block'
    for (ix, iy), cell in cells.items():
        if cell['way'] != '?':
            continue
        xs = [cells[n] for n in ((ix - 1, iy), (ix + 1, iy)) if n in cells and cells[n]['way'] == 'x']
        ys = [cells[n] for n in ((ix, iy - 1), (ix, iy + 1)) if n in cells and cells[n]['way'] == 'y']
        cell['way'] = 'corner' if xs and ys else 'x' if xs else 'y' if ys else 'post'


def runs_of(i, piece):
    """The piece's straight runs: [dict(piece, axis 0 (along x) or 1, along [a0, a1], centre, half, z, cells)]."""
    cells = plan_cells(piece)
    label_cells(cells)
    runs, blocks = [], []
    for axis, way in ((0, 'x'), (1, 'y')):
        members = {k: c for k, c in cells.items() if c['way'] in (way, 'corner')}
        seen = set()
        for key in sorted(members, key=lambda k: (k[1 - axis], k[axis])):
            if key in seen or members[key]['way'] == 'corner':
                continue
            chain, k = [key], key
            seen.add(key)
            for step in (-1, 1):
                k = key
                while True:
                    n = (k[0] + step, k[1]) if axis == 0 else (k[0], k[1] + step)
                    if n not in members or n in seen:
                        break
                    seen.add(n)
                    chain.append(n)
                    k = n
                    if members[n]['way'] == 'corner':
                        break
            boxes = [members[c]['box'] for c in chain]
            a0 = min(b[2 * axis] for b in boxes)
            a1 = max(b[2 * axis + 1] for b in boxes)
            thin = [members[c] for c in chain if members[c]['way'] != 'corner']
            centre = float(np.median([(c['box'][2 * (1 - axis)] + c['box'][2 * (1 - axis) + 1]) / 2 for c in thin]))
            half = float(np.median([(c['box'][2 * (1 - axis) + 1] - c['box'][2 * (1 - axis)]) / 2 for c in thin]))
            z = [min(members[c]['z'][0] for c in chain), max(members[c]['z'][1] for c in chain)]
            runs.append(dict(piece=i, axis=axis, along=[a0, a1], centre=centre, half=half, z=z,
                             cells=[members[c] for c in chain],
                             corners=sum(1 for c in chain if members[c]['way'] == 'corner'),
                             kind='wall' if z[1] - z[0] >= WALL_HEIGHT else 'low'))
    for c in cells.values():
        if c['way'] in ('block', 'post') and c['z'][1] - c['z'][0] >= WALL_HEIGHT:
            blocks.append(dict(piece=i, box=c['box'], z=c['z'], way=c['way']))
    return runs, blocks


# --------------------------------------------------------------------------------------------- measuring
def clip_polygon(poly, k, limit, keep_below):
    """Sutherland-Hodgman: the polygon (list of 3-vectors) cut by the plane coordinate k = limit, keeping the side
    below it (keep_below) or above."""
    out = []
    n = len(poly)
    for m in range(n):
        p0, p1 = poly[m], poly[(m + 1) % n]
        in0 = p0[k] <= limit if keep_below else p0[k] >= limit
        in1 = p1[k] <= limit if keep_below else p1[k] >= limit
        if in0:
            out.append(p0)
        if in0 != in1:
            t = (limit - p0[k]) / (p1[k] - p0[k])
            out.append(p0 + t * (p1 - p0))
    return out


def band_extreme(piece, axis, centre, lo, hi, end, sign, z):
    """The farthest along coordinate, toward `sign`, of the piece's surface (its triangles, cut) whose across offset
    from `centre` lies in [lo, hi] and whose height lies in the band `z`, among the triangles within 72 units of
    `end`; None when none."""
    w = piece['verts']
    if w is None:
        return None
    tri = w[piece['tris']]                              # t x 3 x 3
    a = tri[:, :, axis]
    q = tri[:, :, 1 - axis] - centre
    zz = tri[:, :, 2]
    sel = ((q.max(1) >= lo) & (q.min(1) <= hi) & (zz.max(1) >= z[0]) & (zz.min(1) <= z[1])
           & (np.abs(a - end).min(1) <= 72))
    best = None
    across = 1 - axis
    for t in np.nonzero(sel)[0]:
        poly = [tri[t, 0].copy(), tri[t, 1].copy(), tri[t, 2].copy()]
        for k, limit, below in ((across, centre + hi, True), (across, centre + lo, False), (2, z[1], True),
                                (2, z[0], False)):
            poly = clip_polygon(poly, k, limit, below)
            if not poly:
                break
        if not poly:
            continue
        v = max(pt[axis] for pt in poly) if sign > 0 else min(pt[axis] for pt in poly)
        if best is None or (v > best if sign > 0 else v < best):
            best = v
    return None if best is None else float(best)


def mid_band(z0, z1):
    """Heights clear of base and crown trims: the middle of the shared span."""
    lo, hi = z0 + 24, z1 - 24
    return (lo, hi) if hi > lo else (z0, z1)


def end_record(pieces, run, end, other_line, zb):
    """One run end measured against the line it meets: the box end and core end, each as how far past the other's
    centre line (positive: beyond it, away from the run's body), and the end's two faces."""
    sign = 1 if end == 1 else -1
    a = run['along'][end]
    piece = pieces[run['piece']]
    core = band_extreme(piece, run['axis'], run['centre'], -CORE, CORE, a, sign, zb)
    h = run['half']
    # the end's profile: how far it goes at each face and at the centre line (thin bands), past the other's line
    prof = [band_extreme(piece, run['axis'], run['centre'], lo, hi, a, sign, zb)
            for lo, hi in ((-h + 0.5, -h + 2.5), (-1.0, 1.0), (h - 2.5, h - 0.5))]
    prof = [None if v is None else round(sign * (v - other_line), 2) for v in prof]
    shape = None
    if prof[0] is not None and prof[2] is not None:
        slope = (prof[2] - prof[0]) / max(2 * h - 3, 1.0)
        shape = 'square' if abs(slope) < 0.15 else 'mitre' if abs(slope) > 0.6 else 'step'
    rec = dict(boxPast=round(sign * (a - other_line), 2),
               corePast=None if core is None else round(sign * (core - other_line), 2),
               profile=prof, shape=shape)
    return rec


def reach(past, half):
    """How far an end goes against the other wall (its box past the other's centre line, the other's half
    thickness with trims): to its far face, into it, to its centre line, to its near face, or short of it."""
    if past is None:
        return None
    if past >= half - 3:
        return 'far face'
    if abs(past) <= 3:
        return 'centre line'
    if past > 3:
        return 'past the centre line'
    if past >= -half - 1:
        return 'near face' if past <= -6 else 'into it'
    return 'short of it'


def grid_offset(v, origin):
    return round(fold(v - origin, TILE), 2)


def corner_fill(pieces, square, z, names):
    """The pieces whose fragments fill the corner square (plan box [x0, x1, y0, y1]) at heights z: their names, each
    with the share of the square its fragments' boxes cover (the largest single fragment's)."""
    out = {}
    area = max((square[1] - square[0]) * (square[3] - square[2]), 1e-6)
    for i, piece in pieces.items():
        best = 0.0
        for f, b in piece['fboxes'].items():
            if min(b[5], z[1]) - max(b[4], z[0]) <= 8:
                continue
            ox = min(b[1], square[1]) - max(b[0], square[0])
            oy = min(b[3], square[3]) - max(b[2], square[2])
            if ox > 1 and oy > 1:
                best = max(best, ox * oy / area)
        if best > 0.05:
            out[names.get(i, piece['mesh'] or piece['name'])] = round(best, 2)
    return out


def column_links(pieces, a, b, point, predicted):
    """The listings between piece a's and piece b's columns, both ways: each as (tiles from the joint along the
    listing column, tiles from the joint along the listed one, storeys apart), and whether the rule gives them."""
    def tiles(box):
        dx = max(box[0] - point[0], point[0] - box[1], 0.0)
        dy = max(box[2] - point[1], point[1] - box[3], 0.0)
        return int(np.ceil(max(dx, dy) / TILE - 1e-6))

    out = dict(ab=[], ba=[], ruleExact=True)
    for src, dst, key in ((a, b, 'ab'), (b, a, 'ba')):
        for k, c in enumerate(pieces[src]['cols']):
            listed = {(x, n) for x, n in c['nb'] if x == dst}
            pred = {(x, n) for x, n in predicted.get((src, k), set()) if x == dst}
            if listed != pred:
                out['ruleExact'] = False
            for x, n in sorted(listed):
                if n >= len(pieces[dst]['cols']):
                    continue
                d = pieces[dst]['cols'][n]['box']
                out[key].append((tiles(c['box']), tiles(d), int(round(((d[4] + d[5]) - (c['box'][4] + c['box'][5]))
                                                                       / 2 / STOREY))))
    pairs_ab = {(k, n) for k, c in enumerate(pieces[a]['cols']) for x, n in c['nb'] if x == b}
    pairs_ba = {(n, k) for k, c in enumerate(pieces[b]['cols']) for x, n in c['nb'] if x == a}
    out['mutual'] = len(pairs_ab & pairs_ba)
    out['oneWay'] = len(pairs_ab ^ pairs_ba)
    return out


# --------------------------------------------------------------------------------------------- joints
def find_joints(pieces, runs, blocks, grid):
    """Each wall run end classified (see the docstring); returns [joint dict]."""
    ox, oy = (grid['ox'], grid['oy']) if grid else (0.0, 0.0)
    joints = []
    taken = set()
    for r_i, r in enumerate(runs):
        if r['kind'] != 'wall':
            continue
        for end in (0, 1):
            a = r['along'][end]
            sign = 1 if end == 1 else -1
            best = None
            for s_i, s in enumerate(runs):
                if s_i == r_i or s['kind'] != 'wall':
                    continue
                zo = min(r['z'][1], s['z'][1]) - max(r['z'][0], s['z'][0])
                if zo < 32:
                    continue
                if s['axis'] != r['axis']:
                    # the end on s's line?
                    d_line = sign * (a - s['centre'])          # past s's centre line
                    if not -(s['half'] + NEAR) <= d_line <= s['half'] + NEAR:
                        continue
                    if not s['along'][0] - NEAR <= r['centre'] <= s['along'][1] + NEAR:
                        continue
                    if r['along'][0] + NEAR < s['centre'] < r['along'][1] - NEAR:
                        continue     # s's line crosses r inside its span: not this end's
                    to_end = min(abs(r['centre'] - s['along'][0]), abs(r['centre'] - s['along'][1]))
                    kind = 'L' if to_end <= r['half'] + NEAR else 'T'
                    score = abs(d_line)
                elif abs(s['centre'] - r['centre']) <= 6:
                    other = s['along'][1 - end]
                    gap = sign * (other - a)                # gap between the ends (negative: overlap)
                    if not -NEAR <= gap <= NEAR or (sign > 0 and s['along'][1] < a) or (sign < 0 and s['along'][0] > a):
                        continue
                    kind, score = 'inline', abs(gap)
                else:
                    continue
                if best is None or score < best[0] or (score == best[0] and kind == 'L'):
                    best = (score, kind, s_i)
            point = (a, r['centre']) if r['axis'] == 0 else (r['centre'], a)
            if best is None:
                hit = None
                for b in blocks:
                    if min(b['z'][1], r['z'][1]) - max(b['z'][0], r['z'][0]) < 32:
                        continue
                    if b['box'][0] - 6 <= point[0] <= b['box'][1] + 6 and b['box'][2] - 6 <= point[1] <= b['box'][3] + 6:
                        hit = b
                        break
                joints.append(dict(kind='block' if hit else 'free', r=r_i, end=end, point=point,
                                   block=None if hit is None else hit['piece']))
                continue
            _, kind, s_i = best
            key = (min(r_i, s_i), max(r_i, s_i), kind) if kind in ('L', 'inline') else None
            if key is not None and key in taken:
                continue
            if key is not None:
                taken.add(key)
            joints.append(dict(kind=kind, r=r_i, end=end, s=s_i, point=point))
    return joints


def describe(pieces, runs, j, grid, predicted):
    """A joint's numbers (see the docstring)."""
    ox, oy, tx, ty = (grid['ox'], grid['oy'], grid['tx'], grid['ty']) if grid else (0.0, 0.0, -1.0, -1.0)
    r = runs[j['r']]
    pr = pieces[r['piece']]
    origin_along = (ox, oy)[r['axis']]
    origin_across = (oy, ox)[r['axis']]
    out = dict(kind=j['kind'], map=None,
               r=dict(piece=pr['name'], mesh=pr['mesh'], kit=pr['kit'], axis='xy'[r['axis']],
                      centreOffGrid=grid_offset(r['centre'], origin_across), half=round(r['half'], 2),
                      end=round(r['along'][j['end']], 2), endOffGrid=grid_offset(r['along'][j['end']], origin_along),
                      endOffTileEdge=grid_offset(r['along'][j['end']], origin_along - 1),
                      height=[round(v, 1) for v in r['z']]))
    if j['kind'] in ('free', 'block'):
        zb = mid_band(*r['z'])
        sign = 1 if j['end'] == 1 else -1
        core = band_extreme(pr, r['axis'], r['centre'], -CORE, CORE, r['along'][j['end']], sign, zb)
        out['r']['coreEndOffGrid'] = None if core is None else grid_offset(core, origin_along)
        if j['kind'] == 'block':
            out['block'] = dict(piece=pieces[j['block']]['name'], mesh=pieces[j['block']]['mesh'])
        return out
    s = runs[j['s']]
    ps = pieces[s['piece']]
    z = [max(r['z'][0], s['z'][0]), min(r['z'][1], s['z'][1])]
    zb = mid_band(*z)
    out['samePiece'] = r['piece'] == s['piece']
    out['s'] = dict(piece=ps['name'], mesh=ps['mesh'], kit=ps['kit'], axis='xy'[s['axis']],
                    centreOffGrid=grid_offset(s['centre'], (oy, ox)[s['axis']]), half=round(s['half'], 2),
                    height=[round(v, 1) for v in s['z']])
    if j['kind'] != 'inline':
        out['r'].update(end_record(pieces, r, j['end'], s['centre'], zb))
        out['r']['reach'] = reach(out['r']['boxPast'], s['half'])
    if j['kind'] == 'L':
        s_end = 0 if abs(r['centre'] - s['along'][0]) <= abs(r['centre'] - s['along'][1]) else 1
        out['s'].update(end_record(pieces, s, s_end, r['centre'], zb))
        # profiles as (outer face, centre line, inner face): the inner face is on the other wall's side
        for me, other in ((out['r'], s), (out['s'], r)):
            run = r if me is out['r'] else s
            inner_positive = (other['along'][0] + other['along'][1]) / 2 > run['centre']
            if me.get('profile'):
                me['profile'] = me['profile'] if inner_positive else me['profile'][::-1]
        out['s']['reach'] = reach(out['s']['boxPast'], r['half'])
        out['s']['end'] = round(s['along'][s_end], 2)
        out['s']['endOffGrid'] = grid_offset(s['along'][s_end], (ox, oy)[s['axis']])
        xrun, yrun = (r, s) if r['axis'] == 0 else (s, r)
        px, py = yrun['centre'], xrun['centre']          # where the centre lines cross
        square = [px - yrun['half'], px + yrun['half'], py - xrun['half'], py + xrun['half']]
        out['corner'] = [round(px, 2), round(py, 2)]
        out['cornerFill'] = corner_fill(pieces, square, zb, {r['piece']: 'r', s['piece']: 's'})
    elif j['kind'] == 'T':
        # how the through wall s stands at the stem: its core continuous across the stem's line
        out['s']['spanPastJoint'] = [round(r['centre'] - s['along'][0], 1), round(s['along'][1] - r['centre'], 1)]
    elif j['kind'] == 'inline':
        other = 0 if j['end'] == 1 else 1
        sign = 1 if j['end'] == 1 else -1
        out['gap'] = round(sign * (s['along'][other] - r['along'][j['end']]), 2)
        c_r = band_extreme(pr, r['axis'], r['centre'], -CORE, CORE, r['along'][j['end']], sign, zb)
        c_s = band_extreme(ps, s['axis'], s['centre'], -CORE, CORE, s['along'][other], -sign, zb)
        out['coreGap'] = None if c_r is None or c_s is None else round(sign * (c_s - c_r), 2)
        out['r']['coreEndOffGrid'] = None if c_r is None else grid_offset(c_r, origin_along)
    if r['piece'] != s['piece']:
        point = (s['centre'], r['centre']) if r['axis'] == 0 and s['axis'] == 1 else \
                (r['centre'], s['centre']) if r['axis'] == 1 and s['axis'] == 0 else j['point']
        links = column_links(pieces, r['piece'], s['piece'], point, predicted)
        out['lists'] = dict(rListsS=len(links['ab']), sListsR=len(links['ba']), mutualPairs=links['mutual'],
                            oneWayPairs=links['oneWay'], ruleExact=links['ruleExact'],
                            rDepth=Counter('%d,%d,%+d' % t for t in links['ab']).most_common(),
                            sDepth=Counter('%d,%d,%+d' % t for t in links['ba']).most_common())
    return out


# --------------------------------------------------------------------------------------------- the audit
def audit(maps, verbose=False):
    joints, grid_tally, list_tally, misses = [], Counter(), Counter(), Counter()
    per_map = {}
    run_tally = Counter()
    for name, path in maps:
        t0 = time.time()
        p = Package(path)
        pieces = read_pieces(p)
        grid = level_grid(p)
        grid_record(pieces, grid, grid_tally)
        predicted = rule_lists(pieces)
        before = Counter(list_tally)
        map_misses = Counter()
        list_record(pieces, predicted, list_tally, map_misses)
        for k, v in map_misses.items():
            misses[name + ': ' + k] += v
        runs, blocks = [], []
        for i, piece in pieces.items():
            if piece['abox'] is None or not piece['cols']:
                continue
            rr, bb = runs_of(i, piece)
            runs += rr
            blocks += bb
        for r in runs:
            run_tally[r['kind'], 'xy'[r['axis']]] += 1
        found = find_joints(pieces, runs, blocks, grid)
        for j in found:
            d = describe(pieces, runs, j, grid, predicted)
            d['map'] = name
            joints.append(d)
        diff = {k: list_tally[k] - before[k] for k in list_tally}
        per_map[name] = dict(pieces=len(pieces), runs=len(runs), walls=sum(r['kind'] == 'wall' for r in runs),
                             joints=Counter(j['kind'] for j in found),
                             columns=diff.get('columns', 0), columnsExact=diff.get('columns exact', 0))
        if verbose:
            print('%-28s %5.1fs pieces %3d runs %3d joints %s lists %d/%d' % (
                name, time.time() - t0, len(pieces), len(runs), dict(per_map[name]['joints']),
                per_map[name]['columnsExact'], per_map[name]['columns']), flush=True)
    return joints, grid_tally, list_tally, misses, per_map, run_tally


def stats(values):
    v = [x for x in values if x is not None]
    if not v:
        return None
    c = Counter(round(x) for x in v).most_common(4)
    return dict(n=len(v), median=round(float(np.median(v)), 2), min=round(min(v), 2), max=round(max(v), 2),
                common=c)


def joint_class(j):
    if j['kind'] in ('free', 'block'):
        return j['kind']
    return ('%s same piece' if j.get('samePiece') else '%s two pieces') % j['kind']


def summarise(joints):
    """Per class (and per kit of the run that ends there): counts and the typical numbers."""
    out = {}
    groups = defaultdict(list)
    for j in joints:
        groups[joint_class(j)].append(j)
    for cls, js in sorted(groups.items()):
        rec = dict(count=len(js), kits=Counter(j['r']['kit'] for j in js).most_common(8),
                   rEndOffGrid=stats([j['r'].get('endOffGrid') for j in js]),
                   rEndOffTileEdge=stats([j['r'].get('endOffTileEdge') for j in js]),
                   rCentreOffGrid=stats([j['r'].get('centreOffGrid') for j in js]),
                   rHalf=stats([j['r'].get('half') for j in js]))
        if cls.startswith(('free', 'block')):
            rec['rCoreEndOffGrid'] = stats([j['r'].get('coreEndOffGrid') for j in js])
        else:
            rec['rBoxPast'] = stats([j['r'].get('boxPast') for j in js])
            rec['rCorePast'] = stats([j['r'].get('corePast') for j in js])
            rec['rProfile'] = [stats([(j['r'].get('profile') or [None] * 3)[k] for j in js]) for k in range(3)]
            rec['rShape'] = Counter(j['r'].get('shape') for j in js).most_common()
            rec['sHalf'] = stats([j['s'].get('half') for j in js])
            rec['sCentreOffGrid'] = stats([j['s'].get('centreOffGrid') for j in js])
        if cls.startswith('L'):
            rec['sCorePast'] = stats([j['s'].get('corePast') for j in js])
            rec['sBoxPast'] = stats([j['s'].get('boxPast') for j in js])
            pattern = Counter()
            fill = Counter()
            for j in js:
                ends = sorted(['%s, %s' % (j[w].get('reach'), j[w].get('shape')) for w in ('r', 's')])
                pattern[' / '.join(ends)] += 1
                keys = sorted('the two walls' if k in ('r', 's') else 'another piece'
                              for k in j.get('cornerFill', {}))
                fill[' + '.join(sorted(set(keys))) if keys else 'empty'] += 1
            rec['cornerPattern'] = pattern.most_common(12)
            rec['cornerProfiles'] = Counter(' / '.join(sorted(str(tuple(None if v is None else round(v) for v in
                                                                         (j[w].get('profile') or [None] * 3)))
                                                           for w in ('r', 's'))) for j in js).most_common(12)
            rec['cornerFill'] = fill.most_common(10)
            rec['thirdPieces'] = Counter(k for j in js for k in j.get('cornerFill', {}) if k not in ('r', 's')
                                         ).most_common(10)
        if cls.startswith('T'):
            rec['stemPattern'] = Counter('%s, %s' % (j['r'].get('reach'), j['r'].get('shape'))
                                         for j in js).most_common(10)
            rec['stemOnThroughHalf'] = Counter('%g on %g' % (round(j['r'].get('boxPast') or 0), round(j['s']['half']))
                                               for j in js).most_common(12)
        if cls.startswith('inline'):
            rec['gap'] = stats([j.get('gap') for j in js])
            rec['coreGap'] = stats([j.get('coreGap') for j in js])
        with_lists = [j for j in js if 'lists' in j]
        if with_lists:
            rec['lists'] = dict(
                joints=len(with_lists),
                bothWays=sum(1 for j in with_lists if j['lists']['rListsS'] and j['lists']['sListsR']),
                oneWay=sum(1 for j in with_lists if bool(j['lists']['rListsS']) != bool(j['lists']['sListsR'])),
                none=sum(1 for j in with_lists if not j['lists']['rListsS'] and not j['lists']['sListsR']),
                ruleExact=sum(1 for j in with_lists if j['lists']['ruleExact']),
                listingsPerJoint=stats([j['lists']['rListsS'] + j['lists']['sListsR'] for j in with_lists]),
                depth=Counter(k for j in with_lists for k, n in j['lists']['rDepth'] + j['lists']['sDepth']
                              for _ in range(n)).most_common(12))
        out[cls] = rec
    return out


def by_kit(joints):
    """Per kit of the ending run: its joints' classes and the typical core distances past the other's line."""
    out = defaultdict(lambda: dict(classes=Counter(), corePast=defaultdict(list), boxPast=defaultdict(list),
                                   ends=Counter(), partners=Counter(), maps=Counter()))
    for j in joints:
        k = out[j['r']['kit']]
        cls = joint_class(j)
        k['classes'][cls] += 1
        k['maps'][j['map']] += 1
        if j['r'].get('corePast') is not None:
            k['corePast'][cls].append(j['r']['corePast'])
        if j['r'].get('boxPast') is not None:
            k['boxPast'][cls].append(j['r']['boxPast'])
        if j['r'].get('reach'):
            k['ends']['%s: %s, %s (on a wall %g thick with trims)' % (
                cls, j['r']['reach'], j['r'].get('shape'), round(2 * j['s']['half']))] += 1
        if 's' in j:
            k['partners'][j['s']['kit']] += 1
    return {kit: dict(classes=v['classes'].most_common(), maps=len(v['maps']),
                      corePast={c: stats(x) for c, x in v['corePast'].items()},
                      boxPast={c: stats(x) for c, x in v['boxPast'].items()},
                      ends=v['ends'].most_common(12), partners=v['partners'].most_common(6))
            for kit, v in sorted(out.items(), key=lambda kv: -sum(kv[1]['classes'].values()))}


def samples(joints):
    """Up to SAMPLES joints of each class and kit, the Bar's and the Police Station's first."""
    out = defaultdict(list)
    order = sorted(joints, key=lambda j: (not j['map'].startswith('URB_Bar'), not j['map'].startswith('URB_Police'),
                                          j['map']))
    for j in order:
        key = '%s | %s' % (joint_class(j), j['r']['kit'])
        if len(out[key]) < SAMPLES:
            out[key].append(j)
    return dict(out)


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('--maps', nargs='*', help='map names (default: every map the install lists)')
    a.add_argument('--output', type=Path)
    a.add_argument('--verbose', action='store_true')
    args = a.parse_args()
    import library
    import settings
    game, _ = settings.game_install(settings.load_settings())
    maps = [(n, Path(path)) for n, _, path in library.donors(game)]
    if args.maps:
        want = {m.casefold() for m in args.maps}
        maps = [(n, path) for n, path in maps if n.casefold() in want]
    joints, grid_tally, list_tally, misses, per_map, run_tally = audit(maps, args.verbose)
    summary = dict(
        maps=len(maps),
        runs={'%s %s' % k: v for k, v in sorted(run_tally.items())},
        columnGrid={'%s on %s' % (k[0], ' and '.join(x for x in k[1:] if x) or 'neither'): v
                    for k, v in sorted(grid_tally.items())},
        listRule=dict(list_tally, rule='column X of piece A lists column n of piece B when X\'s box touches B_n\'s '
                                       'box cut to B\'s vertex bounds grown by %g unit' % GROW),
        listRuleMisses=misses.most_common(40),
        joints=summarise(joints))
    print(json.dumps(dict(summary, joints={k: dict(count=v['count']) for k, v in summary['joints'].items()}),
                     indent=1, default=str))
    if args.output:
        result = dict(scope='Read-only: the install\'s maps (%d), their placed fracturing pieces\' meshes and fragment '
                            'columns; nothing written to the game' % len(maps),
                      summary=summary, byKit=by_kit(joints), perMap=per_map, samples=samples(joints))
        args.output.write_text(json.dumps(result, indent=1, default=str) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
