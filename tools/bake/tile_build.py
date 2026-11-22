"""The game's tile build for one tile's static flags and floor, worked out against a map's pieces (tile_world.World)
(diagonal cover plan, stage C2). research/native/cover-build.md is the reading of the exe this follows: section 1
(the order of work), 2 (occupancy and floor), 5 (the blocking bits); the cover step is tile_rule's.

  first_pass(world, tiles, tile)   pass 1: occupied, partly occupied, something near, the floor and its record
  second_pass(world, tiles, tile)  pass 2: standing room (taking the floor away, marking the two tiles above), the
                                   cover step, the twelve blocking bits

`tiles` is a tile_rule.Tiles whose flags and floors the passes read and write, so a region is built by running the
first pass over all of it, then the second (the build's order: x fastest, then y, then z, each pass over every tile
before the next)."""
import numpy as np

import tile_rule
import tile_world

NEAR = 0x20000
FLOOR, RAMP, OCCUPIED, PARTLY = tile_rule.FLOOR, tile_rule.RAMP, tile_rule.OCCUPIED, tile_rule.PARTLY
VALID = 0x400000
ROOM = 0x80000
DOWN_PATH, DOWN_SIGHT = 0x20, 0x800
BIG, SMALL = (48.0, 48.0, 32.0), (20.0, 20.0, 16.0)
LIFT = 28.0                     # the occupancy boxes' centres stand this far over their nominal place
# the six blocking directions: pathing bit, sight bit, the segment from the start
BLOCKS = ((0x2, 0x80, (-96.0, 0.0, 0.0)), (0x4, 0x100, (96.0, 0.0, 0.0)), (0x8, 0x200, (0.0, -96.0, 0.0)),
          (0x10, 0x400, (0.0, 96.0, 0.0)), (0x20, 0x800, (0.0, 0.0, -56.0)), (0x40, 0x1000, (0.0, 0.0, 56.0)))
BLOCK_EXTENT = (1.0, 1.0, 0.5)
LEVEL_FAMILY, FRAC_FAMILY = tile_rule.LEVEL_FAMILY, tile_rule.FRAC_FAMILY


def _occupies(piece):
    """The occupancy step's filter (case 0): a piece with the cover interface that ConsiderForOccupancy."""
    return piece.traced and piece.flags.get('bAlwaysConsiderForCover', True) and piece.cls != 'XComLadder'


def first_pass(world, tiles, tile):
    """Pass 1 for one tile (section 2): its static flags and floor record ({loc, normal, actor} or None), written into
    `tiles`. Returns the flags."""
    p = tiles.position(tile)
    centre = p + (0, 0, LIFT)
    # a PathBlockingVolume first: occupied, the six pathing bits by the stale mask, nothing else
    for lo, hi in world.blocking_volumes:
        if (lo <= centre + BIG).all() and (hi >= centre - BIG).all():
            tiles.flags[tuple(tile)] = OCCUPIED | 0x3F
            tiles.floor.pop(tuple(tile), None)
            return tiles.flag(tile)
    # something near: the octree query always finds the level's volumes that span the grid (the level volume, the
    # cursor volumes), so every tile has it (the bake's: every tile but those of PathBlockingVolumes)
    flags = NEAR
    near = True
    big = [pc for pc, _ in world.overlaps(centre, BIG, 'occupancy') if _occupies(pc)]
    if big:
        flags |= OCCUPIED
        small = [pc for pc, _ in world.overlaps(p + (0, 0, 16.0 + LIFT), SMALL, 'occupancy') if _occupies(pc)]
        if not small:
            flags |= PARTLY
    floor = None
    if near:
        floor = find_floor(world, p)
        if floor is not None:
            flags |= FLOOR | DOWN_PATH
            if floor['normal'][2] < 0.9848:
                flags |= RAMP
            pc = floor['piece']
            if (pc.cls in LEVEL_FAMILY or pc.cls in FRAC_FAMILY) and pc.flags.get('bIsValidDestination'):
                flags |= VALID
    tiles.flags[tuple(tile)] = flags
    if floor is not None:
        tiles.floor[tuple(tile)] = dict(loc=tuple(float(v) for v in floor['loc']),
                                        normal=tuple(float(v) for v in floor['normal']), actor=floor['piece'])
    else:
        tiles.floor.pop(tuple(tile), None)
    return flags


def find_floor(world, p):
    """The floor line (section 2, item 6): an engine line from 30 over the tile's position to 34 under it, its hits
    in order: one not bPathColliding is passed by, one not bCanStepUpOn ends the search, one facing up (z over 0.7)
    is the floor. dict(loc, normal, piece) or None."""
    start, end = p + (0, 0, 30.0), p - (0, 0, 34.0)
    hits = world.trace_all(start, end, kind='engine')
    for h in hits:
        pc = h['piece']
        if not pc.flags.get('bPathColliding'):
            continue
        if not pc.flags.get('bCanStepUpOn'):
            return None
        if h['normal'][2] > 0.7:
            return dict(loc=h['location'], normal=h['normal'], piece=pc)
    return None


def standing_room(tiles, tile):
    """Pass 2's standing-room step (section 2, item 7) for a floor tile: the two tiles over it get ROOM; the floor
    (FLOOR, RAMP, DOWN_PATH) goes when the tile is fully occupied and no ramp, or the tile over it is fully
    occupied."""
    f = tiles.flag(tile)
    if not f & FLOOR:
        return
    for n in (1, 2):
        up = (tile[0], tile[1], tile[2] + n)
        if tiles.inside(up):
            tiles.flags[up] = tiles.flag(up) | ROOM
    above = tiles.flag((tile[0], tile[1], tile[2] + 1))
    full = lambda v: v & OCCUPIED and not v & PARTLY  # noqa: E731
    if (full(f) and not f & RAMP) or full(above):
        tiles.flags[tuple(tile)] = f & ~(FLOOR | RAMP | DOWN_PATH)


def blocking(world, tiles, tile):
    """The blocking bits (section 5) for a tile that had NEAR: pathing (world trace type 3) and sight (type 4), six
    ways from 64 over its floor (a ramp: 32, its floor's piece passed by) or its position. Returns the bits."""
    f = tiles.flag(tile)
    floor = tiles.floor.get(tuple(tile)) if f & FLOOR else None
    p = tiles.position(tile)
    ramp_piece = None
    if floor is not None:
        start = np.array(floor['loc'], float) + (0, 0, 32.0 if f & RAMP else 64.0)
        if f & RAMP:
            ramp_piece = floor.get('actor')
    else:
        start = p
    skip_x = skip_y = False
    if f & RAMP and floor is not None:
        n = floor.get('normal') or (0, 0, 1)
        has_x, has_y = abs(n[0]) > 1e-4, abs(n[1]) > 1e-4
        skip_x, skip_y = (True, False) if has_x and not has_y else (False, True) if has_y and not has_x else (True, True)
    bits = 0
    for i, (path, sight, seg) in enumerate(BLOCKS):
        if i < 2 and skip_x or 2 <= i < 4 and skip_y:
            continue
        end = start + np.array(seg)
        ignore = ramp_piece if isinstance(ramp_piece, tile_world.Piece) else None
        # (a pathing hit whose tile is a ramp with that piece as its floor does not count: section 4, type 3)
        for h in world.trace_all(start, end, BLOCK_EXTENT, 'pathing'):
            if h['piece'] is ignore or _ramp_of(tiles, h):
                continue
            bits |= path
            break
        if world.trace(start, end, BLOCK_EXTENT, 'sight', ignore=ignore) is not None:
            bits |= sight
    if f & FLOOR:
        bits |= DOWN_PATH
        pc = floor.get('actor') if floor else None
        if isinstance(pc, tile_world.Piece) and (pc.cls in LEVEL_FAMILY or pc.cls in FRAC_FAMILY) \
                and pc.flags.get('bBlockUnitVisibility'):
            bits |= DOWN_SIGHT
    return bits


def _ramp_of(tiles, hit):
    """Whether a hit's tile is a ramp whose floor is the hit's piece."""
    t = tiles.at(hit['location'])
    if not tiles.flag(t) & RAMP:
        return False
    f = tiles.floor.get(t)
    return f is not None and f.get('actor') is hit['piece']


def second_pass(world, tiles, tile, near_at_start):
    """Pass 2 for one tile: standing room, the cover step (tile_rule.cover; its static bits), the blocking bits for a
    tile that had NEAR at the start of the pass (`near_at_start`). Returns (the tile's cover result or None)."""
    standing_room(tiles, tile)
    result = None
    if tile_rule.candidate(tiles, tile):
        result = tile_rule.cover(world, tiles, tile, False)
        tiles.flags[tuple(tile)] = tiles.flag(tile) | result['static']
    if near_at_start:
        tiles.flags[tuple(tile)] = tiles.flag(tile) | blocking(world, tiles, tile)
    return result
