import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from package import Reader,FormatError
from skeletal import read_skeletal,bone_matrix,inverse_rigid
from mesh import write_glb
from export_math import multiply


def fixture():
    pack=lambda fmt,*v:struct.pack('<'+fmt,*v)
    array=lambda stride,count,raw:pack('2i',stride,count)+raw
    positions=[(0,0,0),(0,1,0),(1,0,0)]
    vertices=b''.join(bytes([255,128,128,255,128,128,255,255,0,0,0,0,255,0,0,0])+
                      pack('3f',*pos)+pack('2e',0,0) for pos in positions)
    return (pack('7f',0,0,0,1,1,1,2)+pack('2i',1,0)+bytes(24)+pack('i',1)+
            pack('2iI',0,0,0)+pack('4f3f2iI',0,0,0,1,3,4,5,0,0,0)+pack('2i',1,1)+
            pack('i',1)+pack('hhiIB',0,0,0,1,0)+pack('IB',0,2)+array(2,3,pack('3H',0,1,2))+
            pack('ih',1,0)+pack('i',1)+pack('4i',0,0,0,1)+pack('h3i',0,3,0,1)+
            pack('2I',0,3)+pack('iB',1,0)+bytes(16)+pack('4I',1,1,0,1)+
            pack('6f',1,1,1,0,0,0)+array(32,3,vertices))


class P:
    def __init__(self,data):self.data=data
    def native(self,index):return Reader(self.data)
    def name(self,index):return 'synthetic'
    def fname(self,r):r.take(8);return 'root'


class SkeletalTests(unittest.TestCase):
    def test_float_stride_wins_over_packing_hint(self):
        mesh=read_skeletal(P(fixture()),1)
        self.assertTrue(mesh['packedPositionHint'])
        self.assertEqual(mesh['positionStorage'],'float32')
        self.assertEqual(mesh['positions'],[0,0,0,0,0,1,1,0,0])
        self.assertEqual(mesh['joints'],[0]*12)
        self.assertEqual(mesh['weights'],[1,0,0,0]*3)

    def test_bad_skin_weights_and_truncation_rejected(self):
        raw=bytearray(fixture());raw[len(raw)-96+12]=200
        with self.assertRaisesRegex(FormatError,'weights'):read_skeletal(P(raw),1)
        with self.assertRaises(FormatError):read_skeletal(P(fixture()[:-1]),1)

    def test_reference_inverse_bind_is_identity(self):
        bone=dict(position=[3,4,5],quaternion=[0.2,0.3,0.4,0.5])
        matrix=bone_matrix(bone);identity=multiply(matrix,inverse_rigid(matrix))
        for i in range(4):
            for j in range(4):self.assertAlmostEqual(identity[i][j],float(i==j))

    def test_glb_contains_real_skin(self):
        mesh=read_skeletal(P(fixture()),1)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'mesh.glb';write_glb(mesh,path);raw=path.read_bytes()
        size=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+size])
        self.assertEqual(doc['skins'][0]['joints'],[2])
        attrs=doc['meshes'][0]['primitives'][0]['attributes']
        self.assertIn('JOINTS_0',attrs);self.assertIn('WEIGHTS_0',attrs)
        accessor=doc['accessors'][doc['skins'][0]['inverseBindMatrices']]
        self.assertEqual(accessor['type'],'MAT4')
        self.assertNotIn('target',doc['bufferViews'][accessor['bufferView']])


if __name__=='__main__':unittest.main()
