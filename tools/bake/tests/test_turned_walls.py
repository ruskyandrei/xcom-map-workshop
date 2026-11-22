"""A made wall turned off the quarter turns: its fracture columns along its own line (frac_walls.turned,
turned_columns; F-145), and where a blast breaks it by the game's rule (research/native/frac-neighbours.md, section
2.3) against the same wall on a quarter turn. Pure: the walls are made by frac_wall.build, no package read."""
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import frac_wall  # noqa: E402
import frac_walls  # noqa: E402


def yawed(units, at=(0.0, 0.0, 0.0), pitch=0):
    """The 4 x 4 matrix of a piece at `at` turned `units` of the game's yaw (65536 a whole turn), and `pitch`."""
    import math
    c, s = math.cos(units * math.tau / 65536), math.sin(units * math.tau / 65536)
    cp, sp = math.cos(pitch * math.tau / 65536), math.sin(pitch * math.tau / 65536)
    turn = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]) @ np.array([[cp, 0.0, -sp], [0.0, 1.0, 0.0], [sp, 0.0, cp]])
    m = np.eye(4)
    m[:3, :3], m[:3, 3] = turn, at
    return m


def blast_breaks(columns, frag_boxes, hit, radius):
    """The fragments a blast breaks by the game's rule (research/native/frac-neighbours.md, sections 2.1 to 2.3;
    F-145): the columns within `radius` of the hit `hit` whose box meets the filter box (the hit and `radius` across,
    96 in from each side past two tiles, and 128 up and down) are damaged, or, when none meets it, every column within
    `radius`; a damaged column breaks each fragment it lists, lowest first, whose world box (`frag_boxes`) reaches
    into the filter box's heights, until one starts over the hit's height and `radius`."""
    half = radius - 96.0 if radius > 96.0 else radius
    flt = [hit[0] - half, hit[0] + half, hit[1] - half, hit[1] + half, hit[2] - 128.0, hit[2] + 128.0]

    def near(b):
        return sum(max(b[2 * k] - hit[k], 0.0, hit[k] - b[2 * k + 1]) ** 2 for k in range(3)) <= radius * radius

    def meets(b):
        return all(flt[2 * k] <= b[2 * k + 1] and b[2 * k] <= flt[2 * k + 1] for k in range(3))
    damaged = [c for c in columns if near(c['box']) and meets(c['box'])] or [c for c in columns if near(c['box'])]
    out = set()
    for c in damaged:
        for f, min_z in c['frags']:
            if min_z > hit[2] + radius:
                break
            if frag_boxes[f][5] > flt[4] and flt[5] > frag_boxes[f][4]:
                out.add(f)
    return out


class TurnedColumns(unittest.TestCase):
    """A made wall turned off the quarter turns has its columns along its own line (F-145): F0's rule in its frame."""
    GRID = dict(tx=-2785.0, ty=-1921.0, tz=-1.0)        # URB_Bar's level grid
    # EXP-90's wall C1: 384 long, one storey, mitred at its far end, at yaw 5461 (30 degrees)
    C1 = dict(free=1, x0=0.0, x1=384.0, z0=-16.0, z1=192.0, y0=-8.0, y1=8.0, seed=903,
              ends=['free', dict(inset=0.0, lean=-1.0)])
    C1_AT = (-1250.5, -1440.25, 0.0)

    @classmethod
    def setUpClass(cls):
        cls.local = [f['box'] for f in frac_wall.build(cls.C1)['fragments']]

    def test_a_wall_is_turned_off_the_quarter_turns_only_standing_upright(self):
        for units in (0, 16384, 32768, 49152, -16384, 65536):
            self.assertFalse(frac_walls.turned(yawed(units, (100.0, -50.0, 16.0))), units)
        for units in (1, 5000, 5461, 16383, 40000):
            self.assertTrue(frac_walls.turned(yawed(units, (100.0, -50.0, 16.0))), units)
        self.assertFalse(frac_walls.turned(yawed(5461, pitch=2000)))      # tilted: the world's axes (columns)

    def test_its_columns_are_a_tile_along_its_own_line_listing_the_fragments_on_that_stretch(self):
        m = yawed(5461, self.C1_AT)
        world = [frac_walls.world_box(b, m) for b in self.local]
        cols = frac_walls.turned_columns(self.local, m, self.GRID)
        lo, hi = min(b[0] for b in self.local), max(b[1] for b in self.local)
        stretches = [(max(lo - 1.0 + 96.0 * i, lo), min(lo + 95.0 + 96.0 * i, hi)) for i in range(5)]
        storeys = [(-193.0, -1.0), (-1.0, 191.0), (191.0, 383.0)]
        self.assertEqual(len(cols), len(stretches) * len(storeys))
        inv = np.linalg.inv(m)
        for c, ((a0, a1), (z0, z1)) in zip(cols, [(s, z) for s in stretches for z in storeys]):
            want = {f for f, (b, w) in enumerate(zip(self.local, world)) if min(b[1], a1) - max(b[0], a0) > 0
                    and min(w[5], z1) - max(w[4], z0) > 0}
            self.assertEqual({f for f, _ in c['frags']}, want)
            self.assertEqual(c['box'][4:6], [z0, z1])
            self.assertEqual([z for _, z in c['frags']], sorted(z for _, z in c['frags']))
            # its box is the world box round its stretch: its corners in the wall's frame span the stretch exactly
            corners = np.array([[x, y, 0.0, 1.0] for x in c['box'][0:2] for y in c['box'][2:4]]) @ inv.T
            self.assertLessEqual(corners[:, 0].min(), a0 + 1e-6)
            self.assertGreaterEqual(corners[:, 0].max(), a1 - 1e-6)
            across = [min(self.local[f][2] for f in want), max(self.local[f][3] for f in want)]
            box = frac_walls.world_box([a0, a1] + across + [0.0, 0.0], m)
            self.assertTrue(np.allclose(c['box'][:4], box[:4]), (c['box'], box))

    def test_on_its_own_grid_unturned_it_gives_f0s_columns(self):
        # the same rule as F0's in the wall's own frame: at yaw 0, with the level's grid where its own grid lies
        m = yawed(0, (200.0, 300.0, 0.0))
        world = [frac_walls.world_box(b, m) for b in self.local]
        lo = min(w[0] for w in world)
        f0 = frac_walls.columns(world, dict(self.GRID, tx=lo - 1.0))
        own = frac_walls.turned_columns(self.local, m, self.GRID)
        self.assertEqual([c['frags'] for c in own], [c['frags'] for c in f0])
        for a, b in zip(own, f0):
            self.assertTrue(np.allclose(a['box'], b['box']), (a['box'], b['box']))

    def test_a_blast_breaks_it_where_it_breaks_the_same_wall_on_a_quarter_turn(self):
        # EXP-90 check 3: an HE grenade (radius 288) on the pavement about 120 south-east of C1's start
        m = yawed(5461, self.C1_AT)
        world = [frac_walls.world_box(b, m) for b in self.local]
        hit = (-1170.2, -1528.4, 0.0)
        got = blast_breaks(frac_walls.turned_columns(self.local, m, self.GRID), world, hit, 288.0)
        # the same wall on yaw 0, the hit where it is from the wall's start
        rel = np.linalg.inv(m) @ np.array(list(hit) + [1.0])
        m0 = yawed(0, self.C1_AT)
        world0 = [frac_walls.world_box(b, m0) for b in self.local]
        hit0 = (self.C1_AT[0] + rel[0], self.C1_AT[1] + rel[1], 0.0)
        self.assertEqual(got, blast_breaks(frac_walls.columns(world0, self.GRID), world0, hit0, 288.0))
        # its lower rows from the start to past the middle go; the top band stands where its fragments start over 128
        self.assertEqual(sorted(got), [0, 1, 2, 3, 4, 5, 8])
        # columns on the world's axes listed the corner's two lower fragments in a column that meets the blast's square
        # while they lie 40 and more beyond it: they broke (F-145)
        old = blast_breaks(frac_walls.columns(world, self.GRID), world, hit, 288.0)
        self.assertEqual(sorted(old - got), [10, 11])


if __name__ == '__main__':
    unittest.main()
