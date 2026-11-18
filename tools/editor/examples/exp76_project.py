"""EXP-76's project: a made upper floor and roof over a room of made walls (custom geometry plan, stage M5, run E), on
URB_Bar.

In the parking lot (floor 0), as the editor's tools make them:
- a room four by three tiles (x -1728 to -1344, y -1056 to -768): four copies of URB_Bar's inside wall
  URB_BarIntWallB_FRACTURED (XComDecoFracLevelActor_17), two storeys, anticlockwise from the south-west corner, a
  doorway in the second tile of the south side (x -1632 to -1536);
- an upper floor over the whole room: a copy of the bar's upstairs floor Core_384FloorB_FRACTURED
  (XComFracLevelActor_17) made from numbers, the piece at (-1728, -1056, 0), its plate 192 to 194 over the lot, a hole
  one tile square at x -1536 to -1440, y -960 to -864;
- a roof over the room on the walls' tops: a copy of the bar's roof Roof_BarrierSmallFloor_FRACTURED
  (XComFracLevelActor_3) made from numbers, the piece at (-1728, -1056, 384), its plate 382 to 386;
- a building round the room as the Room with a roof tool makes it: floor 1 from -16 to 208, floor 2 from 208 to 400;
- a second roof on its own over open ground east of the room (x -1152 to -960, y -1056 to -864, at 384), with no walls
  under it: a roof standing in the air, to see what the game makes of one.
Game tiles count from the map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

Usage: exp76_project.py --store <projects folder> --builds <builds folder> [--build] [--quick]

The project is saved in the store given (a test server's scratch store: Play in game on that server, started with
--dry-play, then stages its build into the lab copy). The game and the cache are the settings'; URB_Bar must have been
opened in the editor."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import build  # noqa: E402
import compiler  # noqa: E402
import outputnames  # noqa: E402
import projects  # noqa: E402
import settings as settings_module  # noqa: E402

MAP, PL = 'URB_Bar', 'TheWorld.PersistentLevel.'
WALL_DONOR, FLOOR_DONOR, ROOF_DONOR = 'XComDecoFracLevelActor_17', 'XComFracLevelActor_17', 'XComFracLevelActor_3'
PROJECT = ('00000000-0000-4000-8000-0000000e7600', 'EXP-76 floors and roofs')
LOT, TOP = 0.0, 384.0
Q = 16384
DOORWAY = dict(z0=-16.0, z1=160.0)
WALLS = (
    # (label, location, yaw, length, doorway tile or None, seed)
    ('RoomS', [-1728.0, -1056.0, LOT], 0, 384.0, 1, 761),
    ('RoomE', [-1344.0, -1056.0, LOT], Q, 288.0, None, 762),
    ('RoomN', [-1344.0, -768.0, LOT], 2 * Q, 384.0, None, 763),
    ('RoomW', [-1728.0, -768.0, LOT], 3 * Q, 288.0, None, 764),
)
SLABS = (
    # (label, donor, location, slab)
    ('Floor', FLOOR_DONOR, [-1728.0, -1056.0, LOT],
     dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, holes=[dict(x0=192.0, x1=288.0, y0=96.0, y1=192.0)], seed=765, look='floor')),
    ('Roof', ROOF_DONOR, [-1728.0, -1056.0, LOT + TOP], dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, holes=[], seed=766)),
    ('LoneRoof', ROOF_DONOR, [-1152.0, -1056.0, LOT + TOP], dict(x0=0.0, x1=192.0, y0=0.0, y1=192.0, holes=[], seed=767)),
)
ROOM_FLOORS = [[-1728.0, -1056.0, LOT - 16.0, -1344.0, -768.0, LOT + 208.0],
               [-1728.0, -1056.0, LOT + 208.0, -1344.0, -768.0, LOT + 400.0]]


def added(scene):
    by_actor = {o['actor']: o for o in scene['objects'] if o.get('layer') == 'base'}
    out = []
    for label, location, yaw, length, door, seed in WALLS:
        wall = dict(x0=0.0, x1=length, openings=[], seed=seed)
        if door is not None:
            wall['openings'] = [dict(x0=96.0 * door, x1=96.0 * door + 96.0, **DOORWAY)]
        out.append((label, WALL_DONOR, location, [0, yaw, 0], dict(kind='fracWall', version=1, wall=wall)))
    for label, donor, location, slab in SLABS:
        out.append((label, donor, location, [0, 0, 0], dict(kind='fracSlab', version=1, slab=slab)))
    return [dict(id='00000000-0000-4000-8000-0000000e76%02d' % (k + 1), actor=PL + '%s_copy%d' % (donor, k + 1),
                 **{'from': dict(package=MAP, level='base', actor=PL + donor)}, components=[by_actor[PL + donor]['component']],
                 location=location, rotation=rotation, prefab=None, partner=None, generated=generated)
            for k, (label, donor, location, rotation, generated) in enumerate(out)]


def labels():
    return [w[0] for w in WALLS] + [s[0] for s in SLABS]


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
    pieces = added(scene)
    buildings = [dict(id='00000000-0000-4000-8000-0000000e76b1', name='EXP-76 room', kind='building',
                      floors=[dict(boxes=[box]) for box in ROOM_FLOORS])]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=4, id=project_id, name=name, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=[], added=pieces, groups=[], buildings=buildings, nextSerial=len(pieces) + 1,
               view=dict(camera=[-1100, 900, -1500], target=[-1500, 0, -900]))
    if current and current.get('created'):
        doc['created'] = current['created']
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
    print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
    print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
    _, native = compiler.native_split(compiler.stream_only(spec))
    names = dict(zip([PL + p['actor'].split('.')[-1] for p in pieces], labels()))
    print('boxes', [(names.get(PL + c['label'], c['label']), [round(v, 1) for v in c['box']]) for c in native['copies']])
    if not report['ok'] or report['leftOut']:
        raise SystemExit(1)
    saved = store.save(project_id, doc, current['revision'] if current else 0)
    print('saved %s as revision %d (%s): builds as %s' % (name, saved['revision'], saved['file'], output['shipAs']))
    if not args.build:
        return
    try:
        m = build.Build(store.path(project_id), s['cache'], args.builds, game, s['udk'], quick=args.quick).run()
    except build.BuildError as error:
        raise SystemExit('build failed: %s' % error)
    print(json.dumps({k: m.get(k) for k in ('buildId', 'variant', 'quick', 'seconds')}))


if __name__ == '__main__':
    main()
