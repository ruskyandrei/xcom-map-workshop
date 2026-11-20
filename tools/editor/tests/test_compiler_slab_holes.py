"""A made floor or roof whose holes leave none of it (review finding 32): the compiler leaves it out of the build and
says why, and the rest of the project builds. The Build's own check (tools/bake/frac_slab.py) refuses such a slab."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
from editor_fixtures import compiled, left_out, made  # noqa: E402

T = 96.0


def slab(*holes):
    return dict(kind='fracSlab', version=1, slab=dict(x0=0.0, x1=3 * T, y0=0.0, y1=2 * T, seed=4, look='floor',
                                                      holes=[dict(x0=a, x1=b, y0=c, y1=d) for a, b, c, d in holes]))


class AllHoles(unittest.TestCase):
    def test_a_slab_its_holes_leave_none_of_is_left_out_and_said(self):
        for holes in ([(0.0, 3 * T, 0.0, 2 * T)], [(0.0, 2 * T, 0.0, 2 * T), (T, 3 * T, 0.0, 2 * T)]):
            spec, report = compiled([made(slab(*holes), at=(0, 636, 0)), made(slab(), serial=2, at=(0, 1212, 0))])
            self.assertEqual(left_out(report), ['slab-all-holes'], holes)
            (row,) = report['leftOut']
            self.assertIn('its holes leave none of it', row['message'])
            (op,) = [o for o in spec['objects'] if o['type'] == 'copy']
            self.assertEqual(op['labels'], ['XComFracLevelActor_11_copy2'])

    def test_overlapping_holes_that_leave_a_tile_are_a_slab(self):
        spec, report = compiled([made(slab((0.0, 2 * T, 0.0, 2 * T), (T, 3 * T, T, 2 * T)), at=(0, 636, 0))])
        self.assertEqual(left_out(report), [])
        self.assertEqual(len([o for o in spec['objects'] if o['type'] == 'copy']), 1)


if __name__ == '__main__':
    unittest.main()
