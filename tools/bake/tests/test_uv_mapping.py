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

    def test_flip_turn_and_offset_in_that_order(self):
        s = dict(mode='size', u=100.0, v=100.0, flipU=True, turn=90.0, offsetU=0.25, offsetV=-0.5)
        # (100, 0) -> (1, 0) -> flipped (-1, 0) -> turned 90 (0, -1) -> slid (0.25, -1.5)
        close(self, uv_mapping.uv(s, 100.0, 0.0, self.EXTENT), (0.25, -1.5))
        thirty = dict(mode='size', u=10.0, v=10.0, turn=30.0)
        c, s3 = math.cos(math.radians(30)), math.sin(math.radians(30))
        close(self, uv_mapping.uv(thirty, 10.0, 0.0, self.EXTENT), (c, s3))

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


if __name__ == '__main__':
    unittest.main()
