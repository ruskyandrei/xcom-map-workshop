"""EXP-62's project: the piece flags not played yet, in one run on URB_Bar (piece flags plan, P7; EXP-60 played the
mouse on, EXP-61 every flag off on a statue).

On the pavement in front of the bar (its top at 16; three rows of tiles, y -288 to 0; free from x -1728 to 960),
copies with flags, each place two tiles or more from the next, west to east (x rising):
- B0: a box stack (BoxStackA, low cover), the control: no way into its tile, low cover beside it.
- BW: the same with Blocks walking off alone: units stand in its tile; probably no cover from it.
- BC: the same with Gives cover off alone: no way into its tile, no cover beside it.
- BF: the same with Floor on alone: its top may become a place to stand (75 over the pavement).
- F0: a tall fence (FenceTall192, 128 tall, Gives cover off as the map has it) on the tile edge y -192, the control:
  stand on both sides, no crossing, no cover, no sight across.
- FC: the same with Gives cover on: high cover toward it on both sides.
- FS: three such fences in a line (six tiles) with Blocks sight off: no crossing, no cover, but sight across.
And the map's own pieces where they stand, each beside an unedited one of the same kind:
- the hedge south of the car park (bushes XComDestructibleActor_212, _213, _239; props the map skips for pathing):
  Blocks walking on, which opens their pathing gate; the hedge west of it (_197, _210, _211) is the control;
- the bar's west door (XComInteractiveLevelActor_4): Blocks walking and Blocks sight off; the back door
  (XComInteractiveLevelActor_26) is the control;
- the ladder on the bar's west wall (XComLadder_3): Blocks walking off (the map has its sight and mouse off already,
  and it has no cover setting); the ladder on the north wall (XComLadder_4) is the control.

Usage: exp62_project.py <out> [--full | --compile] [--store]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. Bar must have
been opened in the editor at export 27. Without --full the lighting is not baked (the flags change no light).
--store saves the project in the editor's own project store instead (its next revision) and builds it into the
editor's builds folder, so that the editor's Play in game finds it as the project's last build."""
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
_, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha, exporterVersion=27)))
assert scene['exporterVersion'] >= 27, 'open URB_Bar in the editor first (export 27 has the flags)'
parts = {o['actor']: o for o in scene['objects'] if o['layer'] == 'base'}
Z, EDGE = 16.0, -192.0          # the pavement's top; the tile edge between its middle and south rows
X0, TILE = -2784.0, 96.0        # the grid's corner (x) and a tile


def centre(k):
    """The x of tile k's middle."""
    return X0 + TILE * k + TILE / 2


BOX, FENCE = 'XComDestructibleActor_296', 'XComDestructibleActor_39'


def copy(serial, src, location, rotation, flags=None):
    o = parts[PL + src]
    rec = {'id': '00000000-0000-4000-8000-%012d' % serial, 'actor': PL + '%s_copy%d' % (src, serial),
           'from': dict(package=MAP, level='base', actor=PL + src), 'components': [o['component']],
           'location': [float(v) for v in location], 'rotation': list(rotation)}
    if flags:
        rec['flags'] = dict(flags)
    return rec


def box(serial, k, flags=None):
    """A box stack in the middle of the pavement's middle row, tile k across: BoxStackA at yaw 0 has its pivot 2.4 south
    of its box's middle and 2 over its bottom (XComDestructibleActor_296)."""
    return copy(serial, BOX, (centre(k), -144.0 - 2.4, Z + 2.0), (0, 0, 0), flags)


def fence(serial, k, flags=None):
    """A tall fence along the tile edge y -192, two tiles from tile k's west edge: FenceTall192 at yaw 49152 runs 191
    east of a pivot 4 inside its west end, centred on the pivot's y, its pivot at its bottom (XComDestructibleActor_39)."""
    return copy(serial, FENCE, (X0 + TILE * k + 4.0, EDGE, Z), (0, 49152, 0), flags)


PLACES = {
    'B0': [box(1, 12)],
    'BW': [box(2, 15, dict(walking=False))],
    'BC': [box(3, 18, dict(cover=False))],
    'BF': [box(4, 21, dict(floor=True))],
    'F0': [fence(5, 24)],
    'FC': [fence(6, 28, dict(cover=True))],
    'FS': [fence(7 + n, 32 + 2 * n, dict(sight=False)) for n in range(3)],
}
added = [a for v in PLACES.values() for a in v]


def target(name):
    return dict(package=MAP, level='base', actor=PL + name)


HEDGE, HEDGE_CONTROL = ('XComDestructibleActor_212', 'XComDestructibleActor_213', 'XComDestructibleActor_239'), \
    ('XComDestructibleActor_197', 'XComDestructibleActor_210', 'XComDestructibleActor_211')
overrides = ([dict(target=target(n), flags=dict(walking=True)) for n in HEDGE]
             + [dict(target=target('XComInteractiveLevelActor_4'), flags=dict(walking=False, sight=False)),
                dict(target=target('XComLadder_3'), flags=dict(walking=False))])
for k, v in PLACES.items():
    for a in v:
        b = compiler.world_box(parts[a['from']['actor']], scene['meshes'], a['location'], a['rotation'])
        print(k, a['actor'].rsplit('.', 1)[-1], a.get('flags'), 'box', [round(x, 1) for x in b])
for o in overrides:
    print('in place', o['target']['actor'].rsplit('.', 1)[-1], o['flags'])
doc = dict(schema='xcom-map-workshop/project', schemaVersion=2, id='00000000-0000-4000-8000-000000000e62',
           name='EXP-62 piece flags', mode='edit', revision=1, savedAt='2026-11-16T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='URB_Bar_X62', patch='patch_urb_bar_x62'), overrides=overrides, added=added, groups=[],
           nextSerial=len(added) + 1,
           # the viewer's basis (x, up, y): south of the pavement, looking north at the row
           view=dict(camera=[-400, 1500, -1700], target=[-400, 0, -144]))
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
print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
print('notes', json.dumps(sorted({n['code'] for n in report['notes']})))
print('flags', json.dumps(report['counts'].get('flags')))
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(project, cache, builds, game, None, quick='--full' not in sys.argv).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'seconds')}))
print('package', builds / m['variant'])
