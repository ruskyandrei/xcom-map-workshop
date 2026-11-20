"""The editor's Build from the viewer's server (builds.py and its routes), with a stand-in for tools/editor/build.py:
attempts with their own ids, contained process trees drained before a build ends, package swaps settled after a build
dies between its renames, a restarted server's old writers proved gone, and the slot shared with the build queue's
reservation and readers' leases (build queue plan, Q0)."""
from functools import partial
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import builds as builds_module
from builds import BuildRunner
import procs
import publication
from projects import ProjectError, ProjectStore
from viewer_fixtures import ID, OTHER, document
from viewer import Handler, LocalServer

VIEWER = str(Path(__file__).resolve().parents[1])
# Stands in for build.py: prints its stage lines (as build.py does), waits for a go file, then writes a package as
# build.py does (its id unique to the launch, the attempt in its manifest, swapped in with the journal) and prints the
# real success line. Outcomes: ok; fail; grand (a grandchild that waits, its id printed); linger (a grandchild left
# running after a good build); die-<step> (the process ends outright after that step of the swap).
STANDIN = r'''
import datetime, hashlib, json, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, %r)
import publication
project, output, go, outcome = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
rest = sys.argv[5:]
quick = '--quick' in rest
attempt = rest[rest.index('--attempt') + 1] if '--attempt' in rest else None
doc = json.loads(project.read_text(encoding='utf-8'))
print('snapshot: ' + json.dumps(dict(project=doc['id'], revision=doc['revision'])), flush=True)
print('compile: ' + json.dumps(dict(added=1)), flush=True)
if outcome in ('grand', 'linger'):
    grand = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
    print('grandchild: %%d' %% grand.pid, flush=True)
if quick:
    print('  $ python -B -u native_copy.py URB_Bar.upk lit variant --copies native-edit.json', flush=True)
else:
    print('  $ pwsh -File patchtool.ps1 build', flush=True)
print('    progress: relighting 2/5', flush=True)
while not go.exists():
    time.sleep(0.02)
if outcome == 'fail':
    print('build failed: patchtool.ps1 failed (exit 1); see the log', flush=True)
    sys.exit(1)
for s in ('patch', 'light', 'seeds'):
    print(s + ': {}', flush=True)
variant = doc['output']['shipAs']
stamp = datetime.datetime.now().strftime('%%Y%%m%%d-%%H%%M%%S') + ('-' + attempt.replace('-', '')[:8] if attempt else '')
build_id = '%%s-%%s' %% (variant, stamp)
staging = output / '.work' / build_id / 'package'
(staging / 'CookedPCConsole').mkdir(parents=True)
content = ('%%s revision %%s' %% (build_id, doc['revision'])).encode()
(staging / 'CookedPCConsole' / ('%%s.upk' %% variant)).write_bytes(content)
m = dict(schema='xcom-map-workshop/variant-package', schemaVersion=1, buildId=build_id, builtAt='2026-11-07T12:00:00',
         seconds=241, project=dict(id=doc['id'], revision=doc['revision']), variant=variant,
         files={'CookedPCConsole/%%s.upk' %% variant: hashlib.sha256(content).hexdigest()},
         **({'attempt': attempt} if attempt else {}))
if quick:       # a full build's manifest is written as before quick builds: no times, no quick
    m.update(quick=True, seconds=6, times=dict(full=241, quick=6), foreignPieces=2,
             donors=[dict(map='URB_PoliceStation', sha256='d' * 64, file='somewhere', pieces=2, bytes=1234, cut=[])])
(staging / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
die = outcome[4:] if outcome.startswith('die-') else None
existing = output / variant if (output / variant).is_dir() else None
with publication.guard(output, variant):
    publication.publish(output, variant, staging, existing, dict(buildId=build_id, attempt=attempt, project=doc['id']),
                        boundary=lambda name: os._exit(70) if name == die else None)
print('built %%s: %%s (%%s.upk %%s)' %% (build_id, output / variant, variant, hashlib.sha256(content).hexdigest()[:12]), flush=True)
''' % VIEWER


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

    def grandchild(self, timeout=20):
        """The id and identity of the stand-in's grandchild, from its line."""
        end = time.time() + timeout
        while time.time() < end:
            job = self.runner.job
            line = next((l for l in (job or {}).get('lines', []) if l.startswith('grandchild: ')), None)
            if line:
                pid = int(line.split(': ')[1])
                return pid, procs.identity(pid)
            time.sleep(0.05)
        self.fail('no grandchild')

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
        # the launch's own id: in the job, in the build's id and in the manifest; the job is plain JSON
        attempt = s['job']['attempt']
        self.assertEqual(s['job']['origin'], 'foreground')
        self.assertTrue(s['package']['buildId'].endswith('-' + attempt.replace('-', '')[:8]))
        self.assertEqual(s['job']['buildId'], s['package']['buildId'])
        json.dumps(s)
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
        self.assertEqual((s['package']['foreignPieces'], s['package']['foreignEffects'], s['package']['donors']),
                         (2, 0, [dict(map='URB_PoliceStation', pieces=2, effects=None, bytes=1234)]))

    def test_a_build_reads_the_project_and_its_picture_as_captured(self):
        """(review finding 12) The editor's Build captures the saved project, and the picture it names, into an attempt
        folder before build.py starts, as the build queue does: a save under another name and two new pictures after
        the capture change nothing of the build, and the job, the package and the bug report name the same bytes. A
        retry after Cancel captures again."""
        import hashlib
        import io
        import zipfile
        from PIL import Image
        import pictures

        def png(colour):
            out = io.BytesIO()
            Image.new('RGB', (512, 256), colour).save(out, 'PNG')
            return out.getvalue()
        first = pictures.save_picture(self.store, ID, png((10, 20, 30)))['sha256']
        doc = self.store.load(ID)
        self.store.save(ID, dict(doc, picture=dict(sha256=first)), doc['revision'])
        job = self.runner.start(ID)['job']
        snapshot = Path(job['snapshot'])
        captured = snapshot.read_bytes()
        self.assertEqual(snapshot.parent.parent, self.output / '.work' / 'queue-attempts')
        self.assertEqual(snapshot.parent.name, job['attempt'])
        self.assertEqual((job['revision'], job['digest'], job['picture']), (2, hashlib.sha256(captured).hexdigest(), first))
        self.assertEqual(pictures.sha256(pictures.beside(snapshot).read_bytes()), first)
        own = self.store.path(ID)
        for colour in ((200, 0, 0), (0, 200, 0)):     # the first picture is then kept nowhere but in the snapshot
            now = self.store.load(ID)
            digest = pictures.save_picture(self.store, ID, png(colour), saved=(now.get('picture') or {}).get('sha256'))['sha256']
            self.store.save(ID, dict(now, name='Renamed remix', picture=dict(sha256=digest)), now['revision'])
        self.assertNotEqual(self.store.path(ID), own)
        self.assertIsNone(pictures.picture_file(self.store, ID, first))
        self.go.touch()
        s = self.wait(ID, 'built')
        self.assertEqual((snapshot.read_bytes(), s['package']['revision']), (captured, 2))
        self.assertEqual(pictures.sha256(pictures.beside(snapshot).read_bytes()), first)
        # the bug report carries the snapshot and names its bytes
        r = self.runner.report(ID)
        z = zipfile.ZipFile(r['zip'])
        self.assertEqual(z.read('project/project.json'), captured)
        self.assertEqual(json.loads(z.read('report.json'))['build']['digest'], job['digest'])
        # a retry after a cancel captures the latest save, into a folder of its own
        self.go.unlink()
        self.runner.start(ID)
        self.runner.cancel(ID)
        self.wait(ID, 'cancelled')
        self.go.touch()
        again = self.runner.start(ID)['job']
        self.assertEqual(again['revision'], 4)
        self.assertNotEqual(again['snapshot'], job['snapshot'])
        self.assertEqual(again['picture'], digest)
        self.wait(ID, 'built')

    def test_a_tools_indented_warning_is_a_warning_of_the_build(self):
        """(review finding 15) build.py echoes a tool's lines indented under its command line: the relight's warning
        that its writes changed pieces it didn't relight is found there too, not only at a line's start."""
        job = dict(lines=[], stages=[], stage=None, running=None, progress=None, error=None)
        self.runner._line(job, 'warning: the package swap left a note')
        self.runner._line(job, '        warning: writing the lighting changed 37 texels (by up to 0.21) in the lightmaps '
                               'of 2 pieces that were not relit: A, B')
        self.runner._line(job, '    the word warning: in the middle is no warning')
        self.assertEqual(job['warnings'], ['the package swap left a note',
                                           'writing the lighting changed 37 texels (by up to 0.21) in the lightmaps of 2 '
                                           'pieces that were not relit: A, B'])

    def test_a_failure_with_a_code_keeps_it_for_the_page(self):
        """(review finding 55) build.py's "build failed code:" line is kept as the job's errorCode, which the page's
        Prepare prompt goes by; the reason is still the job's error."""
        job = dict(lines=[], stages=[], stage=None, running=None, progress=None, error=None, errorCode=None)
        self.runner._line(job, 'build failed code: export-missing')
        self.runner._line(job, 'build failed: no export of URB_Bar with SHA-256 ...: prepare the map')
        self.assertEqual((job['errorCode'], job['error']), ('export-missing', 'no export of URB_Bar with SHA-256 ...: prepare the map'))

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
        self.assertTrue(self.wait(ID, 'built')['package']['buildId'].startswith('URB_Bar_Remix_0f8b-'))

    def test_a_bug_report_zips_the_project_package_and_logs(self):
        import zipfile
        with self.assertRaises(ProjectError): self.runner.report(ID)          # never built
        self.go.write_text('go')
        self.runner.start(ID)
        s = self.wait(ID, 'built')
        # the build's own work folder (its attempt in its name), though a later-dated one is there
        own = s['job']['buildId']
        for name in (own, 'URB_Bar_Remix_0f8b-20991108-120000'):
            logs = self.output / '.work' / name / 'logs'
            logs.mkdir(parents=True)
            (logs / 'native-copy.log').write_text('relit 3 components\n', encoding='utf-8')
            (logs.parent / 'compile-report.json').write_text('{}', encoding='utf-8')
        r = self.runner.report(ID)
        names = zipfile.ZipFile(r['zip']).namelist()
        self.assertEqual(Path(r['zip']).name, 'URB_Bar_Remix_0f8b-report.zip')
        for name in ('package/manifest.json', f'work/{own}/logs/native-copy.log',
                     f'work/{own}/compile-report.json', 'report.json', 'build-output.txt'):
            self.assertIn(name, names)
        self.assertFalse(any('20991108' in n for n in names))
        self.assertTrue(any(n.startswith('project/') for n in names))
        report = json.loads(zipfile.ZipFile(r['zip']).read('report.json'))
        self.assertEqual((report['variant'], report['build']['state']), ('URB_Bar_Remix_0f8b', 'built'))
        self.assertEqual(sorted(r['files']), sorted(names))         # the answer names what the zip holds
        # a file over the limit is left out of the zip, and the answer says so instead of listing it (review finding 44)
        (self.output / '.work' / own / 'logs' / 'relight.log').write_text('x' * 100000, encoding='utf-8')
        with mock.patch.object(builds_module, 'REPORT_FILE_MAX', 50000):
            r = self.runner.report(ID)
        names = zipfile.ZipFile(r['zip']).namelist()
        self.assertNotIn(f'work/{own}/logs/relight.log', names + r['files'])
        self.assertEqual(r['leftOut'], [f'work/{own}/logs/relight.log'])
        self.assertEqual(sorted(r['files']), sorted(names))
        self.assertEqual(json.loads(zipfile.ZipFile(r['zip']).read('report.json'))['leftOut'], r['leftOut'])
        self.assertFalse((self.output / 'URB_Bar_Remix_0f8b-report.zip.tmp').exists())

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

    # ------------------------------------------------------------------ attempts (build queue plan, Q0)

    def test_two_builds_in_one_second_have_their_own_ids(self):
        self.go.touch()
        first = self.runner._start(self.store.load(ID), self.runner.command(self.store.path(ID)), False)
        first.done.wait(20)
        second = self.runner._start(self.store.load(ID), self.runner.command(self.store.path(ID)), False)
        second.done.wait(20)
        self.assertNotEqual(first.id, second.id)
        self.assertNotEqual(first.job['buildId'], second.job['buildId'])
        self.assertEqual(json.loads((self.output / 'URB_Bar_Remix_0f8b' / 'manifest.json').read_text())['attempt'], second.id)
        # the runner knows its own package by the attempt, not by a later date
        self.assertIsNotNone(self.runner.verify(second, 1))
        self.assertIsNone(self.runner.verify(first, 1))
        self.assertIsNone(self.runner.verify(second, 2))                # another revision
        self.assertIsNone(self.runner.verify(second, 1, full=False))    # it is a full build

    def test_a_stale_cancel_never_stops_a_newer_build(self):
        self.go.touch()
        old = self.runner._start(self.store.load(ID), self.runner.command(self.store.path(ID)), False)
        old.done.wait(20)
        with self.assertRaises(ProjectError): self.runner.stop(ID, old.id)       # it has ended: nothing to stop
        self.go.unlink()
        new = self.runner._start(self.store.load(ID), self.runner.command(self.store.path(ID)), False)
        with self.assertRaises(ProjectError) as error: self.runner.cancel(ID, old.id)
        self.assertEqual(error.exception.extra.get('code'), 'stale-attempt')
        self.assertFalse(self.runner.stop_attempt(old.id))
        self.assertEqual(self.runner.status(ID)['state'], 'running')
        self.runner.cancel(ID, new.id)
        self.assertTrue(new.done.wait(20))
        self.assertEqual(new.job['state'], 'cancelled')

    def test_cancel_ends_every_process_of_the_build_before_it_ends(self):
        self.outcome = 'grand'
        attempt = self.runner._start(self.store.load(ID), self.runner.command(self.store.path(ID)), False)
        grand, born = self.grandchild()
        self.assertIsNotNone(born)
        self.runner.cancel(ID)
        self.assertTrue(attempt.done.wait(30))
        # ended only once its grandchild had: no process of it is left
        self.assertNotEqual(procs.identity(grand), born)
        self.assertEqual(attempt.job['state'], 'cancelled')
        self.assertFalse(list((self.output / '.work' / 'writers').glob('*.json')))

    def test_a_good_build_waits_for_its_leftover_processes(self):
        saved = builds_module.DRAIN_GRACE
        builds_module.DRAIN_GRACE = 0.5
        self.addCleanup(setattr, builds_module, 'DRAIN_GRACE', saved)
        self.outcome = 'linger'
        self.go.touch()
        attempt = self.runner._start(self.store.load(ID), self.runner.command(self.store.path(ID)), False)
        grand, born = self.grandchild()
        self.assertTrue(attempt.done.wait(30))
        self.assertNotEqual(procs.identity(grand), born)
        self.assertEqual(attempt.job['state'], 'built')

    def test_a_prefab_tests_pinned_build_is_contained_too(self):
        self.outcome = 'grand'
        private = Path(self.temp.name) / 'pinned' / 'project.json'
        private.parent.mkdir()
        private.write_text(json.dumps(self.store.load(ID)), encoding='utf-8')
        self.runner.pinned_command = lambda document, output, game, udk: self.runner.command(document)
        job = self.runner.start_pinned(private, private.parent / 'artifacts', 'game', None, False, lambda pid: None)
        self.assertEqual(job['origin'], 'prefab')
        grand, born = self.grandchild()
        self.runner.stop(ID)
        end = time.time() + 30
        while self.runner.pinned_status(job)['state'] == 'running' and time.time() < end:
            time.sleep(0.05)
        self.assertEqual(self.runner.pinned_status(job)['state'], 'cancelled')
        self.assertNotEqual(procs.identity(grand), born)

    def test_a_build_that_dies_between_its_renames_leaves_the_last_package(self):
        self.go.touch()
        first = self.runner._start(self.store.load(ID), self.runner.command(self.store.path(ID)), False)
        first.done.wait(20)
        for step, kept in (('old-aside', first.job['buildId']), ('new-in-place', None)):
            with self.subTest(step=step):
                self.outcome = 'die-' + step
                attempt = self.runner._start(self.store.load(ID), self.runner.command(self.store.path(ID)), False)
                self.assertTrue(attempt.done.wait(30))
                self.assertEqual(attempt.job['state'], 'failed')
                self.assertEqual(publication.pending(self.output), [])           # settled before the build ended
                built = json.loads((self.output / 'URB_Bar_Remix_0f8b' / 'manifest.json').read_text())
                if kept:
                    self.assertEqual(built['buildId'], kept)
                else:       # the new one was wholly in place: kept, though its build never said so
                    self.assertEqual(built['attempt'], attempt.id)
                    self.assertIsNotNone(self.runner.verify(attempt, 1))

    def test_a_failure_to_launch_leaves_the_slot_free(self):
        def broken(*args, **kwargs):
            raise OSError('no such program')
        runner = BuildRunner(self.store, Path(self.temp.name) / 'cache', self.output, command=self.runner.command, launch=broken)
        with self.assertRaises(OSError): runner.start(ID)
        self.assertIsNone(runner.busy())
        self.assertEqual(runner.status(ID)['state'], 'idle')

    def test_a_follower_fault_still_ends_the_build(self):
        real = self.runner._line
        calls = []

        def faulty(job, line):
            calls.append(line)
            if len(calls) == 2: raise RuntimeError('parser broke')
            real(job, line)
        self.runner._line = faulty
        self.go.touch()
        attempt = self.runner._start(self.store.load(ID), self.runner.command(self.store.path(ID)), False)
        self.assertTrue(attempt.done.wait(30))
        self.assertEqual(attempt.job['state'], 'failed')
        self.assertIn('parser broke', attempt.job['error'])
        self.assertIsNone(self.runner.busy())

    def test_a_restarted_server_waits_for_an_earlier_servers_builds(self):
        writers = self.output / '.work' / 'writers'
        writers.mkdir(parents=True)
        alive = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        self.addCleanup(lambda: (alive.kill(), alive.wait()))
        born = procs.identity(alive.pid)
        (writers / 'a.json').write_text(json.dumps(dict(attempt='a', pid=alive.pid, created=born, name='Old build')))
        (writers / 'b.json').write_text(json.dumps(dict(attempt='b', pid=alive.pid, created=born + 1, name='Gone')))
        (writers / 'c.json').write_text(json.dumps(dict(attempt='c', pid=None, name='Never recorded')))
        runner = BuildRunner(self.store, Path(self.temp.name) / 'cache', self.output, command=self.runner.command)
        runner.recover()
        self.assertEqual(runner.busy(), ('a', 'Old build'))
        with self.assertRaises(ProjectError) as error: runner.start(ID)
        self.assertEqual(error.exception.extra.get('code'), 'build-slot')
        self.assertEqual(sorted(p.name for p in writers.iterdir()), ['a.json'])     # the gone ones' records dropped
        alive.kill(); alive.wait()
        end = time.time() + 15
        while runner.busy() and time.time() < end: time.sleep(0.1)
        self.assertIsNone(runner.busy())
        self.assertFalse((writers / 'a.json').exists())
        # an unreadable record is a writer of unknown state: the slot stays busy, with the reason
        (writers / 'd.json').write_text('{')
        runner = BuildRunner(self.store, Path(self.temp.name) / 'cache', self.output, command=self.runner.command)
        runner.recover()
        self.assertIn('can\'t be read', runner.busy()[1])

    def work_folder(self, name):
        """A build's work folder in the builds folder, as build.py leaves one: heavy work, logs and small records."""
        folder = self.output / '.work' / name
        (folder / 'lit').mkdir(parents=True)
        (folder / 'lit' / 'URB_Bar.upk').write_bytes(b'x' * 10)
        (folder / 'logs').mkdir()
        (folder / 'logs' / 'build.log').write_text('log')
        (folder / 'compile-report.json').write_text('{}')
        (folder / 'arrays.bin').write_bytes(bytes(builds_module.SMALL_FILE + 1))
        return folder

    def kept_pieces(self, variant, days):
        """A variant's kept pieces (relight.py PieceCache), last written `days` ago."""
        folder = self.output / '.work' / 'pieces' / variant
        folder.mkdir(parents=True)
        (folder / 'piece.npz').write_bytes(b'kept')
        then = time.time() - days * builds_module.DAY
        os.utime(folder / 'piece.npz', (then, then))
        os.utime(folder, (then, then))
        return folder

    def test_old_work_is_pruned_as_the_server_starts(self):
        """(review findings 49 and 62) As the server starts (recover), the builds folder's old work is pruned beside
        it: a variant a project ships as keeps its three newest work folders whole and older ones keep their logs and
        small records; a variant no project ships as keeps none whole once its last build is ORPHAN_DAYS old (one
        built since is left); kept pieces unused for PIECE_DAYS go (ORPHAN_DAYS for a variant none ships as), those
        of a variant built since stay; the rest of the work folder is left."""
        import datetime
        today = datetime.datetime.now()

        def stamp(days):
            return (today - datetime.timedelta(days=days)).strftime('%Y%m%d-%H%M%S')
        owned = [self.work_folder('URB_Bar_Remix_0f8b-%s' % stamp(days)) for days in (40, 30, 20, 10)]
        gone = [self.work_folder('Deleted_Project-%s-0123abcd' % stamp(days)) for days in (20, 15)]
        recent = self.work_folder('Saved_Elsewhere-%s' % stamp(1))
        (self.output / '.work' / 'patchtool').mkdir()
        (self.output / '.work' / 'patchtool' / 'cooked.bin').write_bytes(bytes(builds_module.SMALL_FILE + 1))
        late = builds_module.PIECE_DAYS + 1
        unused = self.kept_pieces('URB_Bar_Other_1a2b', late)
        built_since = self.kept_pieces('URB_Bar_Remix_0f8b', late)
        gone_pieces = self.kept_pieces('Deleted_Project', builds_module.ORPHAN_DAYS + 1)
        recent_pieces = self.kept_pieces('Saved_Elsewhere', builds_module.ORPHAN_DAYS + 1)
        runner = BuildRunner(self.store, Path(self.temp.name) / 'cache', self.output, command=self.runner.command)
        with mock.patch('builtins.print') as said:
            runner.recover()
            runner.pruner.join(30)
        stripped = ['compile-report.json', 'logs']
        self.assertEqual(sorted(f.name for f in owned[0].iterdir()), stripped)
        self.assertTrue((owned[0] / 'logs' / 'build.log').is_file())
        for folder in owned[1:]:
            self.assertTrue((folder / 'lit' / 'URB_Bar.upk').is_file() and (folder / 'arrays.bin').is_file())
        for folder in gone:
            self.assertEqual(sorted(f.name for f in folder.iterdir()), stripped)
        self.assertTrue((recent / 'arrays.bin').is_file())
        self.assertTrue((self.output / '.work' / 'patchtool' / 'cooked.bin').is_file())
        self.assertEqual([p.exists() for p in (unused, built_since, gone_pieces, recent_pieces)], [False, True, False, True])
        self.assertIn('3 work folders, 2 sets of kept pieces', said.call_args[0][0])
        self.assertEqual(runner.prune(), dict(freed=0, folders=0, pieces=0))     # nothing more to do

    def test_a_server_whose_projects_are_not_the_builds_own_takes_no_variant_for_abandoned(self):
        """A test server given scratch projects beside the real builds folder (viewer.py serve --projects alone)
        prunes with no projects known: a variant none of its projects ships as keeps its newest work folders whole."""
        import datetime
        old = (datetime.datetime.now() - datetime.timedelta(days=builds_module.ORPHAN_DAYS + 5)).strftime('%Y%m%d-%H%M%S')
        real = self.work_folder('Real_Users_Variant-%s' % old)
        runner = BuildRunner(self.store, Path(self.temp.name) / 'cache', self.output, command=self.runner.command,
                             orphans=False)
        self.assertEqual(runner.prune()['folders'], 0)
        self.assertTrue((real / 'arrays.bin').is_file())

    def test_pruning_spares_a_running_builds_work_and_needs_the_projects_for_a_variant_none_ships_as(self):
        """(review finding 49) prune_work leaves the folders it is told to spare; with no projects known (build.py's
        own prune) a variant alone keeps its newest; an unreadable projects folder is no projects known."""
        import datetime
        old = (datetime.datetime.now() - datetime.timedelta(days=builds_module.ORPHAN_DAYS + 5)).strftime('%Y%m%d-%H%M%S')
        folder = self.work_folder('Nobodys_Variant-%s' % old)
        self.assertEqual(builds_module.prune_work(self.output)['folders'], 0)
        self.assertEqual(builds_module.prune_work(self.output, owned=set(), spare=[folder])['folders'], 0)
        self.assertTrue((folder / 'arrays.bin').is_file())
        self.assertEqual(builds_module.prune_work(self.output, owned=set())['folders'], 1)
        self.assertEqual(sorted(f.name for f in folder.iterdir()), ['compile-report.json', 'logs'])
        self.assertEqual(builds_module.owned_variants(self.store.root), {'urb_bar_remix_0f8b', 'urb_bar_other_1a2b'})
        self.assertIsNone(builds_module.owned_variants(Path(self.temp.name) / 'no projects here'))
        (self.store.root / 'not a project.json').write_text('{', encoding='utf-8')
        self.assertEqual(len(builds_module.owned_variants(self.store.root)), 2)

    def test_a_journal_that_cannot_be_settled_blocks_that_projects_builds(self):
        folder = publication.journals(self.output)
        folder.mkdir(parents=True)
        publication.journal_path(self.output, 'URB_Bar_Remix_0f8b').write_text('not json', encoding='utf-8')
        runner = BuildRunner(self.store, Path(self.temp.name) / 'cache', self.output, command=self.runner.command)
        runner.recover()
        with self.assertRaises(ProjectError) as error: runner.start(ID)
        self.assertEqual(error.exception.extra.get('code'), 'output-blocked')
        self.assertIn('blocked', runner.status(ID))
        self.go.touch()
        self.assertEqual(runner.start(OTHER)['state'], 'running')                # another project builds
        self.assertTrue(runner.attempt.done.wait(20))

    def test_the_queue_reserves_the_slot_and_readers_lease_packages(self):
        self.runner.reserve('queue-1', 'The build queue')
        with self.assertRaises(ProjectError) as error: self.runner.start(ID)
        self.assertEqual((error.exception.extra.get('code'), error.exception.extra.get('queue')), ('build-slot', True))
        self.assertIsNone(self.runner.busy('queue-1'))      # not busy for the queue itself
        with self.assertRaises(ProjectError): self.runner.reserve('queue-2', 'Another')
        self.runner.release('queue-2')                      # not its reservation: nothing changes
        self.assertIsNotNone(self.runner.busy())
        self.runner.release('queue-1')
        self.assertIsNone(self.runner.busy())
        with self.runner.lease([ID]) as active:
            self.assertEqual(active, set())
            with self.assertRaises(ProjectError) as error: self.runner.start(ID)
            self.assertEqual(error.exception.extra.get('code'), 'package-in-use')
            self.assertFalse(self.runner.claim(ID, 'queue-1'))          # the queue waits for the reader
        self.assertTrue(self.runner.claim(ID, 'queue-1'))
        self.assertEqual(self.runner.active_projects(), {ID})
        with self.runner.lease([ID, OTHER]) as active:
            self.assertEqual(active, {ID})                  # about to be built: left out by the reader
        self.runner.unclaim(ID, 'queue-1')
        self.assertEqual(self.runner.active_projects(), set())


if __name__ == '__main__':
    unittest.main()
