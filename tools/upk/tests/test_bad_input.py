"""The package readers on damaged input (review finding 50): lzo1x raises ValueError, never IndexError, on a block cut
short or of another length than its table gives, and upkinfo.load reads no command line and leaves sys.path alone."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lzo1x  # noqa: E402
import upkinfo  # noqa: E402

END = b'\x11\x00\x00'
GOOD = bytes([21]) + b'abcd' + bytes([96, 0]) + END       # four literals, then a match of four at distance 1


class Lzo(unittest.TestCase):
    def test_a_block_cut_short_or_of_another_length_is_a_value_error(self):
        self.assertEqual(lzo1x.decompress(GOOD, 8), b'abcddddd')
        self.assertEqual(lzo1x.decompress(GOOD), b'abcddddd')
        for cut in range(1, len(GOOD) - 1):
            with self.assertRaises(ValueError, msg=cut):
                lzo1x.decompress(GOOD[:cut], 8)
        with self.assertRaises(ValueError):
            lzo1x.decompress(b'', 8)
        with self.assertRaisesRegex(ValueError, 'not 9'):
            lzo1x.decompress(GOOD, 9)
        with self.assertRaisesRegex(ValueError, 'lookbehind'):
            lzo1x.decompress(bytes([21]) + b'abcd' + bytes([124, 1]) + END, 8)       # a match before the start


class Load(unittest.TestCase):
    def whole(self, packed, unpacked, data, total):
        """A package compressed whole (the startup packages' form) with one block."""
        return struct.pack('<IIII', 0x9E2A83C1, 131072, packed, total) + struct.pack('<II', packed, unpacked) + data

    def test_a_damaged_whole_compressed_package_is_a_value_error_whatever_the_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, data in (('cut.upk', self.whole(50, 8, GOOD, 8)),             # the block runs past the file
                               ('short.upk', self.whole(len(GOOD) - 3, 8, GOOD[:-3], 8)),
                               ('long.upk', self.whole(len(GOOD), 8, GOOD, 9))):     # its blocks give less than it says
                path = Path(tmp) / name
                path.write_bytes(data)
                before = list(sys.path)
                for argv in (['tool.py'], ['tool.py', '--raw']):       # another program's --raw is not upkinfo's
                    with mock.patch.object(sys, 'argv', argv):
                        with self.assertRaises(ValueError, msg=(name, argv)):
                            upkinfo.load(path)
                self.assertEqual(sys.path, before)
            self.assertEqual(upkinfo.load.__defaults__, (False,))      # raw only when the caller says so


if __name__ == '__main__':
    unittest.main()
