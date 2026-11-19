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

NAME = 'MapPicture'
WIDTH, HEIGHT = 512, 256
FORMAT = 'DXT1'
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
    r = viewer_package.Reader(p.data, start, e['off'] + e['size'])
    tags = []
    while True:
        name = p.fname(r)
        if name == 'None':
            break
        kind = p.fname(r)
        size, _slot = r.unpack('ii')
        subtype = None
        if kind == 'BoolProperty':
            value = bool(r.take(1)[0])
        else:
            if kind in ('StructProperty', 'ByteProperty'):
                subtype = p.fname(r)
            value = p.decode(kind, subtype, r.take(size))
        tags.append([name, kind, subtype, size, value])

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
