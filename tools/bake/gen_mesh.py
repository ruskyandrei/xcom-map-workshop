"""A cooked StaticMesh's or FracturedStaticMesh's native data as numbers, and the same numbers written back
(private/plans/todo/custom-geometry-implementation-plan.md, section 0, stage F1).

read(p, index) gives the native data after the tagged properties as a dict of plain values; write(mesh, at) gives
its bytes again, `at` being the logical offset its first byte will have (the raw triangles' empty inline bulk record
points just past itself). For every static and fracturing mesh of the game's maps, write(read(...)) is the export's
own native data, byte for byte (tests/test_gen_mesh.py, the oracle). A generated mesh (frac_wall.py) is such a dict
made from numbers and written the same way.

The layout is the one tools/viewer/mesh.py and tools/upk/native_fields.py read; here every value is kept:

  bounds          the box-sphere bounds: origin, extent, radius (7 floats)
  bodySetup       the RB_BodySetup export (or 0)
  kdop            the triangle collision tree: root box [min x y z, max x y z], nodes (6 bytes each, bytes), triangles
                  [(a, b, c, value)] (kdop_tree builds one)
  version         the mesh's internal version (18 in every cooked mesh)
  optimisation    the optimisation settings, 7 bytes each (none in cooked meshes)
  simplified      bHasBeenSimplified
  lods            each LOD: its sections, its streams and index buffers (lod_read)
  tail            the LOD info count, the thumbnail's angle and distance, the high-resolution source's name, its CRC,
                  the lighting GUID, the vertex positions version, the streaming texture factors, remove degenerates

and a fracturing mesh's own after it (fractured): the mesh it was sliced from (a reference, 0 in cooked data), its
fragments, the core fragment, the interior section, the core mesh's scale, offset, rotation and plane bias, and two
build versions.

A section: material (an object reference, 0 in the game's fracturing meshes: their component's Materials bind them),
collision, oldCollision, shadow (UBOOLs), first (its first index), triangles, minVertex, maxVertex, slot (the material
index), fragments ([(first index, triangles)] per fragment, a fracturing mesh's), platform (0).

A vertex of the vertex stream: tangent (4 bytes: x, y, z packed, w), normal (4 bytes: x, y, z, the binormal's sign in
w), uvs [(u, v)] per channel (half floats, or full floats when fullUVs). Positions are float triples; colours are 4
bytes each (B, G, R, A); indices are numbers. The streams' element sizes and counts are written as read, so an empty
stream keeps the stride it was saved with.

The triangle collision tree (kdop) is read and written as it is. kdop_tree() makes one for new triangles: a tree the
game reads safely, whose nodes leave each child the whole of its parent's box (see its notes, and F0's audit).
"""
import math
import struct

HULL_ARRAYS = 6     # a fragment's convex hull: vertices, permuted vertices, face triangles, edge directions, face
#                     normals, face planes (all empty in the game's cooked meshes, native_fields._fragment)


class MeshError(ValueError):
    """Native data that doesn't read as a static or fracturing mesh."""


class _R:
    def __init__(self, data, pos, end):
        self.d, self.pos, self.end = data, pos, end

    def take(self, n):
        if n < 0 or self.pos + n > self.end:
            raise MeshError('a read of %d bytes past the end at %d' % (n, self.pos))
        b = bytes(self.d[self.pos:self.pos + n])
        self.pos += n
        return b

    def unpack(self, fmt):
        return struct.unpack('<' + fmt, self.take(struct.calcsize('<' + fmt)))

    def i32(self):
        return self.unpack('i')[0]

    def u32(self):
        return self.unpack('I')[0]

    def count(self):
        n = self.i32()
        if not 0 <= n <= 50_000_000:
            raise MeshError('a count of %d at %d' % (n, self.pos - 4))
        return n

    def array(self):
        """(stride, count, bytes) of an array saved with its element size first; a stride of 0 saves no count."""
        stride = self.count()
        if not stride:
            return 0, None, b''
        n = self.count()
        return stride, n, self.take(stride * n)


def _array(stride, n, data):
    if not stride:
        return struct.pack('<i', 0)
    return struct.pack('<ii', stride, n) + data


# -- reading ---------------------------------------------------------------------------------------------------------
def lod_read(r):
    flags, count, size, offset = r.unpack('4i')
    if flags & 1 or size or count:
        raise MeshError('a LOD whose raw triangles are not an empty inline record')
    if offset != r.pos:
        raise MeshError('the raw triangles\' record points to %d, not past itself (%d)' % (offset, r.pos))
    sections = []
    for _ in range(r.count()):
        material, collision, old, shadow, first, triangles, lo, hi, slot = r.unpack('4i4Ii')
        fragments = [tuple(r.unpack('2i')) for _ in range(r.count())]
        platform = r.take(1)[0]
        if platform:
            raise MeshError('a section with platform data')
        sections.append(dict(material=material, collision=collision, oldCollision=old, shadow=shadow, first=first,
                             triangles=triangles, minVertex=lo, maxVertex=hi, slot=slot, fragments=fragments,
                             platform=platform))
    head = r.unpack('2I')
    stride, n, raw = r.array()
    if stride not in (0, 12) or (n or 0) != head[1] or (stride and head[0] != stride):
        raise MeshError('a position stream that disagrees with its header')
    positions = [struct.unpack_from('<3f', raw, 12 * k) for k in range(n or 0)]
    texcoords, vstride, vn, full = r.unpack('4I')
    stride, n, raw = r.array()
    uv = 8 if full else 4
    if (n or 0) != vn or (stride and stride != vstride) or (vn and vstride != 8 + texcoords * uv):
        raise MeshError('a vertex stream that disagrees with its header')
    vertices = []
    for k in range(n or 0):
        base = k * vstride
        uvs = [struct.unpack_from('<2f' if full else '<2e', raw, base + 8 + c * uv) for c in range(texcoords)]
        vertices.append((raw[base:base + 4], raw[base + 4:base + 8], uvs))
    colour_head = r.unpack('2I')
    colours, colour_array = None, None
    if colour_head[1]:
        stride, n, raw = r.array()
        colour_array = (stride, n)
        colours = [raw[4 * k:4 * k + 4] for k in range(n)]
    vertex_count = r.u32()
    streams = []
    for _ in range(3):                         # indices, wireframe indices, adjacency indices
        stride, n, raw = r.array()
        if stride not in (0, 2, 4):
            raise MeshError('an index buffer of %d-byte indices' % stride)
        streams.append((stride, list(struct.unpack('<%d%s' % (n, 'H' if stride == 2 else 'I'), raw)) if n else []))
    return dict(sections=sections, positionHead=list(head), positionStride=12 if positions or head[0] == 12 else 0,
                positions=positions, texcoords=texcoords, vertexStride=vstride, fullUVs=full, vertexHead=vn,
                vertices=vertices, colourHead=list(colour_head), colourArray=colour_array, colours=colours,
                vertexCount=vertex_count, indices=streams[0], wireframe=streams[1], adjacency=streams[2])


def _fstring(r):
    n = r.i32()
    return n, r.take(n if n >= 0 else -2 * n)


def _fragment(r, fragments):
    centre = r.unpack('3f')
    for _ in range(HULL_ARRAYS):
        if r.count():
            raise MeshError('a fragment with a convex hull')
    box = r.unpack('6f') + (r.take(1)[0],)
    bounds = r.unpack('7f')
    neighbours = list(r.unpack('%di' % r.count()))
    destroyable, root, never_spawn = r.unpack('3i')
    normal = r.unpack('3f')
    n = r.count()
    if n != len(neighbours):
        raise MeshError('a fragment with other counts of neighbours and shared faces')
    dims = list(r.unpack('%df' % n))
    extra = r.i32()
    if not all(-1 <= x < fragments for x in neighbours) or not -1 <= extra < fragments:
        raise MeshError('a fragment index out of range')
    return dict(centre=centre, box=box, bounds=bounds, neighbours=neighbours, destroyable=destroyable, root=root,
                neverSpawn=never_spawn, normal=normal, dims=dims, extra=extra)


def read_native(data, pos, end, fractured=False):
    """The native data data[pos:end] of a static (or, with `fractured`, a fracturing) mesh as numbers; `pos` is the
    logical offset of its first byte (the package's data being the uncompressed package)."""
    r = _R(data, pos, end)
    m = dict(kind='fractured' if fractured else 'static')
    m['bounds'] = r.unpack('7f')
    m['bodySetup'] = r.i32()
    root = r.unpack('6f')
    stride, n, nodes = r.array()
    if stride not in (0, 6):
        raise MeshError('collision tree nodes of %d bytes' % stride)
    tstride, tn, tris = r.array()
    if tstride not in (0, 8):
        raise MeshError('collision triangles of %d bytes' % tstride)
    m['kdop'] = dict(root=root, nodeStride=stride, nodes=nodes, triangleStride=tstride,
                     triangles=[struct.unpack_from('<4H', tris, 8 * k) for k in range(tn or 0)])
    m['version'], source = r.unpack('2i')
    if source:
        raise MeshError('uncooked mesh source data')
    m['optimisation'] = [r.take(7) for _ in range(r.count())]
    m['simplified'] = r.i32()
    lods = r.count()
    if not 1 <= lods <= 16:
        raise MeshError('%d LODs' % lods)
    m['lods'] = [lod_read(r) for _ in range(lods)]
    info = r.count()
    thumb = r.take(16)
    name = _fstring(r)
    crc = r.u32()
    guid = r.take(16)
    vpv = r.i32()
    factors = list(r.unpack('%df' % r.count()))
    degenerates = r.i32()
    m['tail'] = dict(lodInfo=info, thumbnail=thumb, source=name, crc=crc, guid=guid, positionsVersion=vpv,
                     factors=factors, removeDegenerates=degenerates)
    if fractured:
        f = dict(sourceMesh=r.i32())
        count = r.count()
        f['fragments'] = [_fragment(r, count) for _ in range(count)]
        f['core'] = r.i32()
        f['interior'] = r.i32()
        f['coreScale'] = r.unpack('3f')
        f['coreOffset'] = r.unpack('3f')
        f['coreRotation'] = r.unpack('3i')
        f['planeBias'] = r.unpack('3f')
        f['versions'] = r.unpack('2H')
        m['fractured'] = f
    if r.pos != end:
        raise MeshError('%d bytes left after the mesh' % (end - r.pos))
    return m


def read(p, index):
    """Export `index` of the viewer Package `p` (a StaticMesh or a FracturedStaticMesh): read_native of its native
    data, with `at` (the data's logical offset) and `start` (where the native data begins in the export's data)."""
    cls = p.cls(index)
    if cls not in ('StaticMesh', 'FracturedStaticMesh'):
        raise MeshError('%s is a %s' % (p.name(index), cls))
    e = p.exports[index - 1]
    pos = p.properties(index)[1]
    m = read_native(p.data, pos, e['off'] + e['size'], fractured=cls == 'FracturedStaticMesh')
    m['at'], m['start'] = pos, pos - e['off']
    return m


# -- writing ---------------------------------------------------------------------------------------------------------
def lod_write(lod, at):
    out = bytearray(struct.pack('<4i', 0, 0, 0, at + 16))
    out += struct.pack('<i', len(lod['sections']))
    for s in lod['sections']:
        out += struct.pack('<4i4Ii', s['material'], s['collision'], s['oldCollision'], s['shadow'], s['first'],
                           s['triangles'], s['minVertex'], s['maxVertex'], s['slot'])
        out += struct.pack('<i', len(s['fragments'])) + b''.join(struct.pack('<2i', *f) for f in s['fragments'])
        out += bytes([s.get('platform', 0)])
    positions = lod['positions']
    out += struct.pack('<2I', *lod['positionHead'])
    out += _array(lod['positionStride'] if positions or lod['positionStride'] else 0, len(positions),
                  b''.join(struct.pack('<3f', *v) for v in positions))
    full = lod['fullUVs']
    vstride = lod['vertexStride']
    out += struct.pack('<4I', lod['texcoords'], vstride, lod['vertexHead'], full)
    raw = bytearray()
    for tangent, normal, uvs in lod['vertices']:
        raw += tangent + normal
        for uv in uvs:
            raw += struct.pack('<2f' if full else '<2e', *uv)
    out += _array(vstride if lod['vertices'] or vstride else 0, len(lod['vertices']), bytes(raw))
    out += struct.pack('<2I', *lod['colourHead'])
    if lod['colourHead'][1]:
        stride, n = lod['colourArray']
        out += _array(stride, n, b''.join(lod['colours']))
    out += struct.pack('<I', lod['vertexCount'])
    for stride, values in (lod['indices'], lod['wireframe'], lod['adjacency']):
        fmt = 'H' if stride == 2 else 'I'
        out += _array(stride, len(values), struct.pack('<%d%s' % (len(values), fmt), *values) if stride else b'')
    return bytes(out)


def write(m, at):
    """The native data of mesh `m` (read()'s form), its first byte at logical offset `at`."""
    out = bytearray(struct.pack('<7f', *m['bounds']))
    out += struct.pack('<i', m['bodySetup'])
    k = m['kdop']
    out += struct.pack('<6f', *k['root'])
    out += _array(k['nodeStride'], len(k['nodes']) // 6 if k['nodeStride'] else 0, k['nodes'])
    out += _array(k['triangleStride'], len(k['triangles']),
                  b''.join(struct.pack('<4H', *t) for t in k['triangles']))
    out += struct.pack('<2i', m['version'], 0)
    out += struct.pack('<i', len(m['optimisation'])) + b''.join(m['optimisation'])
    out += struct.pack('<i', m['simplified'])
    out += struct.pack('<i', len(m['lods']))
    for lod in m['lods']:
        out += lod_write(lod, at + len(out))
    t = m['tail']
    out += struct.pack('<i', t['lodInfo']) + t['thumbnail']
    out += struct.pack('<i', t['source'][0]) + t['source'][1]
    out += struct.pack('<I', t['crc']) + t['guid'] + struct.pack('<i', t['positionsVersion'])
    out += struct.pack('<i', len(t['factors'])) + struct.pack('<%df' % len(t['factors']), *t['factors'])
    out += struct.pack('<i', t['removeDegenerates'])
    f = m.get('fractured')
    if f is not None:
        out += struct.pack('<i', f['sourceMesh'])
        out += struct.pack('<i', len(f['fragments']))
        for g in f['fragments']:
            out += struct.pack('<3f', *g['centre']) + struct.pack('<i', 0) * HULL_ARRAYS
            out += struct.pack('<6f', *g['box'][:6]) + bytes([g['box'][6]])
            out += struct.pack('<7f', *g['bounds'])
            out += struct.pack('<i', len(g['neighbours'])) + struct.pack('<%di' % len(g['neighbours']), *g['neighbours'])
            out += struct.pack('<3i', g['destroyable'], g['root'], g['neverSpawn'])
            out += struct.pack('<3f', *g['normal'])
            out += struct.pack('<i', len(g['dims'])) + struct.pack('<%df' % len(g['dims']), *g['dims'])
            out += struct.pack('<i', g['extra'])
        out += struct.pack('<ii', f['core'], f['interior'])
        out += struct.pack('<3f', *f['coreScale']) + struct.pack('<3f', *f['coreOffset'])
        out += struct.pack('<3i', *f['coreRotation']) + struct.pack('<3f', *f['planeBias'])
        out += struct.pack('<2H', *f['versions'])
    return bytes(out)


# -- the triangle collision tree ---------------------------------------------------------------------------------------
MAX_LEAF = 5        # the most triangles a leaf holds (F0: the node count rule over the install's meshes)
WHOLE = bytes([128] * 6)    # a node that leaves both children the whole of its parent's box
# What the six bytes of a node are (F0, read from the game's meshes): the tree is complete and implicit, node k's
# children are 2k + 1 and 2k + 2, and the leaves (node count of them, each a run of triangles) have no entry; the
# last entry is padding (zero). Each byte is a signed step (its value less 128) of 1/127 of the parent's extent on
# one axis: the first three move one child's low side in (a step below 0 the second child's, above 0 the first's),
# the last three one child's high side (above 0 the first child's, below 0 the second's), and 128 moves nothing.
# Exactly how the cooker rounds is not pinned (F0), so the tree made here moves nothing: sound for any line check,
# with no culling below the root box.


def node_count(triangles):
    """The entries of the tree of `triangles` triangles: the smallest power of two, at least 1, with no more than
    MAX_LEAF triangles a leaf (the rule every mesh of the game follows, F0); none for none."""
    if not triangles:
        return 0
    n = 1
    while triangles > MAX_LEAF * n:
        n *= 2
    return n


def kdop_tree(positions, triangles):
    """dict(root, nodeStride, nodes, triangleStride, triangles) for `triangles` [(a, b, c, value)] over `positions`
    [(x, y, z)]: the root box is the triangles' corners' box (as float32, as the cooked roots are), the triangles keep
    their order, and every node is WHOLE (padding last)."""
    used = sorted({i for t in triangles for i in t[:3]})
    lo = [min(positions[i][a] for i in used) for a in range(3)]
    hi = [max(positions[i][a] for i in used) for a in range(3)]
    root = struct.unpack('<6f', struct.pack('<6f', *lo, *hi))
    n = node_count(len(triangles))
    nodes = WHOLE * (n - 1) + bytes(6) if n > 1 else bytes(6)
    return dict(root=root, nodeStride=6, nodes=nodes, triangleStride=8, triangles=[tuple(t) for t in triangles])


def kdop_value(slot, fragment, fragments):
    """A fracturing mesh's collision triangle's fourth value: its section's slot times the fragment count, plus its
    fragment (F0: every collision triangle of the game's fracturing meshes). A static mesh's is its section's slot."""
    return slot * fragments + fragment if fragments else slot


def bounds_of(positions):
    """The box-sphere bounds (origin, extent, radius) of `positions`, as the cooked meshes save them: the box's
    centre and half size, and the radius of the farthest point from the centre."""
    lo = [min(p[a] for p in positions) for a in range(3)]
    hi = [max(p[a] for p in positions) for a in range(3)]
    centre = [(a + b) / 2 for a, b in zip(lo, hi)]
    half = [(b - a) / 2 for a, b in zip(lo, hi)]
    radius = max(math.dist(p, centre) for p in positions)
    return tuple(struct.unpack('<7f', struct.pack('<7f', *centre, *half, radius)))
