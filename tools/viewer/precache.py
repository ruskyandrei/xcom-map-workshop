"""The cache filled ahead of use: every piece of the game's maps, and (asked for separately) every map.

The editor caches as it goes: a piece of another map is exported the first time it is placed or a prefab with it is
opened (library.piece), a map the first time it is opened (exports.py). This does it all at once, in the background,
for the page's Settings menu ("Cache everything..."): one job at a time, which can be cancelled at any moment. What is
already in the cache is left; what the cache holds for another file of a map is made again, as is a piece of an older
piece version (library.PIECE_VERSION) or a map an older exporter prepared.

  GET  /precache.json           the job's state (below); with ?plan=1 also what there is to do: {pieces: {ready,
                                stale, total, kept, missing, maps}, maps: {available, total, ready, outdated,
                                missing}, free (bytes left on the cache's drive), estimates}
  POST /precache/start          {pieces: bool, maps: bool} starts the job (202; the running job's state if there is one)
  POST /precache/cancel         stops it: what is cached stays. The pieces' process is asked to stop (a stop file,
                                seen between pieces, so no file of the cache is left half written) and is killed
                                only if it has not gone after STOP_GRACE seconds; a map in hand is abandoned (its
                                export goes to a folder of its own, which the map list never takes)

The state: {state: idle | running | done | cancelled | failed, phase: 'pieces' | 'maps' | None, what, done, total,
fraction, seconds, startedAt, error, options, pieces: {made, kept, failed, failures, pruned} | None,
maps: {made, failed, failures} | None}.

The pieces are `viewer.py library precache` in a process of its own (library.precache: a donor map to a worker); it
reads the library first when it is not there or the install's maps changed. It is a contained process tree, as a
build is (procs.launch; review finding 48): its workers end with it, a kill ends the whole tree by its job (never by a
process id that may have been reused), and it ends with the server. It writes a donor's pieces under the same lock as
the server's own piece requests (library.donor_lock), so the two never write the same files at once. The maps go one after another through
the server's own exporter (ExportRunner), so each takes its place in the map list as it is done, and waits its turn
when the page is preparing a map itself.
"""
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

from builds import PROGRESS
import procs
from projects import ProjectError

VIEWER = Path(__file__).resolve().parent / 'viewer.py'
OWNER = 'precache'
FAILURES_SHOWN = 50
STOP_GRACE = 20
# what one takes, going by a run of every piece and the maps exported so far (the plan's estimates)
PIECE_SECONDS, PIECE_BYTES = 0.065, 660_000
MAP_SECONDS, MAP_BYTES = 28, 130_000_000


def now():
    return datetime.datetime.now().isoformat(timespec='seconds')


class PrecacheRunner:
    def __init__(self, live, cache, command=None, export_version=None, pause=0.5, grace=STOP_GRACE):
        """live: the server's Live (its library, exporter and map list change with the game install); cache: the cache
        root; command(game) gives the pieces' command line (tests stub it); export_version: the exporter's, for the
        maps exported by an older one (None: read from export.py); grace: the seconds a cancelled pieces' process
        has to stop by itself."""
        self.live, self.cache, self.pause, self.grace = live, Path(cache), pause, grace
        self.stop_file = self.cache / 'library' / 'precache.stop'
        self.command = command or (lambda game: [sys.executable, '-B', '-u', str(VIEWER), 'library', 'precache',
                                                 '--cache', str(self.cache), '--game', str(game),
                                                 '--stop-file', str(self.stop_file)])
        self.export_version = export_version
        self.lock = threading.Lock()
        self.job = None

    # ------------------------------------------------------------------------------------------------ what there is
    def version(self):
        if self.export_version is None:
            from export import EXPORT_VERSION
            self.export_version = EXPORT_VERSION
        return self.export_version

    def maps_todo(self):
        """The install's maps not exported, or exported by an older exporter: [(entry, again)]."""
        catalogue = self.live.catalogue
        todo = []
        for entry in list(catalogue['maps'].values()):
            if not entry.get('installed'):
                continue
            version = (entry.get('priority') or (0,))[0]
            old = bool(entry.get('ready') and entry.get('scope') == 'map' and isinstance(version, int)
                       and version < self.version())
            if not entry.get('ready') or old:
                todo.append((entry, old))
        return todo

    def plan(self):
        import library
        pieces = dict(ready=False, stale=False, total=None, kept=None, missing=None, maps=None)
        runner = self.live.library
        if runner is not None:
            try:
                game = runner.install()
                index, _ = runner.index()
                if index is not None:
                    donors = library.piece_plan(self.cache, game, index)
                    total = sum(len(d['actors']) for d in donors)
                    missing = sum(len(d['missing']) for d in donors)
                    pieces = dict(ready=True, stale=any(library.stale(index, game)), total=total, kept=total - missing,
                                  missing=missing, maps=len(donors))
            except (ProjectError, OSError, ValueError) as error:
                pieces['error'] = getattr(error, 'message', None) or str(error)
        else:
            pieces['error'] = 'This server has no library.'
        maps = dict(available=self.live.exports is not None, total=0, ready=0, outdated=0, missing=0)
        if maps['available']:
            listed = [e for e in list(self.live.catalogue['maps'].values()) if e.get('installed')]
            todo = self.maps_todo()
            outdated = sum(1 for _, old in todo if old)
            maps.update(total=len(listed), outdated=outdated, missing=len(todo) - outdated,
                        ready=len(listed) - len(todo))
        try:
            self.cache.mkdir(parents=True, exist_ok=True)
            free = shutil.disk_usage(self.cache).free
        except OSError:
            free = None
        todo_maps = maps['missing'] + maps['outdated']
        return dict(pieces=pieces, maps=maps, free=free, estimates=dict(
            pieces=dict(seconds=round((pieces['missing'] or 0) * PIECE_SECONDS) + (0 if pieces['ready'] and not pieces['stale'] else 40),
                        bytes=(pieces['missing'] or 0) * PIECE_BYTES, known=pieces['ready']),
            maps=dict(seconds=todo_maps * MAP_SECONDS, bytes=maps['missing'] * MAP_BYTES)))

    # ------------------------------------------------------------------------------------------------ the job
    def _status(self):
        job = self.job
        if not job:
            return dict(state='idle', phase=None, what=None, done=0, total=0, fraction=None, seconds=None,
                        startedAt=None, error=None, options=None, pieces=None, maps=None)
        seconds = round(time.monotonic() - job['started'], 1) if job['state'] == 'running' else job['seconds']
        return dict(state=job['state'], phase=job['phase'], what=job['what'], done=job['done'], total=job['total'],
                    fraction=job['fraction'], seconds=seconds, startedAt=job['startedAt'], error=job['error'],
                    options=job['options'], pieces=job['pieces'], maps=job['maps'])

    def running(self):
        """Whether the job runs."""
        with self.lock:
            return bool(self.job and self.job['state'] == 'running')

    def status(self, plan=False):
        with self.lock:
            out = self._status()
        if plan:
            out['plan'] = self.plan()
        return out

    def start(self, options):
        options = options if isinstance(options, dict) else {}
        want = dict(pieces=bool(options.get('pieces')), maps=bool(options.get('maps')))
        if not (want['pieces'] or want['maps']):
            raise ProjectError(400, 'Choose what to cache: the pieces, the maps, or both.')
        if want['pieces']:
            if self.live.library is None:
                raise ProjectError(409, 'This server has no library of pieces.')
            self.live.library.install()         # (the game install must be there: says so now, not in the job)
        if want['maps'] and self.live.exports is None:
            raise ProjectError(409, 'This server does not prepare maps.')
        with self.lock:
            if self.job and self.job['state'] == 'running':
                return self._status()
            job = dict(state='running', phase=None, what='Starting', done=0, total=0, fraction=None, seconds=0,
                       startedAt=now(), started=time.monotonic(), error=None, options=want, pieces=None, maps=None,
                       cancelled=False, pid=None)
            self.job = job
            threading.Thread(target=self._run, args=(job,), daemon=True).start()
            return self._status()

    def cancel(self):
        with self.lock:
            job = self.job
            if not job or job['state'] != 'running':
                return self._status()
            job['cancelled'] = True
            tree = job.get('tree')
        if tree:
            # asked first; killed if it has not gone by then
            try:
                self.stop_file.parent.mkdir(parents=True, exist_ok=True)
                self.stop_file.write_text('stop\n', encoding='utf-8')
            except OSError:
                tree.terminate()
            else:
                timer = threading.Timer(self.grace, lambda: job.get('tree') is tree and tree.terminate())
                timer.daemon = True
                timer.start()
        if self.live.exports is not None:
            self.live.exports.cancel_owned(OWNER)
        return self.status()

    def _run(self, job):
        error = None
        try:
            if job['options']['pieces'] and not job['cancelled']:
                self._pieces(job)
            if job['options']['maps'] and not job['cancelled']:
                self._maps(job)
        except ProjectError as problem:
            error = problem.message
        except Exception as problem:  # noqa: BLE001 (the job's state must say it stopped, whatever stopped it)
            error = '%s: %s' % (type(problem).__name__, problem)
        with self.lock:
            job['seconds'] = round(time.monotonic() - job['started'], 1)
            job['error'] = error
            job['pid'], job['tree'] = None, None
            job['state'] = 'cancelled' if job['cancelled'] else 'failed' if error else 'done'

    def _pieces(self, job):
        game = self.live.library.install()
        self.stop_file.unlink(missing_ok=True)
        with self.lock:
            job.update(phase='pieces', what='Reading the library', done=0, total=0, fraction=None)
            if job['cancelled']:
                return
            try:
                tree = procs.launch(self.command(game), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    encoding='utf-8', errors='replace', creationflags=procs.CREATE_NO_WINDOW)
            except OSError as error:
                raise ProjectError(500, 'Caching the pieces did not start: %s' % error)
            job['pid'], job['tree'] = tree.pid, tree
            proc = tree.proc
        lines, result = [], None
        for raw in proc.stdout:
            line = raw.strip()
            m = PROGRESS.match(line)
            if m and m.group(2):
                done, total = int(m.group(2)), int(m.group(3))
                with self.lock:
                    job.update(what=m.group(1)[:1].upper() + m.group(1)[1:], done=done, total=total,
                               fraction=round(done / total, 4) if total else None)
            elif line.startswith('result: '):
                try:
                    result = json.loads(line[len('result: '):])
                except ValueError:
                    pass
            elif line:
                lines.append(line)
        proc.stdout.close()
        code = proc.wait()
        tree.drain(timeout=30, kill_after=5)        # its workers too, before the job says it is done
        tree.close()
        self.stop_file.unlink(missing_ok=True)
        with self.lock:
            job['pid'], job['tree'] = None, None
            if job['cancelled']:
                if result:      # it stopped by itself: what it had read by then
                    job['pieces'] = dict(made=result.get('made', 0), kept=result.get('kept', 0), failed=0, failures=[],
                                         pruned=0)
                return
        if code or result is None:
            raise ProjectError(500, 'Caching the pieces stopped: %s' % (lines[-1] if lines else 'exit %d' % code))
        failed = result.get('failed') or []
        with self.lock:
            job['pieces'] = dict(made=result.get('made', 0), kept=result.get('kept', 0), failed=len(failed),
                                 failures=['%s of %s: %s' % (f['actor'], f['package'], f['error'])
                                           for f in failed[:FAILURES_SHOWN]],
                                 pruned=result.get('pruned', 0))

    def _maps(self, job):
        exports = self.live.exports
        todo = self.maps_todo()
        made, failures = 0, []
        with self.lock:
            job.update(phase='maps', what='Preparing the maps', done=0, total=len(todo),
                       fraction=0 if todo else None, maps=dict(made=0, failed=0, failures=[]))
        for k, (entry, again) in enumerate(todo):
            map_id, label = entry['id'], entry.get('label') or entry['id']
            state = None
            while not job['cancelled']:
                try:
                    state = exports.start(map_id, prepare=again, owner=OWNER)
                    break
                except ProjectError as problem:
                    if problem.status == 409 and problem.extra.get('exporting'):
                        # the page is preparing a map of its own: wait for it
                        with self.lock:
                            job['what'] = 'Waiting for %s, which is being prepared' % problem.extra['exporting']
                        time.sleep(self.pause)
                        continue
                    state = dict(state='failed', error=problem.message)
                    break
            while state and state.get('state') == 'running':
                with self.lock:
                    part = (state.get('progress') or {}).get('fraction') or 0
                    job.update(what='Preparing %s' % label, done=k, fraction=round((k + part) / len(todo), 4))
                time.sleep(self.pause)
                if job['cancelled']:
                    exports.cancel_owned(OWNER)
                state = exports.status(map_id)
            if job['cancelled']:
                break
            if state and state.get('state') == 'ready':
                made += 1
            else:
                failures.append('%s: %s' % (label, (state or {}).get('error') or 'it was not prepared'))
            with self.lock:
                job.update(done=k + 1, fraction=round((k + 1) / len(todo), 4))
                job['maps'] = dict(made=made, failed=len(failures), failures=failures[:FAILURES_SHOWN])
        with self.lock:
            job['maps'] = dict(made=made, failed=len(failures), failures=failures[:FAILURES_SHOWN])
