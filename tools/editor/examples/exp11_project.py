"""EXP-11's project: static placements on URB_Bar for the first in-game check of the editor's compiler (E3).

Writes the project into the projects folder (the editor settings), so the viewer opens it like any other, and prints
its id. Run again, it saves the same edits as the next revision.

  python tools/editor/examples/exp11_project.py [--cache <viewer cache>]

The edits (research/experiments/EXP-11-static-placement.md):
- a yaw row of StreetLight_D copies at yaw 0, 15, 45 and 90 degrees (y -816), a pitch row at 15, 45 and 90 (y -1488)
  and a roll row at 15, 45 and 90 (y -1008), on tile centres, from XComLevelActor_250;
- three FogPod copies (XComLevelActor_15) on the yaw row's line: +24 and +48 units off a tile centre, and one 64 units
  up, floating;
- a copy of the lamp post XComLevelActor_27, which is also deleted (a deleted template is still copied);
- moved: the FogPod XComLevelActor_15 one tile east (+96 x), and the lamp post XComLevelActor_87 48 units north
  and turned 45 degrees;
- deleted: the lamp post XComLevelActor_27 and the railing StaticMeshActor_60, whose neighbours StaticMeshActor_59
  and StaticMeshActor_61 overlap it and must stay.
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

ID = 'b7f3a2c1-5e11-4c8e-9a3d-2f6e0b1c4d11'
NAME = 'EXP-11 static placement'
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
        added.append({'id': '%s-%012d' % (ID[:23], serial), 'actor': PL + '%s_copy%d' % (name, serial),
                      'from': target(name), 'components': [src['component']],
                      'location': [round(v, 4) for v in at],
                      'rotation': [round(pitch * TURN, 3), round(yaw * TURN, 3), round(roll * TURN, 3)],
                      'prefab': None, 'partner': None})

    light = by[PL + 'XComLevelActor_250']['location'][2]
    for x, yaw in zip((-1392, -1200, -1008, -816), (0, 15, 45, 90)):
        add('XComLevelActor_250', (x, -816, light), yaw=yaw)
    for x, pitch in zip((-2160, -1680, -1200), (15, 45, 90)):
        add('XComLevelActor_250', (x, -1488, light), pitch=pitch)
    for x, roll in zip((-1872, -1488, -1104), (15, 45, 90)):
        add('XComLevelActor_250', (x, -1008, light), roll=roll)
    pod = by[PL + 'XComLevelActor_15']['location'][2]
    add('XComLevelActor_15', (-528 + 24, -816, pod))
    add('XComLevelActor_15', (-336 + 48, -816, pod))
    add('XComLevelActor_15', (-144, -816, pod + 64))
    post = by[PL + 'XComLevelActor_27']
    add('XComLevelActor_27', (-720, -1488, post['location'][2]), yaw=post['rotation'][1] / TURN)

    fog, lamp = by[PL + 'XComLevelActor_15'], by[PL + 'XComLevelActor_87']
    overrides = sorted([
        dict(target=target('XComLevelActor_15'), location=[round(fog['location'][0] + 96, 4), round(fog['location'][1], 4), fog['location'][2]],
             rotation=list(fog['rotation'])),
        dict(target=target('XComLevelActor_87'), location=[round(lamp['location'][0], 4), round(lamp['location'][1] + 48, 4), lamp['location'][2]],
             rotation=[0, lamp['rotation'][1] + 8192, 0]),
        dict(target=target('XComLevelActor_27'), deleted=True),
        dict(target=target('StaticMeshActor_60'), deleted=True),
    ], key=lambda r: (r['target']['package'], r['target']['level'], r['target']['actor']))

    # As the viewer names a project's output (project.js outputNames): 30 characters at most for the patch (T-09).
    shipAs = 'URB_Bar_EXP11Static_' + ID[:4]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name=NAME, mode='edit',
               source=dict(map='URB_Bar', package='URB_Bar.upk', sha256=BAR_SHA, exporterVersion=12),
               output=dict(shipAs=shipAs, patch='patch_' + shipAs.lower()),
               overrides=overrides, added=sorted(added, key=lambda r: r['actor']), nextSerial=serial,
               # The viewer's basis (x, up, y): above the south-west street, looking north over the rows.
               view=dict(camera=[-1200, 1600, -2600], target=[-1300, 0, -1000]))
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
