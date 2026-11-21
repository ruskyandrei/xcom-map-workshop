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


def bar_look_storeys(numbers):
    """(the look's own storeys, whether it can be made one storey) of a look alone: the Bar look's, or a resolved
    measured look's (as the mesh server's wall_look_storeys)."""
    own = frac_wall.storeys_of(frac_wall.look_of(numbers))
    return max(own), max(own) > 1 and 1 in own


def boxes_of(built, dx=0.0, dz=0.0):
    return {tuple(round(v, 2) for v in (b[0] + dx, b[1] + dx, b[2], b[3], b[4] + dz, b[5] + dz))
            for b in (f['box'] for f in built['fragments'])}


class FreeCutTests(unittest.TestCase):
    """(Custom geometry improvements plan, stage 2) Free-form numbers cut at any size: tile edges from the frame's
    origin, a narrow tail sharing the cut before it, tall walls stacked ('repeat') or cut into bands of one stretched
    outline ('stretch'), the whole's seed and place in every piece."""

    def test_cuts_fall_on_the_frames_tile_edges(self):
        # a run from 13.5: cuts at 1536 and 3072 (whole tiles from the frame's origin, 16 apart at most), the tail
        # whatever is left
        self.assertEqual(made_split.free_cuts(13.5, 3400.25, []), [16 * T, 32 * T])
        self.assertEqual(made_split.free_cuts(13.5, 1549.0, []), [])
        # an opening over the cut moves it back to the nearest edge outside it
        self.assertEqual(made_split.free_cuts(0.0, 2000.0, [(1400.0, 1600.0)]), [14 * T])
        # a tail under MIN_PIECE (30 past 1536) shares the cut before it, which moves back a tile
        self.assertEqual(made_split.free_cuts(0.0, 16 * T + 30.0, []), [15 * T])
        self.assertEqual(made_split.free_cuts(-200.25, 13 * T + 16 * T + 20.0, []), [13 * T, 28 * T])
        for lo, hi in ((0.0, 5000.0), (-777.7, 9000.3), (5.0, 1600.0)):
            xs = [lo] + made_split.free_cuts(lo, hi, []) + [hi]
            self.assertTrue(all(b - a <= made_split.MAX_TILES * T + 1e-9 and b - a >= made_split.MIN_PIECE
                                for a, b in zip(xs, xs[1:])), xs)
            self.assertTrue(all(abs(c / T - round(c / T)) < 1e-9 for c in xs[1:-1]), xs)

    def test_a_long_free_wall_is_cut_along(self):
        gap = dict(x0=1500.25, x1=1650.5, z0=-16.0, z1=160.0)
        wall = dict(free=1, x0=13.25, x1=13.25 + 2000.0, y0=-6.0, y1=10.0, z0=-16.0, z1=384.0, seed=7, openings=[gap],
                    ends=['free', dict(inset=0.0, lean=1.0)], mapping=dict(surfaces={}))
        pieces = made_split.wall_pieces(wall, bar_look_storeys, bar_heights, ends=True)
        # (the cut at 1536 falls in the gap: at 1440, the nearest tile edge outside it)
        self.assertEqual([dx for dx, _, _ in pieces], [0.0, 15 * T - 13.25])
        self.assertEqual([n['x1'] for _, _, n in pieces], [15 * T - 13.25, 2013.25 - 15 * T])
        self.assertEqual([n['whole'] for _, _, n in pieces], [[0.0, 2000.0, 0.0, 400.0, 13.25],
                                                             [15 * T - 13.25, 2000.0, 0.0, 400.0, 13.25]])
        self.assertEqual({n['seed'] for _, _, n in pieces}, {7})
        self.assertTrue(all(n['free'] == 1 and n['y0'] == -6.0 and n['mapping'] == dict(surfaces={}) for _, _, n in pieces))
        self.assertEqual([n['openings'] for _, _, n in pieces],
                         [[], [dict(x0=1500.25 - 15 * T, x1=1650.5 - 15 * T, z0=-16.0, z1=160.0)]])
        self.assertEqual([n.get('ends') for _, _, n in pieces], [['free', 'line'], ['line', dict(inset=0.0, lean=1.0)]])
        for _, _, n in pieces:
            frac_wall.check_free(n)
        # unsplit, a free wall is as it is
        short = dict(wall, x1=500.0, openings=[])
        self.assertEqual(made_split.wall_pieces(short, bar_look_storeys, bar_heights), [(0.0, 0.0, short)])

    def test_a_piece_has_the_wholes_cells_and_texture_where_it_is(self):
        # cut at 1536: away from the cut, each piece's fragments are the whole wall's (built unsplit) where it stands
        wall = dict(free=1, x0=0.0, x1=2400.0, seed=11)
        whole = boxes_of(frac_wall.build(wall))
        pieces = made_split.wall_pieces(wall, bar_look_storeys, bar_heights)
        self.assertEqual(len(pieces), 2)
        for dx, dz, n in pieces:
            mine = boxes_of(frac_wall.build(n), dx, dz)
            inner = {b for b in mine if b[0] > dx + 150 and b[1] < dx + n['x1'] - 150}
            self.assertGreater(len(inner), 10)
            self.assertLessEqual(inner, whole)

    def test_repeat_stacks_the_looks_height_with_no_sliver(self):
        self.assertEqual(made_split.repeat_heights(400.0, 400.0, 200.0), [400.0])
        self.assertEqual(made_split.repeat_heights(1200.0, 400.0, 200.0), [400.0, 400.0, 400.0])
        self.assertEqual(made_split.repeat_heights(900.0, 400.0, 200.0), [400.0, 500.0])
        self.assertEqual(made_split.repeat_heights(700.0, 400.0, 200.0), [400.0, 300.0])
        self.assertEqual(made_split.repeat_heights(590.0, 400.0, 200.0), [590.0])
        self.assertEqual(made_split.repeat_heights(250.0, 400.0, 200.0), [250.0])
        wall = dict(free=1, x0=0.0, x1=500.0, z0=-16.0, z1=884.0, seed=3, tall='repeat',
                    openings=[dict(x0=100.0, x1=200.0, z0=300.0, z1=500.0)])
        pieces = made_split.wall_pieces(wall, bar_look_storeys, bar_heights)
        self.assertEqual([(dz, n['z0'], n['z1'], n.get('band')) for _, dz, n in pieces],
                         [(0.0, -16.0, 384.0, None), (400.0, -16.0, 484.0, None)])
        self.assertEqual([n['openings'] for _, _, n in pieces], [[dict(x0=100.0, x1=200.0, z0=300.0, z1=384.0)],
                                                                [dict(x0=100.0, x1=200.0, z0=-16.0, z1=100.0)]])
        self.assertEqual([n['whole'] for _, _, n in pieces], [[0.0, 500.0, 0.0, 900.0, 0.0], [0.0, 500.0, 400.0, 900.0, 0.0]])
        for dx, dz, n in pieces:
            zs = [p[2] + dz for p in frac_wall.build(n)['mesh']['lods'][0]['positions']]
            self.assertEqual((min(zs), max(zs)), (-16.0 + dz, n['z1'] + dz))
        # each stacked piece is the look's own: its texture in its own frame, the cornice on top of each
        self.assertNotIn('uvShiftZ', frac_wall.shaped(pieces[1][2]))

    def test_stretch_cuts_one_outline_into_bands(self):
        self.assertEqual([made_split.stretch_bands(h, 400.0) for h in (300.0, 800.0, 801.0, 1200.0, 1201.0)], [1, 1, 3, 3, 4])
        wall = dict(free=1, x0=0.0, x1=500.0, z0=-16.0, z1=1184.0, seed=3, tall='stretch',
                    openings=[dict(x0=100.0, x1=200.0, z0=300.0, z1=500.0)])
        pieces = made_split.wall_pieces(wall, bar_look_storeys, bar_heights)
        self.assertEqual([(dz, n['z0'], n['z1'], n['band']) for _, dz, n in pieces],
                         [(0.0, -16.0, 1184.0, [-16.0, 384.0]), (400.0, -416.0, 784.0, [-16.0, 384.0]),
                          (800.0, -816.0, 384.0, [-16.0, 384.0])])
        self.assertEqual([n['openings'] for _, _, n in pieces], [[dict(x0=100.0, x1=200.0, z0=300.0, z1=384.0)],
                                                                [dict(x0=100.0, x1=200.0, z0=-16.0, z1=100.0)], []])
        # the bands together are the stretched wall built whole: its cells and its faces' texture where they stand
        whole = frac_wall.build(dict(wall, openings=[]))
        cells = boxes_of(whole)
        R = frac_wall.RECIPE

        def face(built, dz):
            lod = built['mesh']['lods'][0]
            return {(round(p[0], 2), round(p[2] + dz, 2)): v[2][0] for p, v in zip(lod['positions'], lod['vertices'])
                    if abs(p[1] - R['half']) < 1e-3 and v[1][1] > 250}
        whole_face = face(whole, 0.0)
        for _, dz, n in pieces:
            built = frac_wall.build(dict(n, openings=[]))
            mine = boxes_of(built, 0.0, dz)
            inner = {b for b in mine if b[4] > dz + 84 and b[5] < dz + 300 and b[0] > 60 and b[1] < 440}
            self.assertGreater(len(inner), 2)
            self.assertLessEqual(inner, cells)
            shared = set(face(built, dz)) & set(whole_face)
            self.assertGreater(len(shared), 4)
            for key in shared:
                for a, b in zip(face(built, dz)[key], whole_face[key]):
                    self.assertLess(abs((a - b) - round(a - b)), 2e-3, key)
        # one band up to twice the look's height
        self.assertEqual(len(made_split.wall_pieces(dict(wall, z1=784.0), bar_look_storeys, bar_heights)), 1)

    def test_a_measured_look_stretches_and_repeats_by_its_own_height(self):
        look = looks.resolve('wall', DONOR)
        R = look['recipe']
        tall = float(R['top']) - float(R['bottom'])
        wall = dict(free=1, x0=0.0, x1=600.0, z0=0.0, z1=2.4 * tall, seed=3, look=look)
        self.assertEqual([round(dz, 3) for _, dz, _ in made_split.wall_pieces(wall, bar_look_storeys, bar_heights)],
                         [0.0, round(tall, 3)])
        pieces = made_split.wall_pieces(dict(wall, tall='stretch'), bar_look_storeys, bar_heights)
        self.assertEqual(len(pieces), 3)
        for _, _, n in pieces:
            sound = frac_wall.build(n)
            self.assertGreater(sound['counts']['fragments'], 3)

    def test_a_piece_an_opening_takes_whole_is_no_piece(self):
        wall = dict(free=1, x0=0.0, x1=1800.0, seed=3, openings=[dict(x0=1536.0, x1=1800.0, z0=-100.0, z1=1000.0)])
        self.assertEqual([dx for dx, _, _ in made_split.wall_pieces(wall, bar_look_storeys, bar_heights)], [0.0])

    def test_a_large_free_slab(self):
        hole = dict(x0=1400.5, x1=1600.0, y0=10.0, y1=50.0)
        slab = dict(free=1, x0=-20.5, x1=-20.5 + 2000.0, y0=0.0, y1=1536.0 + 30.0, z0=-2.0, z1=2.0, holes=[hole], seed=4,
                    look='floor')
        pieces = made_split.slab_pieces(slab)
        self.assertEqual([(dx, dy) for dx, dy, _ in pieces], [(0.0, 0.0), (14 * T + 20.5, 0.0), (0.0, 15 * T),
                                                             (14 * T + 20.5, 15 * T)])
        self.assertEqual([(n['x1'], n['y1']) for _, _, n in pieces],
                         [(14 * T + 20.5, 15 * T), (2000.0 - 14 * T - 20.5, 15 * T), (14 * T + 20.5, 126.0),
                          (2000.0 - 14 * T - 20.5, 126.0)])
        self.assertEqual(pieces[1][2]['whole'], [14 * T + 20.5, 0.0, 2000.0, 1566.0, -20.5, 0.0])
        self.assertEqual([n['holes'] for _, _, n in pieces], [[], [dict(x0=1400.5 - 14 * T, x1=1600.0 - 14 * T, y0=10.0,
                                                                        y1=50.0)], [], []])
        self.assertTrue(all(n['seed'] == 4 and n['free'] == 1 and (n['z0'], n['z1']) == (-2.0, 2.0) for _, _, n in pieces))
        for _, _, n in pieces:
            frac_slab.check_free(n)
        # a piece the holes cover is no piece (a hole longer than a piece: cut through it); the slab is left while any of
        # it is
        covering = dict(slab, holes=[dict(x0=-20.5, x1=1700.0, y0=0.0, y1=1566.0)])
        self.assertEqual([(dx, dy) for dx, dy, _ in made_split.slab_pieces(covering)], [(15 * T + 20.5, 0.0),
                                                                                       (15 * T + 20.5, 15 * T)])
        self.assertTrue(made_split.slab_left(covering))
        self.assertFalse(made_split.slab_left(dict(slab, holes=[dict(x0=-20.5, x1=1979.5, y0=0.0, y1=1566.0)])))
        # a sliver thinner than the slab generator's snap is none
        self.assertFalse(made_split.slab_left(dict(slab, holes=[dict(x0=-20.5, x1=1979.5 - 1e-3, y0=0.0, y1=1566.0)])))
        # a donor look not resolved here: the holes' own edges say
        donor = dict(mesh='Nowhere.Meshes.Floor_FRACTURED', measure=1)
        self.assertTrue(made_split.slab_left(dict(slab, look=donor)))
        self.assertFalse(made_split.slab_left(dict(slab, look=donor, holes=covering['holes'] + [
            dict(x0=1600.0, x1=1979.5, y0=0.0, y1=1566.0)])))
        # unsplit, a free slab is as it is
        small = dict(slab, x1=500.0, y1=500.0, holes=[])
        self.assertEqual(made_split.slab_pieces(small), [(0.0, 0.0, small)])


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
