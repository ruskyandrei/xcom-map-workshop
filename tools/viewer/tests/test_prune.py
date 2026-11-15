"""Old exports out of the cache (prune.py): of a map's generations of one package and scope the newest stays, the
rest go; another package's, unfinished ones and folders that are not generations stay."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import prune  # noqa: E402

A, B = 'a3ae5a73457c3c3f', '0123456789abcdef'


class Prune(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name)
        self.stamp = 1_700_000_000

    def tearDown(self):
        self.tmp.cleanup()

    def generation(self, map_name, name, scene=True):
        folder = self.cache / map_name / name
        folder.mkdir(parents=True)
        (folder / 'mesh.glb').write_bytes(b'x' * 1000)
        if scene:
            (folder / 'scene.json').write_text('{}', encoding='utf-8')
            self.stamp += 10
            os.utime(folder / 'scene.json', (self.stamp, self.stamp))
        return folder

    def test_the_newest_of_each_package_and_scope_stays(self):
        old = [self.generation('URB_Bar', f'{A}-v{n}-map') for n in (18, 21, 22)]
        twin = self.generation('URB_Bar', f'{A}-v23-map')
        newest = self.generation('URB_Bar', f'{A}-v23-map-30nuu7fe')       # published beside, later
        other = self.generation('URB_Bar', f'{B}-v20-map')                 # another install's package
        sample_old, sample = self.generation('URB_Bar', f'{A}-v1-sample'), self.generation('URB_Bar', f'{A}-v2-sample')
        unfinished = self.generation('URB_Bar', f'{A}-v24-map', scene=False)
        running = self.cache / 'URB_Bar' / '.export-123'
        running.mkdir()
        log = (self.cache / 'URB_Bar' / 'viewer-v11-out.log')
        log.write_text('x', encoding='utf-8')
        (self.cache / 'library' / 'pieces' / 'URB_Bar' / f'{A}-v22').mkdir(parents=True)
        (self.cache / 'library' / 'pieces' / 'URB_Bar' / f'{A}-v23').mkdir(parents=True)
        os.utime(self.cache / 'library' / 'pieces' / 'URB_Bar' / f'{A}-v22', (1, 1))
        self.assertEqual(sorted(p.name for p in prune.stale(self.cache)),
                         sorted([f.name for f in old] + [twin.name, sample_old.name, f'{A}-v22']))
        result = prune.prune(self.cache)
        self.assertEqual(len(result['removed']), 6)
        self.assertGreaterEqual(result['bytes'], 5000)
        for kept in (newest, other, sample, unfinished, running, log, self.cache / 'library' / 'pieces' / 'URB_Bar' / f'{A}-v23'):
            self.assertTrue(kept.exists(), kept)
        for gone in old + [twin, sample_old]:
            self.assertFalse(gone.exists(), gone)

    def test_one_map_and_what_a_server_serves(self):
        old = self.generation('URB_Bar', f'{A}-v22-map')
        self.generation('URB_Bar', f'{A}-v23-map')
        farm_old = self.generation('CsmallScout_Farm', f'{A}-v22-map')
        self.generation('CsmallScout_Farm', f'{A}-v23-map')
        self.assertEqual(prune.stale(self.cache, keep=[old]), [farm_old])
        self.assertEqual(prune.stale(self.cache, only=self.cache / 'URB_Bar'), [old])
        result = prune.prune(self.cache, dry_run=True)
        self.assertEqual(len(result['removed']), 2)
        self.assertTrue(old.exists() and farm_old.exists())


FAKE = """import json, pathlib, sys
root = pathlib.Path(sys.argv[1]) / 'Alpha' / ('%s-v23-map' % sys.argv[2])
root.mkdir(parents=True)
(root / 'scene.json').write_text(json.dumps(dict(schemaVersion=1, exporterVersion=23, name='Alpha', scope='map')))
print(json.dumps(dict(folder=str(root), counts={}, diagnostics=0), indent=2))
"""


class AfterAnExport(unittest.TestCase):
    """The main server's exporter (exports.ExportRunner with prune): once a Prepare publishes the new generation and
    the map serves it, the older ones go; another server's exporter deletes nothing."""
    def run_prepare(self, cache, prune_old):
        import json
        import time
        from exports import ExportRunner
        old = cache / 'Alpha' / ('%s-v22-map' % A)
        old.mkdir(parents=True)
        (old / 'scene.json').write_text(json.dumps(dict(schemaVersion=1, exporterVersion=22, name='Alpha', scope='map')),
                                        encoding='utf-8')
        script = cache.parent / 'fake_export.py'
        script.write_text(FAKE, encoding='utf-8', newline='\n')
        catalogue = dict(maps=dict(Alpha=dict(id='Alpha', label='Alpha', root=old, ready=True)))
        runner = ExportRunner(catalogue, cache, None, command=lambda package: [sys.executable, '-B', str(script), str(cache), A],
                              prune=prune_old)
        runner.package = lambda map_id: Path('Alpha.upk')
        runner.start('Alpha', prepare=True)
        for _ in range(200):
            if runner.job['state'] != 'running':
                break
            time.sleep(0.05)
        self.assertEqual(runner.job['state'], 'ready', runner.job)
        self.assertEqual(Path(catalogue['maps']['Alpha']['root']).name, '%s-v23-map' % A)
        return old, runner.job

    def test_the_main_servers_exporter_prunes(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'cache').mkdir()
            old, job = self.run_prepare(Path(tmp) / 'cache', True)
            self.assertFalse(old.exists())
            self.assertEqual(job['pruned'], [str(Path('Alpha') / ('%s-v22-map' % A))])

    def test_another_servers_exporter_keeps_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'cache').mkdir()
            old, job = self.run_prepare(Path(tmp) / 'cache', False)
            self.assertTrue(old.exists())
            self.assertNotIn('pruned', job)


if __name__ == '__main__':
    unittest.main()
