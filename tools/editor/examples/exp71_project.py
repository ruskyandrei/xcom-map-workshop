"""EXP-71's project: lens flares moved, deleted and copied on URB_Bar, and two brought from another map (the effects
and sounds plan's EXP-F, the flare part, after stage FX6b), in one run.

Bar's own two (LensFlareSource_7 and _8, both LF_XCom_Base_C made from the archetype ARC_LF_XCom_Base_C, colour 1, 1, 1
at strength 0.03, 63 units apart at the heads of the street lamp by the bar's front corner, 343 up):
1. LensFlareSource_7 moved out over the car park, to (-300, -1200, 150).
2. LensFlareSource_8 deleted.
3. A copy of LensFlareSource_7 at (-600, -1200, 150).

AlienBase01's (the library's lens flares, the Add panel's All maps: Lens flares), neither of whose templates Bar has:
4. The hyperwave beacon's glare (LensFlareSource_0, LF_Hyperwave_Beacon, colour 2, 0.5, 0.2: orange), in the open
   over the car park at (0, -1200, 150).
5. An alien ambient glow (LensFlareSource_3, LF_Alien_Ambient_A, colour 3, 0.5, 0.2), in the open at (300, -1200, 150).
6. The beacon's glare again, inside the bar's ground floor at (200, 600, 100), behind its walls and under its upper
   floor: the camera's line to it is blocked from most places (occlusion). The Build stages the donor's actor once
   and clones it twice (4 and 6).

Usage: exp71_project.py <out> [--full | --compile] [--store | --projects <folder>] [--library <cache>]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. Bar must have
been exported at 28 and the library scanned at index 10 (the Add panel's All maps reads the game's maps; --library
reads the library from another cache's, a scratch scan). The flare family is enabled for this build (it waits for
this run). Without --full the lighting is not baked: a flare changes no baked light. --store saves the project in
the editor's own project store instead (its next revision) and builds it into the editor's builds folder, so that
the editor's Play in game finds it as the project's last build; --projects saves it in a project store in <folder>
(a test server's, for the marked shots) and builds under <out>."""
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

MAP, DONOR = 'URB_Bar', 'AlienBase01'
PL = 'TheWorld.PersistentLevel.'
FAMILIES = ('flare',)
s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]
cache = s['cache']
library_cache = sys.argv[sys.argv.index('--library') + 1] if '--library' in sys.argv else cache
if library_cache != cache:
    plain = compiler.Library
    compiler.Library = lambda _cache, install: plain(library_cache, install)
sha = hashlib.sha256(build.lwr_file(game, 'CookedPCConsole', MAP + '.upk').read_bytes()).hexdigest()
_, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha, exporterVersion=28)))
assert scene['exporterVersion'] >= 28, 'export URB_Bar at 28 first (the effects and sounds data)'
records = {r['actor'].rsplit('.', 1)[-1]: r for r in scene['flares']}
library = compiler.Library(cache, game)


def target(actor, package=MAP):
    return dict(package=package, level='base', actor=PL + actor)


def copy(serial, actor, location, package=MAP):
    """A copy of a flare, turned as its original is: this map's from the export, another map's from the library."""
    record = records[actor] if package == MAP else library.effect(target(actor, package))[0]['record']
    assert record['kind'] == 'flare', record['kind']
    return {'id': '00000000-0000-4000-8000-%012d' % (710 + serial), 'actor': PL + '%s_copy%d' % (actor, serial),
            'kind': 'flare', 'from': target(actor, package), 'location': [float(v) for v in location],
            'rotation': [int(v) for v in record['rotation']]}


overrides = [
    dict(target=target('LensFlareSource_7'), location=[-300.0, -1200.0, 150.0],
         rotation=[int(v) for v in records['LensFlareSource_7']['rotation']]),                  # 1: moved
    dict(target=target('LensFlareSource_8'), deleted=True),                                     # 2: deleted
]
added = [
    copy(3, 'LensFlareSource_7', (-600.0, -1200.0, 150.0)),                                     # 3: a copy of Bar's own
    copy(4, 'LensFlareSource_0', (0.0, -1200.0, 150.0), DONOR),                                 # 4: the beacon's glare
    copy(5, 'LensFlareSource_3', (300.0, -1200.0, 150.0), DONOR),                               # 5: an alien glow
    copy(6, 'LensFlareSource_0', (200.0, 600.0, 100.0), DONOR),                                 # 6: the glare, indoors
]
doc = dict(schema='xcom-map-workshop/project', schemaVersion=3, id='00000000-0000-4000-8000-000000000e71',
           name='EXP-71 lens flares', mode='edit', revision=1, savedAt='2026-11-17T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='URB_Bar_X71', patch='patch_urb_bar_x71'), overrides=overrides, added=added, groups=[],
           nextSerial=7,
           # the viewer's basis (x, up, y): south of the street, looking north over it to the bar
           view=dict(camera=[0, 2200, -3400], target=[0, 0, -900]))
OUT.mkdir(parents=True, exist_ok=True)
builds = OUT / 'builds'
if '--store' in sys.argv or '--projects' in sys.argv:
    import projects
    own = '--store' in sys.argv
    store = projects.ProjectStore(s['projects'] if own else sys.argv[sys.argv.index('--projects') + 1])
    try:
        revision = store.load(doc['id']).get('revision', 0)
    except projects.ProjectError:
        revision = 0
    saved = store.save(doc['id'], {k: v for k, v in doc.items() if k not in ('revision', 'savedAt')}, revision)
    project = store.path(doc['id'])
    if own:
        builds = Path(s['output'])
    doc = store.load(doc['id'])
    print('saved in %s as revision %d: %s' % ('the editor\'s store' if own else 'the project store given', saved['revision'],
                                             project.name))
else:
    project = OUT / 'project.json'
    project.write_text(json.dumps(doc, indent=1), encoding='utf-8', newline='\n')
spec, report = compiler.compile_project(doc, scene, FAMILIES, compiler.Library(cache, game), ())
print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
print('notes', json.dumps([(n['code'], n['message'][:200]) for n in report['notes'] if n['code'].startswith('effect')], indent=1))
print('counts', json.dumps(report['counts']['flares']), 'donors', json.dumps(report.get('donors')))
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(project, cache, builds, game, None, enable=FAMILIES, quick='--full' not in sys.argv).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'seconds', 'foreignPieces', 'foreignEffects', 'lightingUnchanged')}))
print('donors', json.dumps([{k: d.get(k) for k in ('map', 'pieces', 'effects', 'flares', 'objectsBrought', 'objectsReused', 'bytes', 'cut', 'sizes')}
                            for d in m.get('donors') or []]))
print('package', builds / m['variant'])
# the built map read back as export 28 reads a map: every lens flare the game will load, and the two edited originals
sys.path[:0] = [str(REPO / 'tools' / 'upk'), str(REPO / 'tools' / 'bake')]
import effects_metadata  # noqa: E402
import native_copy  # noqa: E402
from package import Package  # noqa: E402
q = Package(builds / m['variant'] / 'CookedPCConsole' / ('%s.upk' % m['variant']))
listed = set(native_copy.level_actors(q))
for r in effects_metadata.describe(q)['flares']:
    name = r['actor'].rsplit('.', 1)[-1]
    component = q.own(q.by_name[r['actor']], 'LensFlareComp', 0)
    print('%-24s %s at %s turned %s, %s, colour %s, component %s' % (
        name, 'listed' if q.by_name[r['actor']] in listed else 'NOT LISTED (deleted or staged)',
        [round(v, 1) for v in r['location']], r['rotation'], r['template'], r['colour'],
        q.name(component).rsplit('.', 2)[-2] + '.' + q.name(component).rsplit('.', 1)[-1] if component else None))
