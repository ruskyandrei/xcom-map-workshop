"""EXP-70's project: effects' and ambient sounds' values set on URB_Bar (the effects and sounds plan's EXP-E, after
stage FX5), in one run.

Effects (Bar's own; each value set on the actor itself, or on a copy):
1. A headlight beam (Emitter_24, HeadLight_Beam_Cheap, one of a parked car's pair): its colour made red and its
   Brightness, saved as a number where its system reads a vector (as the game's maps do), from 0.5 to 2; its twin
   (Emitter_46, beside it) as the map has it.
2. Steam (Emitter_16, Steam_Small, drawn at half size, evenly): three times its size.
3. Alien vapour (Emitter_21, P_Alien_Vapor_Constant_Unlit, drawn unevenly at 0.6 by 0.6, 1, 1): three times its size,
   its proportions kept; its four neighbours as the map has them.
4. Steam (Emitter_3, Steam_Large): set to start off.
5-7. Three copies of the steam (Emitter_16) in a row in the street: 5 green, 6 with Spawn 4 (a parameter the effect
   doesn't save: a new entry), 7 as the map has it (the source's half size; the original's own size change isn't a
   copy's).

Ambient sounds:
8. The pickup's idle (AmbientSoundSimple_0, CarPickupIdle): pitch 1.6, heard fully within 600 and fading out by 2,000
   (it was 300 to 750).
9. A car's idle beside it (AmbientSoundSimple_3, CarTaxiIdle): set not to play from the start (an AmbientSoundSimple, which
   nothing in the map's script switches).
10. A copy of the pickup's idle in the car park's far corner: pitch 0.6, volume 0.5, its reach as the map has it.

Usage: exp70_project.py <out> [--full | --compile] [--store]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. Bar must have
been exported at 28. The effect-values and sound-values families are enabled for this build (they wait for this
run). Without --full the lighting is not baked. --store saves the project in the editor's own project store instead
(its next revision) and builds it into the editor's builds folder, so that the editor's Play in game finds it as the
project's last build."""
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
FAMILIES = ('effect-values', 'sound-values')
s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]
cache = s['cache']
sha = hashlib.sha256(build.lwr_file(game, 'CookedPCConsole', MAP + '.upk').read_bytes()).hexdigest()
_, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha, exporterVersion=28)))
assert scene['exporterVersion'] >= 28, 'export URB_Bar at 28 first (the effects and sounds data)'
records = {r['actor'].rsplit('.', 1)[-1]: r for r in scene['effects'] + scene['sounds']}


def target(actor):
    return dict(package=MAP, level='base', actor=PL + actor)


def values(actor, **v):
    kind = records[actor]['kind']
    return {'target': target(actor), kind: v}


def copy(serial, actor, location, **v):
    r = records[actor]
    out = {'id': '00000000-0000-4000-8000-%012d' % (700 + serial), 'actor': PL + '%s_copy%d' % (actor, serial),
           'kind': r['kind'], 'from': target(actor), 'location': [float(x) for x in location],
           'rotation': [int(x) for x in r['rotation']]}
    if v:
        out[r['kind']] = v
    return out


overrides = [
    values('Emitter_24', parameters=[dict(name='Brightness', value=2.0), dict(name='Color', value=[1.5, 0.1, 0.1])]),  # 1
    values('Emitter_16', scale=3.0),                                                                                   # 2
    values('Emitter_21', scale=3.0),                                                                                   # 3
    values('Emitter_3', startsOn=False),                                                                               # 4
    values('AmbientSoundSimple_0', pitch=[1.6, 1.6], radiusMin=600.0, radiusMax=2000.0),                               # 8
    values('AmbientSoundSimple_3', startsOn=False),                                                                    # 9
]
added = [
    copy(5, 'Emitter_16', (-600.0, -1650.0, 26.0), parameters=[dict(name='Color', value=[0.2, 1.5, 0.2])]),       # 5: green
    copy(6, 'Emitter_16', (-300.0, -1650.0, 26.0), parameters=[dict(name='Spawn', value=4.0)]),                   # 6: Spawn 4
    copy(7, 'Emitter_16', (0.0, -1650.0, 26.0)),                                                                  # 7: as it is
    copy(10, 'AmbientSoundSimple_0', (1500.0, -1500.0, 60.0), pitch=[0.6, 0.6], volume=[0.5, 0.5]),               # 10
]
doc = dict(schema='xcom-map-workshop/project', schemaVersion=3, id='00000000-0000-4000-8000-000000000e70',
           name='EXP-70 effect and sound values', mode='edit', revision=1, savedAt='2026-11-17T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='URB_Bar_X70', patch='patch_urb_bar_x70'), overrides=overrides, added=added, groups=[],
           nextSerial=11,
           # the viewer's basis (x, up, y): south of the car park, looking north over it to the bar
           view=dict(camera=[0, 2600, -3200], target=[0, 0, -900]))
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
spec, report = compiler.compile_project(doc, scene, FAMILIES)
print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
print('counts', json.dumps({k: report['counts'][k] for k in ('effects', 'sounds')}))
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(project, cache, builds, game, None, enable=FAMILIES, quick='--full' not in sys.argv).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'seconds')}))
section = m.get('nativeCopies') or {}
for key in ('effects', 'sounds'):
    print(key, json.dumps([{k: r.get(k) for k in ('actor', 'how', 'copy', 'values')} for r in section.get(key) or []]))
print('package', builds / m['variant'])
