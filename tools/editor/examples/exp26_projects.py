"""EXP-26's project for runs 1 and 2: lights edited on URB_Bar (private/plans/done/editor-lights-plan.md, section 6;
research/experiments/EXP-26-lights.md).

One project with every kind of light edit, each in its own place so that no edited pool hides another:
- (a) SpotLight_3 deleted (EXP-17 run 8's spot, so its look is known);
- (b) PointLight_4, one of the two small purple lights just past the pool table's end (XComDestructibleActor_491;
  25 units beyond its short edge, 32 over its top, radius 78), recoloured warm and brightened;
- (c) the lamp post XComLevelActor_37 and its SpotLight_53 moved together 6 tiles east along the south street;
- (d) SpotLight_32 (a parking-lot lamp's spot) copied to the dark street corner by the wrecked sedan, east;
- (e) PointLight_15 copied to the darkest place in the play area, by the police sedans west of the bar, and the
  dumpster XComDestructibleActor_2 (on the north side, where the new light doesn't reach) copied into its pool.

Run 1 builds it with the lighting baked, run 2 without (Bake the lighting off). Run 1's build took --family light,
the light family being off then; it builds for every project since 9 November:

  python -B tools/editor/examples/exp26_projects.py [--cache <viewer cache>]
  python -B tools/editor/build.py "EXP-26 lights"            (run 1)
  python -B tools/editor/build.py "EXP-26 lights" --quick    (run 2)

The generator is historical: it makes the document as the editor wrote it then (project schema 1, an export of
generation 18), and compiles it so (tools/editor/tests/build_outputs.py takes that compile for its bar-pieces input).
It saves it at the schema the projects store writes now, which its fields still meet; if the store ever refuses it,
the generator stops after the compile, saying so.
"""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import compiler  # noqa: E402
import settings  # noqa: E402
from projects import SCHEMA_VERSION, ProjectError, ProjectStore  # noqa: E402
from settings import load_settings  # noqa: E402

PL = 'TheWorld.PersistentLevel.'
ID = '26a0a0b1-2626-4d0a-8e26-3c4d5e6f7a26'
MAP = 'URB_Bar'
SHA = 'a3ae5a73457c3c3f3e490fde9e1ad935f667c4843792fc8d140abc66878e09b5'
STREET = 6 * compiler.TILE          # (c): the lamp post and its spot, east along the south street
SPOT_COPY = [911.0, -1297.0, 300.0]  # (d): the dark corner by the wrecked sedan
POINT_COPY = [-1297.0, -800.0, 170.0]  # (e): beside the police sedans, the play area's darkest ground
DUMPSTER_COPY = [-1150.0, -880.0, 0.0]  # (e): the dumpster's copy, in the new point light's pool, clear of the cars
WARM = dict(color=[255, 176, 96], brightness=2.0)   # (b)


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--cache', default=settings.configured('cache'), help='the viewer cache (default: the cache setting)')
    args = a.parse_args()
    _, scene = compiler.find_export(args.cache, dict(source=dict(map=MAP, sha256=SHA, exporterVersion=18)))
    lights = {l['actor']: l for l in scene['lights'] if l['layer'] == 'base'}
    objects = {o['actor']: o for o in scene['objects'] if o['layer'] == 'base'}
    target = lambda name: dict(package=MAP, level='base', actor=PL + name)
    for name in ('SpotLight_3', 'PointLight_4', 'SpotLight_53', 'SpotLight_32', 'PointLight_15'):
        light = lights[PL + name]
        why = compiler.light_rule(light)
        assert why is None, (name, why)
    post, spot = objects[PL + 'XComLevelActor_37'], lights[PL + 'SpotLight_53']
    moved = lambda where: [where[0] + STREET, where[1], where[2]]
    overrides = [
        dict(target=target('SpotLight_3'), deleted=True),
        dict(target=target('PointLight_4'), location=list(lights[PL + 'PointLight_4']['location']),
             rotation=list(lights[PL + 'PointLight_4']['rotation']), light=dict(WARM)),
        dict(target=target('XComLevelActor_37'), location=moved(post['location']), rotation=list(post['rotation'])),
        dict(target=target('SpotLight_53'), location=moved(spot['location']), rotation=list(spot['rotation'])),
    ]
    dumpster = objects[PL + 'XComDestructibleActor_2']
    added = [
        dict(id='26a0a0b1-2626-4a26-9c26-0d1e2f3a4001', actor=PL + 'SpotLight_32_copy1', **{'from': target('SpotLight_32')},
             components=[lights[PL + 'SpotLight_32']['component']], location=SPOT_COPY,
             rotation=list(lights[PL + 'SpotLight_32']['rotation'])),
        dict(id='26a0a0b1-2626-4a26-9c26-0d1e2f3a4002', actor=PL + 'PointLight_15_copy2', **{'from': target('PointLight_15')},
             components=[lights[PL + 'PointLight_15']['component']], location=POINT_COPY,
             rotation=list(lights[PL + 'PointLight_15']['rotation'])),
        dict(id='26a0a0b1-2626-4a26-9c26-0d1e2f3a4003', actor=PL + 'XComDestructibleActor_2_copy3',
             **{'from': target('XComDestructibleActor_2')}, components=[dumpster['component']], location=DUMPSTER_COPY,
             rotation=[0, 0, 0]),
    ]
    overrides.sort(key=lambda r: r['target']['actor'])
    added.sort(key=lambda e: e['actor'])
    # As the editor names a project's output (web/project.js outputNames): 30 characters at most for the patch (T-09).
    stem = MAP[:12]
    ship = '%s_%s_%s' % (stem, 'Exp26Lights'[:compiler.NAME_LIMIT - len('patch_') - len(stem) - 6], ID[:4])
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=1, id=ID, name='EXP-26 lights', mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=SHA, exporterVersion=18),
               output=dict(shipAs=ship, patch='patch_' + ship.lower()), overrides=overrides, added=added,
               groups=[], areaLightBindings=[], nextSerial=len(added), view=dict(camera=[0, 2600, -3400], target=[-300, 0, -800]))
    spec, report = compiler.compile_project(doc, scene, enable=['light'])
    if not report['ok']:
        raise SystemExit('the project does not compile: %s' % report['errors'])
    # the document is compiled as it was made (schema 1, as build_outputs.py takes it) and saved at the schema the store
    # writes now; one the store refuses even so stops here, the generator being historical (its docstring)
    doc = dict(doc, schemaVersion=SCHEMA_VERSION)
    store = ProjectStore(load_settings()['projects'])
    try:
        current = store.load(ID)
        if current.get('created'):
            doc['created'] = current['created']
        expected = current['revision']
    except Exception:
        expected = 0
    try:
        saved = store.save(ID, doc, expected)
    except ProjectError as error:
        raise SystemExit('the project compiles but is not saved: this generator is historical (EXP-26, schema 1), and '
                         'the projects store refuses its document at schema %d: %s' % (SCHEMA_VERSION, error.message))
    print('saved %s (%s) revision %d in %s as %s: %s; %d warnings' % (
        doc['name'], ID, saved['revision'], store.path(ID), ship, report['counts'], len(report['warnings'])))
    for w in report['warnings']:
        print('  warning:', w.get('code'), w.get('message'))


if __name__ == '__main__':
    main()
