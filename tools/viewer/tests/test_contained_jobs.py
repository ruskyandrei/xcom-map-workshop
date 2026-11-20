"""Exports, library scans and the cache job are contained as builds are (review finding 48): started as process
trees that a Cancel ends whole, never by a bare process id; the pieces folder is locked across processes; temporary
files have names of their own; and the game install changes only when none of them runs, with the setting put back
when the server can't load the new one."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from exports import ExportRunner  # noqa: E402
from gamesetup import GameSetup  # noqa: E402
import library  # noqa: E402
import procs  # noqa: E402
from projects import ProjectError  # noqa: E402
from viewer import Live, install_busy  # noqa: E402

# an export that starts a child of its own, says both ids, and waits to be stopped
SPAWNING = """import subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
print('pids %d %d' % (__import__('os').getpid(), child.pid), flush=True)
time.sleep(60)
"""
# a process that holds a donor's lock until it is stopped
HOLDER = """import sys, time
sys.path.insert(0, sys.argv[1])
import library
with library.donor_lock(sys.argv[2], 'URB_One'):
    print('held', flush=True)
    time.sleep(60)
"""


def gone(pid, seconds=10):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if procs.identity(pid) is None:
            return True
        time.sleep(0.1)
    return False


class Contained(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_cancelling_an_export_ends_its_whole_tree(self):
        script = self.root / 'spawning.py'
        script.write_text(SPAWNING, encoding='utf-8', newline='\n')
        catalogue = dict(maps=dict(Alpha=dict(id='Alpha', label='Alpha', root=None, ready=False)))
        runner = ExportRunner(catalogue, self.root / 'cache', None, command=lambda package: [sys.executable, '-B', str(script)])
        runner.package = lambda map_id: Path('Alpha.upk')
        runner.start('Alpha', owner='precache')
        self.assertEqual(runner.running(), 'Alpha')
        self.assertIsInstance(runner.job['tree'], procs.Contained)
        pids = None
        for _ in range(200):
            line = next((l for l in runner.job['lines'] if l.startswith('pids ')), None)
            if line:
                pids = [int(v) for v in line.split()[1:]]
                break
            time.sleep(0.05)
        self.assertIsNotNone(pids, runner.job['lines'])
        runner.cancel_owned('precache')
        for _ in range(200):
            if runner.job['state'] != 'running':
                break
            time.sleep(0.05)
        self.assertEqual((runner.job['state'], runner.job['error']), ('failed', 'Preparation cancelled.'))
        self.assertTrue(all(gone(pid) for pid in pids), pids)
        self.assertIsNone(runner.running())

    def test_an_export_that_cant_start_says_so(self):
        catalogue = dict(maps=dict(Alpha=dict(id='Alpha', label='Alpha', root=None, ready=False)))
        runner = ExportRunner(catalogue, self.root / 'cache', None, command=lambda package: [str(self.root / 'no-such.exe')])
        runner.package = lambda map_id: Path('Alpha.upk')
        with self.assertRaises(ProjectError) as failed:
            runner.start('Alpha')
        self.assertEqual(failed.exception.status, 500)
        self.assertIn('did not start', failed.exception.message)
        self.assertIsNone(runner.running())

    def test_a_donors_pieces_are_locked_across_processes(self):
        cache = self.root / 'cache'
        script = self.root / 'holder.py'
        script.write_text(HOLDER, encoding='utf-8', newline='\n')
        holder = subprocess.Popen([sys.executable, '-B', str(script), str(HERE.parent), str(cache)], stdout=subprocess.PIPE,
                                  text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), 'held')
            with self.assertRaises(ProjectError) as busy:
                with library.donor_lock(cache, 'urb_one', wait=0.3):
                    pass
            self.assertEqual((busy.exception.status, busy.exception.extra.get('code')), (409, 'piece-busy'))
            with library.donor_lock(cache, 'URB_Two', wait=0.3):      # another donor's is free
                pass
        finally:
            holder.kill()
            holder.wait()
            holder.stdout.close()
        with library.donor_lock(cache, 'URB_One', wait=5):
            pass

    def test_temporary_files_have_names_of_their_own(self):
        record = self.root / 'Crate_1.json'
        names = {library.part_of(record).name for _ in range(50)}
        self.assertEqual(len(names), 50)
        self.assertTrue(all(n.startswith('Crate_1.json.') and n.endswith('.part') for n in names))


class InstallSwitch(unittest.TestCase):
    def test_no_switch_while_an_export_a_scan_or_the_cache_job_runs(self):
        class Running:
            def __init__(self, value): self.value = value
            def running(self): return self.value
        install_busy(Live({}, Running(None), None, Running(False)), Running(False))
        for live, precache, said in ((Live({}, Running('Bar'), None, Running(False)), Running(False), 'Bar is being prepared'),
                                     (Live({}, None, None, Running(True)), None, 'The library of pieces is being read'),
                                     (Live({}, None, None, None), Running(True), 'Cache everything is running')):
            with self.assertRaises(ProjectError) as busy:
                install_busy(live, precache)
            self.assertEqual((busy.exception.status, busy.exception.extra.get('code')), (409, 'install-busy'))
            self.assertTrue(busy.exception.message.startswith(said), busy.exception.message)

    def test_a_failed_switch_puts_the_setting_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = Path(tmp) / 'old', Path(tmp) / 'new'
            for game in (old, new):
                (game / 'XEW' / 'XComGame' / 'CookedPCConsole').mkdir(parents=True)
            stored = dict(game=old)
            def save(updates):
                stored.update(updates)
                return dict(stored)
            def configure(settings):
                raise OSError(13, 'Access is denied')
            setup = GameSetup(configure, load=lambda: dict(stored), save=save, find=lambda: [])
            with self.assertRaises(ProjectError) as failed:
                setup.choose(dict(folder=str(new)))
            self.assertEqual(failed.exception.status, 500)
            self.assertIn('Access is denied', failed.exception.message)
            self.assertEqual(stored['game'], old)
            # one that loads is kept
            setup = GameSetup(lambda settings: None, load=lambda: dict(stored), save=save, find=lambda: [])
            setup.choose(dict(folder=str(new)))
            self.assertEqual(Path(stored['game']), new)


if __name__ == '__main__':
    unittest.main()
