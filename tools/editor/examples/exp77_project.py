"""EXP-77's project: ground shapes made from numbers (custom geometry plan, stage M6, run F), on URB_Bar.

As the editor's Ground tool makes them (the piece at the shape's corner, on tile lines, standing on the ground there):
- in the parking lot's middle (floor 0), in Asphalt (URB_Bar's grassPlanes.AsphaltPlaneFlat, XComLevelActor_131):
  - Ramp: x -1728 to -1440, y -960 to -864, rising east to 96 (about 18 degrees: sloped tiles, no cover on it);
  - Block: x -1440 to -1248, y -960 to -768, 96 high, the ramp's high edge on its west side;
  - Patch: x -1152 to -864, y -960 to -672, its top 1 over the lot;
  - Cover block: x -1056 to -960, y -864 to -768, 64 high, standing on the patch (z 1);
- in the lot, in Rock (CLrgScout_ForestTrench's Rock_E piece, XComLevelActor_34): Rock, x -768 to -576, y -960 to -864,
  128 high, seed 7 (M6 item 6);
- one block of each ground look (tools/bake/ground_looks.json), 64 high, a tile square: outdoors in a row in the lot
  (y -1248 to -1152, from x -1440 every two tiles) and indoors in the bar's kitchen (floor 16, from x -1536, y 768).
A look whose donor is in another map is copied from that map (it must have been opened in the editor).
Game tiles count from the map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

Usage: exp77_project.py --store <projects folder> --builds <builds folder> [--build] [--quick]

The project is saved in the store given (a test server's scratch store: Play in game on that server, started with
--dry-play, then stages its build into the lab copy). The game and the cache are the settings'; URB_Bar must have been
opened in the editor."""
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

MAP, PL = 'URB_Bar', 'TheWorld.PersistentLevel.'
PROJECT = ('00000000-0000-4000-8000-0000000e7700', 'EXP-77 ground')
LOOKS = json.loads((HERE.parents[1] / 'bake' / 'ground_looks.json').read_text(encoding='utf-8'))['looks']
ASPHALT = LOOKS[0]
SHAPES = [
    # (label, look, location, shape numbers)
    ('Ramp', ASPHALT, [-1728.0, -960.0, 0.0], dict(shape='ramp', x0=0.0, x1=288.0, y0=0.0, y1=96.0, height=96.0)),
    ('Block', ASPHALT, [-1440.0, -960.0, 0.0], dict(shape='block', x0=0.0, x1=192.0, y0=0.0, y1=192.0, height=96.0)),
    ('Patch', ASPHALT, [-1152.0, -960.0, 0.0], dict(shape='patch', x0=0.0, x1=288.0, y0=0.0, y1=288.0)),
    ('CoverBlock', ASPHALT, [-1056.0, -864.0, 1.0], dict(shape='block', x0=0.0, x1=96.0, y0=0.0, y1=96.0, height=64.0)),
    ('Rock', next(l for l in LOOKS if l['id'] == 'rock'), [-768.0, -960.0, 0.0],
     dict(shape='rock', x0=0.0, x1=192.0, y0=0.0, y1=96.0, height=128.0, seed=7, look='rock')),
]
INDOORS = [(-1536.0, 768.0), (-1344.0, 768.0), (-1536.0, 960.0), (-1344.0, 960.0)]
for k, look in enumerate(LOOKS):
    named = {} if k == 0 else dict(look=look['id'])
    SHAPES.append(('Out_' + look['id'], look, [-1440.0 + 192.0 * k, -1248.0, 0.0],
                   dict(shape='block', x0=0.0, x1=96.0, y0=0.0, y1=96.0, height=64.0, **named)))
    if k < len(INDOORS):
        SHAPES.append(('In_' + look['id'], look, [INDOORS[k][0], INDOORS[k][1], 16.0],
                       dict(shape='block', x0=0.0, x1=96.0, y0=0.0, y1=96.0, height=64.0, **named)))


def donor_component(s, game, package, actor, scene):
    """The donor's component path: from this map's export, or the export of the map it is in."""
    if package.casefold() != MAP.casefold():
        base = build.lwr_file(game, 'CookedPCConsole', package + '.upk')
        _, scene = compiler.find_export(s['cache'], dict(source=dict(map=package, sha256=build.sha256(base),
                                                                     exporterVersion=build.EXPORT_MINIMUM)),
                                        minimum=build.EXPORT_MINIMUM)
    found = [o for o in scene['objects'] if o.get('layer') == 'base' and o['actor'] == PL + actor]
    if not found:
        raise SystemExit('%s has no %s in its export' % (package, actor))
    return found[0]['component']


def added(s, game, scene):
    out = []
    for k, (label, look, location, numbers) in enumerate(SHAPES):
        comp = donor_component(s, game, look['package'], look['actor'], scene)
        out.append(dict(id='00000000-0000-4000-8000-0000000e77%02d' % (k + 1), actor=PL + '%s_copy%d' % (look['actor'], k + 1),
                        **{'from': dict(package=look['package'], level='base', actor=PL + look['actor'])}, components=[comp],
                        location=location, rotation=[0, 0, 0], prefab=None, partner=None,
                        generated=dict(kind='ground', version=1, ground=numbers)))
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
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=4, id=project_id, name=name, mode='edit',
               source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=output, overrides=[], added=pieces, groups=[], buildings=[], nextSerial=len(pieces) + 1,
               view=dict(camera=[-1100, 900, -1500], target=[-1300, 0, -900]))
    if current and current.get('created'):
        doc['created'] = current['created']
    spec, report = compiler.compile_project(doc, scene, (), compiler.Library(s['cache'], game), ())
    print('compile ok' if report['ok'] else 'COMPILE ERRORS', [(e['code'], e['message'][:240]) for e in report['errors']])
    print('left out', [(e['code'], e['message'][:240]) for e in report['leftOut']])
    print('warnings', json.dumps([(w['code'], w['message'][:240]) for w in report['warnings']], indent=1))
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
        m = build.Build(store.path(project_id), s['cache'], args.builds, game, s['udk'], quick=args.quick).run()
    except build.BuildError as error:
        raise SystemExit('build failed: %s' % error)
    print(json.dumps({k: m.get(k) for k in ('buildId', 'variant', 'quick', 'seconds')}))


if __name__ == '__main__':
    main()
