"""Gate C6 (baker design, section 5; plan step L4): new exports in a map, made by the growing writer.

One receiver's lightmap textures (its colour and directional textures, slots 0 and 1) are cloned as new exports, and
the receiver is pointed at the clones (tools/upk/package_grow.py: the clones and a new export table appended). Then,
by the fixed-size tools (lighting_fixture.py), the clone's colour texture is painted inside the receiver's rectangle
(green by default) and the original colour texture is painted there too (blue): no component reads that rectangle
of the original any more. In the game, a green receiver means it reads the new exports; blue, that it still reads
the originals; anything else (black, a crash), that the grown package isn't taken.

Writes <out>/grown/<map>.upk (the grown map, before painting), <out>/<variant>.upk with <out>/<cache>.tfc and their
fixture manifest (<out>/<variant>.fixture.json, with a `grown` section), which deploy_fixture.py deploys.

  python -B tools/bake/grow_fixture.py <map.upk> <out dir> <variant> --component PATH [--cache Lighting_7005]
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
import audit_lighting as lighting  # noqa: E402
import lighting_fixture  # noqa: E402
import lightmap_fields  # noqa: E402
import package_grow  # noqa: E402

GREEN, BLUE = (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


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


def grow(src, dst, component):
    """The grown map: `component`'s slot-0 and slot-1 textures cloned, and the component pointed at the clones.
    Returns dict(clones: {slot: (original index, clone index, clone name)}, writer report)."""
    p = lighting.Package(src)
    g = package_grow.Grower(str(src))
    lm = lightmap_fields.component_fields(p, p.by_name[component])['lods'][0]['lightmap']
    if lm['type'] != 2:
        raise ValueError(f'{component} has no texture lightmap')
    clones = {}
    for slot in (0, 1):
        s = lm['slots'][slot]
        new = clone_texture(g, p, s['index'])
        g.edit(s['textureOffset'], struct.pack('<i', new))
        e = g.entries[new - 1]
        clones[slot] = (s['index'], new, f'{g.names[e.name_index]}_{e.name_number - 1}')
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    report = g.write(str(dst))
    return dict(clones=clones, writer=report, coordinateBias=lm['coordinateBias'],
                coordinateScale=lm['coordinateScale'])


def build(src, out, variant, component, cache, clone_rgb=GREEN, original_rgb=BLUE):
    src, out = Path(src), Path(out)
    grown = out / 'grown' / src.name
    info = grow(src, grown, component)
    # the readers find the original's texture caches through tfc-folder.txt beside the grown map (nothing copied)
    lighting.link_caches(grown.parent, src.parent)
    fx = lighting_fixture.Fixture(grown, cache, tfc=src.parent / 'Lighting.tfc')
    fx.paint(component, 0, list(clone_rgb))
    original = info['clones'][0][0]
    counts = fx.paint_rect(original, info['coordinateBias'], info['coordinateScale'], [list(original_rgb)])
    fx.log.append(dict(what=f'paint the original {fx.p.name(original)} in the same rectangle rgb {list(original_rgb)}',
                       blocksPerMip=counts))
    manifest = fx.finish(out, variant)
    manifest['grown'] = dict(source=str(src), map=str(grown), component=component,
                             clones={str(k): dict(original=fx.p.name(o), clone=name, export=n)
                                     for k, (o, n, name) in info['clones'].items()},
                             writer=info['writer'], cloneRgb=list(clone_rgb), originalRgb=list(original_rgb))
    (out / f'{variant}.fixture.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8',
                                                newline='\n')
    return manifest


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('src', type=Path)
    a.add_argument('out', type=Path)
    a.add_argument('variant')
    a.add_argument('--component', required=True)
    a.add_argument('--cache', default='Lighting_7005')
    args = a.parse_args()
    m = build(args.src, args.out, args.variant, args.component, args.cache)
    print(json.dumps(dict(outputs=m['outputs'], grown=m['grown']), indent=1))


if __name__ == '__main__':
    main()
