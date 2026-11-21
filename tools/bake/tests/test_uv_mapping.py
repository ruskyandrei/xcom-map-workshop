"""A made piece's texture mapping (tools/bake/uv_mapping.py; the custom geometry improvements plan, section 5): each
mode, the turn, the flips, the offsets and world alignment at sample points, and the half-float rebase."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uv_mapping  # noqa: E402


def close(test, got, want):
    test.assertEqual(len(got), len(want))
    for g, w in zip(got, want):
        test.assertAlmostEqual(g, w, places=9)


class MappingTests(unittest.TestCase):
    EXTENT = (0.0, 384.0, -16.0, 368.0)     # a wall's face, 384 along and 384 up from -16

    def test_size_keeps_the_repeat_s_size(self):
        s = dict(mode='size', u=96.0, v=96.0)
        close(self, uv_mapping.uv(s, 96.0, 48.0, self.EXTENT), (1.0, 0.5))
        # a longer wall: the same place, the same coordinates (bricks keep their size)
        close(self, uv_mapping.uv(s, 96.0, 48.0, (0.0, 768.0, -16.0, 368.0)), (1.0, 0.5))

    def test_count_and_fit_follow_the_size(self):
        count = dict(mode='count', u=3.0, v=1.5)
        close(self, uv_mapping.uv(count, 384.0, 368.0, self.EXTENT), (3.0, 1.5))
        close(self, uv_mapping.uv(count, 768.0, 368.0, (0.0, 768.0, -16.0, 368.0)), (3.0, 1.5))      # three stay three
        fit = dict(mode='fit', u=7.0, v=7.0)                                                        # (u, v read as 1)
        close(self, uv_mapping.uv(fit, 192.0, 176.0, self.EXTENT), (0.5, 0.5))

    def test_tile_along_and_fit_up(self):
        s = dict(mode='size', modeV='fit', u=64.0, v=1.0)
        close(self, uv_mapping.uv(s, 128.0, 368.0, self.EXTENT), (2.0, 1.0))

    def test_turn_scale_flip_and_offset_in_that_order(self):
        s = dict(mode='size', u=100.0, v=50.0, flipU=True, turn=90.0, offsetU=0.25, offsetV=-0.5)
        # (100, 0) -> turned 90 (0, 100) -> scaled (0, 2) -> flipped (-0, 2) -> slid (0.25, 1.5)
        close(self, uv_mapping.uv(s, 100.0, 0.0, self.EXTENT), (0.25, 1.5))
        thirty = dict(mode='size', u=10.0, v=10.0, turn=30.0)
        c, s3 = math.cos(math.radians(30)), math.sin(math.radians(30))
        close(self, uv_mapping.uv(thirty, 10.0, 0.0, self.EXTENT), (c, s3))

    def test_a_turned_repeat_stays_a_rectangle_of_its_size(self):
        # a 96 by 48 repeat turned 30 degrees: its edges are 96 and 48 long along the turned axes, square to each other
        s = dict(mode='size', u=96.0, v=48.0, turn=30.0)
        c, s3 = math.cos(math.radians(30)), math.sin(math.radians(30))
        o = uv_mapping.uv(s, 0.0, 0.0, self.EXTENT)
        close(self, [x - y for x, y in zip(uv_mapping.uv(s, 96.0 * c, -96.0 * s3, self.EXTENT), o)], (1.0, 0.0))
        close(self, [x - y for x, y in zip(uv_mapping.uv(s, 48.0 * s3, 48.0 * c, self.EXTENT), o)], (0.0, 1.0))

    def test_a_turned_count_or_fit_is_across_the_turned_axes(self):
        # a quarter turn: the pattern's u runs up the surface (400 tall), its v along it (384 long); its corners whole
        # counts, so the turned image fits it exactly
        count = dict(mode='count', u=3.0, v=2.0, turn=90.0)
        got = [uv_mapping.uv(count, a, b, self.EXTENT) for a in (0.0, 384.0) for b in (-16.0, 368.0)]
        self.assertEqual(sorted({round(u, 9) for u, _ in got}), [0.0, 3.0])
        self.assertEqual(sorted({round(v, 9) for _, v in got}), [0.0, 2.0])
        # 30 degrees: the fitted image spans the surface's corners' run along each turned axis, 0 to 1
        fit = dict(mode='fit', u=1.0, v=1.0, turn=30.0)
        got = [uv_mapping.uv(fit, a, b, self.EXTENT) for a in (0.0, 384.0) for b in (-16.0, 368.0)]
        close(self, [min(u for u, _ in got), max(u for u, _ in got), min(v for _, v in got), max(v for _, v in got)],
              [0.0, 1.0, 0.0, 1.0])

    def test_world_aligned_surfaces_line_up(self):
        s = dict(mode='size', u=96.0, v=96.0, world=True)
        # two pieces side by side, one framed at 0 and one at 384: the shared edge reads alike
        left = uv_mapping.uv(s, 384.0, 0.0, self.EXTENT, origin=(0.0, 0.0))
        right = uv_mapping.uv(s, 0.0, 0.0, self.EXTENT, origin=(384.0, 0.0))
        close(self, left, right)
        # a piece-local one restarts at its own frame
        local = dict(s, world=False)
        self.assertNotEqual(uv_mapping.uv(local, 0.0, 0.0, self.EXTENT, origin=(384.0, 0.0))[0], left[0])

    def test_rebased_keeps_the_phase(self):
        got = uv_mapping.rebased([(1030.25, -3.5), (1031.75, -2.0)])
        close(self, [v for p in got for v in p], [0.25, 0.5, 1.75, 2.0])
        self.assertTrue(uv_mapping.half_float_room(got))
        self.assertFalse(uv_mapping.half_float_room([(0.0, 0.0), (2000.0, 0.0)]))

    def test_shapes(self):
        uv_mapping.check(dict(surfaces=dict(faces=dict(mode='size', u=64, v=64, turn=30, flipU=True, world=False))))
        for bad in (dict(), dict(surfaces=dict(roof=dict(mode='size', u=1, v=1))),
                    dict(surfaces=dict(top=dict(mode='tile', u=1, v=1))), dict(surfaces=dict(top=dict(mode='size', u=0, v=1))),
                    dict(surfaces=dict(top=dict(mode='size', u=1, v=1, turn='x'))),
                    dict(surfaces=dict(top=dict(mode='size', u=1, v=1, flipU=1))),
                    dict(surfaces=dict(top=dict(mode='size', u=1, v=1, scale=2)))):
            with self.assertRaises(uv_mapping.MappingError, msg=bad):
                uv_mapping.check(bad)
        self.assertIsNone(uv_mapping.surface_of(dict(x0=0), 'top'))
        self.assertEqual(uv_mapping.surface_of(dict(mapping=dict(surfaces=dict(top=dict(mode='fit', u=1, v=1)))), 'top')['mode'], 'fit')

    def test_origins(self):
        uv_mapping.check_origin(None)
        uv_mapping.check_origin(dict(faces=[1, 2], top=[1.5, 2, 3], sides=[0, 0, 0]))
        for bad in ([1, 2], dict(roof=[1, 2]), dict(top=[1]), dict(top=[1, 2, 3, 4]), dict(sides=[1, 2]),
                    dict(top=[1, float('inf')]), dict(top=[1, False]), dict(top='0 0')):
            with self.assertRaises(uv_mapping.MappingError, msg=bad):
                uv_mapping.check_origin(bad)
        numbers = dict(mappingOrigin=dict(faces=[10.0, 20.0], top=[1.0, 2.0, 3.0], sides=[4.0, 5.0, 6.0]))
        self.assertEqual(uv_mapping.origin_of(numbers, 'faces'), (10.0, 20.0))
        self.assertEqual(uv_mapping.origin_of(numbers, 'top'), (1.0, 2.0))
        self.assertEqual(uv_mapping.origin_of(numbers, 'sides', 'xz'), (4.0, 6.0))
        self.assertEqual(uv_mapping.origin_of(numbers, 'sides', 'yz'), (5.0, 6.0))
        self.assertEqual(uv_mapping.origin_of(numbers, 'underside'), (0.0, 0.0))
        self.assertEqual(uv_mapping.origin_of(dict(mappingOrigin=dict(faces=[1.0, 2.0, 3.0])), 'faces'), (1.0, 3.0))

    def test_face_signs_and_mapped(self):
        self.assertEqual(uv_mapping.face_signs('faces', (0.0, 1.0, 0.0)), (1.0, -1.0))
        self.assertEqual(uv_mapping.face_signs('faces', (0.0, -1.0, 0.0)), (-1.0, -1.0))
        self.assertEqual(uv_mapping.face_signs('top'), (1.0, 1.0))
        self.assertEqual(uv_mapping.face_signs('underside', (0.0, 0.0, -1.0)), (-1.0, 1.0))
        # a ground side: its a runs right seen from outside facing +y (x) and -x (y); left facing -y and +x
        for normal, sign in (((0, 1, 0), 1.0), ((-1, 0, 0), 1.0), ((0, -1, 0), -1.0), ((1, 0, 0), -1.0)):
            self.assertEqual(uv_mapping.face_signs('sides', normal), (sign, -1.0), normal)
        with self.assertRaises(uv_mapping.MappingError):
            uv_mapping.face_signs('roof')
        s = dict(mode='size', u=96.0, v=48.0)
        close(self, [v for p in uv_mapping.mapped(s, [(96.0, 48.0), (0.0, 24.0)], self.EXTENT, signs=(-1.0, -1.0))
                     for v in p], [-1.0, -1.0, 0.0, -0.5])


if __name__ == '__main__':
    unittest.main()
