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

    def test_refuses_trailing_data(self):
        with open(self.src, 'ab') as f:
            f.write(b'tail')
        with self.assertRaises(ValueError):
            write_edited(self.src, self.dst, [(self.entries[1][0], b'ab')])


@unittest.skipUnless(BAR and BAR.exists(), NO_BAR)
class RealMap(unittest.TestCase):
    """A forced no-op on one lightmap record in a middle chunk of URB_Bar (the C0 build, not its game check)."""

    def test_forced_noop_on_a_lightmap_record(self):
        sys.path.insert(0, str(HERE.parent))
        import audit_lighting as lighting
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


if __name__ == '__main__':
    unittest.main()
