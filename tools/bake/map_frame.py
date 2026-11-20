"""A map's own picture: a top-level Texture2D named MapPicture in the map package (LWR map packs plan, 4.1 and 4.4).

Long War Rebalance 3.00.00 beta 15 shows a map's own picture on its mission screens when the map package holds a
top-level `Texture2D` named `MapPicture`. Plain Enemy Within and LWR 2.x look for no such object: there it is one more
texture nothing refers to. (`tools/upk/map_picture.py` is an older tool of another kind: it draws a plan of a patch.)

The picture is made the way the game's own map pictures are. Read on 19 November 2026 from the install's
`UILibrary_MapImages_SF.upk` (98 pictures), `UILibrary_MapImages_DLC1_SF.upk` (3), `_DLC2_SF.upk` (3) and
`_HQAssault_SF.upk` (1), licensee 64. The 99 of the first and the last are alike field by field, and the six of the
two DLC packages differ from them in one property more (`describe` reads one; tests/test_map_frame.py compares):

- export entry: class the import `Engine.Texture2D` (class package Core, class Class, under the import of the
  package Engine), no super, no archetype, object flags 0x000F000400000000 (RF_Public, RF_Standalone and the three
  load flags). The game's sit under a forced-export package (`UILibrary_MapImages`) and so carry the export flag
  EF_ForcedExport, with no net object counts, a zero GUID and zero package flags; ours is top-level in the map
  (outer 0) with no export flags, as the maps' own top-level lightmap textures have none;
- data: the net index (4 bytes: the pictures of a package count 0, 1, 2 ...; ours takes the map's next net object),
  then nine tagged properties in this order, 278 bytes with their terminator:
    SizeX            IntProperty   512
    SizeY            IntProperty   256
    OriginalSizeX    IntProperty   512
    OriginalSizeY    IntProperty   256
    Format           ByteProperty  EPixelFormat, PF_DXT1 (saved as a name, 8 bytes)
    MipTailBaseIdx   IntProperty   9
    SRGB             BoolProperty  False
    NeverStream      BoolProperty  True
    LODGroup         ByteProperty  TextureGroup, TEXTUREGROUP_UI (a name, 8 bytes)
  MipTailBaseIdx is 9 although one mip is saved (the cooker's count for 512 x 256 before it dropped the smaller
  mips); the plan's list had 0 there. The game's value is followed. The six DLC pictures save CompressionNoAlpha
  (BoolProperty, True) between SRGB and NeverStream, 25 bytes more: a setting of the editor's texture compressor,
  which a cooked DXT1 picture no longer needs, and the 99 do without it, as ours does;
- native data, 65,608 bytes: an empty source-art bulk record (flags 0, count 0, size 0, offset the position right
  after the record); the mip count, 1; the mip's bulk record (flags 0: in the package, not compressed; count and
  size 65,536; offset the position right after the record); the pixels (DXT1, 8,192 blocks of 4 x 4, rows top to
  bottom); SizeX 512 and SizeY 256; a 16-byte texture cache GUID, different in each picture; then int32 0, 1, 0 (no
  cached PVRTC mips, the largest cached Flash mip, no cached ATITC mips: tools/upk/native_fields.py
  `_texture2d_body`).

An export is 65,890 bytes (a DLC picture's 65,915).
"""
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE))
if str(HERE.parent / 'viewer') not in sys.path:
    sys.path.append(str(HERE.parent / 'viewer'))       # package.py, the reader

NAME = 'MapPicture'
WIDTH, HEIGHT = 512, 256
PIXEL_BYTES = WIDTH * HEIGHT // 2          # DXT1: 8 bytes a block of 16 texels
EXPORT_BYTES = 65890
# the game's own map-image packages (the install's CookedPCConsole, <name>_SF.upk), each picture under a package of
# the name
LIBRARIES = ('UILibrary_MapImages', 'UILibrary_MapImages_DLC1', 'UILibrary_MapImages_DLC2',
             'UILibrary_MapImages_HQAssault')

# Version 1: the game's map pictures as read above. Imports and properties are written as light_factory's and
# cover_blocks' recipes are, with one more kind here: 'int' (an IntProperty).
RECIPE = {
    'kind': 'map picture',
    'imports': [
        ['Engine', 'Core', 'Package'],
        ['Engine.Texture2D', 'Core', 'Class'],
    ],
    'class': 'Engine.Texture2D', 'name': NAME,
    'flags': 0x000F000400000000,
    'properties': [
        ['SizeX', 'int', WIDTH],
        ['SizeY', 'int', HEIGHT],
        ['OriginalSizeX', 'int', WIDTH],
        ['OriginalSizeY', 'int', HEIGHT],
        ['Format', 'enum', ['EPixelFormat', 'PF_DXT1']],
        ['MipTailBaseIdx', 'int', 9],
        ['SRGB', 'bool', False],
        ['NeverStream', 'bool', True],
        ['LODGroup', 'enum', ['TextureGroup', 'TEXTUREGROUP_UI']],
    ],
    'tail': [0, 1, 0],
}


def describe(p, index):
    """What export `index` of the package `p` (tools/viewer/package.py Package), a 2D texture, is made of: its object
    flags, its tagged properties in their order ([name, property type, enum or struct name, size, value]) and its
    native data read field by field (sourceArt and each mip as dict(flags, count, size, offset, after: the position
    right after the record, both from the package's start), pixels (the first mip's bytes in the package), size,
    guid, tail (the int32s after the GUID)); netIndex and bytes (the export's size)."""
    import package as viewer_package
    import props as legacy_props
    e = p.exports[index - 1]
    start = legacy_props.props_start(p.data, e, p.names)
    rows, after = legacy_props.read_tags(p.data, start, e['off'] + e['size'], p.names)
    tags = []
    for name, kind, subtype, _slot, at, size in rows:
        if kind == 'BoolProperty':
            # the size its tag saves (0: a bool's value is its one byte)
            tags.append([name, kind, None, struct.unpack_from('<i', p.data, at - 8)[0], bool(p.data[at])])
        else:
            tags.append([name, kind, subtype, size, p.decode(kind, subtype, p.data[at:at + size])])
    r = viewer_package.Reader(p.data, after, e['off'] + e['size'])

    def record():
        flags, count, size, offset = r.unpack('4i')
        return dict(flags=flags, count=count, size=size, offset=offset, after=r.pos)
    source = record()
    mips, pixels = [], None
    for _ in range(r.count()):
        mip = record()
        if not mip['flags'] & 1:
            data = r.take(mip['size'])
            pixels = data if pixels is None else pixels
        mip['width'], mip['height'] = r.unpack('2i')
        mips.append(mip)
    guid = bytes(r.take(16))
    rest = e['off'] + e['size'] - r.pos
    if rest % 4:
        raise ValueError('%s: %d bytes after its texture cache GUID' % (p.name(index), rest))
    tail = list(r.unpack('%di' % (rest // 4)))
    return dict(flags=e['flags'], netIndex=struct.unpack_from('<i', p.data, e['off'])[0], bytes=e['size'],
                properties=tags, propertyBytes=mips and source['after'] - 16 - start, sourceArt=source, mips=mips,
                pixels=bytes(pixels) if pixels is not None else None, guid=guid, tail=tail)


# ---------------------------------------------------------------- pixels
def encode(image):
    """The DXT1 pixels (PIXEL_BYTES) of a picture: a Pillow image of WIDTH x HEIGHT; its alpha, if any, is dropped."""
    import numpy as np
    import dxt1
    if image.size != (WIDTH, HEIGHT):
        raise ValueError('a map picture is %d x %d, not %d x %d' % ((WIDTH, HEIGHT) + tuple(image.size)))
    rgb = np.asarray(image.convert('RGB'), np.float64) / 255.0
    pixels = dxt1.encode_blocks(dxt1.image_blocks(rgb).reshape(-1, 16, 3))
    if len(pixels) != PIXEL_BYTES:
        raise ValueError('the encoder gave %d bytes' % len(pixels))
    return pixels


def decode(pixels):
    """The picture the game shows for these DXT1 pixels, a Pillow RGB image."""
    import numpy as np
    from PIL import Image
    import dxt1
    if len(pixels) != PIXEL_BYTES:
        raise ValueError('a map picture has %d bytes of pixels, not %d' % (PIXEL_BYTES, len(pixels)))
    rgb = dxt1.decode_image(pixels, WIDTH, HEIGHT)
    return Image.fromarray(np.clip(np.rint(rgb * 255.0), 0, 255).astype(np.uint8), 'RGB')


def encode_file(path):
    """The DXT1 pixels of the picture file `path` (a WIDTH x HEIGHT image Pillow opens)."""
    from PIL import Image
    with Image.open(path) as image:
        return encode(image)


def cache_guid(pixels):
    """The picture's texture cache GUID: from its pixels, so the same picture builds the same bytes."""
    import hashlib
    return hashlib.sha256(b'XComMapEd MapPicture|' + bytes(pixels)).digest()[:16]


# ---------------------------------------------------------------- the export
def _property(g, name, kind, value):
    """One tagged property with the destination's names: 'int' (an IntProperty), 'enum' ([enum, value]: a
    ByteProperty saving a name) and 'bool'."""
    def tag(property_type, size):
        return struct.pack('<iiiiii', g.name(name), 0, g.name(property_type), 0, size, 0)
    if kind == 'int':
        return tag('IntProperty', 4) + struct.pack('<i', value)
    if kind == 'enum':
        return tag('ByteProperty', 8) + struct.pack('<ii', g.name(value[0]), 0) + struct.pack('<ii', g.name(value[1]), 0)
    if kind == 'bool':
        return tag('BoolProperty', 0) + bytes([1 if value else 0])
    raise ValueError(f'unknown property kind {kind!r}')


def picture_data(g, pixels, net, at):
    """A picture export's data, for a place at the logical offset `at` (its two bulk records save their own
    positions): the net index, the recipe's properties, the native data."""
    pixels = bytes(pixels)
    if len(pixels) != PIXEL_BYTES:
        raise ValueError('a map picture has %d bytes of pixels, not %d' % (PIXEL_BYTES, len(pixels)))
    out = bytearray(struct.pack('<i', net))
    for name, kind, value in RECIPE['properties']:
        out += _property(g, name, kind, value)
    out += struct.pack('<ii', g.name('None'), 0)
    out += struct.pack('<iiii', 0, 0, 0, at + len(out) + 16)                       # the source art: none
    out += struct.pack('<i', 1)
    out += struct.pack('<iiii', 0, PIXEL_BYTES, PIXEL_BYTES, at + len(out) + 16)   # the one mip, in the package
    out += pixels + struct.pack('<ii', WIDTH, HEIGHT)
    out += cache_guid(pixels) + struct.pack('<%di' % len(RECIPE['tail']), *RECIPE['tail'])
    return bytes(out)


def find(g):
    """The export index of the package's own picture in the package being grown (`g`): a top-level Texture2D named
    NAME, or None."""
    import light_factory
    for index, e in enumerate(g.entries, 1):
        if e.outer == 0 and g.name_of(e.name_index, e.name_number) == NAME \
                and light_factory.class_of(g, e.cls) == 'Texture2D':
            return index
    return None


def add_picture(g, pixels):
    """The picture made in the map being grown (`g`, a package_grow.Grower): a new top-level export, with the names
    and the `Engine.Texture2D` class import the map lacks; a map that has a picture already (a base map with its own)
    gets its export's data anew, at the end, under the net index it had. Returns (export index, 'added' or
    'replaced')."""
    import cover_blocks
    index = find(g)
    if index is not None:
        net = struct.unpack_from('<i', g.export_data(index), 0)[0]
        g.relocate(index, picture_data(g, pixels, net, g.next_offset()))
        return index, 'replaced'
    found, _made = cover_blocks.recipe_imports(g, RECIPE)
    cls = found[RECIPE['class']]
    if cls >= 0:
        raise ValueError('the map holds Engine as a package of its own; no Texture2D class to import')
    net = g.next_net_index(0)
    data = picture_data(g, pixels, net, g.next_offset())
    return g.new_export(cls, 0, NAME, data, flags=RECIPE['flags'], number=0), 'added'


# ---------------------------------------------------------------- whole files
def locate(p):
    """The map's own picture in the package `p` (tools/viewer/package.py Package): None, or dict(export, swap: the
    logical offsets of its pixels and of its cache GUID when it is laid out as the recipe's (one WIDTH x HEIGHT DXT1
    mip in the package), else None, pixels: that mip's bytes or None)."""
    index = next((i for i, e in enumerate(p.exports, 1)
                  if e['outer'] == 0 and p.name(i) == NAME and p.cls(i) == 'Texture2D'), None)
    if index is None:
        return None
    try:
        d = describe(p, index)
    except (ValueError, struct.error):      # a picture laid out another way: replaced whole, never read as ours
        return dict(export=index, swap=None, pixels=None)
    mips = d['mips']
    ours = (len(mips) == 1 and (mips[0]['flags'], mips[0]['size']) == (0, PIXEL_BYTES)
            and (mips[0]['width'], mips[0]['height']) == (WIDTH, HEIGHT)
            and ['Format', 'ByteProperty', 'EPixelFormat', 8, 'PF_DXT1'] in d['properties'])
    if not ours:
        return dict(export=index, swap=None, pixels=None)
    at = mips[0]['after']
    return dict(export=index, swap=(at, at + PIXEL_BYTES + 8), pixels=d['pixels'])


def write_picture(src, dst, pixels):
    """`dst`: the map package `src` with the picture `pixels` (DXT1, encode) as its own. A map that has one laid out
    as ours gets the pixels and the cache GUID written over the old, every offset kept (package_edit.write_edited); any
    other map is grown (add_picture). Returns dict(export, how: 'swapped', 'added' or 'replaced')."""
    import package as viewer_package
    import package_edit
    import package_grow
    pixels = bytes(pixels)
    if len(pixels) != PIXEL_BYTES:
        raise ValueError('a map picture has %d bytes of pixels, not %d' % (PIXEL_BYTES, len(pixels)))
    found = locate(viewer_package.Package(src))
    if found and found['swap']:
        at, guid_at = found['swap']
        package_edit.write_edited(str(src), str(dst), [(at, pixels), (guid_at, cache_guid(pixels))])
        return dict(export=found['export'], how='swapped')
    g = package_grow.Grower(str(src))
    index, how = add_picture(g, pixels)
    g.write(str(dst))
    return dict(export=index, how=how)
