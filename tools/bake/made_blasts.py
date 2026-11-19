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

A piece the Build cuts into several (made_split) gives each its blasts moved into its frame (for_piece).

The map's own fracturing pieces take blasts too (E6, decision D-5): there a fragment goes when the middle of its
vertices' box (fragment_centres) is within a blast's radius, which the editor works out the same way from the mesh it
draws; the fragments the map already paints out stay out (shown_of), and DestroyedChunks takes each hidden fragment's
bounds from the mesh (chunks_of_bounds).

A piece whose component keeps its fragments (`bPreventChunkRemoval`, most of the game's roofs and floors) draws every
fragment whatever is painted out (F-138). Built broken, it either stays whole in battle as the game's do, its hole cut
into a mesh of its own (cut: the default), or breaks further, the setting turned off (the record's `breaksFurther`)."""
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


def fragment_centres(lod, count):
    """The middle of each fragment's vertices' box in a mesh LOD (its sections' fragment ranges): [x, y, z], or None
    for a fragment with no triangles."""
    idx, pos = lod['indices'][1], lod['positions']
    lo, hi = [None] * count, [None] * count
    for s in lod['sections']:
        for i, (first, n) in enumerate(s.get('fragments') or []):
            if i >= count or not n:
                continue
            for v in idx[first:first + 3 * n]:
                p = pos[v]
                if lo[i] is None:
                    lo[i], hi[i] = list(p), list(p)
                else:
                    for k in range(3):
                        lo[i][k] = min(lo[i][k], p[k])
                        hi[i][k] = max(hi[i][k], p[k])
    return [None if lo[i] is None else [(lo[i][k] + hi[i][k]) / 2 for k in range(3)] for i in range(count)]


def hidden_at(centres, blasts):
    """The fragments whose middle (fragment_centres) is within a blast's radius, in order."""
    return [i for i, c in enumerate(centres)
            if c is not None and any(math.dist(c, b['at']) <= b['radius'] for b in blasts or [])]


def shown_of(raw, count):
    """A component's saved EditorPaintedVisibleFragments as [shown] for its `count` fragments: all shown when it saves
    none, or one of another count."""
    if raw:
        n = struct.unpack_from('<i', raw)[0]
        if n == count and len(raw) == 4 + 4 * n:
            return [bool(v) for v in struct.unpack_from('<%di' % n, raw, 4)]
        if n == count and len(raw) == 4 + n:
            return [bool(v) for v in raw[4:]]
    return [True] * count


def chunks_of_bounds(fragments, gone):
    """DestroyedChunks' value for a mesh read from a map (gen_mesh.read): each hidden fragment's bounds (its origin
    less and more its extent)."""
    out = [struct.pack('<i', len(gone))]
    for i in gone:
        b = fragments[i]['bounds']
        out.append(struct.pack('<6fB', *[b[k] - b[k + 3] for k in range(3)], *[b[k] + b[k + 3] for k in range(3)], 1))
    return b''.join(out)


def cut(mesh, gone):
    """A fracturing mesh (gen_mesh.read's form, a map's or a made one) with the fragments `gone` left out of it: the
    hole of a broken piece the game keeps whole (`bPreventChunkRemoval`: most roofs and floors), which draws every
    fragment whatever its component paints out (F-138), made in the mesh itself (F-139).

    Each LOD keeps its vertices, so the component's lightmap coordinates and painted colours still fit, and its
    sections in order, each holding its kept fragments' triangles in fragment order; a fragment left out keeps its
    record and has no triangles (a range at 0, as the game's meshes save an empty one). The kept fragments beside a
    gone one have their inside faces (the interior section's) moved to a section of their own on the same material,
    put last, so the hole's sides are drawn though every fragment counts as shown. The collision tree is made again
    from the kept triangles. Returns a new dict; `mesh` is left as it is."""
    import gen_mesh
    gone = set(gone)
    f = mesh['fractured']
    frags = f['fragments']
    count = len(frags)
    edge = {i for i in range(count) if i not in gone and gone & set(frags[i]['neighbours'])}
    lods = []
    for lod in mesh['lods']:
        idx = lod['indices'][1]
        kept, sections, sides = [], [], []
        for s in lod['sections']:
            ranges = s.get('fragments') or []
            inside = bool(ranges) and s['slot'] == f['interior']
            first, out, moved = len(kept), [], []
            for i, (a, n) in enumerate(ranges):
                if not n or i in gone or (inside and i in edge):
                    out.append((0, 0))
                    if n and i not in gone:
                        moved.append((i, idx[a:a + 3 * n]))
                    continue
                out.append((len(kept), n))
                kept.extend(idx[a:a + 3 * n])
            if not ranges:
                kept.extend(idx[s['first']:s['first'] + 3 * s['triangles']])
            sections.append(dict(s, first=first, triangles=(len(kept) - first) // 3, fragments=out))
            if moved:
                sides.append((s, moved))
        for s, moved in sides:
            first, out = len(kept), [(0, 0)] * len(s['fragments'])
            for i, tri in moved:
                out[i] = (len(kept), len(tri) // 3)
                kept.extend(tri)
            sections.append(dict(s, first=first, triangles=(len(kept) - first) // 3, fragments=out))
        wire = lod['wireframe']
        lods.append(dict(lod, sections=sections, indices=(lod['indices'][0], kept),
                         wireframe=(wire[0], []) if wire[1] else wire))
    tris = [t for t in mesh['kdop']['triangles'] if not count or t[3] % count not in gone]
    kdop = (gen_mesh.kdop_tree(lods[0]['positions'], tris) if tris
            else dict(mesh['kdop'], nodeStride=0, nodes=b'', triangleStride=0, triangles=[]))
    return dict(mesh, lods=lods, kdop=kdop)


def cut_name(base, gone):
    """A cut mesh's name (cut): `base` and a digest of the fragments left out, so each hole is a mesh of its own."""
    import hashlib
    return '%s_Cut_%s' % (base, hashlib.sha256(repr(sorted(gone)).encode()).hexdigest()[:10])


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
