"""EXP-81's project: made walls and floors past the game's sizes, cut by the Build into pieces it takes, and made walls
and roofs built broken (custom geometry editing plan, stages E4 and E5), on URB_Bar's car park.

The car park's cars and vans are deleted (each assembly whole) so the pieces have room. Copies of URB_Bar's inside
wall URB_BarIntWallB_FRACTURED (XComDecoFracLevelActor_17) and roof (XComFracLevelActor_3), as the editor's tools make
them (x0 0 and the piece at the wall's start, on a tile line, standing on the lot, floor 0), in their donors' looks:
- L: a wall 24 tiles long along x from (-1920, -1152) to (384, -1152), two storeys: the Build makes it as a wall of 16
  tiles and one of 8 joined end to end, the joint at x -384;
- T: a wall four storeys tall along x from (576, -1152) to (864, -1152): two two-storey walls, the upper standing on
  the lower's top (400 up), its top 784 over the lot;
- B: a wall along x from (-1536, -672) to (-1152, -672), broken by one blast of one tile at (-1344, -672), 60 up (its
  lower middle): the fragments within the blast are saved painted out;
- a room four by three tiles, one storey, x 0 to 384, y -768 to -480 (a doorway in the middle of its south side), with
  a roof on its walls' tops (192), broken by one blast of one tile at its middle (192, -624), and a building round it
  (floor 0 from -16 to 192, floor 1 from 192 to 384), as the Room with a roof tool makes them;
- F: a roof 20 tiles by 2 at 192 over the lot, x -1920 to 0, y -1440 to -1248: the Build makes it as a slab of 16 by 2
  and one of 4 by 2 side by side, the joint at x -384.
Game tiles count from the map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

Usage: exp81_project.py --store <projects folder> --builds <builds folder> [--build] [--quick]

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
WALL_DONOR, ROOF_DONOR = 'XComDecoFracLevelActor_17', 'XComFracLevelActor_3'
PROJECT = ('00000000-0000-4000-8000-0000000e8100', 'EXP-81 sizes and breaks')
LOT, Q = 0.0, 16384
DOORWAY = dict(z0=8.0, z1=160.0)
LOT_BOX = (-2112.0, 1440.0, -1536.0, -288.0)        # the car park (x0, x1, y0, y1): its cars and vans go
WALLS = (
    # (label, location, yaw, length, storeys or None, doorway tile or None, blasts or None, seed)
    ('L', [-1920.0, -1152.0, LOT], 0, 96.0 * 24, None, None, None, 811),
    ('T', [576.0, -1152.0, LOT], 0, 288.0, 4, None, None, 812),
    ('B', [-1536.0, -672.0, LOT], 0, 384.0, None, None, [dict(at=[192.0, 0.0, 60.0], radius=96.0)], 813),
    ('RoomS', [0.0, -768.0, LOT], 0, 384.0, 1, 2, None, 814),
    ('RoomE', [384.0, -768.0, LOT], Q, 288.0, 1, None, None, 815),
    ('RoomN', [384.0, -480.0, LOT], 2 * Q, 384.0, 1, None, None, 816),
    ('RoomW', [0.0, -480.0, LOT], 3 * Q, 288.0, 1, None, None, 817),
)
SLABS = (
    # (label, location, slab, blasts or None)
    ('Roof', [0.0, -768.0, LOT + 192.0], dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, holes=[], seed=818),
     [dict(at=[192.0, 144.0, 0.0], radius=96.0)]),
    ('F', [-1920.0, -1440.0, LOT + 192.0], dict(x0=0.0, x1=96.0 * 20, y0=0.0, y1=192.0, holes=[], seed=819), None),
)
ROOM_FLOORS = [[0.0, -768.0, LOT - 16.0, 384.0, -480.0, LOT + 192.0],
               [0.0, -768.0, LOT + 192.0, 384.0, -480.0, LOT + 384.0]]


def added(scene):
    by_actor = {o['actor']: o for o in scene['objects'] if o.get('layer') == 'base'}
    out = []
    for label, location, yaw, length, storeys, door, blasts, seed in WALLS:
        wall = dict(x0=0.0, x1=length, openings=[], seed=seed)
        if door is not None:
            wall['openings'] = [dict(x0=96.0 * door, x1=96.0 * door + 96.0, **DOORWAY)]
        if storeys:
            wall['storeys'] = storeys
        out.append((label, WALL_DONOR, location, [0, yaw, 0], dict(kind='fracWall', version=1, wall=wall,
                                                                     **({'blasts': blasts} if blasts else {}))))
    for label, location, slab, blasts in SLABS:
        out.append((label, ROOF_DONOR, location, [0, 0, 0], dict(kind='fracSlab', version=1, slab=slab,
                                                                  **({'blasts': blasts} if blasts else {}))))
    return [dict(id='00000000-0000-4000-8000-0000000e81%02d' % (k + 1), actor=PL + '%s_copy%d' % (donor, k + 1),
                 **{'from': dict(package=MAP, level='base', actor=PL + donor)}, components=[by_actor[PL + donor]['component']],
                 location=location, rotation=rotation, prefab=None, partner=None, generated=generated)
            for k, (label, donor, location, rotation, generated) in enumerate(out)]


def labels():
    return [w[0] for w in WALLS] + [s[0] for s in SLABS]


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
    pieces = added(scene)
    deletes = lot_deletes(scene)
    print('deleted from the car park: %d pieces of its cars and vans' % len(deletes))
    buildings = [dict(id='00000000-0000-4000-8000-0000000e81b1', name='EXP-81 room', kind='building',
                      floors=[dict(boxes=[box]) for box in ROOM_FLOORS])]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=4, id=project_id, name=name, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=deletes, added=pieces, groups=[], buildings=buildings,
               nextSerial=len(pieces) + 1, view=dict(camera=[-700, 1400, -2600], target=[-700, 0, -900]))
    if current and current.get('created'):
        doc['created'] = current['created']
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
    print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
    print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
    print('notes', json.dumps([(w['code'], w['message'][:200]) for w in report['notes']
                               if w['code'] in ('made-split', 'made-broken')], indent=1))
    _, native = compiler.native_split(compiler.stream_only(spec))
    for c in native['copies']:
        g = c.get('generated') or {}
        if g.get('kind') in ('fracWall', 'fracSlab'):
            numbers = g.get('wall') or g.get('slab')
            print('  %-40s at %-28s %s%s%s' % (c['label'], [round(v) for v in c['location']],
                                              '%g long' % numbers['x1'] if 'wall' in g else '%g by %g' % (numbers['x1'], numbers['y1']),
                                              ', ends %s' % numbers['ends'] if numbers.get('ends') else '',
                                              ', blasts %s' % g['blasts'] if g.get('blasts') else ''))
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
