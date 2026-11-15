"""EXP-22 run 2's project: ladders on CSmallScout_Farm, whose patch holds near helpers (private/plans/done/cars-doors-ladders-plan.md,
sections 3.6 and 5.4).

- XComLadder_4 (a wooden ladder against a shed, facing +X) moves three tiles along the shed's wall, from
  (-1392, -1680) to (-1392, -1392): foot tile (11, 22, 2), top tile (12, 22, 5). patch_farm's XComLadder_3 stands 36
  units from it with its foot a level lower: a near helper, which leaves the variant's copy of patch_farm with a
  warning.
- XComLadder_0 (the red shed's west wall, facing +X) is copied two tiles along its wall, to (-1872, -240): foot tile
  (6, 34, 2), top tile (7, 34, 5). The original stays, with its near helper (patch_farm's XComLadder_4).

The map's package and its records name it in two cases (CsmallScout_Farm.upk, Name="CSmallScout_Farm"): the project
takes the record's, as the editor's map browser does, and its pieces the package's.
The ladder family didn't build yet when it ran: the experiment's build passed it on (build.py --family ladder).
Writes the project into the projects folder (the editor settings) and prints its id. Run again, it saves the same
edit as the next revision.

  python tools/editor/examples/exp22_farm_project.py [--cache <viewer cache>]
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

ID = '22f0a0b1-2222-4d0a-8e22-3c4d5e6f7f22'
NAME = 'EXP-22 ladders on the farm'
MAP, PACKAGE = 'CSmallScout_Farm', 'CsmallScout_Farm'
FARM_SHA = 'ae812dfb72da490956f8e29e822a36be6420f414cb4e8c1ede6c7cc2e9bf9163'
PL = 'TheWorld.PersistentLevel.'
COPY_ID = '22f0a0b1-2222-4a22-9c22-0d1e2f3a4f22'
MOVE_TO = (-1392.0, -1392.0)     # XComLadder_4, three tiles along its wall
COPY_TO = (-1872.27, -240.0)     # XComLadder_0's copy, two tiles along its wall


def output_names(map_name, word, id_):
    """As the editor names a project's output (web/project.js outputNames): 30 characters at most for the patch."""
    stem = map_name[:12]
    room = compiler.NAME_LIMIT - len('patch_') - len(stem) - 6
    ship = '%s_%s_%s' % (stem, word[:room], id_[:4])
    return dict(shipAs=ship, patch='patch_' + ship.lower())


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map=MAP, sha256=FARM_SHA, exporterVersion=14)))
    origin = scene['tileGrid']['origin'][:2]

    def parts(name):
        found = [o for o in scene['objects'] if o['layer'] == 'base' and o['actor'] == PL + name]
        assert found and found[0]['actorClass'] == 'XComLadder', name
        return found

    def grid_pose(src, at):
        # the pose the recipe snap gives: whole tiles from the original, exactly
        return compiler.nearest_grid_pose(src['location'], src['rotation'], [at[0], at[1], src['location'][2]],
                                          list(src['rotation']), origin)

    four, zero = parts('XComLadder_4')[0], parts('XComLadder_0')
    loc4, rot4 = grid_pose(four, MOVE_TO)
    loc0, rot0 = grid_pose(zero[0], COPY_TO)
    target = lambda name: dict(package=PACKAGE, level='base', actor=PL + name)  # noqa: E731
    added = [dict(id=COPY_ID, actor=PL + 'XComLadder_0_copy1', **{'from': target('XComLadder_0')},
                  components=sorted(o['component'] for o in zero), location=loc0, rotation=rot0)]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name=NAME, mode='edit',
               source=dict(map=MAP, package=PACKAGE + '.upk', sha256=FARM_SHA, exporterVersion=14),
               output=output_names(MAP, 'Exp22L', ID),
               overrides=[dict(target=target('XComLadder_4'), location=loc4, rotation=rot4)], added=added, nextSerial=1,
               # The viewer's basis (x, up, y): west of the two sheds, looking east.
               view=dict(camera=[-2600, 900, -900], target=[-1600, 0, -900]))
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
    print('saved %s (%s) revision %d in %s as %s: %d moved, %d added; ladders %s; stream hides %s; warnings %s'
          % (NAME, ID, saved['revision'], store.path(ID), doc['output']['shipAs'], report['counts']['moved'],
             report['counts']['added'], list(zip(copy['labels'], copy['ladders'])), spec.get('streamHides'),
             [w['message'] for w in report['warnings']]))


if __name__ == '__main__':
    main()
