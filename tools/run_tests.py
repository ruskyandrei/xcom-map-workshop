"""Runs the repository's offline test suites and says, at once, which tests failed and why.

Each Python suite (tools/<suite>/tests, test_*.py) runs in its own process with unittest's verbose output, and the
node tests (tools/viewer/tests/*_test.mjs) one file each. The whole output of every suite is kept in a log folder,
and every failure and error is printed with its traceback when its suite ends, so a failure in a long suite (bake
takes about seven minutes, every suite together about ten) needs no second run to be found.

A selection that runs nothing fails: -k matching no test (no file, for node), or node missing. Skipped tests are
counted by reason under their suite, so a run on a computer with no game install says how much it left out.

  python -B tools/run_tests.py                     every suite: viewer, editor, upk, bake, lab, release, repo, node
  python -B tools/run_tests.py viewer editor       only these
  python -B tools/run_tests.py bake -k shell       only the tests whose names hold "shell" (unittest's -k)
  python -B tools/run_tests.py bake -k shell -k relight   the tests whose names hold either
  python -B tools/run_tests.py --log <folder>      where the logs go (default .scratch/tests/<date-time>)
  python -B tools/run_tests.py upk --install       with the checks over every map of the install too
  python -B tools/run_tests.py editor --times      and then the twenty slowest tests and classes of each suite
  python -B tools/run_tests.py --times --log <folder>   the slowest of logs already there, running nothing

The checks over every map of the install (tools/upk/tests/test_game_grid.py: two minutes, most of it opening the maps)
run when every suite runs, as the release does, or with --install; they skip otherwise (XCOM_INSTALL_TESTS is how
the suites are told).

Each line of a log starts with two times in seconds since its suite started, `[begun ended] `: when the line's first
character came and when its end did. unittest writes a test's name when the test starts and its verdict when it
ends, so the two times of a test's line are its start and end, and the gap before a class's first test is the class's
set-up (setUpClass, and the tearDownClass of the class before). --times reads them; the screen shows no times. With
--log naming a folder that already holds logs, --times reads those (the suites named, else every log there) and runs
nothing.

--help lists every environment variable the tests and the tools read (ENVIRONMENT below), what each does and what
skips without it.

Exit status 0 when everything passed, 1 when anything failed or a suite could not run. The browser smoke
(tools/viewer/tests/browser_smoke.py) needs a test server and is not run here.
"""
import argparse
from collections import Counter, namedtuple
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import textwrap
import time

REPO = Path(__file__).resolve().parents[1]
PYTHON_SUITES = ('viewer', 'editor', 'upk', 'bake', 'lab', 'release', 'repo')
SUITES = PYTHON_SUITES + ('node',)
HEADER = re.compile(r'^(FAIL|ERROR): (\S+) \((\S+)\)')
SUMMARY = re.compile(r'^Ran (\d+) tests? in ([\d.]+)s$')
SKIPPED = re.compile(r" \.\.\. skipped '(.*)'$")
STAMP = re.compile(r'^\[ *(\d+\.\d+) +(\d+\.\d+)\] ')
# a test's line in unittest's verbose output: name (module.Class.name) [... verdict]; a docstring's first line, when
# the test has one, comes on the next line before the verdict
TEST = re.compile(r'^(\w+) \((\w[\w.]*\.[\w.]*)\)(?: \.\.\. (.*))?$')
VERDICT = re.compile(r"(?:^|\.\.\. )(ok|FAIL|ERROR|skipped '.*'|skipped|expected failure|unexpected success)$")
NODE_FILE = re.compile(r'^== (\S+) \(exit -?\d+\)$')
SLOWEST = 20

# Every environment variable the tests and the tools read, in groups, as --help prints them: a Var is (its name, what
# it does, what happens without it); a Package is (its name, the install's file it stands for, the tests that read
# it). tools/repo/tests/test_run_tests.py checks that every XCOM_ name the tracked files under tools/ use is here,
# that each here is used, and that the README names no other.
Var = namedtuple('Var', 'name does without')
Package = namedtuple('Package', 'name file readers')
ENVIRONMENT = (
    ('The folders the tests read', (
        Var('XCOM_MAP_WORKSHOP_SETTINGS',
            'The settings file read in place of <Documents>\\XCOM Map Workshop\\settings.json (tools/viewer/settings.py). '
            'It holds every folder the tests and the tools take: the game install, the cache, the projects, the lab. '
            "The browser checks' servers, the release's smoke test and build_outputs.py's Builds are started with it "
            'naming a scratch file.',
            'the settings file in Documents. With neither, the tests that read the game skip, each saying what it lacks.'),
        Var('XCOM_COOKED',
            "A CookedPCConsole folder read in place of the configured install's by the tests that read the install's "
            'maps from it: they take them through tools/lab/labpaths.py (its install_map, test_file and lwr_cooked), '
            "and it is the default of each XCOM_<MAP>_UPK below. Naming another install's folder (plain Enemy "
            "Within's, say) points those tests at it; a test whose package is not there skips, saying where it looked. "
            "The tests that read the game folder as a whole (its config files, its script package) take the settings' "
            'game folder, or XCOM_GAME where it names them.',
            "the configured LWR install's CookedPCConsole (the lwr setting). With neither, those tests skip."),
        Var('XCOM_GAME',
            "A game folder read in place of the configured install's by test_game_grid.py (the upk suite: every map "
            "the editor lists, on a plain Enemy Within install, say) and test_patchtool_record.py (the editor suite: "
            'Set-ShipConfig on copies of its two config files).',
            'the configured install. With none, those tests skip.'),
        Var('XCOM_VIEWER_CACHE',
            "The viewer cache read in place of the cache setting's folder by test_compiler.py: its tests on the export "
            "of URB_Bar they pin by its SHA-256, and on the library of other maps' pieces.",
            "the cache setting's folder. Without the pinned export there (or a library index this version reads), those "
            'tests skip.'),
    )),
    ('Longer checks, off unless set', (
        Var('XCOM_INSTALL_TESTS',
            'Runs the checks over every map of the install (tools/upk/tests/test_game_grid.py, about two minutes). This '
            'runner sets it when every suite runs, as the release does, or with --install.',
            'those checks skip.'),
        Var('XCOM_TRANSPLANT_RING',
            "Set to 1: test_transplant.py runs its oracle over every Firaxis-cooked base map, not three pairs of maps.",
            'that test skips; the three pairs run.'),
    )),
    ('One package of the install each: the file at a path of its own, in place of the one in the folder XCOM_COOKED '
     "names or the configured install's (tools/lab/labpaths.py test_file). The tests that read it skip when the "
     'file is not there.', (
        Package('XCOM_BAR_UPK', 'URB_Bar.upk', 'most of the bake suite\'s tests of a map, test_package_edit.py, '
                'test_package_grow.py, test_manager.py'),
        Package('XCOM_BATTLESHIP_UPK', 'CBattleship_01.upk', 'test_native_lights.py'),
        Package('XCOM_BLANK_UPK', 'CB2_MP_Blank.upk', 'test_native_copy.py'),
        Package('XCOM_BOMB_STREAM_UPK', 'URB_Slaughterhouse_Stream.upk', 'test_stream_copy.py'),
        Package('XCOM_CAPTURE_STREAM_UPK', 'URB_PoliceStation_CNH.upk', 'test_stream_copy.py'),
        Package('XCOM_DEMOLITION_UPK', 'URB_Demolition_EWI.upk', 'test_native_copy.py'),
        Package('XCOM_ENTRANCE_UPK', 'CIN_TP05A_EnteringAlienBase.upk', 'test_intro_copy.py'),
        Package('XCOM_FARM_UPK', 'CsmallScout_Farm.upk', 'test_native_lights.py'),
        Package('XCOM_FORESTTRENCH_UPK', 'CLrgScout_ForestTrench.upk', 'test_light_factory.py'),
        Package('XCOM_FURIES_UPK', 'DLC2_3_Furies.upk', 'test_package_grow.py'),
        Package('XCOM_HIGHWAYFALLEN_UPK', 'URB_HighwayFallen.upk', 'test_native_flags.py'),
        Package('XCOM_INTRO_UPK', 'CIN_DropshipIntros.upk', 'test_intro_copy.py, test_manager.py'),
        Package('XCOM_LOWFRIENDS_UPK', 'DLC1_1_LowFriends.upk', 'test_shadowmaps.py'),
        Package('XCOM_MAP_IMAGES_UPK', 'UILibrary_MapImages_SF.upk', 'test_map_frame.py'),
        Package('XCOM_OVERPASS_UPK', 'URB_StreetOverpass.upk', 'test_fixture.py'),
        Package('XCOM_PATCH_BAR_UPK', 'patch_bar.upk', 'test_stream_copy.py'),
        Package('XCOM_POLICE_PATCH_UPK', 'patch_policestation.upk', 'test_cover_blocks.py'),
        Package('XCOM_POLICE_UPK', 'URB_PoliceStation.upk', 'test_cover_blocks.py, test_gen_mesh.py, '
                'test_light_factory.py, test_native_copy.py, test_streams.py'),
        Package('XCOM_SHADER_CACHE_UPK', 'RefShaderCache-PC-D3D-SM3.upk', 'test_sm3.py, test_shader_cache.py'),
        Package('XCOM_STONEWALL_UPK', 'CLrgScout_Stonewall.upk', 'test_native_copy.py'),
        Package('XCOM_TEMPLE_UPK', 'TempleShip.upk', 'test_light_factory.py, test_native_lights.py'),
        Package('XCOM_TRUCKSTOP_STREAM_UPK', 'URB_TruckStop_Stream.upk', 'test_light_factory.py, test_map_frame.py, '
                'test_build.py'),
        Package('XCOM_TRUCKSTOP_UPK', 'URB_TruckStop_EWI.upk', 'test_light_factory.py'),
    )),
    ('Set by the tools for what they start, not by hand', (
        Var('XCOM_UNPACKED',
            'The folder where tools/upk/decomp.py keeps the decoded images of the maps a Build opens, read and written: '
            'the Build sets it to its work folder, so its processes decode each map once (test_faster_bake.py and '
            'build_outputs.py set it too).',
            'nothing is kept on disk: each process decodes the maps it opens again.'),
        Var('XCOM_UNPACKED_KEEP',
            "A folder of kept decoded images of the install's maps, which decomp.py reads (and writes only in its keep "
            'step), so a later Build opens them without decoding; the Build sets it.',
            'nothing is read from it.'),
        Var('XCOM_WORKSHOP_TEST_FOLDER',
            'The test folder tools/viewer/prefab_tests.py hands to the PowerShell it starts to look for a process still '
            'working in it.',
            'not set by hand: the PowerShell finds nothing.'),
    )),
    ("The lab's hidden game runs (tools/lab/hidden_game.py, which sets the stand-in input's own)", (
        Var('XCOM_HIDDEN_SOUND',
            "Set to 1: a hidden run (tools/lab/GameRemote.cs) leaves the game's sound on.",
            'the game is muted in Windows while the run lasts.'),
        Var('XCOM_STAND_IN_INPUT',
            'Set to always: the stand-in input (tools/lab/StandInInput.c, beside XComEW.exe for a run) gives the game '
            'stand-ins for the mouse and keyboard even where Windows has them (hidden_game.py\'s option, and '
            'test_hidden_game.py).',
            'stand-ins only where Windows has no mouse or keyboard.'),
        Var('XCOM_STAND_IN_INPUT_LOG',
            'A file the stand-in input appends a line to for each device the game asks for and what it got (a run\'s '
            'folder holds it).',
            'no log.'),
        Var('XCOM_STAND_IN_INPUT_TRACE',
            'Set to 1: every call on a stand-in goes into that log too.',
            'the devices alone are logged.'),
        Var('XCOM_STAND_IN_CRASH_LOG',
            "Set to 1: the run's first faults go into that log too (thread, code, module and offset, the modules on "
            "that thread's stack).",
            'no faults are logged.'),
        Var('XCOM_STAND_IN_CHECK_FAULT',
            'Set to 1 by test_hidden_game.py: the stand-in check (tools/lab/tests/StandInInputCheck.cs) faults on '
            'purpose, for the crash log to name.',
            'it does not fault.'),
    )),
)


def environment_names():
    """Every variable ENVIRONMENT lists."""
    return [entry.name for _, entries in ENVIRONMENT for entry in entries]


def environment_help(width=116):
    """ENVIRONMENT as --help prints it."""
    def wrap(text, first, rest):
        return textwrap.wrap(text, width, initial_indent=first, subsequent_indent=rest, break_on_hyphens=False)
    out = ['environment variables (every one the tests and the tools read):']
    for heading, entries in ENVIRONMENT:
        out += [''] + wrap(heading, '  ', '  ')
        for e in entries:
            if isinstance(e, Package):
                out += wrap('%-26s %s: %s' % (e.name, e.file, e.readers), '    ', ' ' * 31)
                continue
            out += ['    ' + e.name] + wrap(e.does, ' ' * 8, ' ' * 8) + wrap('Without it: ' + e.without, ' ' * 8, ' ' * 8)
    return '\n'.join(out)


def stamped(output):
    """[(begun, ended, line)] of a log's lines: their two times, or None and None for a line with no stamp."""
    out = []
    for line in output.splitlines():
        m = STAMP.match(line)
        out.append((float(m.group(1)), float(m.group(2)), line[m.end():]) if m else (None, None, line))
    return out


def unstamped(output):
    """A suite's output without the times its log's lines start with (output with none is returned as it is)."""
    return '\n'.join(line for _, _, line in stamped(output))


def skip_reasons(output):
    """[(reason, count)] of the skipped tests (and skipped classes) in unittest's verbose output, commonest first."""
    return Counter(m.group(1) for line in unstamped(output).splitlines() if (m := SKIPPED.search(line))).most_common()


def failure_blocks(output):
    """[(kind, test, block text)] of unittest's failure and error reports in `output`."""
    lines, blocks, i = unstamped(output).splitlines(), [], 0
    while i < len(lines):
        m = HEADER.match(lines[i])
        if m and i > 0 and lines[i - 1].startswith('====='):
            body = [lines[i]]
            i += 1
            while i < len(lines) and not (lines[i].startswith('=====') or SUMMARY.match(lines[i])
                                          or (lines[i].startswith('-----') and i + 1 < len(lines) and SUMMARY.match(lines[i + 1]))):
                body.append(lines[i])
                i += 1
            test, where = m.group(2), m.group(3)        # Python 3.11+ puts the full name in the brackets
            name = where if where.endswith('.' + test) else f'{where}.{test}'
            blocks.append((m.group(1), name, '\n'.join(body).rstrip()))
            continue
        i += 1
    return blocks


def outcome(output, code):
    """The suite's last unittest line (OK, OK (skipped=3), FAILED (failures=2)), or why it did not run."""
    tail = [line for line in unstamped(output).splitlines() if line.strip()]
    # after unittest's own "Ran N tests" line (a test's prints can follow it in the log, stdout coming after stderr)
    ran = max((k for k, line in enumerate(tail) if line.startswith('Ran ') and ' test' in line), default=len(tail) - 5)
    for line in tail[max(0, ran):]:
        if line.startswith(('OK', 'FAILED')):
            return line
    return f'did not finish (exit {code})' + (f': {tail[-1]}' if tail else '')


def stamp(begun, ended, line):
    return '[%9.3f %9.3f] %s' % (begun, ended, line)


def run(cmd, log, since=None):
    """Runs `cmd`, writing its output to `log` with each line's two times in seconds since `since` (a
    time.monotonic(), default now). Returns (the output without the times, exit code, seconds taken, the stamped
    output)."""
    started = time.monotonic()
    since = started if since is None else since
    # the suites write UTF-8 (a test's message may hold any character), which is how it is read back
    lines, part, begun, now = [], bytearray(), None, 0.0
    with subprocess.Popen(cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          env=dict(os.environ, PYTHONIOENCODING='utf-8')) as proc:
        while True:
            chunk = proc.stdout.read1(65536)
            now = time.monotonic() - since
            if not chunk:
                break
            pos = 0
            while pos < len(chunk):
                begun = now if begun is None else begun
                end = chunk.find(b'\n', pos)
                if end < 0:
                    part += chunk[pos:]
                    break
                part += chunk[pos:end]
                lines.append((begun, now, part.decode('utf-8', 'replace').rstrip('\r')))
                part, begun, pos = bytearray(), None, end + 1
        if begun is not None:
            lines.append((begun, now, part.decode('utf-8', 'replace').rstrip('\r')))
        code = proc.wait()
    marked = ''.join(stamp(*line) + '\n' for line in lines)
    log.write_text(marked, encoding='utf-8', newline='\n')
    return ''.join(line + '\n' for _, _, line in lines), code, time.monotonic() - started, marked


def selection_words(patterns):
    """The -k patterns as a failure line names them: `-k a -k b`."""
    return ' '.join(f'-k {p}' for p in patterns)


def python_suite(name, patterns, logs):
    """One Python suite run; `patterns` the -k patterns (a test whose name holds any of them runs; None or none:
    every test)."""
    cmd = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', f'tools/{name}/tests', '-p', 'test_*.py', '-v']
    for pattern in patterns or ():
        cmd += ['-k', pattern]       # unittest takes -k again and again, a test matching any of them
    output, code, took, _ = run(cmd, logs / f'{name}.log')
    ran = next((m for m in map(SUMMARY.match, output.splitlines()) if m), None)
    count = int(ran.group(1)) if ran else 0
    failures = failure_blocks(output)
    line = outcome(output, code)
    passed = code == 0 and line.startswith('OK')
    if count == 0 and not failures and (code == 5 or 'NO TESTS RAN' in output):
        # Python 3.12's unittest exits 5 when nothing ran: a selection that runs nothing checked nothing
        line, passed = (f'no test matched {selection_words(patterns)}' if patterns else 'no tests ran'), False
    return dict(name=name, passed=passed, line=line, count=count, took=took,
                failures=failures, log=logs / f'{name}.log', skips=skip_reasons(output))


def node_files(patterns):
    """The node test files to run: those whose names hold any of `patterns` (None or none: every one)."""
    files = sorted((REPO / 'tools/viewer/tests').glob('*_test.mjs'))
    return [f for f in files if any(p in f.name for p in patterns)] if patterns else files


def node_suite(patterns, logs):
    files = node_files(patterns)
    if not files or not shutil.which('node'):
        line = (f'no test file matched {selection_words(patterns)}' if patterns else 'no test files') if not files else \
            'node is not installed (or not on the path): the node tests need Node.js'
        (logs / 'node.log').write_text(line + '\n', encoding='utf-8', newline='\n')
        return dict(name='node', passed=False, line=line, count=0, took=0.0, failures=[], log=logs / 'node.log')
    failures, took, parts, since = [], 0.0, [], time.monotonic()
    for f in files:
        begun = time.monotonic() - since
        output, code, t, marked = run(['node', str(f.relative_to(REPO))], logs / f'node-{f.stem}.log', since)
        took += t
        # the file's line in node.log carries its start and end, which --times reads
        parts.append(stamp(begun, time.monotonic() - since, f'== {f.name} (exit {code})') + '\n' + marked)
        if code:
            failures.append(('FAIL', f.name, output.strip()[-4000:] or f'exit {code}'))
    (logs / 'node.log').write_text(''.join(parts), encoding='utf-8', newline='\n')
    line = f'OK ({len(files)} files)' if not failures else f'FAILED ({len(failures)} of {len(files)} files)'
    return dict(name='node', passed=not failures, line=line, count=len(files), took=took,
                failures=failures, log=logs / 'node.log')


def times(output):
    """The times in a suite's stamped log, slowest first: (tests [(seconds, module.Class.test)], classes [(seconds,
    set-up seconds, tests, module.Class)]); a node log's files are its tests. A class's set-up is the gap between the
    end of the test before its first test and that test's start; its time is that and the time from its first test's
    start to its last test's end. None when the log has no times."""
    lines = stamped(output)
    if all(begun is None for begun, _, _ in lines):
        return None
    tests, classes, ended_last, current = [], {}, 0.0, None
    for begun, ended, line in lines:
        if begun is None:
            continue
        m = NODE_FILE.match(line)
        if m:
            tests.append((ended - begun, m.group(1)))
            continue
        m = TEST.match(line)
        if m:
            name, where, rest = m.groups()
            if name in ('setUpClass', 'tearDownClass', 'setUpModule', 'tearDownModule'):
                ended_last, current = ended, None       # a class (or module) whose fixture skipped or failed
                continue
            current = (name, where[:-len(name) - 1] if where.endswith('.' + name) else where, begun)
            if rest is None or not VERDICT.search(line):
                continue                                # its docstring, or what it printed, comes first
        elif current is None or not VERDICT.search(line):
            continue
        name, cls, start = current
        current = None
        tests.append((ended - start, f'{cls}.{name}'))
        c = classes.setdefault(cls, dict(setup=max(0.0, start - ended_last), first=start, last=ended, count=0))
        c['last'], c['count'] = ended, c['count'] + 1
        ended_last = ended
    return (sorted(tests, key=lambda t: (-t[0], t[1])),
            sorted(((c['setup'] + c['last'] - c['first'], c['setup'], c['count'], cls) for cls, c in classes.items()),
                   key=lambda c: (-c[0], c[3])))


def print_times(name, output):
    found = times(output)
    if found is None:
        print(f'\n== {name}: its log has no times (it was written before the runner stamped its lines)')
        return
    tests, classes = found
    print(f'\n== {name}: the {min(SLOWEST, len(tests))} slowest {"files" if name == "node" else "tests"}')
    for seconds, test in tests[:SLOWEST]:
        print(f'  {seconds:8.2f} s  {test}')
    if classes:
        print(f"== {name}: the {min(SLOWEST, len(classes))} slowest classes (set-up: the gap before a class's first test)")
        for seconds, setup, count, cls in classes[:SLOWEST]:
            print(f'  {seconds:8.2f} s  set-up {setup:7.2f} s  {cls} ({count} test{"s" if count != 1 else ""})')


def logged_times(folder, suites):
    """--times over the logs already in `folder`: the suites named, else every suite with a log there."""
    print(f'logs: {folder}')
    missing = []
    for name in suites or SUITES:
        log = folder / f'{name}.log'
        if log.is_file():
            print_times(name, log.read_text(encoding='utf-8', errors='replace'))
        elif suites:
            missing.append(name)
    for name in missing:
        print(f'\n== {name}: no {name}.log in {folder}')
    return 1 if missing else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], epilog=environment_help(),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('suites', nargs='*', metavar='suite',
                    help=f'which to run (default all: {", ".join(SUITES)})')
    ap.add_argument('-k', dest='patterns', action='append', metavar='PATTERN',
                    help="only tests whose names hold this (unittest's -k; for node, file names); given again, those "
                         'that hold any of them')
    ap.add_argument('--log', type=Path, help='folder for the logs (default .scratch/tests/<date-time>)')
    ap.add_argument('--install', action='store_true',
                    help='run the checks over every map of the install too (on when every suite runs)')
    ap.add_argument('--times', action='store_true',
                    help='then print the twenty slowest tests and classes of each suite; with --log naming a folder '
                         'that already holds logs, read those and run nothing')
    args = ap.parse_args(argv)
    # a console that can't show a character of a failure's message shows a stand-in rather than stopping the run
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
    unknown = [s for s in args.suites if s not in SUITES]
    if unknown:
        ap.error(f'unknown suite {", ".join(unknown)} (one of {", ".join(SUITES)})')
    if args.times and args.log and args.log.is_dir() and any(args.log.glob('*.log')):
        return logged_times(args.log, args.suites)
    suites = args.suites or list(SUITES)
    if args.install or not args.suites:
        os.environ['XCOM_INSTALL_TESTS'] = '1'
    logs = args.log or REPO / '.scratch' / 'tests' / datetime.now().strftime('%Y%m%d-%H%M%S')
    logs.mkdir(parents=True, exist_ok=True)
    print(f'logs: {logs}', flush=True)

    results = []
    for name in suites:
        print(f'\n== {name} ...', flush=True)
        r = node_suite(args.patterns, logs) if name == 'node' else python_suite(name, args.patterns, logs)
        results.append(r)
        print(f'== {name}: {r["line"]}, {r["count"]} {"files" if name == "node" else "tests"}, {r["took"]:.0f} s', flush=True)
        for reason, n in r.get('skips', []):
            print(f'   skipped {n}: {reason}', flush=True)
        for kind, test, block in r['failures']:
            print(f'\n-- {kind} {test}\n{block}', flush=True)
        if not r['passed'] and not r['failures']:
            print(f'   see {r["log"]}', flush=True)

    print('\nSummary')
    for r in results:
        skipped = sum(n for _, n in r.get('skips', []))
        print(f'  {"pass" if r["passed"] else "FAIL"}  {r["name"]:<8} {r["line"]}'
              + (f' ({skipped} skipped for {len(r["skips"])} reason(s), listed above)' if skipped else ''))
        for kind, test, _ in r['failures']:
            print(f'          {kind} {test}')
    if args.times:
        for r in results:
            print_times(r['name'], r['log'].read_text(encoding='utf-8', errors='replace'))
    print(f'logs: {logs}')
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
