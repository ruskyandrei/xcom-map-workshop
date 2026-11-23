"""EXP-95's project: diagonal cover marked by hand, on CsmallScout_Farm (private/plans/done/diagonal-cover-by-hand-and-
views-plan.md, stages M4 and M5; KNOWN-BUGS.md KB-20). Schema 7, so the Build carries no mark of its own: it writes
the marks the project names, as the editor's Diagonal cover view saves them.

- A high cover block 272 by 24, turned 45 degrees on open ground (its corner at (1879.3, 230.3)), and two marks at it:
  (45, 40, 0) toward the block, the diagonal (1, -1), where its wall stands; and (47, 40, 0) on its other side toward
  it, (-1, 1), and away from it, (1, 1), where nothing stands (a corner with no wall: written as marked, the plan's
  decision 3).
- The scout's corner (39, 20, 0) taken away (removed): the game's build gives it no cover without its seed.
- The scout's corner (41, 22, 0) given a second corner, (1, -1), where nothing stands, besides its own (-1, 1).
- The scout's hull chunk XComLevelActor_3 (its corners (39, 12, 0) and (41, 10, 0) toward (-1, -1)) copied six tiles
  east of where the Build's carry test put it, at (3024, 912, -128), its marks carried as the page carries them: at
  (51, 42, 0) and (53, 40, 0), toward (-1, -1), `by` the copy.

Usage: exp95_diagonal_project.py <out> [--compile] [--store]

The project goes to <out>/project.json and its quick build under <out>/builds (the lighting is not baked: cover blocks
and copies of the map's pieces need none for a cover check); the game and the cache are the settings'. The farm must
have been opened in the editor at export 40. --store saves it in the editor's own project store instead and builds
into the editor's builds folder."""
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
from compiler_tables import tile_corner  # noqa: E402

MAP, PACKAGE = 'CSmallScout_Farm', 'CsmallScout_Farm'      # (the map as the install's records name it; its file)
PL = 'TheWorld.PersistentLevel.'
s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]
cache = s['cache']
sha = hashlib.sha256(build.lwr_file(game, 'CookedPCConsole', PACKAGE + '.upk').read_bytes()).hexdigest()
_, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha, exporterVersion=40)))
assert scene['exporterVersion'] >= 40, 'open the farm in the editor at export 40 first'
corner = tile_corner(scene['tileGrid'])


def at(t):
    """A tile's middle in the world, as the editor names a tile."""
    return [round(corner[k] + size * (t[k] + 0.5), 4) for k, size in enumerate((96.0, 96.0, 64.0))]


chunk = next(o for o in scene['objects'] if o['actor'] == PL + 'XComLevelActor_3')
copy = {'id': '00000000-0000-4000-8000-000000000951', 'actor': PL + 'XComLevelActor_3_copy1',
        'from': dict(package=PACKAGE, level='base', actor=PL + 'XComLevelActor_3'),
        'components': sorted({o['component'] for o in scene['objects'] if o['actor'] == chunk['actor']}),
        'location': [3024.0, 912.0, -128.0], 'rotation': list(chunk['rotation'])}
block = {'id': '00000000-0000-4000-8000-000000000952', 'actor': PL + 'CoverBlock_copy2',
         'template': dict(kind='cover', version=2), 'cover': dict(type='high', size=[272.0, 24.0], heights=[-12.0, 96.0]),
         'location': [1879.3, 230.3, -128.0], 'rotation': [0, 8192, 0]}
diagonal = dict(
    marks=[dict(at=at((45, 40, 0)), toward=[[1, -1]]),
           dict(at=at((47, 40, 0)), toward=[[-1, 1], [1, 1]]),
           {'at': at((41, 22, 0)), 'toward': [[-1, 1], [1, -1]], 'from': at((41, 22, 0))},
           dict(at=at((51, 42, 0)), toward=[[-1, -1]], by=copy['actor']),
           dict(at=at((53, 40, 0)), toward=[[-1, -1]], by=copy['actor'])],
    removed=[at((39, 20, 0))])
doc = dict(schema='xcom-map-workshop/project', schemaVersion=compiler.SCHEMA_VERSION, id='00000000-0000-4000-8000-000000000e95',
           name='EXP-95 diagonal marks', mode='edit', revision=1, savedAt='2026-11-23T00:00:00Z',
           source=dict(map=MAP, package=PACKAGE + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='CsmallScout_Farm_X95', patch='patch_csmallscout_farm_x95'), overrides=[],
           added=[copy, block], groups=[], nextSerial=3, diagonalCover=diagonal)
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
print('diagonal lane', json.dumps(spec and spec.get('diagonalCover')))
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(build.BuildInputs(project, cache, builds, game, None, quick=True)).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'seconds', 'diagonalCover')}, indent=1))
print('package', builds / m['variant'])
