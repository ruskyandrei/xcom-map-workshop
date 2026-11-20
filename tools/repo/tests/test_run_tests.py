"""The suite runner (tools/run_tests.py): a selection that runs nothing fails, and skips are counted by reason."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import run_tests  # noqa: E402


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
            r = run_tests.node_suite('no-such-node-test-name', Path(tmp))
        self.assertFalse(r['passed'])
        self.assertIn('no test file matched', r['line'])

    def test_a_python_selection_that_matches_nothing_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_tests.python_suite('repo', 'no_such_test_name_anywhere', Path(tmp))
        self.assertFalse(r['passed'])
        self.assertEqual(r['line'], 'no test matched -k no_such_test_name_anywhere')


if __name__ == '__main__':
    unittest.main()
