"""Fixed-size edits of a compressed v845 package at uncompressed (logical) offsets, in any chunk.

Generalises seed_tiles.py's method: only the 128 KB blocks an edit touches are re-encoded (as literal LZO1X runs),
so every logical offset in the package stays the same. A re-encoded block is larger than the original, so its chunk
grows; later chunks move in the file and the summary's chunk table gets their new physical offsets and sizes.
Nothing else in the summary holds a physical offset. The result is decoded again and compared with the intended
bytes before the function returns.

Refuses: overlapping or empty edits, edits outside the compressed chunks (the uncompressed header is not edited),
packages whose chunks are not contiguous or do not end the file, and writing over the input. The game reads a map
whose middle chunks were re-encoded and whose later chunks moved (EXP-17's C0); every Build writes its fixed-size
edits this way, and the tile seeds, link moves and actor bakes of the patch path (seed_tiles.py, world_links.py,
bake_actor.py) are edit lists given to it.

A package stored uncompressed (DLC2_3_Furies.upk as Long War Rebalance ships it) is first put in the layout of the
compressed cooked maps (compressed_layout: the same logical bytes in literal-LZO chunks), so what is written from it
is compressed like every other map.

  python package_edit.py <in.upk> <out.upk> --noop <logical offset> <length>
"""
import argparse
import bisect
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decomp  # noqa: E402
import lzo1x  # noqa: E402
import upkinfo  # noqa: E402

CHUNK_TAG = decomp.CHUNK_TAG
STORE_COMPRESSED = 0x02000000   # PKG_StoreCompressed, in the summary's package flags
COMPRESS_LZO = 2                # the summary's compression flags, as the cooked maps have them
BLOCK_SIZE = 1 << 17            # the cooked maps' block size (128 KB)
CHUNK_UNCOMPRESSED = 1 << 20    # a chunk holds up to this much, unless one item is bigger (the maps' run 0.2-4 MB)


def lzo_literals(data):
    """A valid LZO1X stream holding data as one literal run, then the end marker."""
    n = len(data)
    if n == 0:
        raise ValueError('empty block')
    if n <= 238:
        return bytes([17 + n]) + data + b'\x11\x00\x00'
    rest = n - 3 - 15
    k = (rest - 1) // 255
    r = rest - 255 * k
    return bytes([0]) + bytes(k) + bytes([r]) + data + b'\x11\x00\x00'


def chunk_table_offset(raw, chunks):
    """Physical offset of the summary's compressed-chunk count, checked against the parsed entries."""
    r = upkinfo.R(raw)
    r.u32(); r.u16(); r.u16(); r.u32(); r.fstr(); r.u32()
    for _ in range(11):
        r.u32()  # name, export, import counts/offsets; depends, guids, thumbnails
    r.o += 16
    gc = r.u32()
    r.o += 12 * gc
    r.u32(); r.u32(); r.u32()  # engine, cooker, compression flags
    t = r.o
    n = struct.unpack_from('<I', raw, t)[0]
    if n != len(chunks) or any(struct.unpack_from('<IIII', raw, t + 4 + 16 * i) != tuple(c)
                               for i, c in enumerate(chunks)):
        raise ValueError('chunk table not where expected')
    return t


def chunk_cuts(starts, total, limit=CHUNK_UNCOMPRESSED):
    """Where to cut `total` bytes of items (beginning at `starts`) into chunks of up to `limit`, cutting only at an
    item's start; an item bigger than `limit` gets a chunk to itself. Returns [(start, end)]. The game's loader can't
    serve a read that crosses a chunk boundary, and hangs (EXP-20 run 4, findings register T-14)."""
    bounds = sorted(set([0] + [s for s in starts if 0 < s < total])) + [total]
    cuts = [0]
    for k in range(1, len(bounds) - 1):
        if bounds[k + 1] - cuts[-1] > limit:
            cuts.append(bounds[k])
    cuts.append(total)
    return [(a, b) for a, b in zip(cuts, cuts[1:]) if b > a]


def literal_chunk(part, bsz=BLOCK_SIZE):
    """A compressed chunk's bytes (header, block table, blocks) holding `part` as literal-LZO blocks of `bsz`, each
    decoded again and compared."""
    blocks = [part[k:k + bsz] for k in range(0, len(part), bsz)]
    enc = [lzo_literals(b) for b in blocks]
    for e, b in zip(enc, blocks):
        if lzo1x.decompress(e, len(b)) != b:
            raise ValueError('literal LZO round trip failed')
    body = struct.pack('<IIII', CHUNK_TAG, bsz, sum(map(len, enc)), len(part))
    return body + b''.join(struct.pack('<II', len(e), len(b)) for e, b in zip(enc, blocks)) + b''.join(enc)


def compressed_layout(raw):
    """An uncompressed package (`raw`) in the layout of the compressed cooked maps, as literal-LZO blocks: the same
    logical bytes, every offset in the summary and the tables kept. As the cooked maps have it, the summary stays
    uncompressed with a chunk table added (so its physical size grows by 16 bytes a chunk, and logical offsets don't
    change), the first chunk holds the header's tables whole, from the end of the summary to the header size, and the
    export data follows in chunks of up to CHUNK_UNCOMPRESSED cut only where an export's data starts. The package
    flags get PKG_StoreCompressed and the compression flags LZO. A compressed package is returned as it is."""
    h = upkinfo.summary(raw)
    if h['chunks']:
        return raw
    table = chunk_table_offset(raw, [])
    r = upkinfo.R(raw)
    r.u32(); r.u16(); r.u16(); r.u32(); r.fstr()
    flags_at = r.o
    flags = struct.unpack_from('<I', raw, flags_at)[0]
    if hex(flags) != h['flags']:
        raise ValueError('package flags not where expected')
    start = min(v for v in (h['nameoff'], h['impoff'], h['expoff'], h['dependsoff']) if v)
    header_end = h['headersize']
    _, _, exps = upkinfo.tables(raw, h)
    data = sorted(e['off'] for e in exps if e['size'])
    if not table + 4 <= start < header_end <= len(raw) or (data and data[0] < header_end):
        raise ValueError('the summary, the tables and the export data are not laid out as in a cooked map')
    cuts = [(start, header_end)] + [(header_end + a, header_end + b) for a, b in
                                    chunk_cuts([o - header_end for o in data], len(raw) - header_end)]
    bodies = [literal_chunk(raw[a:b]) for a, b in cuts]
    head = bytearray(raw[:table])
    struct.pack_into('<I', head, flags_at, flags | STORE_COMPRESSED)
    struct.pack_into('<I', head, table - 4, COMPRESS_LZO)
    after = raw[table + 4:start]
    co = len(head) + 4 + 16 * len(cuts) + len(after)
    entries = struct.pack('<I', len(cuts))
    for (a, b), body in zip(cuts, bodies):
        entries += struct.pack('<IIII', a, b - a, co, len(body))
        co += len(body)
    out = bytes(head) + entries + after + b''.join(bodies)
    h2 = upkinfo.summary(out)
    if decomp._decode(out, h2)[start:] != raw[start:] or {k: v for k, v in h2.items() if k not in (
            'chunks', 'flags', 'compflags')} != {k: v for k, v in h.items() if k not in ('chunks', 'flags', 'compflags')}:
        raise ValueError('the compressed layout does not decode to the package')
    return out


def package_bytes(src):
    """The bytes of the package at `src`, compressed: one stored uncompressed in the compressed layout
    (compressed_layout)."""
    with open(src, 'rb') as f:
        return compressed_layout(f.read())


def check_layout(raw, chunks):
    if not chunks:
        raise ValueError('package is not compressed; put it in the compressed layout first (compressed_layout)')
    for i in range(len(chunks) - 1):
        uo, us, co, cs = chunks[i]
        if chunks[i + 1][0] != uo + us or chunks[i + 1][2] != co + cs:
            raise ValueError(f'chunks {i} and {i + 1} are not contiguous')
    uo, us, co, cs = chunks[-1]
    if co + cs != len(raw):
        raise ValueError('data follows the last chunk; this tool cannot move it')


read_chunk = decomp.read_chunk     # the one checked reader of a chunk header (review finding 52)


def overlapping(edits, starts, offset, size):
    """The offset of the edit of `edits` ({offset: bytes}, none empty, none overlapping another; `starts` their offsets
    in order) that meets [offset, offset + size), or None. Only the edit before and the one at or after can: one further
    on meets it only where the one at or after does (review finding 43: a scan of every edit went quadratic)."""
    i = bisect.bisect_left(starts, offset)
    for o in starts[max(0, i - 1):i + 1]:
        if o < offset + size and offset < o + len(edits[o]):
            return o
    return None


def normalise_edits(edits, lo, hi):
    out = sorted((int(off), bytes(data)) for off, data in edits)
    end = None
    for off, data in out:
        if not data:
            raise ValueError(f'empty edit at {off}')
        if off < lo or off + len(data) > hi:
            raise ValueError(f'edit at {off} (+{len(data)}) is outside the compressed chunks [{lo}, {hi})')
        if end is not None and off < end:
            raise ValueError(f'edit at {off} overlaps the previous edit')
        end = off + len(data)
    return out


def write_edited(src, dst, edits, force=False, verify=True, raw=None):
    """Write dst: src with each (logical offset, bytes) in edits written over the same number of bytes.

    With force, every block an edit overlaps is re-encoded even if its bytes did not change (a no-op edit then still
    exercises the re-encode and the chunk moves). Returns a report dict: chunks and blocks re-encoded, bytes changed
    and the file-size change. `verify` False leaves out the check that dst decodes to the intended bytes: for a
    caller that writes a further file from dst and checks that one whole (package_grow.py). `raw` is src's bytes as
    package_bytes gives them, when the caller has them already. An uncompressed src is written compressed: its file-size
    change is the compressed layout's."""
    if os.path.abspath(src) == os.path.abspath(dst):
        raise ValueError('refusing to overwrite the input')
    if raw is None:
        raw = package_bytes(src)
    h = upkinfo.summary(raw)
    chunks = h['chunks']
    check_layout(raw, chunks)
    table = chunk_table_offset(raw, chunks)
    full, _ = decomp.decompress_pkg(src)
    lo, hi = chunks[0][0], chunks[-1][0] + chunks[-1][1]
    edits = normalise_edits(edits, lo, hi)

    starts, ends = [off for off, _ in edits], [off + len(data) for off, data in edits]

    def touches(a, b):
        """Whether an edit meets [a, b): the first edit ending after a, the edits being in order and apart."""
        k = bisect.bisect_right(ends, a)
        return k < len(starts) and starts[k] < b

    expect = bytearray(full)
    changed_bytes = 0
    for off, data in edits:
        changed_bytes += sum(a != b for a, b in zip(full[off:off + len(data)], data))
        expect[off:off + len(data)] = data

    out_chunks, new_entries, report_chunks, reencoded = [], [], [], 0
    co_new = chunks[0][2]
    for i, (uo, us, co, cs) in enumerate(chunks):
        touched = touches(uo, uo + us)
        if not touched:
            out_chunks.append(raw[co:co + cs])
            new_entries.append((uo, us, co_new, cs))
            co_new += cs
            continue
        tag, bsz, usum, blocks, p = read_chunk(raw, co)
        if usum != us:
            raise ValueError(f'chunk {i}: header size {usum} != table size {us}')
        new_blocks, payload, pos = [], [], uo
        for k, (c, u) in enumerate(blocks):
            old = raw[p:p + c]
            p += c
            part = bytes(expect[pos:pos + u])
            hit = touches(pos, pos + u)
            if part == full[pos:pos + u] and not (force and hit):
                enc = old
            else:
                enc = lzo_literals(part)
                if lzo1x.decompress(enc, u) != part:
                    raise ValueError(f'literal LZO round trip failed in chunk {i} block {k}')
                reencoded += 1
            new_blocks.append((len(enc), u))
            payload.append(enc)
            pos += u
        body = struct.pack('<IIII', tag, bsz, sum(c for c, _ in new_blocks), usum)
        body += b''.join(struct.pack('<II', c, u) for c, u in new_blocks) + b''.join(payload)
        out_chunks.append(body)
        new_entries.append((uo, us, co_new, len(body)))
        report_chunks.append(dict(index=i, logicalOffset=uo, oldSize=cs, newSize=len(body)))
        co_new += len(body)

    head = bytearray(raw[:chunks[0][2]])
    for i, entry in enumerate(new_entries):
        struct.pack_into('<IIII', head, table + 4 + 16 * i, *entry)
    out = bytes(head) + b''.join(out_chunks)
    with open(dst, 'wb') as f:
        f.write(out)

    report = dict(edits=len(edits), bytesChanged=changed_bytes, chunksReencoded=report_chunks,
                  blocksReencoded=reencoded, sizeChange=len(out) - len(raw))
    if not verify:
        return report
    # Check: decode what was written and compare with the intended logical bytes.
    full2, h2 = decomp.decompress_pkg(dst)
    if full2[lo:] != bytes(expect[lo:]) or len(full2) != len(expect):
        raise ValueError('verification failed: the written package does not decode to the intended bytes')
    if [tuple(c) for c in h2['chunks']] != new_entries:
        raise ValueError('verification failed: chunk table differs from the planned one')
    h_old = {k: v for k, v in h.items() if k != 'chunks'}
    h_new = {k: v for k, v in h2.items() if k != 'chunks'}
    if h_old != h_new:
        raise ValueError('verification failed: summary fields other than the chunk table changed')
    if out[:table] != raw[:table] or out[table + 4 + 16 * len(chunks):chunks[0][2]] != \
            raw[table + 4 + 16 * len(chunks):chunks[0][2]]:
        raise ValueError('verification failed: header bytes outside the chunk table changed')
    return report


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('src')
    a.add_argument('dst')
    a.add_argument('--noop', nargs=2, type=int, metavar=('OFFSET', 'LENGTH'), required=True,
                   help='rewrite LENGTH bytes at logical OFFSET with their own value (forces a re-encode)')
    args = a.parse_args()
    off, length = args.noop
    full, _ = decomp.decompress_pkg(args.src)
    report = write_edited(args.src, args.dst, [(off, full[off:off + length])], force=True)
    print(report)


if __name__ == '__main__':
    main()
