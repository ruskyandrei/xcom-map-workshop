"""EXP-39's project: one piece of each family from other maps in URB_Bar's car park, built by the Build with the
families' gates lifted. Usage: exp39_project.py <out> [--full | --compile]

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
# (what, home map, actor, where it should stand, on the grid?)
PIECES = [
    ('destructible prop: a dry bush', 'URB_GasStation_EWI', 'XComDestructibleActor_104', [1300.0, -640.0, 0.0], False),
    ('collectible: an alien nav computer', 'CLrgScout_TheBarrens', 'XComCollectible_6', [1392.0, -832.0, 0.0], False),
    ('fracturing wall: an abductor wall, three tiles', 'LAbductor_WindingStream', 'XComFracLevelActor_70', [1150.0, -900.0, 0.0], True),
    ('door: an alien door, one tile', 'CSupplyShip_OverlookA', 'XComInteractiveLevelActor_2', [1440.0, -1056.0, 0.0], True),
    ('physics prop: a body', 'Act2_Pier', 'KAsset_11', [1100.0, -1000.0, 0.0], False),
]
added, plan = [], []
for k, (what, package, actor, want, grid) in enumerate(PIECES, 1):
    record = library.piece(cache, game, dict(package=package, level='base', actor=actor))
    home = record['objects'][0]['location']
    at = list(want)
    if grid:
        # as it stands on its own grid, moved by whole tiles and storeys to the tile nearest the spot wanted
        rebased = [h + o - g for h, o, g in zip(home, origin, record['grid'])]
        at = [rebased[i] + round((want[i] - rebased[i]) / step) * step for i, step in enumerate((96.0, 96.0, 64.0))]
    else:
        at[2] = want[2] + (((home[2] - record['grid'][2] + 32.0) % 64.0) - 32.0 if record.get('grid') else 0.0)
    rotation = list(record['objects'][0]['rotation'])
    added.append({'id': '00000000-0000-4000-8000-%012d' % k, 'actor': PL + '%s_copy%d' % (actor, k),
                  'from': dict(package=package, level='base', actor=PL + actor),
                  'components': sorted(o['component'] for o in record['objects']),
                  'location': [round(v, 4) for v in at], 'rotation': rotation})
    plan.append(dict(what=what, package=package, actor=actor, location=added[-1]['location'], rotation=rotation,
                     home=home, grid=record.get('grid')))
    print(what, '|', package, actor, 'home', [round(v, 1) for v in home], 'grid', record.get('grid'), '->', added[-1]['location'], rotation)
doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id='00000000-0000-4000-8000-000000000e39',
           name='EXP-39 families', mode='edit', revision=1, savedAt='2026-11-11T00:00:00Z',
           source=dict(map='URB_Bar', package='URB_Bar.upk', sha256=scene['source']['sha256'], exporterVersion=19),
           output=dict(shipAs='URB_Bar_X39', patch='patch_urb_bar_x39'), overrides=[], added=added, nextSerial=len(added) + 1)
OUT.mkdir(parents=True, exist_ok=True)
project = OUT / 'project.json'
project.write_text(json.dumps(doc, indent=1), encoding='utf-8', newline='\n')
(OUT / 'plan.json').write_text(json.dumps(plan, indent=1), encoding='utf-8', newline='\n')
gates = ('destructible', 'collectible', 'fracturing', 'door', 'physics')
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
