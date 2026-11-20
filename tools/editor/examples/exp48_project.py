"""EXP-48's project: recipe point lights on the game's blank map, CB2_MP_Blank (prefab plan, stage L1.3).

The blank map has no point or spot light of its own, so every light here is made from the editor's built-in recipes
(tools/bake/light_factory.py): a warm point light inside EXP-44's hut, a green point light over open ground, and a
blue recipe spot light beside it as the known case (EXP-26). The hut is exp44_project.py's, piece for piece.
Usage: exp48_project.py <out> [--quick | --compile] [--store]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. The library
must have been scanned (viewer.py library scan) and the blank map opened once in the editor (its export). The
lighting is baked unless --quick is given.

--store saves the project in the editor's own project store instead (its next revision) and builds it into the
editor's builds folder, so that the editor's Play in game finds it as the project's last build and plays it as it
is."""
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

MAP, HOME = 'CB2_MP_Blank', 'URB_ResearchOutpost'
s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]
cache = s['cache']
_, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=hashlib.sha256(
    build.lwr_file(game, 'CookedPCConsole', MAP + '.upk').read_bytes()).hexdigest(), exporterVersion=20)))
origin = scene['tileGrid']['origin'][:3]
PL = 'TheWorld.PersistentLevel.'
STEP = (96.0, 96.0, 64.0)
# the shed's pieces on its home map (what, actor)
PIECES = [
    ('wall, south (cuts down)', 'XComDecoFracLevelActor_100'),
    ('wall, west (cuts down)', 'XComDecoFracLevelActor_101'),
    ('wall, east (cuts down)', 'XComDecoFracLevelActor_98'),
    ('wall, north (cuts down)', 'XComDecoFracLevelActor_99'),
    ('roof', 'XComFracLevelActor_55'),
    ('freight door, open (cuts down)', 'XComDestructibleActor_159'),
    ('swing door: leaf and frame', 'XComInteractiveLevelActor_17'),
    ('tarped crate', 'XComDestructibleActor_162'),
    ('tarped crate', 'XComDestructibleActor_93'),
    ('small generator', 'XComDestructibleActor_421'),
    ('utility box', 'XComDestructibleActor_157'),
]
# the shed's two floor volumes on its home map (XComFloorVolume_51 and _45): [x0, y0, z0, x1, y1, z1]
FLOORS = [[-192.0, -1536.0, 0.0, 384.0, -960.0, 176.0], [-192.0, -1536.0, 176.0, 384.0, -960.0, 384.0]]
# where the ground floor's south-west corner should be: north-east of the squad's start, clear of the map's own pieces
WANT = [432.0, 912.0, 0.0]

records = [library.piece(cache, game, dict(package=HOME, level='base', actor=actor)) for _, actor in PIECES]
grid = records[0]['grid']
# the home map's place rebased on this map's grid, then moved by whole tiles and storeys
rebase = [origin[i] - grid[i] for i in range(3)]
shift = [round((WANT[i] - (FLOORS[0][i] + rebase[i])) / STEP[i]) * STEP[i] for i in range(3)]
move = [rebase[i] + shift[i] for i in range(3)]
added, plan, seen = [], [], set()
for (what, actor), record in zip(PIECES, records):
    actors = {}
    for o in record['objects']:
        actors.setdefault(o['actor'], []).append(o)
    for name, parts in sorted(actors.items()):
        if name in seen:
            continue
        seen.add(name)
        serial = len(added) + 1
        added.append({'id': '00000000-0000-4000-8000-%012d' % serial, 'actor': '%s_copy%d' % (name, serial),
                      'from': dict(package=HOME, level='base', actor=name),
                      'components': sorted(o['component'] for o in parts),
                      'location': [round(parts[0]['location'][i] + move[i], 4) for i in range(3)],
                      'rotation': list(parts[0]['rotation'])})
        plan.append(dict(what=what, actor=name.rsplit('.', 1)[-1], cls=parts[0]['actorClass'],
                         location=added[-1]['location'], rotation=added[-1]['rotation']))
        print(what, '|', name.rsplit('.', 1)[-1], parts[0]['actorClass'], '->', added[-1]['location'])
floors = [[round(v + move[k % 3], 4) for k, v in enumerate(box)] for box in FLOORS]
# the lights: each made from a recipe, with every value (a point light has no cones)
POINT, SPOT = compiler.LIGHT_RECIPES['point'][1], compiler.LIGHT_RECIPES['spot'][1]
x0, y0, _, x1, y1, _ = floors[0]
LIGHTS = [
    ('point light, warm, inside the hut', 'point', [(x0 + x1) / 2, (y0 + y1) / 2, 128.0], [0, 0, 0],
     dict(POINT, color=[255, 170, 80], brightness=2.0, radius=420.0)),
    ('point light, green, over open ground', 'point', [x0 - 480.0, y0 - 96.0, 160.0], [0, 0, 0],
     dict(POINT, color=[80, 255, 120], brightness=2.0, radius=520.0)),
    ('spot light, blue, pointing down (the known case)', 'spot', [x0 - 480.0, y0 + 480.0, 256.0], [-16384, 0, 0],
     dict(SPOT, color=[90, 150, 255], brightness=2.0, radius=640.0)),
]
for what, kind, at, rotation, values in LIGHTS:
    serial = len(added) + 1
    added.append({'id': '00000000-0000-4000-8000-%012d' % serial,
                  'actor': '%s%sLight_copy%d' % (PL, 'Point' if kind == 'point' else 'Spot', serial),
                  'template': dict(kind=kind, version=1), 'location': at, 'rotation': rotation, 'light': dict(values)})
    plan.append(dict(what=what, actor=added[-1]['actor'].rsplit('.', 1)[-1], cls=kind, location=at, rotation=rotation))
    print(what, '->', at)
buildings = [dict(id='00000000-0000-4000-8000-0000000b0001', name='Hut', kind='building',
                  floors=[dict(boxes=[box]) for box in floors])]
print('building floors', floors)
# what of the map's own stands in the hut's footprint
for o in scene.get('objects') or []:
    at = o.get('location') or [1e9, 1e9, 0]
    if x0 - 96 <= at[0] <= x1 + 96 and y0 - 96 <= at[1] <= y1 + 96 and o.get('actorClass') != 'XComLevelActor':
        print('  in the footprint:', o.get('actor'), o.get('actorClass'), [round(v) for v in at])
doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id='00000000-0000-4000-8000-000000000e48',
           name='EXP-48 point lights', mode='edit', revision=1, savedAt='2026-11-11T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=scene['source']['sha256'], exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='CB2_MP_Blank_X48', patch='patch_cb2_mp_blank_x48'), overrides=[], added=added,
           buildings=buildings, nextSerial=len(added) + 1)
OUT.mkdir(parents=True, exist_ok=True)
builds = OUT / 'builds'
if '--store' in sys.argv:
    import projects
    store = projects.ProjectStore(s['projects'])
    try:
        revision = store.load(doc['id']).get('revision', 0)
    except projects.ProjectError:
        revision = 0
    saved = store.save(doc['id'], {k: v for k, v in doc.items() if k not in ('revision', 'savedAt')}, revision)
    project, builds = store.path(doc['id']), Path(s['output'])
    doc = store.load(doc['id'])
    print('saved in the editor\'s store as revision %d: %s' % (saved['revision'], project.name))
else:
    project = OUT / 'project.json'
    project.write_text(json.dumps(doc, indent=1), encoding='utf-8', newline='\n')
(OUT / 'plan.json').write_text(json.dumps(dict(pieces=plan, buildings=buildings), indent=1), encoding='utf-8', newline='\n')
enable = ('building',)
spec, report = compiler.compile_project(doc, scene, enable, compiler.Library(cache, game), ())
print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:200]) for e in report['errors']])
print('warnings', [(w['code'], w['message'][:160]) for w in report['warnings']])
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(build.BuildInputs(project, cache, builds, game, None, quick='--quick' in sys.argv,
                                      enable=enable)).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'foreignPieces', 'buildings', 'lights', 'seconds')}))
print('shell', m.get('shell'))
print('package', builds / m['variant'])
for stage in m['stages']:
    if stage.get('buildings') and stage.get('stage') == 'light':
        print(json.dumps(stage['buildings'], indent=1))
