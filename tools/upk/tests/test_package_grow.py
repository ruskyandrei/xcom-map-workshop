"""Growing edits by appending (package_grow.py; UDK-removal U2, baker L4 gate C6), on the bar."""
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / 'viewer'))
sys.path.insert(0, str(HERE.parents[1] / 'bake'))
import decomp  # noqa: E402
import package_edit  # noqa: E402
import package_grow  # noqa: E402
import upkinfo  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402

# URB_Bar as shipped: XCOM_BAR_UPK, else the LWR install's (tools/viewer/settings.py); without it the tests skip
BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')
# DLC2_3_Furies as the install has it (LWR's is stored uncompressed): XCOM_FURIES_UPK, else the LWR install's
FURIES, NO_FURIES = labpaths.test_file('XCOM_FURIES_UPK', labpaths.lwr_cooked('DLC2_3_Furies.upk'), 'DLC2_3_Furies.upk')
# a third map for the read-back's decode (another size, another chunk layout)
POLICE, NO_POLICE = labpaths.test_file('XCOM_POLICE_UPK', labpaths.lwr_cooked('URB_PoliceStation.upk'),
                                       'URB_PoliceStation.upk')
FLOOR = 'TheWorld.PersistentLevel.XComLevelActor_302.StaticMeshComponent_7'


class Edits(unittest.TestCase):
    """(Review finding 43) Fixed-size edits are kept in order and checked against their neighbours: an overlap and an
    empty edit are refused, as before, and thousands of edits take no longer than the writing does."""
    def grower(self):
        g = package_grow.Grower.__new__(package_grow.Grower)
        g.chunks, g.end, g.edits, g.edit_starts = [(100, 100000, 0, 0)], 100100, {}, []
        return g

    def test_an_overlap_or_an_empty_edit_is_refused(self):
        g = self.grower()
        for at in (500, 520, 505, 200, 1000):
            g.edit(at, b'abcde')
        self.assertEqual(g.edit_starts, [200, 500, 505, 520, 1000])
        for at, data in ((498, b'xyz'), (504, b'x'), (509, b'xx'), (196, b'x' * 400), (90, b'x'), (100099, b'xx')):
            with self.assertRaises(ValueError, msg=(at, data)):
                g.edit(at, data)
        with self.assertRaisesRegex(ValueError, 'empty'):
            g.edit(3000, b'')
        g.edit(510, b'0123456789')         # between two, touching both
        self.assertEqual(sorted(g.edits), g.edit_starts)

    def test_many_edits_in_any_order(self):
        import random
        import time
        g = self.grower()
        offsets = [100 + 5 * k for k in range(19000)]
        random.Random(1).shuffle(offsets)
        started = time.perf_counter()
        for at in offsets:
            g.edit(at, b'12345')
        self.assertEqual(g.edit_starts, sorted(offsets))
        # (a check of every earlier edit took 11 to 16 s for 20,000; this takes a fraction of a second)
        self.assertLess(time.perf_counter() - started, 10.0)


class ChunkCuts(unittest.TestCase):
    """Where a growing write cuts its chunks: no game file needed (review finding 58: it sat behind the bar's gate)."""

    def test_chunks_are_cut_only_where_an_item_starts(self):
        cut = package_grow.Grower.chunk_cuts
        self.assertEqual(cut([0, 300, 700], 1000, limit=500), [(0, 300), (300, 700), (700, 1000)])
        self.assertEqual(cut([0, 100, 200, 450], 1000, limit=500), [(0, 450), (450, 1000)])
        # an item bigger than the limit gets a chunk to itself
        self.assertEqual(cut([0, 100, 900], 1000, limit=500), [(0, 100), (100, 900), (900, 1000)])
        self.assertEqual(cut([], 1000, limit=500), [(0, 1000)])


def compressed(head, parts, at=None, bsz=1000):
    """A made-up compressed package for decomp's chunk readers: `head` (its bytes before the first chunk), then each
    of `parts` ((logical offset, bytes)) as a literal-LZO chunk of blocks of `bsz`. Returns (the bytes, a summary
    holding the chunk table alone, which is all the decoders read)."""
    b, chunks = bytearray(head), []
    for uo, part in parts:
        body = package_edit.literal_chunk(part, bsz)
        chunks.append((uo, len(part), len(b), len(body)))
        b += body
    return bytes(b), dict(chunks=chunks)


class WrittenDecode(unittest.TestCase):
    """The growing writer's read-back (decomp.decode_written): a block whose packed bytes are the source's at the
    same logical offset is the source's decoded bytes, every other block is decoded, and the image is the one a whole
    decode gives. No game file needed."""

    def test_only_the_blocks_the_write_made_or_moved_are_decoded(self):
        head = bytes(range(100))
        data = bytes((k * 7) % 251 for k in range(6000))
        raw, src_h = compressed(head, [(100, data[:2000]), (2100, data[2000:4000]), (4100, data[4000:])])
        full = decomp._decode(raw, src_h)
        self.assertEqual(full, head + data)
        changed = bytearray(data[2000:4000])
        changed[1500] ^= 0xFF                       # the chunk's second block changes, its first is kept
        tail = data[:2000]                          # the source's first two blocks again, at another place
        b, h = compressed(b'H' * 100, [(100, data[:2000]), (2100, bytes(changed)), (4100, data[4000:]),
                                       (6100, tail)])
        image, taken, decoded = decomp.decode_written(b, h, raw, src_h, full)
        self.assertEqual(image, decomp._decode(b, h))
        self.assertEqual(image[:100], b'H' * 100)
        # kept: the first and third chunks' blocks and the second's first; decoded: the changed block, and the moved
        # pair (packed bytes of the source's, but at another offset)
        self.assertEqual((taken, decoded), (5, 3))

    def test_a_chunk_whose_size_disagrees_with_the_table_is_refused(self):
        data = bytes(3000)
        raw, src_h = compressed(bytes(100), [(100, data)])
        full = decomp._decode(raw, src_h)
        b, h = compressed(bytes(100), [(100, data)])
        uo, us, co, cs = h['chunks'][0]
        with self.assertRaisesRegex(ValueError, 'chunk table says'):
            decomp.decode_written(b, dict(chunks=[(uo, us - 1, co, cs)]), raw, src_h, full)


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class GrowBar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full, cls.h = decomp.decompress_pkg(str(BAR))
        cls.names, cls.imps, cls.exps = upkinfo.tables(cls.full, cls.h)

    def test_a_growing_write_without_changes_moves_only_the_tables(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            report = package_grow.Grower(str(BAR)).write(str(out))
            full, h = decomp.decompress_pkg(str(out))
            names, imps, exps = upkinfo.tables(full, h)
            end = self.h['chunks'][-1][0] + self.h['chunks'][-1][1]
            # every export's data is where it was, and the old bytes are all still there (from the first chunk: the
            # logical image's first bytes are the physical summary's)
            lo = self.h['chunks'][0][0]
            self.assertEqual(full[lo:end], self.full[lo:end])
            self.assertEqual([(e['off'], e['size'], e['name']) for e in exps],
                             [(e['off'], e['size'], e['name']) for e in self.exps])
            self.assertEqual((names, len(imps)), (self.names, len(self.imps)))
            # the table keeps its size (some entries carry net object counts, so not all are 68 bytes)
            self.assertEqual((h['expoff'], h['dependsoff']), (end, end + self.h['dependsoff'] - self.h['expoff']))
            self.assertEqual(h['gens'][0][:2], (len(exps), len(names)))
            self.assertEqual(len(h['chunks']), len(self.h['chunks']) + 1)
            self.assertEqual(report['added'], 0)

    def test_a_new_name_and_a_relocated_export(self):
        g = package_grow.Grower(str(BAR))
        index = g.name('XComMapWorkshopTestName')
        self.assertEqual(index, len(self.names))
        self.assertEqual(g.name('XComMapWorkshopTestName'), index)
        victim = 5
        data = g.export_data(victim) + b'grown'
        g.relocate(victim, data)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            report = g.write(str(out))
            full, h = decomp.decompress_pkg(str(out))
            names, imps, exps = upkinfo.tables(full, h)
            self.assertEqual(names[-1], 'XComMapWorkshopTestName')
            self.assertEqual(report['newNames'], ['XComMapWorkshopTestName'])
            e = exps[victim - 1]
            self.assertEqual(full[e['off']:e['off'] + e['size']], data)
            self.assertGreaterEqual(e['off'], self.h['chunks'][-1][0] + self.h['chunks'][-1][1])

    def test_new_imports_go_after_the_old_and_existing_ones_are_found(self):
        g = package_grow.Grower(str(BAR))
        engine = g.find_import('Package', 'Engine', 0)
        self.assertIsNotNone(engine)
        self.assertEqual(g.add_import('Core', 'Class', engine, 'TriggerVolume'),
                         g.find_import('Class', 'TriggerVolume', engine))
        new = g.add_import('Core', 'Class', engine, 'XComMapWorkshopTestClass')
        self.assertEqual(new, -(len(self.imps) + 1))
        self.assertEqual(g.add_import('Core', 'Class', engine, 'XComMapWorkshopTestClass'), new)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            report = g.write(str(out))
            full, h = decomp.decompress_pkg(str(out))
            names, imps, exps = upkinfo.tables(full, h)
            self.assertEqual(len(imps), len(self.imps) + 1)
            self.assertEqual(imps[:-1], self.imps)
            self.assertEqual(imps[-1], dict(cpkg='Core', cls='Class', outer=engine, name='XComMapWorkshopTestClass'))
            self.assertEqual((report['addedImports'], report['newNames']), (1, ['XComMapWorkshopTestClass']))
            self.assertGreaterEqual(h['impoff'], self.h['chunks'][-1][0] + self.h['chunks'][-1][1])

    def test_a_new_export_with_no_template(self):
        # an entry made from its class, outer, name, archetype and flags alone (new_export), with the package's next net
        # index; nothing of another export's entry is copied
        g = package_grow.Grower(str(BAR))
        level = next(k + 1 for k in range(len(self.exps)) if upkinfo.objname(k + 1, self.imps, self.exps)
                     == 'TheWorld.PersistentLevel')
        engine = g.find_import('Package', 'Engine', 0)
        cls = g.add_import('Core', 'Class', engine, 'XComMapWorkshopTestClass')
        net = g.next_net_index(level)
        self.assertEqual((net, g.net_objects), (self.h['gens'][0][2], self.h['gens'][0][2] + 1))
        data = struct.pack('<ii', 0, net) + struct.pack('<ii', g.name('None'), 0)
        new = g.new_export(cls, level, 'XComMapWorkshopTestObject', data, flags=0x0007000100000000)
        self.assertEqual(new, len(self.exps) + 1)
        self.assertEqual(g.entries[new - 1].name_number, 1)
        self.assertEqual(g.new_export(cls, new, 'XComMapWorkshopTestObject', data), new + 1)
        self.assertEqual(g.entries[new].name_number, 2)
        # refused: no class, a class or archetype outside the package, an import as outer, a bad name or flags
        for bad in (dict(cls=0), dict(cls=-len(g.imports) - 1), dict(cls=len(g.entries) + 1), dict(archetype=10 ** 7),
                    dict(outer=engine), dict(name='None'), dict(name=''), dict(flags=-1), dict(flags=1 << 64),
                    dict(number=-1)):
            args = {**dict(cls=cls, outer=level, name='X', data=data), **bad}
            with self.assertRaises(ValueError, msg=str(bad)):
                g.new_export(args.pop('cls'), args.pop('outer'), args.pop('name'), args.pop('data'), **args)
        self.assertEqual(len(g.entries), new + 1)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            report = g.write(str(out))
            full, h = decomp.decompress_pkg(str(out))
            names, imps, exps = upkinfo.tables(full, h)
            self.assertEqual(report['added'], 2)
            self.assertEqual(h['gens'][0][2], self.h['gens'][0][2] + 1)
            e = exps[new - 1]
            self.assertEqual((e['cls'], e['sup'], e['outer'], e['arch'], e['flags']), (cls, 0, level, 0, 0x0007000100000000))
            self.assertEqual(upkinfo.objname(new, imps, exps), 'TheWorld.PersistentLevel.XComMapWorkshopTestObject_0')
            self.assertEqual(upkinfo.objname(new + 1, imps, exps),
                             'TheWorld.PersistentLevel.XComMapWorkshopTestObject_0.XComMapWorkshopTestObject_1')
            self.assertEqual(full[e['off']:e['off'] + e['size']], data)
            # the entry is a plain one: 68 bytes, no net object counts, zero GUID and package flags
            raw = bytes(g.entries[new - 1].data)
            self.assertEqual((len(raw), raw[40:68]), (68, bytes(28)))

    def test_an_adopted_entry_keeps_everything_but_its_size_and_place(self):
        # an entry made elsewhere (transplant.py: another package's, renumbered): here a forced-export package's own
        # entry, with its net object count and GUID, under a new name
        g = package_grow.Grower(str(BAR))
        k = next(k for k, e in enumerate(g.entries) if e.outer == 0 and e.get('<I', 40) & package_grow.FORCED_EXPORT
                 and e.get('<I', 44) == 1)
        entry = package_grow.Entry(g.entries[k].data)
        entry.put('<i', 12, g.name('XComMapWorkshopTestPackage'))
        data = struct.pack('<i', -1) + struct.pack('<ii', g.name('None'), 0)
        new = g.adopt_export(entry.data, data)
        self.assertEqual(new, len(self.exps) + 1)
        mine, theirs = bytes(g.entries[new - 1].data), bytes(g.entries[k].data)
        self.assertEqual((mine[:12], mine[16:32], mine[40:]), (theirs[:12], theirs[16:32], theirs[40:]))
        self.assertEqual((g.entries[new - 1].size, g.entries[new - 1].offset), (12, g.end))
        # refused: a short or long entry, a name or an import outside the tables, an import as outer
        for bad in (entry.data[:60], bytes(entry.data) + bytes(4)):
            with self.assertRaises(ValueError):
                g.adopt_export(bad, data)
        for at, value in ((12, len(g.names)), (0, -len(g.imports) - 1), (8, -1)):
            wrong = package_grow.Entry(entry.data)
            wrong.put('<i', at, value)
            with self.assertRaises(ValueError, msg=str(at)):
                g.adopt_export(wrong.data, data)
        self.assertEqual(len(g.entries), new)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            report = g.write(str(out))
            full, h = decomp.decompress_pkg(str(out))
            names, imps, exps = upkinfo.tables(full, h)
            self.assertEqual(report['added'], 1)
            self.assertEqual(upkinfo.objname(new, imps, exps), 'XComMapWorkshopTestPackage')
            self.assertEqual(upkinfo.clsname(exps[new - 1]['cls'], imps, exps), 'Package')
            self.assertEqual(h['gens'][0][2], self.h['gens'][0][2])        # no net object of the map's own

    def test_cloned_lightmap_textures_read_back_with_their_payloads(self):
        import lighting_records as lighting
        import grow_fixture
        import lightmap_fields
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'URB_Bar.upk'
            info = grow_fixture.grow(BAR, out, FLOOR)
            lighting.link_caches(d, BAR.parent)      # the grown map reads the map's own texture cache, where it is
            q = lighting.Package(out)
            p = lighting.Package(BAR)
            lm = lightmap_fields.component_fields(q, q.by_name[FLOOR])['lods'][0]['lightmap']
            for slot in (0, 1):
                original, clone, name = info['clones'][slot]
                self.assertEqual(lm['slots'][slot]['index'], clone)
                self.assertEqual(q.name(clone), name)
                self.assertEqual(q.cls(clone), q.cls(original))
                a = lightmap_fields.texture_fields(q, clone)
                b = lightmap_fields.texture_fields(p, original)
                for ma, mb in zip(a['mips'], b['mips']):
                    self.assertEqual((ma['flags'], ma['width'], ma['bytes']), (mb['flags'], mb['width'], mb['bytes']))
                    if ma['inline']:
                        # the copy's own payload, at its new absolute offset
                        self.assertEqual(q.data[ma['payloadOffset']:ma['payloadOffset'] + ma['bytes']],
                                         p.data[mb['payloadOffset']:mb['payloadOffset'] + mb['bytes']])
                        self.assertEqual(struct.unpack_from('<i', q.data, ma['metaOffset'] + 12)[0],
                                         ma['payloadOffset'])
                    else:
                        self.assertEqual(ma['offset'], mb['offset'])


    def test_an_uncompressed_map_is_grown_compressed(self):
        # a map stored uncompressed (DLC2_3_Furies.upk as LWR ships it) is read in the compressed layout
        # (package_edit.compressed_layout) and written compressed, with a fixed-size edit, a new name and a moved export
        sys.path.insert(0, str(HERE))
        from upk_fixtures import uncompressed
        lo = self.h['chunks'][0][0]
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / 'flat.upk', Path(d) / 'URB_Bar.upk'
            src.write_bytes(uncompressed(BAR))
            g = package_grow.Grower(str(src))
            self.assertEqual((g.end, g.full[lo:]), (len(self.full), self.full[lo:]))
            at = self.h['chunks'][2][0] + 64
            g.edit(at, b'XCOM')
            g.name('XComMapWorkshopTestName')
            victim = 5
            data = g.export_data(victim) + b'grown'
            g.relocate(victim, data)
            report = g.write(str(out))
            full, h = decomp.decompress_pkg(str(out))
            names, imps, exps = upkinfo.tables(full, h)
            self.assertEqual((h['flags'], h['compflags']), (self.h['flags'], self.h['compflags']))
            self.assertEqual(full[at:at + 4], b'XCOM')
            self.assertEqual(full[lo:at], self.full[lo:at])
            self.assertEqual(names[-1], 'XComMapWorkshopTestName')
            self.assertEqual(full[exps[victim - 1]['off']:exps[victim - 1]['off'] + len(data)], data)
            self.assertEqual(report['sizeChange'], out.stat().st_size - src.stat().st_size)


def first_literal(block):
    """Where the first literal byte of an LZO1X block lies: a block starts with a literal run, so a byte changed there
    changes what it decodes to and leaves it decodable."""
    t = block[0]
    if t > 17:
        return 1
    if t >= 16:
        raise AssertionError('the block does not start with a literal run')
    k = 1
    if t == 0:
        while block[k] == 0:
            k += 1
        k += 1
    return k


def planted(chunk):
    """A stand-in for decomp.decompress_written that first changes, in the file on disk, the first literal byte of the
    first block of the written file's chunk `chunk` (an index of its chunk table), then reads it as the writer does."""
    real = decomp.decompress_written

    def read(path, *args):
        b = bytearray(Path(path).read_bytes())
        uo, us, co, cs = upkinfo.summary(bytes(b))['chunks'][chunk]
        _, _, _, blocks, at = decomp.read_chunk(b, co)
        b[at + first_literal(b[at:at + blocks[0][0]])] ^= 0xFF
        Path(path).write_bytes(b)
        return real(path, *args)
    return read


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class ReadBack(unittest.TestCase):
    """The growing writer's read-back (Grower.write's check, follow-ups item 1.1): the file on disk decoded with the
    blocks it keeps from the source taken from the source's image is the image a whole decode gives, a fault in a
    chunk the write made or in one it kept fails the check, and the written map is not decoded whole again."""

    def setUp(self):
        decomp._MEMO.clear()
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(decomp._MEMO.clear)
        for name in (decomp.WORK_ENV, decomp.KEEP_ENV):
            os.environ.pop(name, None)

    @staticmethod
    def edited(src):
        """A Grower of `src` with a fixed-size edit in its third chunk, a new name and a relocated export."""
        g = package_grow.Grower(str(src))
        g.edit(g.chunks[2][0] + 64, b'XCOM')
        g.name('XComMapWorkshopTestName')
        g.relocate(5, g.export_data(5) + b'grown')
        return g

    def test_the_read_back_is_the_whole_decode_on_three_maps(self):
        # the bar and the police station as shipped, Furies stored uncompressed (read in the compressed layout)
        for path, why in ((BAR, NO_BAR), (POLICE, NO_POLICE), (FURIES, NO_FURIES)):
            with self.subTest(map=path.name if path else why):
                if not (path and path.exists()):
                    self.skipTest(why)
                g = self.edited(path)
                with tempfile.TemporaryDirectory() as d:
                    out = Path(d) / path.name
                    g.write(str(out))
                    b = out.read_bytes()
                    h = upkinfo.summary(b)
                    image, taken, decoded = decomp.decode_written(b, h, g.raw, g.h, g.full)
                    self.assertEqual(image, decomp._decode(b, h))
                    self.assertEqual(decomp.decompress_pkg(str(out))[0], image)     # what the writer kept
                    # the edited block and the new chunks' are decoded; every other block is the source's
                    blocks = sum(len(decomp.read_chunk(b, co)[3]) for _, _, co, _ in h['chunks'])
                    self.assertEqual(taken + decoded, blocks)
                    self.assertLess(decoded, blocks // 10)

    def test_a_fault_in_a_chunk_the_write_made_fails_the_check(self):
        g = self.edited(BAR)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(decomp, 'decompress_written', planted(-1)):
            with self.assertRaisesRegex(ValueError, 'does not decode to the intended bytes'):
                g.write(str(Path(d) / 'URB_Bar.upk'))

    def test_a_fault_in_a_chunk_kept_from_the_source_fails_the_check(self):
        # a byte changed on disk in a block the write kept (its packed bytes no longer the source's: decoded, and
        # wrong), and a writer that left an edited block as the source had it (its packed bytes the source's: taken
        # from the source's image, which is not what was meant)
        g = self.edited(BAR)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(decomp, 'decompress_written', planted(4)):
            with self.assertRaisesRegex(ValueError, 'does not decode to the intended bytes'):
                g.write(str(Path(d) / 'URB_Bar.upk'))
        g = self.edited(BAR)
        real = package_edit.write_edited
        with tempfile.TemporaryDirectory() as d, mock.patch.object(
                package_edit, 'write_edited', lambda src, dst, edits, **k: real(src, dst, [], **k)):
            with self.assertRaisesRegex(ValueError, 'does not decode to the intended bytes'):
                g.write(str(Path(d) / 'URB_Bar.upk'))

    def test_the_written_map_is_not_decoded_whole(self):
        # the source is decoded once; the written map is read back from the source's blocks, and kept, so the next
        # reader takes it from the memo, and another process from the work folder's kept image
        with tempfile.TemporaryDirectory() as d:
            os.environ[decomp.WORK_ENV] = str(Path(d) / 'unpacked')
            before = dict(decomp.STATS)
            g = self.edited(BAR)
            out = Path(d) / 'URB_Bar.upk'
            g.write(str(out))
            image, _ = decomp.decompress_pkg(str(out))
            got = {k: decomp.STATS[k] - before[k] for k in ('decoded', 'written', 'memo', 'disk')}
            self.assertEqual(got, dict(decoded=1, written=1, memo=2, disk=0))
            decomp._MEMO.clear()
            self.assertEqual(decomp.decompress_pkg(str(out))[0], image)
            self.assertEqual(decomp.STATS['disk'] - before['disk'], 1)


@unittest.skipUnless(FURIES and FURIES.exists(), NO_FURIES)
class GrowFuries(unittest.TestCase):
    def test_the_map_grows(self):
        # DLC2_3_Furies.upk, which LWR stores uncompressed: a growing write without changes reads back whole (a build
        # of the map crashed on it in 0.6.0)
        flat, h = decomp.decompress_pkg(str(FURIES))
        names, imps, exps = upkinfo.tables(flat, h)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'DLC2_3_Furies.upk'
            g = package_grow.Grower(str(FURIES))
            g.name('XComMapWorkshopTestName')
            g.write(str(out))
            full, h2 = decomp.decompress_pkg(str(out))
            self.assertTrue(h2['chunks'])
            lo = h2['chunks'][0][0]
            end = max(e['off'] + e['size'] for e in exps)
            self.assertEqual(full[lo:end], flat[lo:end])
            names2, imps2, exps2 = upkinfo.tables(full, h2)
            self.assertEqual((names2[:-1], imps2), (names, imps))
            self.assertEqual([(e['off'], e['size']) for e in exps2], [(e['off'], e['size']) for e in exps])


if __name__ == '__main__':
    unittest.main()
