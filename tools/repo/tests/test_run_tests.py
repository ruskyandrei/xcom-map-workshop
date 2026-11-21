"""The suite runner (tools/run_tests.py): a selection that runs nothing fails, -k given again adds to the selection,
skips are counted by reason, the logs' lines carry their times and --times reads them, and --help lists every
environment variable the tools read."""
import contextlib
import io
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import run_tests  # noqa: E402

REPO = Path(__file__).resolve().parents[3]

# a made-up verbose unittest run, as its lines come: the two times of each are when it began and when it ended
LOG = [
    (0.50, 0.50, 'setUpClass (m.Skipped) ... skipped \'no install\''),
    (3.00, 3.25, 'test_a (m.Slow.test_a) ... ok'),           # 2.5 s of set-up before it (the gap from 0.50)
    (3.25, 7.25, 'test_b (m.Slow.test_b) ... FAIL'),
    (7.30, 7.30, 'test_c (m.Docs.test_c)'),                   # a test with a docstring: its first line comes next
    (7.30, 8.30, 'The docstring of test_c ... ok'),
    (8.30, 8.40, 'test_d (m.Docs.test_d) ... '),               # it printed something before its verdict
    (8.40, 8.40, 'something it printed'),
    (8.40, 9.40, 'ok'),
    (9.40, 9.40, "test_e (m.Docs.test_e) ... skipped 'needs Playwright'"),
    (9.50, 9.50, ''),
    (9.50, 9.50, '======================================================================'),
    (9.50, 9.50, 'FAIL: test_b (m.Slow.test_b)'),
    (9.50, 9.50, '----------------------------------------------------------------------'),
    (9.50, 9.50, 'Traceback (most recent call last):'),
    (9.50, 9.50, 'AssertionError: 1 != 2'),
    (9.50, 9.50, ''),
    (9.50, 9.50, '----------------------------------------------------------------------'),
    (9.50, 9.50, 'Ran 5 tests in 9.000s'),
    (9.50, 9.50, ''),
    (9.50, 9.50, 'FAILED (failures=1, skipped=1)'),
]
PLAIN = '\n'.join(line for _, _, line in LOG) + '\n'
STAMPED = ''.join(run_tests.stamp(*line) + '\n' for line in LOG)


class Runner(unittest.TestCase):
    def test_skips_are_counted_by_reason(self):
        out = '\n'.join([
            "test_a (m.C.test_a) ... skipped 'no install'",
            "test_b (m.C.test_b) ... ok",
            "setUpClass (m.D) ... skipped 'no install'",
            "test_c (m.E.test_c) ... skipped 'needs Playwright'"])
        self.assertEqual(run_tests.skip_reasons(out), [('no install', 2), ('needs Playwright', 1)])

    def test_a_node_selection_that_matches_no_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_tests.node_suite(['no-such-node-test-name'], Path(tmp))
        self.assertFalse(r['passed'])
        self.assertIn('no test file matched', r['line'])

    def test_a_python_selection_that_matches_nothing_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_tests.python_suite('repo', ['no_such_test_name_anywhere'], Path(tmp))
        self.assertFalse(r['passed'])
        self.assertEqual(r['line'], 'no test matched -k no_such_test_name_anywhere')

    def test_k_given_twice_runs_the_tests_of_both(self):
        # follow-up 4.5: -k given twice kept only the last pattern, so half of what was asked ran, silently
        first, second = 'test_skips_are_counted_by_reason', 'test_a_node_logs_files_are_its_tests'
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                code = run_tests.main(['repo', '-k', first, '-k', second, '--log', tmp])
            log = run_tests.unstamped((Path(tmp) / 'repo.log').read_text(encoding='utf-8'))
        self.assertEqual(code, 0)
        self.assertIn(first, log)
        self.assertIn(second, log)
        self.assertIn('Ran 2 tests', log)

    def test_node_files_matching_any_pattern(self):
        names = [f.name for f in run_tests.node_files(['twin_constants', 'shared_cases'])]
        self.assertEqual(names, ['shared_cases_test.mjs', 'twin_constants_test.mjs'])
        self.assertEqual(run_tests.node_files(['no-such-node-test-name']), [])
        self.assertEqual(len(run_tests.node_files(None)), len(list((REPO / 'tools/viewer/tests').glob('*_test.mjs'))))


class Times(unittest.TestCase):
    def test_the_output_reads_the_same_with_or_without_its_times(self):
        self.assertEqual(run_tests.unstamped(STAMPED), PLAIN.rstrip('\n'))
        for output in (PLAIN, STAMPED):
            self.assertEqual(run_tests.outcome(output, 1), 'FAILED (failures=1, skipped=1)')
            self.assertEqual(run_tests.skip_reasons(output), [('no install', 1), ('needs Playwright', 1)])
            blocks = run_tests.failure_blocks(output)
            self.assertEqual([(k, t) for k, t, _ in blocks], [('FAIL', 'm.Slow.test_b')])
            self.assertTrue(blocks[0][2].endswith('AssertionError: 1 != 2'))

    def test_the_slowest_tests_and_classes(self):
        tests, classes = run_tests.times(STAMPED)
        self.assertEqual([(round(s, 2), t) for s, t in tests],
                         [(4.0, 'm.Slow.test_b'), (1.1, 'm.Docs.test_d'), (1.0, 'm.Docs.test_c'),
                          (0.25, 'm.Slow.test_a'), (0.0, 'm.Docs.test_e')])
        # a class: its set-up (the gap before its first test) and from its first test's start to its last's end
        self.assertEqual([(round(s, 2), round(setup, 2), n, c) for s, setup, n, c in classes],
                         [(6.75, 2.5, 2, 'm.Slow'), (2.15, 0.05, 3, 'm.Docs')])
        self.assertIsNone(run_tests.times(PLAIN))

    def test_a_node_logs_files_are_its_tests(self):
        log = run_tests.stamp(0.0, 1.5, '== a_test.mjs (exit 0)') + '\n' + run_tests.stamp(0.1, 0.1, 'ok 1') + '\n' + \
            run_tests.stamp(1.5, 4.0, '== b_test.mjs (exit 1)') + '\n'
        self.assertEqual(run_tests.times(log), ([(2.5, 'b_test.mjs'), (1.5, 'a_test.mjs')], []))

    def test_a_line_carries_when_it_began_and_when_it_ended(self):
        # a line whose end comes 0.4 s after its start, as a test's verdict comes after its name
        cmd = [sys.executable, '-c', 'import sys, time; sys.stdout.write("name ... "); sys.stdout.flush(); '
                                     'time.sleep(0.4); print("ok"); print("next")']
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'x.log'
            output, code, took, marked = run_tests.run(cmd, log)
            self.assertEqual(log.read_text(encoding='utf-8'), marked)
        self.assertEqual((output, code), ('name ... ok\nnext\n', 0))
        lines = run_tests.stamped(marked)
        self.assertEqual([line for _, _, line in lines], ['name ... ok', 'next'])
        (begun, ended, _), (next_begun, _, _) = lines
        self.assertGreaterEqual(ended - begun, 0.3)
        self.assertGreaterEqual(next_begun, ended)

    def test_times_reads_a_log_folder_without_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'repo.log').write_text(STAMPED, encoding='utf-8', newline='\n')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = run_tests.main(['repo', '--times', '--log', str(folder)])
            self.assertEqual((folder / 'repo.log').read_text(encoding='utf-8'), STAMPED)     # not run again
            self.assertEqual(code, 0)
            self.assertIn('the 5 slowest tests', out.getvalue())
            self.assertIn('4.00 s  m.Slow.test_b', out.getvalue())
            self.assertIn('set-up    2.50 s  m.Slow (2 tests)', out.getvalue())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(run_tests.main(['editor', '--times', '--log', str(folder)]), 1)
            self.assertIn('no editor.log', out.getvalue())


class Environment(unittest.TestCase):
    """run_tests.ENVIRONMENT, which --help prints, lists every environment variable the tests and the tools read
    (review finding 58: they were named only where each was read)."""
    NAME = re.compile(rb'XCOM_[A-Z0-9_]+')

    def names_in(self, path):
        return {m.group().decode() for m in self.NAME.finditer(path.read_bytes())} if path.is_file() else set()

    def test_every_variable_the_tools_read_is_listed_and_each_listed_one_is_read(self):
        # the files Git has or would add under tools/, but the runner itself (where the list is) and this test
        out = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard', 'tools'], cwd=REPO,
                             capture_output=True, check=True).stdout.decode('utf-8')
        own = {Path(run_tests.__file__).resolve(), Path(__file__).resolve()}
        read = set().union(*(self.names_in(REPO / p) for p in out.split('\0') if p and (REPO / p).resolve() not in own))
        listed = run_tests.environment_names()
        self.assertEqual(len(listed), len(set(listed)), 'a variable listed twice')
        self.assertEqual(sorted(read - set(listed)), [], 'read by the tools, not in run_tests.ENVIRONMENT')
        self.assertEqual(sorted(set(listed) - read), [], 'in run_tests.ENVIRONMENT, read by no tool')

    def test_the_readme_names_only_listed_variables(self):
        self.assertEqual(sorted(self.names_in(REPO / 'README.md') - set(run_tests.environment_names())), [])

    def test_help_prints_each_variable(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            run_tests.main(['--help'])
        for name in run_tests.environment_names():
            self.assertIn(name, out.getvalue())


if __name__ == '__main__':
    unittest.main()
