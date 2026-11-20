"""EXP-82's project: the map's own fracturing pieces built broken (custom geometry editing plan, stage E6), on URB_Bar.

- URB_Bar's inside wall XComDecoFracLevelActor_17 (URB_BarIntWallB_FRACTURED, at (-1056, 864, 16), yaw 49152: it runs
  along y from 680 to 1240 on the tile line x -1057) broken where it stands by one blast of one tile at its foot,
  local (-143, 0, 60), the world's (-1056, 1007, 76): the fragments it reaches are saved painted out and its tiles
  worked out again (the spec's pieceBlasts);
- the corner column XComFracLevelActor_5 (at (720, 48, 16)) moved a tile along x, to (816, 48, 16), and broken by a
  blast of two tiles at local (0, 0, 60): its copy carries the blasts;
- an added copy of that column at (720, 432, 16), broken the same way;
- the bar's roof XComFracLevelActor_3 (at (-1056, 576, 400); it keeps its fragments, bPreventChunkRemoval, F-138)
  broken where it stands by a blast of two tiles at local (-288, 288, 0): 7 of its 81 fragments, a hole from x -1536
  to -1152, y 672 to 1056;
- a made roof (a copy of the bar's roof made from numbers, 4 by 3 tiles) at (-1920, -1440, 192) over the car park,
  broken by a blast of one tile at its middle (the world's (-1728, -1296)): 5 of its 15 fragments.
The Build turns bPreventChunkRemoval off on both roofs (F-138's fix candidate).
Game tiles count from the map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

Usage: exp82_project.py --store <projects folder> --builds <builds folder> [--build] [--quick]

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
WALL, COLUMN, ROOF = 'XComDecoFracLevelActor_17', 'XComFracLevelActor_5', 'XComFracLevelActor_3'
PROJECT = ('00000000-0000-4000-8000-0000000e8200', 'EXP-82 map breaks')
WALL_BLASTS = [dict(at=[-143.0, 0.0, 60.0], radius=96.0)]
COLUMN_BLASTS = [dict(at=[0.0, 0.0, 60.0], radius=192.0)]
ROOF_BLASTS = [dict(at=[-288.0, 288.0, 0.0], radius=192.0)]
MADE_ROOF = dict(kind='fracSlab', version=1, slab=dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, holes=[], seed=821),
                 blasts=[dict(at=[192.0, 144.0, 0.0], radius=96.0)])


def target(actor):
    return dict(package=MAP, level='base', actor=PL + actor)


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
    column = next(o for o in scene['objects'] if o.get('layer') == 'base' and o['actor'] == PL + COLUMN)
    roof = next(o for o in scene['objects'] if o.get('layer') == 'base' and o['actor'] == PL + ROOF)
    x, y, z = column['location']
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
    overrides = [dict(target=target(WALL), blasts=WALL_BLASTS),
                 dict(target=target(COLUMN), location=[x + 96.0, y, z], rotation=list(column['rotation']), blasts=COLUMN_BLASTS),
                 dict(target=target(ROOF), blasts=ROOF_BLASTS)]
    added = [dict(id='00000000-0000-4000-8000-0000000e8201', actor=PL + COLUMN + '_copy1', **{'from': target(COLUMN)},
                  components=[column['component']], location=[x, y + 384.0, z], rotation=list(column['rotation']),
                  prefab=None, partner=None, blasts=COLUMN_BLASTS),
             dict(id='00000000-0000-4000-8000-0000000e8202', actor=PL + ROOF + '_copy2', **{'from': target(ROOF)},
                  components=[roof['component']], location=[-1920.0, -1440.0, 192.0], rotation=[0, 0, 0],
                  prefab=None, partner=None, generated=MADE_ROOF)]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=4, id=project_id, name=name, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=overrides, added=added, groups=[], nextSerial=3,
               view=dict(camera=[-1400, 700, 1300], target=[-1056, 0, 1007]))
    if current and current.get('created'):
        doc['created'] = current['created']
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
    print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
    print('notes', json.dumps([(w['code'], w['message'][:200]) for w in report['notes'] if w['code'].endswith('broken')], indent=1))
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
