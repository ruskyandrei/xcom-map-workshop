"""EXP-59's project: cover blocks smaller than a tile (private/plans/done/cover-block-handles-plan.md, H7), on URB_Bar's
pavement in front of the bar, along its middle row (y -192 to -96; the pavement's top is at 16), with a free row on
either side to stand and walk in.

Six places along the row, east to west (x falling), two free tiles between them:
- F: the control, a high cover block, 1 x 1 tile (x 672 to 768): no way into its tile, high cover beside it.
- A: a high block half a tile across (48 x 48) in the middle of its tile (x 384 to 480): units can't stand in that
  tile; the four tiles round it get high cover toward it.
- B: a high wall 8 units through and a tile long, along the edge between two tiles (x 96): units stand on both sides
  but can't cross between them; both get high cover toward it, and it blocks sight across.
- C: a high block 24 x 24 in its tile's corner (x -288, y -192): units stand in its tile and walk past it; it gives
  no cover (it is off the lines the game looks for cover along).
- D: a high block a tile across whose top is 40 over the floor (x -576 to -480): units can stand in its tile and walk
  through it; it gives no cover (the game looks for cover 44 to 60 over the floor).
- E: a high wall 2 units through, along the edge between two tiles (x -864): it fills no tile, so it gives no cover,
  but units can't cross between the two tiles (and it may block sight across).

Usage: exp59_project.py <out> [--full | --compile] [--store]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. Bar must have
been opened once in the editor (its export). Without --full the lighting is not baked (hidden blocks change none).
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
_, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha, exporterVersion=21)))
Z, ROW = 16.0, -192.0       # the pavement's top, the middle row's south edge
HIGH = [-12.0, 96.0]


def block(serial, corner, size, heights=HIGH):
    """A high cover block in units (as the editor's handles size one), its corner at `corner` on the pavement; by
    recipe version 2, as the editor saves a new block."""
    return {'id': '00000000-0000-4000-8000-%012d' % serial, 'actor': PL + 'CoverBlock_copy%d' % serial,
            'template': dict(kind='cover', version=2), 'cover': dict(type='high', size=list(size), heights=list(heights)),
            'location': [corner[0], corner[1], Z], 'rotation': [0, 0, 0]}


PLACES = {
    'F': block(1, (672.0, ROW), (96, 96)),
    'A': block(2, (384.0 + 24, ROW + 24), (48, 48)),
    'B': block(3, (96.0 - 4, ROW), (8, 96)),
    'C': block(4, (-288.0, ROW), (24, 24)),
    'D': block(5, (-576.0, ROW), (96, 96), (-12.0, 40.0)),
    'E': block(6, (-864.0 - 1, ROW), (2, 96)),
}
added = list(PLACES.values())
for k, a in PLACES.items():
    print(k, a['actor'].rsplit('.', 1)[-1], a['cover'], a['location'])
doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id='00000000-0000-4000-8000-000000000e59',
           name='EXP-59 small cover blocks', mode='edit', revision=1, savedAt='2026-11-15T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='URB_Bar_X59', patch='patch_urb_bar_x59'), overrides=[], added=added, groups=[],
           nextSerial=len(added) + 1,
           # the viewer's basis (x, up, y): south of the row, looking north at the six places
           view=dict(camera=[-100, 1400, -1500], target=[-100, 0, -144]))
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
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(build.BuildInputs(project, cache, builds, game, None, quick='--full' not in sys.argv)).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'seconds')}))
print('package', builds / m['variant'])
