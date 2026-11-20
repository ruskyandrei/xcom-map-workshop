"""A map's lighting records, read with the viewer's checked reader (tools/viewer/package.py): a static mesh
component's LOD lighting (its shadow maps, its lightmap and its texture slots), the bulk-data records of a texture's
mips, the properties an object saves itself, and a file's SHA-256. Every Build's relight and copier reads these
(tools/bake), and the editor's light records (tools/viewer/lights.py).

v845 packages, Enemy Within's (licensee 64: two mesh-swap LOD records after the LOD array) and UDK's own (licensee 0).
The field layouts were checked against pinned XCOM-Uncooker declarations; no upstream implementation is vendored
here. The research census these were first written for (audit_lighting.py) imports them from here.
"""
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'viewer'))
from package import Package, Reader, FormatError, cache_file, link_caches  # noqa: E402,F401 (the bakers read them here)


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def refs(r, p):
    n = r.count()
    values = list(r.unpack(f'{n}i'))
    for v in values:
        p.name(v)
    return values


def bulk_meta(r):
    flags, count, size, offset = r.unpack('4i')
    if count < 0 or size < 0:
        raise FormatError('Negative bulk count or size')
    inline = not flags & 1
    if inline:
        r.take(size)
    return dict(flags=flags, count=count, bytes=size, offset=offset, inline=inline)


def lightmap(r, p):
    kind = r.i32()
    result = dict(type=kind)
    if kind == 0:
        return result
    if kind not in (1, 2):
        raise FormatError(f'Unknown lightmap type {kind}')
    n = r.count()
    result['lightGuids'] = [r.take(16).hex() for _ in range(n)]
    if kind == 1:
        result['owner'] = p.name(r.i32())
        result['directionalSamples'] = bulk_meta(r)
        result['scaleVectors'] = [list(r.unpack('3f')) for _ in range(3)]
        result['simpleSamples'] = bulk_meta(r)
    else:
        result['slots'] = []
        for _ in range(3):
            ref = r.i32()
            result['slots'].append(dict(texture=p.name(ref), index=ref, scale=list(r.unpack('3f'))))
        result['coordinateScale'] = list(r.unpack('2f'))
        result['coordinateBias'] = list(r.unpack('2f'))
    return result


def lod_record(r, p):
    result = dict(shadowMaps=refs(r, p), shadowVertexBuffers=refs(r, p), lightmap=lightmap(r, p))
    color = r.take(1)[0]
    if color not in (0, 1):
        raise FormatError('Invalid vertex-color boolean')
    if color:
        stride, count = r.unpack('2I')
        if count:
            actual_stride, actual_count, _ = r.array_bytes()
            if actual_stride != stride or actual_count != count:
                raise FormatError('Vertex-color count/stride mismatch')
    positions = r.count()
    r.take(positions * 12)
    result['overrideVertexColors'] = bool(color)
    return result


def component_record(p, index):
    """A static mesh component's native LOD lighting records. EW (licensee 64) adds two mesh-swap LOD records and
    their meshes; UDK's own packages (licensee 0, same version 845) end after the LOD array."""
    r = p.native(index)
    lods = [lod_record(r, p) for _ in range(r.count())]
    if p.header['lic'] == 0:
        swaps, swap_meshes = [], []
    else:
        swaps = [lod_record(r, p), lod_record(r, p)]
        swap_meshes = [p.name(r.i32()), p.name(r.i32())]
    tail = r.end - r.pos
    if p.cls(index) == 'StaticMeshComponent' and tail:
        raise FormatError(f'StaticMeshComponent has {tail} unconsumed bytes')
    return dict(path=p.name(index), cls=p.cls(index), lods=lods, swaps=swaps,
                swapMeshes=swap_meshes, unparsedSubclassBytes=tail)


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
