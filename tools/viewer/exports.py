"""Export on first open: the viewer's server exports a map of the LWR install the first time the page asks for it.

The catalogue lists every map the install plays (catalogue.with_install); one not exported yet has no root. Opening it
in the page's map browser asks the server to export it: `viewer.py export <package> --scope map` runs in the
background into the cache root (18-32 s for the maps tried), one export at a time, and when it is done the map's entry
takes the new generation, so the page can open it at once, with no restart.

  POST /maps/<id>/export        export the map (202; 409 while another map exports; an exported map answers ready);
                                {"prepare": true} exports an exported map again, for a newer export's data (the editor
                                lights plan's export 18: the page's Prepare; and a map /maps.json marks outdated, older
                                than EXPORT_VERSION, which the page prepares again when it opens), keeping the older
                                generation
  GET  /maps/<id>/export.json   its state: idle, running, ready or failed, the seconds so far, its progress (from the
                                export's `progress: <what> <done>/<total>` lines: the map's pieces are 90% of the
                                bar, its streamed packages' the rest), the error, the log's last lines, and whether
                                another map is exporting (busy)

The package is found when the export starts (maplist.package_of in the install settings.resolve_game finds then), since
switch_install renames the install's folder while the server runs.
"""
import datetime
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

from builds import PROGRESS, stop_process
from catalogue import generation
from maplist import package_of
from projects import ProjectError
from settings import resolve_game

VIEWER = Path(__file__).resolve().parent / 'viewer.py'
KEEP = 200


def now():
    return datetime.datetime.now().isoformat(timespec='seconds')


def result_of(lines):
    """The export command's JSON result (its last output: {"folder": ..., "counts": ..., "diagnostics": ...})."""
    for start in range(len(lines) - 1, -1, -1):
        if lines[start] == '{':
            try: return json.loads('\n'.join(lines[start:]))
            except ValueError: return None
    return None


class ExportRunner:
    def __init__(self, catalogue, cache, lwr, command=None, prune=False):
        """catalogue: the server's (its entries are updated in place); cache: the cache root exports go to; lwr: the
        game setting (a game folder or a folder holding it, or None). command(package) gives the export's command line
        (tests stub it). prune: once a map has its new generation, its older ones are deleted (prune.py; the main
        server's runner)."""
        self.catalogue, self.cache, self.lwr, self.prune = catalogue, Path(cache), lwr, prune
        self.command = command or (lambda package: [sys.executable, '-B', '-u', str(VIEWER), 'export', str(package),
                                                    '--scope', 'map', '--cache', str(self.cache)])
        self.lock = threading.Lock()
        self.job = None

    def entry(self, map_id):
        entry = self.catalogue['maps'].get(map_id)
        if entry is None: raise ProjectError(404, f'No map called {map_id} is listed.')
        return entry

    def package(self, map_id):
        if self.lwr is None: raise ProjectError(409, 'The game install is not set: choose it in the editor (viewer.py settings --game ...).')
        game, note = resolve_game(self.lwr)
        if game is None: raise ProjectError(409, f'The game install was not found: {note}')
        path = package_of(game, map_id)
        if path is None: raise ProjectError(404, f'{map_id}.upk is not in {game}.')
        return path

    def start(self, map_id, prepare=False, owner=None):
        """Export the map; `prepare`: again, though it is exported (a newer exporter's data). The entry keeps its
        current generation until the new one is published, so a failed export leaves it as it was."""
        entry = self.entry(map_id)
        with self.lock:
            running = self.job if self.job and self.job['state'] == 'running' else None
            if (entry.get('ready') and not prepare) or (running and running['map'] == map_id): return self._status(map_id)
            if running:
                raise ProjectError(409, f'{running["label"]} is being prepared. One map at a time.',
                                   exporting=running['map'])
            package = self.package(map_id)
            job = dict(map=map_id, label=entry.get('label') or map_id, package=str(package), state='running',
                       startedAt=now(), started=time.monotonic(), seconds=0, lines=[], error=None, folder=None,
                       progress=None, owner=owner)
            proc = subprocess.Popen(self.command(package), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    encoding='utf-8', errors='replace', start_new_session=sys.platform != 'win32',
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            job['pid'] = proc.pid
            self.job = job
            threading.Thread(target=self._follow, args=(job, proc), daemon=True).start()
            return self._status(map_id)

    def cancel_owned(self, owner):
        with self.lock:
            job = self.job
            if not job or job['state'] != 'running' or job['owner'] != owner:
                return
            job['cancelled'] = True
            pid = job['pid']
        stop_process(pid)

    def _follow(self, job, proc):
        lines = []
        for raw in proc.stdout:
            line = raw.rstrip()
            m = PROGRESS.match(line.strip())
            if m and m.group(2):
                # the map's pieces, then each streamed package's: the map is most of the work
                done, total = int(m.group(2)), int(m.group(3))
                what = m.group(1)
                share = done / max(total, 1)
                with self.lock:
                    job['progress'] = dict(what=what, done=done, total=total,
                                           fraction=round(0.9 * share if what == 'reading the map' else 0.9 + 0.1 * share, 3))
                continue
            lines.append(line)
            with self.lock: job['lines'] = (job['lines'] + [line])[-KEEP:]
        proc.stdout.close()
        code = proc.wait()
        error, fresh = None, None
        if code:
            error = next((l for l in reversed(lines) if l.strip()), f'the export stopped (exit {code})')
        else:
            result = result_of(lines)
            try:
                if not result or not result.get('folder'): raise ValueError('the export printed no result')
                fresh = generation(result['folder'])
                if fresh['id'].casefold() != job['map'].casefold() or fresh['scope'] != 'map':
                    raise ValueError(f'the export made {fresh["id"]} ({fresh["scope"]}), not {job["map"]}')
            except (ValueError, OSError) as problem:
                error, fresh = str(problem), None
        with self.lock:
            if job.get('cancelled'):
                fresh, error = None, 'Preparation cancelled.'
            if fresh:
                entry = self.catalogue['maps'][job['map']]
                # root before ready: a request that sees ready finds the root
                entry.update(root=fresh['root'], scope=fresh['scope'], priority=fresh['priority'])
                entry['ready'] = True
                job['folder'] = str(fresh['root'])
            job['error'] = error
            job['exitCode'] = code
            job['seconds'] = round(time.monotonic() - job['started'], 1)
            job['state'] = 'ready' if fresh else 'failed'
        # the map now serves its new generation: its older ones go (prune.py)
        if fresh and self.prune:
            try:
                import prune
                job['pruned'] = prune.prune(self.cache, only=Path(fresh['root']).parent, keep=[fresh['root']])['removed']
            except OSError:
                pass

    def _status(self, map_id):
        entry = self.catalogue['maps'].get(map_id) or {}
        job = self.job
        mine = job if job and job['map'] == map_id else None
        out = dict(map=map_id, ready=bool(entry.get('ready')), busy=bool(job and job['state'] == 'running' and not mine),
                   exporting=job['map'] if job and job['state'] == 'running' else None)
        if mine:
            seconds = round(time.monotonic() - mine['started'], 1) if mine['state'] == 'running' else mine['seconds']
            out.update(state=mine['state'], seconds=seconds, error=mine['error'], progress=mine['progress'],
                       lines=mine['lines'][-20:], startedAt=mine['startedAt'])
        else:
            out.update(state='ready' if entry.get('ready') else 'idle', seconds=None, error=None, progress=None, lines=[])
        return out

    def status(self, map_id):
        self.entry(map_id)
        with self.lock: return self._status(map_id)
