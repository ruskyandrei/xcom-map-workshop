"""EXP-24 run 2's project: cars made in the map on URB_PoliceStation (private/plans/done/cars-doors-ladders-plan.md, 7.5).

A car is an assembly: its body naming its glass as HidingPartner, the parts its prefab placed (doors, a police car's
light bar) and, on Police Station, a standalone police light bar no prefab places: only the glass's fragment columns
name it, standing 2 units from the body (export 16's `breaks`; compiler.assemblies).
- The sedan XComDestructibleActor_1062 (open doors 1063 and 1064, standalone light bar XComDestructibleActor_471,
  glass XComFracLevelActor_194; at (-1258, 192), yaw 0) moves a quarter turn round, beside its old place.
- The police car XComDestructibleActor_1075 (light bar 1076, glass XComFracLevelActor_200; at (-960, -292), yaw
  16384) is copied a half turn round, just east of it.
- The wreck XComDestructibleActor_1071 (glass XComFracLevelActor_198, whose columns also name the wreck
  XComDestructibleActor_1070 beside it; at (-958, 1152)) is copied 2 tiles north: its copy's columns drop that entry.
- The sedan XComDestructibleActor_1072 (doors 1073 and 1074, standalone light bar XComDestructibleActor_470, glass
  XComFracLevelActor_199; at (-296, -2400)) is deleted.

The car family didn't build yet when it ran: the experiment's build passed it on (build.py --family car).
Writes the project into the projects folder (the editor settings) and prints its id. Run again, it saves the same
edit as the next revision.

  python tools/editor/examples/exp24_police_project.py [--cache <viewer cache>]
"""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import compiler  # noqa: E402
import settings  # noqa: E402
from projects import ProjectStore  # noqa: E402
from settings import load_settings  # noqa: E402

ID = '24f0a0b1-2424-4d0a-8e24-3c4d5e6f7b24'
NAME = 'EXP-24 cars at the police station'
MAP = 'URB_PoliceStation'
SHA = '86785ed731811d0b337e8ab2bb9aa0215678d88b48de0beadea9bf7193f0fa29'
PL = 'TheWorld.PersistentLevel.'
# (pieces, quarter turns about the grid's corner, tiles, storeys), as the recipe snap moves them
SEDAN = ('XComDestructibleActor_1062', 'XComDestructibleActor_1063', 'XComDestructibleActor_1064', 'XComDestructibleActor_471',
         'XComFracLevelActor_194')
MOVES = ((SEDAN, 1, (33, 24), 0),)
COPIES = ((('XComDestructibleActor_1075', 'XComDestructibleActor_1076', 'XComFracLevelActor_200'), 2, (18, 48), 0),  # police
          (('XComDestructibleActor_1071', 'XComFracLevelActor_198'), 0, (0, 2), 0))                                # wreck
DELETED = ('XComDestructibleActor_1072', 'XComDestructibleActor_1073', 'XComDestructibleActor_1074', 'XComDestructibleActor_470',
           'XComFracLevelActor_199')
COPY_ID = '24f0a0b1-2424-4a24-9c24-0d1e2f3a4f%02d'


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map=MAP, sha256=SHA, exporterVersion=16)))
    origin = scene['tileGrid']['origin'][:2]

    def parts(name):
        found = [o for o in scene['objects'] if o['layer'] == 'base' and o['actor'] == PL + name]
        assert found, name
        return found

    def grid_pose(src, turns, tiles, storeys):
        # the pose the recipe snap gives: quarter turns about the grid's corner, whole tiles and storeys, exactly
        x, y = compiler.turned((src['location'][0] - origin[0], src['location'][1] - origin[1]), turns)
        at = [origin[0] + x + compiler.TILE * tiles[0], origin[1] + y + compiler.TILE * tiles[1],
              src['location'][2] + compiler.STOREY * storeys]
        rot = [src['rotation'][0], src['rotation'][1] + turns * compiler.QUARTER, src['rotation'][2]]
        return compiler.nearest_grid_pose(src['location'], src['rotation'], at, rot, origin)

    target = lambda name: dict(package=MAP, level='base', actor=PL + name)  # noqa: E731
    overrides = []
    for names, turns, tiles, storeys in MOVES:
        for name in names:
            loc, rot = grid_pose(parts(name)[0], turns, tiles, storeys)
            overrides.append(dict(target=target(name), location=loc, rotation=rot))
    overrides += [dict(target=target(name), deleted=True) for name in DELETED]
    added = []
    for names, turns, tiles, storeys in COPIES:
        for name in names:
            found = parts(name)
            loc, rot = grid_pose(found[0], turns, tiles, storeys)
            k = len(added) + 1
            added.append(dict(id=COPY_ID % k, actor=PL + '%s_copy%d' % (name, k), **{'from': target(name)},
                              components=sorted(o['component'] for o in found), location=loc, rotation=rot))
    # As the editor names a project's output (web/project.js outputNames): 30 characters at most for the patch (T-09).
    stem = MAP[:12]
    ship = '%s_%s_%s' % (stem, 'Exp24Car'[:compiler.NAME_LIMIT - len('patch_') - len(stem) - 6], ID[:4])
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name=NAME, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=SHA, exporterVersion=16),
               output=dict(shipAs=ship, patch='patch_' + ship.lower()),
               overrides=overrides, added=added, nextSerial=len(added),
               # The viewer's basis (x, up, y): above the station's west side, looking north.
               view=dict(camera=[-1000, 1600, -1000], target=[-1000, 0, 500]))
    spec, report = compiler.compile_project(doc, scene, enable=['car'])
    if not report['ok']:
        raise SystemExit('the project does not compile: %s' % report['errors'])
    store = ProjectStore(load_settings()['projects'])
    try:
        current = store.load(ID)
        if current.get('created'):
            doc['created'] = current['created']
        expected = current['revision']
    except Exception:
        expected = 0
    saved = store.save(ID, doc, expected)
    print('saved %s (%s) revision %d in %s as %s: %d moved, %d deleted, %d added; assemblies %s; %d warnings'
          % (NAME, ID, saved['revision'], store.path(ID), ship, report['counts']['moved'], report['counts']['deleted'],
             report['counts']['added'], [(m['id'], m['turns'], m['translation']) for m in report['assemblies']],
             len(report['warnings'])))
    for a in added:
        print('  %s at %s %s' % (a['actor'].split('.')[-1], [round(v, 2) for v in a['location']], a['rotation']))


if __name__ == '__main__':
    main()
