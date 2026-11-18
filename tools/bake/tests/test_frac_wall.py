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
