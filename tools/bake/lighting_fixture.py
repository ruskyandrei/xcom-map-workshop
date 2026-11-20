"""Build lighting test maps from fixed-size edits (baker design, stage 1: C0, C1, C2; EXP-17).

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

The writer itself (Fixture, the redirect, setscale, image and gray operations, the cache name's rules) is
lightmap_writer.py, which every baked Build uses; this module adds the experiment's noop, scale and paint and the
command line, and re-exports the writer's names for the experiment tools (grow_fixture.py, deploy_fixture.py).

A texture whose mips are all inside the map package (the small lightmaps, up to 64 texels wide, uncompressed) is
written there in place, at the same size; only textures with mips in Lighting.tfc are redirected to the variant
cache.

The variant cache's name is stored in each redirected texture as an FName (name index, number), so the edit keeps its
size, and its text must already be in the map's name table (cache_fname): the editor's Build names it
`<Map>_Lighting`, which a growing write adds to the table first (native_copy.py; the Build's named copy for a relight
alone); a name ending `_<n>` is `<Name>` numbered n + 1 (`Lighting_7000`, the Build's until 16 November 2026, needs
only `Lighting`, which every map has).

  python -B tools/bake/lighting_fixture.py <map.upk> <out dir> <variant> [--cache URB_BarFix_Lighting | Lighting_7000]
      [--noop COMPONENT] [--redirect TEXTURE] [--scale COMPONENT SLOT FACTOR] [--paint COMPONENT SLOT R G B]
"""
import argparse
import json
import math
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lightmap_writer  # noqa: E402
from lightmap_writer import (BULK_TAG, CACHE_FLAG, LZO_FLAG, apply, bulk_block_size, cache_fname,  # noqa: E402,F401
                             cache_table_name, compressed_bulk, parse_cache_name, rect_bounds, sha256)


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


class Fixture(lightmap_writer.Fixture):
    """The writer with the experiment's operations: a forced no-op re-encode (C0), a scaled slot and painted
    rectangles (C2)."""

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
                    self.unedit(m['payloadOffset'])
                    self.log = [e for e in self.log if e.get('offset') != m['payloadOffset']]
                    self.edit(m['payloadOffset'], new, f'paint inline mip {m["width"]}x{m["height"]} of '
                                                       f'{t["fields"]["path"]}')
            else:
                n = 0
            counts.append(dict(mip=f'{m["width"]}x{m["height"]}', blocks=n))
        return counts


def run(src, out_dir, variant, ops, cache=None, tfc=None, fixture=None):
    """lightmap_writer.run with the experiment's operations too: noop, scale and paint."""
    fx = fixture or Fixture(src, cache, tfc)
    for op in ops:
        kind = op['op']
        if kind == 'noop':
            fx.noop(op['component'])
        elif kind == 'scale':
            fx.scale(op['component'], op['slot'], op['factor'])
        elif kind == 'paint':
            fx.paint(op['component'], op['slot'], op['rgb'])
        else:
            apply(fx, op)
    return fx.finish(out_dir, variant)


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('src', type=Path)
    a.add_argument('out', type=Path)
    a.add_argument('variant')
    a.add_argument('--cache', help='variant texture cache name: one the map\'s name table holds, or <Name>_<n> with <Name> in it')
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
