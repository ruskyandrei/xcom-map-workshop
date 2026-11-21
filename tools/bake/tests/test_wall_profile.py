"""A made wall's outline in the free form (wall_profile.py; custom geometry improvements plan, stage 2): the Bar look
written as a measured look, faces moved with the trims kept proud, a height put into or taken out of the longest
upright stretch (else scaled), the outline raised with its texture, and a band of a tall stretched wall."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import frac_wall  # noqa: E402
import looks  # noqa: E402
import wall_profile  # noqa: E402

BAR = frac_wall.RECIPE
ABDUCTOR = dict(mesh='AbductorExtWall.Meshes.AbductorExtWallA_FRACTURED', measure=1)


def corners(R, X='A'):
    return [tuple(round(v, 6) for v in c) for c in R['profile'][X]]


class AsMeasured(unittest.TestCase):
    """The Bar look's recipe in the measured form: the same outline both sides, the faces and trims textured as the
    first path textures them."""
    R = wall_profile.as_measured(BAR)

    def test_its_outline_and_slots_are_the_bars(self):
        self.assertTrue(frac_wall.general(self.R))
        self.assertEqual(corners(self.R), [(y, z) for y, z, _ in BAR['section']])
        self.assertEqual(self.R['profile']['A'], self.R['profile']['B'])
        self.assertEqual([s['face'] for s in self.R['strips']['A']], [False, False, False, True, False, False])
        self.assertEqual(self.R['splits'], dict(A=[192.0], B=[192.0]))
        self.assertEqual(sorted(self.R['faceUV']), ['0A', '1A', '2B', '3B'])
        self.assertEqual(frac_wall.extent(self.R), frac_wall.extent(BAR))
        self.assertEqual((self.R['bottom'], self.R['top'], self.R['half'], self.R['endInset']), (-16.0, 384.0, 8.0, 8.0))
        self.assertEqual(self.R['collisionY'], [-8.0, 8.0])

    def test_its_textures_are_the_first_paths(self):
        P = frac_wall.Profile(self.R)
        for X, side in (('A', 1), ('B', -1)):
            # the faces: u = side x / 192 + 0.5, v = faceV - z / 192, the slot by storey
            for z, k in ((100.0, 0), (300.0, 1)):
                slot, tex = P.surface(X, 3, z)
                self.assertEqual(slot, BAR['slots']['side' + X][k])
                u, v = tex(50.0, z, 0.5)
                self.assertAlmostEqual(u, side * 50.0 / 192 + BAR['faceU'])
                self.assertAlmostEqual(v, BAR['faceV'][0 if X == 'A' else 1] - z / 192)
            # a trim: u = -side x / 96 - side trimU, v the section's v up it
            slot, tex = P.surface(X, 1, 5.0)
            (_, _, va), (_, _, vb) = BAR['section'][1], BAR['section'][2]
            self.assertEqual(slot, BAR['slots']['trim'])
            u, v = tex(50.0, 5.0, 0.25)
            self.assertAlmostEqual(u, -side * 50.0 / 96 - side * BAR['trimU'])
            self.assertAlmostEqual(v, va + 0.25 * (vb - va))
        slot, tex = P.cap(True)
        self.assertEqual((slot, tex(96.0, 4.0)), (BAR['slots']['trim'], (-1.0, BAR['topV'][0] + 4.0 * BAR['topV'][1])))


class Thickened(unittest.TestCase):
    def test_the_faces_move_and_the_trims_stay_proud_of_them(self):
        R = wall_profile.thickened(wall_profile.as_measured(BAR), -20.0, 5.0)
        self.assertEqual([y for y, _ in R['profile']['A']], [8.0, 8.0, 7.0, 5.0, 5.0, 9.0, 9.0])
        self.assertEqual([y for y, _ in R['profile']['B']], [23.0, 23.0, 22.0, 20.0, 20.0, 24.0, 24.0])
        self.assertEqual(frac_wall.extent(R), (-24.0, 9.0))
        self.assertEqual((R['half'], R['collisionY'], R['collisionHalf']), (12.5, [-20.0, 5.0], 12.5))
        self.assertEqual([z for _, z in R['profile']['A']], [z for _, z, _ in BAR['section']])
        # the look's own faces leave it as it is
        same = wall_profile.as_measured(BAR)
        self.assertIs(wall_profile.thickened(same, -8.0, 8.0), same)

    def test_faces_that_cross_the_outline_are_refused(self):
        # the UFO wall's side B reaches in past its centre line: made 2 thick, its outline would cross itself
        look = looks.resolve('wall', ABDUCTOR)['recipe']
        with self.assertRaisesRegex(ValueError, 'thick at'):
            wall_profile.thickened(look, -1.0, 1.0)
        least, _ = wall_profile.thinnest(wall_profile.thickened(look, -14.0, 14.0))
        self.assertGreaterEqual(least, wall_profile.THINNEST)


class Heightened(unittest.TestCase):
    R = wall_profile.as_measured(BAR)

    def test_a_taller_wall_lengthens_its_longest_upright_stretch(self):
        R = wall_profile.heightened(self.R, -16.0, 500.0)
        # the face (12 to 372 on both sides) takes the 116, at its top: the cornice keeps its 12, the skirting its 28
        self.assertEqual([z for _, z in R['profile']['A']], [-16.0, 0.0, 9.0, 12.0, 488.0, 490.0, 500.0])
        self.assertEqual((R['bottom'], R['top'], R['splits']['A']), (-16.0, 500.0, [192.0]))
        self.assertEqual(R['strips'], self.R['strips'])

    def test_a_lower_wall_shortens_it(self):
        R = wall_profile.heightened(self.R, -16.0, 300.0)
        self.assertEqual([z for _, z in R['profile']['B']], [-16.0, 0.0, 9.0, 12.0, 288.0, 290.0, 300.0])
        # one storey, the first path's one-storey wall's outline
        R = wall_profile.heightened(self.R, -16.0, 192.0)
        self.assertEqual([z for _, z in R['profile']['A']], [z for _, z, _ in frac_wall.shaped(dict(storeys=1))['section']])

    def test_a_raised_wall_keeps_its_pattern_on_it(self):
        R = wall_profile.heightened(self.R, 100.0, 500.0)
        self.assertEqual([z for _, z in R['profile']['A']], [z + 116.0 for _, z, _ in BAR['section']])
        self.assertEqual(R['uvShiftZ'], -116.0)
        low, high = frac_wall.Profile(self.R), frac_wall.Profile(R)
        _, tex = low.surface('A', 3, 200.0)
        _, tex2 = high.surface('A', 3, 316.0)
        self.assertEqual(tex2(37.0, 316.0, 0.0), tex(37.0, 200.0, 0.0))

    def test_where_no_stretch_takes_it_every_height_is_scaled(self):
        # an outline sloping all the way up on one side: no upright stretch on both sides
        R = dict(measure=1, bottom=0.0, top=100.0, profile=dict(A=[[8.0, 0.0], [12.0, 100.0]], B=[[8.0, 0.0], [8.0, 100.0]]),
                 strips=dict(A=[dict(slot=0, face=False, uv=[[1.0, 2.0, 3.0], [0.0, 1.0, 0.0]])],
                             B=[dict(slot=0, face=True, uv=None)]), splits=dict(A=[50.0], B=[]))
        self.assertIsNone(wall_profile.storey_cut(R, -50.0))
        out = wall_profile.heightened(R, 0.0, 150.0)
        self.assertEqual((corners(out), out['splits']['A'], out['top']), ([(8.0, 0.0), (12.0, 150.0)], [75.0], 150.0))
        self.assertEqual(out['strips'], R['strips'])
        # the Bar's 400 down to 30 would eat its bands: scaled
        out = wall_profile.heightened(self.R, -16.0, 14.0)
        self.assertEqual(corners(out)[-1], (12.0, 14.0))
        self.assertAlmostEqual(out['profile']['A'][3][1], -16.0 + 28.0 * 30.0 / 400.0)

    def test_storey_cut_takes_height_in_too(self):
        cut = wall_profile.storey_cut(self.R, -100.0)
        self.assertEqual((cut['lo'], cut['hi'], cut['segments']), (472.0, 372.0, dict(A=3, B=3)))
        self.assertIsNone(wall_profile.storey_cut(self.R, 360.0))
        self.assertEqual(wall_profile.storey_cut(self.R, 192.0)['lo'], 180.0)


class Windowed(unittest.TestCase):
    TALL = wall_profile.heightened(wall_profile.as_measured(BAR), -16.0, 1184.0)

    def test_a_band_is_the_outline_between_its_heights(self):
        middle = wall_profile.windowed(self.TALL, 384.0, 784.0)
        self.assertEqual(corners(middle), [(8.0, 384.0), (8.0, 784.0)])
        self.assertEqual(([s['face'] for s in middle['strips']['A']], middle['splits']['A']), ([True], []))
        self.assertEqual((middle['bottom'], middle['top']), (384.0, 784.0))
        bottom = wall_profile.windowed(self.TALL, -16.0, 384.0)
        self.assertEqual(corners(bottom), [(11.0, -16.0), (11.0, 0.0), (10.0, 9.0), (8.0, 12.0), (8.0, 384.0)])
        self.assertEqual(bottom['splits']['A'], [192.0])
        top = wall_profile.windowed(self.TALL, 784.0, 1184.0)
        self.assertEqual(corners(top), [(8.0, 784.0), (8.0, 1172.0), (12.0, 1174.0), (12.0, 1184.0)])
        self.assertIs(wall_profile.windowed(self.TALL, -16.0, 1184.0), self.TALL)

    def test_a_cut_strip_goes_on_as_it_did(self):
        # a band starting half way up the skirting's slope: that strip's texture at a height is the whole's
        whole, part = frac_wall.Profile(self.TALL), frac_wall.Profile(wall_profile.windowed(self.TALL, 4.0, 600.0))
        self.assertEqual(corners(part.R)[0], (round(10.0 + 5.0 / 9.0, 6), 4.0))
        for z in (5.0, 8.0):
            _, tex = whole.surface('A', 1, z)
            _, tex2 = part.surface('A', 0, z)
            a, b = tex(30.0, z, (z - 0.0) / 9.0), tex2(30.0, z, (z - 4.0) / 5.0)
            self.assertAlmostEqual(a[0], b[0])
            self.assertAlmostEqual(a[1], b[1])

    def test_the_free_shape_puts_them_together(self):
        R = wall_profile.free_shape(BAR, -10.0, 6.0, -16.0, 1184.0, [384.0, 784.0])
        self.assertEqual(corners(R), [(6.0, 384.0), (6.0, 784.0)])
        self.assertEqual(corners(R, 'B'), [(10.0, 384.0), (10.0, 784.0)])


if __name__ == '__main__':
    unittest.main()
