"""A built map whose baked lighting lives inside the map file: no texture cache beside it (LWR map packs; F-140).

The Build bakes the lightmaps and shadow maps it changes into its own texture cache, <Map>_Lighting.tfc: their larger
mips (the 128-texel and larger levels of a 1024 atlas) lie in the cache, the small ones inline in the map, and each
texture names the cache in its TextureFileCacheName. LWR 3's map packs live in a folder under CookedPCConsole, and the
game finds a texture cache only in CookedPCConsole itself (EXP-85), so a pack's maps would need their caches lying
beside the pack's folder.

`inline` writes a copy of the map in which every texture that names that cache holds all its mips inline, as the
game's own URB_StreetOverpass holds its ShadowMapTexture2D_173 (1024 x 1024, every mip inline and uncompressed,
NeverStream True, no cache name):
- each cached mip's payload is read from the cache, its LZO blocks undone (the Build writes literal LZO), and stored
  inline uncompressed: flags 0, its size, its offset the logical position right after its own bulk record;
- the inline mips (and the empty source-art record) keep their bytes, their offsets moved with the data;
- TextureFileCacheName is taken out of the texture's properties and NeverStream True put in, so the game loads every
  mip with the map instead of streaming them from a cache;
- the textures that name the game's shared Lighting.tfc (the lightmaps the Build did not change) are left as they
  are: every install has that cache, in CookedPCConsole.

The textures' new data goes after the package's end (package_grow: nothing that was there moves). The map then needs
no <Map>_Lighting.tfc. A NeverStream texture is resident while the map is loaded: the cache's size in texture memory
for the whole battle, instead of the mips the camera needs (EXP-86 measured what that costs). Export map pack
(tools/viewer/manager.py) writes every packed map this way.

  python -B tools/bake/inline_lighting.py <map.upk> <out.upk> [--cache <name>] [--tfc <cache file>]
      (default cache: <map>_Lighting, read beside the map)
"""
import argparse
import hashlib
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upk'))
sys.path.insert(0, str(ROOT / 'viewer'))
sys.path.insert(0, str(ROOT / 'bake'))
import lighting_records as lighting  # noqa: E402
import lightmap_fields  # noqa: E402
import package_grow  # noqa: E402
from package import Reader  # noqa: E402
import props as legacy_props  # noqa: E402
from texture import decompress_payload  # noqa: E402

SEPARATE = 1            # BULKDATA_StoreInSeparateFile
UNUSED = 32             # BULKDATA_Unused
RECORD = 16             # a bulk record: flags, element count, size on disk, offset in file


class InlineError(ValueError):
    pass


class NotNamed(InlineError):
    """No texture of the map names the cache: there is nothing to put inside."""


def _tags(raw, start, end, names):
    """[(name, kind, tag start, tag end)] of the tagged properties in raw[start:end] (the None terminator excluded),
    and the position of the terminator."""
    try:
        rows, after = legacy_props.read_tags(raw, start, end, names)
    except ValueError as error:
        raise InlineError(str(error)) from None
    # a tag is 24 bytes, and a struct's or an enum's name 8 more, before its value
    return [(name, kind, at - 24 - (8 if kind in ('StructProperty', 'ByteProperty') else 0), at + size)
            for name, kind, _, _, at, size in rows], after - 8


def _bulk(r):
    flags, count, size, offset = r.unpack('4i')
    payload = r.take(size) if not flags & SEPARATE else None
    return dict(flags=flags, count=count, size=size, offset=offset, payload=payload)


def _record(flags, count, payload, at):
    """A bulk record and its inline payload, the payload's offset being `at` + RECORD (absolute, logical)."""
    return struct.pack('<4i', flags, count, len(payload), at + RECORD) + payload


def texture_data(p, index, cache_bytes, base, name_index):
    """The texture export's new data, to be placed at the logical offset `base`: every mip inline, no cache name,
    NeverStream True. `cache_bytes`: the cache file's bytes. `name_index(text)`: a name's index in the package being
    written (added there when new). Returns (data, {moved: cached mips made inline, bytes: their raw size})."""
    e = p.exports[index - 1]
    raw = p.data[e['off']:e['off'] + e['size']]
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    end = p.properties(index)[1] - e['off']          # after the terminator
    tags, terminator = _tags(raw, start, end, p.names)
    if terminator + 8 != end: raise InlineError(f'{p.name(index)}: the properties end where the reader does not say')
    kept = b''.join(raw[a:b] for name, _, a, b in tags if name not in ('TextureFileCacheName', 'NeverStream'))
    true = struct.pack('<ii', name_index('NeverStream'), 0) + struct.pack('<ii', name_index('BoolProperty'), 0) \
        + struct.pack('<ii', 0, 0) + b'\x01'
    out = bytearray(raw[:start] + kept + true + struct.pack('<ii', name_index('None'), 0))
    r = Reader(raw, end, len(raw))
    moved = dict(moved=0, bytes=0)

    def put(b):
        at = base + len(out)
        if b['flags'] & SEPARATE:
            if b['flags'] & UNUSED or b['size'] == 0:
                out.extend(struct.pack('<4i', b['flags'] & ~SEPARATE, 0, 0, at + RECORD))
                return
            if b['offset'] < 0 or b['offset'] + b['size'] > len(cache_bytes):
                raise InlineError(f'{p.name(index)}: a mip lies outside the cache')
            payload = decompress_payload(cache_bytes[b['offset']:b['offset'] + b['size']], b['flags'])
            if b['count'] != len(payload): raise InlineError(f'{p.name(index)}: a cached mip unpacks to {len(payload)} bytes, not {b["count"]}')
            moved['moved'] += 1
            moved['bytes'] += len(payload)
            out.extend(_record(0, len(payload), payload, at))
        else:
            payload = decompress_payload(b['payload'], b['flags'])
            out.extend(_record(0, len(payload), payload, at))

    put(_bulk(r))                                      # the source art: empty
    count = r.i32()
    out += struct.pack('<i', count)
    for _ in range(count):
        put(_bulk(r))
        out += r.take(8)                               # its width and height
    out += raw[r.pos:]                                 # the cache GUID and anything after it, as they were
    return bytes(out), moved


def inline(src, dst, cache=None, tfc=None, echo=print):
    """dst: the map `src` with every texture that names the cache `cache` (default <map>_Lighting) holding its mips
    inline (see the module notes). Returns {textures, mips, bytes, cache, sha256}."""
    src, dst = Path(src), Path(dst)
    cache = cache or f'{src.stem}_Lighting'
    tfc = Path(tfc) if tfc else src.parent / f'{cache}.tfc'
    p = lighting.Package(src)
    if p.header['lic'] != 64: raise InlineError('EW licensee-64 maps only')
    chosen = []
    for k in range(1, len(p.exports) + 1):
        if p.cls(k) not in lightmap_fields.TEXTURE_CLASSES: continue
        if (p.effective(k, 'TextureFileCacheName') or '').lower() == cache.lower(): chosen.append(k)
    if not chosen:
        raise NotNamed(f'no texture of {src.name} names the cache {cache}')
    cache_bytes = tfc.read_bytes()
    g = package_grow.Grower(str(src))
    total = dict(textures=0, mips=0, bytes=0)
    for k in chosen:
        data, moved = texture_data(p, k, cache_bytes, g.next_offset(), g.name)
        g.relocate(k, data)
        total['textures'] += 1
        total['mips'] += moved['moved']
        total['bytes'] += moved['bytes']
    dst.parent.mkdir(parents=True, exist_ok=True)
    g.write(str(dst))
    try: check(dst, [p.name(k) for k in chosen], p, cache_bytes)
    except Exception:
        dst.unlink()                                   # no copy that failed its check is left behind
        raise
    total.update(cache=cache, sha256=hashlib.sha256(dst.read_bytes()).hexdigest())
    echo(f'{dst.name}: {total["textures"]} textures, {total["mips"]} mips ({total["bytes"]:,} bytes) moved inside from {tfc.name}')
    return total


def mips_of(p, index, cache_bytes=None):
    """The raw bytes of each mip of a texture: inline ones from the package, cached ones from `cache_bytes`."""
    r = p.native(index)
    lighting.bulk_meta(r)
    out = []
    for _ in range(r.count()):
        at = r.pos
        flags, count, size, offset = struct.unpack_from('<4i', p.data, at)
        meta = lighting.bulk_meta(r)
        r.unpack('2i')
        if meta['flags'] & UNUSED or not size: out.append(b''); continue
        if meta['inline']:
            if offset != at + RECORD: raise InlineError(f'{p.name(index)}: an inline mip\'s offset is not its own position')
            out.append(decompress_payload(p.data[at + RECORD:at + RECORD + size], flags))
        elif cache_bytes is None:
            raise InlineError(f'{p.name(index)}: a mip still lies in a cache')
        else:
            out.append(decompress_payload(cache_bytes[offset:offset + size], flags))
    return out


def check(dst, chosen, source, cache_bytes):
    """The written map read back: each chosen texture (`chosen`: names) without a cache name, NeverStream True, every
    mip inline at its own offset, and every mip's bytes those of the source's (`source`: the map read, `cache_bytes`:
    its cache's bytes); nothing else of the textures changed."""
    q = lighting.Package(dst)
    for name in chosen:
        k, j = q.by_name[name], source.by_name[name]
        if q.effective(k, 'TextureFileCacheName') is not None: raise InlineError(f'{name}: still names a cache')
        if q.effective(k, 'NeverStream') is not True: raise InlineError(f'{name}: not NeverStream')
        if mips_of(q, k) != mips_of(source, j, cache_bytes): raise InlineError(f'{name}: its mips differ from the source\'s')
        for prop in ('SizeX', 'SizeY', 'Format', 'MipTailBaseIdx'):
            if q.effective(k, prop) != source.effective(j, prop): raise InlineError(f'{name}: {prop} changed')
        lightmap_fields.texture_fields(q, k)          # the audit reader's own checks
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('map', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--cache', help='the cache the textures name (default <map>_Lighting)')
    ap.add_argument('--tfc', type=Path, help='the cache file (default <cache>.tfc beside the map)')
    args = ap.parse_args()
    try: inline(args.map, args.out, args.cache, args.tfc)
    except (InlineError, OSError, ValueError) as error:
        print(f'inline_lighting: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
