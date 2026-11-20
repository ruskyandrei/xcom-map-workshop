"""EXP-69's project: effects and ambient sounds of other maps placed in URB_Bar (the effects and sounds plan's EXP-D,
after stage FX4), in one run.

Effects, each from the library's base maps (the Add panel's All maps):
- Moths (P_Moths_Wandering, CAbductor_Cliffside's Emitter_46): a lit system (a light environment) with mesh
  particles, which Bar doesn't have; south of the street.
- Fire (P_Fire_Mid_No_Chunks, CLrgScout_ForestTrench's Emitter_11): mesh and sprite particles, which Bar doesn't
  have; two copies in the lane between the parked cars, so the Build stages it once and clones it twice.
- A headlight beam (HeadLight_Beam_Cheap, URB_MilitaryAmmo's Emitter_104): a system Bar has already (its
  floodlights' and the taxi's): the copy plays Bar's own, the closure bringing only the actor.

Ambient sounds:
- An air-conditioning unit (IndustrialAirConditioningUnit, Act2_Pier's AmbientSoundSimple_0): a simple sound (its
  own cue and node) of a wave Bar doesn't have; reach 200 to 1,250 units; south-east.
- A hyperwave beacon (HyperWaveBeacon, AlienBase01's AmbientSound_11): a sound whose cue is a game asset others play
  too (a shared cue), of a wave Bar doesn't have; reach 500 to 1,250; south.
- A fountain (Fountain, URB_Boulevard's AmbientSoundSimple_1): a simple sound whose radii come from an archetype of
  its map (inherited), of a wave Bar doesn't have; reach 100 to 2,500; north-west.
The sounds were chosen for reaches the game's camera can hear from (the map's TV static reaches 125 units).

Usage: exp69_project.py <out> [--full | --compile] [--store] [--library <cache>]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. Bar must have
been exported at 28 and the library scanned (index 9: the Add panel's All maps reads the game's maps). --library
reads the library from another cache's (a scratch scan). Without --full the lighting is not baked. --store saves the
project in the editor's own project store instead (its next revision) and builds it into the editor's builds folder,
so that the editor's Play in game finds it as the project's last build."""
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
library_cache = sys.argv[sys.argv.index('--library') + 1] if '--library' in sys.argv else cache
if library_cache != cache:
    plain = compiler.Library
    compiler.Library = lambda _cache, install: plain(library_cache, install)
sha = hashlib.sha256(build.lwr_file(game, 'CookedPCConsole', MAP + '.upk').read_bytes()).hexdigest()
_, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha, exporterVersion=28)))
assert scene['exporterVersion'] >= 28, 'export URB_Bar at 28 first (the effects and sounds data)'
library = compiler.Library(cache, game)


def donor(package, actor):
    """The donor actor's record as the library reads it (its pose and kind)."""
    template, entry = library.effect(dict(package=package, level='base', actor=PL + actor))
    return template['record'], entry


def copy(serial, package, actor, location, turn=0):
    record, _ = donor(package, actor)
    rotation = [int(v) for v in record['rotation']]
    return {'id': '00000000-0000-4000-8000-%012d' % (690 + serial), 'actor': PL + '%s_copy%d' % (actor, serial),
            'kind': record['kind'], 'from': dict(package=package, level='base', actor=PL + actor),
            'location': [float(v) for v in location], 'rotation': [rotation[0], rotation[1] + turn, rotation[2]]}


added = [
    copy(1, 'CAbductor_Cliffside', 'Emitter_46', (-900.0, -1250.0, 200.0)),                 # 1: moths (lit, mesh)
    copy(2, 'CLrgScout_ForestTrench', 'Emitter_11', (-250.0, -820.0, 2.0)),                 # 2: fire
    copy(3, 'CLrgScout_ForestTrench', 'Emitter_11', (350.0, -820.0, 2.0)),                  # 3: the same fire again
    copy(4, 'URB_MilitaryAmmo', 'Emitter_104', (-1500.0, -600.0, 48.0)),                    # 4: a beam Bar has
    copy(5, 'Act2_Pier', 'AmbientSoundSimple_0', (1500.0, -1400.0, 40.0)),                  # 5: air conditioning
    copy(6, 'AlienBase01', 'AmbientSound_11', (-500.0, -1500.0, 60.0)),                     # 6: shared cue
    copy(7, 'URB_Boulevard', 'AmbientSoundSimple_1', (-2300.0, 1300.0, 20.0)),              # 7: inherited radii
]
doc = dict(schema='xcom-map-workshop/project', schemaVersion=3, id='00000000-0000-4000-8000-000000000e69',
           name='EXP-69 effects and sounds from other maps', mode='edit', revision=1, savedAt='2026-11-17T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='URB_Bar_X69', patch='patch_urb_bar_x69'), overrides=[], added=added, groups=[],
           nextSerial=len(added) + 1,
           # the viewer's basis (x, up, y): north of the street, looking south over it
           view=dict(camera=[-500, 1500, 600], target=[-500, 0, -1000]))
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
print('notes', json.dumps([(n['code'], n['message'][:200]) for n in report['notes'] if n['code'].startswith('effect')], indent=1))
print('donors', json.dumps(report.get('donors')))
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(build.BuildInputs(project, cache, builds, game, None, quick='--full' not in sys.argv)).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'seconds', 'foreignPieces', 'foreignEffects')}))
print('donors', json.dumps([{k: d.get(k) for k in ('map', 'pieces', 'effects', 'objectsBrought', 'objectsReused', 'bytes', 'sizes')}
                            for d in m.get('donors') or []]))
section = m.get('nativeCopies') or {}
for key in ('effects', 'sounds', 'floorEmitters'):
    print(key, json.dumps(section.get(key), indent=None)[:1600])
print('package', builds / m['variant'])
