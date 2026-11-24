"""Builder routes, compatibility and physical bounds (no game required)."""
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import viewer_fixtures as fixtures
from prefab_bounds import measure, policy, require_supported
from prefabs import validate
from export_math import transform, view_matrix
from library import pieces_root


class BoundsTests(unittest.TestCase):
    def test_shared_boundary_cases(self):
        for case in json.loads(Path(__file__).with_name('prefab_size_cases.json').read_text()):
            with self.subTest(case['name']):
                result = policy([(case['name'], case['box'])])
                # (the limits warn and refuse nothing: plan "sturdier prefabs", R7)
                self.assertEqual((bool(result['warnings']), result['errors'], result['supported']), (case['large'], [], True))
                if 'tall' in case:
                    self.assertEqual(result['tall'], case['tall'])
                self.assertEqual(result['tiles'], case['tiles'])
                if 'outside' in case:
                    self.assertEqual(bool(result['outside']), case['outside'])

    def test_the_limits_are_the_pages(self):
        # tools/viewer/tests/limits.json is checked by the page's test too (prefab_document_test.mjs)
        import compiler
        import prefab_bounds as b
        import prefabs
        limits = json.loads(Path(__file__).with_name('limits.json').read_text())
        self.assertEqual(limits, dict(gridLevels=b.GRID_LEVELS, playedLevels=b.PLAYED_LEVELS, gridTop=b.GRID_TOP, minZ=b.MIN_Z,
                                      maxZ=b.MAX_Z, tiles=b.MAX_TILES, stageLevels=compiler.STAGE_LEVELS_MAX,
                                      stageGrid=compiler.STAGE_GRID_MAX, buildingFloors=compiler.BUILDING_FLOORS_MAX))
        self.assertEqual(prefabs.MAX_FLOORS, compiler.BUILDING_FLOORS_MAX)

    def test_geometry_wins_over_declared_floor_and_actor_origin(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp); folder = pieces_root(cache) / 'Donor' / 'generation'; folder.mkdir(parents=True)
            # A source whose pivot is far from its physical mesh; the component adds a translation.
            points = [0, 0, 0, 96, 0, 0, 0, 2200, 96]
            doc = dict(meshes=[dict(primitives=[dict(attributes=dict(POSITION=0))])],
                       accessors=[dict(bufferView=0, componentType=5126, type='VEC3', count=3)],
                       bufferViews=[dict(byteOffset=0, byteLength=36)])
            raw = json.dumps(doc).encode(); raw += b' ' * (-len(raw) % 4)
            (folder / 'mesh.glb').write_bytes(struct.pack('<III', 0x46546C67, 2, 28 + len(raw) + 36) + struct.pack('<I4s', len(raw), b'JSON') + raw + struct.pack('<I4s', 36, b'BIN\0') + struct.pack('<9f', *points))
            source = fixtures.prefab()['pieces'][0]; source['location'] = [0, 0, 0]; source['rotation'] = [0, 0, 0]
            record = dict(base='/cache-library/Donor/generation/', objects=[dict(actor=source['from']['actor'], component=source['components'][0],
                mesh='mesh', matrix=view_matrix(transform([100, 0, 0], [0, 0, 0], [1, 1, 1])), location=[100, 0, 0], rotation=[0, 0, 0])], meshes=dict(mesh=dict(url='mesh.glb')))
            library = SimpleNamespace(cache=cache, piece=lambda _: record)
            prefab = fixtures.prefab(pieces=[source], floor=dict(tiles=[1, 1]), buildings=[], groups=[])
            result = measure(prefab, library)
            self.assertTrue(result['warnings']); self.assertTrue(result['verified'])
            self.assertEqual(result['bounds'], [0, 0, 0, 96, 96, 2200])
            # (over the height allowance: said, and saved all the same)
            self.assertEqual(require_supported(prefab, library)['warnings'], result['warnings'])

            # The server's library reads every record in one batch (a large selection's save asked one by one, each
            # piece looking the install up again); a piece the batch can't give is unknown, as before.
            asked, short = [], source['from']['actor'].split('.')[-1]
            def records(sources):
                asked.append([s['actor'] for s in sources])
                return [dict(record=record) if s['actor'] == short else dict(error='not in the install') for s in sources]
            def one_by_one(_):
                raise AssertionError('asked for a piece by itself')
            batched = SimpleNamespace(cache=cache, records=records, piece=one_by_one)
            other = copy.deepcopy(source); other['actor'] = 'Other_1'; other['from'] = dict(source['from'], actor='Other_1')
            both = fixtures.prefab(pieces=[source, other], floor=dict(tiles=[1, 1]), buildings=[], groups=[])
            result = measure(both, batched)
            self.assertEqual(asked, [[short, 'Other_1']])
            self.assertEqual(result['unknown'], ['Other_1'])
            self.assertEqual(measure(prefab, batched)['bounds'], [0, 0, 0, 96, 96, 2200])

    def test_legacy_import_is_readable_and_unknown_is_not_certified(self):
        old = fixtures.prefab(floor=dict(tiles=[512, 512]))
        validate(old, fixtures.ID)
        self.assertEqual(len(measure(old)['warnings']), 1)
        small = measure(fixtures.prefab())
        self.assertTrue(small['supported']); self.assertFalse(small['verified']); self.assertEqual(len(small['unknown']), 3)
        missing = fixtures.prefab(pieces=[fixtures.prefab()['pieces'][0]], groups=[], buildings=[])
        missing['pieces'][0]['location'] = [-40000, 0, -2000]  # a pivot says nothing about unavailable mesh bounds
        self.assertTrue(measure(missing)['supported']); self.assertFalse(measure(missing)['verified'])


class BuilderRoutes(unittest.TestCase):
    setUp = fixtures.PrefabServer.setUp
    call = fixtures.PrefabServer.call

    def test_families_without_a_map(self):
        status, table = self.call('GET', '/families.json')
        self.assertEqual(status, 200)
        self.assertEqual(table['assemblies'], [])
        self.assertEqual(table['lightRules'], {})
        self.assertEqual(set(table['lightRecipes']), {'point', 'spot'})
        self.assertIsNone(table['exportProblem'])

    def test_complete_recovery_and_stale_write_kept_as_stale(self):
        doc = fixtures.prefab()
        self.store.save(fixtures.ID, doc, 0)
        # Working coordinates, mixed groups and unresolved recipes survive; no size cap on recovery.
        doc['pieces'][0]['location'] = [-40000, 0, -64]
        doc['floor']['tiles'] = [800, 8]
        page, other = 'aaaaaaaa-0000-4000-8000-00000000000a', 'bbbbbbbb-0000-4000-8000-00000000000b'
        state = dict(owner=page, baseRevision=1, document=doc, nextSerial=100, envelope=[-40000, 0, 0, 768, 576, 0])
        route = f'/prefabs/{fixtures.ID}/recovery.json'
        self.assertEqual(self.call('PUT', route, state), (200, dict(ok=True, revision=1, stale=False)))
        status, kept = self.call('GET', route)
        self.assertEqual(status, 200)
        self.assertEqual(kept['document'], doc); self.assertEqual(kept['envelope'], state['envelope'])
        self.assertEqual((kept['owner'], kept['others']), (page, 0))
        self.assertEqual(self.call('PUT', route, state, {'Origin': 'http://evil.example'})[0], 403)
        # another page saves (review finding 3): this page's draft stays, and its next one is kept as stale
        self.store.save(fixtures.ID, fixtures.prefab(), 1, owner=other)
        self.assertEqual(self.call('GET', route)[1]['owner'], page)
        self.assertEqual(self.call('PUT', route, state), (200, dict(ok=True, revision=2, stale=True)))
        self.assertEqual(self.call('PUT', route, dict(state, baseRevision=3))[0], 409)
        self.assertEqual(self.call('DELETE', route)[0], 400)
        self.assertEqual(self.call('DELETE', route + f'?owner={other}'), (200, dict(dropped=False)))
        self.assertEqual(self.call('DELETE', route + f'?owner={page}'), (200, dict(dropped=True)))
        self.assertIsNone(self.call('GET', route)[1])
        bad = copy.deepcopy(state); bad['document']['pieces'][0]['location'][0] = float('nan')
        self.assertEqual(self.call('PUT', route, bad)[0], 422)
        self.assertEqual(self.call('PUT', route, dict(state, owner='../x'))[0], 400)

    def test_building_only_save_and_old_oversized_import(self):
        doc = fixtures.prefab(pieces=[], groups=[])
        self.assertEqual(self.call('PUT', f'/prefabs/{fixtures.ID}/prefab.json', dict(expectedRevision=0, document=doc))[0], 200)
        # over the height allowance: saved, with the warning in its size and on its card (R7)
        doc['buildings'][0]['floors'][0]['boxes'][0][5] = 2113
        self.assertEqual(self.call('PUT', f'/prefabs/{fixtures.ID}/prefab.json', dict(expectedRevision=1, document=doc))[0], 200)
        self.assertEqual(self.call('POST', '/prefabs/import', dict(document=doc, clash='copy'))[0], 200)
        size = self.call('POST', '/prefabs/size', dict(document=doc))[1]
        self.assertEqual((size['supported'], len(size['warnings']), size['tall']), (True, 1, True))
        self.assertEqual(self.store.load(fixtures.ID)['revision'], 2)
        card = next(p for p in self.call('GET', '/prefabs.json')[1]['prefabs'] if p['id'] == fixtures.ID)
        self.assertEqual((len(card['largeSize']), card['tall']), (1, True))

    def test_an_earlier_editors_prefab_is_placed_as_it_is(self):
        # Placing a prefab sends it as stored to /prefabs/size (and /prefabs/recover-sources): a file an earlier editor
        # saved, of an older schema, is read there, not refused as a stale page's save ("This page is older than the
        # editor's server", which a reload doesn't cure)
        for version in (1, 2, 3, 4):
            old = fixtures.prefab(schemaVersion=version)
            status, size = self.call('POST', '/prefabs/size', dict(document=old))
            self.assertEqual((status, size.get('supported')), (200, True), (version, size))
            answer = self.call('POST', '/prefabs/recover-sources', dict(document=old))[1]
            self.assertNotIn('older than the editor', answer.get('error', ''), version)
        # a save of one is still refused: a page older than the server would drop the newer fields
        status, refused = self.call('PUT', f'/prefabs/{fixtures.ID}/prefab.json',
                                    dict(expectedRevision=0, document=fixtures.prefab(schemaVersion=4)))
        self.assertEqual(status, 409); self.assertIn('older than the editor', refused['error'])
        # and a schema this editor doesn't read is refused on placing too
        status, refused = self.call('POST', '/prefabs/size', dict(document=fixtures.prefab(schemaVersion=99)))
        self.assertEqual(status, 409); self.assertIn('newer editor', refused['error'])


if __name__ == '__main__': unittest.main()
