"""EXP-23 run 1's project: doors made in the map (private/plans/done/cars-doors-ladders-plan.md, section 6.8).

The bar's walls are fractured meshes with their doorways in them, and a fracturing piece doesn't build before M3, so
the project makes its openings with doors: a deleted door leaves its doorway open.
- The inner wall (XComDecoFracLevelActor_16) holds two doors, 7 tiles apart: XComInteractiveLevelActor_7 (with its
  frame XComDestructibleActor_65) is deleted, and XComInteractiveLevelActor_6 (frame XComDestructibleActor_60) moves
  7 tiles along the wall into its doorway, from (-816, 672) to (-1488, 672).
- The front door, XComInteractiveLevelActor_5 (frame XComDestructibleActor_30, the facade at (-1008, 192)), is copied
  into the doorway door 6 leaves, 2 tiles east and 5 north, unturned: (-816, 672).
- The west wall's door, XComInteractiveLevelActor_4 (frame XComDestructibleActor_31, at (-1632, 816)), is deleted: its
  doorway stays open.

The door family didn't build yet when it ran: the experiment's build passed it on (build.py --family door).
Writes the project into the projects folder (the editor settings) and prints its id. Run again, it saves the same
edit as the next revision.

  python tools/editor/examples/exp23_doors_project.py [--cache <viewer cache>]
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

ID = '23e0a0b1-2323-4d0a-8e23-3c4d5e6f7a23'
NAME = 'EXP-23 doors on the bar'
BAR_SHA = 'a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5'
PL = 'TheWorld.PersistentLevel.'
MOVED = ('XComDestructibleActor_60', 'XComInteractiveLevelActor_6')      # 7 tiles along the inner wall (-X)
MOVE_TILES = (-7, 0)
COPIED = ('XComDestructibleActor_30', 'XComInteractiveLevelActor_5')     # into door 6's doorway
COPY_TILES = (2, 5)
DELETED = ('XComDestructibleActor_65', 'XComInteractiveLevelActor_7', 'XComDestructibleActor_31',
           'XComInteractiveLevelActor_4')
COPY_IDS = ('23e0a0b1-2323-4a23-9c23-0d1e2f3a4b01', '23e0a0b1-2323-4a23-9c23-0d1e2f3a4b02')


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map='URB_Bar', sha256=BAR_SHA, exporterVersion=14)))
    origin = scene['tileGrid']['origin'][:2]

    def parts(name):
        found = [o for o in scene['objects'] if o['layer'] == 'base' and o['actor'] == PL + name]
        assert found, name
        return found

    def grid_pose(src, tiles):
        # the pose the recipe snap gives: whole tiles from the original, exactly
        at = [src['location'][0] + compiler.TILE * tiles[0], src['location'][1] + compiler.TILE * tiles[1],
              src['location'][2]]
        return compiler.nearest_grid_pose(src['location'], src['rotation'], at, list(src['rotation']), origin)

    target = lambda name: dict(package='URB_Bar', level='base', actor=PL + name)  # noqa: E731
    overrides = []
    for name in MOVED:
        loc, rot = grid_pose(parts(name)[0], MOVE_TILES)
        overrides.append(dict(target=target(name), location=loc, rotation=rot))
    overrides += [dict(target=target(name), deleted=True) for name in DELETED]
    added = []
    for k, (name, id_) in enumerate(zip(COPIED, COPY_IDS), 1):
        found = parts(name)
        loc, rot = grid_pose(found[0], COPY_TILES)
        added.append(dict(id=id_, actor=PL + '%s_copy%d' % (name, k), **{'from': target(name)},
                          components=sorted(o['component'] for o in found), location=loc, rotation=rot))
    # As the viewer names a project's output (project.js outputNames): 30 characters at most for the patch (T-09).
    ship = 'URB_Bar_EXP23Door_' + ID[:4]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name=NAME, mode='edit',
               source=dict(map='URB_Bar', package='URB_Bar.upk', sha256=BAR_SHA, exporterVersion=14),
               output=dict(shipAs=ship, patch='patch_' + ship.lower()),
               overrides=overrides, added=added, nextSerial=len(added),
               # The viewer's basis (x, up, y): above the bar's back room, looking north at the inner wall.
               view=dict(camera=[-1150, 1300, -300], target=[-1150, 0, 600]))
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
    print('saved %s (%s) revision %d in %s as %s: %d moved, %d deleted, %d added; assemblies %s; warnings %s'
          % (NAME, ID, saved['revision'], store.path(ID), ship, report['counts']['moved'], report['counts']['deleted'],
             report['counts']['added'], [(m['id'], m['translation']) for m in report['assemblies']],
             [w['message'] for w in report['warnings']]))


if __name__ == '__main__':
    main()
