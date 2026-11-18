"""The cursor's own floors over made floors and roofs (custom geometry plan, M5b; findings register F-128).

The game's 3D cursor finds its floors in the level's cursor volumes alone (XComCursorVolume, F-88): the floor it is
on is a volume's m_iFloorNumber, and it looks down from that volume's top for the ground. A made floor whose top is
under a break of the map's cursor floors is taken by the cursor of the floor below, and the room under it is not cut
away on the floor above (EXP-76 run E). So each made floor and roof (a `fracSlab`) brings floors of its own over its
footprint:

- each of the map's plain cursor volumes that overlaps a footprint is taken out and stands again as clones of itself
  over what it covered outside the footprints (the same floor and heights; nothing overlaps, as in the game's maps);
- over the footprints the floors are made again cell by cell: the map's breaks there, each slab's break taking the
  nearest within HALF a storey (never the column's bottom) or adding one of its own. A slab's break is UNDER units
  under its underside: the cursor of a floor looks down from its volume's top, and one starting on the slab's top
  landed on it where no building cut the slab away (EXP-80 run G, the long floor), while the floor over it finds
  the slab's top inside its own volume;
- stair and turned volumes stay as they are; a footprint over one is reported.

split() is the rule, on plain numbers: the compiler runs it on its cursor_storeys and the page's twin is
web/floors.js madeStoreys. apply() is the Build's writer (native_copy, after the made pieces are written)."""

HALF = 96.0         # a slab's break takes a map break this near it (half a storey)
EDGE = 1.0          # an overlap thinner than this is none
TOP_SLACK = 2.0     # a slab's break this near the column's top adds no floor
UNDER = 2.0         # a slab's floor starts this far under its underside


def slab_break(box):
    """Where a made slab's floor starts: UNDER under its underside (box [x0, y0, z0, x1, y1, z1])."""
    return box[2] - UNDER


def _overlap(a, b):
    """Whether two boxes [x0, y0, z0, x1, y1, z1] overlap in X and Y by more than EDGE."""
    return min(a[3], b[3]) - max(a[0], b[0]) > EDGE and min(a[4], b[4]) - max(a[1], b[1]) > EDGE


def _covers(box, x, y):
    return box[0] <= x <= box[3] and box[1] <= y <= box[4]


def rectangles(xs, ys, value):
    """The cells [xs[i], xs[i + 1]] x [ys[j], ys[j + 1]] merged into rectangles of one value: `value(i, j)` gives the
    cell's (hashable) value, or None for a cell left out. Runs along X in each row, then runs of the same span and
    value carried up Y. Returns [(value, [x0, y0, x1, y1])], in the order they close."""
    out, open_ = [], {}
    nx, ny = len(xs) - 1, len(ys) - 1
    for j in range(ny + 1):
        runs = []
        i = 0
        while j < ny and i < nx:
            v = value(i, j)
            if v is None:
                i += 1
                continue
            start = i
            while i + 1 < nx and value(i + 1, j) == v:
                i += 1
            runs.append((start, i + 1, v))
            i += 1
        now = {}
        for r in runs:
            now[r] = open_.pop(r, j)
        for (a, b, v), start in open_.items():
            out.append((v, [xs[a], ys[start], xs[b], ys[j]]))
        open_ = now
    return out


def _column(cx, cy, plain, slabs, grid):
    """The floors over the cell at (cx, cy): ((z0, z1, floor), ...) from the lowest up, and the source volume of each
    (the key of the map's volume whose break it is or that the floor stands in), or (None, None) for a cell with no
    volume over it and no grid."""
    over = [v for v in plain if _covers(v['box'], cx, cy)]
    if over:
        bottom = min(v['box'][2] for v in over)
        top = max(v['box'][5] for v in over)
        marks = []
        for v in sorted(over, key=lambda v: (v['box'][2], -(v['floor'] or 0), str(v['key']))):
            z = v['box'][2]
            if not any(abs(z - m['z']) <= EDGE for m in marks):
                marks.append(dict(z=z, floor=v['floor'] or 0, source=v['key'], taken=False))
    elif grid:
        bottom, top = grid[2], grid[5]
        marks = [dict(z=bottom, floor=1, source=None, taken=False)]
    else:
        return None, None
    for t in sorted({slab_break(s['box']) for s in slabs if _covers(s['box'], cx, cy)}):
        if t <= bottom + HALF or t >= top - TOP_SLACK:
            continue
        near = [m for m in marks[1:] if not m['taken'] and abs(m['z'] - t) <= HALF]
        if near:
            m = min(near, key=lambda m: (abs(m['z'] - t), m['z']))
            m.update(z=t, taken=True)
        else:
            below = max((m for m in marks if m['z'] < t), key=lambda m: m['z'])
            marks.append(dict(z=t, floor=None, source=below['source'], taken=True))
        marks.sort(key=lambda m: m['z'])
    floor = None
    for m in marks:
        if m['floor'] is None or (floor is not None and m['floor'] <= floor):
            m['floor'] = (floor if floor is not None else 0) + 1
        floor = m['floor']
    ends = [m['z'] for m in marks[1:]] + [top]
    return (tuple((round(m['z'], 3), round(end, 3), m['floor']) for m, end in zip(marks, ends)),
            tuple(m['source'] for m in marks))


def _moves(slab, plain, grid):
    """Whether a slab's break changes the floors over its centre (split's rule)."""
    b = slab['box']
    cx, cy, top_z = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2, slab_break(b)
    over = [v for v in plain if _covers(v['box'], cx, cy)]
    if over:
        bottom, top = min(v['box'][2] for v in over), max(v['box'][5] for v in over)
        breaks = [v['box'][2] for v in over if v['box'][2] > bottom + EDGE]
    elif grid:
        bottom, top, breaks = grid[2], grid[5], []
    else:
        return False
    return bottom + HALF < top_z < top - TOP_SLACK and not any(abs(z - top_z) <= EDGE for z in breaks)


def split(volumes, slabs, grid=None):
    """The map's cursor volumes with the made slabs' floors over their footprints.
    - `volumes`: [dict(key, floor, box [x0, y0, z0, x1, y1, z1], stair, turned)], the map's (listed) cursor volumes;
    - `slabs`: [dict(box [x0, y0, z0, x1, y1, z1], label)], the made floors and roofs;
    - `grid`: the tile grid's box, for footprint cells no volume is over.
    Returns dict(hidden: the keys of the volumes taken out, volumes: [dict(source: a key to clone, or None for any,
    floor, box, over: True for a footprint's floor, False for what a hidden volume covered outside them)], crossed:
    [dict(slab: label, volume: key, why: 'stair' or 'turned')]). Only the slabs whose tops change the floors over them
    count (one on a break already, or within half a storey of the column's bottom, changes nothing)."""
    slabs = [s for s in slabs if s['box'][3] - s['box'][0] > EDGE and s['box'][4] - s['box'][1] > EDGE]
    out = dict(hidden=[], volumes=[], crossed=[])
    plain = [v for v in volumes if not v.get('stair') and not v.get('turned')]
    # the slabs that change the floors over them: a top inside the column's floors (over its centre), past half a
    # storey over its bottom, not on a break already
    moving = [s for s in slabs if _moves(s, plain, grid)]
    if not moving:
        return out
    for v in volumes:
        if v.get('stair') or v.get('turned'):
            for s in moving:
                if _overlap(v['box'], s['box']):
                    out['crossed'].append(dict(slab=s.get('label'), volume=v['key'], why='stair' if v.get('stair') else 'turned'))
    hit = [v for v in plain if any(_overlap(v['box'], s['box']) for s in moving)]
    feet = [s['box'] for s in moving]

    def inside(x, y):
        return any(f[0] < x < f[3] and f[1] < y < f[4] for f in feet)

    # what each hidden volume covered outside the footprints, as clones of it
    for v in hit:
        b = v['box']
        xs = sorted({b[0], b[3]} | {e for f in feet for e in (f[0], f[3]) if b[0] < e < b[3]})
        ys = sorted({b[1], b[4]} | {e for f in feet for e in (f[1], f[4]) if b[1] < e < b[4]})
        for _, r in rectangles(xs, ys, lambda i, j: None if inside((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2) else 1):
            out['volumes'].append(dict(source=v['key'], floor=v['floor'], box=[r[0], r[1], b[2], r[2], r[3], b[5]], over=False))
    # the footprints' floors, cell by cell, cut by the footprints' and the hit volumes' edges
    lo = [min(f[k] for f in feet) for k in (0, 1)]
    hi = [max(f[k + 3] for f in feet) for k in (0, 1)]
    xs = sorted({e for f in feet for e in (f[0], f[3])} | {e for v in hit for e in (v['box'][0], v['box'][3]) if lo[0] < e < hi[0]})
    ys = sorted({e for f in feet for e in (f[1], f[4])} | {e for v in hit for e in (v['box'][1], v['box'][4]) if lo[1] < e < hi[1]})
    sources = {}

    def cell(i, j):
        cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
        if not inside(cx, cy):
            return None
        bands, keys = _column(cx, cy, plain, slabs, grid)
        if bands is not None:
            sources.setdefault(bands, keys)
        return bands

    for bands, r in rectangles(xs, ys, cell):
        for (z0, z1, floor), key in zip(bands, sources[bands]):
            out['volumes'].append(dict(source=key, floor=floor, box=[r[0], r[1], z0, r[2], r[3], z1], over=True))
    out['hidden'] = [v['key'] for v in hit]
    return out


def storeys(volumes, slabs, grid=None):
    """The cursor's floors after split(): [(floor, box)], the volumes that stay and the new ones (the compiler's
    cursor_storeys form; stair and turned volumes left out)."""
    s = split(volumes, slabs, grid)
    gone = set(s['hidden'])
    kept = [(v['floor'], list(v['box'])) for v in volumes if v['key'] not in gone and not v.get('stair') and not v.get('turned')]
    return kept + [(v['floor'], v['box']) for v in s['volumes']]


def apply(g, p, slabs):
    """The Build's writer: the map `p` (being grown as `g`) given the made slabs' floors. `slabs`: [dict(box, label)],
    world boxes [x0, y0, z0, x1, y1, z1]. The hit volumes are taken out of the level's list, and clones of them, each
    sized by its span and given its floor, are returned to be listed. Returns (record or None, the clones)."""
    import native_copy
    import shell
    live = shell.listed(p)
    found = [i for i in shell.actors(p, 'XComCursorVolume') if i in live]
    if not found or not slabs:
        return None, []
    volumes = []
    for i in found:
        turned = any(p.own(i, 'Rotation', [0, 0, 0]))
        if turned:
            # (an approximate box, for the crossing report only: its brush's bounds round its place)
            origin, extent = native_copy.brush_bounds(p, i)
            loc = p.own(i, 'Location', [0.0, 0.0, 0.0])
            r = max(extent) * max(p.own(i, 'DrawScale3D', [1.0, 1.0, 1.0])) * p.own(i, 'DrawScale', 1.0)
            box = [loc[k] + origin[k] - r for k in range(3)] + [loc[k] + origin[k] + r for k in range(3)]
        else:
            lo, hi = native_copy.brush_box(p, i)
            box = list(lo) + list(hi)
        volumes.append(dict(key=i, floor=p.effective(i, 'm_iFloorNumber') or 0, box=box, turned=turned,
                            stair=bool(p.effective(i, 'm_bTreatAsStair'))))
    try:
        grid = shell.grid_box(p)
    except ValueError:
        grid = None
    plan = split(volumes, slabs, grid)
    if not plan['hidden'] and not plan['volumes']:
        return (dict(hidden=[], added=[], crossed=[dict(c, volume=p.name(c['volume']).rsplit('.', 1)[-1]) for c in plan['crossed']])
                if plan['crossed'] else None), []
    native_copy.empty_slots(g, p, set(plan['hidden']))
    walker = native_copy.Walker(p)
    walker.names = g.names
    fallback = min((v for v in volumes if not v['stair'] and not v['turned']), key=lambda v: (v['floor'], v['key']),
                   default=None)
    if fallback is None:
        raise ValueError('the map has no plain cursor volume to clone the made floors\' from')
    clones, added = [], []
    for v in plan['volumes']:
        source = v['source'] if v['source'] is not None else fallback['key']
        made = native_copy.clone_actor(g, p, source, p.own(source, 'Location', [0.0, 0.0, 0.0]), [0, 0, 0])
        b = v['box']
        box = shell.set_span(walker, g, p, made['actor'], {0: (b[0], b[3]), 1: (b[1], b[4]), 2: (b[2], b[5])},
                             like=source, props={'m_iFloorNumber': v['floor']})
        clones.append(made['actor'])
        added.append(dict(export=made['actor'], clone=p.name(source).rsplit('.', 1)[-1], floor=v['floor'],
                          box=[round(x, 3) for x in box], over=v['over']))
    record = dict(hidden=sorted(p.name(i).rsplit('.', 1)[-1] for i in plan['hidden']), added=added,
                  crossed=[dict(c, volume=p.name(c['volume']).rsplit('.', 1)[-1]) for c in plan['crossed']])
    return record, clones


def verify(q, record):
    """The written map `q` read back: each added volume listed, with its floor and box; each hidden one not listed.
    Raises ValueError on a difference."""
    import native_copy
    import shell
    live = shell.listed(q)
    names = {q.name(i).rsplit('.', 1)[-1]: i for i in shell.actors(q, 'XComCursorVolume')}
    for name in record['hidden']:
        if names.get(name) in live:
            raise ValueError('the cursor volume %s is still in the level\'s list' % name)
    for a in record['added']:
        i = a['export']
        if i not in live or q.cls(i) != 'XComCursorVolume':
            raise ValueError('the made floors\' cursor volume %d is not in the level\'s list' % i)
        if (q.effective(i, 'm_iFloorNumber') or 0) != a['floor']:
            raise ValueError('cursor volume %s has floor %s, not %s' % (q.name(i), q.effective(i, 'm_iFloorNumber'), a['floor']))
        lo, hi = native_copy.brush_box(q, i)
        if max(abs(x - y) for x, y in zip(list(lo) + list(hi), a['box'])) > 0.05:
            raise ValueError('cursor volume %s spans %s, not %s' % (q.name(i), list(lo) + list(hi), a['box']))
