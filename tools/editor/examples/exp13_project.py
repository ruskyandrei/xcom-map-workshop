"""EXP-13's project: destructible props placed on URB_Bar by the editor's compiler, after they joined milestone M1.

Writes the project into the projects folder (the editor settings), so the viewer opens it like any other, and prints
its id. Run again, it saves the same edits as the next revision.

  python tools/editor/examples/exp13_project.py [--cache <viewer cache>]

The edits (research/experiments/EXP-13-destructible-props.md), all XComDestructibleActor, in and beside the south-west
street of EXP-11:
- copies: a dumpster at yaw 0 and one at 45 degrees (pivots on tile corners, as the map's dumpsters stand); a closed
  trash can upright and one knocked over (roll 90, lifted so it lies on the ground); a box stack at 15 degrees, a keg
  and a trash bag at 45 degrees, on tile centres;
- moved: the dumpster XComDestructibleActor_62 one tile north and turned 90 degrees, inside its fenced lot;
- deleted: the dumpster XComDestructibleActor_61 beside it, and the fence section XComDestructibleActor_18 between
  XComDestructibleActor_39 and XComDestructibleActor_89, which must stay.
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

ID = 'd3e1c0a7-13de-4b5a-9c2e-7f1a3b5c8d13'
NAME = 'EXP-13 destructible props'
BAR_SHA = 'a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5'
PL = 'TheWorld.PersistentLevel.'
TURN = 65536 / 360.0     # rotation units per degree


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map='URB_Bar', sha256=BAR_SHA, exporterVersion=12)))
    by = {o['actor']: o for o in scene['objects'] if o['layer'] == 'base'}

    def target(name):
        return dict(package='URB_Bar', level='base', actor=PL + name)

    added, serial = [], 0

    def add(name, at, pitch=0.0, yaw=0.0, roll=0.0):
        nonlocal serial
        serial += 1
        src = by[PL + name]
        assert src['actorClass'] == 'XComDestructibleActor' and not src.get('partner'), name
        added.append({'id': '%s-%012d' % (ID[:23], serial), 'actor': PL + '%s_copy%d' % (name, serial),
                      'from': target(name), 'components': [src['component']],
                      'location': [round(v, 4) for v in at],
                      'rotation': [round(pitch * TURN, 3), round(yaw * TURN, 3), round(roll * TURN, 3)],
                      'prefab': None, 'partner': None})

    dumpster, can = 'XComDestructibleActor_61', 'XComDestructibleActor_29'
    add(dumpster, (-1344, -768, 0))
    add(dumpster, (-960, -768, 0), yaw=45)
    add(can, (-1200, -1008, 0))
    # Rolled onto its side about its base, the can's radius (23.7) would be below the ground.
    add(can, (-1104, -1200, 23.7), roll=90)
    add('XComDestructibleActor_292', (-1680, -1008, 0), yaw=15)      # box stack
    add('XComDestructibleActor_13', (-1872, -1008, 0))               # keg
    add('XComDestructibleActor_297', (-1488, -1008, 0), yaw=45)      # trash bag

    moved = by[PL + 'XComDestructibleActor_62']
    overrides = sorted([
        dict(target=target('XComDestructibleActor_62'),
             location=[round(moved['location'][0], 4), round(moved['location'][1] + 96, 4), moved['location'][2]],
             rotation=[0, moved['rotation'][1] + 16384, 0]),
        dict(target=target('XComDestructibleActor_61'), deleted=True),
        dict(target=target('XComDestructibleActor_18'), deleted=True),
    ], key=lambda r: (r['target']['package'], r['target']['level'], r['target']['actor']))

    # As the viewer names a project's output (project.js outputNames): 30 characters at most for the patch (T-09).
    shipAs = 'URB_Bar_EXP13Destr_' + ID[:4]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name=NAME, mode='edit',
               source=dict(map='URB_Bar', package='URB_Bar.upk', sha256=BAR_SHA, exporterVersion=12),
               output=dict(shipAs=shipAs, patch='patch_' + shipAs.lower()),
               overrides=overrides, added=sorted(added, key=lambda r: r['actor']), nextSerial=serial,
               # The viewer's basis (x, up, y): above the south-west street, looking north-west over the props.
               view=dict(camera=[-1100, 1300, -2500], target=[-1700, 0, -1100]))
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
    print('saved %s (%s) revision %d in %s: %d moved, %d deleted, %d added'
          % (NAME, ID, saved['revision'], store.path(ID), report['counts']['moved'], report['counts']['deleted'], report['counts']['added']))


if __name__ == '__main__':
    main()
