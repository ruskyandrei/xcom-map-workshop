"""The game's cover rule for one tile, worked out against a map's pieces (tile_world.World), and the diagonal cover
finder (private/plans/todo/diagonal-cover-plan.md, stages C1 and C2). research/native/cover-build.md is the reading
of the exe this follows: its sections 3 (which directions) and 4 (one direction, steps 1 to 13), cited by step.

  cover(world, tile, ...)     a tile's cover flags, static bits and cover location, straight or diagonal
  finder(world, tile, ...)    whether a tile is one the game's build would give diagonal cover: it gets no straight
                              cover, and one of the four diagonals passes (the rule as a seeded tile has it)

A tile's inputs come from a `Tiles` view: its static flags and floor (from the map's bake, or worked out), and the
grid. Nothing here reads a package."""
import math

import numpy as np

S = 0.7071067811865476
# section 4's tables: the cover, low, peek-left, peek-right, climb-onto, climb-over and static bits; the straight and
# diagonal directions d and right vectors R; the tile delta (used only by step 8)
TABLE = [
    dict(name='N', cover=0x1, low=0x10, left=0x100, right=0x1000, onto=0x20000, over=0x200000, static=0x10,
         d=(0, 1), R=(-1, 0), dd=(-S, S), RR=(-S, -S), delta=(0, 1)),
    dict(name='S', cover=0x2, low=0x20, left=0x200, right=0x2000, onto=0x40000, over=0x400000, static=0x8,
         d=(0, -1), R=(1, 0), dd=(S, -S), RR=(S, S), delta=(0, -1)),
    dict(name='E', cover=0x4, low=0x40, left=0x400, right=0x4000, onto=0x80000, over=0x800000, static=0x2,
         d=(-1, 0), R=(0, -1), dd=(-S, -S), RR=(S, -S), delta=(1, 0)),
    dict(name='W', cover=0x8, low=0x80, left=0x800, right=0x8000, onto=0x100000, over=0x1000000, static=0x4,
         d=(1, 0), R=(0, 1), dd=(S, S), RR=(-S, S), delta=(-1, 0)),
]
LENGTH, DIAGONAL_LENGTH = 124.0, 135.744
UP = 52.0                       # the sweep's start over the floor (44 to 60 with its box)
EXTENT = (1.0, 1.0, 8.0)        # the sweep's box (half-size)
FACING = 0.71
BACK = 40.0                     # the cover location stands this far back from the wall
FLOOR_DOWN = 36.0
DIAGONAL = 0x10000
FLOOR, RAMP, OCCUPIED, PARTLY = 0x2000, 0x4000, 0x8000, 0x10000
LEVEL_FAMILY = ('XComLevelActor', 'XComOpacityFadeLevelActor', 'XComDestructibleActor', 'XComCollectible',
                'XComInteractiveLevelActor', 'XComLadder', 'XComMergedLevelActor')
FRAC_FAMILY = ('XComFracLevelActor', 'XComDecoFracLevelActor')
TILE = (96.0, 96.0, 64.0)


class Tiles:
    """The tile inputs the rule reads: `corner` (the game's tile corner, WorldBounds.Min), `dims`, and per tile its
    static flags (`flags`: {tile: u32}) and floor (`floor`: {tile: dict(loc, actor)})."""

    def __init__(self, corner, dims, flags, floor):
        self.corner, self.dims, self.flags, self.floor = tuple(corner), tuple(dims), flags, floor

    def position(self, tile):
        """The tile's position P0: the corner + (96x + 48, 96y + 48, 64z + 32)."""
        return np.array([self.corner[k] + TILE[k] * tile[k] + TILE[k] / 2 for k in range(3)])

    def inside(self, tile):
        return all(0 <= tile[k] < self.dims[k] for k in range(3))

    def at(self, point):
        """The tile holding a world point."""
        return tuple(int(math.floor((point[k] - self.corner[k]) / TILE[k])) for k in range(3))

    def flag(self, tile):
        return self.flags.get(tuple(tile), 0)

    def floor_when(self, tile, working):
        """Whether `tile` has a floor while the build works out the cover of tile `working`. The build's second pass
        goes tile by tile, x fastest, then y, then z, and its standing-room step takes a floor away before the tile's
        cover step: a tile not reached yet still has the floor its first pass found (its floor record, which the
        standing-room step leaves), one already passed has its last flags."""
        tile = tuple(tile)
        if (tile[2], tile[1], tile[0]) > (working[2], working[1], working[0]):
            return tile in self.floor or bool(self.flag(tile) & FLOOR)
        return bool(self.flag(tile) & FLOOR)


def straight_directions(tiles, tile):
    """The straight directions the build tests on a tile (section 3), indices into TABLE."""
    f = tiles.flag(tile)
    if f & OCCUPIED and not f & PARTLY:
        return []
    if f & OCCUPIED and f & PARTLY:
        return [0, 1, 2, 3]
    out = []
    for i, e in enumerate(TABLE):
        n = (tile[0] + (e['d'][0]), tile[1] + (e['d'][1]), tile[2])
        if not tiles.inside(n) or tiles.flag(n) & OCCUPIED:
            out.append(i)
    return out


def direction(world, tiles, tile, i, diagonal, why=None):
    """One direction's part of a tile's cover (section 4, steps 1 to 13): dict(flags, static, point (Q.x, Q.y, zQ),
    wall (W), hit (the piece), low), or None with `why` (a list) told the step that stopped it."""
    e = TABLE[i]
    d = np.array((e['dd'] if diagonal else e['d']) + (0,), float)
    R = np.array((e['RR'] if diagonal else e['R']) + (0,), float)
    length = DIAGONAL_LENGTH if diagonal else LENGTH
    p0 = tiles.position(tile)
    floor = tiles.floor[tuple(tile)]
    f = np.array([p0[0], p0[1], floor['loc'][2]])
    start = f + (0, 0, UP)
    end = start + d * length

    def no(step):
        if why is not None:
            why.append(step)
        return None
    # 1. the main sweep
    h = world.trace(start, end, EXTENT, 'cover')
    if h is None:
        return no('no hit')
    # 2. facing
    if abs(float(h['normal'] @ d)) < FACING:
        return no('facing %.3f' % abs(float(h['normal'] @ d)))
    # 4. refine: an engine sweep to the hit, which any blocking piece stops but one asking to be ignored for cover
    import tile_world
    r = world.trace(np.array([start[0], start[1], h['location'][2]]), h['location'], EXTENT, 'engine',
                    skip=lambda pc: pc.traced and tile_world.ignored_for_cover(pc))
    wall = r['location'] if r is not None else h['location']
    # 5. the cover location's candidate, inside the tile
    q = wall - BACK * d
    if not (abs(q[0] - p0[0]) < 48.0 and abs(q[1] - p0[1]) < 48.0):
        return no('location outside the tile')
    # 6. the floor under it
    fl = world.trace(np.array([q[0], q[1], p0[2]]), np.array([q[0], q[1], p0[2] - FLOOR_DOWN]), kind='engine')
    if fl is None:
        return no('no floor under the location')
    fp = fl['piece']
    if fp.cls in LEVEL_FAMILY + FRAC_FAMILY and fp.flags.get('bIsValidDestination') is False:
        return no('floor not a valid destination')
    zq = float(fl['location'][2])
    piece = h['piece']
    # 7. high or low
    if piece.force == 2:
        low = True
    elif piece.force == 1:
        low = False
    else:
        a = np.array([start[0], start[1], zq + 96.0])
        hh = world.trace(a, a + d * length, EXTENT, 'height')
        low = not (hh is not None and hh['piece'].force != 2)
    # 8. a low cover over a ramp of the same piece
    if low:
        n = (tile[0] + e['delta'][0], tile[1] + e['delta'][1], tile[2])
        nf = tiles.floor.get(n)
        if tiles.flag(n) & RAMP and nf and nf.get('actor') == piece.actor:
            return no('ramp of the same piece')
    # 9. the ignore flag
    if piece.ignore_flag == 1 and not low or piece.ignore_flag == 2 and low:
        return no('ignore flag')
    flags = e['cover'] | (e['low'] if low else 0)
    # 11. the step-outs
    for side, sign, bit in ((0, -1.0, e['left']), (1, 1.0, e['right'])):
        q2 = np.array([q[0], q[1], 0.0])
        side_v = sign * R
        clear = True
        for z in (zq + 96.0, zq + 60.0):
            a = q2 + (0, 0, z)
            if world.trace(a, a + side_v * 96.0, kind='cover') is not None:
                clear = False
                break
        if not clear:
            continue
        a = q2 + side_v * 68.0 + (0, 0, zq + 96.0)
        if world.trace(a, a + d * 96.0, kind='cover') is not None:
            continue
        g = world.trace(a, np.array([a[0], a[1], zq - 20.0]), kind='engine')
        if g is None:
            continue
        holder = tiles.at(g['location'] + (0, 0, 4.0))
        if not tiles.floor_when(holder, tile) or abs(float(g['location'][2]) - zq) >= 20.0:
            continue
        flags |= bit
    # 12. climbing, over low cover only
    if low:
        onto_ok = piece.cls in FRAC_FAMILY or piece.cls == 'XComDestructibleActor' or piece.flags.get('bCanClimbOnto')
        if onto_ok or piece.flags.get('bCanClimbOver'):
            a = np.array([q[0], q[1], zq + 88.0])
            if world.trace(a, a + d * 96.0, kind='height') is None:
                b = wall + d * 68.0
                top, bottom = np.array([b[0], b[1], zq + 160.0]), np.array([b[0], b[1], zq + 12.0])
                c = world.trace(top, bottom, kind='height')
                if c is None or float(c['location'][2]) - zq < 32.0:
                    flags |= e['over']
                elif onto_ok:
                    flags |= e['onto']
    return dict(flags=flags, static=e['static'], point=(float(q[0]), float(q[1]), zq),
                wall=tuple(float(v) for v in wall), hit=piece.name, low=low, inside=h['inside'],
                facing=round(abs(float(h['normal'] @ d)), 4), normal=tuple(round(float(v), 4) for v in h['normal']))


def cover(world, tiles, tile, diagonal, directions=None, notes=None):
    """A tile's cover: dict(flags (with DIAGONAL when `diagonal`), static (the bits the cover step adds), location
    (or None), parts {direction name: the direction's result}), over `directions` (default: section 3's). `notes`
    (a dict) gets each direction's stopping step."""
    if directions is None:
        directions = [0, 1, 2, 3] if diagonal else straight_directions(tiles, tile)
    flags, static, points, parts = DIAGONAL if diagonal else 0, 0, [], {}
    for i in directions:
        why = []
        r = direction(world, tiles, tile, i, diagonal, why)
        if notes is not None:
            notes[TABLE[i]['name']] = why[0] if why else 'cover'
        if r is None:
            continue
        parts[TABLE[i]['name']] = r
        flags |= r['flags']
        static |= r['static']
        points.append(r['point'])
    location = None
    if points:
        p0 = tiles.position(tile)
        mean = np.mean(np.array(points), axis=0)
        location = tuple(float(np.clip(mean[k], p0[k] - lim, p0[k] + lim)) for k, lim in enumerate((44.0, 44.0, 32.0)))
    return dict(flags=flags, static=static, location=location, parts=parts)


def candidate(tiles, tile):
    """Whether the build works out cover on a tile at all: a floor (0x2000), no ramp (0x4000), not fully occupied."""
    f = tiles.flag(tile)
    return bool(f & FLOOR) and not f & RAMP and tuple(tile) in tiles.floor and not (f & OCCUPIED and not f & PARTLY)


SQUARE = 0.999          # the finder's wall: within 2.6 degrees of the diagonal


def finder(world, tiles, tile, straight=False):
    """Whether a tile is one to give diagonal cover (findings register F-151): a wall at 45 degrees crosses it (the
    tile is partly occupied, and a diagonal's wall faces that diagonal to within 2.6 degrees, SQUARE) and gives high
    cover there, and the straight rule gives the tile no cover. On the game's own maps this takes 245 of the 289
    tiles the designers marked that a diagonal passes on, and 110 corners of the same kind they left unmarked; the
    marks are the designers' choice, not a rule, so the Build asks the finder only of tiles a project changes.

    dict(diagonal (the answer), cover (the diagonal cover), straight (the straight cover flags, or None when not
    worked out), partly, facing (the best diagonal's), high, notes). With `straight`, the straight cover is worked
    out on every tile a diagonal passes on, for a record."""
    notes = dict(diagonal={}, straight={})
    diag = cover(world, tiles, tile, True, notes=notes['diagonal'])
    f = tiles.flag(tile)
    partly = bool(f & OCCUPIED and f & PARTLY)
    facing = max((r['facing'] for r in diag['parts'].values()), default=0.0)
    high = any(not r['low'] for r in diag['parts'].values())
    shape = bool(diag['flags'] & 0xF) and partly and facing >= SQUARE and high
    plain = cover(world, tiles, tile, False, notes=notes['straight']) if shape or (straight and diag['parts']) else None
    found = shape and not plain['flags'] & 0xF
    return dict(diagonal=found, cover=diag, straight=plain['flags'] if plain else None, partly=partly, facing=facing,
                high=high, notes=notes)
