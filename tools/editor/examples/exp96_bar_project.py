"""EXP-96's second project: a building whose floors are the cursor's on URB_Bar as it is (the building cursor floors
plan, stage C5). The boat of the experiment's first map has nothing to stand on off it, so the cursor could not be
carried on and off its building; the bar's lot has open ground all round.

- One building of two floors on the lot west of the bar (x -1728 to -1344, y -1056 to -768, the ground at 0): floor 1
  from 0 to 160, floor 2 from 160 to 352, ticked (`cursorFloors`). Its cursor floors are -2 to 158 and 158 to 352; the
  bar's own four, everywhere else, start at 0, 210, 402 and 594.

Usage: exp96_bar_project.py <out> [--game <install>] [--compile]

The project goes to <out>/project.json and its quick build under <out>/builds (no lighting baked: a cursor check needs
none); the cache is the settings', the game the settings' unless --game names one."""
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
OUT = Path(sys.argv[1])
sys.path[:0] = [str(REPO / 'tools' / 'editor'), str(REPO / 'tools' / 'viewer')]
import build  # noqa: E402
import compiler  # noqa: E402
import settings as settings_module  # noqa: E402

MAP = 'URB_Bar'
s = settings_module.load_settings()
game = Path(sys.argv[sys.argv.index('--game') + 1]) if '--game' in sys.argv else settings_module.resolve_game(s['game'])[0]
cache = s['cache']
sha = hashlib.sha256(build.lwr_file(game, 'CookedPCConsole', MAP + '.upk').read_bytes()).hexdigest()
_, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha, exporterVersion=42)))
FOOT = (-1728.0, -1056.0, -1344.0, -768.0)
tower = dict(id='00000000-0000-4000-8000-000000000961', name='Tower', kind='building', cursorFloors=True,
             floors=[dict(boxes=[[FOOT[0], FOOT[1], z0, FOOT[2], FOOT[3], z1]]) for z0, z1 in ((0.0, 160.0), (160.0, 352.0))])
doc = dict(schema='xcom-map-workshop/project', schemaVersion=compiler.SCHEMA_VERSION, id='00000000-0000-4000-8000-000000000e96',
           name='EXP-96 bar tower', mode='edit', revision=1, savedAt='2026-11-23T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='URB_Bar_X96', patch='patch_urb_bar_x96'), overrides=[], added=[], groups=[],
           buildings=[tower], nextSerial=1)
OUT.mkdir(parents=True, exist_ok=True)
project = OUT / 'project.json'
project.write_text(json.dumps(doc, indent=1), encoding='utf-8', newline='\n')
spec, report = compiler.compile_project(doc, scene, (), compiler.Library(cache, game), ())
print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
print('notes', json.dumps([(n['code'], n['message'][:240]) for n in report['notes'] if n['code'].startswith('building')], indent=1))
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
builds = OUT / 'builds'
try:
    m = build.Build(build.BuildInputs(project, cache, builds, game, None, quick=True)).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'seconds')}, indent=1))
print('package', builds / m['variant'])
