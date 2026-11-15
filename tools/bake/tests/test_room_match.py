"""room_match's report: facing, brightness bands, the checkerboard groups and the per-component ranking, on made-up
texels (no map needed)."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import room_match  # noqa: E402


def component(name, b, a, nz, world, parts=None):
    return dict(component='TheWorld.PersistentLevel.' + name, mesh='Pkg.Meshes.' + name, b=np.asarray(b, float),
                a=np.asarray(a, float), nz=np.asarray(nz, float), world=np.asarray(world, float), buried=0,
                parts=parts or {})


class ReportTest(unittest.TestCase):
    def test_facing(self):
        self.assertEqual(list(room_match.facing(np.array([1.0, 0.0, -1.0, 0.71, -0.69]))),
                         ['floor', 'wall', 'ceiling', 'floor', 'wall'])

    def test_exact_match_is_perfect(self):
        world = [[x * 10.0, 0.0, 0.0] for x in range(40)]
        b = np.linspace(0.1, 1.0, 40)
        rep = room_match.report([component('Floor', b, b, [1.0] * 40, world)])
        self.assertEqual(rep['all']['within10'], 1.0)
        self.assertEqual(rep['checker']['texelsWithin10'], 1.0)
        self.assertAlmostEqual(rep['all']['medianRatio'], 1.0)
        self.assertEqual(rep['byFacing']['wall']['lit'], 0)

    def test_dark_texels_are_not_judged(self):
        rep = room_match.report([component('Dim', [0.01, 0.02], [1.0, 1.0], [1, 1], [[0, 0, 0], [1, 0, 0]])])
        self.assertEqual(rep['all']['lit'], 0)
        self.assertNotIn('within10', rep['all'])

    def test_checker_groups_by_cube_and_component(self):
        # cube x < 192 is right, cube 192..384 is half as bright: half the texels in groups within 10%
        world = [[50.0, 0, 0]] * 10 + [[250.0, 0, 0]] * 10
        b = [0.5] * 20
        a = [0.5] * 10 + [0.25] * 10
        rep = room_match.report([component('Wall', b, a, [0.0] * 20, world)])
        self.assertEqual(rep['checker']['groups'], 2)
        self.assertAlmostEqual(rep['checker']['texelsWithin10'], 0.5)
        self.assertAlmostEqual(rep['checker']['texelsWithin40'], 0.5)
        # the same texels as two components, one per cube: still two groups, and B carries all the error
        two =room_match.report([component('A', b[:10], a[:10], [0.0] * 10, world[:10]),
                                 component('B', b[10:], a[10:], [0.0] * 10, world[10:])])
        self.assertEqual(two['checker']['groups'], 2)
        self.assertEqual(two['components'][0]['component'], 'B')       # carries all the error
        self.assertAlmostEqual(two['components'][0]['errorShare'], 1.0)

    def test_bands_and_parts(self):
        b = [0.03, 0.07, 0.15, 0.3, 0.8]
        a = [0.06, 0.07, 0.15, 0.3, 0.4]
        parts = {k: np.zeros(5) for k in room_match.PARTS}
        parts['direct'] = np.array(a) * 0.75
        parts['bounce'] = np.array(a) * 0.25
        rep = room_match.report([component('F', b, a, [1.0] * 5, [[x * 300.0, 0, 0] for x in range(5)], parts)],
                                parts=True)
        bands = {tuple(x['band']): x for x in rep['byBrightness']}
        self.assertAlmostEqual(bands[(0.01, 0.05)]['medianRatio'], 2.0)
        self.assertAlmostEqual(bands[(0.5, None)]['medianRatio'], 0.5)
        floor = rep['partShares']['floor']
        self.assertAlmostEqual(floor['direct'], 0.75)
        self.assertAlmostEqual(floor['bounce'], 0.25)
        self.assertAlmostEqual(floor['originalOverOurs'], (0.07 + 0.15 + 0.3 + 0.8) / (0.07 + 0.15 + 0.3 + 0.4))


if __name__ == '__main__':
    unittest.main()
