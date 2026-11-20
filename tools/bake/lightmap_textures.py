"""A map's lightmap textures as the Build reads and copies them: the largest mip of an original bake, decoded (every
relight reads the light a piece had before the edit from it), and a texture cloned as a new export of a growing map
(a copy's own lightmaps, tools/bake/native_copy.py; a made wall's, frac_walls.py).

The top mips read are kept for each package while it is open (RAW_KEPT of them), in a table of this module's keyed
by the package object, which nothing else holds.
"""
from pathlib import Path
import struct
import sys
import weakref

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upk'))
sys.path.insert(0, str(ROOT / 'viewer'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dxt1  # noqa: E402
import lighting_records as lighting  # noqa: E402
import lightmap_fields  # noqa: E402
from texture import decompress_payload  # noqa: E402

_KEPT = weakref.WeakKeyDictionary()     # package -> {texture export: (DXT1 bytes, width, height)}


def top_mip_rgb(p, index):
    """The largest live mip of a DXT1 texture as float RGB in [0, 1], decoded by dxt1.py (the one DXT1 decoder: a
    palette's in-between colours exact, where Pillow's decoder rounds them down to whole 255ths)."""
    raw, w, h = top_mip_raw(p, index)
    return dxt1.decode_image(raw, w, h)


def top_mip_rect(p, index, x0, y0, x1, y1):
    """top_mip_rgb(p, index)[y0:y1, x0:x1], decoding only the 4-texel blocks the rectangle touches: a piece's
    rectangle is a small part of its atlas, and a relight reads two for every piece."""
    raw, w, h = top_mip_raw(p, index)
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    bx0, by0, bx1, by1 = max(0, x0 // 4), max(0, y0 // 4), min(bw, -(-x1 // 4)), min(bh, -(-y1 // 4))
    if bx1 <= bx0 or by1 <= by0:
        return np.zeros((0, 0, 3))
    image = dxt1.decode_region(raw, w, h, bx0, by0, bx1, by1)
    return image[y0 - by0 * 4:y1 - by0 * 4, x0 - bx0 * 4:x1 - bx0 * 4]


RAW_KEPT = 64       # top mips kept for each package (half a megabyte each at 1,024 texels)


def top_mip_raw(p, index):
    """(DXT1 bytes, width, height) of a texture's largest live mip, kept for the package (many pieces share an
    atlas, and reading one from the texture cache decodes its LZO in Python)."""
    kept = _KEPT.setdefault(p, {})
    if index in kept:
        return kept[index]
    if p.effective(index, 'Format') != 'PF_DXT1':
        raise ValueError(f'{p.name(index)} is not DXT1')
    r = p.native(index)
    lighting.bulk_meta(r)
    best = None
    for _ in range(r.count()):
        start = r.pos
        m = lighting.bulk_meta(r)
        m['width'], m['height'] = r.unpack('2i')
        if m['bytes'] and not m['flags'] & 32 and (best is None or m['width'] > best[0]['width']):
            best = (m, start)
    if best is None:
        raise ValueError(f'{p.name(index)} has no live mip')
    m, start = best
    if m['inline']:
        payload = p.data[start + 16:start + 16 + m['bytes']]
    else:
        cache = p.effective(index, 'TextureFileCacheName')
        with lighting.cache_file(p.path.parent, cache).open('rb') as f:
            f.seek(m['offset'])
            payload = f.read(m['bytes'])
    raw = decompress_payload(payload, m['flags'])
    w, h = m['width'], m['height']
    if len(raw) != max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 8:
        raise ValueError('DXT1 mip size mismatch')
    if len(kept) >= RAW_KEPT:
        kept.pop(next(iter(kept)))
    kept[index] = (raw, w, h)
    return kept[index]


def bulk_meta_offsets(p, index):
    """Absolute logical offsets of a texture export's bulk-data records: the first (before the mip count), then one per
    mip."""
    r = p.native(index)
    first = r.pos
    t = lightmap_fields.texture_fields(p, index)
    return [first] + [m['metaOffset'] for m in t['mips']]


def clone_texture(g, p, index):
    """A copy of texture export `index` as a new export (its own name number), its inline payloads' absolute offsets
    moved to where the copy lies. Cached mips keep their offsets in the texture cache. Returns the new export index."""
    e = p.exports[index - 1]
    off, size = e['off'], e['size']
    data = bytearray(p.data[off:off + size])
    at = g.next_offset()
    for meta in bulk_meta_offsets(p, index):
        flags, count, nbytes, offset = struct.unpack_from('<4i', p.data, meta)
        if flags & 1:
            continue                    # in a texture cache
        if offset != meta + 16:
            raise ValueError(f'{p.name(index)}: an inline bulk record at {meta} points to {offset}, not past itself')
        struct.pack_into('<i', data, meta - off + 12, offset - off + at)
    g.fresh_net_index(index, data)          # a clone sharing its original's net index is a duplicate to the game
    new = g.add_export(index, bytes(data))
    if g.entries[new - 1].offset != at:
        raise ValueError('the clone did not land where its offsets say')
    return new
