"""The families route's content (families.py): the compiler's family table and a map's assemblies, each once."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from families import FamilyCache, families  # noqa: E402

PL = 'TheWorld.PersistentLevel.'


def part(actor, cls, at, mesh='m', **extra):
    return dict(actor=PL + actor, actorClass=cls, sourcePackage='URB_Bar', layer='base', location=list(at),
                rotation=[0, 0, 0], mesh=mesh, prefab=extra.get('prefab'), partner=extra.get('partner'))


def scene():
    """A ladder, a door with its frame, a car (body, glass and light bar), a lone prop, and a streamed piece named as
    the ladder is."""
    objects = [
        part('XComLadder_3', 'XComLadder', (432, 1296, 16)),
        part('XComInteractiveLevelActor_26', 'XComInteractiveLevelActor', (480, 144, 16), mesh='leaf'),
        part('XComDestructibleActor_502', 'XComDestructibleActor', (480, 144.4, 16), mesh='frame'),
        part('XComDestructibleActor_24', 'XComDestructibleActor', (0, 0, 0), prefab='PrefabInstance_41',
             partner=PL + 'XComFracLevelActor_25'),
        part('XComFracLevelActor_25', 'XComFracLevelActor', (0, 0, 0), prefab='PrefabInstance_41'),
        part('XComDestructibleActor_26', 'XComDestructibleActor', (0, 0, 0), prefab='PrefabInstance_41'),
        part('XComDestructibleActor_4', 'XComDestructibleActor', (0, -96, 0)),
        dict(part('XComLadder_3', 'XComLadder', (0, 0, 0)), sourcePackage='patch_bar', layer='stream'),
    ]
    meshes = {'m': dict(name='Props.Meshes.Box', bounds=[0, 0, 237.4, 15, 31, 237.4, 240]),
              'leaf': dict(name='Doors.Meshes.DoorSwingSingleD'), 'frame': dict(name='Doors.Meshes.DoorSwingSingleD_Frame')}
    # patch_bar's hidden ladder beside the bar's, with the same ends (its XComLadder_11)
    helper = dict(part('XComLadder_11', 'XComLadder', (436, 1296, 14)), sourcePackage='patch_bar', layer='stream', hidden=True)
    return dict(name='URB_Bar', objects=objects, meshes=meshes, buildings=[],
                tileGrid=dict(origin=[-2783.9998, -1920.0, 0.0], size=[96, 96, 64]),
                streams={'patch_bar': dict(kind='lwr', objects=[helper])})


class FamilyTests(unittest.TestCase):
    def test_serve_family_lifts_a_family(self):
        """`serve --family effect` (families.ENABLED): the page is told the family builds, as the Build is."""
        import families as module
        module.ENABLED.add('effect')
        try:
            got = families(scene())['families']
        finally:
            module.ENABLED.discard('effect')
        self.assertEqual((got['effect']['builds'], got['sound']['builds']), (True, False))
        self.assertFalse(families(scene())['families']['effect']['builds'])

    def test_the_table_and_the_assemblies_each_once(self):
        got = families(scene())
        self.assertEqual(got['map'], 'URB_Bar')
        self.assertEqual(set(got['families']), {'scenery', 'destructible', 'collectible', 'ladder', 'door', 'frameless-door',
                                                'car', 'van', 'fracturing', 'physics', 'other', 'light', 'building',
                                                'effect', 'sound'})
        # effects and sounds (the effects and sounds plan, FX3) wait for their game check, unless the server lifts them
        self.assertEqual({f: got['families'][f]['builds'] for f in ('effect', 'sound')}, {'effect': False, 'sound': False})
        self.assertTrue(got['families']['ladder']['grid'])
        # the page takes what builds and what keeps the pose rule from here: fracturing pieces build on the grid,
        # physics props at any pose (9 November 2026); doors without a frame still wait
        self.assertEqual({f: (v['builds'], v['grid']) for f, v in got['families'].items() if f in ('fracturing', 'physics', 'frameless-door')},
                         {'fracturing': (True, True), 'physics': (True, False), 'frameless-door': (True, True)})
        self.assertEqual((got['classFamily']['XComDecoFracLevelActor'], got['classFamily']['KAsset']), ('fracturing', 'physics'))
        self.assertEqual(got['classFamily']['XComLadder'], 'ladder')
        self.assertEqual(got['grid'], dict(tile=96.0, storey=64.0, quarter=16384, slack=0.5))
        found = {a['family']: a for a in got['assemblies']}
        self.assertEqual(sorted(found), ['car', 'door', 'ladder'])
        self.assertEqual(found['door']['members'], [PL + 'XComDestructibleActor_502', PL + 'XComInteractiveLevelActor_26'])
        self.assertEqual(found['door']['pivot'], PL + 'XComInteractiveLevelActor_26')
        self.assertEqual(found['car']['pivot'], PL + 'XComDestructibleActor_24')
        self.assertEqual(len(found['car']['members']), 3)
        self.assertEqual(found['ladder']['members'], [PL + 'XComLadder_3'])
        self.assertEqual(got['helpers'], {PL + 'XComLadder_3': [dict(stream='patch_bar', actor=PL + 'XComLadder_11',
                                                                       match='exact', distance=4.0)]})
        json.dumps(got)

    def test_the_cache_reads_a_map_once(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'scene.json'
            path.write_text(json.dumps(scene()), encoding='utf-8')
            cache = FamilyCache()
            first = cache.get(folder)
            path.write_text('{}', encoding='utf-8')
            self.assertIs(cache.get(folder), first)


class LightTableTests(unittest.TestCase):
    """families.json's light verdicts, recipes and the export check (editor lights plan 3.4, 4.1, 4.2)."""
    def test_verdicts_recipes_and_the_export_check(self):
        s = scene()
        s['lights'] = [dict(id='light:1', actor=PL + 'PointLight_1', layer='base', role='static', kind='point',
                            lightmapGuid='0' * 32, bakedInto=['x'], referencedBy=[], channels=False),
                       dict(id='light:2', actor=PL + 'GeneratedMeshAreaLight_2', layer='base', role='area', kind='spot')]
        got = families(s)
        self.assertIsNone(got['lightRules']['light:1'])
        self.assertIn('glowing surface', got['lightRules']['light:2'])
        self.assertEqual(got['lightRecipes']['spot']['latest'], 1)
        self.assertEqual(got['lightRecipes']['spot']['values']['outerConeAngle'], 44.0)
        self.assertIn('older than export 18', got['exportProblem'])
        self.assertIn('note', got['families']['light'])
        s.update(exporterVersion=18, lightMetadata=dict(version=1, areaMatcher=1))
        self.assertIsNone(families(s)['exportProblem'])


if __name__ == '__main__':
    unittest.main()
