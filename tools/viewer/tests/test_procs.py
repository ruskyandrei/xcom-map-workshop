"""The server's builds as contained process trees (procs.py; build queue plan, 9.3): stopping a tree stops every
process of it, a server that dies takes its trees with it, a process that can't be contained never runs, and a tree
a server started before it restarted is found by its identity, not its id alone."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import procs  # noqa: E402

# a child that starts a grandchild, says both ids, and waits
CHILD = ("import subprocess, sys, time\n"
         "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
         "print(g.pid, flush=True)\n"
         "time.sleep(120)\n")
# a stand-in for the server: launches CHILD contained, writes the ids, and waits to be killed
SERVER = ("import json, subprocess, sys, time\n"
          "sys.path.insert(0, sys.argv[1])\n"
          "import procs\n"
          "c = procs.launch([sys.executable, '-c', sys.argv[3]], stdout=subprocess.PIPE, text=True)\n"
          "grand = int(c.proc.stdout.readline())\n"
          "json.dump(dict(child=c.pid, childAt=c.created, grand=grand, grandAt=procs.identity(grand)), open(sys.argv[2], 'w'))\n"
          "time.sleep(120)\n")


def wait_gone(pid, created, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if procs.identity(pid) != created:
            return True
        time.sleep(0.05)
    return False


class Contained(unittest.TestCase):
    def test_terminate_stops_the_whole_tree_and_drain_waits_for_it(self):
        c = procs.launch([sys.executable, '-c', CHILD], stdout=subprocess.PIPE, text=True)
        self.addCleanup(c.close)
        grand = int(c.proc.stdout.readline())
        born = procs.identity(grand)
        self.assertIsNotNone(born)
        self.assertEqual(c.active(), 2 if procs.WINDOWS else 1)
        alive = [pid for pid, _ in procs.tree_alive(c.pid, c.created)]
        self.assertIn(c.pid, alive)
        if procs.WINDOWS:
            self.assertIn(grand, alive)
        c.terminate()
        self.assertTrue(c.drain(15))
        # gone, not merely told to end: drain waits for each process it saw
        self.assertNotEqual(procs.identity(grand), born)
        self.assertEqual(procs.tree_alive(c.pid, c.created), [])
        c.proc.stdout.close()
        c.proc.wait()

    def test_a_natural_exit_drains_at_once(self):
        c = procs.launch([sys.executable, '-c', 'print("done")'], stdout=subprocess.PIPE, text=True)
        self.addCleanup(c.close)
        self.assertEqual(c.proc.stdout.read().strip(), 'done')
        c.proc.wait()
        self.assertTrue(c.drain(10))
        self.assertEqual(c.active(), 0)

    def test_a_server_that_dies_takes_its_trees_with_it(self):
        """The real Windows case: the stand-in server is killed outright (TerminateProcess); the job's last handle
        closes with it and the child and grandchild end."""
        with tempfile.TemporaryDirectory() as temp:
            ids = Path(temp) / 'ids.json'
            server = subprocess.Popen([sys.executable, '-c', SERVER, str(HERE.parent), str(ids), CHILD],
                                      creationflags=procs.CREATE_NO_WINDOW)
            end = time.monotonic() + 30
            while not ids.is_file() or not ids.read_text():
                self.assertLess(time.monotonic(), end, 'the stand-in server never launched its child')
                time.sleep(0.05)
            time.sleep(0.1)
            found = json.loads(ids.read_text())
            self.assertIsNotNone(procs.identity(found['grand']))
            server.kill()
            server.wait()
            if not procs.WINDOWS:
                self.skipTest('kill on job close is Windows behaviour; elsewhere the session outlives its server')
            self.assertTrue(wait_gone(found['child'], found['childAt']), 'the child outlived its server')
            self.assertTrue(wait_gone(found['grand'], found['grandAt']), 'the grandchild outlived its server')
            self.assertEqual(procs.tree_alive(found['child'], found['childAt']), [])

    @unittest.skipUnless(procs.WINDOWS, 'the job is Windows containment')
    def test_a_process_that_cannot_be_contained_never_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            ran = Path(temp) / 'ran'
            with mock.patch.object(procs, '_AssignProcessToJobObject', lambda job, handle: 0):
                with self.assertRaises(procs.ContainError):
                    procs.launch([sys.executable, '-c', f'open({str(ran)!r}, "w").write("ran")'])
            time.sleep(0.5)
            self.assertFalse(ran.exists())

    def test_a_child_in_a_folder_of_any_name_writes_its_output_in_utf8(self):
        """A piped Python child writes in the system's code page unless told otherwise; launch tells it UTF-8, so a
        folder whose name that code page lacks (Cyrillic on a Western system) is printed, not fatal. The test's own
        environment is stripped of the variables first (the test runner sets one)."""
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'Сборка карт'
            folder.mkdir()
            script = folder / 'tool.py'
            script.write_text('import sys\nprint(sys.stdout.encoding)\nprint(__file__)\n', encoding='utf-8')
            bare = {k: v for k, v in __import__('os').environ.items() if k not in ('PYTHONUTF8', 'PYTHONIOENCODING')}
            c = procs.launch([sys.executable, '-B', str(script)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding='utf-8', errors='replace', env=bare)
            self.addCleanup(c.close)
            out = c.proc.stdout.read()
            self.assertEqual(c.proc.wait(), 0, out)
            encoding, path = out.splitlines()[:2]
            self.assertEqual(encoding.lower().replace('-', ''), 'utf8')
            self.assertEqual(Path(path), script)
            c.proc.stdout.close()

    def test_identity_names_a_live_process_and_not_a_dead_one(self):
        p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        born = procs.identity(p.pid)
        self.assertIsNotNone(born)
        p.kill(); p.wait()
        self.assertTrue(wait_gone(p.pid, born))
        self.assertIsNone(procs.identity(0))
        self.assertIsNone(procs.identity('12'))
        # a tree whose root is gone and whose creation time doesn't match anything: nothing of it runs
        self.assertEqual(procs.tree_alive(p.pid, born), [])


if __name__ == '__main__':
    unittest.main()
