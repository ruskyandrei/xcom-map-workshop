"""T2 service, shared runner, private packages and play/install lifecycle."""
from functools import partial
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gamelaunch
import installs
from builds import BuildRunner
from prefab_tests import PrefabTests, read, stage, write
from play import Player
from projects import ProjectError, ProjectStore
from viewer import Handler, LocalServer
import test_play
from test_prefabs import prefab
from viewer_fixtures import document

BUILDER = """
from pathlib import Path
import hashlib, json, sys, time
project, output, gate = map(Path, sys.argv[1:4])
doc = json.loads(project.read_text(encoding='utf8'))
variant = doc['output']['shipAs']
print('compile: {}', flush=True)
while not gate.exists():
    time.sleep(.02)
data = b'private test map'
relative = 'CookedPCConsole/' + variant + '.upk'
folder = output / variant
(folder / relative).parent.mkdir(parents=True)
(folder / relative).write_bytes(data)
m = dict(schema='xcom-map-workshop/variant-package', buildId=variant+'-fresh', variant=variant,
         project=dict(id=doc['id'], name=doc['name'], revision=doc['revision']),
         source=doc['source'], prefabTest=doc['prefabTest'], quick='--quick' in sys.argv,
         files={relative: hashlib.sha256(data).hexdigest()})
(folder / 'manifest.json').write_text(json.dumps(m), encoding='utf8')
if gate.read_text() == 'fail':
    sys.exit(1)
print('built '+m['buildId']+': '+str(folder), flush=True)
"""


def uuid():
    return str(uuid4())


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.game = self.root / 'Game'
        test_play.game_folder(self.game, test_play.dep.set_field(test_play.record('bar'), 'Name', stage.MAP))
        self.maps = installs.config(self.game, 'DefaultMaps.ini')
        self.maps_before = self.maps.read_bytes()
        self.base = installs.cooked(self.game) / f'{stage.MAP}.upk'
        self.base.write_bytes(b'blank')
        self.donor = installs.cooked(self.game) / 'Donor.upk'
        self.donor.write_bytes(b'donor')
        self.running = False
        check = patch.object(installs, 'game_running', side_effect=lambda: self.running)
        check.start()
        self.addCleanup(check.stop)
        self.script, self.gate = self.root / 'builder.py', self.root / 'go'
        self.script.write_text(BUILDER, encoding='utf8')
        self.store = ProjectStore(self.root / 'projects')
        self.builds = BuildRunner(self.store, self.root / 'cache', self.root / 'builds',
                                  command=lambda _: [sys.executable, '-c', 'import time; time.sleep(60)'])
        self.builds.pinned_command = lambda doc, output, *_: [
            sys.executable, '-u', str(self.script), str(doc), str(output), str(self.gate)]
        self.launches = []
        self.settings = dict(game=self.game, install=None, udk=None)
        self.player = Player(self.settings, self.builds, install=self.game, appear=.1, every=.01, cleanup=False,
                             command=lambda *_: ([], None, 'dry'),
                             start=lambda *args: self.launches.append(args), user_documents=self.root / 'documents')
        self.live = SimpleNamespace(player=self.player, exports=None)
        self.tests = PrefabTests(self.builds, self.live, prepare=self.prepare, process_active=lambda _: False)
        self.addCleanup(self.stop_build)

    def stop_build(self):
        if busy := self.builds.busy():
            self.builds.stop(busy[0])
            end = time.monotonic() + 4
            while self.builds.busy() and time.monotonic() < end:
                time.sleep(.02)

    def prepare(self, snapshot, test, cache, game):
        return dict(project=dict(id=test, revision=1, name=snapshot['name'],
                                 output=dict(shipAs='Test_' + test.replace('-', '')[:20]),
                                 source=dict(map=stage.MAP, sha256=installs.sha256(self.base),
                                             exporterVersion=stage.EXPORT_VERSION)),
                    donors={'Donor': installs.sha256(self.donor)}, size=dict(tiles=[2, 3]),
                    placement=dict(grid=[36, 36]), report=dict(warnings=[]))

    def request(self, **options):
        doc = prefab(pieces=[], groups=[])
        return dict(dict(snapshot=doc, requestId=uuid(), unsaved=True), **options)

    def wait(self, test, phase):
        end = time.monotonic() + 10
        while time.monotonic() < end:
            result = self.tests.status(test)
            if result['phase'] == phase:
                return result
            if result['phase'] == 'failed' and phase != 'failed':
                self.fail(str(result))
            time.sleep(.02)
        self.fail(str(self.tests.status(test)))

    def ready(self, outcome='ok'):
        result = self.tests.start(self.request())
        self.gate.write_text(outcome)
        return self.wait(result['id'], 'ready' if outcome == 'ok' else 'failed')

    def assert_code(self, code, action):
        with self.assertRaises(ProjectError) as caught:
            action()
        self.assertEqual(caught.exception.extra['code'], code)

    def test_routes_require_a_complete_snapshot_and_are_same_origin(self):
        server = LocalServer(('127.0.0.1', 0), partial(Handler, prefab_tests=self.tests))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            def call(path, body=None, **headers):
                request = Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                  headers={'Content-Type': 'application/json', **headers})
                try:
                    with urlopen(request) as answer:
                        return answer.status, json.load(answer)
                except HTTPError as error:
                    return error.code, json.load(error)
            request = self.request(quick=True)
            self.assertEqual(call('/prefab-tests', request, Origin='http://elsewhere')[0], 403)
            self.assertEqual(call('/prefab-tests', dict(prefab=request['snapshot']['id']))[0], 400)
            self.assertEqual(call('/prefab-tests/invalid.json')[0], 404)
            # the builder's check: the prepare step alone, nothing built, no test started
            self.assertEqual(call('/prefab-tests/check', dict(snapshot=request['snapshot']), Origin='http://elsewhere')[0], 403)
            self.assertEqual(call('/prefab-tests/check', dict(document=1))[0], 400)
            self.assertEqual(call('/prefab-tests/check', dict(snapshot=request['snapshot'])),
                             (200, dict(ready=True, refused=None, issues=[], leftOut=0, stage=None)))
            self.assertIsNone(self.builds.busy())
            status, job = call('/prefab-tests', request, Origin=base)
            self.assertEqual(status, 202)
            test = job['id']
            self.assertEqual(call('/prefab-tests', request)[1]['id'], test)
            self.assertEqual(call('/prefab-tests', dict(request, quick=False))[0], 409)
            self.assertEqual(call(f'/prefab-tests/{test}/cancel', {})[0], 200)
            self.wait(test, 'cancelled')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_the_check_says_what_a_test_would_without_building(self):
        gone = dict(code='not-placeable', message='Left out: Fence: it is hidden in its map', actor='Fence', leftOut=True)
        warning = dict(code='off-grid', message='The door is off the grid.', actor='Door')
        answers = iter([
            dict(project=dict(stage=dict(grid=[40, 36, 22])), report=dict(warnings=[]), issues=[gone, warning], leftOut=[gone]),
            ProjectError(422, 'too large to test', code='squad-room', issues=[dict(code='squad-room', message='too large to test')],
                         notes=[gone]),
            ProjectError(422, 'CB2_MP_Blank needs an export before this test can build.', code='stage-unprepared',
                         issues=[dict(code='stage-unprepared', message='x')]),
        ])

        def prepare(*_):
            answer = next(answers)
            if isinstance(answer, Exception):
                raise answer
            return answer
        self.tests.prepare = prepare
        doc = self.request()['snapshot']
        self.assertEqual(self.tests.check(doc), dict(ready=True, refused=None, issues=[gone, warning], leftOut=1, stage=[40, 36, 22]))
        refused = self.tests.check(doc)
        self.assertEqual((refused['refused'], [i['code'] for i in refused['issues']], refused['leftOut']),
                         ('too large to test', ['squad-room', 'not-placeable'], 1))
        waiting = self.tests.check(doc)
        self.assertEqual((waiting['ready'], waiting['issues']), (False, []))
        self.assertIn('Test in game prepares the blank map', waiting['message'])
        self.assertIsNone(self.builds.busy())       # (nothing was built)

    def test_private_snapshot_and_idempotent_dry_launch(self):
        request = self.request(quick=True)
        snapshot = request['snapshot']
        snapshot['revision'] = 17
        job = self.tests.start(request)
        snapshot['buildings'][0]['floors'][0]['boxes'][0][0] = 99
        self.gate.write_text('ok')
        test = job['id']
        result = self.wait(test, 'ready')
        self.assertEqual(result['source']['revision'], 17)
        self.assertEqual(read(self.tests.folder(test) / 'snapshot.json')['buildings'][0]['floors'][0]['boxes'][0][0], 0)
        self.assertEqual(self.store.list(), [])
        attempt = dict(buildId=result['buildId'], attemptId=uuid())
        self.assert_code('build-mismatch', lambda: self.tests.play(test, dict(attempt, buildId='older')))
        self.assertEqual(self.tests.play(test, attempt)['phase'], 'dry')
        self.assertEqual(self.tests.play(test, attempt)['phase'], 'dry')
        self.assert_code('test-not-ready', lambda: self.tests.play(test, dict(attempt, attemptId=uuid())))
        self.assertEqual(len(self.launches), 1)
        self.assertTrue(self.player.test_installed(self.game, test))
        installs.clear_play(self.game)
        self.assertEqual(self.maps.read_bytes(), self.maps_before)

    def test_saving_carries_through_to_the_launch(self):
        # Enable saving in Build and test's panel (play.py): the game starts at its main menu on the start file
        self.assert_code('test-request', lambda: self.tests.start(self.request(saving='yes')))
        job = self.tests.start(self.request(saving=True))
        self.assertTrue(job['saving'])
        self.gate.write_text('ok')
        ready = self.wait(job['id'], 'ready')
        status = self.tests.play(job['id'], dict(buildId=ready['buildId'], attemptId=uuid()))
        self.assertEqual(status['played']['saving'], dict(key=gamelaunch.SAVE_KEY, forced=None))
        self.assertEqual(installs.start_file(self.game).read_text(encoding='ascii'),
                         f'setbind {gamelaunch.SAVE_KEY} exec {installs.PLAY_FILE}\n')
        installs.clear_play(self.game)
        self.assertFalse(installs.start_file(self.game).exists() or installs.play_file(self.game).exists())

    def test_project_and_test_share_one_lock_and_cancel_only_the_test(self):
        project = uuid()
        self.store.save(project, document(project), 0)
        self.builds.start(project)
        self.assert_code('build-busy', lambda: self.tests.start(self.request()))
        self.stop_build()
        test = self.tests.start(self.request())['id']
        self.wait(test, 'building')
        with self.assertRaises(ProjectError):
            self.builds.start(project)
        self.tests.cancel(test)
        self.wait(test, 'cancelled')
        self.assertIsNone(self.builds.busy())
        self.assertEqual(self.launches, [])

    def test_cancel_ready_and_failed_build_cannot_play_an_artifact(self):
        ready = self.ready()
        self.tests.cancel(ready['id'])
        self.assert_code('test-not-ready', lambda: self.tests.play(
            ready['id'], dict(buildId=ready['buildId'], attemptId=uuid())))
        failed = self.ready('fail')
        self.assertNotIn('buildId', failed)
        self.assert_code('build-mismatch', lambda: self.tests.play(
            failed['id'], dict(buildId=failed['variant'] + '-fresh', attemptId=uuid())))
        self.assertEqual(self.launches, [])

    def test_cancel_wins_during_launch_verification(self):
        ready = self.ready()
        test = ready['id']
        verify = threading.Event()
        continue_launch = threading.Event()
        original = self.tests._package
        results = []
        def package(*args):
            verify.set()
            continue_launch.wait(3)
            return original(*args)
        with patch.object(self.tests, '_package', side_effect=package):
            worker = threading.Thread(target=lambda: results.append(self.tests.play(
                test, dict(buildId=ready['buildId'], attemptId=uuid()))))
            worker.start()
            try:
                self.assertTrue(verify.wait(3))
                self.assertEqual(self.tests.cancel(test)['phase'], 'cancelled')
            finally:
                continue_launch.set()
                worker.join(4)
        self.assertEqual(results[0]['attempt']['state'], 'cancelled')
        self.assertEqual(self.launches, [])

    def test_changed_sources_and_settings_invalidate_the_verified_build(self):
        first = self.ready()
        self.donor.write_bytes(b'new donor')
        status = self.tests.play(first['id'], dict(buildId=first['buildId'], attemptId=uuid()))
        self.assertEqual(status['issues'][0]['code'], 'source-changed')
        self.assertFalse(status['retryable'])
        second = self.ready()
        self.player.settings['udk'] = self.root / 'different'
        status = self.tests.play(second['id'], dict(buildId=second['buildId'], attemptId=uuid()))
        self.assertEqual(status['issues'][0]['code'], 'settings-changed')
        self.assertEqual(self.launches, [])

    def test_launch_failure_restores_install_and_retry_waits_for_game_exit(self):
        ready = self.ready()
        self.player.cleanup = True
        self.player.command = lambda *_: ([], None, 'direct')
        def fail(*_):
            raise OSError('could not start game')
        self.player.start = fail
        test = ready['id']
        first = dict(buildId=ready['buildId'], attemptId=uuid())
        status = self.tests.play(test, first)
        self.assertTrue(status['retryable'])
        self.assertFalse(self.player.test_installed(self.game, test))
        self.assertEqual(self.maps.read_bytes(), self.maps_before)
        def started(*args):
            self.running = True
            self.launches.append(args)
        self.player.start = started
        self.assertEqual(self.tests.play(test, first)['attempt']['state'], 'failed')
        self.assertEqual(self.tests.play(test, dict(first, attemptId=uuid()))['phase'], 'playing')
        self.assertEqual(self.tests.cancel(test)['phase'], 'playing')
        self.running = False
        self.wait(test, 'finished')
        self.assertEqual(len(self.launches), 1)
        self.assertEqual(self.maps.read_bytes(), self.maps_before)

    def test_install_journal_rolls_back_files_if_the_configuration_write_fails(self):
        ready = self.ready()
        test = ready['id']
        with patch.object(installs, 'replace_bytes', side_effect=OSError('config is locked')):
            status = self.tests.play(test, dict(buildId=ready['buildId'], attemptId=uuid()))
        self.assertEqual(status['phase'], 'failed')
        self.assertFalse(self.player.test_installed(self.game, test))
        self.assertFalse((installs.cooked(self.game) / (ready['variant'] + '.upk')).exists())
        self.assertEqual(self.maps.read_bytes(), self.maps_before)
        self.assertEqual(self.launches, [])

    def test_restart_holds_an_interrupted_build_while_a_tool_still_uses_it(self):
        ready = self.ready()
        test = ready['id']
        path = self.tests.folder(test) / 'test.json'
        kept = read(path)
        kept.update(phase='building', dryMode=False)
        write(path, kept)
        self.running = True
        restarted = PrefabTests(self.builds, self.live, process_active=lambda _: self.running)
        self.assertEqual(restarted.status(test)['issues'][0]['code'], 'test-interrupted')
        self.assertIsNotNone(self.builds.busy())
        self.assertTrue(restarted._in_use(restarted.jobs[test]))
        self.running = False
        self.assertIsNone(self.builds.busy())
        self.assertFalse(restarted._in_use(restarted.jobs[test]))
        self.assertEqual(self.launches, [])

    def test_restart_survives_an_old_test_whose_folder_can_not_be_deleted(self):
        ready = self.ready()
        test = ready['id']
        path = self.tests.folder(test) / 'test.json'
        old = read(path)
        old.update(updatedAt='2020-01-01T00:00:00Z', dryMode=False)    # a dry run's test is never pruned
        write(path, old)
        unreadable = self.tests.root / str(uuid4())
        unreadable.mkdir()
        (unreadable / 'test.json').write_text('{', encoding='utf-8')
        with patch('prefab_tests.KEEP_SECONDS', 0), patch('prefab_tests.shutil.rmtree', side_effect=PermissionError('held')):
            restarted = PrefabTests(self.builds, self.live, process_active=lambda _: False)
        self.assertIn(test, restarted.jobs)                 # kept for the next prune
        self.assertTrue(unreadable.is_dir())
        restarted = PrefabTests(self.builds, self.live, process_active=lambda _: False)
        self.assertNotIn(test, restarted.jobs)              # nothing holds it now: pruned by its age
        self.assertFalse(self.tests.folder(test).exists())

    def test_restart_follows_an_installed_game_and_keeps_its_files_until_exit(self):
        self.player.cleanup = True
        ready = self.ready()
        test = ready['id']
        folder = self.tests.folder(test)
        package = folder / 'artifacts' / ready['variant']
        installed = installs.install_package(self.game, package, test=test)
        installs.write_play_file(self.game, 'test\n', installed)
        job = read(folder / 'test.json')
        job.update(phase='launching', launchAt=job['updatedAt'], launchCommitted=True)
        job['attempts'][uuid()] = dict(state='launching')
        write(folder / 'test.json', job)
        self.running = True
        self.tests = PrefabTests(self.builds, self.live, process_active=lambda _: False)
        self.assertEqual(self.tests.status(test)['phase'], 'playing')
        self.assertTrue(self.tests._in_use(self.tests.jobs[test]))
        self.assertTrue(package.is_dir())
        self.running = False
        self.wait(test, 'finished')
        self.assertEqual(self.maps.read_bytes(), self.maps_before)
        self.assertEqual(self.launches, [])


if __name__ == '__main__':
    unittest.main()
