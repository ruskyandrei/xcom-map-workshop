"""What xcom_editor.cmd asks the editor's server before it stops it, and how it knows a server it started is up
(review finding 47). The launcher's restart (its double-click) used to kill the server whatever it was doing, a build
or a queue of builds included, and said a server that was still preparing its cache had not started.

  python tools/viewer/launch_check.py busy --port 8768
      whether the server is building: exit 0 when nothing is; 1 when a build or the build queue runs (said in a line);
      2 when the server does not answer (said too)
  python tools/viewer/launch_check.py wait --port 8768 [--seconds 300]
      wait until a server answers on the port: exit 0 once one does; 1 when the server the launcher started beside
      this (the python process the same cmd started) has ended, or the time is up
"""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import procs  # noqa: E402


def building(port, timeout=30.0):
    """What the server on `port` is building, in words ([] when nothing): the projects being built (GET /manager.json,
    each project's `building`: a build from the build window or the queue's) and its build queue while it runs (GET
    /manager/queue.json). An OSError or a ValueError when it does not answer."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def get(path):
        with opener.open(f'http://127.0.0.1:{port}{path}', timeout=timeout) as answer:
            return json.loads(answer.read().decode('utf-8'))
    listed = get('/manager.json')
    names = [str(p.get('name') or p.get('variant') or p.get('id')) for p in listed.get('projects') or []
             if isinstance(p, dict) and p.get('building')]
    out = [f'building {", ".join(names)}'] if names else []
    try: queue = get('/manager/queue.json')
    except urllib.error.HTTPError as error:
        if error.code != 404: raise
        queue = {}                                      # a server with no build queue
    if queue.get('state') in ('running', 'stopping'):
        left = sum(1 for i in queue.get('items') or [] if isinstance(i, dict) and i.get('state') in ('waiting', 'starting', 'building'))
        out.append(f'its build queue is {queue["state"]} ({left} to build)')
    return out


def started(parent):
    """Whether a python process that `parent` started (the cmd running the launcher, whose `start` made the server its
    child) still runs, this one aside. True when the process table can't be read."""
    try: table = procs.processes()
    except OSError: return True
    return any(p != os.getpid() and pp == parent and name.lower().startswith('python') for p, (pp, name) in table.items())


def wait(port, seconds=300.0, parent=None, poll=0.5, say=print):
    """Until a server answers on 127.0.0.1:`port`: 'listening'; 'ended' once no python process `parent` started is left
    (the server died: a port in use, a broken setting); 'timeout' when the time is up. Says every 15 s that it waits."""
    start = time.monotonic()
    note = start + 15
    while time.monotonic() - start < seconds:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1): return 'listening'
        except OSError:
            pass
        if parent is not None and not started(parent): return 'ended'
        if time.monotonic() >= note:
            say(f'Still starting ({round(time.monotonic() - start)} s): the editor prepares its cache before it listens.', flush=True)
            note += 15
        time.sleep(poll)
    return 'timeout'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('action', choices=('busy', 'wait'))
    ap.add_argument('--port', type=int, default=8768)
    ap.add_argument('--seconds', type=float, default=300.0)
    args = ap.parse_args(argv)
    if args.action == 'busy':
        try: doing = building(args.port)
        except (OSError, ValueError) as error:
            print(f'The editor on port {args.port} did not answer whether it is building ({error}).')
            return 2
        if not doing: return 0
        print(f'The editor is {"; ".join(doing)}. Stopping it stops that too.')
        return 1
    got = wait(args.port, args.seconds, parent=os.getppid())
    if got == 'listening': return 0
    if got == 'ended':
        print('The editor did not start: its process ended. Run python tools\\viewer\\viewer.py serve in a console to see why.')
    else:
        print(f'The editor has not answered on port {args.port} after {round(args.seconds)} s; its window says what it is doing.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
