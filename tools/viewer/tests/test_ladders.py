"""A ladder's climb ends (ladders.py ends): the cases of ladder_cases.json, which web/ladders.js ladderEnds gives too
(ladders_test.mjs), so the inspector's end marks and the compiler's climb warning cannot part. The numbers both use are
held to twin_constants.json by test_twin_constants.py."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ladders  # noqa: E402

CASES = json.loads(Path(__file__).with_name('ladder_cases.json').read_text(encoding='utf-8'))['cases']


class Ends(unittest.TestCase):
    def test_the_cases(self):
        self.assertGreaterEqual(len(CASES), 10)
        for c in CASES:
            with self.subTest(c['why']):
                got = ladders.ends(c['location'], c['rotation'], c['extentZ'], c['origin'],
                                   {tuple(t) for t in c['floors']})
                want = dict(c['ends'])
                for key in ('top', 'foot'):
                    self.assertEqual(len(got[key]), 3)
                    for a, b in zip(got.pop(key), want.pop(key)):
                        self.assertAlmostEqual(a, b, delta=1e-9)
                self.assertEqual(got, want)

    def test_the_points_tiles(self):
        # the tiles are those of the points, on the grid from the case's corner
        for c in CASES:
            with self.subTest(c['why']):
                top, foot = ladders.points(c['location'], c['rotation'], c['extentZ'])
                self.assertEqual(list(ladders.tile_of(top, c['origin'])), c['ends']['topTile'])
                self.assertEqual(list(ladders.tile_of(foot, c['origin'])), c['ends']['footTile'])

    def test_every_verdict_is_among_the_cases(self):
        self.assertEqual({'+'.join(c['ends']['why']) for c in CASES}, {'', 'foot', 'top', 'foot+top'})
        # a linked top under the top's own tile
        self.assertTrue(any(c['ends']['linkedTop'] and c['ends']['linkedTop'][2] == c['ends']['topTile'][2] - 1
                            for c in CASES))


if __name__ == '__main__':
    unittest.main()
