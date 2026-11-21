"""Plays with the test squad (play.py, squads.SquadService) and its routes, on the play tests' scratch installs
(viewer_fixtures.PlayInstalls) with the squad's game files added (squad_fixture.py): one snapshot per play, taken before anything in
the install changes; every kind of play writes it; a squad that can't be played stops the play with nothing changed;
and the page's routes. Every test keeps its squad file in a scratch folder."""
from functools import partial
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import installs  # noqa: E402
import squad_fixture  # noqa: E402
import squadrecords  # noqa: E402
import squads  # noqa: E402
from projects import ProjectError  # noqa: E402
from viewer_fixtures import ID, PlayInstalls, record  # noqa: E402
import deploy_fixture as dep  # noqa: E402  (tools/bake, which installs put on the path)
from viewer import Handler, LocalServer  # noqa: E402


class SquadPlay(unittest.TestCase):
    """viewer_fixtures.PlayInstalls' scratch installs and helpers, with the squad's game files in the game install."""
    package = PlayInstalls.package
    settle = PlayInstalls.settle
    files = PlayInstalls.files

    def setUp(self):
        PlayInstalls.setUp(self)
        squad_fixture.make_game(self.lwr, markers=False)
        patch = squad_fixture.enums()
        patch.__enter__()
        self.addCleanup(patch.__exit__, None, None, None)

    def player(self, **more):
        player = PlayInstalls.player(self, **more)
        player.squads = squads.SquadService(self.squad_store, player.target)
        return player

    @property
    def squad_store(self):
        if not hasattr(self, '_squad_store'):
            self._squad_store = squads.SquadStore(Path(self.temp.name) / 'Workshop' / squads.FILE)
        return self._squad_store

    def play_file(self):
        return (self.lwr / 'XEW/Binaries' / installs.PLAY_FILE).read_text(encoding='ascii')

    def saved(self, **changes):
        doc = squadrecords.default_document()
        doc['units'][0].update(changes)
        self.squad_store.save(doc, self.squad_store.read()[1])
        return doc


class Snapshot(SquadPlay):
    def test_no_file_plays_the_default_six(self):
        player = self.player()
        r = player.play(dict(map='URB_Bar'))
        squad = r['played']['squad']
        self.assertEqual((squad['name'], squad['count'], len(squad['units'])), ('Test squad', 6, 6))
        line = next(l for l in self.play_file().split('\n') if 'm_aSoldiers' in l)
        self.assertIn('strFirstName="Tom",strLastName="Alpha"', line)
        self.assertEqual(player.status()['squad'], dict(name='Test squad', units=6, saved=False, playable=True, errors=[], warnings=0))
        self.settle(player)

    def test_the_saved_squad_lands_and_a_save_meanwhile_waits_for_the_next_play(self):
        self.saved(first='Zed')
        player = self.player()
        original = player._map

        def map_and_save_another(game, map_id, mission=None):
            self.saved(first='Later')           # another tab saves while this play installs
            return original(game, map_id, mission)
        player._map = map_and_save_another
        r = player.play(dict(map='URB_Bar'))
        self.assertIn('strFirstName="Zed"', self.play_file())
        self.assertNotIn('Later', self.play_file())
        self.assertTrue(r['played']['squad']['units'][0].startswith('Zed Alpha:'))
        self.settle(player)
        player._map = original
        player.play(dict(map='URB_Bar'))
        self.assertIn('strFirstName="Later"', self.play_file())
        self.settle(player)

    def test_a_squad_that_cant_be_played_changes_nothing(self):
        self.saved(first='O"Brien')
        before = self.files(self.lwr)
        player = self.player()
        with self.assertRaises(ProjectError) as error: player.play(dict(map='URB_Bar'))
        self.assertEqual((error.exception.status, error.exception.extra.get('code')), (409, 'squad'))
        self.assertIn('Not started', error.exception.message)
        self.assertIn('letters, digits, spaces', error.exception.message)
        self.assertEqual(self.started, [])
        self.assertFalse((self.lwr / 'XEW/Binaries' / installs.PLAY_FILE).exists())
        self.assertEqual(self.files(self.lwr), before)
        self.assertFalse(installs.read_ledger(self.lwr).get('config'))      # nothing kept aside either
        self.assertFalse(player.status()['squad']['playable'])

    def test_an_unreadable_file_stops_the_play_and_stays(self):
        self.squad_store.path.parent.mkdir(parents=True, exist_ok=True)
        self.squad_store.path.write_bytes(b'{broken')
        player = self.player()
        with self.assertRaises(ProjectError) as error: player.play(dict(map='URB_Bar'))
        self.assertIn('file can\'t be used', error.exception.message)
        self.assertEqual(self.squad_store.path.read_bytes(), b'{broken')
        self.assertIn('problem', player.status()['squad'])

    def test_every_kind_of_play_writes_the_squad(self):
        self.saved(first='Kay')
        player = self.player()
        self.package()
        for request in (dict(project=ID), dict(project=ID, zone='a'), dict(map='URB_Bar', saving=True)):
            with self.subTest(request):
                r = player.play(request)
                self.assertIn('strFirstName="Kay"', self.play_file())
                self.assertEqual(r['played']['squad']['name'], 'Test squad')
                self.settle(player)
        # a prefab test: the same squad, and no aliens
        played = player._run(lambda game: dict(kind='prefab', map='URB_Bar', record=None), test='abc')
        text = self.play_file()
        self.assertIn('strFirstName="Kay"', text)
        self.assertIn('m_eAlienType eChar_None', text)
        self.assertEqual(played['squad']['count'], 6)
        self.settle(player)

    def test_a_covert_operative_gets_a_soldier_first(self):
        """T-44: the stand-in operative of a data recovery or covert extraction takes the first unit's looks, and a
        SHIV has none (the battle then waits on its loading screen), so a soldier lands first there."""
        import missions
        exalt = dep.set_field(dep.set_field(record('bar'), 'MissionType', 'eMission_CaptureAndHold',
                                                                quoted=False), 'DisplayName', 'URB_Bar (Data recovery) |0')
        maps = self.lwr / 'XEW/XComGame/Config/DefaultMaps.ini'
        maps.write_bytes(maps.read_bytes().replace(record('bar'), record('bar') + dep.EOL + exalt))
        doc = squadrecords.default_document()
        shiv = dict(squadrecords._unit(9, first='Tracks', last='', cls='eSC_None', armour='eItem_SHIVDeck_I', sidearm=None,
                                       weapons=['eItem_ShivMinigun'], items=[], look=None, country=None, kind='shiv'))
        doc['units'] = [shiv] + doc['units'][:3]
        self.squad_store.save(doc, self.squad_store.read()[1])
        player = self.player()
        r = player.play(dict(map='URB_Bar', mission=1))
        line = next(l for l in self.play_file().split('\n') if 'm_aSoldiers' in l)
        self.assertLess(line.index('strFirstName="Tom"'), line.index('strName="Tracks"'))
        self.assertIn(missions.LEAD_NOTE.format(name='Tom Alpha'), r['played']['mission']['notes'])
        self.assertEqual(r['played']['mission']['missing'], [])
        self.settle(player)
        # an abduction keeps the squad's order
        player.play(dict(map='URB_Bar', mission=0))
        line = next(l for l in self.play_file().split('\n') if 'm_aSoldiers' in l)
        self.assertLess(line.index('strName="Tracks"'), line.index('strFirstName="Tom"'))
        self.settle(player)
        # only SHIVs: the play goes ahead and says what happens
        doc['units'] = [shiv]
        self.squad_store.save(doc, self.squad_store.read()[1])
        r = player.play(dict(map='URB_Bar', mission=1))
        self.assertEqual(r['played']['mission']['missing'], [missions.NO_LEAD_MISSING])
        self.assertIn('strName="Tracks"', self.play_file())
        self.settle(player)


class Routes(SquadPlay):
    def test_get_save_check_import_export(self):
        player = self.player()
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=self.catalogue, projects=self.store,
                                                       builds=self.builds, player=player))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            def call(method, path, body=None, origin=None):
                request = Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                  headers={'Content-Type': 'application/json', **({'Origin': origin} if origin else {})})
                try:
                    with urlopen(request, timeout=10) as r: return r.status, json.loads(r.read())
                except HTTPError as e: return e.code, json.loads(e.read())
            status, s = call('GET', '/squad.json')
            self.assertEqual((status, s['revision'], s['saved'], s['problem']), (200, 'none', False, None))
            self.assertEqual(s['document'], s['default'])
            self.assertTrue(s['check']['playable'])
            self.assertEqual(s['install']['family'], 'lwr')
            self.assertIn('slots', s['choices'])
            self.assertIn('mec', s['choices']['templates'])
            doc = s['document']
            doc['units'][0]['first'] = 'Una'
            self.assertEqual(call('PUT', '/squad.json', dict(expectedRevision='none', document=doc), origin='http://evil.example')[0], 403)
            status, r = call('PUT', '/squad.json', dict(expectedRevision='none', document=doc))
            self.assertEqual((status, r['saved']), (200, True))
            saved = json.loads(self.squad_store.path.read_text(encoding='utf-8'))
            self.assertEqual((saved['units'][0]['first'], saved['source']['family']), ('Una', 'lwr'))
            status, r = call('PUT', '/squad.json', dict(expectedRevision='none', document=doc))
            self.assertEqual((status, r['code']), (409, 'squad-changed'))
            bad = json.loads(json.dumps(doc)); bad['units'][0]['first'] = 'A,b'
            status, r = call('POST', '/squad/check', dict(document=bad))
            self.assertEqual(status, 200)
            self.assertFalse(r['check']['playable'])
            self.assertTrue(r['check']['units'][0]['errors'])
            self.assertEqual(call('POST', '/squad/check', dict(document=dict(doc, schema='x')))[0], 422)
            status, shared = call('POST', '/squad/export', dict(document=doc))
            self.assertEqual((status, shared['name']), (200, 'Test squad.xcomsquad.json'))
            self.assertNotIn(str(self.temp.name), shared['text'])
            status, r = call('POST', '/squad/import', dict(text=shared['text']))
            self.assertEqual((status, r['document']['units'][0]['first']), (200, 'Una'))
            self.assertNotIn('source', r['document'])
            self.assertEqual(json.loads(self.squad_store.path.read_text(encoding='utf-8'))['units'][0]['first'], 'Una')
            self.assertEqual(call('DELETE', '/squad.json')[0], 405)
            status, play = call('GET', '/play.json')
            self.assertEqual(play['squad']['name'], 'Test squad')
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)

    def test_no_squad_service(self):
        player = PlayInstalls.player(self)
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=self.catalogue, projects=self.store,
                                                       builds=self.builds, player=player))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with self.assertRaises(HTTPError) as error: urlopen(f'http://127.0.0.1:{server.server_port}/squad.json', timeout=10)
            self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)


del SquadPlay

if __name__ == '__main__':
    unittest.main()
