"""Ground shapes made from numbers (ground.py; custom geometry plan, M6): a patch, a block, a ramp and a rock, their
faces (no bottom), world-planar texture coordinates, a plain mesh's sections, their collision (a box, a ramp's wedge,
a rock's hull) and the slope's words; bad numbers refused."""
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
ROCK = dict(shape='rock', x0=0.0, x1=192.0, y0=0.0, y1=96.0, height=96.0, seed=7)


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
        # (F-137) a patch's top 3 over the ground: the blank map's floor planes are drawn 2 over their collision
        self.assertEqual(ground.local_box(PATCH)[4:], [3.0 - ground.look_of(PATCH)['thickness'], 3.0])
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

    def test_a_rock_is_its_seeds_hull_within_its_footprint(self):
        import math
        corners, faces = ground.corners_and_faces(ROCK)
        lo = [min(c[k] for c in corners) for k in range(3)]
        hi = [max(c[k] for c in corners) for k in range(3)]
        self.assertTrue(lo[0] >= 0 and lo[1] >= 0 and hi[0] <= 192 and hi[1] <= 96, (lo, hi))
        self.assertEqual((lo[2], round(hi[2], 3)), (0.0, 96.0))       # standing on the ground, reaching its height
        # every face faces out (the solid's middle behind it), the bottom (flat, facing down) last and left out
        mid = [sum(c[k] for c in corners) / len(corners) for k in range(3)]
        for loop in faces:
            pts = [corners[i] for i in loop]
            n = ground._normal(pts)
            centre = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
            self.assertGreater(sum(n[k] * (centre[k] - mid[k]) for k in range(3)), 0)
        self.assertAlmostEqual(ground._normal([corners[i] for i in faces[-1]])[2], -1.0, 6)
        # its collision is the same hull: a face for each of the mesh's, the bottom too
        (hull,) = ground.solids(ROCK)
        self.assertEqual(len(hull['FacePlaneData']), len(faces))
        out = ground.build(ROCK)
        self.assertEqual(out['counts']['charts'], len([f for f in ground.faces_of(ROCK).polys]))
        self.assertTrue(gen_mesh.write(out['mesh'], 0))
        # the same seed the same rock, another seed another; its faces tilt every way
        self.assertEqual(ground.corners_and_faces(dict(ROCK)), (corners, faces))
        self.assertNotEqual(ground.corners_and_faces(dict(ROCK, seed=8))[0], corners)
        tilts = [math.degrees(math.acos(max(-1.0, min(1.0, ground._normal([corners[i] for i in f])[2])))) for f in faces[:-1]]
        self.assertTrue(min(tilts) < 45 < max(tilts))
        self.assertNotEqual(ground.mesh_name(ROCK), ground.mesh_name(dict(ROCK, seed=8)))

    def test_bad_numbers_are_refused(self):
        for bad in (dict(PATCH, shape='dome'), dict(PATCH, x1=100.0), dict(PATCH, x1=96.0 * 17), dict(BLOCK, height=0),
                    dict(BLOCK, height=500.0), dict(RAMP, height=True), dict(PATCH, look='marble'), None,
                    dict(ROCK, seed=None), dict(ROCK, seed=-1), dict(ROCK, seed=2 ** 31), dict(ROCK, seed=1.5),
                    dict(ROCK, seed=True)):
            with self.assertRaises(ValueError):
                ground.check(bad)


if __name__ == '__main__':
    unittest.main()
