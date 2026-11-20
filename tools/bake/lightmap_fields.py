"""Logical offsets of the fixed-size lighting fields in a v845 EW map (baker design, stage 1).

For one placed static/fractured mesh component: each LOD's lightmap texture references, slot scales and atlas
coordinate scale/bias. For one lightmap/shadow-map texture: its cache name (an FName: name index plus number), each
mip's bulk record (flags, element count, size on disk, offset in file) and its dimensions.

Offsets are into the package's uncompressed (logical) image, as package_edit.write_edited takes them. A component's
records and their places are those of the one reader of them (tools/upk/native_fields.py mesh_lods); a texture's
values are checked against lighting_records' reader, so a layout mistake fails instead of producing a wrong offset.
Read-only.

  python -B tools/bake/lightmap_fields.py <map.upk> <component or texture path> [...]
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'upk'))
sys.path.insert(0, str(ROOT / 'viewer'))
import lighting_records as lighting  # noqa: E402
from package import LEADING_SHADOW_MAP, FormatError  # noqa: E402
import props as legacy_props  # noqa: E402

COMPONENT_CLASSES = ('StaticMeshComponent', 'FracturedStaticMeshComponent')
TEXTURE_CLASSES = ('LightMapTexture2D', 'ShadowMapTexture2D')


def property_offsets(p, index):
    """{(name, array index): (value offset, size, kind)} for an export's own tagged properties."""
    e = p.exports[index - 1]
    if p.cls(index) in LEADING_SHADOW_MAP:
        raise FormatError('Dominant-light components are not handled here')
    start = legacy_props.props_start(p.data, e, p.names)
    try:
        rows, after = legacy_props.read_tags(p.data, start, e['off'] + e['size'], p.names)
    except ValueError as error:
        raise FormatError(str(error)) from None
    if after != p.properties(index)[1]:
        raise FormatError('Property scan disagrees with the package reader')
    return {(name, slot): (at, size, kind) for name, kind, _, slot, at, size in rows}


def _lightmap(lm, p):
    """lightmap_fields' form of native_fields.lightmap_record's record: its places, the number of its lights."""
    out = dict(offset=lm['offset'], type=lm['type'])
    if lm['type'] == 1:
        out.update(lightGuidsOffset=lm['lightGuidsOffset'], ownerOffset=lm['ownerOffset'], owner=lm['owner'],
                   bulkOffsets=[lm['directionalSamples']['at'], lm['simpleSamples']['at']],
                   scaleVectorsOffset=lm['scaleVectorsOffset'])
    elif lm['type'] == 2:
        out.update(lightGuidsOffset=lm['lightGuidsOffset'],
                   slots=[dict(textureOffset=s['textureOffset'], index=s['index'], texture=p.name(s['index']),
                               scaleOffset=s['scaleOffset'], scale=s['scale']) for s in lm['slots']],
                   coordinateScaleOffset=lm['coordinateScaleOffset'], coordinateScale=lm['coordinateScale'],
                   coordinateBiasOffset=lm['coordinateBiasOffset'], coordinateBias=lm['coordinateBias'])
    out['lightGuidCount'] = len(lm.get('lightGuids', []))
    return out


def component_fields(p, index):
    if p.cls(index) not in COMPONENT_CLASSES:
        raise FormatError(f'{p.name(index)} is a {p.cls(index)}, not a static mesh component')
    lods = [dict(shadowMapsOffset=lod['shadowMaps']['at'], shadowMaps=lod['shadowMaps']['refs'],
                 lightmap=_lightmap(lod['lightmap'], p)) for lod in lighting.component_lods(p, index)[0]['lods']]
    owner = p.exports[index - 1]['outer']
    return dict(path=p.name(index), cls=p.cls(index), export=index, owner=p.name(owner) if owner > 0 else None,
                lods=lods)


def texture_fields(p, index):
    if p.cls(index) not in TEXTURE_CLASSES:
        raise FormatError(f'{p.name(index)} is a {p.cls(index)}, not a lightmap or shadow-map texture')
    props = property_offsets(p, index)
    cache = props.get(('TextureFileCacheName', 0))
    if cache is not None and cache[1] != 8:
        raise FormatError('Texture has no own 8-byte TextureFileCacheName')
    # a texture kept wholly inside the map (NeverStream: URB_StreetOverpass's ShadowMapTexture2D_173, 1024 x 1024
    # G8) saves no cache name: cacheNameOffset and cache are None, and every live mip must be inline (checked below)
    name_index, number = struct.unpack_from('<ii', p.data, cache[0]) if cache is not None else (None, None)
    r = p.native(index)
    lighting.bulk_meta(r)
    mips = []
    for _ in range(r.count()):
        at = r.pos
        meta = lighting.bulk_meta(r)
        meta['metaOffset'] = at
        if meta['inline']:
            meta['payloadOffset'] = at + 16
        meta['width'], meta['height'] = r.unpack('2i')
        mips.append(meta)
    guid_at = r.pos
    guid = r.take(16).hex()
    check = lighting.texture_record(p, index)
    live = [m for m in mips if m['bytes'] and not m['flags'] & 32]
    largest = max(live, key=lambda m: m['width'] * m['height']) if live else None
    if cache is None:
        if any(not m['inline'] for m in live):
            raise FormatError('Texture has mips in a texture cache but no own TextureFileCacheName')
        own_cache = None
    else:
        own_cache = p.names[name_index] + (f'_{number - 1}' if number else '')
    if len(mips) != check['mipCount'] or guid != check['cacheGuid'] or own_cache != check['cache']:
        raise FormatError('Texture fields disagree with the audit reader')
    if largest is not None and {k: largest[k] for k in check['largestMip']} != check['largestMip']:
        raise FormatError('Largest mip disagrees with the audit reader')
    return dict(path=p.name(index), cls=p.cls(index), export=index, format=p.effective(index, 'Format'),
                cacheNameOffset=cache[0] if cache is not None else None, cacheNameIndex=name_index, cacheNameNumber=number, cache=check['cache'],
                cacheGuidOffset=guid_at, cacheGuid=guid, mips=mips)


def fields(p, path):
    index = p.by_name.get(path)
    if index is None:
        raise FormatError(f'No export {path}')
    if p.cls(index) in COMPONENT_CLASSES:
        return component_fields(p, index)
    return texture_fields(p, index)


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    p = lighting.Package(sys.argv[1])
    if p.header['lic'] != 64:
        raise SystemExit('This tool reads EW licensee-64 records')
    for path in sys.argv[2:]:
        print(json.dumps(fields(p, path), indent=1))


if __name__ == '__main__':
    main()
