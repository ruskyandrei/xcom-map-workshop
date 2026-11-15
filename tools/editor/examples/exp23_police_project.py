"""EXP-23 run 2's project: doors made in the map on URB_PoliceStation (private/plans/done/cars-doors-ladders-plan.md, 6.8).

Police Station's doors stand a level up (z 80, on a grid whose origin is at z -48), in fractured walls with their
doorways in them, as on the bar; the project makes its openings with doors again (EXP-23 run 1).
- The inner back wall (XComDecoFracLevelActor_4, along Y at x -384) holds two single doors 13 tiles apart:
  XComInteractiveLevelActor_2 (frame XComDestructibleActor_93) is deleted, and XComInteractiveLevelActor_95 (frame
  XComDestructibleActor_1090, a prefab's) moves 13 tiles along the wall into its doorway, from (-384, 720) to
  (-384, -528).
- XComInteractiveLevelActor_0 (frame XComDestructibleActor_42, the back wall at (672, -1680)) is copied into the
  doorway door 95 leaves, 11 tiles west and 25 north, unturned: (-384, 720).
- The inner wall XComDecoFracLevelActor_11 (PoliceStationWallD, along X at y -672) has two double doorways with no
  door. The west facade's double door 17 and 18 (each half a leaf with its frame, 15 and 35; at x -480, y -912 and
  -816) is copied a quarter turn round into the west one (x -192 to 0): its halves at (-48, -672) and (-144, -672).
- The facade's other double door, 19 and 20 (frames 13 and 14, y -1680 and -1584), is deleted: its doorway stays
  open.

The door family didn't build yet when it ran: the experiment's build passed it on (build.py --family door).
Writes the project into the projects folder (the editor settings) and prints its id. Run again, it saves the same
edit as the next revision.

  python tools/editor/examples/exp23_police_project.py [--cache <viewer cache>]
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

ID = '23f0a0b1-2323-4d0a-8e23-3c4d5e6f7b23'
NAME = 'EXP-23 doors at the police station'
MAP = 'URB_PoliceStation'
SHA = '86785ed731811d0b337e8ab2bb9aa0215678d88b48de0beadea9bf7193f0fa29'
PL = 'TheWorld.PersistentLevel.'
# (pieces, quarter turns about the grid's corner, tiles), as the recipe snap moves them
MOVES = ((('XComDestructibleActor_1090', 'XComInteractiveLevelActor_95'), 0, (0, -13)),)  # along the inner back wall
COPIES = ((('XComDestructibleActor_42', 'XComInteractiveLevelActor_0'), 0, (-11, 25)),    # into door 95's doorway
          (('XComDestructibleActor_15', 'XComInteractiveLevelActor_17', 'XComDestructibleActor_35',
            'XComInteractiveLevelActor_18'), 1, (34, 6)))                                  # into WallD's doorway
DELETED = ('XComDestructibleActor_93', 'XComInteractiveLevelActor_2', 'XComDestructibleActor_13',
           'XComInteractiveLevelActor_19', 'XComDestructibleActor_14', 'XComInteractiveLevelActor_20')
COPY_ID = '23f0a0b1-2323-4a23-9c23-0d1e2f3a4c%02d'


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

    def grid_pose(src, turns, tiles):
        # the pose the recipe snap gives: quarter turns about the grid's corner and whole tiles, exactly
        x, y = compiler.turned((src['location'][0] - origin[0], src['location'][1] - origin[1]), turns)
        at = [origin[0] + x + compiler.TILE * tiles[0], origin[1] + y + compiler.TILE * tiles[1], src['location'][2]]
        rot = [src['rotation'][0], src['rotation'][1] + turns * compiler.QUARTER, src['rotation'][2]]
        return compiler.nearest_grid_pose(src['location'], src['rotation'], at, rot, origin)

    target = lambda name: dict(package=MAP, level='base', actor=PL + name)  # noqa: E731
    overrides = []
    for names, turns, tiles in MOVES:
        for name in names:
            loc, rot = grid_pose(parts(name)[0], turns, tiles)
            overrides.append(dict(target=target(name), location=loc, rotation=rot))
    overrides += [dict(target=target(name), deleted=True) for name in DELETED]
    added = []
    for names, turns, tiles in COPIES:
        for name in names:
            found = parts(name)
            loc, rot = grid_pose(found[0], turns, tiles)
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
               # The viewer's basis (x, up, y): above the station's west half, looking north.
               view=dict(camera=[-400, 1800, -1800], target=[-400, 80, -300]))
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
