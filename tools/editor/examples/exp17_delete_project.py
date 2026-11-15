"""EXP-17 run 9's project: the bar's pool table deleted by the editor, its light baked out of the room by our relight.

Writes the project into the projects folder (the editor settings), so the viewer opens it like any other, and prints
its id. Run again, it saves the same edit as the next revision.

  python tools/editor/examples/exp17_delete_project.py [--cache <viewer cache>]

The edit (research/experiments/EXP-17-lighting-edits-in-game.md, run 9): the pool table XComDestructibleActor_491 is
deleted, with the glass standing on its edge, XComDestructibleActor_45, which would float without it. The compiler
hides both exactly; tools/bake/relight.py --remove-caster for each takes their shadow and bounce out of the room's
baked light. The spec is compiled with --stream-only, since the relit variant of
URB_Bar, not patchtool, ships the map.
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

ID = '7a1f0e17-0917-4c0d-8e5a-3b2d1c9f0a17'
NAME = 'EXP-17 pool table deleted'
BAR_SHA = 'a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5'
PL = 'TheWorld.PersistentLevel.'
POOL_TABLE = 'XComDestructibleActor_491'
GLASS = 'XComDestructibleActor_45'          # a short glass on the table's edge


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map='URB_Bar', sha256=BAR_SHA, exporterVersion=12)))
    by = {o['actor']: o for o in scene['objects'] if o['layer'] == 'base'}
    for name in (POOL_TABLE, GLASS):
        assert by[PL + name]['actorClass'] == 'XComDestructibleActor' and not by[PL + name].get('partner'), name
    x, y, _ = by[PL + POOL_TABLE]['location']
    overrides = [dict(target=dict(package='URB_Bar', level='base', actor=PL + name), deleted=True)
                 for name in sorted((POOL_TABLE, GLASS))]
    # As the viewer names a project's output (project.js outputNames): 30 characters at most for the patch (T-09).
    shipAs = 'URB_Bar_EXP17Pool_' + ID[:4]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name=NAME, mode='edit',
               source=dict(map='URB_Bar', package='URB_Bar.upk', sha256=BAR_SHA, exporterVersion=12),
               output=dict(shipAs=shipAs, patch='patch_' + shipAs.lower()),
               overrides=overrides, added=[], nextSerial=0,
               # The viewer's basis (x, up, y): above the room, looking down at where the pool table stood.
               view=dict(camera=[round(x + 300), 700, round(y - 450)], target=[round(x), 0, round(y)]))
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
          % (NAME, ID, saved['revision'], store.path(ID), report['counts']['moved'], report['counts']['deleted'],
             report['counts']['added']))


if __name__ == '__main__':
    main()
