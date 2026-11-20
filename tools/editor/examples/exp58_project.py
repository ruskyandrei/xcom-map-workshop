"""EXP-58's project: blockers (Discord feedback S6), invisible blocks that stop movement and give no cover, on URB_Bar's
pavement in front of the bar, in the row of free tiles south of EXP-52's places (the pavement's top is at 16).

Three places along the row, west to east:
- A: a blocker, 1 x 1 tile, in no group: units can't walk into its tile or stand on it, a unit beside it gets no
  cover from it, units see past it.
- B: the control, a high cover block, 1 x 1, three tiles east of A: high cover beside it and no way through, as
  always.
- C: a blocker over a copy of the trash can XComDestructibleActor_0, grouped with it (Break together), five tiles east
  of A: blocks the tile until the can is destroyed, then goes.

Usage: exp58_project.py <out> [--full | --compile] [--store]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. Bar must have
been opened once in the editor (its export). Without --full the lighting is not baked (blockers change none).
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
objects = {}
for o in scene['objects']:
    if o['layer'] == 'base':
        objects.setdefault(o['actor'], []).append(o)
T, Z, ROW = 96.0, 16.0, -96.0       # tile size, the pavement's top, the row's south edge


def target(name):
    return dict(package=MAP, level='base', actor=PL + name)


def block(serial, x, kind, name='CoverBlock'):
    """A cover block or blocker of 1 x 1 tile, its corner at (x, ROW) on the pavement; by recipe version 2."""
    return {'id': '00000000-0000-4000-8000-%012d' % serial, 'actor': PL + '%s_copy%d' % (name, serial),
            'template': dict(kind='cover', version=2), 'cover': dict(width=1, length=1, type=kind, height=1),
            'location': [x, ROW, Z], 'rotation': [0, 0, 0]}


can = objects[PL + 'XComDestructibleActor_0'][0]
A, B, C = -576.0, -288.0, -96.0
added = [
    block(1, A, 'block', 'Blocker'),                                                        # A
    block(2, B, 'high'),                                                                    # B
    {'id': '00000000-0000-4000-8000-%012d' % 3, 'actor': PL + 'XComDestructibleActor_0_copy3',
     'from': target('XComDestructibleActor_0'), 'components': sorted(o['component'] for o in objects[PL + 'XComDestructibleActor_0']),
     'location': [C + T / 2, ROW + T / 2, can['location'][2]], 'rotation': list(can['rotation'])},    # C: the can
    block(4, C, 'block', 'Blocker'),                                                        # C: its blocker
]
groups = [dict(id='00000000-0000-4000-8000-0000000c0058', locked=True, breakTogether=True,
               members=[dict(added=PL + 'XComDestructibleActor_0_copy3'), dict(added=PL + 'Blocker_copy4')])]
for a in added:
    print(a['actor'].rsplit('.', 1)[-1], a.get('cover') or 'a copy', a['location'])
doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id='00000000-0000-4000-8000-000000000e58',
           name='EXP-58 blockers', mode='edit', revision=1, savedAt='2026-11-15T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='URB_Bar_X58', patch='patch_urb_bar_x58'), overrides=[], added=added, groups=groups,
           nextSerial=len(added) + 1,
           # the viewer's basis (x, up, y): south of the row, looking at the three places
           view=dict(camera=[-330, 1100, -1300], target=[-330, 0, -48]))
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
print('groups', json.dumps(report['groups']))
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(build.BuildInputs(project, cache, builds, game, None, quick='--full' not in sys.argv)).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'seconds')}))
print('package', builds / m['variant'])
