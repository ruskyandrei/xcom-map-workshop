"""Read-only audit of the game's fracturing building walls, for a fracturing wall made from numbers
(private/plans/done/custom-geometry-implementation-plan.md, section 0, stage F0; findings register T-42).

Over every map the install lists (tools/viewer/library.py donors), or the maps named with --maps, it reads each placed
fracturing piece (XComDecoFracLevelActor, XComFracLevelActor) whose mesh's name holds "wall", and every fracturing
mesh's triangle collision tree:

  tree        every static and fracturing mesh written back from its numbers (tools/bake/gen_mesh.py), byte for
              byte; the node count against gen_mesh.node_count; for fracturing meshes, each collision triangle's
              fourth value against its section's slot and its fragment (gen_mesh.kdop_value), and whether the
              collision triangles are the index buffer's, in another order; how the nodes' bytes split
  walls       per wall mesh: size, triangles, fragments and their sizes, sections, vertex colours, and per placed
              piece the materials its component binds to each slot; the trims (a slot whose material is a trim set):
              how far they stand proud of the faces and at what heights
  columns     each placed wall's FragmentColumns: its bounds against the tile cells and storeys, and its fragment
              list (FragCache) against two rules, a fragment's box overlapping the column's box and its true shape
              (its triangles' convex hull) overlapping the column's box by more than a sliver; each MinZ against the
              fragment's lowest corner
  component   the fracturing component's saved numbers: FragmentBoundsMinZ and MaxZ against the fragments' world
              heights, NumResourceIndices against the index count, the lightmap resolution
  turned      (21 November 2026, the custom geometry improvements plan, 4.6) each placed wall's yaw, and for the walls
              turned off the quarter turns their columns' world boxes: the game's own rule for a wall at a free angle,
              if its maps hold any

Prints a summary; --output writes the JSON. No game file is written.

  python -B research/evidence/frac-wall-audit.py [--maps URB_Bar URB_PoliceStation] [--output <file.json>]
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
SLIVER = 1.0        # cubic units: a true-shape overlap smaller than this counts as none


def fragment_triangles(m):
    """{fragment: [(a, b, c)]} over every section of LOD 0, and {triangle (sorted corners): (slot, fragment)}."""
    lod = m['lods'][0]
    idx = lod['indices'][1]
    per, where = defaultdict(list), {}
    for s in lod['sections']:
        for f, (first, count) in enumerate(s['fragments']):
            for t in range(first // 3, first // 3 + count):
                tri = tuple(idx[3 * t:3 * t + 3])
                per[f].append(tri)
                where[tri] = (s['slot'], f)
    return per, where


def tree_record(m, fragments):
    """What the collision tree of mesh `m` shows: node count rule, fourth values, order, node bytes."""
    k = m['kdop']
    tris = k['triangles']
    nodes = np.frombuffer(k['nodes'], np.uint8).reshape(-1, 6) if k['nodes'] else np.zeros((0, 6), np.uint8)
    out = dict(triangles=len(tris), nodes=len(nodes), ruleHolds=len(nodes) == gen_mesh.node_count(len(tris)))
    if len(nodes):
        out['lastNodeZero'] = bool(not nodes[-1].any())
        inner = nodes[:-1]
        out['innerWhole'] = int(sum(1 for n in inner if (n == 128).all()))
        out['innerNodes'] = int(len(inner))
    lod = m['lods'][0]
    idx = lod['indices'][1]
    buffer = [tuple(idx[3 * t:3 * t + 3]) for t in range(len(idx) // 3)]
    out['sameTriangles'] = sorted(tuple(t[:3]) for t in tris) == sorted(buffer)
    out['sameOrder'] = [tuple(t[:3]) for t in tris] == buffer
    if fragments:
        _, where = fragment_triangles(m)
        ok = sum(1 for t in tris if t[:3] in where
                 and t[3] == gen_mesh.kdop_value(where[t[:3]][0], where[t[:3]][1], fragments))
        out['fourthValueRule'] = [ok, len(tris)]
    else:
        slot_of = {}
        for s in lod['sections']:
            for t in range(s['first'] // 3, s['first'] // 3 + s['triangles']):
                slot_of[buffer[t]] = s['slot']
        ok = sum(1 for t in tris if slot_of.get(t[:3]) == t[3])
        out['fourthValueRule'] = [ok, len(tris)]
    return out


def overlap_volume(points, box):
    """The volume of the convex hull of `points` (n x 3) inside the box [x0, x1, y0, y1, z0, z1], or 0."""
    from scipy.optimize import linprog
    from scipy.spatial import ConvexHull, HalfspaceIntersection
    try:
        hull = ConvexHull(points)
    except Exception:
        return 0.0
    planes = [hull.equations]
    for a in range(3):
        n = np.zeros(4)
        n[a], n[3] = -1, box[2 * a]
        planes.append(n[None])
        n = np.zeros(4)
        n[a], n[3] = 1, -box[2 * a + 1]
        planes.append(n[None])
    h = np.vstack(planes)
    norm = np.linalg.norm(h[:, :3], axis=1)
    res = linprog(np.r_[np.zeros(3), -1.0], A_ub=np.c_[h[:, :3], norm], b_ub=-h[:, 3],
                  bounds=[(None, None)] * 3 + [(0, None)], method='highs')
    if not res.success or res.x[3] < 1e-3:
        return 0.0
    try:
        inter = HalfspaceIntersection(h, res.x[:3])
        return float(ConvexHull(inter.intersections).volume)
    except Exception:
        return 0.0


def box_overlap(a, b, slack=0.0):
    return all(min(a[2 * k + 1], b[2 * k + 1]) - max(a[2 * k], b[2 * k]) > slack for k in range(3))


def wall_audit(p, actor, comp, mesh, m, stats, column_rows):
    """The columns and component numbers of one placed wall; adds to `stats` and `column_rows`."""
    world = lightmap_texels.world_matrix(p, comp)
    lod = m['lods'][0]
    pos = np.array(lod['positions'], float)
    wpos = (np.c_[pos, np.ones(len(pos))] @ world.T)[:, :3]
    per, _ = fragment_triangles(m)
    frags = len(m['fractured']['fragments'])
    fpts = {f: wpos[sorted({i for t in per[f] for i in t})] for f in range(frags) if per.get(f)}
    fbox = {f: [v for k in range(3) for v in (pts[:, k].min(), pts[:, k].max())] for f, pts in fpts.items()}
    cols = p.structs(p.own(actor, 'FragmentColumns'))
    record = dict(columns=len(cols), boxRule=0, shapeRule=0, tileColumns=0, tileBoxRule=0, minZ=[], columnBoxes=[])
    for c in cols:
        b = struct.unpack('<6fB', c[('Bounds', 0)]['value'])
        box = [b[0], b[3], b[1], b[4], b[2], b[5]]
        saved = [(it.get(('FragIndex', 0), {}).get('value', 0), it.get(('MinZ', 0), {}).get('value', 0.0))
                 for it in p.structs(c.get(('FragCache', 0), {}).get('value'))]
        listed = {f for f, _ in saved}
        by_box = {f for f, fb in fbox.items() if box_overlap(fb, box)}
        by_shape = set()
        for f in by_box:
            if overlap_volume(fpts[f], box) > SLIVER:
                by_shape.add(f)
        record['columnBoxes'].append([round(v, 1) for v in box])
        record['boxRule'] += by_box == listed
        record['shapeRule'] += by_shape == listed
        # a column a tile long (or less, at a wall's end) and a storey tall, as the inner walls' are
        if max(box[1] - box[0], box[3] - box[2]) <= TILE + 0.5 and abs(box[5] - box[4] - STOREY) < 0.5:
            record['tileColumns'] += 1
            record['tileBoxRule'] += by_box == listed
        for f, z in saved:
            if f in fbox:
                record['minZ'].append(float(z) - float(fbox[f][4]))
        if len(column_rows) < 4000:
            column_rows.append(dict(listed=sorted(listed), box=sorted(by_box), shape=sorted(by_shape)))
        stats['minZ sorted'] += [z for _, z in saved] == sorted(z for _, z in saved)
        stats['columns'] += 1
    # the component's saved numbers
    zs = [fb[4] for fb in fbox.values()] + [fb[5] for fb in fbox.values()]
    record['fragmentBoundsZ'] = [p.own(comp, 'FragmentBoundsMinZ'), p.own(comp, 'FragmentBoundsMaxZ'),
                                 float(min(zs)), float(max(zs))]
    record['numResourceIndices'] = [p.own(comp, 'NumResourceIndices'), len(lod['indices'][1])]
    record['lightmapRes'] = [p.own(comp, 'OverriddenLightMapRes'), p.own(mesh, 'LightMapResolution')]
    return record


def slot_record(m, p, comp):
    """Per section: slot, triangles, the material the component binds, whether its vertex colours vary."""
    lod = m['lods'][0]
    idx = lod['indices'][1]
    mats = p.refs(p.own(comp, 'Materials')) if p.own(comp, 'Materials') is not None else []
    pos = np.array(lod['positions'], float)
    out = []
    for s in lod['sections']:
        verts = sorted(set(idx[s['first']:s['first'] + 3 * s['triangles']]))
        colours = {lod['colours'][v] for v in verts} if lod['colours'] else set()
        p_ = pos[verts]
        uv = np.array([lod['vertices'][v][2][0] for v in verts], float)
        rec = dict(slot=s['slot'], triangles=s['triangles'],
                   material=p.name(mats[s['slot']]) if s['slot'] < len(mats) and mats[s['slot']] else None,
                   colours=len(colours), box=[round(float(v), 2) for k in range(3)
                                              for v in (p_[:, k].min(), p_[:, k].max())])
        # texture repeat: world units per UV unit along the longest direction (least squares over the slot's verts)
        live = [k for k in range(3) if np.ptp(p_[:, k]) > 1e-3]     # a face's flat axis says nothing
        if len(verts) >= 3 and live:
            p_ = p_[:, live]
            a = np.c_[p_, np.ones(len(p_))]
            su, *_ = np.linalg.lstsq(a, uv[:, 0], rcond=None)
            sv, *_ = np.linalg.lstsq(a, uv[:, 1], rcond=None)
            n = len(live)
            rec['repeat'] = [round(1 / float(np.linalg.norm(su[:n])), 1) if np.linalg.norm(su[:n]) > 1e-9 else None,
                             round(1 / float(np.linalg.norm(sv[:n])), 1) if np.linalg.norm(sv[:n]) > 1e-9 else None]
        out.append(rec)
    return out


def audit(maps, verbose=False):
    trees, wall_meshes, placed = {}, {}, []
    stats = Counter()
    column_rows = []
    oracle = Counter()
    for name, path in maps:
        t0 = time.time()
        p = Package(path)
        level = p.by_name.get('TheWorld.PersistentLevel')
        for i in range(1, len(p.exports) + 1):
            cls = p.cls(i)
            if cls in ('StaticMesh', 'FracturedStaticMesh'):
                try:
                    m = gen_mesh.read(p, i)
                except gen_mesh.MeshError:
                    oracle['unread'] += 1
                    continue
                e = p.exports[i - 1]
                same = gen_mesh.write(m, m['at']) == bytes(p.data[m['at']:e['off'] + e['size']])
                oracle[cls, same] += 1
                key = p.name(i)
                if cls == 'FracturedStaticMesh' and key not in trees:
                    trees[key] = tree_record(m, len(m['fractured']['fragments']))
                elif cls == 'StaticMesh':
                    k = m['kdop']
                    oracle['static rule', len(k['nodes']) // 6 == gen_mesh.node_count(len(k['triangles']))] += 1
        for i in range(1, len(p.exports) + 1):
            if p.cls(i) not in FRACTURING or p.exports[i - 1]['outer'] != level:
                continue
            comp = p.own(i, 'FracturedStaticMeshComponent')
            if not comp or comp < 0:
                continue
            mesh = p.own(comp, 'StaticMesh')
            if not mesh or mesh < 0 or p.cls(mesh) != 'FracturedStaticMesh' or 'wall' not in p.name(mesh).lower():
                continue
            m = gen_mesh.read(p, mesh)
            key = p.name(mesh)
            frags = m['fractured']['fragments']
            if key not in wall_meshes:
                sizes = [[2 * g['bounds'][3], 2 * g['bounds'][4], 2 * g['bounds'][5]] for g in frags]
                lod = m['lods'][0]
                wall_meshes[key] = dict(size=[round(2 * v, 1) for v in m['bounds'][3:6]],
                                        triangles=len(lod['indices'][1]) // 3, vertices=len(lod['positions']),
                                        fragments=len(frags), sections=len(lod['sections']),
                                        fragmentSize=[round(float(np.median([s[k] for s in sizes])), 1) for k in range(3)],
                                        destroyable=sum(1 for g in frags if g['destroyable']),
                                        roots=sum(1 for g in frags if g['root']), core=m['fractured']['core'],
                                        extra=Counter(g['extra'] for g in frags).most_common(2),
                                        colourValues=len(set(lod['colours'])) if lod['colours'] else 0,
                                        uvChannels=lod['texcoords'], slots=slot_record(m, p, comp), placed=0)
            wall_meshes[key]['placed'] += 1
            try:
                rec = wall_audit(p, i, comp, mesh, m, stats, column_rows)
            except (ValueError, KeyError) as err:
                stats['wall audit skipped'] += 1
                if verbose:
                    print('  skipped', p.name(i), err)
                continue
            rot = p.own(i, 'Rotation') or [0, 0, 0]
            boxes = rec.pop('columnBoxes')
            turned = int(rot[1]) % 16384 != 0
            placed.append(dict(map=name, actor=p.name(i).split('.')[-1], mesh=key, yaw=int(rot[1]),
                               **({'columnBoxes': boxes} if turned else {}), **rec))
        if verbose:
            print('%-28s %5.1fs  walls so far %d' % (name, time.time() - t0, len(placed)), flush=True)
    return trees, wall_meshes, placed, stats, column_rows, oracle


def summary(trees, wall_meshes, placed, stats, oracle):
    cols = sum(r['columns'] for r in placed)
    minz = [d for r in placed for d in r['minZ']]
    rows = [r['fragmentBoundsZ'] for r in placed if r['fragmentBoundsZ'][0] is not None]
    res = [r['numResourceIndices'] for r in placed]
    fourth = [t['fourthValueRule'] for t in trees.values()]
    return dict(
        oracle={('%s %s' % k if isinstance(k, tuple) else k): v for k, v in oracle.items()},
        fracturingMeshes=len(trees),
        nodeRuleHolds=sum(t['ruleHolds'] for t in trees.values()),
        lastNodeZero=sum(t.get('lastNodeZero', True) for t in trees.values()),
        fourthValueRule=[sum(a for a, _ in fourth), sum(b for _, b in fourth)],
        meshesAllFourthValues=sum(a == b for a, b in fourth),
        sameTrianglesAsIndexBuffer=sum(t['sameTriangles'] for t in trees.values()),
        sameOrderAsIndexBuffer=sum(t['sameOrder'] for t in trees.values()),
        innerNodesWhole=[sum(t.get('innerWhole', 0) for t in trees.values()),
                         sum(t.get('innerNodes', 0) for t in trees.values())],
        wallMeshes=len(wall_meshes), placedWalls=len(placed), columns=cols,
        columnsBoxRule=sum(r['boxRule'] for r in placed), columnsShapeRule=sum(r['shapeRule'] for r in placed),
        tileColumns=sum(r['tileColumns'] for r in placed), tileColumnsBoxRule=sum(r['tileBoxRule'] for r in placed),
        wallsAllColumnsBoxRule=sum(r['boxRule'] == r['columns'] for r in placed),
        minZSorted=stats['minZ sorted'],
        minZMinusLowestCorner=dict(count=len(minz), within0p01=sum(abs(d) <= 0.01 for d in minz),
                                   min=round(min(minz), 3) if minz else None, max=round(max(minz), 3) if minz else None),
        fragmentBoundsZ=dict(count=len(rows), minMatches=sum(abs(a - c) <= 0.01 for a, b, c, d in rows),
                             maxMatches=sum(abs(b - d) <= 0.01 for a, b, c, d in rows)),
        numResourceIndices=dict(count=len(res), equalIndexCount=sum(a == b for a, b in res)),
        wallAuditSkipped=stats['wall audit skipped'],
        turnedWalls=dict(count=sum(1 for r in placed if r['yaw'] % 16384), maps=sorted({r['map'] for r in placed if r['yaw'] % 16384}),
                         columns=sum(r['columns'] for r in placed if r['yaw'] % 16384),
                         boxRule=sum(r['boxRule'] for r in placed if r['yaw'] % 16384)),
    )


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
    trees, walls, placed, stats, rows, oracle = audit(maps, args.verbose)
    result = dict(scope='Read-only: the install\'s maps (%d), their static and fracturing meshes and placed fracturing '
                        'walls; nothing written to the game' % len(maps),
                  summary=summary(trees, walls, placed, stats, oracle), wallMeshes=walls,
                  placedWalls=[dict(r, minZ=dict(count=len(r['minZ']),
                                                 worst=round(max((abs(d) for d in r['minZ']), default=0.0), 3)))
                               for r in placed],
                  trees=trees)
    print(json.dumps(result['summary'], indent=1))
    if args.output:
        args.output.write_text(json.dumps(result, indent=1, default=str) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
