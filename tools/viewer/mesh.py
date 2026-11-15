"""LOD-0 EW mesh reader. All offsets are checked against the export boundary."""
import math
import struct
from package import FormatError


def bulk(r):
    flags, count, size, offset = r.unpack("4i")
    if size < 0 and not flags & 32:
        raise FormatError("Negative live bulk payload")
    data = b"" if flags & 1 else r.take(max(0, size))
    return dict(flags=flags, count=count, size=size, offset=offset, data=data)


def read_mesh(p, index):
    r = p.native(index)
    bounds = list(r.unpack("7f"))
    r.i32()  # BodySetup reference
    r.take(24)  # compact KDOP root bounds
    r.array_bytes()  # quantized nodes
    r.array_bytes()  # collision triangles
    version, source_data = r.unpack("2i")
    if source_data: raise FormatError("Uncooked mesh source data is not supported")
    r.take(r.count() * 7)  # optimization settings
    r.i32()  # simplified
    lod_count = r.count()
    if not 1 <= lod_count <= 16: raise FormatError(f"Invalid LOD count {lod_count}")
    raw = bulk(r)
    if raw["size"]: raise FormatError("Unexpected cooked raw-triangle payload")
    sections = []
    for _ in range(r.count()):
        mat, collision, old_collision, shadow, first, triangles, lo, hi, slot = r.unpack("4i4Ii")
        fragments = [list(r.unpack("2i")) for _ in range(r.count())]
        if r.take(1)[0]: raise FormatError("Unsupported platform mesh section")
        sections.append(dict(material=mat, first=first, count=triangles * 3,
                             slot=slot, fragments=fragments))
    pos_stride, nv = r.unpack("2I")
    stride, count, positions = r.array_bytes()
    if stride != pos_stride or count != nv or stride != 12 or not nv:
        raise FormatError("Invalid position stream")
    texcoords, vertex_stride, vn, full_uv = r.unpack("4I")
    stride, count, vertices = r.array_bytes()
    if count != nv or vn != nv or stride != vertex_stride:
        raise FormatError("Vertex stream counts disagree")
    uv_bytes = 8 if full_uv else 4
    if not 1 <= texcoords <= 8 or stride != 8 + texcoords * uv_bytes:
        raise FormatError(f"Unsupported vertex layout {stride}/{texcoords}/{full_uv}")
    color_stride, color_count = r.unpack("2I")
    colors = None
    if color_count:
        cs, cn, colors = r.array_bytes()
        if cs != 4 or cn != color_count or color_stride != 4:
            raise FormatError("Invalid colour stream")
        # The stream is indexed by vertex, so a longer one is read as far as the vertices go (FX_Cloth.Flags.Flag_B
        # in URB_FastFood holds 180 colours for 90 vertices: the 90, twice over). A shorter one can't colour them all.
        if cn < nv: raise FormatError("Colour stream shorter than the vertex stream")
        colors = colors[:nv * 4]
    if r.u32() != nv: raise FormatError("LOD vertex count mismatch")
    element_size, ni, indices = r.array_bytes()
    if element_size not in (2, 4): raise FormatError("Unsupported index size")
    ids = list(struct.unpack(f"<{ni}{'H' if element_size == 2 else 'I'}", indices))
    if any(i >= nv for i in ids): raise FormatError("Index outside vertex stream")
    out = dict(name=p.name(index), bounds=bounds, version=version, lods=lod_count,
               positions=[], normals=[], tangents=[], uvs=[[] for _ in range(texcoords)],
               colors=[], indices=ids, sections=sections)
    for i in range(nv):
        x, y, z = struct.unpack_from("<3f", positions, i * 12)
        if not all(math.isfinite(v) for v in (x, y, z)): raise FormatError("Nonfinite vertex")
        out["positions"].extend((x, z, y))
        base = i * stride
        tangent = [(v - 127.5) / 127.5 for v in vertices[base:base + 4]]
        normal = [(v - 127.5) / 127.5 for v in vertices[base + 4:base + 8]]
        out["normals"].extend((normal[0], normal[2], normal[1]))
        out["tangents"].extend((tangent[0], tangent[2], tangent[1], -normal[3]))
        for channel in range(texcoords):
            u, v = struct.unpack_from("<2f" if full_uv else "<2e", vertices,
                                      base + 8 + channel * uv_bytes)
            out["uvs"][channel].extend((u, v))
        if colors:
            b, g, red, a = colors[i * 4:i * 4 + 4]
            out["colors"].extend((red / 255, g / 255, b / 255, a / 255))
    # UE3's source indices are clockwise. The Y/Z reflection changes them to
    # glTF's counterclockwise front faces; reversing again would turn them inward.
    if ni % 3: raise FormatError("Non-triangular index buffer")
    for s in sections:
        if s["first"] < 0 or s["first"] + s["count"] > ni:
            raise FormatError("Section outside index buffer")
        for first, triangles in s["fragments"]:
            if first < 0 or triangles < 0 or first + triangles * 3 > ni:
                raise FormatError("Fragment outside index buffer")
    out["lod0End"] = r.pos
    out["exportEnd"] = r.end
    return out


def write_glb(mesh, path):
    """Geometry only: effective UE materials are bound by the viewport."""
    import json
    blob = bytearray()
    views, accessors = [], []
    def attribute(data, fmt, component, kind, width, target):
        while len(blob) % 4: blob.append(0)
        offset = len(blob)
        blob.extend(struct.pack(f"<{len(data)}{fmt}", *data))
        view=dict(buffer=0,byteOffset=offset,byteLength=len(blob)-offset)
        if target is not None:view['target']=target
        views.append(view)
        item = dict(bufferView=len(views)-1, componentType=component, count=len(data)//width, type=kind)
        if kind == "VEC3":
            item["min"] = [min(data[k::3]) for k in range(3)]
            item["max"] = [max(data[k::3]) for k in range(3)]
        accessors.append(item)
        return len(accessors)-1
    attrs = {"POSITION": attribute(mesh["positions"], "f", 5126, "VEC3", 3, 34962),
             "NORMAL": attribute(mesh["normals"], "f", 5126, "VEC3", 3, 34962),
             "TANGENT": attribute(mesh["tangents"], "f", 5126, "VEC4", 4, 34962)}
    for i, uv in enumerate(mesh["uvs"]): attrs[f"TEXCOORD_{i}"] = attribute(uv, "f", 5126, "VEC2", 2, 34962)
    if mesh["colors"]: attrs["COLOR_0"] = attribute(mesh["colors"], "f", 5126, "VEC4", 4, 34962)
    if mesh.get('bones'):
        attrs['JOINTS_0']=attribute(mesh['joints'],'H',5123,'VEC4',4,34962)
        attrs['WEIGHTS_0']=attribute(mesh['weights'],'f',5126,'VEC4',4,34962)
    primitives = []
    for section in mesh["sections"]:
        if not section["count"]: continue
        ids = mesh["indices"][section["first"]:section["first"]+section["count"]]
        accessor = attribute(ids, "I", 5125, "SCALAR", 1, 34963)
        primitives.append(dict(attributes=attrs, indices=accessor,
                               extras=dict(materialSlot=section["slot"])))
    nodes=[dict(mesh=0)];skins=[]
    if mesh.get('bones'):
        from skeletal import bone_matrix,inverse_rigid
        from export_math import multiply
        nodes=[dict(children=[1,2]),dict(mesh=0,skin=0)]
        globals_=[];inverse=[]
        for i,bone in enumerate(mesh['bones']):
            local=bone_matrix(bone)
            global_=multiply(globals_[bone['parent']],local) if i else local
            globals_.append(global_)
            inv=inverse_rigid(global_)
            inverse.extend(inv[row][column] for column in range(4) for row in range(4))
            children=[2+j for j,b in enumerate(mesh['bones']) if j and b['parent']==i]
            node=dict(name=bone['name'],matrix=[local[row][column] for column in range(4) for row in range(4)])
            if children:node['children']=children
            nodes.append(node)
        accessor=attribute(inverse,'f',5126,'MAT4',16,None)
        skins=[dict(joints=list(range(2,2+len(mesh['bones']))),skeleton=2,inverseBindMatrices=accessor)]
    doc = dict(asset=dict(version="2.0", generator="XCOM map viewer"),
               buffers=[dict(byteLength=len(blob))], bufferViews=views, accessors=accessors,
               meshes=[dict(primitives=primitives)], nodes=nodes, scenes=[dict(nodes=[0])], scene=0)
    if skins:doc['skins']=skins
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    blob += b"\0" * (-len(blob) % 4)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, 28+len(js)+len(blob)) +
                     struct.pack("<I4s", len(js), b"JSON") + js +
                     struct.pack("<I4s", len(blob), b"BIN\0") + blob)
