"""The free form of a made piece's numbers (custom geometry improvements plan, section 10.2), what the slab and ground
generators share of it (frac_slab.py, slab_cells.py, ground.py).

The numbers dict holds `free: 1`. Old numbers never hold `free`, so every old path stays byte for byte as it was. In
the free form a piece's extents are finite game units in its own frame, any size: no tile multiples, no tile minimum.

  is_free     whether numbers are in the free form (NumbersError for a `free` of another value)
  extents     x0 < x1, y0 < y1, z0 < z1 checked: finite numbers, each pair in order and at least MIN_SIZE apart; a size
              is never changed to fit
  mapping     the texture mapping (section 5) and its world origin checked: `mapping` {surfaces: {role: surface}} and
              `mappingOrigin` {role: place} as uv_mapping.py says, which each generator applies to its own surfaces'
              faces (a wall's 'faces', a slab's 'top' and 'underside', a ground shape's 'top' and 'sides')
  held        a face's texture coordinates as the mesh writer's half floats hold them (gen_mesh writes them so): whole
              repeats taken off each axis so they stay near 0, which keeps their place in the pattern (the phase); a
              face spanning so many repeats that no such shift keeps it under HALF_PHASE is refused, the error naming
              the half floats

Each refusal is a NumbersError, a ValueError with a code (code never decides by a message's words): 'free' (a `free`
of another value), 'number' (not a finite number), 'extent' (a pair out of order or too close), 'mapping', 'hole',
'left' (nothing of the piece left), 'chunk' (a piece larger than the splitter's chunk), 'points' (a rock's moved
points), 'whole' (a split piece's place) and 'half-floats' (texture coordinates no shift holds)."""
import math

import uv_mapping

# a half float's steps: 1/1024 of a repeat under 1, 1/32 from 32, half a repeat from 512, a whole repeat from 1,024 and
# none past 65,504 (struct's 'e' format refuses it). From HALF_PHASE out it holds whole numbers only, so a vertex there
# keeps no place within the repeat: every corner past it would draw the pattern from its start
HALF_PHASE = 1024.0
MIN_SIZE = 0.01      # the least extent of a free piece along an axis, in units: less is no solid to build


class NumbersError(ValueError):
    """A free piece's numbers refused: its reason in words, and `code` for the code that reads it."""

    def __init__(self, code, words):
        super().__init__(words)
        self.code = code


def number(v):
    """Whether `v` is a finite number (a bool is not)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def is_free(numbers):
    """Whether `numbers` are in the free form: `free` is 1. NumbersError ('free') for a `free` of any other value."""
    if not isinstance(numbers, dict) or 'free' not in numbers:
        return False
    if numbers['free'] != 1:
        raise NumbersError('free', 'the free form is free: 1 (the numbers have free: %r)' % (numbers['free'],))
    return True


def extents(numbers, what, axes='xyz'):
    """[x0, x1, y0, y1, z0, z1] (the axes asked for) of free numbers, checked: each a finite number, each pair's second
    past its first by MIN_SIZE or more. NumbersError ('number', 'extent') naming the pair otherwise."""
    out = []
    for a in axes:
        lo, hi = numbers.get(a + '0'), numbers.get(a + '1')
        if not (number(lo) and number(hi)):
            raise NumbersError('number', '%s needs %s0 and %s1, finite numbers (it has %r and %r)' % (what, a, a, lo, hi))
        if not hi - lo >= MIN_SIZE:
            raise NumbersError('extent', '%s runs from %s0 %g to %s1 %g: %s1 must be past %s0, by %g or more'
                               % (what, a, lo, a, hi, a, a, MIN_SIZE))
        out += [float(lo), float(hi)]
    return out


def mapping(numbers, what):
    """The numbers' texture mapping and its world origin checked (uv_mapping.check, check_origin): `mapping` absent or
    {surfaces: {role: surface}}, `mappingOrigin` absent or {role: place}. NumbersError ('mapping') saying what is
    wrong."""
    if 'mapping' in numbers and not isinstance(numbers['mapping'], dict):
        raise NumbersError('mapping', "%s's texture mapping is a dict of its surfaces (it has %r)" % (what, numbers['mapping']))
    try:
        if 'mapping' in numbers:
            uv_mapping.check(numbers['mapping'])
        uv_mapping.check_origin(numbers.get('mappingOrigin'))
    except uv_mapping.MappingError as error:
        raise NumbersError('mapping', "%s's texture mapping: %s" % (what, error)) from None


def held(uvs, what):
    """`uvs` [(u, v)] of one face with whole repeats taken off each axis, the middle of their range brought to the
    nearest whole number of 0: the same places in the pattern, as near 0 as they go. NumbersError ('half-floats') when
    the face spans so many repeats that its coordinates would still reach HALF_PHASE from 0."""
    out = [[float(u), float(v)] for u, v in uvs]
    for axis in (0, 1):
        values = [uv[axis] for uv in out]
        lo, hi = min(values), max(values)
        if not (math.isfinite(lo) and math.isfinite(hi)):
            raise NumbersError('number', "%s's texture coordinates are not finite" % what)
        k = math.floor((lo + hi) / 2 + 0.5)
        if max(hi - k, k - lo) >= HALF_PHASE:
            raise NumbersError('half-floats', "%s spans %.1f repeats of its texture along %s: the mesh's texture "
                               "coordinates are half floats, which keep a place within a repeat only under %d repeats "
                               "from 0, so one face can span about %d at most" % (what, hi - lo, 'uv'[axis],
                                                                                 HALF_PHASE, 2 * HALF_PHASE - 1))
        if k:
            for uv in out:
                uv[axis] -= k
    return [tuple(uv) for uv in out]
