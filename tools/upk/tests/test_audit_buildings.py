"""The game editor's rule for which floors list a piece (audit_buildings.touched and listing)."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import audit_buildings as buildings  # noqa: E402

# two storeys of 192 over one footprint, and an L-shaped third floor of two boxes
FLOORS = [[[0, 0, 16, 960, 960, 208]], [[0, 0, 208, 960, 960, 400]],
          [[0, 0, 400, 480, 960, 592], [480, 0, 400, 960, 480, 592]]]


def box(x0, x1, y0, y1, z0, z1):
    return [x0, x1, y0, y1, z0, z1]


class Touched(unittest.TestCase):
    def test_a_piece_inside_one_floor(self):
        self.assertEqual(buildings.touched(box(100, 200, 100, 200, 16, 100), FLOORS), [0])

    def test_a_wall_reaching_the_next_floor_counts_for_both(self):
        self.assertEqual(buildings.touched(box(0, 16, 0, 192, 16, 214), FLOORS), [0, 1])

    def test_a_bottom_within_the_margin_of_the_top_does_not_count(self):
        # the first floor's slab: 12 units under the ground floor's top, so it is the first floor's only
        self.assertEqual(buildings.touched(box(0, 960, 0, 960, 196, 208), FLOORS), [1])
        self.assertEqual(buildings.touched(box(0, 960, 0, 960, 187, 208), FLOORS), [0, 1])

    def test_any_box_of_a_floor_counts(self):
        self.assertEqual(buildings.touched(box(600, 700, 100, 200, 400, 500), FLOORS), [2])
        self.assertEqual(buildings.touched(box(600, 700, 600, 700, 400, 500), FLOORS), [])

    def test_outside_counts_only_within_the_slack(self):
        wall = box(-12, -1, 0, 192, 16, 200)
        self.assertEqual(buildings.touched(wall, FLOORS), [])
        self.assertEqual(buildings.touched(wall, FLOORS, slack=2.0), [0])


class Listing(unittest.TestCase):
    def test_none(self):
        self.assertEqual(buildings.listing([], True), [])

    def test_one_floor_has_no_cutdown(self):
        self.assertEqual(buildings.listing([1], True), [(1, 0)])
        self.assertEqual(buildings.listing([1], False), [(1, 0)])

    def test_a_masked_piece_is_listed_on_the_lowest_with_the_highest_as_its_cutdown(self):
        self.assertEqual(buildings.listing([0, 1], True), [(0, 1)])
        self.assertEqual(buildings.listing([1, 2, 3], True), [(1, 3)])

    def test_a_piece_without_the_mask_is_listed_on_each(self):
        self.assertEqual(buildings.listing([2, 0, 1], False), [(0, 0), (1, 0), (2, 0)])


if __name__ == '__main__':
    unittest.main()
