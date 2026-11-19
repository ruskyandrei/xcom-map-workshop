"""EXP-83's project: broken roofs kept whole in battle, and one let break further (F-139), on URB_Bar.

- The bar's roof XComFracLevelActor_3 (at (-1056, 576, 400): x -1632 to -480, y 96 to 1248, its top at 402; it keeps
  its fragments, bPreventChunkRemoval) broken where it stands by a blast of two tiles at local (-288, 288, 0), as in
  EXP-82: 7 of its 81 fragments, a hole from x -1536 to -1152, y 672 to 1056. Left as the game keeps its roofs, it
  stays whole in battle: the Build keeps the setting on and points it at a copy of its mesh with those fragments cut
  away (frac_walls.cut_copy).
- The roof's other piece XComFracLevelActor_7 (at (96, 672, 400), yaw -16384: x -480 to 768, y 0 to 1248; it keeps
  its fragments too, and holds the roof's air-conditioning units at x -48 and 42, y 432 and 912) broken by a blast of
  one tile at its far corner, local (-478, 624, 0), the world's (720, 1150), and asked to break further
  (breaksFurther): the setting turned off, as EXP-82's roofs were.
Game tiles count from the map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

Usage: exp83_project.py --store <projects folder> --builds <builds folder> [--build] [--quick]

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
ROOF, ROOF_B = 'XComFracLevelActor_3', 'XComFracLevelActor_7'
PROJECT = ('00000000-0000-4000-8000-0000000e8300', 'EXP-83 kept roofs')
ROOF_BLASTS = [dict(at=[-288.0, 288.0, 0.0], radius=192.0)]
ROOF_B_BLASTS = [dict(at=[-478.0, 624.0, 0.0], radius=96.0)]


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
    overrides = [dict(target=target(ROOF), blasts=ROOF_BLASTS),
                 dict(target=target(ROOF_B), blasts=ROOF_B_BLASTS, breaksFurther=True)]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=4, id=project_id, name=name, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=overrides, added=[], groups=[], nextSerial=1,
               view=dict(camera=[-1400, 700, 1300], target=[-560, 576, 400]))
    if current and current.get('created'):
        doc['created'] = current['created']
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
    print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
    print('notes', json.dumps([(w['code'], w['message']) for w in report['notes'] if w['code'].endswith('broken')], indent=1))
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
