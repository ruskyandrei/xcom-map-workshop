"""Build lighting test maps from fixed-size edits (baker design, stage 1: C0, C1, C2).

Writes <out>/<variant>.upk, a copy of the source map with the chosen edits, and, when a texture is redirected, the
variant texture cache <out>/<cache>.tfc with the redirected mips. The shared Lighting.tfc is only read. A manifest
(<out>/<variant>.fixture.json) records the source and output hashes and every edit with its old and new values.

Operations (a JSON list, or the CLI flags):
- {"op": "noop", "component": path}: rewrite the component's LOD-0 lightmap record with its own bytes, forcing that
  block to be re-encoded (C0).
- {"op": "redirect", "texture": name}: copy the texture's mips stored in Lighting.tfc into the variant cache unchanged
  and point the texture there (C1).
- {"op": "scale", "component": path, "slot": 1, "factor": [fx, fy, fz]}: multiply one LOD-0 slot scale (C2).
- {"op": "setscale", "component": path, "slot": 1, "value": [x, y, z]}: set one LOD-0 slot scale (C2).
- {"op": "paint", "component": path, "slot": 0, "rgb": [r, g, b]}: redirect the slot's texture if needed and fill the
  component's atlas rectangle with one colour in every mip, as whole DXT1 blocks only (C2). Inline mips are painted in
  place (they are uncompressed); cached mips are re-encoded as literal LZO. With "rgb" a list of colours, the
  rectangle is split into that many bands along atlas U, one colour each.
- {"op": "image", "component": path, "slot": 1, "npz": file, "key": name}: write per-texel values into the
  component's rectangle: the .npz holds <name> (h, w, 3: stored 0-1 values over the rectangle's texel bounds at the
  top mip) and <name>_mask (h, w: the texels to set). Partly covered blocks are merged; lower mips down to 1/64 of
  the top mip's width (16 texels for a 1024 atlas, 4 for the small ones) are rebuilt from the edited top mip by box
  averaging (relight.py writes these).

- {"op": "gray", "texture": name, "x0": x, "y0": y, "npz": file, "key": name}: write one-byte texels (a G8
  dominant-light shadow map, `shadowmaps.py`) at [x0, x0 + w) x [y0, y0 + h) of the top mip: the .npz holds <name>
  (h, w: values 0-1) and <name>_mask; lower mips are rebuilt over the touched texels by box averaging.

A texture whose mips are all inside the map package (the small lightmaps, up to 64 texels wide, uncompressed) is
written there in place, at the same size; only textures with mips in Lighting.tfc are redirected to the variant
cache.

The variant cache is named like any texture cache, `<Name>_<n>`, where <Name> must already be in the map's name table:
the cache name is stored as an FName (name index, number n + 1), so the edit keeps its size.

  python -B tools/bake/lighting_fixture.py <map.upk> <out dir> <variant> [--cache Lighting_7000]
      [--noop COMPONENT] [--redirect TEXTURE] [--scale COMPONENT SLOT FACTOR] [--paint COMPONENT SLOT R G B]
"""
import argparse
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upk'))
sys.path.insert(0, str(ROOT / 'viewer'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_lighting as lighting  # noqa: E402
import dxt1  # noqa: E402
import lightmap_fields  # noqa: E402
from lightmap_texels import rect_bounds  # noqa: E402
import package_edit  # noqa: E402
from texture import decompress_payload  # noqa: E402

BULK_TAG = 0x9E2A83C1
CACHE_FLAG = 1          # BULKDATA_StoreInSeparateFile
LZO_FLAG = 16           # BULKDATA_SerializeCompressedLZO


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def solid_block(rgb):
    """A DXT1 block that decodes to one colour (both endpoints equal, every index 0)."""
    if len(rgb) != 3 or not all(0.0 <= c <= 1.0 for c in rgb):
        raise ValueError('colour channels must be in [0, 1]')
    r, g, b = (round(rgb[0] * 31), round(rgb[1] * 63), round(rgb[2] * 31))
    c = r << 11 | g << 5 | b
    return struct.pack('<HHI', c, c, 0)


def block_range(bias, scale, size):
    """Whole 4-texel blocks inside the rectangle [bias, bias + scale) of an atlas `size` texels wide."""
    lo, hi = bias * size, (bias + scale) * size
    first, last = math.ceil(lo / 4 - 1e-9), math.floor(hi / 4 + 1e-9)
    return max(first, 0), min(last, max(1, size // 4))


def paint_dxt1(raw, width, height, bias, scale, blocks):
    """Copy of raw (a DXT1 mip) with the whole blocks inside the rectangle painted; returns (data, blocks painted).

    `blocks` is one DXT1 block for the whole rectangle, or a list of N blocks: the rectangle's block columns are then
    split into N bands of (nearly) equal width, left to right in atlas U, each painted with its own block. A band can
    get no columns at a small mip."""
    if isinstance(blocks, (bytes, bytearray)):
        blocks = [bytes(blocks)]
    bw = max(1, (width + 3) // 4)
    if len(raw) != bw * max(1, (height + 3) // 4) * 8:
        raise ValueError('DXT1 mip size mismatch')
    x0, x1 = block_range(bias[0], scale[0], width)
    y0, y1 = block_range(bias[1], scale[1], height)
    n = len(blocks)
    edges = [x0 + round(k * max(0, x1 - x0) / n) for k in range(n + 1)]
    out = bytearray(raw)
    count = 0
    for band, block in enumerate(blocks):
        for by in range(y0, y1):
            for bx in range(edges[band], edges[band + 1]):
                k = (by * bw + bx) * 8
                out[k:k + 8] = block
                count += 1
    return bytes(out), count


def compressed_bulk(raw, block_size):
    """UE3 compressed bulk payload (LZO flag) holding raw as literal-LZO blocks."""
    blocks = [raw[k:k + block_size] for k in range(0, len(raw), block_size)]
    enc = [package_edit.lzo_literals(b) for b in blocks]
    out = struct.pack('<4I', BULK_TAG, block_size, sum(map(len, enc)), len(raw))
    out += b''.join(struct.pack('<II', len(e), len(b)) for e, b in zip(enc, blocks)) + b''.join(enc)
    if decompress_payload(out, LZO_FLAG) != raw:
        raise ValueError('compressed bulk round trip failed')
    return out


def bulk_block_size(payload):
    tag, block_size = struct.unpack_from('<II', payload, 0)
    if tag != BULK_TAG or block_size == 0:
        raise ValueError('not a compressed bulk payload')
    return block_size


def parse_cache_name(p, cache):
    m = re.fullmatch(r'([A-Za-z][A-Za-z0-9_]*?)_(\d+)', cache)
    if not m:
        raise ValueError('the cache name must look like <Name>_<number>, for example Lighting_7000')
    base, n = m.group(1), int(m.group(2))
    if base not in p.names:
        raise ValueError(f'{base} is not in the map\'s name table')
    if (p.path.parent / f'{cache}.tfc').exists():
        raise ValueError(f'{cache}.tfc already exists beside the source map')
    return p.names.index(base), n + 1


class Fixture:
    def __init__(self, src, cache, tfc=None):
        """`tfc`: the Lighting.tfc to read cached mips from (default: the source map's, beside it or where its
        tfc-folder.txt points)."""
        self.p = lighting.Package(src)
        self.tfc = Path(tfc) if tfc else lighting.cache_file(self.p.path.parent, 'Lighting')
        if self.p.header['lic'] != 64:
            raise ValueError('EW licensee-64 maps only')
        self.cache = cache
        self.cache_name = parse_cache_name(self.p, cache) if cache else None
        self.edits = {}            # logical offset -> bytes
        self.force = []            # offsets of forced no-op edits
        self.cache_data = bytearray()
        self.redirected = {}       # texture export -> {mip index: (payload, raw)}
        self.in_package = {}       # texture export -> its fields, for textures with every mip inline
        self.imaged = {}           # texture export -> the components whose rectangles were written into it (image)
        self.log = []

    def edit(self, offset, data, what):
        old = bytes(self.p.data[offset:offset + len(data)])
        for o, d in self.edits.items():
            if o < offset + len(data) and offset < o + len(d):
                raise ValueError(f'{what}: overlaps an earlier edit at {o}')
        self.edits[offset] = bytes(data)
        self.log.append(dict(what=what, offset=offset, old=old.hex(), new=bytes(data).hex()))

    def component(self, path):
        index = self.p.by_name.get(path)
        if index is None:
            raise ValueError(f'no export {path}')
        f = lightmap_fields.component_fields(self.p, index)
        if not f['lods'] or f['lods'][0]['lightmap']['type'] != 2:
            raise ValueError(f'{path} has no LOD-0 texture lightmap')
        return f['lods'][0]['lightmap']

    def noop(self, path):
        lm = self.component(path)
        at = lm['slots'][0]['textureOffset']
        self.edit(at, self.p.data[at:at + 16], f'noop {path}')
        self.force.append(at)

    def scale(self, path, slot, factor):
        lm = self.component(path)
        s = lm['slots'][slot]
        new = [a * b for a, b in zip(s['scale'], factor)]
        if not all(math.isfinite(v) and v > 0 for v in new):
            raise ValueError('scaled values must be finite and positive')
        self.edit(s['scaleOffset'], struct.pack('<3f', *new), f'scale {path} slot {slot} {s["scale"]} -> {new}')

    def _texture(self, index):
        return lightmap_fields.texture_fields(self.p, index)

    def redirect(self, index):
        """Read the texture's cached mips; the cache retarget is written by finish(). A texture with every mip inside
        the package has nothing to redirect: its mips are edited in place (empty `mips`)."""
        if index in self.redirected:
            return self.redirected[index]
        if index in self.in_package:
            return self.in_package[index]
        if self.cache_name is None:
            raise ValueError('redirect and paint need --cache')
        t = self._texture(index)
        # no cache name: kept wholly inside the map (texture_fields checked every live mip is inline), so no mip is
        # read below and it is edited in place
        if t['cache'] is not None and t['cache'] != 'Lighting':
            raise ValueError(f'{t["path"]} is not in Lighting.tfc')
        mips = {}
        tfc = self.tfc
        with tfc.open('rb') as f:
            for k, m in enumerate(t['mips']):
                if not m['flags'] & CACHE_FLAG or not m['bytes'] or m['flags'] & 32:
                    continue
                if m['flags'] & ~(CACHE_FLAG | LZO_FLAG):
                    raise ValueError(f'unexpected bulk flags {m["flags"]}')
                f.seek(m['offset'])
                payload = f.read(m['bytes'])
                raw = decompress_payload(payload, m['flags'])
                if len(raw) != m['count']:
                    raise ValueError('cached mip size mismatch')
                mips[k] = dict(payload=payload, raw=raw, meta=m)
        if not mips:
            live = [m for m in t['mips'] if m['bytes'] and not m['flags'] & 32]
            if not live or any(not m['inline'] or m['flags'] for m in live):
                raise ValueError(f'{t["path"]} has neither cached mips nor uncompressed inline ones')
            self.in_package[index] = dict(fields=t, mips={})
            return self.in_package[index]
        self.redirected[index] = dict(fields=t, mips=mips)
        return self.redirected[index]

    def setscale(self, path, slot, value):
        lm = self.component(path)
        s = lm['slots'][slot]
        if len(value) != 3 or not all(math.isfinite(v) and v > 0 for v in value):
            raise ValueError('a scale is three finite positive values')
        self.edit(s['scaleOffset'], struct.pack('<3f', *value), f'set scale {path} slot {slot} {s["scale"]} -> {value}')

    def paint(self, path, slot, rgb):
        """Paint one colour (rgb) or bands of colours (a list of rgb, left to right in atlas U)."""
        lm = self.component(path)
        s = lm['slots'][slot]
        if s['index'] <= 0:
            raise ValueError(f'{path} slot {slot} has no texture')
        bands = rgb if rgb and isinstance(rgb[0], (list, tuple)) else [rgb]
        counts = self.paint_rect(s['index'], lm['coordinateBias'], lm['coordinateScale'], bands)
        self.log.append(dict(what=f'paint {path} slot {slot} ({s["texture"]}) rgb {bands if len(bands) > 1 else rgb}',
                             blocksPerMip=counts))

    def paint_rect(self, index, bias, scale, bands):
        """Paint the rectangle [bias, bias + scale) of texture `index` (atlas coordinates) in every mip, as whole DXT1
        blocks, with one colour per band along atlas U. Returns the blocks painted per mip."""
        t = self.redirect(index)
        block = [solid_block(c) for c in bands]
        counts = []
        for k, m in enumerate(t['fields']['mips']):
            if k in t['mips']:
                mip = t['mips'][k]
                mip['raw'], n = paint_dxt1(mip['raw'], m['width'], m['height'], bias, scale, block)
                mip['painted'] = mip.get('painted', 0) + n
            elif m['inline'] and m['bytes'] and not m['flags']:
                raw = self.edits.get(m['payloadOffset'], bytes(self.p.data[m['payloadOffset']:
                                                                        m['payloadOffset'] + m['bytes']]))
                new, n = paint_dxt1(raw, m['width'], m['height'], bias, scale, block)
                if n:
                    self.edits.pop(m['payloadOffset'], None)
                    self.log = [e for e in self.log if e.get('offset') != m['payloadOffset']]
                    self.edit(m['payloadOffset'], new, f'paint inline mip {m["width"]}x{m["height"]} of '
                                                       f'{t["fields"]["path"]}')
            else:
                n = 0
            counts.append(dict(mip=f'{m["width"]}x{m["height"]}', blocks=n))
        return counts

    def _mip_raw(self, t, k, m):
        """(raw DXT1 bytes, where) of mip k: the redirected copy for cached mips, else the inline payload."""
        if k in t['mips']:
            return t['mips'][k]['raw'], 'cache'
        if m['inline'] and m['bytes'] and not m['flags']:
            return self.edits.get(m['payloadOffset'], bytes(self.p.data[m['payloadOffset']:
                                                                     m['payloadOffset'] + m['bytes']])), 'inline'
        return None, None

    def image(self, path, slot, texels, mask, min_mip_size=None, only_changed=False, ring=False):
        """Write per-texel values into the component's atlas rectangle: `texels` (h, w, 3) stored values (0-1) at the
        top mip, covering the rectangle's texel bounds (x0, y0, x1, y1) as `lightmap_texels.rasterise` gives them,
        and `mask` (h, w) the texels to set. Blocks the rectangle only partly covers are decoded, merged and
        re-encoded. Each lower mip (down to `min_mip_size` texels wide; by default 1/64 of the top mip's width and at
        least 4) is the box average of the edited top mip, re-encoded on the blocks the rectangle touches; smaller
        mips, and mips under 4 texels high, are left as they are.

        `only_changed`: only the blocks that hold a masked texel are written (in a lower mip, the blocks whose
        texels average one); every other block keeps its bytes, so what the mask leaves out stays the original's
        exactly (faster-bake plan, 5.2). Without it every block the rectangle touches is encoded again.

        `ring`: the texels just outside the rectangle are written with it (faster-bake plan, 5.3). A lightmap's
        coordinates run to the rectangle's very edge, where the game's filtering reads half of its light from the
        texel beyond: the piece's own padding, which the original bake filled from the border (URB_Bar: no rectangle
        comes within a texel of another, and the ring differs from the border by 0.05 where texels three further
        out differ by 0.43). Each ring texel takes the new value of the rectangle's texel nearest it, where that
        one is written; so the padding follows a border that changed, and a new slot scale.

        Only the part of the top mip the written blocks cover is decoded, not the whole atlas."""
        lm = self.component(path)
        s = lm['slots'][slot]
        if s['index'] <= 0:
            raise ValueError(f'{path} slot {slot} has no texture')
        t = self.redirect(s['index'])
        self.imaged.setdefault(s['index'], set()).add(path)
        mips = t['fields']['mips']
        top_raw, _ = self._mip_raw(t, 0, mips[0])
        width, height = mips[0]['width'], mips[0]['height']
        if min_mip_size is None:
            min_mip_size = max(4, width // 64)
        x0, y0, x1, y1 = rect_bounds(lm, width, height)
        if texels.shape[:2] != (y1 - y0, x1 - x0) or mask.shape != texels.shape[:2]:
            raise ValueError('texels and mask must cover the rectangle exactly')
        rect = (x0, y0, x1, y1)
        if ring:    # the blocks written are those of the rectangle with its ring
            x0, y0, x1, y1 = max(0, x0 - 1), max(0, y0 - 1), min(width, x1 + 1), min(height, y1 + 1)
        # the mips written, each with its block bounds; and the part of the top mip those blocks cover
        plan = []
        for k, m in enumerate(mips):
            f = 1 << k
            raw = None
            if not (m['width'] != width >> k or m['height'] != height >> k
                    or (k and (m['width'] < min_mip_size or m['height'] < 4))):
                raw, where = self._mip_raw(t, k, m)
            if raw is None:
                plan.append(None)
                continue
            w_k, h_k = m['width'], m['height']
            bx0, by0 = (x0 // f) // 4, (y0 // f) // 4
            bx1, by1 = -(-((x1 + f - 1) // f) // 4), -(-((y1 + f - 1) // f) // 4)
            bx1, by1 = min(bx1, max(1, w_k // 4)), min(by1, max(1, h_k // 4))
            plan.append((raw, where, bx0, by0, bx1, by1))
        live = [(k, q) for k, q in enumerate(plan) if q]
        pad_w, pad_h = max(1, (width + 3) // 4) * 4, max(1, (height + 3) // 4) * 4
        X0 = min(q[2] * 4 << k for k, q in live)
        Y0 = min(q[3] * 4 << k for k, q in live)
        X1 = min(max(q[4] * 4 << k for k, q in live), pad_w)
        Y1 = min(max(q[5] * 4 << k for k, q in live), pad_h)
        original = dxt1.decode_region(top_raw, width, height, X0 // 4, Y0 // 4, X1 // 4, Y1 // 4)
        original = original[:height - Y0, :width - X0]
        edited = original.copy()
        wx0, wy0, wx1, wy1 = x0, y0, x1, y1         # what is written: the rectangle, with its ring if asked
        x0, y0, x1, y1 = rect
        region = edited[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0]
        region[mask] = np.clip(texels[mask], 0, 1)
        changed = np.zeros(edited.shape[:2], bool)
        changed[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0] = mask
        if ring:
            # each texel of the written area with the rectangle's texel nearest it; the ring's are those outside
            ny = np.clip(np.arange(wy0, wy1), y0, y1 - 1) - y0
            nx = np.clip(np.arange(wx0, wx1), x0, x1 - 1) - x0
            take = mask[np.ix_(ny, nx)]
            take[y0 - wy0:y1 - wy0, x0 - wx0:x1 - wx0] = False
            edited[wy0 - Y0:wy1 - Y0, wx0 - X0:wx1 - X0][take] = np.clip(texels[np.ix_(ny, nx)][take], 0, 1)
            changed[wy0 - Y0:wy1 - Y0, wx0 - X0:wx1 - X0] |= take
        counts = []
        outside_change = unmasked_change = 0.0
        for k, m in enumerate(mips):
            f = 1 << k
            if plan[k] is None:
                counts.append(dict(mip=f'{m["width"]}x{m["height"]}', blocks=0))
                continue
            raw, where, bx0, by0, bx1, by1 = plan[k]
            w_k, h_k = m['width'], m['height']
            # the block region at mip k, from the edited top mip (box average over f x f texels)
            ys, xs = slice(by0 * 4 * f - Y0, by1 * 4 * f - Y0), slice(bx0 * 4 * f - X0, bx1 * 4 * f - X0)
            src = edited[ys, xs]
            img = src.reshape(src.shape[0] // f, f, src.shape[1] // f, f, 3).mean((1, 3))
            if k == 0:
                inside = np.zeros(img.shape[:2], bool)      # (with its ring, which is written on purpose)
                inside[wy0 - by0 * 4:wy1 - by0 * 4, wx0 - bx0 * 4:wx1 - bx0 * 4] = True
                masked = np.zeros(img.shape[:2], bool)
                masked[y0 - by0 * 4:y1 - by0 * 4, x0 - bx0 * 4:x1 - bx0 * 4] = mask
                before = original[ys, xs]
            blocks = dxt1.encode_blocks(dxt1.image_blocks(img).reshape(-1, 16, 3))
            bw, bh = max(1, (w_k + 3) // 4), max(1, (h_k + 3) // 4)
            new = np.frombuffer(raw, np.uint8).reshape(bh, bw, 8).copy()
            fresh = np.frombuffer(blocks, np.uint8).reshape(by1 - by0, bx1 - bx0, 8)
            if only_changed:
                c = changed[ys, xs]
                write = c.reshape(c.shape[0] // (4 * f), 4 * f, c.shape[1] // (4 * f), 4 * f).any((1, 3))
                new[by0:by1, bx0:bx1][write] = fresh[write]
                n = int(write.sum())
            else:
                new[by0:by1, bx0:bx1] = fresh
                n = (bx1 - bx0) * (by1 - by0)
            new = new.tobytes()
            if k == 0:
                after = dxt1.decode_region(new, w_k, h_k, bx0, by0, bx1, by1)[:before.shape[0], :before.shape[1]]
                change = np.abs(after - before).max(2)
                outside_change = float(change[~inside].max()) if (~inside).any() else 0.0
                unmasked_change = float(change[inside & ~masked].max()) if (inside & ~masked).any() else 0.0
            if where == 'cache':
                t['mips'][k]['raw'] = new
                t['mips'][k]['painted'] = t['mips'][k].get('painted', 0) + n
            elif n:
                self.edits.pop(m['payloadOffset'], None)
                self.log = [e for e in self.log if e.get('offset') != m['payloadOffset']]
                self.edit(m['payloadOffset'], new, f'image inline mip {w_k}x{h_k} of {t["fields"]["path"]}')
            counts.append(dict(mip=f'{w_k}x{h_k}', blocks=n))
        self.log.append(dict(what=f'image {path} slot {slot} ({s["texture"]}): {int(mask.sum())} texels in '
                                  f'[{x0}, {x1}) x [{y0}, {y1})',
                             blocksPerMip=counts, maxChangeOutsideRect=round(outside_change, 5),
                             maxChangeUnmaskedInRect=round(unmasked_change, 5)))

    def gray(self, index, x0, y0, values, mask, min_mip_size=None):
        """Write one-byte-per-texel values (a G8 shadow map) into the texture's top mip: `values` (h, w) in [0, 1]
        at texels [x0, x0 + w) x [y0, y0 + h), `mask` (h, w) the texels to set. Each lower mip (down to
        `min_mip_size` texels wide, by default 1/64 of the top mip's width and at least 4) is the box average of the
        edited top mip over the texels the rectangle touches; smaller mips are left as they are."""
        t = self.redirect(index)
        mips = t['fields']['mips']
        if t['fields']['format'] != 'PF_G8':
            raise ValueError(f'{t["fields"]["path"]} is {t["fields"]["format"]}, not PF_G8')
        width, height = mips[0]['width'], mips[0]['height']
        if min_mip_size is None:
            min_mip_size = max(4, width // 64)
        h, w = values.shape
        if mask.shape != values.shape or x0 < 0 or y0 < 0 or x0 + w > width or y0 + h > height:
            raise ValueError('values and mask must lie inside the top mip')
        top_raw, _ = self._mip_raw(t, 0, mips[0])
        edited = np.frombuffer(top_raw, np.uint8).reshape(height, width).astype(np.float64)
        region = edited[y0:y0 + h, x0:x0 + w]
        region[mask] = np.round(np.clip(values[mask], 0, 1) * 255)
        counts = []
        for k, m in enumerate(mips):
            f = 1 << k
            if m['width'] != width >> k or m['height'] != height >> k or (k and m['width'] < min_mip_size):
                counts.append(dict(mip=f'{m["width"]}x{m["height"]}', texels=0))
                continue
            raw, where = self._mip_raw(t, k, m)
            if raw is None:
                counts.append(dict(mip=f'{m["width"]}x{m["height"]}', texels=0))
                continue
            # the touched texels at mip k, from the edited top mip (box average over f x f texels)
            ax0, ay0 = x0 // f, y0 // f
            ax1, ay1 = min(-(-(x0 + w) // f), m['width']), min(-(-(y0 + h) // f), m['height'])
            src = edited[ay0 * f:ay1 * f, ax0 * f:ax1 * f]
            img = src.reshape(ay1 - ay0, f, ax1 - ax0, f).mean((1, 3))
            new = np.frombuffer(raw, np.uint8).reshape(m['height'], m['width']).copy()
            new[ay0:ay1, ax0:ax1] = np.round(img).astype(np.uint8)
            new = new.tobytes()
            if where == 'cache':
                t['mips'][k]['raw'] = new
                t['mips'][k]['painted'] = t['mips'][k].get('painted', 0) + img.size
            else:
                self.edits.pop(m['payloadOffset'], None)
                self.log = [e for e in self.log if e.get('offset') != m['payloadOffset']]
                self.edit(m['payloadOffset'], new, f'gray inline mip {m["width"]}x{m["height"]} of '
                                                   f'{t["fields"]["path"]}')
            counts.append(dict(mip=f'{m["width"]}x{m["height"]}', texels=int(img.size)))
        self.log.append(dict(what=f'gray {t["fields"]["path"]}: {int(mask.sum())} texels in [{x0}, {x0 + w}) x '
                                  f'[{y0}, {y0 + h})', texelsPerMip=counts))

    def others_changed(self, threshold=0.03):
        """What the image writes changed in the rectangles of components they were not for (faster-bake plan, 5.3):
        a write encodes whole 4-texel blocks again, and a rectangle shares its edge blocks with what lies around it.
        That is padding as a rule; this says when it is another piece's light. Returns dict(textures, pieces: the
        components touched, texels: how many of their top-mip texels changed by more than `threshold`, largest)."""
        out = dict(textures=0, pieces=[], texels=0, largest=0.0)
        if not self.imaged:
            return out
        rects = {}
        for i in range(1, len(self.p.exports) + 1):
            if not self.p.cls(i).endswith('StaticMeshComponent'):
                continue
            try:
                f = lightmap_fields.component_fields(self.p, i)
            except Exception:
                continue
            if not f['lods'] or f['lods'][0]['lightmap']['type'] != 2:
                continue
            for slot in f['lods'][0]['lightmap']['slots'][:2]:
                if slot['index'] in self.imaged:
                    rects.setdefault(slot['index'], []).append((self.p.name(i), f['lods'][0]['lightmap']))
        for index, written in self.imaged.items():
            t = self.redirected.get(index) or self.in_package.get(index)
            m = t['fields']['mips'][0]
            width, height = m['width'], m['height']
            now, _ = self._mip_raw(t, 0, m)
            if 0 in t['mips']:
                before = decompress_payload(t['mips'][0]['payload'], m['flags'])
            else:
                before = bytes(self.p.data[m['payloadOffset']:m['payloadOffset'] + m['bytes']])
            if now == before:
                continue
            diff = np.abs(dxt1.decode_image(now, width, height) - dxt1.decode_image(before, width, height)).max(2)
            ours = np.zeros(diff.shape, bool)
            for path, lm in rects.get(index, []):
                if path in written:
                    x0, y0, x1, y1 = rect_bounds(lm, width, height)
                    ours[y0:y1, x0:x1] = True
            diff[ours] = 0.0
            touched = False
            for path, lm in rects.get(index, []):
                if path in written:
                    continue
                x0, y0, x1, y1 = rect_bounds(lm, width, height)
                d = diff[y0:y1, x0:x1]
                n = int((d > threshold).sum())
                if n:
                    touched = True
                    out['pieces'].append(path)
                    out['texels'] += n
                    out['largest'] = max(out['largest'], round(float(d.max()), 5))
            out['textures'] += touched
        out['pieces'] = sorted(set(out['pieces']))
        return out

    def finish(self, out_dir, variant):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = out_dir / f'{variant}.upk'
        if self.redirected:
            name_index, number = self.cache_name
            for index, t in self.redirected.items():
                f = t['fields']
                self.edit(f['cacheNameOffset'], struct.pack('<ii', name_index, number),
                          f'cache name of {f["path"]}: {f["cache"]} -> {self.cache}')
                for k, mip in sorted(t['mips'].items()):
                    m = mip['meta']
                    if mip.get('painted'):
                        payload = compressed_bulk(mip['raw'], bulk_block_size(mip['payload']))
                    else:
                        payload = mip['payload']
                    offset = len(self.cache_data)
                    self.cache_data += payload
                    meta = struct.pack('<4i', m['flags'], m['count'], len(payload), offset)
                    self.edit(m['metaOffset'], meta, f'mip {m["width"]}x{m["height"]} of {f["path"]} -> '
                                                     f'{self.cache}.tfc @{offset} ({len(payload)} bytes)')
        edits = sorted(self.edits.items())
        report = package_edit.write_edited(str(self.p.path), str(dst), edits, force=bool(self.force))
        files = {str(dst): sha256(dst.read_bytes())}
        if self.redirected:
            tfc = out_dir / f'{self.cache}.tfc'
            tfc.write_bytes(bytes(self.cache_data))
            files[str(tfc)] = sha256(bytes(self.cache_data))
        self.check(dst)
        manifest = dict(source=str(self.p.path), sourceSha256=lighting.digest(self.p.path), variant=variant,
                        cache=self.cache if self.redirected else None, outputs=files, writer=report, edits=self.log,
                        **({'otherPiecesChanged': self.others_changed()} if self.imaged else {}),
                        tool=dict(path='tools/bake/lighting_fixture.py', sha256=lighting.digest(__file__)))
        (out_dir / f'{variant}.fixture.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8',
                                                         newline='\n')
        return manifest

    def check(self, dst):
        """Re-read the written map: the redirected textures name the variant cache and decode from it."""
        q = lighting.Package(dst)
        for index, t in self.redirected.items():
            f = lightmap_fields.texture_fields(q, index)
            if f['cache'] != self.cache:
                raise ValueError(f'{f["path"]} does not name {self.cache} after writing')
            for k, mip in t['mips'].items():
                m = f['mips'][k]
                payload = bytes(self.cache_data[m['offset']:m['offset'] + m['bytes']])
                if decompress_payload(payload, m['flags']) != mip['raw']:
                    raise ValueError(f'{f["path"]} mip {k} does not decode to the intended pixels')


def run(src, out_dir, variant, ops, cache=None, tfc=None, fixture=None):
    """`fixture`: a Fixture of `src` and `cache` already opened (relight.py's probe), instead of opening the map
    again."""
    fx = fixture or Fixture(src, cache, tfc)
    for op in ops:
        kind = op['op']
        if kind == 'noop':
            fx.noop(op['component'])
        elif kind == 'redirect':
            index = fx.p.by_name.get(op['texture'])
            if index is None:
                raise ValueError(f'no texture {op["texture"]}')
            fx.redirect(index)
        elif kind == 'scale':
            fx.scale(op['component'], op['slot'], op['factor'])
        elif kind == 'setscale':
            fx.setscale(op['component'], op['slot'], op['value'])
        elif kind == 'paint':
            fx.paint(op['component'], op['slot'], op['rgb'])
        elif kind == 'image':
            with np.load(op['npz']) as data:
                fx.image(op['component'], op['slot'], data[op['key']], data[op['key'] + '_mask'],
                         only_changed=bool(op.get('onlyChanged')), ring=bool(op.get('ring')))
        elif kind == 'gray':
            index = fx.p.by_name.get(op['texture'])
            if index is None:
                raise ValueError(f'no texture {op["texture"]}')
            with np.load(op['npz']) as data:
                fx.gray(index, op['x0'], op['y0'], data[op['key']], data[op['key'] + '_mask'])
        else:
            raise ValueError(f'unknown operation {kind}')
    return fx.finish(out_dir, variant)


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('src', type=Path)
    a.add_argument('out', type=Path)
    a.add_argument('variant')
    a.add_argument('--cache', help='variant texture cache name, <Name>_<n>')
    a.add_argument('--ops', type=Path, help='JSON list of operations')
    a.add_argument('--noop', action='append', default=[], metavar='COMPONENT')
    a.add_argument('--redirect', action='append', default=[], metavar='TEXTURE')
    a.add_argument('--scale', action='append', nargs=3, default=[], metavar=('COMPONENT', 'SLOT', 'FACTOR'))
    a.add_argument('--paint', action='append', nargs=5, default=[], metavar=('COMPONENT', 'SLOT', 'R', 'G', 'B'))
    args = a.parse_args()
    if args.out.resolve() == args.src.resolve().parent:
        a.error('write the fixture outside the source map\'s folder')
    ops = json.loads(args.ops.read_text(encoding='utf-8')) if args.ops else []
    ops += [dict(op='noop', component=c) for c in args.noop]
    ops += [dict(op='redirect', texture=t) for t in args.redirect]
    ops += [dict(op='scale', component=c, slot=int(s), factor=[float(f)] * 3) for c, s, f in args.scale]
    ops += [dict(op='paint', component=c, slot=int(s), rgb=[float(r), float(g), float(b)])
            for c, s, r, g, b in args.paint]
    if not ops:
        a.error('no operations')
    manifest = run(args.src, args.out, args.variant, ops, args.cache)
    print(json.dumps(dict(outputs=manifest['outputs'], writer=manifest['writer']), indent=1))
    for e in manifest['edits']:
        print('-', e['what'])


if __name__ == '__main__':
    main()
