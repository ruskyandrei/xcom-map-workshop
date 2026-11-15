"""EXP-52's project: cover blocks that break with their group, on URB_Bar's pavement in front of the bar
(private/plans/done/breaking-cover-blocks-plan.md).

Three places along the pavement (trash cans, Toughness_METAL, 90 health; the pavement's top is at 16):
- A, west: the map's own trash can XComDestructibleActor_183, left in place, grouped (Break together) with a low
  cover block over its tile (its neighbour XComDestructibleActor_184 stands in the same tile and is not in the
  group). No copy in the group: the map's piece gets the block in its AffectedChildren.
- B, east: a copy of the trash can XComDestructibleActor_0 on the open pavement east of C, grouped with a
  high cover block over its tile.
- C, the middle, the control: a high cover block over the tile of the map's cans XComDestructibleActor_0 and _1, in no
  group: it is built as it always was and stays when the cans go.

Usage: exp52_project.py <out> [--full | --compile] [--store]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. Bar must have
been opened once in the editor (its export). Without --full the lighting is not baked (cover blocks change none).
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
T = 96.0


def target(name):
    return dict(package=MAP, level='base', actor=PL + name)


def tile_corner(location):
    """The corner of the tile a place is in (tiles are 96 across, on multiples of 96 here), on the place's floor."""
    return [T * (location[0] // T), T * (location[1] // T), 16.0]


def block(serial, corner, kind):
    return {'id': '00000000-0000-4000-8000-%012d' % serial, 'actor': PL + 'CoverBlock_copy%d' % serial,
            'template': dict(kind='cover', version=1), 'cover': dict(width=1, length=1, type=kind, height=1),
            'location': corner, 'rotation': [0, 0, 0]}


can_a = objects[PL + 'XComDestructibleActor_183'][0]
can_c = objects[PL + 'XComDestructibleActor_0'][0]
copy_at = [-432.0, -48.0, can_c['location'][2]]             # east of the cans of C, on the open pavement
added = [
    block(1, tile_corner(can_a['location']), 'low'),                                        # A
    {'id': '00000000-0000-4000-8000-%012d' % 2, 'actor': PL + 'XComDestructibleActor_0_copy2',
     'from': target('XComDestructibleActor_0'), 'components': sorted(o['component'] for o in objects[PL + 'XComDestructibleActor_0']),
     'location': copy_at, 'rotation': list(can_c['rotation'])},                             # B: the can
    block(3, tile_corner(copy_at), 'high'),                                                 # B: its block
    block(4, tile_corner(can_c['location']), 'high'),                                       # C
]
groups = [dict(id='00000000-0000-4000-8000-0000000a0052', locked=True, breakTogether=True,
               members=[target('XComDestructibleActor_183'), dict(added=PL + 'CoverBlock_copy1')]),
          dict(id='00000000-0000-4000-8000-0000000b0052', locked=True, breakTogether=True,
               members=[dict(added=PL + 'XComDestructibleActor_0_copy2'), dict(added=PL + 'CoverBlock_copy3')])]
for a in added:
    print(a['actor'].rsplit('.', 1)[-1], a.get('cover') or 'a copy', a['location'])
doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id='00000000-0000-4000-8000-000000000e52',
           name='EXP-52 cover blocks that break', mode='edit', revision=1, savedAt='2026-11-13T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='URB_Bar_X52', patch='patch_urb_bar_x52'), overrides=[], added=added, groups=groups,
           nextSerial=len(added) + 1,
           # the viewer's basis (x, up, y): south of the pavement, looking at the three places
           view=dict(camera=[-840, 1200, -1300], target=[-840, 0, 144]))
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
    m = build.Build(project, cache, builds, game, None, quick='--full' not in sys.argv).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'seconds')}))
print('package', builds / m['variant'])
