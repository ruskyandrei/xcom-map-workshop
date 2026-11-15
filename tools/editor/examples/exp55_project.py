"""EXP-55's project: a data recovery with a capture point moved (the mission types plan,
private/plans/done/mission-types-plan.md, Part E and section 6).

URB_PoliceStation's data recovery streams URB_PoliceStation_CNH, which has two capture points, each a group of a
capture volume (`XComCapturePointVolume_1`: about seven tiles by six) and the actor it captures
(`XComCapturePointActor_0`), in a room of the police station (`XComBuildingVolume_2`) on its raised floor (z 80).
This project moves capture point 1's group, both parts by one offset of whole tiles at the same height, to the
nearest place at least MIN_TILES away, clear of where it was, inside the same building, whose every tile has floor
at the height of the floor the captured actor stands on (the map's saved floor tiles): a block of the station's
ground floor nine tiles along y. Nothing else is edited: the Build writes the variant's copy of the stream with the two parts moved in place
(stream_copy.py --moves), which the data recovery's record streams, and seeds and rebuilds the base map's tiles under
a moved part that touches them.

Usage: exp55_project.py <out> [--compile] [--store]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. Police Station
must have an export 24 in the cache (its mission objects). --store saves the project in the editor's own project
store (its next revision) and builds it into the editor's builds folder, so that the editor's Play in game finds it
as the project's last build; pick Data recovery in the header before Play in game. A plan of the move (plan.json)
goes beside it in <out>."""
import hashlib
import json
import math
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
OUT = Path(sys.argv[1])
sys.path[:0] = [str(REPO / 'tools' / 'editor'), str(REPO / 'tools' / 'viewer')]
import build  # noqa: E402
import compiler  # noqa: E402
import projects  # noqa: E402
import settings as settings_module  # noqa: E402

MAP, STREAM = 'URB_PoliceStation', 'URB_PoliceStation_CNH'
GROUP, OTHER = 'capture:XComCapturePointVolume_1', 'capture:XComCapturePointVolume_0'
PROJECT_ID = '00000000-0000-4000-8000-000000000e55'
MIN_TILES, SEARCH = 6, 24

s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]
cache = s['cache']
sha = hashlib.sha256(build.lwr_file(game, 'CookedPCConsole', MAP + '.upk').read_bytes()).hexdigest()
_, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha, exporterVersion=24)), minimum=24)
grid = scene['tileGrid']
(ox, oy, oz), (sx, sy, sz) = grid['origin'][:3], (grid.get('size') or [96, 96, 64])[:3]
objects = scene['streams'][STREAM]['missionObjects']
members = [o for o in objects if o.get('group') == GROUP]
volume = next(o for o in members if o['actorClass'] == 'XComCapturePointVolume')
actor = next(o for o in members if o['actorClass'] == 'XComCapturePointActor')
other = next(o for o in objects if o.get('group') == OTHER and o['actorClass'] == 'XComCapturePointVolume')
heights = {}
for f in scene['tactical']['floorTiles']:
    heights.setdefault(tuple(f['tile'][:2]), []).append(f['location'][2])
tile = lambda p: (math.floor((p[0] - ox) / sx), math.floor((p[1] - oy) / sy), math.floor((p[2] - oz) / sz))  # noqa: E731


def box_tiles(box, d=(0, 0)):
    """The tiles whose centres are inside a volume's box across, moved by d tiles."""
    b0, b1 = box['min'], box['max']
    return [(x + d[0], y + d[1]) for x in range(grid['dimensions'][0]) for y in range(grid['dimensions'][1])
            if b0[0] <= ox + (x + 0.5) * sx <= b1[0] and b0[1] <= oy + (y + 0.5) * sy <= b1[1]]


here = box_tiles(volume['box'])
at = tile(actor['location'])
floor_z = min(heights[at[:2]], key=lambda z: abs(z - actor['location'][2]))   # the floor the actor stands on
floored = lambda t: any(abs(z - floor_z) <= 6 for z in heights.get(t, ()))  # noqa: E731
had = sum(map(floored, here))
inside = lambda t, b: b['min'][0] <= ox + (t[0] + 0.5) * sx <= b['max'][0] and b['min'][1] <= oy + (t[1] + 0.5) * sy <= b['max'][1]  # noqa: E731
floor_boxes = lambda b: [box for f in b['floors'] if f['bottom'] - 8 <= floor_z <= f['top'] for box in f['boxes']]  # noqa: E731
building = next(b for b in scene['buildings'] if any(inside(t, box) for box in floor_boxes(b) for t in here))
home = floor_boxes(building)
blocked = set(box_tiles(other['box'])) | set(here)
best = None
for dx in range(-SEARCH, SEARCH + 1):
    for dy in range(-SEARCH, SEARCH + 1):
        if math.hypot(dx, dy) < MIN_TILES:
            continue
        moved = [(x + dx, y + dy) for x, y in here]
        if any(not (0 <= x < grid['dimensions'][0] and 0 <= y < grid['dimensions'][1]) for x, y in moved):
            continue
        if blocked & set(moved) or not all(map(floored, moved)) or not floored((at[0] + dx, at[1] + dy)):
            continue
        if not all(any(inside(t, box) for box in home) for t in moved):
            continue
        if best is None or math.hypot(dx, dy) < math.hypot(*best):
            best = (dx, dy)
if best is None:
    raise SystemExit('no place for capture point 1 in its building with floor under the whole volume')
offset = [best[0] * sx, best[1] * sy, 0.0]
target = lambda o: dict(package=STREAM, level='stream', actor=o['actor'])  # noqa: E731
overrides = [dict(target=target(o), location=[round(o['location'][k] + offset[k], 4) for k in range(3)],
                  rotation=[int(v) for v in o['rotation']]) for o in members]
plan = dict(group=GROUP, building=building['actor'], offsetTiles=list(best), offset=offset, floorHeight=floor_z, volumeTiles=len(here), floorBefore=had,
            moved=[dict(actor=o['actor'].rsplit('.', 1)[-1], old=o['location'], new=r['location']) for o, r in zip(members, overrides)])
print(json.dumps(plan, indent=1))
centre = [(volume['box']['min'][k] + volume['box']['max'][k]) / 2 + offset[k] for k in range(3)]
doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=PROJECT_ID, name='EXP-55 moved capture point',
           mode='edit', revision=1, savedAt='2026-11-15T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='URB_PoliceS_X55', patch='patch_urb_polices_x55'), overrides=overrides, added=[],
           nextSerial=1, missions=[dict(record=2)],
           # the viewer's basis (x, up, y): east of the moved point and the old place, looking at both
           view=dict(camera=[centre[0] + 1600, 1900, centre[1] - 900], target=[centre[0], 0, centre[1] - 400]))
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'plan.json').write_text(json.dumps(plan, indent=1) + '\n', encoding='utf-8', newline='\n')
builds = OUT / 'builds'
if '--store' in sys.argv:
    store = projects.ProjectStore(s['projects'])
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
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(project, cache, builds, game, None, quick=True).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'seconds', 'streamCopies')}))
for line in m['config']['maps']:
    print(' ', line[:400])
print('package', builds / m['variant'])
