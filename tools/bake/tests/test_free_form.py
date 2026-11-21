"""The free form of made pieces' numbers (free_form.py; custom geometry improvements plan, section 10.2): what is free,
extents checked without changing them, and texture coordinates held near 0 in whole repeats as the mesh's half floats
keep them, a face spanning too many repeats refused with that reason."""
import math
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import free_form  # noqa: E402


def half(v):
    return struct.unpack('<e', struct.pack('<e', v))[0]


class FreeForm(unittest.TestCase):
    def test_free_is_one_and_nothing_else(self):
        self.assertFalse(free_form.is_free(dict(x0=0.0)))
        self.assertFalse(free_form.is_free(None))
        self.assertTrue(free_form.is_free(dict(free=1)))
        for bad in (2, 0, 'yes', None):
            with self.assertRaises(free_form.NumbersError) as e:
                free_form.is_free(dict(free=bad))
            self.assertEqual(e.exception.code, 'free')

    def test_extents_any_finite_size_never_changed(self):
        n = dict(x0=-10.25, x1=0.5, y0=3.0, y1=3.75, z0=-1000.0, z1=50000.0)
        self.assertEqual(free_form.extents(n, 'a piece'), [-10.25, 0.5, 3.0, 3.75, -1000.0, 50000.0])
        self.assertEqual(free_form.extents(n, 'a piece', 'xy'), [-10.25, 0.5, 3.0, 3.75])
        for key, value, code in (('x1', -10.25, 'extent'), ('y1', 2.0, 'extent'), ('z0', math.inf, 'number'),
                                 ('x0', math.nan, 'number'), ('y0', True, 'number'), ('z1', None, 'number'),
                                 ('x1', -10.249, 'extent')):
            with self.assertRaises(free_form.NumbersError) as e:
                free_form.extents(dict(n, **{key: value}), 'a piece')
            self.assertEqual(e.exception.code, code, key)
            self.assertIn(key[0], str(e.exception))

    def test_a_mapping_is_a_dict_when_given(self):
        free_form.mapping(dict(), 'a piece')
        free_form.mapping(dict(mapping=dict(surfaces={})), 'a piece')
        with self.assertRaises(free_form.NumbersError) as e:
            free_form.mapping(dict(mapping=[1]), 'a piece')
        self.assertEqual(e.exception.code, 'mapping')

    def test_held_takes_whole_repeats_off_keeping_the_phase(self):
        uvs = [(1500.3, -700.6), (1530.8, -650.1), (1490.05, -690.35)]
        out = free_form.held(uvs, 'a face')
        for (u, v), (hu, hv) in zip(uvs, out):
            self.assertAlmostEqual((u - hu) % 1.0, 0.0, 6)          # whole repeats taken off
            self.assertAlmostEqual(round(u - hu), u - hu, 6)
            self.assertAlmostEqual((v - hv) % 1.0, 0.0, 6)
        # the middle of each axis's range within half a repeat of 0
        for axis in (0, 1):
            values = [uv[axis] for uv in out]
            self.assertLessEqual(abs((min(values) + max(values)) / 2), 0.5)
        # near 0 the half floats keep each place to within 1/64 of a repeat; far out they would not
        self.assertTrue(all(abs(half(u) - u) < 1 / 64 for u, _ in out))
        self.assertGreater(max(abs(half(u) - u) for u, _ in uvs), 0.2)

    def test_held_refuses_only_what_no_shift_holds(self):
        # 2,040 repeats: centred, under 1,024 from 0 each way
        out = free_form.held([(0.0, 0.0), (2040.0, 0.0)], 'a face')
        self.assertTrue(all(abs(u) < free_form.HALF_PHASE for u, _ in out))
        with self.assertRaises(free_form.NumbersError) as e:
            free_form.held([(0.0, 0.0), (0.0, 2050.0)], "a ground block's side")
        self.assertEqual(e.exception.code, 'half-floats')
        self.assertIn('half floats', str(e.exception))
        self.assertIn("a ground block's side", str(e.exception))


if __name__ == '__main__':
    unittest.main()
