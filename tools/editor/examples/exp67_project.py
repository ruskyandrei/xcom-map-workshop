"""EXP-67's project: fracturing walls made from numbers (custom geometry plan, section 0, stages F3 and F4), on the
pavement in front of URB_Bar.

Three copies of the bar's inside wall URB_BarIntWallB_FRACTURED (XComDecoFracLevelActor_17), each a copy of the
same piece at yaw 0 along the tile edge y -192 between the pavement's middle and south rows, two tiles or more apart,
west to east (x rising):
- Reference: the donor's own mesh, lit fresh as the made walls are (generated kind `relit`), so that it and the twin
  differ only in their meshes. Its box runs from x -1720 to -1160.
- Twin: a wall made from numbers on the donor's own tiles in its frame (x -384 to 192 there; its solid, 8 in from
  each end, is the donor's -376 to 184), its slots and materials the donor's, its fragments new (seed 1). Its box runs
  from x -952 to -392.
- Custom: a wall made from numbers four tiles long (x 0 to 384 in its frame, its solid 8 to 376) with a doorway one
  tile wide and 176 tall (x 96 to 192, z -16 to 160), seed 2. Its box runs from x -184 to 184, the doorway from -96
  to 0.
The build makes their meshes and fragment columns (tools/bake/frac_walls.py) and lights them from nothing.

Usage: exp67_project.py [--build] [--quick] [--out <folder>]

Without --out the project is saved in the editor's own project store (its next revision on a second run) with the map
name the store's rules give, and --build builds it into the editor's builds folder, so that the editor's Play in game
plays it as the project's last build. With --out the project and its build go under <folder> (a scratch folder)
instead. --quick builds without baking (the walls then carry their donor's lightmap, which doesn't fit them). The game
and the cache are the settings'; URB_Bar must have been opened in the editor."""
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
PROJECT = ('00000000-0000-4000-8000-000000000e67', 'EXP-67 fracturing walls')
Z, EDGE = 16.0, -192.0          # the pavement's top (the donor's own z in the bar); a tile edge along the pavement
WALLS = (
    # (label, x, generated)
    ('Reference', -1344.0, dict(kind='relit', version=1)),
    ('Twin', -576.0, dict(kind='fracWall', version=1, wall=dict(x0=-384.0, x1=192.0, openings=[], seed=1))),
    ('Custom', -192.0, dict(kind='fracWall', version=1,
                            wall=dict(x0=0.0, x1=384.0, openings=[dict(x0=96.0, x1=192.0, z0=-16.0, z1=160.0)], seed=2))),
)


def target(name):
    return dict(package=MAP, level='base', actor=PL + name)


def added(scene):
    parts = [o for o in scene['objects'] if o['layer'] == 'base' and o['actor'] == PL + DONOR]
    if not parts:
        raise SystemExit('%s is not in this export of %s' % (DONOR, MAP))
    return [dict(id='00000000-0000-4000-8000-0000000e67%02d' % (k + 1), actor=PL + '%s_copy%d' % (DONOR, k + 1),
                 **{'from': target(DONOR)}, components=sorted(o['component'] for o in parts), location=[x, EDGE, Z],
                 rotation=[0, 0, 0], prefab=None, partner=None, generated=generated)
            for k, (_, x, generated) in enumerate(WALLS)]


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('--build', action='store_true', help='build it (into the editor\'s builds folder, or <out>/builds)')
    a.add_argument('--quick', action='store_true', help='with --build: without baking (to check the rest first)')
    a.add_argument('--out', type=Path, help='a scratch folder for the project and its build, in place of the store')
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
    walls = added(scene)
    project_id, name = PROJECT
    current = None
    if args.out is None:
        store = projects.ProjectStore(s['projects'])
        try:
            current = store.load(project_id)
        except projects.ProjectError:
            pass
    if current and outputnames.valid_output(current.get('output')):
        output = current['output']          # fixed at the first save
    elif args.out is None:
        claims = outputnames.Claims(store.root, s['output'], [game])
        output = outputnames.allocate(name, claims.taken, outputnames.base_streams(game, MAP))
        print('%s: %s' % (name, output.pop('reason') or 'its name as one word'))
    else:
        output = dict(shipAs='URB_Bar_X67', patch='patch_urb_bar_x67')
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=2, id=project_id, name=name, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=[], added=walls, groups=[], nextSerial=len(walls) + 1,
               # the viewer's basis (x, up, y): south of the pavement, looking north at the three walls
               view=dict(camera=[-760, 900, -1500], target=[-760, 150, -192]))
    if current and current.get('created'):
        doc['created'] = current['created']
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
    print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
    print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
    print('notes', json.dumps(sorted({n['code'] for n in report['notes']})))
    if not report['ok'] or report['leftOut']:
        raise SystemExit(1)
    if args.out is None:
        saved = store.save(project_id, doc, current['revision'] if current else 0)
        project, builds = store.path(project_id), Path(s['output'])
        print('saved %s as revision %d (%s): builds as %s' % (name, saved['revision'], saved['file'], output['shipAs']))
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        project, builds = args.out / 'project.json', args.out / 'builds'
        project.write_text(json.dumps(doc, indent=1), encoding='utf-8', newline='\n')
    if not args.build:
        return
    play = settings_module.install_game(s)[0] if args.out is None else None
    try:
        m = build.Build(build.BuildInputs(project, s['cache'], builds, game, s['udk'], quick=args.quick,
                                          games=[play] if play else [])).run()
    except build.BuildError as error:
        raise SystemExit('build failed: %s' % error)
    print(json.dumps({k: m.get(k) for k in ('buildId', 'variant', 'quick', 'seconds')}))
    print('package', builds / m['variant'])


if __name__ == '__main__':
    main()
