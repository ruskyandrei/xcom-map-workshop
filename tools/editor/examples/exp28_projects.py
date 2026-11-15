"""EXP-28 run 1's project: fracturing pieces and physics props made in the map
(research/experiments/EXP-28-fracturing-physics.md).

URB_Bar's walls, storey floors and counter are fracturing pieces (XComDecoFracLevelActor, XComFracLevelActor), and its
14 corpses are physics props (KAsset). Both families build since 9 November 2026. The project:
- copies the inner wall XComDecoFracLevelActor_16 (URB_BarIntWallA, along X at y 672, two doorways) with its two
  doors, XComInteractiveLevelActor_6 (frame XComDestructibleActor_60) and XComInteractiveLevelActor_7 (frame
  XComDestructibleActor_65), 9 tiles south onto the sidewalk in front of the bar: a free-standing wall with two doors.
  One move for all five pieces, so the wall's copy still lists the doors' copies in its fragment columns;
- moves the island counter's south section XComFracLevelActor_23 (BarSection4Long) 2 tiles south, into the front room;
- deletes the inner cross wall XComDecoFracLevelActor_17 (URB_BarIntWallB, along Y at x -1056): the back rooms become
  one. What hangs on it (two TVs, shelves, a menu) stays where it hangs;
- copies the upstairs floor strip XComFracLevelActor_17 (Core_384FloorB, 10 tiles by 1 at z 208, over the front
  recess) 2 tiles north, over the front room where the map has no floor at that height;
- copies the corpse KAsset_0 2 tiles east, moves KAsset_2 to a pose off the grid (a physics prop takes any pose) and
  deletes KAsset_1. On this map the corpses carry the tag `deleteme`, and whether the game shows them at all isn't
  known (findings register, F-70): the run looks for them and reads the log.

Writes the project into the projects folder (the editor settings) and prints its id. Run again, it saves the same
edit as the next revision.

  python -B tools/editor/examples/exp28_projects.py [--cache <viewer cache>]
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

ID = '28e0a0b1-2828-4d0a-8e28-3c4d5e6f7a28'
NAME = 'EXP-28 walls and corpses on the bar'
MAP = 'URB_Bar'
BAR_SHA = 'a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5'
PL = 'TheWorld.PersistentLevel.'
# (pieces, tiles (dx, dy)): each group copied by one whole-tile move
COPIES = (
    (('XComDecoFracLevelActor_16', 'XComInteractiveLevelActor_6', 'XComDestructibleActor_60',
      'XComInteractiveLevelActor_7', 'XComDestructibleActor_65'), (0, -9)),      # the inner wall and its two doors
    (('XComFracLevelActor_17',), (0, 2)),                                         # the upstairs floor strip
    (('KAsset_0',), (2, 0)),                                                      # a corpse
)
MOVES = ((('XComFracLevelActor_23',), (0, -2)),)                                  # the counter's south section
DELETED = ('XComDecoFracLevelActor_17', 'KAsset_1')
# a physics prop moved off the grid: 37.5 units east, 20 north, turned by 5000 rotation units
FREE_MOVE = ('KAsset_2', (37.5, 20.0, 0.0), 5000)


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map=MAP, sha256=BAR_SHA, exporterVersion=18)))
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

    target = lambda name: dict(package=MAP, level='base', actor=PL + name)  # noqa: E731
    overrides = []
    for names, tiles in MOVES:
        for name in names:
            loc, rot = grid_pose(parts(name)[0], tiles)
            overrides.append(dict(target=target(name), location=loc, rotation=rot))
    name, (dx, dy, dz), dyaw = FREE_MOVE
    src = parts(name)[0]
    overrides.append(dict(target=target(name), location=[src['location'][0] + dx, src['location'][1] + dy, src['location'][2] + dz],
                          rotation=[src['rotation'][0], src['rotation'][1] + dyaw, src['rotation'][2]]))
    overrides += [dict(target=target(name), deleted=True) for name in DELETED]
    added, serial = [], 0
    for names, tiles in COPIES:
        for name in names:
            serial += 1
            found = parts(name)
            loc, rot = grid_pose(found[0], tiles)
            added.append(dict(id='28e0a0b1-2828-4a28-9c28-0d1e2f3a4b%02d' % serial, actor=PL + '%s_copy%d' % (name, serial),
                              **{'from': target(name)}, components=sorted(o['component'] for o in found),
                              location=loc, rotation=rot))
    # As the viewer names a project's output (project.js outputNames): 30 characters at most for the patch (T-09).
    ship = 'URB_Bar_Exp28Frac_' + ID[:4]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name=NAME, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=BAR_SHA, exporterVersion=18),
               output=dict(shipAs=ship, patch='patch_' + ship.lower()),
               overrides=overrides, added=added, nextSerial=len(added),
               # The viewer's basis (x, up, y): above the street south of the bar, looking north at its front.
               view=dict(camera=[-1100, 1500, -1500], target=[-1100, 0, 300]))
    spec, report = compiler.compile_project(doc, scene)
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
