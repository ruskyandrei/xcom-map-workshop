"""What a map's lightmaps and shadow maps weigh, and what they would at the size of what their pieces read (smaller
built maps plan, stage S0; F-151).

For each lighting texture of a map (LightMapTexture2D, DXT1; ShadowMapTexture2D, G8): its size, the bytes its mips
hold inside the map and in a texture cache, the records that read it (a mesh component's lightmap at each LOD, a
ShadowMap2D) and the box they read (lightmap_textures.crop_box: their rectangles with the writer's ring, on whole
blocks, a power of two each way), and what a texture of that box would hold with its mips. A built map whose copies
clone whole atlases (editor 0.6.0 and earlier) shows it at once: hundreds of 1,024-texel textures inside it, each read in
a small rectangle.

`inside` is the quick count the Build prints after it puts the lightmaps inside the map: the textures and the bytes
held inside, with no reading of who uses them.

  python -B tools/bake/lighting_size.py <map.upk> [--list] [--json <out.json>]
"""
import argparse
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import lighting_records as lighting  # noqa: E402
import lightmap_fields  # noqa: E402
import lightmap_textures  # noqa: E402
from lightmap_texels import rect_bounds  # noqa: E402


def texture(p, k):
    """A texture's format, cache name and mips (each bulk_meta's dict with its width and height), read from the
    package alone: no texture cache need lie beside it (a package's folder has none; lightmap_fields.texture_fields
    checks every cached mip against its cache)."""
    r = p.native(k)
    lighting.bulk_meta(r)                   # the source art
    mips = []
    for _ in range(r.count()):
        m = lighting.bulk_meta(r)
        m['width'], m['height'] = r.unpack('2i')
        mips.append(m)
    return dict(format=p.effective(k, 'Format'), cache=p.effective(k, 'TextureFileCacheName'), mips=mips)


def _held(t):
    """(bytes inside the map, bytes in a texture cache) of a texture's live mips (texture's dict)."""
    inside = cached = 0
    for m in t['mips']:
        if not m['bytes'] or m['flags'] & 32:
            continue
        if m['inline']:
            inside += m['bytes']
        else:
            cached += m['bytes']
    return inside, cached


def inside(path):
    """The lighting textures of the map at `path` and what they hold inside it: dict(textures (those whose top mip
    is inside the map), bytes (every mip inside the map: the small mips of the others too), cached (bytes in texture
    caches), whole (textures of 1,024 by 1,024 inside))."""
    p = lighting.Package(Path(path))
    out = dict(textures=0, bytes=0, cached=0, whole=0)
    for k in range(1, len(p.exports) + 1):
        if p.cls(k) not in lightmap_fields.TEXTURE_CLASSES:
            continue
        t = texture(p, k)
        held, cached = _held(t)
        top = t['mips'][0]
        out['bytes'] += held
        out['cached'] += cached
        if top['inline']:
            out['textures'] += 1
            out['whole'] += (top['width'], top['height']) == (1024, 1024)
    return out


def readers(p):
    """{texture export: [(reader's path, rectangle (x0, y0, x1, y1))]}: every mesh component's texture lightmap at
    each LOD and every ShadowMap2D of the map, with the rectangle each reads."""
    out, sizes = {}, {}

    def size(t):
        if t not in sizes:
            top = texture(p, t)['mips'][0]
            sizes[t] = (top['width'], top['height'])
        return sizes[t]

    for i in range(1, len(p.exports) + 1):
        cls = p.cls(i)
        if cls in lightmap_fields.COMPONENT_CLASSES:
            try:
                lods = lightmap_fields.component_fields(p, i)['lods']
            except Exception:       # a component the reader doesn't take: it reads no texture we can name
                continue
            for n, lod in enumerate(lods):
                lm = lod['lightmap']
                if lm['type'] != 2:
                    continue
                for s in lm['slots']:
                    if s['index'] > 0 and p.cls(s['index']) in lightmap_fields.TEXTURE_CLASSES:
                        out.setdefault(s['index'], []).append(('%s LOD%d' % (p.name(i), n),
                                                               rect_bounds(lm, *size(s['index']))))
        elif cls == 'ShadowMap2D':
            t = p.own(i, 'Texture', 0)
            scale, bias = p.own(i, 'CoordinateScale'), p.own(i, 'CoordinateBias')
            if t <= 0 or p.cls(t) not in lightmap_fields.TEXTURE_CLASSES:
                continue
            if isinstance(scale, (bytes, bytearray)) and isinstance(bias, (bytes, bytearray)):
                rec = dict(coordinateScale=struct.unpack('<2f', scale), coordinateBias=struct.unpack('<2f', bias))
                out.setdefault(t, []).append((p.name(i), rect_bounds(rec, *size(t))))
            else:
                out.setdefault(t, []).append((p.name(i), None))
    return out


def boxed_bytes(fmt, box, width, height):
    """The bytes of a texture of the box `box` (crop_box's, or None for the whole) with its mips."""
    w, h = (box[2], box[3]) if box else (width, height)
    return sum(lightmap_textures.mip_bytes(fmt, sw, sh) for sw, sh, _, _ in lightmap_textures.mip_sizes(fmt, w, h))


def survey(path):
    """Every lighting texture of the map at `path`: dict(textures [dict(name, cls, size, inside, cached, cache,
    readers, box, boxBytes)], summary dict(textures, inside (bytes inside the map), cached, insideTextures (those
    whose top mip is inside), whole (of them, 1,024 by 1,024), unread, boxBytes (they at their box's size), boxable
    (how many of them a box makes smaller)))."""
    p = lighting.Package(Path(path))
    who = readers(p)
    rows, s = [], dict(textures=0, inside=0, cached=0, insideTextures=0, whole=0, unread=0, boxBytes=0, boxable=0)
    for k in range(1, len(p.exports) + 1):
        if p.cls(k) not in lightmap_fields.TEXTURE_CLASSES:
            continue
        t = texture(p, k)
        held, cached = _held(t)
        top = t['mips'][0]
        fmt = t['format']
        rects = [r for _, r in who.get(k, [])]
        box = None if None in rects else lightmap_textures.crop_box(rects, top['width'], top['height'], fmt)
        row = dict(name=p.name(k), cls=p.cls(k), size=[top['width'], top['height']], inside=held, cached=cached,
                   cache=t['cache'], readers=[n for n, _ in who.get(k, [])], box=list(box) if box else None,
                   boxBytes=boxed_bytes(fmt, box, top['width'], top['height']) if rects else 0)
        rows.append(row)
        s['textures'] += 1
        s['inside'] += held
        s['cached'] += cached
        if top['inline']:
            s['insideTextures'] += 1
            s['whole'] += (top['width'], top['height']) == (1024, 1024)
            s['boxBytes'] += row['boxBytes']
            s['boxable'] += bool(box)
        s['unread'] += not rects
    return dict(map=Path(path).name, textures=rows, summary=s)


def mb(n):
    return '%.1f MB' % (n / 1e6)


def describe(s):
    """A line of survey's summary."""
    return ('lightmaps inside the map: %s in %d textures (%d of them whole 1,024-texel atlases); at the size of what '
            'their pieces read: %s; in texture caches: %s; read by nothing: %d'
            % (mb(s['inside']), s['insideTextures'], s['whole'], mb(s['boxBytes']), mb(s['cached']), s['unread']))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('map', type=Path)
    ap.add_argument('--list', action='store_true', help='a line for each texture held inside the map, largest first')
    ap.add_argument('--json', type=Path, help='write the whole survey here')
    args = ap.parse_args()
    got = survey(args.map)
    if args.list:
        for r in sorted((r for r in got['textures'] if r['inside']), key=lambda r: -r['inside']):
            print('%10s  %-18s %4dx%-4d  read by %d%s  %s' % (
                '{:,}'.format(r['inside']), r['cls'], r['size'][0], r['size'][1], len(r['readers']),
                ', box %dx%d: %s' % (r['box'][2], r['box'][3], '{:,}'.format(r['boxBytes'])) if r['box'] else '',
                r['name'].split('.')[-1]))
    print('%s: %s' % (got['map'], describe(got['summary'])))
    if args.json:
        args.json.write_text(json.dumps(got, indent=1) + '\n', encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
