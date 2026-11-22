"""Read-only: a map's diagonal cover (cover flag 0x10000, COVER_Diagonal), in its bake and after a battle's tile rebuild
(findings register F-149).

  python -B research/evidence/diagonal-cover.py maps <map.upk> ... [--json <out>]
        per map: its XComCoverSeed actors (how many with bDiagonalCover), the tiles of its baked cover store that
        carry 0x10000, each with the seed standing in it, and the rebuild volumes (XComRebuildWorldDataVolume) of its
        level that reach it. A volume's reach is the cube the battle rebuilds for it: its bounds' centre, the bounds'
        sphere radius either way on every axis (XGBattle.DoWorldDataRebuild), the sphere the brush's own times
        the volume's largest scale (native_copy.volume_sphere, F-150).
  python -B research/evidence/diagonal-cover.py save <save> <map.upk> [--level <z> ...] [--draw]
        a tactical save of a battle on that map against the map's bake: the static and cover flags of every tile that
        differ, counted by level, and each baked diagonal tile's flags before and after. --draw adds a picture of each
        level's changed tiles (s static, c cover, b both; a capital, or D, on a baked diagonal tile).

The save's tile stores lie in the layout the map's XComWorldDataContainer has (tools/lab/save_tiles.py finds the
static store; the cover store follows it). Nothing is written but --json's file.
"""
import argparse
import json
import math
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / 'tools'
for d in ('upk', 'viewer', 'bake', 'lab'):
    sys.path.insert(0, str(TOOLS / d))
import native_copy  # noqa: E402
import save_tiles  # noqa: E402
import world_grid  # noqa: E402
from package import Package  # noqa: E402

DIAGONAL = 0x10000
STATIC, COVER = 0, 1        # the container's first two stores (world_links.NAMES)


def baked(p):
    """(dims, {tile: static flags}, {tile: cover flags}) of a map's baked tile data, present tiles only."""
    _, blob = world_grid.container_of(p)
    model = world_grid.decode(blob)
    words = lambda k: {t: struct.unpack('<I', raw)[0] for t, (raw, present) in model['stores'][k].items() if present}  # noqa: E731
    return model['dims'], words(STATIC), words(COVER)


def tile_of(grid, at):
    return (int((at[0] - grid['tx']) // 96), int((at[1] - grid['ty']) // 96), int((at[2] - grid['tz']) // 64))


def map_report(path):
    p = Package(str(path))
    grid = native_copy.level_grid(p)
    dims, _, cover = baked(p)
    level = p.by_name['TheWorld.PersistentLevel']
    _, _, listed = native_copy.actor_list(p)
    listed = set(listed)
    seeds, volumes = [], []
    for i in range(1, len(p.exports) + 1):
        if p.exports[i - 1]['outer'] != level or i not in listed:
            continue
        name = p.name(i).rsplit('.', 1)[-1]
        if p.cls(i) == 'XComCoverSeed':
            at = p.own(i, 'Location', [0.0, 0.0, 0.0])
            seeds.append(dict(name=name, location=at, diagonal=bool(p.effective(i, 'bDiagonalCover', False)),
                              tile=tile_of(grid, at)))
        elif p.cls(i) == 'XComRebuildWorldDataVolume':
            centre, radius = native_copy.volume_sphere(p, i)
            volumes.append(dict(name=name, centre=centre, radius=radius))
    tiles = []
    for t in sorted(t for t, f in cover.items() if f & DIAGONAL):
        centre = [grid['tx'] + (t[0] + .5) * 96, grid['ty'] + (t[1] + .5) * 96, grid['tz'] + (t[2] + .5) * 64]
        tiles.append(dict(tile=list(t), cover='%06x' % cover[t], seed=[s['name'] for s in seeds if s['tile'] == t],
                          rebuiltBy=[v['name'] for v in volumes
                                     if all(abs(centre[k] - v['centre'][k]) <= v['radius'] for k in range(3))]))
    on = {tuple(t['tile']) for t in tiles}
    return dict(map=Path(path).stem, grid=list(dims), seeds=len(seeds), diagonalSeeds=sum(s['diagonal'] for s in seeds),
                diagonalTiles=len(tiles), rebuildVolumes=len(volumes),
                diagonalTilesRebuilt=sum(1 for t in tiles if t['rebuiltBy']), tiles=tiles,
                seedsOffDiagonalTiles=[dict(name=s['name'], tile=list(s['tile']), diagonal=s['diagonal'])
                                       for s in seeds if s['tile'] not in on])


def flag_store(blob, at):
    """A flags store saved at `at`: ({tile: flags} of its present tiles, the offset after it)."""
    _, n = struct.unpack_from('<II', blob, at)
    at += 8 + 4 * n + 12
    out = {}
    for _ in range(n):
        _, _, x, y, z, m = struct.unpack_from('<IIiiiI', blob, at)
        if m != 18:
            raise ValueError('not a flags store: a chunk of %d tiles at %d' % (m, at))
        at += 24
        for i in range(m):
            f, present = struct.unpack_from('<IB', blob, at + 5 * i)
            if present:
                out[(x + i % 3, y + (i // 3) % 3, z + i // 9)] = f
        at += 5 * m
    return out, at


def save_report(save, path, levels=(), draw=False):
    dims, b_static, b_cover = baked(Package(str(path)))
    blob = save_tiles.decompress(Path(save).read_bytes())
    chunks = math.prod(-(-dims[k] // (3, 3, 2)[k]) for k in range(3))
    first = save_tiles.static_store(blob, dims, chunks)
    s_static, end = flag_store(blob, first['chunks'][0]['off'] - 12 - 4 * chunks - 8)
    s_cover, _ = flag_store(blob, end)
    count = lambda cover: sum(1 for f in cover.values() if f & DIAGONAL)  # noqa: E731
    print('%s: %d x %d x %d tiles; cover tiles with 0x10000: baked %d, in the save %d'
          % ((Path(path).stem,) + tuple(dims) + (count(b_cover), count(s_cover))))
    show = lambda store, t: '%06x' % store[t] if t in store else '--'  # noqa: E731
    for z in levels or range(dims[2]):
        ch = {t for t in set(b_static) | set(s_static) if t[2] == z and b_static.get(t) != s_static.get(t)}
        cc = {t for t in set(b_cover) | set(s_cover) if t[2] == z and b_cover.get(t) != s_cover.get(t)}
        if not ch and not cc:
            continue
        print('level %d: static flags changed on %d tiles, cover flags on %d' % (z, len(ch), len(cc)))
        if draw:
            pts = ch | cc | {t for t, f in b_cover.items() if t[2] == z and f & DIAGONAL}
            xs, ys = [t[0] for t in pts], [t[1] for t in pts]
            print('  x %d..%d, y %d down to %d' % (min(xs), max(xs), max(ys), min(ys)))
            for y in range(max(ys), min(ys) - 1, -1):
                row = ''
                for x in range(min(xs), max(xs) + 1):
                    t = (x, y, z)
                    mark = 'b' if t in ch and t in cc else 's' if t in ch else 'c' if t in cc else '.'
                    if b_cover.get(t, 0) & DIAGONAL:
                        mark = 'D' if mark == '.' else mark.upper()
                    row += mark
                print('  ' + row)
        for t in sorted(t for t, f in b_cover.items() if t[2] == z and f & DIAGONAL):
            print('  diagonal tile %s: static %s -> %s, cover %s -> %s'
                  % (t, show(b_static, t), show(s_static, t), show(b_cover, t), show(s_cover, t)))


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = a.add_subparsers(dest='what', required=True)
    m = sub.add_parser('maps')
    m.add_argument('maps', nargs='+', type=Path)
    m.add_argument('--json', type=Path)
    s = sub.add_parser('save')
    s.add_argument('save', type=Path)
    s.add_argument('map', type=Path)
    s.add_argument('--level', action='append', type=int, default=[])
    s.add_argument('--draw', action='store_true')
    args = a.parse_args(argv)
    if args.what == 'save':
        save_report(args.save, args.map, args.level, args.draw)
        return 0
    reports = [map_report(path) for path in args.maps]
    for r in reports:
        print('%-28s seeds %2d (diagonal %2d), baked diagonal tiles %2d, rebuild volumes %3d reaching %d of them'
              % (r['map'], r['seeds'], r['diagonalSeeds'], r['diagonalTiles'], r['rebuildVolumes'],
                 r['diagonalTilesRebuilt']))
    if args.json:
        args.json.write_text(json.dumps(dict(maps=reports), indent=1) + '\n', encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
