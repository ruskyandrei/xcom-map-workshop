"""EXP-19 run 1's project: the moon's shadow maps (baker plan step L3). One of the dumpsters behind the bar is
moved along the back wall: deleted where it stands, and a copy of it put in the gap toward the next dumpster.

Under the moon (the bar's dominant light, nearly overhead) a dumpster's shadow lies on the asphalt under and just
beside it. Until L3 the moon's shadow maps kept it: a moved piece left a dark footprint where it stood. The build now
relights them: the footprint is moonlit, and the copy casts its shadow where it stands.

Writes the project into the projects folder (the editor settings), so the viewer opens it like any other, and prints
its id. Run again, it saves the same edit as the next revision.

  python tools/editor/examples/exp19_moon_project.py [--cache <viewer cache>]

The edit: XComDestructibleActor_294 (Dumpster_A, at (-1539, 1719) against the back wall, the second dumpster from the
alley end) is deleted; its copy stands at (-1100, 1719), facing the same way, between it and XComDestructibleActor_6.
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

ID = '19e0a0b1-2222-4d0a-8e19-3c4d5e6f7a19'
NAME = 'EXP-19 dumpster moved under the moon'
BAR_SHA = 'a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5'
PL = 'TheWorld.PersistentLevel.'
DUMPSTER = 'XComDestructibleActor_294'
COPY_ID = '19e0a0b1-2222-4a19-9c19-0d1e2f3a4b19'
TO = (-1100.0, 1719.0)


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map='URB_Bar', sha256=BAR_SHA, exporterVersion=12)))
    parts = [o for o in scene['objects'] if o['layer'] == 'base' and o['actor'] == PL + DUMPSTER]
    dumpster = parts[0]
    assert dumpster['actorClass'] == 'XComDestructibleActor' and not dumpster.get('partner')
    target = dict(package='URB_Bar', level='base', actor=PL + DUMPSTER)
    added = [dict(id=COPY_ID, actor=PL + DUMPSTER + '_copy1', **{'from': dict(target)},
                  components=sorted(o['component'] for o in parts),
                  location=[TO[0], TO[1], dumpster['location'][2]], rotation=list(dumpster['rotation']))]
    # As the viewer names a project's output (project.js outputNames): 30 characters at most for the patch (T-09).
    shipAs = 'URB_Bar_EXP19Moon_' + ID[:4]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name=NAME, mode='edit',
               source=dict(map='URB_Bar', package='URB_Bar.upk', sha256=BAR_SHA, exporterVersion=12),
               output=dict(shipAs=shipAs, patch='patch_' + shipAs.lower()),
               overrides=[dict(target=target, deleted=True)], added=added, nextSerial=1,
               # The viewer's basis (x, up, y): above the parking lot, looking at the two places.
               view=dict(camera=[-1320, 900, 2500], target=[-1320, 0, 1719]))
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
