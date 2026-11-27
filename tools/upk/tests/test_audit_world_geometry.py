"""The D5 check (audit_world_geometry; game-likeness plan, stage D5): its readers of a level's model, a model component
and an instanced mesh component on made-up packages, and what it finds on the install's maps (skipped without it)."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import audit_world_geometry as audit  # noqa: E402
import labpaths  # noqa: E402
from package import Package  # noqa: E402
from upk_fixtures import made_up_package  # noqa: E402

# the configured install's packages, or the folder XCOM_COOKED names
COOKED = Path(labpaths.lwr_cooked() or 'no-install-configured')
HEAD = struct.pack('<i', 7) + struct.pack('<2i', 0, 0)      # a net index, then no tagged properties
SQUARE = [(0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 50.0, 0.0), (0.0, 50.0, 0.0)]


def bulk(size, rows):
    return struct.pack('<2i', size, len(rows)) + b''.join(rows)


def node(surf, pool, vertices, component=0):
    raw = bytearray(64)
    struct.pack_into('<ii', raw, 16, pool, surf)
    struct.pack_into('<H', raw, 28, component)
    raw[54] = vertices
    return bytes(raw)


def model_body(flags=0xE00, vertices=4):
    native = (bytes(28) + bulk(12, []) + bulk(12, [struct.pack('<3f', *v) for v in SQUARE])
              + bulk(64, [node(0, 0, vertices)]) + struct.pack('<i', 0)
              + struct.pack('<i', 1) + struct.pack('<iI', 0, flags) + bytes(20) + struct.pack('<i', 0) + bytes(28)
              + bulk(24, [struct.pack('<i', k) + bytes(20) for k in range(4)]))
    return HEAD + native


def component_body(model=1, tail=b''):
    native = (struct.pack('<ii', model, 1) + struct.pack('<i', 1)
              + struct.pack('<i', 0)                                  # its lightmap: none
              + struct.pack('<ii', 2, 0) + struct.pack('<iH', 1, 0)   # the component, no material; node 0
              + struct.pack('<i', 0) + struct.pack('<i', 1) + bytes(16)  # no shadow maps; one irrelevant light
              + struct.pack('<H', 0) + struct.pack('<iH', 1, 0))      # its index; its nodes
    return HEAD + native + tail


def lod():
    return struct.pack('<ii', 0, 0) + struct.pack('<i', 0) + b'\x00' + struct.pack('<i', 0)


def instanced_body(size=80, places=((10.0, 20.0, 30.0), (40.0, 50.0, 60.0))):
    rows = []
    for x, y, z in places:
        rows.append(struct.pack('<16f', 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1) + struct.pack('<4f', .5, .25, 0, 0)
                    + bytes(size - 80))
    native = struct.pack('<i', 1) + lod() + lod() + lod() + struct.pack('<2i', 0, 0) + bulk(size, rows)
    return HEAD + native


class MadeUp(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def package(self, objects):
        data, _ = made_up_package(objects)
        path = Path(self.folder.name) / 'Made.upk'
        path.write_bytes(data)
        return Package(path)

    def test_a_model_gives_its_nodes_surfaces_and_points(self):
        p = self.package((('Model', 'Model_1', 0, model_body()),))
        got = audit.model_values(p, 1)
        self.assertEqual(got['nodes'], [dict(surf=0, vertPool=0, vertices=4, component=0)])
        self.assertEqual(got['surfaces'], [dict(material=0, flags=0xE00, actor=0)])
        self.assertEqual(got['verts'], [0, 1, 2, 3])
        self.assertEqual(got['points'][2], (100.0, 50.0, 0.0))

    def test_a_node_past_the_vertex_pool_is_refused(self):
        p = self.package((('Model', 'Model_1', 0, model_body(vertices=5)),))
        with self.assertRaises(audit.GeometryError):
            audit.model_values(p, 1)

    def test_a_model_component_reads_to_its_last_byte(self):
        p = self.package((('Model', 'Model_1', 0, model_body()), ('ModelComponent', 'ModelComponent_1', 0,
                                                                  component_body())))
        got = audit.model_component(p, 2)
        self.assertEqual((got['model'], got['zone'], got['componentIndex'], got['nodes']), (1, 1, 0, [0]))
        self.assertEqual(got['elements'], [dict(lightmap=0, component=2, material=0, nodes=[0], shadowMaps=[],
                                                irrelevantLights=1)])

    def test_bytes_after_a_model_component_are_refused(self):
        p = self.package((('Model', 'Model_1', 0, model_body()), ('ModelComponent', 'ModelComponent_1', 0,
                                                                  component_body(tail=b'\0\0'))))
        with self.assertRaises(audit.GeometryError):
            audit.model_component(p, 2)

    def test_an_instanced_component_gives_each_instance(self):
        p = self.package((('InstancedStaticMeshComponent', 'Inst_1', 0, instanced_body()),))
        got = audit.instances(p, 1)
        self.assertEqual([g['matrix'][12:15] for g in got], [[10.0, 20.0, 30.0], [40.0, 50.0, 60.0]])
        self.assertEqual(got[0]['lightmapBias'], [0.5, 0.25])

    def test_instances_of_another_size_are_refused(self):
        p = self.package((('InstancedStaticMeshComponent', 'Inst_1', 0, instanced_body(size=84)),))
        with self.assertRaises(audit.GeometryError):
            audit.instances(p, 1)


def install_package(name):
    path = COOKED / f'{name}.upk'
    if not path.exists():
        raise unittest.SkipTest(f'{name} not available')
    return path


class Install(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (COOKED / 'XComGame.upk').exists():
            raise unittest.SkipTest('no install configured')
        cls.classes = audit.Classes(COOKED)

    def test_the_toggled_kind_and_its_visibility_bit(self):
        self.assertTrue(self.classes.toggled('XComFracDecoComponent'))
        self.assertTrue(self.classes.instanced('XComFracDebrisComponent'))
        self.assertFalse(self.classes.instanced('StaticMeshComponent'))
        self.assertEqual(self.classes.visibility, 0x800000)

    def test_the_tutorial_script_level_draws_a_box_of_bsp(self):
        rec = audit.package_record(install_package('Act2_Pier_script'), self.classes)
        b = rec['bsp']
        self.assertEqual((b['components'], b['drawnNodes'], b['drawnTriangles']), (3, 6, 12))
        self.assertEqual(b['materials'], {'EngineMaterials.DefaultMaterial': 6})
        self.assertEqual(b['box'], dict(min=[1056.0, -528.0, 4096.0], max=[2256.0, 112.0, 4352.0]))
        self.assertEqual(b['problems'], [])

    def test_the_bar_draws_no_bsp_and_no_instance_as_it_loads(self):
        rec = audit.package_record(install_package('URB_Bar'), self.classes)
        self.assertEqual((rec['bsp']['components'], rec['bsp']['problems'], rec['terrain']), (0, [], {}))
        flame = [r for r in rec['instanced'] if r['cls'] == 'InstancedStaticMeshComponent']
        self.assertEqual(sorted(r['archetype'] for r in flame), ['FlameThrowerHit', 'FlameThrowerSplash'])
        self.assertTrue(all(r['hidden'] and r['instances'] == 0 for r in flame))
        self.assertEqual(sum(r['drawnAtLoad'] for r in rec['instanced']), 0)

    def test_a_broken_wall_draws_the_chunks_at_its_broken_edges(self):
        rec = audit.package_record(install_package('URB_PoliceStation'), self.classes)
        deco = [r for r in rec['instanced'] if r['cls'] == 'XComFracDecoComponent']
        self.assertEqual(sum(r['drawnAtLoad'] for r in deco), 70)
        # every saved bit is what the broken-edge rule gives
        pairs = {k for r in deco for k in r['rule']}
        self.assertLessEqual(pairs, {'True/True', 'False/False'})


if __name__ == '__main__':
    unittest.main()
