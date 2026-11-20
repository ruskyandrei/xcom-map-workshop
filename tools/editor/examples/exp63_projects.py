"""EXP-63's projects: the lighting file named after the map (output names plan, stage N4), two variants of URB_Bar
whose lighting visibly changes, each built with its lighting baked into its own <Map>_Lighting.tfc.

- "Output Names Lighting Tests" builds as OutputNamesLightingTests, a map name of the full 24 characters, so its cache
  is OutputNamesLightingTests_Lighting.tfc (a 33-character name). Its edit is EXP-17 run 9's: the pool table
  (XComDestructibleActor_491) deleted with the glass on its edge (XComDestructibleActor_45), its shadow and bounce
  taken out of the room's baked light.
- "EXP-63 second" builds as EXP63Second (EXP63Second_Lighting.tfc). Its edit is EXP-17 run 11's: a copy of the claw
  machine (XComDestructibleActor_316) under the ceiling spot at (-48, 1008), its shadow baked into the floor.

Both are saved in the editor's own project store (their next revision on a second run) with the map names the store's
rules give (tools/viewer/outputnames.py: allocated on the first save against the projects, the builds and the game
install, then fixed), and with --build built with the lighting baked into the editor's builds folder, so that the
editor's Play in game plays each as its project's last build. The game, the cache and the folders are the settings'.

  python -B tools/editor/examples/exp63_projects.py [--build] [--quick]
"""
import argparse
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
POOL_TABLE, GLASS, CLAW = 'XComDestructibleActor_491', 'XComDestructibleActor_45', 'XComDestructibleActor_316'
FIRST = ('00000000-0000-4000-8000-000000000e63', 'Output Names Lighting Tests')
SECOND = ('00000000-0000-4000-8000-000000000e64', 'EXP-63 second')
COPY_ID = '00000000-0000-4000-8000-0000000e6301'
CLAW_AT = (-48.0, 1008.0)


def target(name):
    return dict(package=MAP, level='base', actor=PL + name)


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('--build', action='store_true', help='build both into the editor\'s builds folder')
    a.add_argument('--quick', action='store_true', help='with --build: without baking (to check the rest first)')
    args = a.parse_args()
    s = settings_module.load_settings()
    game = settings_module.resolve_game(s['game'])[0]
    if game is None:
        raise SystemExit('set the game install first')
    base = build.lwr_file(game, 'CookedPCConsole', MAP + '.upk')
    sha = build.sha256(base)
    export, scene = compiler.find_export(s['cache'], dict(source=dict(map=MAP, sha256=sha, exporterVersion=build.EXPORT_MINIMUM)),
                                         minimum=build.EXPORT_MINIMUM)
    print('base map %s (SHA-256 %s), export %s' % (base, sha[:12], export))
    claw = [o for o in scene['objects'] if o['layer'] == 'base' and o['actor'] == PL + CLAW]
    edits = {
        FIRST[0]: dict(overrides=[dict(target=target(n), deleted=True) for n in (POOL_TABLE, GLASS)], added=[],
                       view=dict(camera=[-600, 700, 300], target=[-300, 0, 700])),
        SECOND[0]: dict(overrides=[], added=[dict(id=COPY_ID, actor=PL + CLAW + '_copy1', **{'from': target(CLAW)},
                                                   components=sorted(o['component'] for o in claw),
                                                   location=[CLAW_AT[0], CLAW_AT[1], claw[0]['location'][2]],
                                                   rotation=list(claw[0]['rotation']))],
                        view=dict(camera=[round(CLAW_AT[0] + 300), 700, round(CLAW_AT[1] - 450)],
                                  target=[round(CLAW_AT[0]), 0, round(CLAW_AT[1])])),
    }
    store = projects.ProjectStore(s['projects'])
    streams = outputnames.base_streams(game, MAP)
    built = []
    for project_id, name in (FIRST, SECOND):
        try:
            current = store.load(project_id)
        except projects.ProjectError:
            current = None
        if current and outputnames.valid_output(current.get('output')):
            output = current['output']          # fixed at the first save
        else:
            claims = outputnames.Claims(store.root, s['output'], [game])
            output = outputnames.allocate(name, claims.taken, streams)
            print('%s: %s' % (name, output.pop('reason') or 'its name as one word'))
        doc = dict(schema='xcom-map-workshop/project', schemaVersion=2, id=project_id, name=name, mode='edit',
                   source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
                   output=output, groups=[], nextSerial=len(edits[project_id]['added']) + 1, **edits[project_id])
        if current and current.get('created'):
            doc['created'] = current['created']
        spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
        if not report['ok']:
            raise SystemExit('%s does not compile: %s' % (name, [e['message'] for e in report['errors']]))
        saved = store.save(project_id, doc, current['revision'] if current else 0)
        print('saved %s as revision %d (%s): builds as %s, its cache %s.tfc'
              % (name, saved['revision'], saved['file'], output['shipAs'], outputnames.cache_name(output['shipAs'])))
        built.append(project_id)
    if not args.build:
        return
    play = settings_module.install_game(s)[0]
    for project_id in built:
        m = build.Build(build.BuildInputs(store.path(project_id), s['cache'], s['output'], game, s['udk'],
                                          quick=args.quick, games=[play] if play else [])).run()
        print('built %s: cache %s, files %s' % (m['buildId'], m['cache'], sorted(Path(f).name for f in m['files'])))


if __name__ == '__main__':
    main()
