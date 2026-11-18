"""Ground looks from any donor (ground_measure.py, ground.py; custom geometry plan, M4 work order B step 3): a shape made
in a measured recipe and measured again gives the recipe back, and the twin check; on the install, today's seven looks'
donors measure as their looks were written, a painted donor is made in its commonest colour (D14), a masked overlay
is left out (D14), and a donor placed at scale 2 gives the repeat its placing draws, its copy standing at scale 1 in a
Build."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
for folder in ('viewer', 'upk', 'lab'):
    sys.path.insert(0, str(HERE.parents[1] / folder))
sys.path.insert(0, str(HERE.parent))
import gen_mesh  # noqa: E402
import ground  # noqa: E402
import ground_measure  # noqa: E402
import labpaths  # noqa: E402
import measure_common as mc  # noqa: E402

# a measured recipe: the material in slot 1 of 3, its top turned a quarter (u along y), two repeats, a painted colour
RECIPE = dict(material='Pkg.Materials.Some_Mud', slot=1, sections=3,
              uv=dict(top=[[0.0, 0.0025, 0.25], [-0.004, 0.0, 0.5]]), repeat=400.0, thickness=6.0,
              colours=dict(outside='ff802000', interior='ff802000'),
              lightmap=dict(density=0.1, margin=2, interiorDensity=1.0, block=4),
              measured=dict(size=[384.0, 192.0, 6.0], scale=[1.0, 1.0, 1.0], shape='flat'))
PIER, NO_PIER = labpaths.install_map('URB_PierA_Terror')


def look(recipe=RECIPE):
    return dict(mesh='Pkg.Meshes.Some_Plane', material=recipe['material'], measure=1, recipe=recipe)


class MadeAndMeasured(unittest.TestCase):
    PATCH = dict(shape='patch', x0=0.0, x1=384.0, y0=0.0, y1=192.0)

    def test_the_recipe_comes_back(self):
        out = ground.build(dict(self.PATCH, look=look()))
        lod = out['mesh']['lods'][0]
        self.assertEqual([s['slot'] for s in lod['sections']], [0, 1, 2])
        self.assertEqual([s['triangles'] > 0 for s in lod['sections']], [False, True, False])
        got = ground_measure.measure_mesh(out['mesh'], 1, light=dict(type=2, rect=out['lightmapRect']),
                                          name=RECIPE['material'])['recipe']
        self.assertEqual((got['slot'], got['sections'], got['thickness'], got['colours']), (1, 3, 6.0, RECIPE['colours']))
        self.assertFalse(mc.map_differs(got['uv']['top'], RECIPE['uv']['top']), got['uv']['top'])

    def test_the_sides_take_the_tops_repeats(self):
        out = ground.build(dict(shape='block', x0=0.0, x1=96.0, y0=0.0, y1=96.0, height=200.0, look=look()))
        lod = out['mesh']['lods'][0]
        for p, (_, n, uvs) in zip(lod['positions'], lod['vertices']):
            if abs(n[2] - 127.5) < 5:            # a side: v down it at the top's v repeat (250)
                self.assertAlmostEqual(uvs[0][1], -p[2] / 250.0, 2)

    def test_the_twin_check_passes(self):
        result = ground_measure.twin(RECIPE)
        self.assertTrue(result['ok'], ground_measure.verdict(result))
        self.assertEqual(result['built'], dict(shape='patch', x0=0.0, x1=384.0, y0=0.0, y1=192.0))

    def test_a_given_look_is_named_by_the_look_not_its_spelling(self):
        shape = dict(self.PATCH, look=look())
        reordered = json.loads(json.dumps(RECIPE, sort_keys=True))
        self.assertEqual(ground.mesh_name(dict(self.PATCH, look=look(reordered))), ground.mesh_name(shape))
        self.assertNotEqual(ground.mesh_name(dict(self.PATCH, look=look(dict(RECIPE, thickness=4.0)))),
                            ground.mesh_name(shape))
        with self.assertRaises(ValueError):
            ground.check(dict(self.PATCH, look=dict(mesh='Pkg.M', material='Pkg.X', measure=1)))

    def test_a_given_look_keeps_its_colour_over_the_templates(self):
        template = ground.default_template()
        out = ground.build(dict(self.PATCH, look=look()), template)
        self.assertEqual({bytes(c) for c in out['mesh']['lods'][0]['colours']}, {bytes.fromhex('ff802000')})
        out = ground.build(dict(self.PATCH, look=look()), template, colour=bytes.fromhex('00ff00ff'))
        self.assertEqual({bytes(c) for c in out['mesh']['lods'][0]['colours']}, {bytes.fromhex('00ff00ff')})


class TodaysDonors(unittest.TestCase):
    """The seven looks' donors (ground_looks.json), each from its map (skipped where the install lacks it)."""

    def test_they_measure_as_their_looks_were_written(self):
        from package import Package
        seen = 0
        for name, info in ground.LOOKS.items():
            path, _ = labpaths.install_map(info['package'])
            if not (path and path.exists()):
                continue
            p = Package(path)
            entry = ground_measure.measure(p, info['actor'], info['material'])
            R, facts = entry['recipe'], entry['facts']
            self.assertEqual(facts['mesh'], info['donor'])
            self.assertIsNone(facts['leftOut'], name)
            self.assertEqual((R['slot'], R['sections']), (info['recipe']['slot'], info['recipe']['sections']), name)
            if name != 'rock':          # (the rock's texture is laid out piece by piece: one even repeat, warned)
                self.assertLess(abs(R['repeat'] - info['recipe']['repeat']) / info['recipe']['repeat'], 0.01, name)
            _, _, mesh = mc.find_placing(p, info['actor'], ground_measure.PLAIN, 'StaticMeshComponent')
            result = ground_measure.twin(R, gen_mesh.read(p, mesh))
            self.assertTrue(result['ok'], (name, ground_measure.verdict(result)))
            self.assertEqual(entry, ground_measure.measure(p, info['actor'], info['material']))
            seen += 1
        if not seen:
            self.skipTest('no map of the seven looks in the install')

    def test_a_painted_donor_is_made_in_its_commonest_colour(self):
        from package import Package
        path, why = labpaths.install_map('URB_Bar')
        if not (path and path.exists()):
            self.skipTest(why)
        entry = ground_measure.measure(Package(path), 'XComLevelActor_131')
        self.assertTrue(entry['facts']['painted'])
        self.assertEqual(entry['recipe']['colours']['outside'], 'ffffffff')      # (34 of the plane's 121)
        self.assertTrue(any('painted colours' in w and 'ffffffff' in w for w in entry['warnings']), entry['warnings'])


@unittest.skipUnless(PIER and PIER.exists(), NO_PIER)
class PierDonors(unittest.TestCase):
    """URB_PierA_Terror: a road plane placed at scale 2 (XComLevelActor_140) and a masked rubble overlay
    (XComLevelActor_345)."""
    SCALED, MASKED = 'XComLevelActor_140', 'XComLevelActor_345'

    @classmethod
    def setUpClass(cls):
        from package import Package
        cls.p = Package(PIER)
        cls.scaled = ground_measure.measure(cls.p, cls.SCALED)

    def test_a_masked_overlay_is_left_out(self):
        entry = ground_measure.measure(self.p, self.MASKED)
        self.assertTrue(entry['facts']['leftOut'])
        self.assertTrue(entry['warnings'][0].startswith('left out of the ground looks: masked'), entry['warnings'])

    def test_a_scaled_donor_gives_the_repeat_its_placing_draws(self):
        R = self.scaled['recipe']
        self.assertEqual(R['measured']['scale'], [2.0, 2.0, 2.0])
        _, comp, mesh = mc.find_placing(self.p, self.SCALED, ground_measure.PLAIN, 'StaticMeshComponent')
        unscaled = ground_measure.measure_mesh(gen_mesh.read(self.p, mesh), R['slot'], name=R['material'])['recipe']
        self.assertAlmostEqual(R['repeat'], 2 * unscaled['repeat'], 0)
        self.assertIsNone(self.scaled['facts']['leftOut'])

    def test_its_copy_stands_at_scale_1_in_a_build(self):
        import native_copy
        from package import Package
        R = self.scaled['recipe']
        shape = dict(shape='block', x0=0.0, x1=192.0, y0=0.0, y1=96.0, height=64.0,
                     look=dict(mesh=self.scaled['facts']['mesh'], material=R['material'], measure=1, recipe=R))
        with tempfile.TemporaryDirectory() as tmp:
            m = native_copy.build(PIER, Path(tmp), 'Scaled', [dict(
                actor=self.SCALED, label='Block', location=[0.0, 0.0, 0.0], rotation=[0, 0, 0],
                generated=dict(kind='ground', version=1, ground=shape))], bake=False)
            q = Package(Path(tmp) / 'Scaled.upk')
            actor = {c['label']: c['export'] for c in m['nativeCopies']['copies']}['Block']
            comp = q.own(actor, 'StaticMeshComponent')
            self.assertEqual(mc.scale_of(q, actor, comp), [1.0, 1.0, 1.0])
            rec = {r['label']: r for r in m['nativeCopies']['generatedWalls']}['Block']
            self.assertEqual([round(v, 2) for v in rec['box']], [0.0, 192.0, 0.0, 96.0, 0.0, 64.0])
            built = gen_mesh.read(q, q.own(comp, 'StaticMesh'))
            lod = built['lods'][0]
            top = R['uv']['top']
            for p, (_, n, uvs) in zip(lod['positions'], lod['vertices']):
                if n[2] > 250:
                    self.assertAlmostEqual(uvs[0][0], top[0][0] * p[0] + top[0][1] * p[1] + top[0][2], 2)


if __name__ == '__main__':
    unittest.main()
