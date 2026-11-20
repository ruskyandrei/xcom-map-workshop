"""EXP-72's base spawn point project (private/plans/todo/editor-spawns-implementation-plan.md, stage SP6): URB_Bar's
abduction with its own spawn points edited in place, built quick with the spawn family on (--family spawn):

- pod 0 (XComAlienPod_Abduction_0) moved one tile across and turned a quarter;
- pod 1 made the commander's pod (a flag the pod saves none of);
- Meld point 2 (easy, destroyed on turn 4) made hard and destroyed on turn 6;
- Meld point 3 put in spawn group 1.

Usage: exp72_sp6_project.py <projects folder> <builds folder> --cache <cache> [--compile] [--again] [--cleared]
       [--grid X Y Z]

The export of URB_Bar in <cache> must be export 33 or later. --again builds a second time into <builds folder>/again
and says whether the map comes out byte for byte the same. --cleared builds the same edits on the cleared map, --grid on
the map's grid resized (a project of its own id each, so the store keeps all three)."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / 'tools' / 'editor'), str(REPO / 'tools' / 'viewer')]
import build  # noqa: E402
import compiler  # noqa: E402
import projects  # noqa: E402
import settings as settings_module  # noqa: E402

PROJECT_ID = '00000000-0000-4000-8000-000000072006'
PL = 'TheWorld.PersistentLevel.'

ap = argparse.ArgumentParser()
ap.add_argument('projects', type=Path)
ap.add_argument('builds', type=Path)
ap.add_argument('--cache', type=Path, required=True)
ap.add_argument('--compile', action='store_true')
ap.add_argument('--again', action='store_true')
ap.add_argument('--cleared', action='store_true')
ap.add_argument('--grid', type=int, nargs=3)
a = ap.parse_args()

s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]
folder = next(f for f in sorted(a.cache.glob('URB_Bar/*-map*'), reverse=True)
              if (json.loads((f / 'scene.json').read_text(encoding='utf-8')).get('exporterVersion') or 0) >= 33)
scene = json.loads((folder / 'scene.json').read_text(encoding='utf-8'))
spawns = {r['actor'].rsplit('.', 1)[-1]: r for r in scene['spawns']}
pod0 = spawns['XComAlienPod_Abduction_0']
target = lambda name: dict(package='URB_Bar', level='base', actor=PL + name)  # noqa: E731
overrides = [
    dict(target=target('XComAlienPod_Abduction_0'), location=[pod0['location'][0] + 96, pod0['location'][1], pod0['location'][2]],
         rotation=[pod0['rotation'][0], pod0['rotation'][1] + 16384, pod0['rotation'][2]]),
    dict(target=target('XComAlienPod_Abduction_1'), spawn=dict(commander=True)),
    dict(target=target('XComMeldContainerSpawnPoint_2'), spawn=dict(difficulty='Hard', destroyedOnTurn=6)),
    dict(target=target('XComMeldContainerSpawnPoint_3'), spawn=dict(spawnGroup=1)),
]
src = scene['source']
doc = dict(schema=projects.SCHEMA, schemaVersion=projects.SCHEMA_VERSION, id=PROJECT_ID, name='EXP-72 Bar spawn points',
           mode='edit', source=dict(map='URB_Bar', package=Path(src['file']).name, sha256=src['sha256'],
                                    exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='URB_Bar_X72S', patch='patch_urb_bar_x72s'), overrides=overrides, added=[], groups=[],
           areaLightBindings=[], missions=[dict(record=0)])
if a.cleared or a.grid:
    suffix = ('C' if a.cleared else '') + ('G' if a.grid else '')
    PROJECT_ID = PROJECT_ID[:-1] + ('7' if a.cleared and not a.grid else '8' if a.grid and not a.cleared else '9')
    doc.update(id=PROJECT_ID, name='EXP-72 Bar spawn points %s' % suffix,
               output=dict(shipAs='URB_Bar_X72S' + suffix, patch='patch_urb_bar_x72s' + suffix.lower()))
    if a.cleared:
        doc['cleared'] = True
    if a.grid:
        doc['stage'] = dict(grid=a.grid)
store = projects.ProjectStore(str(a.projects))
try:
    revision = store.load(PROJECT_ID).get('revision', 0)
except projects.ProjectError:
    revision = 0
saved = store.save(PROJECT_ID, doc, revision)
doc = store.load(PROJECT_ID)
spec, report = compiler.compile_project(doc, scene, ('spawn',), compiler.Library(str(a.cache), game), ())
print('revision %d: %s' % (saved['revision'], 'compile ok' if report['ok'] else 'COMPILE ERRORS'),
      [(e['code'], e['message'][:200]) for e in report['errors']], report['counts'].get('spawns'))
for d in report['warnings'] + report['notes']:
    print('  %s %s: %s' % ('warning' if d in report['warnings'] else 'note', d['code'], d['message'][:220]))
if not report['ok'] or a.compile:
    sys.exit(0 if report['ok'] else 1)


def built(out):
    m = build.Build(build.BuildInputs(store.path(PROJECT_ID), str(a.cache), out, game, None, quick=True,
                                      enable=('spawn',))).run()
    upk = out / m['variant'] / 'CookedPCConsole' / ('%s.upk' % m['variant'])
    print('built %s in %ss: spawnEdits %s, lightingUnchanged %s, %s' % (m['variant'], m.get('seconds'), m.get('spawnEdits'),
                                                                       m.get('lightingUnchanged'), hashlib.sha256(upk.read_bytes()).hexdigest()[:16]))
    return m, upk


m, upk = built(a.builds)
if a.again:
    again = a.builds / 'again'
    shutil.rmtree(again, ignore_errors=True)
    _, upk2 = built(again)
    print('second build byte for byte the first:', upk.read_bytes() == upk2.read_bytes())
