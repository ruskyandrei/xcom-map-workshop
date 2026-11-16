"""The build queue (buildqueue.py and its routes; build queue plan, Q1), with test_builds.py's stand-in for build.py:
rows built in order, a project's failure apart from the queue's, waits for another's build and for readers, Stop at
each step of a row, Resume, receipts, the store's file (backup, corruption, a newer schema, crashes at each write), a
second owner, changed settings and the routes. Steps are held with the queue's hooks (events), not timed sleeps."""
from functools import partial
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import buildqueue  # noqa: E402
from buildqueue import BuildQueue  # noqa: E402
from builds import BuildRunner  # noqa: E402
import gamesetup  # noqa: E402
from projects import ProjectError, ProjectStore  # noqa: E402
from test_builds import STANDIN  # noqa: E402
from test_projects import ID, OTHER, document  # noqa: E402
from viewer import Handler, LocalServer  # noqa: E402

THIRD = '2c3d4e5f-1d2a-4b6c-8e9f-123456789abc'
MISSING = '3d4e5f6a-1d2a-4b6c-8e9f-123456789abc'


def until(check, timeout=30, what='the condition'):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError(f'timed out waiting for {what}')


class Hold:
    """A hook that holds the worker at a step until released."""

    def __init__(self):
        self.reached, self.go = threading.Event(), threading.Event()

    def __call__(self, item_id):
        self.reached.set()
        if not self.go.wait(30):
            raise AssertionError('never released')


class Queue(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.store = ProjectStore(root / 'projects')
        self.output, self.go = root / 'builds', root / 'go'
        self.output.mkdir()
        for pid, name, variant in ((ID, 'Bar remix', 'URB_Bar_Remix_0f8b'), (OTHER, 'Other bar', 'URB_Bar_Other_1a2b'),
                                   (THIRD, 'Third bar', 'URB_Bar_Third_2c3d')):
            self.store.save(pid, document(pid, name=name, output=dict(shipAs=variant, patch='patch_' + variant.lower())), 0)
        self.script = root / 'standin.py'
        self.script.write_text(STANDIN, encoding='utf-8')
        self.outcomes = {}
        self.ctx = dict(projects=str(root / 'projects'), output=str(self.output), cache=str(root / 'cache'), game='G',
                        udk=None, checkGames=[])
        self.runner = self.make_runner()
        self.queue = self.make_queue()
        self.addCleanup(self.shutdown)

    def make_runner(self):
        runner = BuildRunner(self.store, Path(self.temp.name) / 'cache', self.output,
                             command=lambda f: [sys.executable, '-u', str(self.script), str(f), str(self.output), str(self.go),
                                                self.outcome_of(f)])
        runner.queue_command = lambda snapshot, context, saved_file: [
            sys.executable, '-u', str(self.script), str(snapshot), str(self.output), str(self.go), self.outcome_of(snapshot)]
        return runner

    def make_queue(self, activate=True):
        queue = BuildQueue(self.store, self.runner, lambda: dict(self.ctx))
        if activate:
            self.assertTrue(queue.activate())
        return queue

    def outcome_of(self, path):
        return self.outcomes.get(json.loads(Path(path).read_text(encoding='utf-8'))['id'], 'ok')

    def shutdown(self):
        self.go.touch()
        for hook in self.queue.hooks.values():
            if isinstance(hook, Hold): hook.go.set()
        self.queue.close(wait=30)
        if self.runner.attempt: self.runner.attempt.done.wait(30)

    @staticmethod
    def die(queue):
        """The server holding `queue` dies here: its worker writes nothing more and starts nothing, its store's lock
        is let go (the operating system's, when a process ends)."""
        def dead(change):
            queue.fault = 'dead'
            return False
        queue._transition = dead
        queue.owner.release()

    def call(self, action, queue=None, **fields):
        queue = queue or self.queue
        view = queue.view()
        request = dict(queueId=view.get('queueId'), expectedRevision=view.get('revision') or 0, requestId=str(uuid.uuid4()),
                       **fields)
        return getattr(queue, action)(request)

    def row(self, project, view=None):
        return next(i for i in (view or self.queue.view())['items'] if i['project'] == project)

    def settled(self, state='finished'):
        return until(lambda: self.queue.view()['state'] == state and self.queue.view(), what=f'the queue {state}')

    # ------------------------------------------------------------------ building

    def test_rows_build_in_order_each_as_saved_when_its_turn_comes(self):
        hold = Hold()
        self.queue.hooks['intent'] = lambda item_id: hold(item_id) if self.queue._row(item_id)['project'] == OTHER else None
        self.go.touch()
        status, answer = self.call('add', projects=[ID, OTHER, ID])
        self.assertEqual((status, answer['appended'], answer['queue']['state']), (202, [ID, OTHER], 'running'))
        self.assertTrue(hold.reached.wait(30))
        # saved while it waits: its turn takes this revision
        self.store.save(OTHER, document(OTHER, name='Other bar', output=dict(shipAs='URB_Bar_Other_1a2b', patch='patch_urb_bar_other_1a2b')), 1)
        self.assertEqual(self.row(ID)['state'], 'built')
        hold.go.set()
        view = self.settled()
        built = [(i['project'], i['state'], i['result']['revision']) for i in view['items']]
        self.assertEqual(built, [(ID, 'built', 1), (OTHER, 'built', 2)])
        self.assertEqual((view['counts']['processed'], view['counts']['built']), (2, 2))
        manifest = json.loads((self.output / 'URB_Bar_Other_1a2b' / 'manifest.json').read_text())
        self.assertEqual(manifest['attempt'], self.row(OTHER, view)['attempt'])
        # the snapshot it read is kept, immutable, apart from the project's file
        snapshot = self.output / '.work' / 'queue-attempts' / manifest['attempt'] / 'project.json'
        self.assertEqual(json.loads(snapshot.read_text())['revision'], 2)
        self.assertTrue((snapshot.parent / 'build.log').is_file())
        self.assertIsNone(self.runner.busy())                  # the slot is free once the queue has finished

    def test_a_project_that_fails_fails_alone(self):
        self.outcomes[OTHER] = 'fail'
        self.go.touch()
        self.call('add', projects=[MISSING, OTHER, ID])
        view = self.settled()
        states = {i['project']: (i['state'], i['error']) for i in view['items']}
        self.assertEqual(states[ID], ('built', None))
        self.assertEqual(states[OTHER][0], 'failed')
        self.assertIn('patchtool.ps1 failed', states[OTHER][1])
        self.assertEqual(states[MISSING][0], 'failed')
        self.assertIn('could not be read', states[MISSING][1])
        self.assertEqual(view['counts']['failed'], 2)

    def test_the_queue_waits_for_another_build_and_holds_the_slot_between_rows(self):
        incumbent = self.runner._start(self.store.load(THIRD), self.runner.command(self.store.path(THIRD)), False)
        self.call('add', projects=[ID, OTHER])
        view = until(lambda: self.queue.view()['waitingFor'] and self.queue.view(), what='a wait')
        self.assertEqual(view['waitingFor']['kind'], 'build')
        self.assertEqual(view['waitingFor']['name'], 'Third bar')
        hold = Hold()
        self.queue.hooks['intent'] = lambda item_id: hold(item_id) if self.queue._row(item_id)['project'] == OTHER else None
        self.go.touch()
        self.assertTrue(incumbent.done.wait(30))
        self.assertTrue(hold.reached.wait(30))
        # between the queue's rows no other build starts: structured 409, the queue named
        with self.assertRaises(ProjectError) as error: self.runner.start(THIRD)
        self.assertEqual((error.exception.extra.get('code'), error.exception.extra.get('queue')), ('build-slot', True))
        hold.go.set()
        self.settled()
        self.assertEqual(self.runner.start(THIRD)['state'], 'running')

    def test_the_queue_waits_for_a_reader_of_the_next_projects_package(self):
        self.go.touch()
        with self.runner.lease([ID]):
            self.call('add', projects=[ID])
            view = until(lambda: self.queue.view()['waitingFor'] and self.queue.view(), what='a wait')
            self.assertEqual(view['waitingFor']['kind'], 'reader')
            self.assertEqual(self.row(ID, view)['state'], 'waiting')
        self.assertEqual(self.row(ID, self.settled())['state'], 'built')

    # ------------------------------------------------------------------ stopping and resuming

    def test_stop_while_capturing_launches_nothing(self):
        hold = Hold()
        self.queue.hooks['captured'] = hold
        self.call('add', projects=[ID, OTHER])
        self.assertTrue(hold.reached.wait(30))
        status, answer = self.call('stop')
        self.assertEqual((status, answer['queue']['state']), (202, 'stopping'))
        status, _ = self.call('stop')                       # again while it drains: harmless
        self.assertEqual(status, 202)
        with self.assertRaises(ProjectError) as error: self.call('resume')
        self.assertEqual(error.exception.extra['code'], 'queue-stopping')
        with self.assertRaises(ProjectError) as error: self.call('add', projects=[THIRD])
        self.assertEqual(error.exception.extra['code'], 'queue-stopping')
        hold.go.set()
        view = self.settled('stopped')
        self.assertEqual([i['state'] for i in view['items']], ['waiting', 'waiting'])
        self.assertIsNone(self.runner.job)                  # nothing was launched
        self.assertTrue(view['canResume'])
        self.assertIsNone(self.runner.busy())               # the slot is free while stopped

    def test_stop_while_building_stops_its_build_and_resume_starts_it_again_as_saved(self):
        hold = Hold()
        self.queue.hooks['spawned'] = hold
        self.call('add', projects=[ID, OTHER])
        self.assertTrue(hold.reached.wait(30))
        first = self.row(ID)['attempt']
        status, _ = self.call('stop')
        self.assertEqual(status, 202)
        hold.go.set()
        view = self.settled('stopped')
        row = self.row(ID, view)
        self.assertEqual((row['state'], row['earlier']), ('waiting', 1))
        self.assertIn('starts again on Resume', row['interrupted'])
        self.assertEqual(self.runner.job['state'], 'cancelled')
        self.assertFalse((self.output / 'URB_Bar_Remix_0f8b').exists())
        # Resume: the latest save, a new attempt
        self.store.save(ID, document(name='Bar remix', output=dict(shipAs='URB_Bar_Remix_0f8b', patch='patch_urb_bar_remix_0f8b')), 1)
        del self.queue.hooks['spawned']
        self.go.touch()
        status, _ = self.call('resume')
        self.assertEqual(status, 202)
        self.assertEqual(self.call('resume')[0], 200)       # running already: harmless
        view = self.settled()
        row = self.row(ID, view)
        self.assertEqual((row['state'], row['result']['revision'], row['attempts']), ('built', 2, 2))
        self.assertNotEqual(row['attempt'], first)

    def test_a_package_that_went_in_before_stop_stays_built(self):
        hold = Hold()
        self.queue.hooks['ended'] = hold
        self.go.touch()
        self.call('add', projects=[ID, OTHER])
        self.assertTrue(hold.reached.wait(30))
        self.call('stop')
        hold.go.set()
        view = self.settled('stopped')
        self.assertEqual([i['state'] for i in view['items']], ['built', 'waiting'])

    def test_stop_while_waiting_for_another_build_leaves_that_build_running(self):
        incumbent = self.runner._start(self.store.load(THIRD), self.runner.command(self.store.path(THIRD)), False)
        self.call('add', projects=[ID])
        until(lambda: self.queue.view()['waitingFor'], what='a wait')
        status, answer = self.call('stop')
        self.assertEqual((status, answer['queue']['state']), (200, 'stopped'))
        self.assertEqual(self.call('stop')[0], 200)
        self.assertEqual(incumbent.job['state'], 'running')
        self.go.touch()
        self.assertTrue(incumbent.done.wait(30))
        self.assertEqual(incumbent.job['state'], 'built')
        self.assertEqual(self.row(ID)['state'], 'waiting')

    def test_cancel_in_the_build_window_stops_the_queue(self):
        hold = Hold()
        self.queue.hooks['spawned'] = hold
        self.call('add', projects=[ID, OTHER])
        self.assertTrue(hold.reached.wait(30))
        attempt = self.row(ID)['attempt']
        with self.assertRaises(ProjectError): self.runner.cancel(ID, str(uuid.uuid4()))      # a stale page's
        self.runner.cancel(ID, attempt)
        hold.go.set()
        view = self.settled('stopped')
        self.assertEqual([i['state'] for i in view['items']], ['waiting', 'waiting'])

    def test_a_late_ending_never_changes_a_newer_attempts_row(self):
        hold = Hold()
        self.queue.hooks['spawned'] = hold
        self.call('add', projects=[ID])
        self.assertTrue(hold.reached.wait(30))
        item = self.row(ID)['itemId']
        self.queue._ended(item, str(uuid.uuid4()), 'failed', error='an old attempt')
        self.assertEqual(self.row(ID)['state'], 'building')
        self.go.touch()
        hold.go.set()
        self.assertEqual(self.row(ID, self.settled())['state'], 'built')

    # ------------------------------------------------------------------ requests

    def test_add_remove_clear_and_receipts(self):
        self.go.touch()
        self.call('add', projects=[ID])
        view = self.settled()
        # a built row added again goes to the end, its earlier attempt kept
        hold = Hold()
        self.queue.hooks['intent'] = hold
        status, answer = self.call('add', projects=[OTHER, ID])
        self.assertEqual((answer['appended'], answer['reset']), ([OTHER, ID], []))      # a finished queue: a new one
        self.assertNotEqual(answer['queue']['queueId'], view['queueId'])
        self.assertTrue(hold.reached.wait(30))
        status, answer = self.call('add', projects=[THIRD, OTHER])
        self.assertEqual((answer['appended'], answer['alreadyQueued']), ([THIRD], [OTHER]))
        waiting = [i for i in answer['queue']['items'] if i['state'] == 'waiting']
        self.assertEqual([i['position'] for i in waiting], [1, 2])
        # Remove: waiting rows only, the whole request checked before anything changes
        building = self.row(OTHER)['itemId']
        with self.assertRaises(ProjectError) as error: self.call('remove', items=[waiting[0]['itemId'], building])
        self.assertEqual(error.exception.extra['code'], 'queue-remove')
        self.assertEqual(len(self.queue.view()['items']), 3)
        with self.assertRaises(ProjectError) as error: self.call('remove', items=['not-a-uuid'])
        self.assertEqual(error.exception.status, 400)
        status, _ = self.call('remove', items=[i['itemId'] for i in waiting])
        self.assertEqual(status, 200)
        # Clear is refused while running
        with self.assertRaises(ProjectError) as error: self.call('clear')
        self.assertEqual(error.exception.extra['code'], 'queue-running')
        hold.go.set()
        view = self.settled()
        self.assertEqual([i['project'] for i in view['items']], [OTHER])
        # a receipt: the same request again gets its answer, another with its id is refused, a stale one too
        request = dict(queueId=view['queueId'], expectedRevision=view['revision'], requestId=str(uuid.uuid4()))
        status, answer = self.queue.clear(dict(request))
        self.assertEqual((status, answer['cleared'], answer['queue']['state']), (200, True, 'idle'))
        status, again = self.queue.clear(dict(request))
        self.assertEqual((status, again['cleared'], again['repeated']), (200, True, True))
        with self.assertRaises(ProjectError) as error: self.queue.stop(dict(request))
        self.assertEqual(error.exception.extra['code'], 'request-conflict')
        with self.assertRaises(ProjectError) as error:
            self.queue.stop(dict(request, requestId=str(uuid.uuid4())))     # the old queue's id: stale
        self.assertEqual(error.exception.extra['code'], 'queue-stale')
        # Clear deleted no package
        self.assertTrue((self.output / 'URB_Bar_Other_1a2b' / 'manifest.json').is_file())
        for bad in (None, [], {'queueId': None}, dict(request, extra=1), dict(request, expectedRevision=-1)):
            with self.assertRaises(ProjectError) as error: self.queue.stop(bad)
            self.assertEqual(error.exception.status, 400)

    def test_removing_the_last_waiting_row_settles_the_queue(self):
        incumbent = self.runner._start(self.store.load(THIRD), self.runner.command(self.store.path(THIRD)), False)
        self.call('add', projects=[ID])
        until(lambda: self.queue.view()['waitingFor'], what='a wait')
        self.call('remove', items=[self.row(ID)['itemId']])
        view = self.queue.view()
        self.assertEqual((view['state'], view['queueId']), ('idle', None))
        self.go.touch(); incumbent.done.wait(30)
        self.assertIsNone(self.runner.busy())

    def test_adding_to_a_stopped_queue_leaves_it_stopped(self):
        incumbent = self.runner._start(self.store.load(THIRD), self.runner.command(self.store.path(THIRD)), False)
        self.call('add', projects=[ID])
        until(lambda: self.queue.view()['waitingFor'], what='a wait')
        self.call('stop')
        status, answer = self.call('add', projects=[OTHER])
        self.assertEqual((status, answer['queue']['state']), (202, 'stopped'))
        self.go.touch(); incumbent.done.wait(30)
        self.assertEqual(self.queue.view()['state'], 'stopped')
        self.assertIsNone(self.runner.job if self.runner.job['project'] != THIRD else None)

    def test_requests_at_once_take_one_worker_and_one_row_each(self):
        hold = Hold()
        self.queue.hooks['intent'] = hold
        view = self.queue.view()
        results = []

        def send(project):
            try: results.append(self.queue.add(dict(queueId=view['queueId'], expectedRevision=view['revision'],
                                                     requestId=str(uuid.uuid4()), projects=[project]))[0])
            except ProjectError as error: results.append(error.extra.get('code'))
        threads = [threading.Thread(target=send, args=(p,)) for p in (ID, OTHER, THIRD) * 3]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(results.count(202), 1)              # the rest saw a revision that had moved on
        self.assertEqual(results.count('queue-stale'), len(threads) - 1)
        self.assertTrue(hold.reached.wait(30))
        self.assertEqual(sum(1 for t in threading.enumerate() if t.name == 'build-queue'), 1)
        self.go.touch(); hold.go.set()
        self.settled()

    # ------------------------------------------------------------------ the store

    def test_a_storage_failure_holds_the_queue_and_says_so(self):
        real, calls = self.queue._save, []

        def failing():
            calls.append(1)
            if len(calls) == 3: raise OSError('disk full')       # the row's capture written: refused
            real()
        self.queue._save = failing
        self.go.touch()
        self.call('add', projects=[ID, OTHER])
        view = until(lambda: self.queue.view()['fault'] and self.queue.view(), what='a fault')
        self.assertIn('disk full', view['fault'])
        self.assertIsNone(self.runner.job)
        self.assertEqual(view['state'], 'running')
        self.assertTrue(view['actions']['stop'])
        self.queue._save = real
        status, answer = self.call('stop')
        self.assertIsNone(answer['queue']['fault'])
        self.assertEqual(answer['queue']['state'], 'stopped')

    def test_the_file_survives_a_restart_and_starts_nothing(self):
        hold = Hold()
        self.queue.hooks['captured'] = hold
        request = dict(queueId=None, expectedRevision=0, requestId=str(uuid.uuid4()), projects=[ID, OTHER])
        self.queue.add(dict(request))
        self.assertTrue(hold.reached.wait(30))
        # the server dies here: its queue never stops (a new one reads the file as it was left)
        saved = json.loads((self.output / '.work' / 'build-queue.json').read_text())
        self.assertEqual([i['state'] for i in saved['items']], ['starting', 'waiting'])
        self.die(self.queue)
        hold.go.set()
        self.queue = second = self.make_queue()
        view = until(lambda: not second.view()['recovering'] and second.view(), what='the recovery')
        self.assertEqual((view['state'], [i['state'] for i in view['items']]), ('stopped', ['waiting', 'waiting']))
        self.assertIn('stopped during its build', self.row(ID, view)['interrupted'])
        self.assertIn('Resume', view['reason'])
        # the same request again, after the restart: its first answer, no new rows
        status, answer = second.add(dict(request))
        self.assertEqual((status, answer['repeated'], len(answer['queue']['items'])), (202, True, 2))

    def test_a_package_of_that_attempt_in_place_is_built_though_its_result_was_never_written(self):
        hold = Hold()
        self.queue.hooks['ended'] = hold
        self.go.touch()
        self.call('add', projects=[ID])
        self.assertTrue(hold.reached.wait(30))
        # the build has ended and its package is in place; the server dies before the result is written
        self.die(self.queue)
        hold.go.set()
        self.queue = second = self.make_queue()
        view = until(lambda: not second.view()['recovering'] and second.view(), what='the recovery')
        row = self.row(ID, view)
        self.assertEqual((view['state'], row['state'], row['result']['recovered']), ('finished', 'built', True))

    def test_rows_wait_while_an_earlier_servers_build_still_runs(self):
        attempt = str(uuid.uuid4())
        state = buildqueue.empty()
        state.update(queueId=str(uuid.uuid4()), state='running', context=self.ctx, revision=4,
                     items=[dict(itemId=str(uuid.uuid4()), project=ID, name='Bar remix', variant='URB_Bar_Remix_0f8b',
                                 state='building', attempt=dict(id=attempt, revision=1), attempts=1)])
        (self.output / '.work').mkdir(exist_ok=True)
        (self.output / '.work' / 'build-queue.json').write_text(json.dumps(state), encoding='utf-8')
        alive = threading.Event()
        self.runner.recovered[attempt] = ('Bar remix', lambda: not alive.is_set())
        self.queue.owner.release()
        self.queue = second = self.make_queue()
        view = second.view()
        self.assertTrue(view['recovering'])
        self.assertEqual(view['state'], 'stopped')
        with self.assertRaises(ProjectError) as error: self.call('resume', queue=second)
        self.assertEqual(error.exception.extra['code'], 'queue-recovering')
        with self.assertRaises(ProjectError) as error: self.call('clear', queue=second)
        self.assertEqual(error.exception.extra['code'], 'queue-recovering')
        alive.set()
        view = until(lambda: not second.view()['recovering'] and second.view(), what='the recovery')
        self.assertEqual(self.row(ID, view)['state'], 'waiting')

    def test_a_file_that_cannot_be_read_is_kept_and_only_reset_sets_it_aside(self):
        self.go.touch()
        self.call('add', projects=[ID])
        self.settled()
        self.call('add', projects=[OTHER])
        self.settled()
        self.queue.close()
        work = self.output / '.work'
        self.assertTrue((work / 'build-queue.json.bak').is_file())
        # torn: the last good copy is read, the bad bytes kept
        (work / 'build-queue.json').write_text('{"schema": "xcom-map-workshop/build-queue", "it', encoding='utf-8')
        self.queue = second = self.make_queue()
        view = second.view()
        self.assertTrue(view['available'])
        self.assertIn('last good copy', view['notice'])
        self.assertEqual(len(list(work.glob('build-queue.unreadable-*.json'))), 1)
        second.close()
        # torn with no copy: an error, nothing accepted but reset
        (work / 'build-queue.json').write_text('{', encoding='utf-8')
        (work / 'build-queue.json.bak').unlink()
        self.queue = third = self.make_queue()
        self.assertEqual(third.view()['state'], 'unreadable')
        with self.assertRaises(ProjectError) as error:
            third.add(dict(queueId=None, expectedRevision=0, requestId=str(uuid.uuid4()), projects=[ID]))
        self.assertEqual(error.exception.extra['code'], 'queue-unreadable')
        with self.assertRaises(ProjectError): third.reset(dict(requestId=str(uuid.uuid4())))      # not confirmed
        status, answer = third.reset(dict(requestId=str(uuid.uuid4()), confirm=True))
        self.assertEqual((status, answer['reset'], answer['queue']['state']), (200, True, 'idle'))
        self.assertTrue(Path(answer['archived']).is_file())
        third.close()
        # a newer schema: not read, not replaced by the copy
        (work / 'build-queue.json').write_text(json.dumps(dict(buildqueue.empty(), schemaVersion=2)), encoding='utf-8')
        self.queue = fourth = self.make_queue()
        self.assertEqual(fourth.view()['state'], 'unreadable')
        self.assertIn('schema version 2', fourth.view()['error'])

    def test_one_server_owns_the_queue_and_nothing_is_touched_before_activate(self):
        other = self.make_queue(activate=False)
        self.assertFalse(other.activate())
        self.assertFalse(other.view()['available'])
        with self.assertRaises(ProjectError) as error:
            other.add(dict(queueId=None, expectedRevision=0, requestId=str(uuid.uuid4()), projects=[ID]))
        self.assertEqual(error.exception.extra['code'], 'queue-unavailable')
        # a queue made but never activated (the server's port could not be bound) reads, writes and locks nothing
        with tempfile.TemporaryDirectory() as temp:
            runner = BuildRunner(self.store, Path(temp) / 'cache', Path(temp) / 'builds')
            BuildQueue(self.store, runner, lambda: dict(self.ctx))
            self.assertFalse((Path(temp) / 'builds').exists())

    # ------------------------------------------------------------------ settings

    def test_changed_settings_stop_the_queue_and_keep_it_from_resuming(self):
        hold = Hold()
        self.queue.hooks['intent'] = hold
        self.call('add', projects=[ID, OTHER])
        self.assertTrue(hold.reached.wait(30))
        # while it runs, another game install can't be chosen
        with self.assertRaises(ProjectError) as error: self.queue.settings_guard()
        self.assertEqual(error.exception.extra['code'], 'queue-running')
        setup = gamesetup.GameSetup(save=lambda updates: self.fail('saved'), guard=self.queue.settings_guard)
        with mock.patch.object(gamesetup, 'resolve_game', lambda folder: (Path(folder), 'a game')):
            with self.assertRaises(ProjectError): setup.choose(dict(folder='another-install'))
        # changed outside the editor meanwhile: found before the build starts
        self.ctx['game'] = 'H'
        hold.go.set()
        view = self.settled('stopped')
        self.assertIn('settings changed', view['reason'])
        self.assertTrue(view['contextChanged'])
        self.assertFalse(view['canResume'])
        self.assertIsNone(self.runner.job)
        with self.assertRaises(ProjectError) as error: self.call('resume')
        self.assertEqual(error.exception.extra['code'], 'context-changed')
        with self.assertRaises(ProjectError) as error: self.call('add', projects=[THIRD])
        self.assertEqual(error.exception.extra['code'], 'context-changed')
        self.queue.settings_guard()             # stopped: the install may change
        self.assertEqual(self.call('clear')[0], 200)
        self.go.touch()
        self.call('add', projects=[ID])
        self.assertEqual(self.queue.q['context']['game'], 'H')
        self.settled()

    # ------------------------------------------------------------------ routes

    def test_the_routes(self):
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=dict(defaultMap=None, maps={}), projects=self.store,
                                                       builds=self.runner, queue=self.queue))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            def call(method, path, body=None, origin=None):
                request = Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                  headers={'Content-Type': 'application/json', **({'Origin': origin} if origin else {})})
                try:
                    with urlopen(request, timeout=10) as r: return r.status, json.loads(r.read()), r.headers
                except HTTPError as e: return e.code, json.loads(e.read()), e.headers
            status, view, headers = call('GET', '/manager/queue.json')
            self.assertEqual((status, view['state'], view['queueId']), (200, 'idle', None))
            self.assertIn('no-store', headers.get('Cache-Control'))
            envelope = lambda v: dict(queueId=v['queueId'], expectedRevision=v['revision'], requestId=str(uuid.uuid4()))  # noqa: E731
            self.assertEqual(call('POST', '/manager/queue', dict(envelope(view), projects=[ID]), origin='http://evil.example')[0], 403)
            self.assertEqual(call('POST', '/manager/queue', dict(envelope(view), projects='x'))[0], 400)
            hold = Hold()
            self.queue.hooks['spawned'] = hold
            status, answer, _ = call('POST', '/manager/queue', dict(envelope(view), projects=[ID]))
            self.assertEqual((status, answer['appended']), (202, [ID]))
            self.assertTrue(hold.reached.wait(30))
            view = call('GET', '/manager/queue.json')[1]
            self.assertEqual(self.row(ID, view)['job']['attempt'], self.row(ID, view)['attempt'])
            self.assertEqual(call('POST', '/manager/queue/stop', envelope(view))[0], 202)
            hold.go.set()
            view = self.settled('stopped')
            self.assertEqual(call('POST', '/manager/queue/stop', envelope(view))[0], 200)
            self.go.touch()
            self.assertEqual(call('POST', '/manager/queue/resume', envelope(view))[0], 202)
            view = self.settled()
            self.assertEqual(call('POST', '/manager/queue/clear', envelope(view))[0], 200)
            self.assertEqual(call('POST', '/manager/queue/clear', dict(envelope(view), requestId='nope'))[0], 400)
            self.assertEqual(call('GET', '/manager/queue/stop')[0], 405)
            # a server without a queue
            bare = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=dict(defaultMap=None, maps={}), projects=self.store,
                                                         builds=self.runner))
            other = threading.Thread(target=bare.serve_forever, daemon=True); other.start()
            try:
                with self.assertRaises(HTTPError) as error: urlopen(f'http://127.0.0.1:{bare.server_port}/manager/queue.json', timeout=10)
                self.assertEqual(error.exception.code, 404)
            finally:
                bare.shutdown(); bare.server_close()
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
