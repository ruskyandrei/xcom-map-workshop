"""A variant package put in place with a journal (publication.py; build queue plan, 9.3): a build killed outright at
each step of the swap leaves, once reconciled, the last package or the new one whole; a journal that can't be read
blocks the variant without deleting anything; the variant's guard is held by the operating system, released when its
holder dies and never taken from a live one because time passed."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import installs  # noqa: E402
import publication  # noqa: E402

V = 'URB_Bar_Remix_0f8b'
# publish() run in a process of its own that ends outright (os._exit) after the named step
DIE = ("import json, os, sys\n"
       "sys.path.insert(0, sys.argv[1])\n"
       "import publication\n"
       "output, variant, staging, existing, identity, step = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] or None, json.loads(sys.argv[6]), sys.argv[7]\n"
       "with publication.guard(output, variant):\n"
       "    publication.publish(output, variant, staging, existing, identity, boundary=lambda name: os._exit(70) if name == step else None)\n"
       "os._exit(0)\n")
# holds the guard until killed
HOLD = ("import sys, time\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import publication\n"
        "with publication.guard(sys.argv[2], sys.argv[3]):\n"
        "    print('held', flush=True)\n"
        "    time.sleep(120)\n")


def package(folder, build_id, content, attempt=None):
    cooked = folder / 'CookedPCConsole'
    cooked.mkdir(parents=True)
    (cooked / f'{V}.upk').write_bytes(content)
    m = dict(schema=installs.PACKAGE_SCHEMA, schemaVersion=1, buildId=build_id, project=dict(id='p1', revision=1),
             variant=V, files={f'CookedPCConsole/{V}.upk': hashlib.sha256(content).hexdigest()},
             **({'attempt': attempt} if attempt else {}))
    (folder / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
    return m


class Publication(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'builds'
        self.output.mkdir()

    def staging(self, build_id='new', content=b'new map', attempt='a1'):
        folder = self.output / '.work' / f'{V}-{build_id}' / 'package'
        package(folder, build_id, content, attempt)
        return folder

    def built(self):
        return json.loads((self.output / V / 'manifest.json').read_text(encoding='utf-8'))['buildId']

    def leftovers(self):
        folder = publication.journals(self.output)
        return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []

    def test_a_package_goes_in_and_its_old_one_goes(self):
        package(self.output / V, 'old', b'old map')
        with publication.guard(self.output, V):
            warnings = publication.publish(self.output, V, self.staging(), self.output / V,
                                           dict(buildId='new', attempt='a1', project='p1'))
        self.assertEqual((warnings, self.built(), self.leftovers()), ([], 'new', []))
        self.assertIsNone(publication.recover(self.output, V))

    def die_at(self, step, existing=True):
        if existing:
            package(self.output / V, 'old', b'old map')
        staging = self.staging()
        result = subprocess.run([sys.executable, '-c', DIE, str(HERE.parent), str(self.output), V, str(staging),
                                 str(self.output / V) if existing else '', json.dumps(dict(buildId='new', attempt='a1', project='p1')),
                                 step], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 70, result.stderr)

    def test_a_build_killed_at_each_step_leaves_a_whole_package(self):
        for step, after in (('journal', 'old'), ('old-aside', 'old'), ('new-in-place', 'new'), ('committed', 'new'),
                            ('cleaned', 'new')):
            with self.subTest(step=step):
                shutil.rmtree(self.output); self.output.mkdir()
                self.die_at(step)
                self.assertEqual(publication.pending(self.output), [V])
                # the dead build's guard is free at once: the operating system let it go
                results = publication.recover_all(self.output)
                self.assertNotEqual(results[V]['state'], 'blocked', results)
                self.assertEqual(self.built(), after)
                installs.read_package(self.output / V)          # whole: every file as its manifest says
                self.assertEqual(self.leftovers(), [])

    def test_a_first_build_killed_leaves_none_or_its_own(self):
        self.die_at('journal', existing=False)
        self.assertEqual(publication.recover_all(self.output)[V]['state'], 'none')
        self.assertFalse((self.output / V).exists())
        shutil.rmtree(self.output); self.output.mkdir()
        self.die_at('new-in-place', existing=False)
        self.assertEqual(publication.recover_all(self.output)[V]['state'], 'committed')
        self.assertEqual(self.built(), 'new')

    def test_a_new_package_that_does_not_match_its_manifest_gives_way_to_the_old(self):
        self.die_at('new-in-place')
        (self.output / V / 'CookedPCConsole' / f'{V}.upk').write_bytes(b'torn')
        result = publication.recover_all(self.output)[V]
        self.assertEqual(result['state'], 'restored')
        self.assertEqual(self.built(), 'old')
        self.assertEqual(len([n for n in self.leftovers() if n.endswith('.rejected')]), 1)     # kept, not deleted

    def test_a_journal_that_cannot_be_read_blocks_the_variant_and_deletes_nothing(self):
        package(self.output / V, 'old', b'old map')
        folder = publication.journals(self.output)
        folder.mkdir(parents=True)
        publication.journal_path(self.output, V).write_text('{"schema": "xcom-map-workshop/publication", "sch', encoding='utf-8')
        result, = publication.recover_all(self.output).values()     # named by its file: its name can't be read
        self.assertEqual(result['state'], 'blocked')
        self.assertIn('can\'t be settled', result['reason'])
        self.assertTrue(publication.journal_path(self.output, V).is_file())
        with publication.guard(self.output, V):
            with self.assertRaises(publication.Blocked):
                publication.publish(self.output, V, self.staging(), self.output / V, dict(buildId='new', attempt='a1'))
        self.assertEqual(self.built(), 'old')
        # a journal pointing outside its folder is not followed either
        publication.journal_path(self.output, V).write_text(json.dumps(dict(
            schema=publication.SCHEMA, schemaVersion=1, variant=V, state='prepared', final=str(self.output / V),
            existing=str(self.output / V), backup=str(Path(self.temp.name) / 'elsewhere'), build=dict(buildId='x'))), encoding='utf-8')
        self.assertEqual(publication.recover_all(self.output)[V]['state'], 'blocked')
        self.assertEqual(self.built(), 'old')

    def test_the_guard_is_held_by_its_live_holder_and_freed_when_it_dies(self):
        holder = subprocess.Popen([sys.executable, '-c', HOLD, str(HERE.parent), str(self.output), V],
                                  stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), 'held')
            started = time.monotonic()
            with self.assertRaises(publication.Busy):
                with publication.guard(self.output, V, wait=0.5):
                    pass
            self.assertGreaterEqual(time.monotonic() - started, 0.4)
            # an old lock file's age means nothing: the holder is alive
            lock = publication.lock_path(self.output, V)
            import os
            os.utime(lock, (time.time() - 10 ** 6, time.time() - 10 ** 6))
            self.assertEqual(publication.recover_all(self.output), {})
            with self.assertRaises(publication.Busy):
                with publication.guard(self.output, V, wait=0):
                    pass
        finally:
            holder.kill(); holder.wait(); holder.stdout.close()
        with publication.guard(self.output, V, wait=5):
            pass
        # several at once, in one order whatever order they are asked in
        with publication.guards(self.output, [V, 'Another_1', V.lower()]):
            pass


if __name__ == '__main__':
    unittest.main()
