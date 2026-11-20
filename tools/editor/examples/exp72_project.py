"""EXP-72 run 2's project (private/plans/todo/editor-spawns-implementation-plan.md, stage SP4): EXP-54's cleared
URB_Bar played as an added council bomb, with the bomb and its eight power nodes, which an added bomb takes from
URB_Slaughterhouse_Stream (export 33's `donors`), placed on floor of this map. Each group (the bomb with its button,
floor marker, emitters, rebuild volume, visible point and helper point; each node with its button, emitters and
rebuild volume) is moved whole onto a floor tile that stays, the tiles at least five apart, each part keeping its
height over the floor it stood on.

Usage: exp72_project.py <projects folder> <builds folder> --cache <cache> [--compile]

EXP-54's project must be in the editor's project store (exp54_project.py --store); the export of URB_Bar in <cache>
must be export 33 or later. The project is saved as revision 1 (or its next) in <projects folder> and built quick
into <builds folder>: a test server's (serve --projects, --builds) for a dry Play in game into the lab copy."""
import argparse
import copy
import json
import math
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / 'tools' / 'editor'), str(REPO / 'tools' / 'viewer')]
import build  # noqa: E402
import compiler  # noqa: E402
import projects  # noqa: E402
import settings as settings_module  # noqa: E402

EXP54_ID = '00000000-0000-4000-8000-000000000e54'
PROJECT_ID = '00000000-0000-4000-8000-000000000e72'
KIND = 'Special/Bomb'
APART = 5           # tiles between two groups' places
GROUP_MAIN = ('bomb', 'node')   # the role of each group's main object, which the floor is picked for

ap = argparse.ArgumentParser()
ap.add_argument('projects', type=Path)
ap.add_argument('builds', type=Path)
ap.add_argument('--cache', type=Path, required=True)
ap.add_argument('--compile', action='store_true')
a = ap.parse_args()

s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]
base = projects.ProjectStore(s['projects']).load(EXP54_ID)
doc = copy.deepcopy({k: v for k, v in base.items() if k not in ('id', 'name', 'output', 'revision', 'savedAt', 'created')})
doc.update(schemaVersion=projects.SCHEMA_VERSION, id=PROJECT_ID, name='EXP-72 added bomb placed', output=dict(shipAs='URB_Bar_X72', patch='patch_urb_bar_x72'),
           missions=[dict(kind=KIND)])
doc['overrides'] = [o for o in doc.get('overrides') or [] if (o.get('target') or {}).get('level') != 'stream']

_, scene = compiler.find_export(str(a.cache), doc)
donor = (scene.get('donors') or {}).get(KIND)
if not donor:
    raise SystemExit('the export has no bomb donor: export 33 or later is needed (%s)' % scene.get('exporterVersion'))
stream, objects = donor['stream'], donor['missionObjects']

# the floor tiles that stay with the project's edits, their surfaces' heights (the compiler's own reading)
c = compiler.Compiler(doc, scene, (), compiler.Library(str(a.cache), game), ())
c.run()
stays = c.floor_now()
grid = scene['tileGrid']
corner = compiler.tile_corner(grid)
centre_of = lambda t: [corner[0] + (t[0] + 0.5) * grid['size'][0], corner[1] + (t[1] + 0.5) * grid['size'][1]]  # noqa: E731
floors = {tuple(f['tile']): f['location'][2] for f in (scene.get('tactical') or {}).get('floorTiles') or []
          if tuple(f['tile']) in stays}
# the floor the project's own pieces give (a cleared map's is all of it): the top of the flat box over the tile's centre
for t in c.added_floors()[0]:
    x, y = centre_of(t)
    tops = [b['box'][5] for b in c.copies if b.get('box') and b['box'][0] <= x <= b['box'][1] and b['box'][2] <= y <= b['box'][3]
            and b['box'][5] - b['box'][4] <= compiler.FLOOR_THICK]
    if tops and t not in floors:
        floors[t] = max(tops)
if not floors:
    raise SystemExit('no floor stays on the map')
lowest = min(t[2] for t in floors)
dims = grid['dimensions']       # inside the grid: a cleared map's floor pieces may reach past it
ground = sorted(t for t in floors if t[2] == lowest and 0 <= t[0] < dims[0] and 0 <= t[1] < dims[1])
picked = []
for t in ground:
    if all(math.hypot(t[0] - u[0], t[1] - u[1]) >= APART for u in picked):
        picked.append(t)
groups = sorted({o['group'] for o in objects if o.get('group')}, key=lambda g: (g != 'bomb', g))
if len(picked) < len(groups):
    raise SystemExit('only %d floor tiles %d apart for %d groups' % (len(picked), APART, len(groups)))
# spread them: every k-th of the tiles found, so the groups stand across the fields
step = len(picked) / len(groups)
places = [picked[int(k * step)] for k in range(len(groups))]
moves = []
for group, tile in zip(groups, places):
    parts = [o for o in objects if o.get('group') == group]
    main = next(o for o in parts if o.get('role') in GROUP_MAIN)
    floor = floors[tile]
    centre = centre_of(tile)
    lift = main['location'][2] % 64          # its height over the floor it stood on (Slaughterhouse's: 4 and 8)
    delta = [centre[0] - main['location'][0], centre[1] - main['location'][1], floor + lift - main['location'][2]]
    for o in parts:
        moves.append(dict(target=dict(package=stream, level='stream', actor=o['actor']),
                          location=[round(o['location'][k] + delta[k], 3) for k in range(3)],
                          rotation=[int(round(v)) for v in o.get('rotation') or [0, 0, 0]]))
    print('%-28s tile %s floor %.1f: %s at %s' % (group, tile, floor, main['actor'].rsplit('.', 1)[-1],
                                                 [round(main['location'][k] + delta[k], 1) for k in range(3)]))
doc['overrides'] = doc['overrides'] + moves

store = projects.ProjectStore(str(a.projects))
try:
    revision = store.load(PROJECT_ID).get('revision', 0)
except projects.ProjectError:
    revision = 0
saved = store.save(PROJECT_ID, {k: v for k, v in doc.items() if k not in ('revision', 'savedAt')}, revision)
doc = store.load(PROJECT_ID)
print('saved as revision %d in %s' % (saved['revision'], a.projects))
spec, report = compiler.compile_project(doc, scene, (), compiler.Library(str(a.cache), game), ())
print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
print('warnings', json.dumps([(w['code'], w['message'][:200]) for w in report['warnings']], indent=1))
print('notes', json.dumps([(n['code'], n['message'][:160]) for n in report['notes'] if n['code'].startswith('mission')], indent=1))
if not report['ok'] or a.compile:
    sys.exit(0 if report['ok'] else 1)
m = build.Build(build.BuildInputs(store.path(PROJECT_ID), str(a.cache), a.builds, game, None, quick=True)).run()
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'seconds', 'replaceStreams')}))
print('package', a.builds / m['variant'])
