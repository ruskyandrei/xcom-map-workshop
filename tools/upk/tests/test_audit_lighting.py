"""Native static-mesh-component lighting records in EW (licensee 64) and UDK (licensee 0) packages."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import audit_lighting as lighting  # noqa: E402
from package import Reader  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

# UDK_EXAMPLE_MAP, else the one in UDK (the udk setting)
UDK_EXAMPLE, NO_UDK_EXAMPLE = labpaths.test_file(
    'UDK_EXAMPLE_MAP', labpaths.configured('udk', 'UDKGame', 'Content', 'Maps', 'Examples', 'ExampleMap.udk'),
    'UDK 2011-09 ExampleMap.udk')


def lod(lightmap_type=2):
    """One LOD record: no shadow maps or vertex buffers, a 2D lightmap (or none), no vertex colours, no positions."""
    out = struct.pack('<ii', 0, 0) + struct.pack('<i', lightmap_type)
    if lightmap_type == 2:
        out += struct.pack('<i', 1) + bytes(range(16))
        for ref, s in ((1, 1.0), (2, 3.0), (3, 2.0)):
            out += struct.pack('<i3f', ref, s, s, s)
        out += struct.pack('<4f', 0.25, 0.25, 0.5, 0.75)
    return out + b'\0' + struct.pack('<i', 0)


class StubPackage:
    def __init__(self, licensee, native):
        self.header = dict(ver=845, lic=licensee)
        self.data = native

    def native(self, index):
        return Reader(self.data)

    def name(self, ref):
        return {0: 'None', 1: 'NormalizedAverageColor0_1', 2: 'DirectionalMaxComponent0_1',
                3: 'SimpleLightmap_0_1', 4: 'SwapMesh'}[ref]

    def cls(self, index):
        return 'StaticMeshComponent'


class ComponentRecord(unittest.TestCase):
    def test_ew_record_has_two_swap_lods_and_meshes(self):
        native = struct.pack('<i', 1) + lod() + lod(0) + lod(0) + struct.pack('<ii', 4, 0)
        r = lighting.component_record(StubPackage(64, native), 1)
        self.assertEqual(len(r['lods']), 1)
        self.assertEqual(len(r['swaps']), 2)
        self.assertEqual(r['swapMeshes'], ['SwapMesh', 'None'])
        self.assertEqual(r['lods'][0]['lightmap']['slots'][1]['scale'], [3.0, 3.0, 3.0])

    def test_udk_record_ends_after_the_lod_array(self):
        native = struct.pack('<i', 1) + lod()
        r = lighting.component_record(StubPackage(0, native), 1)
        self.assertEqual((r['swaps'], r['swapMeshes']), ([], []))
        lm = r['lods'][0]['lightmap']
        self.assertEqual([s['texture'] for s in lm['slots']],
                         ['NormalizedAverageColor0_1', 'DirectionalMaxComponent0_1', 'SimpleLightmap_0_1'])
        self.assertEqual(lm['coordinateBias'], [0.5, 0.75])

    def test_trailing_bytes_are_refused_for_static_mesh_components(self):
        native = struct.pack('<i', 1) + lod() + b'\0\0\0\0'
        with self.assertRaises(lighting.FormatError):
            lighting.component_record(StubPackage(0, native), 1)


@unittest.skipUnless(UDK_EXAMPLE and UDK_EXAMPLE.exists(), NO_UDK_EXAMPLE)
class UdkExampleMap(unittest.TestCase):
    def test_lightmass_writes_ews_directional_pair_plus_a_simple_lightmap(self):
        p = lighting.Package(UDK_EXAMPLE)
        self.assertEqual((p.header['ver'], p.header['lic']), (845, 0))
        kinds, names = set(), set()
        for i in range(1, len(p.exports) + 1):
            if p.cls(i) == 'StaticMeshComponent' and p.name(i).startswith('TheWorld.'):
                for record in lighting.component_record(p, i)['lods']:
                    lm = record['lightmap']
                    kinds.add(lm['type'])
                    if lm['type'] == 2:
                        names.add(tuple(s['texture'].rstrip('0123456789_') for s in lm['slots']))
        self.assertIn(2, kinds)
        self.assertEqual(names, {('NormalizedAverageColor', 'DirectionalMaxComponent', 'SimpleLightmap')})


if __name__ == '__main__':
    unittest.main()
