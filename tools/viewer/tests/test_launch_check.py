"""What xcom_editor.cmd asks the editor before it stops it, and how it knows a server it started is up
(launch_check.py; review finding 47): on stand-in servers of the test, on ports the system gives."""
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import launch_check  # noqa: E402


class Answers(BaseHTTPRequestHandler):
    def __init__(self, routes, *args, **kwargs):
        self.routes = routes
        super().__init__(*args, **kwargs)

    def do_GET(self):
        status, body = self.routes.get(self.path, (404, {'error': 'Not found.'}))
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class LaunchCheck(unittest.TestCase):
    def serve(self, routes):
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Answers, routes))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_port

    def test_what_the_editor_is_building(self):
        idle = self.serve({'/manager.json': (200, dict(projects=[dict(id='a', name='Bar remix', building=False)])),
                           '/manager/queue.json': (200, dict(state='idle', items=[]))})
        self.assertEqual(launch_check.building(idle), [])
        busy = self.serve({'/manager.json': (200, dict(projects=[dict(id='a', name='Bar remix', building=True),
                                                                  dict(id='b', name='Temple', building=False)])),
                           '/manager/queue.json': (200, dict(state='running', items=[dict(state='building'), dict(state='waiting'),
                                                                                     dict(state='built')]))})
        self.assertEqual(launch_check.building(busy), ['building Bar remix', 'its build queue is running (2 to build)'])
        # a queue running between two builds is building too, and a server with no queue is asked for its builds alone
        between = self.serve({'/manager.json': (200, dict(projects=[])), '/manager/queue.json': (200, dict(state='running', items=[dict(state='waiting')]))})
        self.assertEqual(launch_check.building(between), ['its build queue is running (1 to build)'])
        no_queue = self.serve({'/manager.json': (200, dict(projects=[dict(name='X', building=True)]))})
        self.assertEqual(launch_check.building(no_queue), ['building X'])

    def test_the_command_says_it_and_exits_by_it(self):
        busy = self.serve({'/manager.json': (200, dict(projects=[dict(name='Bar remix', building=True)])),
                           '/manager/queue.json': (200, dict(state='idle'))})
        idle = self.serve({'/manager.json': (200, dict(projects=[])), '/manager/queue.json': (200, dict(state='idle'))})
        broken = self.serve({'/manager.json': (500, dict(error='broken'))})
        script = str(HERE.parent / 'launch_check.py')
        run = lambda port: subprocess.run([sys.executable, '-B', script, 'busy', '--port', str(port)],  # noqa: E731
                                          capture_output=True, text=True, timeout=60)
        done = run(busy)
        self.assertEqual(done.returncode, 1)
        self.assertIn('building Bar remix', done.stdout)
        self.assertEqual(run(idle).returncode, 0)
        done = run(broken)
        self.assertEqual(done.returncode, 2)
        self.assertIn('did not answer', done.stdout)
        with socket.socket() as s:                       # a port nothing listens on
            s.bind(('127.0.0.1', 0))
            free = s.getsockname()[1]
        self.assertEqual(run(free).returncode, 2)

    def test_waiting_for_a_server_that_starts_late(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        listener = socket.socket()
        self.addCleanup(listener.close)

        def later():
            time.sleep(0.6)
            listener.bind(('127.0.0.1', port))
            listener.listen()
        threading.Thread(target=later, daemon=True).start()
        said = []
        self.assertEqual(launch_check.wait(port, seconds=20, poll=0.05, say=lambda *a, **k: said.append(a)), 'listening')
        self.assertEqual(launch_check.wait(self.free_port(), seconds=0.3, poll=0.05), 'timeout')

    def free_port(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    @unittest.skipUnless(sys.platform == 'win32', 'the process table is read on Windows')
    def test_a_server_whose_process_ended_is_not_waited_for(self):
        """The launcher's `start` makes the server a child of its cmd, as the helper is: while a python child of the
        same parent runs the helper waits, and once none is left it stops waiting."""
        # a stand-in for the launcher's cmd: it starts a short-lived python (the server) and stays
        cmd = subprocess.Popen([sys.executable, '-c', 'import subprocess, sys, time\n'
                                'subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2)"])\n'
                                'print("started", flush=True)\ntime.sleep(30)\n'], stdout=subprocess.PIPE, text=True)
        self.addCleanup(cmd.wait)
        self.addCleanup(cmd.kill)
        self.assertEqual(cmd.stdout.readline().strip(), 'started')
        self.assertTrue(launch_check.started(cmd.pid))
        start = time.monotonic()
        self.assertEqual(launch_check.wait(self.free_port(), seconds=30, parent=cmd.pid, poll=0.05), 'ended')
        self.assertLess(time.monotonic() - start, 20)
        self.assertFalse(launch_check.started(cmd.pid))
        cmd.stdout.close()


if __name__ == '__main__':
    unittest.main()
