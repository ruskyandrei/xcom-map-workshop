"""Made walls, floors and roofs built broken (custom geometry editing plan, B5, decision D-4 at its default, 19 November
2026: the user, "be able to pre-break walls and floors").

A made piece's request carries `blasts`, [{at: [x, y, z], radius}]: each a blast the user set off with Break in its
panel, a point in the piece's numbers' frame (its mesh's) and how far it reaches. Saved as blasts, not as fragments,
so the damage stays where it was when the piece is made longer, taller or in another look.

A fragment is knocked out when its centre (the mesh's fragment centre) lies within a blast's radius. The Build
writes the result on the copy's component as the game's own painted-out pieces are saved (research of 19 November
2026: 161 components in 34 maps save the array, 30 with fragments hidden):
- `EditorPaintedVisibleFragments`, an int for each of the mesh's fragments, 1 shown and 0 hidden;
- `DestroyedChunks`, a Box (its Min, its Max and IsValid 1: 25 bytes) for each hidden fragment in order, its bounds
  in the mesh's frame.
The editor's mesh server (viewer/generated.py) leaves the hidden fragments' triangles out, so the page draws the
piece as the game will.

A piece the Build cuts into several (made_split) gives each its blasts moved into its frame (for_piece)."""
import math
import struct

MIN_RADIUS, MAX_RADIUS = 24.0, 384.0
MAX_BLASTS = 64


def check(blasts):
    """The blasts, checked (ValueError): a list of at most MAX_BLASTS, each {at: three numbers, radius:
    MIN_RADIUS to MAX_RADIUS}. Returns them in one spelling (floats)."""
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)  # noqa: E731
    if not isinstance(blasts, list) or len(blasts) > MAX_BLASTS:
        raise ValueError('blasts are a list of at most %d' % MAX_BLASTS)
    out = []
    for b in blasts:
        if not (isinstance(b, dict) and set(b) == {'at', 'radius'} and isinstance(b['at'], list) and len(b['at']) == 3
                and all(num(v) for v in b['at']) and num(b['radius']) and MIN_RADIUS <= b['radius'] <= MAX_RADIUS):
            raise ValueError('a blast is {at: [x, y, z], radius: %g to %g} (it has %r)' % (MIN_RADIUS, MAX_RADIUS, b))
        out.append(dict(at=[float(v) for v in b['at']], radius=float(b['radius'])))
    return out


def for_piece(blasts, origin, span=None):
    """The blasts moved into a piece's frame: `origin` (x, y, z) is where the piece's frame starts in the whole's;
    `span` [(lo, hi) along x, (lo, hi) along y or None], the piece's extent in its frame, keeps only the blasts that
    reach it."""
    out = []
    for b in blasts or []:
        at = [b['at'][k] - origin[k] for k in range(3)]
        if span is not None:
            gap = [max(lo - at[k], 0.0, at[k] - hi) for k, s in enumerate(span) if s is not None for lo, hi in [s]]
            if math.hypot(*gap) > b['radius']:
                continue
        out.append(dict(at=at, radius=b['radius']))
    return out


def hidden(built, blasts):
    """The fragments of a made piece (frac_wall.build's or frac_slab.build's) its blasts knock out, in order: those
    whose centre is within a blast's radius."""
    if not blasts:
        return []
    frags = built['mesh']['fractured']['fragments']
    return [i for i, f in enumerate(frags)
            if any(math.dist(f['centre'], b['at']) <= b['radius'] for b in blasts)]


def visible_value(count, gone):
    """EditorPaintedVisibleFragments' value: its count, then 1 for each fragment shown and 0 for each hidden."""
    gone = set(gone)
    return struct.pack('<i', count) + b''.join(struct.pack('<i', 0 if i in gone else 1) for i in range(count))


def chunks_value(built, gone):
    """DestroyedChunks' value: its count, then each hidden fragment's bounds in the mesh's frame (Min, Max, IsValid 1),
    as the game's maps save them."""
    out = [struct.pack('<i', len(gone))]
    for i in gone:
        x0, x1, y0, y1, z0, z1 = built['fragments'][i]['box']
        out.append(struct.pack('<6fB', x0, y0, z0, x1, y1, z1, 1))
    return b''.join(out)


def kept_indices(lod, gone):
    """A mesh LOD's sections with the hidden fragments' triangles left out: [(slot, indices)] in section order."""
    gone = set(gone)
    idx = lod['indices'][1]
    out = []
    for s in lod['sections']:
        kept = []
        for i, (first, count) in enumerate(s.get('fragments') or []):
            if count and i not in gone:
                kept.extend(idx[first:first + 3 * count])
        if not s.get('fragments'):
            kept = list(idx[s['first']:s['first'] + 3 * s['triangles']])
        out.append((s['slot'], kept))
    return out
