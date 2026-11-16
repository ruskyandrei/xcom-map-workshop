"""
Plans and applies the tile seeds a patch needs in its base map's baked world data (EXP-07, findings register F-29).

The game's runtime tile rebuild only re-checks a tile whose baked static flags have a bit in 0xFFF
(research/native-code-notes.md). A piece a patch adds where the map had nothing, above the ground, is never seen
there: it blocks neither line of sight nor movement. Seeding bit 0x1 on those tiles in a copy of the map makes the
rebuild compute them from what stands there. Every seeded tile must also be rebuilt at load, or it keeps the seed
bit; patchtool places an XComMapEdTileSeeds actor that rebuilds exactly the planned boxes.

  python seed_map.py plan  <spec.json> <map.upk> <plan.tsv> [--inventory <map inventory.tsv>]
  python seed_map.py apply <map.upk> <out.upk> <plan.tsv> [<plan.tsv> ...] [--seed 0x1]

plan: the tiles each placed piece crosses, from tile level 1 up (level 0 always has floor bits):
  - copy:  each source piece's box from the map inventory (tools/upk/map_inventory.py, made next to the plan when
           not given), moved from the pivot to the copy's location and turned by its yaw, plus MARGIN in x and y.
           A copy with absolute poses (the editor's compiler) gives each copy's world box itself, in boxes
           ([x0, x1, y0, y1, z0, z1], worked out from the mesh bounds turned by the full rotation), plus MARGIN;
  - spawn: the tiles whose centre is inside location +- rebuildExtent (the spawner's own rebuild box);
  - actor: the tiles whose centre is inside its rebuild volume.
Objects with "seed": false, and the whole spec with "seed": false, are left out. The grid is the map's one
XComLevelVolume. Each row also gives the world box to rebuild: the tiles' own extent plus 8 units.

apply: seeds the union of the plans' tiles in a copy of map.upk (tools/upk/seed_tiles.py) and verifies it.
"""
import json, math, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seed_tiles

TILE, FLOOR = 96.0, 64.0
MARGIN = 24.0      # a piece within a quarter tile of a tile edge also seeds the tile across it
REBUILD_PAD = 8.0
HERE = os.path.dirname(os.path.abspath(__file__))
HEADER = ['object', 'type', 'piece', 'x0', 'x1', 'y0', 'y1', 'z0', 'z1', 'wx0', 'wx1', 'wy0', 'wy1', 'wz0', 'wz1']


def rng(s):
    a, b = s.split('..')
    return float(a), float(b)


def read_inventory(path):
    rows = {}
    with open(path) as f:
        head = f.readline().rstrip('\n').split('\t')
        for line in f:
            v = dict(zip(head, line.rstrip('\n').split('\t')))
            box = None
            if v.get('box x'):
                box = rng(v['box x']) + rng(v['box y']) + rng(v['box z'])
            rows[v['name']] = dict(cls=v['class'], loc=(float(v['x']), float(v['y']), float(v['z'])), yaw=float(v.get('yaw') or 0), box=box)
    return rows


def inventory_for(map_path, plan_path, origin, tsv=None):
    """The map's inventory TSV: tsv (made there when missing or older than the map), or one next to the plan."""
    if not tsv:
        stem = os.path.splitext(os.path.basename(map_path))[0]
        tsv = os.path.join(os.path.dirname(os.path.abspath(plan_path)), stem + '-inventory.tsv')
    prefix = tsv[:-4] if tsv.endswith('.tsv') else tsv
    if not os.path.exists(tsv) or os.path.getmtime(tsv) < os.path.getmtime(map_path):
        subprocess.run([sys.executable, os.path.join(HERE, 'map_inventory.py'), map_path, prefix,
                        '--origin', str(origin[0]), str(origin[1])], check=True, stdout=subprocess.DEVNULL)
    return tsv


def grid(inv, spec_origin, map_path=None):
    """The map's tile grid as native_copy.level_grid has it: the corner of its level volume's box (in the inventory),
    and the counts and the game's corner (tx, ty, tz) from the map itself where `map_path` is given
    (scene_metadata.game_grid), else the box's counts, rounded, and a unit under its corner."""
    vols = [r for r in inv.values() if r['cls'] == 'XComLevelVolume' and r['box']]
    if len(vols) != 1:
        raise SystemExit('expected one XComLevelVolume in the map, found %d' % len(vols))
    x0, x1, y0, y1, z0, z1 = vols[0]['box']
    g = dict(ox=x0, oy=y0, oz=z0, nx=round((x1 - x0) / TILE), ny=round((y1 - y0) / TILE), nz=round((z1 - z0) / FLOOR),
             tx=x0 - 1, ty=y0 - 1, tz=z0 - 1)
    if map_path:
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'viewer'))
        import scene_metadata
        from package import Package
        game = scene_metadata.game_grid(Package(map_path), dict(min=[x0, y0, z0], max=[x1, y1, z1]))
        if game:
            g.update(nx=game['dimensions'][0], ny=game['dimensions'][1], nz=game['dimensions'][2],
                     tx=game['tiles'][0], ty=game['tiles'][1], tz=game['tiles'][2])
    if spec_origin and (abs(spec_origin[0] - x0) > 1 or abs(spec_origin[1] - y0) > 1):
        raise SystemExit('the spec\'s map.origin %s is not the level volume\'s corner (%g, %g)' % (spec_origin, x0, y0))
    return g


def turn(dx, dy, yaw):
    k = int(round(yaw / 90.0)) % 4
    return [(dx, dy), (-dy, dx), (-dx, -dy), (dy, -dx)][k]


def moved_box(box, pivot, loc, yaw):
    x0, x1, y0, y1, z0, z1 = box
    pts = [turn(x - pivot[0], y - pivot[1], yaw) for x in (x0, x1) for y in (y0, y1)]
    xs = [loc[0] + p[0] for p in pts]; ys = [loc[1] + p[1] for p in pts]
    dz = loc[2] - pivot[2]
    return (min(xs), max(xs), min(ys), max(ys), z0 + dz, z1 + dz)


def tiles_touched(box, g, margin):
    """Tile ranges a world box (grown by margin in x and y) reaches into, levels from 1 up."""
    x0, x1, y0, y1, z0, z1 = box
    e = 1e-3
    tx = (math.floor((x0 - margin - g['ox']) / TILE + e), math.ceil((x1 + margin - g['ox']) / TILE - e) - 1)
    ty = (math.floor((y0 - margin - g['oy']) / TILE + e), math.ceil((y1 + margin - g['oy']) / TILE - e) - 1)
    tz = (max(1, math.floor((z0 - g['oz']) / FLOOR + e)), math.ceil((z1 - g['oz']) / FLOOR - e) - 1)
    return tx + ty + tz


def tiles_centred(box, g):
    """Tile ranges whose centres lie inside a world box, levels from 1 up."""
    x0, x1, y0, y1, z0, z1 = box
    tx = (math.ceil((x0 - g['ox']) / TILE - 0.5), math.floor((x1 - g['ox']) / TILE - 0.5))
    ty = (math.ceil((y0 - g['oy']) / TILE - 0.5), math.floor((y1 - g['oy']) / TILE - 0.5))
    tz = (max(1, math.ceil((z0 - g['oz']) / FLOOR - 0.5)), math.floor((z1 - g['oz']) / FLOOR - 0.5))
    return tx + ty + tz


def clamp(t, g):
    x0, x1, y0, y1, z0, z1 = t
    t = (max(0, x0), min(g['nx'] - 1, x1), max(0, y0), min(g['ny'] - 1, y1), max(1, z0), min(g['nz'] - 1, z1))
    return t if t[0] <= t[1] and t[2] <= t[3] and t[4] <= t[5] else None


def world_of(t, g):
    x0, x1, y0, y1, z0, z1 = t
    p = REBUILD_PAD
    return (g['ox'] + x0 * TILE - p, g['ox'] + (x1 + 1) * TILE + p, g['oy'] + y0 * TILE - p, g['oy'] + (y1 + 1) * TILE + p,
            g['oz'] + z0 * FLOOR - p, g['oz'] + (z1 + 1) * FLOOR + p)


def position(o, spec, what):
    m = spec.get('map', {})
    ox, oy = (m.get('origin') or [0, 0])[:2]
    ts = m.get('tileSize', 96)
    gz = m.get('groundZ', 3.999993)
    if 'location' in o:
        p = list(o['location'])
    elif 'tile' in o:
        add = ts / 2 if o.get('anchor', 'corner') == 'center' else 0
        p = [ox + ts * o['tile'][0] + add, oy + ts * o['tile'][1] + add]
    else:
        raise SystemExit('%s has no location or tile' % what)
    if len(p) == 2:
        p.append(o.get('z', gz))
    elif 'z' in o:
        p[2] = o['z']
    return p


def plan(spec_path, map_path, out, inv_path=None):
    spec = json.load(open(spec_path))
    origin = (spec.get('map', {}).get('origin') or [-2784, -1920])[:2]
    inv = read_inventory(inventory_for(map_path, out, origin, inv_path))
    g = grid(inv, spec.get('map', {}).get('origin'), map_path)
    rows, notes = [], []
    if spec.get('seed', True) is not False:
        for i, o in enumerate(spec.get('objects', [])):
            kind = o.get('type', 'actor')
            if o.get('seed', True) is False:
                continue
            what = 'objects[%d]' % i
            if kind == 'copy' and 'poses' in o:
                boxes = o.get('boxes') or []
                for k, piece in enumerate(o.get('from', [])):
                    if k >= len(boxes) or not boxes[k] or len(boxes[k]) != 6:
                        notes.append('%s: copy %d (%s) has no box in boxes; not seeded' % (what, k, piece)); continue
                    t = clamp(tiles_touched(tuple(float(v) for v in boxes[k]), g, MARGIN), g)
                    if t:
                        rows.append((i, kind, piece) + t)
            elif kind == 'copy':
                loc = position(o, spec, what)
                for piece in o.get('from', []):
                    r = inv.get(piece)
                    if not r or not r['box']:
                        notes.append('%s: %s has no box in the inventory; not seeded' % (what, piece)); continue
                    t = clamp(tiles_touched(moved_box(r['box'], o['pivot'], loc, o.get('yaw', 0)), g, MARGIN), g)
                    if t:
                        rows.append((i, kind, piece) + t)
            elif kind == 'ladder':
                loc = position(o, spec, what)
                t = clamp(tiles_touched((loc[0] - 48, loc[0] + 48, loc[1] - 48, loc[1] + 48, loc[2], loc[2] + 476), g, MARGIN), g)
                if t:
                    rows.append((i, kind, o.get('mesh', 'LadderMetal.Meshes.LadderMetalA_448')) + t)
            elif kind == 'bake':
                # A base-map actor baked into a new place in the map: its box, moved there.
                r = inv.get(o.get('actor', ''))
                if not r or not r['box']:
                    notes.append('%s: %s has no box in the inventory; not seeded' % (what, o.get('actor'))); continue
                loc = position(o, spec, what)
                turn_by = o['yaw'] - r['yaw'] if o.get('yaw') is not None else 0
                t = clamp(tiles_touched(moved_box(r['box'], r['loc'], loc, turn_by), g, MARGIN), g)
                if t:
                    rows.append((i, kind, o['actor']) + t)
            elif kind == 'spawn':
                loc = position(o, spec, what)
                e = o.get('rebuildExtent', [192, 256, 160])
                t = clamp(tiles_centred((loc[0] - e[0], loc[0] + e[0], loc[1] - e[1], loc[1] + e[1], loc[2] - e[2], loc[2] + e[2]), g), g)
                if t:
                    rows.append((i, kind, o.get('archetype', '')) + t)
            elif kind == 'actor' and o.get('volume', True) is not False:
                loc = position(o, spec, what)
                v = o.get('volume', True)
                v = v if isinstance(v, dict) else {}
                h = v.get('half', 128); h = [h] * 3 if not isinstance(h, list) else h
                c = v.get('location') or [loc[k] + (v.get('offset') or [0, 0, 12])[k] for k in range(3)]
                t = clamp(tiles_centred((c[0] - h[0], c[0] + h[0], c[1] - h[1], c[1] + h[1], c[2] - h[2], c[2] + h[2]), g), g)
                if t:
                    rows.append((i, kind, o.get('mesh', '')) + t)
    with open(out, 'w', newline='\n') as f:
        f.write('\t'.join(HEADER) + '\n')
        for r in rows:
            w = world_of(r[3:9], g)
            f.write('\t'.join(str(v) for v in r) + '\t' + '\t'.join('%g' % v for v in w) + '\n')
    n = len(set(tile_set(rows)))
    for s in notes:
        print('note: ' + s)
    print('planned %d box(es), %d tiles, grid origin (%g, %g, %g) %dx%dx%d; wrote %s' % (
        len(rows), n, g['ox'], g['oy'], g['oz'], g['nx'], g['ny'], g['nz'], out))


def tile_set(rows):
    for r in rows:
        x0, x1, y0, y1, z0, z1 = r[3:9]
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    yield (x, y, z)


def read_plan(path):
    with open(path) as f:
        head = f.readline().rstrip('\n').split('\t')
        if head[:9] != HEADER[:9]:
            raise SystemExit('%s is not a seed plan' % path)
        return [tuple(v[:3]) + tuple(int(x) for x in v[3:9]) for v in (l.rstrip('\n').split('\t') for l in f) if len(v) >= 9]


def apply(src, dst, plans, seed):
    rows = [r for p in plans for r in read_plan(p)]
    tiles = set(tile_set(rows))
    changed, already, dims = seed_tiles.seed_package(src, dst, tiles, seed)
    print('seeded %d of %d planned tiles with 0x%X (%d already had low bits); wrote %s, verified' % (
        len(changed), len(tiles), seed, already, dst))


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ('plan', 'apply'):
        raise SystemExit(__doc__)
    if a[0] == 'plan':
        inv = None
        if '--inventory' in a:
            k = a.index('--inventory'); inv = a[k + 1]; del a[k:k + 2]
        if len(a) != 4:
            raise SystemExit('plan <spec.json> <map.upk> <plan.tsv> [--inventory <tsv>]')
        plan(a[1], a[2], a[3], inv)
    else:
        seed = seed_tiles.SEED_DEFAULT
        if '--seed' in a:
            k = a.index('--seed'); seed = int(a[k + 1], 0); del a[k:k + 2]
        if len(a) < 4:
            raise SystemExit('apply <map.upk> <out.upk> <plan.tsv> [...]')
        apply(a[1], a[2], a[3:], seed)


if __name__ == '__main__':
    main()
