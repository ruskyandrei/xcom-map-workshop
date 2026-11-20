"""Fixed-size edits of compressed packages in any chunk (baker design, stage 1)."""
import os
from pathlib import Path
import random
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import decomp  # noqa: E402
import lzo1x  # noqa: E402
import package_edit  # noqa: E402
from package_edit import lzo_literals, write_edited  # noqa: E402
import upkinfo  # noqa: E402

sys.path.insert(0, str(HERE.parents[1] / 'lab'))
import labpaths  # noqa: E402
from upk_fixtures import uncompressed  # noqa: E402

# URB_Bar as shipped: XCOM_BAR_UPK, else the LWR install's (tools/viewer/settings.py); without it the tests skip
BAR, NO_BAR = labpaths.test_file('XCOM_BAR_UPK', labpaths.lwr_cooked('URB_Bar.upk'), 'URB_Bar.upk')


def fstr(s):
    return struct.pack('<i', len(s) + 1) + s.encode('latin1') + b'\0'


def summary(chunks):
    head = struct.pack('<IHHI', 0x9E2A83C1, 845, 64, 0) + fstr('None') + struct.pack('<I', 0)
    head += struct.pack('<11I', *([0] * 11)) + bytes(range(16))
    head += struct.pack('<I3I', 1, 1, 2, 3) + struct.pack('<III', 8916, 0, 2)
    head += struct.pack('<I', len(chunks)) + b''.join(struct.pack('<IIII', *c) for c in chunks)
    return head + struct.pack('<II', 0, 0)


def make_package(path, logical, chunk_sizes, block=300):
    """A synthetic compressed package: a summary, then the logical bytes split into LZO chunks."""
    n = len(chunk_sizes)
    header_len = len(summary([(0, 0, 0, 0)] * n))
    uo0 = header_len - 16 * n
    bodies, pos = [], 0
    for size in chunk_sizes:
        data = logical[pos:pos + size]
        blocks = [data[k:k + block] for k in range(0, size, block)]
        enc = [lzo_literals(b) for b in blocks]
        body = struct.pack('<IIII', 0x9E2A83C1, block, sum(map(len, enc)), size)
        body += b''.join(struct.pack('<II', len(e), len(b)) for e, b in zip(enc, blocks)) + b''.join(enc)
        bodies.append(body)
        pos += size
    entries, uo, co = [], uo0, header_len
    for size, body in zip(chunk_sizes, bodies):
        entries.append((uo, size, co, len(body)))
        uo += size
        co += len(body)
    raw = summary(entries) + b''.join(bodies)
    Path(path).write_bytes(raw)
    return uo0, entries


class LiteralEncoder(unittest.TestCase):
    def test_round_trips_short_long_and_full_blocks(self):
        rng = random.Random(7)
        for n in list(range(1, 600)) + [131071, 131072]:
            data = bytes(rng.randrange(256) for _ in range(n))
            self.assertEqual(lzo1x.decompress(lzo_literals(data), n), data, n)

    def test_refuses_empty(self):
        with self.assertRaises(ValueError):
            lzo_literals(b'')


class Overlapping(unittest.TestCase):
    def test_the_neighbours_find_what_a_scan_of_every_edit_finds(self):
        # (review finding 43) edits apart from each other, in any order; a new one meets one of them exactly when the
        # one before it or the one at or after it does
        rng = random.Random(3)
        edits, starts = {}, []
        for _ in range(400):
            off, size = rng.randrange(0, 5000), rng.randrange(1, 12)
            if any(o < off + size and off < o + len(d) for o, d in edits.items()):
                continue
            edits[off] = bytes(size)
            starts = sorted(edits)
        for _ in range(3000):
            off, size = rng.randrange(-20, 5020), rng.randrange(1, 40)
            found = package_edit.overlapping(edits, starts, off, size)
            every = [o for o, d in edits.items() if o < off + size and off < o + len(d)]
            self.assertEqual(found is not None, bool(every), (off, size))
            if found is not None:
                self.assertIn(found, every)
        self.assertIsNone(package_edit.overlapping({}, [], 10, 4))


class SyntheticPackage(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.dir.name, 'in.upk')
        self.dst = os.path.join(self.dir.name, 'out.upk')
        rng = random.Random(1)
        self.logical = bytes(rng.randrange(256) for _ in range(5000))
        self.uo0, self.entries = make_package(self.src, self.logical, [1500, 2000, 1500])
        self.full, _ = decomp.decompress_pkg(self.src)
        self.assertEqual(self.full[self.uo0:], self.logical)

    def tearDown(self):
        self.dir.cleanup()

    def decoded(self):
        full, h = decomp.decompress_pkg(self.dst)
        return full, h['chunks']

    def test_middle_chunk_edit_moves_later_chunks(self):
        off = self.entries[1][0] + 700
        report = write_edited(self.src, self.dst, [(off, b'\x01\x02\x03\x04')])
        full, chunks = self.decoded()
        expect = bytearray(self.full)
        expect[off:off + 4] = b'\x01\x02\x03\x04'
        self.assertEqual(full[self.uo0:], bytes(expect[self.uo0:]))
        self.assertEqual(chunks[0], self.entries[0])
        self.assertEqual([c[:2] for c in chunks], [c[:2] for c in self.entries])
        self.assertEqual(chunks[2][2], chunks[1][2] + chunks[1][3])
        self.assertEqual(report['blocksReencoded'], 1)
        self.assertEqual([c['index'] for c in report['chunksReencoded']], [1])
        self.assertEqual(report['sizeChange'], os.path.getsize(self.dst) - os.path.getsize(self.src))

    def test_edit_across_block_and_chunk_boundaries(self):
        off = self.entries[1][0] - 2
        data = b'\xAA' * 6
        report = write_edited(self.src, self.dst, [(off, data), (self.entries[1][0] + 299, b'\xBB\xBB')])
        full, _ = self.decoded()
        expect = bytearray(self.full)
        expect[off:off + 6] = data
        expect[self.entries[1][0] + 299:self.entries[1][0] + 301] = b'\xBB\xBB'
        self.assertEqual(full[self.uo0:], bytes(expect[self.uo0:]))
        self.assertEqual([c['index'] for c in report['chunksReencoded']], [0, 1])
        self.assertEqual(report['blocksReencoded'], 3)

    def test_forced_noop_reencodes_and_decodes_identically(self):
        off = self.entries[1][0] + 10
        report = write_edited(self.src, self.dst, [(off, self.full[off:off + 8])], force=True)
        full, _ = self.decoded()
        self.assertEqual(full[self.uo0:], self.full[self.uo0:])
        self.assertEqual(report['bytesChanged'], 0)
        self.assertEqual(report['blocksReencoded'], 1)

    def test_unforced_noop_leaves_file_identical(self):
        off = self.entries[2][0] + 10
        report = write_edited(self.src, self.dst, [(off, self.full[off:off + 8])])
        self.assertEqual(report['blocksReencoded'], 0)
        self.assertEqual(Path(self.dst).read_bytes(), Path(self.src).read_bytes())

    def test_refusals(self):
        mid = self.entries[1][0]
        bad = [
            [(mid, b'ab'), (mid + 1, b'cd')],            # overlap
            [(self.uo0 - 4, b'abcd')],                   # header, outside the chunks
            [(self.uo0 + len(self.logical) - 1, b'ab')],  # past the end
            [(mid, b'')],                                # empty
        ]
        for edits in bad:
            with self.assertRaises(ValueError, msg=edits):
                write_edited(self.src, self.dst, edits)
        with self.assertRaises(ValueError):
            write_edited(self.src, self.src, [(mid, b'ab')])

    def test_many_edits_reencode_the_blocks_they_meet_and_no_other(self):
        # (review finding 43) each chunk and block is tested against its neighbouring edits only
        rng = random.Random(7)
        edits, at = [], self.uo0
        while True:
            at += rng.randrange(1, 60)
            size = rng.randrange(1, 9)
            if at + size > self.uo0 + len(self.logical):
                break
            edits.append((at, bytes(rng.randrange(256) for _ in range(size))))
            at += size
        rng.shuffle(edits)
        report = write_edited(self.src, self.dst, edits)
        expect = bytearray(self.full)
        for off, data in edits:
            expect[off:off + len(data)] = data
        full, _ = self.decoded()
        self.assertEqual(full[self.uo0:], bytes(expect[self.uo0:]))
        self.assertEqual([c['index'] for c in report['chunksReencoded']], [0, 1, 2])
        self.assertEqual(report['edits'], len(edits))

    def test_refuses_trailing_data(self):
        with open(self.src, 'ab') as f:
            f.write(b'tail')
        with self.assertRaises(ValueError):
            write_edited(self.src, self.dst, [(self.entries[1][0], b'ab')])

    def test_the_actor_bakers_edits_are_written_by_it_in_blocks_of_any_size(self):
        # (review finding 52) bake_actor.rewrite is an edit list for write_edited; its own encoder refused blocks
        # under 19 bytes, and these are 10
        import bake_actor
        uo0, entries = make_package(self.src, self.logical, [1500, 2000, 1500], block=10)
        off = entries[1][0] + 703
        chunks, grew = bake_actor.rewrite(self.src, self.dst, [(off, b'\x05\x06\x07')])
        full, got = self.decoded()
        expect = bytearray(self.logical)
        expect[off - uo0:off - uo0 + 3] = b'\x05\x06\x07'
        self.assertEqual(full[uo0:], bytes(expect))
        self.assertEqual((chunks, [c[:2] for c in got]), (1, [c[:2] for c in entries]))
        self.assertEqual(grew, os.path.getsize(self.dst) - os.path.getsize(self.src))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class RealMap(unittest.TestCase):
    """A forced no-op on one lightmap record in a middle chunk of URB_Bar (the C0 build, not its game check)."""

    def test_forced_noop_on_a_lightmap_record(self):
        sys.path.insert(0, str(HERE.parent))
        import lighting_records as lighting
        p = lighting.Package(BAR)
        h = upkinfo.summary(BAR.read_bytes())
        index = next(i for i in range(1, len(p.exports) + 1)
                     if p.cls(i) == 'StaticMeshComponent' and p.name(i).startswith('TheWorld.')
                     and lighting.component_record(p, i)['lods'])
        start = p.exports[index - 1]['off']
        chunk = next(k for k, (uo, us, co, cs) in enumerate(h['chunks']) if uo <= start < uo + us)
        self.assertLess(chunk, len(h['chunks']) - 1, 'want a middle chunk so later chunks move')
        with tempfile.TemporaryDirectory() as d:
            dst = os.path.join(d, 'URB_Bar.upk')
            report = write_edited(str(BAR), dst, [(start, p.data[start:start + 16])], force=True)
            self.assertEqual(report['bytesChanged'], 0)
            self.assertGreater(report['sizeChange'], 0)
            q = lighting.Package(dst)
            self.assertEqual(q.data[h['chunks'][0][0]:], p.data[h['chunks'][0][0]:])
            self.assertEqual(lighting.component_record(q, index), lighting.component_record(p, index))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class UncompressedMap(unittest.TestCase):
    """A map stored uncompressed (DLC2_3_Furies.upk as LWR ships it; a build of it crashed: the writers took only
    compressed maps) is put in the compressed cooked maps' layout first; here the bar, uncompressed."""

    @classmethod
    def setUpClass(cls):
        cls.raw = BAR.read_bytes()
        cls.h = upkinfo.summary(cls.raw)
        cls.full, _ = decomp.decompress_pkg(str(BAR))
        cls.flat = uncompressed(BAR)
        cls.lo = cls.h['chunks'][0][0]

    def test_the_layout_is_the_cooked_maps(self):
        self.assertEqual(upkinfo.summary(self.flat)['chunks'], [])
        out = package_edit.compressed_layout(self.flat)
        h = upkinfo.summary(out)
        # every summary field as the cooked map has it, its flags and compression flags too, but the chunk table
        self.assertEqual({k: v for k, v in h.items() if k != 'chunks'},
                         {k: v for k, v in self.h.items() if k != 'chunks'})
        self.assertEqual(h['chunks'][0][:2], self.h['chunks'][0][:2])     # the header's tables whole, in the first
        self.assertEqual(h['chunks'][0][:2], (h['nameoff'], h['headersize'] - h['nameoff']))
        self.assertEqual(h['chunks'][0][2], self.h['chunks'][0][0] + 16 * len(h['chunks']))
        package_edit.check_layout(out, h['chunks'])
        self.assertEqual(decomp._decode(out, h)[self.lo:], self.full[self.lo:])
        # chunks cut only where an export's data starts, none past the limit but for one export
        _, _, exps = upkinfo.tables(self.full, self.h)
        starts = {e['off']: e['size'] for e in exps if e['size']}
        for uo, us, co, cs in h['chunks'][1:]:
            self.assertIn(uo, starts)
            self.assertTrue(us <= package_edit.CHUNK_UNCOMPRESSED or us == starts[uo], (uo, us))
            self.assertEqual(package_edit.read_chunk(out, co)[1], package_edit.BLOCK_SIZE)

    def test_a_compressed_package_is_returned_as_it_is(self):
        self.assertIs(package_edit.compressed_layout(self.raw), self.raw)

    def test_an_edit_of_an_uncompressed_map_is_written_compressed(self):
        start = self.h['chunks'][3][0] + 100
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, 'flat.upk'), os.path.join(d, 'out.upk')
            Path(src).write_bytes(self.flat)
            report = write_edited(src, dst, [(start, b'XCOM')])
            full, h = decomp.decompress_pkg(dst)
            self.assertEqual(h['compflags'], package_edit.COMPRESS_LZO)
            self.assertEqual(full[start:start + 4], b'XCOM')
            self.assertEqual(full[self.lo:start] + full[start + 4:], self.full[self.lo:start] + self.full[start + 4:])
            self.assertEqual(report['bytesChanged'], sum(a != b for a, b in zip(self.full[start:start + 4], b'XCOM')))


def flat_package(sizes, seed=5):
    """A synthetic package stored uncompressed: a v845 summary with no chunks, a name table, an export table and its
    depends, then each export's data (random bytes of `sizes`). Returns (its bytes, the export data's offsets)."""
    rng = random.Random(seed)
    names = b''.join(fstr(n) + struct.pack('<Q', 0) for n in ('None', 'Core', 'Thing'))

    def head(nameoff, expoff, dependsoff, headersize):
        out = struct.pack('<IHHI', 0x9E2A83C1, 845, 64, headersize) + fstr('None') + struct.pack('<I', 0x8)
        out += struct.pack('<11I', 3, nameoff, len(sizes), expoff, 0, 0, dependsoff, 0, 0, 0, 0) + bytes(range(16))
        out += struct.pack('<I3I', 1, len(sizes), 3, 0) + struct.pack('<III', 8916, 0, 0)
        return out + struct.pack('<I', 0) + struct.pack('<II', 0, 0)       # no chunks, the package source, no extra

    size0 = len(head(0, 0, 0, 0))
    nameoff = size0
    expoff = nameoff + len(names)
    dependsoff = expoff + 68 * len(sizes)
    headersize = dependsoff + 4 * len(sizes)
    offsets, at = [], headersize
    for n in sizes:
        offsets.append(at)
        at += n
    table = b''.join(struct.pack('<iiiiiiQIIII', 0, 0, 0, 2, k, 0, 0, n, off, 0, 0) + bytes(16) + struct.pack('<I', 0)
                     for k, (n, off) in enumerate(zip(sizes, offsets)))
    data = b''.join(bytes(rng.randrange(256) for _ in range(n)) if n < 4096 else rng.randbytes(n) for n in sizes)
    raw = head(nameoff, expoff, dependsoff, headersize) + names + table + bytes(4 * len(sizes)) + data
    assert len(raw) == at
    return raw, offsets


class SyntheticUncompressed(unittest.TestCase):
    """The uncompressed-map layout on a synthetic package (review finding 62: UncompressedMap needs URB_Bar): the
    summary keeps every field but its flags and chunks, the header's tables are the first chunk, the export data
    is cut only where an export starts and into chunks of up to CHUNK_UNCOMPRESSED (an export bigger than that gets
    one to itself), and an edit of it is written compressed."""
    SIZES = [300, 700_000, 500_000, 1_300_000, 40]

    @classmethod
    def setUpClass(cls):
        cls.flat, cls.offsets = flat_package(cls.SIZES)
        cls.h = upkinfo.summary(cls.flat)

    def test_the_layout_is_the_cooked_maps(self):
        out = package_edit.compressed_layout(self.flat)
        h = upkinfo.summary(out)
        self.assertEqual({k: v for k, v in h.items() if k not in ('chunks', 'flags', 'compflags')},
                         {k: v for k, v in self.h.items() if k not in ('chunks', 'flags', 'compflags')})
        self.assertEqual(int(h['flags'], 16), int(self.h['flags'], 16) | package_edit.STORE_COMPRESSED)
        self.assertEqual(h['compflags'], package_edit.COMPRESS_LZO)
        start, end = h['nameoff'], h['headersize']
        self.assertEqual([c[:2] for c in h['chunks']],
                         [(start, end - start), (self.offsets[0], 300 + 700_000), (self.offsets[2], 500_000),
                          (self.offsets[3], 1_300_000), (self.offsets[4], 40)])
        package_edit.check_layout(out, h['chunks'])
        self.assertEqual(decomp._decode(out, h)[start:], self.flat[start:])
        for uo, us, co, cs in h['chunks']:
            self.assertEqual(package_edit.read_chunk(out, co)[1], package_edit.BLOCK_SIZE)
        self.assertIs(package_edit.compressed_layout(out), out)          # a compressed package is returned as it is

    def test_an_edit_is_written_compressed(self):
        at = self.offsets[3] + 1000
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, 'flat.upk'), os.path.join(d, 'out.upk')
            Path(src).write_bytes(self.flat)
            write_edited(src, dst, [(at, b'XCOM')])
            full, h = decomp.decompress_pkg(dst)
        self.assertEqual(h['compflags'], package_edit.COMPRESS_LZO)
        expect = bytearray(self.flat)
        expect[at:at + 4] = b'XCOM'
        self.assertEqual(full[h['nameoff']:], bytes(expect[h['nameoff']:]))

    def test_a_package_not_laid_out_as_a_cooked_map_is_refused(self):
        bad = bytearray(self.flat)
        struct.pack_into('<I', bad, 8, self.offsets[0] + 10)          # a header size past the first export's data
        with self.assertRaises(ValueError):
            package_edit.compressed_layout(bytes(bad))


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class PatchWriters(unittest.TestCase):
    """The tile seeder and the link mover write through write_edited (review finding 52): any chunk, an uncompressed
    map too, and only the bytes they mean to change."""

    @classmethod
    def setUpClass(cls):
        import world_links
        cls.full, cls.h = decomp.decompress_pkg(str(BAR))
        cls.blob, cls.names, cls.pkg = world_links.read_input(str(BAR))
        cls.cont = cls.pkg['cont']
        cls.dims, cls.static_at, _ = world_links.static_tiles(cls.blob)
        cls.lo = cls.h['chunks'][0][0]

    def static_flags(self, path):
        import world_links
        full, _ = decomp.decompress_pkg(path)
        blob = full[self.cont['off']:self.cont['off'] + self.cont['size']]
        dims, where, _ = world_links.static_tiles(blob)
        return full, {t: struct.unpack_from('<IB', blob, at) for t, at in where.items()}

    def seeded(self, src):
        import seed_tiles
        box = [(x, y, z) for x in range(10, 21) for y in range(10, 21) for z in range(0, 4)]
        with tempfile.TemporaryDirectory() as d:
            dst = os.path.join(d, 'seeded.upk')
            changed, already, dims = seed_tiles.seed_package(src, dst, box)
            full, flags = self.static_flags(dst)
            note = Path(dst + '.seeded.txt').read_text().splitlines()
        return changed, already, dims, full, flags, note

    def test_seeds_go_on_the_empty_tiles_and_nowhere_else(self):
        changed, already, dims, full, flags = self.seeded(str(BAR))[:5]
        before = self.static_flags(str(BAR))[1]
        self.assertEqual(dims, self.dims)
        self.assertTrue(changed and already)
        for x, y, z, old, new, present in changed:
            self.assertEqual((before[(x, y, z)], flags[(x, y, z)]), ((old, present), (old | 1, 1)))
        seeded = {r[:3] for r in changed}
        self.assertEqual({t: v for t, v in flags.items() if t not in seeded},
                         {t: v for t, v in before.items() if t not in seeded})
        # nothing else in the package changed (the summary's chunk table aside)
        expect = bytearray(self.full)
        for t in seeded:
            at = self.cont['off'] + self.static_at[t]
            expect[at:at + 5] = full[at:at + 5]
        self.assertEqual(full[self.lo:], bytes(expect[self.lo:]))

    def test_an_uncompressed_map_is_seeded_as_the_compressed_one(self):
        with tempfile.TemporaryDirectory() as d:
            flat = os.path.join(d, 'flat.upk')
            Path(flat).write_bytes(uncompressed(BAR))
            got = self.seeded(flat)
        want = self.seeded(str(BAR))
        self.assertEqual(got[:3], want[:3])
        self.assertEqual(got[3][self.lo:], want[3][self.lo:])
        self.assertEqual(got[5], want[5])

    def test_moved_links_are_the_only_change(self):
        import world_links
        link = next(l for l in world_links.all_links(world_links.parse_container(self.blob)) if l['obj'])
        new = bytearray(self.blob)
        struct.pack_into('<f', new, link['off'] + 12, link['cost'] + 1.0)
        with tempfile.TemporaryDirectory() as d:
            dst = os.path.join(d, 'links.upk')
            grew = world_links.write_package(self.pkg, dst, bytes(new))
            back, _, _ = world_links.read_input(dst)
            full, _ = decomp.decompress_pkg(dst)
            self.assertEqual(grew, os.path.getsize(dst) - BAR.stat().st_size)
        self.assertEqual(back, bytes(new))
        o, end = self.cont['off'], self.cont['off'] + self.cont['size']
        self.assertEqual(full[self.lo:o] + full[end:], self.full[self.lo:o] + self.full[end:])


if __name__ == '__main__':
    unittest.main()
