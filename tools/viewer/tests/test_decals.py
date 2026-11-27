"""The map's placed decals in the export (decals.py; game-likeness plan, D1, export 46): a decal's mesh made from its
stored receivers (each part's index range, the vertices in the world in the mesh's axes, the texture coordinates,
blend and depth the game's decal vertex shader gives them, its tangent frame), a part on a piece the export lacks left
out; on the install's URB_Bar, every decal's record (its actor, place, frame, size, material, the piece it lies on and
its receivers by piece) and its mesh file (skipped without it)."""
from pathlib import Path
import json
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'upk'))
import numpy as np  # noqa: E402
import decals  # noqa: E402
import decal_records  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
# a decal looking down from (100, 200, 30): its tangent the world's -y, its binormal +x (decal_records.owner_frame)
FRAME = dict(location=[100.0, 200.0, 30.0], tangent=[0.0, -1.0, 0.0], binormal=[1.0, 0.0, 0.0], normal=[0.0, 0.0, 1.0],
             width=200.0, height=100.0, tile=[1.0, 1.0], offset=[0.0, 0.0], nearPlane=0.0, farPlane=300.0,
             blendRange=[89.5, 180.0], depthBias=-1e-05, decalRotation=0.0)


def receiver(positions, indices, normal=(127, 127, 255, 255)):
    raw = b''.join(struct.pack('<3f', *p) + bytes((255, 127, 127, 128)) + bytes(normal) + bytes(8) for p in positions)
    return dict(vertices=raw, vertexCount=len(positions), indices=tuple(indices), triangles=len(indices) // 3)


def glb_json(path):
    data = Path(path).read_bytes()
    size = struct.unpack_from('<I', data, 12)[0]
    return json.loads(data[20:20 + size])


class TheMesh(unittest.TestCase):
    def test_parts_their_ranges_and_what_the_vertex_shader_gives(self):
        identity = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        moved = [[1, 0, 0, 100], [0, 1, 0, 200], [0, 0, 1, 0], [0, 0, 0, 1]]
        floor = receiver([(100, 200, 0), (100, 300, 0), (50, 200, 0)], (0, 1, 2))
        square = receiver([(0, 0, 0), (50, 0, 0), (0, 100, 0), (50, 100, 0)], (0, 1, 2, 2, 1, 3))
        mesh, ranges = decals.decal_mesh(FRAME, [(floor, identity), (square, moved)])
        self.assertEqual([(first, count) for first, count, _ in ranges], [(0, 3), (3, 6)])
        self.assertEqual(mesh['indices'], [0, 1, 2, 3, 4, 5, 5, 4, 6])        # the second part's after the first's
        self.assertAlmostEqual(ranges[0][2], 50 * 100 / 2)
        self.assertAlmostEqual(ranges[1][2], 50 * 100)
        positions = np.asarray(mesh['positions']).reshape(-1, 3)
        self.assertEqual(positions[3].tolist(), [100, 0, 200])                 # in the mesh's axes: x, z, y
        uv = np.asarray(mesh['uvs'][0]).reshape(-1, 2)
        self.assertTrue(np.allclose(uv[:3], [[0.5, 0.5], [1.0, 0.5], [0.5, 1.0]]))
        blend_depth = np.asarray(mesh['uvs'][1]).reshape(-1, 2)
        self.assertTrue(np.allclose(blend_depth[:, 0], 1.0) and np.allclose(blend_depth[:, 1], 30.0))
        # the decal's tangent on a floor is the way u grows (+y), in the mesh's axes (0, 0, 1); its binormal (-x) is
        # cross(normal, tangent) * w in the game's axes, w written negated in the mesh's
        tangents = np.asarray(mesh['tangents']).reshape(-1, 4)
        self.assertTrue(np.allclose(tangents[0], [0, 0, 1, -1], atol=1e-2), tangents[0])
        self.assertEqual(mesh['sections'], [dict(first=0, count=9, slot=0)])



@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class OnTheInstall(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import export
        from package import Package
        cls.folder = tempfile.TemporaryDirectory()
        cls.p = Package(BAR)
        cls.ex = export.Exporter(cls.p, Path(cls.folder.name))
        cls.ex.prefabs = export.prefab_members(cls.p, cls.ex.warn)
        # the pieces the decals lie on, as the export makes them
        wanted = set()
        for i in range(1, len(cls.p.exports) + 1):
            if cls.p.cls(i) == 'DecalComponent':
                wanted |= {r['component'] for r in decal_records.receivers(cls.p.native(i), cls.p)}
        cls.objects = [cls.ex.component(cls.p.exports[c - 1]['outer'], c) for c in sorted(wanted)]
        cls.records = decals.records(cls.ex, cls.objects)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_every_decal_and_its_parts(self):
        found = self.records
        self.assertEqual(len(found), 38)
        self.assertEqual(sum(r['mesh']['vertices'] for r in found), 12140)
        self.assertEqual(sum(r['mesh']['triangles'] for r in found), 4434)
        self.assertEqual(sum(len(r['receivers']) for r in found), 51)
        ids = {o['id'] for o in self.objects}
        for r in found:
            with self.subTest(r['actor']):
                self.assertTrue(r['actor'].startswith('TheWorld.PersistentLevel.DecalActor_'))
                self.assertEqual((r['actorClass'], r['layer'], r['sourcePackage'], r['listed'], r['hidden']),
                                 ('DecalActor', 'base', 'URB_Bar', True, False))
                self.assertEqual(r['id'], f"{self.p.by_name[r['actor']]}:{self.p.by_name[r['component']]}")
                # the frame is the actor's (owner_frame)
                place, tangent, binormal, normal = decal_records.owner_frame(r['location'], r['rotation'])
                self.assertTrue(np.allclose(r['frame']['normal'], normal, atol=1e-5))
                self.assertTrue(np.allclose(r['frame']['tangent'], tangent, atol=1e-5))
                self.assertTrue(np.allclose(r['frame']['location'], place, atol=1e-3))
                self.assertGreater(r['size']['width'], 0)
                self.assertGreater(r['size']['farPlane'], r['size']['nearPlane'])
                self.assertIn(r['material'], self.ex.materials)
                # its parts, one after the other, each on a piece of the export
                at = 0
                for part in r['receivers']:
                    self.assertIn(part['piece'], ids)
                    self.assertEqual((part['first'], part['count']), (at, 3 * part['triangles']))
                    at += part['count']
                self.assertEqual(at, 3 * r['mesh']['triangles'])
                self.assertEqual(r['liesOn'], max(r['receivers'], key=lambda x: x['area'])['piece'])
                glb = glb_json(Path(self.folder.name) / r['mesh']['url'])
                attributes = glb['meshes'][0]['primitives'][0]['attributes']
                self.assertEqual(set(attributes), {'POSITION', 'NORMAL', 'TANGENT', 'TEXCOORD_0', 'TEXCOORD_1'})
                self.assertEqual(glb['accessors'][attributes['POSITION']]['count'], r['mesh']['vertices'])
        # no decal of URB_Bar is a prefab's: the fog pod's (KNOWN-BUGS.md KB-3) are actors of their own around it
        self.assertEqual({r['prefab'] for r in found}, {None})
        by_actor = {r['actor'].rsplit('.', 1)[-1]: r for r in found}
        burnt = by_actor['DecalActor_1']          # the charred patch beside the fog pod: on a car and the ground
        self.assertEqual([part['actor'].rsplit('.', 1)[-1] for part in burnt['receivers']],
                         ['XComDestructibleActor_33', 'XComLevelActor_263'])
        self.assertEqual(burnt['size']['blendRange'], [50.0, 80.0])

    def test_a_part_on_a_piece_the_export_lacks_is_left_out(self):
        import export
        gone = self.objects[0]['id']
        ex = export.Exporter(self.p, Path(self.folder.name) / 'without')
        ex.folder.mkdir()
        ex.prefabs = self.ex.prefabs
        found = decals.records(ex, self.objects[1:])
        self.assertEqual(len(found), 38)
        self.assertFalse(any(part['piece'] == gone for r in found for part in r['receivers']))
        self.assertTrue(any('is left out' in d['message'] for d in ex.diagnostics))
        self.assertLess(sum(r['mesh']['triangles'] for r in found if r['mesh']), 4434)


if __name__ == '__main__':
    unittest.main()
