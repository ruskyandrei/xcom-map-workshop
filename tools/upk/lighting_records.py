"""A map's lighting records, read with the viewer's checked reader (tools/viewer/package.py): a static mesh
component's LOD lighting (its shadow maps, its lightmap and its texture slots), the bulk-data records of a texture's
mips, the properties an object saves itself, the Level's lighting samples for moving things (`probe_volume`), and a
file's SHA-256. Every Build's relight and copier reads these (tools/bake), and the editor's light records
(tools/viewer/lights.py).

v845 packages, Enemy Within's (licensee 64: two mesh-swap LOD records after the LOD array) and UDK's own (licensee 0).
The field layouts were checked against pinned XCOM-Uncooker declarations; no upstream implementation is vendored
here. The research census these were first written for (audit_lighting.py) imports them from here. A mesh component's
LOD records and a bulk record are read by native_fields.py's one reader (with their places in the package); these
give its values in the form the bakers read.
"""
import hashlib
import math
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'viewer'))
from package import Package, Reader, FormatError, cache_file, link_caches  # noqa: E402,F401 (the bakers read them here)
import native_fields  # noqa: E402   (beside this file: found as this module was)


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def refs(r, p):
    return native_fields.object_refs(r, p)['refs']


def bulk_meta(r):
    b = native_fields.bulk_record(r)
    if b['count'] < 0 or b['bytes'] < 0:
        raise FormatError('Negative bulk count or size')
    return _bulk(b)


def _bulk(b):
    return dict(flags=b['flags'], count=b['count'], bytes=b['bytes'], offset=b['offset'], inline=b['inline'])


def lightmap(r, p):
    return _lightmap(native_fields.lightmap_record(r, p), p)


def _lightmap(lm, p):
    result = dict(type=lm['type'])
    if lm['type'] == 0:
        return result
    result['lightGuids'] = lm['lightGuids']
    if lm['type'] == 1:
        result['owner'] = p.name(lm['owner'])
        result['directionalSamples'] = _bulk(lm['directionalSamples'])
        result['scaleVectors'] = lm['scaleVectors']
        result['simpleSamples'] = _bulk(lm['simpleSamples'])
    else:
        result['slots'] = [dict(texture=p.name(s['index']), index=s['index'], scale=s['scale']) for s in lm['slots']]
        result['coordinateScale'] = lm['coordinateScale']
        result['coordinateBias'] = lm['coordinateBias']
    return result


def lod_record(r, p):
    return _lod(native_fields.lod_record(r, p), p)


def _lod(lod, p):
    return dict(shadowMaps=lod['shadowMaps']['refs'], shadowVertexBuffers=lod['shadowVertexBuffers']['refs'],
                lightmap=_lightmap(lod['lightmap'], p), overrideVertexColors=lod['overrideVertexColors'])


def component_lods(p, index):
    """(native_fields.mesh_lods of a static mesh component, the bytes of its native data after them): none in a
    StaticMeshComponent (a FormatError otherwise); a subclass's are its own."""
    r = p.native(index)
    lods = native_fields.mesh_lods(r, p)
    tail = r.end - r.pos
    if p.cls(index) == 'StaticMeshComponent' and tail:
        raise FormatError(f'StaticMeshComponent has {tail} unconsumed bytes')
    return lods, tail


def component_record(p, index):
    """A static mesh component's native LOD lighting records. EW (licensee 64) adds two mesh-swap LOD records and
    their meshes; UDK's own packages (licensee 0, same version 845) end after the LOD array."""
    lods, tail = component_lods(p, index)
    return dict(path=p.name(index), cls=p.cls(index), lods=[_lod(x, p) for x in lods['lods']],
                swaps=[_lod(x, p) for x in lods['swaps']], swapMeshes=[p.name(m['ref']) for m in lods['swapMeshes']],
                unparsedSubclassBytes=tail)


def explicit_properties(p, index, keys):
    out = {}
    for key in keys:
        value = p.own(index, key)
        if value is None:
            continue
        if isinstance(value, bytes):
            if key in ('LightingChannels', 'LightmassSettings'):
                value = {k[0]:v['value'] for k,v in p.tagged(Reader(value)).items()}
            else:
                value = dict(rawBytes=len(value))
        out[key] = value
    return out


def matrix_rows(raw):
    """A saved Matrix struct (64 bytes) as four rows of (X, Y, Z, W): the X, Y and Z axes and the origin, each row
    saved W first (native_lights.parent_to_world writes them so)."""
    v = struct.unpack('<16f', bytes(raw))
    return [[v[4 * k + 1], v[4 * k + 2], v[4 * k + 3], v[4 * k]] for k in range(4)]


def dominant_shadow_map(p, index):
    """A DominantDirectionalLightComponent's own shadow map of the level, for moving things: dict(offset: its first
    depth's place in p.data, sizeX, sizeY, depths: the counted WORD array the cooked component saves ahead of its
    header, row by row with X fastest, each a depth along the light's direction, 0 at the importance bounds' near face
    and 65535 at their far one; worldToLight and lightToWorld (matrix_rows), bounds: the light-space box (min x, y,
    z, max x, y, z) the map covers), from the component's DominantLightShadowInfo. FormatError for another class, an
    array running past the export, or a count that is not sizeX x sizeY."""
    if p.cls(index) != 'DominantDirectionalLightComponent':
        raise FormatError(f'{p.name(index)} is a {p.cls(index)}, not a DominantDirectionalLightComponent')
    e = p.exports[index - 1]
    r = Reader(p.data, e['off'], e['off'] + e['size'])
    count = r.count()
    offset = r.pos
    depths = struct.unpack(f'<{count}H', r.take(2 * count))
    raw = p.own(index, 'DominantLightShadowInfo')
    info = {name: item['value'] for (name, slot), item in p.tagged(Reader(bytes(raw))).items()
            if slot == 0} if raw is not None else {}
    size = (info.get('ShadowMapSizeX', 0), info.get('ShadowMapSizeY', 0))
    if size[0] * size[1] != count:
        raise FormatError(f'{p.name(index)}: {count} depths for a {size[0]} x {size[1]} shadow map')
    out = dict(offset=offset, sizeX=size[0], sizeY=size[1], depths=depths)
    if not count and raw is None:           # a light that has no map of the level
        return dict(out, worldToLight=None, lightToWorld=None, bounds=None)
    for key, member in (('worldToLight', 'WorldToLight'), ('lightToWorld', 'LightToWorld')):
        value = info.get(member)
        if not isinstance(value, (bytes, bytearray)) or len(value) != 64:
            raise FormatError(f'{p.name(index)}: no {member} matrix')
        out[key] = matrix_rows(value)
    box = info.get('LightSpaceImportanceBounds')
    if not isinstance(box, (bytes, bytearray)) or len(box) != 25:
        raise FormatError(f'{p.name(index)}: no LightSpaceImportanceBounds box')
    out['bounds'] = list(struct.unpack('<6f', bytes(box)[:24]))
    return out


# DominantLightShadowInfo's members a writer of the light's map of the level sets in place, with the sizes they save
SHADOW_INFO_MEMBERS = dict(WorldToLight=64, LightToWorld=64, LightSpaceImportanceBounds=25, ShadowMapSizeX=4,
                           ShadowMapSizeY=4)


def shadow_info_places(p, index):
    """Where a DominantDirectionalLightComponent saves its DominantLightShadowInfo's members, for a writer that sets
    them in place: {member: its value's place in p.data} for SHADOW_INFO_MEMBERS (a matrix's 64 bytes, each row W
    first as matrix_rows reads them; the box's six floats and its IsValid byte; the two sizes). The component's
    properties are walked from past its leading array of depths (dominant_shadow_map), as the package's reader takes
    them, by props.tags. FormatError for another class, a walk that ends elsewhere than the package's reader does, or
    a member missing or of another size."""
    import props as legacy_props
    if p.cls(index) != 'DominantDirectionalLightComponent':
        raise FormatError(f'{p.name(index)} is a {p.cls(index)}, not a DominantDirectionalLightComponent')
    e = p.exports[index - 1]
    m = dominant_shadow_map(p, index)
    skip = m['offset'] - e['off'] + 2 * len(m['depths'])
    start = legacy_props.props_start(p.data, dict(e, off=e['off'] + skip, size=e['size'] - skip), p.names)
    try:
        rows, after = legacy_props.read_tags(p.data, start, e['off'] + e['size'], p.names)
        if after != p.properties(index)[1]:
            raise FormatError(f'{p.name(index)}: the property walk disagrees with the package reader')
        info = [(at, size) for name, kind, sub, slot, at, size in rows
                if name == 'DominantLightShadowInfo' and kind == 'StructProperty' and slot == 0]
        if len(info) != 1:
            raise FormatError(f'{p.name(index)}: no DominantLightShadowInfo')
        at, size = info[0]
        members, end = legacy_props.read_tags(p.data, at, at + size, p.names)
    except ValueError as error:
        raise FormatError(str(error)) from None
    if end != at + size:
        raise FormatError(f'{p.name(index)}: DominantLightShadowInfo does not end where its tag says')
    found = {name: (place, length) for name, _, _, slot, place, length in members if slot == 0}
    out = {}
    for name, length in SHADOW_INFO_MEMBERS.items():
        if name not in found or found[name][1] != length:
            raise FormatError(f'{p.name(index)}: DominantLightShadowInfo saves no {length}-byte {name}')
        out[name] = found[name][0]
    return out


# A Level's precomputed light volume lies at the end of its native data, before an empty visibility handler (28 bytes)
# and an empty volume distance field (45): a 37-byte header (bInitialized, the bounds as six floats and IsValid, the
# sample spacing, the sample count), then the samples, 33 bytes each as saved (FVolumeLightingSample: position and
# radius, four direction bytes, the indirect, environment and ambient colours, then bShadowedFromDominantLights; the
# upstream FixedSize(35) annotation is not the stride: the fields and both real export boundaries agree on 33).
VOLUME_SUFFIX, VOLUME_HEADER, SAMPLE_BYTES = 73, 37, 33
MARK_AT = 32                # a sample's bShadowedFromDominantLights: 1 where the map's dominant light does not reach


def light_volume(p, index):
    """The Level `index`'s precomputed light volume, its lighting samples for moving things: dict(offset: the
    volume's header in p.data (logical bytes), bounds (min x, y, z, max x, y, z), spacing, samples: each sample's
    fields as saved (x, y, z, radius, four direction bytes, the indirect, environment and ambient colours' B, G, R, A
    bytes, the mark)). It is found as the one complete, valid volume that ends where the suffix begins (the physics
    caches before it are not parsed); FormatError when the suffix is not empty or no one volume fits."""
    r = p.native(index)
    suffix = VOLUME_SUFFIX
    if p.data[r.end-suffix:r.end] != bytes(suffix):
        raise FormatError('Level has a nonempty/unknown visibility or distance-field suffix')
    candidates = []
    for count in range(1, (r.end-r.pos-suffix-VOLUME_HEADER)//SAMPLE_BYTES + 1):
        start = r.end-suffix-VOLUME_HEADER-SAMPLE_BYTES*count
        if p.data[start:start+4] != b'\x01\x00\x00\x00':
            continue
        if p.data[start+28] != 1 or struct.unpack_from('<i', p.data, start+33)[0] != count:
            continue
        box = struct.unpack_from('<6f', p.data, start+4)
        spacing = struct.unpack_from('<f', p.data, start+29)[0]
        if not all(math.isfinite(v) and abs(v) < 1e8 for v in box):
            continue
        if not all(box[k] < box[k+3] for k in range(3)) or not math.isfinite(spacing) or spacing < 0:
            continue
        samples = [struct.unpack_from('<4f4B4B4B4BB', p.data, start+VOLUME_HEADER+SAMPLE_BYTES*k)
                   for k in range(count)]
        if not all(all(math.isfinite(v) and abs(v) < 1e8 for v in s[:4])
                   and s[3] > 0 and s[-1] in (0, 1) for s in samples):
            continue
        candidates.append((start, box, spacing, samples))
    if len(candidates) != 1:
        raise FormatError(f'Expected one complete valid volume suffix; found {len(candidates)}')
    start, box, spacing, samples = candidates[0]
    return dict(offset=start, bounds=list(box), spacing=spacing, samples=samples)


def mark_places(volume):
    """Where each sample's mark lies in the package's logical bytes, in the samples' order (light_volume's
    `volume`)."""
    return [volume['offset'] + VOLUME_HEADER + SAMPLE_BYTES * k + MARK_AT for k in range(len(volume['samples']))]


def mark_edits(volume, marks):
    """The fixed-size edits that give the volume's samples the marks `marks` (one 0 or 1 a sample, in order), as
    package_edit.write_edited takes them ((logical offset, bytes) pairs, in order): only the marks that change.
    ValueError for a count that is not the samples' or a mark that is not 0 or 1."""
    marks = list(marks)
    if len(marks) != len(volume['samples']):
        raise ValueError(f'{len(marks)} marks for {len(volume["samples"])} samples')
    edits = []
    for place, sample, mark in zip(mark_places(volume), volume['samples'], marks):
        if mark not in (0, 1):
            raise ValueError(f"a sample's mark is 0 or 1, not {mark!r}")
        if sample[-1] != mark:
            edits.append((place, bytes([mark])))
    return edits


def probe_volume(p, index, points):
    """light_volume's samples counted for the research census (audit_lighting.py), with the three samples nearest to
    each of `points` (dicts of label and location)."""
    v = light_volume(p, index)
    start, box, spacing, samples = v['offset'], v['bounds'], v['spacing'], v['samples']
    result = dict(method='unique bounded suffix, 33-byte samples; physics prefix not parsed',
                  level=p.name(index), offset=start, bounds=list(box), sampleSpacing=spacing,
                  count=len(samples), radiusRange=[min(s[3] for s in samples), max(s[3] for s in samples)],
                  nonzeroIndirectRGB=sum(any(s[8:11]) for s in samples),
                  nonzeroEnvironmentRGB=sum(any(s[12:15]) for s in samples),
                  nonzeroAmbientRGB=sum(any(s[16:19]) for s in samples),
                  shadowedFromDominant=sum(s[-1] for s in samples),
                  centersOutsideStoredBounds=sum(not all(box[k]-1 <= s[k] <= box[k+3]+1
                                                          for k in range(3)) for s in samples), points=[])
    for point in points:
        xyz = point['location']
        nearest = sorted((math.dist(s[:3], xyz), k) for k, s in enumerate(samples))
        covered = [(d, k) for d, k in nearest if d <= samples[k][3]]
        closest = []
        for dist, k in nearest[:3]:
            s = samples[k]
            closest.append(dict(sampleIndex=k, distance=dist, position=list(s[:3]), radius=s[3],
                                indirectBGRA=list(s[8:12]), environmentBGRA=list(s[12:16]),
                                ambientBGRA=list(s[16:20])))
        result['points'].append(dict(label=point['label'], location=xyz, sphereCoverageCount=len(covered),
                                     closest=closest))
    return result


def texture_record(p, index):
    r = p.native(index)
    bulk_meta(r)
    mips = []
    for _ in range(r.count()):
        mip = bulk_meta(r)
        mip['width'], mip['height'] = r.unpack('2i')
        if not 0 < mip['width'] <= 16384 or not 0 < mip['height'] <= 16384:
            raise FormatError('Invalid texture dimensions')
        mips.append(mip)
    cache_guid = r.take(16).hex()
    cache = p.effective(index, 'TextureFileCacheName')
    live = [m for m in mips if m['bytes'] and not m['flags'] & 32]
    for m in live:
        if not m['inline']:
            if not cache or not cache.replace('_', '').isalnum():
                raise FormatError('Invalid cache name')
            file = cache_file(p.path.parent, cache)
            if m['offset'] < 0 or m['offset']+m['bytes'] > file.stat().st_size:
                raise FormatError('Texture mip range outside cache')
    return dict(path=p.name(index), cls=p.cls(index), format=p.effective(index, 'Format'), cache=cache,
                cacheGuid=cache_guid, largestMip=max(live, key=lambda m:m['width']*m['height']) if live else None,
                mipCount=len(mips), externalLiveMipCount=sum(not m['inline'] for m in live),
                nativeSuffixBytes=r.end-r.pos)
