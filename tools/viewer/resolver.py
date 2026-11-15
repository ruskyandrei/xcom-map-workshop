"""Experimental visual patch resolver. Native gameplay is deliberately not run.

Inputs are immutable exports and patchtool specs. Unknown operations/fields and
missing renderable sources are reported rather than silently claiming parity.
"""
import copy
import math
import re
from itertools import product
from export_math import transform,multiply,view_matrix
from lights import sun_records


def extras(operation):
    result={}
    for line in operation.get('extra',[]):
        key,sep,value=line.partition('=')
        if not sep: raise ValueError(f'Invalid extra property: {line}')
        result[key.strip()]=value.strip()
    return result


def vector(value):
    match=re.fullmatch(r'\(X=([-+.\deE]+),Y=([-+.\deE]+),Z=([-+.\deE]+)\)',value.replace(' ',''))
    if not match: raise ValueError(f'Unsupported vector: {value}')
    return [float(v) for v in match.groups()]


# patchtool's defaults (tools/patch/patchtool.ps1 Read-Spec), so a preview places what the builder places.
GROUND_Z=3.999993     # map.groundZ: the Z the editor stored for the shipped floor-standing cover patches
HIDE_HALF=512         # a hide object's half-size
# What XComMapEdCopier copies or moves; it logs anything else as "can't copy yet" and leaves it out.
COPYABLE={'XComInteractiveLevelActor','XComLadder','XComFracLevelActor','XComDecoFracLevelActor',
          'XComDestructibleActor','XComLevelActor','StaticMeshActor'}
# With absolute poses the copier places neither fractured pieces, doors nor ladders (their columns, interaction points
# and climbs follow the group transform).
NOT_BY_POSE={'XComInteractiveLevelActor','XComLadder','XComFracLevelActor','XComDecoFracLevelActor'}


def position(op,spec):
    if 'tile' in op:
        origin=spec.get('map',{}).get('origin',[0,0]);size=spec.get('map',{}).get('tileSize',96)
        shift=size/2 if op.get('anchor','corner')=='center' else 0
        return [origin[i]+size*op['tile'][i]+shift for i in range(2)]+[op.get('z',spec.get('map',{}).get('groundZ',GROUND_Z))]
    pos=list(op.get('location',[0,0,0]))
    if len(pos)==2:pos.append(spec.get('map',{}).get('groundZ',GROUND_Z))
    if 'z' in op:pos[2]=op['z']
    if len(pos)!=3 or not all(math.isfinite(v) for v in pos):raise ValueError('Invalid location')
    return pos


def turn(v,yaw):
    c,s=math.cos(math.radians(yaw)),math.sin(math.radians(yaw))
    return [c*v[0]-s*v[1],s*v[0]+c*v[1],v[2]]


def place(obj,loc,rotation,scale):
    obj['location'],obj['rotation'],obj['scale']=loc,rotation,scale
    cm=obj.get('componentTransform',transform([0,0,0],[0,0,0],[1,1,1]))
    obj['matrix']=view_matrix(multiply(transform(loc,rotation,scale),cm))


def bounds(obj,meshes):
    b=meshes[obj['mesh']]['bounds'];m=obj['matrix'];points=[]
    for sx,sy,sz in product((-1,1),repeat=3):
        v=[b[0]+sx*b[3],b[2]+sz*b[5],b[1]+sy*b[4]]
        view=[sum(m[k*4+j]*v[k] for k in range(3))+m[12+j] for j in range(3)]
        points.append([view[0],view[2],view[1]])
    return [[min(v[j] for v in points) for j in range(3)], [max(v[j] for v in points) for j in range(3)]]


def game_round(n):return math.floor(n+0.5) if n>=0 else math.ceil(n-0.5)


def snap(parts,meshes,origin,yaw):
    native=int(yaw*65536/360);quarter=native & 16383
    if 1820<quarter<16384-1820:return
    boxes=[bounds(p,meshes) for p in parts]
    lo=[min(b[0][k] for b in boxes) for k in range(3)];hi=[max(b[1][k] for b in boxes) for k in range(3)]
    if any(not 0<hi[k]-lo[k]<=1500 for k in range(2)):return
    shift=[]
    for k in range(2):
        n=max(1,game_round((hi[k]-lo[k])/96));mid=(lo[k]+hi[k])/2;offset=48 if n%2 else 0
        target=origin[k]+offset+96*game_round((mid-origin[k]-offset)/96)
        shift.append(target-mid)
    return shift+[0]


def resolve_scene(base,spec,template_provider=None):
    out=copy.deepcopy(base);objects=out['objects'];notes=[];building_ids={}
    # Asset tables are append-only during export; template imports can add bindings.
    for key in ('meshes','materials','textures'):out[key]=base[key]
    original={};hide_sources={}
    for obj in objects:
        name=obj['actor'].split('.')[-1]
        if obj.get('layer')!='inherited':original.setdefault(name,[]).append(obj)
        hide_sources.setdefault((obj.get('sourcePackage','base'),name),[]).append(obj)
    def note(index,msg):notes.append(dict(source=f'operation {index}',message=msg))
    if spec.get('base') and spec['base'].casefold() not in {s['name'].casefold() for s in base.get('inheritedPatches',[])}:
        note('composition',f"Inherited patch {spec['base']} is not composed yet; this preview covers base-map scenery and supported spec operations")
    def attach(obj,building,extra):
        if building is None:
            obj['floors']=[];return
        if int(extra.get('BuildingFloor','-1'))>=0:
            obj['floors']=[dict(building=building,floor=int(extra['BuildingFloor']),cutdownFloor=0)]
        else:
            obj['floors']=[{**f,'building':building} for f in obj.get('floors',[])]
    for index,op in enumerate(spec.get('objects',[])):
        kind=op.get('type','actor');extra=extras(op);dest=position(op,spec);yaw=op.get('yaw',0)
        known={'CopyScale','BuildingFloor','BuildingName','DrawScale3D','bCopyDoors','bCopyLadders','bSnapToTiles',
               'KeepGroundHeight','bHideFragments','bHideLights','bHideVolumes','bHideCursorVolumes','bLogTiles','bLogCursor',
               'bProbeIndoor','LateRebuild','LadderFootRebuild','ProbeStart','ProbeEnd'}
        for key in extra:
            if key not in known and not re.fullmatch(r'(Path|Floor)Probes\(\d+\)',key):note(index,f'Unsupported extra property {key}')
        if kind=='copy' and 'poses' in op:
            # Absolute poses (the editor's compiler): each source to its own location and full rotator.
            scale=vector(extra['CopyScale']) if 'CopyScale' in extra else [1,1,1]
            names=op.get('from',[]);poses=op['poses'];labels=op.get('labels',[])
            if len(poses)!=len(names):note(index,'poses needs one pose per name in from');continue
            for k,(source,pose) in enumerate(zip(names,poses)):
                if source not in original:note(index,f'No rendered source for {source} (may require skeletal support)');continue
                cls=original[source][0]['actorClass']
                if cls in NOT_BY_POSE:note(index,f"The copier doesn't place {source} ({cls}) by an absolute pose");continue
                if cls not in COPYABLE:note(index,f"The copier can't copy {source} ({cls})");continue
                label=labels[k] if k<len(labels) else f'{source}_copy{index}_{k}'
                for si,src in enumerate(original[source]):
                    obj=copy.deepcopy(src)
                    place(obj,list(pose['location']),list(pose['rotation']),[src['scale'][j]*scale[j] for j in range(3)])
                    obj['provenance']=dict(operation=index,type='copy',sourceActor=src['actor'],label=label)
                    obj['id']=f'copy:{index}:{k}:{si}';obj['actor']=f'Preview.{label}';obj['moved']=False
                    if obj.get('prefab'):obj['prefab']=f"copy{index}:{obj['prefab']}"
                    obj['partner']=None;attach(obj,None,extra)
                    objects.append(obj)
        elif kind=='copy':
            pivot=op.get('pivot',[0,0,0]);scale=vector(extra['CopyScale']) if 'CopyScale' in extra else [1,1,1]
            if yaw%90:note(index,f'patchtool refuses a copy turned by {yaw} degrees (only multiples of 90)');continue
            building=None
            if 'building' in op:
                building=f'copy-{index}';building_ids[index]=building
                floors=[]
                for fi,names in enumerate(op['building']['floors']):
                    sources=[f for b in base.get('buildings',[]) for f in b['floors'] if any(v.split('.')[-1] in names for v in f['volumes'])]
                    floors.append(dict(index=fi,volumes=names,bottom=min((f['bottom'] for f in sources if f['bottom'] is not None),default=0)+dest[2]-pivot[2],
                                       top=max((f['top'] for f in sources if f['top'] is not None),default=0)+dest[2]-pivot[2],members=[]))
                out.setdefault('buildings',[]).append(dict(id=building,name=f"XComBuildingVolume_{spec.get('nameBase',900)+index}0",floors=floors))
            elif 'inBuilding' in op:building=building_ids.get(op['inBuilding'])
            for source in op.get('from',[]):
                if source not in original:note(index,f'No rendered source for {source} (may require skeletal support)');continue
                if original[source][0]['actorClass'] not in COPYABLE:
                    note(index,f"The copier can't copy {source} ({original[source][0]['actorClass']})");continue
                for si,src in enumerate(original[source]):
                    moved=src['actorClass'] in ('XComInteractiveLevelActor','XComLadder') and extra.get('bCopyDoors' if src['actorClass']=='XComInteractiveLevelActor' else 'bCopyLadders','False').lower()!='true'
                    obj=src if moved else copy.deepcopy(src)
                    offset=turn([src['location'][k]-pivot[k] for k in range(3)],yaw)
                    rot=list(src['rotation']);rot[1]+=int(yaw*65536/360)
                    # CopyScale scales copies only: the copier moves a door or ladder as it is.
                    place(obj,[dest[k]+offset[k] for k in range(3)],rot,list(src['scale']) if moved else [src['scale'][k]*scale[k] for k in range(3)])
                    obj['provenance']=dict(operation=index,type='move' if moved else 'copy',sourceActor=src['actor'])
                    obj['moved']=moved;attach(obj,building,extra)
                    if not moved:
                        obj['id']=f'copy:{index}:{source}:{si}';obj['actor']=f'Preview.{source}_copy{index}'
                        # Copies link only to copies made by the same operation, never to the originals.
                        if obj.get('prefab'):obj['prefab']=f"copy{index}:{obj['prefab']}"
                        partner=(obj.get('partner') or '').split('.')[-1]
                        obj['partner']=f'Preview.{partner}_copy{index}' if partner in op.get('from',[]) else None
                        objects.append(obj)
        elif kind=='hide' and op.get('exact'):
            # Exact targets (the editor's compiler): only the base map's actors named in alsoHide, wherever they stand.
            for name in op.get('alsoHide',[]):
                parts=[p for p in original.get(name,[]) if p.get('layer','base')=='base' and not p.get('moved')]
                if not parts:note(index,f'No base-map actor {name} to hide');continue
                for obj in parts:obj['hidden']=True;obj['hiddenBy']=index
        elif kind=='hide':
            half=op.get('half',[HIDE_HALF]*3);half=[half]*3 if isinstance(half,(int,float)) else half
            lo=[dest[k]-half[k] for k in range(3)];hi=[dest[k]+half[k] for k in range(3)]
            keep=set(op.get('keep',[]));also=set(op.get('alsoHide',[]));ground=float(extra.get('KeepGroundHeight',40))
            for (_,name),parts in hide_sources.items():
                if name in keep or any(p.get('moved') for p in parts):continue
                if all(p['actorClass'].endswith('Volume') for p in parts):continue
                boxes=[bounds(p,out['meshes']) for p in parts]
                amin=[min(b[0][k] for b in boxes) for k in range(3)];amax=[max(b[1][k] for b in boxes) for k in range(3)]
                center=[(amin[k]+amax[k])/2 for k in range(3)]
                if name not in also and (not all(lo[k]<=center[k]<=hi[k] for k in range(3)) or amax[2]<lo[2]+ground):continue
                for obj in parts:obj['hidden']=True;obj['hiddenBy']=index
            # XComMapEdHider: a light is taken (switched off) only with bHideLights, by its location
            # or by name in alsoHide; the map's sun and sky light count as lights too. Like every
            # XComMapEd class, a patch's own sun is never taken.
            if extra.get('bHideLights','False').lower()=='true':
                for light in out.get('lights',[]):
                    name=light['actor'].split('.')[-1]
                    if light['layer']=='patch' or light.get('hiddenBy') is not None or name in keep:continue
                    if name in also or all(lo[k]<=light['location'][k]<=hi[k] for k in range(3)):
                        light['enabled']=False;light['hiddenBy']=index
        elif kind in ('spawn','ladder'):
            if kind=='ladder':
                mesh_name=op.get('mesh','LadderMetal.Meshes.LadderMetalA_448')
                main=[copy.deepcopy(o) for o in base['objects'] if base['meshes'][o['mesh']]['name']==mesh_name][:1]
                partner=[]
            else:
                main=template_provider(op['archetype']) if template_provider else []
                partner=template_provider(op['partner']) if op.get('partner') and template_provider else []
            if not main:note(index,f'No supported visual template for {kind}');continue
            parts=[]
            for group,offset in [(main,[0,0,0]),(partner,op.get('partnerOffset',[0,0,0]))]:
                offset=turn(offset,yaw)
                for src in group:
                    obj=copy.deepcopy(src)
                    scale=vector(extra['DrawScale3D']) if 'DrawScale3D' in extra else obj['scale']
                    place(obj,[dest[k]+offset[k] for k in range(3)],[0,int(yaw*65536/360),0],scale)
                    obj['id']=f'{kind}:{index}:{len(parts)}';obj['actor']=f'Preview.{kind}_{index}_{len(parts)}'
                    obj['provenance']=dict(operation=index,type=kind,sourceActor=src['actor'])
                    obj['prefab']=f'{kind}{index}';obj['partner']=None   # a spawned body and its partner move together
                    obj['hidden']=op.get('hidden',kind=='ladder');obj['floors']=[]
                    if 'tint' in op:obj['tint']=op['tint']
                    b=next((b['id'] for b in out.get('buildings',[]) if b['name']==extra.get('BuildingName')),None)
                    attach(obj,b,extra);parts.append(obj)
            if extra.get('bSnapToTiles','False').lower()=='true':
                shift=snap(parts[:len(main)],out['meshes'],spec.get('map',{}).get('origin',[0,0]),yaw)
                if shift:
                    for obj in parts:place(obj,[obj['location'][k]+shift[k] for k in range(3)],obj['rotation'],obj['scale'])
            objects.extend(parts)
        elif kind in ('sun','photo'):
            # Both place an XComMapEdSun: patchtool's sun object, or the one the photo object spawns.
            fields=('sun','sky','yaw','pitch') if kind=='sun' else ('sun','sky','sunYaw','sunPitch')
            sun,sky,sun_yaw,sun_pitch=[float(op.get(f,d)) for f,d in zip(fields,(1.2,0.5,138,50))]
            for light in sun_records(f'{kind}:{index}',sun,sky,sun_yaw,sun_pitch):
                light['provenance']=dict(operation=index,type=kind)
                out.setdefault('lights',[]).append(light)
        elif kind=='volume':pass
        else:note(index,f'Unsupported operation type {kind}')
    out['name']=spec.get('map',{}).get('shipAs') or spec.get('name','Patch preview')
    out['scope']='map';out['preview']=dict(experimental=True,spec=spec.get('name'),notes=notes,gameVerified=False)
    out['diagnostics'].extend(notes)
    return out
