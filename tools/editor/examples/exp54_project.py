"""EXP-54's project: a cleared map played as each kind of mission a record alone gives it (the mission types plan,
private/plans/done/mission-types-plan.md, Part D and section 6).

EXP-51's cleared URB_Bar, played and passed on 13 November (its floors round two landing zones, and the shed of
URB_ResearchOutpost made as a building of the project), copied under a project of its own with:
- `missions`: an added council bomb (Long War's bomb mutator should place the bomb and power nodes of
  URB_Slaughterhouse_Stream on the map), an added terror site, and an added crashed small scout. None of Bar's own
  records: the Build writes the three added ones, each made from Bar's abduction record.
- the shed marked as a UFO building (kind `ufo`), so the crashed UFO has one: Long War puts the commander's pod in it.

Usage: exp54_project.py <out> [--full | --compile] [--store]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. EXP-51's
project must be in the editor's project store (exp51_project.py --store), and Bar opened once in the editor.
Without --full the lighting is not baked. --store saves the project in the editor's own project store instead (its
next revision) and builds it into the editor's builds folder, so that the editor's Play in game finds it as the
project's last build; pick the mission in the header (or the play window) before Play in game."""
import copy
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
OUT = Path(sys.argv[1])
sys.path[:0] = [str(REPO / 'tools' / 'editor'), str(REPO / 'tools' / 'viewer')]
import build  # noqa: E402
import compiler  # noqa: E402
import projects  # noqa: E402
import settings as settings_module  # noqa: E402

BASE_ID = '00000000-0000-4000-8000-000000000e51'
PROJECT_ID = '00000000-0000-4000-8000-000000000e54'
MISSIONS = [dict(kind='Special/Bomb'), dict(kind='TerrorSite'), dict(kind='Crash', ship='eShip_UFOSmallScout')]

s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]
cache = s['cache']
store = projects.ProjectStore(s['projects'])
base = store.load(BASE_ID)
doc = copy.deepcopy({k: v for k, v in base.items() if k not in ('id', 'name', 'output', 'revision', 'savedAt', 'created')})
doc.update(id=PROJECT_ID, name='EXP-54 added missions', output=dict(shipAs='URB_Bar_X54', patch='patch_urb_bar_x54'),
           missions=MISSIONS, revision=1, savedAt='2026-11-15T00:00:00Z')
sheds = [b for b in doc.get('buildings') or [] if b.get('name') == 'Shed']
if len(sheds) != 1:
    raise SystemExit('EXP-51\'s project has no one shed: %s' % [b.get('name') for b in doc.get('buildings') or []])
sheds[0]['kind'] = 'ufo'
print('missions', MISSIONS, '| the shed', sheds[0]['id'], 'as a UFO building')

_, scene = compiler.find_export(cache, doc)
OUT.mkdir(parents=True, exist_ok=True)
builds = OUT / 'builds'
if '--store' in sys.argv:
    try:
        revision = store.load(PROJECT_ID).get('revision', 0)
    except projects.ProjectError:
        revision = 0
    saved = store.save(PROJECT_ID, {k: v for k, v in doc.items() if k not in ('revision', 'savedAt')}, revision)
    project, builds = store.path(PROJECT_ID), Path(s['output'])
    doc = store.load(PROJECT_ID)
    print('saved in the editor\'s store as revision %d: %s' % (saved['revision'], project.name))
else:
    project = OUT / 'project.json'
    project.write_text(json.dumps(doc, indent=1), encoding='utf-8', newline='\n')
spec, report = compiler.compile_project(doc, scene, (), compiler.Library(cache, game), ())
print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
print('notes', json.dumps([(n['code'], n['message'][:200]) for n in report['notes'] if n['code'].startswith('mission')], indent=1))
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(build.BuildInputs(project, cache, builds, game, None, quick='--full' not in sys.argv)).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'seconds')}))
print('missions', m['config'].get('missions'), m['config'].get('recordMissions'))
for line in m['config']['maps']:
    print(' ', line[:400])
print('package', builds / m['variant'])
