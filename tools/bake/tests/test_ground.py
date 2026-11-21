"""Ground shapes made from numbers (ground.py; custom geometry plan, M6): a patch, a block, a ramp and a rock, their
faces (no bottom), world-planar texture coordinates, a plain mesh's sections, their collision (a box, a ramp's wedge,
a rock's hull) and the slope's words; bad numbers refused.

The free form (custom geometry improvements plan, section 10.2): old numbers build byte for byte as on the commit it
started from; free numbers give the box whole, any size (past 64 tiles, past 384 high, under a tile, off the tile
edges), each face's texture coordinates held near 0 in whole repeats, and a face too many repeats across for the half
floats refused with that reason."""
import math
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fixtures  # noqa: E402
import gen_mesh  # noqa: E402
import ground  # noqa: E402
from free_form import NumbersError  # noqa: E402

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

    def test_a_rock_with_moved_points_is_their_hull(self):
        # (look picker and rock points plan, R1, R2) its points as the seed gives them make the same rock; a corner moved
        # makes another, its hull's corners the points that stick out; a point pushed inside the others is no corner
        seeded, corners = ground.rock_corners(ROCK)
        self.assertEqual(len(seeded), ground.ROCK_POINTS)
        self.assertTrue(all(p[2] == 0.0 for p in seeded[:ground.ROCK_RING]))
        given = dict(ROCK, points=[list(p) for p in seeded])
        self.assertEqual(ground.corners_and_faces(given), ground.corners_and_faces(ROCK))
        self.assertEqual(ground.rock_corners(given), (seeded, corners))
        top = max(range(len(seeded)), key=lambda i: seeded[i][2])
        self.assertIn(top, corners)
        moved = [list(p) for p in seeded]
        moved[top] = [10.0, 10.0, 96.0]
        out, faces = ground.corners_and_faces(dict(ROCK, points=moved))
        self.assertIn((10.0, 10.0, 96.0), [tuple(round(v, 3) for v in c) for c in out])
        self.assertNotEqual(ground.mesh_name(dict(ROCK, points=moved)), ground.mesh_name(ROCK))
        inside = [list(p) for p in seeded]
        i = next(c for c in corners if c >= ground.ROCK_RING and c != top)
        inside[i] = [96.0, 48.0, 30.0]        # (the middle of the rock)
        self.assertNotIn(i, ground.rock_corners(dict(ROCK, points=inside))[1])
        self.assertTrue(gen_mesh.write(ground.build(dict(ROCK, points=moved))['mesh'], 0))
        # the rules: 24 points, inside the footprint and between 0 and the height, the ground ring on the ground
        for bad in (moved[:-1], moved + [moved[0]], [p[:2] for p in moved],
                    [[300.0, 10.0, 10.0]] + moved[1:], moved[:8] + [[50.0, 50.0, 120.0]] + moved[9:],
                    [[50.0, 50.0, 10.0]] + moved[1:], moved[:8] + [[50.0, 50.0, -5.0]] + moved[9:],
                    moved[:8] + [[50.0, True, 10.0]] + moved[9:]):
            with self.assertRaises(ValueError):
                ground.check(dict(ROCK, points=bad))
        with self.assertRaises(ValueError):
            ground.check(dict(BLOCK, points=moved))

    def test_bad_numbers_are_refused(self):
        for bad in (dict(PATCH, shape='dome'), dict(PATCH, x1=100.0), dict(PATCH, x1=96.0 * (ground.MAX_TILES + 1)), dict(BLOCK, height=0),
                    dict(BLOCK, height=500.0), dict(RAMP, height=True), dict(PATCH, look='marble'), None,
                    dict(ROCK, seed=None), dict(ROCK, seed=-1), dict(ROCK, seed=2 ** 31), dict(ROCK, seed=1.5),
                    dict(ROCK, seed=True)):
            with self.assertRaises(ValueError):
                ground.check(bad)


# old numbers of every shape (named looks, a look given whole with its planar map, a rock from its seed and one with
# moved points), each build's digest (fixtures.made_digest) recorded on the commit the free form started from
GIVEN = dict(mesh='Pkg.Group.Ground', material='Pkg.Mat', measure=1,
             recipe=dict(repeat=256.0, slot=1, sections=2, thickness=6.0, colours=dict(outside='11223344', interior='11223344'),
                         lightmap=dict(density=0.1, margin=2, interiorDensity=1.0, block=4),
                         uv=dict(top=[[0.0, 1 / 200.0, 0.3], [-1 / 250.0, 0.0, 0.7]])))
OLD = {
    'patch': (PATCH, 'd6d07d20b68b58ad8dc22902471f7420e136d57bd6e018b14afe2cc4eb8e1e78'),
    'patch-big': (dict(shape='patch', x0=-960.0, x1=5184.0, y0=96.0, y1=6240.0, look='grass'),
                  'f78bc58bc8946250d645311d62a65444a9e2af5cf2728a559016e680d25a449e'),
    'block': (dict(BLOCK, look='concrete'), '281a002fcf7f797945f6b1ad5d6c83fa5b7615a6f3e4e0dc63530922f5cad841'),
    'ramp': (RAMP, 'ec9336228289e2d6376f0a34dc15263e2edac17105abe2139a2d89b5dd270471'),
    'rock': (ROCK, '46da77dfeae2f3a33dff6db19865f1cc482d079b69d5b5645c57e8939f9adc9f'),
    'given-block': (dict(shape='block', x0=0.0, x1=384.0, y0=0.0, y1=288.0, height=384.0, look=GIVEN),
                    'f6c807c8d04bbf04bec23c05eafef9eee5ce8c318c784e019ca729dad2013bc1'),
}
MOVED_ROCK = '9b5b25c0f7d5695a84676c381a8d6d877be1e4565ed82865dadd0ef7be59cd58'


def half(v):
    return struct.unpack('<e', struct.pack('<e', v))[0]


def uvs_of(out):
    return [v[2][0] for v in out['mesh']['lods'][0]['vertices']]


class OldNumbers(unittest.TestCase):
    def test_they_build_byte_for_byte_as_before_the_free_form(self):
        for key, (shape, digest) in OLD.items():
            with self.subTest(key):
                self.assertEqual(fixtures.made_digest(ground.build(shape), ground.mesh_name(shape)), digest)
        pts, _ = ground.rock_corners(ROCK)
        moved = [list(p) for p in pts]
        top = max(range(len(moved)), key=lambda i: moved[i][2])
        moved[top] = [10.0, 10.0, 96.0]
        rock = dict(ROCK, points=moved)
        self.assertEqual(fixtures.made_digest(ground.build(rock), ground.mesh_name(rock)), MOVED_ROCK)


class FreeShapes(unittest.TestCase):
    def test_the_box_is_the_numbers(self):
        for shape, box in ((dict(shape='patch', free=1, x0=-10.5, x1=30.25, y0=7.0, y1=9.5, z0=-5.0, z1=3.0),
                            [-10.5, 30.25, 7.0, 9.5, -5.0, 3.0]),
                           (dict(shape='block', free=1, x0=0.0, x1=50.5, y0=0.0, y1=40.0, z0=10.0, z1=1000.0),
                            [0.0, 50.5, 0.0, 40.0, 10.0, 1000.0]),
                           (dict(shape='ramp', free=1, x0=0.0, x1=500.0, y0=0.0, y1=96.0, z0=-20.0, z1=600.0),
                            [0.0, 500.0, 0.0, 96.0, -20.0, 600.0])):
            with self.subTest(shape['shape']):
                out = ground.build(shape)
                self.assertTrue(gen_mesh.write(out['mesh'], 0))
                corners, _ = ground.corners_and_faces(shape)
                self.assertEqual([v for k in range(3) for v in (min(c[k] for c in corners), max(c[k] for c in corners))], box)
                self.assertEqual(ground.local_box(shape), box)
                self.assertEqual(ground.check_free(shape), box)
        # the ramp rises from z0 at x0 to z1 at x1; its slope says so
        ramp = dict(shape='ramp', free=1, x0=0.0, x1=500.0, y0=0.0, y1=96.0, z0=-20.0, z1=600.0)
        (wedge,) = ground.solids(ramp)
        self.assertEqual(wedge['ElemBox'][1], [500.0, 96.0, 600.0])
        self.assertAlmostEqual(ground.slope(ramp), math.degrees(math.atan2(620.0, 500.0)))
        self.assertIn('no floor', ground.slope_words(ramp))
        block = dict(shape='block', free=1, x0=0.0, x1=50.5, y0=0.0, y1=40.0, z0=10.0, z1=1000.0)
        self.assertEqual(ground.solids(block), [((0.0, 0.0, 10.0), (50.5, 40.0, 1000.0))])

    def test_past_64_tiles_and_past_384_high(self):
        patch = dict(shape='patch', free=1, x0=-100.0, x1=96.0 * 300 + 0.5, y0=0.0, y1=96.0 * 200, z0=-5.0, z1=3.0,
                     look='grass')
        out = ground.build(patch)
        self.assertTrue(gen_mesh.write(out['mesh'], 0))
        tall = dict(shape='block', free=1, x0=0.0, x1=96.0 * 80, y0=0.0, y1=96.0, z0=0.0, z1=5000.0)
        self.assertEqual(ground.local_box(tall)[5], 5000.0)
        self.assertTrue(gen_mesh.write(ground.build(tall)['mesh'], 0))
        ramp = dict(shape='ramp', free=1, x0=0.0, x1=96.0 * 100, y0=0.0, y1=96.0 * 70, z0=0.0, z1=1000.0)
        self.assertTrue(gen_mesh.write(ground.build(ramp)['mesh'], 0))

    def test_the_texture_is_held_near_0_and_in_phase(self):
        patch = dict(shape='patch', free=1, x0=12005.0, x1=13000.0, y0=-9000.0, y1=-8000.7, z0=-5.0, z1=3.0, look='grass')
        rep = ground.look_of(patch)['repeat']
        out = ground.build(patch)
        lod = out['mesh']['lods'][0]
        tops = 0
        for p, (_, n, (uv, _lm)) in zip(lod['positions'], lod['vertices']):
            self.assertLess(max(abs(uv[0]), abs(uv[1])), 4.0)
            if n[2] > 250:
                tops += 1
                for got, want in ((uv[0], p[0] / rep), (uv[1], p[1] / rep)):
                    # the same place in the pattern, to the half float's step near 2 (1/512)
                    self.assertLess(abs(((got - want) + 0.5) % 1.0 - 0.5), 1 / 512)
        self.assertEqual(tops, 4)
        # the old numbers' coordinates were the places themselves, which half floats round past 32 repeats
        self.assertGreater(abs(half(12005.0 / rep) - 12005.0 / rep), 1 / 128)

    def test_a_face_too_many_repeats_across_is_refused_with_its_reason(self):
        rep = ground.look_of(dict(shape='patch', look='sidewalk'))['repeat']       # 192
        fits = dict(shape='patch', free=1, x0=0.0, x1=rep * 2040, y0=0.0, y1=96.0, z0=-5.0, z1=3.0, look='sidewalk')
        self.assertTrue(gen_mesh.write(ground.build(fits)['mesh'], 0))
        for shape in (dict(fits, x1=rep * 2060), dict(shape='block', free=1, x0=0.0, x1=96.0, y0=0.0, y1=96.0, z0=0.0,
                                                       z1=rep * 2060, look='sidewalk')):
            with self.assertRaises(NumbersError) as e:
                ground.build(shape)
            self.assertEqual(e.exception.code, 'half-floats')
            self.assertIn('half floats', str(e.exception))

    def test_a_free_rock_stands_on_its_bottom_within_its_box(self):
        rock = dict(shape='rock', free=1, x0=10.0, x1=60.5, y0=-30.0, y1=0.0, z0=5.0, z1=700.0, seed=3)
        pts, corners = ground.rock_corners(rock)
        self.assertTrue(all(abs(p[2] - 5.0) < 1e-9 for p in pts[:ground.ROCK_RING]))
        self.assertEqual(max(p[2] for p in pts), 700.0)
        self.assertTrue(all(10.0 <= p[0] <= 60.5 and -30.0 <= p[1] <= 0.0 for p in pts))
        out = ground.build(rock)
        self.assertTrue(gen_mesh.write(out['mesh'], 0))
        self.assertEqual(ground.local_box(rock), [10.0, 60.5, -30.0, 0.0, 5.0, 700.0])
        moved = [list(p) for p in pts]
        moved[corners[-1]] = [11.0, -29.0, 650.0]
        self.assertTrue(gen_mesh.write(ground.build(dict(rock, points=moved))['mesh'], 0))
        for bad in ([[p[0], p[1], 0.0] for p in moved],                                 # its ring under its bottom
                    moved[:-1] + [[11.0, -29.0, 701.0]], moved[:-1] + [[70.0, -29.0, 300.0]]):
            with self.assertRaises(ValueError):
                ground.check(dict(rock, points=bad))

    def test_plain_is_taken_and_not_read_and_a_mapping_changes_the_texture_alone(self):
        # (the mapping's own checks: test_texture_mapping.py)
        patch = dict(shape='patch', free=1, x0=0.0, x1=200.0, y0=0.0, y1=100.0, z0=-5.0, z1=3.0)
        a = ground.build(patch)['mesh']['lods'][0]
        b = ground.build(dict(patch, plain=True))['mesh']['lods'][0]
        for key in ('positions', 'vertices', 'indices', 'colours'):
            self.assertEqual(a[key], b[key], key)
        mapped = dict(patch, plain=True, mapping=dict(surfaces=dict(top=dict(mode='fit', u=1, v=1))))
        b = ground.build(mapped)['mesh']['lods'][0]
        for key in ('positions', 'indices', 'colours'):
            self.assertEqual(a[key], b[key], key)
        self.assertEqual([v[2][1] for v in a['vertices']], [v[2][1] for v in b['vertices']])
        self.assertNotEqual([v[2][0] for v in a['vertices']], [v[2][0] for v in b['vertices']])
        self.assertNotEqual(ground.mesh_name(mapped), ground.mesh_name(patch))

    def test_bad_free_numbers_are_refused(self):
        good = dict(shape='block', free=1, x0=0.0, x1=50.0, y0=0.0, y1=40.0, z0=0.0, z1=10.0)
        ground.check(good)
        for change, code in ((dict(x1=0.0), 'extent'), (dict(z1=-1.0), 'extent'), (dict(y0=math.inf), 'number'),
                             (dict(z0=None), 'number'), (dict(free=3), 'free'), (dict(mapping=5), 'mapping'),
                             (dict(points=[[0.0, 0.0, 0.0]] * 24), 'points')):
            with self.assertRaises(NumbersError) as e:
                ground.check(dict(good, **change))
            self.assertEqual(e.exception.code, code, change)
        for bad in (dict(good, shape='dome'), dict(good, look='marble'), dict(good, shape='rock')):     # (no seed)
            with self.assertRaises(ValueError):
                ground.check(bad)
        with self.assertRaises(NumbersError) as e:
            ground.check_free(BLOCK)
        self.assertEqual(e.exception.code, 'free')


if __name__ == '__main__':
    unittest.main()
