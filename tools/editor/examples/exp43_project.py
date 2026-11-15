"""EXP-43 run 2's project: a few pieces of other maps on the game's blank map, CB2_MP_Blank, which the Build first
equips with soldier spawn points, cursor volumes and a volume template (tools/bake/shell.py).
Usage: exp43_project.py <out> [--full | --compile] [--grid]

--grid is run 3's project: the same on a grid of 54 by 54 tiles (the map's own is 36 by 36), with two more pieces
on the new ground.

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. The library
must have been scanned (viewer.py library scan) and the blank map opened once in the editor (its export). Without
--full the lighting is not baked."""
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

MAP = 'CB2_MP_Blank'
s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]
cache = s['cache']
_, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=hashlib.sha256(
    build.lwr_file(game, 'CookedPCConsole', MAP + '.upk').read_bytes()).hexdigest(), exporterVersion=19)))
origin = scene['tileGrid']['origin'][:3]
PL = 'TheWorld.PersistentLevel.'
STEP = (96.0, 96.0, 64.0)
# (what, home map, a part of it, where it should stand, quarter turns from how it stands at home)
PIECES = [
    # east of the squad's start (x -240 to 48, y 336 to 720), clear of the map's own van, pickup and wall
    ('destructible prop: a dry bush', 'URB_GasStation_EWI', 'XComDestructibleActor_104', [336.0, 336.0, 0.0], 0),
    ('fracturing wall: an abductor wall, three tiles', 'LAbductor_WindingStream', 'XComFracLevelActor_70',
     [528.0, 528.0, 0.0], 0),
    ('car: an SUV with its doors open (body, glass, two doors)', 'URB_OfficePaper_Terror',
     'XComDestructibleActor_388', [432.0, 912.0, 0.0], 0),
    ('van: a moving van (its cab and box, with its own building and floor volumes)', 'URB_ResearchOutpost_EWI',
     'XComDestructibleActor_238', [912.0, 624.0, 0.0], 0),
]
GRID = '--grid' in sys.argv
if GRID:
    PIECES += [
        # on the new ground, past the map's own edge (x 1344, y 2112)
        ('fracturing wall: an abductor wall, on the new ground', 'LAbductor_WindingStream', 'XComFracLevelActor_70',
         [2064.0, 1296.0, 0.0], 0),
        ('destructible prop: a dry bush, on the new ground', 'URB_GasStation_EWI', 'XComDestructibleActor_104',
         [1776.0, 2736.0, 0.0], 0),
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
doc = dict(schema='xcom-map-workshop/project', schemaVersion=1,
           id='00000000-0000-4000-8000-000000000e44' if GRID else '00000000-0000-4000-8000-000000000e43',
           name='EXP-43 blank map stage, 54 by 54' if GRID else 'EXP-43 blank map stage',
           **({'stage': {'grid': [54, 54]}} if GRID else {}), mode='edit', revision=1, savedAt='2026-11-11T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=scene['source']['sha256'], exporterVersion=19),
           output=dict(shipAs='CB2_MP_Blank_X43B' if GRID else 'CB2_MP_Blank_X43',
                       patch='patch_cb2_mp_blank_x43b' if GRID else 'patch_cb2_mp_blank_x43'), overrides=[], added=added, nextSerial=len(added) + 1)
OUT.mkdir(parents=True, exist_ok=True)
project = OUT / 'project.json'
project.write_text(json.dumps(doc, indent=1), encoding='utf-8', newline='\n')
(OUT / 'plan.json').write_text(json.dumps(plan, indent=1), encoding='utf-8', newline='\n')
gates = ()
spec, report = compiler.compile_project(doc, scene, (), compiler.Library(cache, game), gates)
print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:200]) for e in report['errors']])
print('warnings', [(w['code'], w['message'][:160]) for w in report['warnings']])
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(project, cache, OUT / 'builds', game, None, quick='--full' not in sys.argv, foreign=gates).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'foreignPieces', 'seconds')}))
print([(d['map'], d['pieces'], d['objectsBrought'], d['bytes'], len(d['cut'])) for d in m['donors']])
print('shell', m.get('shell'))
