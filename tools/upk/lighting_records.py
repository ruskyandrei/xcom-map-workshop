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


def probe_volume(p, index, points):
    r = p.native(index)
    # Empty FPrecomputedVisibilityHandler (28) + FPrecomputedVolumeDistanceField (45).
    suffix = 73
    if p.data[r.end-suffix:r.end] != bytes(suffix):
        raise FormatError('Level has a nonempty/unknown visibility or distance-field suffix')
    candidates = []
    # A volume header is 37 bytes: UBOOL, FBox (6 floats + byte), spacing, sample count.
    # Serialized sample fields occupy 33 bytes; the upstream FixedSize(35) annotation
    # is not used as a stride. Actual fields and both real export boundaries agree on 33.
    for count in range(1, (r.end-r.pos-suffix-37)//33 + 1):
        start = r.end-suffix-37-33*count
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
        samples = [struct.unpack_from('<4f4B4B4B4BB', p.data, start+37+33*k) for k in range(count)]
        if not all(all(math.isfinite(v) and abs(v) < 1e8 for v in s[:4])
                   and s[3] > 0 and s[-1] in (0, 1) for s in samples):
            continue
        candidates.append((start, box, spacing, samples))
    if len(candidates) != 1:
        raise FormatError(f'Expected one complete valid volume suffix; found {len(candidates)}')
    start, box, spacing, samples = candidates[0]
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
