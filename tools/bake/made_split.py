"""Made pieces past the sizes the game is known to take, cut into pieces it takes (custom geometry editing plan, B4,
decision D-3, 19 November 2026: the user keeps growing these walls and floors as much as they want).

A wall of any length is cut into lengths of at most MAX_TILES tiles, joined end to end (the compiler's wall_joins gives
them 'line' ends, as two walls drawn end to end have, and a break passes between them); each cut is a tile edge as far
along as it goes outside every opening. A wall taller than its look's storeys is its look's storeys stacked: as many
whole donors as go, then pieces one storey tall where the look can be made one storey (frac_wall.storeys_of), each
standing on the top of the one under it (one piece's bottom on the other's top: no face is doubled). A slab of any
size is cut into pieces of at most MAX_TILES by MAX_TILES tiles. Ground shapes don't break and are not cut.

Each piece is its own numbers in its own frame (x0 0, its openings or holes cut to it and moved into it) with `whole`:
where it sits in the whole piece, so its texture (frac_wall, frac_slab) and a measured look's paint (frac_walls
in_frame) go on across the cuts. The compiler makes each piece a copy of its own; the editor's mesh server
(viewer/generated.py) joins them into one mesh, so the page draws what the Build makes. A piece no cut leaves is the
numbers as they are.

Numbers in the free form (`free: 1`; custom geometry improvements plan, stage 2) are cut at any size: along at tile
edges counted from the frame's origin, at most MAX_TILES apart, each as far along as it goes outside every opening or
hole, the last piece whatever is left (a tail under MIN_PIECE, which its own end or its fracture would eat, shares the
cut before it, which moves back a tile: free_cuts). A wall taller than its look is cut up by its `tall`: 'repeat',
its look's height stacked while a storey of the look or more would be left over one more, the top piece the rest
(lengthened or shortened, so no sliver is made: repeat_heights); 'stretch', one piece up to twice its look's height,
else bands of equal height no taller than its look, each a `band` [lo, hi] of the one stretched outline (frac_wall,
wall_profile.windowed). Every piece keeps the whole's seed (its cells come from a lattice counted in the whole's
frame) and has `whole`: a wall's [its place along (from the whole's x0), the whole's length, its place up (its
floor's height in the whole's frame), the whole's height, the whole's x0], a slab's [its place along x, along y (from
the whole's x0 and y0), the whole's width, depth, the whole's x0, y0], so a generator reads where the piece's frame
starts in the whole's (frac_wall.whole_origin, slab_cells.origin). A free slab's piece is kept where the slab
generator finds some of it left (slab_cells.FreeSlab)."""
import math

import frac_slab
import free_form
from free_form import NumbersError
import slab_cells

TILE = 96.0
MAX_TILES = 16
MAX_STOREYS = 12
SEED_STEP = 7919
MIN_PIECE = 48.0    # units: a free piece's least length; a shorter tail shares the cut before it (free_cuts)


def levels(storeys, own, lower):
    """The storeys of each piece of a wall `storeys` tall, from the bottom: one piece when its look is made that tall
    (its own storeys, or one where it can be made one storey: `lower`); else its look's own as many times as they go,
    then one-storey pieces where it can be made one storey, else its own storeys once more."""
    if storeys == own or (storeys == 1 and lower):
        return [storeys]
    out = [own] * (storeys // own)
    rest = storeys - own * len(out)
    if rest:
        out += [1] * rest if lower else [own]
    return out


def cuts(length, spans):
    """The cuts of a run `length` long (from 0), tile edges at most MAX_TILES apart, each as far along as it goes
    outside every span ((a, b): an opening's or a hole's), else MAX_TILES along."""
    tiles = int(round(length / TILE))
    out, start = [], 0
    while tiles - start > MAX_TILES:
        step = MAX_TILES
        for k in range(MAX_TILES, 0, -1):
            b = (start + k) * TILE
            if not any(a + 1e-6 < b < c - 1e-6 for a, c in spans):
                step = k
                break
        start += step
        out.append(start * TILE)
    return out


def _seed(seed, k):
    return seed if k == 0 else (int(seed) + SEED_STEP * k - 1) % 999999 + 1


def wall_pieces(wall, look_storeys, heights, ends=False):
    """[(dx, dz, numbers)] of a made wall: each piece's place in the wall's frame (along it, up) and its numbers.
    `look_storeys(numbers)` gives (own storeys, whether one storey can be made) of the wall's look; `heights(numbers)`
    a piece's (bottom, top) in its frame. `ends`: give the pieces their end styles (the joints 'line', the wall's own
    ends at its ends) for drawing; the compiler's wall_joins works them out from where the pieces stand. Free-form
    numbers: free_wall_pieces, which asks `look_storeys` and `heights` of the look alone (its numbers' look, no size)."""
    if free_form.is_free(wall):
        return free_wall_pieces(wall, look_storeys, heights, ends)
    x0, x1 = float(wall['x0']), float(wall['x1'])
    own, lower = look_storeys(wall)
    storeys = wall.get('storeys') or own
    openings = wall.get('openings') or []
    xs = [x0] + [x0 + c for c in cuts(x1 - x0, [(o['x0'] - x0, o['x1'] - x0) for o in openings])] + [x1]
    stack = levels(storeys, own, lower)
    if len(xs) == 2 and len(stack) == 1:
        return [(0.0, 0.0, wall)]
    keep = {k: v for k, v in wall.items() if k not in ('x0', 'x1', 'openings', 'storeys', 'ends', 'seed', 'whole')}
    wall_ends = list(wall.get('ends') or ('free', 'free'))
    out, dz, k = [], 0.0, 0
    for n in stack:
        level = dict(keep, x0=0.0, x1=1.0, **({'storeys': 1} if n == 1 and own != 1 else {}))
        bottom, top = heights(level)
        for j, (a, b) in enumerate(zip(xs, xs[1:])):
            piece = dict(level, x0=0.0, x1=b - a, seed=_seed(wall.get('seed', 1), k))
            gaps = []
            for o in openings:
                ox0, ox1 = max(o['x0'], a), min(o['x1'], b)
                oz0, oz1 = max(o['z0'], dz + bottom), min(o['z1'], dz + top)
                if ox1 - ox0 > 1e-6 and oz1 - oz0 > 1e-6:
                    gaps.append(dict(x0=ox0 - a, x1=ox1 - a, z0=oz0 - dz, z1=oz1 - dz))
            k += 1
            # (a piece an opening takes whole is no piece)
            if any(g['x0'] <= 1e-6 and g['x1'] >= b - a - 1e-6 and g['z0'] <= bottom + 1e-6 and g['z1'] >= top - 1e-6
                   for g in gaps):
                continue
            piece['openings'] = gaps
            if len(xs) > 2:
                piece['whole'] = [a - x0, x1 - x0]
            if ends:
                e = [wall_ends[0] if j == 0 else 'line', wall_ends[1] if j == len(xs) - 2 else 'line']
                if e != ['free', 'free']:
                    piece['ends'] = e
            out.append((a - x0, dz, piece))
        dz += top - bottom
    return out


def solid(width, depth, holes):
    """Whether a slab `width` by `depth` (whole tiles from 0) keeps a tile its `holes` (in its frame; they may
    overlap) leave: one whose centre is in no hole."""
    return any(not any(h['x0'] < (i + 0.5) * TILE < h['x1'] and h['y0'] < (j + 0.5) * TILE < h['y1'] for h in holes)
               for i in range(int(round(width / TILE))) for j in range(int(round(depth / TILE))))


def slab_left(slab):
    """Whether the slab's holes leave any of it (its numbers: x0, x1, y0, y1, holes; free-form numbers as the slab
    generator finds it: free_left)."""
    if free_form.is_free(slab):
        return free_left(slab)
    x0, y0 = float(slab['x0']), float(slab['y0'])
    holes = [dict(x0=h['x0'] - x0, x1=h['x1'] - x0, y0=h['y0'] - y0, y1=h['y1'] - y0) for h in slab.get('holes') or []]
    return solid(float(slab['x1']) - x0, float(slab['y1']) - y0, holes)


def slab_pieces(slab):
    """[(dx, dy, numbers)] of a made slab: each piece's place in the slab's frame and its numbers (at most MAX_TILES
    by MAX_TILES tiles, its holes cut to it and moved into it, `whole` [dx, dy, width, depth]). Free-form numbers:
    free_slab_pieces."""
    if free_form.is_free(slab):
        return free_slab_pieces(slab)
    x0, x1, y0, y1 = (float(slab[k]) for k in ('x0', 'x1', 'y0', 'y1'))
    holes = slab.get('holes') or []
    xs = [x0] + [x0 + c for c in cuts(x1 - x0, [(h['x0'] - x0, h['x1'] - x0) for h in holes])] + [x1]
    ys = [y0] + [y0 + c for c in cuts(y1 - y0, [(h['y0'] - y0, h['y1'] - y0) for h in holes])] + [y1]
    if len(xs) == 2 and len(ys) == 2:
        return [(0.0, 0.0, slab)]
    keep = {k: v for k, v in slab.items() if k not in ('x0', 'x1', 'y0', 'y1', 'holes', 'seed', 'whole')}
    out, k = [], 0
    for b0, b1 in zip(ys, ys[1:]):
        for a0, a1 in zip(xs, xs[1:]):
            cut = []
            for h in holes:
                hx0, hx1, hy0, hy1 = max(h['x0'], a0), min(h['x1'], a1), max(h['y0'], b0), min(h['y1'], b1)
                if hx1 - hx0 > 1e-6 and hy1 - hy0 > 1e-6:
                    cut.append(dict(x0=hx0 - a0, x1=hx1 - a0, y0=hy0 - b0, y1=hy1 - b0))
            piece = dict(keep, x0=0.0, x1=a1 - a0, y0=0.0, y1=b1 - b0, holes=cut, seed=_seed(slab.get('seed', 1), k),
                         whole=[a0 - x0, b0 - y0, x1 - x0, y1 - y0])
            k += 1
            # (a piece all holes is no piece: its tiles are tested, the holes may overlap, review finding 32)
            if not solid(a1 - a0, b1 - b0, cut):
                continue
            out.append((a0 - x0, b0 - y0, piece))
    return out


# ---------------------------------------------------------------------------------------------------- the free form
def free_cuts(lo, hi, spans):
    """The cuts of a free run lo..hi (places in the frame): tile edges, counted from the frame's origin, at most
    MAX_TILES tiles apart, each as far along as it goes outside every span ((a, b): an opening's or a hole's) and at
    least MIN_PIECE past the cut before it, else as far as goes, through a span. A tail under MIN_PIECE shares the
    cut before it: that cut moves back a tile (to the nearest edge outside the spans that leaves the piece before it
    MIN_PIECE and the tail no longer than MAX_TILES), or goes where none does."""
    def clear(c):
        return not any(a + 1e-6 < c < b - 1e-6 for a, b in spans)
    longest = MAX_TILES * TILE
    out, start = [], float(lo)
    while hi - start > longest + 1e-9:
        far = math.floor((start + longest) / TILE + 1e-9) * TILE
        edges = [far - k * TILE for k in range(MAX_TILES + 1) if far - k * TILE >= start + MIN_PIECE - 1e-9]
        start = next((c for c in edges if clear(c)), far)
        out.append(start)
    if out and hi - out[-1] < MIN_PIECE - 1e-9:
        before = out[-2] if len(out) > 1 else float(lo)
        back = [out[-1] - k * TILE for k in range(1, MAX_TILES) if out[-1] - k * TILE >= before + MIN_PIECE - 1e-9]
        if back:
            out[-1] = next((c for c in back if clear(c)), back[0])
        else:
            out.pop()
    return out


def repeat_heights(height, look, storey):
    """The heights of a free 'repeat' wall's stacked pieces, from the bottom, for a wall `height` tall in a look
    `look` tall whose storey is `storey`: the look's height while a storey or more would be left over one more, then
    the rest (more or less than the look's height by under a storey: no sliver)."""
    out, left = [], float(height)
    while left - look >= storey - 1e-9:
        out.append(float(look))
        left -= look
    return out + [left]


def stretch_bands(height, look):
    """How many bands a free 'stretch' wall `height` tall in a look `look` tall is cut into: one up to twice the
    look's height, else as few of equal height as are no taller than the look."""
    return 1 if height <= 2 * look + 1e-9 else math.ceil(height / look - 1e-9)


def free_wall_pieces(wall, look_storeys, heights, ends=False):
    """wall_pieces of free-form numbers (the module's docstring): [(dx, dz, numbers)], each piece's place in the
    wall's frame (from its x0 along, from its floor up) and its numbers in its own frame, x0 0 and its bottom where the
    whole's is; `look_storeys` and `heights` as wall_pieces', asked of the look alone (its own storeys; its own
    bottom and top)."""
    x0, x1 = float(wall['x0']), float(wall['x1'])
    look = dict({k: wall[k] for k in ('look',) if k in wall}, x0=0.0, x1=1.0)
    own_bottom, own_top = (float(v) for v in heights(look))
    own, _ = look_storeys(look)
    tall = own_top - own_bottom
    z0, z1 = float(wall.get('z0', own_bottom)), float(wall.get('z1', own_top))
    height = z1 - z0
    openings = wall.get('openings') or []
    xs = [x0] + free_cuts(x0, x1, [(float(o['x0']), float(o['x1'])) for o in openings]) + [x1]
    levels = []                 # (its place up, its numbers' z0, z1 and band)
    if wall.get('tall', 'repeat') == 'stretch':
        n = stretch_bands(height, tall)
        edges = [z0 + height * k / n for k in range(n)] + [z1]
        for a, b in zip(edges, edges[1:]):
            levels.append((a - z0, dict(z0=z0 - (a - z0), z1=z1 - (a - z0), **({'band': [z0, z0 + (b - a)]} if n > 1 else {}))))
    else:
        dz = 0.0
        for h in repeat_heights(height, tall, tall / max(1, int(own))):
            levels.append((dz, dict(z0=z0, z1=z0 + h)))
            dz += h
    if len(xs) == 2 and len(levels) == 1:
        return [(0.0, 0.0, wall)]
    keep = {k: v for k, v in wall.items() if k not in ('x0', 'x1', 'openings', 'ends', 'whole', 'z0', 'z1', 'band',
                                                       'storeys')}
    wall_ends = list(wall.get('ends') or ('free', 'free'))
    out = []
    for dz, level in levels:
        bottom, top = level.get('band') or (level['z0'], level['z1'])
        for j, (a, b) in enumerate(zip(xs, xs[1:])):
            gaps = []
            for o in openings:
                ox0, ox1 = max(float(o['x0']), a), min(float(o['x1']), b)
                oz0, oz1 = max(float(o['z0']) - dz, bottom), min(float(o['z1']) - dz, top)
                if ox1 - ox0 > 1e-6 and oz1 - oz0 > 1e-6:
                    gaps.append(dict(x0=ox0 - a, x1=ox1 - a, z0=oz0, z1=oz1))
            # (a piece an opening takes whole is no piece)
            if any(g['x0'] <= 1e-6 and g['x1'] >= b - a - 1e-6 and g['z0'] <= bottom + 1e-6 and g['z1'] >= top - 1e-6
                   for g in gaps):
                continue
            whole = [a - x0, x1 - x0, dz, height, x0]
            piece = dict(keep, x0=0.0, x1=b - a, openings=gaps, whole=whole, **level)
            if ends:
                e = [wall_ends[0] if j == 0 else 'line', wall_ends[1] if j == len(xs) - 2 else 'line']
                if e != ['free', 'free']:
                    piece['ends'] = e
            out.append((a - x0, dz, piece))
    return out


def free_left(slab):
    """Whether free slab numbers keep any of the slab, as the slab generator finds it (slab_cells.FreeSlab, which
    refuses with code 'left' where its holes, their sides snapped, leave none); where its look can't be had here (a
    donor look not resolved, as the compiler may hold one), by the holes' own edges (covered). Other refusals are
    raised."""
    try:
        R = frac_slab.look_of(slab)
    except ValueError:
        x0, y0 = float(slab['x0']), float(slab['y0'])
        holes = [dict(x0=float(h['x0']) - x0, x1=float(h['x1']) - x0, y0=float(h['y0']) - y0, y1=float(h['y1']) - y0)
                 for h in slab.get('holes') or []]
        return not covered(float(slab['x1']) - x0, float(slab['y1']) - y0, holes)
    try:
        slab_cells.FreeSlab(slab, R)
    except NumbersError as error:
        if error.code == 'left':
            return False
        raise
    return True


def covered(width, depth, holes):
    """Whether the `holes` (rectangles in a slab 0..width by 0..depth; they may overlap, and reach past it) cover all
    of it: each part of it between the holes' edges, wider and deeper than the slab generator's snap
    (slab_cells.SNAP), in one of them."""
    xs = sorted({0.0, width} | {min(max(float(h[k]), 0.0), width) for h in holes for k in ('x0', 'x1')})
    ys = sorted({0.0, depth} | {min(max(float(h[k]), 0.0), depth) for h in holes for k in ('y0', 'y1')})
    for a, b in zip(xs, xs[1:]):
        for c, d in zip(ys, ys[1:]):
            if b - a > slab_cells.SNAP and d - c > slab_cells.SNAP and not any(
                    h['x0'] <= (a + b) / 2 <= h['x1'] and h['y0'] <= (c + d) / 2 <= h['y1'] for h in holes):
                return False
    return True


def free_slab_pieces(slab):
    """slab_pieces of free-form numbers (the module's docstring): [(dx, dy, numbers)], each piece's place in the
    slab's frame (from its x0, y0) and its numbers in its own frame (from 0), its holes cut to it and moved into it,
    the whole's seed, `whole` [its place along x, along y, the whole's width, depth, the whole's x0, y0]; a piece of
    which nothing is left is no piece (free_left)."""
    x0, x1, y0, y1 = (float(slab[k]) for k in ('x0', 'x1', 'y0', 'y1'))
    holes = slab.get('holes') or []
    xs = [x0] + free_cuts(x0, x1, [(float(h['x0']), float(h['x1'])) for h in holes]) + [x1]
    ys = [y0] + free_cuts(y0, y1, [(float(h['y0']), float(h['y1'])) for h in holes]) + [y1]
    if len(xs) == 2 and len(ys) == 2:
        return [(0.0, 0.0, slab)]
    keep = {k: v for k, v in slab.items() if k not in ('x0', 'x1', 'y0', 'y1', 'holes', 'whole')}
    out = []
    for b0, b1 in zip(ys, ys[1:]):
        for a0, a1 in zip(xs, xs[1:]):
            cut = []
            for h in holes:
                hx0, hx1 = max(float(h['x0']), a0), min(float(h['x1']), a1)
                hy0, hy1 = max(float(h['y0']), b0), min(float(h['y1']), b1)
                if hx1 - hx0 > 1e-6 and hy1 - hy0 > 1e-6:
                    cut.append(dict(x0=hx0 - a0, x1=hx1 - a0, y0=hy0 - b0, y1=hy1 - b0))
            piece = dict(keep, x0=0.0, x1=a1 - a0, y0=0.0, y1=b1 - b0, holes=cut,
                         whole=[a0 - x0, b0 - y0, x1 - x0, y1 - y0, x0, y0])
            if free_left(piece):
                out.append((a0 - x0, b0 - y0, piece))
    return out
