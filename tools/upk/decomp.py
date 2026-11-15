"""Decompress a fully-compressed UE3 package (LZO) into a flat package image.

Decoding is pure Python and slow (URB_Bar: over a second), and a build opens the same map many times, in many
processes. So a decoded image is kept, by the SHA-256 of the compressed file it came from:
- in this process, the last few (MEMO_SIZE);
- on disk, when the environment names a folder: XCOM_UNPACKED (read and written: a build's work folder) and
  XCOM_UNPACKED_KEEP (read; written only by `keep`: the pristine maps a later build opens again). A kept image is
  <sha256>.unpacked, written beside its final name and moved into place, and is used only if it has the length the
  package's chunk table gives. Without the variables nothing is read or written on disk.
"""
import collections
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lzo1x  # noqa: E402
import upkinfo  # noqa: E402

MEMO_SIZE = 4
WORK_ENV, KEEP_ENV = 'XCOM_UNPACKED', 'XCOM_UNPACKED_KEEP'
KEEP_FILES = 12         # the kept folder's newest images stay (prune_kept)
_MEMO = collections.OrderedDict()       # sha256 of the compressed file -> the decoded image
STATS = dict(decoded=0, memo=0, disk=0, seconds=0.0)     # what this process did (the build's timings read it)


def _decode(b, h):
    total = max(uo + us for uo, us, co, cs in h['chunks'])
    out = bytearray(total)
    out[:h['chunks'][0][0]] = b[:h['chunks'][0][0]]
    for uo, us, co, cs in h['chunks']:
        r = upkinfo.R(b, co)
        tag = r.u32(); bsz = r.u32(); csum = r.u32(); usum = r.u32()
        nb = (usum + bsz - 1) // bsz
        blocks = [(r.u32(), r.u32()) for _ in range(nb)]
        p = r.o; pos = uo
        for c, u in blocks:
            d = lzo1x.decompress(b[p:p + c], u)
            if len(d) != u:
                raise ValueError('size mismatch %d %d' % (len(d), u))
            out[pos:pos + u] = d; pos += u; p += c
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


def decompress_pkg(path):
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
        data = _decode(b, h)
        STATS['decoded'] += 1
        STATS['seconds'] += time.perf_counter() - t
        if os.environ.get(WORK_ENV):
            _write_kept(os.environ[WORK_ENV], key, data)
    _MEMO[key] = data
    while len(_MEMO) > MEMO_SIZE:
        _MEMO.popitem(last=False)
    return data, h


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
