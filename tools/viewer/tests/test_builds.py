"""The editor's Build from the viewer's server (builds.py and its routes), with a stand-in for tools/editor/build.py."""
from functools import partial
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from builds import BuildRunner
from projects import ProjectError, ProjectStore
from test_projects import ID, OTHER, document
from viewer import Handler, LocalServer

# Stands in for build.py: prints its stage lines (as build.py does), waits for a go file, writes a package if asked.
STANDIN = r'''
import json, sys, time
from pathlib import Path
project, output, go, ok = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4] == 'ok'
quick = '--quick' in sys.argv[5:]
doc = json.loads(project.read_text(encoding='utf-8'))
print('snapshot: ' + json.dumps(dict(project=doc['id'], revision=doc['revision'])), flush=True)
print('compile: ' + json.dumps(dict(added=1)), flush=True)
if quick:
    print('  $ python -B -u native_copy.py URB_Bar.upk lit variant --copies native-edit.json', flush=True)
else:
    print('  $ pwsh -File patchtool.ps1 build', flush=True)
print('    progress: relighting 2/5', flush=True)
while not go.exists():
    time.sleep(0.02)
if not ok:
    print('build failed: patchtool.ps1 failed (exit 1); see the log', flush=True)
    sys.exit(1)
for s in ('patch', 'light', 'seeds'):
    print(s + ': {}', flush=True)
variant = doc['output']['shipAs']
(output / variant).mkdir(parents=True, exist_ok=True)
m = dict(buildId=variant + '-1', builtAt='2026-11-07T12:00:00', seconds=241, project=dict(id=doc['id'], revision=doc['revision']),
         files={'CookedPCConsole/%s.upk' % variant: 'x'})
if quick:       # a full build's manifest is written as before quick builds: no times, no quick
    m.update(quick=True, seconds=6, times=dict(full=241, quick=6), foreignPieces=2,
             donors=[dict(map='URB_PoliceStation', sha256='d' * 64, file='somewhere', pieces=2, bytes=1234, cut=[])])
(output / variant / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
print('built ' + variant, flush=True)
'''


class Builds(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.store = ProjectStore(root / 'projects')
        self.output, self.go = root / 'builds', root / 'go'
        self.output.mkdir()
        self.store.save(ID, document(output=dict(shipAs='URB_Bar_Remix_0f8b', patch='patch_urb_bar_remix_0f8b')), 0)
        self.store.save(OTHER, document(OTHER, output=dict(shipAs='URB_Bar_Other_1a2b', patch='patch_urb_bar_other_1a2b')), 0)
        script = root / 'standin.py'
        script.write_text(STANDIN, encoding='utf-8')
        self.outcome = 'ok'
        self.runner = BuildRunner(self.store, root / 'cache', self.output,
                                  command=lambda f: [sys.executable, '-u', str(script), str(f), str(self.output), str(self.go), self.outcome])

    def wait(self, project_id, state, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            s = self.runner.status(project_id)
            if s['state'] == state: return s
            time.sleep(0.05)
        self.fail(f'no {state}: {self.runner.status(project_id)}')

    def wait_stage(self, project_id, stage, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            s = self.runner.status(project_id)
            if s['job'] and s['job']['stage'] == stage: return s
            time.sleep(0.05)
        self.fail(f'no stage {stage}: {self.runner.status(project_id)}')

    def test_a_build_runs_to_a_package_and_one_at_a_time(self):
        self.assertEqual(self.runner.status(ID)['state'], 'idle')
        self.assertIsNone(self.runner.status(ID)['package'])
        started = self.runner.start(ID)
        self.assertEqual((started['state'], started['job']['revision']), ('running', 1))
        s = self.wait_stage(ID, 'compile')
        end = time.time() + 20
        while not s['job']['progress'] and time.time() < end:
            time.sleep(0.05); s = self.runner.status(ID)
        self.assertEqual(s['job']['running'], 'patch and cook')
        self.assertEqual([x['stage'] for x in s['job']['stages']], ['snapshot', 'compile'])
        self.assertTrue(all(x['at'] for x in s['job']['stages']))     # when each stage ended, for the page's times
        # a tool's progress lines set the job's progress and stay out of its lines
        self.assertEqual(s['job']['progress'], dict(what='relighting', done=2, total=5))
        self.assertFalse(any('progress:' in line for line in s['job']['lines']))
        with self.assertRaises(ProjectError) as error: self.runner.start(OTHER)
        self.assertEqual(error.exception.status, 409)
        self.assertTrue(self.runner.status(OTHER)['busy'])
        self.go.touch()
        s = self.wait(ID, 'built')
        self.assertEqual((s['package']['revision'], s['package']['seconds']), (1, 241))
        # a package from before quick builds: a full one, and its time the full build's
        self.assertEqual((s['job']['quick'], s['package']['quick'], s['package']['times']), (False, False, {'full': 241}))
        self.assertEqual((s['package']['foreignPieces'], s['package']['donors']), (0, []))
        self.assertIsNone(s['job']['progress'])          # the next stage line clears it
        self.assertEqual(s['package']['folder'], str(self.output / 'URB_Bar_Remix_0f8b'))
        self.assertEqual([x['stage'] for x in s['job']['stages']], ['snapshot', 'compile', 'patch', 'light', 'seeds'])
        # another project's package is not this one's
        self.assertIsNone(self.runner.status(OTHER)['package'])
        self.assertEqual(self.runner.start(OTHER)['state'], 'running')
        self.wait(OTHER, 'built')

    def test_a_quick_build_runs_build_py_quick(self):
        started = self.runner.start(ID, quick=True)
        self.assertTrue(started['job']['quick'])
        end = time.time() + 20
        s = self.runner.status(ID)
        while not s['job']['running'] and time.time() < end:
            time.sleep(0.05); s = self.runner.status(ID)
        # native_copy.py without --bake: the edit made in the map, no relighting
        self.assertEqual(s['job']['running'], 'making the edit in the map')
        self.go.touch()
        s = self.wait(ID, 'built')
        self.assertEqual((s['package']['quick'], s['package']['times']), (True, {'full': 241, 'quick': 6}))
        # its pieces of other maps and where they came from, without the donor's folder
        self.assertEqual((s['package']['foreignPieces'], s['package']['donors']),
                         (2, [dict(map='URB_PoliceStation', pieces=2, bytes=1234)]))

    def test_a_failed_build_says_why(self):
        self.outcome = 'fail'
        self.runner.start(ID)
        self.go.touch()
        s = self.wait(ID, 'failed')
        self.assertIn('patchtool.ps1 failed', s['job']['error'])
        self.assertIsNone(s['package'])

    def test_a_running_build_cancels_and_leaves_the_last_package(self):
        with self.assertRaises(ProjectError): self.runner.cancel(ID)          # nothing running
        self.runner.start(ID)
        self.wait_stage(ID, 'compile')
        self.runner.cancel(ID)
        s = self.wait(ID, 'cancelled')
        self.assertIn('Cancelled', s['job']['error'])
        self.assertIsNone(s['package'])
        # the next build starts as usual
        self.go.write_text('go')
        self.runner.start(ID)
        self.assertEqual(self.wait(ID, 'built')['package']['buildId'], 'URB_Bar_Remix_0f8b-1')

    def test_a_bug_report_zips_the_project_package_and_logs(self):
        import zipfile
        with self.assertRaises(ProjectError): self.runner.report(ID)          # never built
        self.go.write_text('go')
        self.runner.start(ID)
        self.wait(ID, 'built')
        logs = self.output / '.work' / 'URB_Bar_Remix_0f8b-20261108-120000' / 'logs'
        logs.mkdir(parents=True)
        (logs / 'native-copy.log').write_text('relit 3 components\n', encoding='utf-8')
        (logs.parent / 'compile-report.json').write_text('{}', encoding='utf-8')
        r = self.runner.report(ID)
        names = zipfile.ZipFile(r['zip']).namelist()
        self.assertEqual(Path(r['zip']).name, 'URB_Bar_Remix_0f8b-report.zip')
        for name in ('package/manifest.json', 'work/URB_Bar_Remix_0f8b-20261108-120000/logs/native-copy.log',
                     'work/URB_Bar_Remix_0f8b-20261108-120000/compile-report.json', 'report.json', 'build-output.txt'):
            self.assertIn(name, names)
        self.assertTrue(any(n.startswith('project/') for n in names))
        report = json.loads(zipfile.ZipFile(r['zip']).read('report.json'))
        self.assertEqual((report['variant'], report['build']['state']), ('URB_Bar_Remix_0f8b', 'built'))

    def test_the_routes_build_only_for_the_viewer_itself(self):
        catalogue = dict(defaultMap='URB_Bar', maps=dict(URB_Bar=dict(root=Path(self.temp.name))))
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=catalogue, projects=self.store, builds=self.runner))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            def call(method, path, origin=None, body=b'{}'):
                request = Request(base + path, method=method, data=body if method == 'POST' else None,
                                  headers={'Content-Type': 'application/json', **({'Origin': origin} if origin else {})})
                try:
                    with urlopen(request, timeout=10) as r: return r.status, json.loads(r.read())
                except HTTPError as e: return e.code, json.loads(e.read())
            self.assertEqual(call('GET', f'/projects/{ID}/build.json')[1]['state'], 'idle')
            self.assertEqual(call('POST', f'/projects/{ID}/build', origin='http://evil.example')[0], 403)
            # the page's Build and its first poll on one kept-alive connection: the POST's body is read, so the poll
            # isn't taken for a request named '{}GET'
            connection = HTTPConnection('127.0.0.1', server.server_port, timeout=10)
            connection.request('POST', f'/projects/{ID}/build', body=b'{}', headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            status, body = response.status, json.loads(response.read())
            self.assertEqual((status, body['state'], body['job']['quick']), (202, 'running', False))
            connection.request('GET', f'/projects/{ID}/build.json')
            response = connection.getresponse()
            self.assertEqual((response.status, json.loads(response.read())['state']), (200, 'running'))
            connection.close()
            self.assertEqual(call('POST', f'/projects/{OTHER}/build')[0], 409)
            self.assertEqual(call('POST', '/projects/not-a-uuid/build')[0], 404)
            self.go.touch()
            self.wait(ID, 'built')
            self.assertEqual(call('GET', f'/projects/{ID}/build.json')[1]['package']['revision'], 1)
            # {"quick": true}: a quick build; anything else asks for a full one
            status, body = call('POST', f'/projects/{ID}/build', body=b'{"quick": true}')
            self.assertEqual((status, body['job']['quick']), (202, True))
            self.assertTrue(self.wait(ID, 'built')['package']['quick'])
            status, body = call('POST', f'/projects/{ID}/build', body=b'{"quick": "yes"}')
            self.assertEqual((status, body['job']['quick']), (202, False))
            self.wait(ID, 'built')
            # a builds-folder path shown in Explorer: a folder opened, a file selected (never run); nothing outside
            shown = []
            self.runner.reveal_with = shown.append
            folder = self.output / 'URB_Bar_Remix_0f8b'
            zip_ = self.output / 'URB_Bar_Remix_0f8b-report.zip'
            zip_.write_bytes(b'zip')
            reveal = lambda path, **more: call('POST', '/builds/reveal', body=json.dumps(dict(path=path)).encode(), **more)  # noqa: E731
            self.assertEqual(reveal(str(folder))[0], 200)
            self.assertEqual(reveal(str(zip_))[0], 200)
            self.assertEqual(shown, [f'"{folder.resolve()}"', f'/select,"{zip_.resolve()}"'])
            self.assertEqual(reveal(self.temp.name)[0], 403)                                  # above the builds folder
            self.assertEqual(reveal(str(self.output / '..' / 'projects'))[0], 403)
            self.assertEqual(reveal(str(self.output / 'gone'))[0], 404)
            self.assertEqual(call('POST', '/builds/reveal', body=b'{}')[0], 400)
            self.assertEqual(reveal(str(folder), origin='http://evil.example')[0], 403)
            self.assertEqual(len(shown), 2)
            self.runner.reveal_with = None
            self.assertEqual(reveal(str(folder))[0], 501)                                     # no Explorer here
            # the package summary names no zip (builds make none)
            self.assertNotIn('zip', call('GET', f'/projects/{ID}/build.json')[1]['package'])
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
