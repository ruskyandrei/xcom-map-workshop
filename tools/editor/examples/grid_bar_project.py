"""URB_Bar on a larger grid and nothing else: a project whose only edit is the map's size (Map grid).

Usage: grid_bar_project.py <out> [--grid NX NY [NZ]] [--quick | --full | --compile]

The project goes to <out>/project.json and the build under <out>/builds; the game and the cache are the settings'.
Bar must have been opened once in the editor. --grid is the size in tiles across and deep (and levels; default
GRID: four tiles more than Bar's own each way across, its own levels). --compile only compiles (the report beside the
project); --quick builds without baking the lighting; --full bakes it.

A grown grid is the one edit that sends a baked Build to the relight alone, on a copy of the map the growing writer
names (build.py's named_base): tools/editor/tests/build_outputs.py records that route with this project (its input
bar-grid). A full build of it stops in the relight today (KNOWN-BUGS.md KB-2, T-37); --quick builds."""
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
PROJECT_ID = '9a1d0000-0000-4000-8000-0000009a1d00'
GRID = [56, 43]     # URB_Bar's own grid is 52 by 39 tiles, 12 levels


def scene_of(cache, game):
    sha = hashlib.sha256(build.lwr_file(game, 'CookedPCConsole', MAP + '.upk').read_bytes()).hexdigest()
    _, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha)))
    return sha, scene


def document(sha, scene, grid):
    return dict(schema='xcom-map-workshop/project', schemaVersion=4, id=PROJECT_ID, name='Bar grown', mode='edit',
                revision=1, source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
                output=dict(shipAs='URB_Bar_Grown_9a1d', patch='patch_urb_bar_grown_9a1d'),
                overrides=[], added=[], nextSerial=0, stage=dict(grid=list(grid)))


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('out', type=Path)
    a.add_argument('--grid', nargs='+', type=int, default=GRID, metavar='N',
                   help='tiles across, tiles deep and optionally levels (default %s)' % ' '.join(map(str, GRID)))
    mode = a.add_mutually_exclusive_group()
    mode.add_argument('--quick', action='store_true')
    mode.add_argument('--full', action='store_true')
    mode.add_argument('--compile', action='store_true')
    args = a.parse_args(argv)
    if len(args.grid) not in (2, 3):
        a.error('--grid takes two or three numbers')
    s = settings_module.load_settings()
    game = settings_module.resolve_game(s['game'])[0]
    sha, scene = scene_of(s['cache'], game)
    doc = document(sha, scene, args.grid)
    args.out.mkdir(parents=True, exist_ok=True)
    project = args.out / 'project.json'
    compiler.write_json(project, doc)
    t = time.time()
    spec, report = compiler.compile_project(doc, scene, library=compiler.Library(s['cache'], game))
    compiler.write_json(args.out / 'compile-report.json', report)
    print('compiled in %.2f s: %d errors, %d left out, warnings %s' % (
        time.time() - t, report['counts']['errors'], len(report.get('leftOut') or []),
        sorted({w['code'] for w in report['warnings']})))
    for e in report['errors'][:10] + (report.get('leftOut') or [])[:10]:
        print('  %s' % e['message'])
    if args.compile or spec is None:
        return 0 if spec else 1
    t = time.time()
    m = build.Build(build.BuildInputs(project, s['cache'], args.out / 'builds', game, s['udk'],
                                      quick=not args.full)).run()
    print('built in %.1f s: %s' % (time.time() - t, m.get('buildId')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
