"""EXP-99 (game-likeness plan, T-S3): URB_Bar made day by the project's time of day (`sun`), built without baking, so
a game run shows the sun's new colour and brightness, the sky light on the soldiers, the records' time of day, and with
a turned sun how wrong the old shadows are.

Usage: exp99_project.py <out> [--time HH:MM] [--keep-direction] [--cache <cache>] [--game <install>] [--quick | --compile]

The record is the one the Map settings window's time bar makes (the page's own rules, tools/viewer/web/sun_rules.js,
run by node: the curve made the map's own, the dial where it puts the light as the map has it, the bar moved to
--time, 13:00 by default), with the fog and colour of the hour beside it where the export has the map's atmosphere
(export 43). At noon the sun stands at 56 degrees where Bar's moon stands at 81: the direction changes.
--keep-direction gives the light the map's own rotation instead (only its colour, brightness, the sky light and the time
change), as a record set by hand may. The project goes to <out>/project.json and the build under <out>/builds; the game
and the cache are the settings' unless named (--game: an install folder, read only). --compile only compiles (the
report beside the project); --quick (the default) builds without baking the lighting.

tools/editor/tests/build_outputs.py records the sun lane with this project (its input bar-sun)."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / 'tools' / 'editor'), str(REPO / 'tools' / 'viewer')]
import build  # noqa: E402
import compiler  # noqa: E402
import settings as settings_module  # noqa: E402
import sun_curve  # noqa: E402

MAP = 'URB_Bar'
PROJECT_ID = '99a10000-0000-4000-8000-000000099a10'
RULES = REPO / 'tools' / 'viewer' / 'web' / 'sun_rules.js'
# the page's own steps for a bar moved to a time on a map (sun_settings.js and sun_wiring.js through sun_rules.js)
SCRIPT = """
import { bestTime, mapCurve, ownSun, shownTime, timeSet } from %s;
let text = '';
process.stdin.on('data', chunk => { text += chunk; });
process.stdin.on('end', () => {
  const { scene, curve, time } = JSON.parse(text);
  const own = ownSun(scene);
  const mine = mapCurve(curve, own, bestTime(curve, own));
  const at = shownTime(null, own, curve);
  const set = timeSet({ curve: mine, own, time, heading: at.heading });
  process.stdout.write(JSON.stringify({ own, ...set }));
});
"""


def scene_of(cache, game):
    sha = hashlib.sha256(build.lwr_file(game, 'CookedPCConsole', MAP + '.upk').read_bytes()).hexdigest()
    _, scene = compiler.find_export(cache, dict(source=dict(map=MAP, sha256=sha, exporterVersion=43)))
    return sha, scene


def bar_record(scene, hour, keep_direction=False):
    """(the project's `sun`, its `atmosphere` or None) as the time bar makes them at `hour` on the map of `scene`."""
    node = shutil.which('node')
    if not node:
        raise SystemExit('exp99_project.py runs the page\'s rules with node, which is not on the path')
    given = dict(scene=dict(lights=scene.get('lights') or [], atmosphere=scene.get('atmosphere')), curve=sun_curve.load(),
                 time=hour)
    out = subprocess.run([node, '--input-type=module', '-e', SCRIPT % json.dumps(RULES.as_uri())],
                         input=json.dumps(given), capture_output=True, text=True, encoding='utf-8', check=True)
    made = json.loads(out.stdout)
    sun = made['sun']
    if keep_direction:
        sun['light']['rotation'] = list(made['own']['rotation'])
    return sun, made['atmosphere']


def document(sha, scene, hour, keep_direction):
    sun, atmosphere = bar_record(scene, hour, keep_direction)
    return dict(schema='xcom-map-workshop/project', schemaVersion=compiler.SCHEMA_VERSION, id=PROJECT_ID,
                name='Bar by day', mode='edit', revision=1,
                source=dict(map=MAP, package=MAP + '.upk', sha256=sha, exporterVersion=scene['exporterVersion']),
                output=dict(shipAs='URB_Bar_Day_99a1', patch='patch_urb_bar_day_99a1'),
                overrides=[], added=[], nextSerial=0, sun=sun, **({'atmosphere': atmosphere} if atmosphere else {}))


def hour_of(text):
    h, m = text.split(':')
    return int(h) + int(m) / 60


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('out', type=Path)
    a.add_argument('--time', default='13:00', help='the bar\'s time, HH:MM (default %(default)s)')
    a.add_argument('--keep-direction', action='store_true', help='the light keeps the map\'s own rotation')
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
    doc = document(sha, scene, hour_of(args.time), args.keep_direction)
    args.out.mkdir(parents=True, exist_ok=True)
    project = args.out / 'project.json'
    compiler.write_json(project, doc)
    t = time.time()
    spec, report = compiler.compile_project(doc, scene, library=compiler.Library(cache, game))
    compiler.write_json(args.out / 'compile-report.json', report)
    print('compiled in %.2f s: %d errors, %d left out, warnings %s, sun %s' % (
        time.time() - t, report['counts']['errors'], len(report.get('leftOut') or []),
        sorted({w['code'] for w in report['warnings']}), report.get('sun')))
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
