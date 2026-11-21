"""The package readers on damaged input (review finding 50): lzo1x raises ValueError, never IndexError, on a block cut
short or of another length than its table gives, and upkinfo.load reads no command line and leaves sys.path alone;
the one chunk reader (decomp.read_chunk, review finding 52) refuses a damaged chunk header; upkinfo's summary, tables
and names, kismet_links' and schema's names refuse a damaged package with a ValueError (KB-9)."""
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
from upk_fixtures import made_up_package  # noqa: E402

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


OBJECTS = (('Package', 'Group', 0, b''), ('Texture2D', 'URB_Bar', 1, b'\0' * 8), ('StaticMesh', 'Rock', 1, b'\0' * 4))


def read(data):
    """Everything upkinfo reads of a package's header: its summary, tables, every export's path and class."""
    h = upkinfo.summary(data)
    names, imps, exps = upkinfo.tables(data, h)
    paths = [upkinfo.objname(k, imps, exps) for k in range(-len(imps), len(exps) + 1)]
    return h, names, paths, [upkinfo.clsname(e['cls'], imps, exps) for e in exps]


def patched(data, at, fmt, *values):
    out = bytearray(data)
    struct.pack_into(fmt, out, at, *values)
    return bytes(out)


class Header(unittest.TestCase):
    """upkinfo on a damaged package (KB-9): the summary, the tables, the paths and classes refuse with a ValueError that
    says what they met, never a struct.error, an IndexError, a loop or a name made up as '?N'. Before, a cut-short
    package was a struct.error, which a caller catching ValueError let through (a damaged map-picture package stopped
    the Project manager's listing)."""

    def setUp(self):
        self.data, self.at = made_up_package(OBJECTS)

    def test_the_made_up_package_reads(self):
        h, names, paths, classes = read(self.data)
        self.assertEqual((h['ver'], h['lic'], h['addpkgs'], h['chunks'], len(h['gens'])), (845, 64, ['Extra'], [], 1))
        self.assertEqual(paths[-3:], ['Group', 'Group.URB_Bar', 'Group.Rock'])
        self.assertEqual(paths[:5], ['Engine.StaticMesh', 'Engine.Texture2D', 'Engine.Package', 'Engine', 'None'])
        self.assertEqual(classes, ['Package', 'Texture2D', 'StaticMesh'])

    def test_a_package_cut_anywhere_in_its_header_or_tables_is_a_value_error(self):
        for cut in range(self.at['depends']):
            with self.assertRaises(ValueError, msg=cut):
                read(self.data[:cut])
        read(self.data[:self.at['depends']])      # what follows the export table is not read: cut there, it reads
        # what each says it met, and where
        with self.assertRaisesRegex(ValueError, 'cut short in the summary: a field at byte %d' % self.at['gens']):
            read(self.data[:self.at['gens'] - 3])                 # inside the package's GUID
        with self.assertRaisesRegex(ValueError, 'lists 1 generations at byte %d, more than the 11 bytes left'
                                    % (self.at['gens'] + 4)):
            read(self.data[:self.at['gens'] + 15])
        with self.assertRaisesRegex(ValueError, 'string of 6 bytes at byte %d runs past' % (self.at['addpkgs'] + 4)):
            read(self.data[:self.at['addpkgs'] + 9])
        with self.assertRaisesRegex(ValueError, 'cut short in name 10 of 10: a field at byte %d'
                                    % (self.at['name_at'][9] + 9)):
            read(self.data[:self.at['name_at'][9] + 12])       # in the last name's flags, after 'Rock'
        with self.assertRaisesRegex(ValueError, 'cut short in export 3 of 3'):
            read(self.data[:self.at['depends'] - 1])

    def test_a_wild_count_is_refused_before_it_is_read(self):
        counts = dict(self.at['counts'], gens=self.at['gens'], chunks=self.at['chunks'], addpkgs=self.at['addpkgs'])
        for what, at in counts.items():
            for wild in (1000, 0xFFFFFFFF):
                with self.assertRaisesRegex(ValueError, 'lists %d .* more than' % wild, msg=(what, wild)):
                    read(patched(self.data, at, '<I', wild))

    def test_a_string_longer_than_the_bytes_left_is_refused(self):
        for at in (self.at['folder'], self.at['name_at'][3], self.at['addpkgs'] + 4):
            for length in (1000, -1000, len(self.data) - at - 3):
                with self.assertRaisesRegex(ValueError, 'runs past the end', msg=(at, length)):
                    read(patched(self.data, at, '<i', length))

    def test_a_name_index_out_of_range_is_refused_not_made_up(self):
        name = self.at['export_at'][1] + 12              # export 2's name
        for index in (99, -1, len(self.data)):
            with self.assertRaisesRegex(ValueError, 'name index %d' % index):
                read(patched(self.data, name, '<i', index))
        with self.assertRaisesRegex(ValueError, 'name index 77'):
            read(patched(self.data, self.at['imports'] + 8, '<i', 77))       # an import's class name

    def test_an_outer_or_class_out_of_range_and_a_looping_outer_chain_are_refused(self):
        outer = [at + 8 for at in self.at['export_at']]
        cls = self.at['export_at'][1]
        bad = {'an outer past the exports': patched(self.data, outer[1], '<i', 99),
               'an outer past the imports': patched(self.data, outer[1], '<i', -99),
               'a class past the imports': patched(self.data, cls, '<i', -99),
               'a class past the exports': patched(self.data, cls, '<i', 4)}
        for what, data in bad.items():
            with self.assertRaisesRegex(ValueError, 'out of range', msg=what):
                read(data)
        looping = patched(patched(self.data, outer[0], '<i', 3), outer[2], '<i', 1)    # Group in Rock, Rock in Group
        with self.assertRaisesRegex(ValueError, 'outer chain loops'):
            read(looping)
        with self.assertRaisesRegex(ValueError, 'outer chain loops'):
            read(patched(self.data, outer[0], '<i', 1))                     # an export its own outer

    def test_a_file_too_short_for_a_package_is_a_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            for size in (0, 3, 7):
                path = Path(tmp) / ('short%d.upk' % size)
                path.write_bytes(self.data[:size])
                with self.assertRaisesRegex(ValueError, 'too few for a package'):
                    upkinfo.load(path)
            path = Path(tmp) / 'cut.upk'
            path.write_bytes(self.data[:self.at['exports'] + 30])
            with self.assertRaisesRegex(ValueError, 'lists 3 exports at byte'):
                upkinfo.tables(*upkinfo.load(path))


class Names(unittest.TestCase):
    """The other readers of a name index refuse one out of range (KB-9; the install's 8,233 packages have none)."""

    def test_the_kismet_reader_refuses_a_name_index_out_of_range(self):
        import kismet_links
        names = ['None', 'VarName', 'Leader']
        blob = struct.pack('<2i', 2, 0) + struct.pack('<2i', 2, 3) + struct.pack('<2i', 3, 0) + struct.pack('<2i', -1, 0)
        p = kismet_links.P(blob, names, [], [])
        self.assertEqual(p.name(0), ('Leader', 8))
        self.assertEqual(p.name(8), ('Leader_2', 16))
        for at in (16, 24):         # before, '?3' and '?-1'
            with self.assertRaisesRegex(ValueError, 'name index'):
                p.name(at)

    def test_the_schema_refuses_a_name_index_out_of_range_and_a_negative_one_that_would_wrap(self):
        import schema

        def struct_with(index):
            body = struct.pack('<iii', 0, index, 0) + bytes(40)      # net index, the closing None, then the fields
            return made_up_package((('ScriptStruct', 'Vector', 0, body),))[0]

        good = struct_with(0)
        names = upkinfo.tables(good, upkinfo.summary(good))[0]
        self.assertEqual(names[0], 'None')
        with tempfile.TemporaryDirectory() as tmp:
            core = Path(tmp) / 'Core.upk'
            core.write_bytes(good)
            self.assertEqual(list(schema.build(tmp, packages=('Core',))['structs']), ['Core.Vector'])
            # 99 past the table (an IndexError before); -len(names) wraps to names[0], 'None', and read on before
            for index in (99, -1, -len(names)):
                core.write_bytes(struct_with(index))
                with self.assertRaisesRegex(ValueError, 'name index %d' % index):
                    schema.build(tmp, packages=('Core',))


if __name__ == '__main__':
    unittest.main()
