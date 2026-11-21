"""Decompress a fully-compressed UE3 package (LZO) into a flat package image.

Decoding is pure Python and slow (URB_Bar: over a second), and a build opens the same map many times, in many
processes. So a decoded image is kept, by the SHA-256 of the compressed file it came from:
- in this process, the last few (MEMO_SIZE);
- on disk, when the environment names a folder: XCOM_UNPACKED (read and written: a build's work folder) and
  XCOM_UNPACKED_KEEP (read; written only by `keep`: the pristine maps a later build opens again). A kept image is
  <sha256>.unpacked, written beside its final name and moved into place, and is used only if it has the length the
  package's chunk table gives. Without the variables nothing is read or written on disk.
A package written from another (the growing writer's read-back) is decoded only where its blocks are not its source's
(decompress_written), and kept as a decoded one is.
"""
import collections
import hashlib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lzo1x  # noqa: E402
import upkinfo  # noqa: E402

MEMO_SIZE = 4
WORK_ENV, KEEP_ENV = 'XCOM_UNPACKED', 'XCOM_UNPACKED_KEEP'
KEEP_FILES = 12         # the kept folder's newest images stay (prune_kept)
_MEMO = collections.OrderedDict()       # sha256 of the compressed file -> the decoded image
# what this process did (the build's timings read it): packages decoded whole, taken from this process's memo or from
# a kept image, and packages written from a source decoded with the source's blocks reused (decompress_written);
# seconds is the decoding of both kinds
STATS = dict(decoded=0, memo=0, disk=0, written=0, seconds=0.0)


CHUNK_TAG = 0x9E2A83C1


def read_chunk(b, co):
    """The compressed chunk whose header is at `co` in `b`, checked: (tag, block size, its uncompressed size, its
    blocks' (packed, unpacked) sizes, where the first block starts). Refused (ValueError): another tag, a block size
    of 0, a block table that does not add up to the header's two sizes, and a header or blocks running past the end
    of `b`. The one reader of a chunk header (review finding 52): the map decode here, upkinfo.load's packages
    compressed whole, and package_edit's writers."""
    if co + 16 > len(b):
        raise ValueError(f'chunk header at {co} cut short')
    tag, bsz, csum, usum = struct.unpack_from('<IIII', b, co)
    if tag != CHUNK_TAG or bsz == 0:
        raise ValueError(f'bad chunk header at {co}')
    nb = (usum + bsz - 1) // bsz
    at = co + 16 + 8 * nb
    if at > len(b):
        raise ValueError(f'chunk at {co}: block table cut short')
    blocks = [struct.unpack_from('<II', b, co + 16 + 8 * k) for k in range(nb)]
    if sum(c for c, _ in blocks) != csum or sum(u for _, u in blocks) != usum:
        raise ValueError(f'chunk at {co}: block table does not add up')
    if at + csum > len(b):
        raise ValueError(f'chunk at {co} cut short')
    return tag, bsz, usum, blocks, at


def decode_blocks(b, blocks, at):
    """The bytes of `blocks` ((packed, unpacked) sizes, from read_chunk) whose first starts at `at` in `b`, each
    block decoded to the length its table gives (lzo1x raises ValueError otherwise)."""
    out = bytearray()
    for c, u in blocks:
        out += lzo1x.decompress(b[at:at + c], u)
        at += c
    return out


def _decode(b, h):
    total = max(uo + us for uo, us, co, cs in h['chunks'])
    out = bytearray(total)
    out[:h['chunks'][0][0]] = b[:h['chunks'][0][0]]
    for uo, us, co, cs in h['chunks']:
        _, _, usum, blocks, at = read_chunk(b, co)
        if usum != us:
            raise ValueError(f'the chunk at {co} holds {usum} bytes, the chunk table says {us}')
        out[uo:uo + us] = decode_blocks(b, blocks, at)
    return bytes(out)


def _folders():
    return [f for f in (os.environ.get(WORK_ENV), os.environ.get(KEEP_ENV)) if f]


def _read_kept(key, total):
    for folder in _folders():
        path = os.path.join(folder, key + '.unpacked')
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except OSError:
            continue
        if len(data) == total:
            try:
                os.utime(path)          # read now: prune_kept drops the images read longest ago
            except OSError:
                pass
            return data
    return None


def _write_kept(folder, key, data):
    try:
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, key + '.unpacked')
        if os.path.isfile(path) and os.path.getsize(path) == len(data):
            return
        temp = '%s.%d.tmp' % (path, os.getpid())
        with open(temp, 'wb') as f:
            f.write(data)
        os.replace(temp, path)
    except OSError:
        pass                # a folder that can't be written only costs the next reader its decoding


def _decoded(path, decode, counter):
    """(the decoded image, the summary) of the package at `path`: from this process's memo, a kept image, or
    `decode(bytes, summary)` (counted under `counter`), kept in the memo and in the work folder. A package stored
    uncompressed is its own image."""
    import time
    with open(path, 'rb') as f:
        b = f.read()
    h = upkinfo.summary(b)
    if not h['chunks']:
        return b, h
    key = hashlib.sha256(b).hexdigest()
    if key in _MEMO:
        _MEMO.move_to_end(key)
        STATS['memo'] += 1
        return _MEMO[key], h
    total = max(uo + us for uo, us, co, cs in h['chunks'])
    data = _read_kept(key, total)
    if data is not None:
        STATS['disk'] += 1
    else:
        t = time.perf_counter()
        data = decode(b, h)
        STATS[counter] += 1
        STATS['seconds'] += time.perf_counter() - t
        if os.environ.get(WORK_ENV):
            _write_kept(os.environ[WORK_ENV], key, data)
    _MEMO[key] = data
    while len(_MEMO) > MEMO_SIZE:
        _MEMO.popitem(last=False)
    return data, h


def decompress_pkg(path):
    return _decoded(path, _decode, 'decoded')


def blocks_of(raw, h):
    """{logical offset: (unpacked size, physical offset, packed size)} of every block of the compressed package `raw`
    (its summary `h`), each chunk read by read_chunk."""
    out = {}
    for uo, us, co, cs in h['chunks']:
        _, _, usum, blocks, at = read_chunk(raw, co)
        if usum != us:
            raise ValueError(f'the chunk at {co} holds {usum} bytes, the chunk table says {us}')
        for c, u in blocks:
            out[uo] = (u, at, c)
            uo += u
            at += c
    return out


def decode_written(b, h, raw, src_h, full):
    """The image of the package `b` (its summary `h`) written from the package `raw` (`src_h`, decoded as `full`),
    as _decode gives it: a block of `b` whose packed bytes are those of `raw`'s block at the same logical offset and
    of the same unpacked size is taken from `full` (the decode of the same bytes); every other block is decoded. Each
    chunk is read as _decode reads it (read_chunk; its size against the chunk table's). Returns (the image, blocks
    taken, blocks decoded)."""
    source = blocks_of(raw, src_h)
    total = max(uo + us for uo, us, co, cs in h['chunks'])
    out = bytearray(total)
    out[:h['chunks'][0][0]] = b[:h['chunks'][0][0]]
    taken = decoded = 0
    for uo, us, co, cs in h['chunks']:
        _, _, usum, blocks, at = read_chunk(b, co)
        if usum != us:
            raise ValueError(f'the chunk at {co} holds {usum} bytes, the chunk table says {us}')
        for c, u in blocks:
            s = source.get(uo)
            if (s is not None and s[0] == u and s[2] == c and uo + u <= len(full)
                    and b[at:at + c] == raw[s[1]:s[1] + c]):
                out[uo:uo + u] = full[uo:uo + u]
                taken += 1
            else:
                out[uo:uo + u] = lzo1x.decompress(b[at:at + c], u)
                decoded += 1
            uo += u
            at += c
    return bytes(out), taken, decoded


def decompress_written(path, raw, src_h, full):
    """decompress_pkg of the package at `path`, written from the package whose compressed bytes are `raw` (its summary
    `src_h`, its decoded image `full`: package_grow.Grower's source): the blocks `path` keeps from `raw` are taken
    from `full` and only the others are decoded (decode_written), the same bytes as a whole decode in a fraction of
    its time (a grown map keeps all but the blocks its edits touch). The image is kept in the memo and the work
    folder under the file's hash, as decompress_pkg keeps it, so the next reader of the file decodes nothing."""
    return _decoded(path, lambda b, h: decode_written(b, h, raw, src_h, full)[0], 'written')


def keep(path, folder):
    """Decode the package at `path` (or take its kept image) and keep the image in `folder`, for later builds."""
    data, h = decompress_pkg(path)
    if h['chunks']:
        with open(path, 'rb') as f:
            key = hashlib.sha256(f.read()).hexdigest()
        _write_kept(folder, key, data)
        prune_kept(folder)


def prune_kept(folder, keep_files=KEEP_FILES):
    """Leave the `keep_files` images of `folder` read most recently."""
    try:
        files = sorted((os.path.join(folder, n) for n in os.listdir(folder) if n.endswith('.unpacked')),
                       key=os.path.getmtime, reverse=True)
        for old in files[keep_files:]:
            os.remove(old)
    except OSError:
        pass


if __name__ == '__main__':
    data, h = decompress_pkg(sys.argv[1])
    open(sys.argv[2], 'wb').write(data)
    print('ok', len(data))
