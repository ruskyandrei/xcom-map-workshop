"""The UDK Lightmass calibration scene writer and the tangent frames its reader uses."""
from pathlib import Path
import math
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import udk_calib_scene as scene  # noqa: E402
import udk_calib_read as reader  # noqa: E402

R2 = math.sqrt(0.5)


def close(a, b, tol=1e-6):
    return all(abs(x - y) < tol for x, y in zip(a, b))


class Rotations(unittest.TestCase):
    def test_a_light_pitched_down_45_degrees_comes_from_minus_x(self):
        self.assertTrue(close(scene.light_direction(-8192, 0), (-R2, 0, R2)))
        self.assertTrue(close(scene.light_direction(-16384, 0), (0, 0, 1)))

    def test_pitch_tilts_the_normal_towards_minus_x(self):
        x, y, z = scene.rotation_matrix(8192, 0, 0)
        self.assertTrue(close(z, (-R2, 0, R2)))
        self.assertTrue(close(x, (R2, 0, R2)))
        self.assertTrue(close(y, (0, 1, 0)))

    def test_yaw_turns_x_towards_y(self):
        x, y, z = scene.rotation_matrix(0, 16384, 0)
        self.assertTrue(close(x, (0, 1, 0)) and close(y, (-1, 0, 0)) and close(z, (0, 0, 1)))

    def test_rotator_from_axes_inverts_rotation_matrix(self):
        for rot in [(0, 0, 0), (8192, 0, 0), (0, 16384, 0), (-3000, 12000, 7000), (4096, -20000, -9000)]:
            self.assertEqual(scene.rotator_from_axes(*scene.rotation_matrix(*rot)), rot)

    def test_light_tangent_placement_puts_the_light_where_asked(self):
        to_light = scene.light_direction(-8192, 0)
        for az, el in [(90, 35), (210, 10), (0, 90), (330, 60), (150, 5)]:
            rot = scene.rotator_from_axes(*scene.axes_for_tangent_light(to_light, az, el))
            t, b, n = reader.tangent_frame(scene.rotation_matrix(*rot))
            l_ts = [sum(p * q for p, q in zip(to_light, v)) for v in (t, b, n)]
            want = (math.cos(math.radians(el)) * math.cos(math.radians(az)),
                    math.cos(math.radians(el)) * math.sin(math.radians(az)), math.sin(math.radians(el)))
            self.assertTrue(close(l_ts, want, 2e-3), (az, el, l_ts, want))

    def test_top_face_frame_is_tangent_x_binormal_minus_y(self):
        t, b, n = reader.tangent_frame(scene.rotation_matrix(0, 0, 0))
        self.assertTrue(close(t, (1, 0, 0)) and close(b, (0, -1, 0)) and close(n, (0, 0, 1)))
        t, b, n = reader.tangent_frame(scene.rotation_matrix(0, 16384, 0))
        self.assertTrue(close(t, (0, 1, 0)) and close(b, (1, 0, 0)))


class SceneText(unittest.TestCase):
    SPEC = dict(light=dict(pitch=-8192, yaw=0, brightness=2.0, color=[255, 128, 64]),
                receivers=[dict(name='a', location=[0, 0, 0]), dict(name='b', location=[1600, 0, 0], yaw=8192)])

    def test_note_first_then_one_light_and_each_receiver(self):
        t3d, manifest = scene.build(self.SPEC)
        actors = [line.split()[2] for line in t3d.splitlines() if line.strip().startswith('Begin Actor')]
        self.assertEqual(actors, ['Class=Note', 'Class=DirectionalLight', 'Class=StaticMeshActor', 'Class=StaticMeshActor'])
        self.assertIn('Brightness=2.000000', t3d)
        self.assertIn('LightColor=(B=64,G=128,R=255,A=0)', t3d)
        self.assertIn('UseDirectLightMap=True', t3d)
        self.assertEqual(t3d.count(scene.MESH), 2)
        self.assertEqual([r['actor'] for r in manifest['receivers']], ['StaticMeshActor_901', 'StaticMeshActor_902'])
        self.assertTrue(close(manifest['light']['toLight'], (-R2, 0, R2)))
        self.assertTrue(close(manifest['receivers'][1]['axes'][0], (R2, R2, 0)))

    def test_light_lists_the_archetypes_components_in_their_order(self):
        t3d, _ = scene.build(self.SPEC)
        self.assertIn("Components(0)=SpriteComponent'SpriteComponent_900'", t3d)
        self.assertIn("Components(1)=DirectionalLightComponent'DirectionalLightComponent_900'", t3d)
        self.assertIn("Components(2)=ArrowComponent'ArrowComponent_900'", t3d)

    def test_more_lights_get_their_own_actors_and_directions(self):
        spec = dict(self.SPEC, moreLights=[dict(pitch=-10923, yaw=16384, brightness=1.5, color=[64, 128, 255])])
        t3d, manifest = scene.build(spec)
        self.assertIn('Begin Actor Class=DirectionalLight Name=DirectionalLight_891 ', t3d)
        self.assertEqual([lt['actor'] for lt in manifest['lights']], ['DirectionalLight_900', 'DirectionalLight_891'])
        self.assertTrue(close(manifest['lights'][1]['toLight'], (0, -0.5, math.sqrt(0.75)), 1e-4))
        self.assertEqual(manifest['light'], manifest['lights'][0])

    def test_duplicate_receiver_names_are_refused(self):
        spec = dict(self.SPEC, receivers=[dict(name='a', location=[0, 0, 0])] * 2)
        with self.assertRaises(ValueError):
            scene.build(spec)


class PointAndSpotLights(unittest.TestCase):
    SPEC = dict(pointLights=[dict(location=[0, 0, 256], radius=1024, falloffExponent=2)],
                spotLights=[dict(location=[0, 6000, 384], pitch=-12288, yaw=0, radius=1270, falloffExponent=4,
                                 innerConeAngle=20, outerConeAngle=44, brightness=8.0)],
                receivers=[dict(name='p', location=[0, 0, 0], scale=0.5, lightmapRes=512)])

    def test_point_light_lists_the_archetypes_components_in_their_order(self):
        t3d, manifest = scene.build(self.SPEC)
        self.assertIn("Begin Actor Class=PointLight Name=PointLight_880 Archetype=PointLight'Engine.Default__PointLight'",
                      t3d)
        block = t3d[t3d.index('Name=PointLight_880'):t3d.index('Name=SpotLight_870')]
        order = [line.split('=', 1)[1] for line in block.splitlines() if line.strip().startswith('Components(')]
        self.assertEqual(order, ["SpriteComponent'SpriteComponent_880'",
                                 "DrawLightRadiusComponent'DrawLightRadiusComponent_880'",
                                 "DrawLightRadiusComponent'DrawLightRadiusComponent_8801'",
                                 "PointLightComponent'PointLightComponent_880'"])
        self.assertIn('Radius=1024.000000', block)
        self.assertIn('FalloffExponent=2.000000', block)
        self.assertEqual(manifest['pointLights'][0]['actor'], 'PointLight_880')
        self.assertIsNone(manifest['light'])

    def test_spot_light_lists_seven_components_and_its_cone(self):
        t3d, manifest = scene.build(self.SPEC)
        block = t3d[t3d.index('Name=SpotLight_870'):]
        block = block[:block.index('End Actor')]
        order = [line.split('=', 1)[1].split("'")[0] for line in block.splitlines()
                 if line.strip().startswith('Components(')]
        self.assertEqual(order, ['SpriteComponent', 'DrawLightRadiusComponent', 'DrawLightConeComponent',
                                 'DrawLightConeComponent', 'DrawLightRadiusComponent', 'SpotLightComponent',
                                 'ArrowComponent'])
        for text in ('InnerConeAngle=20.000000', 'OuterConeAngle=44.000000', 'Brightness=8.000000',
                     'Rotation=(Pitch=-12288,Yaw=0,Roll=0)'):
            self.assertIn(text, block)
        # pitched 67.5 degrees down along +X
        self.assertTrue(close(manifest['spotLights'][0]['direction'],
                              (math.cos(math.radians(67.5)), 0, -math.sin(math.radians(67.5))), 1e-6))

    def test_object_names_are_unique(self):
        t3d, _ = scene.build(self.SPEC)
        names = [line.split('ObjName=')[1].split()[0] for line in t3d.splitlines() if 'ObjName=' in line]
        self.assertEqual(len(names), len(set(names)))

    def test_light_tangent_needs_a_directional_light(self):
        spec = dict(self.SPEC, receivers=[dict(name='p', location=[0, 0, 0], lightTangent=[90, 45])])
        with self.assertRaises(ValueError):
            scene.build(spec)


class ImportanceVolume(unittest.TestCase):
    SPEC = dict(PointAndSpotLights.SPEC, importanceVolume=dict(min=[-800, -800, -300], max=[1100, 2200, 1300]))

    def test_volume_is_a_box_brush_with_one_component(self):
        t3d, manifest = scene.build(self.SPEC)
        block = t3d[t3d.index('Begin Actor Class=LightmassImportanceVolume'):]
        block = block[:block.index('End Actor')]
        self.assertIn("Archetype=LightmassImportanceVolume'Engine.Default__LightmassImportanceVolume'", block)
        self.assertEqual([l.strip() for l in block.splitlines() if l.strip().startswith('Components(')],
                         ["Components(0)=BrushComponent'BrushComponent_860'"])
        self.assertIn('Location=(X=150.000000,Y=700.000000,Z=500.000000)', block)
        self.assertEqual(block.count('Begin Polygon'), 6)
        self.assertLess(block.index('Begin Brush Name=Model_860'), block.index('Begin Object Class=BrushComponent'))
        self.assertEqual(manifest['importanceVolume'], self.SPEC['importanceVolume'])
        # every polygon: four corners on its face, listed clockwise seen from outside (as the editor writes brushes)
        polys = block.split('Begin Polygon')[1:]
        for poly in polys:
            lines = [l.split() for l in poly.splitlines() if l.strip()]
            normal = [float(v) for v in next(l[1] for l in lines if l[0] == 'Normal').split(',')]
            verts = [[float(v) for v in l[1].split(',')] for l in lines if l[0] == 'Vertex']
            self.assertEqual(len(verts), 4)
            e1 = [verts[1][k] - verts[0][k] for k in range(3)]
            e2 = [verts[2][k] - verts[0][k] for k in range(3)]
            cross = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]
            self.assertLess(sum(c * n for c, n in zip(cross, normal)), 0)
            axis = max(range(3), key=lambda k: abs(normal[k]))
            half = [950, 1500, 800][axis]
            self.assertTrue(all(abs(v[axis] - normal[axis] * half) < 1e-6 for v in verts))

    def test_scene_without_volume_has_none(self):
        t3d, manifest = scene.build(PointAndSpotLights.SPEC)
        self.assertNotIn('LightmassImportanceVolume', t3d)
        self.assertIsNone(manifest['importanceVolume'])

    def test_empty_box_is_refused(self):
        with self.assertRaises(ValueError):
            scene.build(dict(self.SPEC, importanceVolume=dict(min=[0, 0, 0], max=[10, 0, 10])))


class TopFaceTexels(unittest.TestCase):
    def test_texel_centres_map_back_to_their_uvs(self):
        # an unturned receiver at scale 0.5 filling a 512 x 512 atlas
        lm = dict(coordinateScale=[1.0, 1.0], coordinateBias=[0.0, 0.0])
        rec = dict(location=[100.0, 200.0, 50.0], scale=0.5, axes=scene.rotation_matrix(0, 0, 0))
        px, py, world = reader.top_face_texels(lm, rec, [512, 512])
        (au, bu, _), (av, _, cv) = reader.TOP_UV_FROM_LOCAL
        u = au + bu * (world[:, 0] - 100.0) / 0.5
        v = av + cv * (world[:, 1] - 200.0) / 0.5
        self.assertTrue(abs(u - (px + 0.5) / 512).max() < 1e-9 and abs(v - (py + 0.5) / 512).max() < 1e-9)
        self.assertTrue((world[:, 2] == 50.0).all())
        # the face spans local x -2127..1969 and y -2015..2081 (here halved and offset), margins kept inside
        self.assertTrue(world[:, 0].min() > 100 - 1064 and world[:, 0].max() < 100 + 985)
        self.assertTrue(world[:, 1].min() > 200 - 1008 and world[:, 1].max() < 200 + 1041)
        self.assertGreater(len(px), 400 * 400)

    def test_uv_map_matches_the_template_floor(self):
        sys.path.insert(0, str(HERE.parents[1] / 'lab'))
        import labpaths
        path = labpaths.configured('udk', 'Engine', 'Content', 'MapTemplates.upk')
        if path is None or not path.exists():
            self.skipTest('UDK not installed here (the udk setting)')
        sys.path.insert(0, str(HERE.parents[1] / 'upk'))
        sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
        import audit_lighting
        from mesh import read_mesh
        p = audit_lighting.Package(path)
        m = read_mesh(p, p.by_name['SM_Template_Map_Floor'])
        pos, uv = m['positions'], m['uvs'][1]
        (au, bu, cu), (av, bv, cv) = reader.TOP_UV_FROM_LOCAL
        checked = 0
        for k in range(len(pos) // 3):
            x, z, y = pos[3 * k:3 * k + 3]   # read_mesh gives (x, z, y)
            u, v = uv[2 * k:2 * k + 2]
            if abs(z) < 1e-3 and u < 0.82 and v > 0.18:
                self.assertLess(abs(au + bu * x + cu * y - u), 5e-4)
                self.assertLess(abs(av + bv * x + cv * y - v), 5e-4)
                checked += 1
        self.assertEqual(checked, 100)


if __name__ == '__main__':
    unittest.main()
