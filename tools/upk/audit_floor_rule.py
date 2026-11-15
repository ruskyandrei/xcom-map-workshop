"""Which floors of a building list a piece: the game editor's rule (F-87) under several readings of "touches", put
against what every map of the install saves (a read-only survey; findings register F-87, 14 November 2026).

  python -B tools/upk/audit_floor_rule.py <game install> <out.json> [--jobs 6] [--only NAME]

For every building of every map the editor lists (library.donors) and every piece of a listed class standing within
64 units of one of its floor volumes or listed by it, the rule's answer is compared with the floors the map saves for
it (m_aCachedActors), the floor volumes' inclusion and exclusion lists (m_aInclusionActors, m_aExclusionActors)
applied on top as the game editor applies them. Counted apart: pieces the map lists ("listed") and pieces near a
building it doesn't ("unlisted"). The readings of "touches":
- render, render2: the drawn mesh's box meets the volume, or comes within 2 units (the Build's rule before);
- render0c, render2c: the same, and the piece collides (bCollideActors and CollideActors): the Build's rule since;
- coll, coll2, collBottom, elem, exact, exact2, exactCollBottom, coll2nc: by the mesh's collision (its simple
  collision hulls, else its triangles) instead of its drawn box, in turn: their box, with 2 units, with its bottom,
  each hull's box, the hulls themselves (a separating-axis test), coll2nc ignoring the collide flags;
- render2cc: render2c for pieces with collision only; xy<n>_z<m>: n units of slack across, m up and down (zs: none).
Printed: each reading's share right of each group; the JSON keeps the counts, each error's kind by reading
(cat|reading|group|none, extra or other|collide=..|hulls, tris or none) and up to 400 misses per map.
"""
import argparse
import collections
import json
import multiprocessing
import os
import sys
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[2])
LISTED = ('XComLevelActor', 'XComOpacityFadeLevelActor', 'XComDestructibleActor', 'XComFracLevelActor', 'XComDecoFracLevelActor',
          'XComInteractiveLevelActor', 'XComLadder', 'XComCollectible', 'KAsset')
MARGIN = 20.0
PL = 'TheWorld.PersistentLevel'


def setup(repo):
    for folder in ('tools/upk', 'tools/viewer', 'tools/bake', 'tools/editor'):
        sys.path.insert(0, os.path.join(repo, folder))


def overlap(a, v, slack):
    """a: [x0, x1, y0, y1, z0, z1]; v: [x0, y0, z0, x1, y1, z1]"""
    return all(a[2 * j] <= v[j + 3] + slack and a[2 * j + 1] >= v[j] - slack for j in range(3))


def listing(floors, mask):
    if not floors:
        return []
    if mask and len(floors) > 1:
        return [(min(floors), max(floors))]
    return [(k, 0) for k in sorted(floors)]


def box_of(pts):
    return [float(v) for k in range(3) for v in (pts[:, k].min(), pts[:, k].max())]


def tri_box(tris, v, slack=0.0):
    """Whether any triangle (n, 3, 3) meets the box v [x0, y0, z0, x1, y1, z1] (separating axis test)."""
    import numpy as np
    lo = np.array(v[:3]) - slack
    hi = np.array(v[3:]) + slack
    c = (lo + hi) / 2
    h = (hi - lo) / 2
    t = tris - c
    # box axes
    mn, mx = t.min(axis=1), t.max(axis=1)
    keep = np.all((mn <= h) & (mx >= -h), axis=1)
    if not keep.any():
        return False
    t = t[keep]
    e = [t[:, 1] - t[:, 0], t[:, 2] - t[:, 1], t[:, 0] - t[:, 2]]
    n = np.cross(e[0], e[1])
    d = np.einsum('ij,ij->i', n, t[:, 0])
    r = np.abs(n) @ h
    ok = np.abs(d) <= r + 1e-6
    axes = np.eye(3)
    for ei in e:
        for a in axes:
            ax = np.cross(np.broadcast_to(a, ei.shape), ei)
            p = np.einsum('ijk,ik->ij', t, ax)
            rr = np.abs(ax) @ h
            ok &= ~((p.min(axis=1) > rr + 1e-6) | (p.max(axis=1) < -rr - 1e-6))
    return bool(ok.any())


def hull_box(pts, v, slack=0.0):
    """Whether a convex hull (its points, (n, 3)) meets box v, by SAT on the box axes and the hull's face normals
    (approximate: edge cross axes left out, so it may say yes for a near miss at an edge)."""
    import numpy as np
    lo = np.array(v[:3]) - slack
    hi = np.array(v[3:]) + slack
    if np.any(pts.max(axis=0) < lo) or np.any(pts.min(axis=0) > hi):
        return False
    tris = pts.reshape(-1, 3, 3)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    norm = np.linalg.norm(n, axis=1)
    n = n[norm > 1e-9] / norm[norm > 1e-9, None]
    c = (lo + hi) / 2
    h = (hi - lo) / 2
    proj_pts = (pts - c) @ n.T          # (npts, nn)
    r = np.abs(n) @ h
    sep = (proj_pts.min(axis=0) > r + 1e-6) | (proj_pts.max(axis=0) < -r - 1e-6)
    return not bool(sep.any())


def one(job):
    name, role, path = job
    setup(REPO)
    import numpy as np
    from package import Package, Reader
    import scene_metadata
    import lightmap_texels
    import collision as coll
    out = dict(map=name, role=role)
    try:
        p = Package(path)
    except Exception as error:  # noqa: BLE001
        return dict(out, error=str(error))
    level = p.by_name.get(PL)
    if level is None:
        return dict(out, error='no level')
    actors = [i for i in p.children.get(level, []) if p.exports[i - 1]['outer'] == level]

    def main_mesh(actor):
        return next((k for k in p.children.get(actor, []) if 'MeshComponent' in p.cls(k)), None)

    # buildings: [floors: [volumes: (box, use, incl, excl)]]
    buildings, residents = {}, collections.defaultdict(dict)
    special = set()
    lists = collections.defaultdict(lambda: collections.defaultdict(lambda: [set(), set()]))  # actor -> building -> [incl floors, excl floors]
    list_stats = collections.Counter()
    for i in actors:
        if p.cls(i) != 'XComBuildingVolume':
            continue
        try:
            floors = []
            for fi, row in enumerate(p.structs(p.effective(i, 'Floors'))):
                refs = [r for r in p.refs(row.get(('FloorVolumes', 0), {}).get('value')) if r > 0]
                vols = []
                for r in refs:
                    b = scene_metadata.volume_bounds(p, r)
                    if not b:
                        continue
                    use = p.effective(r, 'm_bUseForBuildingReveal', True) or p.effective(r, 'm_bNonEnterableBuildingPiece', False)
                    for n, key in enumerate(('m_aInclusionActors', 'm_aExclusionActors')):
                        raw = p.own(r, key)
                        if raw:
                            got = [x for x in p.refs(raw) if x > 0]
                            special.update(got)
                            list_stats[key] += len(got)
                            list_stats[key + ' volumes'] += 1
                            for x in got:
                                lists[x][i][n].add(fi)
                    vols.append(([*b['min'], *b['max']], bool(use)))
                floors.append(vols)
                for e in p.structs(row.get(('m_aCachedActors', 0), {}).get('value')):
                    ref = e.get(('ResidentActor', 0), {}).get('value', 0)
                    if ref > 0:
                        residents[ref][(i, fi)] = e.get(('CutdownFloor', 0), {}).get('value', 0)
            if floors:
                buildings[i] = floors
        except Exception:  # noqa: BLE001
            continue
    if not buildings:
        return dict(out, counts={}, misses=[])

    render_cache, coll_cache = {}, {}
    counts = collections.Counter()
    misses = []
    VARIANTS = ('render', 'render2', 'coll', 'coll2', 'collBottom', 'elem', 'exact', 'exact2', 'exactCollBottom')
    ALL = VARIANTS + ('render0c', 'render2c', 'coll2nc', 'render2cc') + tuple(
        'xy%d_%s' % (sxy, z) for sxy in (2, 4, 8, 12, 16, 24) for z in ('z0', 'z2', 'zs'))
    for a in actors:
        cls = p.cls(a)
        if cls not in LISTED:
            continue
        if a in special:
            counts['special'] += 1
        comp = main_mesh(a)
        if comp is None:
            continue
        try:
            mi = p.effective(comp, 'StaticMesh', 0)
            if not mi or mi <= 0 or p.cls(mi) not in ('StaticMesh', 'FracturedStaticMesh'):
                counts['no static mesh'] += 1
                continue
            m = lightmap_texels.world_matrix(p, comp)
            if mi not in render_cache:
                cm = lightmap_texels.component_mesh(p, comp)
                render_cache[mi] = (cm['positions'], cm['triangles'])
            pos, tris = render_cache[mi]
            wpos = pos @ m[:3, :3].T + m[:3, 3]
            rbox = box_of(wpos)
            if mi not in coll_cache:
                simple_box = p.own(mi, 'UseSimpleBoxCollision', True) is not False
                if not simple_box:
                    coll_cache[mi] = ('tris', None)
                else:
                    bs = coll.body_setup(p, mi)
                    if not bs:
                        coll_cache[mi] = ('none', None)
                    else:
                        agg = p.own(bs, 'AggGeom')
                        els = []
                        if isinstance(agg, (bytes, bytearray)):
                            geom = p.tagged(Reader(agg))
                            for elem in p.structs(geom.get(('ConvexElems', 0), {}).get('value')):
                                verts = coll._vectors(elem[('VertexData', 0)]['value'], 3)
                                idx = coll._ints(elem[('FaceTriData', 0)]['value'])
                                if idx:
                                    els.append(np.array([verts[k] for k in idx], float))
                            for elem in p.structs(geom.get(('BoxElems', 0), {}).get('value')):
                                els.append(np.array(coll._box_triangles(elem), float))
                        coll_cache[mi] = ('hulls', els) if els else ('none', None)
            kind, els = coll_cache[mi]
        except Exception as error:  # noqa: BLE001
            counts['unread'] += 1
            continue
        mesh_flag = bool(p.effective(comp, 'bCutoutMask', False))
        collide = p.effective(a, 'bCollideActors', True) is not False and p.effective(comp, 'CollideActors', True) is not False
        if kind == 'hulls':
            wels = [e @ m[:3, :3].T + m[:3, 3] for e in els]
            cbox = box_of(np.concatenate(wels))
            ebox = [box_of(e) for e in wels]
        elif kind == 'tris':
            wels, cbox, ebox = None, rbox, [rbox]
        else:
            wels, cbox, ebox = None, None, []
        wtris = wpos[tris] if kind == 'tris' else None
        for b, floors in buildings.items():
            saved = sorted((k, cut) for (bb, k), cut in residents.get(a, {}).items() if bb == b)
            near = any(overlap(rbox, v, 64) for vols in floors for v, _ in vols)
            if not saved and not near:
                continue
            res = {}

            incl, excl = lists[a][b] if a in lists and b in lists[a] else (set(), set())

            def touched(test, bottom):
                got = []
                for k, vols in enumerate(floors):
                    for v, use in vols:
                        if use and bottom is not None and bottom < v[5] - MARGIN and test(v):
                            got.append(k)
                            break
                got = sorted((set(got) | incl) - excl)
                return listing(got, mesh_flag)
            res['render'] = touched(lambda v: overlap(rbox, v, 0), rbox[4])
            res['render2'] = touched(lambda v: overlap(rbox, v, 2), rbox[4])
            res['render0c'] = touched(lambda v: collide and overlap(rbox, v, 0), rbox[4])
            res['render2c'] = touched(lambda v: collide and overlap(rbox, v, 2), rbox[4])
            res['coll2nc'] = touched(lambda v: cbox is not None and overlap(cbox, v, 2), rbox[4])
            res['render2cc'] = touched(lambda v: collide and cbox is not None and overlap(rbox, v, 2), rbox[4])
            for sxy in (2, 4, 8, 12, 16, 24):
                for sz in (0, 2):
                    res['xy%d_z%d' % (sxy, sz)] = touched(
                        lambda v, sxy=sxy, sz=sz: collide and all(rbox[2 * j] <= v[j + 3] + (sxy if j < 2 else sz)
                                                                 and rbox[2 * j + 1] >= v[j] - (sxy if j < 2 else sz) for j in range(3)), rbox[4])
                res['xy%d_zs' % sxy] = touched(
                    lambda v, sxy=sxy: collide and all(rbox[2 * j] <= v[j + 3] + sxy and rbox[2 * j + 1] >= v[j] - sxy for j in range(2))
                    and rbox[4] < v[5] and rbox[5] > v[2], rbox[4])
            if not collide or cbox is None:
                for k in VARIANTS[2:]:
                    res[k] = touched(lambda v: False, rbox[4])
            else:
                res['coll'] = touched(lambda v: overlap(cbox, v, 0), rbox[4])
                res['coll2'] = touched(lambda v: overlap(cbox, v, 2), rbox[4])
                res['collBottom'] = touched(lambda v: overlap(cbox, v, 0), cbox[4])
                res['elem'] = touched(lambda v: any(overlap(e, v, 0) for e in ebox), rbox[4])
                if kind == 'hulls':
                    ex = lambda v, s=0.0: any(hull_box(e, v, s) for e in wels)  # noqa: E731
                else:
                    ex = lambda v, s=0.0: tri_box(wtris, v, s)  # noqa: E731
                res['exact'] = touched(lambda v: ex(v), rbox[4])
                res['exact2'] = touched(lambda v: ex(v, 2.0), rbox[4])
                res['exactCollBottom'] = touched(lambda v: ex(v), cbox[4])
            group = 'listed' if saved else 'unlisted'
            for k in ALL:
                counts['%s|%s|%s' % (k, group, res[k] == saved)] += 1
                if res[k] != saved:
                    cat = 'none' if not res[k] else 'extra' if not saved else 'other'
                    counts['cat|%s|%s|%s|collide=%s|%s' % (k, group, cat, collide, kind)] += 1
            if res['render2'] != saved or res['exact'] != saved:
                if len(misses) < 400:
                    misses.append(dict(piece=p.name(a).split('.')[-1], cls=cls, mesh=p.name(mi), kind=kind, mask=mesh_flag,
                                       collide=collide, saved=saved, **{k: res[k] for k in ALL},
                                       rbox=[round(x, 1) for x in rbox], cbox=cbox and [round(x, 1) for x in cbox],
                                       floors=[[v for v, _ in vols] for vols in floors]))
    counts.update({'lists|' + k: n for k, n in list_stats.items()})
    return dict(out, counts=dict(counts), misses=misses)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('game')
    ap.add_argument('out')
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--only')
    args = ap.parse_args()
    setup(REPO)
    import library
    jobs = [(n, r, str(path)) for n, r, path in library.donors(Path(args.game))
            if not args.only or args.only.casefold() in n.casefold()]
    with multiprocessing.Pool(args.jobs) as pool:
        rows = pool.map(one, jobs, chunksize=1)
    total = collections.Counter()
    for r in rows:
        for k, n in (r.get('counts') or {}).items():
            total[k] += n
    Path(args.out).write_text(json.dumps(dict(total=dict(total), packages=rows)), encoding='utf-8', newline='\n')
    variants = sorted({k.split('|')[0] for k in total if '|' in k} - {'cat', 'lists'})
    print('packages', len(rows), 'errors', [r['map'] for r in rows if 'error' in r])
    for k in ('special', 'unread', 'no static mesh'):
        print(k, total.get(k, 0))
    for k in sorted(total):
        if k.startswith('lists|'):
            print(k, total[k], 'in', sum(1 for r in rows if (r.get('counts') or {}).get(k)), 'packages')
    for v in variants:
        line = []
        for g in ('listed', 'unlisted'):
            ok, bad = total.get('%s|%s|True' % (v, g), 0), total.get('%s|%s|False' % (v, g), 0)
            line.append('%s %d/%d (%.1f%%)' % (g, ok, ok + bad, 100.0 * ok / max(1, ok + bad)))
        print('%-16s %s' % (v, '   '.join(line)))


if __name__ == '__main__':
    main()
