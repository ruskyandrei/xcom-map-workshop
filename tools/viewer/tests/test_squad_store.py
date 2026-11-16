"""The test squad's file (squads.py): no file against a bad one, the revision a save is based on, the backup, a bad
file's bytes kept, the document's checks, and the shared file's round trip (no local folder in it, a newer version
refused). Every test uses a scratch folder, never the user's own squad."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import squads  # noqa: E402
from squads import SquadError, SquadStore  # noqa: E402


def unit(**fields):
    base = dict(id='unit-1', kind='soldier', first='Tom', last='Alpha', **{'class': 'eSC_Assault'}, rank=1, look='man-a',
                country='eCountry_Canada', armour='eItem_ArmorKevlar', sidearm='eItem_Pistol', weapons=['eItem_Shotgun'],
                items=['eItem_FragGrenade'], perks=[], stats={})
    base.update(fields)
    return base


def document(*units, name='Test squad'):
    return dict(schema=squads.SCHEMA, version=1, name=name, units=list(units) or [unit()])


class Store(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'Workshop' / squads.FILE
        self.store = SquadStore(self.path)

    def tearDown(self):
        self.folder.cleanup()

    def test_path_is_beside_the_settings(self):
        self.assertEqual(squads.store_path(Path(self.folder.name) / 'x' / 'settings.json'),
                         Path(self.folder.name) / 'x' / 'test-squad.json')

    def test_no_file_then_save_then_conflict(self):
        self.assertEqual(self.store.read(), (None, 'none', None))
        revision = self.store.save(document(), 'none')
        saved, current, problem = self.store.read()
        self.assertEqual((current, problem), (revision, None))
        self.assertEqual(saved['units'][0]['first'], 'Tom')
        with self.assertRaises(SquadError) as refused: self.store.save(document(name='Other'), 'none')
        self.assertEqual(refused.exception.status, 409)
        self.assertEqual(refused.exception.extra['revision'], revision)
        second = self.store.save(document(name='Other'), revision)
        self.assertNotEqual(second, revision)
        self.assertEqual(json.loads((self.path.parent / squads.PREVIOUS).read_text(encoding='utf-8'))['name'], 'Test squad')

    def test_an_edit_of_the_file_meanwhile_is_a_conflict(self):
        revision = self.store.save(document(), 'none')
        self.path.write_text(self.path.read_text(encoding='utf-8').replace('Tom', 'Tim'), encoding='utf-8')
        with self.assertRaises(SquadError): self.store.save(document(), revision)

    def test_a_bad_file_is_reported_and_kept(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b'{"schema": "xcom-map-workshop/test-squad", "units": [')
        saved, revision, problem = self.store.read()
        self.assertIsNone(saved)
        self.assertNotEqual(revision, 'none')
        self.assertIn('not a squad file', problem)
        self.assertEqual(self.path.read_bytes()[:10], b'{"schema":')            # reading changed nothing
        self.store.save(document(), revision)
        kept = list(self.path.parent.glob('test-squad.bad-*.json'))
        self.assertEqual(len(kept), 1)
        self.assertTrue(kept[0].read_bytes().endswith(b'"units": ['))
        self.assertFalse((self.path.parent / squads.PREVIOUS).exists())

    def test_a_newer_file_is_reported_not_replaced(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps(dict(document(), version=99)), encoding='utf-8')
        saved, _, problem = self.store.read()
        self.assertIsNone(saved)
        self.assertIn('newer XCOM Map Workshop', problem)


class Checks(unittest.TestCase):
    def test_fields(self):
        good = squads.check_document(document())
        self.assertEqual(list(good), ['schema', 'version', 'name', 'units'])
        self.assertEqual(list(good['units'][0]), list(squads.UNIT_KEYS))
        bad = [
            dict(document(), schema='other'), dict(document(), version=0), dict(document(), name='  '),
            document(*[unit(id=f'u{i}') for i in range(9)]), dict(document(), units=[]),
            document(unit(), unit()),                                       # the same id twice
            document(unit(kind='tank')), document(unit(rank=40)), document(unit(rank=True)),
            document(unit(first='A' * 25)), document(unit(first='new\nline')), document(unit(armour='eItem Kevlar')),
            document(unit(weapons=['eItem_X'] * 17)), document(unit(stats={'luck': 3})), document(unit(stats={'hp': -1})),
            document(unit(stats={'hp': 1.5})), document(unit(extra=1)), document(unit(id='')),
        ]
        for i, doc in enumerate(bad):
            with self.subTest(i), self.assertRaises(SquadError): squads.check_document(doc)
        # text the game can't take is still saved (Play says why): quotes, commas, accents
        self.assertEqual(squads.check_document(document(unit(first='O"Brien, (é)')))['units'][0]['first'], 'O"Brien, (é)')

    def test_unknown_selections_stay(self):
        kept = squads.check_document(document(unit(weapons=['eItem_SomethingElse'], perks=['ePerk_Gone'])))
        self.assertEqual(kept['units'][0]['weapons'], ['eItem_SomethingElse'])
        self.assertEqual(kept['units'][0]['perks'], ['ePerk_Gone'])


class Sharing(unittest.TestCase):
    def test_round_trip_without_local_details(self):
        doc = dict(document(name='Night/Shift: B'), source=dict(family='lwr', fingerprint='abc'))
        name, text = squads.export_document(doc)
        self.assertEqual(name, 'Night_Shift_ B.xcomsquad.json')
        shared = json.loads(text)
        self.assertNotIn('source', shared)
        self.assertNotIn('revision', shared)
        self.assertNotIn(':\\', text)
        back = squads.import_document(text)
        self.assertEqual(back['units'], squads.check_document(doc)['units'])

    def test_refusals(self):
        _, text = squads.export_document(document())
        newer = json.dumps(dict(json.loads(text), version=2))
        with self.assertRaises(SquadError) as error: squads.import_document(newer)
        self.assertTrue(error.exception.extra.get('newer'))
        for bad in ('not json', '[]', json.dumps({'schema': 'x'}), 'x' * (squads.MAX_BYTES + 1), None):
            with self.subTest(str(bad)[:20]), self.assertRaises(SquadError): squads.import_document(bad)


if __name__ == '__main__':
    unittest.main()
