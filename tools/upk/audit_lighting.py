"""Read-only v845/licensee-64 lighting census for the Bar/Temple research snapshots.

Writes metadata only; never modifies inputs, exports game payloads or runs UDK.
The Level probe reader is deliberately restricted: it recognizes a unique complete
light-volume suffix followed by empty visibility/distance-field records. It does
not deserialize the preceding Level physics caches or prove runtime interpolation.
Field layouts were checked against pinned XCOM-Uncooker declarations; see the
lighting research report for sources. No upstream implementation is vendored here.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'viewer'))
from package import Package, Reader, FormatError, cache_file, link_caches  # noqa: F401 (link_caches for the bakers)


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


def verify_texture_sample(p, record):
    """Decode one representative high mip without writing image or texture data."""
    import io
    from PIL import Image
    from texture import decompress_payload, dds_header
    index = p.by_name[record['path']]
    r = p.native(index)
    bulk_meta(r)
    wanted = record['largestMip']
    payload = None
    for _ in range(r.count()):
        start = r.pos
        mip = bulk_meta(r)
        mip['width'], mip['height'] = r.unpack('2i')
        if mip == wanted:
            if mip['inline']:
                payload = p.data[start+16:start+16+mip['bytes']]
            else:
                with cache_file(p.path.parent, record['cache']).open('rb') as f:
                    f.seek(mip['offset'])
                    payload = f.read(mip['bytes'])
    if payload is None:
        raise FormatError('Representative mip not found')
    raw = decompress_payload(payload,wanted['flags'])
    w,h = wanted['width'],wanted['height']
    if record['format']=='PF_DXT1':
        if len(raw)!=max(1,(w+3)//4)*max(1,(h+3)//4)*8:
            raise FormatError('DXT1 mip size mismatch')
        image = Image.open(io.BytesIO(dds_header(w,h,'DXT1',len(raw))+raw)).convert('RGB')
    elif record['format']=='PF_G8':
        if len(raw)!=w*h:
            raise FormatError('G8 mip size mismatch')
        image = Image.frombytes('L',(w,h),raw)
    else:
        raise FormatError('Unexpected representative texture format')
    return dict(width=w,height=h,decodedBytes=len(raw),payloadSha256=hashlib.sha256(payload).hexdigest(),
                decodedSha256=hashlib.sha256(raw).hexdigest(),pixelRanges=image.getextrema())


def script_defaults(path):
    p=Package(path)
    targets=['Default__LightEnvironmentComponent','Default__DynamicLightEnvironmentComponent',
             'Default__LightComponent','Default__SkyLightComponent','Default__SkyLight.SkyLightComponent0',
             'Default__StaticMeshActor.StaticMeshComponent0','Default__XComLevelActor.StaticMeshComponent0',
             'Default__XComDestructibleActor.MyNEWLightEnvironment',
             'Default__XComInteractiveLevelActor.MyNEWLightEnvironment']
    keys=['bEnabled','bDynamic','bSynthesizeDirectionalLight','bSynthesizeSHLight','bForceNonCompositeDynamicLights',
          'NumVolumeVisibilitySamples','AmbientGlow','AmbientShadowColor','bIsCharacterLightEnvironment',
          'bUsePrecomputedShadows','bIgnoreLightMapData','bForceDirectLightMap','LightingChannels',
          'UseDirectLightMap','CastShadows','bCastCompositeShadow']
    return dict(path=str(p.path),sha256=digest(p.path),explicitDefaults={name:explicit_properties(p,p.by_name[name],keys)
                 for name in targets if name in p.by_name})


def audit(path, points):
    p = Package(path)
    if p.header['lic'] != 64:
        raise FormatError('This audit requires EW licensee-64 native component records')
    types = collections.Counter(p.cls(i) for i in range(1, len(p.exports)+1))
    result = dict(path=str(p.path), sha256=digest(p.path), header={k:p.header[k] for k in ('ver','lic','guid')},
                  exportClasses=dict(sorted(types.items())), components=[], textures=[], levels=[], lights=[],
                  explicitEnvironmentOverrides=[], worldSettings=[], errors=[])
    mesh_ids=set()
    for i in range(1, len(p.exports)+1):
        cls, name = p.cls(i), p.name(i)
        try:
            if cls in ('StaticMeshComponent', 'FracturedStaticMeshComponent') and name.startswith('TheWorld.'):
                result['components'].append(component_record(p,i))
                ref=p.effective(i,'StaticMesh',0)
                if ref>0:
                    mesh_ids.add(ref)
            elif cls in ('LightMapTexture2D','ShadowMapTexture2D'):
                result['textures'].append(texture_record(p,i))
            elif cls == 'Level':
                result['levels'].append(probe_volume(p,i,points))
            elif cls == 'WorldInfo':
                result['worldSettings'].append(dict(path=name,overrides=explicit_properties(p,i,
                    ['LightmassSettings','bForceNoPrecomputedLighting','CharacterLightingContrastFactor'])))
            elif cls.endswith('LightComponent') and name.startswith('TheWorld.'):
                result['lights'].append(dict(path=name, cls=cls, overrides=explicit_properties(p,i,
                    ['LightGuid','LightmapGuid','Brightness','LightColor','Radius','LightingChannels',
                     'UseDirectLightMap','bEnabled','CastShadows','CastStaticShadows','CastDynamicShadows',
                     'bCastCompositeShadow','bHasLightEverBeenBuiltIntoLightMap','LightmassSettings'])))
            elif cls == 'DynamicLightEnvironmentComponent' and name.startswith('TheWorld.'):
                result['explicitEnvironmentOverrides'].append(dict(path=name, overrides=explicit_properties(p,i,
                    ['bEnabled','bDynamic','bSynthesizeSHLight','bSynthesizeDirectionalLight',
                     'bForceNonCompositeDynamicLights','NumVolumeVisibilitySamples','AmbientGlow',
                     'AmbientShadowColor','BoundsMethod','bIsCharacterLightEnvironment'])))
        except (ValueError,IndexError,struct.error,OSError) as e:
            result['errors'].append(dict(path=name, cls=cls, error=str(e)))
    first = collections.Counter(str(c['lods'][0]['lightmap']['type']) if c['lods'] else 'no LODData'
                                for c in result['components'])
    result['summary'] = dict(componentCount=len(result['components']), lod0LightmapTypes=dict(first),
        componentsWithShadowmaps=sum(bool(c['lods'] and c['lods'][0]['shadowMaps']) for c in result['components']),
        textureCount=len(result['textures']), textureFormats=dict(collections.Counter(t['format'] for t in result['textures'])),
        textureCaches=dict(collections.Counter(str(t['cache']) for t in result['textures'])),
        lightmapSlotPatterns=dict(collections.Counter(
            ','.join(s['texture'].rsplit('_',1)[0] if s['index'] else 'None' for s in c['lods'][0]['lightmap']['slots'])
            for c in result['components'] if c['lods'] and c['lods'][0]['lightmap']['type']==2)),
        levelProbeCounts=[v['count'] for v in result['levels']], errorCount=len(result['errors']))
    # Retain a bounded set of examples, not a dump of thousands of game objects.
    examples, seen = [], set()
    for c in result.pop('components'):
        signature = (c['cls'], c['path'].split('.')[-2].rsplit('_',1)[0],
                     c['lods'][0]['lightmap']['type'] if c['lods'] else -1)
        if signature in seen:
            continue
        seen.add(signature)
        if len(examples) >= 16:
            continue
        for lod in c['lods']+c['swaps']:
            if 'lightGuids' in lod['lightmap']:
                lod['lightmap']['lightGuidCount'] = len(lod['lightmap'].pop('lightGuids'))
        examples.append(c)
    result['componentExamples'] = examples
    textures = result.pop('textures')
    result['textureExamples'] = [next(t for t in textures if t['cls']==cls)
                                 for cls in sorted({t['cls'] for t in textures})]
    for t in result['textureExamples']:
        t['payloadCheck'] = verify_texture_sample(p,t)
    lights = result.pop('lights')
    result['lightOverridePatterns'] = dict(collections.Counter(
        json.dumps(dict(cls=l['cls'], **l['overrides'].get('LightingChannels',{})),sort_keys=True)
        for l in lights))
    result['lightExamples'] = [l for l in lights if l['cls'] in ('SkyLightComponent','DominantDirectionalLightComponent')
                              or '.SpotLight_44.' in l['path']][:8]
    dle = result.pop('explicitEnvironmentOverrides')
    result['placedLightEnvironmentCount'] = len(dle)
    result['environmentOverridePatterns'] = dict(collections.Counter(
        json.dumps(d['overrides'],sort_keys=True) for d in dle))
    from mesh import read_mesh
    uv_counts=collections.Counter()
    uv_errors=[]
    invalid_uv=[]
    for index in sorted(mesh_ids):
        try:
            mesh=read_mesh(p,index)
            channel=p.effective(index,'LightMapCoordinateIndex')
            uv_counts[json.dumps(dict(uvChannels=len(mesh['uvs']),savedLightmapIndex=channel),sort_keys=True)]+=1
            if channel is not None and not 0<=channel<len(mesh['uvs']):
                invalid_uv.append(p.name(index))
        except (ValueError,IndexError,struct.error) as error:
            uv_errors.append(dict(mesh=p.name(index),error=str(error)))
    result['meshUvSummary']=dict(uniqueReferencedMeshes=len(mesh_ids),patterns=dict(uv_counts),
                                  savedIndexOutsideLod0Channels=invalid_uv,errors=uv_errors)
    return result


def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('packages', nargs='+', type=Path)
    a.add_argument('--out', required=True, type=Path)
    a.add_argument('--points-spec', type=Path, help='Optional patch spec; copy poses supply probe query points')
    a.add_argument('--defaults', nargs='*', type=Path, default=[], help='Optional Engine/XComGame packages for explicit CDO defaults')
    args = a.parse_args()
    for src in args.packages:
        if args.out.resolve().is_relative_to(src.resolve().parent):
            a.error('Output must be outside the input content directory')
    if args.out.suffix != '.json':
        a.error('Metadata output must be JSON')
    points, provenance, point_map = [], None, None
    if args.points_spec:
        spec = json.loads(args.points_spec.read_text(encoding='utf-8'))
        point_map = spec.get('map',{}).get('name')
        for obj in spec.get('objects',[]):
            poses, labels = obj.get('poses',[]), obj.get('labels',[])
            points.extend(dict(label=labels[i] if i<len(labels) else str(i), location=pose['location'])
                          for i,pose in enumerate(poses))
        provenance = dict(path=str(args.points_spec.resolve()), sha256=digest(args.points_spec))
    before = {str(p.resolve()):digest(p) for p in args.packages+args.defaults}
    result = dict(date='2026-11-06', scope='Read-only structural census; no visual or runtime equivalence claim. '
                  'Properties called overrides exclude unresolved class defaults; probe colours are encoded bytes, '
                  'not decoded linear radiance. Sphere coverage is geometric, not the engine interpolation rule.',
                  scriptSha256=digest(__file__), pointsSource=provenance,
                  packages=[audit(p,points if p.stem==point_map else []) for p in args.packages],
                  scriptDefaults=[script_defaults(p) for p in args.defaults])
    assert before == {str(p.resolve()):digest(p) for p in args.packages+args.defaults}, 'Inputs changed during audit'
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    for p in result['packages']:
        print(Path(p['path']).stem, json.dumps(p['summary']))
        if p['errors']:
            print('First errors:',json.dumps(p['errors'][:3]))


if __name__ == '__main__':
    main()
