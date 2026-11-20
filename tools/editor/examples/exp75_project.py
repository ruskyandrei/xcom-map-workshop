"""EXP-75's project: made walls that meet, a door in a made wall, a room in a building and a wall on a roof (custom
geometry plan, stage M3, run C), on URB_Bar.

Copies of URB_Bar's inside wall URB_BarIntWallB_FRACTURED (XComDecoFracLevelActor_17), as the editor's wall and room
tools make them (x0 0 and the piece at the wall's start, on a tile line, standing on the floor), two storeys unless
said:
- an L in the parking lot (floor 0): A along x from (-1344, -672) to (-1056, -672), three tiles; B from A's far end
  south to (-1056, -864), two tiles. A is the longer, so it runs through to B's far face; B butts on A's face;
- a T in the lot: D along x from (-960, -672) to (-480, -672), five tiles, a doorway in its second tile (x -864 to
  -768); E from D's line at x -672 south to (-672, -960), three tiles: its end stops on D's face;
- a room in the lot, three by three tiles (x -1728 to -1440, y -1056 to -768), four walls anticlockwise from its
  south-west corner, a doorway in the middle of its south side, in a building made round it (the Buildings view's
  record): floor 1 from 0 to 208, floor 2 from 208 to 400, over the room's footprint;
- F on the pavement before the bar (floor 16), along x from (-1536, -192) to (-1152, -192), a doorway in its second
  tile (x -1440 to -1344), and in it a copy of the bar's door XComInteractiveLevelActor_6 with its frame
  (XComDestructibleActor_60), moved by whole tiles (-576, -864, 0) from where it stands in the bar's inside wall;
- G on the bar's roof (floor 400), along x from (-1440, 384) to (-1152, 384), a doorway in its second tile (x -1344
  to -1248);
- W1a and W1b in the lot: a one-storey wall along x from (-1344, -1248) to (-1056, -1248) and another standing on it
  (192 higher), which since M3 list each other's columns.
Game tiles count from the map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

Usage: exp75_project.py --store <projects folder> --builds <builds folder> [--build] [--quick]

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
DONOR = 'XComDecoFracLevelActor_17'
DONOR_COMPONENT = PL + DONOR + '.FracturedStaticMeshComponent_12'
DOOR = PL + 'XComInteractiveLevelActor_6'
DOOR_MOVE = (-576.0, -864.0, 0.0)
PROJECT = ('00000000-0000-4000-8000-0000000e7500', 'EXP-75 joined walls')
LOT, PAVEMENT, ROOF = 0.0, 16.0, 400.0
Q = 16384
DOORWAY = dict(z0=-16.0, z1=160.0)
WALLS = (
    # (label, location, yaw, length, storeys, doorway tile or None, seed)
    ('A', [-1344.0, -672.0, LOT], 0, 288.0, 2, None, 751),
    ('B', [-1056.0, -672.0, LOT], 3 * Q, 192.0, 2, None, 752),
    ('D', [-960.0, -672.0, LOT], 0, 480.0, 2, 1, 753),
    ('E', [-672.0, -672.0, LOT], 3 * Q, 288.0, 2, None, 754),
    ('RoomS', [-1728.0, -1056.0, LOT], 0, 288.0, 2, 1, 755),
    ('RoomE', [-1440.0, -1056.0, LOT], Q, 288.0, 2, None, 756),
    ('RoomN', [-1440.0, -768.0, LOT], 2 * Q, 288.0, 2, None, 757),
    ('RoomW', [-1728.0, -768.0, LOT], 3 * Q, 288.0, 2, None, 758),
    ('F', [-1536.0, -192.0, PAVEMENT], 0, 384.0, 2, 1, 759),
    ('G', [-1440.0, 384.0, ROOF], 0, 288.0, 2, 1, 760),
    ('W1a', [-1344.0, -1248.0, LOT], 0, 288.0, 1, None, 761),
    ('W1b', [-1344.0, -1248.0, LOT + 192.0], 0, 288.0, 1, None, 762),
)
ROOM_FLOORS = [[-1728.0, -1056.0, 0.0, -1440.0, -768.0, 208.0], [-1728.0, -1056.0, 208.0, -1440.0, -768.0, 400.0]]


def added(scene):
    out = []
    for k, (label, location, yaw, length, storeys, door, seed) in enumerate(WALLS):
        wall = dict(x0=0.0, x1=length, openings=[], seed=seed)
        if door is not None:
            wall['openings'] = [dict(x0=96.0 * door, x1=96.0 * door + 96.0, **DOORWAY)]
        if storeys == 1:
            wall['storeys'] = 1
        out.append(dict(id='00000000-0000-4000-8000-0000000e75%02d' % (k + 1), actor=PL + '%s_copy%d' % (DONOR, k + 1),
                        **{'from': dict(package=MAP, level='base', actor=PL + DONOR)}, components=[DONOR_COMPONENT],
                        location=location, rotation=[0, yaw, 0], prefab=None, partner=None,
                        generated=dict(kind='fracWall', version=1, wall=wall)))
    # the bar's door and its frame, moved by whole tiles into F's doorway
    door = compiler.assemblies(scene, MAP)[DOOR]
    by_actor = {o['actor']: o for o in scene['objects'] if o.get('layer') == 'base'}
    for member in door['members']:
        o = by_actor[member]
        k = len(out) + 1
        out.append(dict(id='00000000-0000-4000-8000-0000000e75%02d' % k, actor=PL + '%s_copy%d' % (member.split('.')[-1], k),
                        **{'from': dict(package=MAP, level='base', actor=member)}, components=[o['component']],
                        location=[o['location'][i] + DOOR_MOVE[i] for i in range(3)], rotation=list(o['rotation']),
                        prefab=None, partner=None))
    return out


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
    buildings = [dict(id='00000000-0000-4000-8000-0000000e75b1', name='EXP-75 room', kind='building',
                      floors=[dict(boxes=[box]) for box in ROOM_FLOORS])]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=4, id=project_id, name=name, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=[], added=pieces, groups=[], buildings=buildings, nextSerial=len(pieces) + 1,
               view=dict(camera=[-1100, 900, -1500], target=[-1100, 0, -800]))
    if current and current.get('created'):
        doc['created'] = current['created']
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
    print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
    print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
    names = {PL + '%s_copy%d' % (DONOR, k + 1): w[0] for k, w in enumerate(WALLS)}
    _, native = compiler.native_split(compiler.stream_only(spec))
    print('ends', [(names.get(PL + c['label'], c['label']), c['generated']['wall'].get('ends'))
                   for c in native['copies'] if (c.get('generated') or {}).get('kind') == 'fracWall'])
    if not report['ok'] or report['leftOut']:
        raise SystemExit(1)
    saved = store.save(project_id, doc, current['revision'] if current else 0)
    print('saved %s as revision %d (%s): builds as %s' % (name, saved['revision'], saved['file'], output['shipAs']))
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
