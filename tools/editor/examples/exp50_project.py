"""EXP-50's project: the map's own buildings edited in place on URB_Bar (map buildings plan, step E6).

- The bar (XComBuildingVolume_0): its plain ground-floor box XComFloorVolume_14 (in front of the bar's east end)
  stretched four tiles south, over the pavement and the first row of the car park. The Build moves and stretches the
  map's own volume in place (its Location and DrawScale3D); the bar's other seven volumes stay byte for byte.
- The sign (XComBuildingVolume_2, two floors: the business sign on the pavement south of the bar, listed on both)
  moved eight tiles west with the sign itself (XComLevelActor_25), along the pavement (east of it is the landing
  zone and the grounded Skyranger, which would stand in its boxes). The Build moves the building's own two volumes;
  the sign's copy takes the original's place in the lists (the carried listing), the original is hidden.
Bar has no third building that can be edited (its others are vans' or have no floors), so no building is deleted in
this run: that path is the one vans' buildings have taken out of the level since EXP-24.

Usage: exp50_project.py <out> [--full | --compile] [--store]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. Bar must have
been opened once in the editor at export 21. Without --full the lighting is not baked. --store saves the project in
the editor's own project store instead (its next revision) and builds it into the editor's builds folder, so that the
editor's Play in game finds it as the project's last build."""
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
PL = 'TheWorld.PersistentLevel.'
s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]
cache = s['cache']
sha = hashlib.sha256(build.lwr_file(game, 'CookedPCConsole', MAP + '.upk').read_bytes()).hexdigest()
_, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha, exporterVersion=21)))
assert scene['exporterVersion'] >= 21, 'open Bar in the editor first (export 21)'
by_actor = {b['actor']: b for b in scene['buildings']}
objects = {o['actor']: o for o in scene['objects'] if o['layer'] == 'base'}
STRETCH_SOUTH = 4 * 96.0     # XComFloorVolume_14's south side, from y 0 to -384
SIGN_WEST = 8 * 96.0         # the sign and its building


def record(actor, change):
    """The map building's project record (as the editor saves it), its boxes from the export, changed by change(floors)."""
    b = by_actor[actor]
    floors = [dict(boxes=[[*box['min'], *box['max']] for box in f['boxes']], volumes=[v.rsplit('.', 1)[-1] for v in f['volumes']])
              for f in b['floors']]
    change(floors)
    return dict(id='map:PersistentLevel.' + actor, name=actor, kind='building',
                replaces=dict(package=MAP, level='base', actor=PL + actor), floors=floors)


def stretch(floors):
    k = floors[0]['volumes'].index('XComFloorVolume_14')
    floors[0]['boxes'][k][1] -= STRETCH_SOUTH


def move(floors):
    for f in floors:
        f['boxes'] = [[v + (-SIGN_WEST if i % 3 == 0 else 0.0) for i, v in enumerate(box)] for box in f['boxes']]


buildings = [record('XComBuildingVolume_0', stretch), record('XComBuildingVolume_2', move)]
sign = objects[PL + 'XComLevelActor_25']
overrides = [dict(target=dict(package=MAP, level='base', actor=PL + 'XComLevelActor_25'),
                  location=[sign['location'][0] - SIGN_WEST, sign['location'][1], sign['location'][2]],
                  rotation=list(sign['rotation']))]
for b in buildings:
    print(b['name'], json.dumps(b['floors']))
print('sign to', overrides[0]['location'])
doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id='00000000-0000-4000-8000-000000000e50',
           name='EXP-50 map buildings', mode='edit', revision=1, savedAt='2026-11-13T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=21),
           output=dict(shipAs='URB_Bar_X50', patch='patch_urb_bar_x50'), overrides=overrides, added=[],
           buildings=buildings, nextSerial=0,
           # the viewer's basis (x, up, y): south-east of the bar, looking at the stretched box and the sign's new place
           view=dict(camera=[600, 1500, -2600], target=[-200, 0, -900]))
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
spec, report = compiler.compile_project(doc, scene, (), compiler.Library(cache, game), ())
print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
print('map buildings', report.get('mapBuildings'))
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(project, cache, builds, game, None, quick='--full' not in sys.argv).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'buildings', 'seconds')}))
print('package', builds / m['variant'])
for stage in m['stages']:
    if stage.get('buildingEdits'):
        print(json.dumps(stage['buildingEdits'], indent=1)[:6000])
