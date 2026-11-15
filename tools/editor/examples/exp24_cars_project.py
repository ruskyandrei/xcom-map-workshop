"""EXP-24 run 1's project: cars made in the map on URB_Bar (private/plans/done/cars-doors-ladders-plan.md, section 7.5).

A car is an assembly: its body (an XComDestructibleActor) naming its glass (an XComFracLevelActor) as HidingPartner,
and parts the prefab placed (the police car's light bar). It copies, moves and deletes as one, by the recipe snap.
- The police car, XComDestructibleActor_64 (yaw -728, with its light bar XComDestructibleActor_143 and glass
  XComFracLevelActor_45, at (-1240, -482)), is copied a quarter turn round, across the street just south of it: the
  grid move turns it about the grid's corner and shifts it 30 tiles east and 5 south.
- The sedan XComDestructibleActor_136 (glass XComFracLevelActor_50, at (-2026, 1), yaw -16384) moves a tile west and
  5 north along the west street, clear of its old place.
- The SUV XComDestructibleActor_137 (glass XComFracLevelActor_51, at (-2402, -684)) is deleted.

The car family didn't build yet when it ran: the experiment's build passed it on (build.py --family car).
Writes the project into the projects folder (the editor settings) and prints its id. Run again, it saves the same
edit as the next revision.

  python tools/editor/examples/exp24_cars_project.py [--cache <viewer cache>]
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

ID = '24e0a0b1-2424-4d0a-8e24-3c4d5e6f7a24'
NAME = 'EXP-24 cars on the bar'
MAP = 'URB_Bar'
SHA = 'a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5'
PL = 'TheWorld.PersistentLevel.'
# (pieces, quarter turns about the grid's corner, tiles, storeys), as the recipe snap moves them
MOVES = ((('XComDestructibleActor_136', 'XComFracLevelActor_50'), 0, (-1, 5), 0),)          # the sedan
COPIES = ((('XComDestructibleActor_64', 'XComDestructibleActor_143', 'XComFracLevelActor_45'), 1, (30, -5), 0),)  # police
DELETED = ('XComDestructibleActor_137', 'XComFracLevelActor_51')                                  # the SUV
COPY_ID = '24e0a0b1-2424-4a24-9c24-0d1e2f3a4e%02d'


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map=MAP, sha256=SHA, exporterVersion=15)))
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
               source=dict(map=MAP, package=MAP + '.upk', sha256=SHA, exporterVersion=15),
               output=dict(shipAs=ship, patch='patch_' + ship.lower()),
               overrides=overrides, added=added, nextSerial=len(added),
               # The viewer's basis (x, up, y): above the street south of the bar, looking north.
               view=dict(camera=[-1600, 1400, -1900], target=[-1600, 0, -500]))
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
