"""The convex hull writer (hulls.py; custom geometry plan, M6 item 3): the cover blocks' recipe box as cover_blocks
writes it, field for field, from its own face loops and from its corners alone; a ramp's wedge closed and bounded;
corners that make no solid refused. (research/evidence/hull-audit.py --self-check also checks it against the farm's
ramps in the install.)"""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import cover_blocks  # noqa: E402
import hulls  # noqa: E402

FIELDS = ('VertexData', 'PermutedVertexData', 'FaceTriData', 'EdgeDirections', 'FaceNormalDirections',
          'FacePlaneData', 'ElemBox')


def packed(element):
    """Each field as the bytes it is saved as (single precision)."""
    out = {}
    for k in FIELDS:
        v = element[k]
        if k == 'FaceTriData':
            out[k] = struct.pack('<%di' % len(v), *v)
        elif k == 'ElemBox':
            out[k] = struct.pack('<6f', *v[0], *v[1]) + bytes([v[2]])
        else:
            out[k] = b''.join(struct.pack('<%df' % len(r), *r) for r in v)
    return out


class Hulls(unittest.TestCase):
    def setUp(self):
        self.spec = cover_blocks.recipe(1)['bodySetup']
        self.lo, self.hi = [-48.0] * 3, [48.0] * 3
        self.theirs = cover_blocks.convex_hull(self.lo, self.hi, self.spec)

    def test_the_recipe_box_is_the_cover_blocks_field_for_field(self):
        loops = hulls.face_loops(self.theirs['VertexData'], hulls.tri_rows(self.theirs['FaceTriData']))
        corners = [[(self.lo, self.hi)[c[a]][a] for a in range(3)] for c in self.spec['corners']]
        self.assertEqual(packed(hulls.hull_element(corners, loops)), packed(self.theirs))
        # from its corners alone, in their saved order: the hull's own vertex order and triangles
        self.assertEqual(packed(hulls.hull_element(self.theirs['VertexData'])), packed(self.theirs))

    def test_a_wedge_is_closed_and_bounded(self):
        corners, faces = hulls.wedge((192.0, 96.0), 96.0)
        for e in (hulls.hull_element(corners, faces), hulls.hull_element(corners)):
            self.assertEqual(len(e['FacePlaneData']), 5)
            self.assertEqual(len(e['VertexData']), 6)
            self.assertEqual(e['ElemBox'][0], [0.0, 0.0, 0.0])
            self.assertEqual(e['ElemBox'][1], [192.0, 96.0, 96.0])
            # every corner on or inside every plane (w, x, y, z: x*nx + y*ny + z*nz = w on the plane)
            for w, nx, ny, nz in e['FacePlaneData']:
                for v in e['VertexData']:
                    self.assertLessEqual(v[0] * nx + v[1] * ny + v[2] * nz - w, 1e-3)

    def test_corners_that_make_no_solid_are_refused(self):
        with self.assertRaises(ValueError):
            hulls.hull_element([[0, 0, 0], [96, 0, 0], [96, 96, 0], [0, 96, 0]])


if __name__ == '__main__':
    unittest.main()
