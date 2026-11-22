"""The game's cover rule and the diagonal cover finder against a map's pieces (tile_world.py, tile_rule.py; diagonal
cover plan, stage C1; findings register F-153).

The sweeps and the rule are checked on pieces made here; the rule's answer on CsmallScout_Farm's eight marked tiles
against the map's bake reads the install and skips without it."""
import math
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402
import tile_rule  # noqa: E402
import tile_world  # noqa: E402

FARM, NO_FARM = labpaths.install_map('CsmallScout_Farm')
S = math.sqrt(0.5)


def box(lo, hi):
    """A box's corners."""
    return [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def turned_box(centre, half, yaw):
    """A box turned `yaw` radians about z."""
    c, s = math.cos(yaw), math.sin(yaw)
    out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                x, y = sx * half[0], sy * half[1]
                out.append([centre[0] + c * x - s * y, centre[1] + s * x + c * y, centre[2] + sz * half[2]])
    return out


class Sweeps(unittest.TestCase):
    def setUp(self):
        self.world = tile_world.World.empty()
        self.cube = self.world.add(tile_world.solid_piece('cube', 'XComLevelActor', [(box((100, -50, 0), (200, 50, 100)),
                                                                                       None, None)]))

    def test_a_box_sweep_meets_a_face_at_its_box_distance(self):
        h = self.world.trace((0, 0, 50), (300, 0, 50), (1, 1, 8))
        self.assertAlmostEqual(h['time'] * 300, 99.0, places=6)          # the box's centre 1 short of the face
        self.assertTrue(np.allclose(h['normal'], (-1, 0, 0)))
        self.assertFalse(h['inside'])

    def test_a_line_meets_the_face_itself(self):
        h = self.world.trace((0, 0, 50), (300, 0, 50))
        self.assertAlmostEqual(h['time'] * 300, 100.0, places=6)

    def test_a_box_sweep_passing_a_corner_by_less_than_its_size_meets_it(self):
        # passing 0.5 off the cube's lower y face with a box 1 wide each way: met; 1.5 off: not
        h = self.world.trace((0, -50.5, 50), (300, -50.5, 50), (1, 1, 8))
        self.assertIsNotNone(h)
        self.assertIsNone(self.world.trace((0, -51.5, 50), (300, -51.5, 50), (1, 1, 8)))

    def test_a_sweep_starting_inside_hits_at_time_zero(self):
        h = self.world.trace((150, 0, 50), (300, 0, 50), (1, 1, 8))
        self.assertEqual(h['time'], 0.0)
        self.assertTrue(h['inside'])

    def test_a_turned_box_gives_its_turned_face(self):
        w = tile_world.World.empty()
        w.add(tile_world.solid_piece('wall', 'XComLevelActor', [(turned_box((100, 100, 50), (60, 8, 50), -math.pi / 4),
                                                                   None, None)]))
        h = w.trace((0, 0, 50), (200, 200, 50), (1, 1, 8))
        self.assertAlmostEqual(abs(float(h['normal'] @ np.array([S, S, 0]))), 1.0, places=6)

    def test_kinds_filter_pieces(self):
        ignored = self.world.add(tile_world.solid_piece('ignored', 'XComLevelActor',
                                                        [(box((40, -50, 0), (60, 50, 100)), None, None)],
                                                        flags=dict(bIgnoreForCover=True)))
        self.assertEqual(self.world.trace((0, 0, 50), (300, 0, 50), (1, 1, 8))['piece'].name, 'cube')
        self.assertIs(self.world.trace((0, 0, 50), (300, 0, 50), (1, 1, 8), kind='engine')['piece'], ignored)
        plain = tile_world.solid_piece('plain', 'StaticMeshActor', [(box((20, -50, 0), (30, 50, 100)), None, None)])
        self.world.add(plain)
        self.assertEqual(self.world.trace((0, 0, 50), (300, 0, 50), (1, 1, 8))['piece'].name, 'cube')
        self.assertIs(self.world.trace((0, 0, 50), (300, 0, 50), kind='engine')['piece'], plain)

    def test_a_still_box_overlaps(self):
        self.assertEqual([pc.name for pc, _ in self.world.overlaps((150, 0, 50), (48, 48, 32), 'occupancy')], ['cube'])
        self.assertEqual(self.world.overlaps((0, 0, 50), (48, 48, 32), 'occupancy'), [])


class Corner(unittest.TestCase):
    """A floor of one piece and a wall turned 45 degrees across the corner of tile (1, 1, 0)."""

    def setUp(self):
        self.world = tile_world.World.empty()
        self.floor = self.world.add(tile_world.solid_piece('floor', 'XComLevelActor',
                                                           [(box((-500, -500, -20), (500, 500, 0)), None, None)]))
        # the tile's position (144, 144, 32): a wall 192 long, 16 thick, 150 high, its face 50 from the position
        # along the north-east diagonal
        face = np.array([144, 144]) + 50 * np.array([S, S])
        centre = face + 8 * np.array([S, S])
        self.wall = self.world.add(tile_world.solid_piece('wall', 'XComLevelActor',
                                                          [(turned_box((centre[0], centre[1], 75), (8, 96, 75), math.pi / 4),
                                                            None, None)]))
        dims = (4, 4, 2)
        flags = {(x, y, z): 0 for x in range(4) for y in range(4) for z in range(2)}
        floor = {}
        for x in range(4):
            for y in range(4):
                flags[(x, y, 0)] = tile_rule.FLOOR | 0x20 | 0x20000
                floor[(x, y, 0)] = dict(loc=(96 * x + 48, 96 * y + 48, 0.0), actor=1)
        flags[(1, 1, 0)] |= tile_rule.OCCUPIED | tile_rule.PARTLY
        self.tiles = tile_rule.Tiles((0, 0, 0), dims, flags, floor)

    def test_the_diagonal_gives_high_cover_with_its_location_40_back(self):
        r = tile_rule.cover(self.world, self.tiles, (1, 1, 0), True)
        self.assertEqual(r['flags'] & 0xFF, 0x8)            # W: (s, s), high
        self.assertTrue(r['flags'] & tile_rule.DIAGONAL)
        want = np.array([144, 144]) + (50 - 1 * math.sqrt(2) - 40) * np.array([S, S])
        self.assertTrue(np.allclose(r['location'][:2], want, atol=1e-6), r['location'])
        self.assertEqual(r['location'][2], 0.0)

    def test_the_straight_rule_gives_none_and_the_finder_takes_it(self):
        r = tile_rule.finder(self.world, self.tiles, (1, 1, 0))
        self.assertTrue(r['diagonal'])
        self.assertEqual(r['straight'] & 0xF, 0)
        self.assertTrue(r['partly'])
        self.assertGreaterEqual(r['facing'], tile_rule.SQUARE)

    def test_the_finder_leaves_a_tile_the_wall_does_not_cross(self):
        self.tiles.flags[(1, 1, 0)] &= ~(tile_rule.OCCUPIED | tile_rule.PARTLY)
        self.assertFalse(tile_rule.finder(self.world, self.tiles, (1, 1, 0))['diagonal'])

    def test_the_finder_leaves_a_wall_off_the_diagonal(self):
        self.world = tile_world.World.empty()
        self.world.add(self.floor)
        face = np.array([144, 144]) + 50 * np.array([S, S])
        self.world.add(tile_world.solid_piece('wall', 'XComLevelActor', [(turned_box(
            (face[0] + 6, face[1] + 6, 75), (8, 96, 75), math.pi / 4 + math.radians(10)), None, None)]))
        r = tile_rule.finder(self.world, self.tiles, (1, 1, 0))
        self.assertFalse(r['diagonal'])
        self.assertLess(r['facing'], tile_rule.SQUARE)

    def test_a_low_wall_gives_low_cover_and_the_finder_leaves_it(self):
        self.world = tile_world.World.empty()
        self.world.add(self.floor)
        face = np.array([144, 144]) + 50 * np.array([S, S])
        centre = face + 8 * np.array([S, S])
        self.world.add(tile_world.solid_piece('low', 'XComLevelActor', [(turned_box((centre[0], centre[1], 35),
                                                                                    (8, 96, 35), math.pi / 4), None, None)]))
        r = tile_rule.finder(self.world, self.tiles, (1, 1, 0))
        self.assertEqual(r['cover']['flags'] & 0xFF, 0x88)  # W, low
        self.assertFalse(r['diagonal'])

    def test_the_visiting_order_decides_a_neighbours_floor(self):
        # a tile not visited yet keeps the floor its first pass found (its record), a visited one its last flags
        self.tiles.flags[(2, 1, 0)] &= ~tile_rule.FLOOR
        self.assertTrue(self.tiles.floor_when((2, 1, 0), (1, 1, 0)))
        self.assertFalse(self.tiles.floor_when((2, 1, 0), (3, 1, 0)))


@unittest.skipUnless(FARM and FARM.exists(), NO_FARM)
class FarmMarks(unittest.TestCase):
    """CsmallScout_Farm's eight marked tiles (the scout's slanted corners): the rule gives each its baked cover bit
    for bit, step-outs included, and its cover location to 0.15 unit; the finder takes all eight and leaves a
    bulldozer's corner the designers did not mark."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HERE.parents[2] / 'research' / 'evidence'))
        import importlib.util
        import lighting_records as lighting
        spec = importlib.util.spec_from_file_location('diagonal_finder', HERE.parents[2] / 'research' / 'evidence'
                                                      / 'diagonal-finder.py')
        finder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(finder)
        cls.p = lighting.Package(FARM)
        cls.tiles, cls.cover, cls.locs = finder.inputs(cls.p)
        cls.world = tile_world.World(cls.p)
        cls.marked = sorted(t for t, v in cls.cover.items() if v & tile_rule.DIAGONAL)

    def test_the_marked_tiles(self):
        self.assertEqual(self.marked, [(39, 12, 0), (39, 20, 0), (41, 10, 0), (41, 22, 0), (49, 10, 0), (49, 22, 0),
                                       (51, 12, 0), (51, 20, 0)])

    def test_the_rule_gives_the_baked_cover(self):
        for t in self.marked:
            with self.subTest(tile=t):
                r = tile_rule.cover(self.world, self.tiles, t, True)
                self.assertEqual('%06x' % r['flags'], '%06x' % self.cover[t])
                self.assertLessEqual(max(abs(r['location'][k] - self.locs[t][k]) for k in range(3)), 0.15)

    def test_the_finder_takes_the_marks_and_leaves_a_bulldozers_corner(self):
        for t in self.marked:
            with self.subTest(tile=t):
                self.assertTrue(tile_rule.finder(self.world, self.tiles, t)['diagonal'])
        r = tile_rule.finder(self.world, self.tiles, (49, 29, 0))
        self.assertTrue(r['cover']['flags'] & 0xF)       # a diagonal passes there
        self.assertFalse(r['diagonal'])


@unittest.skipUnless(FARM and FARM.exists(), NO_FARM)
class FarmWholeTiles(unittest.TestCase):
    """The Build's whole-tile writer (diagonal_keep.plan_whole) on CsmallScout_Farm as it is: each marked tile, and a
    few open and occupied ones, written whole come back as the bake has them, static and cover flags, cover location,
    floor and links (research/evidence/whole-tile-check.py does every map's)."""

    @classmethod
    def setUpClass(cls):
        import diagonal_keep
        import lighting_records as lighting
        cls.keep = diagonal_keep
        cls.ld = diagonal_keep.Loaded(lighting.Package(FARM))
        cls.marked = {t for t, v in cls.ld.cover.items() if v & tile_rule.DIAGONAL}

    def test_tiles_written_whole_are_the_bakes(self):
        ld = self.ld
        for t in sorted(self.marked) + [(45, 42, 0), (40, 11, 0), (44, 14, 0)]:
            with self.subTest(tile=t):
                r = self.keep.plan_whole(ld, {t}, self.marked, set())[t]
                rec = ld.floors[t]['record']
                self.assertEqual('%07x' % r['static'], '%07x' % ld.flags[t])
                self.assertEqual('%06x' % r['cover'], '%06x' % ld.cover.get(t, 0))
                if t in ld.location:
                    self.assertLessEqual(max(abs(r['location'][k] - ld.location[t][k]) for k in range(3)), 0.15)
                self.assertLessEqual(max(abs(r['floor']['loc'][k] - rec['loc'][k]) for k in range(3)), 0.1)
                self.assertEqual([(tuple(l['to']), list(l['types']), l['obj']) for l in r['floor']['links']],
                                 [(tuple(l['to']), list(l['types']), l['obj']) for l in rec['links']])


if __name__ == '__main__':
    unittest.main()
