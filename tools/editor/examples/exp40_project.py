"""EXP-40's project: a car, a door with its frame and a ladder from other maps in URB_Bar, built by the Build with
their gates lifted. Usage: exp40_project.py <out> [--full | --compile]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. The library
must have been scanned (viewer.py library scan). Without --full the lighting is not baked."""
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
OUT = Path(sys.argv[1])
sys.path[:0] = [str(REPO / 'tools' / 'editor'), str(REPO / 'tools' / 'viewer')]
import build  # noqa: E402
import compiler  # noqa: E402
import library  # noqa: E402
import settings as settings_module  # noqa: E402

s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]
cache = s['cache']
_, scene = compiler.find_export(cache, dict(source=dict(map='URB_Bar', sha256=hashlib.sha256(
    build.lwr_file(game, 'CookedPCConsole', 'URB_Bar.upk').read_bytes()).hexdigest(), exporterVersion=19)))
origin = scene['tileGrid']['origin'][:3]
PL = 'TheWorld.PersistentLevel.'
STEP = (96.0, 96.0, 64.0)
# (what, home map, a part of it, where it should stand, quarter turns from how it stands at home)
PIECES = [
    ('car: an SUV with its doors open (body, glass, two doors)', 'URB_OfficePaper_Terror',
     'XComDestructibleActor_388', [1250.0, -800.0, 0.0], 0),
    ('door with a frame: a barn door', 'URB_SmallCemetery', 'XComInteractiveLevelActor_101', [1536.0, -1104.0, 0.0], 0),
    # on the bar's outer wall, five tiles along from the bar's own ladder (past the ice box) and turned as it is
    ('ladder: a drain pipe, seven storeys', 'URB_ConvienienceStore_EWI', 'XComLadder_1', [-48.0, 1296.0, 16.0], 2),
]
added, plan, serial = [], [], 0
for what, package, actor, want, turns in PIECES:
    record = library.piece(cache, game, dict(package=package, level='base', actor=actor))
    whole = record.get('assembly')
    head = next(o for o in record['objects'] if o['actor'] == (whole['pivot'] if whole else PL + actor))
    # as it stands on its own grid, moved by whole tiles and storeys to the tile nearest the spot wanted
    rebased = [h + o - g for h, o, g in zip(head['location'], origin, record['grid'])]
    shift = [round((want[i] - rebased[i]) / STEP[i]) * STEP[i] for i in range(3)]
    actors = {}
    for o in record['objects']:
        actors.setdefault(o['actor'], []).append(o)
    for name, parts in sorted(actors.items()):
        serial += 1
        at = [parts[0]['location'][i] + origin[i] - record['grid'][i] + shift[i] for i in range(3)]
        if turns:       # about the head's own place (the examples turn single pieces only)
            at = [rebased[i] + shift[i] for i in range(3)]
        added.append({'id': '00000000-0000-4000-8000-%012d' % serial, 'actor': '%s_copy%d' % (name, serial),
                      'from': dict(package=package, level='base', actor=name),
                      'components': sorted(o['component'] for o in parts),
                      'location': [round(v, 4) for v in at],
                      'rotation': [parts[0]['rotation'][0], parts[0]['rotation'][1] + 16384 * turns,
                                   parts[0]['rotation'][2]]})
        plan.append(dict(what=what, package=package, actor=name.rsplit('.', 1)[-1], location=added[-1]['location'],
                         rotation=added[-1]['rotation'], assembly=bool(whole)))
        print(what, '|', package, name.rsplit('.', 1)[-1], parts[0]['actorClass'], '->', added[-1]['location'],
              added[-1]['rotation'])
doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id='00000000-0000-4000-8000-000000000e40',
           name='EXP-40 assemblies', mode='edit', revision=1, savedAt='2026-11-11T00:00:00Z',
           source=dict(map='URB_Bar', package='URB_Bar.upk', sha256=scene['source']['sha256'], exporterVersion=19),
           output=dict(shipAs='URB_Bar_X40', patch='patch_urb_bar_x40'), overrides=[], added=added, nextSerial=len(added) + 1)
OUT.mkdir(parents=True, exist_ok=True)
project = OUT / 'project.json'
project.write_text(json.dumps(doc, indent=1), encoding='utf-8', newline='\n')
(OUT / 'plan.json').write_text(json.dumps(plan, indent=1), encoding='utf-8', newline='\n')
gates = ('car', 'door', 'ladder')
spec, report = compiler.compile_project(doc, scene, (), compiler.Library(cache, game), gates)
print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:200]) for e in report['errors']])
print('warnings', [(w['code'], w['message'][:160]) for w in report['warnings']])
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(build.BuildInputs(project, cache, OUT / 'builds', game, None, quick='--full' not in sys.argv,
                                      foreign=gates)).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'foreignPieces', 'seconds')}))
print([(d['map'], d['pieces'], d['objectsBrought'], d['bytes'], len(d['cut'])) for d in m['donors']])
