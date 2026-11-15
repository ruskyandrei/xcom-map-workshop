"""Checked EW skeletal LOD-0 reader, retaining reference bones and skin weights."""
import math
import struct
from package import FormatError
from mesh import bulk


def read_skeletal(p,index):
    r=p.native(index)
    bounds=list(r.unpack('7f'))
    materials=list(r.unpack(f'{r.count()}i'))
    origin=list(r.unpack('3f'));rotation=list(r.unpack('3i'))
    bones=[]
    for i in range(r.count()):
        name=p.fname(r);r.u32();q=list(r.unpack('4f'));pos=list(r.unpack('3f'))
        children,parent=r.unpack('2i');r.take(4)
        if (i and not 0<=parent<i) or not all(math.isfinite(v) for v in q+pos):
            raise FormatError('Invalid reference skeleton')
        bones.append(dict(name=name,parent=parent,position=pos,quaternion=q))
    if not bones:raise FormatError('Skeletal mesh has no reference bones')
    r.i32();lods=r.count()
    if not 1<=lods<=16:raise FormatError('Invalid skeletal LOD count')
    sections=[]
    for _ in range(r.count()):
        slot,chunk,first,triangles,sorting=r.unpack('hhiIB')
        if not 0<=slot<len(materials):raise FormatError('Invalid skeletal material slot')
        sections.append(dict(slot=slot,chunk=chunk,first=first,count=triangles*3,material=materials[slot],fragments=[]))
    r.u32();index_size=r.take(1)[0]
    stride,ni,raw_indices=r.array_bytes()
    if index_size!=stride or stride not in (2,4):raise FormatError('Invalid skeletal index buffer')
    indices=list(struct.unpack(f'<{ni}{"H" if stride==2 else "I"}',raw_indices))
    r.take(r.count()*2)  # active bones
    chunks=[]
    for _ in range(r.count()):
        first=r.u32()
        r.take(r.count()*61)  # optional CPU rigid vertices
        r.take(r.count()*64)  # optional CPU soft vertices
        bone_map=list(r.unpack(f'{r.count()}h'))
        rigid,soft,influences=r.unpack('3i')
        if min(rigid,soft)<0 or not 0<=influences<=4 or any(not 0<=b<len(bones) for b in bone_map):
            raise FormatError('Invalid skeletal chunk')
        chunks.append(dict(first=first,count=rigid+soft,bones=bone_map))
    r.u32();nv=r.u32();r.take(r.count());bulk(r)
    channels=r.u32();uv_channels,full,packed_hint=r.unpack('3I')
    extension=list(r.unpack('3f'));mesh_origin=list(r.unpack('3f'))
    stride,count,vertices=r.array_bytes()
    if channels!=uv_channels or not 1<=channels<=4 or nv!=count or not nv:
        raise FormatError('Skeletal GPU vertex counts disagree')
    uv_size=8 if full else 4
    # EW sets the packed-position hint even when the actual bulk stride contains
    # float XYZ. Validate storage by stride; never reinterpret float bits as 11:11:10.
    float_positions=stride==28+channels*uv_size
    if not float_positions:raise FormatError(f'Unsupported skeletal vertex stride {stride}')
    joints=[None]*nv
    for chunk in chunks:
        for vi in range(chunk['first'],chunk['first']+chunk['count']):
            if vi>=nv or joints[vi] is not None:raise FormatError('Overlapping/out-of-range skin chunk')
            base=vi*stride;local=vertices[base+8:base+12];weights=vertices[base+12:base+16]
            if sum(weights)!=255:raise FormatError('Skin weights do not sum to 255')
            if any(w and b>=len(chunk['bones']) for b,w in zip(local,weights)):
                raise FormatError('Skin index outside chunk bone map')
            joints[vi]=[chunk['bones'][b] if w else 0 for b,w in zip(local,weights)]
    if any(j is None for j in joints):raise FormatError('Skin chunks do not cover GPU vertices')
    if any(v>=nv for v in indices):raise FormatError('Skeletal index outside vertex buffer')
    for section in sections:
        if section['first']<0 or section['first']+section['count']>ni or not 0<=section['chunk']<len(chunks):
            raise FormatError('Skeletal section outside buffers')
    mesh=dict(name=p.name(index),bounds=bounds,version=845,lods=lods,positions=[],normals=[],tangents=[],
              uvs=[[] for _ in range(channels)],colors=[],indices=indices,sections=sections,
              bones=bones,joints=[],weights=[],origin=origin,rotOrigin=rotation,
              packedPositionHint=bool(packed_hint),positionStorage='float32',lod0End=r.pos,exportEnd=r.end)
    for i in range(nv):
        base=i*stride
        pos=struct.unpack_from('<3f',vertices,base+16)
        if not all(math.isfinite(v) for v in pos):raise FormatError('Nonfinite skeletal vertex')
        mesh['positions'].extend((pos[0],pos[2],pos[1]))
        tangent=[(v-127.5)/127.5 for v in vertices[base:base+4]]
        normal=[(v-127.5)/127.5 for v in vertices[base+4:base+8]]
        mesh['normals'].extend((normal[0],normal[2],normal[1]))
        mesh['tangents'].extend((tangent[0],tangent[2],tangent[1],-normal[3]))
        mesh['joints'].extend(joints[i]);mesh['weights'].extend(v/255 for v in vertices[base+12:base+16])
        for channel in range(channels):
            mesh['uvs'][channel].extend(struct.unpack_from('<2f' if full else '<2e',vertices,base+28+channel*uv_size))
    # Positions are already in reference mesh space. Origin/RotOrigin are import
    # metadata, not an additional component transform (bounds verify this).
    return mesh


def bone_matrix(bone):
    x,y,z,w=bone['quaternion'];length=math.sqrt(x*x+y*y+z*z+w*w)
    if length<1e-8:raise FormatError('Zero reference-bone quaternion')
    x,y,z,w=-x/length,-z/length,-y/length,w/length
    px,pz,py=bone['position']
    return [[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),px],
            [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),py],
            [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y),pz], [0,0,0,1]]


def inverse_rigid(matrix):
    out=[[matrix[j][i] for j in range(3)]+[0] for i in range(3)]+[[0,0,0,1]]
    for i in range(3):out[i][3]=-sum(out[i][j]*matrix[j][3] for j in range(3))
    return out
