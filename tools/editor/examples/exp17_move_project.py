"""EXP-17 run 10's project: the bar's pool table moved by the editor into a ceiling spot's pool, with its shadow baked
onto the floor at the new place and taken away at the old one.

Writes the project into the projects folder (the editor settings), so the viewer opens it like any other, and prints
its id. Run again, it saves the same edit as the next revision.

  python tools/editor/examples/exp17_move_project.py [--cache <viewer cache>]

The edit (research/experiments/EXP-17-lighting-edits-in-game.md, run 10):
- the pool table XComDestructibleActor_491 moves from (528, 670) to (-48, 240), turned a quarter turn (yaw 16384),
  onto the open floor under the ceiling spot SpotLight_3, by the island counter's corner nearest the street windows:
  the brightest open floor in the room that fits it (EXP-17 run 10 notes);
- the short glass on its edge, XComDestructibleActor_45, moves with it and turns with it.
The compiler hides both where they stood and copies them to the new poses. The spec is compiled with --stream-only:
the relit variant of URB_Bar ships the map, with the patch's tile seeds (map.seedExternally), and
tools/bake/relight.py --edit-spec takes the same spec, so the copies' shadows are baked into the floor around them.
"""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import compiler  # noqa: E402
import settings  # noqa: E402
from export_math import transform  # noqa: E402
from projects import ProjectStore  # noqa: E402
from settings import load_settings  # noqa: E402

ID = '7a1f0e17-1010-4d0e-9b6c-5e4f3a2b1c10'
NAME = 'EXP-17 pool table moved'
BAR_SHA = 'a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5'
PL = 'TheWorld.PersistentLevel.'
POOL_TABLE = 'XComDestructibleActor_491'
GLASS = 'XComDestructibleActor_45'
TO, YAW = (-48.0, 240.0), 16384


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map='URB_Bar', sha256=BAR_SHA, exporterVersion=12)))
    by = {o['actor']: o for o in scene['objects'] if o['layer'] == 'base'}
    table, glass = by[PL + POOL_TABLE], by[PL + GLASS]
    for o in (table, glass):
        assert o['actorClass'] == 'XComDestructibleActor' and not o.get('partner') and o['rotation'] == [0, 0, 0]
    new_table = [TO[0], TO[1], table['location'][2]]
    # the glass keeps its place on the table: its offset from the table, turned with it
    m = transform(new_table, [0, YAW, 0], [1, 1, 1])
    off = [glass['location'][k] - table['location'][k] for k in range(3)]
    new_glass = [round(sum(m[i][k] * off[k] for k in range(3)) + m[i][3], 4) for i in range(3)]

    def target(name):
        return dict(package='URB_Bar', level='base', actor=PL + name)
    overrides = [dict(target=target(GLASS), location=new_glass, rotation=[0, YAW, 0]),
                 dict(target=target(POOL_TABLE), location=new_table, rotation=[0, YAW, 0])]
    # As the viewer names a project's output (project.js outputNames): 30 characters at most for the patch (T-09).
    shipAs = 'URB_Bar_EXP17Move_' + ID[:4]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name=NAME, mode='edit',
               source=dict(map='URB_Bar', package='URB_Bar.upk', sha256=BAR_SHA, exporterVersion=12),
               output=dict(shipAs=shipAs, patch='patch_' + shipAs.lower()),
               overrides=overrides, added=[], nextSerial=0,
               # The viewer's basis (x, up, y): above the counter's corner, looking down at the table's new place.
               view=dict(camera=[round(TO[0] + 300), 700, round(TO[1] - 450)], target=[round(TO[0]), 0, round(TO[1])]))
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
    print('saved %s (%s) revision %d in %s: %d moved, %d deleted, %d added; glass to %s'
          % (NAME, ID, saved['revision'], store.path(ID), report['counts']['moved'], report['counts']['deleted'],
             report['counts']['added'], new_glass))


if __name__ == '__main__':
    main()
