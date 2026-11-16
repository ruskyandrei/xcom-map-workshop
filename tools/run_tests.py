"""Runs the repository's offline test suites and says, at once, which tests failed and why.

Each Python suite (tools/<suite>/tests, test_*.py) runs in its own process with unittest's verbose output, and the
node tests (tools/viewer/tests/*_test.mjs) one file each. The whole output of every suite is kept in a log folder,
and every failure and error is printed with its traceback when its suite ends, so a failure in a long suite (bake
takes about a quarter of an hour) needs no second run to be found.

  python -B tools/run_tests.py                     every suite: viewer, editor, upk, bake, release, repo, node
  python -B tools/run_tests.py viewer editor       only these
  python -B tools/run_tests.py bake -k shell       only the tests whose names hold "shell" (unittest's -k)
  python -B tools/run_tests.py --log <folder>      where the logs go (default .scratch/tests/<date-time>)
  python -B tools/run_tests.py upk --install       with the checks over every map of the install too

The checks over every map of the install (tools/upk/tests/test_game_grid.py: two minutes, most of it opening the maps)
run when every suite runs, as the release does, or with --install; they skip otherwise (XCOM_INSTALL_TESTS is how
the suites are told).

Exit status 0 when everything passed, 1 when anything failed or a suite could not run. The browser smoke
(tools/viewer/tests/browser_smoke.py) needs a test server and is not run here.
"""
import argparse
from datetime import datetime
import os
from pathlib import Path
import re
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
PYTHON_SUITES = ('viewer', 'editor', 'upk', 'bake', 'release', 'repo')
SUITES = PYTHON_SUITES + ('node',)
HEADER = re.compile(r'^(FAIL|ERROR): (\S+) \((\S+)\)')
SUMMARY = re.compile(r'^Ran (\d+) tests? in ([\d.]+)s$')


def failure_blocks(output):
    """[(kind, test, block text)] of unittest's failure and error reports in `output`."""
    lines, blocks, i = output.splitlines(), [], 0
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
    tail = [line for line in output.splitlines() if line.strip()]
    for line in reversed(tail[-5:]):
        if line.startswith(('OK', 'FAILED')):
            return line
    return f'did not finish (exit {code})' + (f': {tail[-1]}' if tail else '')


def run(cmd, log):
    started = time.monotonic()
    # the suites write UTF-8 (a test's message may hold any character), which is how it is read back
    proc = subprocess.run(cmd, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    log.write_text(proc.stdout, encoding='utf-8', newline='\n')
    return proc.stdout, proc.returncode, time.monotonic() - started


def python_suite(name, pattern, logs):
    cmd = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', f'tools/{name}/tests', '-p', 'test_*.py', '-v']
    if pattern:
        cmd += ['-k', pattern]
    output, code, took = run(cmd, logs / f'{name}.log')
    ran = next((m for m in map(SUMMARY.match, output.splitlines()) if m), None)
    count = int(ran.group(1)) if ran else 0
    failures = failure_blocks(output)
    passed = code == 0 and outcome(output, code).startswith('OK')
    return dict(name=name, passed=passed, line=outcome(output, code), count=count, took=took,
                failures=failures, log=logs / f'{name}.log')


def node_suite(pattern, logs):
    files = sorted((REPO / 'tools/viewer/tests').glob('*_test.mjs'))
    if pattern:
        files = [f for f in files if pattern in f.name]
    failures, took, parts = [], 0.0, []
    for f in files:
        output, code, t = run(['node', str(f.relative_to(REPO))], logs / f'node-{f.stem}.log')
        took += t
        parts.append(f'== {f.name} (exit {code})\n{output}')
        if code:
            failures.append(('FAIL', f.name, output.strip()[-4000:] or f'exit {code}'))
    (logs / 'node.log').write_text('\n'.join(parts), encoding='utf-8', newline='\n')
    line = f'OK ({len(files)} files)' if not failures else f'FAILED ({len(failures)} of {len(files)} files)'
    return dict(name='node', passed=not failures, line=line, count=len(files), took=took,
                failures=failures, log=logs / 'node.log')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('suites', nargs='*', metavar='suite',
                    help=f'which to run (default all: {", ".join(SUITES)})')
    ap.add_argument('-k', dest='pattern', help="only tests whose names hold this (unittest's -k; for node, file names)")
    ap.add_argument('--log', type=Path, help='folder for the logs (default .scratch/tests/<date-time>)')
    ap.add_argument('--install', action='store_true',
                    help='run the checks over every map of the install too (on when every suite runs)')
    args = ap.parse_args(argv)
    # a console that can't show a character of a failure's message shows a stand-in rather than stopping the run
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
    unknown = [s for s in args.suites if s not in SUITES]
    if unknown:
        ap.error(f'unknown suite {", ".join(unknown)} (one of {", ".join(SUITES)})')
    suites = args.suites or list(SUITES)
    if args.install or not args.suites:
        os.environ['XCOM_INSTALL_TESTS'] = '1'
    logs = args.log or REPO / '.scratch' / 'tests' / datetime.now().strftime('%Y%m%d-%H%M%S')
    logs.mkdir(parents=True, exist_ok=True)
    print(f'logs: {logs}', flush=True)

    results = []
    for name in suites:
        print(f'\n== {name} ...', flush=True)
        r = node_suite(args.pattern, logs) if name == 'node' else python_suite(name, args.pattern, logs)
        results.append(r)
        print(f'== {name}: {r["line"]}, {r["count"]} {"files" if name == "node" else "tests"}, {r["took"]:.0f} s', flush=True)
        for kind, test, block in r['failures']:
            print(f'\n-- {kind} {test}\n{block}', flush=True)
        if not r['passed'] and not r['failures']:
            print(f'   see {r["log"]}', flush=True)

    print('\nSummary')
    for r in results:
        print(f'  {"pass" if r["passed"] else "FAIL"}  {r["name"]:<8} {r["line"]}')
        for kind, test, _ in r['failures']:
            print(f'          {kind} {test}')
    print(f'logs: {logs}')
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
