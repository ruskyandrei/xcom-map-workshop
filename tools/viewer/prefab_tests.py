"""Private prefab test snapshots, build/launch authorization and recovery."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from uuid import uuid4

import installs
from library import digest_of
from maplist import package_of
from projects import ID, ProjectError, now
from settings import lwr_game

sys.path.append(str(Path(__file__).resolve().parents[1] / 'editor'))
import prefab_stage as stage  # noqa: E402

ACTIVE = {'preparing', 'building', 'launching', 'playing'}
KEEP_SECONDS = 7 * 86400
KEEP_TESTS = 20


def sha(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def problem(code, message, status=409, **extra):
    return ProjectError(status, message, code=code, **extra)


def token(value):
    return isinstance(value, str) and ID.fullmatch(value)


def write(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=1) + '\n', encoding='utf-8', newline='\n')
    temp.replace(path)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def worker_active(folder):
    """A restarted server can still have a build or one of its tools writing in the test folder."""
    if sys.platform == 'win32':
        command = (
            "$d = $env:XCOM_WORKSHOP_TEST_FOLDER; "
            "$p = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { "
            "$_.CommandLine -and $_.CommandLine.IndexOf($d, [StringComparison]::OrdinalIgnoreCase) -ge 0 }; "
            "if ($p) { exit 0 }; exit 3")
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
                env=dict(os.environ, XCOM_WORKSHOP_TEST_FOLDER=str(folder)), capture_output=True, timeout=10,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return result.returncode != 3
        except (OSError, subprocess.TimeoutExpired):
            return True
    try:
        result = subprocess.run(['ps', '-e', '-o', 'args='], capture_output=True, timeout=10)
        return result.returncode != 0 or os.fsencode(folder) in result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return True


class PrefabTests:
    def __init__(self, builds, live, *, prepare=stage.prepare, process_active=worker_active):
        self.builds, self.live = builds, live
        self.prepare, self.process_active = prepare, process_active
        self.root = builds.output.resolve() / '.prefab-tests'
        self.lock = threading.RLock()
        self.jobs, self.requests = {}, {}
        self.build_jobs, self.export_jobs = {}, {}
        self._recover()

    def folder(self, test):
        if not token(test):
            raise problem('test-id', 'Invalid prefab test ID.', 404)
        path = self.root / test
        if path.resolve().parent != self.root or path.is_symlink():
            raise problem('test-id', 'Invalid prefab test folder.', 404)
        return path

    def save(self, job):
        job['updatedAt'] = now()
        write(self.folder(job['id']) / 'test.json', job)

    def get(self, test):
        self.folder(test)
        if test not in self.jobs:
            raise problem('test-missing', 'This prefab test is no longer available.', 404)
        return self.jobs[test]

    def view(self, job):
        private = {'attempts', 'requestId', 'requestHash', 'projectHash', 'manifestHash', 'interruptedBuild', 'pid'}
        data = {k: deepcopy(v) for k, v in job.items() if k not in private}
        test = job['id']
        if test in self.build_jobs:
            data['build'] = self.builds.pinned_status(self.build_jobs[test])
        if test in self.export_jobs:
            runner, map_id = self.export_jobs[test]
            data['preparation'] = runner.status(map_id)
        return data

    def status(self, test):
        with self.lock:
            return self.view(self.get(test))

    def check(self, snapshot):
        """What a test of this snapshot would say, without building anything (plan "sturdier prefabs", R5): the
        prepare step alone. dict(ready, refused: why the test itself would not start or None, issues: the pieces left
        out first and then the warnings, each with its piece's name (`actor`), leftOut: how many, stage: the test
        stage's grid). `ready` false: the blank map has no export yet, so nothing could be checked."""
        game, note = lwr_game(self.live.player.settings)
        if game is None:
            raise problem('install-unavailable', note)
        try:
            result = self.prepare(snapshot, str(uuid4()), self.builds.cache, Path(game))
        except ProjectError as error:
            extra = error.extra
            if extra.get('code') in ('stage-unprepared', 'stage-missing'):
                return dict(ready=False, refused=None, issues=[], leftOut=0, stage=None,
                            message=error.message + ' Test in game prepares the blank map; the check works after.')
            if 'issues' not in extra:
                raise
            issues = extra['issues'] + (extra.get('notes') or [])
            return dict(ready=True, refused=error.message, issues=issues, stage=None,
                        leftOut=sum(1 for i in issues if i.get('leftOut')))
        return dict(ready=True, refused=None, issues=result.get('issues', result['report']['warnings']),
                    leftOut=len(result.get('leftOut', [])), stage=result['project'].get('stage', {}).get('grid'))

    def _settings(self):
        player = self.live.player
        game, note = lwr_game(player.settings)
        install, install_note, _ = player.target()
        if game is None or install is None:
            raise problem('install-unavailable', note if game is None else install_note)
        udk = player.settings.get('udk')
        return dict(game=str(game.resolve()), install=str(install.resolve()), udk=str(Path(udk).resolve()) if udk else None)

    def _map_hash(self, game, package):
        path = package_of(Path(game), package)
        if path is None:
            raise problem('donor-missing', f'{package}.upk is missing from the game install.')
        return digest_of(path)

    def _check_inputs(self, job):
        inputs = job['inputs']
        if any(inputs[k] != v for k, v in self._settings().items()):
            raise problem('settings-changed', 'The game or build settings changed. Start a new prefab test.')
        for package, digest in inputs['packages'].items():
            if self._map_hash(inputs['game'], package) != digest:
                raise problem('source-changed', f'{package}.upk changed. Start a new prefab test.')
        if stage.EXPORT_VERSION != inputs['exporterVersion']:
            raise problem('exporter-changed', 'The map exporter changed. Start a new prefab test.')

    def start(self, request):
        if (not isinstance(request, dict) or set(request) - {'snapshot', 'requestId', 'quick', 'unsaved', 'saving'}
                or not token(request.get('requestId')) or 'snapshot' not in request):
            raise problem('test-request', 'Send a complete builder snapshot and a request ID.', 400)
        snapshot = request['snapshot']
        stage.validate_snapshot(snapshot)
        quick, unsaved = request.get('quick', False), request.get('unsaved', not snapshot.get('revision'))
        saving = request.get('saving', False)
        if not isinstance(quick, bool) or not isinstance(unsaved, bool) or not isinstance(saving, bool):
            raise problem('test-request', 'Quick, unsaved and saving must be true or false.', 400)
        snapshot_hash = sha(snapshot)
        request_hash = sha([snapshot_hash, quick, unsaved] + ([True] if saving else []))
        request_id = request['requestId']
        with self.lock:
            if request_id in self.requests:
                job = self.jobs[self.requests[request_id]]
                if job['requestHash'] != request_hash:
                    raise problem('request-conflict', 'That request ID already belongs to different test contents.')
                return self.view(job)
            if busy := next((j for j in self.jobs.values() if j['phase'] in ACTIVE), None):
                raise problem('test-busy', f'{busy["label"]} is already testing.', test=busy['id'])
            if busy := self.builds.busy():
                raise problem('build-busy', f'{busy[1]} is building. Try again when it finishes.', building=busy[0])
            inputs = self._settings()
            self._prune(reserve=1)
            test = str(uuid4())
            folder = self.folder(test)
            folder.mkdir(parents=True)
            job = dict(id=test, requestId=request_id, requestHash=request_hash, snapshotHash=snapshot_hash,
                       label=snapshot['name'] if snapshot.get('revision') else 'Unsaved prefab',
                       source=dict(id=snapshot['id'], revision=snapshot.get('revision')) if snapshot.get('revision') else None,
                       unsaved=unsaved, quick=quick, saving=saving, phase='preparing', createdAt=now(), issues=[], inputs=inputs,
                       attempts={}, cancelRequested=False, dryMode=not self.live.player.cleanup)
            write(folder / 'snapshot.json', snapshot)
            self.save(job)
            self.jobs[test] = job
            self.requests[request_id] = test
            threading.Thread(target=self._run, args=(job,), daemon=True, name='prefab-test-build').start()
            return self.view(job)

    def _cancelled(self, job):
        if job['cancelRequested']:
            raise problem('test-cancelled', 'Prefab test cancelled.')

    def _export_stage(self, job):
        runner = self.live.exports
        if runner is None:
            raise problem('stage-unprepared', 'Prepare the blank map in the map browser first.')
        map_id = next((key for key in runner.catalogue['maps'] if key.casefold() == stage.MAP.casefold()), None)
        if map_id is None:
            raise problem('stage-missing', 'The blank map is missing from the map catalogue.')
        with self.lock:
            self._cancelled(job)
            try:
                runner.start(map_id, prepare=True, owner=job['id'])
            except ProjectError as error:
                raise problem('export-busy' if 'exporting' in error.extra else 'stage-export',
                              error.message, **error.extra) from error
            self.export_jobs[job['id']] = runner, map_id
        try:
            while True:
                with self.lock:
                    self._cancelled(job)
                    result = runner.status(map_id)
                if result['state'] == 'ready':
                    return
                if result['state'] != 'running':
                    raise problem('stage-export', result.get('error') or 'The blank map could not be prepared.')
                time.sleep(0.2)
        finally:
            with self.lock:
                job['preparation'] = runner.status(map_id)
                del self.export_jobs[job['id']]

    def _run(self, job):
        test, inputs = job['id'], job['inputs']
        folder = self.folder(test)
        try:
            snapshot = read(folder / 'snapshot.json')
            if sha(snapshot) != job['snapshotHash']:
                raise problem('snapshot-changed', 'The private prefab snapshot changed.')
            with self.lock:
                self._cancelled(job)
            game = Path(inputs['game'])
            packages = {name: self._map_hash(game, name) for name in (stage.MAP, stage.SHELL_DONOR)}
            with self.lock:
                inputs.update(packages=packages, exporterVersion=stage.EXPORT_VERSION)
                self.save(job)
            self._check_inputs(job)
            try:
                result = self.prepare(snapshot, test, self.builds.cache, game)
            except ProjectError as error:
                if error.extra.get('code') != 'stage-unprepared':
                    raise
                self._export_stage(job)
                self._check_inputs(job)
                result = self.prepare(snapshot, test, self.builds.cache, game)
            project = result['project']
            packages = dict(packages)
            for name, digest in result['donors'].items():
                prior = next((v for k, v in packages.items() if k.casefold() == name.casefold()), digest)
                if digest != prior:
                    raise problem('source-changed', f'{name}.upk changed during test preparation.')
                packages[name] = digest
            with self.lock:
                inputs['packages'] = packages
            if project['source']['sha256'] != packages[stage.MAP]:
                raise problem('source-changed', 'The blank map changed during test preparation.')
            self._check_inputs(job)
            project['prefabTest'] = dict(id=test, snapshotHash=job['snapshotHash'])
            document, output = folder / 'project.json', folder / 'artifacts'
            with self.lock:
                self._cancelled(job)
                write(document, project)
                write(folder / 'compile-report.json', result['report'])
                output.mkdir()
                job.update(phase='building', size=result['size'], placement=result['placement'],
                           issues=result.get('issues', result['report']['warnings']),
                           leftOut=len(result.get('leftOut', [])), projectHash=sha(project),
                           variant=project['output']['shipAs'], revision=project['revision'])
                self.save(job)

                def started(pid):
                    job['pid'] = pid
                    self.save(job)

                self.build_jobs[test] = self.builds.start_pinned(document, output, game, inputs['udk'], job['quick'], started)
            while True:
                build = self.builds.pinned_status(self.build_jobs[test])
                if build['state'] != 'running':
                    break
                time.sleep(0.2)
            with self.lock:
                job['build'] = build
                del self.build_jobs[test]
                self._cancelled(job)
            if build['state'] != 'built' or not build.get('buildId'):
                raise problem('build-failed', build.get('error') or 'The test did not produce a new package.')
            self._check_inputs(job)
            manifest = self._package(job, build['buildId'])
            with self.lock:
                self._cancelled(job)
                job.update(phase='ready', buildId=manifest['buildId'], manifestHash=sha(manifest))
                self.save(job)
        except (ProjectError, OSError, ValueError, KeyError, TypeError, installs.InstallError) as error:
            with self.lock:
                if job['cancelRequested']:
                    job.update(phase='cancelled')
                else:
                    self._failed(job, error, 'build' if job['phase'] == 'building' else 'preparation')
                self.save(job)

    def _failed(self, job, error, phase, retryable=False):
        extra = error.extra if isinstance(error, ProjectError) else {}
        issues = extra.get('issues') or [dict(code=extra.get('code', phase + '-failed'), message=str(error))]
        report = extra.get('report') or {}
        job.update(phase='failed', failedDuring=phase, retryable=retryable,
                   issues=issues + (extra.get('notes') or report.get('warnings', [])))
        for key in ('size', 'placement', 'cleanup'):
            if key in extra:
                job[key] = extra[key]

    def _package(self, job, build_id):
        folder = self.folder(job['id'])
        project = read(folder / 'project.json')
        if sha(project) != job['projectHash'] or sha(read(folder / 'snapshot.json')) != job['snapshotHash']:
            raise problem('snapshot-changed', 'The private project or prefab snapshot changed.')
        output = folder / 'artifacts' / job['variant']
        if output.resolve() != output:
            raise problem('package-changed', 'The prefab test package moved.')
        manifest = read(output / 'manifest.json')
        if not isinstance(manifest, dict):
            raise problem('package-changed', 'The prefab test package manifest is invalid.')
        source, identity = manifest.get('source') or {}, manifest.get('project') or {}
        if (manifest.get('buildId') != build_id or manifest.get('variant') != job['variant']
                or manifest.get('prefabTest') != project['prefabTest'] or identity.get('id') != job['id']
                or identity.get('revision') != job['revision'] or bool(manifest.get('quick')) != job['quick']
                or source.get('map') != stage.MAP or source.get('sha256') != project['source']['sha256']
                or source.get('exporterVersion') != job['inputs']['exporterVersion']
                or job.get('manifestHash', sha(manifest)) != sha(manifest)):
            raise problem('package-changed', 'The package does not match the build of this prefab snapshot.')
        files = manifest.get('files') or {}
        if f'CookedPCConsole/{job["variant"]}.upk' not in files or any(
                (output / rel).resolve().parent != output / 'CookedPCConsole' for rel in files):
            raise problem('package-changed', 'The prefab test package files are invalid.')
        inputs = {name.casefold(): digest for name, digest in job['inputs']['packages'].items()}
        donors = list(manifest.get('donors') or [])
        if shell := manifest.get('shell'):
            donors.append(dict(map=shell.get('donor'), sha256=shell.get('sha256')))
        if any(not d.get('map') or inputs.get(d['map'].casefold()) != d.get('sha256') for d in donors):
            raise problem('source-changed', 'A donor used by the build differs from the prepared sources.')
        verified, _ = installs.read_package(output)
        if verified != manifest:
            raise problem('package-changed', 'The prefab test package changed during verification.')
        return manifest

    def cancel(self, test):
        with self.lock:
            job = self.get(test)
            can_cancel_launch = job['phase'] == 'launching' and not job.get('launchCommitted')
            if job['phase'] in ('preparing', 'building', 'ready') or can_cancel_launch:
                job['cancelRequested'] = True
                if job['phase'] == 'ready' or can_cancel_launch:
                    job['phase'] = 'cancelled'
                self.save(job)
                if test in self.export_jobs:
                    self.export_jobs[test][0].cancel_owned(test)
                if test in self.build_jobs:
                    try: self.builds.stop(test)
                    except ProjectError: pass  # the exact build just ended
            return self.view(job)

    def play(self, test, request):
        if (not isinstance(request, dict) or set(request) != {'buildId', 'attemptId'}
                or not token(request.get('attemptId')) or not isinstance(request.get('buildId'), str)):
            raise problem('launch-request', 'Send the expected build ID and a launch-attempt ID.', 400)
        attempt, build_id = request['attemptId'], request['buildId']
        with self.lock:
            job = self.get(test)
            if build_id != job.get('buildId'):
                raise problem('build-mismatch', 'That build is not the verified result of this test.')
            if attempt in job['attempts']:
                return dict(self.view(job), attempt=job['attempts'][attempt])
            if job['cancelRequested'] or not (job['phase'] == 'ready' or job.get('retryable') and job['phase'] == 'failed'):
                raise problem('test-not-ready', 'This prefab test is not ready to launch.')
            job.update(phase='launching', launchAt=now(), retryable=False, launchCommitted=False)
            job['attempts'][attempt] = dict(state='launching')
            self.save(job)
        try:
            self._check_inputs(job)
            manifest = self._package(job, build_id)
            player = self.live.player

            def commit_launch():
                self._check_inputs(job)
                with self.lock:
                    self._cancelled(job)
                    job['launchCommitted'] = True
                    self.save(job)

            played = player.play_test(test, self.folder(test) / 'artifacts' / job['variant'], manifest,
                                      Path(job['inputs']['install']), commit_launch,
                                      lambda appeared, error: self._finished(test, appeared, error),
                                      saving=job.get('saving', False))
        except (ProjectError, OSError, ValueError, KeyError, TypeError, installs.InstallError) as error:
            with self.lock:
                if job['cancelRequested']:
                    job['attempts'][attempt] = dict(state='cancelled')
                else:
                    code = error.extra.get('code') if isinstance(error, ProjectError) else None
                    self._failed(job, error, 'launch', retryable=code is None and isinstance(error, ProjectError))
                    job['attempts'][attempt] = dict(state='failed', message=str(error))
                self.save(job)
        else:
            with self.lock:
                if job['phase'] == 'launching':
                    job.update(phase='dry' if played['how'] == 'dry' else 'playing', played=played)
                    job.pop('cleanup', None)
                job['attempts'][attempt] = dict(state='started', played=played)
                self.save(job)
        with self.lock:
            return dict(self.view(job), attempt=job['attempts'][attempt])

    def _finished(self, test, appeared, error):
        with self.lock:
            job = self.get(test)
            if job['phase'] == 'failed' and job.get('cleanup'):
                if error: job['cleanup'] = error
                else: job.pop('cleanup', None)
                self.save(job)
                return
            if job['phase'] not in ('launching', 'playing'):
                return
            if error or not appeared:
                self._failed(job, problem('game-cleanup' if error else 'game-not-started',
                                          error or 'XCOM did not start in time.'), 'launch', retryable=True)
            else:
                job.update(phase='finished')
            self.save(job)

    def _in_use(self, job):
        if job.get('interruptedBuild') and self.process_active(self.folder(job['id'])):
            return True
        game = (job.get('inputs') or {}).get('install')
        if not game:
            return False
        try:
            journal = installs.test_install_path(game)
            if journal.is_file() and read(journal).get('test') == job['id']:
                return True
            ledger = installs.read_ledger(game)
            variant = job.get('variant')
            return (self.live.player.test_installed(game, job['id'])
                    or bool(variant and (variant in (ledger.get('installed') or {})
                                         or variant + '.upk' in (ledger.get('playFiles') or {})
                                         or any(v['variant'] == variant for v in ledger.get('rotation') or []))))
        except (OSError, ValueError, installs.InstallError):
            return True

    def _prune(self, reserve=0):
        candidates = sorted((j for j in self.jobs.values() if j['phase'] not in ACTIVE and not j.get('dryMode')),
                            key=lambda j: j['updatedAt'], reverse=True)
        now_seconds = time.time()
        for number, job in enumerate(candidates):
            updated = datetime.fromisoformat(job['updatedAt'].replace('Z', '+00:00')).timestamp()
            if number < KEEP_TESTS - reserve and now_seconds - updated < KEEP_SECONDS:
                continue
            if self._in_use(job):
                continue
            test = job['id']
            try:
                shutil.rmtree(self.folder(test))
            except OSError:
                continue    # a file of it is held (a scan, a tool still closing): kept for the next prune
            del self.jobs[test]
            del self.requests[job['requestId']]

    def _recover(self):
        if not self.root.is_dir():
            return
        for path in self.root.iterdir():
            if not token(path.name) or path.is_symlink() or not path.is_dir():
                continue
            try:
                job = read(self.folder(path.name) / 'test.json')
            except (OSError, ValueError):
                try:
                    if time.time() - path.stat().st_mtime >= KEEP_SECONDS and not self.process_active(path):
                        shutil.rmtree(self.folder(path.name))
                except OSError:
                    pass    # held or gone meanwhile: the server starts all the same, and the next start tries again
                continue
            if (not isinstance(job, dict) or job.get('id') != path.name or not token(job.get('requestId'))
                    or 'phase' not in job or 'updatedAt' not in job):
                continue
            test = job['id']
            self.jobs[test] = job
            self.requests[job['requestId']] = test
            if job['phase'] == 'building' or job.get('interruptedBuild'):
                job['interruptedBuild'] = True
                self.builds.recovered[test] = (job['label'], lambda p=path: self.process_active(p))
            if job['phase'] in ('preparing', 'building'):
                self._failed(job, problem('test-interrupted', 'The editor stopped before the test build was verified.'),
                             'build' if job.get('interruptedBuild') else 'preparation')
                self.save(job)
            elif job['phase'] in ('launching', 'playing') or (job['phase'] == 'failed' and job.get('cleanup')):
                self._resume_play(job)
        self._prune()

    def _resume_play(self, job):
        test = job['id']
        game = Path(job['inputs']['install'])
        player = self.live.player
        for attempt in job['attempts'].values():
            if attempt['state'] == 'launching':
                attempt.update(state='interrupted', message='The editor restarted during launch.')
        if job.get('dryMode'):
            self._failed(job, problem('test-interrupted', 'The editor stopped during the dry launch.'), 'launch')
            self.save(job)
            return
        try:
            with player.lock:
                installs.recover_test_install(game)
        except (OSError, ValueError, installs.InstallError) as error:
            if not installs.game_running():
                self._failed(job, error, 'launch', retryable=True)
                job['cleanup'] = str(error)
                self.save(job)
                return
        if player.test_installed(game, test):
            launched = datetime.fromisoformat(job['launchAt'].replace('Z', '+00:00'))
            remaining = max(0, player.appear - (datetime.now(timezone.utc) - launched).total_seconds())
            job['phase'] = 'playing'
            self.save(job)
            with player.lock:
                player.watch(game, appear=remaining, finished=lambda appeared, error: self._finished(test, appeared, error))
                player.test_watching = player.watching
        else:
            self._failed(job, problem('test-interrupted', 'The editor stopped during launch. You can retry this build.'),
                         'launch', retryable=bool(job.get('buildId')))
            self.save(job)
