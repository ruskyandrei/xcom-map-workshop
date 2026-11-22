"""Read-only: the diagonal cover rule and finder (tools/bake/tile_rule.py) against the game's own maps (diagonal cover
plan, stage C1; findings register F-153).

For every base map the install lists (tools/viewer/library.py donors), or the maps named, with its baked tile data as
the inputs (static flags, floors), on every tile the build works cover out on (a floor, no ramp, not fully occupied):
- the game's answer: the bake's tiles whose cover flags carry 0x10000 (COVER_Diagonal), the tiles its designers
  marked with cover seeds;
- the rule: the diagonal cover the build would give each marked tile, set beside the bake (flags bit for bit, the
  cover location to 0.15 unit);
- the finder: which tiles it calls diagonal, marked or not;
- how the conditions the plan asked about (section 4.2) split marked from unmarked tiles: on every tile a diagonal
  passes on, five conditions counted (VARIANTS);
- each cover seed (XComCoverSeed, bDiagonalCover) with its tile and that tile's baked flags, so a seed that baked to
  nothing is explained.

  python -B research/evidence/diagonal-finder.py [<map.upk> ...] [--json <out>] [--jobs N]
"""
import argparse
import json
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / 'tools'
for d in ('upk', 'viewer', 'bake'):
    sys.path.insert(0, str(TOOLS / d))

# the conditions counted on every tile a diagonal passes on (r: the finder's answer with straight=True)
VARIANTS = (
    ('no straight cover', lambda r: not (r['straight'] or 0) & 0xF),
    ('and partly occupied', lambda r: not (r['straight'] or 0) & 0xF and r['partly']),
    ('and the wall at 45 degrees', lambda r: not (r['straight'] or 0) & 0xF and r['partly'] and r['facing'] >= 0.999),
    ('and high (the finder)', lambda r: r['diagonal']),
    ('partly, 45 degrees, high, straight or not', lambda r: r['partly'] and r['facing'] >= 0.999 and r['high']),
)


def inputs(p):
    """(Tiles from the map's bake, cover flags {tile: u32}, cover locations {tile: (x, y, z)})."""
    import native_copy
    import tile_rule
    import world_grid
    import world_links
    grid = native_copy.level_grid(p)
    _, blob = world_grid.container_of(p)
    wd = world_links.parse_container(blob)

    def store(k):
        return {t['tile']: t['value'] for c in wd['stores'][k]['chunks'] for t in c['tiles'] if t['present']}
    floor = {t: dict(loc=v['loc'], actor=v['actor']) for t, v in store(2).items()}
    tiles = tile_rule.Tiles((grid['tx'], grid['ty'], grid['tz']), wd['dims'], store(0), floor)
    return tiles, store(1), store(3)


def describe(world, tiles, tile, r):
    """A tile the finder or a mark names: its flags, each passing diagonal's wall (piece, mesh, facing, distance,
    high or low) and each straight direction's stopping step."""
    import numpy as np
    parts = {}
    p0 = tiles.position(tile)
    pieces = {pc.name: pc for pc in world.pieces}
    for name, d in r['cover']['parts'].items():
        pc = pieces.get(d['hit'])
        mesh = world.p.name(world.p.effective(_first_component(world.p, pc.actor), 'StaticMesh', 0) or 0) if pc else ''
        parts[name] = dict(piece=d['hit'], cls=pc.cls if pc else None, mesh=mesh.split('.')[-1], facing=d['facing'],
                           low=d['low'], wall=round(float(np.hypot(d['wall'][0] - p0[0], d['wall'][1] - p0[1])), 1))
    return dict(tile=list(tile), flags='%06x' % tiles.flag(tile), cover='%06x' % r['cover']['flags'],
                straight='%06x' % r['straight'] if r['straight'] is not None else None, partly=r['partly'],
                parts=parts, straightNotes=r['notes']['straight'])


def _first_component(p, actor):
    import tile_world
    stack = list(p.children.get(actor, []))
    while stack:
        c = stack.pop()
        stack.extend(p.children.get(c, []))
        if p.cls(c) in tile_world.MESH_COMPONENTS and (p.effective(c, 'StaticMesh', 0) or 0) > 0:
            return c
    return 0


def check(path):
    """One map's record."""
    import lighting_records as lighting
    import tile_rule
    import tile_world
    t0 = time.time()
    p = lighting.Package(Path(path))
    try:
        tiles, cover, locs = inputs(p)
    except (ValueError, KeyError) as e:
        return dict(map=Path(path).stem, error='%s: %s' % (type(e).__name__, e))
    world = tile_world.World(p)
    baked = {t for t, v in cover.items() if v & tile_rule.DIAGONAL}
    marked, extra, scanned = [], [], 0
    variants = {name: [0, 0] for name, _ in VARIANTS}       # [marked, unmarked] tiles a diagonal passes on
    for tile in sorted(tiles.floor, key=lambda t: (t[2], t[1], t[0])):
        if not tile_rule.candidate(tiles, tile):
            if tile in baked:
                marked.append(dict(tile=list(tile), baked='%06x' % cover[tile], flags='%06x' % tiles.flag(tile),
                                   rule=None, why='no floor of its own: the seed sets the flag, no cover is worked out'))
            continue
        scanned += 1
        r = tile_rule.finder(world, tiles, tile, straight=True)
        if r['cover']['parts']:
            for name, test in VARIANTS:
                if test(r):
                    variants[name][0 if tile in baked else 1] += 1
        if tile in baked:
            c = r['cover']
            loc = locs.get(tile)
            off = max(abs(c['location'][k] - loc[k]) for k in range(3)) if c['location'] and loc else None
            marked.append(dict(describe(world, tiles, tile, r), baked='%06x' % cover[tile], rule='%06x' % c['flags'],
                               exact=c['flags'] == cover[tile] and (off is None and loc is None and not c['location']
                                                                     or off is not None and off <= 0.15),
                               location=round(off, 2) if off is not None else None, finder=r['diagonal']))
        elif r['diagonal']:
            extra.append(describe(world, tiles, tile, r))
    for tile in sorted(baked - set(tiles.floor)):
        marked.append(dict(tile=list(tile), baked='%06x' % cover[tile], rule=None, why='no floor record'))
    seeds = []
    level = p.by_name['TheWorld.PersistentLevel']
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) == 'XComCoverSeed' and p.exports[i - 1]['outer'] == level:
            at = p.own(i, 'Location', [0.0, 0.0, 0.0])
            t = tiles.at(at)
            seeds.append(dict(name=p.name(i).split('.')[-1], location=[round(v, 1) for v in at], tile=list(t),
                              diagonal=bool(p.effective(i, 'bDiagonalCover', False)), inGrid=tiles.inside(t),
                              flags='%06x' % tiles.flag(t), baked=t in baked))
    return dict(map=Path(path).stem, seconds=round(time.time() - t0, 1), scanned=scanned, world=world.counts,
                assumed=len(world.resolver.assumed), baked=len(baked), marked=marked, extra=extra,
                variants=variants, seeds=seeds)


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('maps', nargs='*', type=Path)
    a.add_argument('--json', type=Path)
    a.add_argument('--jobs', type=int, default=1)
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
            for r in pool.map(check, maps):
                out.append(r)
                report(r)
    else:
        for path in maps:
            r = check(path)
            out.append(r)
            report(r)
    read = [r for r in out if 'error' not in r]
    marks = [m for r in read for m in r['marked']]
    total = dict(maps=len(out), notRead=[r['map'] for r in out if 'error' in r], marked=len(marks),
                 worked=sum(1 for m in marks if m.get('rule') is not None),
                 exact=sum(1 for m in marks if m.get('exact')), finder=sum(1 for m in marks if m.get('finder')),
                 extra=sum(len(r['extra']) for r in read),
                 extraMaps=sum(1 for r in read if r['extra']),
                 variants={name: [sum(r['variants'][name][k] for r in read) for k in (0, 1)] for name, _ in VARIANTS},
                 seeds=sum(len(r['seeds']) for r in read),
                 seedsOutside=sum(1 for r in read for s in r['seeds'] if not s['inGrid']))
    print('all: %(maps)d maps; %(marked)d marked tiles, %(worked)d with cover worked out, %(exact)d exact; the finder '
          'takes %(finder)d of them and %(extra)d unmarked tiles on %(extraMaps)d maps' % total)
    for name, (m, u) in total['variants'].items():
        print('  %-44s marked %3d, unmarked %5d' % (name, m, u))
    print('  seeds %(seeds)d, outside the grid %(seedsOutside)d' % total)
    if args.json:
        args.json.write_text(json.dumps(dict(total=total, maps=out), indent=1) + '\n', encoding='utf-8', newline='\n')
    return 0


def report(r):
    if 'error' in r:
        print('%-28s not read: %s' % (r['map'], r['error']))
        return
    exact = sum(1 for m in r['marked'] if m.get('exact'))
    worked = sum(1 for m in r['marked'] if m.get('rule') is not None)
    finder = sum(1 for m in r['marked'] if m.get('finder'))
    print('%-28s %4.0fs %6d tiles: marked %2d (%2d worked out, %2d exact), finder takes %2d of them and %3d others'
          % (r['map'], r['seconds'], r['scanned'], r['baked'], worked, exact, finder, len(r['extra'])))


if __name__ == '__main__':
    sys.exit(main())
