"""EXP-22 run 1's project: ladders made in the map (private/plans/done/cars-doors-ladders-plan.md, section 5.4).

- XComLadder_3 (the bar's west wall, facing +X, saved with no Rotation) moves two tiles along its wall, from
  (-1680, 336) to (-1680, 528): the order hazard (its copy's own rebuild volume reaches its foot before its top),
  which the Build's small volume over the top tile, first in the level's list, answers. Its helper in patch_bar
  (XComLadder_11) leaves the variant's copy of the patch, so the old place no longer climbs.
- XComLadder_4 (the south wall, facing -Y) is copied a quarter turn round onto the west wall, at (-1680, 1008), facing
  +X: foot tile (11, 30, 0), top tile (12, 30, 6) on the roof. The original stays, with its helper.

The ladder family didn't build yet when it ran: the experiment's build passed it on (build.py --family ladder).
Writes the project into the projects folder (the editor settings), so the viewer opens it like any other, and prints
its id. Run again, it saves the same edit as the next revision.

  python tools/editor/examples/exp22_ladders_project.py [--cache <viewer cache>]
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

ID = '22e0a0b1-2222-4d0a-8e22-3c4d5e6f7a22'
NAME = 'EXP-22 ladders on the bar'
BAR_SHA = 'a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5'
PL = 'TheWorld.PersistentLevel.'
COPY_ID = '22e0a0b1-2222-4a22-9c22-0d1e2f3a4b22'
MOVE_TO = (-1680.0, 528.0)       # XComLadder_3, two tiles along its wall
COPY_TO = (-1680.0, 1008.0)      # XComLadder_4's copy, a quarter turn round


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map='URB_Bar', sha256=BAR_SHA, exporterVersion=14)))
    origin = scene['tileGrid']['origin'][:2]

    def parts(name):
        found = [o for o in scene['objects'] if o['layer'] == 'base' and o['actor'] == PL + name]
        assert found and found[0]['actorClass'] == 'XComLadder', name
        return found

    def grid_pose(src, at, turns):
        # the pose the recipe snap gives: whole tiles and quarter turns from the original, exactly
        return compiler.nearest_grid_pose(src['location'], src['rotation'], [at[0], at[1], src['location'][2]],
                                          [0, src['rotation'][1] + turns * compiler.QUARTER, 0], origin)

    three, four = parts('XComLadder_3')[0], parts('XComLadder_4')
    loc3, rot3 = grid_pose(three, MOVE_TO, 0)
    loc4, rot4 = grid_pose(four[0], COPY_TO, 1)
    target = lambda name: dict(package='URB_Bar', level='base', actor=PL + name)  # noqa: E731
    added = [dict(id=COPY_ID, actor=PL + 'XComLadder_4_copy1', **{'from': target('XComLadder_4')},
                  components=sorted(o['component'] for o in four), location=loc4, rotation=rot4)]
    # As the viewer names a project's output (project.js outputNames): 30 characters at most for the patch (T-09).
    shipAs = 'URB_Bar_EXP22Ladder_' + ID[:4]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name=NAME, mode='edit',
               source=dict(map='URB_Bar', package='URB_Bar.upk', sha256=BAR_SHA, exporterVersion=14),
               output=dict(shipAs=shipAs, patch='patch_' + shipAs.lower()),
               overrides=[dict(target=target('XComLadder_3'), location=loc3, rotation=rot3)], added=added, nextSerial=1,
               # The viewer's basis (x, up, y): west of the bar, looking at its west wall.
               view=dict(camera=[-2600, 1100, 700], target=[-1680, 200, 700]))
    spec, report = compiler.compile_project(doc, scene, enable=['ladder'])
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
    copy = spec['objects'][0]
    print('saved %s (%s) revision %d in %s: %d moved, %d deleted, %d added; ladders %s; stream hides %s; warnings %s'
          % (NAME, ID, saved['revision'], store.path(ID), report['counts']['moved'], report['counts']['deleted'],
             report['counts']['added'], list(zip(copy['labels'], copy['ladders'])), spec.get('streamHides'),
             [w['message'] for w in report['warnings']]))


if __name__ == '__main__':
    main()
