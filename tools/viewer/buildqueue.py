"""The build queue (build queue plan, sections 3, 6 and 9): the project manager's Build puts the ticked projects in a
queue, and the server builds them one after another, each a full build (lighting baked) of the project as it is saved
when its turn comes.

  GET  /manager/queue.json     the queue: its state, its rows, the running build's stage, step and progress, whose
                               build it waits for, each waiting row's estimate, and what may be done now (actions)
  POST /manager/queue          {"projects": [id...], envelope}: add; a new queue starts at once, a stopped one stays
                               stopped (202)
  POST /manager/queue/stop     {envelope}: stop (202 while the running build drains, 200 once settled)
  POST /manager/queue/resume   {envelope}: go on from the first waiting row (202)
  POST /manager/queue/remove   {"items": [itemId...], envelope}: take waiting rows out (200)
  POST /manager/queue/clear    {envelope}: every row and result gone, the queue idle (200); never a project or package
  POST /manager/queue/reset    {"requestId", "confirm": true}: a queue file that can't be read set aside (archived),
                               and the queue idle; only when nothing of it can still be writing

The envelope is {queueId, expectedRevision, requestId}: the queue the page saw (null for an idle store that has no
queue), the revision it saw, and a UUID of the request. A request whose id was seen before gets the answer it got
then (with the queue now); the same id with other contents, or a stale queue or revision, is 409 with the queue now.
Receipts are kept RECEIPT_DAYS days, across Clear and new queues. The revision moves with transitions, not with
progress lines.

States: idle (empty), running (it may be waiting for another's build, or for a reader of the next project's package:
waitingFor), stopping (its build being stopped), stopped (Resume goes on; recovering while an earlier server's build of
it is proved gone), finished (every row built or failed; it stays until Clear or the next Build). Rows: waiting,
starting, building, built, failed.

How a row is built (one worker thread while the queue runs, the build slot reserved for the whole queue,
builds.py reserve):
  1. it waits while another holds the slot (the editor's Build, a prefab test), or while a reader holds the project's
     package (builds.py claim);
  2. the launch intent is written (the row starting, its attempt's id), then the project is captured as saved
     (builds.capture: projects.py capture) into an immutable snapshot, <builds>/.work/queue-attempts/<attempt>/
     project.json, with the map picture it names beside it (project.picture.png), as the editor's Build captures;
  3. if Stop came meanwhile nothing is launched; else build.py builds the snapshot, every folder pinned from the
     context the queue started with (builds.py start_queued);
  4. once the attempt has ended (its processes gone, its package swap settled), the package is verified as this
     attempt's (its token, project, revision, a full build, its files) and the row is built, or failed with why.
A project that can't be read, or whose build fails, fails alone and the queue goes on. A store that can't be written
holds the queue (its rows as they were) and says so.

Stop closes dispatch at once and stops the queue's own build (the row waits again, built if its package went in
first); a build of someone else's it was waiting for is left running. Resume captures the project again: the latest
save, from the beginning.

The queue lives in <builds>/.work/build-queue.json (a unique temporary file, then a replace; the last good file kept as
build-queue.json.bak), owned by one server through an operating-system lock on <builds>/.work/build-queue.lock,
taken once the server's port is bound (activate). A restarted server starts nothing: the rows it finds starting or
building are settled once their builds are proved gone (a package of that very attempt in place is built, even if
its result was never written; anything else waits again), and the queue is stopped until Resume. A file it can't read,
or of a newer schema, is not an empty queue: its bytes are kept, the queue says why, and only reset sets it aside.

The context (projects, builds, cache, game install, UDK, the other install names are checked against) is pinned when a
queue starts. While it runs or stops, choosing another game install is refused (settings_guard); a stopped queue whose
context changed meanwhile can't Resume or take more rows: Clear, then queue again.
"""
import copy
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import threading
import time
import uuid

from builds import capture as capture_project
import publication
from projects import ID, ProjectError

SCHEMA = 'xcom-map-workshop/build-queue'
SCHEMA_VERSION = 1
MAX_ROWS = 1000
RECEIPT_DAYS = 7
RECEIPT_MAX = 1000
DIAGNOSTICS = 5             # earlier attempts kept per row
ATTEMPT_DAYS = 14           # snapshots of attempts no row names any more are deleted after this
POLL = 2.0                  # the worker's fallback poll while it waits for the slot (it is woken when it may free)
ENVELOPE = ('queueId', 'expectedRevision', 'requestId')


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def problem(status, message, code, **extra):
    return ProjectError(status, message, code=code, **extra)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def empty():
    return dict(schema=SCHEMA, schemaVersion=SCHEMA_VERSION, queueId=None, revision=0, state='idle', context=None,
                stopReason=None, createdAt=None, updatedAt=utc(), activeSeconds=0.0, items=[], diagnostics={},
                receipts={})


def valid(data):
    """Whether a loaded file is a queue of this schema with rows of the right shape (raises ValueError saying why)."""
    if not isinstance(data, dict) or data.get('schema') != SCHEMA:
        raise ValueError('it is not a build queue')
    if data.get('schemaVersion') != SCHEMA_VERSION:
        raise ValueError(f'it is of schema version {data.get("schemaVersion")}, and this editor reads {SCHEMA_VERSION}')
    if data.get('state') not in ('idle', 'running', 'stopping', 'stopped', 'finished'):
        raise ValueError('its state is unknown')
    if not isinstance(data.get('items'), list) or not isinstance(data.get('revision'), int):
        raise ValueError('its rows are malformed')
    for item in data['items']:
        if (not isinstance(item, dict) or not ID.fullmatch(str(item.get('itemId'))) or not ID.fullmatch(str(item.get('project')))
                or item.get('state') not in ('waiting', 'starting', 'building', 'built', 'failed')):
            raise ValueError('a row is malformed')
    for key, kind in (('diagnostics', dict), ('receipts', dict)):
        if not isinstance(data.get(key, {}), kind):
            raise ValueError(f'its {key} are malformed')
    return data


class AttemptRef:
    """What verification needs of an attempt the queue launched before this server started (builds.verify)."""

    def __init__(self, attempt_id, project, variant, output):
        self.id, self.variant, self.output = attempt_id, variant, Path(output)
        self.job = dict(project=project)


class BuildQueue:
    def __init__(self, projects, builds, context, clock=time.monotonic):
        """projects: the ProjectStore; builds: the BuildRunner; context(): the folders and installs a build uses now
        (dict(projects, output, cache, game, udk, checkGames), or raises ProjectError why there are none).
        Nothing is read or locked until activate."""
        self.projects, self.builds, self.context, self.clock = projects, builds, context, clock
        self.root = builds.output / '.work'
        self.file = self.root / 'build-queue.json'
        self.backup = self.root / 'build-queue.json.bak'
        self.attempts = self.root / 'queue-attempts'
        self.owner = publication.FileLock(self.root / 'build-queue.lock')
        self.lock = threading.RLock()
        self.cond = threading.Condition(self.lock)
        self.q = None
        self.available, self.unavailable = False, 'The build queue is starting.'
        self.error = None           # the file can't be read: dict(message, kept)
        self.notice = None          # restored from the backup, and why
        self.fault = None           # the store can't be written: dispatch held
        self.recovering = False
        self.waiting_for = None
        self.worker, self.worker_live = None, False
        self.token = str(uuid.uuid4())     # this server's queue as the slot's owner
        self.active = None          # (item, Attempt) being built
        self.stop_after = None      # the attempt a stop tells the builds runner to stop once it is saved (_stopping)
        self.ran_since = None       # clock() when the queue last started running (active seconds)
        self.started_at = {}        # item id -> clock() when its build started
        self.estimates = {}         # item id -> seconds or None
        self.hooks = {}             # name -> callable(item): tests hold the worker at a step
        builds.queue = self
        builds.listeners.append(self.poke)

    # ------------------------------------------------------------------ owning and loading the store

    def activate(self):
        """Once the server's port is bound: own the store (another server holding it leaves this queue unavailable),
        load it and reconcile what an earlier server left. Starts no build."""
        try:
            got = self.owner.acquire(0)
        except OSError as error:
            got, why = False, f'The build queue\'s lock could not be taken: {error}'
        else:
            why = ('Another editor server owns this builds folder\'s build queue. Use that server, or stop it and '
                   'restart this one.')
        if not got:
            with self.lock:
                self.unavailable = why
            return False
        with self.lock:
            self.available, self.unavailable = True, None
            self._load()
            interrupted = self.q and [i for i in self.q['items'] if i['state'] in ('starting', 'building')]
            if self.q and (interrupted or self.q['state'] in ('running', 'stopping')):
                self.recovering = True
                pending = any(i['state'] != 'built' and i['state'] != 'failed' for i in self.q['items'])
                self.q['state'] = 'stopped' if pending else 'finished'
                self.q['stopReason'] = ('The editor stopped while the queue was building. Resume goes on.' if pending else None)
            self._prune_attempts()
        threading.Thread(target=self._recover, daemon=True, name='build-queue-recover').start()
        return True

    def close(self, wait=120.0):
        """The server is closing: stop the queue (its build drained) and let go of the store."""
        with self.lock:
            running = self.available and self.q and self.q['state'] in ('running', 'stopping')
        if running:
            try:
                self._stop(reason='The editor was closed while the queue was building. Resume goes on.')
            except ProjectError:
                # the queue can't be saved: its build is stopped all the same, as the server is closing (the file
                # still says running, which the next server's start makes sure has ended)
                with self.lock:
                    attempt = self.active[1] if self.active else None
                if attempt is not None:
                    self._tell_stop(attempt.id)
            end = self.clock() + wait
            while self.clock() < end:
                with self.lock:
                    if not (self.worker and self.worker.is_alive()):
                        break
                time.sleep(0.1)
        self.owner.release()

    def _load(self):
        self.q, self.error, self.notice = None, None, None
        try:
            raw = self.file.read_bytes()
        except FileNotFoundError:
            raw = None
        except OSError as error:
            self.error = dict(message=f'The build queue\'s file could not be read: {error}', kept=str(self.file))
            return
        if raw is None:
            restored = self._from_backup()
            if restored is not None:
                self.q = restored
                self.notice = 'The queue\'s file was missing; its last good copy was read.'
            else:
                self.q = empty()
            return
        data = None
        try:
            data = json.loads(raw.decode('utf-8'))
            self.q = valid(data)
            self.q.setdefault('diagnostics', {})
            self.q.setdefault('receipts', {})
            return
        except (UnicodeDecodeError, ValueError) as error:
            reason = str(error)
            # a queue of a newer editor is left for it, not replaced by the last good copy: told by its version, not by
            # the error's words, so an older version's file is restored from the copy (review finding 50)
            version = data.get('schemaVersion') if isinstance(data, dict) and data.get('schema') == SCHEMA else None
            newer = isinstance(version, int) and not isinstance(version, bool) and version > SCHEMA_VERSION
        kept = self.root / f'build-queue.unreadable-{datetime.datetime.now():%Y%m%d-%H%M%S}.json'
        try:
            shutil.copyfile(self.file, kept)
        except OSError:
            kept = self.file
        restored = None if newer else self._from_backup()
        if restored is not None:
            self.q = restored
            self.notice = (f'The queue\'s file could not be read ({reason}; kept as {kept.name}); its last good copy was '
                           'read, its builds stopped.')
            return
        self.error = dict(message=f'The build queue\'s file can\'t be read: {reason}. It is kept as it is ({kept}); reset '
                                  f'the queue to set it aside and start again.', kept=str(kept))

    def _from_backup(self):
        try:
            data = valid(json.loads(self.backup.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            return None
        data.setdefault('diagnostics', {})
        data.setdefault('receipts', {})
        for item in data['items']:
            if item['state'] in ('starting', 'building'):
                item['state'] = 'waiting' if not item.get('attempt') else item['state']
        return data

    def _save(self):
        """The queue to disk (a unique temporary file, then a replace; the file it replaces kept as the last good
        copy). Raises OSError; the caller decides."""
        self.q['updatedAt'] = utc()
        self.root.mkdir(parents=True, exist_ok=True)
        temp = self.file.with_name(f'{self.file.name}.{uuid.uuid4().hex[:10]}.tmp')
        with open(temp, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(self.q, stream, indent=1)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        try:
            if self.file.is_file():
                current = self.file.read_bytes()
                try:
                    valid(json.loads(current.decode('utf-8')))
                    spare = self.backup.with_name(f'{self.backup.name}.{uuid.uuid4().hex[:10]}.tmp')
                    spare.write_bytes(current)
                    os.replace(spare, self.backup)
                except (UnicodeDecodeError, ValueError):
                    pass
            os.replace(temp, self.file)
        finally:
            temp.unlink(missing_ok=True)

    def _commit(self, before):
        """Save, or put the queue back as it was (`before`) and say the store can't be written. A page's request that
        is saved clears a fault the worker met (the store can be written again; Resume goes on)."""
        try:
            self._save()
            self.fault = None
        except OSError as error:
            self.q = before
            self.fault = f'The build queue could not be saved ({error}); nothing changed and no build starts until it can.'
            raise problem(500, self.fault, 'queue-storage', queue=self._view())
        self._settled_slot()

    def _settled_slot(self):
        """A queue that has stopped or finished lets go of the build slot in the same step that says so (the worker
        lets go too as it leaves; a second release changes nothing)."""
        if self.q['state'] in ('stopped', 'finished', 'idle'):
            self.builds.release(self.token)

    # ------------------------------------------------------------------ requests

    def _usable(self):
        if not self.available:
            raise problem(409, self.unavailable or 'The build queue is unavailable.', 'queue-unavailable')
        if self.error:
            raise problem(409, self.error['message'], 'queue-unreadable', queue=self._view())

    @staticmethod
    def _envelope(request, keys):
        if not isinstance(request, dict) or set(request) - set(ENVELOPE) - set(keys):
            raise problem(400, 'Send {queueId, expectedRevision, requestId} and the request\'s own fields.', 'queue-request')
        queue_id, revision, request_id = request.get('queueId'), request.get('expectedRevision'), request.get('requestId')
        if not (queue_id is None or (isinstance(queue_id, str) and ID.fullmatch(queue_id))):
            raise problem(400, 'queueId is the queue\'s id or null.', 'queue-request')
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise problem(400, 'expectedRevision is a whole number.', 'queue-request')
        if not (isinstance(request_id, str) and ID.fullmatch(request_id)):
            raise problem(400, 'requestId is a UUID.', 'queue-request')
        return queue_id, revision, request_id

    @staticmethod
    def _ids(value, what):
        if not isinstance(value, list) or not value:
            raise problem(400, f'Send "{what}": [id...].', 'queue-request')
        if len(value) > MAX_ROWS:
            raise problem(400, f'At most {MAX_ROWS} {what} in one request.', 'queue-request')
        if not all(isinstance(v, str) and ID.fullmatch(v) for v in value):
            raise problem(400, f'"{what}" are UUIDs.', 'queue-request')
        return list(dict.fromkeys(value))

    def _request(self, action, request, keys, act):
        """A change to the queue (see the module notes): (HTTP status, answer)."""
        queue_id, revision, request_id = self._envelope(request, keys)
        payload = {k: request.get(k) for k in keys}
        fingerprint = digest([action, payload, queue_id, revision])
        starts = False
        with self.lock:
            self._usable()
            receipts = self.q['receipts']
            seen = receipts.get(request_id)
            if seen is not None:
                if seen['hash'] != fingerprint:
                    raise problem(409, 'That request id was used for another request.', 'request-conflict', queue=self._view())
                return seen['status'], dict(seen['answer'], repeated=True, queue=self._view())
            if queue_id != self.q['queueId'] or revision != self.q['revision']:
                raise problem(409, 'The queue changed since this page saw it.', 'queue-stale', queue=self._view())
            before = copy.deepcopy(self.q)
            try:
                status, answer, changed, starts = act(payload)
            except BaseException:
                self.q, self.stop_after = before, None      # a request refused part-way leaves the queue as it was
                raise
            if changed:
                self.q['revision'] += 1
            receipts[request_id] = dict(hash=fingerprint, at=time.time(), action=action, status=status, answer=answer)
            self._prune_receipts()
            try:
                self._commit(before)
            finally:
                stop, self.stop_after = self.stop_after, None
            if stop is not None:
                self._tell_stop(stop)       # (saved: a queue that can't be saved stays running, its build too)
            if starts:
                self._start_worker()
            self.cond.notify_all()
            return status, dict(answer, queue=self._view())

    def _prune_receipts(self):
        receipts = self.q['receipts']
        old = time.time() - RECEIPT_DAYS * 86400
        for key in [k for k, v in receipts.items() if not isinstance(v, dict) or v.get('at', 0) < old]:
            del receipts[key]
        if len(receipts) > RECEIPT_MAX:
            for key in sorted(receipts, key=lambda k: receipts[k]['at'])[:len(receipts) - RECEIPT_MAX]:
                del receipts[key]

    def add(self, request):
        def act(payload):
            ids = self._ids(payload['projects'], 'projects')
            q = self.q
            if q['state'] == 'stopping':
                raise problem(409, 'The queue is stopping; add the projects once it has stopped.', 'queue-stopping', queue=self._view())
            fresh = q['state'] in ('idle', 'finished')
            if fresh:
                context = self._current_context()
                q.update(queueId=str(uuid.uuid4()), state='running', context=context, stopReason=None, createdAt=utc(),
                         activeSeconds=0.0, items=[], diagnostics={})
                self.estimates.clear()
            elif q['state'] == 'stopped':
                self._same_context()
            rows = {i['project']: i for i in q['items']}
            appended, already, reset = [], [], []
            for project_id in ids:
                item = rows.get(project_id)
                if item and item['state'] in ('waiting', 'starting', 'building'):
                    already.append(project_id)
                elif item:
                    self._remember(item)
                    q['items'].remove(item)
                    item.update(state='waiting', queuedAt=utc(), attempt=None, error=None, interrupted=None,
                                startedAt=None, endedAt=None, seconds=None, result=None)
                    q['items'].append(item)
                    reset.append(project_id)
                else:
                    item = dict(itemId=str(uuid.uuid4()), project=project_id, name=self._name(project_id), variant=None,
                                state='waiting', queuedAt=utc(), attempt=None, attempts=0, error=None, interrupted=None,
                                startedAt=None, endedAt=None, seconds=None, result=None)
                    q['items'].append(item)
                    rows[project_id] = item
                    appended.append(project_id)
                self.estimates[item['itemId']] = self._estimate(item)
            if len(q['items']) > MAX_ROWS:
                raise problem(409, f'A queue holds at most {MAX_ROWS} rows.', 'queue-full', queue=self._view())
            if q['state'] == 'running' and fresh:
                self.ran_since = self.clock()
            return 202, dict(appended=appended, alreadyQueued=already, reset=reset), True, q['state'] == 'running'
        return self._request('add', request, ('projects',), act)

    def stop(self, request):
        def act(payload):
            return self._stopping(reason='Stopped. Resume goes on from the first waiting project.')
        return self._request('stop', request, (), act)

    def _stopping(self, reason):
        q = self.q
        if q['state'] == 'stopping':
            return 202, dict(stopped=False), False, False
        if q['state'] != 'running':
            return 200, dict(stopped=True), False, False
        self._accumulate()
        building = self.active is not None or any(i['state'] in ('starting', 'building') for i in q['items'])
        q.update(state='stopping' if building else 'stopped', stopReason=reason)
        attempt = self.active[1] if self.active else None
        # its build is told to stop by the caller once the change is saved (_tell_stop)
        self.stop_after = attempt.id if attempt is not None else None
        self.waiting_for = None
        return (202 if building else 200), dict(stopped=not building), True, False

    def _stop(self, reason):
        """Stop without a page's request (Cancel in the build window, the server closing)."""
        with self.lock:
            if not self.available or self.error or self.q['state'] != 'running':
                return
            before = copy.deepcopy(self.q)
            _, _, changed, _ = self._stopping(reason)
            stop, self.stop_after = self.stop_after, None
            if changed:
                self.q['revision'] += 1
                self._commit(before)        # (one that can't be saved raises: the queue and its build go on)
            if stop is not None:
                self._tell_stop(stop)
            self.cond.notify_all()

    def _tell_stop(self, attempt_id):
        """The builds runner told to stop the queue's build, on a thread of its own: the runner's lock comes after
        this one."""
        threading.Thread(target=self.builds.stop_attempt, args=(attempt_id,), daemon=True, name='build-queue-stop').start()

    def stop_for(self, attempt_id):
        """The build window's Cancel on the queue's build: the queue stops (its build with it)."""
        with self.lock:
            if not (self.active and self.active[1].id == attempt_id):
                raise problem(409, 'That build has ended; another one is running now.', 'stale-attempt')
        self._stop('Stopped from the build\'s window. Resume goes on from the first waiting project.')

    def resume(self, request):
        def act(payload):
            q = self.q
            if q['state'] == 'stopping':
                raise problem(409, 'The queue is still stopping.', 'queue-stopping', queue=self._view())
            if q['state'] != 'stopped':
                return 200, dict(resumed=False), False, False
            if self.recovering:
                raise problem(409, 'The queue is still making sure the builds of before the restart have ended.',
                              'queue-recovering', queue=self._view())
            self._same_context()
            if not any(i['state'] == 'waiting' for i in q['items']):
                q.update(state='finished' if q['items'] else 'idle', stopReason=None)
                if not q['items']:
                    q.update(queueId=None, context=None)
                return 200, dict(resumed=False), True, False
            q.update(state='running', stopReason=None)
            self.ran_since = self.clock()
            for item in q['items']:
                if item['state'] == 'waiting':
                    self.estimates[item['itemId']] = self._estimate(item)
            return 202, dict(resumed=True), True, True
        return self._request('resume', request, (), act)

    def remove(self, request):
        def act(payload):
            ids = self._ids(payload['items'], 'items')
            q = self.q
            rows = {i['itemId']: i for i in q['items']}
            wrong = [i for i in ids if i not in rows or rows[i]['state'] != 'waiting']
            if wrong:
                raise problem(409, 'Only waiting rows can be removed, and these are not: ' + ', '.join(
                    rows[i]['name'] or rows[i]['project'] if i in rows else i for i in wrong) + '.', 'queue-remove',
                    queue=self._view())
            q['items'] = [i for i in q['items'] if i['itemId'] not in ids]
            for i in ids:
                q['diagnostics'].pop(i, None)
                self.estimates.pop(i, None)
            self._settle_if_done()
            return 200, dict(removed=ids), True, False
        return self._request('remove', request, ('items',), act)

    def clear(self, request):
        def act(payload):
            q = self.q
            if q['state'] in ('running', 'stopping'):
                raise problem(409, 'Stop the queue before clearing it.', 'queue-running', queue=self._view())
            if self.recovering:
                raise problem(409, 'The queue is still making sure the builds of before the restart have ended.',
                              'queue-recovering', queue=self._view())
            if q['state'] == 'idle' and not q['items']:
                return 200, dict(cleared=False), False, False
            receipts = q['receipts']
            self.q = dict(empty(), receipts=receipts, revision=q['revision'])
            self.estimates.clear()
            return 200, dict(cleared=True), True, False
        return self._request('clear', request, (), act)

    def reset(self, request):
        """The queue file that can't be read set aside and the queue started afresh (only when nothing of it can
        still be writing: no build running, no journal unsettled)."""
        if (not isinstance(request, dict) or set(request) - {'requestId', 'confirm'} or request.get('confirm') is not True
                or not (isinstance(request.get('requestId'), str) and ID.fullmatch(request['requestId']))):
            raise problem(400, 'Send {"requestId": a UUID, "confirm": true}.', 'queue-request')
        with self.lock:
            if not self.available:
                raise problem(409, self.unavailable or 'The build queue is unavailable.', 'queue-unavailable')
            if not self.error:
                return 200, dict(reset=False, queue=self._view())
        if self.builds.busy_info() or publication.pending(self.builds.output):
            raise problem(409, 'A build, or a package swap to settle, is still there: the queue file is set aside once '
                               'nothing can be writing.', 'queue-busy')
        with self.lock:
            archived = self.root / f'build-queue.reset-{datetime.datetime.now():%Y%m%d-%H%M%S}.json'
            try:
                if self.file.is_file():
                    os.replace(self.file, archived)
                self.q, self.error = empty(), None
                self._save()
            except OSError as error:
                raise problem(500, f'The queue file could not be set aside: {error}', 'queue-storage')
            return 200, dict(reset=True, archived=str(archived), queue=self._view())

    def settings_guard(self):
        """Called before the game install is changed (gamesetup.py): refused while the queue runs or stops."""
        with self.lock:
            if self.available and self.q and self.q['state'] in ('running', 'stopping'):
                raise problem(409, 'The build queue is building with this game install: stop it in the project manager '
                                   'before choosing another.', 'queue-running')

    # ------------------------------------------------------------------ helpers of the requests

    def _current_context(self):
        try:
            context = self.context()
        except ProjectError as error:
            raise problem(409, f'Not queued: {error.message}', 'queue-context')
        return {k: (str(v) if isinstance(v, Path) else [str(x) for x in v] if isinstance(v, (list, tuple)) else v)
                for k, v in context.items()}

    def _same_context(self):
        try:
            now = self._current_context()
        except ProjectError as error:
            raise problem(409, error.message, 'queue-context', queue=self._view())
        if self.q['context'] and now != self.q['context']:
            changed = ', '.join(k for k in sorted(set(now) | set(self.q['context'])) if now.get(k) != self.q['context'].get(k))
            raise problem(409, f'The queue was started with other settings ({changed} changed since): clear it, then '
                               'queue the projects again.', 'context-changed', queue=self._view())

    def _name(self, project_id):
        # (as the store last read the file: review finding 20)
        try:
            return self.projects.cached(project_id).get('name')
        except ProjectError:
            return None

    def _estimate(self, item):
        """How long the project's last full build took (its package's times.full), or None when unknown."""
        try:
            document = self.projects.cached(item['project'])
        except ProjectError:
            return None
        package = self.builds.package(item['project'], (document.get('output') or {}).get('shipAs'))
        seconds = ((package or {}).get('times') or {}).get('full')
        return seconds if isinstance(seconds, (int, float)) and math.isfinite(seconds) and seconds > 0 else None

    def _remember(self, item):
        """An ended row's attempt kept in its diagnostics (the last DIAGNOSTICS) before the row goes again."""
        if item.get('attempt') or item.get('result') or item.get('error'):
            kept = self.q['diagnostics'].setdefault(item['itemId'], [])
            kept.append({k: item.get(k) for k in ('state', 'attempt', 'startedAt', 'endedAt', 'seconds', 'result',
                                                  'error', 'interrupted')})
            del kept[:-DIAGNOSTICS]

    def _settle_if_done(self):
        """With no row left to build, a running or stopped queue settles: finished with results, idle without."""
        q = self.q
        if q['state'] not in ('running', 'stopped'):
            return
        if any(i['state'] in ('waiting', 'starting', 'building') for i in q['items']):
            return
        self._accumulate()
        q.update(state='finished' if q['items'] else 'idle', stopReason=None)
        if not q['items']:
            q.update(queueId=None, context=None)

    def _accumulate(self):
        if self.ran_since is not None:
            self.q['activeSeconds'] = round(self.q.get('activeSeconds', 0.0) + self.clock() - self.ran_since, 1)
            self.ran_since = None

    # ------------------------------------------------------------------ the worker

    def poke(self):
        """The slot or a lease may have freed (builds.py listeners)."""
        with self.cond:
            self.cond.notify_all()

    def _start_worker(self):
        """One worker at a time (`worker_live` is set and cleared under the lock, so a worker leaving can't be taken
        for one that goes on)."""
        if self.worker_live:
            return
        self.worker_live = True
        self.worker = threading.Thread(target=self._run, daemon=True, name='build-queue')
        self.worker.start()

    def _hook(self, name, item_id):
        hook = self.hooks.get(name)
        if hook:
            hook(item_id)

    def _row(self, item_id):
        return next((i for i in self.q['items'] if i['itemId'] == item_id), None)

    def _transition(self, change):
        """Apply change() to the queue and save it, the lock held. Rows are found by id inside change(), since a
        store that can't be written puts the queue back as it was (a copy): False then, and dispatch is held."""
        before = copy.deepcopy(self.q)
        change()
        self.q['revision'] += 1
        try:
            self._save()
            self._settled_slot()
            return True
        except OSError as error:
            self.q = before
            self.fault = (f'The build queue could not be saved ({error}): no further build starts until it can. Stop '
                          'and Resume once the builds folder can be written.')
            return False

    def _run(self):
        reserved = False
        try:
            self.builds.reserve(self.token, 'The build queue')
            reserved = True
            while self._step():
                pass
        except ProjectError:
            with self.lock:
                self.fault = 'Another build queue holds the build slot.'
        finally:
            with self.lock:
                self.waiting_for = None
                if self.q['state'] != 'running':
                    self._accumulate()
            if reserved:
                self.builds.release(self.token)
            with self.lock:
                self.worker_live = False
                # a row added, or Resume, while this worker was leaving: another goes on
                if (self.q['state'] == 'running' and not self.fault
                        and any(i['state'] == 'waiting' for i in self.q['items'])):
                    self._start_worker()

    def _back(self, item_id, why):
        """The row waits again (nothing of its attempt was launched); a stopping queue is stopped."""
        def change():
            item = self._row(item_id)
            if item:
                item.update(state='waiting', attempt=None, startedAt=None, interrupted=why)
            if self.q['state'] == 'stopping':
                self.q['state'] = 'stopped'
        self._transition(change)
        self.started_at.pop(item_id, None)

    def _step(self):
        """One row taken through (see the module notes). False when the worker is done."""
        with self.lock:
            while True:
                q = self.q
                if q['state'] != 'running' or self.fault:
                    return False
                item = next((i for i in q['items'] if i['state'] == 'waiting'), None)
                if item is None:
                    if self._transition(self._settle_if_done):
                        self.cond.notify_all()
                    return False
                busy = self.builds.busy_info(self.token)
                if busy:
                    self.waiting_for = dict(kind='build', name=busy['name'], project=busy['project'])
                    self.cond.wait(POLL)
                    continue
                if not self.builds.claim(item['project'], self.token):
                    self.waiting_for = dict(kind='reader', name=item['name'], project=item['project'])
                    self.cond.wait(POLL)
                    continue
                self.waiting_for = None
                item_id, project_id, generation = item['itemId'], item['project'], q['queueId']
                context = q['context']
                attempt_id = str(uuid.uuid4())

                def intent():
                    row = self._row(item_id)
                    row.update(state='starting', attempt=dict(id=attempt_id, number=row.get('attempts', 0) + 1),
                               attempts=row.get('attempts', 0) + 1, error=None, interrupted=None, startedAt=utc(),
                               endedAt=None, seconds=None, result=None)
                if not self._transition(intent):
                    self.builds.unclaim(project_id, self.token)
                    return False
                self.started_at[item_id] = self.clock()
                if item_id not in self.estimates:
                    self.estimates[item_id] = self._estimate(self._row(item_id))
                break
        self._hook('intent', item_id)
        # captured as saved, into a snapshot of its own with its picture (outside every lock but the store's own)
        folder = self.attempts / attempt_id
        try:
            document, sha, path, snapshot, picture = capture_project(self.projects, project_id, folder)
        except ProjectError as error:
            return self._ended(item_id, attempt_id, 'failed', error=f'It could not be read: {error.message}')
        except OSError as error:
            with self.lock:
                self._back(item_id, None)
                self.fault = f'The project\'s snapshot could not be written ({error}): no further build starts until it can.'
            self.builds.unclaim(project_id, self.token)
            return False
        self._hook('captured', item_id)
        revision = document.get('revision')
        variant = (document.get('output') or {}).get('shipAs')
        with self.lock:
            stopped = self.q['state'] != 'running' or self.q['queueId'] != generation
            if not stopped:
                try:
                    now = self._current_context()
                except ProjectError:
                    now = None
                if now != context:
                    stopped = True
                    self._accumulate()
                    self._transition(lambda: self.q.update(
                        state='stopped', stopReason='The settings changed since the queue started (the game install or a '
                                                    'folder): clear it, then queue the projects again.'))
            if stopped:
                self._back(item_id, 'Stopped before its build started: it starts again on Resume.')
                self.builds.unclaim(project_id, self.token)
                self.cond.notify_all()
                return False

            def captured():
                row = self._row(item_id)
                row['attempt'].update(revision=revision, digest=sha, file=str(path), **({'picture': picture} if picture else {}))
                row.update(variant=variant, name=document.get('name') or row['name'])
            if not self._transition(captured):
                self._back(item_id, None)
                self.builds.unclaim(project_id, self.token)
                return False
        try:
            handle = self.builds.start_queued(document, snapshot, context, path, self.token, attempt_id, folder / 'build.log',
                                              digest=sha, picture=picture)
        except ProjectError as error:
            self.builds.unclaim(project_id, self.token)
            if error.extra.get('code') == 'build-slot':
                with self.lock:
                    self._back(item_id, None)
                return True
            return self._ended(item_id, attempt_id, 'failed', error=error.message)
        except OSError as error:
            self.builds.unclaim(project_id, self.token)
            return self._ended(item_id, attempt_id, 'failed', error=f'Its build could not be started: {error}')
        with self.lock:
            self.active = (item_id, handle)
            self._transition(lambda: self._row(item_id).update(state='building'))
            cancel = self.q['state'] != 'running'
        if cancel:
            self.builds.stop_attempt(handle.id)
        self._hook('spawned', item_id)
        while not handle.done.wait(1.0):
            pass
        manifest = self.builds.verify(handle, revision, full=True)
        with self.lock:
            self.active = None
        if manifest:
            result = dict(buildId=manifest.get('buildId'), revision=revision, seconds=manifest.get('seconds'),
                          warnings=list(handle.job.get('warnings') or []), leftOut=len(manifest.get('leftOut') or []),
                          lightingUnchanged=bool(manifest.get('lightingUnchanged')))
            return self._ended(item_id, attempt_id, 'built', result=result)
        if handle.cancelled:
            return self._ended(item_id, attempt_id, 'waiting', interrupted='Stopped: it starts again on Resume, from the '
                                                                           'beginning, as it is saved then.')
        return self._ended(item_id, attempt_id, 'failed', error=handle.job.get('error') or
                           'The build ended without a package of its own.')

    def _ended(self, item_id, attempt_id, state, result=None, error=None, interrupted=None):
        self._hook('ended', item_id)
        with self.lock:
            began = self.started_at.pop(item_id, None)

            def change():
                item = self._row(item_id)
                if item is None or not item.get('attempt') or item['attempt'].get('id') != attempt_id:
                    return
                item.update(state=state, endedAt=utc(), result=result, error=error, interrupted=interrupted,
                            seconds=round(self.clock() - began, 1) if began is not None else None)
                if state == 'waiting':
                    self._remember(item)
                    item.update(attempt=None, startedAt=None, endedAt=None, seconds=None)
                if self.q['state'] == 'stopping':
                    self.q['state'] = 'stopped'
            ok = self._transition(change)
            item = self._row(item_id)
            if item:
                self.builds.unclaim(item['project'], self.token)
            self.cond.notify_all()
            return ok and self.q['state'] == 'running'

    # ------------------------------------------------------------------ after a restart

    def _recover(self):
        """The rows an earlier server left starting or building, settled once their builds are proved gone."""
        with self.lock:
            if not (self.q and self.recovering):
                return
            rows = [copy.deepcopy(i) for i in self.q['items'] if i['state'] in ('starting', 'building')]
        while True:
            keys = self._recovered_keys()
            alive = [i for i in rows if i.get('attempt') and i['attempt']['id'] in keys]
            if not alive:
                break
            with self.lock:
                self.waiting_for = dict(kind='recovering', name=alive[0]['name'], project=alive[0]['project'])
            time.sleep(1.0)
        results = {}
        for item in rows:
            attempt = item.get('attempt') or {}
            if attempt.get('id') and item.get('variant') and isinstance(attempt.get('revision'), int):
                ref = AttemptRef(attempt['id'], item['project'], item['variant'], self.builds.output)
                results[item['itemId']] = self.builds.verify(ref, attempt['revision'], full=True)
        with self.lock:
            def change():
                for kept in rows:
                    item = self._row(kept['itemId'])
                    if item is None or item['state'] not in ('starting', 'building'):
                        continue
                    m = results.get(item['itemId'])
                    if m:
                        item.update(state='built', endedAt=utc(), result=dict(
                            buildId=m.get('buildId'), revision=item['attempt'].get('revision'), seconds=m.get('seconds'),
                            warnings=[], leftOut=len(m.get('leftOut') or []),
                            lightingUnchanged=bool(m.get('lightingUnchanged')), recovered=True))
                    else:
                        self._remember(dict(item, state='failed', interrupted='The editor stopped during its build.'))
                        item.update(state='waiting', attempt=None, startedAt=None, endedAt=None, seconds=None,
                                    interrupted='The editor stopped during its build: it starts again on Resume.')
                q = self.q
                if q['state'] == 'stopped' and not any(i['state'] in ('waiting', 'starting', 'building') for i in q['items']):
                    q.update(state='finished' if q['items'] else 'idle', stopReason=None)
            self._transition(change)
            self.recovering = False
            self.waiting_for = None
            self.cond.notify_all()

    def _recovered_keys(self):
        return self.builds.recovered_alive()

    def _prune_attempts(self):
        """Snapshots of attempts no row or diagnostic names any more, older than ATTEMPT_DAYS, deleted."""
        if not self.attempts.is_dir() or not self.q:
            return
        named = {(i.get('attempt') or {}).get('id') for i in self.q['items']}
        named |= {(d.get('attempt') or {}).get('id') for kept in self.q.get('diagnostics', {}).values() for d in kept}
        old = time.time() - ATTEMPT_DAYS * 86400
        for folder in self.attempts.iterdir():
            try:
                if folder.name not in named and folder.stat().st_mtime < old:
                    shutil.rmtree(folder)
            except OSError:
                pass

    # ------------------------------------------------------------------ what the page sees

    def view(self):
        with self.lock:
            return self._view()

    def _view(self):
        if not self.available:
            return dict(available=False, reason=self.unavailable, state='unavailable', items=[], actions={})
        if self.error:
            return dict(available=True, state='unreadable', error=self.error['message'], items=[], queueId=None,
                        revision=None, actions=dict(reset=True))
        q = self.q
        running_id, job = (self.active[0], self.builds.pinned_status(self.active[1].job)) if self.active else (None, None)
        items, position = [], 0
        for item in q['items']:
            row = {k: item.get(k) for k in ('itemId', 'project', 'name', 'variant', 'state', 'attempts', 'queuedAt', 'startedAt',
                                            'endedAt', 'seconds', 'result', 'error', 'interrupted')}
            row['revision'] = (item.get('attempt') or {}).get('revision')
            row['attempt'] = (item.get('attempt') or {}).get('id')
            if item['state'] == 'waiting':
                position += 1
                row['position'] = position
            if item['state'] in ('waiting', 'starting', 'building'):
                row['estimate'] = self.estimates.get(item['itemId'])
            if item['state'] in ('starting', 'building') and item['itemId'] in self.started_at:
                row['elapsed'] = round(self.clock() - self.started_at[item['itemId']], 1)
            if running_id == item['itemId'] and job:
                row['job'] = dict(stage=job.get('stage'), running=job.get('running'), progress=job.get('progress'),
                                  stages=[s.get('stage') for s in job.get('stages') or []], attempt=job.get('attempt'))
            row['earlier'] = len(q['diagnostics'].get(item['itemId']) or [])
            items.append(row)
        counts = {s: sum(1 for i in q['items'] if i['state'] == s) for s in ('waiting', 'starting', 'building', 'built', 'failed')}
        counts.update(total=len(q['items']), processed=counts['built'] + counts['failed'])
        active = q.get('activeSeconds', 0.0) + (self.clock() - self.ran_since if self.ran_since is not None else 0.0)
        state = q['state']
        settled_stop = state == 'stopped' and not self.recovering
        try:
            changed = bool(q['context'] and self._current_context() != q['context'])
        except ProjectError:
            changed = bool(q['context'])
        return dict(available=True, queueId=q['queueId'], revision=q['revision'], state=state, reason=q.get('stopReason'),
                    recovering=self.recovering, waitingFor=self.waiting_for, fault=self.fault, notice=self.notice,
                    contextChanged=changed, items=items, counts=counts, activeSeconds=round(active, 1),
                    createdAt=q.get('createdAt'), updatedAt=q.get('updatedAt'),
                    canResume=settled_stop and not changed and counts['waiting'] > 0,
                    actions=dict(add=state != 'stopping' and not (state == 'stopped' and changed),
                                 stop=state == 'running', resume=settled_stop and not changed and counts['waiting'] > 0,
                                 remove=counts['waiting'] > 0, clear=(settled_stop or state == 'finished')))
