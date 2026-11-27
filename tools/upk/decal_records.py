"""A placed decal as the game stores it: its frame, and the triangles it was clipped to on each surface it lies on
(the game-likeness plan, stage D1; findings F-210, F-211).

A placed decal is a DecalActor (or DecalActorMovable) holding one DecalComponent. After its tagged properties the
component saves its static receivers:
- a count, then for each receiver:
  - the receiving component (an object reference: a static or fracturing mesh component of the level);
  - its vertices, written with their element size before their count: 28 bytes each, the position in the receiver's
    own space (three floats), a packed tangent and a packed normal (four bytes each, b / 127.5 - 1, the normal's w the
    sign of the binormal) and the receiver's lightmap coordinate (two floats: zero in the game's maps, which give no
    decal a lightmap);
  - its indices, written the same way: 16-bit, three a triangle (a decal that is not clipped, bNoClip, writes none:
    its vertices are three a triangle);
  - the count of its triangles;
  - its lightmap: a type (0 in every map of the game; the form of any other is not known here, so it is refused);
  - its shadow maps: a counted array of references (empty in every map of the game);
  - two integers (0 in every map of the game).
An archetype's component (the civilians' bodies' archetypes, a physics prop's closure) has no receivers.

The decal's size is its component's tagged properties, else its archetypes' in the package, over the class's defaults
(DEFAULTS: Default__DecalComponent's in Engine.upk, which the install test compares): Width, Height, TileX, TileY,
OffsetX, OffsetY, NearPlane, FarPlane, DecalRotation, BlendRange, DepthBias. Its frame is its owner actor's (a
DecalActor's component follows its owner, DecalTransform_OwnerAbsolute): at the actor's Location, the normal the
actor's -X axis, the tangent its -Y and the binormal its Z, which HitLocation, HitNormal, HitTangent and HitBinormal
repeat where they are saved (F-210). The owner's DrawScale does not size a decal.

What the game's decal vertex shader (the FLocalDecalVertexFactory base pass) gives a point: with L, T, B and N the
frame's location, tangent, binormal and normal in the receiver's space (DecalLocation, DecalLocalTangent,
DecalLocalBinormal, DecalLocalNormal) and M the decal's matrix,
  texture coordinates = DecalOffset - M (p - L) + 0.5,
  blend               = saturate((dot(N, n) - (a + b) / 2) / (b - a) + 0.5)   (n the surface's normal),
  depth               = dot(L - p, N),
and the decal's own tangent frame is cross(n, normalize(cross(n, T))) and the same with B: the frame's tangent and
binormal turned into the surface, negated. The pixel shader cuts what lies outside 0..1 in both coordinates or outside
NearPlane..FarPlane in depth, and fades the decal over the last fifth of its depth (F-211). The engine's values
(not in a file, set by its code): M's rows are T TileX / Width and B TileY / Height, DecalOffset (OffsetX, OffsetY),
DecalBlendInterval (a, b) the cosines of BlendRange's Y and X (in degrees). Every stored vertex of the install's
clipped decals lies in 0..1 and NearPlane..FarPlane by these. `coordinates` works it out in the world, which is the
same for a receiver at scale 1.

  DEFAULTS                                        Default__DecalComponent's members this reads
  receivers(r, p) -> [dict]                       a DecalComponent's static receivers, from the reader's place
  vertices(receiver) -> (positions, tangents, normals)  a receiver's vertices decoded, in its own space
  member(p, component, key)                       a member as the package saves it (the component's, its archetypes')
  frame(p, component) -> dict                     the decal's frame and size
  saved_frame(p, component) -> dict               its Hit members as saved (the survey compares them with the frame)
  owner_frame(location, rotation)                 the frame an owner actor gives its decal
  in_world(matrix, positions, normals) -> (points, normals)     a receiver's vertices put in the world
  coordinates(frame, points, normals) -> (u, v, blend, depth)   the vertex shader's values at points of the world
  surface_frame(frame, normals) -> (tangents, binormals)        the decal's tangent frame on surfaces
"""
import math
from pathlib import Path
import struct
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'viewer'))
from package import FormatError  # noqa: E402
from export_math import transform  # noqa: E402

VERTEX_SIZE = 28
VERTEX = np.dtype([('position', '<f4', 3), ('tangent', 'u1', 4), ('normal', 'u1', 4), ('lightmap', '<f4', 2)])
INDEX_SIZE = 2
# Default__DecalComponent's members (Engine.upk); NearPlane, OffsetX, OffsetY and DecalRotation are the struct's zero.
# Default__DecalActor's component and DecalActorBase's change none of these.
DEFAULTS = {'Width': 200.0, 'Height': 200.0, 'TileX': 1.0, 'TileY': 1.0, 'OffsetX': 0.0, 'OffsetY': 0.0,
            'NearPlane': 0.0, 'FarPlane': 300.0, 'DecalRotation': 0.0, 'BlendRange': [89.5, 180.0],
            'DepthBias': -1e-05}
FRAME = ('HitLocation', 'HitTangent', 'HitBinormal', 'HitNormal')
# the actors whose decal takes its frame from them (Default__DecalActorBase's component: DecalTransform_OwnerAbsolute)
OWNERS = ('DecalActor', 'DecalActorMovable')


def _sized(r, size, what):
    """An array written with its element size before its count: (count, bytes). An empty one may write a size of 0."""
    at = r.pos
    stride = r.count()
    count = r.count()
    if count and stride != size:
        raise FormatError('%s at %d: elements of %d bytes, where %d-byte ones were expected' % (what, at, stride, size))
    return count, r.take(stride * count)


def receivers(r, p):
    """The static receivers of a DecalComponent's native data, from the reader's place (where its tagged properties
    end) to its end: [dict(componentAt (the reference's place in the package), component, vertexCount, vertices (the
    raw 28-byte vertices), indices (a tuple), triangles, lightmap (its type), shadowMaps (references), data,
    instance)]. Refused (FormatError) where a count or an index doesn't fit, where a receiver has a lightmap, and
    where bytes are left after the last receiver."""
    out = []
    for _ in range(r.count()):
        at = r.pos
        component = r.i32()
        p.name(component)
        count, raw = _sized(r, VERTEX_SIZE, 'a decal receiver\'s vertices')
        n, packed = _sized(r, INDEX_SIZE, 'a decal receiver\'s indices')
        indices = struct.unpack('<%dH' % n, packed)
        triangles = r.i32()
        indexed = bool(n)
        if not n and triangles and count == 3 * triangles:
            indices = tuple(range(count))           # a decal that is not clipped (bNoClip): its vertices three a triangle
        elif n % 3 or triangles != n // 3:
            raise FormatError('a decal receiver at %d: %d indices for %d triangles' % (at, n, triangles))
        if indices and max(indices) >= count:
            raise FormatError('a decal receiver at %d: an index past its %d vertices' % (at, count))
        lightmap = r.i32()
        if lightmap:
            raise FormatError('a decal receiver at %d has a lightmap (type %d), whose form is not known' % (at, lightmap))
        shadows = [r.i32() for _ in range(r.count())]
        for ref in shadows:
            p.name(ref)
        data, instance = r.unpack('2i')
        out.append(dict(componentAt=at, component=component, vertexCount=count, vertices=raw, indices=indices,
                        indexed=indexed, triangles=triangles, lightmap=lightmap, shadowMaps=shadows, data=data,
                        instance=instance))
    if r.pos != r.end:
        raise FormatError('a decal component: %d bytes left after its receivers' % (r.end - r.pos))
    return out


def vertices(receiver):
    """A receiver's vertices in its own space: (positions, tangents, normals), arrays of rows ([x, y, z] and [x, y, z,
    w]), the packed vectors unpacked as the game's vertex shader does (b / 127.5 - 1)."""
    raw = np.frombuffer(receiver['vertices'], dtype=VERTEX, count=receiver['vertexCount'])
    positions = raw['position'].astype(np.float64)
    if not np.isfinite(positions).all():
        raise FormatError('a decal vertex that is not a number')
    return positions, (raw['tangent'] - 127.5) / 127.5, (raw['normal'] - 127.5) / 127.5


def owner_frame(location, rotation):
    """(location, tangent, binormal, normal) of a decal its owner actor places (DecalTransform_OwnerAbsolute): at the
    actor's Location, its normal the actor's -X axis, its tangent its -Y and its binormal its Z (F-210)."""
    m = transform([0, 0, 0], rotation, [1, 1, 1])
    x, y, z = ([float(m[r][c]) for r in range(3)] for c in range(3))
    return [float(v) for v in location], [-v for v in y], z, [-v for v in x]


def member(p, component, key):
    """A member of the decal's component as the package saves it: its own, else its archetypes' in the package (a
    decal placed from an archetype, as the civilians' bodies of URB_CommercialStreet are, saves its size and material
    there), else None (the class's: DEFAULTS)."""
    seen = set()
    while 0 < component <= len(p.exports) and component not in seen:
        seen.add(component)
        item = p.properties(component)[0].get((key, 0))
        if item is not None:
            return item['value']
        component = p.exports[component - 1]['arch']
    return None


def frame(p, component):
    """The decal's frame and size: dict(location, tangent, binormal, normal (game units and axes), width, height,
    tile [x, y], offset [x, y], nearPlane, farPlane, decalRotation, blendRange [x, y] (degrees), depthBias, byOwner),
    each size member as the package saves it (member) over DEFAULTS. A decal of a DecalActor (the class's
    DecalTransform is DecalTransform_OwnerAbsolute) has its owner's frame (owner_frame, `byOwner` true): its saved Hit
    members are the same. Another's is its saved Hit members (None where missing)."""
    def own(key):
        return member(p, component, key)

    def number(key):
        v = own(key)
        return float(v) if isinstance(v, (int, float)) else DEFAULTS[key]

    def vector(key):
        v = own(key)
        return [float(x) for x in v] if isinstance(v, list) and len(v) == 3 else None
    blend = own('BlendRange')
    blend = (list(struct.unpack('<2f', bytes(blend))) if isinstance(blend, (bytes, bytearray)) and len(blend) == 8
             else list(DEFAULTS['BlendRange']))
    owner = p.exports[component - 1]['outer']
    by_owner = (owner > 0 and p.cls(owner) in OWNERS
                and own('DecalTransform') in (None, 'DecalTransform_OwnerAbsolute'))
    if by_owner:
        location, tangent, binormal, normal = owner_frame(p.effective(owner, 'Location', [0, 0, 0]),
                                                          p.effective(owner, 'Rotation', [0, 0, 0]))
    else:
        location, tangent, binormal, normal = (vector(k) for k in FRAME)
    return dict(location=location, tangent=tangent, binormal=binormal, normal=normal, width=number('Width'),
                height=number('Height'), tile=[number('TileX'), number('TileY')],
                offset=[number('OffsetX'), number('OffsetY')], nearPlane=number('NearPlane'),
                farPlane=number('FarPlane'), decalRotation=number('DecalRotation'), blendRange=blend,
                depthBias=number('DepthBias'), byOwner=by_owner)


def saved_frame(p, component):
    """The decal's Hit members as the package saves them (member): {member: [x, y, z]} of those it saves."""
    out = {}
    for key in FRAME:
        value = member(p, component, key)
        if isinstance(value, list) and len(value) == 3:
            out[key] = [float(x) for x in value]
    return out


def _unit(v):
    """Rows of `v` made unit length; rows too short to have a direction are left as they are (zero)."""
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return np.where(n > 1e-12, v / np.where(n > 1e-12, n, 1.0), v)


def in_world(matrix, positions, normals):
    """(points, normals) of a receiver's vertices in the world: its local-to-world `matrix` (4 x 4 rows, game axes:
    the export's actor and component transforms) on the positions, its inverse transpose on the normals (unit)."""
    m = np.asarray(matrix, dtype=np.float64)
    points = np.asarray(positions, dtype=np.float64) @ m[:3, :3].T + m[:3, 3]
    turn = np.linalg.inv(m[:3, :3]).T
    return points, _unit(np.asarray(normals, dtype=np.float64)[:, :3] @ turn.T)


def coordinates(f, points, normals):
    """(u, v, blend, depth) of the game's decal vertex shader at points of the world with the surface's normals there
    (arrays of rows, game units and axes), for the decal of frame `f` (frame's dict): four arrays of one value a point."""
    d = np.asarray(points, dtype=np.float64) - np.asarray(f['location'], dtype=np.float64)
    u = f['offset'][0] - d @ np.asarray(f['tangent']) * (f['tile'][0] / f['width']) + 0.5
    v = f['offset'][1] - d @ np.asarray(f['binormal']) * (f['tile'][1] / f['height']) + 0.5
    a, b = (math.cos(math.radians(x)) for x in (f['blendRange'][1], f['blendRange'][0]))
    facing = _unit(np.asarray(normals, dtype=np.float64)[:, :3]) @ np.asarray(f['normal'])
    blend = np.clip((facing - (a + b) / 2) / (b - a) + 0.5, 0.0, 1.0) if b != a else np.ones(len(d))
    return u, v, blend, -(d @ np.asarray(f['normal']))


def surface_frame(f, normals):
    """(tangents, binormals): the decal's tangent frame on surfaces of these normals (rows, game axes), as its vertex
    shader makes it (the frame's tangent and binormal turned into the surface, negated: the directions its texture
    coordinates grow along). A row where the surface is edge on to the frame's axis is zero."""
    n = _unit(np.asarray(normals, dtype=np.float64)[:, :3])
    out = []
    for axis in (f['tangent'], f['binormal']):
        side = np.cross(n, np.asarray(axis, dtype=np.float64))
        length = np.linalg.norm(side, axis=1, keepdims=True)
        side = np.where(length > 1e-6, side / np.where(length > 1e-6, length, 1.0), 0.0)
        out.append(np.cross(n, side))
    return out[0], out[1]
