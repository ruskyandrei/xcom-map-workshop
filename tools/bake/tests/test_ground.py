"""Ground shapes made from numbers (ground.py; custom geometry plan, M6): a patch, a block and a ramp, their faces
(no bottom), world-planar texture coordinates, a plain mesh's sections, their collision (a box, a ramp's wedge) and
the slope's words; bad numbers refused."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import gen_mesh  # noqa: E402
import ground  # noqa: E402

PATCH = dict(shape='patch', x0=0.0, x1=192.0, y0=0.0, y1=96.0)
BLOCK = dict(shape='block', x0=0.0, x1=96.0, y0=0.0, y1=192.0, height=64.0)
RAMP = dict(shape='ramp', x0=0.0, x1=288.0, y0=0.0, y1=96.0, height=96.0)


class Ground(unittest.TestCase):
    def test_each_shape_is_a_plain_mesh_without_a_bottom(self):
        for shape, faces in ((PATCH, 5), (BLOCK, 5), (RAMP, 4)):
            out = ground.build(shape)
            m = out['mesh']
            self.assertIsNone(m['fractured'])
            lod = m['lods'][0]
            self.assertEqual([s['slot'] for s in lod['sections']], [0])
            self.assertEqual(lod['sections'][0]['fragments'], [])
            self.assertEqual(out['counts']['charts'], faces)
            # no face looks down
            self.assertTrue(all(poly['normal'][2] > -0.5 for poly in ground.faces_of(shape).polys), shape)
            self.assertTrue(gen_mesh.write(m, 0))
            box = ground.local_box(shape)
            self.assertEqual(box[:4], [shape['x0'], shape['x1'], shape['y0'], shape['y1']])

    def test_the_top_repeats_the_material_by_the_world(self):
        out = ground.build(BLOCK)
        lod = out['mesh']['lods'][0]
        rep = ground.look_of(BLOCK)['repeat']
        for p, (_, normal, uvs) in zip(lod['positions'], lod['vertices']):
            if normal[2] > 200:        # the top's (its normal up)
                self.assertAlmostEqual(uvs[0][0], p[0] / rep, 2)
                self.assertAlmostEqual(uvs[0][1], p[1] / rep, 2)

    def test_heights_and_collision(self):
        self.assertEqual(ground.local_box(PATCH)[4:], [-ground.look_of(PATCH)['thickness'], 0.0])
        self.assertEqual(ground.local_box(BLOCK)[4:], [0.0, 64.0])
        self.assertEqual(ground.solids(BLOCK), [((0.0, 0.0, 0.0), (96.0, 192.0, 64.0))])
        (wedge,) = ground.solids(RAMP)
        self.assertEqual(len(wedge['FacePlaneData']), 5)
        self.assertEqual(wedge['ElemBox'][1], [288.0, 96.0, 96.0])

    def test_the_slope_in_words(self):
        self.assertEqual(ground.slope_words(BLOCK), '')
        self.assertIn('gives cover', ground.slope_words(dict(RAMP, x1=960.0, height=96.0)))      # under 10 degrees
        self.assertIn('no cover', ground.slope_words(RAMP))                                       # 18 degrees
        self.assertIn('no floor', ground.slope_words(dict(RAMP, x1=96.0, height=192.0)))         # 63 degrees

    def test_bad_numbers_are_refused(self):
        for bad in (dict(PATCH, shape='dome'), dict(PATCH, x1=100.0), dict(PATCH, x1=96.0 * 17), dict(BLOCK, height=0),
                    dict(BLOCK, height=500.0), dict(RAMP, height=True), dict(PATCH, look='marble'), None):
            with self.assertRaises(ValueError):
                ground.check(bad)


if __name__ == '__main__':
    unittest.main()
