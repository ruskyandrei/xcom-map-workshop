"""A free-form slab's fragments and collision (custom geometry improvements plan, 4.3; the free form, 10.2):
frac_slab.build makes a slab whose numbers hold `free: 1` (free_form.py) from what FreeSlab gives.

The numbers: x0 < x1, y0 < y1 (the footprint: any finite values in the piece's frame), z0 < z1 (its underside and its
top), holes [dict(x0, x1, y0, y1)] (rectangles anywhere inside the footprint, overlapping or not), seed, look, and for
a piece of a split slab `whole` [dx, dy, W, D] (as made_split gives it: where the piece's frame starts from the whole's
corner, the whole's width and depth), with the whole's corner in its own frame as two more numbers, [dx, dy, W, D, cx,
cy], where that corner is not the frame's origin (origin and extent read it: where the piece's frame starts in the
whole's, and the whole's footprint, which a texture mapping's top and underside read).

  lattice      cells of the look's tile t counted from the frame's origin: cell (i, j) is [i t, (i + 1) t] by
               [j t, (j + 1) t] of the whole slab's frame (a piece of a split slab reads it from its `whole` place, so
               its cells are the whole's)
  cut cells    each cell cut by the footprint and the holes: what is left of it is rectangles (a grid of the cell's and
               the holes' sides, its solid parts joined in runs), one fragment for each connected group of them. A cell
               a hole cuts in two is two fragments; an L of a cell is one fragment of two faces
  whole cells  a cell neither cut nor holed takes a pattern from a hash of (seed, i, j): a whole tile, its two halves
               on a diagonal (the look's `split` share), or one of two cells side by side (its `long` share, its axis
               from the hash). Pairs have fixed places on the lattice, cells (2k, 2k + 1) along x and along y: an x
               pair is made where both cells are whole and either wants one, then a y pair among the cells left; a
               cell whose own way has no whole partner wants the other way. A cell's pattern so depends only on the
               cells within two of it, and a size change re-rolls only the cells near what it cuts
  least width  a cut cell's piece whose box is thinner than LEAST joins the fragment beside it that it shares the most
               edge with (one not thin, or a thin one already joined to one); one that touches none stays its own
  faces        each fragment a list of convex polygons, anticlockwise: two of a fragment's that share a whole edge and
               make a convex polygon together are one. Every polygon has a corner at each other polygon's corner on
               its sides (frac_wall.insert_points), so neighbours' edges meet exactly, and starts at a corner its next
               two are not in line with (the face's tangent is read from its first three)
  coordinates  values closer than SNAP are one (the footprint's kept first, then a hole's, then the lattice's), so no
               sliver thinner than that is made
  collision    boxes over the footprint less its holes (cut into strips at the holes' sides, each strip's runs clear of
               holes one box, neighbouring strips with the same runs joined), between the look's collision heights at
               their distances from its plate's bottom and top, so they move with the plate's (a roof's, 2 under its
               drawn top: thickened, its bottom follows the underside); the plate's own where that leaves none"""
import bisect
import hashlib
import math

import frac_wall
import free_form
from free_form import NumbersError

SNAP = 2e-3          # values closer than this are one
LEAST = 8.0          # a cut cell's piece thinner than this joins the fragment beside it


def roll(seed, i, j, k):
    """A number in [0, 1) from (seed, i, j, k), the same on every computer."""
    digest = hashlib.md5(('%d|%d|%d|%d' % (seed, i, j, k)).encode()).digest()
    return int.from_bytes(digest[:8], 'little') / 2.0 ** 64


def origin(slab):
    """Where the piece's frame starts in the whole slab's frame (its `whole` place; (0, 0) for a slab not split)."""
    whole = slab.get('whole')
    if whole is None:
        return (0.0, 0.0)
    if not (isinstance(whole, (list, tuple)) and len(whole) in (4, 6) and all(free_form.number(v) for v in whole)
            and whole[2] > 0 and whole[3] > 0):
        raise NumbersError('whole', "a split slab's piece's place is [dx, dy, W, D] or [dx, dy, W, D, cx, cy], finite "
                           "numbers, W and D over 0 (it has %r)" % (whole,))
    corner = (float(whole[4]), float(whole[5])) if len(whole) == 6 else (0.0, 0.0)
    return (float(whole[0]) + corner[0], float(whole[1]) + corner[1])


def extent(slab):
    """The whole slab's footprint (x0, x1, y0, y1) in the whole's frame, as a texture mapping reads its top and
    underside: a piece of a split slab's from its `whole` (its corner, to that and its width and depth), else its own
    numbers' (checked as origin checks them)."""
    whole = slab.get('whole')
    if whole is None:
        return (float(slab['x0']), float(slab['x1']), float(slab['y0']), float(slab['y1']))
    origin(slab)
    cx, cy = (float(whole[4]), float(whole[5])) if len(whole) == 6 else (0.0, 0.0)
    return (cx, cx + float(whole[2]), cy, cy + float(whole[3]))


class Snapped:
    """Values closer than SNAP made one: each run of values with no gap over SNAP given its best (the lowest rank, then
    the lowest value), so the values left are more than SNAP apart."""

    def __init__(self, ranked):
        self.value = {}
        group = []
        for v, rank in sorted(ranked):
            if group and v - group[-1][0] > SNAP:
                self._close(group)
                group = []
            group.append((v, rank))
        if group:
            self._close(group)
        self.keys = sorted(self.value)

    def _close(self, group):
        best = min(group, key=lambda g: (g[1], g[0]))[0]
        for v, _ in group:
            self.value[v] = best

    def __call__(self, v):
        if v in self.value:
            return self.value[v]
        k = bisect.bisect_left(self.keys, v)
        near = min(self.keys[max(0, k - 1):k + 1], key=lambda q: abs(q - v))
        return self.value[near] if abs(near - v) <= SNAP else v


class FreeSlab:
    """A free slab's numbers checked (NumbersError) and laid out: `box` [x0, x1, y0, y1, z0, z1], `origin`, `holes`
    (each (x0, x1, y0, y1) clipped to the footprint, on the snapped values), `collision` (its heights); fragments()
    and solids() as the module's words say."""

    def __init__(self, slab, R):
        what = 'a free slab'
        self.box = free_form.extents(slab, what)
        self.x0, self.x1, self.y0, self.y1, self.z0, self.z1 = self.box
        free_form.mapping(slab, what)
        seed = slab.get('seed', 1)
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise NumbersError('number', "a slab's seed is a whole number (it has %r)" % (seed,))
        self.seed = seed
        self.t, self.split, self.long = float(R['tile']), float(R['split']), float(R['long'])
        self.origin = origin(slab)
        holes = slab.get('holes') or []
        if not isinstance(holes, list):
            raise NumbersError('hole', "a slab's holes are a list (it has %r)" % (holes,))
        raw = []
        for h in holes:
            if not isinstance(h, dict):
                raise NumbersError('hole', 'a hole needs its sides, x0, x1, y0 and y1: %r' % (h,))
            hx0, hx1, hy0, hy1 = free_form.extents(h, 'a hole', 'xy')
            if not (self.x0 - SNAP <= hx0 and hx1 <= self.x1 + SNAP and self.y0 - SNAP <= hy0 and hy1 <= self.y1 + SNAP):
                raise NumbersError('hole', 'a hole outside its slab: %r (the slab is %g to %g by %g to %g)'
                                   % (h, self.x0, self.x1, self.y0, self.y1))
            raw.append((max(hx0, self.x0), min(hx1, self.x1), max(hy0, self.y0), min(hy1, self.y1)))
        ox, oy = self.origin
        self.sx = Snapped([(self.x0, 0), (self.x1, 0)] + [(v, 1) for h in raw for v in h[:2]]
                          + [(v, 2) for v in self._lines(self.x0, self.x1, ox)])
        self.sy = Snapped([(self.y0, 0), (self.y1, 0)] + [(v, 1) for h in raw for v in h[2:]]
                          + [(v, 2) for v in self._lines(self.y0, self.y1, oy)])
        if self.sx(self.x1) != self.x1 or self.sy(self.y1) != self.y1:
            raise NumbersError('extent', "the holes' sides stand closer than %g to each other right across the slab"
                               % SNAP)
        snapped = [(self.sx(h[0]), self.sx(h[1]), self.sy(h[2]), self.sy(h[3])) for h in raw]
        self.holes = [h for h in snapped if h[0] < h[1] and h[2] < h[3]]
        c0, c1 = (float(v) for v in R['collision'])
        lo, hi = self.z0 + (c0 - float(R['bottom'])), self.z1 - (float(R['top']) - c1)
        self.collision = (lo, hi) if hi - lo >= SNAP else (self.z0, self.z1)
        if not self.solids():
            # (as frac_wall's openings: nothing would be left to build, review finding 32)
            raise NumbersError('left', "the slab's holes leave none of it")

    def _lines(self, lo, hi, shift):
        """The lattice's lines from lo - SNAP to hi + SNAP, in the piece's frame."""
        t = self.t
        return [i * t - shift for i in range(math.ceil((lo + shift - SNAP) / t), math.floor((hi + shift + SNAP) / t) + 1)]

    # ------------------------------------------------------------------------------------------------ the collision
    def solids(self):
        """The collision boxes [(lo, hi)]: the footprint less its holes, between the collision heights."""
        xs = sorted({self.x0, self.x1} | {v for h in self.holes for v in h[:2]})
        strips = []
        for a, b in zip(xs, xs[1:]):
            m = (a + b) / 2
            cut = sorted((h[2], h[3]) for h in self.holes if h[0] < m < h[1])
            runs, y = [], self.y0
            for h0, h1 in cut:
                if h0 > y:
                    runs.append((y, h0))
                y = max(y, h1)
            if y < self.y1:
                runs.append((y, self.y1))
            if strips and strips[-1][2] == runs and strips[-1][1] == a:
                strips[-1][1] = b
            else:
                strips.append([a, b, runs])
        z0, z1 = self.collision
        return [((a, y0, z0), (b, y1, z1)) for a, b, runs in strips for y0, y1 in runs]

    # ------------------------------------------------------------------------------------------------ the cells
    def cells(self):
        """{(i, j): (x0, x1, y0, y1, whole, holes)} of the lattice's cells the footprint reaches: each cut to the
        footprint, on the snapped values, whether it is whole (neither cut nor holed), and the holes that reach it."""
        t, (ox, oy) = self.t, self.origin
        out = {}
        for i in range(math.floor((self.x0 + ox) / t), math.ceil((self.x1 + ox) / t)):
            a, b = i * t - ox, (i + 1) * t - ox
            lo, hi = self.sx(max(self.x0, a)), self.sx(min(self.x1, b))
            if lo >= hi:
                continue
            whole_x = self.x0 - a <= SNAP and b - self.x1 <= SNAP
            for j in range(math.floor((self.y0 + oy) / t), math.ceil((self.y1 + oy) / t)):
                c, d = j * t - oy, (j + 1) * t - oy
                blo, bhi = self.sy(max(self.y0, c)), self.sy(min(self.y1, d))
                if blo >= bhi:
                    continue
                holes = [h for h in self.holes if h[0] < hi and h[1] > lo and h[2] < bhi and h[3] > blo]
                whole = whole_x and self.y0 - c <= SNAP and d - self.y1 <= SNAP and not holes
                out[(i, j)] = (lo, hi, blo, bhi, whole, holes)
        return out

    def patterns(self, whole):
        """The whole cells' patterns: (kind {cell: 'tile', 'split' or 'long'}, pairs {first cell: 'x' or 'y'}, the cells
        the pairs take). Each cell has a kind, an axis and a turn from the hash; of a pair's place (two whole cells),
        the cell whose turn comes first decides, as the old slabs' shuffled order had the cell met first take its free
        neighbour: an x pair where it is long and wants x (its axis, or its y partner is not whole), then a y pair
        among the cells left where it is long (its axis y, or its x pair not made). The shares of tiles split and
        joined so stay near the old slabs' for the same look (the looks' shares were fitted on those)."""
        kind, axis, turn = {}, {}, {}
        for i, j in whole:
            r = roll(self.seed, i, j, 0)
            kind[(i, j)] = 'split' if r < self.split else 'long' if r < self.split + self.long else 'tile'
            axis[(i, j)] = 'x' if roll(self.seed, i, j, 1) < 0.5 else 'y'
            turn[(i, j)] = roll(self.seed, i, j, 3)
        pairs, taken = {}, set()
        for i, j in sorted(whole):
            other = (i + 1, j)
            if i % 2 or other not in whole:
                continue
            first = min(((i, j), other), key=lambda c: turn[c])
            if kind[first] == 'long' and (axis[first] == 'x' or (first[0], first[1] ^ 1) not in whole):
                pairs[(i, j)] = 'x'
                taken |= {(i, j), other}
        for i, j in sorted(whole):
            other = (i, j + 1)
            if j % 2 or other not in whole or (i, j) in taken or other in taken:
                continue
            first = min(((i, j), other), key=lambda c: turn[c])
            if kind[first] == 'long':
                pairs[(i, j)] = 'y'
                taken |= {(i, j), other}
        return kind, pairs, taken

    # ------------------------------------------------------------------------------------------------ the fragments
    def fragments(self):
        """The fragments: [[polygon [(x, y)] anticlockwise, ...]], each polygon convex (see the module's words)."""
        cells = self.cells()
        whole = {c for c, v in cells.items() if v[4]}
        kind, pairs, taken = self.patterns(whole)
        frags = []          # dict(polys, cells, thin)
        for i, j in sorted(cells, key=lambda c: (c[1], c[0])):
            lo, hi, blo, bhi, is_whole, holes = cells[(i, j)]
            if not is_whole:
                for rects in groups(cut_cell(lo, hi, blo, bhi, holes)):
                    w = max(r[1] for r in rects) - min(r[0] for r in rects)
                    h = max(r[3] for r in rects) - min(r[2] for r in rects)
                    frags.append(dict(polys=[_rect(*r) for r in rects], cells=[(i, j)], thin=min(w, h) < LEAST))
                continue
            if (i, j) in pairs:
                other = (i + 1, j) if pairs[(i, j)] == 'x' else (i, j + 1)
                o = cells[other]
                frags.append(dict(polys=[_rect(lo, o[1], blo, o[3])], cells=[(i, j), other], thin=False))
            elif (i, j) in taken:
                continue
            elif kind[(i, j)] == 'split':
                a, b, c, d = (lo, blo), (hi, blo), (hi, bhi), (lo, bhi)
                halves = [[a, b, c], [a, c, d]] if roll(self.seed, i, j, 2) < 0.5 else [[a, b, d], [b, c, d]]
                frags += [dict(polys=[half], cells=[(i, j)], thin=False) for half in halves]
            else:
                frags.append(dict(polys=[_rect(lo, hi, blo, bhi)], cells=[(i, j)], thin=False))
        out = [_joined(polys) for polys in self._thin_joined(frags)]
        return self._cornered(out)

    def _thin_joined(self, frags):
        """The fragments' polygons with each thin one joined to the fragment beside it (see the module's words)."""
        by_cell = {}
        for k, f in enumerate(frags):
            for c in f['cells']:
                by_cell.setdefault(c, []).append(k)
        rep = list(range(len(frags)))

        def find(k):
            while rep[k] != k:
                k = rep[k]
            return k
        anchored = [not f['thin'] for f in frags]
        changed = True
        while changed:
            changed = False
            for k, f in enumerate(frags):
                if not f['thin'] or find(k) != k:
                    continue
                (i, j), = f['cells']
                near = sorted({g for di in (-1, 0, 1) for dj in (-1, 0, 1) for g in by_cell.get((i + di, j + dj), ())})
                sums = {}
                for g in near:
                    r = find(g)
                    if g == k or r == k or not anchored[r]:
                        continue
                    length = shared_length(f['polys'], frags[g]['polys'])
                    if length > 0:
                        sums[r] = sums.get(r, 0.0) + length
                if sums:
                    rep[k] = max(sums, key=lambda r: (sums[r], -r))
                    anchored[k] = True
                    changed = True
        out = {}
        for k, f in enumerate(frags):
            out.setdefault(find(k), []).extend(f['polys'])
        return [out[k] for k in sorted(out)]

    def _cornered(self, frags):
        """`frags` with every polygon given a corner at each other polygon's corner on its sides, and started at a
        corner its next two are not in line with."""
        t, (ox, oy) = self.t, self.origin

        def bucket(p):
            return (math.floor((p[0] + ox) / t), math.floor((p[1] + oy) / t))
        points = {}
        for polys in frags:
            for poly in polys:
                for p in poly:
                    points.setdefault(bucket(p), set()).add(p)
        out = []
        for polys in frags:
            done = []
            for poly in polys:
                (ilo, jlo), (ihi, jhi) = bucket((min(p[0] for p in poly), min(p[1] for p in poly))), \
                    bucket((max(p[0] for p in poly), max(p[1] for p in poly)))
                near = sorted({p for i in range(ilo - 1, ihi + 2) for j in range(jlo - 1, jhi + 2)
                               for p in points.get((i, j), ())})
                ring = [p for p, _ in frac_wall.insert_points([(p, None) for p in poly], near)]
                done.append(_started(ring))
            out.append(done)
        return out


def cut_cell(lo, hi, blo, bhi, holes):
    """The rectangles [(x0, x1, y0, y1)] of the cell [lo, hi] by [blo, bhi] that `holes` leave: a grid of the cell's
    and the holes' sides, each row's solid parts joined in runs, runs of the same sides in rows one over another one
    rectangle."""
    xs = sorted({lo, hi} | {v for h in holes for v in h[:2] if lo < v < hi})
    ys = sorted({blo, bhi} | {v for h in holes for v in h[2:] if blo < v < bhi})
    rows = [[not any(h[0] < (xs[a] + xs[a + 1]) / 2 < h[1] and h[2] < (ys[b] + ys[b + 1]) / 2 < h[3] for h in holes)
             for a in range(len(xs) - 1)] for b in range(len(ys) - 1)]
    rects, started = [], {}
    for b in range(len(rows) + 1):
        runs = []
        if b < len(rows):
            a, row = 0, rows[b]
            while a < len(row):
                if row[a]:
                    s = a
                    while a < len(row) and row[a]:
                        a += 1
                    runs.append((s, a))
                else:
                    a += 1
        for run in [r for r in started if r not in runs]:
            rects.append((xs[run[0]], xs[run[1]], ys[started.pop(run)], ys[b]))
        for run in runs:
            started.setdefault(run, b)
    return sorted(rects, key=lambda r: (r[2], r[0]))


def groups(rects):
    """`rects` in connected groups (two touch where they share an edge of some length), each in their order, the
    groups in the order of their first."""
    rep = list(range(len(rects)))

    def find(k):
        while rep[k] != k:
            k = rep[k]
        return k
    for a in range(len(rects)):
        for b in range(a + 1, len(rects)):
            p, q = rects[a], rects[b]
            beside = (p[1] == q[0] or q[1] == p[0]) and min(p[3], q[3]) > max(p[2], q[2])
            over = (p[3] == q[2] or q[3] == p[2]) and min(p[1], q[1]) > max(p[0], q[0])
            if beside or over:
                rep[find(b)] = find(a)
    out = {}
    for k, r in enumerate(rects):
        out.setdefault(find(k), []).append(r)
    return [out[k] for k in sorted(out)]


def shared_length(polys, others):
    """The length of edge the polygons `polys` share with `others` (their sides along x or y)."""
    def sides(ps):
        for poly in ps:
            for k in range(len(poly)):
                p, q = poly[k], poly[(k + 1) % len(poly)]
                if p[0] == q[0]:
                    yield ('x', p[0], min(p[1], q[1]), max(p[1], q[1]))
                elif p[1] == q[1]:
                    yield ('y', p[1], min(p[0], q[0]), max(p[0], q[0]))
    theirs = list(sides(others))
    total = 0.0
    for way, line, a, b in sides(polys):
        for w, ln, c, d in theirs:
            if w == way and ln == line:
                total += max(0.0, min(b, d) - max(a, c))
    return total


def _rect(x0, x1, y0, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _turn(a, b, c):
    """The cross product of (b - a) and (c - b): over 0 for a left turn."""
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])


def _in_line(a, b, c):
    return abs(_turn(a, b, c)) <= 1e-9 * max(1.0, math.dist(a, b) * math.dist(b, c))


def _joined(polys):
    """A fragment's polygons with two that share a whole edge and make a convex polygon together made one, the
    corners left in line on a side taken out (the ones other polygons need come back in _cornered)."""
    polys = [list(p) for p in polys]
    merged = True
    while merged:
        merged = False
        for a in range(len(polys)):
            for b in range(a + 1, len(polys)):
                ring = _union(polys[a], polys[b])
                if ring:
                    polys[a] = ring
                    del polys[b]
                    merged = True
                    break
            if merged:
                break
    return polys


def _union(a, b):
    """The convex polygon a and b (convex, anticlockwise) make where they share a whole edge, or None."""
    for i in range(len(a)):
        p, q = a[i], a[(i + 1) % len(a)]
        for j in range(len(b)):
            if b[j] == q and b[(j + 1) % len(b)] == p:
                ring = [a[(i + 1 + k) % len(a)] for k in range(len(a))] + [b[(j + 2 + k) % len(b)] for k in range(len(b) - 2)]
                # (two convex polygons side by side make no spike: a corner in line with its neighbours is on a side)
                ring = [ring[k] for k in range(len(ring)) if not _in_line(ring[k - 1], ring[k], ring[(k + 1) % len(ring)])]
                n = len(ring)
                if n >= 3 and all(_turn(ring[k - 1], ring[k], ring[(k + 1) % n]) > 0 for k in range(n)):
                    return ring
                return None
    return None


def _started(ring):
    """`ring` started at a corner whose next two are not in line with it."""
    n = len(ring)
    for k in range(n):
        if not _in_line(ring[k], ring[(k + 1) % n], ring[(k + 2) % n]):
            return ring[k:] + ring[:k]
    return ring


def area(poly):
    """A polygon's area (anticlockwise: over 0)."""
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))


def centre(polys):
    """The middle of a fragment's polygons, weighed by their areas."""
    total, cx, cy = 0.0, 0.0, 0.0
    for poly in polys:
        for a, b in zip(poly, poly[1:] + poly[:1]):
            c = a[0] * b[1] - b[0] * a[1]
            total += c
            cx += (a[0] + b[0]) * c
            cy += (a[1] + b[1]) * c
    if abs(total) < 1e-12:
        pts = [p for poly in polys for p in poly]
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    return (cx / (3 * total), cy / (3 * total))
