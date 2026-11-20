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
            import json
            m = prune.GENERATION.match(name)
            (folder / 'scene.json').write_text(json.dumps(dict(schemaVersion=1, name=map_name, scope=m.group('scope'),
                                                               exporterVersion=int(m.group('version')))), encoding='utf-8')
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


SHA = A + '1' * 48


class OneChoice(unittest.TestCase):
    """The map list, the pruning and the Build agree on a usable generation (review finding 17): a newer generation
    whose scene.json is truncated, of another schema, of another package or of another version than its name says is
    passed over by all three, and the newest readable one is the one they keep and take."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name)
        self.stamp = 1_700_000_000

    def generation(self, name, version, text=None, sha=SHA):
        import json
        folder = self.cache / 'URB_Bar' / name
        folder.mkdir(parents=True)
        (folder / 'scene.json').write_text(text if text is not None else json.dumps(dict(
            schemaVersion=1, name='URB_Bar', scope='map', exporterVersion=version, source=dict(sha256=sha))),
            encoding='utf-8')
        self.stamp += 10
        os.utime(folder / 'scene.json', (self.stamp, self.stamp))
        return folder

    def test_catalogue_prune_and_build_pass_over_what_cant_be_used(self):
        sys.path.insert(0, str(HERE.parents[1] / 'editor'))
        import compiler
        from catalogue import load_catalogue
        old = self.generation(f'{A}-v34-map', 34)
        good = self.generation(f'{A}-v35-map', 35)
        twin = self.generation(f'{A}-v35-map-x1y2z3', 35)                  # an equal-version re-export, published beside
        broken = [self.generation(f'{A}-v36-map', 36, text='{"schemaVersion": 1, "name": "URB_B'),
                  self.generation(f'{A}-v37-map', 37, text='{"schemaVersion": 2, "name": "URB_Bar", "scope": "map", '
                                                           '"exporterVersion": 37}'),
                  self.generation(f'{A}-v38-map', 38, sha=B + '2' * 48),     # another package under this one's name
                  self.generation(f'{A}-v40-map', 39)]                       # another version than its name says
        doc = dict(source=dict(map='URB_Bar', sha256=SHA, exporterVersion=35))
        self.assertEqual(load_catalogue(self.cache)['maps']['URB_Bar']['root'], twin)
        self.assertEqual(compiler.find_export(self.cache, doc)[0].parent, twin)
        self.assertEqual(sorted(prune.stale(self.cache)), sorted([old, good]))
        # a generation a server serves (pinned) stays whatever its age
        self.assertEqual(prune.stale(self.cache, keep=[good]), [old])
        prune.prune(self.cache)
        for kept in [twin] + broken:
            self.assertTrue(kept.exists(), kept)
        self.assertEqual(load_catalogue(self.cache)['maps']['URB_Bar']['root'], twin)
        self.assertEqual(compiler.find_export(self.cache, doc)[0].parent, twin)


class ReuseLaunch(unittest.TestCase):
    """A second start of the main server while one runs (review finding 16) takes the port first: finding it held, it
    deletes nothing and reads nothing of the cache, so the running server's generation and a newer one both stay."""

    def test_a_reuse_launch_leaves_the_cache_alone(self):
        import json
        from functools import partial
        import threading
        from unittest import mock
        from urllib.request import urlopen
        from catalogue import load_catalogue
        import viewer
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            folders = {}
            for version in (22, 23):
                folder = folders[version] = cache / 'Alpha' / ('%s-v%d-map' % (A, version))
                folder.mkdir(parents=True)
                (folder / 'scene.json').write_text(json.dumps(dict(schemaVersion=1, exporterVersion=version, name='Alpha',
                                                                   scope='map')), encoding='utf-8')
            running = viewer.LocalServer(('127.0.0.1', 0), partial(viewer.Handler, catalogue=load_catalogue(folders[22])))
            thread = threading.Thread(target=running.serve_forever, daemon=True)
            thread.start()
            try:
                port = running.server_port
                for extra in (['--reuse'], []):
                    argv = ['viewer.py', 'serve', str(cache), '--port', str(port), '--no-open'] + extra
                    with mock.patch.object(viewer, 'MAIN_PORT', port), mock.patch.object(sys, 'argv', argv), \
                            mock.patch.object(prune, 'prune', side_effect=AssertionError('pruned')), \
                            mock.patch.object(viewer, 'load_catalogue', side_effect=AssertionError('catalogue read')):
                        if extra:
                            viewer.main()
                        else:
                            with self.assertRaises(SystemExit):
                                viewer.main()
                    self.assertTrue(folders[22].exists() and folders[23].exists())
                with urlopen(f'http://127.0.0.1:{port}/cache/scene.json', timeout=10) as response:
                    self.assertEqual(json.load(response)['exporterVersion'], 22)
            finally:
                running.shutdown()
                running.server_close()
                thread.join(timeout=5)


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
