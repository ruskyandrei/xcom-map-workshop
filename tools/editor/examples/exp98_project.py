"""EXP-98 (game-likeness plan, C5a): URB_Bar with its height fog or its grade changed by the project's `atmosphere`, so
a hidden game run shows whether a Build's fog and grade reach the game.

Usage: exp98_project.py <out> [--look fog|grade|both] [--cache <cache>] [--game <install>] [--quick | --compile]

--look fog (the default): a thick red fog, thicker low down (density 0.6, height 600, falloff 1, the most it covers 0.95,
the colour away from the moon and toward it both red: some 40% of a near floor and 80% of the far map hidden at the
game's camera, by the editor's sums); grade: a green grade (Scene_Colorize 0.6, 1.4, 0.6 and the
map's blue lift in the shadows taken out); both: the two. The project goes to <out>/project.json and the build under
<out>/builds; the game and the cache are the settings' unless named (--game: an install folder, read only). Bar must
have been exported at version 43 or newer. --compile only compiles (the report beside the project); --quick (the
default) builds without baking the lighting: the atmosphere is the WorldInfo's settings and changes no baked light.

tools/editor/tests/build_outputs.py records the atmosphere lane with this project (its input bar-atmosphere)."""
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
PROJECT_ID = '98a70000-0000-4000-8000-000000098a70'
RED = [0.85, 0.08, 0.06, 1.0]
LOOKS = {
    'fog': dict(fog=dict(bEnabled=True, FogDensity=0.6, FogHeight=600.0, FogHeightFalloff=1.0, FogMaxOpacity=0.95,
                         StartDistance=0.0, OppositeLightColor=RED, OppositeLightBrightness=1.0,
                         LightInscatteringColor=RED, LightInscatteringBrightness=1.0)),
    'grade': dict(postProcess=dict(Scene_Colorize=[0.6, 1.4, 0.6], Scene_Shadows=[0.0, 0.0, 0.0])),
}
LOOKS['both'] = dict(LOOKS['fog'], **LOOKS['grade'])


def scene_of(cache, game):
    sha = hashlib.sha256(build.lwr_file(game, 'CookedPCConsole', MAP + '.upk').read_bytes()).hexdigest()
    _, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha, exporterVersion=43)))
    return sha, scene


def document(sha, scene, look):
    return dict(schema='xcom-map-workshop/project', schemaVersion=compiler.SCHEMA_VERSION, id=PROJECT_ID,
                name='Bar atmosphere', mode='edit', revision=1,
                source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
                output=dict(shipAs='URB_Bar_Atmos_98a7', patch='patch_urb_bar_atmos_98a7'),
                overrides=[], added=[], nextSerial=0, atmosphere=LOOKS[look])


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('out', type=Path)
    a.add_argument('--look', choices=sorted(LOOKS), default='fog')
    a.add_argument('--cache', type=Path, help='the export cache (default: the settings\')')
    a.add_argument('--game', type=Path, help='the install whose URB_Bar is built (default: the settings\')')
    mode = a.add_mutually_exclusive_group()
    mode.add_argument('--quick', action='store_true')
    mode.add_argument('--compile', action='store_true')
    args = a.parse_args(argv)
    s = settings_module.load_settings()
    game = args.game or settings_module.resolve_game(s['game'])[0]
    cache = args.cache or s['cache']
    sha, scene = scene_of(cache, game)
    doc = document(sha, scene, args.look)
    args.out.mkdir(parents=True, exist_ok=True)
    project = args.out / 'project.json'
    compiler.write_json(project, doc)
    t = time.time()
    spec, report = compiler.compile_project(doc, scene, library=compiler.Library(cache, game))
    compiler.write_json(args.out / 'compile-report.json', report)
    print('compiled in %.2f s: %d errors, %d left out, warnings %s, atmosphere %s' % (
        time.time() - t, report['counts']['errors'], len(report.get('leftOut') or []),
        sorted({w['code'] for w in report['warnings']}), report.get('atmosphere')))
    for e in report['errors'][:10] + (report.get('leftOut') or [])[:10]:
        print('  %s' % e['message'])
    if args.compile or spec is None:
        return 0 if spec else 1
    t = time.time()
    m = build.Build(build.BuildInputs(project, cache, args.out / 'builds', game, s['udk'], quick=True)).run()
    print('built in %.1f s: %s' % (time.time() - t, m.get('buildId')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
