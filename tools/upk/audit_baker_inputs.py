"""Read-only baker input/workload audit for v845 EW maps.

Reuses audit_lighting's native readers. Counts source geometry and atlas rectangle
areas, not final visible triangles, UV occupancy, measured ray throughput or bake
time. Writes bounded metadata only; no game payloads are exported.
"""
import argparse
import collections
import json
import math
from pathlib import Path

import audit_lighting as lighting
from mesh import read_mesh


def audit(path):
    p = lighting.Package(path)
    if p.header['lic'] != 64:
        raise ValueError('This audit requires EW/licensee-64 component records')
    light_guids = {'LightGuid': set(), 'LightmapGuid': set()}
    baked_guids, shadow_guids = set(), set()
    meshes, textures = {}, {}
    count = with_mesh = triangles = rect_count = 0
    area = 0.0
    lod_counts, sizes, dimension_pairs = collections.Counter(), collections.Counter(), collections.Counter()
    scales, nonunit_scales, all_2d_records = [], 0, 0
    candidates, errors = [], []
    texture_own_flags = collections.Counter()
    for i in range(1, len(p.exports)+1):
        cls, name = p.cls(i), p.name(i)
        if cls.endswith('LightComponent'):
            for key in light_guids:
                raw = p.own(i,key)
                if isinstance(raw,bytes) and len(raw)==16:
                    light_guids[key].add(raw.hex())
        if cls=='ShadowMap2D':
            raw = p.own(i,'LightGuid')
            if isinstance(raw,bytes) and len(raw)==16:
                shadow_guids.add(raw.hex())
        if cls=='LightMapTexture2D':
            props = {key:p.own(i,key) for key in ('SRGB','CompressionSettings','LODGroup','NeverStream','bNoTiling')}
            texture_own_flags[json.dumps(props,sort_keys=True)]+=1
        if cls not in ('StaticMeshComponent','FracturedStaticMeshComponent') or not name.startswith('TheWorld.'):
            continue
        count+=1
        try:
            component = lighting.component_record(p,i)
            mesh_index = p.effective(i,'StaticMesh',0)
            if mesh_index>0:
                if mesh_index not in meshes:
                    meshes[mesh_index] = read_mesh(p,mesh_index)
                triangles += len(meshes[mesh_index]['indices'])//3
                with_mesh+=1
                lod_counts[meshes[mesh_index]['lods']]+=1
            for lod in component['lods']:
                lm = lod['lightmap']
                baked_guids.update(lm.get('lightGuids',[]))
                if lm['type']==2:
                    all_2d_records+=1
                    scale=lm['slots'][1]['scale']
                    if not all(math.isfinite(x) for x in scale):
                        raise ValueError('Nonfinite lightmap scale')
                    scales.extend(scale)
                    nonunit_scales+=scale!=[1.0,1.0,1.0]
            if not component['lods'] or component['lods'][0]['lightmap']['type']!=2:
                continue
            lm=component['lods'][0]['lightmap']
            dims=[]
            for slot in lm['slots'][:2]:
                ref=slot['index']
                if ref<=0:
                    raise ValueError('Expected two local lightmap texture references')
                if ref not in textures:
                    textures[ref]=lighting.texture_record(p,ref)
                mip=textures[ref]['largestMip']
                if mip is None:
                    raise ValueError('Lightmap has no live mip')
                dims.append((mip['width'],mip['height']))
            dimension_pairs[str(dims)]+=1
            w,h=(lm['coordinateScale'][k]*dims[0][k] for k in range(2))
            if not all(math.isfinite(v) and v>0 for v in (w,h)):
                raise ValueError('Invalid mapped atlas rectangle')
            area+=w*h
            rect_count+=1
            sizes[str((round(w),round(h)))]+=1
            owner=p.exports[i-1]['outer']
            if (owner>0 and p.cls(owner)=='StaticMeshActor' and mesh_index>0
                    and not component['lods'][0]['shadowMaps'] and len(candidates)<3):
                candidates.append(dict(component=name,mesh=p.name(mesh_index),
                    savedLightmapUvIndex=p.effective(mesh_index,'LightMapCoordinateIndex'),
                    rectangle=[w,h],textures=[s['texture'] for s in lm['slots']],
                    note='Structural candidate only; visibility/material/gameplay suitability not checked'))
        except (ValueError,IndexError) as error:
            errors.append(dict(component=name,error=str(error)))
    return dict(path=str(p.path),sha256=lighting.digest(p.path),
        geometry=dict(components=count,componentsWithLocalMesh=with_mesh,uniqueMeshes=len(meshes),
                      uniqueLod0Triangles=sum(len(m['indices'])//3 for m in meshes.values()),
                      instancedLod0Triangles=triangles,componentMeshLodCounts=dict(lod_counts)),
        allocations=dict(lod0TextureMappedComponents=rect_count,sumRectangleAreaTexels=area,
                         mostCommonRectangleSizes=sizes.most_common(12),textureDimensionPairs=dict(dimension_pairs),
                         interpretation='Scale times largest available mip dimensions; not rasterized UV occupancy; '
                                        'does not count padding, all LODs, shadows, probes or inherited streams'),
        guidAssociations=dict(uniqueLightmapGuids=len(baked_guids),
            matchesLightmapGuid=len(baked_guids & light_guids['LightmapGuid']),
            matchesLightGuid=len(baked_guids & light_guids['LightGuid']),
            unmatchedLightmapGuids=len(baked_guids-light_guids['LightmapGuid']),
            uniqueShadowGuids=len(shadow_guids),shadowMatchesLightGuid=len(shadow_guids & light_guids['LightGuid']),
            shadowMatchesLightmapGuid=len(shadow_guids & light_guids['LightmapGuid'])),
        directionalScale=dict(all2dLodRecords=all_2d_records,nonUnitRecords=nonunit_scales,
                              min=min(scales) if scales else None,max=max(scales) if scales else None),
        explicitLightmapTextureFlags=dict(texture_own_flags),structuralCandidates=candidates,errors=errors)


def main():
    a=argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('packages',nargs='+',type=Path)
    a.add_argument('--out',required=True,type=Path)
    args=a.parse_args()
    if args.out.suffix!='.json':
        a.error('Output must be metadata JSON')
    for src in args.packages:
        if args.out.resolve().is_relative_to(src.resolve().parent):
            a.error('Output must be outside the input content directory')
    before={str(p.resolve()):lighting.digest(p) for p in args.packages}
    result=dict(date='2026-11-06',scope='Read-only input audit, not a baker or runtime test',
        toolHashes={'tools/upk/audit_baker_inputs.py':lighting.digest(__file__),
                    'tools/upk/audit_lighting.py':lighting.digest(lighting.__file__)},
        packages=[audit(p) for p in args.packages])
    assert before=={str(p.resolve()):lighting.digest(p) for p in args.packages},'Input changed during audit'
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    for p in result['packages']:
        print(Path(p['path']).stem,json.dumps({k:p[k] for k in ['geometry','guidAssociations','directionalScale']}))
        print('LOD-0 rectangle area:',p['allocations']['sumRectangleAreaTexels'],'errors:',len(p['errors']))
    if any(p['errors'] for p in result['packages']):
        raise SystemExit(1)


if __name__=='__main__':
    main()
