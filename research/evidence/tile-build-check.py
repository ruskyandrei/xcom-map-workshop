"""Read-only: the game's tile build worked out from a map's pieces (tools/bake/tile_build.py and tile_rule.py)
against the map's bake (diagonal cover plan, stage C2; findings register F-152).

For every base map the install lists (tools/viewer/library.py donors), or the maps named: regions of tiles built from
nothing (pass 1 over the region and a margin of two tiles, then pass 2, in the build's order), each tile set beside
the bake:
- its static flags bit for bit, less the bits the passes here do not make (MASK: the stale 0x1, the 2-by-2 bit
  0x100000, the drop bit 0x200000, the edge bits 0x800000 to 0x4000000, water 0x8000000), and on a marked tile less
  its cover step's static bits (the seed makes them diagonal: diagonal-finder.py checks those);
- its floor record: there or not, its location (0.1 unit), its normal (0.001), its floor piece;
- its straight cover flags and location (0.15 unit), on the tiles the bake has no seed on.
The regions: the box round the map's marked tiles, if it has any, and SAMPLES boxes centred on tiles with pieces
near, picked by a generator seeded with the map's name. Each mismatch is counted by bit and kept as an example.

  python -B research/evidence/tile-build-check.py [<map.upk> ...] [--json <out>] [--jobs N] [--samples N]
"""
import argparse
import collections
import json
import random
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / 'tools'
for d in ('upk', 'viewer', 'bake'):
    sys.path.insert(0, str(TOOLS / d))

MASK = 0x1 | 0x100000 | 0x200000 | 0x7800000 | 0x8000000
COVER_STATIC = 0x2 | 0x4 | 0x8 | 0x10
MARGIN = 2
SAMPLES = 3
SIZE = (10, 10, 3)


def finder_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location('diagonal_finder', Path(__file__).parent / 'diagonal-finder.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def regions(baked, cover, name, samples):
    """[(x0, x1, y0, y1, z0, z1)]: the marked tiles' box, and boxes centred on tiles with pieces near."""
    dims = baked.dims
    out = []
    marked = [t for t, v in cover.items() if v & 0x10000]
    if marked:
        lo = [max(0, min(t[k] for t in marked) - (4 if k < 2 else 1)) for k in range(3)]
        hi = [min(dims[k] - 1, max(t[k] for t in marked) + (4 if k < 2 else 2)) for k in range(3)]
        out.append((lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
    near = sorted(t for t, v in baked.flags.items() if v & 0x20000 and 0 < t[2] < dims[2] - 1 or v & 0x20000 and t[2] == 0)
    rng = random.Random(name)
    for _ in range(samples if near else 0):
        c = rng.choice(near)
        b = [max(0, c[k] - SIZE[k] // 2) for k in range(3)]
        out.append((b[0], min(dims[0] - 1, b[0] + SIZE[0] - 1), b[1], min(dims[1] - 1, b[1] + SIZE[1] - 1),
                    b[2], min(dims[2] - 1, b[2] + SIZE[2] - 1)))
    return out


def build(world, baked, box):
    """The tiles of `box` and a margin built from nothing: (Tiles, {tile: straight cover result})."""
    import tile_build
    import tile_rule
    x0, x1, y0, y1, z0, z1 = box
    dims = baked.dims
    tiles = tile_rule.Tiles(baked.corner, dims, {}, {})
    # (two levels under: a floor's standing room marks the two tiles over it)
    order = [(x, y, z) for z in range(max(0, z0 - 2), min(dims[2], z1 + 2))
             for y in range(max(0, y0 - MARGIN), min(dims[1], y1 + MARGIN + 1))
             for x in range(max(0, x0 - MARGIN), min(dims[0], x1 + MARGIN + 1))]
    for t in order:
        tile_build.first_pass(world, tiles, t)
    near = {t: bool(tiles.flag(t) & tile_build.NEAR) for t in order}
    covers = {t: tile_build.second_pass(world, tiles, t, near[t]) for t in order}
    return tiles, covers


def check(path, samples=SAMPLES):
    import lighting_records as lighting
    import tile_world
    df = finder_module()
    t0 = time.time()
    p = lighting.Package(Path(path))
    try:
        baked, cover, locs = df.inputs(p)
    except (ValueError, KeyError) as e:
        return dict(map=Path(path).stem, error='%s: %s' % (type(e).__name__, e))
    world = tile_world.World(p)
    stats = collections.Counter()
    bits = collections.Counter()
    examples = collections.defaultdict(list)
    seen = set()
    boxes = regions(baked, cover, Path(path).stem, samples)
    for box in boxes:
        tiles, covers = build(world, baked, box)
        x0, x1, y0, y1, z0, z1 = box
        for t in [(x, y, z) for z in range(z0, z1 + 1) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]:
            if t in seen:
                continue
            seen.add(t)
            stats['tiles'] += 1
            marked = bool(cover.get(t, 0) & 0x10000)
            mask = MASK | (COVER_STATIC if marked else 0)
            a, b = baked.flag(t) & ~mask, tiles.flag(t) & ~mask
            stats['flags exact'] += a == b
            for k in range(28):
                m = 1 << k
                if (a ^ b) & m:
                    key = '%07x only in the %s' % (m, 'bake' if a & m else 'rule')
                    bits[key] += 1
                    if len(examples[key]) < 3:
                        examples[key].append([list(t), '%07x' % baked.flag(t), '%07x' % tiles.flag(t)])
            bf, rf = baked.floor.get(t), tiles.floor.get(t)
            if bf or rf:
                stats['floor records'] += 1
                if bf and rf:
                    same_loc = max(abs(bf['loc'][k] - rf['loc'][k]) for k in range(3)) <= 0.1
                    stats['floor exact'] += same_loc and getattr(rf['actor'], 'actor', None) == bf['actor']
                    stats['floor place exact'] += same_loc
                elif bf:
                    stats['floor only in the bake'] += 1
                    if len(examples['floor only in the bake']) < 3:
                        examples['floor only in the bake'].append([list(t), '%07x' % baked.flag(t)])
                else:
                    stats['floor only in the rule'] += 1
            if not marked and (cover.get(t) or covers.get(t) and covers[t]['flags']):
                stats['cover tiles'] += 1
                rc = covers.get(t)
                rflags = rc['flags'] if rc else 0
                same = rflags == cover.get(t, 0)
                if same and rflags:
                    loc = locs.get(t)
                    same = bool(loc and rc['location'] and max(abs(rc['location'][k] - loc[k]) for k in range(3)) <= 0.15)
                stats['cover exact'] += same
                if not same and len(examples['cover differs']) < 4:
                    examples['cover differs'].append([list(t), '%06x' % cover.get(t, 0), '%06x' % rflags])
    return dict(map=Path(path).stem, seconds=round(time.time() - t0, 1), regions=boxes, stats=dict(stats),
                bits=dict(bits.most_common()), examples=dict(examples))


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('maps', nargs='*', type=Path)
    a.add_argument('--json', type=Path)
    a.add_argument('--jobs', type=int, default=1)
    a.add_argument('--samples', type=int, default=SAMPLES)
    args = a.parse_args(argv)
    maps = args.maps
    if not maps:
        import library
        import settings
        game, _ = settings.game_install(settings.load_settings())
        maps = [Path(path) for _, role, path in library.donors(game) if role == 'base']
    out = []
    if args.jobs > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(args.jobs) as pool:
            for r in pool.map(check, maps, [args.samples] * len(maps)):
                out.append(r)
                report(r)
    else:
        for path in maps:
            r = check(path, args.samples)
            out.append(r)
            report(r)
    read = [r for r in out if 'error' not in r]
    total = collections.Counter()
    bits = collections.Counter()
    for r in read:
        total.update(r['stats'])
        bits.update(r['bits'])
    t = dict(total)
    print('all: %d maps, %d tiles; flags exact %.2f%%; floor records %d, exact %.2f%%; cover tiles %d, exact %.2f%%'
          % (len(read), t.get('tiles', 0), 100.0 * t.get('flags exact', 0) / max(t.get('tiles', 1), 1),
             t.get('floor records', 0), 100.0 * t.get('floor exact', 0) / max(t.get('floor records', 1), 1),
             t.get('cover tiles', 0), 100.0 * t.get('cover exact', 0) / max(t.get('cover tiles', 1), 1)))
    for k, v in bits.most_common(16):
        print('   %-26s %d' % (k, v))
    if args.json:
        args.json.write_text(json.dumps(dict(total=t, bits=dict(bits.most_common()), notRead=[r['map'] for r in out
                                                                                           if 'error' in r], maps=out),
                                        indent=1) + '\n', encoding='utf-8', newline='\n')
    return 0


def report(r):
    if 'error' in r:
        print('%-28s not read: %s' % (r['map'], r['error']))
        return
    s = r['stats']
    print('%-28s %4.0fs %5d tiles: flags %5.1f%%, floor %5.1f%%, cover %5.1f%% (%d)'
          % (r['map'], r['seconds'], s.get('tiles', 0), 100.0 * s.get('flags exact', 0) / max(s.get('tiles', 1), 1),
             100.0 * s.get('floor exact', 0) / max(s.get('floor records', 1), 1),
             100.0 * s.get('cover exact', 0) / max(s.get('cover tiles', 1), 1), s.get('cover tiles', 0)))


if __name__ == '__main__':
    sys.exit(main())
