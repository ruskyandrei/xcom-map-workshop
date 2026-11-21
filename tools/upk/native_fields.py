"""The names, object references and bulk-data records an export keeps after its tagged properties, in its native
data (private/plans/done/cross-map-assets-implementation-plan.md, X2).

Most classes are their tagged properties and nothing else, or native bytes that hold no number of the package
(PLAIN). The classes below keep some, each read by its layout:

  textures          the source-art bulk record; a 2D texture's mips, each a bulk record
  StaticMesh        its body setup, each LOD's raw-triangle bulk record and section materials
  fractured mesh    a StaticMesh's, and after them the mesh it was sliced from; its component's are a mesh component's
  Material          the textures its compiled shaders sample (and the expressions of its dependency map)
  material instance the same, of its own permutation, and its static parameters' names
  mesh components   each LOD's shadow maps and lightmap (texture references, or a vertex lightmap's owner and two
                    bulk records), EW's two mesh-swap records and their meshes
  SoundNodeWave     bulk records to the end
  SkeletalMesh      its materials, each bone's name (twice: the reference skeleton, the map of names to bone
                    numbers), each LOD's raw-point-index bulk record, its clothing assets
  DecalComponent    the component of each static receiver (an archetype's has none)
  Model             a brush's geometry (a volume's box): its owner, each surface's material and actor, each zone's
                    actor, its Polys
  Polys             its owner, and each polygon's actor, material and two names
  BrushComponent    nothing: its cached collision hulls (a blocking volume has them) are bytes

fields(p, index, start) gives [(offset, kind)] from the start of the export's data, `start` being where its tagged
properties end (typed_props.fields(...).end). A kind is 'name' (8 bytes: index, number), 'object' (4 bytes) or 'bulk'
(a 16-byte record: flags, element count, size, offset; when its payload lies in the export, right after the record,
the offset is the payload's absolute place in the package and must move with the export). Two more kinds mark what one
cook of a package writes differently from another and no renumbering explains, 'cook4' and 'cook16' (COOK: their
lengths): the last value of a material's compiled resource, and a 2D texture's cache GUID (a cubemap's faces, kept
whole in each package, get a new one in each). They stay as they are when an export is copied. A class with native bytes
that is neither mapped nor known to be plain raises Unmapped: there is no silent third case. `p` is a viewer Package.
"""
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'viewer'))
from package import FormatError, Reader  # noqa: E402

NAME, OBJECT, BULK = 'name', 'object', 'bulk'
COOK = {'cook4': 4, 'cook16': 16}
STORED_ELSEWHERE = 0x1          # a bulk record whose payload is in a texture cache (or nowhere): nothing to move


class NativeError(ValueError):
    """The native data of a mapped class doesn't read as its layout."""


class Unmapped(NativeError):
    """A class with native data that has no layout here and isn't known to be plain."""


class _Out:
    def __init__(self, p, index, start):
        e = p.exports[index - 1]
        self.p, self.index, self.off = p, index, e['off']
        self.r = Reader(p.data, e['off'] + start, e['off'] + e['size'])
        self.fields = []

    def at(self):
        return self.r.pos - self.off

    def obj(self):
        self.fields.append((self.at(), OBJECT))
        value = self.r.i32()
        try:
            self.p.name(value)
        except FormatError:
            raise NativeError('no object %d at %d' % (value, self.at() - 4)) from None
        return value

    def objs(self):
        return [self.obj() for _ in range(self.r.count())]

    def name(self):
        self.fields.append((self.at(), NAME))
        return self.p.fname(self.r)

    def bulk(self, b=None):
        """A bulk record (bulk_record's: read here, unless given) as a field. One whose payload is in the export must
        point to it, right after itself."""
        b = bulk_record(self.r) if b is None else b
        self.fields.append((b['at'] - self.off, BULK))
        if b['inline'] and b['offset'] != b['at'] + 16:
            raise NativeError('a bulk record at %d points to %d, not past itself' % (b['at'] - self.off, b['offset']))

    def objects(self, refs):
        """object_refs' record as fields: each reference after the count."""
        self.fields += [(refs['at'] + 4 + 4 * k - self.off, OBJECT) for k in range(len(refs['refs']))]

    def fstring(self):
        n = self.r.i32()
        self.r.take(n if n >= 0 else -2 * n)

    def done(self, what):
        if self.r.pos != self.r.end:
            raise NativeError('%s: %d bytes left of its native data' % (what, self.r.end - self.r.pos))


# -- textures ------------------------------------------------------------------------------------------------------
def _texture(o):
    o.bulk()                                    # source art (empty in cooked data)


def _mips(o):
    for _ in range(o.r.count()):
        o.bulk()
        o.r.take(8)                             # width, height


def _texture2d_body(o):
    _texture(o)
    _mips(o)
    o.fields.append((o.at(), 'cook16'))
    o.r.take(16)                                # the texture cache GUID
    _mips(o)                                    # cached PVRTC mips (none on PC)
    o.r.take(4)                                 # the largest cached Flash mip
    _mips(o)                                    # cached ATITC mips (none on PC)


def _texture2d(o):
    _texture2d_body(o)
    o.done('a 2D texture')


def _lightmap_texture(o):
    _texture2d_body(o)
    o.r.take(4)                                 # its lightmap flags
    o.done('a lightmap texture')


def _texture_only(o):
    _texture(o)
    o.done('a texture')


# -- meshes --------------------------------------------------------------------------------------------------------
def _static_lod(o):
    r = o.r
    o.bulk()                                    # raw triangles (empty in cooked data)
    for _ in range(r.count()):
        o.obj()                                 # the section's material
        r.take(32)
        r.take(r.count() * 8)                   # fragments
        if r.take(1)[0]:
            raise NativeError('a mesh section with platform data')
    stride, count = r.unpack('2I')
    if r.array_bytes()[:2] != (stride, count) and count:
        raise NativeError('a position stream that disagrees with its header')
    r.unpack('4I')
    r.array_bytes()
    _, colours = r.unpack('2I')
    if colours:
        r.array_bytes()
    r.u32()
    r.array_bytes()                             # indices
    r.array_bytes()                             # wireframe indices
    r.array_bytes()                             # adjacency indices


def _static_mesh_head(o):
    r = o.r
    r.take(28)                                  # bounds
    o.obj()                                     # body setup
    r.take(24)
    r.array_bytes()
    r.array_bytes()
    _, source = r.unpack('2i')
    if source:
        raise NativeError('uncooked mesh source data')
    r.take(r.count() * 7)
    r.i32()
    lods = r.count()
    if not 1 <= lods <= 16:
        raise NativeError('%d LODs' % lods)
    for _ in range(lods):
        _static_lod(o)
    return lods


def _static_mesh_tail(o, lods):
    r = o.r
    if r.count() != lods:                       # LOD info: a count, the entries are tagged properties
        raise NativeError('a LOD info count that is not the LOD count')
    r.take(16)                                  # thumbnail angle and distance
    o.fstring()                                 # the high-resolution source mesh's name
    r.take(4 + 16 + 4)                          # its CRC, the lighting GUID, the vertex position version
    r.take(r.count() * 4)                       # cached streaming texture factors
    r.take(4)                                   # remove degenerates


def _static_mesh(o):
    _static_mesh_tail(o, _static_mesh_head(o))
    o.done('a static mesh')


# -- materials -----------------------------------------------------------------------------------------------------
def _material_resource(o):
    r = o.r
    for _ in range(r.count()):
        o.fstring()                             # compile errors
    for _ in range(r.count()):                  # texture dependency lengths: expression, length
        o.obj()
        r.take(4)
    r.take(4 + 16 + 4)                          # the longest dependency, the material's ID, its UV count
    o.objs()                                    # the textures its uniform expressions sample
    r.take(24)
    r.take(r.count() * 16)
    r.take(4)
    if o.p.header['lic'] == 64:
        r.take(16)
        r.take(r.count() * 16)
        o.fields.append((o.at(), 'cook4'))
        r.take(4)


def _material(o):
    _material_resource(o)
    o.done('a material')


def _material_instance(o):
    if not o.p.own(o.index, 'bHasStaticPermutationResource', False):
        o.done('a material instance without a permutation of its own')
        return
    r = o.r
    _material_resource(o)
    r.take(16)                                  # the static parameter set's base material ID
    for _ in range(r.count()):                  # switches
        o.name()
        r.take(8 + 16)
    for _ in range(r.count()):                  # component masks
        o.name()
        r.take(16 + 4 + 16)
    for _ in range(r.count()):                  # normal parameters
        o.name()
        r.take(1 + 4 + 16)
    for _ in range(r.count()):                  # terrain layer weights
        o.name()
        r.take(4 + 4 + 16)
    o.done('a material instance')


# -- mesh components -----------------------------------------------------------------------------------------------
# The one reader of a mesh component's LOD records and of a bulk record (review finding 52): lighting_records (the
# Build's relight and copier, the editor's light records, the research census) and lightmap_fields (the relight's
# writes) take their values and places from these, and fields() here a component's references and bulk records. Each
# value comes with its absolute place in the package. A refusal is a FormatError (fields() makes it a NativeError).
def bulk_record(r):
    """A bulk-data record at the reader's place: dict(at (its place), flags, count, bytes (its size on disk), offset,
    inline). An inline payload (bit 0 of the flags clear: not in a separate file) follows the record and is passed
    over, so its size can't be negative; a record of a separate file can say -1 (a texture's unused mips do)."""
    at = r.pos
    flags, count, size, offset = r.unpack('4i')
    inline = not flags & STORED_ELSEWHERE
    if inline:
        r.take(size)
    return dict(at=at, flags=flags, count=count, bytes=size, offset=offset, inline=inline)


def object_refs(r, p):
    """A counted array of object references at the reader's place: dict(at (the count's place), refs); each names an
    object of `p`."""
    at = r.pos
    refs = list(r.unpack('%di' % r.count()))
    for ref in refs:
        p.name(ref)
    return dict(at=at, refs=refs)


def lightmap_record(r, p):
    """A LOD's lightmap at the reader's place: dict(offset, type: 0 none, 1 per vertex, 2 in textures). Types 1 and 2
    add lightGuidsOffset and lightGuids (hex): the lights baked into it. A vertex lightmap lies in the component's own
    data: its ownerOffset and owner (an object index), the bulk records of its directional samples
    (directionalSamples) and of its simple samples (simpleSamples), neither with a negative count or size, and the
    three scale vectors between them (scaleVectorsOffset, scaleVectors). A texture lightmap: its three slots
    [dict(textureOffset, index, scaleOffset, scale)], its coordinateScale and its coordinateBias, each with its
    offset."""
    out = dict(offset=r.pos)
    kind = out['type'] = r.i32()
    if kind == 0:
        return out
    if kind not in (1, 2):
        raise FormatError(f'Unknown lightmap type {kind}')
    n = r.count()
    out['lightGuidsOffset'] = r.pos
    out['lightGuids'] = [r.take(16).hex() for _ in range(n)]
    if kind == 1:
        out['ownerOffset'] = r.pos
        out['owner'] = r.i32()
        p.name(out['owner'])
        out['directionalSamples'] = _samples(r)
        out['scaleVectorsOffset'] = r.pos
        out['scaleVectors'] = [list(r.unpack('3f')) for _ in range(3)]
        out['simpleSamples'] = _samples(r)
        return out
    out['slots'] = []
    for _ in range(3):
        at = r.pos
        ref = r.i32()
        p.name(ref)
        out['slots'].append(dict(textureOffset=at, index=ref, scaleOffset=r.pos, scale=list(r.unpack('3f'))))
    out['coordinateScaleOffset'] = r.pos
    out['coordinateScale'] = list(r.unpack('2f'))
    out['coordinateBiasOffset'] = r.pos
    out['coordinateBias'] = list(r.unpack('2f'))
    return out


def _samples(r):
    b = bulk_record(r)
    if b['count'] < 0 or b['bytes'] < 0:
        raise FormatError('Negative bulk count or size')
    return b


def lod_record(r, p):
    """One LOD's lighting at the reader's place: dict(shadowMaps, shadowVertexBuffers (object_refs'), lightmap
    (lightmap_record's), overrideVertexColors). Its painted vertex colours (a flag, 0 or 1; when set the colours'
    stride and count, then with a count the colours as an array of that stride and count) and its positions (12 bytes
    each) are passed over; the colours' places are given, overrideVertexColorsOffset (the flag's) and
    overrideVertexColorsEnd (where they end: the positions' count)."""
    out = dict(shadowMaps=object_refs(r, p), shadowVertexBuffers=object_refs(r, p), lightmap=lightmap_record(r, p))
    out['overrideVertexColorsOffset'] = r.pos
    colour = r.take(1)[0]
    if colour not in (0, 1):
        raise FormatError('Invalid vertex-color boolean')
    if colour:
        stride, count = r.unpack('2I')
        if count:
            actual_stride, actual_count, _ = r.array_bytes()
            if actual_stride != stride or actual_count != count:
                raise FormatError('Vertex-color count/stride mismatch')
    out['overrideVertexColorsEnd'] = r.pos
    r.take(r.count() * 12)
    out['overrideVertexColors'] = bool(colour)
    return out


def mesh_lods(r, p):
    """A static or fractured mesh component's LOD records, from the reader's place (where its native data starts):
    dict(lods [lod_record's], swaps, swapMeshes [dict(at, ref)]). Enemy Within (licensee 64) saves two mesh-swap LOD
    records and their two meshes after the LOD array; UDK's own packages (licensee 0, the same version 845) end after
    it. The reader is left after them."""
    lods = [lod_record(r, p) for _ in range(r.count())]
    swaps, meshes = [], []
    if p.header['lic'] != 0:
        swaps = [lod_record(r, p), lod_record(r, p)]
        for _ in range(2):
            at = r.pos
            ref = r.i32()
            p.name(ref)
            meshes.append(dict(at=at, ref=ref))
    return dict(lods=lods, swaps=swaps, swapMeshes=meshes)


def _mesh_component(o):
    """A mesh component's references and bulk records, in their order: each LOD's (the swaps' after the LOD array's)
    shadow maps and shadow vertex buffers, then its lightmap's owner and two bulk records, or its three textures;
    then the swaps' two meshes."""
    lods = mesh_lods(o.r, o.p)
    for lod in lods['lods'] + lods['swaps']:
        o.objects(lod['shadowMaps'])
        o.objects(lod['shadowVertexBuffers'])
        lm = lod['lightmap']
        if lm['type'] == 1:
            o.fields.append((lm['ownerOffset'] - o.off, OBJECT))
            o.bulk(lm['directionalSamples'])
            o.bulk(lm['simpleSamples'])
        elif lm['type'] == 2:
            o.fields += [(s['textureOffset'] - o.off, OBJECT) for s in lm['slots']]
    o.fields += [(m['at'] - o.off, OBJECT) for m in lods['swapMeshes']]


def _static_mesh_component(o):
    _mesh_component(o)
    o.done('a static mesh component')


# -- fracturing meshes ---------------------------------------------------------------------------------------------
# A FracturedStaticMesh is a StaticMesh, whole, and then: the mesh it was sliced from (a reference, none in cooked
# data), its fragments, and 60 bytes of numbers. Its only package number is that one reference; the fragments are
# walked because their lengths vary. What EW (licensee 64) writes differently from the engine's source: a fragment's
# neighbours are 4 bytes each, not one, and each fragment ends with one more index. Read so over the install on
# 11 November 2026: 1,679 meshes with 46,989 fragments in 2,979 packages, each to its last byte, the source none in
# all; and 4,062 components, with references only (no vertex lightmap among them).
_HULL_ARRAYS = (12, 16, 4, 12, 12, 16)          # vertices, permuted vertices, face triangles, edge directions,
#                                                 face normals, face planes: the bytes of one element of each


def _fragment(o, fragments):
    r = o.r
    r.take(12)                                  # centre
    for _ in _HULL_ARRAYS:                      # its convex hull: cooked out of every fragment of the install, so
        if r.count():                           # the element sizes above are the engine's and were never met
            raise NativeError('a fragment with a convex hull')
    r.take(25 + 28)                             # the hull's box (two corners, a flag); the fragment's bounds
    neighbours = r.count()
    for other in r.unpack('%di' % neighbours):  # the fragment across each face, or -1
        if not -1 <= other < fragments:
            raise NativeError('a fragment neighbour of %d among %d fragments' % (other, fragments))
    r.take(12 + 12)                             # can be destroyed, root, never spawn a chunk; the outside normal
    if r.count() != neighbours:                 # each shared face's size
        raise NativeError('a fragment with other counts of neighbours and shared faces')
    r.take(4 * neighbours)
    if not -1 <= r.i32() < fragments:           # EW's own: a fragment of this mesh, or -1
        raise NativeError('a fragment whose last index is no fragment')


def _fractured_mesh(o):
    r = o.r
    _static_mesh_tail(o, _static_mesh_head(o))
    o.obj()                                     # the source static mesh
    fragments = r.count()
    for _ in range(fragments):
        _fragment(o, fragments)
    core = r.i32()                              # the core fragment, or -1
    if not -1 <= core < fragments:
        raise NativeError('a core fragment of %d among %d' % (core, fragments))
    r.take(4 + 48 + 4)                          # the interior section; the core mesh's scale, offset and rotation
    #                                             and the plane bias; two build versions, 2 bytes each
    o.done('a fractured mesh')


def _fractured_mesh_component(o):
    """A fractured mesh component's native data is a static mesh component's and no more: its fragments' state is
    in its properties."""
    _mesh_component(o)
    o.done('a fractured mesh component')


# -- sounds --------------------------------------------------------------------------------------------------------
def _sound_wave(o):
    while o.r.pos < o.r.end:
        o.bulk()


# -- skeletal meshes -----------------------------------------------------------------------------------------------
def _skeletal_indices(o):
    r = o.r
    r.take(4)                                   # needs CPU access
    size = r.take(1)[0]
    stride = r.array_bytes()[0]
    if stride not in (0, size) or size not in (2, 4):
        raise NativeError('an index buffer of %d-byte indices declared as %d' % (stride, size))


def _skeletal_lod(o, colours):
    r = o.r
    r.take(r.count() * 13)                      # sections: material slot, chunk, first index, triangles, sorting
    _skeletal_indices(o)
    r.take(r.count() * 2)                       # active bones
    for _ in range(r.count()):                  # chunks
        r.take(4)                               # first vertex
        if r.count() or r.count():
            raise NativeError('a skin chunk with CPU vertices')
        r.take(r.count() * 2)                   # bone map
        r.take(12)                              # rigid and soft vertex counts, the most influences
    r.take(8)                                   # size, vertex count
    r.take(r.count())                           # required bones
    o.bulk()                                    # raw point indices (empty in cooked data)
    r.take(4 + 12 + 24)                         # UV channels; the vertex buffer's own header
    r.array_bytes()                             # vertices
    if colours:
        r.array_bytes()                         # vertex colours
    if r.count():
        raise NativeError('a LOD with alternate vertex influences')
    _skeletal_indices(o)                        # adjacency indices


def _skeletal_mesh(o):
    r = o.r
    r.take(28)                                  # bounds
    o.objs()                                    # materials
    r.take(24)                                  # origin, rotation origin
    for _ in range(r.count()):                  # reference skeleton
        o.name()
        r.take(4 + 28 + 8 + 4)                  # flags, orientation and position, children and parent, colour
    r.take(4)                                   # skeletal depth
    lods = r.count()
    if not 1 <= lods <= 16:
        raise NativeError('%d LODs' % lods)
    colours = o.p.own(o.index, 'bHasVertexColors', False)
    for _ in range(lods):
        _skeletal_lod(o, colours)
    for _ in range(r.count()):                  # bone names to bone numbers
        o.name()
        r.take(4)
    if r.count():
        raise NativeError('per-polygon bone collision data')
    for _ in range(r.count()):                  # bones that break: names as text
        o.fstring()
    r.take(r.count())                           # and how each breaks
    o.objs()                                    # clothing assets, one a material
    r.take(r.count() * 4)                       # cached streaming texture factors
    if r.i32():
        raise NativeError('uncooked mesh source data')
    o.done('a skeletal mesh')


# -- decals --------------------------------------------------------------------------------------------------------
def _decal_component(o):
    r = o.r
    for _ in range(r.count()):                  # static receivers (an archetype's has none)
        o.obj()                                 # the component the decal lies on
        r.array_bytes()                         # vertices
        r.array_bytes()                         # indices
        r.take(4)                               # triangles
        if r.i32():                             # none has one in the game's maps, so its form here is not known
            raise NativeError('a decal receiver with a lightmap')
        o.objs()                                # shadow maps (none in the game's maps)
        r.take(8)
    o.done('a decal component')


# -- brushes (a volume's geometry) ----------------------------------------------------------------------------------
_LIGHTMASS = 36         # a primitive's Lightmass settings: nine four-byte values


def _sized(o, size, what):
    """An array written with its element size before its count: returns the count, its elements skipped."""
    r = o.r
    stride, count = r.i32(), r.i32()
    if stride != size or count < 0:
        raise NativeError('%s: elements of %d bytes, %d of them, where %d-byte ones were expected'
                          % (what, stride, count, size))
    r.take(stride * count)
    return count


def _model(o):
    """UModel: its bounds; vectors, points and BSP nodes; the owner; the surfaces; the vertices; the zones; the
    Polys it was built from; leaf hulls, leaves and portal nodes; its vertex buffer; its lighting GUID and the
    surfaces' Lightmass settings."""
    r = o.r
    r.take(28)                                  # bounds: origin, extent, radius
    _sized(o, 12, 'vectors')
    _sized(o, 12, 'points')
    _sized(o, 64, 'nodes')
    o.obj()                                     # owner
    for _ in range(r.count()):                  # surfaces
        o.obj()                                 # material
        r.take(24)                              # flags; base, normal, texture U and V; the brush polygon
        o.obj()                                 # the brush's actor
        r.take(28)                              # plane, shadow map scale, lighting channels, Lightmass index
    _sized(o, 24, 'vertices')
    r.take(4)                                   # shared sides
    for _ in range(r.count()):                  # zones
        o.obj()                                 # the zone's actor
        r.take(20)                              # last render time, connectivity, visibility
    o.obj()                                     # Polys
    _sized(o, 4, 'leaf hulls')
    _sized(o, 4, 'leaves')
    r.take(8)                                   # root outside, linked
    _sized(o, 4, 'portal nodes')
    r.take(4)                                   # unique vertices
    _sized(o, 36, 'the vertex buffer')
    r.take(16)                                  # lighting GUID: the cook's, kept as it is
    r.take(_LIGHTMASS * r.count())
    o.done('a model')


def _polys(o):
    """UPolys: how many polygons (twice), the owner, then each polygon."""
    r = o.r
    count, most = r.i32(), r.i32()
    if not 0 <= count <= most:
        raise NativeError('%d polygons of %d' % (count, most))
    o.obj()                                     # owner
    for _ in range(count):
        r.take(48)                              # base, normal, texture U and V
        r.take(12 * r.count())                  # vertices
        r.take(4)                               # flags
        o.obj()                                 # actor
        o.name()                                # item name
        o.obj()                                 # material
        r.take(16 + _LIGHTMASS)                 # link, brush polygon, shadow map scale, lighting channels; Lightmass
        o.name()                                # ruleset variation
    o.done('polys')


def _brush_component(o):
    for _ in range(o.r.count()):                # cached collision hulls (a blocking volume's): bytes, no numbers
        _sized(o, 1, 'a cached hull')
    o.done('a brush component')


MAPPED = {
    'Model': _model, 'Polys': _polys, 'BrushComponent': _brush_component,
    'SkeletalMesh': _skeletal_mesh,
    'DecalComponent': _decal_component,
    'Texture2D': _texture2d, 'TextureFlipBook': _texture2d,
    'LightMapTexture2D': _lightmap_texture, 'ShadowMapTexture2D': _texture2d,
    'TextureCube': _texture_only,
    'StaticMesh': _static_mesh,
    'Material': _material, 'DecalMaterial': _material,
    'MaterialInstanceConstant': _material_instance, 'MaterialInstanceTimeVarying': _material_instance,
    'StaticMeshComponent': _static_mesh_component,
    'FracturedStaticMesh': _fractured_mesh,
    'FracturedStaticMeshComponent': _fractured_mesh_component,
    'SoundNodeWave': _sound_wave,
}
# Classes with native bytes after their properties that hold no name, reference or offset. Each is an asset class
# (never an object of a level, whose native data could hold what an asset's doesn't), compared between maps over the
# ring of 96 with the fields of its properties alone and found equal every time (tools/bake/transplant.py oracle,
# 11 November 2026: 10,913 body setups, 1,237 sound cues, 426 animation sequences, 152 physics asset instances, 13
# Flash movies). BrushComponent, Model and Polys, once left out, have their layouts above.
# What a door or a physics prop holds besides its skeletal mesh has no native data at all in cooked maps
# (SkeletalMeshComponent, PhysicsAsset, AnimSet, AnimTree, AnimNodeSequence, SkeletalMeshSocket) or is plain here.
PLAIN = frozenset(('RB_BodySetup', 'SoundCue', 'AnimSequence', 'PhysicsAssetInstance', 'SwfMovie'))


def fields(p, index, start):
    """[(offset, kind)] of export `index`'s native data, which begins at `start` in its data."""
    e = p.exports[index - 1]
    if start == e['size']:
        return []
    cls = p.cls(index)
    reader = MAPPED.get(cls)
    if reader is None:
        if cls in PLAIN:
            return []
        raise Unmapped('%s: a %s has %d bytes of native data and no layout here'
                       % (p.name(index), cls, e['size'] - start))
    o = _Out(p, index, start)
    try:
        reader(o)
    except (FormatError, struct.error) as error:
        raise NativeError('%s (%s): %s' % (p.name(index), cls, error)) from None
    except NativeError as error:
        raise type(error)('%s (%s): %s' % (p.name(index), cls, error)) from None
    return o.fields
