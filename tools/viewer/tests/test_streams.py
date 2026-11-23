"""What a map's missions stream into it (export 13), and textures from compiled shaders: on the LWR install's
URB_PoliceStation, which has three missions, an LWR patch, a mission stream and a material with no texture
parameter."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lab'))
import export  # noqa: E402
from package import Package  # noqa: E402
import labpaths  # noqa: E402

# XCOM_POLICE_UPK, else the LWR install's (the lwr setting) or the one in the folder XCOM_COOKED names; without it the
# tests skip
POLICE, NO_POLICE = labpaths.test_file('XCOM_POLICE_UPK', labpaths.lwr_cooked('URB_PoliceStation.upk'),
                                       'URB_PoliceStation.upk')


@unittest.skipUnless(POLICE and POLICE.exists(), NO_POLICE)
class Streams(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = Package(POLICE)

    def test_the_missions_and_what_each_streams(self):
        records = export.map_records(POLICE)
        self.assertEqual([r['label'] for r in records], ['Abduction', 'Terror', 'Data recovery'])
        # export 37: each mission's kind (a council mission's is Special/<council type>)
        self.assertEqual([r['kind'] for r in records], ['Abduction', 'TerrorSite', 'CaptureAndHold'])
        self.assertEqual(records[2]['group'], 'exalt')
        # landing intros are left out; the LWR patch is in every record, the data recovery's own stream in one
        self.assertEqual(records[0]['streams'], ['patch_policestation', 'patch_hide_randomized_objects'])
        self.assertEqual(records[2]['streams'], ['URB_PoliceStation_CNH', 'patch_policestation'])
        self.assertTrue(all(not s.startswith('CIN_') for r in records for s in r['streams']))
        self.assertEqual(export.stream_package(POLICE, 'patch_policestation').name, 'patch_policestation.upk')
        self.assertIsNone(export.stream_package(POLICE, 'patch_nowhere'))
        # a package outside an install has no records
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(export.map_records(Path(d) / 'URB_PoliceStation.upk'), [])

    def test_a_streamed_package_becomes_a_layer_of_fixed_pieces(self):
        seen = []
        with tempfile.TemporaryDirectory() as d:
            result = dict(meshes={}, materials={}, textures={}, diagnostics=[])
            streams = export.stream_layers(self.p, result, Path(d), [dict(streams=['patch_policestation', 'patch_gone'])],
                                           progress=lambda what, done, total: seen.append((what, done, total)))
        patch = streams['patch_policestation']
        self.assertEqual((patch['kind'], patch['package'], patch['error']), ('lwr', 'patch_policestation.upk', None))
        # LWR's cover blocks: placed hidden in game
        self.assertEqual((len(patch['objects']), patch['hiddenComponents'], patch['rebuildVolumes']), (6, 6, 5))
        # export 41 (KB-22): each rebuild volume as the battle reads it, the same as the Build's reading
        # (tools/bake/native_copy.py volume_sphere: the two agree on all 409 of the install's patch levels' volumes)
        spheres = patch['rebuildSpheres']
        self.assertEqual(len(spheres), 5)
        self.assertTrue(all(s['actor'].startswith('TheWorld.PersistentLevel.XComRebuildWorldDataVolume') and s['radius'] > 0
                            and len(s['centre']) == 3 for s in spheres), spheres)
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'bake'))
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'upk'))
        import audit_lighting
        import native_copy
        q = audit_lighting.Package(export.stream_package(POLICE, 'patch_policestation'))
        for s in spheres:
            centre, radius = native_copy.volume_sphere(q, q.by_name[s['actor']])
            self.assertAlmostEqual(s['radius'], radius, places=2)
            for k in range(3): self.assertAlmostEqual(s['centre'][k], centre[k], places=2)
        for o in patch['objects']:
            self.assertEqual((o['layer'], o['stream'], o['floors'], o['sceneryRole']), ('stream', 'patch_policestation', [], None))
            self.assertTrue(o['id'].startswith('stream-patch_policestation-'))
            self.assertIn(o['mesh'], result['meshes'])
        self.assertEqual(streams['patch_gone']['error'], 'not in the install')
        self.assertEqual(seen[-1], ('reading patch_policestation', 6, 6))

    def test_a_mission_streams_objects_with_what_lists_them_and_their_groups(self):
        # export 24 (mission types plan, C1): Police Station's data recovery stream
        with tempfile.TemporaryDirectory() as d:
            result = dict(meshes={}, materials={}, textures={}, diagnostics=[])
            streams = export.stream_layers(self.p, result, Path(d), [dict(streams=['URB_PoliceStation_CNH', 'patch_policestation'])])
        self.assertNotIn('missionObjects', streams['patch_policestation'])         # an LWR patch is no mission's
        objects = streams['URB_PoliceStation_CNH']['missionObjects']
        count = lambda kind: sum(o['kind'] == kind for o in objects)  # noqa: E731
        self.assertEqual([count(k) for k in ('dropIn', 'pod', 'landing', 'soldier', 'operative', 'radar', 'wave')],
                         [24, 2, 1, 6, 1, 4, 1])
        # every drop-in point is in a wave group; two capture points, each a volume and the actor it captures
        self.assertTrue(all(any('XComWaveSystem_0' in r for r in o['referencedBy']) for o in objects if o['kind'] == 'dropIn'))
        groups = {}
        for o in objects:
            if o['group']: groups.setdefault(o['group'], []).append(o['role'])
        self.assertEqual(sorted(groups), ['capture:XComCapturePointVolume_0', 'capture:XComCapturePointVolume_1'])
        self.assertEqual([sorted(roles) for roles in groups.values()], [['captured', 'volume']] * 2)   # its rebuild volumes stand elsewhere
        volume = next(o for o in objects if o['actorClass'] == 'XComCapturePointVolume')
        self.assertLess(volume['box']['min'][0], volume['box']['max'][0])

    def test_the_bomb_and_its_power_nodes_group_as_long_wars_mutator_finds_them(self):
        stream = POLICE.parent / 'URB_Slaughterhouse_Stream.upk'
        if not stream.exists(): self.skipTest('URB_Slaughterhouse_Stream not available')
        import scene_metadata
        objects = scene_metadata.mission_objects(Package(stream))
        groups = {}
        for o in objects:
            if o['group']: groups.setdefault(o['group'], []).append(o['role'])
        # export 33: the PointInSpace beside it too, as FindBomb collects it (F-124)
        self.assertEqual(sorted(groups['bomb']), ['bomb', 'button', 'effect', 'effect', 'effect', 'effect', 'effect',
                                                  'point', 'rebuild', 'visible', 'waypoint'])
        nodes = [g for g in groups if g.startswith('node:')]
        self.assertEqual(len(nodes), 8)
        self.assertTrue(all(sorted(groups[g]) == ['button', 'effect', 'effect', 'node', 'rebuild'] for g in nodes))

    def test_a_material_without_a_texture_parameter_takes_its_compiled_shaders(self):
        parent = self.p.by_name['StreetSet.Materials.Asphalt_Patch']
        self.assertEqual([self.p.name(t) for t in export.compiled_textures(self.p, parent)],
                         ['StreetSet.Textures.Asphalt_Patch_DIFF', 'StreetSet.Textures.Asphalt_Patch_MASK'])
        with tempfile.TemporaryDirectory() as d:
            exporter = export.Exporter(self.p, Path(d))
            info = exporter.materials[exporter.material(self.p.by_name['StreetSet.Materials.Asphalt_Patch_G'])]
            # its PatchSet (0, 0, 1, 1) picks the mask's blue channel for the cut-out
            self.assertTrue(info['diffuse'].endswith('-RGB') and info['opacity'].endswith('-B'))
            source = lambda key: exporter.textures[exporter.textures[key]['derivedFrom']]['name']  # noqa: E731
            self.assertEqual((source(info['diffuse']), source(info['opacity'])),
                             ('StreetSet.Textures.Asphalt_Patch_DIFF', 'StreetSet.Textures.Asphalt_Patch_MASK'))
            self.assertIn("colour from the compiled shader's Asphalt_Patch_DIFF, cut out by Asphalt_Patch_MASK's B channel",
                          ' '.join(d['message'] for d in exporter.diagnostics if d['source'] == info['name']))
            self.assertEqual(info['render']['opacitySource'], 'packed-alpha')
            # Firaxis's own misspelt parameter (PROP_Objects_Old's "Diffsue_Map"), known by its texture's name
            pipes = next(i for n, i in self.p.by_name.items() if n.endswith('.PipeParts_A')
                         and self.p.cls(i) == 'MaterialInstanceConstant')
            info = exporter.materials[exporter.material(pipes)]
            self.assertEqual(info['render']['diffuseParameter'], 'Diffsue_Map')
            self.assertIsNotNone(info['diffuse'])


if __name__ == '__main__':
    unittest.main()
