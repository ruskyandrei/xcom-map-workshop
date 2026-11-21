"""Made walls and floors of any size cut into pieces the game takes (made_split.py; custom geometry editing plan, B4,
decision D-3): where the cuts fall, how a tall wall stacks, and the texture going on across a cut (frac_wall's and
frac_slab's `whole`)."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import frac_slab  # noqa: E402
import frac_wall  # noqa: E402
import looks  # noqa: E402
import made_split  # noqa: E402

T = made_split.TILE
DONOR = dict(mesh='AbductorExtWall.Meshes.AbductorExtWallA_FRACTURED', measure=1)     # (in the catalogue: two storeys)


def bar_storeys(wall):
    return 2, True


def bar_heights(wall):
    R = frac_wall.shaped(wall)
    return R['bottom'], R['top']


class CutTests(unittest.TestCase):
    def test_levels(self):
        # a look's own storeys and one storey are one piece; taller, its own stacked, then one-storey pieces, or its
        # own once more where it can't be made one storey
        self.assertEqual(made_split.levels(2, 2, True), [2])
        self.assertEqual(made_split.levels(1, 2, True), [1])
        self.assertEqual(made_split.levels(4, 2, True), [2, 2])
        self.assertEqual(made_split.levels(5, 2, True), [2, 2, 1])
        self.assertEqual(made_split.levels(2, 3, True), [1, 1])
        self.assertEqual(made_split.levels(5, 3, False), [3, 3])
        self.assertEqual(made_split.levels(3, 1, False), [1, 1, 1])

    def test_cuts_fall_on_tile_edges_outside_the_gaps(self):
        self.assertEqual(made_split.cuts(16 * T, []), [])
        self.assertEqual(made_split.cuts(40 * T, []), [16 * T, 32 * T])
        # a gap over tiles 15 and 16 moves the first cut to its start
        self.assertEqual(made_split.cuts(40 * T, [(15 * T, 17 * T)]), [15 * T, 31 * T])
        # a gap longer than a piece: cut through it at 16, then as far as goes past it
        self.assertEqual(made_split.cuts(40 * T, [(0.5 * T, 30 * T)]), [16 * T, 32 * T])

    def test_a_wall_no_cut_leaves_is_as_it_is(self):
        wall = dict(x0=-96.0, x1=384.0, openings=[], seed=3, ends=['through', 'free'])
        self.assertEqual(made_split.wall_pieces(wall, bar_storeys, bar_heights, ends=True), [(0.0, 0.0, wall)])

    def test_a_long_tall_wall(self):
        # 20 tiles, three storeys, a gap over tiles 12 to 19 across the first storey's top: cut at the gap's start
        # (16 falls in it), two lengths by two levels (two storeys, then one 400 up, the lower piece's height), the gap
        # cut to the pieces it falls in
        gap = dict(x0=12 * T, x1=20 * T, z0=300.0, z1=500.0)
        wall = dict(x0=0.0, x1=20 * T, openings=[gap], seed=7, storeys=3, ends=['free', 'through'])
        pieces = made_split.wall_pieces(wall, bar_storeys, bar_heights, ends=True)
        self.assertEqual([(dx, dz) for dx, dz, _ in pieces], [(0.0, 0.0), (12 * T, 0.0), (0.0, 400.0), (12 * T, 400.0)])
        self.assertEqual([n['x1'] for _, _, n in pieces], [12 * T, 8 * T, 12 * T, 8 * T])
        self.assertEqual([n.get('storeys') for _, _, n in pieces], [None, None, 1, 1])
        self.assertEqual([n['openings'] for _, _, n in pieces], [
            [], [dict(x0=0.0, x1=8 * T, z0=300.0, z1=384.0)], [], [dict(x0=0.0, x1=8 * T, z0=-16.0, z1=100.0)]])
        self.assertEqual([n['ends'] for _, _, n in pieces], [['free', 'line'], ['line', 'through']] * 2)
        self.assertEqual([n['whole'] for _, _, n in pieces], [[0.0, 20 * T], [12 * T, 20 * T]] * 2)
        self.assertEqual(len({n['seed'] for _, _, n in pieces}), 4)
        for _, _, n in pieces:
            frac_wall.build(n)

    def test_a_piece_a_gap_takes_whole_is_no_piece(self):
        gap = dict(x0=16 * T, x1=20 * T, z0=-100.0, z1=1000.0)
        wall = dict(x0=0.0, x1=20 * T, openings=[gap], seed=7)
        self.assertEqual([dx for dx, _, _ in made_split.wall_pieces(wall, bar_storeys, bar_heights)], [0.0])

    def test_a_large_slab(self):
        hole = dict(x0=15 * T, x1=17 * T, y0=0.0, y1=T)
        slab = dict(x0=0.0, x1=30 * T, y0=0.0, y1=20 * T, holes=[hole], seed=4, look='floor')
        pieces = made_split.slab_pieces(slab)
        self.assertEqual([(dx, dy) for dx, dy, _ in pieces], [(0.0, 0.0), (15 * T, 0.0), (0.0, 16 * T), (15 * T, 16 * T)])
        self.assertEqual([n['holes'] for _, _, n in pieces], [[], [dict(x0=0.0, x1=2 * T, y0=0.0, y1=T)], [], []])
        self.assertTrue(all(n['look'] == 'floor' for _, _, n in pieces))
        for _, _, n in pieces:
            frac_slab.check(n)
        self.assertEqual(made_split.slab_pieces(dict(slab, x1=16 * T, y1=16 * T, holes=[])),
                         [(0.0, 0.0, dict(slab, x1=16 * T, y1=16 * T, holes=[]))])


    def test_overlapping_holes_drop_only_the_pieces_they_take_whole(self):
        # (review finding 32) 17 by 1 tiles, holes over tiles 0 to 9 and 0 to 8: their areas add up to more than the
        # first 16-tile piece's, yet its tiles 10 to 15 are solid, and it stays; a piece the holes take whole goes
        holes = [dict(x0=0.0, x1=10 * T, y0=0.0, y1=T), dict(x0=0.0, x1=9 * T, y0=0.0, y1=T)]
        slab = dict(x0=0.0, x1=17 * T, y0=0.0, y1=T, holes=holes, seed=2)
        pieces = made_split.slab_pieces(slab)
        self.assertEqual([(dx, n['x1']) for dx, _, n in pieces], [(0.0, 16 * T), (16 * T, T)])
        self.assertEqual(pieces[0][2]['holes'], holes)
        self.assertEqual(frac_slab.tiles(pieces[0][2]), {(i, 0) for i in range(10, 16)})
        self.assertTrue(made_split.slab_left(slab))
        self.assertFalse(made_split.slab_left(dict(slab, holes=holes + [dict(x0=8 * T, x1=17 * T, y0=0.0, y1=T)])))
        self.assertFalse(made_split.slab_pieces(dict(slab, holes=holes + [dict(x0=8 * T, x1=17 * T, y0=0.0, y1=T)])))


class OldNumbersTests(unittest.TestCase):
    """Numbers before the free form (no `free`) are cut as they were: the pieces of a tall wall, a long wall and a
    large slab hashed on the commit the free form started from (495bd26, custom geometry improvements plan, stage 2)."""

    def test_old_cuts_are_byte_for_byte(self):
        import hashlib
        gap = dict(x0=12 * T, x1=20 * T, z0=300.0, z1=500.0)
        tall = dict(x0=0.0, x1=20 * T, openings=[gap], seed=7, storeys=3, ends=['free', 'through'])
        long = dict(x0=96.0, x1=96.0 + 37 * T, openings=[dict(x0=1500.0, x1=1700.0, z0=-16.0, z1=160.0)], seed=9)
        slab = dict(x0=0.0, x1=30 * T, y0=0.0, y1=20 * T, holes=[dict(x0=15 * T, x1=17 * T, y0=0.0, y1=T)], seed=4,
                    look='floor')
        for name, pieces, want in (
                ('tall', made_split.wall_pieces(tall, bar_storeys, bar_heights, ends=True),
                 '0be2701b06a1233a84f320f1c7979b0efcc7193c7e0a1cab926caca76c155527'),
                ('long', made_split.wall_pieces(long, bar_storeys, bar_heights),
                 'fb30580c5ba808533ab827a27a0a4ef7a5a7420ad574463d9d9a510e3cd6613d'),
                ('slab', made_split.slab_pieces(slab), '17a33ab9552493c79016825383dc68de77db21b85e2eae923cbadfb6673736cf')):
            with self.subTest(name):
                self.assertEqual(hashlib.sha256(repr(pieces).encode()).hexdigest(), want)


class TextureTests(unittest.TestCase):
    """A piece's texture goes on from where it sits in the whole (`whole`): its faces read as the whole's would at
    the same place."""

    def face_uvs(self, built, R):
        """[(x, u)] of side A's face vertices (normal +y, on the face's plane)."""
        lod = built['mesh']['lods'][0]
        return [(p[0], v[2][0][0]) for p, v in zip(lod['positions'], lod['vertices'])
                if v[1][1] > 250 and abs(p[1] - R['half']) < 1e-3 and R['face'][0] + 1 < p[2] < R['face'][1] - 1]

    def test_a_bar_wall_piece_goes_on_from_its_start(self):
        R = frac_wall.RECIPE
        start = 7 * T
        piece = frac_wall.build(dict(x0=0.0, x1=4 * T, openings=[], seed=2, whole=[start, 20 * T]))
        got = self.face_uvs(piece, R)
        self.assertGreater(len(got), 4)
        for x, u in got:
            self.assertAlmostEqual(u, (x + start) / R['faceRepeat'] + R['faceU'], delta=1e-3, msg=x)
        self.assertEqual(piece['whole'], [start, 20 * T])

    def test_a_measured_wall_piece_reads_its_profile_at_its_place(self):
        look = looks.resolve('wall', DONOR)
        start = 5 * T
        plain = frac_wall.Profile(frac_wall.shaped(dict(x0=0.0, x1=4 * T, look=look)))
        piece = frac_wall.Profile(frac_wall.shaped(dict(x0=0.0, x1=4 * T, look=look, whole=[start, 12 * T])))
        for X in 'AB':
            for k in range(len(plain.sides[X]) - 1):
                z = (plain.sides[X][k][1] + plain.sides[X][k + 1][1]) / 2
                slot, tex = plain.surface(X, k, z)
                slot2, tex2 = piece.surface(X, k, z)
                self.assertEqual(slot, slot2)
                for x in (0.0, 50.0, 300.0):
                    self.assertEqual(tex2(x, z, 0.5), tex(x + start, z, 0.5))
        frac_wall.build(dict(x0=0.0, x1=4 * T, look=look, seed=3, whole=[start, 12 * T]))

    def test_a_slab_piece_goes_on_from_its_corner(self):
        # the slab's top at a place in the piece reads as the whole slab's at the same place
        whole = frac_slab.build(dict(x0=0.0, x1=8 * T, y0=0.0, y1=4 * T, holes=[], seed=1))
        piece = frac_slab.build(dict(x0=0.0, x1=4 * T, y0=0.0, y1=2 * T, holes=[], seed=1,
                                     whole=[4 * T, 2 * T, 8 * T, 4 * T]))

        def top(built, dx=0.0, dy=0.0):
            lod = built['mesh']['lods'][0]
            return {(round(p[0] + dx, 2), round(p[1] + dy, 2)): v[2][0]
                    for p, v in zip(lod['positions'], lod['vertices']) if v[1][2] > 250}
        a, b = top(whole), top(piece, 4 * T, 2 * T)
        shared = set(a) & set(b)
        self.assertGreater(len(shared), 4)
        for key in shared:
            self.assertAlmostEqual(a[key][0], b[key][0], delta=1e-3, msg=key)
            self.assertAlmostEqual(a[key][1], b[key][1], delta=1e-3, msg=key)


if __name__ == '__main__':
    unittest.main()
