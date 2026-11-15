"""Fixed-size edits of a compressed v845 package at uncompressed (logical) offsets, in any chunk.

Generalises seed_tiles.py's method: only the 128 KB blocks an edit touches are re-encoded (as literal LZO1X runs),
so every logical offset in the package stays the same. A re-encoded block is larger than the original, so its chunk
grows; later chunks move in the file and the summary's chunk table gets their new physical offsets and sizes.
Nothing else in the summary holds a physical offset. The result is decoded again and compared with the intended
bytes before the function returns.

Refuses: overlapping or empty edits, edits outside the compressed chunks (the uncompressed header is not edited),
packages whose chunks are not contiguous or do not end the file, and writing over the input. Moving later chunks is
a format operation the game has not yet been seen to accept (baker design, C0); seed_tiles.py only ever grew the last
chunk.

  python package_edit.py <in.upk> <out.upk> --noop <logical offset> <length>
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decomp  # noqa: E402
import lzo1x  # noqa: E402
import upkinfo  # noqa: E402

CHUNK_TAG = 0x9E2A83C1


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


def check_layout(raw, chunks):
    if not chunks:
        raise ValueError('package is not compressed; edit its bytes directly')
    for i in range(len(chunks) - 1):
        uo, us, co, cs = chunks[i]
        if chunks[i + 1][0] != uo + us or chunks[i + 1][2] != co + cs:
            raise ValueError(f'chunks {i} and {i + 1} are not contiguous')
    uo, us, co, cs = chunks[-1]
    if co + cs != len(raw):
        raise ValueError('data follows the last chunk; this tool cannot move it')


def read_chunk(raw, co):
    r = upkinfo.R(raw, co)
    tag, bsz, csum, usum = r.u32(), r.u32(), r.u32(), r.u32()
    if tag != CHUNK_TAG or bsz == 0:
        raise ValueError(f'bad chunk header at {co}')
    nb = (usum + bsz - 1) // bsz
    blocks = [(r.u32(), r.u32()) for _ in range(nb)]
    if sum(c for c, _ in blocks) != csum or sum(u for _, u in blocks) != usum:
        raise ValueError(f'chunk at {co}: block table does not add up')
    return tag, bsz, usum, blocks, r.o


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


def write_edited(src, dst, edits, force=False, verify=True):
    """Write dst: src with each (logical offset, bytes) in edits written over the same number of bytes.

    With force, every block an edit overlaps is re-encoded even if its bytes did not change (a no-op edit then still
    exercises the re-encode and the chunk moves). Returns a report dict: chunks and blocks re-encoded, bytes changed
    and the file-size change. `verify` False leaves out the check that dst decodes to the intended bytes: for a
    caller that writes a further file from dst and checks that one whole (package_grow.py)."""
    if os.path.abspath(src) == os.path.abspath(dst):
        raise ValueError('refusing to overwrite the input')
    with open(src, 'rb') as f:
        raw = f.read()
    h = upkinfo.summary(raw)
    chunks = h['chunks']
    check_layout(raw, chunks)
    table = chunk_table_offset(raw, chunks)
    full, _ = decomp.decompress_pkg(src)
    lo, hi = chunks[0][0], chunks[-1][0] + chunks[-1][1]
    edits = normalise_edits(edits, lo, hi)

    expect = bytearray(full)
    changed_bytes = 0
    for off, data in edits:
        changed_bytes += sum(a != b for a, b in zip(full[off:off + len(data)], data))
        expect[off:off + len(data)] = data

    out_chunks, new_entries, report_chunks, reencoded = [], [], [], 0
    co_new = chunks[0][2]
    for i, (uo, us, co, cs) in enumerate(chunks):
        touched = any(off < uo + us and off + len(data) > uo for off, data in edits)
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
            hit = any(off < pos + u and off + len(data) > pos for off, data in edits)
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
