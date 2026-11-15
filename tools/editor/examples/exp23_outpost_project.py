"""EXP-23 run 3's project: doors upstairs on URB_ResearchOutpost (private/plans/done/cars-doors-ladders-plan.md, 6.4 and 6.8).

The outpost's east building (XComBuildingVolume_7) has two doors on its floor 2 (z 384), one in each of the
rooftop structure's walls along X, and no doorway without its door upstairs; the project makes its opening with a door,
as runs 1 and 2 did.
- XComInteractiveLevelActor_26 (frame XComDestructibleActor_303, the wall at y 1248) is deleted, and
  XComInteractiveLevelActor_25 (frame XComDestructibleActor_302, the wall at y 480) moves into its doorway, a tile east
  and 8 north, unturned: (1584, 480, 384) to (1680, 1248, 384).
- XComInteractiveLevelActor_0 (frame XComDestructibleActor_0), a ground-floor door of the west building (floor 0 of
  XComBuildingVolume_4, at (-1776, -768, 0)), is copied into the doorway door 25 leaves, 35 tiles east, 13 north and
  6 storeys up, unturned: (1584, 480, 384), floor 2 of the east building.

The door family didn't build yet when it ran: the experiment's build passed it on (build.py --family door).
Writes the project into the projects folder (the editor settings) and prints its id. Run again, it saves the same
edit as the next revision.

  python tools/editor/examples/exp23_outpost_project.py [--cache <viewer cache>]
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

ID = '23a0a0b1-2323-4d0a-8e23-3c4d5e6f7c23'
NAME = 'EXP-23 doors upstairs at the outpost'
MAP = 'URB_ResearchOutpost'
SHA = '50ad92b70e959aacbf126a821d70d481551c5b8f5569237f6b24d44b307c113d'
PL = 'TheWorld.PersistentLevel.'
# (pieces, quarter turns about the grid's corner, tiles, storeys), as the recipe snap moves them
MOVES = ((('XComDestructibleActor_302', 'XComInteractiveLevelActor_25'), 0, (1, 8), 0),)    # into door 26's doorway
COPIES = ((('XComDestructibleActor_0', 'XComInteractiveLevelActor_0'), 0, (35, 13), 6),)    # into door 25's, upstairs
DELETED = ('XComDestructibleActor_303', 'XComInteractiveLevelActor_26')
COPY_ID = '23a0a0b1-2323-4a23-9c23-0d1e2f3a4d%02d'


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map=MAP, sha256=SHA, exporterVersion=14)))
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
    ship = '%s_%s_%s' % (stem, 'Exp23Door'[:compiler.NAME_LIMIT - len('patch_') - len(stem) - 6], ID[:4])
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name=NAME, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=SHA, exporterVersion=14),
               output=dict(shipAs=ship, patch='patch_' + ship.lower()),
               overrides=overrides, added=added, nextSerial=len(added),
               # The viewer's basis (x, up, y): above the east building's rooftop room, looking north.
               view=dict(camera=[1650, 1700, -300], target=[1650, 384, 860]))
    spec, report = compiler.compile_project(doc, scene, enable=['door'])
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
