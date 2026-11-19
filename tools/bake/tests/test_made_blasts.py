"""Made walls, floors and roofs built broken (made_blasts.py; custom geometry editing plan, B5): the blasts checked,
moved into a cut piece's frame, the fragments they knock out, the component's arrays as the game's maps save them,
and the mesh drawn without those fragments."""
from pathlib import Path
import math
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import frac_slab  # noqa: E402
import frac_wall  # noqa: E402
import made_blasts  # noqa: E402

WALL = dict(x0=0.0, x1=384.0, openings=[], seed=2)


class BlastTests(unittest.TestCase):
    def test_blasts_are_checked(self):
        good = [dict(at=[100, 0, 50], radius=96)]
        self.assertEqual(made_blasts.check(good), [dict(at=[100.0, 0.0, 50.0], radius=96.0)])
        for bad in ('x', [dict(at=[1, 2], radius=96)], [dict(at=[1, 2, 3], radius=4)], [dict(at=[1, 2, 3], radius=999)],
                    [dict(at=[1, 2, 3], radius=96, more=1)], [dict(at=[1, 2, float('nan')], radius=96)],
                    [dict(at=[1, 2, 3], radius=True)], good * (made_blasts.MAX_BLASTS + 1)):
            with self.assertRaises(ValueError, msg=bad):
                made_blasts.check(bad)

    def test_a_cut_piece_takes_the_blasts_that_reach_it_in_its_frame(self):
        blasts = [dict(at=[100.0, 0.0, 50.0], radius=96.0), dict(at=[1600.0, 0.0, 50.0], radius=96.0)]
        # the second piece starts 1536 along: the first blast is 1436 short of it, the second 64 into it
        self.assertEqual(made_blasts.for_piece(blasts, (1536.0, 0.0, 0.0), [(0.0, 768.0), None]),
                         [dict(at=[64.0, 0.0, 50.0], radius=96.0)])
        # one 50 short of its start still reaches it
        self.assertEqual(len(made_blasts.for_piece([dict(at=[1486.0, 0.0, 0.0], radius=96.0)], (1536.0, 0, 0),
                                                   [(0.0, 768.0), None])), 1)
        self.assertEqual(made_blasts.for_piece(blasts, (0.0, 0.0, 400.0)), [
            dict(at=[100.0, 0.0, -350.0], radius=96.0), dict(at=[1600.0, 0.0, -350.0], radius=96.0)])

    def test_the_fragments_within_a_blast_go(self):
        built = frac_wall.build(WALL)
        frags = built['mesh']['fractured']['fragments']
        self.assertEqual(made_blasts.hidden(built, []), [])
        blast = dict(at=[96.0, 12.0, 96.0], radius=96.0)
        gone = made_blasts.hidden(built, [blast])
        self.assertTrue(0 < len(gone) < len(frags))
        for i, f in enumerate(frags):
            self.assertEqual(i in gone, math.dist(f['centre'], blast['at']) <= 96.0)

    def test_the_arrays_are_the_games(self):
        built = frac_wall.build(WALL)
        n = len(built['mesh']['fractured']['fragments'])
        gone = made_blasts.hidden(built, [dict(at=[96.0, 0.0, 96.0], radius=96.0)])
        raw = made_blasts.visible_value(n, gone)
        count, *values = struct.unpack('<%di' % (n + 1), raw)
        self.assertEqual(count, n)
        self.assertEqual([k for k, v in enumerate(values) if v == 0], gone)
        self.assertEqual(set(values), {0, 1})
        chunks = made_blasts.chunks_value(built, gone)
        self.assertEqual(struct.unpack_from('<i', chunks)[0], len(gone))
        self.assertEqual(len(chunks), 4 + 25 * len(gone))
        for k, i in enumerate(gone):
            x0, y0, z0, x1, y1, z1, valid = struct.unpack_from('<6fB', chunks, 4 + 25 * k)
            box = built['fragments'][i]['box']
            for got, want in zip((x0, x1, y0, y1, z0, z1), box):
                self.assertAlmostEqual(got, want, places=3)
            self.assertEqual(valid, 1)

    def test_the_mesh_drawn_leaves_the_fragments_out(self):
        for built in (frac_wall.build(WALL), frac_slab.build(dict(x0=0.0, x1=384.0, y0=0.0, y1=288.0, holes=[], seed=4))):
            lod = built['mesh']['lods'][0]
            frags = built['mesh']['fractured']['fragments']
            centre = frags[len(frags) // 2]['centre']
            gone = made_blasts.hidden(built, [dict(at=list(centre), radius=60.0)])
            self.assertTrue(gone)
            kept = made_blasts.kept_indices(lod, gone)
            self.assertEqual([slot for slot, _ in kept], [s['slot'] for s in lod['sections']])
            want = sum(3 * t for s in lod['sections'] for i, (_, t) in enumerate(s['fragments']) if i not in gone)
            self.assertEqual(sum(len(k) for _, k in kept), want)
            self.assertLess(want, len(lod['indices'][1]))
            self.assertEqual(sum(len(k) for _, k in made_blasts.kept_indices(lod, [])), len(lod['indices'][1]))


class MapTests(unittest.TestCase):
    """(E6) The map's own fracturing pieces: a fragment's middle is that of its vertices' box, as the editor works it out
    from the mesh it draws; the map's saved painted fragments read in both of their forms; DestroyedChunks from the
    fragments' bounds."""

    def test_a_fragment_s_middle_is_that_of_its_vertices_box(self):
        built = frac_wall.build(WALL)
        lod = built['mesh']['lods'][0]
        n = len(built['mesh']['fractured']['fragments'])
        centres = made_blasts.fragment_centres(lod, n)
        self.assertEqual(len(centres), n)
        idx, pos = lod['indices'][1], lod['positions']
        for i in range(n):
            points = [pos[v] for s in lod['sections'] if i < len(s['fragments'])
                      for v in idx[s['fragments'][i][0]:s['fragments'][i][0] + 3 * s['fragments'][i][1]]]
            if not points:
                self.assertIsNone(centres[i])
                continue
            for k in range(3):
                self.assertAlmostEqual(centres[i][k], (min(p[k] for p in points) + max(p[k] for p in points)) / 2, places=4)
        # a fragment with no triangles has no middle
        empty = dict(lod, sections=[dict(s, fragments=[(f, 0) if i == 0 else (f, t) for i, (f, t) in enumerate(s['fragments'])])
                                    for s in lod['sections']])
        self.assertIsNone(made_blasts.fragment_centres(empty, n)[0])

    def test_the_fragments_whose_middle_a_blast_reaches_go(self):
        centres = [[0.0, 0.0, 0.0], None, [100.0, 0.0, 0.0], [300.0, 0.0, 0.0]]
        self.assertEqual(made_blasts.hidden_at(centres, [dict(at=[0.0, 0.0, 0.0], radius=100.0)]), [0, 2])
        self.assertEqual(made_blasts.hidden_at(centres, [dict(at=[290.0, 0.0, 0.0], radius=24.0)]), [3])
        self.assertEqual(made_blasts.hidden_at(centres, []), [])

    def test_the_maps_painted_fragments_are_read_in_both_forms(self):
        self.assertEqual(made_blasts.shown_of(None, 3), [True] * 3)
        self.assertEqual(made_blasts.shown_of(struct.pack('<4i', 3, 1, 0, 1), 3), [True, False, True])
        self.assertEqual(made_blasts.shown_of(struct.pack('<i', 3) + bytes([0, 1, 1]), 3), [False, True, True])
        # one of another mesh's count says nothing of this one's
        self.assertEqual(made_blasts.shown_of(struct.pack('<3i', 2, 0, 0), 3), [True] * 3)
        self.assertEqual(made_blasts.shown_of(made_blasts.visible_value(4, [1, 3]), 4), [True, False, True, False])

    def test_destroyed_chunks_take_the_fragments_bounds(self):
        fragments = [dict(bounds=(10.0, 20.0, 30.0, 1.0, 2.0, 3.0, 4.0)), dict(bounds=(0.0, 0.0, 0.0, 5.0, 5.0, 5.0, 9.0))]
        raw = made_blasts.chunks_of_bounds(fragments, [0])
        self.assertEqual(struct.unpack_from('<i', raw)[0], 1)
        self.assertEqual(len(raw), 4 + 25)
        self.assertEqual(struct.unpack_from('<6fB', raw, 4), (9.0, 18.0, 27.0, 11.0, 22.0, 33.0, 1))
        self.assertEqual(made_blasts.chunks_of_bounds(fragments, []), struct.pack('<i', 0))


if __name__ == '__main__':
    unittest.main()
