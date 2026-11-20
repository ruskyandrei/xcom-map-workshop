"""A map's lighting records, read with the viewer's checked reader (tools/viewer/package.py): a static mesh
component's LOD lighting (its shadow maps, its lightmap and its texture slots), the bulk-data records of a texture's
mips, the properties an object saves itself, and a file's SHA-256. Every Build's relight and copier reads these
(tools/bake), and the editor's light records (tools/viewer/lights.py).

v845 packages, Enemy Within's (licensee 64: two mesh-swap LOD records after the LOD array) and UDK's own (licensee 0).
The field layouts were checked against pinned XCOM-Uncooker declarations; no upstream implementation is vendored
here. The research census these were first written for (audit_lighting.py) imports them from here. A mesh component's
LOD records and a bulk record are read by native_fields.py's one reader (with their places in the package); these
give its values in the form the bakers read.
"""
import hashlib
from pathlib import Path
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
