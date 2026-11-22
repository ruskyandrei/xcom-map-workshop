"""A map's lightmap textures as the Build reads and copies them: the largest mip of an original bake, decoded (every
relight reads the light a piece had before the edit from it), and a texture cloned as a new export of a growing map
(a copy's own lightmaps, tools/bake/native_copy.py; a made wall's, frac_walls.py).

A copy's own lighting is a texture the size of what it reads (smaller built maps plan, F-151): the map's bake packs
many pieces' rectangles into one 1,024-texel atlas, and a copy reads a small rectangle of it. `crop_box` finds the box
a copy's rectangles take (with the one-texel ring the writer fills, on whole DXT1 blocks, a power of two on each side,
at least the game's smallest), `cropped_texture` makes a texture of that box holding the source's bake over it, and
`moved_record` points a lightmap's or a shadow map's coordinate scale and bias into it. `blank_texture` is one of a
chosen size holding nothing, for a piece lit from nothing (a made wall's, frac_walls.py). Each is the form the game's
own small textures take inside a map (research/evidence/lighting-texture-survey.py): every mip inline and
uncompressed, the chain down to one texel (a DXT1 mip's sides stored no smaller than 4), MipTailBaseIdx its last mip,
NeverStream and no cache name, as inline_lighting.py writes a texture and EXP-86 played (the plan's decision D1).

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
import props as legacy_props  # noqa: E402
from texture import decompress_payload  # noqa: E402

_KEPT = weakref.WeakKeyDictionary()     # package -> {texture export: (top mip bytes, width, height)}


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
    if p.effective(index, 'Format') != 'PF_DXT1':
        raise ValueError(f'{p.name(index)} is not DXT1')
    return top_mip_bytes(p, index)


def mip_bytes(fmt, width, height):
    """The bytes of a mip of `width` by `height` texels in the format `fmt` (PF_DXT1: 8 for each 4 by 4 block, a
    side under 4 taking a whole block; PF_G8: one a texel)."""
    if fmt == 'PF_DXT1':
        return max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * 8
    if fmt == 'PF_G8':
        return width * height
    raise ValueError(f'{fmt} is no lighting texture format')


def top_mip_bytes(p, index):
    """(bytes, width, height) of a lightmap's (DXT1) or a shadow map's (G8) largest live mip, kept for the package
    as top_mip_raw's are."""
    kept = _KEPT.setdefault(p, {})
    if index in kept:
        return kept[index]
    fmt = p.effective(index, 'Format')
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
    if len(raw) != mip_bytes(fmt, w, h):
        raise ValueError(f'{p.name(index)}: its {fmt} top mip is {len(raw)} bytes, not {mip_bytes(fmt, w, h)}')
    if len(kept) >= RAW_KEPT:
        kept.pop(next(iter(kept)))
    kept[index] = (bytes(raw), w, h)
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


# ------------------------------------------------------------------------------------- textures sized to a piece

SMALLEST = {'PF_DXT1': 4, 'PF_G8': 8}       # the smallest side of the game's own lightmaps and shadow maps
LEAST_STORED = {'PF_DXT1': 4, 'PF_G8': 1}   # a mip's sides as stored: a DXT1 mip no smaller than one block
DROPPED = ('TextureFileCacheName', 'NeverStream', 'FirstResourceMemMip')     # streaming's: none inside the map
RECORD = 16             # a bulk record: flags, element count, size on disk, offset in file


def power_of_two(n, least):
    """The smallest power of two that is at least n and at least `least`."""
    v = least
    while v < n:
        v *= 2
    return v


def mip_sizes(fmt, width, height):
    """[(stored width, stored height, width, height)] of each mip of a `width` by `height` texture (powers of two),
    as the game's own are: down to one texel on the longer side, a DXT1 mip's sides stored no smaller than 4
    (URB_TruckStop_EWI's 32 by 4 lightmap: 32x4, 16x4, 8x4, then three of 4x4)."""
    out, k = [], 0
    least = LEAST_STORED[fmt]
    while True:
        w, h = max(1, width >> k), max(1, height >> k)
        out.append((max(least, w), max(least, h), w, h))
        if w == 1 and h == 1:
            return out
        k += 1


def made_mips(fmt, top, width, height):
    """The bytes of every mip of a texture whose top mip is `top` (its bytes, `width` by `height`): the top as it is,
    each lower one the box average of the top mip's texels (as lightmap_writer.Fixture.image rebuilds them), DXT1
    encoded by dxt1.py; a mip stored larger than it is (a DXT1 side under 4) repeats its texels to fill the block."""
    sizes = mip_sizes(fmt, width, height)
    if fmt == 'PF_DXT1':
        image = dxt1.decode_image(top, width, height)
    else:
        image = np.frombuffer(top, np.uint8).reshape(height, width).astype(np.float64)
    out = [bytes(top)]
    for sw, sh, w, h in sizes[1:]:
        small = image.reshape(h, height // h, w, width // w, *image.shape[2:]).mean((1, 3))
        small = np.repeat(np.repeat(small, sh // h, 0), sw // w, 1)
        if fmt == 'PF_DXT1':
            out.append(dxt1.encode_blocks(dxt1.image_blocks(small).reshape(-1, 16, 3)))
        else:
            out.append(np.round(small).astype(np.uint8).tobytes())
    return out


def crop_box(rects, width, height, fmt, ring=1):
    """The box (x0, y0, w, h) of a `width` by `height` texture that a texture of its own needs to hold the
    rectangles `rects` ((x0, y0, x1, y1), half-open texels): their bounds, `ring` texels wider each way (the ring
    lightmap_writer.Fixture.image writes and the game's filtering reads), kept inside the texture; for DXT1 its start
    moved down onto a whole block; each side rounded up to a power of two, at least the game's smallest (SMALLEST),
    and moved back inside where it would pass the texture's edge. None when that is the whole texture (it is cloned
    as it is), when no rectangle is given, or for a texture whose sides are not powers of two."""
    rects = [r for r in rects if r is not None]
    if not rects or width & (width - 1) or height & (height - 1):
        return None
    x0 = max(0, min(r[0] for r in rects) - ring)
    y0 = max(0, min(r[1] for r in rects) - ring)
    x1 = min(width, max(max(r[2], r[0] + 1) for r in rects) + ring)
    y1 = min(height, max(max(r[3], r[1] + 1) for r in rects) + ring)
    if fmt == 'PF_DXT1':
        x0, y0 = x0 // 4 * 4, y0 // 4 * 4
    w = min(width, power_of_two(x1 - x0, SMALLEST[fmt]))
    h = min(height, power_of_two(y1 - y0, SMALLEST[fmt]))
    x0, y0 = min(x0, width - w), min(y0, height - h)
    if (w, h) == (width, height):
        return None
    return (x0, y0, w, h)


def moved_record(scale, bias, size, box):
    """A coordinate scale and bias (each (u, v), as fractions of a `size` = (W, H) texture) pointing at the same
    texels in a texture of the box `box` = (x0, y0, w, h) of it: scale * (W / w, H / h) and
    (bias * (W, H) - (x0, y0)) / (w, h). Each side's ratio is a power of two and x0 a whole number no larger than
    bias * W, so the values are exact in the 32-bit floats the records hold, and rect_bounds over the box's texture
    gives the old rectangle moved by (x0, y0). A ValueError where they would not be."""
    (W, H), (x0, y0, w, h) = size, box
    s = [float(np.float32(v)) for v in scale]
    b = [float(np.float32(v)) for v in bias]
    out_s = (s[0] * (W / w), s[1] * (H / h))
    out_b = ((b[0] * W - x0) / w, (b[1] * H - y0) / h)
    if any(float(np.float32(v)) != v for v in out_s + out_b):
        raise ValueError(f'a lightmap record moved into a {w} by {h} box is not exact')
    return out_s, out_b


def _int_tag(g, name, value):
    return struct.pack('<ii', g.name(name), 0) + struct.pack('<ii', g.name('IntProperty'), 0) \
        + struct.pack('<ii', 4, 0) + struct.pack('<i', value)


def _after_mips(raw, end):
    """The bytes of a texture export after its mips (its cache GUID and what follows), `raw` its data and `end`
    where its properties end."""
    pos = end
    flags, _, size, _ = struct.unpack_from('<4i', raw, pos)       # the source art
    pos += RECORD + (0 if flags & 1 else size)
    count = struct.unpack_from('<i', raw, pos)[0]
    pos += 4
    for _ in range(count):
        flags, _, size, _ = struct.unpack_from('<4i', raw, pos)
        pos += RECORD + (0 if flags & 1 else size) + 8
    return bytes(raw[pos:])


def sized_texture(g, p, template, width, height, mips):
    """A new texture export of the map `g` grows: a copy of texture export `template` (of `p`; its class, format and
    saved properties) whose mips are `mips` (their bytes, top first, as mip_sizes lays them out for `width` by
    `height`), every one inline and uncompressed; SizeX, SizeY and MipTailBaseIdx (its last mip) set, no cache name,
    NeverStream True, a net index of its own. Returns its export index."""
    fmt = p.effective(template, 'Format')
    sizes = mip_sizes(fmt, width, height)
    if len(mips) != len(sizes) or any(len(m) != mip_bytes(fmt, sw, sh) for m, (sw, sh, _, _) in zip(mips, sizes)):
        raise ValueError(f'mips that are not a {width} by {height} {fmt} texture\'s')
    e = p.exports[template - 1]
    raw = p.data[e['off']:e['off'] + e['size']]
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    end = p.properties(template)[1] - e['off']          # after the terminator
    rows, after = legacy_props.read_tags(raw, start, end, p.names)
    if after != end:
        raise ValueError(f'{p.name(template)}: its properties end where the reader does not say')
    values = dict(SizeX=width, SizeY=height, MipTailBaseIdx=len(sizes) - 1)
    out = bytearray(raw[:start])
    for name, kind, _, slot, at, size in rows:
        if name in DROPPED:
            continue
        tag = bytearray(raw[at - 24 - (8 if kind in ('StructProperty', 'ByteProperty') else 0):at + size])
        if name in values and kind == 'IntProperty' and size == 4 and slot == 0:
            struct.pack_into('<i', tag, len(tag) - 4, values.pop(name))
        out += tag
    for name, value in values.items():                  # one the template left at its default
        out += _int_tag(g, name, value)
    out += struct.pack('<ii', g.name('NeverStream'), 0) + struct.pack('<ii', g.name('BoolProperty'), 0) \
        + struct.pack('<ii', 0, 0) + b'\x01' + struct.pack('<ii', g.name('None'), 0)
    base = g.next_offset()
    out += struct.pack('<4i', 0, 0, 0, base + len(out) + RECORD)          # the source art: empty
    out += struct.pack('<i', len(sizes))
    for m, (sw, sh, _, _) in zip(mips, sizes):
        out += struct.pack('<4i', 0, len(m), len(m), base + len(out) + RECORD) + bytes(m) + struct.pack('<2i', sw, sh)
    out += _after_mips(raw, end)                        # the cache GUID and what follows it, as the template's
    g.fresh_net_index(template, out)
    new = g.add_export(template, bytes(out))
    if g.entries[new - 1].offset != base:
        raise ValueError('the sized texture did not land where its offsets say')
    return new


def cropped_texture(g, p, source, box):
    """sized_texture of the box `box` = (x0, y0, w, h) of texture `source`: its top mip the source's over the box
    (DXT1 blocks or G8 bytes copied as they are; a DXT1 box starts on a whole block), its lower mips made from that
    (made_mips). Returns its export index."""
    fmt = p.effective(source, 'Format')
    raw, width, height = top_mip_bytes(p, source)
    x0, y0, w, h = box
    if x0 < 0 or y0 < 0 or x0 + w > width or y0 + h > height:
        raise ValueError(f'a box {box} outside {p.name(source)}\'s {width} by {height}')
    if fmt == 'PF_DXT1':
        if x0 % 4 or y0 % 4 or w % 4 or h % 4:
            raise ValueError(f'a DXT1 box {box} not on whole blocks')
        blocks = np.frombuffer(raw, np.uint8).reshape(max(1, height // 4), max(1, width // 4), 8)
        top = blocks[y0 // 4:(y0 + h) // 4, x0 // 4:(x0 + w) // 4].tobytes()
    else:
        top = np.frombuffer(raw, np.uint8).reshape(height, width)[y0:y0 + h, x0:x0 + w].tobytes()
    return sized_texture(g, p, source, w, h, made_mips(fmt, top, w, h))


def blank_texture(g, p, template, width, height):
    """sized_texture of `width` by `height` holding nothing (DXT1 black, G8 0), for a piece lit from nothing: the
    relight writes every texel of its rectangle and its ring. `template`: a texture of the class and format wanted.
    Returns its export index."""
    fmt = p.effective(template, 'Format')
    return sized_texture(g, p, template, width, height,
                         [bytes(mip_bytes(fmt, sw, sh)) for sw, sh, _, _ in mip_sizes(fmt, width, height)])
