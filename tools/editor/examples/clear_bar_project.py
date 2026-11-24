"""A cleared URB_Bar (Clear map plan, steps C6 and C9): every piece of the map deleted as the editor's Clear map deletes
them (all the base level's pieces but the landing's, the hidden ones and the sky backdrop), `cleared` set, and
optionally a size.

Usage: clear_bar_project.py <out> [--grid NX NY NZ] [--zones] [--keep-outside] [--keep-triggers]
                            [--parts PART ...] [--sound CUE|none] [--volume V] [--cache <cache>]
                            [--quick | --full | --compile]

The project goes to <out>/project.json and the build under <out>/builds; the game and the cache are the settings'.
Bar must have been opened once in the editor at export 21 or newer. --compile only compiles (the report beside the
project); --quick builds without baking the lighting; --full bakes it. --zones gives it two landing zones (ZONES): the
map's own landing moved four tiles east and turned to face west (its Skyranger, carried by the same move, stays in
the grid), and one added on the car park, facing north. --keep-outside is the Clear map window's "Keep the scenery
outside the play area": the pieces whose place is outside Bar's play area (here by the actor's place, where the page
goes by each part's box) are not deleted, and the project says `clearKeepsOutside`, so the Build keeps the lights,
smoke and stains out there too. Without --keep-triggers (the window's "Keep the map's triggers and scripts",
`clearKeepsTriggers`) the Build takes out Bar's two touch triggers (its rats) and turns their events off (F-159).
--parts clears only the parts named (pieces, lights, effects, triggers: the clear-by-parts plan), saved as schema 9's
`cleared` ({part: {}}, each part keeping the outside with --keep-outside); the pieces' delete records come only with
the pieces. Without it the project says `cleared: true`, every part, as a project of schema 1 to 8 does.
--sound gives the map another background sound (`backgroundSound`, schema 5: a cue of
tools/viewer/background_sounds.json, brought from its map, or none) and --volume its volume; Bar must then have been
opened at export 39 or newer. --cache exports from another cache than the settings' (a scratch one)."""
import argparse
import hashlib
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / 'tools' / 'editor'), str(REPO / 'tools' / 'viewer')]
import build  # noqa: E402
import compiler  # noqa: E402
import settings as settings_module  # noqa: E402

MAP = 'URB_Bar'
PROJECT_ID = 'c1ea2000-0000-4000-8000-00000000c1ea'
ZONES = [dict(id='c1ea-zone-1', location=[1103, -1681, 64], direction='west', kind='normal'),
         dict(id='c1ea-zone-2', location=[-1297, -1681, 80], direction='north', kind='normal')]


def scene_of(cache, game):
    sha = hashlib.sha256(build.lwr_file(game, 'CookedPCConsole', MAP + '.upk').read_bytes()).hexdigest()
    _, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha, exporterVersion=21)))
    return sha, scene


def outside(scene, o):
    """Whether the piece's place is outside the map's play area (its level volume, in the viewer's basis [x, up, y])."""
    b = scene['playableBounds']
    x, y = o['location'][:2]
    return x < b['min'][0] or x > b['max'][0] or y < b['min'][2] or y > b['max'][2]


def cleared_overrides(scene, keep_outside=False):
    """The delete records a Clear map makes: each base-level piece once, but the landing's, the hidden ones and the
    sky backdrop (which the page never deletes), and with `keep_outside` those outside the play area."""
    seen, out = set(), []
    for o in scene['objects']:
        if o['layer'] != 'base' or o.get('hidden') or o.get('environment') or compiler.is_landing(o) or o['actor'] in seen:
            continue
        if keep_outside and outside(scene, o):
            continue
        seen.add(o['actor'])
        out.append(dict(target=dict(package=o['sourcePackage'], level='base', actor=o['actor']), deleted=True))
    return sorted(out, key=lambda r: r['target']['actor'])


def document(sha, scene, grid=None, zones=None, added=(), keep_outside=False, keep_triggers=False, sound=None,
             parts=None):
    """The project: every part cleared (`cleared: true`), or with `parts` those alone (schema 9)."""
    newer = keep_triggers or sound is not None or parts is not None
    overrides = cleared_overrides(scene, keep_outside) if parts is None or 'pieces' in parts else []
    doc = dict(schema='xcom-map-workshop/project', schemaVersion=compiler.SCHEMA_VERSION if newer else 1, id=PROJECT_ID,
               name='Bar cleared', mode='edit',
               revision=1, source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
               output=dict(shipAs='URB_Bar_Cleared_c1ea', patch='patch_urb_bar_cleared_c1ea'),
               overrides=overrides, added=list(added), nextSerial=len(added),
               cleared={k: ({'keepOutside': True} if keep_outside else {}) for k in parts} if parts is not None else True)
    if keep_outside and parts is None:
        doc['clearKeepsOutside'] = True
    if keep_triggers:
        doc['clearKeepsTriggers'] = True
    if sound is not None:
        doc['backgroundSound'] = sound
    if grid:
        doc['stage'] = dict(grid=list(grid))
    if zones is not None:
        doc['landingZones'] = zones
    return doc


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('out', type=Path)
    a.add_argument('--grid', nargs=3, type=int, metavar=('NX', 'NY', 'NZ'))
    a.add_argument('--zones', action='store_true', help="two landing zones: the map's own moved and turned, one added")
    a.add_argument('--keep-outside', action='store_true', help='keep the scenery outside the play area')
    a.add_argument('--keep-triggers', action='store_true', help="keep the map's triggers and scripts")
    a.add_argument('--parts', nargs='+', choices=compiler.CLEAR_PARTS,
                   help='clear only these parts (schema 9); without it, every part')
    a.add_argument('--sound', help="the map's background sound: a cue's path, or none")
    a.add_argument('--volume', type=float, help="the background sound's volume (with --sound)")
    a.add_argument('--cache', type=Path, help="the viewer cache to read Bar's export from (default: the settings')")
    mode = a.add_mutually_exclusive_group()
    mode.add_argument('--quick', action='store_true')
    mode.add_argument('--full', action='store_true')
    mode.add_argument('--compile', action='store_true')
    args = a.parse_args(argv)
    if args.parts and args.keep_triggers:
        a.error('--keep-triggers is for a clear of every part: with --parts, leave out triggers')
    s = settings_module.load_settings()
    game = settings_module.resolve_game(s['game'])[0]
    cache = args.cache or s['cache']
    sha, scene = scene_of(cache, game)
    sound = None
    if args.sound:
        sound = dict(cue=None if args.sound.lower() == 'none' else args.sound,
                     **({'volume': args.volume} if args.volume is not None else {}))
    doc = document(sha, scene, args.grid, ZONES if args.zones else None, keep_outside=args.keep_outside,
                   keep_triggers=args.keep_triggers, sound=sound, parts=args.parts)
    args.out.mkdir(parents=True, exist_ok=True)
    project = args.out / 'project.json'
    compiler.write_json(project, doc)
    t = time.time()
    spec, report = compiler.compile_project(doc, scene, library=compiler.Library(cache, game))
    compiler.write_json(args.out / 'compile-report.json', report)
    print('compiled in %.2f s: %d deleted, %d errors, warnings %s' % (
        time.time() - t, report['counts']['deleted'], report['counts']['errors'],
        sorted({w['code'] for w in report['warnings']})))
    for e in report['errors'][:10]:
        print('  error:', e['message'])
    for e in report['leftOut'][:10]:
        print('  left out:', e['message'])
    if args.compile or spec is None:
        return 0 if spec else 1
    t = time.time()
    m = build.Build(build.BuildInputs(project, cache, args.out / 'builds', game, s['udk'],
                                      quick=not args.full)).run()
    print('built in %.1f s: %s' % (time.time() - t, m.get('buildId')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
