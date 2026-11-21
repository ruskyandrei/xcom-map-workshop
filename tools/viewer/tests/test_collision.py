"""The game's collision for line checks (collision.py): box elements placed by their W-first planes, convex hulls in
the mesh's frame, one solid each, and the cache's guard against a package other than the one exported."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import collision
from package import FormatError, Package
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lab'))
import labpaths

# the farm of the configured install, or of the folder XCOM_COOKED names; without it the package tests skip
FARM, NO_FARM = labpaths.install_map('CsmallScout_Farm')


def plane(w, x, y, z):
    return struct.pack('<4f', w, x, y, z)


def top_along(elements, origin, x, y):
    """The highest point where the vertical line at (x, y) meets the triangles, the mesh placed at `origin` unturned."""
    best = None
    for flat in elements:
        pts = [(flat[i] + origin[0], flat[i + 1] + origin[1], flat[i + 2] + origin[2]) for i in range(0, len(flat), 3)]
        for a, b, c in (pts[i:i + 3] for i in range(0, len(pts), 3)):
            d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(d) < 1e-9:
                continue
            l0 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / d
            l1 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / d
            if min(l0, l1, 1 - l0 - l1) < -1e-6:
                continue
            z = l0 * a[2] + l1 * b[2] + (1 - l0 - l1) * c[2]
            best = z if best is None else max(best, z)
    return best


class BoxElements(unittest.TestCase):
    def test_a_box_is_placed_by_its_planes_saved_w_first(self):
        """CSmallScout_Farm's backdrop grass (BckGroundGrass_A_A): its box's X axis looks down, its Z axis along the
        mesh's X, its origin 67.87 up; read W first, it lies flat as the drawn mesh does (x ±2090, y ±1557, z 0..154)."""
        tm = plane(0, 0, 0, -1) + plane(0, 0, 1, 0) + plane(0, 1, 0, 0) + plane(1, 0, 0, 67.8689)
        elem = {('TM', 0): {'value': tm}, ('X', 0): {'value': 135.7377}, ('Y', 0): {'value': 3167.919},
                ('Z', 0): {'value': 4227.529}}
        pts = collision._box_triangles(elem)
        self.assertEqual(len(pts), 36)
        lo = [round(min(p[k] for p in pts), 1) for k in range(3)]
        hi = [round(max(p[k] for p in pts), 1) for k in range(3)]
        self.assertEqual(lo, [-2113.8, -1584.0, 0.0])
        self.assertEqual(hi, [2113.8, 1584.0, 135.7])

    def test_a_box_without_a_matrix_stands_at_the_origin(self):
        pts = collision._box_triangles({('X', 0): {'value': 2.0}, ('Y', 0): {'value': 4.0}, ('Z', 0): {'value': 6.0}})
        self.assertEqual([min(p[k] for p in pts) for k in range(3)], [-1, -2, -3])
        self.assertEqual([max(p[k] for p in pts) for k in range(3)], [1, 2, 3])


class MeshIds(unittest.TestCase):
    def test_a_streamed_patchs_mesh_is_not_the_maps_own(self):
        class P:
            exports = [{}] * 10
            cls = staticmethod(lambda i: 'StaticMesh' if i == 7 else 'Texture2D')
        self.assertEqual(collision.mesh_export(P, '7'), 7)
        self.assertEqual(collision.mesh_export(P, '7-284e324d95f9'), 7)
        self.assertIsNone(collision.mesh_export(P, '8'))
        self.assertIsNone(collision.mesh_export(P, '11'))
        self.assertIsNone(collision.mesh_export(P, 'stream-patch_farm-278'))


class Cache(unittest.TestCase):
    def test_a_package_other_than_the_one_exported_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Map.upk'
            path.write_bytes(b'not the exported map')
            with self.assertRaisesRegex(FormatError, 'not the file this map was exported from'):
                collision.CollisionCache().get('root', {'source': {'sha256': '0' * 64}}, lambda: path, ['1'])


@unittest.skipUnless(FARM and FARM.exists(), NO_FARM)
class Farm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = Package(FARM)

    def test_the_ramps_hulls_stand_over_the_drawn_ramp_where_the_floors_went(self):
        """TornEarth.Meshes.SmallscoutRamps (XComLevelActor_28 at (480, -2016, 0), unturned): ten convex hulls, their top
        86.15 and 49.64 at the tile centres of EXP-32 run 2, where the drawn ramp is at 80.9 and 48.0 and floors 1 unit
        over the drawn ramp weren't found."""
        mesh = self.p.by_name['TornEarth.Meshes.SmallscoutRamps']
        c = collision.line_collision(self.p, mesh)
        self.assertTrue(c['simple'])
        self.assertEqual(len(c['elements']), 10)
        self.assertAlmostEqual(top_along(c['elements'], (480, -2016, 0), 1776, -3120), 86.15, places=1)
        self.assertAlmostEqual(top_along(c['elements'], (480, -2016, 0), 1872, -3216), 49.64, places=1)

    def test_the_backdrop_grass_box_lies_flat_as_drawn(self):
        mesh = self.p.by_name['Sidewalk.Meshes.BckGroundGrass_A_A']
        c = collision.line_collision(self.p, mesh)
        self.assertEqual(len(c['elements']), 1)
        flat = c['elements'][0]
        zs = flat[2::3]
        self.assertEqual((round(min(zs), 1), round(max(zs), 1)), (0.0, 135.7))
