"""Read-only: the game's neighbour links (each floor tile's Neighbors list) worked out by the reading of the exe in
research/native/neighbour-links.md, against the game's own maps' bakes.

For every base map the install lists (tools/viewer/library.py donors), or the maps named, with the map's baked tile
data as the inputs (static flags, cover flags, floor records, cover locations, interact points) and its pieces
(tools/bake/tile_world.py) for the build's traces, every floor tile's links are predicted in the build's order and
set beside the bake's:
- links predicted, baked, matched exactly (target, cost to 0.001, traversal types, path object, positions to 0.1
  unit), tiles whose whole list matches (in order, and as a set);
- per kind (plain, ClimbOver, ClimbOnto, KickDoor, DropDown, JumpUp, WallClimb, ClimbLadder), the same counts;
- every miss with its cause (which condition of the reading decided it), grouped, with a few examples each;
- the static bits the same function writes: 0x100000 (2 x 2 standing room) and 0x200000 (the drop search went two
  levels down), predicted against the bake.

  python -B research/evidence/neighbour-links-check.py [<map.upk> ...] [--json <out>] [--jobs N] [--examples N]
"""
import argparse
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parents[2] / 'tools'
for d in ('upk', 'viewer', 'bake'):
    sys.path.insert(0, str(TOOLS / d))

# the reading itself is tools/bake/tile_links.py (its one home); this script sets it beside the bakes
from tile_links import (  # noqa: E402,F401
    TILE, FLOOR, RAMP, OCCUPIED, PARTLY, UP_BLOCKED, DOWN_BLOCKED, STAND2X2, DROP2, NORMAL, CLIMB_OVER, CLIMB_ONTO,
    LADDER, DROP_DOWN, LANDING, KICK_DOOR, WALL_CLIMB, JUMP_UP, NAMES, DIRS, DIAGONAL_SWEEP, DESTRUCTIBLE, full,
    Map, link, Predictor)


class Suspects:
    """What the reading's sweep does not model near a diagonal it got wrong (for the misses' causes only): every
    level actor's mesh component the 'engine' trace does not meet (not colliding, not world geometry, no BodySetup),
    by its mesh's bounds box placed as UE3 places it; fracturing pieces (their fragments are not read); actors with a
    skeletal mesh component (not read), by their location."""

    def __init__(self, world, p):
        import lightmap_texels
        import native_copy
        import tile_world
        self.items = []
        modelled = {pc.actor: pc for pc in world.pieces}
        rv = world.resolver
        for a in native_copy.level_actors(p):
            if a <= 0:
                continue
            cls = p.cls(a)
            if cls.endswith('Volume') or cls in ('WorldInfo',):
                continue
            pc = modelled.get(a)
            comps = list(tile_world.World._components(world, a))
            stack, skeletal = list(p.children.get(a, [])), False
            while stack:
                c = stack.pop()
                stack.extend(p.children.get(c, []))
                skeletal = skeletal or p.cls(c) == 'SkeletalMeshComponent'
            if skeletal:
                loc = np.array(p.effective(a, 'Location', [0.0, 0.0, 0.0]) or [0.0, 0.0, 0.0], float)
                self.items.append((loc - 96.0, loc + 96.0, 'skeletal mesh (%s)' % cls))
            if pc is not None and cls in tile_world.FRAC_FAMILY:
                for lo, hi in pc.bounds:
                    self.items.append((lo, hi, 'fracturing piece (its fragments are not read)'))
                continue
            if pc is not None and pc.engine_box:
                continue
            for c in comps:
                colliding = rv.value(a, 'bCollideActors', False) and rv.value(c, 'CollideActors', False)
                why = ('not colliding' if not colliding else
                       'not world geometry' if not rv.value(a, 'bWorldGeometry', False) else
                       'no BodySetup or not blocking a box')
                try:
                    mtx = lightmap_texels.world_matrix(p, c)
                except (ValueError, KeyError, IndexError):
                    continue
                ox, oy, oz, ex, ey, ez, _ = p.native(p.effective(c, 'StaticMesh', 0)).unpack('7f')
                corners = np.array([[ox + sx * ex, oy + sy * ey, oz + sz * ez] for sx in (-1, 1) for sy in (-1, 1)
                                    for sz in (-1, 1)]) @ mtx[:3, :3].T + mtx[:3, 3]
                if (corners.max(0) - corners.min(0))[:2].max() > 20000.0:
                    continue        # a sky dome
                self.items.append((corners.min(0), corners.max(0), 'mesh %s (%s)' % (why, cls)))

    ORDER = ('skeletal', 'fracturing', 'mesh not world', 'mesh no', 'mesh not colliding (S', 'mesh not colliding')

    def near(self, a, b):
        """The likeliest thing near a sweep that the reading does not model (by ORDER), or 'nothing'."""
        ext = np.array(DIAGONAL_SWEEP)
        lo, hi = np.minimum(a, b) - ext, np.maximum(a, b) + ext
        found = {label for l, h, label in self.items if (l <= hi).all() and (h >= lo).all()}
        for head in self.ORDER:
            for label in sorted(found):
                if label.startswith(head):
                    return label
        return 'nothing'


def hit_kind(h):
    """A false block's hit, in words: its piece's class, and how it met the sweep."""
    nz = h['normal'][2]
    how = ('starting inside it' if h['inside'] else 'a face looking up' if nz > 0.7 else
           'a face looking down' if nz < -0.7 else 'a side face')
    return '%s, %s' % (h['piece'].cls, how)


def same(a, b):
    if a['to'] != b['to'] or a['types'] != b['types'] or a['obj'] != b['obj'] or abs(a['cost'] - b['cost']) > 1e-3:
        return False
    if len(a['pos']) != len(b['pos']):
        return False
    return all(abs(u[k] - v[k]) <= 0.1 for u, v in zip(a['pos'], b['pos']) for k in range(3))


def kind(l):
    return NAMES.get(tuple(l['types']), str(tuple(l['types'])))


def check(path, examples=6):
    """One map's record."""
    import lighting_records as lighting
    import tile_world
    t0 = time.time()
    p = lighting.Package(Path(path))
    try:
        m = Map(p)
    except (ValueError, KeyError) as e:
        return dict(map=Path(path).stem, error='%s: %s' % (type(e).__name__, e))
    world = tile_world.World(p)
    pr = Predictor(m, world, p)
    # (a grid of odd NZ saves a level z = NZ in its static store, its last chunks being two levels high; those tiles
    # have flags, floors among them, but no floor records and no links: the link step reads inside the grid only)
    order = sorted((t for t, f in m.static.items() if f & FLOOR and m.inside(t)), key=lambda t: (t[2], t[1], t[0]))
    lists = {t: pr.tile(t) for t in order}
    pr.ladders(lists)
    baked = {t: [link(l['to'], l['cost'], l['types'], l['obj'], l['pos']) for l in m.floor[t]['links']]
             for t in m.floor}
    counts = Counter()
    per_kind = defaultdict(Counter)
    misses = defaultdict(list)
    why = {(t, n): c for t, n, k, c in pr.why}
    found = []

    def suspects():
        if not found:
            found.append(Suspects(world, p))
        return found[0]
    tiles_exact = tiles_set = 0
    for t in sorted(set(lists) | {t for t, v in baked.items() if v}, key=lambda t: (t[2], t[1], t[0])):
        pred, bake = lists.get(t, []), baked.get(t, [])
        if len(pred) == len(bake) and all(same(a, b) for a, b in zip(pred, bake)):
            tiles_exact += 1
        left = list(bake)
        unmatched = []
        for a in pred:
            j = next((j for j, b in enumerate(left) if same(a, b)), None)
            counts['predicted'] += 1
            per_kind[kind(a)]['predicted'] += 1
            if j is None:
                unmatched.append(a)
            else:
                counts['matched'] += 1
                per_kind[kind(a)]['matched'] += 1
                left.pop(j)
        for b in bake:
            counts['baked'] += 1
            per_kind[kind(b)]['baked'] += 1
        if not unmatched and not left:
            tiles_set += 1
        for a in unmatched:
            # the same link with another position or object: a near miss, else a link the bake does not have
            near = next((b for b in left if b['to'] == a['to'] and b['types'] == a['types']), None)
            if near is not None:
                left.remove(near)
                cause = '%s: target and types match, %s differ' % (kind(a), ', '.join(
                    w for w, bad in (('object', a['obj'] != near['obj']), ('cost', abs(a['cost'] - near['cost']) > 1e-3),
                                     ('positions', not same(dict(a, obj=0, cost=0), dict(near, obj=0, cost=0))))
                    if bad))
                misses[cause].append(dict(tile=t, predicted=a, baked=near))
                continue
            cause = '%s predicted, not baked' % kind(a)
            if kind(a) == 'plain':
                n = a['to']
                if abs(n[0] - t[0]) + abs(n[1] - t[1]) == 2:
                    near = suspects().near(*pr.sweeps[(t, n)][:2])
                    cause += ': diagonal, the sweep met nothing; near it, not modelled: %s' % near
                else:
                    cause += ': straight'
            misses[cause].append(dict(tile=t, predicted=a))
        for b in left:
            cause = '%s baked, not predicted' % kind(b)
            if kind(b) == 'plain':
                n = b['to']
                c = why.get((t, n))
                if c is None:
                    c = ('no floor on the target' if not m.flag(n) & FLOOR else
                         'not tried (dz beyond 1 or not a neighbour)')
                elif c == 'diagonal sweep':
                    c = 'the diagonal sweep met %s' % hit_kind(pr.sweeps[(t, n)][2])
                cause += ': %s' % c
            misses[cause].append(dict(tile=t, baked=b))
    # the static bits
    bits = {}
    stand = {t for t in m.static if m.inside(t) and pr.stand2x2(t)}
    flagged = {t for t, f in m.static.items() if f & STAND2X2 and m.inside(t)}
    bits['0x100000'] = dict(both=len(stand & flagged), ruleOnly=len(stand - flagged), flagOnly=len(flagged - stand),
                            examples=dict(ruleOnly=[list(t) for t in sorted(stand - flagged)[:examples]],
                                          flagOnly=[list(t) for t in sorted(flagged - stand)[:examples]]))
    flagged = {t for t, f in m.static.items() if f & DROP2 and m.inside(t)}
    drop = pr.drop_bits
    bits['0x200000'] = dict(both=len(drop & flagged), ruleOnly=len(drop - flagged), flagOnly=len(flagged - drop),
                            examples=dict(ruleOnly=[list(t) for t in sorted(drop - flagged)[:examples]],
                                          flagOnly=[list(t) for t in sorted(flagged - drop)[:examples]]))

    def short(e):
        out = dict(tile=list(e['tile']))
        for k in ('predicted', 'baked'):
            if k in e:
                l = e[k]
                out[k] = dict(to=list(l['to']), cost=round(l['cost'], 3), types=kind(l), obj=l['obj'],
                              pos=[[round(c, 1) for c in q] for q in l['pos']])
                sw = pr.sweeps.get((tuple(e['tile']), tuple(l['to'])))
                if sw is not None:
                    a, b, h = sw
                    out['sweep'] = dict(start=[round(float(v), 1) for v in a], end=[round(float(v), 1) for v in b],
                                        hit=None if h is None else dict(
                                            piece=h['piece'].name, cls=h['piece'].cls, time=round(float(h['time']), 3),
                                            inside=bool(h['inside']),
                                            normal=[round(float(v), 2) for v in h['normal']]))
        return out
    return dict(map=Path(path).stem, seconds=round(time.time() - t0, 1), dims=list(m.dims), floorTiles=len(order),
                world=world.counts, links=dict(counts), tilesExact=tiles_exact, tilesSet=tiles_set,
                tiles=len(set(lists) | {t for t, v in baked.items() if v}),
                kinds={k: dict(v) for k, v in sorted(per_kind.items())},
                misses={c: dict(count=len(v), examples=[short(e) for e in v[:examples]])
                        for c, v in sorted(misses.items(), key=lambda kv: -len(kv[1]))},
                bits=bits, notes=dict(pr.notes))


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('maps', nargs='*', type=Path)
    a.add_argument('--json', type=Path)
    a.add_argument('--jobs', type=int, default=1)
    a.add_argument('--examples', type=int, default=6)
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
        from functools import partial
        with ProcessPoolExecutor(args.jobs) as pool:
            for r in pool.map(partial(check, examples=args.examples), maps):
                out.append(r)
                report(r)
    else:
        for path in maps:
            r = check(path, args.examples)
            out.append(r)
            report(r)
    read = [r for r in out if 'error' not in r]
    total = dict(maps=len(out), notRead=[r['map'] for r in out if 'error' in r])
    for k in ('predicted', 'baked', 'matched'):
        total[k] = sum(r['links'].get(k, 0) for r in read)
    total['tiles'] = sum(r['tiles'] for r in read)
    total['tilesExact'] = sum(r['tilesExact'] for r in read)
    total['tilesSet'] = sum(r['tilesSet'] for r in read)
    kinds = defaultdict(Counter)
    causes = Counter()
    bits = defaultdict(Counter)
    for r in read:
        for k, v in r['kinds'].items():
            kinds[k].update(v)
        for c, v in r['misses'].items():
            causes[c] += v['count']
        for b, v in r['bits'].items():
            bits[b].update({k: v[k] for k in ('both', 'ruleOnly', 'flagOnly')})
    total['kinds'] = {k: dict(v) for k, v in sorted(kinds.items())}
    total['misses'] = dict(causes.most_common())
    total['bits'] = {k: dict(v) for k, v in bits.items()}
    notes = Counter()
    for r in read:
        notes.update(r['notes'])
    total['notes'] = dict(sorted(notes.items()))
    print('all: %d maps; links baked %d, predicted %d, matched %d (%.2f%% of baked); tiles %d, exact in order %d, '
          'as a set %d' % (total['maps'], total['baked'], total['predicted'], total['matched'],
                           100.0 * total['matched'] / max(total['baked'], 1), total['tiles'], total['tilesExact'],
                           total['tilesSet']))
    for k, v in total['kinds'].items():
        print('  %-12s baked %6d predicted %6d matched %6d' % (k, v.get('baked', 0), v.get('predicted', 0),
                                                             v.get('matched', 0)))
    for c, n in list(total['misses'].items())[:30]:
        print('  %6d  %s' % (n, c))
    for b, v in total['bits'].items():
        print('  bit %s: both %d, rule only %d, flag only %d' % (b, v['both'], v['ruleOnly'], v['flagOnly']))
    for k, v in total['notes'].items():
        print('  note: %s: %d' % (k, v))
    if args.json:
        args.json.write_text(json.dumps(dict(total=total, maps=out), indent=1) + '\n', encoding='utf-8', newline='\n')
    return 0


def report(r):
    if 'error' in r:
        print('%-28s not read: %s' % (r['map'], r['error']))
        return
    c = r['links']
    print('%-28s %4.0fs baked %6d predicted %6d matched %6d (%.2f%%); tiles %5d exact %5d; 0x100000 %d/%d/%d, '
          '0x200000 %d/%d/%d' % (r['map'], r['seconds'], c.get('baked', 0), c.get('predicted', 0), c.get('matched', 0),
                                 100.0 * c.get('matched', 0) / max(c.get('baked', 1), 1), r['tiles'], r['tilesExact'],
                                 *[r['bits'][b][k] for b in ('0x100000', '0x200000')
                                   for k in ('both', 'ruleOnly', 'flagOnly')]))


if __name__ == '__main__':
    sys.exit(main())
