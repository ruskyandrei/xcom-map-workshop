"""The mesh writer (gen_mesh.py; custom geometry plan, section 0, stage F1): a static or fracturing mesh's native data
read as numbers and written back.

The oracle reads the configured install (tools/viewer/settings.py) and skips without it: every static and fracturing
mesh of URB_Bar and URB_PoliceStation written back from its numbers is its own native data, byte for byte (over the
whole install: research/evidence/frac-wall-audit.py). The collision tree's rules are checked on the same meshes, and
the tree made for new triangles on its own."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(TOOLS / 'upk'))
sys.path.insert(0, str(TOOLS / 'viewer'))
sys.path.insert(0, str(TOOLS / 'lab'))
import gen_mesh  # noqa: E402
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
POLICE, NO_POLICE = labpaths.test_file('XCOM_POLICE_UPK', labpaths.lwr_cooked('URB_PoliceStation.upk'),
                                       'URB_PoliceStation.upk')
MESHES = ('StaticMesh', 'FracturedStaticMesh')


def meshes(path):
    from package import Package
    p = Package(path)
    return p, [i for i in range(1, len(p.exports) + 1) if p.cls(i) in MESHES]


class Oracle(unittest.TestCase):
    """Every mesh of two maps written back from its numbers."""

    def check(self, path):
        p, found = meshes(path)
        counts = {cls: 0 for cls in MESHES}
        for i in found:
            m = gen_mesh.read(p, i)
            e = p.exports[i - 1]
            self.assertEqual(gen_mesh.write(m, m['at']), bytes(p.data[m['at']:e['off'] + e['size']]), p.name(i))
            counts[p.cls(i)] += 1
        self.assertTrue(all(counts.values()), counts)

    @unittest.skipUnless(BAR.exists(), NO_BAR)
    def test_every_mesh_of_the_bar_is_written_back_byte_for_byte(self):
        self.check(BAR)

    @unittest.skipUnless(POLICE.exists(), NO_POLICE)
    def test_every_mesh_of_the_police_station_is_written_back_byte_for_byte(self):
        self.check(POLICE)

    @unittest.skipUnless(BAR.exists(), NO_BAR)
    def test_a_mesh_written_elsewhere_points_its_raw_triangles_past_their_record(self):
        p, found = meshes(BAR)
        m = gen_mesh.read(p, found[0])
        b = gen_mesh.write(m, 5000)
        again = gen_mesh.read_native(bytes(5000) + b, 5000, 5000 + len(b), fractured=m['kind'] == 'fractured')
        self.assertEqual(gen_mesh.write(again, 5000), b)
        with self.assertRaises(gen_mesh.MeshError):
            gen_mesh.read_native(bytes(4000) + b, 4000, 4000 + len(b), fractured=m['kind'] == 'fractured')


class TreeRules(unittest.TestCase):
    """What the game's collision trees show, which kdop_tree and kdop_value follow."""

    @unittest.skipUnless(BAR.exists(), NO_BAR)
    def test_the_node_count_is_the_smallest_power_of_two_with_five_triangles_a_leaf(self):
        p, found = meshes(BAR)
        for i in found:
            k = gen_mesh.read(p, i)['kdop']
            self.assertEqual(len(k['nodes']) // 6, gen_mesh.node_count(len(k['triangles'])), p.name(i))
            if k['nodes']:
                self.assertEqual(k['nodes'][-6:], bytes(6), 'the last node is padding')

    @unittest.skipUnless(BAR.exists(), NO_BAR)
    def test_a_fracturing_meshs_collision_triangle_names_its_slot_and_fragment(self):
        p, found = meshes(BAR)
        checked = 0
        for i in found:
            if p.cls(i) != 'FracturedStaticMesh':
                continue
            m = gen_mesh.read(p, i)
            lod = m['lods'][0]
            idx = lod['indices'][1]
            frags = len(m['fractured']['fragments'])
            where = {}
            for s in lod['sections']:
                for f, (first, n) in enumerate(s['fragments']):
                    for t in range(first // 3, first // 3 + n):
                        where[tuple(idx[3 * t:3 * t + 3])] = (s['slot'], f)
            for t in m['kdop']['triangles']:
                self.assertEqual(t[3], gen_mesh.kdop_value(*where[t[:3]], frags), p.name(i))
                checked += 1
        self.assertGreater(checked, 30000)

    def test_node_counts(self):
        self.assertEqual([gen_mesh.node_count(n) for n in (0, 1, 5, 6, 10, 11, 12, 902, 5118, 5166)],
                         [0, 1, 1, 2, 2, 4, 4, 256, 1024, 2048])

    def test_a_new_tree_leaves_every_child_its_parents_box(self):
        positions = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 20.0, 0.0), (0.0, 0.0, 30.5)]
        tris = [(0, 1, 2, 0), (0, 2, 3, 1), (0, 3, 1, 2), (1, 3, 2, 3)] * 3
        k = gen_mesh.kdop_tree(positions, tris)
        self.assertEqual(k['root'], (0.0, 0.0, 0.0, 10.0, 20.0, 30.5))
        self.assertEqual(k['nodes'], gen_mesh.WHOLE * 3 + bytes(6))
        self.assertEqual(k['triangles'], tris)
        one = gen_mesh.kdop_tree(positions, tris[:4])
        self.assertEqual(one['nodes'], bytes(6))

    def test_fourth_values(self):
        self.assertEqual(gen_mesh.kdop_value(5, 5, 30), 155)
        self.assertEqual(gen_mesh.kdop_value(0, 1, 30), 1)
        self.assertEqual(gen_mesh.kdop_value(3, 0, 0), 3)

    def test_bounds_are_the_box_centre_half_size_and_farthest_corner(self):
        b = gen_mesh.bounds_of([(-376.0, -12.0, -16.0), (184.0, 12.0, 384.0), (0.0, 0.0, 0.0)])
        self.assertEqual(b[:6], (-96.0, 0.0, 184.0, 280.0, 12.0, 200.0))
        self.assertAlmostEqual(b[6], (280.0 ** 2 + 12.0 ** 2 + 200.0 ** 2) ** 0.5, 3)


if __name__ == '__main__':
    unittest.main()
