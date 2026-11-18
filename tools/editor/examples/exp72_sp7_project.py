"""EXP-72's spawn point copies and deletes (private/plans/todo/editor-spawns-implementation-plan.md, stage SP7): URB_Bar's
abduction with a pod copied twice, a Meld point copied and a pod deleted, built quick with the spawn family on:

- pod 2 (XComAlienPod_Abduction_2) and pod 3 copied, each onto a floor tile of the map a few tiles from its template;
- Meld point 2 (easy, destroyed on turn 4) copied the same way and made hard;
- pod 4 deleted (nothing names it).

Bar then has six pods where it had five. Usage:

  exp72_sp7_project.py <projects folder> <builds folder> --cache <cache> [--compile] [--again]

The export of URB_Bar in <cache> must be export 33 or later. --again builds a second time into <builds folder>/again
and says whether the map comes out byte for byte the same."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / 'tools' / 'editor'), str(REPO / 'tools' / 'viewer')]
import build  # noqa: E402
import compiler  # noqa: E402
import projects  # noqa: E402
import settings as settings_module  # noqa: E402

PROJECT_ID = '00000000-0000-4000-8000-000000072010'
PL = 'TheWorld.PersistentLevel.'

ap = argparse.ArgumentParser()
ap.add_argument('projects', type=Path)
ap.add_argument('builds', type=Path)
ap.add_argument('--cache', type=Path, required=True)
ap.add_argument('--compile', action='store_true')
ap.add_argument('--again', action='store_true')
a = ap.parse_args()

s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]
folder = next(f for f in sorted(a.cache.glob('URB_Bar/*-map*'), reverse=True)
              if (json.loads((f / 'scene.json').read_text(encoding='utf-8')).get('exporterVersion') or 0) >= 33)
scene = json.loads((folder / 'scene.json').read_text(encoding='utf-8'))
spawns = {r['actor'].rsplit('.', 1)[-1]: r for r in scene['spawns']}
src = scene['source']
doc = dict(schema=projects.SCHEMA, schemaVersion=projects.SCHEMA_VERSION, id=PROJECT_ID, name='EXP-72 Bar spawn copies',
           mode='edit', source=dict(map='URB_Bar', package=Path(src['file']).name, sha256=src['sha256'],
                                    exporterVersion=scene['exporterVersion']),
           output=dict(shipAs='URB_Bar_X72C', patch='patch_urb_bar_x72c'), overrides=[], added=[], groups=[],
           areaLightBindings=[], missions=[dict(record=0)])

# the floor tiles of the map (the compiler's reading) and the other points' tiles, so a copy stands on floor of its own
c = compiler.Compiler(doc, scene, ('spawn',), compiler.Library(str(a.cache), game), ())
c.run()
floors = c.floor_now()
grid = scene['tileGrid']
corner = compiler.tile_corner(grid)
size = grid.get('size') or [96, 96, 64]
tile_of = lambda p: tuple(int((p[k] - corner[k]) // size[k]) for k in range(3))  # noqa: E731
taken = {tile_of(r['location']) for r in scene['spawns']}


def place_near(name, label):
    """The template's place moved whole tiles across onto the nearest floor tile of its level no other point has."""
    t = spawns[name]
    at = tile_of(t['location'])
    for ring in range(2, 9):
        for dx, dy in sorted({(x, y) for x in range(-ring, ring + 1) for y in range(-ring, ring + 1)
                              if max(abs(x), abs(y)) == ring}):
            u = (at[0] + dx, at[1] + dy, at[2])
            if u in floors and u not in taken:
                taken.add(u)
                loc = [round(t['location'][0] + dx * size[0], 3), round(t['location'][1] + dy * size[1], 3), t['location'][2]]
                print('%s: %s copied %d,%d tiles across, to tile %s at %s' % (label, name, dx, dy, u, loc))
                return loc
    raise SystemExit('no free floor tile near %s' % name)


target = lambda name: dict(package='URB_Bar', level='base', actor=PL + name)  # noqa: E731
copies = [('pod2copy', 'XComAlienPod_Abduction_2', 'pod', None), ('pod3copy', 'XComAlienPod_Abduction_3', 'pod', None),
          ('meld2copy', 'XComMeldContainerSpawnPoint_2', 'meld', dict(difficulty='Hard'))]
for k, (label, name, kind, values) in enumerate(copies):
    rec = dict(id='00000000-0000-4000-8000-0000000720%02d' % (20 + k), kind=kind, actor=PL + '%s_copy%d' % (name, k + 1),
               **{'from': target(name)}, location=place_near(name, label),
               rotation=[int(v) for v in spawns[name]['rotation']])
    if values:
        rec['spawn'] = values
    doc['added'].append(rec)
doc['overrides'].append(dict(target=target('XComAlienPod_Abduction_4'), deleted=True))
doc['nextSerial'] = len(copies)

store = projects.ProjectStore(str(a.projects))
try:
    revision = store.load(PROJECT_ID).get('revision', 0)
except projects.ProjectError:
    revision = 0
saved = store.save(PROJECT_ID, doc, revision)
doc = store.load(PROJECT_ID)
spec, report = compiler.compile_project(doc, scene, ('spawn',), compiler.Library(str(a.cache), game), ())
print('revision %d: %s' % (saved['revision'], 'compile ok' if report['ok'] else 'COMPILE ERRORS'),
      [(e['code'], e['message'][:200]) for e in report['errors']], report['counts'].get('spawns'))
for d in report['warnings'] + report['notes']:
    print('  %s %s: %s' % ('warning' if d in report['warnings'] else 'note', d['code'], d['message'][:220]))
lane = next((o for o in spec['objects'] if o.get('type') == 'spawns'), None) if report['ok'] else None
if lane:
    for copy in lane['copies']:
        print('  copy %s of %s: pod index %s, values %s' % (copy['name'], copy['source'], copy.get('podIndex'), copy.get('spawn')))
if not report['ok'] or a.compile:
    sys.exit(0 if report['ok'] else 1)


def built(out):
    m = build.Build(store.path(PROJECT_ID), str(a.cache), out, game, None, quick=True, enable=('spawn',)).run()
    upk = out / m['variant'] / 'CookedPCConsole' / ('%s.upk' % m['variant'])
    print('built %s in %ss: spawnEdits %s, %s' % (m['variant'], m.get('seconds'), m.get('spawnEdits'),
                                                 hashlib.sha256(upk.read_bytes()).hexdigest()[:16]))
    return m, upk


m, upk = built(a.builds)
if a.again:
    again = a.builds / 'again'
    shutil.rmtree(again, ignore_errors=True)
    _, upk2 = built(again)
    print('second build byte for byte the first:', upk.read_bytes() == upk2.read_bytes())
