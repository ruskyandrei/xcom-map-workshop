"""A made piece's texture mapping (the custom geometry improvements plan, section 5): how a surface of a wall, floor,
roof or ground piece takes its texture when its look's own mapping is replaced. One rule for the three generators
(frac_wall.py, frac_slab.py, ground.py) and the editor's preview, which reaches it through them.

A free-form piece's numbers may carry `mapping` {surfaces: {role: surface}}, a role one of 'faces' (a wall's two
faces), 'top', 'underside' (a slab's) and 'sides' (a ground shape's); a role not listed keeps its look's mapping. A
surface:

  mode      'size': `u` and `v` are game units per repeat (a 96-wide brick pattern keeps its bricks' size as the wall
            grows); 'count': `u` and `v` are repeats across the whole surface (fractions too: three stay three after a
            resize); 'fit': one repeat over the whole surface (`u` and `v` are read as 1). `modeV`, when given, is the
            mode along v, so a surface can tile along u and fit along v.
  turn      degrees the pattern is turned about its origin
  flipU, flipV   the pattern mirrored along u or v
  offsetU, offsetV   the pattern slid, in repeats
  world     the pattern's origin is the world's (adjoining surfaces line up), not the piece's own frame's

A point of a surface is given as (a, b): its place in game units on the surface's two axes, in the piece's frame (a
wall's face: a along the wall, b up; a top or underside: a along x, b along y; a ground side: a along it, b up). The
surface's extent (a0, a1, b0, b1) is the whole logical piece's (a piece of a split wall or slab reads it from the
whole: frac_wall/frac_slab `whole`), so a fit or a count goes on across the cuts. `origin` (a, b) is where the piece's
frame stands on the surface's axes in the world, for a world-aligned surface (the compiler and the Build know the
pose; the generator is handed it).

The order is the editor's and the Build's alike: the point scaled to repeats by the mode, mirrored, turned, then slid by
the offsets.

Made meshes write texture coordinates as half floats (gen_mesh.py: steps of 1/32 of a repeat from 32 repeats out, of a
whole repeat from 1,024, nothing past 65,504): rebased() takes whole repeats off a face's coordinates so they stay near
0, keeping the pattern's phase (for a surface that tiles), and half_float_room() says whether a face's span still
fits."""
import math

ROLES = ('faces', 'top', 'underside', 'sides')
MODES = ('size', 'fit', 'count')
HALF_MAX = 65504.0          # the largest half float
HALF_FINE = 1024.0          # past this a half float's step is a whole repeat or more


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


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def surface_of(numbers, role):
    """A piece's mapping of one surface, or None for its look's own."""
    m = (numbers or {}).get('mapping')
    return ((m or {}).get('surfaces') or {}).get(role) if m else None


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
    (a world-aligned surface's)."""
    a0, a1, b0, b1 = extent
    if surface.get('world'):
        a, b = a + origin[0], b + origin[1]
        a0, a1, b0, b1 = a0 + origin[0], a1 + origin[0], b0 + origin[1], b1 + origin[1]
    mode_u, mode_v = surface['mode'], surface.get('modeV', surface['mode'])
    U = _scaled(a, mode_u, float(surface['u']), a0, a1)
    V = _scaled(b, mode_v, float(surface['v']), b0, b1)
    if surface.get('flipU'):
        U = -U
    if surface.get('flipV'):
        V = -V
    turn = math.radians(float(surface.get('turn', 0.0)))
    if turn:
        c, s = math.cos(turn), math.sin(turn)
        U, V = U * c - V * s, U * s + V * c
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
