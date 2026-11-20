"""EXP-78's project: the farm's earth mounds replaced by ground shapes made from numbers, and a hole in the ground half
covered by a patch (custom geometry plan, stage M6, run F's second part), on CsmallScout_Farm.

The farm's crash site (research/experiments/EXP-78-farm-ground.md): the crater floor is at -128, the field west of
x 480 at 0, and `XComLevelActor_28` (TornEarth.Meshes.SmallscoutRamps, ten collision hulls) is the earth the crash threw
up round the UFO: a strip along x 480 to 960 at y -2880 to -2400 with its top at about 3, and a mound south of the UFO
(x 1340 to 2510, y -3280 to -2880) up to about 100. The project:
- deletes `XComLevelActor_28`;
- in its west strip's place, as the editor's Ground tool makes them (on tile lines, standing on the crater floor), in
  Dirt (URB_MilitaryAmmo's StaticMeshActor_67, copied from that map):
  - Mound: a block, x 480 to 864, y -2880 to -2496, 128 high (its top at 0, level with the field west of it);
  - Ramp: x 864 to 1152, y -2784 to -2592, rising west from the crater floor to the block's top (128 over three
    tiles, about 24 degrees: sloped tiles, no cover on it);
- deletes the ground plane `XComLevelActor_145` (grassPlanes.AsphaltPlaneFlat, x 1439 to 2399, y -480 to 480, at
  -128; nothing else gives its tiles a floor), leaving a hole, and covers its east half with a patch in Grass
  (URB_CommercialStreet's XComLevelActor_129): x 1920 to 2400, y -480 to 480, its top 1 over -128.
Game tiles count from the map's corner (-2497, -3553, -129): tile centres at x -2449 + 96 i, y -3505 + 96 j.

Usage: exp78_project.py --store <projects folder> --builds <builds folder> [--build] [--quick]

The project is saved in the store given (a test server's scratch store: Play in game on that server, started with
--dry-play, then stages its build into the lab copy). The game and the cache are the settings'; CsmallScout_Farm,
URB_MilitaryAmmo and URB_CommercialStreet must have been opened in the editor."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
import build  # noqa: E402
import compiler  # noqa: E402
import outputnames  # noqa: E402
import projects  # noqa: E402
import settings as settings_module  # noqa: E402

MAP, PL = 'CsmallScout_Farm', 'TheWorld.PersistentLevel.'
PROJECT = ('00000000-0000-4000-8000-0000000e7800', 'EXP-78 farm ground')
LOOKS = {look['id']: look for look in
         json.loads((HERE.parents[1] / 'bake' / 'ground_looks.json').read_text(encoding='utf-8'))['looks']}
DELETED = ['XComLevelActor_28', 'XComLevelActor_145']
SHAPES = [
    # (label, look, location, yaw, shape numbers)
    ('Mound', 'dirt', [480.0, -2880.0, -128.0], 0,
     dict(shape='block', x0=0.0, x1=384.0, y0=0.0, y1=384.0, height=128.0, look='dirt')),
    ('Ramp', 'dirt', [1152.0, -2592.0, -128.0], 32768,
     dict(shape='ramp', x0=0.0, x1=288.0, y0=0.0, y1=192.0, height=128.0, look='dirt')),
    ('Patch', 'grass', [1920.0, -480.0, -128.0], 0,
     dict(shape='patch', x0=0.0, x1=480.0, y0=0.0, y1=960.0, look='grass')),
]


def donor(s, game, package, actor, scene):
    """The donor's export object: from this map's export, or the export of the map it is in."""
    if package.casefold() != MAP.casefold():
        base = build.lwr_file(game, 'CookedPCConsole', package + '.upk')
        _, scene = compiler.find_export(s['cache'], dict(source=dict(map=package, sha256=build.sha256(base),
                                                                     exporterVersion=build.EXPORT_MINIMUM)),
                                        minimum=build.EXPORT_MINIMUM)
    found = [o for o in scene['objects'] if o.get('layer') == 'base' and o['actor'] == PL + actor]
    if not found:
        raise SystemExit('%s has no %s in its export' % (package, actor))
    return found[0]


def added(s, game, scene):
    out = []
    for k, (label, look_id, location, yaw, numbers) in enumerate(SHAPES):
        look = LOOKS[look_id]
        obj = donor(s, game, look['package'], look['actor'], scene)
        out.append(dict(id='00000000-0000-4000-8000-0000000e78%02d' % (k + 1), actor=PL + '%s_copy%d' % (look['actor'], k + 1),
                        **{'from': dict(package=look['package'], level='base', actor=PL + look['actor'])},
                        components=[obj['component']], location=location, rotation=[0, yaw, 0], prefab=None,
                        partner=None, generated=dict(kind='ground', version=1, ground=numbers)))
    return out


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('--store', type=Path, required=True, help='the projects folder to save it in (a scratch one)')
    a.add_argument('--builds', type=Path, required=True, help='the builds folder to build it into (a scratch one)')
    a.add_argument('--build', action='store_true')
    a.add_argument('--quick', action='store_true', help='with --build: without baking')
    args = a.parse_args()
    s = settings_module.load_settings()
    game = settings_module.resolve_game(s['game'])[0]
    if game is None:
        raise SystemExit('set the game install first')
    base = build.lwr_file(game, 'CookedPCConsole', MAP + '.upk')
    sha = build.sha256(base)
    export, scene = compiler.find_export(s['cache'], dict(source=dict(map=MAP, sha256=sha, exporterVersion=build.EXPORT_MINIMUM)),
                                         minimum=build.EXPORT_MINIMUM)
    print('base map %s (SHA-256 %s), export %s' % (base.name, sha[:12], export.parent.name))
    store = projects.ProjectStore(args.store)
    project_id, name = PROJECT
    try:
        current = store.load(project_id)
    except projects.ProjectError:
        current = None
    if current and outputnames.valid_output(current.get('output')):
        output = current['output']
    else:
        claims = outputnames.Claims(store.root, str(args.builds), [game])
        output = outputnames.allocate(name, claims.taken, outputnames.base_streams(game, MAP))
        output.pop('reason', None)
    pieces = added(s, game, scene)
    overrides = [dict(target=dict(package=MAP, level='base', actor=PL + n), deleted=True) for n in DELETED]
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=4, id=project_id, name=name, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=overrides, added=pieces, groups=[], buildings=[], nextSerial=len(pieces) + 1,
               view=dict(camera=[600, -1200, 1400], target=[900, -2000, -100]))
    if current and current.get('created'):
        doc['created'] = current['created']
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
    print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
    print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
    print('notes', sorted({n['code'] for n in report['notes']}))
    _, native = compiler.native_split(compiler.stream_only(spec))
    names = dict(zip([p['actor'].split('.')[-1] for p in pieces], [x[0] for x in SHAPES]))
    print('boxes', [(names.get(c['label'], c['label']), [round(v, 1) for v in c['box']]) for c in native['copies']])
    if not report['ok'] or report['leftOut']:
        raise SystemExit(1)
    saved = store.save(project_id, doc, current['revision'] if current else 0)
    print('saved %s as revision %d (%s): builds as %s' % (name, saved['revision'], saved['file'], output['shipAs']))
    if not args.build:
        return
    try:
        m = build.Build(build.BuildInputs(store.path(project_id), s['cache'], args.builds, game, s['udk'],
                                          quick=args.quick)).run()
    except build.BuildError as error:
        raise SystemExit('build failed: %s' % error)
    print(json.dumps({k: m.get(k) for k in ('buildId', 'variant', 'quick', 'seconds')}))


if __name__ == '__main__':
    main()
