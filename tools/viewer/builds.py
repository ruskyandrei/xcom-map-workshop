"""The editor's Build, run from the viewer's server (first-editor plan, section 7; slice E4).

The page saves the project first (its Save never builds), then asks the server to build the saved revision:
tools/editor/build.py runs in the background, one build at a time (patchtool drives one UDK), and the page follows its
stages from the log. The result is a variant package in the builds folder; nothing is installed anywhere.

  POST /projects/<id>/build        start building the saved project (409 while a build runs); {"quick": true}: a quick
                                   build (build.py --quick: the edit made in the map, its lighting not baked)
  GET  /projects/<id>/build.json   the build's state: idle, running, built, failed or cancelled, whether it is quick,
                                   its stages (each with the time it ended), the step running and its progress, the
                                   log's last lines, and the project's last package (from its manifest: whether it is
                                   quick, and how long the last full and quick builds took) if there is one
  POST /projects/<id>/build-cancel stop the project's running build (its tools with it); the last good package stays,
                                   since a build swaps its package in only at the end. {"attempt": id}: only if that
                                   launch is the one running (a stale page's cancel never stops a newer build). A
                                   build of the build queue's is stopped by stopping the queue (buildqueue.py)
  POST /projects/<id>/report       a zip for a bug report: the project file, the last package's manifest and README,
                                   the newest build's logs and compile report, and the build's output here
                                   (<builds>/<variant>-report.zip); {zip, files}
  POST /builds/reveal {path}       show a folder or file of the builds folder in Windows Explorer (a build's folder, a
                                   bug report's zip): a folder opened, a file selected in its folder, never run; a path
                                   outside the builds folder is refused (403), one not there any more is 404

A tool's `progress: <what> [<done>/<total>]` lines (relight.py prints one per component) set the job's progress and
stay out of its lines.

Each launch is an attempt (build queue plan, 9.2 to 9.4): a UUID, given to build.py (--attempt, written in the
manifest and the build's id), with an origin (foreground: the editor's Build and Play in game's; prefab: a prefab
test; queue: the build queue's) fixed before anyone can see it. Its processes are contained (procs.py), so Cancel and
Stop end every process of it and the server's death ends them too. It ends (its `done` event, then the runner's
listeners, outside the runner's lock) only once its processes are all gone and a journal its package swap left is
settled (publication.py). A record of each running attempt (<builds>/.work/writers/<attempt>.json: its process and
the folder it writes) lets a restarted server prove the old one's builds are gone before anything builds again; one
still running, or one whose state can't be known, keeps the build slot busy with the reason.

The one build slot is shared: the editor's Build, Play in game's build, prefab tests and the build queue. The queue
reserves it while it runs (reserve/release), so no other build starts between its projects; a build already running
finishes first. Readers of packages (Install in the game, the map pack, Play in game) take leases (lease): a project
being built, or about to be, is refused, and the queue waits before it starts a project whose package is being read.

Lock order: the build queue's lock may be held while this runner's is taken, never the other way round; the runner
calls nothing outside itself while it holds its lock, and the store's lock (projects.py) is never held across a wait.
"""
import contextlib
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from uuid import uuid4
import zipfile

import procs
import publication
from projects import ProjectError
from version import VERSION

BUILD = Path(__file__).resolve().parents[1] / 'editor' / 'build.py'
STAGES = ('snapshot', 'compile', 'patch', 'shell', 'transplant', 'light', 'seeds')
STAGE_LINE = re.compile(r'^(%s): (\{.*\})$' % '|'.join(STAGES))
PROGRESS = re.compile(r'^progress: (.+?)(?: (\d+)/(\d+))?$')
VARIANT = re.compile(r'[A-Za-z][A-Za-z0-9_]*')
KEEP = 400
DRAIN_GRACE = 15.0          # seconds a finished build.py's leftover processes get before they are killed
DRAIN_LIMIT = 90.0          # seconds after which processes that won't end leave the slot busy (a writer of unknown state)


def now():
    return datetime.datetime.now().isoformat(timespec='seconds')


def explorer(command):
    """Run Windows Explorer with this command line (Windows' own explorer.exe, never one found on PATH)."""
    exe = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'explorer.exe'
    subprocess.Popen(f'"{exe}" {command}', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def stop_process(pid):
    """Stop a process this server started and its children (the exporter's and the precache's; builds are contained
    process trees instead: procs.py)."""
    if sys.platform == 'win32':
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(pid)], capture_output=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    else:
        import signal
        try: os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError: pass


def slot_busy(message, **extra):
    """The structured answer when the build slot is taken (the only refusal the build queue waits on)."""
    return ProjectError(409, message, code='build-slot', **extra)


class Attempt:
    """One launch of build.py (see the module notes): its fixed ids and origin, the job the routes show, its process
    tree and `done`, set once it has ended, its processes gone and its package settled."""

    def __init__(self, attempt_id, origin, owner, job, output, variant, snapshot=None):
        self.id, self.origin, self.owner = attempt_id, origin, owner
        self.job, self.output, self.variant, self.snapshot = job, Path(output), variant, snapshot
        self.done = threading.Event()
        self.tree = None
        self.cancelled = False


class BuildRunner:
    def __init__(self, projects, cache, output, command=None, reveal_with=None, launch=procs.launch):
        """projects: the ProjectStore; cache: the viewer cache the page shows; output: the builds folder.
        command(project_file) gives the build's command line, reveal_with(arguments) runs Explorer (tests stub both);
        launch: how a process tree is started (procs.launch)."""
        self.projects, self.cache, self.output = projects, Path(cache), Path(output)
        self.reveal_with = reveal_with or (explorer if sys.platform == 'win32' else None)
        self.command = command or (lambda f: [sys.executable, '-B', '-u', str(BUILD), str(f), '--cache', str(self.cache),
                                              '--output', str(self.output)])
        self.launch = launch
        self.lock = threading.Lock()
        self.job = None             # the latest job (a dict the routes show), as before attempts
        self.attempt = None         # its Attempt
        self.recovered = {}         # key -> (name, active()): writers this server did not start (prefab tests', old ones)
        self.reservation = None     # dict(owner, label): the build queue's hold on the slot
        self.leases = {}            # project id -> how many readers hold its package
        self.claims = {}            # project id -> owner: a project the queue is about to build
        self.blocked = {}           # variant (lower case) -> why its output waits (an unsettled journal)
        self.listeners = []         # called (no arguments, outside the lock) when the slot may have freed
        self.queue = None           # the build queue (buildqueue.py), when the server has one

    # ------------------------------------------------------------------ starting

    def start(self, project_id, quick=False):
        """Start building the saved project; `quick`: build.py --quick, the edit without its lighting baked."""
        document = self.projects.load(project_id)
        self._start(document, self.command(self.projects.path(project_id)), quick)
        return self.status(project_id)

    def pinned_command(self, document, output, game, udk):
        return [sys.executable, '-B', '-u', str(BUILD), str(document), '--cache', str(self.cache),
                '--output', str(output), '--game', str(game)] + (['--udk', str(udk)] if udk else [])

    def start_pinned(self, document, output, game, udk, quick, started):
        """Build a private project file into its own fresh artifact directory under the shared lock."""
        with Path(document).open(encoding='utf-8') as source:
            doc = json.load(source)
        return self._start(doc, self.pinned_command(document, output, game, udk), quick,
                           log=Path(document).with_name('build.log'), started=started, origin='prefab',
                           output=output).job

    def queue_command(self, snapshot, context, saved_file):
        """A build queue attempt's command line: the snapshot, every folder pinned (nothing read from the settings
        after the capture), the projects folder and the other install its names are checked against (build.py)."""
        command = [sys.executable, '-B', '-u', str(BUILD), str(snapshot), '--pinned', '--cache', str(context['cache']),
                   '--output', str(context['output']), '--game', str(context['game']), '--projects', str(context['projects']),
                   '--saved-file', str(saved_file)]
        if context.get('udk'):
            command += ['--udk', str(context['udk'])]
        for game in context.get('checkGames') or ():
            command += ['--check-game', str(game)]
        return command

    def start_queued(self, document, snapshot, context, saved_file, owner, attempt_id, log):
        """A full build of the queue's snapshot (buildqueue.py): its Attempt. The queue holds the reservation."""
        return self._start(document, self.queue_command(snapshot, context, saved_file), False, log=log, origin='queue',
                           owner=owner, attempt_id=attempt_id, snapshot=str(snapshot))

    def _start(self, document, command, quick, log=None, started=None, origin='foreground', owner=None, attempt_id=None,
               output=None, snapshot=None):
        attempt_id = attempt_id or str(uuid4())
        variant = (document.get('output') or {}).get('shipAs')
        output = Path(output) if output else self.output
        with self.lock:
            if busy := self._busy(owner):
                raise slot_busy(busy['message'], building=busy['project'], **({'queue': True} if busy['queue'] else {}))
            if origin != 'prefab' and isinstance(variant, str) and variant.lower() in self.blocked:
                raise ProjectError(409, f'Not built: {self.blocked[variant.lower()]}', code='output-blocked')
            if origin != 'queue' and self.leases.get(document['id']):
                raise ProjectError(409, 'Not built: the project\'s last package is being installed or zipped. Try again '
                                        'in a moment.', code='package-in-use')
            job = dict(project=document['id'], name=document.get('name'), revision=document.get('revision'),
                       variant=variant, quick=bool(quick), state='running', attempt=attempt_id, origin=origin,
                       stage=None, stages=[], lines=[], startedAt=now(), finishedAt=None, error=None, running=None,
                       progress=None, **({'snapshot': snapshot} if snapshot else {}))
            attempt = Attempt(attempt_id, origin, owner, job, output, variant, snapshot)
            attempt.tree = self.launch(command + ['--attempt', attempt_id] + (['--quick'] if quick else []),
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                                       errors='replace', creationflags=procs.CREATE_NO_WINDOW)
            job['pid'] = attempt.tree.pid
            self._write_writer(attempt)
            self.job, self.attempt = job, attempt
            self.claims.pop(document['id'], None)
        try:
            if started:
                started(attempt.tree.pid)
        finally:
            threading.Thread(target=self._follow, args=(attempt, log), daemon=True, name='build-follow').start()
        return attempt

    # ------------------------------------------------------------------ the slot

    def busy(self, owner=None):
        """(project, name) of what holds the build slot for anyone but `owner`, or None."""
        with self.lock:
            busy = self._busy(owner)
        return (busy['project'], busy['name']) if busy else None

    def busy_info(self, owner=None):
        with self.lock:
            return self._busy(owner)

    def _busy(self, owner=None):
        job = self.job
        if job and job['state'] == 'running':
            return dict(project=job['project'], name=job['name'], queue=job.get('origin') == 'queue',
                        message=f'A build is running: {job["name"]}. One build at a time.')
        for key, (name, active) in tuple(self.recovered.items()):
            if active():
                return dict(project=key, name=name, queue=False,
                            message=f'A build is running: {name}. One build at a time.')
            del self.recovered[key]
            threading.Thread(target=self.reconcile, daemon=True, name='build-reconcile').start()
        if self.reservation and self.reservation['owner'] != owner:
            return dict(project=None, name=self.reservation['label'], queue=True,
                        message='The build queue is building projects one after another. Stop it in the project '
                                'manager, or wait until it ends.')
        return None

    def reserve(self, owner, label):
        """The build queue's hold on the slot: no build of anyone else's starts until release (one running finishes)."""
        with self.lock:
            if self.reservation and self.reservation['owner'] != owner:
                raise slot_busy('Another build queue holds the build slot.')
            self.reservation = dict(owner=owner, label=label)

    def release(self, owner):
        with self.lock:
            if self.reservation and self.reservation['owner'] == owner:
                self.reservation = None
        self._notify()

    def active_projects(self):
        """The projects being built now or about to be (the shared active-writer query): set of ids."""
        with self.lock:
            return self._active()

    def _active(self):
        active = set(self.claims)
        if self.job and self.job['state'] == 'running':
            active.add(self.job['project'])
        return active

    def claim(self, project_id, owner):
        """The queue is about to build `project_id`: True, and it counts as building, unless a reader holds its
        package (then False, and the queue waits)."""
        with self.lock:
            if self.leases.get(project_id):
                return False
            self.claims[project_id] = owner
            return True

    def unclaim(self, project_id, owner):
        with self.lock:
            if self.claims.get(project_id) == owner:
                del self.claims[project_id]
        self._notify()

    @contextlib.contextmanager
    def lease(self, project_ids):
        """Readers of packages (Install, the map pack, Play in game): yields the set of the projects being built (left
        out by the reader), and holds the others' packages until the block ends."""
        with self.lock:
            active = self._active()
            held = [p for p in dict.fromkeys(project_ids) if p not in active]
            for p in held:
                self.leases[p] = self.leases.get(p, 0) + 1
        try:
            yield active
        finally:
            with self.lock:
                for p in held:
                    self.leases[p] -= 1
                    if not self.leases[p]:
                        del self.leases[p]
            self._notify()

    def _notify(self):
        for listener in tuple(self.listeners):
            try:
                listener()
            except Exception:       # noqa: BLE001 - a listener's failure is its own
                pass

    # ------------------------------------------------------------------ following

    def pinned_status(self, job):
        with self.lock:
            return dict(job, lines=job['lines'][-40:], stages=list(job['stages']))

    @staticmethod
    def _watch(attempt):
        """Once build.py has exited: every process of it gone (leftovers get DRAIN_GRACE, then are killed). A leftover
        holds the output pipe open, so this, not the end of the output, is what ends the reading."""
        attempt.tree.proc.wait()
        try:
            attempt.drained = attempt.tree.drain(DRAIN_LIMIT, kill_after=0 if attempt.cancelled else DRAIN_GRACE)
        except Exception:       # noqa: BLE001 - unknown: counted as not drained
            attempt.drained = False

    def _follow(self, attempt, log=None):
        job, tree = attempt.job, attempt.tree
        proc = tree.proc
        problem = None
        attempt.drained = None
        watcher = threading.Thread(target=self._watch, args=(attempt,), daemon=True, name='build-drain')
        watcher.start()
        try:
            for raw in self._lines(proc, log):
                self._line(job, raw.rstrip())
        except Exception as error:      # noqa: BLE001 - a log or parser fault never leaves a build running for ever
            problem = f'the build\'s output could not be read: {error}'
        finally:
            if problem:
                tree.terminate()        # nothing reads its output any more: it can't be followed
            try:
                proc.stdout.close()
            except OSError:
                pass
            code = proc.wait()
            watcher.join(DRAIN_LIMIT + 30)
            # then its package swap settled
            settled = None
            try:
                drained = bool(attempt.drained)
                if drained:
                    tree.close()
                    settled = self._settle(attempt)
                    self._drop_writer(attempt)
            except Exception as error:      # noqa: BLE001 - the attempt still ends, its slot kept busy
                drained, problem = False, problem or f'the build\'s end could not be settled: {error}'
            if not drained:
                with self.lock:
                    self.recovered[attempt.id] = (job.get('name') or 'a build',
                                                  lambda t=tree: bool(t.active() or t.lingering()))
            with self.lock:
                job['finishedAt'] = now()
                job['exitCode'] = code
                if attempt.cancelled:
                    job['cancelled'] = True
                job['state'] = 'cancelled' if attempt.cancelled else 'built' if code == 0 and drained and not problem else 'failed'
                if job['state'] == 'cancelled':
                    job['error'] = 'Cancelled: the last good package, if any, is as it was.'
                elif not drained:
                    job['error'] = 'Some of the build\'s processes did not end; no build starts until they have.'
                elif problem:
                    job['error'] = problem
                elif code and not job['error']:
                    job['error'] = (job['lines'] or [f'the build stopped (exit {code})'])[-1]
                if settled and settled.get('state') == 'blocked':
                    job['error'] = (job['error'] + ' ' if job['error'] else '') + settled['reason']
            attempt.done.set()
            self._notify()

    def _line(self, job, line):
        with self.lock:
            p = PROGRESS.match(line.strip())
            if p:
                job['progress'] = dict(what=p.group(1), done=int(p.group(2)) if p.group(2) else None,
                                       total=int(p.group(3)) if p.group(3) else None)
                return
            job['lines'] = (job['lines'] + [line])[-KEEP:]
            m = STAGE_LINE.match(line)
            if m:
                try: result = json.loads(m.group(2))
                except ValueError: result = {}
                job['stages'].append(dict(result, stage=m.group(1), at=now()))
                job['stage'] = m.group(1)
                job['running'] = job['progress'] = None
            elif line.startswith('build failed: '):
                job['error'] = line[len('build failed: '):]
            elif line.startswith('built ') and ': ' in line:
                job['buildId'] = line[6:].split(': ', 1)[0]
            elif line.startswith('warning: '):
                job.setdefault('warnings', []).append(line[len('warning: '):])
            elif line.startswith('  $ '):
                tool = next((t for t in ('patchtool.ps1', 'native_copy.py', 'relight.py') if t in line), None)
                if tool: job['running'] = dict(patchtool='patch and cook',
                                               native_copy='copying and relighting' if '--bake' in line else 'making the edit in the map',
                                               relight='relighting')[tool.split('.')[0]]
                job['progress'] = None

    @staticmethod
    def _lines(proc, log):
        if log is None:
            yield from proc.stdout
            return
        try:
            stream = Path(log).open('w', encoding='utf-8', newline='\n')
        except OSError:
            yield from proc.stdout
            return
        with stream:
            for line in proc.stdout:
                try:
                    stream.write(line)
                    stream.flush()
                except OSError:
                    pass
                yield line

    def _settle(self, attempt):
        """A journal the attempt's package swap left (it died between its renames), settled now that its processes are
        gone: publication.recover under the variant's guard. Its result, or None."""
        variant = attempt.variant
        if not (isinstance(variant, str) and VARIANT.fullmatch(variant)):
            return None
        if not publication.journal_path(attempt.output, variant).is_file():
            return None
        try:
            with publication.guard(attempt.output, variant, wait=30):
                result = publication.recover(attempt.output, variant)
        except publication.PublishError as error:
            result = dict(state='blocked', reason=str(error))
        except OSError as error:
            result = dict(state='blocked', reason=f'{variant}\'s package swap could not be settled: {error}')
        if result and result.get('state') == 'blocked' and attempt.output == self.output:
            with self.lock:
                self.blocked[variant.lower()] = result['reason']
        return result

    # ------------------------------------------------------------------ restarts

    def _writers(self):
        return self.output / '.work' / 'writers'

    def _write_writer(self, attempt):
        folder = self._writers()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            record = dict(attempt=attempt.id, origin=attempt.origin, project=attempt.job['project'],
                          name=attempt.job.get('name'), variant=attempt.variant, output=str(attempt.output),
                          pid=attempt.tree.pid, created=attempt.tree.created, startedAt=attempt.job['startedAt'])
            temp = folder / f'{attempt.id}.json.tmp'
            temp.write_text(json.dumps(record) + '\n', encoding='utf-8', newline='\n')
            os.replace(temp, folder / f'{attempt.id}.json')
        except OSError:
            pass        # its processes are contained all the same: the server's death ends them

    def _drop_writer(self, attempt):
        try:
            (self._writers() / f'{attempt.id}.json').unlink(missing_ok=True)
        except OSError:
            pass

    def recover(self):
        """At start (before any request can build): the writers an earlier server left (their records) proved gone,
        or kept as busy until they are; then every journal of a package swap settled once no writer is left. The
        prefab tests' own recovered builds are registered beside these (prefab_tests.py)."""
        folder = self._writers()
        for path in sorted(folder.glob('*.json')) if folder.is_dir() else ():
            try:
                record = json.loads(path.read_text(encoding='utf-8'))
                pid, created = record.get('pid'), record.get('created')
                key = str(record['attempt'])
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                with self.lock:
                    self.recovered[f'writer:{path.stem}'] = (f'a build of an earlier server ({path.name} can\'t be read)',
                                                             lambda: True)
                continue
            if not isinstance(pid, int):
                path.unlink(missing_ok=True)    # launched contained and never recorded: ended with its server
                continue
            if procs.tree_alive(pid, created):
                with self.lock:
                    self.recovered[key] = (record.get('name') or 'a build of an earlier server',
                                           lambda p=pid, c=created, f=path: self._still(p, c, f))
            else:
                path.unlink(missing_ok=True)
        self.reconcile()

    @staticmethod
    def _still(pid, created, record):
        if procs.tree_alive(pid, created):
            return True
        record.unlink(missing_ok=True)
        return False

    def reconcile(self):
        """Every journal of the builds folder settled (publication.recover_all) when no writer of an earlier server is
        left; the variants whose journal can't be settled are blocked (their builds refused with the reason)."""
        with self.lock:
            for key, (_, active) in tuple(self.recovered.items()):
                if active():
                    return
                del self.recovered[key]
            if self.job and self.job['state'] == 'running':
                return
        results = publication.recover_all(self.output)
        with self.lock:
            for variant, result in results.items():
                if result and result.get('state') == 'blocked':
                    self.blocked[variant.lower()] = result['reason']
                else:
                    self.blocked.pop(variant.lower(), None)

    # ------------------------------------------------------------------ stopping

    def stop(self, project_id, attempt=None):
        """Stop the project's running build and every process of it (relight.py and the rest are its children).
        `attempt`: only if that launch is the one running."""
        with self.lock:
            job, handle = self.job, self.attempt
            if not (job and job['project'] == project_id and job['state'] == 'running'):
                raise ProjectError(409, 'No build of this project is running.')
            if attempt is not None and job.get('attempt') != attempt:
                raise ProjectError(409, 'That build has ended; another one is running now.', code='stale-attempt')
            handle.cancelled = True
            job['cancelled'] = True
            tree = handle.tree
        tree.terminate()

    def stop_attempt(self, attempt_id):
        """Stop the build this attempt is, if it still runs (the build queue's Stop): True when it was told to."""
        with self.lock:
            handle = self.attempt
            if not (handle and handle.id == attempt_id and handle.job['state'] == 'running'):
                return False
            handle.cancelled = True
            handle.job['cancelled'] = True
            tree = handle.tree
        tree.terminate()
        return True

    def cancel(self, project_id, attempt=None):
        with self.lock:
            job = self.job
            queued = bool(job and job['project'] == project_id and job['state'] == 'running' and job.get('origin') == 'queue')
        if queued and self.queue is not None:
            if attempt is not None and job.get('attempt') != attempt:
                raise ProjectError(409, 'That build has ended; another one is running now.', code='stale-attempt')
            self.queue.stop_for(job['attempt'])
        else:
            self.stop(project_id, attempt)
        return self.status(project_id)

    # ------------------------------------------------------------------ packages

    def verify(self, attempt, revision, full=True):
        """The builds folder's package of the attempt's project, if it is that attempt's (its token, project, revision,
        full or quick) and its files match its manifest, read under the variant's guard: its manifest, or None."""
        variant = attempt.variant
        if not (isinstance(variant, str) and VARIANT.fullmatch(variant)):
            return None
        folder = attempt.output / variant
        try:
            with publication.guard(attempt.output, variant, wait=publication.READ_WAIT):
                import installs
                m, _ = installs.read_package(folder)
        except Exception:       # noqa: BLE001 - no package, a torn one, a guard that stays held: not verified
            return None
        project = m.get('project') or {}
        if (m.get('attempt') != attempt.id or project.get('id') != attempt.job['project']
                or project.get('revision') != revision or bool(m.get('quick')) == full):
            return None
        return m

    def report(self, project_id):
        """A bug report's zip in the builds folder: what to send when a build goes wrong (or plays wrong). For a
        build of a snapshot (the build queue's), the snapshot it read, not the project as saved since."""
        document = self.projects.load(project_id)
        variant = (document.get('output') or {}).get('shipAs')
        if not variant or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', variant): raise ProjectError(409, 'The project has no variant name yet.')
        with self.lock:
            job = self.job if self.job and self.job['project'] == project_id else None
            lines = list(job['lines']) if job else []
            summary = {k: job.get(k) for k in ('state', 'name', 'revision', 'startedAt', 'finishedAt', 'exitCode', 'error',
                                               'attempt', 'origin')} if job else None
            snapshot = Path(job['snapshot']) if job and job.get('snapshot') else None
            token = (job.get('attempt') or '').replace('-', '')[:8] if job else ''
        work = sorted((self.output / '.work').glob(f'{variant}-*'), key=lambda p: p.name) if (self.output / '.work').is_dir() else []
        work = [w for w in work if w.is_dir() and re.fullmatch(r'\d{8}-\d{6}(-[0-9a-f]{8})?', w.name[len(variant) + 1:])]
        mine = [w for w in work if token and w.name.endswith('-' + token)]
        if mine: work = [w for w in work if w is not mine[-1]] + [mine[-1]]
        own = snapshot if snapshot and snapshot.is_file() else self.projects.path(project_id)
        files = [(own, f'project/{own.name}')]
        package = self.output / variant
        files += [(package / n, f'package/{n}') for n in ('manifest.json', 'README.txt') if (package / n).is_file()]
        if work:
            newest = work[-1]
            files += [(p, f'work/{newest.name}/{p.relative_to(newest).as_posix()}')
                      for p in sorted(newest.rglob('*')) if p.is_file() and (p.suffix in ('.log', '.txt') or p.name == 'compile-report.json'
                                                                            or p.name.endswith('.relight.json'))]
        if not work and not (package / 'manifest.json').is_file(): raise ProjectError(409, 'The project has not been built yet: there is nothing to report.')
        target = self.output / f'{variant}-report.zip'
        temp = target.with_suffix('.zip.tmp')
        with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as z:
            for path, name in files:
                if path.stat().st_size <= 32 << 20: z.write(path, name)
            z.writestr('report.json', json.dumps(dict(editorVersion=VERSION, project=project_id, variant=variant, madeAt=now(),
                                                      build=summary, work=[w.name for w in work[-3:]]), indent=1))
            if lines: z.writestr('build-output.txt', '\n'.join(lines) + '\n')
        temp.replace(target)
        return dict(zip=str(target), files=[n for _, n in files] + ['report.json'] + (['build-output.txt'] if lines else []))

    def reveal(self, path):
        """Show a folder or file of the builds folder in Windows Explorer: a folder opened, a file selected in its
        folder (Explorer's /select, which never runs it). Paths outside the builds folder are refused."""
        if not isinstance(path, str) or not path.strip(): raise ProjectError(400, 'Send {path}.')
        target, root = Path(path).resolve(), self.output.resolve()
        if target != root and root not in target.parents: raise ProjectError(403, 'Only the builds folder and what is in it can be shown.')
        if not target.exists(): raise ProjectError(404, f'{target} is not there any more.')
        if self.reveal_with is None: raise ProjectError(501, 'Showing a folder needs Windows Explorer.')
        # Windows paths can't hold a double quote, so quoting is enough
        self.reveal_with(f'"{target}"' if target.is_dir() else f'/select,"{target}"')
        return dict(shown=str(target))

    def package(self, project_id, variant):
        """The project's last package: its manifest's summary, or None."""
        if not variant or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', variant): return None
        folder = self.output / variant
        try: m = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        except (OSError, ValueError): return None
        if (m.get('project') or {}).get('id') != project_id: return None
        # how long the project's last full and quick builds took (build.py last_times); a package from before quick
        # builds was a full one
        times = m.get('times') if isinstance(m.get('times'), dict) else (
            {'full': m['seconds']} if m.get('seconds') is not None and not m.get('quick') else {})
        return dict(folder=str(folder), buildId=m.get('buildId'), builtAt=m.get('builtAt'), seconds=m.get('seconds'),
                    quick=bool(m.get('quick')), times=times,
                    # its pieces of other maps, and the maps they were brought from (build.py transplant)
                    foreignPieces=m.get('foreignPieces') or 0,
                    donors=[{k: d.get(k) for k in ('map', 'pieces', 'bytes')} for d in m.get('donors') or []],
                    revision=m['project'].get('revision'), files=sorted(Path(f).name for f in m.get('files') or {}))

    def status(self, project_id):
        document = self.projects.load(project_id)
        variant = (document.get('output') or {}).get('shipAs')
        with self.lock:
            job = self.job
            mine = job if job and job['project'] == project_id else None
            busy = self._busy()
            out = dict(state=mine['state'] if mine else 'idle',
                       job={k: (list(v) if isinstance(v, list) else v) for k, v in mine.items()} if mine else None,
                       busy=bool(busy and busy['project'] != project_id),
                       output=str(self.output))
            if isinstance(variant, str) and variant.lower() in self.blocked:
                out['blocked'] = self.blocked[variant.lower()]
        if out['job']:
            out['job']['lines'] = out['job']['lines'][-40:]
        out['package'] = self.package(project_id, variant)
        return out
