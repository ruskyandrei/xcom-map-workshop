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

What a build reads is captured before it is launched (`capture`; review finding 12): the saved project's bytes, read
whole under the store's lock (projects.py capture), into a snapshot of its own, <builds>/.work/queue-attempts/
<attempt>/project.json, and the map picture the project names beside it (project.picture.png, its SHA-256 checked),
for the editor's Build and the build queue alike. build.py builds the snapshot (--saved-file names the project's own
file, --projects its folder), so a save, a rename or a new picture after the capture changes nothing of the build,
and the job (`digest`, `picture`), the manifest (project.sha256, picture.sha256) and a bug report (the snapshot itself)
name the same bytes. The build queue prunes the folder (buildqueue.py, ATTEMPT_DAYS).

What builds leave in <builds>/.work is pruned (`prune_work`; review finding 49) by build.py after every build, built
or failed, and by the server as it starts (`BuildRunner.prune`, beside recover), which also knows the variants the
projects ship as: every variant keeps its KEEP_WORK newest work folders whole and older ones keep their logs and small
records; a variant no project ships as keeps none whole once its last build is ORPHAN_DAYS old; kept pieces unused for
PIECE_DAYS go (ORPHAN_DAYS for a variant none ships as).

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
import shutil
import subprocess
import sys
import threading
import time
from uuid import uuid4
import zipfile

import atomic_files
import pictures
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
REPORT_FILE_MAX = 32 << 20  # a bug report's zip leaves out a file larger than this (and says so)
# what builds leave in <builds>/.work (prune_work)
KEEP_WORK = 3               # of every variant's work folders (<Variant>-<stamp>), the newest kept whole
ORPHAN_DAYS = 14            # a variant no project ships as keeps none whole, nor its kept pieces, once its last build is this old
PIECE_DAYS = 30             # a variant's kept pieces (.work/pieces/<Variant>) are deleted once unused this long
SMALL_FILE = 1 << 20        # an older work folder keeps its logs and its files up to this size (its records)
WORK_FOLDER = re.compile(r'([A-Za-z][A-Za-z0-9_]*)-(\d{8}-\d{6})(?:-[0-9a-f]{8})?')   # and since 16 November the attempt's
DAY = 86400.0


def now():
    return datetime.datetime.now().isoformat(timespec='seconds')


def explorer(command):
    """Run Windows Explorer with this command line (Windows' own explorer.exe, never one found on PATH)."""
    exe = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'explorer.exe'
    subprocess.Popen(f'"{exe}" {command}', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def _write(path, data):
    atomic_files.write_bytes(path, data, sync=True)


def capture(projects, project_id, folder):
    """The saved project captured for a build into `folder` (see the module notes): its bytes as project.json, read
    whole under the store's lock, and the map picture its document names as project.picture.png (pictures.beside),
    copied only when the kept file's SHA-256 is the one named (else the build says the picture is missing). Returns
    (document, the bytes' SHA-256, the project's own file, the snapshot, the picture's SHA-256 or None). ProjectError
    when the project can't be read; OSError when the snapshot can't be written."""
    document, data, sha, path = projects.capture(project_id)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    snapshot = folder / 'project.json'
    _write(snapshot, data)
    picture, named = None, pictures.named(document)
    kept = pictures.picture_file(projects, project_id, named) if named else None
    if kept is not None:
        try:
            png = kept.read_bytes()
        except OSError:
            png = None
        if png is not None and pictures.sha256(png) == named:
            _write(pictures.beside(snapshot), png)
            picture = named
    return document, sha, path, snapshot, picture


def owned_variants(root):
    """The variants (output.shipAs, lower case) the project files in the folder `root` ship as, or None when the
    folder or a file in it can't be read now (then no variant is taken for one that no project ships as). A file that
    is not JSON is no project the editor builds."""
    try:
        paths = [p for p in Path(root).iterdir() if p.is_file() and p.suffix.lower() == '.json']
    except (OSError, TypeError):
        return None
    owned = set()
    for path in paths:
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
        except OSError:
            return None
        except ValueError:
            continue
        output = document.get('output') if isinstance(document, dict) else None
        if isinstance(output, dict) and isinstance(output.get('shipAs'), str):
            owned.add(output['shipAs'].lower())
    return owned


def _size(folder):
    total = 0
    for file in folder.rglob('*'):
        try:
            if file.is_file():
                total += file.stat().st_size
        except OSError:
            pass
    return total


def _strip(folder):
    """A work folder down to its logs and its small files (its records): the bytes freed."""
    freed = 0
    try:
        children = list(folder.iterdir())
    except OSError:
        return 0
    for child in children:
        try:
            if child.is_dir() and child.name != 'logs':
                size = _size(child)
                shutil.rmtree(child)
                freed += size
            elif child.is_file() and child.stat().st_size > SMALL_FILE:
                size = child.stat().st_size
                child.unlink()
                freed += size
        except OSError:
            pass        # a file held open: a later prune takes it
    return freed


def _made(stamp, folder):
    """When a work folder's build started: its name's stamp (local time), else the folder's own time."""
    try:
        return datetime.datetime.strptime(stamp, '%Y%m%d-%H%M%S').timestamp()
    except ValueError:
        try:
            return folder.stat().st_mtime
        except OSError:
            return 0.0


def prune_work(output, owned=None, keep=KEEP_WORK, spare=(), now=None):
    """What builds leave in <output>/.work pruned (faster-bake plan 6.1; review finding 49), by build.py after every
    build, built or failed, and by the server as it starts (BuildRunner.prune). Each build leaves 60 to 150 MB of work
    (the grown map, the lit map, the arrays, the previews). Of every variant the `keep` newest work folders stay whole
    (a bug report reads the newest: BuildRunner.report); older ones keep their logs and small records (_strip).
    `owned`: the variants the projects ship as (owned_variants), or None when that is not known; a variant none ships
    as keeps no work folder whole once its last build is ORPHAN_DAYS old. A variant's kept pieces (relight.py
    PieceCache, one build's worth) are deleted once neither they nor the variant's work folders have changed for
    PIECE_DAYS, or ORPHAN_DAYS for a variant none ships as. `spare`: folders left as they are (a running build's own).
    The rest of .work (patchtool's, the publish journals, the snapshots, which buildqueue.py prunes) is left.
    Returns dict(freed=bytes, folders=work folders pruned, pieces=kept piece sets deleted)."""
    root = Path(output) / '.work'
    now = time.time() if now is None else now
    owned = None if owned is None else {v.lower() for v in owned}
    spared = {os.path.normcase(os.path.abspath(p)) for p in spare if p}

    def listed(folder):
        try:
            return [p for p in folder.iterdir() if p.is_dir()]
        except OSError:
            return []

    def left(folder):
        return os.path.normcase(os.path.abspath(folder)) in spared
    variants = {}
    for folder in listed(root):
        m = WORK_FOLDER.fullmatch(folder.name)
        if m:
            variants.setdefault(m.group(1).lower(), []).append((m.group(2), folder.name, folder))
    freed = folders = pieces = 0
    last = {}           # variant -> when its newest build started
    for variant, found in variants.items():
        found.sort(key=lambda f: f[:2])
        last[variant] = _made(found[-1][0], found[-1][2])
        orphan = owned is not None and variant not in owned and last[variant] < now - ORPHAN_DAYS * DAY
        whole = 0 if orphan else max(keep, 0)
        for _, _, old in found[:len(found) - whole]:
            got = 0 if left(old) else _strip(old)
            freed += got
            folders += bool(got)
    for cache in listed(root / 'pieces'):
        if left(cache):
            continue
        variant = cache.name.lower()
        try:
            used = max([cache.stat().st_mtime] + [f.stat().st_mtime for f in cache.iterdir()])
        except OSError:
            continue
        days = ORPHAN_DAYS if owned is not None and variant not in owned else PIECE_DAYS
        if max(used, last.get(variant, 0.0)) < now - days * DAY:
            size = _size(cache)
            shutil.rmtree(cache, ignore_errors=True)
            if not cache.exists():
                freed += size
                pieces += 1
    return dict(freed=freed, folders=folders, pieces=pieces)


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
    def __init__(self, projects, cache, output, command=None, reveal_with=None, launch=procs.launch, enable=(),
                 orphans=True):
        """projects: the ProjectStore; cache: the viewer cache the page shows; output: the builds folder.
        command(project_file) gives the build's command line, reveal_with(arguments) runs Explorer (tests stub both);
        launch: how a process tree is started (procs.launch); enable: families every build makes although the
        compiler doesn't yet (build.py --family; an experiment's server: viewer.py serve --family).
        orphans: whether the prune at start may treat a variant no project here ships as as abandoned; off for a
        server whose projects folder is not the one these builds were made from (a test server's scratch projects
        beside the real builds folder would take every real variant for abandoned)."""
        self.projects, self.cache, self.output = projects, Path(cache), Path(output)
        self.orphans = orphans
        self.reveal_with = reveal_with or (explorer if sys.platform == 'win32' else None)
        self.families = [a for f in enable for a in ('--family', f)]
        self.command = command or (lambda f: [sys.executable, '-B', '-u', str(BUILD), str(f), '--cache', str(self.cache),
                                              '--output', str(self.output)] + self.families)
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
        self.pruner = None          # the thread pruning the builds folder's old work as the server starts (prune)

    # ------------------------------------------------------------------ starting

    def attempts(self):
        """The folder of the attempts' snapshots (capture), shared with the build queue."""
        return self.output / '.work' / 'queue-attempts'

    def start(self, project_id, quick=False):
        """Start building the saved project; `quick`: build.py --quick, the edit without its lighting baked. The
        project is captured first (capture), and build.py builds that snapshot."""
        attempt_id = str(uuid4())
        folder = self.attempts() / attempt_id
        try:
            document, sha, path, snapshot, picture = capture(self.projects, project_id, folder)
        except OSError as error:
            shutil.rmtree(folder, ignore_errors=True)
            raise ProjectError(500, f'The project could not be captured for its build: {error}')
        command = self.command(snapshot) + ['--saved-file', str(path), '--projects', str(self.projects.root)]
        try:
            self._start(document, command, quick, attempt_id=attempt_id, snapshot=str(snapshot), digest=sha, picture=picture)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)       # nothing was launched from it
            raise
        return self.status(project_id)

    def pinned_command(self, document, output, game, udk):
        return [sys.executable, '-B', '-u', str(BUILD), str(document), '--cache', str(self.cache),
                '--output', str(output), '--game', str(game)] + (['--udk', str(udk)] if udk else []) + self.families

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
        command += self.families
        for game in context.get('checkGames') or ():
            command += ['--check-game', str(game)]
        return command

    def start_queued(self, document, *, snapshot, context, saved_file, owner, attempt_id, log, digest=None, picture=None):
        """A full build of the queue's snapshot (buildqueue.py): its Attempt. The queue holds the reservation."""
        return self._start(document, self.queue_command(snapshot, context, saved_file), False, log=log, origin='queue',
                           owner=owner, attempt_id=attempt_id, snapshot=str(snapshot), digest=digest, picture=picture)

    def _start(self, document, command, quick, *, log=None, started=None, origin='foreground', owner=None, attempt_id=None,
               output=None, snapshot=None, digest=None, picture=None):
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
                       stage=None, stages=[], lines=[], startedAt=now(), finishedAt=None, error=None, errorCode=None, running=None,
                       progress=None, **({'snapshot': snapshot} if snapshot else {}),
                       # the captured bytes' SHA-256 and the picture's (capture): the manifest names the same
                       **({'digest': digest} if digest else {}), **({'picture': picture} if picture else {}))
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

    def recovered_alive(self):
        """The keys of the writers this server did not start that still run (the gone ones dropped, their journals
        then settled)."""
        with self.lock:
            alive = set()
            for key, (_, active) in tuple(self.recovered.items()):
                if active():
                    alive.add(key)
                else:
                    del self.recovered[key]
                    threading.Thread(target=self.reconcile, daemon=True, name='build-reconcile').start()
            return alive

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
            elif line.startswith('build failed code: '):
                # which failure it is (build.py BuildError.code: export-missing, the export too old to build from), for
                # the page's remedy (review finding 55)
                job['errorCode'] = line[len('build failed code: '):].strip()
            elif line.startswith('built ') and ': ' in line:
                job['buildId'] = line[6:].split(': ', 1)[0]
            elif line.lstrip().startswith('warning: '):
                # build.py's own at the line's start, a tool's indented under its command line (relight.py's writes
                # reaching pieces it didn't relight)
                job.setdefault('warnings', []).append(line.lstrip()[len('warning: '):])
            elif line.startswith('running:'):
                # build.py's line before each tool it starts (Build.tool): what the step shows while the tool runs, or
                # nothing (an empty line: a tool whose step says enough in its own words)
                job['running'] = line[len('running:'):].strip() or None
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
            atomic_files.write_text(folder / f'{attempt.id}.json', json.dumps(record) + '\n')
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
        # the builds folder's old work pruned beside the start (the first prune of a folder may free gigabytes)
        self.pruner = threading.Thread(target=self.prune, daemon=True, name='build-work-prune')
        self.pruner.start()

    def prune(self):
        """The builds folder's old work pruned (prune_work), with the variants the projects ship as known, so a
        variant no project ships as is pruned too: as the server starts (recover). The result, or None when it failed
        (never the server's start)."""
        try:
            owned = owned_variants(getattr(self.projects, 'root', None)) if self.orphans else None
            result = prune_work(self.output, owned=owned)
        except Exception as error:
            result, said = None, f'The builds folder\'s old work could not be pruned: {error}'
        else:
            said = (f'Old build work pruned: {result["freed"] / 2 ** 20:.0f} MB freed ({result["folders"]} work '
                    f'folders, {result["pieces"]} sets of kept pieces).') if result['freed'] else None
        if said:
            try:
                print(said, flush=True)
            except (OSError, ValueError):       # an output that can't take it: the prune is done all the same
                pass
        return result

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
        build of a snapshot (the editor's Build and the build queue's: capture), the snapshot it read, not the project
        as saved since."""
        document = self.projects.load(project_id)
        variant = (document.get('output') or {}).get('shipAs')
        if not variant or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', variant): raise ProjectError(409, 'The project has no variant name yet.')
        with self.lock:
            job = self.job if self.job and self.job['project'] == project_id else None
            lines = list(job['lines']) if job else []
            summary = {k: job.get(k) for k in ('state', 'name', 'revision', 'startedAt', 'finishedAt', 'exitCode', 'error',
                                               'attempt', 'origin', 'digest', 'picture')} if job else None
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
        written, skipped = [], []       # the answer names what the zip holds: a file over REPORT_FILE_MAX is left out
        try:
            with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as z:
                for path, name in files:
                    if path.stat().st_size <= REPORT_FILE_MAX:
                        z.write(path, name)
                        written.append(name)
                    else:
                        skipped.append(name)
                z.writestr('report.json', json.dumps(dict(editorVersion=VERSION, project=project_id, variant=variant, madeAt=now(),
                                                          build=summary, work=[w.name for w in work[-3:]],
                                                          **({'leftOut': skipped} if skipped else {})), indent=1))
                if lines: z.writestr('build-output.txt', '\n'.join(lines) + '\n')
            atomic_files.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        return dict(zip=str(target), files=written + ['report.json'] + (['build-output.txt'] if lines else []),
                    **({'leftOut': skipped} if skipped else {}))

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
                    # its pieces, effects and sounds of other maps, and the maps they were brought from (build.py
                    # transplant; effects and sounds since the effects and sounds plan's FX4)
                    foreignPieces=m.get('foreignPieces') or 0, foreignEffects=m.get('foreignEffects') or 0,
                    donors=[{k: d.get(k) for k in ('map', 'pieces', 'effects', 'bytes')} for d in m.get('donors') or []],
                    revision=m['project'].get('revision'), files=sorted(Path(f).name for f in m.get('files') or {}))

    def status(self, project_id):
        # (polled every 2 s: the project's output names as the store last read them, not the file read again each
        # time: review finding 20)
        variant = (self.projects.cached(project_id).get('output') or {}).get('shipAs')
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
