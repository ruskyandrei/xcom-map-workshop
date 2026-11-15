"""EXP-17 run 11's project: a piece added from nothing, a copy of the bar's claw machine, standing in a ceiling spot's
pool with its shadow baked into the floor. The first project built by the editor's build (tools/editor/build.py) and
installed by the lab installer (tools/lab/lab_install.py).

Writes the project into the projects folder (the editor settings), so the viewer opens it like any other, and prints
its id. Run again, it saves the same edit as the next revision.

  python tools/editor/examples/exp17_add_project.py [--cache <viewer cache>]

The edit (research/experiments/EXP-17-lighting-edits-in-game.md, run 11): a copy of the claw machine
XComDestructibleActor_316, which stays where it stands against the back wall, at (-48, 1008), facing as the original
does: the open floor under the ceiling spot SpotLight_8, at the island counter's far corner from the street windows,
the brightest open floor in the room that fits it (floor light 7.37 under it).
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

ID = '7a1f0e17-1111-4e0f-8c6d-2b3a4c5d6e11'
NAME = 'EXP-17 claw machine added'
BAR_SHA = 'a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5'
PL = 'TheWorld.PersistentLevel.'
CLAW = 'XComDestructibleActor_316'
COPY_ID = '7a1f0e17-1111-4a11-9c11-0c1a3f4e5d11'
TO = (-48.0, 1008.0)


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map='URB_Bar', sha256=BAR_SHA, exporterVersion=12)))
    parts = [o for o in scene['objects'] if o['layer'] == 'base' and o['actor'] == PL + CLAW]
    claw = parts[0]
    assert claw['actorClass'] == 'XComDestructibleActor' and not claw.get('partner')
    added = [dict(id=COPY_ID, actor=PL + CLAW + '_copy1',
                  **{'from': dict(package='URB_Bar', level='base', actor=PL + CLAW)},
                  components=sorted(o['component'] for o in parts),
                  location=[TO[0], TO[1], claw['location'][2]], rotation=list(claw['rotation']))]
    # As the viewer names a project's output (project.js outputNames): 30 characters at most for the patch (T-09).
    shipAs = 'URB_Bar_EXP17Add_' + ID[:4]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name=NAME, mode='edit',
               source=dict(map='URB_Bar', package='URB_Bar.upk', sha256=BAR_SHA, exporterVersion=12),
               output=dict(shipAs=shipAs, patch='patch_' + shipAs.lower()),
               overrides=[], added=added, nextSerial=1,
               # The viewer's basis (x, up, y): above the counter, looking at the copy's place.
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
    print('saved %s (%s) revision %d in %s: %d moved, %d deleted, %d added; warnings %s'
          % (NAME, ID, saved['revision'], store.path(ID), report['counts']['moved'], report['counts']['deleted'],
             report['counts']['added'], [w['message'] for w in report['warnings']]))


if __name__ == '__main__':
    main()
