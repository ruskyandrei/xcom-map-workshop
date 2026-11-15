"""EXP-45's project: a tower of three storeys and a roof, every deck to be walked on, made as a new building on the
game's blank map, CB2_MP_Blank (prefab plan, stage B2).

The tower is put together from pieces of three other maps, four tiles by six:
- walls: URB_Demolition_EWI's site office walls, a storey (192) high, which cut down (plain, with a window, with a
  doorway), eight to a storey;
- decks: CSmallScout_NukedCity's van roof, a slab of four tiles by two, two to a deck. Each deck covers four of the
  six rows and leaves two open for the ladder up to it: the second storey's and the roof's at the north end, the
  third storey's at the south end;
- ladders: URB_PierA_Asian's 192 ladder, one from each deck to the next, inside.
The project asks for one building of four floors (three storeys and the roof's), one box each.

Usage: exp45_project.py <out> [--full | --compile] [--store]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. The library
must have been scanned (viewer.py library scan) and the blank map opened once in the editor (its export). Without
--full the lighting is not baked. --store saves the project in the editor's own project store instead (its next
revision) and builds it into the editor's builds folder, so that the editor's Play in game finds it as the project's
last build."""
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

KIT = dict(plain=('URB_Demolition_EWI', 'XComDestructibleActor_187'),      # a wall of three tiles
           short=('URB_Demolition_EWI', 'XComDestructibleActor_373'),      # a wall of two tiles
           window=('URB_Demolition_EWI', 'XComDestructibleActor_285'),     # three tiles, with a window
           doorway=('URB_Demolition_EWI', 'XComDestructibleActor_230'),    # three tiles, with a doorway
           slab=('CSmallScout_NukedCity', 'XComLevelActor_10'),            # a deck slab, four tiles by two
           ladder=('URB_PierA_Asian', 'XComLadder_3'))                     # climbs 192
records = {k: library.piece(cache, game, dict(package=package, level='base', actor=actor)) for k, (package, actor) in KIT.items()}

T = 96.0
X0, Y0 = 384.0, 960.0                       # the south-west corner, on tile lines; north-east of the squad's start
X1, Y1 = X0 + 4 * T, Y0 + 6 * T
STOREY, LIFT = 192.0, 0.0                   # a deck's top is on its storey's level exactly, as the ground's is
SLAB_TOP = 241.5                            # the slab's collision top over its origin (its home map's file)
BASES = [0.0, STOREY + LIFT, 2 * STOREY + LIFT]         # where each storey's walls and ladder stand
added, plan = [], []


def box_at(kind, location, rotation):
    r = records[kind]
    return compiler.union([compiler.world_box(o, r['meshes'], location, rotation) for o in r['objects']])


def put(kind, what, location, rotation):
    r = records[kind]
    actors = {}
    for o in r['objects']:
        actors.setdefault(o['actor'], []).append(o)
    for name, parts in sorted(actors.items()):
        serial = len(added) + 1
        added.append({'id': '00000000-0000-4000-8000-%012d' % serial, 'actor': '%s_copy%d' % (name, serial),
                      'from': dict(package=KIT[kind][0], level='base', actor=name),
                      'components': sorted(o['component'] for o in parts),
                      'location': [round(v, 4) for v in location], 'rotation': list(rotation)})
        plan.append(dict(what=what, kind=kind, actor=added[-1]['actor'].rsplit('.', 1)[-1], location=added[-1]['location'],
                         rotation=list(rotation), box=[round(v, 1) for v in box_at(kind, location, rotation)]))


def wall(kind, what, side, start, base):
    """A wall on a side of the footprint ('S', 'N': along x from X0 + start; 'W', 'E': along y from Y0 + start), its
    middle on the footprint's line and its foot at `base`."""
    rotation = [0, 0 if side in 'SN' else 16384, 0]
    b = box_at(kind, [0.0, 0.0, 0.0], rotation)
    if side in 'SN':
        location = [X0 + start - b[0], (Y0 if side == 'S' else Y1) - (b[2] + b[3]) / 2, base - b[4]]
    else:
        location = [(X0 if side == 'W' else X1) - (b[0] + b[1]) / 2, Y0 + start - b[2], base - b[4]]
    put(kind, what, location, rotation)


def slab(what, row, level):
    """A deck slab over rows `row` and `row` + 1, its collision top LIFT over `level`."""
    b = box_at('slab', [0.0, 0.0, 0.0], [0, 0, 0])
    put('slab', what, [(X0 + X1) / 2 - (b[0] + b[1]) / 2, Y0 + T * (row + 1) - (b[2] + b[3]) / 2, level + LIFT - SLAB_TOP], [0, 0, 0])


def ladder(what, column, row, north, base):
    """A ladder whose foot tile is (column, row) of the footprint, climbing to the deck over the next row to the
    north (or south): it stands at the middle of its foot tile, as the game's own do."""
    put('ladder', what, [X0 + T * (column + 0.5), Y0 + T * (row + 0.5), base], [0, 16384 if north else -16384, 0])


for n, base in enumerate(BASES):
    storey = 'storey %d' % (n + 1)
    for side in 'SN':
        for start in (0.0, 2 * T):
            wall('short', '%s wall, %s' % (storey, dict(S='south', N='north')[side]), side, start, base)
    wall('doorway' if n == 0 else 'window', '%s wall, west%s' % (storey, ' (the way in)' if n == 0 else ''), 'W', 0.0, base)
    wall('plain', '%s wall, west' % storey, 'W', 3 * T, base)
    wall('window', '%s wall, east' % storey, 'E', 0.0, base)
    wall('plain', '%s wall, east' % storey, 'E', 3 * T, base)
# decks: (name, the level, the two slabs' first rows)
for what, level, rows in (('deck of storey 2', STOREY, (0, 2)), ('deck of storey 3', 2 * STOREY, (2, 4)), ('roof deck', 3 * STOREY, (0, 2))):
    for row in rows:
        slab(what, row, level)
ladder('ladder: ground to storey 2', 1, 4, False, 0.0)
ladder('ladder: storey 2 to storey 3', 2, 1, True, BASES[1])
ladder('ladder: storey 3 to the roof', 1, 4, False, BASES[2])

# the floors' boxes: each from 8 under its deck's level to 8 under the next, so that a deck slab (16 thick, its top
# on the level) is its own storey's alone and the walls under it reach into it and cut down
tops = [STOREY - 8.0, 2 * STOREY - 8.0, 3 * STOREY - 8.0, 760.0]
floors = [[X0, Y0, 0.0 if k == 0 else tops[k - 1], X1, Y1, tops[k]] for k in range(4)]
buildings = [dict(id='00000000-0000-4000-8000-0000000b0045', name='Tower', kind='building',
                  floors=[dict(boxes=[box]) for box in floors])]
for row in plan:
    print('%-34s %-8s %-36s at %s turned %s' % (row['what'], row['kind'], row['actor'], row['location'], row['rotation'][1]))
print('building floors', floors)
doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id='00000000-0000-4000-8000-000000000e46',
           name='EXP-45 tower', mode='edit', revision=1, savedAt='2026-11-11T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=scene['source']['sha256'], exporterVersion=19),
           output=dict(shipAs='CB2_MP_Blank_X45', patch='patch_cb2_mp_blank_x45'), overrides=[], added=added,
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
spec, report = compiler.compile_project(doc, scene, (), compiler.Library(cache, game), ())
print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
print('warnings', json.dumps([(w['code'], w['message'][:200]) for w in report['warnings']], indent=1))
if spec:
    print('ladders', [c for o in spec['objects'] for c in (o.get('ladders') or []) if c])
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(project, cache, builds, game, None, quick='--full' not in sys.argv).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'foreignPieces', 'buildings', 'seconds')}))
print('shell', m.get('shell'))
print('package', builds / m['variant'])
for stage in m['stages']:
    if stage.get('buildings') and stage.get('stage') == 'light':
        print(json.dumps(stage['buildings'], indent=1)[:6000])
