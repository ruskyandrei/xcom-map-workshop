"""EXP-73's project: walls drawn with the wall tool's numbers on a map without the Bar's wall (custom geometry plan,
stage M1, run A), on URB_PoliceStation.

Four copies of URB_Bar's inside wall URB_BarIntWallB_FRACTURED (XComDecoFracLevelActor_17), brought from URB_Bar, as
the editor's wall tool makes them (x0 0 and the piece at the wall's start, on a tile corner, standing on the floor):
- W1, along x on the parking lot (y -2112, x -1440 to -1056, four tiles): a window in its second tile (sill 72, top
  168) and a doorway in its third (to 160);
- W2, along y (a quarter turn: its columns run along y) on the parking lot (x -1152, y -2400 to -2208, two tiles): a
  window in its first tile;
- W3, one tile along x on the parking lot (y -2400, x -1440 to -1344) with an opening over its whole lower storey
  (to 200 over the floor): its lower storey's face slots hold no triangles (an empty section in the game's mesh);
- W4, on the station's roof (z 466; y -1248, x -384 to -96, three tiles): a doorway in its middle tile.
Heights: the parking lot's floor tiles are at 14.5, the roof's at 466 (the export's tactical floor tiles).

Usage: exp73_project.py --store <projects folder> --builds <builds folder> [--build] [--quick]

The project is saved in the store given (a test server's scratch store: Play in game on that server, started with
--dry-play, then stages its build into the lab copy). The game and the cache are the settings'; URB_PoliceStation must
have been opened in the editor, and URB_Bar's piece read once (the library)."""
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

MAP, DONOR_MAP, PL = 'URB_PoliceStation', 'URB_Bar', 'TheWorld.PersistentLevel.'
DONOR = 'XComDecoFracLevelActor_17'
DONOR_COMPONENT = PL + DONOR + '.FracturedStaticMeshComponent_12'
PROJECT = ('00000000-0000-4000-8000-000000000e73', 'EXP-73 wall tool')
LOT, ROOF = 14.5, 466.0
WINDOW = lambda k: dict(x0=96.0 * k, x1=96.0 * k + 96, z0=72.0, z1=168.0)  # noqa: E731
DOORWAY = lambda k: dict(x0=96.0 * k, x1=96.0 * k + 96, z0=-16.0, z1=160.0)  # noqa: E731
WALLS = (
    # (label, location, yaw, length, openings, seed)
    ('W1', [-1440.0, -2112.0, LOT], 0, 384.0, [WINDOW(1), DOORWAY(2)], 731),
    ('W2', [-1152.0, -2400.0, LOT], 16384, 192.0, [WINDOW(0)], 732),
    ('W3', [-1440.0, -2400.0, LOT], 0, 96.0, [dict(x0=0.0, x1=96.0, z0=-16.0, z1=200.0)], 733),
    ('W4', [-384.0, -1248.0, ROOF], 0, 288.0, [DOORWAY(1)], 734),
)


def added():
    return [dict(id='00000000-0000-4000-8000-0000000e73%02d' % (k + 1), actor=PL + '%s_copy%d' % (DONOR, k + 1),
                 **{'from': dict(package=DONOR_MAP, level='base', actor=PL + DONOR)}, components=[DONOR_COMPONENT],
                 location=location, rotation=[0, yaw, 0], prefab=None, partner=None,
                 generated=dict(kind='fracWall', version=1,
                                wall=dict(x0=0.0, x1=length, openings=openings, seed=seed)))
            for k, (_, location, yaw, length, openings, seed) in enumerate(WALLS)]


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
    walls = added()
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=4, id=project_id, name=name, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=[], added=walls, groups=[], nextSerial=len(walls) + 1,
               view=dict(camera=[-900, 1000, -1500], target=[-1200, 16, -2200]))
    if current and current.get('created'):
        doc['created'] = current['created']
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
    print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
    print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
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
