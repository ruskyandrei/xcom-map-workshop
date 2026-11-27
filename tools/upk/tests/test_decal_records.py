"""A placed decal as the game stores it (decal_records.py; game-likeness plan, D1; F-210, F-211): its receivers read to
the component's end, its frame from its owner, its size over the class's defaults (an archetype's members among
them) and what the game's decal vertex shader makes of a point, on made-up packages; on the install's URB_Bar, every
decal read, its stored vertices inside its box and its saved members its owner's frame; the defaults against
Engine.upk (skipped without the install)."""
from pathlib import Path
import math
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
import paths  # noqa: E402
paths.use('upk', 'viewer', 'lab')
import numpy as np  # noqa: E402
import decal_records  # noqa: E402
from package import FormatError, Package  # noqa: E402
import labpaths  # noqa: E402
sys.path.insert(0, str(HERE))
from upk_fixtures import made_up_package  # noqa: E402

BAR, NO_BAR = labpaths.install_map('URB_Bar')
ENGINE, NO_ENGINE = labpaths.install_map('Engine')
NAMES = ('Location', 'Rotation', 'StructProperty', 'Vector', 'Rotator', 'Width', 'Height', 'FloatProperty',
         'FarPlane', 'HitNormal')


def vertex(position, tangent=(255, 127, 127, 128), normal=(127, 127, 255, 255)):
    return struct.pack('<3f', *position) + bytes(tangent) + bytes(normal) + struct.pack('<2f', 0, 0)


def receiver(component, positions, indices, triangles=None, lightmap=0, shadows=(), closing=(0, 0)):
    """One stored receiver: the component, the sized vertices and indices, the triangles, the lightmap's type, the
    counted shadow maps and the two closing integers."""
    verts = b''.join(vertex(p) for p in positions)
    out = struct.pack('<i', component) + struct.pack('<2i', 28, len(positions)) + verts
    out += struct.pack('<2i', 2, len(indices)) + struct.pack('<%dH' % len(indices), *indices)
    out += struct.pack('<i', len(indices) // 3 if triangles is None else triangles) + struct.pack('<i', lightmap)
    out += struct.pack('<i', len(shadows)) + b''.join(struct.pack('<i', s) for s in shadows)
    return out + struct.pack('<2i', *closing)


FLOOR = [(0.0, 0.0, 0.0), (96.0, 0.0, 0.0), (0.0, 96.0, 0.0)]


def decal_package(folder, receivers=None, own=None, archetype=None, tail=b''):
    """A made-up map: export 1 a DecalActor at (100, 200, 30) looking down (pitch -90), export 2 its DecalComponent
    (its own members `own` {name: (kind, struct or None, value bytes)}, its receivers, then `tail`), export 3 a
    StaticMeshComponent the decal lies on, export 4 a DecalComponent archetype of export 2 with members `archetype`
    when given. Returns the package read."""
    names = ['None', 'Core', 'Engine', 'Package', 'Class', 'DecalActor', 'DecalComponent', 'StaticMeshComponent',
             'Actor', 'Decal', 'Floor', 'Template'] + list(NAMES)
    index = {n: i for i, n in enumerate(names)}

    def tag(name, kind, sub, value):
        head = struct.pack('<6i', index[name], 0, index[kind], 0, len(value), 0)
        return head + (struct.pack('<2i', index[sub], 0) if sub else b'') + value

    def body(members):
        return struct.pack('<i', 0) + b''.join(tag(n, k, s, v) for n, (k, s, v) in members.items()) + struct.pack('<2i', 0, 0)
    actor = body({'Location': ('StructProperty', 'Vector', struct.pack('<3f', 100, 200, 30)),
                  'Rotation': ('StructProperty', 'Rotator', struct.pack('<3i', -16384, 0, 0))})
    stored = [receiver(3, FLOOR, (0, 1, 2))] if receivers is None else receivers
    component = body(own or {}) + struct.pack('<i', len(stored)) + b''.join(stored) + tail
    objects = [('DecalActor', 'Actor', 0, actor), ('DecalComponent', 'Decal', 1, component),
               ('StaticMeshComponent', 'Floor', 0, body({}))]
    if archetype is not None:
        objects.append(('DecalComponent', 'Template', 0, body(archetype) + struct.pack('<i', 0)))
    # (Template named whether or not the archetype is made, so that the names' places are the ones `index` gives)
    data, places = made_up_package(tuple(objects), extra_names=('Template',) + NAMES)
    if archetype is not None:                  # export 2's archetype is export 4
        struct.pack_into('<i', data := bytearray(data), places['export_at'][1] + 20, 4)
        data = bytes(data)
    path = Path(folder) / 'Decals.upk'
    path.write_bytes(data)
    return Package(path)


class MadeUp(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def test_a_receiver_reads_to_the_components_end(self):
        p = decal_package(self.folder.name)
        found = decal_records.receivers(p.native(2), p)
        self.assertEqual(len(found), 1)
        rec = found[0]
        self.assertEqual((rec['component'], rec['vertexCount'], rec['indices'], rec['triangles'], rec['lightmap'],
                          rec['shadowMaps'], rec['data'], rec['instance'], rec['indexed']),
                         (3, 3, (0, 1, 2), 1, 0, [], 0, 0, True))
        self.assertEqual(struct.unpack_from('<i', p.data, rec['componentAt'])[0], 3)
        positions, tangents, normals = decal_records.vertices(rec)
        self.assertEqual(positions.tolist(), [list(v) for v in FLOOR])
        self.assertTrue(np.allclose(normals[:, :3], [[-0.0039, -0.0039, 1.0]] * 3, atol=1e-3))
        self.assertTrue(np.allclose(tangents[:, 0], 1.0))

    def test_a_decal_that_is_not_clipped_has_no_indices(self):
        p = decal_package(self.folder.name, [receiver(3, FLOOR, (), triangles=1)])
        rec = decal_records.receivers(p.native(2), p)[0]
        self.assertEqual((rec['indices'], rec['indexed']), ((0, 1, 2), False))

    def test_what_does_not_fit_is_refused(self):
        cases = {'bytes left': dict(tail=b'\x00' * 4),
                 'lightmap': dict(receivers=[receiver(3, FLOOR, (0, 1, 2), lightmap=2)]),
                 'index past': dict(receivers=[receiver(3, FLOOR, (0, 1, 5))]),
                 'triangles': dict(receivers=[receiver(3, FLOOR, (0, 1, 2), triangles=2)]),
                 'no object': dict(receivers=[receiver(9, FLOOR, (0, 1, 2))]),
                 'cut short': dict(receivers=[receiver(3, FLOOR, (0, 1, 2))[:-6]])}
        for why, given in cases.items():
            with self.subTest(why):
                p = decal_package(self.folder.name, **given)
                with self.assertRaises(FormatError):
                    decal_records.receivers(p.native(2), p)

    def test_the_frame_is_the_owners_and_the_size_over_the_defaults(self):
        p = decal_package(self.folder.name, own={'Width': ('FloatProperty', None, struct.pack('<f', 300.0))})
        f = decal_records.frame(p, 2)
        self.assertTrue(f['byOwner'])
        self.assertEqual(f['location'], [100.0, 200.0, 30.0])
        for got, want in ((f['normal'], [0, 0, 1]), (f['tangent'], [0, -1, 0]), (f['binormal'], [1, 0, 0])):
            self.assertTrue(np.allclose(got, want, atol=1e-6), (got, want))
        self.assertEqual((f['width'], f['height'], f['farPlane'], f['tile'], f['blendRange']),
                         (300.0, 200.0, 300.0, [1.0, 1.0], [89.5, 180.0]))

    def test_an_archetypes_members_are_the_decals(self):
        # a decal placed from an archetype saves its size there (URB_CommercialStreet's civilians' bodies)
        p = decal_package(self.folder.name, own={'Width': ('FloatProperty', None, struct.pack('<f', 75.0))},
                          archetype={'Height': ('FloatProperty', None, struct.pack('<f', 275.0)),
                                     'Width': ('FloatProperty', None, struct.pack('<f', 999.0)),
                                     'HitNormal': ('StructProperty', 'Vector', struct.pack('<3f', 0, 0, 1))})
        f = decal_records.frame(p, 2)
        self.assertEqual((f['width'], f['height']), (75.0, 275.0))
        self.assertEqual(decal_records.saved_frame(p, 2), {'HitNormal': [0.0, 0.0, 1.0]})
        self.assertEqual(decal_records.receivers(p.native(4), p), [])         # an archetype has no receivers


class TheVertexShader(unittest.TestCase):
    """coordinates and surface_frame: what the game's decal vertex shader makes of points (F-211)."""
    FRAME = dict(location=[100.0, 200.0, 30.0], tangent=[0.0, -1.0, 0.0], binormal=[1.0, 0.0, 0.0],
                 normal=[0.0, 0.0, 1.0], width=200.0, height=100.0, tile=[1.0, 1.0], offset=[0.0, 0.0],
                 blendRange=[50.0, 80.0])

    def test_the_box_runs_from_nought_to_one(self):
        f = self.FRAME
        up = [[0, 0, 1]] * 4
        # the centre; the decal's -tangent side (u 1) and its -binormal side (v 1); the far corner
        points = [[100, 200, 0], [100, 300, 0], [50, 200, 0], [150, 100, 10]]
        u, v, blend, depth = decal_records.coordinates(f, points, up)
        self.assertTrue(np.allclose(u, [0.5, 1.0, 0.5, 0.0]))
        self.assertTrue(np.allclose(v, [0.5, 0.5, 1.0, 0.0]))
        self.assertTrue(np.allclose(depth, [30, 30, 30, 20]))
        self.assertTrue(np.allclose(blend, 1.0))

    def test_tiling_and_offsets(self):
        f = dict(self.FRAME, tile=[2.0, 1.0], offset=[0.25, -0.5])
        u, v, _, _ = decal_records.coordinates(f, [[100, 300, 0]], [[0, 0, 1]])
        self.assertTrue(np.allclose([u[0], v[0]], [0.25 + 1.0 + 0.5, -0.5 + 0.5]))

    def test_the_blend_by_the_surfaces_angle(self):
        # full up to BlendRange.X (50 degrees off the decal's normal), none past BlendRange.Y (80 degrees), linear in
        # the cosine between them
        f = self.FRAME
        middle = math.degrees(math.acos((math.cos(math.radians(50)) + math.cos(math.radians(80))) / 2))
        normals = [[math.sin(math.radians(a)), 0, math.cos(math.radians(a))] for a in (0, 50, middle, 80, 120)]
        _, _, blend, _ = decal_records.coordinates(f, [[100, 200, 0]] * 5, normals)
        self.assertTrue(np.allclose(blend, [1.0, 1.0, 0.5, 0.0, 0.0], atol=1e-6), blend)

    def test_the_decals_frame_on_a_surface(self):
        f = self.FRAME
        tangent, binormal = decal_records.surface_frame(f, [[0, 0, 1], [0, 0.6, 0.8], [0, 1, 0]])
        # on a floor: the frame's tangent and binormal negated (the ways u and v grow)
        self.assertTrue(np.allclose(tangent[0], [0, 1, 0]) and np.allclose(binormal[0], [-1, 0, 0]))
        # on a slope: turned into it, still unit and on the surface
        self.assertTrue(np.isclose(np.linalg.norm(tangent[1]), 1.0) and np.isclose(tangent[1] @ [0, 0.6, 0.8], 0.0))
        # edge on to the tangent: none
        self.assertTrue(np.allclose(tangent[2], 0.0))

    def test_a_receivers_vertices_in_the_world(self):
        m = [[2, 0, 0, 10], [0, 1, 0, 20], [0, 0, 1, 30], [0, 0, 0, 1]]
        points, normals = decal_records.in_world(m, [[1, 1, 1]], [[1, 0, 1, 1]])
        self.assertTrue(np.allclose(points, [[12, 21, 31]]))
        self.assertTrue(np.allclose(normals, [[1 / math.sqrt(5), 0, 2 / math.sqrt(5)]]))        # inverse transpose


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class InstallBar(unittest.TestCase):
    def test_every_decal_reads_and_lies_in_its_box(self):
        from export_math import multiply, transform
        p = Package(BAR)

        def placed(component):          # a receiver's actor and component transforms, as the export places a piece
            actor = p.exports[component - 1]['outer']
            scale = [v * p.effective(actor, 'DrawScale', 1) for v in p.effective(actor, 'DrawScale3D', [1, 1, 1])]
            return multiply(transform(p.effective(actor, 'Location', [0, 0, 0]), p.effective(actor, 'Rotation', [0, 0, 0]),
                                      scale),
                            transform(p.effective(component, 'Translation', [0, 0, 0]),
                                      p.effective(component, 'Rotation', [0, 0, 0]), p.effective(component, 'Scale3D', [1, 1, 1])))
        decals = receivers = vertices = triangles = 0
        for i in range(1, len(p.exports) + 1):
            if p.cls(i) != 'DecalComponent':
                continue
            found = decal_records.receivers(p.native(i), p)
            if not found:
                continue
            decals += 1
            f = decal_records.frame(p, i)
            # the Hit members it saves are its owner's frame (F-210)
            got = dict(zip(decal_records.FRAME, (f['location'], f['tangent'], f['binormal'], f['normal'])))
            for key, value in decal_records.saved_frame(p, i).items():
                self.assertTrue(np.allclose(value, got[key], atol=1e-3), (p.name(i), key))
            for rec in found:
                receivers += 1
                vertices += rec['vertexCount']
                triangles += rec['triangles']
                points, normals = decal_records.in_world(placed(rec['component']),
                                                         *decal_records.vertices(rec)[::2])
                u, v, _, depth = decal_records.coordinates(f, points, normals)
                self.assertTrue(((u > -0.01) & (u < 1.01) & (v > -0.01) & (v < 1.01)).all(), p.name(i))
                self.assertTrue(((depth > f['nearPlane'] - 1) & (depth < f['farPlane'] + 1)).all(), p.name(i))
        # research/evidence/decal-audit-2026-11-27.json
        self.assertEqual((decals, receivers, vertices, triangles), (38, 51, 12140, 4434))


@unittest.skipUnless(ENGINE and ENGINE.exists(), NO_ENGINE)
class InstallDefaults(unittest.TestCase):
    def test_the_defaults_are_engines(self):
        p = Package(ENGINE)
        base = p.by_name['Default__DecalComponent']
        for key, value in decal_records.DEFAULTS.items():
            saved = p.own(base, key)
            if key == 'BlendRange':
                saved = list(struct.unpack('<2f', bytes(saved)))
            self.assertTrue(np.allclose(saved if saved is not None else 0.0, value, atol=1e-9), key)
        # the decal actor's component templates change none of them
        for template in ('Default__DecalActorBase.NewDecalComponent', 'Default__DecalActor.NewDecalComponent'):
            own = {k for (k, _) in p.properties(p.by_name[template])[0]}
            self.assertFalse(own & set(decal_records.DEFAULTS), template)


if __name__ == '__main__':
    unittest.main()
