"""EXP-74's projects: made walls lit as the game's are (custom geometry plan, stage M2, run B), on URB_Bar beside its
own inside wall.

Copies of URB_Bar's inside wall URB_BarIntWallB_FRACTURED (XComDecoFracLevelActor_17), as the editor's wall tool makes
them (x0 0 and the piece at the wall's start, on a tile corner, standing on the floor):
- W16, sixteen tiles along x on the pavement before the bar (y -192, x -1728 to -192, the floor at 16), under the
  awning's lamps, two storeys;
- R, the reference: the donor's own mesh lit from nothing as the made walls are, on the pavement past W16's end
  (y -192, x 0 to 576);
- W2, two tiles along x in the parking lot (y -672, x -1728 to -1536, the floor at 0), in the moonlight, two storeys;
- W1, one storey, three tiles along x in the parking lot (y -672, x -1344 to -1056);
- W1a and W1b: a one-storey wall (y -672, x -768 to -480) and another standing on it (the same, 192 higher), as for an
  upstairs room.
Game tiles count from the map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

Two projects, the same walls: `EXP-74 wall light` (built with the lighting baked) and, with --quick-project, `EXP-74
wall light quick` (built without baking: each wall one even light).

Usage: exp74_project.py --store <projects folder> --builds <builds folder> [--quick-project] [--build] [--quick]

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
PROJECTS = {False: ('00000000-0000-4000-8000-000000000e74', 'EXP-74 wall light'),
            True: ('00000000-0000-4000-8000-000000000e75', 'EXP-74 wall light quick')}
PAVEMENT, LOT = 16.0, 0.0
WALLS = (
    # (label, location, length, storeys, seed); None for the reference (the donor's own mesh, relit)
    ('W16', [-1728.0, -192.0, PAVEMENT], 1536.0, 2, 741),
    ('R', [384.0, -192.0, PAVEMENT], None, 2, None),
    ('W2', [-1728.0, -672.0, LOT], 192.0, 2, 742),
    ('W1', [-1344.0, -672.0, LOT], 288.0, 1, 743),
    ('W1a', [-768.0, -672.0, LOT], 288.0, 1, 744),
    ('W1b', [-768.0, -672.0, LOT + 192.0], 288.0, 1, 745),
)


def added(quick):
    out = []
    for k, (_, location, length, storeys, seed) in enumerate(WALLS):
        if length is None:
            generated = dict(kind='relit', version=1)
        else:
            wall = dict(x0=0.0, x1=length, openings=[], seed=seed)
            if storeys == 1:
                wall['storeys'] = 1
            generated = dict(kind='fracWall', version=1, wall=wall)
        out.append(dict(id='00000000-0000-4000-8000-0000000e%d%02d' % (75 if quick else 74, k + 1),
                        actor=PL + '%s_copy%d' % (DONOR, k + 1),
                        **{'from': dict(package=MAP, level='base', actor=PL + DONOR)}, components=[DONOR_COMPONENT],
                        location=location, rotation=[0, 0, 0], prefab=None, partner=None, generated=generated))
    return out


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('--store', type=Path, required=True, help='the projects folder to save it in (a scratch one)')
    a.add_argument('--builds', type=Path, required=True, help='the builds folder to build it into (a scratch one)')
    a.add_argument('--quick-project', action='store_true', help='the second project (built without baking)')
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
    project_id, name = PROJECTS[args.quick_project]
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
    walls = added(args.quick_project)
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=projects.SCHEMA_VERSION, id=project_id, name=name, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=[], added=walls, groups=[], nextSerial=len(walls) + 1,
               view=dict(camera=[-900, 900, -1200], target=[-900, 16, -400]))
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
