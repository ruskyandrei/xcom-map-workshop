"""EXP-72 runs 3 to 5's projects (private/plans/todo/editor-spawns-implementation-plan.md, stages SP8 and SP9), each a
quick build saved in a projects folder and built into a builds folder (a test server's, for a dry Play in game):

- `dropins-lw`: URB_PierA's Council rescue alone (the record that streams URB_PierA_Stream, whose scripted actions drop
  aliens in at its points), with one effect far from the action deleted so that the project has work: scripted
  drop-ins as Long War plays them;
- `dropins-placed`: the same with `spawnRules: {"dropIns": "placed"}`;
- `wave`: URB_PoliceStation's data recovery alone, with the destinations of XComWaveSystem_0's set 1, wave 1, group 1
  (nine points of URB_PoliceStation_CNH) moved together by one offset onto floor of the same level, at least six
  tiles away.

Usage: exp72_sp8_sp9_projects.py <projects folder> <builds folder> --cache <cache> [--only NAME] [--compile]

The exports of URB_PierA and URB_PoliceStation in <cache> must be export 33 or later."""
import argparse
import json
import math
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / 'tools' / 'editor'), str(REPO / 'tools' / 'viewer')]
import build  # noqa: E402
import compiler  # noqa: E402
import projects  # noqa: E402
import settings as settings_module  # noqa: E402

IDS = {'dropins-lw': '00000000-0000-4000-8000-000000072003', 'dropins-placed': '00000000-0000-4000-8000-000000072004',
       'wave': '00000000-0000-4000-8000-000000072005'}
NAMES = {'dropins-lw': ('EXP-72 Pier A drop-ins as Long War', 'URB_PierA_X72L'),
         'dropins-placed': ('EXP-72 Pier A drop-ins placed', 'URB_PierA_X72P'),
         'wave': ('EXP-72 Police Station wave moved', 'URB_PoliceS_X72W')}
WAVE = ('XComWaveSystem_0', 1, 1, 1)        # the wave system, set, wave, group whose destinations move
APART = 6

ap = argparse.ArgumentParser()
ap.add_argument('projects', type=Path)
ap.add_argument('builds', type=Path)
ap.add_argument('--cache', type=Path, required=True)
ap.add_argument('--only', choices=sorted(IDS))
ap.add_argument('--compile', action='store_true')
a = ap.parse_args()

s = settings_module.load_settings()
game = settings_module.resolve_game(s['game'])[0]


def export_of(map_name):
    for folder in sorted(a.cache.glob('%s/*-map*' % map_name), reverse=True):
        scene = json.loads((folder / 'scene.json').read_text(encoding='utf-8'))
        if (scene.get('exporterVersion') or 0) >= 33:
            return scene
    raise SystemExit('no export 33 of %s in %s' % (map_name, a.cache))


def document(key, scene, map_name, record_label, overrides, **more):
    name, ship = NAMES[key]
    index = next(i for i, m in enumerate(scene['missions']) if m['label'] == record_label)
    src = scene['source']
    return dict(schema=projects.SCHEMA, schemaVersion=projects.SCHEMA_VERSION, id=IDS[key], name=name, mode='edit',
                source=dict(map=map_name, package=Path(src['file']).name, sha256=src['sha256'],
                            exporterVersion=scene['exporterVersion']),
                output=dict(shipAs=ship, patch='patch_' + ship.lower()), overrides=overrides, added=[], groups=[],
                areaLightBindings=[], missions=[dict(record=index)], **more)


def far_effect(scene, points):
    """The map's own effect (export 28) farthest from every given point that the compiler lets go."""
    best = None
    for e in scene.get('effects') or []:
        if e.get('layer', 'base') != 'base' or e.get('kind', 'effect') != 'effect' or e.get('carriedBy') or not (e.get('can') or {}).get('delete', True):
            continue
        d = min(math.hypot(e['location'][0] - p[0], e['location'][1] - p[1]) for p in points)
        if best is None or d > best[0]:
            best = (d, e)
    return best[1]


def projects_to_make():
    out = {}
    if a.only in (None, 'dropins-lw', 'dropins-placed'):
        pier = export_of('URB_PierA')
        stream = pier['streams']['URB_PierA_Stream']['missionObjects']
        points = [o['location'] for o in stream] + [r['location'] for r in pier.get('spawns') or []]
        e = far_effect(pier, points)
        gone = [dict(target=dict(package='URB_PierA', level='base', actor=e['actor']), deleted=True)]
        print('Pier A: the effect deleted is %s at %s' % (e['actor'].rsplit('.', 1)[-1], [round(v) for v in e['location']]))
        out['dropins-lw'] = (document('dropins-lw', pier, 'URB_PierA', 'Council rescue', gone), pier)
        out['dropins-placed'] = (document('dropins-placed', pier, 'URB_PierA', 'Council rescue', gone,
                                          spawnRules=dict(dropIns='placed')), pier)
    if a.only in (None, 'wave'):
        police = export_of('URB_PoliceStation')
        objects = police['streams']['URB_PoliceStation_CNH']['missionObjects']
        by, wset, wave, group = WAVE
        moved = [o for o in objects if any(u.get('how') == 'wave' and u.get('by') == by and (u.get('set'), u.get('wave'), u.get('group'))
                                           == (wset, wave, group) for u in o.get('uses') or [])]
        grid = police['tileGrid']
        corner = compiler.tile_corner(grid)
        size = grid['size']
        tile = lambda p: (int(math.floor((p[0] - corner[0]) / size[0])), int(math.floor((p[1] - corner[1]) / size[1])),  # noqa: E731
                          int(math.floor((p[2] - corner[2]) / size[2])))
        floors = {tuple(f['tile']) for f in police['tactical']['floorTiles']}
        stood = [tile(o['location']) for o in moved]
        level = lambda t: t if t in floors else (t[0], t[1], t[2] - 1)  # noqa: E731
        # the group's tiles moved clear of where it stood (a tile between), so a unit's tile says which place it took
        x0, x1 = min(t[0] for t in stood), max(t[0] for t in stood)
        y0, y1 = min(t[1] for t in stood), max(t[1] for t in stood)
        best = None
        for dx in range(-30, 31):
            for dy in range(-30, 31):
                if math.hypot(dx, dy) < APART or (x0 - 1 <= x0 + dx <= x1 + 1 or x0 - 1 <= x1 + dx <= x1 + 1) and \
                        (y0 - 1 <= y0 + dy <= y1 + 1 or y0 - 1 <= y1 + dy <= y1 + 1):
                    continue
                if all((level(t)[0] + dx, level(t)[1] + dy, level(t)[2]) in floors for t in stood):
                    d = math.hypot(dx, dy)
                    if best is None or d < best[0]:
                        best = (d, dx, dy)
        if best is None:
            raise SystemExit('no offset puts every point of the group on floor')
        _, dx, dy = best
        overrides = [dict(target=dict(package='URB_PoliceStation_CNH', level='stream', actor=o['actor']),
                          location=[round(o['location'][0] + dx * size[0], 3), round(o['location'][1] + dy * size[1], 3),
                                    round(o['location'][2], 3)],
                          rotation=[int(v) for v in o.get('rotation') or [0, 0, 0]]) for o in moved]
        print('Police Station: %d destinations of %s set %d wave %d group %d moved by %d, %d tiles' % (len(moved), by, wset, wave, group, dx, dy))
        for o, m in zip(moved, overrides):
            print('  %-26s %s -> %s' % (o['actor'].rsplit('.', 1)[-1], [round(v) for v in o['location']], [round(v) for v in m['location']]))
        out['wave'] = (document('wave', police, 'URB_PoliceStation', 'Data recovery', overrides), police)
    return out


store = projects.ProjectStore(str(a.projects))
for key, (doc, scene) in projects_to_make().items():
    try:
        revision = store.load(doc['id']).get('revision', 0)
    except projects.ProjectError:
        revision = 0
    saved = store.save(doc['id'], doc, revision)
    doc = store.load(doc['id'])
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(str(a.cache), game), ())
    print('%s: revision %d, %s' % (key, saved['revision'], 'compile ok' if report['ok'] else 'COMPILE ERRORS'),
          [(e['code'], e['message'][:200]) for e in report['errors']])
    for d in report['warnings'] + report['notes']:
        if d['code'].startswith(('dropins', 'spawn', 'mission', 'stream')):
            print('   %s: %s' % (d['code'], d['message'][:260]))
    if not report['ok'] or a.compile:
        continue
    m = build.Build(build.BuildInputs(store.path(doc['id']), str(a.cache), a.builds, game, None, quick=True)).run()
    print('   built %s in %ss; dropInExclusion %s' % (m['variant'], m.get('seconds'), (m.get('config') or {}).get('dropInExclusion')))
