"""Read-only: the Build's whole-tile writer (tools/bake/diagonal_keep.py, plan_whole) run on the game's own maps as
they are, each tile set beside the map's bake (diagonal cover plan, stage D2; findings register F-155).

plan_whole works a tile out whole as the game's full build would (passes 1 and 2, the link step, the ladders), the
tiles round it as the bake has them. On a map nobody changed, every tile it writes should come back as the bake has
it. For every base map the install lists (tools/viewer/library.py donors), or the maps named: every tile with
diagonal cover (worked out as seeded tiles), and SAMPLES floor tiles picked by a generator seeded with the map's
name (worked out as unseeded tiles), each compared:
- its static flags bit for bit (the bits no pass makes are the bake's own: diagonal_keep.KEPT_BITS);
- its cover flags bit for bit, its cover location to 0.15 unit;
- its floor record: there or not, its location (0.1 unit), its normal (0.001), its floor piece;
- its links, in order (target, cost, kinds, path object, positions to 0.1 unit).

  python -B research/evidence/whole-tile-check.py [<map.upk> ...] [--json <out>] [--jobs N] [--samples N]
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

SAMPLES = 40


def same_link(a, b):
    if tuple(a['to']) != tuple(b['to']) or list(a['types']) != list(b['types']) or a['obj'] != b['obj'] \
            or abs(a['cost'] - b['cost']) > 1e-3 or len(a['pos']) != len(b['pos']):
        return False
    return all(abs(u[k] - v[k]) <= 0.1 for u, v in zip(a['pos'], b['pos']) for k in range(3))


def near(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    return all(abs(a[k] - b[k]) <= tol for k in range(3))


def compare(ld, t, r):
    """{part: bool} for one written tile against the bake."""
    rec = ld.floors[t]['record'] if t in ld.floors else None
    out = dict(static=r['static'] == ld.flags.get(t, 0), cover=r['cover'] == ld.cover.get(t, 0),
               location=near(r['location'], ld.location.get(t), 0.15))
    f = r['floor']
    if f is None or rec is None:
        out['floor'] = f is None and rec is None
        out['links'] = out['floor']
    else:
        actor = ld.floors[t]['actor']
        actor = actor.actor if hasattr(actor, 'actor') else actor
        out['floor'] = near(f['loc'], rec['loc'], 0.1) and near(f['normal'], rec['normal'], 0.001) and f['actor'] == actor
        out['links'] = len(f['links']) == len(rec['links']) and all(same_link(a, b) for a, b in zip(f['links'],
                                                                                                    rec['links']))
    return out


def check(path, samples=SAMPLES):
    import diagonal_keep
    import lighting_records as lighting
    import native_copy
    t0 = time.time()
    p = lighting.Package(Path(path))
    try:
        ld = diagonal_keep.Loaded(p)
    except (ValueError, KeyError) as e:
        return dict(map=Path(path).stem, error='%s: %s' % (type(e).__name__, e))
    marked = set(native_copy.diagonal_tiles(p))
    floors = sorted(t for t, f in ld.flags.items() if f & 0x2000 and t in ld.floors and t not in marked
                    and all(0 <= t[k] < ld.dims[k] for k in range(3)))
    rng = random.Random(Path(path).stem)
    picked = rng.sample(floors, min(samples, len(floors)))
    out = dict(map=Path(path).stem)
    for group, tiles in (('marked', sorted(marked)), ('sampled', picked)):
        counts = collections.Counter()
        bits = collections.Counter()
        examples = []
        for t in tiles:
            if not all(0 <= t[k] < ld.dims[k] for k in range(3)):
                continue
            r = diagonal_keep.plan_whole(ld, {t}, marked, set())[t]
            c = compare(ld, t, r)
            counts['tiles'] += 1
            for k, v in c.items():
                counts[k] += v
            counts['whole'] += all(c.values())
            if not c['static']:
                diff = r['static'] ^ ld.flags.get(t, 0)
                for b in range(32):
                    if diff >> b & 1:
                        bits['0x%x %s' % (1 << b, 'written only' if r['static'] >> b & 1 else 'bake only')] += 1
            if not all(c.values()) and len(examples) < 4:
                examples.append(dict(tile=list(t), wrong=[k for k, v in c.items() if not v],
                                     static=['%07x' % r['static'], '%07x' % ld.flags.get(t, 0)],
                                     cover=['%06x' % r['cover'], '%06x' % ld.cover.get(t, 0)]))
        out[group] = dict(counts=dict(counts), bits=dict(bits.most_common()), examples=examples)
    out['seconds'] = round(time.time() - t0, 1)
    return out


def report(r):
    if 'error' in r:
        print('%-28s not read: %s' % (r['map'], r['error']))
        return
    parts = []
    for g in ('marked', 'sampled'):
        c = r[g]['counts']
        if c.get('tiles'):
            parts.append('%s %d whole %d (static %d cover %d loc %d floor %d links %d)' % (
                g, c['tiles'], c.get('whole', 0), c.get('static', 0), c.get('cover', 0), c.get('location', 0),
                c.get('floor', 0), c.get('links', 0)))
    print('%-28s %4.0fs %s' % (r['map'], r['seconds'], '; '.join(parts)))


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
        from functools import partial
        with ProcessPoolExecutor(args.jobs) as pool:
            for r in pool.map(partial(check, samples=args.samples), maps):
                out.append(r)
                report(r)
    else:
        for path in maps:
            r = check(path, args.samples)
            out.append(r)
            report(r)
    read = [r for r in out if 'error' not in r]
    total = dict(maps=len(out), notRead=[r['map'] for r in out if 'error' in r])
    for g in ('marked', 'sampled'):
        c, b = collections.Counter(), collections.Counter()
        for r in read:
            c.update(r[g]['counts'])
            b.update(r[g]['bits'])
        total[g] = dict(counts=dict(c), bits=dict(b.most_common()))
        print('all %s: %s' % (g, dict(c)))
        for k, v in b.most_common(12):
            print('   %-28s %d' % (k, v))
    if args.json:
        args.json.write_text(json.dumps(dict(total=total, maps=out), indent=1) + '\n', encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
