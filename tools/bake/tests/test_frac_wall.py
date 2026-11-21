"""A fracturing wall made from numbers (frac_wall.py; custom geometry plan, section 0, stage F2).

The walls are the proof of concept's two: the twin (the donor's own tiles, x -384 to 192, seed 1) and the custom wall
(four tiles, x 0 to 384, a doorway at x 96 to 192 up to z 160, seed 2); a wall's solid stops 8 short of its ends. Their meshes are checked on their own: every
fragment a closed solid, the neighbours mutual, every triangle facing out, the lightmap coordinates in the square,
the collision triangles naming their slot and fragment, the faces covering the outline but the doorway, the mesh
written and read back, the same numbers the same mesh. With the configured install (tools/viewer/settings.py) the
recipe and the default template are checked against the donor, URB_Bar's URB_BarIntWallB_FRACTURED."""
from collections import Counter
import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(TOOLS / 'upk'))
sys.path.insert(0, str(TOOLS / 'viewer'))
sys.path.insert(0, str(TOOLS / 'lab'))
import frac_wall  # noqa: E402
import gen_mesh  # noqa: E402
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
TWIN = dict(x0=-384.0, x1=192.0, openings=[], seed=1)
DOOR = dict(x0=96.0, x1=192.0, z0=-16.0, z1=160.0)
CUSTOM = dict(x0=0.0, x1=384.0, openings=[DOOR], seed=2)
BUILT = {}


def built(wall):
    key = repr(sorted(wall.items(), key=str))
    if key not in BUILT:
        BUILT[key] = frac_wall.build(wall)
    return BUILT[key]


def triangles(mesh):
    """[(slot, fragment, (a, b, c) positions, vertex index of a)] of LOD 0."""
    lod = mesh['lods'][0]
    pos, idx = lod['positions'], lod['indices'][1]
    out = []
    for s in lod['sections']:
        for f, (first, n) in enumerate(s['fragments']):
            for t in range(first // 3, first // 3 + n):
                out.append((s['slot'], f, [pos[i] for i in idx[3 * t:3 * t + 3]], idx[3 * t]))
    return out


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def area(tri):
    c = cross(sub(tri[1], tri[0]), sub(tri[2], tri[0]))
    return 0.5 * sum(v * v for v in c) ** 0.5


class Walls(unittest.TestCase):
    """The two walls' meshes, made with the default template (no install)."""

    def test_the_twin_stands_in_the_donors_box(self):
        b = built(TWIN)['mesh']['bounds']
        for got, want in zip(b[:6], (-96.0, 0.0, 184.0, 280.0, 12.0, 200.0)):
            self.assertAlmostEqual(got, want, 3)
        b = built(CUSTOM)['mesh']['bounds']
        for got, want in zip(b[:6], (192.0, 0.0, 184.0, 184.0, 12.0, 200.0)):
            self.assertAlmostEqual(got, want, 3)

    def test_the_ends_stop_short_of_the_tile_edges_and_the_openings_sides_do_not(self):
        # as the game's inside walls end (EXP-67: an end on a tile edge reached a unit into the next tile column)
        inset = frac_wall.RECIPE['endInset']
        for wall in (TWIN, CUSTOM):
            out = built(wall)
            xs = [p[0] for p in out['mesh']['lods'][0]['positions']]
            self.assertAlmostEqual(min(xs), wall['x0'] + inset, 3)
            self.assertAlmostEqual(max(xs), wall['x1'] - inset, 3)
            self.assertAlmostEqual(min(lo[0] for lo, _ in out['solids']), wall['x0'] + inset, 3)
            self.assertAlmostEqual(max(hi[0] for _, hi in out['solids']), wall['x1'] - inset, 3)
        sides = sorted({v for lo, hi in built(CUSTOM)['solids'] for v in (lo[0], hi[0])})
        self.assertEqual(sides, [8.0, 96.0, 192.0, 376.0])
        # an opening reaching past an end is cut to the solid
        self.assertEqual(frac_wall.solid_wall(dict(x0=0, x1=192, openings=[dict(x0=0, x1=96, z0=-16, z1=160)]))['openings'],
                         [dict(x0=8.0, x1=96.0, z0=-16.0, z1=160.0)])

    def test_every_fragment_is_a_closed_solid(self):
        for wall in (TWIN, CUSTOM):
            m = built(wall)['mesh']
            edges = {}
            for _, f, tri, _ in triangles(m):
                tri = [tuple(round(c, 3) for c in p) for p in tri]
                e = edges.setdefault(f, Counter())
                for a, b in ((0, 1), (1, 2), (2, 0)):
                    e[tri[a], tri[b]] += 1
            self.assertEqual(len(edges), len(m['fractured']['fragments']))
            for f, e in edges.items():
                self.assertEqual([k for k, c in e.items() if e.get((k[1], k[0]), 0) != c], [], 'fragment %d' % f)

    def test_neighbours_name_each_other(self):
        for wall in (TWIN, CUSTOM):
            frags = built(wall)['mesh']['fractured']['fragments']
            nb = [g['neighbours'] for g in frags]
            for f, row in enumerate(nb):
                self.assertEqual(len(row), len(frags[f]['dims']))
                for g in row:
                    if g >= 0:
                        self.assertIn(f, nb[g])
            self.assertTrue(all(any(g >= 0 for g in row) for row in nb), 'every fragment has a neighbour')

    def test_every_triangle_faces_out_as_ue3s_front_faces_do(self):
        for wall in (TWIN, CUSTOM):
            m = built(wall)['mesh']
            vertices = m['lods'][0]['vertices']
            for slot, f, (a, b, c), first in triangles(m):
                n = [(x - 127.5) / 127.5 for x in vertices[first][1][:3]]
                self.assertLess(sum(x * y for x, y in zip(cross(sub(b, a), sub(c, a)), n)), 1e-6, (slot, f))

    def test_lightmap_coordinates_stay_in_the_square(self):
        for wall in (TWIN, CUSTOM):
            out = built(wall)
            uv = [v[2][1] for v in out['mesh']['lods'][0]['vertices']]
            self.assertTrue(all(0.0 <= u <= 1.0 and 0.0 <= v <= 1.0 for u, v in uv))
            w, h = out['lightmapRect']
            self.assertTrue(w > 0 and h > 0 and w % 4 == 0 and h % 4 == 0)

    def test_the_lightmap_rectangle_follows_the_wall_at_the_donors_density(self):
        # (M2) the twin's charts at the donor's density on its faces: its rectangle at least the donor's 158-texel square
        # (the donor gives its trims and ends fewer texels than its faces) and no more than half as large again; a
        # wall's rectangle grows with its length
        w, h = built(TWIN)['lightmapRect']
        self.assertGreaterEqual(w * h, 158 * 158)
        self.assertLess(w * h, 1.5 * 158 * 158)
        areas = [(lambda r: r[0] * r[1])(frac_wall.build(dict(x0=0.0, x1=96.0 * t, openings=[], seed=1))['lightmapRect'])
                 for t in (1, 4, 16)]
        self.assertEqual(areas, sorted(areas))
        # the texels a unit along a face are the recipe's density whatever the length
        for t in (2, 16):
            out = frac_wall.build(dict(x0=0.0, x1=96.0 * t, openings=[], seed=1))
            lod = out['mesh']['lods'][0]
            pos, uv = lod['positions'], [v[2][1] for v in lod['vertices']]
            face = [k for k, v in enumerate(lod['vertices']) if v[1][1] > 250]        # side A's faces (normal +y)
            xs = sorted(face, key=lambda k: pos[k][0])
            a, b = xs[0], xs[-1]
            if abs(pos[b][0] - pos[a][0]) > 1:
                texels = abs(uv[b][0] - uv[a][0]) * out['lightmapRect'][0] / abs(pos[b][0] - pos[a][0])
                self.assertLess(abs(texels - frac_wall.RECIPE['lightmap']['density']) / frac_wall.RECIPE['lightmap']['density'], 0.01)

    def test_collision_triangles_name_their_slot_and_fragment(self):
        for wall in (TWIN, CUSTOM):
            m = built(wall)['mesh']
            lod = m['lods'][0]
            idx = lod['indices'][1]
            nfrag = len(m['fractured']['fragments'])
            want = []
            for s in lod['sections']:
                for f, (first, n) in enumerate(s['fragments']):
                    want += [gen_mesh.kdop_value(s['slot'], f, nfrag)] * n
            k = m['kdop']
            self.assertEqual([t[3] for t in k['triangles']], want)
            self.assertEqual([t[:3] for t in k['triangles']], [tuple(idx[i:i + 3]) for i in range(0, len(idx), 3)])
            self.assertEqual(len(k['nodes']) // 6, gen_mesh.node_count(len(idx) // 3))

    def test_the_faces_cover_the_outline_but_the_doorway(self):
        R = frac_wall.RECIPE
        face = R['face'][1] - R['face'][0]
        for wall, hole in ((TWIN, 0.0), (CUSTOM, (DOOR['x1'] - DOOR['x0']) * (DOOR['z1'] - R['face'][0]))):
            m = built(wall)['mesh']
            for slots, y in ((R['slots']['sideA'], R['half']), (R['slots']['sideB'], -R['half'])):
                got = sum(area(tri) for slot, _, tri, _ in triangles(m)
                          if slot in slots and all(abs(p[1] - y) < 1e-3 for p in tri))
                length = wall['x1'] - wall['x0'] - 2 * R['endInset']
                self.assertAlmostEqual(got, length * face - hole, delta=0.5)

    def test_nothing_stands_in_the_doorway(self):
        out = built(CUSTOM)
        for _, f, tri, _ in triangles(out['mesh']):
            cx, cz = sum(p[0] for p in tri) / 3, sum(p[2] for p in tri) / 3
            self.assertFalse(DOOR['x0'] + 0.5 < cx < DOOR['x1'] - 0.5 and cz < DOOR['z1'] - 0.5, f)
        for lo, hi in out['solids']:
            self.assertFalse(lo[0] < DOOR['x1'] and hi[0] > DOOR['x0'] and lo[2] < DOOR['z1'], (lo, hi))
        self.assertEqual(len(out['solids']), 3)
        self.assertEqual(len(built(TWIN)['solids']), 1)

    def test_every_fragment_goes_through_the_wall(self):
        for wall in (TWIN, CUSTOM):
            for f in built(wall)['fragments']:
                self.assertLessEqual(f['box'][2], -frac_wall.RECIPE['half'])
                self.assertGreaterEqual(f['box'][3], frac_wall.RECIPE['half'])

    def test_the_mesh_is_written_and_read_back(self):
        for wall in (TWIN, CUSTOM):
            m = dict(built(wall)['mesh'], bodySetup=0)
            b = gen_mesh.write(m, 4000)
            again = gen_mesh.read_native(bytes(4000) + b, 4000, 4000 + len(b), fractured=True)
            self.assertEqual(gen_mesh.write(again, 4000), b)
            self.assertEqual(len(again['fractured']['fragments']), len(m['fractured']['fragments']))

    def test_the_same_numbers_make_the_same_mesh(self):
        a = gen_mesh.write(dict(frac_wall.build(CUSTOM)['mesh'], bodySetup=0), 0)
        self.assertEqual(a, gen_mesh.write(dict(built(CUSTOM)['mesh'], bodySetup=0), 0))
        other = dict(CUSTOM, seed=3)
        self.assertNotEqual(a, gen_mesh.write(dict(frac_wall.build(other)['mesh'], bodySetup=0), 0))
        self.assertEqual(frac_wall.mesh_name(CUSTOM), frac_wall.mesh_name(dict(CUSTOM)))
        self.assertNotEqual(frac_wall.mesh_name(CUSTOM), frac_wall.mesh_name(other))
        self.assertTrue(frac_wall.mesh_name(TWIN).startswith('FracWall_576_'))

    def test_fragment_counts(self):
        self.assertEqual(built(TWIN)['counts']['fragments'], 30)
        self.assertEqual(built(CUSTOM)['counts']['fragments'], 27)


class Looks(unittest.TestCase):
    """(M4 item 1) A look is data: wall_looks.json's looks, the first the Bar's inside wall, whose recipe is RECIPE."""

    def test_the_default_look_is_the_bars_and_its_recipe_is_recipe(self):
        self.assertEqual(frac_wall.DEFAULT_LOOK, 'bar-inside')
        self.assertIs(frac_wall.look_of({}), frac_wall.RECIPE)
        self.assertIs(frac_wall.look_of(dict(look='bar-inside')), frac_wall.RECIPE)
        look = frac_wall.LOOKS['bar-inside']
        self.assertEqual((look['donor'], look['package'], look['actor']),
                         (frac_wall.RECIPE['donor'], 'URB_Bar', 'XComDecoFracLevelActor_17'))
        for key in ('bottom', 'top', 'storey', 'face', 'half', 'endInset', 'section', 'slots', 'cell', 'lightmap'):
            self.assertIn(key, frac_wall.RECIPE)

    def test_a_look_not_listed_is_refused(self):
        import frac_walls
        with self.assertRaises(ValueError):
            frac_wall.look_of(dict(look='marble'))
        with self.assertRaises(ValueError):
            frac_walls.check(dict(kind='fracWall', version=2, wall=dict(x0=0, x1=96, look='marble')))
        with self.assertRaises(ValueError):
            frac_walls.check(dict(kind='fracWall', version=1, wall=dict(x0=0, x1=96, look='bar-inside')))
        frac_walls.check(dict(kind='fracWall', version=2, wall=dict(x0=0, x1=96, look='bar-inside')))

    def test_the_file_is_lf_and_checked_in_order(self):
        raw = frac_wall.LOOKS_FILE.read_bytes()
        self.assertNotIn(b'\r', raw)
        self.assertEqual(list(frac_wall.LOOKS)[0], frac_wall.DEFAULT_LOOK)


class Slabs(unittest.TestCase):
    """(M5) frac_slab: a slab of whole tiles with a hole, its fragments, faces, collision and records."""
    S = dict(x0=0.0, x1=480.0, y0=0.0, y1=384.0, holes=[dict(x0=192.0, x1=288.0, y0=96.0, y1=288.0)], seed=3)

    def test_it_covers_its_footprint_but_the_hole_in_its_own_fragments(self):
        import frac_slab
        polys = frac_slab.fragments(self.S)
        def area(poly):
            return 0.5 * abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1])))
        self.assertAlmostEqual(sum(area(p) for p in polys), 480 * 384 - 96 * 192, 3)
        for poly in polys:
            cx, cy = sum(x for x, _ in poly) / len(poly), sum(y for _, y in poly) / len(poly)
            self.assertFalse(192 < cx < 288 and 96 < cy < 288)
        self.assertEqual(polys, frac_slab.fragments(dict(self.S)))      # the same seed, the same pattern

    def test_its_mesh_has_the_looks_slots_and_no_faces_inside(self):
        import frac_slab
        out = frac_slab.build(self.S)
        lod = out['mesh']['lods'][0]
        self.assertEqual([s['slot'] for s in lod['sections']], [0, 1])
        self.assertEqual(out['mesh']['fractured']['interior'], 2)
        zs = sorted({round(p[2], 3) for p in lod['positions']})
        self.assertEqual(zs, [-2.0, 2.0])
        # the top's and underside's areas are the footprint's less the hole; the edges' the outline's and the hole's
        n = len(lod['indices'][1]) // 3
        self.assertGreater(n, 0)
        self.assertEqual(out['counts']['fragments'], len(frac_slab.fragments(self.S)))
        rec = out['mesh']['fractured']['fragments']
        self.assertTrue(all(set(r['dims']) == {1.0} for r in rec))
        self.assertTrue(all(r['root'] == 0 and r['destroyable'] == 1 for r in rec))

    def test_its_collision_is_a_box_a_rectangle_round_the_hole_under_the_top(self):
        import frac_slab
        boxes = frac_slab.solids(self.S)
        self.assertEqual(boxes, [((0.0, 0.0, -2.0), (192.0, 384.0, 0.0)), ((192.0, 0.0, -2.0), (288.0, 96.0, 0.0)),
                                 ((192.0, 288.0, -2.0), (288.0, 384.0, 0.0)), ((288.0, 0.0, -2.0), (480.0, 384.0, 0.0))])

    def test_holes_that_leave_none_of_it_are_refused(self):
        # (review finding 32) one hole over all of it, or two that overlap and cover it between them: said, where the
        # build stopped on an empty min()
        import frac_slab
        slab = dict(x0=0.0, x1=288.0, y0=0.0, y1=192.0, seed=1)
        for holes in ([dict(x0=0.0, x1=288.0, y0=0.0, y1=192.0)],
                      [dict(x0=0.0, x1=192.0, y0=0.0, y1=192.0), dict(x0=96.0, x1=288.0, y0=0.0, y1=192.0)]):
            for make in (frac_slab.check, frac_slab.build):
                with self.assertRaisesRegex(ValueError, "the slab's holes leave none of it"):
                    make(dict(slab, holes=holes))
        # one tile left is a slab
        self.assertEqual(frac_slab.tiles(dict(slab, holes=[dict(x0=0.0, x1=192.0, y0=0.0, y1=192.0),
                                                           dict(x0=96.0, x1=288.0, y0=96.0, y1=192.0)])), {(2, 0)})

    def test_bad_numbers_are_refused(self):
        import frac_slab
        for bad in (dict(self.S, x1=500.0), dict(self.S, x1=96.0 * 17), dict(self.S, holes=[dict(x0=0, x1=50, y0=0, y1=96)]),
                    dict(self.S, holes=[dict(x0=0, x1=96, y0=0, y1=500)]), dict(self.S, look='marble'), dict(self.S, seed=1.5)):
            with self.assertRaises(ValueError):
                frac_slab.check(bad)


class JoinedEnds(unittest.TestCase):
    """(M3 item 2) A wall's ends joined to another made wall: 'through' to the far face of the wall it meets at an L,
    'line' on the tile edge against the next wall end to end, 'free' 8 short as before; the corner of an L closed."""
    W = dict(x0=0.0, x1=384.0, openings=[dict(x0=288.0, x1=384.0, z0=-16.0, z1=160.0)], seed=5)

    def test_each_style_stops_the_solid_where_it_says(self):
        for ends, (a, b) in ((('free', 'free'), (8.0, 376.0)), (('through', 'line'), (-8.0, 384.0)),
                             (('line', 'through'), (0.0, 392.0))):
            wall = dict(self.W, ends=list(ends))
            out = built(wall)
            xs = [p[0] for p in out['mesh']['lods'][0]['positions']]
            self.assertEqual((min(xs), max(xs)), (a, b), ends)
            self.assertEqual((min(lo[0] for lo, _ in out['solids']), max(hi[0] for _, hi in out['solids'])), (a, b))
        # the doorway at the far tile keeps its sides; past it, at a through end, 8 of solid at the corner
        self.assertEqual(frac_wall.solid_wall(dict(self.W, ends=['free', 'through']))['openings'],
                         [dict(x0=288.0, x1=384.0, z0=-16.0, z1=160.0)])
        self.assertEqual(frac_wall.ends_of(self.W), ('free', 'free'))

    def test_a_joined_wall_is_closed_and_named_apart(self):
        wall = dict(self.W, ends=['through', 'line'])
        m = built(wall)['mesh']
        edges = {}
        for _, f, tri, _ in triangles(m):
            tri = [tuple(round(c, 3) for c in p) for p in tri]
            e = edges.setdefault(f, Counter())
            for a, b in ((0, 1), (1, 2), (2, 0)):
                e[tri[a], tri[b]] += 1
        for f, e in edges.items():
            self.assertEqual([k for k, c in e.items() if e.get((k[1], k[0]), 0) != c], [], 'fragment %d' % f)
        self.assertNotEqual(frac_wall.mesh_name(wall), frac_wall.mesh_name(self.W))

    def test_bad_ends_are_refused(self):
        import frac_walls
        for ends in (['free'], ['free', 'mitre'], 'free'):
            with self.assertRaises(ValueError):
                frac_wall.ends_of(dict(self.W, ends=ends))
        frac_walls.check(dict(kind='fracWall', version=2, wall=dict(self.W, ends=['through', 'free'])))
        frac_walls.check(dict(kind='fracWall', version=1, wall=self.W))
        with self.assertRaises(ValueError):
            frac_walls.check(dict(kind='fracWall', version=1, wall=dict(self.W, ends=['through', 'free'])))
        with self.assertRaises(ValueError):
            frac_walls.check(dict(kind='fracWall', version=3, wall=self.W))

    def test_an_l_closes_its_corner_and_touches_the_game_tiles_the_games_corners_do(self):
        # wall A along x from 0 to 384 (its x1 end through), wall B along y from the corner (0 at A's line, its x0 end
        # free: it butts on A's face). The game counts its tiles from a unit under the piece grid and marks a tile
        # partly occupied where a solid reaches into it (F-116): the corner square, filled, reaches the tile outside the
        # corner by 7 units each way, as every L of the game's (none leaves its corner square empty: wall-joints.py).
        a = built(dict(x0=0.0, x1=384.0, openings=[], seed=1, ends=['free', 'through']))['solids']
        b = built(dict(x0=0.0, x1=384.0, openings=[], seed=2, ends=['free', 'free']))['solids']
        # B turned a quarter (its x along +y) and standing at A's x1
        boxes = [(lo[0], hi[0], lo[1], hi[1]) for lo, hi in a]
        boxes += [(384.0 - hi[1], 384.0 - lo[1], lo[0], hi[0]) for lo, hi in b]
        # the corner square [376, 392] x [-8, 8] is filled
        for x, y in ((380.0, -6.0), (390.0, -6.0), (390.0, 6.0), (378.0, 6.0)):
            self.assertTrue(any(x0 <= x <= x1 and y0 <= y <= y1 for x0, x1, y0, y1 in boxes), (x, y))

        def tiles(box):
            x0, x1, y0, y1 = box
            first = lambda v: int(math.floor((v + 1) / 96.0 + 1e-9))  # noqa: E731
            last = lambda v: int(math.ceil((v + 1) / 96.0 - 1e-9))  # noqa: E731
            return {(i, j) for i in range(first(x0), last(x1)) for j in range(first(y0), last(y1))}
        hit = set().union(*(tiles(b) for b in boxes))
        free = set().union(*(tiles(b) for b in [(lo[0], hi[0], lo[1], hi[1]) for lo, hi in
                                                 built(dict(x0=0.0, x1=384.0, openings=[], seed=1))['solids']]
                             + boxes[len(a):]))
        self.assertEqual(hit - free, {(4, -1)})


@unittest.skipUnless(BAR.exists(), NO_BAR)
class OneStorey(unittest.TestCase):
    """(M2 item 5) A wall of one storey: from the floor at -16 to 192, as the game's one-storey inside walls stand, its
    face to 180 and the donor's cornice from there to the top; its upper storey's slots empty."""
    WALL = dict(x0=0.0, x1=384.0, openings=[dict(x0=96.0, x1=192.0, z0=-16.0, z1=160.0)], seed=4, storeys=1)

    def test_it_stands_a_storey_high_with_the_donors_cornice_at_its_top(self):
        out = built(self.WALL)
        zs = [p[2] for p in out['mesh']['lods'][0]['positions']]
        self.assertEqual((min(zs), max(zs)), (-16.0, 192.0))
        R = frac_wall.shaped(self.WALL)
        self.assertEqual((R['top'], R['face']), (192.0, [12.0, 180.0]))
        self.assertEqual([z for _, z, _ in R['section']], [-16.0, 0.0, 9.0, 12.0, 180.0, 182.0, 192.0])
        # the skirting is the donor's, the cornice the donor's a storey lower
        self.assertEqual([(y, v) for y, _, v in R['section']], [(y, v) for y, _, v in frac_wall.RECIPE['section']])
        self.assertIs(frac_wall.shaped(dict(self.WALL, storeys=2)), frac_wall.RECIPE)
        self.assertIs(frac_wall.shaped({k: v for k, v in self.WALL.items() if k != 'storeys'}), frac_wall.RECIPE)

    def test_its_upper_storeys_slots_are_empty(self):
        sections = {s['slot']: s['triangles'] for s in built(self.WALL)['mesh']['lods'][0]['sections']}
        self.assertEqual((sections[1], sections[3]), (0, 0))
        self.assertTrue(all(sections[k] > 0 for k in (0, 2, 4, 5)))

    def test_its_collision_and_box_stop_at_its_top(self):
        import frac_walls
        out = built(self.WALL)
        self.assertEqual(max(hi[2] for _, hi in out['solids']), 192.0)
        self.assertEqual(frac_walls.local_box(self.WALL)[5], 192.0)
        self.assertEqual(max(f['box'][5] for f in out['fragments']), 192.0)

    def test_its_numbers_are_checked_and_named_apart_from_a_tall_ones(self):
        import frac_walls
        frac_walls.check(dict(kind='fracWall', version=1, wall=self.WALL))
        with self.assertRaises(ValueError):
            frac_walls.check(dict(kind='fracWall', version=1, wall=dict(self.WALL, storeys=3)))
        with self.assertRaises(ValueError):
            frac_wall.shaped(dict(self.WALL, storeys=0))
        self.assertNotEqual(frac_wall.mesh_name(self.WALL), frac_wall.mesh_name(dict(self.WALL, storeys=2)))


class Gaps(unittest.TestCase):
    """One kind of gap (19 November 2026): a threshold kept under a doorway, a gap along the whole wall leaving a strip
    of wall under or over it (its seeds all in the gap, each moved into the strip), one taking the whole wall
    refused."""

    def test_a_threshold_is_kept_under_a_doorway(self):
        door = dict(DOOR, z0=8.0)
        mesh = built(dict(CUSTOM, openings=[door]))['mesh']
        inside = [sum(p[2] for p in tri) / 3 for _, _, tri, _ in triangles(mesh)
                  if door['x0'] + 0.5 < sum(p[0] for p in tri) / 3 < door['x1'] - 0.5]
        self.assertTrue(any(z < door['z0'] for z in inside))
        self.assertFalse(any(door['z0'] + 0.5 < z < door['z1'] - 0.5 for z in inside))

    def test_a_gap_along_the_whole_wall_leaves_its_strip(self):
        for gap in (dict(x0=0.0, x1=384.0, z0=8.0, z1=384.0), dict(x0=0.0, x1=384.0, z0=-16.0, z1=300.0)):
            out = frac_wall.build(dict(CUSTOM, openings=[gap]))
            self.assertTrue(out['fragments'], gap)
            zs = [p[2] for _, _, tri, _ in triangles(out['mesh']) for p in tri]
            self.assertTrue(zs, gap)
            self.assertTrue(all(z <= gap['z0'] + 1e-3 or z >= gap['z1'] - 1e-3 for z in zs), gap)

    def test_a_gap_taking_the_whole_wall_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'leave none'):
            frac_wall.build(dict(CUSTOM, openings=[dict(x0=0.0, x1=384.0, z0=-16.0, z1=384.0)]))


def sound(test, out):
    """The checks every wall's mesh passes, on a built wall `out`: each fragment closed, the neighbours mutual, every
    triangle facing out, the lightmap coordinates in the square, the mesh written and read back."""
    m = out['mesh']
    edges = {}
    for _, f, tri, _ in triangles(m):
        tri = [tuple(round(c, 3) for c in p) for p in tri]
        e = edges.setdefault(f, Counter())
        for a, b in ((0, 1), (1, 2), (2, 0)):
            e[tri[a], tri[b]] += 1
    test.assertEqual(len(edges), len(m['fractured']['fragments']))
    for f, e in edges.items():
        test.assertEqual([k for k, c in e.items() if e.get((k[1], k[0]), 0) != c], [], 'fragment %d' % f)
    nb = [g['neighbours'] for g in m['fractured']['fragments']]
    for f, row in enumerate(nb):
        for g in row:
            if g >= 0:
                test.assertIn(f, nb[g])
    vertices = m['lods'][0]['vertices']
    for slot, f, (a, b, c), first in triangles(m):
        n = [(x - 127.5) / 127.5 for x in vertices[first][1][:3]]
        test.assertLess(sum(x * y for x, y in zip(cross(sub(b, a), sub(c, a)), n)), 1e-6, (slot, f))
    test.assertTrue(all(0.0 <= u <= 1.0 and 0.0 <= v <= 1.0 for u, v in (v[2][1] for v in vertices)))
    b = gen_mesh.write(dict(m, bodySetup=0), 4000)
    again = gen_mesh.read_native(bytes(4000) + b, 4000, 4000 + len(b), fractured=True)
    test.assertEqual(gen_mesh.write(again, 4000), b)


def positions(out):
    return out['mesh']['lods'][0]['positions']


class FreeForm(unittest.TestCase):
    """(Custom geometry improvements plan, stage 2) Walls in the free form (`free: 1`): any extents, faces, bottom and
    top, a band of a tall stretched wall, cells from a hashed lattice, leaning (mitred) ends, gaps anywhere."""
    BAR_LOOK = dict(free=1, x0=13.25, x1=157.5, y0=-20.0, y1=5.0, z0=0.0, z1=217.25, seed=3,
                    openings=[dict(x0=50.75, x1=88.5, z0=0.0, z1=150.0)])

    @classmethod
    def setUpClass(cls):
        import looks
        cls.look = looks.resolve('wall', dict(mesh='AbductorExtWall.Meshes.AbductorExtWallA_FRACTURED', measure=1))

    def walls(self):
        return {
            'fractional': self.BAR_LOOK,
            'own size': dict(free=1, x0=0.0, x1=384.0, seed=2),
            'taller': dict(free=1, x0=0.0, x1=500.0, z0=-16.0, z1=700.0, seed=4),
            'lower': dict(free=1, x0=-100.0, x1=300.0, z0=-16.0, z1=300.0, seed=4),
            'band': dict(free=1, x0=0.0, x1=500.0, z0=-16.0, z1=1184.0, band=[384.0, 784.0], seed=4, tall='stretch'),
            'measured lower': dict(free=1, x0=0.0, x1=480.0, z0=0.0, z1=300.0, look=self.look, seed=5),
            'measured thick': dict(free=1, x0=0.0, x1=480.0, z0=0.0, z1=500.0, y0=-30.0, y1=12.0, look=self.look, seed=5),
            'mitre 90': dict(free=1, x0=0.0, x1=384.0, seed=6, ends=[dict(inset=0.0, lean=-1.0), dict(inset=8.0, lean=1.0)]),
            'mitre 45': dict(free=1, x0=0.0, x1=600.0, seed=6, ends=['free', dict(inset=0.0, lean=2.4142)],
                             openings=[dict(x0=200.0, x1=300.0, z0=-16.0, z1=160.0)]),
            'mitre cut through': dict(free=1, x0=0.0, x1=600.0, seed=6, ends=['line', dict(inset=0.0, lean=1.0)],
                                      openings=[dict(x0=450.0, x1=600.0, z0=-16.0, z1=160.0)]),
            'short mitred both ends': dict(free=1, x0=0.0, x1=120.0, seed=6,
                                           ends=[dict(inset=0.0, lean=1.0), dict(inset=0.0, lean=-1.0)]),
            'measured mitre': dict(free=1, x0=0.0, x1=480.0, look=self.look, seed=5, ends=[dict(inset=-3.0, lean=0.4142),
                                                                                          'line']),
        }

    def test_free_walls_are_sound(self):
        for name, wall in self.walls().items():
            with self.subTest(name):
                sound(self, built(wall))

    def test_its_extents_are_its_numbers(self):
        out = built(self.BAR_LOOK)
        xs, ys, zs = zip(*positions(out))
        inset = frac_wall.RECIPE['endInset']
        self.assertAlmostEqual(min(xs), 13.25 + inset, 3)
        self.assertAlmostEqual(max(xs), 157.5 - inset, 3)
        self.assertEqual((min(zs), max(zs)), (0.0, 217.25))
        # the faces at y0 and y1, the trims as proud of them as the look's (3 at the skirting, 4 at the cornice)
        self.assertEqual((min(ys), max(ys)), (-24.0, 9.0))
        lod = out['mesh']['lods'][0]
        R = frac_wall.RECIPE
        for slots, y in ((R['slots']['sideA'], 5.0), (R['slots']['sideB'], -20.0)):
            face = [pos for _, _, tri, _ in triangles(out['mesh']) for pos in tri
                    if all(abs(p[1] - y) < 1e-3 for p in tri)]
            self.assertTrue(face, y)
        self.assertEqual({(lo[1], hi[1]) for lo, hi in out['solids']}, {(-20.0, 5.0)})
        self.assertEqual(frac_wall.solid_box(self.BAR_LOOK), [21.25, 149.5, -24.0, 9.0, 0.0, 217.25])
        # the gap: nothing stands in it
        for _, _, tri, _ in triangles(out['mesh']):
            cx, cz = sum(p[0] for p in tri) / 3, sum(p[2] for p in tri) / 3
            self.assertFalse(51.25 < cx < 88.0 and cz < 149.5)
        self.assertEqual(len(lod['sections']), 6)

    def test_a_height_between_storeys_keeps_the_looks_bands(self):
        for z1 in (300.0, 450.0, 700.0):
            out = built(dict(free=1, x0=0.0, x1=384.0, z0=-16.0, z1=z1, seed=4))
            zs = {round(p[2], 3) for p in positions(out)}
            self.assertEqual((min(zs), max(zs)), (-16.0, z1))
            # the cornice still 12 tall at the top (its foot 12 under it), the skirting 28 at the bottom
            self.assertTrue({z1 - 12.0, z1 - 10.0, 12.0, 9.0, 0.0} <= zs, z1)
        for z1 in (250.0, 500.0):
            out = built(dict(free=1, x0=0.0, x1=480.0, z0=0.0, z1=z1, look=self.look, seed=5))
            zs = [p[2] for p in positions(out)]
            self.assertAlmostEqual(max(zs), z1, 3)
            self.assertEqual(min(zs), 0.0)

    def test_a_band_is_a_window_of_the_stretched_wall(self):
        R = frac_wall.RECIPE
        tall = dict(free=1, x0=0.0, x1=500.0, z0=-16.0, z1=1184.0, seed=4, tall='stretch')
        for band, skirting, cornice in (([-16.0, 384.0], True, False), ([384.0, 784.0], False, False),
                                        ([784.0, 1184.0], False, True)):
            out = built(dict(tall, band=band))
            zs = [p[2] for p in positions(out)]
            self.assertEqual((min(zs), max(zs)), tuple(band))
            # a trim strip (a trim triangle not level) only where the band holds the skirting or the cornice
            strips = [tri for slot, _, tri, _ in triangles(out['mesh'])
                      if slot == R['slots']['trim'] and max(p[2] for p in tri) - min(p[2] for p in tri) > 1e-3]
            self.assertEqual(any(max(p[2] for p in t) < 20 for t in strips), skirting, band)
            self.assertEqual(any(min(p[2] for p in t) > 1100 for t in strips), cornice, band)

    def test_cells_stay_put_when_an_end_moves(self):
        # the seeds come from a lattice counted from the frame's origin: dragging an end changes the cells near it only
        def boxes(wall, keep):
            return {tuple(round(v, 3) for v in f['box']) for f in built(wall)['fragments'] if keep(f['box'])}
        base = dict(free=1, x0=0.0, x1=1000.0, seed=7)
        far = boxes(base, lambda b: b[1] < 800.0)
        self.assertGreater(len(far), 20)
        self.assertEqual(boxes(dict(base, x1=1062.5), lambda b: b[1] < 800.0), far)
        self.assertEqual(boxes(dict(base, x1=937.25), lambda b: b[1] < 800.0), far)
        near = boxes(base, lambda b: b[0] > 200.0)
        self.assertEqual(boxes(dict(base, x0=-71.5), lambda b: b[0] > 200.0), near)
        self.assertEqual(boxes(dict(base, z1=500.0), lambda b: b[5] < 300.0), boxes(base, lambda b: b[5] < 300.0))
        self.assertNotEqual(boxes(dict(base, seed=8), lambda b: b[1] < 800.0), far)

    def test_a_piece_reads_the_wholes_lattice(self):
        # a piece of a split wall (its origin along the whole 400, up it 0) has the whole's cells where it is
        whole = {tuple(round(v, 3) for v in f['box']) for f in built(dict(free=1, x0=0.0, x1=1000.0, seed=7))['fragments']}
        # (the place along from the whole's x0, its x0 the fifth number: -50 + 450 is the same origin, 400)
        for place in ([400.0, 1000.0, 0.0, 400.0], [450.0, 1050.0, 0.0, 400.0, -50.0]):
            piece = built(dict(free=1, x0=0.0, x1=500.0, seed=7, whole=place))['fragments']
            inner = [f['box'] for f in piece if f['box'][0] > 150.0 and f['box'][1] < 350.0]
            self.assertGreater(len(inner), 3)
            for b in inner:
                self.assertIn(tuple(round(v, 3) for v in (b[0] + 400.0, b[1] + 400.0) + tuple(b[2:])), whole)

    def check_mitre(self, wall, end, lean):
        """The end `end` of `wall` leans `lean`: every corner on its plane or clear of its reach, the faces' texture read
        at the moved place, its collision a hull leaning as it does."""
        out = built(wall)
        R = frac_wall.shaped(wall)
        solid = frac_wall.solid_wall(wall, R)
        xe = solid['x1' if end else 'x0']
        reach = abs(lean) * frac_wall.reach_of(R)
        sign = 1 if end else -1
        on = 0
        for x, y, z in positions(out):
            d = sign * (x - (xe + lean * y))
            self.assertLess(d, 1e-3, (x, y, z))             # nothing past the plane
            if abs(d) < 1e-3:
                on += 1
            else:
                # a corner not on the end is where it was built: further in from the end than the end's reach
                self.assertGreater(-sign * (x - xe), reach, (x, y, z))
        self.assertGreater(on, 10)
        # side A's face corners on the plane: u = x / 192 + 0.5 at the moved x (the look's face texture), whole repeats
        # aside (each face's held near 0)
        lod = out['mesh']['lods'][0]
        Rl = frac_wall.RECIPE
        checked = 0
        for (x, y, z), v in zip(lod['positions'], lod['vertices']):
            if abs(y - Rl['half']) < 1e-3 and v[1][1] > 250 and 13 < z < 371 and abs(x - (xe + lean * y)) < 1e-3:
                d = v[2][0][0] - (x / Rl['faceRepeat'] + Rl['faceU'])
                self.assertLess(abs(d - round(d)), 0.01, (x, y, z))
                checked += 1
        self.assertGreater(checked, 1)
        hulls = [s for s in out['solids'] if isinstance(s, dict)]
        self.assertEqual(len(hulls), 1)
        lo, hi = R['collisionY']
        xs = sorted({round(v[0], 3) for v in hulls[0]['VertexData']})
        for y in (lo, hi):
            self.assertTrue(any(abs(x - (xe + lean * y)) < 0.01 for x in xs), (y, xs))

    def test_a_mitred_end_leans_on_its_plane(self):
        # a right angle's mitre (45 degrees across the wall), a 45-degree corner's and a 135-degree corner's
        for lean in (1.0, -1.0, 1.0 / math.tan(math.radians(22.5)), math.tan(math.radians(22.5))):
            with self.subTest(lean=lean):
                wall = dict(free=1, x0=0.0, x1=600.0, seed=6, ends=['free', dict(inset=0.0, lean=lean)],
                            openings=[dict(x0=200.0, x1=300.0, z0=-16.0, z1=160.0)])
                sound(self, built(wall))
                self.check_mitre(wall, 1, lean)
                wall = dict(free=1, x0=-50.0, x1=500.0, seed=9, ends=[dict(inset=4.0, lean=lean), 'line'])
                sound(self, built(wall))
                self.check_mitre(wall, 0, lean)

    def test_a_lean_is_clamped_at_the_sharpest_corner(self):
        wall = dict(free=1, x0=0.0, x1=800.0, seed=6, ends=['free', dict(inset=0.0, lean=20.0)])
        self.assertEqual(frac_wall.solid_wall(wall)['lean'], [0.0, frac_wall.MAX_LEAN])
        self.check_mitre(wall, 1, frac_wall.MAX_LEAN)

    def test_a_gap_keeps_clear_of_a_leaning_end_unless_cut_through(self):
        end = dict(inset=0.0, lean=1.0)
        for gap in (dict(x0=500.0, x1=590.0, z0=-16.0, z1=160.0), dict(x0=590.0, x1=600.0, z0=-16.0, z1=160.0)):
            with self.assertRaisesRegex(ValueError, 'leaning end'):
                frac_wall.build(dict(free=1, x0=0.0, x1=600.0, seed=6, ends=['free', end], openings=[gap]))
        # cut through to the end, from clear of its reach: built
        wall = dict(free=1, x0=0.0, x1=600.0, seed=6, ends=['free', end], openings=[dict(x0=450.0, x1=600.0, z0=-16.0, z1=160.0)])
        sound(self, built(wall))
        self.check_mitre(wall, 1, 1.0)

    def test_a_gap_may_reach_a_free_end(self):
        out = built(dict(free=1, x0=0.0, x1=384.0, seed=6, openings=[dict(x0=0.0, x1=100.0, z0=-16.0, z1=160.0)]))
        for _, _, tri, _ in triangles(out['mesh']):
            self.assertFalse(sum(p[0] for p in tri) / 3 < 99.5 and sum(p[2] for p in tri) / 3 < 159.5)

    def test_a_far_pieces_texture_is_held_near_0(self):
        # a piece 11,000 along a long wall: its faces' coordinates are the whole's less whole repeats, near 0 where the
        # mesh's half floats keep them sharp (unheld, they would be over 100)
        out = built(dict(free=1, x0=0.0, x1=1536.0, seed=3, whole=[11000.0, 12536.0, 0.0, 400.0, 0.0]))
        uvs = [v[2][0] for v in out['mesh']['lods'][0]['vertices']]
        self.assertLess(max(abs(c) for uv in uvs for c in uv), 10.0)

    def test_the_box_holds_a_leaning_end(self):
        wall = dict(free=1, x0=0.0, x1=600.0, seed=6, ends=[dict(inset=3.0, lean=-0.5), dict(inset=-2.0, lean=2.0)])
        box = frac_wall.solid_box(wall)
        self.assertEqual(box, [3.0 - 0.5 * 12.0, 602.0 + 2.0 * 12.0, -12.0, 12.0, -16.0, 384.0])
        xs = [p[0] for p in positions(built(wall))]
        self.assertAlmostEqual(min(xs), box[0], 3)
        self.assertAlmostEqual(max(xs), box[1], 3)

    def test_its_mapping_is_taken_and_not_used_yet(self):
        mapping = dict(surfaces=dict(faces=dict(mode='size', u=96.0, v=96.0, turn=30.0)))
        a, b = built(dict(self.BAR_LOOK)), built(dict(self.BAR_LOOK, mapping=mapping))
        self.assertEqual(positions(a), positions(b))
        self.assertEqual([v[2] for v in a['mesh']['lods'][0]['vertices']], [v[2] for v in b['mesh']['lods'][0]['vertices']])

    def test_an_older_whole_is_read(self):
        R = frac_wall.shaped(dict(free=1, x0=0.0, x1=300.0, whole=[100.0, 1000.0]))
        self.assertEqual((R['uvShift'], frac_wall.whole_origin(dict(whole=[100.0, 1000.0]))), (100.0, (100.0, 0.0)))
        self.assertEqual(frac_wall.whole_origin(dict(whole=[100.0, 1000.0, 400.0, 1200.0])), (100.0, 400.0))
        sound(self, built(dict(free=1, x0=0.0, x1=300.0, whole=[100.0, 1000.0])))

    def test_bad_free_numbers_are_refused_with_their_codes(self):
        import free_form
        base = dict(free=1, x0=0.0, x1=384.0, seed=2)
        for bad, code in ((dict(base, x1=0.0), 'extent'), (dict(base, x1=float('nan')), 'number'),
                          (dict(base, y0=8.0, y1=-8.0), 'extent'), (dict(base, z0=100.0, z1=100.0), 'extent'),
                          (dict(base, x1='384'), 'number'), (dict(base, seed=True), 'number'),
                          (dict(base, seed=1.5), 'number'), (dict(base, tall='grow'), 'tall'),
                          (dict(base, band=[300.0, 500.0]), 'band'), (dict(base, band=[300.0]), 'band'),
                          (dict(base, whole=[1.0, 2.0, 3.0]), 'whole'), (dict(base, whole=[1.0, 0.0, 3.0, 4.0]), 'whole'),
                          (dict(base, mapping=[]), 'mapping'),
                          (dict(base, openings=[dict(x0=300.0, x1=400.0, z0=0.0, z1=100.0)]), 'opening'),
                          (dict(base, openings=[dict(x0=30.0, x1=40.0, z0=100.0, z1=100.0)]), 'opening'),
                          (dict(base, ends=['free']), 'ends'), (dict(base, ends=['free', 'mitre']), 'ends'),
                          (dict(base, ends=['free', dict(inset=0.0, lean=float('inf'))]), 'ends'),
                          (dict(base, x1=10.0), 'ends'),
                          (dict(base, ends=[dict(inset=0.0, lean=3.0), dict(inset=0.0, lean=-3.0)], x1=40.0), 'ends'),
                          (dict(base, look=self.look, y0=-1.0, y1=1.0), 'thickness'),
                          (dict(base, ends=['free', dict(inset=0.0, lean=1.0)],
                                openings=[dict(x0=300.0, x1=375.0, z0=0.0, z1=100.0)]), 'lean'),
                          (dict(base, free=0), 'free'), (dict(x0=0.0, x1=384.0), 'free')):
            with self.subTest(bad=bad):
                with self.assertRaises(free_form.NumbersError) as caught:
                    frac_wall.check_free(bad)
                self.assertEqual(caught.exception.code, code, caught.exception)
        with self.assertRaisesRegex(ValueError, 'not listed'):
            frac_wall.check_free(dict(base, look='marble'))
        self.assertIs(frac_wall.check_free(base), base)


class OldNumbers(unittest.TestCase):
    """Walls of the numbers before the free form (no `free`) build byte for byte as they did: each one's written mesh,
    collision, fragment boxes, lightmap rectangle and counts hashed on the commit the free form started from (495bd26,
    custom geometry improvements plan, stage 2), in the Bar's look and in two measured looks of the catalogue."""
    HASHES = {
        'twin': '5819ef1245bddb5d302e3202a5c429ce2537ee15d7001c84006e70f68a174bca',
        'door-joined': '96d5bf1d4bec89827de3cabb57ac514a66a4c2fb5a6abb12f588e1509e02e42b',
        'one-storey': 'edd2ea41b211cfd36e88bb9cd78b9a7b78e15ea625680a08a4a211547d14871b',
        'piece': 'a0fee819192d95d73a1ca8ca6fb78e45251ec5ebaa72e839a8fa559631ae9e84',
        'measured': 'e8043db4e103b8c4ac1954a519a9e5acf125ed8f22e84b10aae6d96948dec7d3',
        'measured-low': '8b01039a1d508e158b91679aa2dca27c756b91007804916bbb237e4d4eda5453',
        'measured-piece': '68d5ba3e0685397cf2a85dcdb4fd0ec11c9b68958bf08ade1974bf278f7f4e74',
    }
    NAMES = {
        'twin': 'FracWall_576_3150237b59', 'door-joined': 'FracWall_384_05325f00b0', 'one-storey': 'FracWall_384_234bb844af',
        'piece': 'FracWall_384_ebb231afea', 'measured': 'FracWall_480_6edf0d8ebf', 'measured-low': 'FracWall_288_ace7ede1ff',
        'measured-piece': 'FracWall_384_8470f2f96b',
    }

    @staticmethod
    def walls():
        import looks
        T = 96.0
        look = looks.resolve('wall', dict(mesh='AbductorExtWall.Meshes.AbductorExtWallA_FRACTURED', measure=1))
        low = looks.resolve('wall', dict(mesh='BLDG_RoadHouse.Meshes.RHWallEast_FRACTURED', measure=1))
        return {
            'twin': TWIN,
            'door-joined': dict(CUSTOM, ends=['through', 'line']),
            'one-storey': dict(x0=0.0, x1=384.0, openings=[DOOR], seed=4, storeys=1),
            'piece': dict(x0=0.0, x1=4 * T, openings=[], seed=2, whole=[7 * T, 20 * T]),
            'measured': dict(x0=0.0, x1=5 * T, openings=[dict(x0=T, x1=2 * T, z0=0.0, z1=200.0)], seed=3, look=look),
            'measured-low': dict(x0=0.0, x1=3 * T, openings=[], seed=5, look=low, storeys=1, ends=['free', 'through']),
            'measured-piece': dict(x0=0.0, x1=4 * T, look=look, seed=3, whole=[5 * T, 12 * T]),
        }

    def test_old_walls_build_byte_for_byte(self):
        import hashlib
        for name, wall in self.walls().items():
            with self.subTest(name):
                out = built(wall)
                mesh = gen_mesh.write(dict(out['mesh'], bodySetup=0), 0)
                rest = repr((out['solids'], out['fragments'], out['lightmapRect'], out['counts'], out.get('whole')))
                self.assertEqual(hashlib.sha256(mesh + rest.encode()).hexdigest(), self.HASHES[name])
                self.assertEqual(frac_wall.mesh_name(wall), self.NAMES[name])


class Donor(unittest.TestCase):
    """The recipe and the default template against the donor itself."""

    @classmethod
    def setUpClass(cls):
        from package import Package
        p = Package(BAR)
        cls.donor = gen_mesh.read(p, p.by_name[frac_wall.RECIPE['donor']])

    def test_the_template_is_the_donors_save_but_its_geometry(self):
        d, t = self.donor, frac_wall.default_template()
        for k in ('kind', 'version', 'optimisation', 'simplified'):
            self.assertEqual(d[k], t[k], k)
        for k in t['tail']:
            if k != 'guid':         # each made mesh has its own
                self.assertEqual(d['tail'][k], t['tail'][k], k)
        for k in t['fractured']:
            if k != 'fragments':
                self.assertEqual(d['fractured'][k], t['fractured'][k], k)
        for k in ('positionStride', 'texcoords', 'vertexStride', 'fullUVs'):
            self.assertEqual(d['lods'][0][k], t['lods'][0][k], k)

    def test_the_twin_stands_in_the_donors_bounds(self):
        for got, want in zip(built(TWIN)['mesh']['bounds'], self.donor['bounds']):
            self.assertAlmostEqual(got, want, delta=0.01)

    def test_the_donors_sides_follow_the_recipes_section(self):
        lod = self.donor['lods'][0]
        normals = [[(x - 127.5) / 127.5 for x in v[1][:3]] for v in lod['vertices']]
        idx = lod['indices'][1]
        checked = 0
        for s in lod['sections']:
            if s['slot'] == frac_wall.RECIPE['slots']['interior']:
                continue
            for v in set(idx[s['first']:s['first'] + 3 * s['triangles']]):
                n, (x, y, z) = normals[v], lod['positions'][v]
                if abs(n[0]) > 0.5 or abs(n[2]) > 0.9:      # the ends, the top and the bottom
                    continue
                self.assertAlmostEqual(abs(y), frac_wall.half_width(z), delta=0.05, msg=(x, y, z))
                checked += 1
        self.assertGreater(checked, 200)

    def test_the_donors_faces_repeat_as_the_recipe_says(self):
        R = frac_wall.RECIPE
        lod = self.donor['lods'][0]
        idx = lod['indices'][1]
        for slots, sign, v0 in ((R['slots']['sideA'], 1, R['faceV'][0]), (R['slots']['sideB'], -1, R['faceV'][1])):
            checked = 0
            for s in lod['sections']:
                if s['slot'] not in slots:
                    continue
                for v in set(idx[s['first']:s['first'] + 3 * s['triangles']]):
                    x, y, z = lod['positions'][v]
                    if abs(y - sign * R['half']) > 1e-3 or not R['face'][0] <= z <= R['face'][1]:
                        continue
                    u, w = lod['vertices'][v][2][0]
                    self.assertAlmostEqual(u, sign * x / R['faceRepeat'] + R['faceU'], delta=0.01, msg=(x, z))
                    self.assertAlmostEqual(w, v0 - z / R['faceRepeat'], delta=0.01, msg=(x, z))
                    checked += 1
            self.assertGreater(checked, 50)


if __name__ == '__main__':
    unittest.main()
