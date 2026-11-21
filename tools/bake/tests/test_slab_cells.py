"""A free-form slab's fragments and collision (slab_cells.py; custom geometry improvements plan, 4.3 and 10.2, and
stage 1's experiment: a partial slab builds with its collision cut right): cells of a lattice counted from the frame's
origin, cut by the footprint and the holes into convex polygons that cover the solid area exactly and meet corner to
corner; whole cells patterned from a hash, so a size change re-rolls only the cells near the cut; thin pieces joined to
their neighbours; collision over the solid area only, moved with the plate."""
import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import frac_slab  # noqa: E402
import slab_cells  # noqa: E402
from free_form import NumbersError  # noqa: E402

ROOF = frac_slab.look_of(dict(look='roof'))         # bottom -2, top 2, collision [-2, 0]: 2 under its top
FLOOR = frac_slab.look_of(dict(look='floor'))       # the plate whole
# a fractional footprint off the tile edges, a hole crossing a tile edge, one inside a tile, one at the slab's edge
PARTIAL = dict(free=1, x0=10.5, x1=500.25, y0=-30.0, y1=260.75, z0=-2.0, z1=2.0, seed=4,
               holes=[dict(x0=150.0, x1=230.0, y0=40.0, y1=70.0), dict(x0=300.0, x1=330.0, y0=120.0, y1=150.0),
                      dict(x0=10.5, x1=60.0, y0=200.0, y1=260.75)])


def layout(slab, R=ROOF):
    return slab_cells.FreeSlab(slab, R)


def solid_area(slab):
    """The footprint's area less the holes' union (by a grid of every side)."""
    holes = slab.get('holes') or []
    xs = sorted({slab['x0'], slab['x1']} | {h[k] for h in holes for k in ('x0', 'x1')})
    ys = sorted({slab['y0'], slab['y1']} | {h[k] for h in holes for k in ('y0', 'y1')})
    total = 0.0
    for a, b in zip(xs, xs[1:]):
        for c, d in zip(ys, ys[1:]):
            m, n = (a + b) / 2, (c + d) / 2
            if not any(h['x0'] < m < h['x1'] and h['y0'] < n < h['y1'] for h in holes):
                total += (b - a) * (d - c)
    return total


def overlap(box, hole):
    (x0, y0, _), (x1, y1, _) = box
    return max(0.0, min(x1, hole['x1']) - max(x0, hole['x0'])) * max(0.0, min(y1, hole['y1']) - max(y0, hole['y0']))


def polys_of(frags):
    return [poly for polys in frags for poly in polys]


class Coverage(unittest.TestCase):
    """Stage 1's experiment: a partial slab (a fractional footprint, a hole crossing a tile) cut right."""

    CASES = (PARTIAL,
             dict(free=1, x0=0.0, x1=40.0, y0=0.0, y1=25.5, z0=0.0, z1=4.0),                       # under a tile
             dict(free=1, x0=-100.0, x1=100.0, y0=-50.0, y1=146.0, z0=0.0, z1=4.0, seed=9,
                  holes=[dict(x0=-10.0, x1=10.0, y0=-50.0, y1=146.0)]),                            # cut in two
             dict(free=1, x0=0.0, x1=384.0, y0=0.0, y1=384.0, z0=0.0, z1=4.0, seed=2,
                  holes=[dict(x0=90.0, x1=200.0, y0=90.0, y1=200.0), dict(x0=150.0, x1=300.0, y0=150.0, y1=250.0)]))

    def test_the_fragments_cover_exactly_the_solid_area(self):
        for slab in self.CASES:
            frags = layout(slab).fragments()
            polys = polys_of(frags)
            self.assertAlmostEqual(sum(slab_cells.area(p) for p in polys), solid_area(slab), 6, slab)
            for poly in polys:
                self.assertGreater(slab_cells.area(poly), 0)
                c = (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
                for h in slab.get('holes') or []:
                    self.assertFalse(h['x0'] < c[0] < h['x1'] and h['y0'] < c[1] < h['y1'], (poly, h))
                for p in poly:
                    self.assertTrue(slab['x0'] <= p[0] <= slab['x1'] and slab['y0'] <= p[1] <= slab['y1'])

    def test_the_collision_covers_the_solid_area_and_no_hole(self):
        for slab in self.CASES:
            boxes = layout(slab).solids()
            self.assertAlmostEqual(sum((b[1][0] - b[0][0]) * (b[1][1] - b[0][1]) for b in boxes), solid_area(slab), 6)
            for box in boxes:
                for h in slab.get('holes') or []:
                    self.assertEqual(overlap(box, h), 0.0, (box, h))
            # (the boxes don't overlap each other: their areas add up to the solid area, which they all lie in)

    def test_every_face_is_convex_anticlockwise_and_meets_its_neighbours_corner_to_corner(self):
        for slab in self.CASES:
            polys = polys_of(layout(slab).fragments())
            corners = {p for poly in polys for p in poly}
            for poly in polys:
                n = len(poly)
                turns = [slab_cells._turn(poly[k - 1], poly[k], poly[(k + 1) % n]) for k in range(n)]
                self.assertTrue(all(t >= -1e-9 for t in turns), poly)              # convex, anticlockwise
                self.assertFalse(slab_cells._in_line(poly[0], poly[1], poly[2]))   # the tangent's corners
                for k in range(n):
                    a, b = poly[k], poly[(k + 1) % n]
                    for c in corners:
                        if c in (a, b):
                            continue
                        s = ((c[0] - a[0]) * (b[0] - a[0]) + (c[1] - a[1]) * (b[1] - a[1])) / math.dist(a, b) ** 2
                        off = abs((c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0])) / math.dist(a, b)
                        self.assertFalse(0 < s < 1 and off < 1e-6, ('a corner on a side', poly, c))

    def test_a_cell_a_hole_cuts_in_two_is_two_fragments_an_l_one(self):
        # the hole x 140 to 180 spans the cell (96..192) from y 0 to 96: the cell's two sides are two fragments
        slab = dict(free=1, x0=0.0, x1=288.0, y0=0.0, y1=96.0, z0=0.0, z1=4.0, holes=[dict(x0=140.0, x1=180.0, y0=0.0, y1=96.0)])
        frags = layout(slab, FLOOR).fragments()
        middle = [f for f in frags if all(96.0 <= p[0] <= 192.0 for poly in f for p in poly)]
        self.assertEqual(len(middle), 2)
        # a corner hole leaves an L: one fragment, two faces
        slab = dict(free=1, x0=0.0, x1=96.0, y0=0.0, y1=96.0, z0=0.0, z1=4.0, holes=[dict(x0=40.0, x1=96.0, y0=40.0, y1=96.0)])
        (only,) = layout(slab, FLOOR).fragments()
        self.assertEqual(len(only), 2)


class Lattice(unittest.TestCase):
    def test_cells_are_counted_from_the_frames_origin(self):
        cells = layout(PARTIAL).cells()
        self.assertEqual(min(cells), (0, -1))
        self.assertEqual(cells[(0, -1)][:4], (10.5, 96.0, -30.0, 0.0))
        self.assertEqual(cells[(5, 2)][:4], (480.0, 500.25, 192.0, 260.75))
        self.assertTrue(cells[(2, 1)][4])                  # 192..288 by 96..192: whole
        self.assertFalse(cells[(1, 0)][4])                 # the hole at 150..230 by 40..70 cuts it
        self.assertFalse(cells[(2, 0)][4])

    def test_a_split_piece_reads_the_whole_slabs_lattice(self):
        whole = dict(free=1, x0=0.0, x1=1536.0, y0=0.0, y1=960.0, z0=0.0, z1=4.0, seed=8)
        # the right half as a piece in its own frame, its place 768 along
        piece = dict(whole, x0=0.0, x1=768.0, whole=[768.0, 0.0, 1536.0, 960.0])
        frags_whole = {tuple(map(tuple, p)) for p in polys_of(layout(whole).fragments())}
        moved = {tuple((x + 768.0, y) for x, y in p) for p in polys_of(layout(piece).fragments())}
        # every cell of the piece but those its cut edge's pairs reach is the whole slab's, the same pattern
        far = {p for p in moved if min(x for x, _ in p) >= 768.0 + 2 * 96.0}
        self.assertTrue(far)
        self.assertLessEqual(far, frags_whole)
        # the whole's corner in its own frame, where it is not the origin: the lattice stays the frame's
        shifted = dict(piece, whole=[700.0, 0.0, 1536.0, 960.0, 68.0, 0.0])
        self.assertEqual(slab_cells.origin(shifted), (768.0, 0.0))
        self.assertEqual(layout(shifted).fragments(), layout(piece).fragments())

    def test_a_size_change_re_rolls_only_the_cells_near_the_cut(self):
        base = dict(free=1, x0=-40.0, x1=1000.0, y0=0.0, y1=700.0, z0=0.0, z1=4.0, seed=12,
                    holes=[dict(x0=300.0, x1=420.0, y0=200.0, y1=260.0)])
        before = {tuple(p) for p in polys_of(layout(base).fragments())}
        for x1 in (1000.5, 1040.0, 1250.0, 1536.0):
            after = {tuple(p) for p in polys_of(layout(dict(base, x1=x1)).fragments())}
            # the old edge's cell starts at 960; the cells within two of it (from 768) may change, none before
            keep = {p for p in before if max(x for x, _ in p) <= 768.0}
            self.assertTrue(keep)
            self.assertLessEqual(keep, after, x1)
        # the near side too: x0 moved, the cells far from it stay
        after = {tuple(p) for p in polys_of(layout(dict(base, x0=-100.25)).fragments())}
        self.assertLessEqual({p for p in before if min(x for x, _ in p) >= 192.0}, after)

    def test_the_seed_and_the_shares_choose_the_pattern(self):
        slab = dict(free=1, x0=0.0, x1=960.0, y0=0.0, y1=960.0, z0=0.0, z1=4.0, seed=1)
        a = layout(slab).fragments()
        self.assertEqual(a, layout(dict(slab)).fragments())
        self.assertNotEqual(a, layout(dict(slab, seed=2)).fragments())
        tiles = layout(slab, dict(ROOF, split=0.0, long=0.0)).fragments()
        self.assertEqual(len(tiles), 100)
        halves = layout(slab, dict(ROOF, split=1.0, long=0.0)).fragments()
        self.assertEqual(len(halves), 200)
        self.assertTrue(all(len(f) == 1 and len(f[0]) == 3 for f in halves))
        pairs = layout(slab, dict(ROOF, split=0.0, long=1.0)).fragments()
        self.assertLess(len(pairs), 70)

    def test_about_the_old_slabs_fragments_a_tile_for_the_same_shares(self):
        # (the looks' shares were fitted on the old slabs' fragments: slab_measure.shares)
        for split, long_ in ((0.35, 0.3), (0.2, 0.4), (0.0, 0.4), (0.1, 0.8)):
            R = dict(ROOF, split=split, long=long_)
            look = dict(mesh='(shares)', measure=1, recipe=R)
            old = sum(len(frac_slab.fragments(dict(x0=0.0, x1=1536.0, y0=0.0, y1=1536.0, seed=s, look=look)))
                      for s in range(1, 11))
            new = sum(len(layout(dict(free=1, x0=0.0, x1=1536.0, y0=0.0, y1=1536.0, z0=0.0, z1=4.0, seed=s), R)
                          .fragments()) for s in range(1, 11))
            self.assertLess(abs(new / old - 1), 0.08, (split, long_, old, new))


class ThinPieces(unittest.TestCase):
    def test_a_sliver_at_the_edge_joins_its_neighbour(self):
        # x1 4 past a tile edge: each 4-wide piece joins the fragment beside it (one convex face where it can)
        slab = dict(free=1, x0=0.0, x1=196.0, y0=0.0, y1=192.0, z0=0.0, z1=4.0, seed=3)
        frags = layout(slab, dict(ROOF, split=0.0, long=0.0)).fragments()
        self.assertEqual(len(frags), 4)
        for f in frags:
            xs = [p[0] for poly in f for p in poly]
            self.assertGreater(max(xs) - min(xs), 8.0)
        right = [f for f in frags if max(p[0] for poly in f for p in poly) == 196.0]
        self.assertEqual(len(right), 2)
        self.assertTrue(all(len(f) == 1 for f in right))           # 96 + 4 wide: one rectangle
        # a slab thinner than the least width all along is still built, its pieces their own
        thin = dict(free=1, x0=0.0, x1=5.0, y0=0.0, y1=300.0, z0=0.0, z1=4.0)
        frags = layout(thin).fragments()
        self.assertEqual(len(frags), 4)
        self.assertAlmostEqual(sum(slab_cells.area(p) for p in polys_of(frags)), 1500.0)

    def test_a_sliver_a_hole_leaves_joins_the_fragment_beside_it(self):
        slab = dict(free=1, x0=0.0, x1=288.0, y0=0.0, y1=96.0, z0=0.0, z1=4.0, seed=3,
                    holes=[dict(x0=100.0, x1=187.0, y0=0.0, y1=96.0)])
        frags = layout(slab, dict(ROOF, split=0.0, long=0.0)).fragments()
        # the 4-wide sliver (96..100) joins the cell left of it, the 5-wide one (187..192) the cell right of it
        self.assertEqual(len(frags), 2)
        self.assertEqual(sorted((min(p[0] for poly in f for p in poly), max(p[0] for poly in f for p in poly))
                                for f in frags), [(0.0, 100.0), (187.0, 288.0)])


class Heights(unittest.TestCase):
    def test_the_collision_keeps_its_distances_from_the_plate(self):
        # the roof's 2 under its drawn top: thickened downwards, its bottom follows the underside
        self.assertEqual(layout(dict(PARTIAL, z0=-30.0, z1=2.0)).collision, (-30.0, 0.0))
        self.assertEqual(layout(dict(PARTIAL, z0=100.0, z1=110.0)).collision, (100.0, 108.0))
        # a plate thinner than that keeps its whole plate
        self.assertEqual(layout(dict(PARTIAL, z0=0.0, z1=1.5)).collision, (0.0, 1.5))
        # the floor's is its whole plate
        self.assertEqual(layout(dict(PARTIAL, z0=150.0, z1=200.0), FLOOR).collision, (150.0, 200.0))
        self.assertEqual({(b[0][2], b[1][2]) for b in layout(dict(PARTIAL, z0=-30.0, z1=2.0)).solids()}, {(-30.0, 0.0)})


class Refusals(unittest.TestCase):
    def test_bad_numbers_are_refused_with_their_reason(self):
        for change, code in ((dict(x1=10.5), 'extent'), (dict(z1=-3.0), 'extent'), (dict(y0=math.nan), 'number'),
                             (dict(seed=1.5), 'number'), (dict(seed=True), 'number'),
                             (dict(holes=[dict(x0=0.0, x1=50.0, y0=0.0, y1=10.0)]), 'hole'),
                             (dict(holes=[dict(x0=20.0, x1=20.0, y0=0.0, y1=10.0)]), 'extent'),
                             (dict(holes=[7]), 'hole'), (dict(holes='none'), 'hole'),
                             (dict(holes=[dict(x0=10.5, x1=500.25, y0=-30.0, y1=260.75)]), 'left'),
                             (dict(holes=[dict(x0=10.5, x1=300.0, y0=-30.0, y1=260.75),
                                          dict(x0=250.0, x1=500.25, y0=-30.0, y1=260.75)]), 'left'),
                             (dict(whole=[1.0, 2.0]), 'whole'), (dict(whole=[1.0, 2.0, 0.0, 5.0]), 'whole'),
                             (dict(mapping='brick'), 'mapping')):
            with self.assertRaises(NumbersError) as e:
                layout(dict(PARTIAL, **change))
            self.assertEqual(e.exception.code, code, change)
            self.assertIsInstance(e.exception, ValueError)

    def test_holes_touching_the_edges_and_each_other(self):
        # a hole a hair inside the edge reaches it (no sliver of a thousandth); holes meeting or overlapping
        slab = dict(free=1, x0=0.0, x1=192.0, y0=0.0, y1=96.0, z0=0.0, z1=4.0,
                    holes=[dict(x0=0.0005, x1=50.0, y0=0.0, y1=40.0), dict(x0=50.0, x1=80.0, y0=0.0, y1=40.0),
                           dict(x0=70.0, x1=120.0, y0=20.0, y1=60.0)])
        lay = layout(slab, FLOOR)
        self.assertEqual(lay.holes[0][0], 0.0)
        frags = lay.fragments()
        expect = 192.0 * 96.0 - 80.0 * 40.0 - (120.0 - 80.0) * 40.0 - (80.0 - 70.0) * 20.0
        self.assertAlmostEqual(sum(slab_cells.area(p) for p in polys_of(frags)), expect, 6)
        self.assertAlmostEqual(sum((b[1][0] - b[0][0]) * (b[1][1] - b[0][1]) for b in lay.solids()), expect, 6)


if __name__ == '__main__':
    unittest.main()
