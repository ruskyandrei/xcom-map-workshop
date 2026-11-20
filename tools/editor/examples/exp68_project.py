"""EXP-68's project: effects and sounds moved, copied and deleted (the effects and sounds plan's EXP-C, after stage
FX3), in one run on URB_Bar.

- Steam: the street steam by the taxi (Emitter_16, Steam_Small) moved to the pavement in front of the bar and turned a
  quarter; two copies of it beside it; a third copy on the bar's roof (its building's floor 3: index 2).
- The cutaway: one of the five floodlight beams on the bar's back wall (Emitter_14, listed by the bar's floor 2: index
  1, though it stands outside that floor's box) moved further from the wall, so that it is no floor's; the other four
  are untouched.
- The script: the map's script sets a parameter on two rat effects when a unit touches a trigger beside each
  (TriggerVolume_0 for Emitter_18 in the north-west alley, TriggerVolume_1 for Emitter_19 in the south-west one).
  Emitter_18 moved two tiles east; Emitter_19 deleted.
- Sounds: the bar's music (AmbientSoundSimple_2, BarMuzak) moved out of the bar to near the squad's start, and a copy
  of it at the far east street, beyond its reach from the squad; the taxi's engine idle (AmbientSoundSimple_3) deleted.
- The claw machine (XComDestructibleActor_316) moved two tiles along the back wall; its lights (Emitter_10, which the
  machine carries) kept where they are (`effect.follow: none`).

Usage: exp68_project.py <out> [--full | --compile] [--store]

The project and the build go under <out> (a scratch folder); the game and the cache are the settings'. Bar must have
been exported at 28 (opened in the editor, or viewer.py export). The effect and sound families are enabled for this
build (they wait for this run). Without --full the lighting is not baked. --store saves the project in the editor's own
project store instead (its next revision) and builds it into the editor's builds folder, so that the editor's Play in
game finds it as the project's last build (on a server started with serve --family effect --family sound)."""
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
FAMILIES = ('effect', 'sound')
s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]
cache = s['cache']
sha = hashlib.sha256(build.lwr_file(game, 'CookedPCConsole', MAP + '.upk').read_bytes()).hexdigest()
_, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha, exporterVersion=28)))
assert scene['exporterVersion'] >= 28, 'export URB_Bar at 28 first (the effects and sounds data)'
records = {r['actor']: r for r in scene['effects'] + scene['sounds']}


def target(name):
    return dict(package=MAP, level='base', actor=PL + name)


def at(name):
    r = records[PL + name]
    return [round(v, 4) for v in r['location']], [int(v) for v in r['rotation']]


STEAM, MUSIC = 'Emitter_16', 'AmbientSoundSimple_2'
steam_rot = at(STEAM)[1]                                   # [0, 0, 16384]
PAVEMENT = -144.0                                          # the middle of the pavement in front of the bar (top at 16)
overrides = [
    dict(target=target(STEAM), location=[-1104.0, PAVEMENT, 26.0],
         rotation=[steam_rot[0], steam_rot[1] + 16384, steam_rot[2]]),                          # 1: moved and turned
    dict(target=target('Emitter_14'), location=[-627.0, 1400.0, 333.0], rotation=at('Emitter_14')[1]),   # 4: off floor 2
    dict(target=target('Emitter_18'), location=[at('Emitter_18')[0][0] + 192.0, *at('Emitter_18')[0][1:]],
         rotation=at('Emitter_18')[1]),                                                          # 6: rats moved
    dict(target=target('Emitter_19'), deleted=True),                                             # 7: rats deleted
    dict(target=target(MUSIC), location=[1200.0, -1700.0, 73.0], rotation=at(MUSIC)[1]),         # 8: music moved
    dict(target=target('AmbientSoundSimple_3'), deleted=True),                                   # 10: taxi idle deleted
    dict(target=target('XComDestructibleActor_316'), location=[139.6484, 1189.8403, 20.0998], rotation=[0, 32768, 0]),  # 11
    dict(target=target('Emitter_10'), effect=dict(follow='none')),                               # 12: its lights stay
]


def copy(serial, kind, src, location, rotation):
    return {'id': '00000000-0000-4000-8000-%012d' % (680 + serial), 'actor': PL + '%s_copy%d' % (src, serial),
            'kind': kind, 'from': target(src), 'location': [float(v) for v in location], 'rotation': list(rotation)}


added = [
    copy(1, 'effect', STEAM, (-912.0, PAVEMENT, 26.0), steam_rot),          # 2
    copy(2, 'effect', STEAM, (-720.0, PAVEMENT, 26.0), steam_rot),          # 3
    copy(3, 'effect', STEAM, (150.0, 620.0, 420.0), steam_rot),             # 5: on the roof
    copy(4, 'sound', MUSIC, (1900.0, 300.0, 73.0), at(MUSIC)[1]),           # 9: far east
]
doc = dict(schema='xcom-map-workshop/project', schemaVersion=3, id='00000000-0000-4000-8000-000000000e68',
           name='EXP-68 effects and sounds', mode='edit', revision=1, savedAt='2026-11-17T00:00:00Z',
           source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='URB_Bar_X68', patch='patch_urb_bar_x68'), overrides=overrides, added=added, groups=[],
           nextSerial=len(added) + 1,
           # the viewer's basis (x, up, y): south of the bar, looking north at its front
           view=dict(camera=[-300, 1600, -1900], target=[-300, 0, 300]))
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
spec, report = compiler.compile_project(doc, scene, FAMILIES, compiler.Library(cache, game), ())
print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
print('notes', json.dumps([(n['code'], n['message'][:200]) for n in report['notes'] if n['code'].startswith('effect')], indent=1))
if not report['ok'] or '--compile' in sys.argv:
    sys.exit(0 if report['ok'] else 1)
try:
    m = build.Build(build.BuildInputs(project, cache, builds, game, None, enable=FAMILIES,
                                      quick='--full' not in sys.argv)).run()
except build.BuildError as error:
    print('build failed:', error)
    sys.exit(1)
print(json.dumps({k: m.get(k) for k in ('variant', 'quick', 'seconds')}))
section = m.get('nativeCopies') or {}
for key in ('effects', 'sounds', 'floorEmitters'):
    print(key, json.dumps(section.get(key), indent=None)[:1600])
print('package', builds / m['variant'])
