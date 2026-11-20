"""The server's guards on every request (review findings 45 and 46): the static routes refuse an absolute, drive or
network path before anything is joined or opened, every request's Host (and Origin, when sent) is checked in one
place, any failure of a route is answered as a JSON 500 with its reason, and a raw body's Content-Length is checked."""
from functools import partial
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalogue import load_catalogue  # noqa: E402
import viewer  # noqa: E402
from viewer import Handler, LocalServer, contained  # noqa: E402


class Contained(unittest.TestCase):
    """viewer.contained: the joined path or root/.denied, worked out from the text alone."""

    def test_absolute_drive_and_network_parts_are_refused_without_touching_them(self):
        root = Path(tempfile.gettempdir()).resolve() / 'served'
        denied = str(root / '.denied')
        touched = []
        def spy(*args, **kwargs):
            touched.append(args)
            raise AssertionError('the path was touched')
        with mock.patch.object(os, 'stat', spy), mock.patch.object(os, 'lstat', spy), \
                mock.patch.object(Path, 'resolve', spy), mock.patch.object(os.path, 'realpath', spy):
            for rel in ('\\\\host\\share\\f', '//host/share/f', '/host/share/f', '\\host\\share\\f', 'C:/Windows/win.ini',
                        'C:\\Windows\\win.ini', 'C:win.ini', 'mesh.glb:stream', '..\\..\\x', '../x', 'a/../../x', 'a\x00b'):
                self.assertEqual(contained(root, rel), denied, rel)
            self.assertEqual(contained(root, 'mesh-1.glb'), str(root / 'mesh-1.glb'))
            self.assertEqual(contained(root, 'vendor/three/three.module.js'), str(root / 'vendor' / 'three' / 'three.module.js'))
            self.assertEqual(contained(root, 'a/../mesh-1.glb'), str(root / 'mesh-1.glb'))
            self.assertEqual(contained(root, ''), str(root))
        self.assertEqual(touched, [])


class Server(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name) / 'URB_Bar' / 'current'
        root.mkdir(parents=True)
        (root / 'scene.json').write_text(json.dumps(dict(schemaVersion=1, exporterVersion=11, name='URB_Bar', scope='map')),
                                         encoding='utf8', newline='\n')
        (root / 'mesh-1.glb').write_bytes(b'bar')

    def serve(self, **kwargs):
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=load_catalogue(self.temp.name), **kwargs))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def stop():
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.addCleanup(stop)
        self.port = server.server_port
        return f'http://127.0.0.1:{self.port}'

    def status(self, base, path, headers=None, method='GET', data=None):
        try:
            with urlopen(Request(base + path, data=data, headers=headers or {}, method=method), timeout=10) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()

    def test_static_routes_refuse_absolute_drive_and_network_paths(self):
        base = self.serve()
        self.assertEqual(self.status(base, '/cache/URB_Bar/mesh-1.glb'), (200, b'bar'))
        for path in ('/%5C%5Chost%5Cshare%5Cf', '/C:/Windows/win.ini', '/cache/URB_Bar///host/share/f',
                     '/cache/URB_Bar/%5C%5Chost%5Cshare%5Cf', '/cache/URB_Bar/C:/Windows/win.ini', '/%2F%2Fhost/share/f'):
            self.assertEqual(self.status(base, path)[0], 404, path)

    def test_every_request_checks_its_host_and_origin(self):
        class Store:
            root = Path(self.temp.name)
            def list(self): return []
        base = self.serve(projects=Store())
        own = f'127.0.0.1:{self.port}'
        self.assertEqual(self.status(base, '/projects.json')[0], 200)
        self.assertEqual(self.status(base, '/projects.json', {'Host': f'localhost:{self.port}'})[0], 200)
        self.assertEqual(self.status(base, '/projects.json', {'Origin': f'http://{own}'})[0], 200)
        for headers in ({'Host': f'evil.example:{self.port}'}, {'Host': 'evil.example'}, {'Host': '127.0.0.1'},
                        {'Origin': 'http://evil.example'}, {'Origin': 'null'}):
            for path in ('/projects.json', '/maps.json', '/cache/URB_Bar/mesh-1.glb', '/index.html', '/guide.html'):
                code, body = self.status(base, path, headers)
                self.assertEqual(code, 403, (headers, path))
                self.assertIn('error', json.loads(body))
        # a refused request's body is read, so the connection's next request starts clean
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        connection.request('POST', '/play/start', body=b'{"map": "URB_Bar"}',
                           headers={'Host': 'evil.example', 'Content-Type': 'application/json'})
        self.assertEqual(connection.getresponse().status, 403)
        connection.close()

    def test_a_failing_route_answers_a_json_500_with_its_reason(self):
        class Store:
            root = Path(self.temp.name)
            def list(self): raise RuntimeError('the disk is on fire')
            def load(self, project_id): raise OSError(28, 'No space left on device')
        base = self.serve(projects=Store())
        code, body = self.status(base, '/projects.json')
        self.assertEqual(code, 500)
        self.assertIn('the disk is on fire', json.loads(body)['error'])
        code, body = self.status(base, '/projects/0f8b1234-1d2a-4b6c-8e9f-123456789abc/project.json')
        self.assertEqual(code, 500)
        self.assertIn('No space left on device', json.loads(body)['error'])
        # the server goes on answering
        self.assertEqual(self.status(base, '/cache/URB_Bar/mesh-1.glb'), (200, b'bar'))

    def test_a_raw_bodys_content_length_is_checked(self):
        class Prefabs:
            root = Path(self.temp.name)
            def save_picture(self, prefab_id, data): return dict(ok=True, length=len(data))
        class Builds:
            def start(self, project_id, quick=False): return dict(quick=quick)
        base = self.serve(prefabs=Prefabs(), projects=type('S', (), dict(root=Path(self.temp.name)))(), builds=Builds())
        for path, method in (('/prefabs/0f8b1234-1d2a-4b6c-8e9f-123456789abc/picture.png', 'PUT'),
                             ('/projects/0f8b1234-1d2a-4b6c-8e9f-123456789abc/build', 'POST')):
            for length in ('-1', 'abc', '-5'):
                connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
                connection.putrequest(method, path)
                connection.putheader('Content-Length', length)
                connection.putheader('Content-Type', 'application/json')
                connection.endheaders()
                response = connection.getresponse()
                self.assertEqual(response.status, 400, (path, length))
                self.assertIn('Content-Length', json.loads(response.read())['error'])
                connection.close()


if __name__ == '__main__':
    unittest.main()
