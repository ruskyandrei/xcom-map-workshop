"""The game install chosen in the page (gamesetup.py, its routes in viewer.py) and a first run's empty cache."""
from functools import partial
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from catalogue import load_catalogue  # noqa: E402
import gamesetup  # noqa: E402
from projects import ProjectError  # noqa: E402
from viewer import Handler, Live, LocalServer  # noqa: E402


def game(folder, *config):
    (folder / 'XEW' / 'XComGame' / 'CookedPCConsole').mkdir(parents=True)
    (folder / 'XEW' / 'XComGame' / 'Config').mkdir(parents=True)
    for name in config: (folder / 'XEW' / 'XComGame' / 'Config' / name).write_text('', encoding='utf8')
    return folder


class GameSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_installs_are_found_in_steams_libraries(self):
        steam, library = self.root / 'Steam', self.root / 'Library 2'
        (steam / 'steamapps').mkdir(parents=True)
        # libraryfolders.vdf writes paths with doubled backslashes
        escaped = str(library).replace('\\', '\\\\')
        (steam / 'steamapps' / 'libraryfolders.vdf').write_text(
            '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t}\n}\n' % escaped, encoding='utf8')
        plain = game(steam / 'steamapps' / 'common' / 'XCom-Enemy-Unknown', 'DefaultMaps.ini')
        lwr = game(library / 'steamapps' / 'common' / 'XCom-Enemy-Unknown.LWR', 'DefaultLZMutator.ini', 'DefaultLWRebalance.ini')
        lab = game(library / 'steamapps' / 'common' / 'XCom-Enemy-Unknown.Lab')
        (lab / 'XComLab-copy.txt').write_text('', encoding='utf8')
        (library / 'steamapps' / 'common' / 'Other Game').mkdir()
        found = gamesetup.find_installs([steam])
        self.assertEqual([(Path(f['folder']), f['kind'], f['lab']) for f in found],
                         [(plain, 'ew', False), (lwr, 'lwr', False), (lab, 'ew', True)])
        self.assertIn('lab copy', found[-1]['label'])

    def test_choosing_an_install_saves_it_and_relists_the_maps(self):
        plain = game(self.root / 'EW', 'DefaultMaps.ini')
        stored, configured = {}, []
        settings = lambda: dict(projects=self.root / 'p', output=self.root / 'o', cache=self.root / 'c',  # noqa: E731
                                game=stored.get('game'), lwr=stored.get('game'), install=None, udk=None, lab=None)

        def save(updates):
            stored.update(updates)
            return settings()
        setup = gamesetup.GameSetup(configured.append, load=settings, save=save, find=lambda: [], pick=lambda start: str(plain))
        self.assertIsNone(setup.status(checks=False)['game']['folder'])
        with self.assertRaises(ProjectError) as error: setup.choose(dict(folder=str(self.root / 'nowhere')))
        self.assertEqual(error.exception.status, 409)
        with self.assertRaises(ProjectError): setup.choose(dict(folder=''))
        self.assertEqual((stored, configured), ({}, []))
        status = setup.choose(dict(folder=f'"{plain}"'))
        self.assertEqual((status['game']['folder'], status['game']['kind']), (str(plain), 'ew'))
        self.assertEqual(stored['game'], plain)
        self.assertEqual(len(configured), 1)
        self.assertEqual(setup.browse(), dict(folder=str(plain)))
        checks = {c['name']: c for c in setup.status()['checks']}
        self.assertEqual(checks['game']['status'], 'ok')

    def test_a_first_runs_empty_cache_serves_and_the_routes_answer(self):
        cache = self.root / 'cache'; cache.mkdir()
        with self.assertRaisesRegex(ValueError, 'No prepared maps'): load_catalogue(cache)
        catalogue = load_catalogue(cache, allow_empty=True)
        self.assertEqual(catalogue, dict(defaultMap=None, maps={}))
        plain = game(self.root / 'EW', 'DefaultMaps.ini')
        live = Live(catalogue)
        chosen = []
        setup = gamesetup.GameSetup(lambda s: (chosen.append(s), setattr(live, 'catalogue', dict(defaultMap=None, maps={}))),
                                    load=lambda: dict(projects=None, output=None, cache=cache, game=None, lwr=None,
                                                      install=None, udk=None, lab=None),
                                    save=lambda u: dict(projects=None, output=None, cache=cache, game=u['game'], lwr=u['game'],
                                                        install=None, udk=None, lab=None),
                                    find=lambda: [], pick=lambda start: None)
        server = LocalServer(('127.0.0.1', 0), partial(Handler, live=live, setup=setup))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{server.server_port}'

        def call(method, path, body=None, origin=None):
            data = None if body is None else json.dumps(body).encode()
            request = Request(base + path, data=data, method=method, headers={'Content-Type': 'application/json'} if data else {})
            if origin: request.add_header('Origin', origin)
            try:
                with urlopen(request) as response: return response.status, json.loads(response.read())
            except HTTPError as error: return error.code, json.loads(error.read())
        self.assertEqual(call('GET', '/maps.json'), (200, dict(defaultMap=None, maps=[])))
        status, body = call('GET', '/setup.json?checks=0')
        self.assertEqual((status, body['game']['folder'], 'checks' in body), (200, None, False))
        self.assertEqual(call('POST', '/setup/game', dict(folder=str(plain)), origin='http://evil.example')[0], 403)
        status, body = call('POST', '/setup/game', dict(folder=str(plain)))
        self.assertEqual((status, len(chosen)), (200, 1))
        self.assertEqual(call('POST', '/setup/browse', {}), (200, dict(folder=None)))
        self.assertEqual(call('GET', '/setup/game')[0], 405)
        # nothing exported: an asset asked for is denied, not a crash
        with self.assertRaises(HTTPError): urlopen(base + '/cache/URB_Bar/scene.json')


if __name__ == '__main__': unittest.main()
