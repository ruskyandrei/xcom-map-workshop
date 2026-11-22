"""EXP-84's project: flags on made walls and ground, a rock shaped by its points, and three gap cases left unplayed
(19 November 2026, before the custom geometry branch goes into main), on URB_Bar's car park.

The car park's cars and vans are deleted (each assembly whole) so the pieces have room. Walls are copies of URB_Bar's
inside wall URB_BarIntWallB_FRACTURED (XComDecoFracLevelActor_17), as the editor's tools make them (x0 0 and the piece
at the wall's start, on a tile line, standing on the floor):
- N, C, S: one-storey walls five tiles long along x at y -1152 on the lot: N with its flags as made (the control), C
  with Gives cover off, S with Blocks sight off; N from x -2016, C from -1344, S from -672;
- G0, G: ground blocks two tiles by one, 64 tall, made on URB_CommercialAlley's asphalt plane (StaticMeshActor_50, a
  static mesh actor the Build makes a level piece): G0 as made (the control) at x -1920 to -1728, G with Gives cover
  off at x -1440 to -1248, both y -864 to -768;
- R: a rock on the same asphalt, its footprint grown to three tiles by two (x -960 to -672, y -864 to -672): its
  seed's points, with two of its foot's points and one of its middle ring's pulled out into the third tile (x -768 to
  -672, y -754 to -684), as the editor's blue points do;
- D: a two-storey wall on the pavement before the bar (floor 16), along x from (-1536, -192) to (-1152, -192), a
  doorway in its second tile (x -1440 to -1344) with the threshold Add gap leaves (8 over the floor), and in it a copy
  of the bar's door XComInteractiveLevelActor_6 with its frame, moved by whole tiles (-576, -864, 0) as in EXP-75;
- T: a one-storey wall along x from (0, -384) to (384, -384), a gap in its second tile from 72 up through its top
  (192): a notch;
- W: a two-storey wall along x from (576, -384) to (960, -384), one gap the whole wall long from 72 to 168: a strip
  under it and one over it (frac_wall moves the fragment seeds into the strips).
Game tiles count from the map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

Usage: exp84_project.py --store <projects folder> --builds <builds folder> [--build] [--quick]

The project is saved in the store given (a test server's scratch store: Play in game on that server, started with
--dry-play, then stages its build into the lab copy). The game and the cache are the settings'; URB_Bar must have been
opened in the editor, and the library scanned (the asphalt donor comes from URB_CommercialAlley)."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
sys.path.insert(0, str(HERE.parents[1] / 'bake'))
import build  # noqa: E402
import compiler  # noqa: E402
import ground as ground_shapes  # noqa: E402
import library  # noqa: E402
import outputnames  # noqa: E402
import projects  # noqa: E402
import settings as settings_module  # noqa: E402

MAP, PL = 'URB_Bar', 'TheWorld.PersistentLevel.'
WALL_DONOR = 'XComDecoFracLevelActor_17'
GROUND_MAP, GROUND_DONOR = 'URB_CommercialAlley', 'StaticMeshActor_50'
DOOR = PL + 'XComInteractiveLevelActor_6'
DOOR_MOVE = (-576.0, -864.0, 0.0)
PROJECT = ('00000000-0000-4000-8000-0000000e8400', 'EXP-84 made flags rocks gaps')
LOT, PAVEMENT, Q = 0.0, 16.0, 16384
LOT_BOX = (-2112.0, 1440.0, -1536.0, -288.0)        # the car park (x0, x1, y0, y1): its cars and vans go
WALLS = (
    # (label, location, length, storeys, openings, flags, seed)
    ('N', [-2016.0, -1152.0, LOT], 480.0, 1, [], None, 841),
    ('C', [-1344.0, -1152.0, LOT], 480.0, 1, [], dict(cover=False), 842),
    ('S', [-672.0, -1152.0, LOT], 480.0, 1, [], dict(sight=False), 843),
    ('D', [-1536.0, -192.0, PAVEMENT], 384.0, 2, [dict(x0=96.0, x1=192.0, z0=8.0, z1=160.0)], None, 844),
    ('T', [0.0, -384.0, LOT], 384.0, 1, [dict(x0=96.0, x1=192.0, z0=72.0, z1=192.0)], None, 845),
    ('W', [576.0, -384.0, LOT], 384.0, 2, [dict(x0=0.0, x1=384.0, z0=72.0, z1=168.0)], None, 846),
)
BLOCKS = (
    # (label, location, flags)
    ('G0', [-1920.0, -864.0, LOT], None),
    ('G', [-1440.0, -864.0, LOT], dict(cover=False)),
)
ROCK_AT = [-960.0, -864.0, LOT]


def rock(look):
    """The rock R: the seed's points of a rock two tiles square, two foot points and one of the middle ring pulled out
    into a third tile east (the footprint grown east keeps its corner where it is, as the editor's points do)."""
    seeded = dict(shape='rock', x0=0.0, x1=192.0, y0=0.0, y1=192.0, height=96.0, seed=847)
    pts = [list(p) for p in ground_shapes.rock_points(seeded)]
    ring = sorted(range(ground_shapes.ROCK_RING), key=lambda i: -pts[i][0])
    pts[ring[0]], pts[ring[1]] = [282.0, 110.0, 0.0], [282.0, 180.0, 0.0]
    middle = max(range(ground_shapes.ROCK_RING, ground_shapes.ROCK_RING + 8), key=lambda i: pts[i][0])
    pts[middle] = [276.0, 150.0, 70.0]
    shape = dict(seeded, x1=288.0, points=pts, look=look)
    _, corners = ground_shapes.rock_corners({k: v for k, v in shape.items() if k != 'look'})
    print('rock R: %d points, %d corners, moved %s' % (len(pts), len(corners), [ring[0], ring[1], middle]))
    return dict(kind='ground', version=4, ground=shape)


def added(scene, cache, game):
    by_actor = {o['actor']: o for o in scene['objects'] if o.get('layer') == 'base'}
    out = []        # (label, fields)
    for label, location, length, storeys, openings, flags, seed in WALLS:
        wall = dict(x0=0.0, x1=length, openings=openings, seed=seed)
        if storeys == 1:
            wall['storeys'] = 1
        out.append((label, dict(components=[by_actor[PL + WALL_DONOR]['component']], location=location, rotation=[0, 0, 0],
                                **{'from': dict(package=MAP, level='base', actor=PL + WALL_DONOR)},
                                generated=dict(kind='fracWall', version=1, wall=wall), **({'flags': flags} if flags else {}))))
    # the asphalt donor through the library (a piece of another map)
    record = library.piece(cache, game, dict(package=GROUND_MAP, level='base', actor=GROUND_DONOR), {})
    (donor,) = [o for o in record['objects'] if o['actor'].split('.')[-1] == GROUND_DONOR]
    if not donor.get('pieceFlags'):
        raise SystemExit('the library record of %s has no flags: the library is older than piece version 10' % GROUND_DONOR)
    cat = json.loads((ROOT / 'tools' / 'bake' / 'looks' / 'ground.json').read_text(encoding='utf-8'))
    (entry,) = [e for e in cat['looks'] if e['map'] == GROUND_MAP and e['actor'].split('.')[-1] == GROUND_DONOR]
    look = dict(mesh=entry['mesh'], material=entry['material'], measure=cat['measure'])
    ground_from = dict(components=[donor['component']], rotation=[0, 0, 0],
                       **{'from': dict(package=GROUND_MAP, level='base', actor=PL + GROUND_DONOR)})
    for label, location, flags in BLOCKS:
        block = dict(kind='ground', version=2, ground=dict(shape='block', x0=0.0, x1=192.0, y0=0.0, y1=96.0, height=64.0,
                                                            look=look))
        out.append((label, dict(ground_from, location=location, generated=block, **({'flags': flags} if flags else {}))))
    out.append(('R', dict(ground_from, location=ROCK_AT, generated=rock(look))))
    # the bar's door and its frame, moved by whole tiles into D's doorway
    for member in compiler.assemblies(scene, MAP)[DOOR]['members']:
        o = by_actor[member]
        out.append(('door ' + member.split('.')[-1], dict(
            components=[o['component']], location=[o['location'][i] + DOOR_MOVE[i] for i in range(3)],
            rotation=list(o['rotation']), **{'from': dict(package=MAP, level='base', actor=member)})))
    return [dict(id='00000000-0000-4000-8000-0000000e84%02d' % (k + 1),
                 actor=PL + '%s_copy%d' % (f['from']['actor'].split('.')[-1], k + 1), prefab=None, partner=None, **f)
            for k, (label, f) in enumerate(out)], [label for label, _ in out]


def lot_deletes(scene):
    """Delete records for the car park's cars and vans, each assembly whole."""
    by_actor = {o['actor']: o for o in scene['objects'] if o.get('layer') == 'base'}
    out = []
    for pivot, a in sorted(compiler.assemblies(scene, MAP).items()):
        if a.get('family') not in ('car', 'van') or pivot not in by_actor:
            continue
        x, y = by_actor[pivot]['location'][:2]
        if LOT_BOX[0] <= x <= LOT_BOX[1] and LOT_BOX[2] <= y <= LOT_BOX[3]:
            out += [dict(target=dict(package=MAP, level='base', actor=m), deleted=True) for m in a['members']]
    return sorted(out, key=lambda r: r['target']['actor'])


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('--store', type=Path, required=True, help='the projects folder to save it in (a scratch one)')
    a.add_argument('--builds', type=Path, required=True, help='the builds folder to build it into (a scratch one)')
    a.add_argument('--build', action='store_true')
    a.add_argument('--quick', action='store_true', help='with --build: without baking')
    args = a.parse_args()
    s = settings_module.load_settings()
    game = settings_module.resolve_game(s['game'])[0]
    if game is None:
        raise SystemExit('set the game install first')
    base = build.lwr_file(game, 'CookedPCConsole', MAP + '.upk')
    sha = build.sha256(base)
    export, scene = compiler.find_export(s['cache'], dict(source=dict(map=MAP, sha256=sha, exporterVersion=build.EXPORT_MINIMUM)),
                                         minimum=build.EXPORT_MINIMUM)
    print('base map %s (SHA-256 %s), export %s' % (base.name, sha[:12], export.parent.name))
    store = projects.ProjectStore(args.store)
    project_id, name = PROJECT
    try:
        current = store.load(project_id)
    except projects.ProjectError:
        current = None
    if current and outputnames.valid_output(current.get('output')):
        output = current['output']
    else:
        claims = outputnames.Claims(store.root, str(args.builds), [game])
        output = outputnames.allocate(name, claims.taken, outputnames.base_streams(game, MAP))
        output.pop('reason', None)
    pieces, labels = added(scene, s['cache'], game)
    deletes = lot_deletes(scene)
    print('deleted from the car park: %d pieces of its cars and vans' % len(deletes))
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=projects.SCHEMA_VERSION, id=project_id, name=name, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=deletes, added=pieces, groups=[], buildings=[],
               nextSerial=len(pieces) + 1, view=dict(camera=[-700, 1400, -2600], target=[-700, 0, -900]))
    if current and current.get('created'):
        doc['created'] = current['created']
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
    print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
    print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
    print('flag notes', json.dumps([(w['code'], w['message'][:200]) for w in report['notes'] if w['code'].startswith('flags')], indent=1))
    _, native = compiler.native_split(compiler.stream_only(spec))
    for c in native['copies']:
        print('  %-44s at %-24s %s%s' % (c['label'], [round(v) for v in c['location']], (c.get('generated') or {}).get('kind', ''),
                                         ' flags %s' % c['flags'] if c.get('flags') else ''))
    if not report['ok'] or report['leftOut']:
        raise SystemExit(1)
    saved = store.save(project_id, doc, current['revision'] if current else 0)
    print('saved %s as revision %d (%s): builds as %s' % (name, saved['revision'], saved['file'], output['shipAs']))
    print('pieces:', ', '.join(labels))
    if not args.build:
        return
    try:
        m = build.Build(build.BuildInputs(store.path(project_id), s['cache'], args.builds, game, s['udk'],
                                          quick=args.quick)).run()
    except build.BuildError as error:
        raise SystemExit('build failed: %s' % error)
    print(json.dumps({k: m.get(k) for k in ('buildId', 'variant', 'quick', 'seconds')}))


if __name__ == '__main__':
    main()
