"""The package readers on damaged input (review finding 50): lzo1x raises ValueError, never IndexError, on a block cut
short or of another length than its table gives, and upkinfo.load reads no command line and leaves sys.path alone;
the one chunk reader (decomp.read_chunk, review finding 52) refuses a damaged chunk header."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import decomp  # noqa: E402
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


class Chunks(unittest.TestCase):
    """decomp.read_chunk, the one checked reader of a chunk header (review finding 52): the map decode, the packages
    compressed whole and package_edit's writers read through it."""
    def chunk(self, tag=0x9E2A83C1, block=131072, packed=len(GOOD), total=8, table=None):
        table = table if table is not None else [(len(GOOD), 8)]
        return (struct.pack('<IIII', tag, block, packed, total) + b''.join(struct.pack('<II', *t) for t in table)
                + GOOD)

    def test_a_good_chunk_and_its_blocks(self):
        b = self.chunk()
        self.assertEqual(decomp.read_chunk(b, 0), (0x9E2A83C1, 131072, 8, [(len(GOOD), 8)], 24))
        self.assertEqual(bytes(decomp.decode_blocks(b, [(len(GOOD), 8)], 24)), b'abcddddd')

    def test_a_damaged_header_is_refused(self):
        damaged = {'another tag': self.chunk(tag=0x12345678), 'a block size of 0': self.chunk(block=0),
                   'packed sizes that do not add up': self.chunk(packed=len(GOOD) + 1),
                   'unpacked sizes that do not add up': self.chunk(table=[(len(GOOD), 7)]),
                   'a header cut short': self.chunk()[:12], 'a block table cut short': self.chunk()[:20],
                   'blocks cut short': self.chunk()[:-1]}
        for what, b in damaged.items():
            with self.assertRaises(ValueError, msg=what):
                decomp.read_chunk(b, 0)

    def test_a_map_decode_refuses_a_chunk_of_another_size_than_its_table_gives(self):
        b = self.chunk()
        self.assertEqual(decomp._decode(b, dict(chunks=[(0, 8, 0, len(b))])), b'abcddddd')
        with self.assertRaisesRegex(ValueError, 'chunk table says 9'):
            decomp._decode(b, dict(chunks=[(0, 9, 0, len(b))]))
        with self.assertRaisesRegex(ValueError, 'bad chunk header'):       # before, read on as a chunk
            decomp._decode(b'\0' * 4 + b, dict(chunks=[(0, 8, 0, len(b))]))


if __name__ == '__main__':
    unittest.main()
