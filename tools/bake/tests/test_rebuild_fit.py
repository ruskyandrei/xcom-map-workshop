"""Rebuild volumes fitted round tiles the battle's rebuild must not take (rebuild_fit.py; findings register F-149)."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import rebuild_fit  # noqa: E402

CORNER = (-2497.0, -3553.0, -129.0)     # CsmallScout_Farm's tile corner: off the whole numbers, as every map's is


def taken(cube, corner=CORNER):
    """The tiles the game queues for a cube's volume, by the game's rule (span)."""
    centre, radius = rebuild_fit.pose(cube, corner)
    (x0, x1), (y0, y1), (z0, z1) = rebuild_fit.span(centre, radius, corner)
    return (x0, x1, y0, y1, z0, z1)


def cells(ranges, cut=None):
    x0, x1, y0, y1, z0, z1 = ranges
    if cut:
        x0, x1, y0, y1, z0, z1 = (max(x0, cut[0]), min(x1, cut[1]), max(y0, cut[2]), min(y1, cut[3]),
                                  max(z0, cut[4]), min(z1, cut[5]))
    return {(x, y, z) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) for z in range(z0, z1 + 1)}


class Cubes(unittest.TestCase):
    def test_a_cubes_volume_takes_its_tiles_and_no_others(self):
        for k in range(0, 130):
            for at in ((0, 0, 0), (5, 7, 3), (-4, -9, -30), (61, 88, 17)):
                cube = at + (k,)
                self.assertEqual(taken(cube), rebuild_fit.tiles(cube), cube)

    def test_its_faces_stand_well_inside_its_outer_tiles(self):
        # a volume a few units larger or smaller than asked takes the same tiles
        for k in (0, 1, 2, 3, 4, 7, 39, 91):
            cube = (3, 4, 1, k)
            centre, radius = rebuild_fit.pose(cube, CORNER)
            for off in (-6.0, 6.0):
                (x0, x1), (y0, y1), (z0, z1) = rebuild_fit.span(centre, radius + off, CORNER)
                self.assertEqual((x0, x1, y0, y1, z0, z1), rebuild_fit.tiles(cube), (cube, off))

    def test_the_levels_a_cube_takes(self):
        self.assertEqual([rebuild_fit.levels(k) for k in range(6)], [1, 2, 3, 5, 6, 8])
        self.assertEqual([rebuild_fit.width_for(n) for n in (1, 2, 3, 4, 5, 6, 7, 18)], [1, 1, 2, 3, 3, 4, 5, 12])

    def test_the_tiles_a_box_is_there_for(self):
        # a Build's box stands 8 past its tiles on each side: tiles 3..5 by 10..11, levels 0..6
        box = [CORNER[0] + 1 + 96 * 3 - 8, CORNER[0] + 1 + 96 * 6 + 8, CORNER[1] + 1 + 96 * 10 - 8, CORNER[1] + 1 + 96 * 12 + 8,
               CORNER[2] + 1 - 8, CORNER[2] + 1 + 64 * 7 + 8]
        self.assertEqual(rebuild_fit.centred(box, CORNER), (3, 5, 10, 11, 0, 6))
        self.assertEqual(rebuild_fit.centred(box, CORNER, (5, 11, 4)), (3, 4, 10, 10, 0, 3))
        self.assertIsNone(rebuild_fit.centred(box, CORNER, (3, 20, 20)))


class Fit(unittest.TestCase):
    def check(self, need, forbidden):
        cubes = rebuild_fit.fit(need, forbidden)
        left = cells(need) - set(forbidden)
        for cube in cubes:
            got = taken(cube)
            self.assertEqual(got, rebuild_fit.tiles(cube))
            hit = [t for t in forbidden if all(got[2 * k] <= t[k] <= got[2 * k + 1] for k in range(3))]
            self.assertEqual(hit, [], cube)
            self.assertTrue(cells(got, need) & left, 'a cube that takes nothing new: %r' % (cube,))
            left -= cells(got, need)
        self.assertEqual(left, set())
        return cubes

    def test_nothing_forbidden_is_one_cube(self):
        self.assertEqual(self.check((2, 5, 3, 4, 0, 6), set()), [(2, 3, 0, 5)])     # five levels wide enough for 7

    def test_a_tile_beside_the_box_is_left_alone(self):
        # tiles 36..38 by 10..14, seven levels, a forbidden tile at (39, 12, 0) and the two over it
        forbidden = {(39, 12, z) for z in range(3)}
        cubes = self.check((36, 38, 10, 14, 0, 6), forbidden)
        self.assertLessEqual(len(cubes), 8)

    def test_holes_inside_a_whole_grid(self):
        # CsmallScout_Farm's eight diagonal tiles in a grid of 67 by 91, the ground and three levels over it
        holes = [(39, 12), (39, 20), (41, 10), (41, 22), (49, 10), (49, 22), (51, 12), (51, 20)]
        forbidden = {(x, y, z) for x, y in holes for z in range(3)}
        cubes = self.check((0, 66, 0, 90, 0, 3), forbidden)
        self.assertLessEqual(len(cubes), 30)
        self.assertFalse([c for c in cubes if c[3] == 0])

    def test_a_tile_over_the_box_is_left_alone(self):
        # a forbidden tile five levels up over the box's own tiles: the cubes stay under it
        forbidden = {(4, 4, 5), (4, 4, 6), (4, 4, 7)}
        cubes = self.check((0, 9, 0, 9, 0, 4), forbidden)
        self.assertTrue(all(rebuild_fit.tiles(c)[5] <= 4 for c in cubes if c[0] <= 4 < c[0] + max(c[3], 1)
                            and c[1] <= 4 < c[1] + max(c[3], 1)))

    def test_one_free_level_between_two_forbidden_tiles_gets_a_single_tile(self):
        forbidden = {(1, 1, 0), (1, 1, 2)}
        cubes = self.check((1, 1, 1, 1, 1, 1), forbidden)
        self.assertEqual(cubes, [(1, 1, 1, 0)])

    def test_forbidden_tiles_on_upper_decks(self):
        forbidden = {(x, y, z + n) for x, y, z in [(10, 10, 2), (12, 10, 9), (30, 40, 7), (31, 41, 0)] for n in range(3)}
        self.check((0, 47, 0, 87, 0, 11), forbidden)

    def test_the_cubes_come_lowest_level_first_then_y_then_x(self):
        cubes = rebuild_fit.fit((0, 66, 0, 90, 0, 3), {(39, 12, 0), (39, 12, 1), (39, 12, 2)})
        firsts = [(c[2], c[1], c[0]) for c in cubes if c[2] >= 0]
        self.assertEqual(firsts, sorted(firsts))


if __name__ == '__main__':
    unittest.main()
