"""The prefab library's store and routes (private/plans/done/prefab-library-plan.md, stage P1 and P5): saving and listing,
deleting to a kept folder, the picture, importing a file from elsewhere with the choice when its id is here already,
and refusing malformed and hostile files."""
import copy
from functools import partial
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalogue import load_catalogue
from prefabs import SCHEMA, SCHEMA_VERSION, PrefabStore, recover_sources, validate
from projects import ProjectError
import settings as settings_module
from viewer import Handler, LocalServer

ID = '0f8b2c4e-1d2a-4b6c-8e9f-123456789abc'
OTHER = '1a2b3c4d-5e6f-4a1b-8c2d-3e4f5a6b7c8d'
PL = 'TheWorld.PersistentLevel.'
LIGHT = dict(color=[255, 240, 200], brightness=1.5, radius=512.0, falloffExponent=2.0, innerConeAngle=0.0,
             outerConeAngle=44.0, enabled=True)
PNG = b'\x89PNG\r\n\x1a\n' + b'\0' * 32


def prefab(prefab_id=ID, **changes):
    doc = dict(
        schema=SCHEMA, schemaVersion=SCHEMA_VERSION, id=prefab_id, name='Corner shop', floor=dict(tiles=[8, 6]),
        pieces=[
            dict(actor=PL + 'Wall_1_copy1', **{'from': dict(package='URB_Bar', level='base', actor=PL + 'Wall_1')},
                 components=[PL + 'Wall_1.StaticMeshComponent_3'], location=[96, 48, 0], rotation=[0, 16384, 0],
                 prefab=None, partner=None, recipe=dict(key='ab12cd', name='Core_384FloorB')),
            dict(actor=PL + 'Car_2_copy2', **{'from': dict(package='URB_Street', level='base', actor=PL + 'Car_2')},
                 components=[PL + 'Car_2.StaticMeshComponent_0'], location=[288, 96, 0], rotation=[0, 0, 0],
                 prefab='copy2:Car_2', partner=PL + 'Glass_2_copy3', tinted=True),
            dict(actor=PL + 'Glass_2_copy3', **{'from': dict(package='URB_Street', level='base', actor=PL + 'Glass_2')},
                 components=[PL + 'Glass_2.StaticMeshComponent_1'], location=[288, 96, 0], rotation=[0, 0, 0],
                 prefab='copy2:Car_2', partner=None),
            dict(actor=PL + 'CoverBlock_copy4', template=dict(kind='cover', version=1),
                 cover=dict(width=2, length=1, type='high', height=1), location=[0, 0, 12], rotation=[0, 0, 0]),
            dict(actor=PL + 'SpotLight_copy5', template=dict(kind='spot', version=1), light=dict(LIGHT),
                 location=[384, 288, 160], rotation=[-16384, 0, 0]),
        ],
        groups=[dict(id='g-inner', breakTogether=True, members=[dict(added=PL + 'Car_2_copy2'), dict(added=PL + 'Glass_2_copy3')]),
                dict(id='g-outer', members=[dict(group='g-inner'), dict(added=PL + 'Wall_1_copy1'), dict(building='b1')])],
        buildings=[dict(id='b1', name='Corner shop', kind='building', floors=[dict(boxes=[[0, 0, 0, 768, 576, 192]])])],
        donors=[dict(package='URB_Bar', sha256='a' * 64), dict(package='URB_Street')], mission=None)
    doc.update(changes)
    return doc


def changed(path, value, base=None):
    """The sample prefab with one value replaced at `path` (keys and indexes)."""
    doc = copy.deepcopy(base or prefab())
    at = doc
    for key in path[:-1]: at = at[key]
    if value is DROP: del at[path[-1]]
    else: at[path[-1]] = value
    return doc


DROP = object()


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'prefabs'
        self.store = PrefabStore(self.root)

    def files(self):
        return sorted(p.name for p in self.root.iterdir() if p.is_file())

    def test_save_numbers_revisions_keeps_the_previous_and_lists(self):
        first = self.store.save(ID, prefab(), 0)
        self.assertEqual((first['revision'], first['file']), (1, 'Corner shop.json'))
        second = self.store.save(ID, prefab(name='Corner shop 2'), 1)
        self.assertEqual((second['revision'], second['created']), (2, first['created']))
        self.assertEqual(self.files(), ['Corner shop 2.json'])
        previous = json.loads((self.root / '.workshop' / ID / 'prefab.prev.json').read_text(encoding='utf8'))
        self.assertEqual((previous['revision'], previous['name']), (1, 'Corner shop'))
        self.assertEqual(self.store.list(), [dict(id=ID, name='Corner shop 2', file='Corner shop 2.json', revision=2,
                                                  savedAt=second['savedAt'], pieces=4, lights=1, effects=0, sounds=0, flares=0, buildings=1,
                                                  tiles=[8, 6],
                                                  maps=['URB_Bar', 'URB_Street'], picture=False)])
        self.assertEqual(self.store.load(ID)['pieces'], prefab()['pieces'])
        with self.assertRaises(ProjectError) as stale: self.store.save(ID, prefab(), 1)
        self.assertEqual((stale.exception.status, stale.exception.extra), (409, dict(revision=2)))
        self.assertIn('This prefab was saved elsewhere', stale.exception.message)

    def test_a_deleted_prefab_is_kept_in_a_folder_not_erased(self):
        self.store.save(ID, prefab(), 0)
        self.store.save(ID, prefab(), 1)
        self.store.save_picture(ID, PNG)
        self.assertTrue(self.store.list()[0]['picture'])
        gone = self.store.delete(ID)
        self.assertEqual(self.store.list(), [])
        kept = list((self.root / '.workshop' / 'deleted').iterdir())
        self.assertEqual([str(p) for p in kept], [gone['kept']])
        self.assertEqual(json.loads(kept[0].read_text(encoding='utf8'))['id'], ID)
        self.assertTrue(kept[0].name.startswith('Corner shop '))
        self.assertFalse((self.root / '.workshop' / ID).exists())
        with self.assertRaises(ProjectError) as missing: self.store.delete(ID)
        self.assertEqual(missing.exception.status, 404)
        # the id is free again: the same prefab can be saved or imported anew
        self.assertEqual(self.store.save(ID, prefab(), 0)['revision'], 1)

    def test_the_picture_is_a_small_png_of_a_prefab_that_is_there(self):
        with self.assertRaises(ProjectError) as none: self.store.save_picture(ID, PNG)
        self.assertEqual(none.exception.status, 404)
        self.store.save(ID, prefab(), 0)
        for data in (b'<svg onload=alert(1)>', b'', PNG + b'\0' * (1 << 20)):
            with self.assertRaises(ProjectError) as refused: self.store.save_picture(ID, data)
            self.assertEqual(refused.exception.status, 422)
        self.store.save_picture(ID, PNG)
        self.assertEqual(self.store.picture_path(ID).read_bytes(), PNG)

    def test_an_imported_file_is_stored_and_one_already_here_asks(self):
        sent = prefab(revision=7, savedAt='2026-01-01T00:00:00Z')
        first = self.store.import_file(sent)
        self.assertEqual((first['id'], first['revision'], first['name']), (ID, 1, 'Corner shop'))
        with self.assertRaises(ProjectError) as clash: self.store.import_file(prefab(name='Corner shop, theirs'))
        self.assertEqual(clash.exception.status, 409)
        self.assertEqual(clash.exception.extra['clash'], dict(id=ID, name='Corner shop', revision=1, savedAt=first['savedAt']))
        self.assertEqual(self.store.load(ID)['name'], 'Corner shop')
        # replace: over the one here, as its next revision, the one before kept
        replaced = self.store.import_file(prefab(name='Corner shop, theirs'), 'replace')
        self.assertEqual((replaced['id'], replaced['revision'], replaced['replaced']), (ID, 2, True))
        self.assertEqual(self.store.load(ID)['name'], 'Corner shop, theirs')
        self.assertEqual(json.loads((self.root / '.workshop' / ID / 'prefab.prev.json').read_text(encoding='utf8'))['name'], 'Corner shop')
        # copy: a prefab of its own, the one here untouched
        copied = self.store.import_file(prefab(name='Corner shop, theirs'), 'copy')
        self.assertNotEqual(copied['id'], ID)
        self.assertEqual((copied['revision'], copied['name'], copied['copied']), (1, 'Corner shop, theirs (imported)', True))
        self.assertEqual(self.store.load(copied['id'])['id'], copied['id'])
        self.assertEqual(self.store.load(ID)['revision'], 2)
        again = self.store.import_file(prefab(name='Corner shop, theirs'), 'copy')
        self.assertEqual(again['name'], 'Corner shop, theirs (imported) 2')
        self.assertEqual(len(self.store.list()), 3)

    def test_other_schemas_and_versions_are_refused(self):
        for doc, status, words in ((None, 422, 'not an XCOM Map Workshop prefab'), ([], 422, 'not an XCOM Map Workshop prefab'),
                                   (prefab(schema='xcom-map-workshop/project'), 422, 'not an XCOM Map Workshop prefab'),
                                   (prefab(schemaVersion=4), 409, 'A newer editor is needed'),
                                   (prefab(id='../../evil'), 422, 'no valid id')):
            with self.assertRaises(ProjectError) as refused: self.store.import_file(doc)
            self.assertEqual(refused.exception.status, status, doc)
            self.assertIn(words, refused.exception.message)
        self.assertFalse(self.root.exists())

    def test_effects_and_sounds_are_pieces_of_their_own_kind(self):
        # schema 3 (effects and sounds plan, stage FX6a): a copy of a map's effect or sound, with its values at most
        steam = dict(actor=PL + 'Emitter_3_copy6', kind='effect', **{'from': dict(package='URB_Bar', level='base', actor=PL + 'Emitter_3')},
                     location=[96, 96, 32], rotation=[0, 0, 0],
                     effect=dict(scale=1.5, startsOn=False, parameters=[dict(name='Color', value=[1, 0.5, 0.25]), dict(name='Brightness', value=2)]))
        hum = dict(actor=PL + 'AmbientSoundSimple_2_copy7', kind='sound',
                   **{'from': dict(package='URB_Street', level='base', actor=PL + 'AmbientSoundSimple_2')},
                   location=[-4000, 9000, 64], rotation=[0, 0, 0], sound=dict(radiusMin=100, radiusMax=90000, volume=[0.4, 0.6], pitch=[1, 1]))
        doc = prefab()
        doc['pieces'] += [steam, hum]
        doc['groups'].append(dict(id='g-fx', members=[dict(added=steam['actor']), dict(added=hum['actor'])]))
        self.assertEqual(validate(doc, ID), [])
        saved = self.store.save(ID, doc, 0)
        self.assertEqual(self.store.load(ID)['pieces'][-2:], [steam, hum])
        row = self.store.list()[0]
        self.assertEqual((row['pieces'], row['lights'], row['effects'], row['sounds']), (4, 1, 1, 1))
        self.assertEqual(saved['revision'], 1)
        # each is where it stands for the size: a sound's reach is no part of the footprint
        from prefab_bounds import measure
        only = dict(doc, pieces=[steam, dict(hum, location=[200, 300, 64])], groups=[], buildings=[])
        size = measure(only)
        self.assertEqual((size['bounds'], size['tiles'], size['unknown']), ([96, 96, 32, 200, 300, 64], [2, 3], []))
        for path, value in (
                (['kind'], 'flare'), (['kind'], 'weather'), (['components'], ['x']),      # (a flare with an effect's values) (['partner'], None), (['sound'], dict(volume=[1, 1])),
                (['from', 'level'], 'stream'), (['from', 'package'], '..\\x'), (['effect'], 'big'), (['effect', 'scale'], 0),
                (['effect', 'scale'], 'two'), (['effect', 'startsOn'], 1), (['effect', 'follow'], 'me'), (['effect', 'script'], 'x'),
                (['effect', 'parameters'], dict(Color=1)), (['effect', 'parameters', 0, 'value'], [1, 2]),
                (['effect', 'parameters', 0, 'value'], 'red'), (['effect', 'parameters', 0, 'name'], '<b>'),
                (['effect', 'parameters'], [dict(name=f'P{k}', value=1) for k in range(65)])):
            with self.assertRaises(ProjectError, msg=path):
                validate(changed(['pieces', 5] + path, value, doc), ID)
        for path, value in ((['radiusMin'], -1), (['volume'], [1]), (['pitch'], 'high'), (['scale'], 2)):
            with self.assertRaises(ProjectError, msg=path):
                validate(changed(['pieces', 6, 'sound'] + path, value, doc), ID)
        # the recipes' recovery leaves them as saved, and their map stays among the donors
        out = recover_sources(dict(doc, pieces=[steam, hum], groups=[], donors=[dict(package='URB_Bar', sha256='a' * 64), dict(package='URB_Street')]),
                              None, lambda source: None)
        self.assertEqual((out['document']['pieces'], out['repaired'], out['unresolved']), ([steam, hum], [], []))
        self.assertEqual([d['package'] for d in out['document']['donors']], ['URB_Bar', 'URB_Street'])

    def test_a_lens_flare_is_a_piece_of_its_own_kind_without_values(self):
        # effects and sounds plan, stage FX6b: a copy of a map's lens flare, in schema 3 still; never a values object
        glare = dict(actor=PL + 'LensFlareSource_7_copy8', kind='flare', location=[48, 144, 300], rotation=[0, 8192, 0],
                     **{'from': dict(package='URB_Bar', level='base', actor=PL + 'LensFlareSource_7')})
        other = dict(glare, actor=PL + 'LensFlareSource_8_copy9', location=[48, 240, 300])
        doc = prefab()
        doc['pieces'] += [other, glare]
        doc['groups'].append(dict(id='g-flare', members=[dict(added=glare['actor']), dict(added=other['actor'])]))
        self.assertEqual(validate(doc, ID), [])
        self.assertEqual(doc['schemaVersion'], 3)
        self.store.save(ID, doc, 0)
        self.assertEqual(self.store.load(ID)['pieces'][-1], glare)
        row = self.store.list()[0]
        self.assertEqual((row['pieces'], row['lights'], row['effects'], row['sounds'], row['flares']), (4, 1, 0, 0, 2))
        from prefab_bounds import measure
        size = measure(dict(doc, pieces=[glare], groups=[], buildings=[]))
        self.assertEqual((size['bounds'], size['unknown']), ([48, 144, 300, 48, 144, 300], []))
        at = ['pieces', len(doc['pieces']) - 1]
        for path, value in ((['flare'], dict(colour=[1, 0, 0, 1])), (['flare'], {}), (['effect'], dict(scale=2)), (['sound'], dict(volume=[1, 1])),
                            (['components'], ['x']), (['from', 'level'], 'stream'), (['template'], dict(kind='spot', version=1))):
            with self.assertRaises(ProjectError, msg=path):
                validate(changed(at + path, value, doc), ID)
        out = recover_sources(dict(doc, pieces=[glare], groups=[], donors=[dict(package='URB_Bar', sha256='a' * 64)]), None, lambda source: None)
        self.assertEqual((out['document']['pieces'], out['repaired'], out['unresolved']), ([glare], [], []))

    def test_schema_1_is_read_imported_as_3_and_a_stale_page_cant_save(self):
        # schema 2 adds a copied piece's flags (piece flags plan), 3 effects and sounds
        stored = self.store.import_file(prefab(schemaVersion=1))
        self.assertEqual(self.store.load(stored['id'])['schemaVersion'], 3)
        with self.assertRaises(ProjectError) as refused: self.store.save(ID, prefab(schemaVersion=1), 1)
        self.assertEqual(refused.exception.status, 409)
        self.assertIn('older than the editor', refused.exception.message)
        flagged = changed(['pieces', 0, 'flags'], dict(walking=False, mouse=True))
        self.store.save(ID, flagged, 1)
        self.assertEqual(self.store.load(ID)['pieces'][0]['flags'], dict(walking=False, mouse=True))
        for bad in ({}, dict(walking=0), dict(ethereal=True), dict(cover=None), [True], 'off'):
            with self.assertRaises(ProjectError, msg=repr(bad)) as refused:
                validate(changed(['pieces', 0, 'flags'], bad), ID)
            self.assertIn('flags', refused.exception.message)
        # a cover block or a light has no flags
        with self.assertRaises(ProjectError):
            validate(changed(['pieces', 3, 'flags'], dict(walking=False)), ID)

    def test_a_newer_editors_small_fields_are_carried_and_named(self):
        # plan "sturdier prefabs", R6: a field this editor doesn't know is kept when its value is small, and named;
        # in the records the compiler takes exactly (a source, a template, a light's values) it is still refused
        doc = changed(['cursor'], [1, 2, 3])
        for path, value in ((['pieces', 0, 'cursor'], 'floor'), (['groups', 0, 'colour'], 7), (['buildings', 0, 'roof'], None),
                            (['donors', 0, 'note'], 'x' * 200), (['buildings', 0, 'floors', 0, 'height'], 3)):
            doc = changed(path, value, doc)
        self.assertEqual(validate(doc, ID), ['colour', 'cursor', 'height', 'note', 'roof'])
        self.assertEqual(validate(prefab(), ID), [])
        saved = self.store.save(ID, doc, 0)
        kept = self.store.load(ID)
        self.assertEqual((kept['cursor'], kept['pieces'][0]['cursor'], kept['groups'][0]['colour']), ([1, 2, 3], 'floor', 7))
        (card,) = self.store.list()
        self.assertEqual((saved['revision'], card['unknownFields']), (1, ['colour', 'cursor', 'height', 'note', 'roof']))

    def test_malformed_and_hostile_files_are_refused_whole(self):
        long = 'A' * 300
        cases = [
            (['surprise'], dict(a=1)), (['name'], ''), (['name'], 'x' * 121), (['name'], 'a\x00b'), (['name'], 7),
            (['floor'], None), (['floor', 'tiles'], [8]), (['floor', 'tiles'], [0, 6]), (['floor', 'tiles'], [8, 100000]),
            (['floor', 'tiles'], [8.5, 6]), (['floor', 'tiles'], [True, 6]), (['mission'], dict(script='x')),
            (['pieces'], 'all of them'), (['pieces'], [dict(prefab()['pieces'][3], actor=f'B_{k}') for k in range(5001)]),
            (['pieces', 0], 'a wall'), (['pieces', 0, 'actor'], '../../x'), (['pieces', 0, 'actor'], '<img src=x onerror=alert(1)>'),
            (['pieces', 0, 'actor'], long), (['pieces', 0, 'actor'], PL + 'Car_2_copy2'), (['pieces', 0, 'extra'], 'x' * 201),
            (['pieces', 0, 'location'], [0, 0]), (['pieces', 0, 'location'], [0, 0, float('nan')]),
            (['pieces', 0, 'location'], [0, 0, float('inf')]), (['pieces', 0, 'location'], [0, 0, 1e9]),
            (['pieces', 0, 'location'], ['0', 0, 0]), (['pieces', 0, 'rotation'], [0, True, 0]), (['pieces', 0, 'rotation'], DROP),
            (['pieces', 0, 'from', 'package'], '..\\..\\Windows'), (['pieces', 0, 'from', 'package'], 'URB Bar'),
            (['pieces', 0, 'from', 'level'], 'stream'), (['pieces', 0, 'from', 'actor'], 'a/b'), (['pieces', 0, 'from', 'x'], 1),
            (['pieces', 0, 'from'], 'URB_Bar'), (['pieces', 0, 'components'], []), (['pieces', 0, 'components'], ['a b']),
            (['pieces', 0, 'components'], ['C'] * 2), (['pieces', 0, 'components'], [f'C{k}' for k in range(65)]),
            (['pieces', 0, 'prefab'], 'a tag with spaces'), (['pieces', 0, 'partner'], PL + 'Nobody'), (['pieces', 0, 'tinted'], 'yes'),
            (['pieces', 0, 'recipe'], dict(key='k', name='n', more=1)), (['pieces', 0, 'recipe', 'key'], '../x'),
            (['pieces', 0, 'recipe', 'name'], long),
            (['pieces', 3, 'template'], dict(kind='cover', version=0)), (['pieces', 3, 'template', 'kind'], 'laser'),
            (['pieces', 3, 'cover', 'width'], 1000), (['pieces', 3, 'cover', 'type'], 'high cover!'), (['pieces', 3, 'from'], {}),
            (['pieces', 4, 'light', 'color'], [255, 255, 300]), (['pieces', 4, 'light', 'color'], [1.5, 2, 3]),
            (['pieces', 4, 'light', 'radius'], -1), (['pieces', 4, 'light', 'radius'], float('nan')),
            (['pieces', 4, 'light', 'enabled'], 1), (['pieces', 4, 'light', 'brightness'], DROP), (['pieces', 4, 'light', 'glow'], 1),
            (['groups'], {}), (['groups', 0, 'members'], [dict(added=PL + 'Car_2_copy2')]),
            (['groups', 0, 'members', 0], dict(added=PL + 'Nobody')), (['groups', 0, 'members', 0], dict(package='URB_Bar', level='base', actor='A')),
            (['groups', 0, 'members', 0], dict(group='g-inner')), (['groups', 0, 'members', 0], dict(added=PL + 'Wall_1_copy1')),
            (['groups', 0, 'breakTogether'], 'yes'), (['groups', 0, 'id'], 'g outer'), (['groups', 1, 'id'], 'g-inner'),
            (['groups', 1, 'members', 2], dict(building='b9')), (['groups', 0, 'script'], [[1]]),
            (['groups', 0, 'members', 0], dict(group='g-outer')),
            (['buildings', 0, 'kind'], 'bunker'), (['buildings', 0, 'floors'], []), (['buildings', 0, 'floors'], [dict(boxes=[[0, 0, 0, 96, 96, 64]])] * 11),
            (['buildings', 0, 'floors', 0, 'boxes'], [[0, 0, 0, 96, 96]]), (['buildings', 0, 'floors', 0, 'boxes'], [[0, 0, 0, 96, 96, 0]]),
            (['buildings', 0, 'floors', 0, 'boxes'], [[0, 0, 0, 96, 96, float('inf')]]), (['buildings', 0, 'name'], long),
            (['buildings', 0, 'id'], 'b 1'), (['buildings', 0, 'floors', 0, 'height'], dict(a=1)),
            (['buildings', 0, 'bad key!'], 1), (['pieces', 0, 'more'], float('nan')),
            (['donors', 0, 'package'], 'C:\\maps\\URB_Bar'), (['donors', 0, 'sha256'], 'abc'), (['donors', 1, 'package'], 'urb_bar'),
            (['donors', 0, 'path'], list(range(17))), (['created'], 5),
        ]
        for path, value in cases:
            with self.assertRaises(ProjectError, msg=(path, value)) as refused:
                validate(changed(path, value), ID)
            self.assertIn(refused.exception.status, (409, 422), (path, value))
            # what is said names no part of the file as markup: a message is words of ours and plain names only
            self.assertNotIn('<', refused.exception.message, (path, value))
            with self.assertRaises(ProjectError): self.store.save(ID, changed(path, value), 0)
        self.assertFalse(self.root.exists())
        validate(prefab(), ID)
        # what is optional can be left out, and a prefab can be of pieces only
        validate(changed(['pieces', 0, 'recipe'], DROP), ID)
        validate(prefab(groups=[], buildings=[], donors=[]), ID)
        bare = prefab(groups=[]); del bare['buildings'], bare['donors'], bare['mission']
        validate(bare, ID)
        with self.assertRaises(ProjectError): validate(prefab(), OTHER)

    def test_a_file_put_in_the_folder_by_hand_is_checked_when_it_is_read(self):
        self.root.mkdir(parents=True)
        (self.root / 'dropped in.json').write_text(json.dumps(changed(['pieces', 0, 'actor'], '<img src=x>')), encoding='utf8')
        (self.root / 'odd.json').write_text(json.dumps(dict(prefab(OTHER), pieces='many', buildings=3, donors='x')), encoding='utf8')
        # listed (the list reads no further than it must, and breaks on nothing), refused when opened
        self.assertEqual(sorted(p['file'] for p in self.store.list()), ['dropped in.json', 'odd.json'])
        for prefab_id in (ID, OTHER):
            with self.assertRaises(ProjectError) as refused: self.store.load(prefab_id)
            self.assertEqual(refused.exception.status, 422)
        # a sound one dropped in opens
        (self.root / 'odd.json').write_text(json.dumps(prefab(OTHER, name='From a friend', revision=3)), encoding='utf8')
        self.assertEqual(self.store.load(OTHER)['name'], 'From a friend')

    def test_json_that_python_reads_but_json_forbids_is_refused(self):
        text = json.dumps(prefab()).replace('[96, 48, 0]', '[NaN, 48, Infinity]')
        with self.assertRaises(ProjectError): self.store.import_file(json.loads(text))


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        scene = root / 'cache' / 'URB_Bar' / 'current'; scene.mkdir(parents=True)
        (scene / 'scene.json').write_text(json.dumps(dict(schemaVersion=1, exporterVersion=12, name='URB_Bar', scope='map')), encoding='utf8', newline='\n')
        self.store = PrefabStore(root / 'prefabs')
        self.server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=load_catalogue(root / 'cache'), prefabs=self.store))
        thread = threading.Thread(target=self.server.serve_forever, daemon=True); thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close(), thread.join(timeout=5)))

    def call(self, method, path, body=None, headers=None, raw=None):
        data = raw if raw is not None else None if body is None else json.dumps(body).encode()
        request = Request(self.base + path, data=data, method=method,
                          headers={'Content-Type': 'image/png' if raw is not None else 'application/json', **(headers or {})})
        try:
            with urlopen(request) as response:
                payload = response.read()
                return response.status, (payload if response.headers['Content-Type'] == 'image/png' else json.loads(payload))
        except HTTPError as error: return error.code, json.load(error)

    def test_save_open_list_picture_delete_and_import_over_http(self):
        self.assertEqual(self.call('GET', '/prefabs.json'), (200, dict(folder=str(self.store.root), prefabs=[])))
        status, saved = self.call('PUT', f'/prefabs/{ID}/prefab.json', dict(expectedRevision=0, document=prefab()))
        self.assertEqual((status, saved['revision']), (200, 1))
        status, opened = self.call('GET', f'/prefabs/{ID}/prefab.json')
        self.assertEqual((status, opened['name'], opened['revision'], len(opened['pieces'])), (200, 'Corner shop', 1, 5))
        status, conflict = self.call('PUT', f'/prefabs/{ID}/prefab.json', dict(expectedRevision=0, document=prefab()))
        self.assertEqual((status, conflict['revision']), (409, 1))
        self.assertEqual(self.call('GET', f'/prefabs/{ID}/picture.png')[0], 404)
        self.assertEqual(self.call('PUT', f'/prefabs/{ID}/picture.png', raw=PNG), (200, dict(ok=True)))
        self.assertEqual(self.call('GET', f'/prefabs/{ID}/picture.png'), (200, PNG))
        self.assertEqual(self.call('PUT', f'/prefabs/{ID}/picture.png', raw=b'not a picture')[0], 422)
        self.assertTrue(self.call('GET', '/prefabs.json')[1]['prefabs'][0]['picture'])
        # a file from elsewhere: stored; here already: the choice
        status, taken = self.call('POST', '/prefabs/import', dict(document=prefab(OTHER, name='From a friend')))
        self.assertEqual((status, taken['id'], taken['revision']), (200, OTHER, 1))
        status, clash = self.call('POST', '/prefabs/import', dict(document=prefab(OTHER, name='From a friend, again')))
        self.assertEqual((status, clash['clash']['name']), (409, 'From a friend'))
        self.assertEqual(self.call('POST', '/prefabs/import', dict(document=prefab(OTHER, name='Again'), clash='replace'))[1]['revision'], 2)
        self.assertEqual(self.call('POST', '/prefabs/import', dict(document=prefab(OTHER, name='Again'), clash='copy'))[1]['name'], 'Again (imported)')
        self.assertEqual(self.call('POST', '/prefabs/import', dict(document=changed(['pieces', 0, 'actor'], '<b>')))[0], 422)
        self.assertEqual(len(self.call('GET', '/prefabs.json')[1]['prefabs']), 3)
        self.assertEqual(self.call('DELETE', f'/prefabs/{ID}/prefab.json')[0], 200)
        self.assertEqual(self.call('GET', f'/prefabs/{ID}/prefab.json')[0], 404)
        self.assertEqual(self.call('DELETE', f'/prefabs/{ID}/prefab.json')[0], 404)
        self.assertEqual(len(self.call('GET', '/prefabs.json')[1]['prefabs']), 2)

    def test_changes_from_other_pages_or_hosts_are_refused(self):
        body = dict(expectedRevision=0, document=prefab())
        self.assertEqual(self.call('PUT', f'/prefabs/{ID}/prefab.json', body, {'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.call('PUT', f'/prefabs/{ID}/prefab.json', body, {'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.call('POST', '/prefabs/import', dict(document=prefab()), {'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.call('DELETE', f'/prefabs/{ID}/prefab.json', headers={'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.call('PUT', f'/prefabs/{ID}/prefab.json', body, {'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.call('GET', '/prefabs/not-an-id/prefab.json')[0], 404)
        self.assertEqual(self.call('PUT', '/prefabs/../prefab.json', body)[0], 404)
        self.assertFalse(self.store.root.exists())

    def test_a_server_without_a_library_says_so(self):
        server = LocalServer(('127.0.0.1', 0), partial(Handler, catalogue=load_catalogue(Path(self.temp.name) / 'cache')))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=5)))
        self.base = f'http://127.0.0.1:{server.server_port}'
        self.assertEqual(self.call('GET', '/prefabs.json')[0], 404)


class SettingTests(unittest.TestCase):
    def test_the_prefabs_folder_is_beside_the_projects_unless_set(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'settings.json'
            loaded = settings_module.load_settings(path)
            self.assertEqual(loaded['prefabs'], loaded['projects'].parent / 'prefabs')
            moved = settings_module.save_settings({'projects': Path(temp) / 'mine' / 'projects'}, path)
            self.assertEqual(moved['prefabs'], (Path(temp) / 'mine' / 'prefabs').resolve())
            chosen = settings_module.save_settings({'prefabs': Path(temp) / 'shared'}, path)
            self.assertEqual(chosen['prefabs'], (Path(temp) / 'shared').resolve())

    def test_portable_upgrade_keeps_an_existing_documents_prefab_library(self):
        with tempfile.TemporaryDirectory() as temp:
            docs, kit = Path(temp) / 'Documents', Path(temp) / 'portable'
            old = docs / settings_module.APP / 'prefabs'
            old.mkdir(parents=True)
            (old / 'Example.json').write_text('{}', encoding='utf-8')
            kit.mkdir()
            with patch.object(settings_module, 'documents', return_value=docs), \
                    patch.object(settings_module, 'editor_folder', return_value=kit):
                loaded = settings_module.load_settings(Path(temp) / 'settings.json')
                self.assertEqual(loaded['projects'], kit / 'projects')
                self.assertEqual(loaded['prefabs'], old)
                (kit / 'prefabs').mkdir()
                (kit / 'prefabs' / 'Current.json').write_text('{}', encoding='utf-8')
                self.assertEqual(settings_module.load_settings(Path(temp) / 'settings.json')['prefabs'], kit / 'prefabs')

    def test_doctor_checks_the_prefab_folder_and_its_parent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / 'prefabs'
            file.write_text('keep this file', encoding='utf-8')
            self.assertEqual(settings_module._writable_folder('prefabs', file)['status'], 'wrong')
            self.assertEqual(settings_module._writable_folder('prefabs', file / 'nested')['status'], 'wrong')
            self.assertEqual(settings_module._writable_folder('prefabs', root / 'future')['status'], 'ok')
            self.assertEqual(list(root.iterdir()), [file])


class RecipeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.document = prefab()
        self.wall, self.car, self.glass = self.document['pieces'][:3]
        self.key = self.wall['recipe']['key']

    def source(self, *actors, package='URB_New', key=None, member=None):
        key = key or self.key
        return dict(key=key, source=dict(package=package, sha256='c' * 64),
                    recipes={PL + a: dict(key=key, name='Match', **({'member': member} if member else {})) for a in actors},
                    objects=[dict(actor=PL + a, component=PL + a + '.StaticMeshComponent_40') for a in actors])

    def recover(self, record, extra=()):
        target = next(iter(record['recipes'])).split('.')[-1]
        source = dict(package=record['source']['package'], level='base', actor=target)
        index = dict(entries=[dict(key=record['key'], placeable=True, source=source)])
        records = {(source['package'], target): record, **dict(extra)}
        result = recover_sources(self.document, index, lambda s: records[s['package'], s['actor']])
        validate(result['document'], self.document['id'])
        return result

    def test_exact_recipe_rewrites_only_source_fields_and_donor_hash(self):
        result = self.recover(self.source('Wall_33'))
        self.assertEqual(result['repaired'], [self.wall['actor']])
        self.assertEqual(result['document']['groups'], self.document['groups'])
        self.assertEqual(result['document']['pieces'][1:], self.document['pieces'][1:])
        placed = result['document']['pieces'][0]
        for key in ('actor', 'prefab', 'partner', 'location', 'rotation'):
            self.assertEqual(placed[key], self.wall[key])
        self.assertEqual(placed['from']['actor'], PL + 'Wall_33')
        self.assertEqual(placed['components'], [PL + 'Wall_33.StaticMeshComponent_40'])
        self.assertIn(dict(package='URB_New', sha256='c' * 64), result['document']['donors'])
        self.assertNotIn('URB_Bar', [d['package'] for d in result['document']['donors']])

    def test_an_assembly_moves_as_a_whole_when_the_members_are_distinct(self):
        for piece in (self.car, self.glass):
            piece['recipe'] = dict(key='456789ab', name='Car')
        result = self.recover(self.source('Car_33', 'Glass_33', key='456789ab'))
        self.assertEqual(result['repaired'], [self.car['actor'], self.glass['actor']])
        self.assertEqual(result['document']['pieces'][1]['partner'], self.glass['actor'])
        self.assertEqual(result['document']['pieces'][2]['from']['actor'], PL + 'Glass_33')
        self.assertEqual(self.recover(self.source('Car_33', 'Car_34', key='456789ab'))['repaired'], [])

    def test_donor_hash_is_unchanged_if_unmatched_pieces_still_use_the_old_donor(self):
        self.car['from']['package'] = 'URB_Bar'
        result = self.recover(self.source('Wall_33', package='URB_Bar'))
        self.assertEqual(result['repaired'], [])
        self.assertEqual(result['document']['donors'], self.document['donors'])


if __name__ == '__main__':
    unittest.main()
