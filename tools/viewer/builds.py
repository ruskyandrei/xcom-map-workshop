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
                                   since a build swaps its package in only at the end
  POST /projects/<id>/report       a zip for a bug report: the project file, the last package's manifest and README,
                                   the newest build's logs and compile report, and the build's output here
                                   (<builds>/<variant>-report.zip); {zip, files}
  POST /builds/reveal {path}       show a folder or file of the builds folder in Windows Explorer (a build's folder, a
                                   bug report's zip): a folder opened, a file selected in its folder, never run; a path
                                   outside the builds folder is refused (403), one not there any more is 404

A tool's `progress: <what> [<done>/<total>]` lines (relight.py prints one per component) set the job's progress and
stay out of its lines.
"""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import zipfile

from projects import ProjectError
from version import VERSION

BUILD = Path(__file__).resolve().parents[1] / 'editor' / 'build.py'
STAGES = ('snapshot', 'compile', 'patch', 'shell', 'transplant', 'light', 'seeds')
STAGE_LINE = re.compile(r'^(%s): (\{.*\})$' % '|'.join(STAGES))
PROGRESS = re.compile(r'^progress: (.+?)(?: (\d+)/(\d+))?$')
KEEP = 400


def now():
    return datetime.datetime.now().isoformat(timespec='seconds')


def explorer(command):
    """Run Windows Explorer with this command line (Windows' own explorer.exe, never one found on PATH)."""
    exe = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'explorer.exe'
    subprocess.Popen(f'"{exe}" {command}', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def stop_process(pid):
    if sys.platform == 'win32':
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(pid)], capture_output=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    else:
        import signal
        try: os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError: pass


class BuildRunner:
    def __init__(self, projects, cache, output, command=None, reveal_with=None):
        """projects: the ProjectStore; cache: the viewer cache the page shows; output: the builds folder.
        command(project_file) gives the build's command line, reveal_with(arguments) runs Explorer (tests stub both)."""
        self.projects, self.cache, self.output = projects, Path(cache), Path(output)
        self.reveal_with = reveal_with or (explorer if sys.platform == 'win32' else None)
        self.command = command or (lambda f: [sys.executable, '-B', '-u', str(BUILD), str(f), '--cache', str(self.cache),
                                              '--output', str(self.output)])
        self.lock = threading.Lock()
        self.job = None
        self.recovered = {}

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
                           log=Path(document).with_name('build.log'), started=started)

    def busy(self):
        with self.lock:
            return self._busy()

    def _busy(self):
        if self.job and self.job['state'] == 'running':
            return self.job['project'], self.job['name']
        for project, (name, active) in tuple(self.recovered.items()):
            if active():
                return project, name
            del self.recovered[project]
        return None

    def _start(self, document, command, quick, log=None, started=None):
        with self.lock:
            if busy := self._busy():
                project, name = busy
                raise ProjectError(409, f'A build is running: {name}. One build at a time.', building=project)
            job = dict(project=document['id'], name=document.get('name'), revision=document.get('revision'),
                       variant=(document.get('output') or {}).get('shipAs'), quick=bool(quick), state='running',
                       stage=None, stages=[], lines=[], startedAt=now(), finishedAt=None, error=None, running=None,
                       progress=None)
            proc = subprocess.Popen(command + (['--quick'] if quick else []),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                                    start_new_session=sys.platform != 'win32',
                                    errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            job['pid'] = proc.pid
            self.job = job
        try:
            if started:
                started(proc.pid)
        finally:
            threading.Thread(target=self._follow, args=(job, proc, log), daemon=True).start()
        return job

    def pinned_status(self, job):
        with self.lock:
            return dict(job, lines=job['lines'][-40:], stages=list(job['stages']))

    def _follow(self, job, proc, log=None):
        for raw in self._lines(proc, log):
            line = raw.rstrip()
            with self.lock:
                p = PROGRESS.match(line.strip())
                if p:
                    job['progress'] = dict(what=p.group(1), done=int(p.group(2)) if p.group(2) else None,
                                           total=int(p.group(3)) if p.group(3) else None)
                    continue
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
                elif line.startswith('  $ '):
                    tool = next((t for t in ('patchtool.ps1', 'native_copy.py', 'relight.py') if t in line), None)
                    if tool: job['running'] = dict(patchtool='patch and cook',
                                                   native_copy='copying and relighting' if '--bake' in line else 'making the edit in the map',
                                                   relight='relighting')[tool.split('.')[0]]
                    job['progress'] = None
        proc.stdout.close()
        code = proc.wait()
        with self.lock:
            job['finishedAt'] = now()
            job['exitCode'] = code
            job['state'] = 'cancelled' if job.get('cancelled') else 'built' if code == 0 else 'failed'
            if job['state'] == 'cancelled':
                job['error'] = 'Cancelled: the last good package, if any, is as it was.'
            elif code and not job['error']:
                job['error'] = (job['lines'] or [f'the build stopped (exit {code})'])[-1]

    @staticmethod
    def _lines(proc, log):
        if log is None:
            yield from proc.stdout
            return
        try:
            with log.open('w', encoding='utf-8', newline='\n') as stream:
                for line in proc.stdout:
                    stream.write(line)
                    yield line
        except OSError:
            yield from proc.stdout

    def stop(self, project_id):
        """Stop the project's running build and the tools it runs (relight.py and the rest are its children)."""
        with self.lock:
            job = self.job
            if not (job and job['project'] == project_id and job['state'] == 'running'):
                raise ProjectError(409, 'No build of this project is running.')
            job['cancelled'] = True
            pid = job['pid']
        stop_process(pid)

    def cancel(self, project_id):
        self.stop(project_id)
        return self.status(project_id)

    def report(self, project_id):
        """A bug report's zip in the builds folder: what to send when a build goes wrong (or plays wrong)."""
        document = self.projects.load(project_id)
        variant = (document.get('output') or {}).get('shipAs')
        if not variant or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', variant): raise ProjectError(409, 'The project has no variant name yet.')
        work = sorted((self.output / '.work').glob(f'{variant}-*'), key=lambda p: p.name) if (self.output / '.work').is_dir() else []
        work = [w for w in work if w.is_dir()]
        files = [(self.projects.path(project_id), f'project/{self.projects.path(project_id).name}')]
        package = self.output / variant
        files += [(package / n, f'package/{n}') for n in ('manifest.json', 'README.txt') if (package / n).is_file()]
        if work:
            newest = work[-1]
            files += [(p, f'work/{newest.name}/{p.relative_to(newest).as_posix()}')
                      for p in sorted(newest.rglob('*')) if p.is_file() and (p.suffix in ('.log', '.txt') or p.name == 'compile-report.json'
                                                                            or p.name.endswith('.relight.json'))]
        with self.lock:
            job = self.job if self.job and self.job['project'] == project_id else None
            lines = list(job['lines']) if job else []
            summary = {k: job.get(k) for k in ('state', 'name', 'revision', 'startedAt', 'finishedAt', 'exitCode', 'error')} if job else None
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
                       busy=bool(busy and busy[0] != project_id),
                       output=str(self.output))
        if out['job']:
            out['job']['lines'] = out['job']['lines'][-40:]
        out['package'] = self.package(project_id, variant)
        return out
