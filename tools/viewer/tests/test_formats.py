"""Synthetic regression fixtures; no game data is needed or stored here."""
import io
from pathlib import Path
import struct
import sys
import unittest
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from package import Reader, FormatError
from mesh import read_mesh
from export import transform, view_matrix, multiply
from texture import decompress_payload, dds_header
from PIL import Image
from viewer_fixtures import minimal_mesh


class FixturePackage:
    def __init__(self,blob): self.blob=blob
    def native(self,index): return Reader(self.blob)
    def name(self,index): return 'SyntheticTriangle'


class FormatTests(unittest.TestCase):
    def test_truncated_record_rejected(self):
        with self.assertRaises(FormatError): Reader(b'\0').u32()
        with self.assertRaises(FormatError): Reader(b'\xff'*4).count()
        with self.assertRaises(FormatError): read_mesh(FixturePackage(minimal_mesh()[:-1]),1)

    def test_mesh_winding_and_uvs(self):
        mesh = read_mesh(FixturePackage(minimal_mesh()),1)
        self.assertEqual(mesh['indices'],[0,1,2])
        a,b,c = [mesh['positions'][i:i+3] for i in (0,3,6)]
        u,v = [b[i]-a[i] for i in range(3)],[c[i]-a[i] for i in range(3)]
        normal_y = u[2]*v[0]-u[0]*v[2]
        self.assertGreater(normal_y,0)
        self.assertGreater(mesh['normals'][1],0.9)
        self.assertEqual(mesh['uvs'][0],[0,0,0,0,0,0])

    def test_bad_index_rejected(self):
        blob = minimal_mesh()[:-2]+struct.pack('<H',9)
        with self.assertRaisesRegex(FormatError,'Index outside'): read_mesh(FixturePackage(blob),1)

    def test_colour_stream(self):
        """A colour per vertex; a stream longer than the vertices (URB_FastFood's FX_Cloth.Flags.Flag_B: each colour
        twice over) read as far as they go; a shorter one, or one whose header and array disagree, refused."""
        three = bytes([0,0,255,255, 0,255,0,255, 255,0,0,255])      # BGRA: red, green, blue
        want = [1,0,0,1, 0,1,0,1, 0,0,1,1]
        self.assertEqual(read_mesh(FixturePackage(minimal_mesh(three)),1)['colors'],want)
        mesh = read_mesh(FixturePackage(minimal_mesh(three*2)),1)
        self.assertEqual(mesh['colors'],want)
        self.assertEqual(mesh['indices'],[0,1,2])
        self.assertEqual(read_mesh(FixturePackage(minimal_mesh()),1)['colors'],[])
        with self.assertRaisesRegex(FormatError,'shorter'): read_mesh(FixturePackage(minimal_mesh(three[:8])),1)
        with self.assertRaisesRegex(FormatError,'Invalid colour'): read_mesh(FixturePackage(minimal_mesh(three,stated=6)),1)

    def test_basis_and_component_composition(self):
        actor = transform([10,20,30],[0,16384,0],[2,2,2])
        component = transform([1,0,0],[0,0,0],[1,1,1])
        matrix = view_matrix(multiply(actor,component))
        for a,b in zip(matrix[12:15],[10,30,22]): self.assertAlmostEqual(a,b)
        for point in ([0,0,0],[1,2,3]):
            source = transform(point,[0,0,0],[1,1,1])
            self.assertEqual(view_matrix(source)[12:15],[point[0],point[2],point[1]])

    def test_bulk_validation(self):
        data=b'example texture payload'*10
        compressed=zlib.compress(data)
        blob=struct.pack('<6I',0x9e2a83c1,131072,len(compressed),len(data),len(compressed),len(data))+compressed
        self.assertEqual(decompress_payload(blob,2),data)
        with self.assertRaises(FormatError): decompress_payload(blob[:-1],2)

    def test_bc1_texture_wrapper(self):
        image=Image.open(io.BytesIO(dds_header(4,4,'DXT1',8)+struct.pack('<HHI',0xf800,0,0)))
        self.assertEqual(image.size,(4,4))
        self.assertEqual(image.convert('RGB').getpixel((0,0)),(255,0,0))


if __name__ == '__main__': unittest.main()
