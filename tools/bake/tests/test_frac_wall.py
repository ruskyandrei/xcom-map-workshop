"""A fracturing wall made from numbers (frac_wall.py; custom geometry plan, section 0, stage F2).

The walls are the proof of concept's two: the twin (the donor's own tiles, x -384 to 192, seed 1) and the custom wall
(four tiles, x 0 to 384, a doorway at x 96 to 192 up to z 160, seed 2); a wall's solid stops 8 short of its ends. Their meshes are checked on their own: every
fragment a closed solid, the neighbours mutual, every triangle facing out, the lightmap coordinates in the square,
the collision triangles naming their slot and fragment, the faces covering the outline but the doorway, the mesh
written and read back, the same numbers the same mesh. With the configured install (tools/viewer/settings.py) the
recipe and the default template are checked against the donor, URB_Bar's URB_BarIntWallB_FRACTURED."""
from collections import Counter
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
            self.assertGreater(out['lightmapScale'], 0.0)

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


@unittest.skipUnless(BAR.exists(), NO_BAR)
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
