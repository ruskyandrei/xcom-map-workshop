"""Made pieces past the sizes the game is known to take, cut into pieces it takes (custom geometry editing plan, B4,
decision D-3, 19 November 2026: the user, "let the user keep growing these walls/floors as much as they want").

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
numbers as they are."""

TILE = 96.0
MAX_TILES = 16
MAX_STOREYS = 12
SEED_STEP = 7919


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
    ends at its ends) for drawing; the compiler's wall_joins works them out from where the pieces stand."""
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
    """Whether the slab's holes leave any of it (its numbers: x0, x1, y0, y1, holes)."""
    x0, y0 = float(slab['x0']), float(slab['y0'])
    holes = [dict(x0=h['x0'] - x0, x1=h['x1'] - x0, y0=h['y0'] - y0, y1=h['y1'] - y0) for h in slab.get('holes') or []]
    return solid(float(slab['x1']) - x0, float(slab['y1']) - y0, holes)


def slab_pieces(slab):
    """[(dx, dy, numbers)] of a made slab: each piece's place in the slab's frame and its numbers (at most MAX_TILES
    by MAX_TILES tiles, its holes cut to it and moved into it, `whole` [dx, dy, width, depth])."""
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
