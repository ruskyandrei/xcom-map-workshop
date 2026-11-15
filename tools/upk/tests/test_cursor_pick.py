"""The mouse cursor's pick flag on placed pieces (cursor_pick.py): the tag walk on synthetic properties, and Temple
Ship's arches made clickable when the install's TempleShip.upk is there."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import cursor_pick  # noqa: E402
import decomp  # noqa: E402
import upkinfo  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

TEMPLE, NO_TEMPLE = labpaths.install_map('TempleShip')

NAMES = ['None', 'BoolProperty', 'StructProperty', 'ByteProperty', 'IntProperty', 'Vector', 'EFoo',
         'bIgnoreFor3DCursorCollision', 'Location', 'Kind', 'Count']


def name(s):
    return struct.pack('<ii', NAMES.index(s), 0)


def tag(pname, ptype, value, extra=''):
    size = 0 if ptype == 'BoolProperty' else len(value)
    return name(pname) + name(ptype) + struct.pack('<ii', size, 0) + (name(extra) if extra else b'') + value


class WalkTags(unittest.TestCase):
    def test_each_kind_gives_its_value_offset(self):
        blob = (tag('Location', 'StructProperty', struct.pack('<3f', 1, 2, 3), 'Vector')
                + tag('Kind', 'ByteProperty', b'\x02', 'EFoo')
                + tag('bIgnoreFor3DCursorCollision', 'BoolProperty', b'\x01')
                + tag('Count', 'IntProperty', struct.pack('<i', 7))
                + name('None'))
        got = list(cursor_pick.walk_tags(blob, 0, len(blob), NAMES))
        self.assertEqual([g[0] for g in got], ['Location', 'Kind', 'bIgnoreFor3DCursorCollision', 'Count'])
        flag = got[2]
        self.assertEqual((flag[1], blob[flag[3]]), ('BoolProperty', 1))
        self.assertEqual(struct.unpack_from('<3f', blob, got[0][3]), (1, 2, 3))
        self.assertEqual(blob[got[1][3]], 2)
        self.assertEqual(struct.unpack_from('<i', blob, got[3][3])[0], 7)

    def test_missing_none_is_refused(self):
        blob = tag('Count', 'IntProperty', struct.pack('<i', 7))
        with self.assertRaises(ValueError):
            list(cursor_pick.walk_tags(blob, 0, len(blob), NAMES))


@unittest.skipUnless(TEMPLE and TEMPLE.exists(), NO_TEMPLE)
class TempleShipArches(unittest.TestCase):
    def test_arches_made_clickable_and_nothing_else_changed(self):
        b, h = upkinfo.load(str(TEMPLE))
        before = cursor_pick.find_pieces(b, h)
        self.assertEqual(len(before), 273)  # every placed KnuckleWorm_A piece of the shipped map
        self.assertTrue(all(p['flag'] == 1 for p in before))
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / 'TempleShip.upk')
            report, _ = cursor_pick.write_flag(str(TEMPLE), out)
            self.assertEqual(report['pieces'], 273)
            b2, h2 = upkinfo.load(out)
            after = cursor_pick.find_pieces(b2, h2)
            self.assertTrue(all(p['flag'] == 0 for p in after))
            old, _ = decomp.decompress_pkg(str(TEMPLE))
            new, _ = decomp.decompress_pkg(out)
        lo = h['chunks'][0][0]
        changed = {i for i in range(lo, len(old)) if old[i] != new[i]}
        self.assertEqual(changed, {p['offset'] for p in before})


if __name__ == '__main__':
    unittest.main()
