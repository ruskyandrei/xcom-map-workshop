"""Rebuild volumes that stop short of tiles the battle's rebuild must not take (findings register F-149).

The battle rebuilds, for each XComRebuildWorldDataVolume, the tiles of a cube: the volume's bounds' centre, the bounds'
sphere radius either way on every axis (XGBattle.DoWorldDataRebuild; `span` is that rule, as native_copy.rebuild_order
reads it). So one volume over a box of tiles reaches past the box, and a tile with diagonal cover it reaches loses
that cover: the rebuild clears a tile and only a map's full build reads the cover seeds.

`fit` covers a box of tiles with cubes that reach none of the `forbidden` tiles; `pose` is a cube's centre and radius
in the world (the sphere its volume's bounds must have: native_copy.reach_box places a volume for it). A cube here is (x, y, z, k): k by k tiles from the
corner tile (x, y), `levels(k)` levels up from level z; k 0 is one tile on one level. Its faces stand EDGE inside the
tiles it takes, so it takes those and no others. A cube may hang over the grid's sides, its bottom and its top (the
game clamps it), and may take tiles outside the box that are not forbidden, as the one volume did.

Pure: no package is read here. native_copy.add_rebuild_volume calls it, and only for a volume that would reach a
forbidden tile; every other volume is made as before.
"""
import math

TILE = (96.0, 96.0, 64.0)
EDGE = 8.0          # how far inside its outer tiles a cube's faces stand
SINGLE = 24.0       # the radius of a cube over one tile on one level (native_copy.tile_volume's)


def span(centre, radius, corner, dims=None):
    """The tile ranges ((x0, x1), (y0, y1), (z0, z1)) the battle queues for a volume whose bounds have `centre` and
    sphere `radius`: the cube centre ± radius, counted from the game's tile `corner`, cut to a grid of `dims`."""
    out = []
    for k in range(3):
        lo = math.floor((centre[k] - radius - corner[k]) / TILE[k])
        hi = math.floor((centre[k] + radius - corner[k]) / TILE[k])
        out.append((lo, hi) if dims is None else (max(0, lo), min(dims[k] - 1, hi)))
    return tuple(out)


def centred(box, corner, dims=None):
    """The tile ranges (x0, x1, y0, y1, z0, z1) whose centres lie in a world box [x0, x1, y0, y1, z0, z1], or None
    for none: the tiles a rebuild volume is put there for (its box stands a little past them). Cut to a grid of
    `dims` when given (a grid being made larger is not: the box says how far it goes)."""
    out = []
    for k in range(3):
        lo = math.ceil((box[2 * k] - corner[k]) / TILE[k] - 0.5)
        hi = math.floor((box[2 * k + 1] - corner[k]) / TILE[k] - 0.5)
        if dims is not None:
            lo, hi = max(0, lo), min(dims[k] - 1, hi)
        if lo > hi:
            return None
        out += [lo, hi]
    return tuple(out)


def levels(k):
    """How many levels a cube k tiles wide takes, counted up from the level its bottom face stands in."""
    return 1 if k == 0 else math.floor((TILE[0] * k - EDGE) / TILE[2]) + 1


def width_for(n):
    """The narrowest cube that takes n levels."""
    k = 1
    while levels(k) < n:
        k += 1
    return k


def pose(cube, corner):
    """(centre, radius) in the world of a cube (x, y, z, k), for a grid counted from the game's tile `corner`."""
    x, y, z, k = cube
    if k == 0:
        return [corner[0] + TILE[0] * (x + 0.5), corner[1] + TILE[1] * (y + 0.5), corner[2] + TILE[2] * (z + 0.5)], SINGLE
    radius = TILE[0] * k / 2 - EDGE
    return [corner[0] + TILE[0] * (x + k / 2), corner[1] + TILE[1] * (y + k / 2),
            corner[2] + TILE[2] * z + EDGE + radius], radius


def tiles(cube):
    """The tile ranges (x0, x1, y0, y1, z0, z1) a cube takes, the grid's sides aside."""
    x, y, z, k = cube
    w = max(k, 1)
    return (x, x + w - 1, y, y + w - 1, z, z + levels(k) - 1)


def fit(need, forbidden):
    """Cubes that between them take every tile of the tile box `need` (x0, x1, y0, y1, z0, z1, each end counted in)
    that is not forbidden, and none of the `forbidden` tiles ((x, y, z), inside the box or not), in the order made:
    lowest level first, then y, then x. Each is the widest cube from its first tile toward +x and +y that fits, no
    wider than the box needs."""
    x0, x1, y0, y1, z0, z1 = need
    forbidden = set(forbidden)
    left = {(x, y, z) for z in range(z0, z1 + 1) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)} - forbidden
    out = []
    for cx, cy, cz in sorted(left, key=lambda t: (t[2], t[1], t[0])):
        if (cx, cy, cz) not in left:
            continue
        widest = max(x1 - cx + 1, y1 - cy + 1, width_for(z1 - cz + 1))
        best = (0, cz)
        for k in range(1, widest + 1):
            inside = [z for x, y, z in forbidden if cx <= x < cx + k and cy <= y < cy + k]
            if cz in inside:
                break
            under = max((z for z in inside if z < cz), default=None)
            over = min((z for z in inside if z > cz), default=None)
            n = levels(k)
            if over is not None and under is not None and over - under - 1 < n:
                break
            # from its first tile's level up, or down from under the forbidden tile over it
            low = cz if over is None or cz + n - 1 < over else over - n
            if under is not None and low <= under:
                break
            best = (k, low)
        cube = (cx, cy, best[1], best[0])
        out.append(cube)
        a = tiles(cube)
        left -= {(x, y, z) for z in range(max(a[4], z0), min(a[5], z1) + 1) for y in range(max(a[2], y0), min(a[3], y1) + 1)
                 for x in range(max(a[0], x0), min(a[1], x1) + 1)}
    return out
