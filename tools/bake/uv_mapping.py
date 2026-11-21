"""A made piece's texture mapping (the custom geometry improvements plan, section 5): how a surface of a wall, floor,
roof or ground piece takes its texture when its look's own mapping is replaced. One rule for the three generators
(frac_wall.py, frac_slab.py, ground.py) and the editor's preview, which reaches it through them.

A free-form piece's numbers may carry `mapping` {surfaces: {role: surface}}, a role one of 'faces' (a wall's two
faces), 'top' (a slab's or a ground shape's, a ramp's slope and a rock's faces turned more up than aside too),
'underside' (a slab's) and 'sides' (a ground shape's); a role not listed, or not the piece's, keeps its look's mapping,
as every other face does (a wall's trims, caps, ends and gaps' sides, its faces inside; a slab's edges). A surface:

  mode      'size': `u` and `v` are game units per repeat along the pattern's own axes (a 96-wide brick pattern keeps
            its bricks' size as the wall grows, and its bricks' shape when turned); 'count': `u` and `v` are repeats
            across the whole surface (fractions too: three stay three after a resize); 'fit': one repeat over the whole
            surface (`u` and `v` are read as 1). `modeV`, when given, is the mode along v, so a surface can tile along
            u and fit along v. A count or a fit is across the surface as the turned pattern's axes measure it (its
            corners' run along each), so a quarter turn fits the turned image exactly and no turn shears it.
  turn      degrees the pattern is turned about its origin (turned whole: a repeat stays a rectangle)
  flipU, flipV   the pattern mirrored along u or v (its own axes)
  offsetU, offsetV   the pattern slid, in repeats (along its own axes)
  world     the pattern's origin is the world's (adjoining surfaces line up), not the piece's own frame's

A point of a surface is given as (a, b): its place in game units on the surface's two axes, in the piece's frame (a
wall's face: a along the wall (x), b up (z), both faces; a top or underside: a along x, b along y, a ramp's slope
projected straight down as its look's own texture is; a ground side: a along x on a side facing along y, along y on
one facing along x, b up). The surface's extent (a0, a1, b0, b1) is the whole logical piece's (a piece of a split wall
or slab reads it from the whole: frac_wall/frac_slab `whole`; a ground shape's is its box, a side's a its run along
the box), so a fit or a count goes on across the cuts. `origin` (a, b) is where the piece's frame stands on the
surface's axes in the world, for a world-aligned surface (the compiler and the Build know the pose; the generator is
handed it).

The order is the editor's and the Build's alike: the point turned, scaled to repeats by the mode along the turned
axes, mirrored, then slid by the offsets (U, V = flips * S * R(turn) * (a, b) + offsets). Seen from the pattern, it is
slid, mirrored, sized and then turned on the surface. (Until stage 4 the point was scaled before it was turned, which
sheared a turned pattern whose u and v differ: a 96 by 48 repeat turned 30 degrees drew as an 87 by 64 parallelogram;
nothing had used the rule yet.)

What the generators do with it (mapped, face_signs, origin_of): each corner of a face of a listed surface takes the
rule's (U, V) at its (a, b), times the face's signs, as its texture coordinates (UV channel 0, before the tangents are
worked out from them; the lightmap's channel, the vertex paint and the slots stay as the look makes them). The signs
make a mapping with no turn and no flips read its image as the looks' own mappings do on the game's donors, the right
way round seen from outside: the mesh's v runs down the image, so a wall's faces write -V (b runs up); a wall's side B
(facing -y) and a slab's underside write -U, the mirror of side A and of the top through the piece, as the donors'
own textures are (the walls' side A u = x / repeat, side B u = -x / repeat; the floors' tops u = x, v = y, their
undersides u = -x), so one mapping's pattern goes through the piece and a single offset keeps both faces in place when
the frame's origin moves. A ground shape's side writes -U where its a runs to the left seen from outside (a side
facing -y or +x), as a wall's side B. A positive turn so turns the image clockwise seen from a wall's side A, a slab's
underside and a ground shape's sides facing +y or -x, anticlockwise seen from a wall's side B, from above a top and on
the other two sides (the game's y runs down the image seen from above).

`mappingOrigin` (in the numbers, beside `mapping`): {role: place}, where the piece's frame stands in the world, read
for a surface with `world` (origin_of; (0, 0) when not given): [a0, b0] on the role's own axes ('faces': along x, up;
'top' and 'underside': x, y), or [x, y, z] on the frame's three axes, which every role takes ('sides' takes only that:
a side along x reads x, one along y reads y). A split piece's numbers carry its whole's mapping and origin unchanged,
its points being placed in the whole's frame.

Made meshes write texture coordinates as half floats (gen_mesh.py: steps of 1/32 of a repeat from 32 repeats out, of a
whole repeat from 1,024, nothing past 65,504): rebased() takes whole repeats off a face's coordinates so they stay near
0, keeping the pattern's phase (for a surface that tiles), and half_float_room() says whether a face's span still
fits (the generators hold each face's coordinates with free_form.held, which refuses one no shift keeps)."""
import math

ROLES = ('faces', 'top', 'underside', 'sides')
MODES = ('size', 'fit', 'count')
HALF_MAX = 65504.0          # the largest half float
HALF_FINE = 1024.0          # past this a half float's step is a whole repeat or more
# the axes of the frame a role's two-number mappingOrigin is on ('sides' takes the three-number form only)
ORIGIN_AXES = {'faces': 'xz', 'top': 'xy', 'underside': 'xy'}


class MappingError(ValueError):
    pass


def check(mapping):
    """A mapping's shape checked (MappingError): {surfaces: {role: surface}} as the module says."""
    if not isinstance(mapping, dict) or set(mapping) - {'surfaces'} or not isinstance(mapping.get('surfaces'), dict):
        raise MappingError('a mapping is {surfaces: {role: surface}}')
    for role, s in mapping['surfaces'].items():
        if role not in ROLES:
            raise MappingError('a mapping of an unknown surface %r (they are %s)' % (role, ', '.join(ROLES)))
        if not isinstance(s, dict) or s.get('mode') not in MODES or s.get('modeV', s.get('mode')) not in MODES:
            raise MappingError('the %s surface needs a mode, one of %s' % (role, ', '.join(MODES)))
        extra = set(s) - {'mode', 'modeV', 'u', 'v', 'turn', 'flipU', 'flipV', 'offsetU', 'offsetV', 'world'}
        if extra:
            raise MappingError('the %s surface has fields a mapping has not: %s' % (role, ', '.join(sorted(extra))))
        for k in ('u', 'v'):
            if not _number(s.get(k)) or s[k] <= 0:
                raise MappingError('the %s surface needs a positive %s' % (role, k))
        for k in ('turn', 'offsetU', 'offsetV'):
            if k in s and not _number(s[k]):
                raise MappingError("the %s surface's %s is a number" % (role, k))
        for k in ('flipU', 'flipV', 'world'):
            if k in s and not isinstance(s[k], bool):
                raise MappingError("the %s surface's %s is true or false" % (role, k))
    return mapping


def check_origin(origin):
    """A piece's `mappingOrigin` checked (MappingError): absent (None), or {role: [a0, b0] or [x, y, z]} of finite
    numbers, 'sides' taking [x, y, z] only (the module's words)."""
    if origin is None:
        return origin
    if not isinstance(origin, dict):
        raise MappingError('a mappingOrigin is {role: [a0, b0] or [x, y, z]} (it has %r)' % (origin,))
    for role, place in origin.items():
        if role not in ROLES:
            raise MappingError('a mappingOrigin of an unknown surface %r (they are %s)' % (role, ', '.join(ROLES)))
        sizes = (3,) if role == 'sides' else (2, 3)
        if not (isinstance(place, (list, tuple)) and len(place) in sizes and all(map(_number, place))):
            raise MappingError("the %s surface's mappingOrigin is %s of finite numbers (it has %r)"
                               % (role, '[x, y, z]' if role == 'sides' else '[a0, b0] or [x, y, z]', place))
    return origin


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def surface_of(numbers, role):
    """A piece's mapping of one surface, or None for its look's own."""
    m = (numbers or {}).get('mapping')
    return ((m or {}).get('surfaces') or {}).get(role) if m else None


def origin_of(numbers, role, axes=None):
    """Where the piece's frame stands in the world on a surface's two axes (its numbers' mappingOrigin, the module's
    words): `axes` two of 'x', 'y' and 'z' (a ground side's 'xz' or 'yz'; the role's own, ORIGIN_AXES, when not given);
    (0, 0) when the numbers have none for the role."""
    place = ((numbers or {}).get('mappingOrigin') or {}).get(role)
    if place is None:
        return (0.0, 0.0)
    if len(place) == 2:
        return (float(place[0]), float(place[1]))
    axes = axes or ORIGIN_AXES[role]
    return tuple(float(place['xyz'.index(k)]) for k in axes)


def face_signs(role, normal=(0.0, 0.0, 1.0)):
    """(the sign of u, the sign of v) a face of `role` whose outward normal is `normal` writes the rule's (U, V) with
    (the module's words): a wall's faces (1, -1) on side A (facing +y), (-1, -1) on side B; a top (1, 1); an underside
    (-1, 1); a ground shape's side (1, -1) where its a (x on a side facing along y, else y) runs to the right seen from
    outside, (-1, -1) where it runs to the left."""
    if role == 'faces':
        return (1.0 if normal[1] > 0 else -1.0, -1.0)
    if role == 'top':
        return (1.0, 1.0)
    if role == 'underside':
        return (-1.0, 1.0)
    if role == 'sides':
        right = normal[1] if abs(normal[1]) > abs(normal[0]) else -normal[0]
        return (1.0 if right > 0 else -1.0, -1.0)
    raise MappingError('a face of an unknown surface %r' % (role,))


def mapped(surface, points, extent, origin=(0.0, 0.0), signs=(1.0, 1.0)):
    """A face's texture coordinates [(u, v)] mapped by `surface`: uv() at each of its corners' places `points` [(a, b)]
    (the whole surface's `extent`, the frame's world `origin`), times the face's `signs` (face_signs)."""
    out = []
    for a, b in points:
        u, v = uv(surface, a, b, extent, origin)
        out.append((signs[0] * u, signs[1] * v))
    return out


def _scaled(value, mode, size, low, high):
    """A place along one axis in repeats: per `size` units, `size` repeats over low..high, or one repeat over it."""
    if mode == 'size':
        return value / size
    span = high - low
    if span <= 0:
        return 0.0
    count = 1.0 if mode == 'fit' else size
    return (value - low) / span * count


def uv(surface, a, b, extent, origin=(0.0, 0.0)):
    """The texture coordinates (u, v) of the point (a, b) of a surface mapped by `surface` (the module's words),
    `extent` (a0, a1, b0, b1) the whole surface's, `origin` the piece frame's place on the surface's axes in the world
    (a world-aligned surface's): the point turned, scaled along the turned axes (a count or a fit over the run of the
    surface's corners along each), mirrored, slid."""
    a0, a1, b0, b1 = extent
    if surface.get('world'):
        a, b = a + origin[0], b + origin[1]
        a0, a1, b0, b1 = a0 + origin[0], a1 + origin[0], b0 + origin[1], b1 + origin[1]
    turn = math.radians(float(surface.get('turn', 0.0)))
    if turn:
        c, s = math.cos(turn), math.sin(turn)
        a, b = a * c - b * s, a * s + b * c
        corners = [(x * c - y * s, x * s + y * c) for x in (a0, a1) for y in (b0, b1)]
        a0, a1 = min(p[0] for p in corners), max(p[0] for p in corners)
        b0, b1 = min(p[1] for p in corners), max(p[1] for p in corners)
    mode_u, mode_v = surface['mode'], surface.get('modeV', surface['mode'])
    U = _scaled(a, mode_u, float(surface['u']), a0, a1)
    V = _scaled(b, mode_v, float(surface['v']), b0, b1)
    if surface.get('flipU'):
        U = -U
    if surface.get('flipV'):
        V = -V
    return (U + float(surface.get('offsetU', 0.0)), V + float(surface.get('offsetV', 0.0)))


def rebased(uvs):
    """A face's texture coordinates with whole repeats taken off, so they stay near 0 (half floats): its smallest u and
    v brought into [0, 1), the rest shifted by the same whole numbers, so the pattern's phase is kept."""
    if not uvs:
        return list(uvs)
    du, dv = math.floor(min(p[0] for p in uvs)), math.floor(min(p[1] for p in uvs))
    return [(p[0] - du, p[1] - dv) for p in uvs]


def half_float_room(uvs):
    """Whether a face's coordinates, rebased, stay where half floats are fine (under HALF_FINE repeats): the face spans
    fewer repeats than that. False means a cut of the piece, or a larger repeat, is needed."""
    if not uvs:
        return True
    return max(max(p[0] for p in uvs) - min(p[0] for p in uvs), max(p[1] for p in uvs) - min(p[1] for p in uvs)) < HALF_FINE
