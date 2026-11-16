"""How the maps of an install set the piece flags (piece flags plan, stage P0; research/native/piece-flags.md): a
read-only survey of every placed piece's five settings as tools/viewer/piece_flags.py resolves them.

  python -B tools/upk/audit_piece_flags.py <game install> <out.json> [--jobs 6] [--only NAME]

The maps are those the editor lists (library.donors: one package per listed map, the base maps; their streamed
patches are not read). Each actor of the persistent level is counted once, whatever its components. Counted per map
and in all:
- actors by family (piece_flags.CLASSES), and each role's state among them;
- drawn, colliding pieces (a mesh, not bHidden nor HiddenGame, colliding: piece_flags.collides) with walking off, with
  cover off, with walking, cover and sight all off (Floor apart), and of those the ones the mouse skips;
- props saving or inheriting bIgnoreForPathing, and those with walking and cover off too;
- pieces whose mesh's short name holds "TV": their role states by mesh and map, the maps whose TVs are set more than
  one way and those where one TV mesh is;
- ladders (XComLadder): sight off, and walking, cover and sight off;
- where each setting came from (actor, archetype, class, table, assumed), and the actors with an archetype in another
  package that the map doesn't carry (their values assumed from the class);
- the values that could not be read (unknown).
Every map's file name, size and SHA-256 are in the output, so a later run can say whether it read the same files.
"""
import argparse
import collections
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import sys

REPO = str(Path(__file__).resolve().parents[2])
PL = 'TheWorld.PersistentLevel.'


def setup(repo):
    for folder in ('tools/upk', 'tools/viewer'):
        sys.path.insert(0, os.path.join(repo, folder))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def mesh_names(p, actor):
    """The short names of the meshes under an actor."""
    out = []

    def under(i):
        for c in p.children.get(i, []):
            yield c
            yield from under(c)
    for c in under(actor):
        if p.cls(c) in ('StaticMeshComponent', 'FracturedStaticMeshComponent', 'XComMapEdMeshComponent'):
            m = p.effective(c, 'StaticMesh', 0) or 0
        elif p.cls(c) == 'SkeletalMeshComponent':
            m = p.effective(c, 'SkeletalMesh', 0) or 0
        else:
            continue
        if m:
            out.append(p.name(m).split('.')[-1])
    return out


def drawn(p, actor):
    """Whether the actor draws in the game: not bHidden, and a mesh component not HiddenGame."""
    if p.effective(actor, 'bHidden', False):
        return False

    def under(i):
        for c in p.children.get(i, []):
            yield c
            yield from under(c)
    return any(not p.effective(c, 'HiddenGame', False) for c in under(actor)
               if 'MeshComponent' in p.cls(c) and ((p.effective(c, 'StaticMesh', 0) or 0) or (p.effective(c, 'SkeletalMesh', 0) or 0)))


def survey(job):
    repo, name, path = job
    setup(repo)
    import piece_flags as pf
    from package import Package
    p = Package(Path(path))
    families, states = collections.Counter(), collections.Counter()
    sources, unknown = collections.Counter(), collections.Counter()
    c = collections.Counter()
    tvs = collections.defaultdict(collections.Counter)
    unresolved = []
    for i, full in enumerate(p.paths, 1):
        if not (full.startswith(PL) and full.count('.') == 2) or full.rsplit('.', 1)[-1].startswith('Default__'):
            continue
        r = pf.resolve(p, i)
        if r['family'] is None:
            continue
        families[r['family']] += 1
        for prop, s in r['source'].items():
            sources[s] += 1
            if r['raw'][prop] is None:
                unknown[prop] += 1
        if any(s == 'assumed' for s in r['source'].values()):
            unresolved.append(full.rsplit('.', 1)[-1])
        st = pf.states(r['cls'], r['raw'])
        for role, v in st.items():
            states['%s|%s|%s' % (r['family'], role, v)] += 1
        meshes = mesh_names(p, i)
        if not meshes:
            continue
        seen = drawn(p, i) and pf.collides(p, i)
        if seen:
            c['drawnColliding'] += 1
            if st['walking'] == 'off':
                c['walkingOff'] += 1
            if st['cover'] == 'off':
                c['coverOff'] += 1
            if all(st[k] in ('off', 'n/a') for k in ('walking', 'cover', 'sight')) and r['family'] != 'plain':
                c['threeOff'] += 1
                c['threeOffMeshes|' + meshes[0]] += 1
                if st['mouse'] == 'off':
                    c['threeOffMouseOff'] += 1
        if r['family'] in pf.GATED and r['raw'].get('bIgnoreForPathing'):
            c['gate'] += 1
            if st['walking'] == 'off' and st['cover'] == 'off':
                c['gateWalkingCoverOff'] += 1
        if r['cls'] == 'XComLadder':
            c['ladders'] += 1
            if st['sight'] == 'off':
                c['laddersSightOff'] += 1
            if all(st[k] in ('off', 'n/a') for k in ('walking', 'cover', 'sight')):
                c['laddersThreeOff'] += 1
        for m in meshes:
            if 'TV' in m:
                tvs[m]['%s|%s|%s|%s' % (st['walking'], st['cover'], st['sight'], st['mouse'])] += 1
                break
    mesh3 = {k.split('|', 1)[1]: v for k, v in c.items() if k.startswith('threeOffMeshes|')}
    counts = {k: v for k, v in c.items() if not k.startswith('threeOffMeshes|')}
    return dict(map=name, file=Path(path).name, size=os.path.getsize(path), sha256=sha256(path),
                families=dict(families), states=dict(states), sources=dict(sources), unknown=dict(unknown),
                counts=counts, threeOffMeshes=mesh3, tvs={m: dict(v) for m, v in tvs.items()},
                unresolved=sorted(unresolved))


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('game', type=Path)
    a.add_argument('out', type=Path)
    a.add_argument('--jobs', type=int, default=4)
    a.add_argument('--only', action='append', help='only this map (repeatable)')
    args = a.parse_args()
    setup(REPO)
    import library
    jobs = [(REPO, name, str(path)) for name, _, path in library.donors(args.game)
            if not args.only or name in args.only]
    with multiprocessing.Pool(args.jobs) as pool:
        maps = sorted(pool.map(survey, jobs), key=lambda m: m['map'].casefold())
    total = collections.Counter()
    for key in ('families', 'states', 'sources', 'unknown', 'counts', 'threeOffMeshes'):
        for m in maps:
            for k, v in m[key].items():
                total['%s|%s' % (key, k)] += v
    tv_maps = {}
    for m in maps:
        for mesh, kinds in m['tvs'].items():
            tv_maps.setdefault(mesh, {})[m['map']] = kinds
    mixed = sorted({mp for mesh in tv_maps.values() for mp, kinds in mesh.items() if len(kinds) > 1})
    ways = collections.defaultdict(set)
    for mesh in tv_maps.values():
        for mp, kinds in mesh.items():
            ways[mp] |= set(kinds)
    mixed_any = sorted(mp for mp, kinds in ways.items() if len(kinds) > 1)
    out = dict(tool='tools/upk/audit_piece_flags.py', population='library.donors: the base map of each map the editor '
               'lists, persistent level only, each actor once', maps=len(maps),
               files=[dict(map=m['map'], file=m['file'], size=m['size'], sha256=m['sha256']) for m in maps],
               total={k: v for k, v in sorted(total.items()) if not k.startswith('threeOffMeshes|')},
               threeOffMeshCount=sum(1 for k in total if k.startswith('threeOffMeshes|')),
               tvs=dict(meshes=len(tv_maps), pieces=sum(sum(k.values()) for mesh in tv_maps.values() for k in mesh.values()),
                        maps=len({mp for mesh in tv_maps.values() for mp in mesh}), mapsWithOneMeshTwoWays=mixed,
                        mapsWithTvsSetTwoWays=mixed_any,
                        byMesh=tv_maps),
               unresolved={m['map']: m['unresolved'] for m in maps if m['unresolved']},
               perMap={m['map']: dict(families=m['families'], counts=m['counts'], sources=m['sources'],
                                      unknown=m['unknown']) for m in maps})
    args.out.write_text(json.dumps(out, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    t = out['total']
    print('%d maps; %d actors with flags (%s)' % (len(maps), sum(v for k, v in t.items() if k.startswith('families|')),
                                                  ', '.join('%s %d' % (k.split('|')[1], v) for k, v in t.items()
                                                            if k.startswith('families|'))))
    print('drawn, colliding: %d; walking off %d, cover off %d, walking, cover and sight off %d (%d meshes), of those '
          'the mouse skips %d' % (t.get('counts|drawnColliding', 0), t.get('counts|walkingOff', 0),
                                  t.get('counts|coverOff', 0), t.get('counts|threeOff', 0), out['threeOffMeshCount'],
                                  t.get('counts|threeOffMouseOff', 0)))
    print('props with the pathing gate: %d (walking and cover off too: %d)' % (t.get('counts|gate', 0),
                                                                             t.get('counts|gateWalkingCoverOff', 0)))
    print('ladders: %d, sight off %d, walking, cover and sight off %d' % (
        t.get('counts|ladders', 0), t.get('counts|laddersSightOff', 0), t.get('counts|laddersThreeOff', 0)))
    print('TVs: %d pieces of %d meshes in %d maps; TVs set more than one way in %d maps, one mesh set two ways in %d' % (
        out['tvs']['pieces'], out['tvs']['meshes'], out['tvs']['maps'], len(mixed_any), len(mixed)))
    print('settings by source: %s; unknown %d; actors with an assumed value %d' % (
        ', '.join('%s %d' % (k.split('|')[1], v) for k, v in t.items() if k.startswith('sources|')),
        sum(v for k, v in t.items() if k.startswith('unknown|')), sum(len(v) for v in out['unresolved'].values())))


if __name__ == '__main__':
    main()
