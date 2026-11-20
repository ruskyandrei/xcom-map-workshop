"""The cache filled ahead of use (precache.py, library.precache): what there is to do, the job, its cancelling, and
the routes. The pieces' process and the maps' exporter are stand-ins; a real piece is read in test_library."""
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
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import library
import precache
from projects import ProjectError
from viewer import Handler, Live, LocalServer


def entry(package, actor):
    return dict(source=dict(package=package, level='base', actor=actor))


class Plans(unittest.TestCase):
    """library.piece_plan and library.precache, the game's maps and a piece's export stood in for."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cache, self.game = self.root / 'cache', self.root / 'game'
        self.game.mkdir()
        self.maps = {}
        for name in ('URB_One', 'URB_Two'):
            self.maps[name] = self.game / (name + '.upk')
            self.maps[name].write_bytes(name.encode())
        stat = self.maps['URB_One'].stat()
        # URB_One is as the index scanned it (its SHA-256 is taken from the index); URB_Two changed since
        self.index = dict(donors=[dict(package='URB_One', sha256='a' * 64, size=stat.st_size, mtime=int(stat.st_mtime)),
                                  dict(package='URB_Two', sha256='b' * 64, size=1, mtime=1)],
                          entries=[entry('URB_One', 'Crate_1'), entry('URB_One', 'Crate_2'), entry('URB_Two', 'Wall_1'),
                                   entry('URB_Gone', 'Lamp_1')])
        patches = [mock.patch('library.donors', lambda game: [(n, 'base', p) for n, p in self.maps.items()]),
                   mock.patch('library.load_index', lambda cache: self.index),
                   mock.patch('library.piece', self.fake_piece)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.made = []

    def fake_piece(self, cache, game, source, shared=None):
        if source['actor'] == 'Crate_2':
            raise ProjectError(422, 'Crate_2 in URB_One has nothing to draw.')
        folder = self.folder(source['package'])
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (source['actor'] + '.json')).write_text(json.dumps(dict(version=library.PIECE_VERSION)), encoding='utf-8')
        self.made.append(source['actor'])

    def folder(self, package):
        return next(d['folder'] for d in library.piece_plan(self.cache, self.game, self.index) if d['package'] == package)

    def test_the_plan_says_what_the_cache_lacks_by_the_maps_as_they_are_now(self):
        plan = library.piece_plan(self.cache, self.game, self.index)
        # a donor the install lacks is left out
        self.assertEqual([(d['package'], d['actors'], d['missing']) for d in plan],
                         [('URB_One', ['Crate_1', 'Crate_2'], ['Crate_1', 'Crate_2']), ('URB_Two', ['Wall_1'], ['Wall_1'])])
        from export import EXPORT_VERSION
        self.assertEqual(plan[0]['folder'].name, '%s-v%d' % ('a' * 16, EXPORT_VERSION))
        self.assertEqual(plan[1]['folder'].name, '%s-v%d' % (library.sha256(self.maps['URB_Two'])[:16], EXPORT_VERSION))
        # a record of this version is kept; one of another version, or one cut short, is not
        folder = plan[0]['folder']
        folder.mkdir(parents=True)
        (folder / 'Crate_1.json').write_text(json.dumps(dict(version=library.PIECE_VERSION, key='k')), encoding='utf-8')
        (folder / 'Crate_2.json').write_text(json.dumps(dict(version=library.PIECE_VERSION - 1)), encoding='utf-8')
        self.assertEqual(library.piece_plan(self.cache, self.game, self.index)[0]['missing'], ['Crate_2'])
        (folder / 'Crate_2.json').write_text('{"vers', encoding='utf-8')
        self.assertEqual(library.piece_plan(self.cache, self.game, self.index)[0]['missing'], ['Crate_2'])

    def test_every_missing_piece_is_read_the_failed_named_and_old_generations_deleted(self):
        current = self.folder('URB_Two')
        old = current.parent / (current.name.split('-v')[0] + '-v1')
        old.mkdir(parents=True)
        (old / 'Wall_1.json').write_text('{}', encoding='utf-8')
        # another file's generation (the other install's copy of the map) stays as its own (review finding 18)
        other = current.parent / ('f' * 16 + '-v1')
        other.mkdir(parents=True)
        steps = []
        result = library.precache(self.game, self.cache, jobs=1, progress=lambda done, total: steps.append((done, total)))
        self.assertEqual(sorted(self.made), ['Crate_1', 'Wall_1'])
        self.assertEqual((result['pieces'], result['kept'], result['made'], result['pruned']), (3, 0, 2, 1))
        self.assertEqual(result['failed'], [dict(package='URB_One', actor='Crate_2', error='Crate_2 in URB_One has nothing to draw.')])
        self.assertEqual((steps[0], steps[-1]), ((0, 3), (3, 3)))
        self.assertFalse(old.exists())
        self.assertTrue(other.exists())
        self.assertFalse(result['stopped'])
        # again: what is cached is left, only the one that failed is tried
        self.made.clear()
        result = library.precache(self.game, self.cache, jobs=1)
        self.assertEqual((self.made, result['kept'], result['made'], len(result['failed'])), ([], 2, 0, 1))


class Stops(Plans):
    def test_a_stop_file_stops_between_pieces_and_nothing_is_deleted(self):
        current = self.folder('URB_Two')
        old = current.parent / (current.name.split('-v')[0] + '-v1')
        old.mkdir(parents=True)
        stop = self.root / 'stop'
        plain = self.fake_piece

        def piece_then_stop(cache, game, source, shared=None):
            plain(cache, game, source, shared)
            stop.write_text('stop')
        with mock.patch('library.piece', piece_then_stop):
            result = library.precache(self.game, self.cache, jobs=1, stop=stop)
        # the piece in hand was finished; the others wait for the next run, and the old generation stays till then
        self.assertEqual((len(self.made), result['stopped'], result['pruned'], old.exists()), (1, True, 0, True))
        stop.unlink()
        result = library.precache(self.game, self.cache, jobs=1, stop=stop)
        self.assertEqual((sorted(self.made), result['stopped'], old.exists()), (['Crate_1', 'Wall_1'], False, False))


class FakeLibrary:
    def __init__(self, cache):
        self.cache = cache

    def install(self):
        return Path('game')

    def index(self):
        return None, None


class FakeExports:
    """The server's exporter: a map takes `ticks` readings to prepare; `fails` are the maps that fail."""

    def __init__(self, catalogue, ticks=2, fails=()):
        self.catalogue, self.ticks, self.fails = catalogue, ticks, set(fails)
        self.started, self.left, self.cancelled, self.busy = [], {}, [], 0

    def start(self, map_id, prepare=False, owner=None):
        if self.busy:
            self.busy -= 1
            raise ProjectError(409, 'Another map is being prepared. One map at a time.', exporting='URB_Other')
        self.started.append((map_id, prepare, owner))
        self.left[map_id] = self.ticks
        return dict(state='running', progress=dict(fraction=0.5))

    def status(self, map_id):
        if map_id in self.cancelled:
            return dict(state='failed', error='Preparation cancelled.')
        self.left[map_id] -= 1
        if self.left[map_id] > 0:
            return dict(state='running', progress=dict(fraction=0.5))
        if map_id in self.fails:
            return dict(state='failed', error='it broke')
        self.catalogue['maps'][map_id].update(ready=True, scope='map', priority=(99,))
        return dict(state='ready')

    def cancel_owned(self, owner):
        self.cancelled += [m for m, _, o in self.started if o == owner and self.left.get(m, 0) > 0]


def a_map(name, **state):
    return dict(id=name, name=name, label=name.replace('_', ' '), installed=True, **state)


PROGRAM = ("import sys,time,json\n"
           "print('progress: caching the pieces 0/4', flush=True)\n"
           "print('progress: caching the pieces 2/4', flush=True)\n"
           "%s\n"
           "print('result: ' + json.dumps(dict(pieces=5, kept=1, made=3, pruned=2, seconds=1,"
           " failed=[dict(package='URB_One', actor='Crate_2', error='nothing to draw')])), flush=True)\n")


class Jobs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.catalogue = dict(defaultMap='URB_Bar', maps={m['id']: m for m in (
            a_map('URB_Bar', ready=True, scope='map', priority=(99,)),
            a_map('URB_Old', ready=True, scope='map', priority=(3,)),          # an older exporter's
            a_map('URB_New'),
            dict(a_map('Lab_Sample', ready=True, scope='sample', priority=(1,)), installed=False))})
        self.exports = FakeExports(self.catalogue)
        self.live = Live(self.catalogue, self.exports, None, FakeLibrary(Path(self.tmp.name)))

    def runner(self, body='', **options):
        return precache.PrecacheRunner(self.live, Path(self.tmp.name), export_version=99, pause=0.01,
                                       command=lambda game: [sys.executable, '-c', PROGRAM % body], **options)

    def wait(self, runner, state=None, seconds=20):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            status = runner.status()
            if (status['state'] != 'running') if state is None else state(status):
                return status
            time.sleep(0.01)
        self.fail('the job did not get there: %s' % runner.status())

    def test_the_plan_counts_the_maps_and_says_the_library_is_not_read(self):
        plan = self.runner().status(plan=True)['plan']
        self.assertEqual(plan['maps'], dict(available=True, total=3, ready=1, outdated=1, missing=1))
        self.assertEqual((plan['pieces']['ready'], plan['pieces']['missing']), (False, None))
        self.assertEqual(plan['estimates']['maps'], dict(seconds=2 * precache.MAP_SECONDS, bytes=precache.MAP_BYTES))
        self.assertGreater(plan['free'], 0)
        # a server that prepares no maps says so
        self.live.exports = None
        self.assertFalse(self.runner().plan()['maps']['available'])

    def test_the_pieces_then_the_maps_one_after_another(self):
        runner = self.runner()
        self.assertEqual(runner.status()['state'], 'idle')
        runner.start(dict(pieces=True, maps=True))
        done = self.wait(runner)
        self.assertEqual((done['state'], done['error'], done['options']), ('done', None, dict(pieces=True, maps=True)))
        self.assertEqual(done['pieces'], dict(made=3, kept=1, failed=1, failures=['Crate_2 of URB_One: nothing to draw'], pruned=2))
        # the map not exported, and the one an older exporter made (again): through the server's own exporter
        self.assertEqual(self.exports.started, [('URB_Old', True, 'precache'), ('URB_New', False, 'precache')])
        self.assertEqual((done['maps'], done['done'], done['total'], done['fraction']), (dict(made=2, failed=0, failures=[]), 2, 2, 1.0))
        self.assertEqual(runner.plan()['maps'], dict(available=True, total=3, ready=3, outdated=0, missing=0))

    def test_only_what_was_asked_for_and_nothing_is_refused(self):
        runner = self.runner()
        with self.assertRaises(ProjectError):
            runner.start(dict(pieces=False, maps=False))
        runner.start(dict(pieces=True))
        done = self.wait(runner)
        self.assertEqual((done['state'], done['maps'], self.exports.started), ('done', None, []))

    def test_a_map_that_fails_is_named_and_the_rest_go_on_and_a_busy_exporter_is_waited_for(self):
        self.exports.fails, self.exports.busy = {'URB_Old'}, 3
        runner = self.runner()
        runner.start(dict(maps=True))
        done = self.wait(runner)
        self.assertEqual((done['state'], done['maps']), ('done', dict(made=1, failed=1, failures=['URB Old: it broke'])))

    def test_a_cancelled_pieces_process_is_asked_to_stop_and_says_what_it_read(self):
        # the process sees the stop file (as library.precache does, between pieces) and ends by itself: not killed
        body = ("import os\n"
                "while not os.path.exists(%r): time.sleep(0.02)\n" % str(Path(self.tmp.name) / 'library' / 'precache.stop'))
        runner = self.runner(body, grace=60)
        runner.start(dict(pieces=True, maps=True))
        self.wait(runner, lambda s: s['total'] == 4 and s['done'] == 2)
        with mock.patch('procs.Contained.terminate', side_effect=AssertionError('killed')):
            runner.cancel()
            done = self.wait(runner)
        self.assertEqual((done['state'], done['pieces']['made'], self.exports.started), ('cancelled', 3, []))
        self.assertFalse(runner.stop_file.exists())

    def test_cancelling_stops_the_pieces_process_and_leaves_the_maps_undone(self):
        # (one that does not stop by itself is killed after the grace)
        runner = self.runner('time.sleep(60)', grace=0.2)
        runner.start(dict(pieces=True, maps=True))
        at = self.wait(runner, lambda s: s['total'] == 4 and s['done'] == 2)
        self.assertEqual((at['phase'], at['what'], at['fraction']), ('pieces', 'Caching the pieces', 0.5))
        # a second start while it runs is the running job's state
        self.assertEqual(runner.start(dict(maps=True))['options'], dict(pieces=True, maps=True))
        started = time.monotonic()
        runner.cancel()
        done = self.wait(runner)
        self.assertEqual((done['state'], done['pieces'], self.exports.started), ('cancelled', None, []))
        self.assertLess(time.monotonic() - started, 10)

    def test_cancelling_during_the_maps_stops_the_map_in_hand(self):
        self.exports.ticks = 10 ** 6
        runner = self.runner()
        runner.start(dict(maps=True))
        self.wait(runner, lambda s: s['phase'] == 'maps' and s['what'].startswith('Preparing URB'))
        runner.cancel()
        done = self.wait(runner)
        self.assertEqual((done['state'], set(self.exports.cancelled), len(self.exports.started)), ('cancelled', {'URB_Old'}, 1))

    def test_a_pieces_process_that_fails_is_the_jobs_error(self):
        runner = self.runner('print("no donor maps were found"); sys.exit(2)')
        runner.start(dict(pieces=True, maps=True))
        done = self.wait(runner)
        self.assertEqual((done['state'], self.exports.started), ('failed', []))
        self.assertIn('no donor maps were found', done['error'])


class Routes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        catalogue = dict(defaultMap='URB_Bar', maps=dict(URB_Bar=a_map('URB_Bar', ready=True, scope='map', priority=(99,)),
                                                        URB_New=a_map('URB_New')))
        live = Live(catalogue, FakeExports(catalogue), None, FakeLibrary(Path(self.tmp.name)))
        self.runner = precache.PrecacheRunner(live, Path(self.tmp.name), export_version=99, pause=0.01,
                                              command=lambda game: [sys.executable, '-c', PROGRAM % ''])
        self.server = LocalServer(('127.0.0.1', 0), partial(Handler, live=live, precache=self.runner))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = 'http://127.0.0.1:%d' % self.server.server_port

    def call(self, method, path, body=None, origin=True):
        headers = {'Content-Type': 'application/json'}
        headers['Origin'] = self.base if origin else 'http://elsewhere.example'
        request = Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                          headers=headers)
        try:
            with urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_the_state_the_plan_a_start_and_a_cancel(self):
        status, body = self.call('GET', '/precache.json')
        self.assertEqual((status, body['state'], 'plan' in body), (200, 'idle', False))
        status, body = self.call('GET', '/precache.json?plan=1')
        self.assertEqual((status, body['plan']['maps']['missing']), (200, 1))
        self.assertEqual(self.call('POST', '/precache/start', dict())[0], 400)
        self.assertEqual(self.call('POST', '/precache/start', dict(maps=True), origin=False)[0], 403)
        status, body = self.call('POST', '/precache/start', dict(maps=True))
        self.assertEqual((status, body['state']), (202, 'running'))
        end = time.monotonic() + 20
        while self.call('GET', '/precache.json')[1]['state'] == 'running' and time.monotonic() < end:
            time.sleep(0.02)
        status, body = self.call('GET', '/precache.json')
        self.assertEqual((body['state'], body['maps']['made']), ('done', 1))
        # nothing runs: a cancel answers the state as it is
        self.assertEqual(self.call('POST', '/precache/cancel', dict())[1]['state'], 'done')


if __name__ == '__main__':
    unittest.main()
