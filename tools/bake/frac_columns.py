"""A fracturing piece's fragment columns in the map being grown (private/plans/done/cars-doors-ladders-plan.md, 6.3, 7.2
and step G8): read from its bytes (fragment_columns), a column's struct given new lists (column_with), carried with a
copy (move_columns; same_move finds the pieces one move carried, shift_fragment_heights the component's saved heights)
and the level's columns edited for the pieces an edit hides and copies (edit_columns). The copy tool's steps call them
(native_copy.fracturing_copies and wall_columns), and the walls made from numbers write and list theirs with them
(frac_walls.py). A struct array of tagged properties is read and rebuilt by native_copy's helpers (find_prop,
struct_elements, struct_entries, entry_for, with_array, rebuilt), which the building floors and the effects' lanes use
too, and a box carried by a move is native_copy.moved_box."""
import struct

# (native_copy puts tools/upk, whose props this reads, on the path; it imports this module only inside its steps)
from native_copy import (FRACTURING, Walker, entry_for, find_prop, moved_box, rebuilt, struct_elements, struct_entries,
                         with_array)
import props as legacy_props

# how much of a column, moved with a copy, must overlap a destination column (of the smaller of the two) for the copy
# to be listed there (edit_columns)
COLUMN_MATCH = 0.5


def fragment_columns(walker, b, start):
    """A fracturing piece's FragmentColumns (export bytes `b`, tagged properties from `start`): (the property, as
    find_prop gives it, [dict(element (start, end), box [x0, x1, y0, y1, z0, z1] (world), field: its
    DestructibleCache property or None, entries: struct_entries of it, neighbours: struct_entries of its
    FracActorCache, the other fracturing pieces' columns it lists, {FracActor, ColumnIndex})]), or None when it saves
    none."""
    found = find_prop(walker, b, start, len(b), 'FragmentColumns[0]')
    if found is None:
        return None
    columns = []
    for s, e in struct_elements(walker, b, found[2], found[3]):
        bounds = find_prop(walker, b, s, e, 'Bounds[0]')
        v = struct.unpack_from('<6f', b, bounds[2])
        field = find_prop(walker, b, s, e, 'DestructibleCache[0]')
        columns.append(dict(element=(s, e), box=[v[0], v[3], v[1], v[4], v[2], v[5]], field=field,
                            entries=struct_entries(walker, b, field, 'DestructibleActor'),
                            neighbours=struct_entries(walker, b, find_prop(walker, b, s, e, 'FracActorCache[0]'),
                                                      'FracActor')))
    return found, columns


def column_with(g, walker, b, column, destructibles, neighbours=None):
    """A column's struct element (fragment_columns', of export bytes `b`) with its DestructibleCache holding the
    struct bytes `destructibles` and, unless None, its FracActorCache `neighbours`."""
    piece = with_array(g, b, column['element'], column['field'], 'DestructibleCache', destructibles)
    if neighbours is None:
        return piece
    return with_array(g, piece, (0, len(piece)), find_prop(walker, piece, 0, len(piece), 'FracActorCache[0]'),
                      'FracActorCache', neighbours)


def same_move(a, b, slack=1.0):
    """Whether two pieces were carried by one rigid move: `a` and `b` are each (before, after), a pose (location,
    rotation) each. The same turn, and translations within `slack` units."""
    import numpy as np
    from export_math import transform

    def move(before, after):
        return np.array(transform(after[0], after[1], [1, 1, 1]), float) @ np.linalg.inv(
            np.array(transform(before[0], before[1], [1, 1, 1]), float))
    ma, mb = move(*a), move(*b)
    return bool(np.abs(ma[:3, :3] - mb[:3, :3]).max() < 1e-3 and np.abs(ma[:3, 3] - mb[:3, 3]).max() <= slack)


def overlap(a, b):
    """How much of the smaller of two boxes the other covers (0 to 1)."""
    inter, va, vb = 1.0, 1.0, 1.0
    for k in range(3):
        inter *= max(0.0, min(a[2 * k + 1], b[2 * k + 1]) - max(a[2 * k], b[2 * k]))
        va *= max(a[2 * k + 1] - a[2 * k], 1e-6)
        vb *= max(b[2 * k + 1] - b[2 * k], 1e-6)
    return inter / min(va, vb)


def move_columns(g, p, original, copy, before, after, members, partners=None):
    """A fracturing copy's own fragment columns (a car's glass, a wall, a storey floor) carried with it
    (private/plans/done/cars-doors-ladders-plan.md, 7.2 and step G8): each column's Bounds box moved as the copy moved from the
    pose `before` to `after` ((location, rotation) each; a quarter turn keeps it axis aligned), every MinZ (its
    FragCache's and DestructibleCache's) raised by the storey shift, the fragment indices kept (they index the mesh).
    Its DestructibleCache (the pieces that go when the column breaks) and its FracActorCache (the other fracturing
    pieces' columns beside it) keep:
    - the entries of the assembly's own copies (`members`, export indices: the clone already points them at the
      copies);
    - the entries of pieces copied in the same build by the same move (`partners`, {original export: its copy}: a
      wall's door, the wall beside it), which then name those copies.
    The rest are dropped (a fence, a neighbouring wreck, a wall that stayed behind: the copy doesn't break them where
    the original stands). Returns dict(columns, dropped: the DestructibleCache entries dropped, and, when there are
    any, carried: the entries now naming a partner's copy, neighbours: {kept, dropped} of the FracActorCache), or None
    when the copy saves no columns."""
    walker = Walker(p, g)
    partners = partners or {}
    e = p.exports[original - 1]
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    b = bytearray(g.export_data(copy))
    parsed = fragment_columns(walker, b, start)
    if parsed is None:
        return None
    field, columns = parsed
    dz = after[0][2] - before[0][2]
    dropped, carried, near, pieces = 0, 0, [0, 0], []

    def keep(entries, shift):
        """(the entries kept, how many of them name a partner's copy)"""
        out, moved = [], 0
        for x in entries:
            if x['actor'] in members:
                out.append(entry_for(x, x['actor'], shift))
            elif x['actor'] in partners:
                out.append(entry_for(x, partners[x['actor']], shift))
                moved += 1
        return out, moved

    for column in columns:
        s_, e_ = column['element']
        bounds = find_prop(walker, b, s_, e_, 'Bounds[0]')
        box = moved_box(column['box'], before, after)
        struct.pack_into('<6f', b, bounds[2], box[0], box[2], box[4], box[1], box[3], box[5])
        frag = find_prop(walker, b, s_, e_, 'FragCache[0]')
        for entry_start, entry_end in (struct_elements(walker, b, frag[2], frag[3]) if frag else []):
            mz = find_prop(walker, b, entry_start, entry_end, 'MinZ[0]')
            if mz:
                struct.pack_into('<f', b, mz[2], struct.unpack_from('<f', b, mz[2])[0] + dz)
        kept, moved = keep(column['entries'], dz)
        dropped += len(column['entries']) - len(kept)
        carried += moved
        beside, _ = keep(column['neighbours'], 0.0)
        near[0] += len(beside)
        near[1] += len(column['neighbours']) - len(beside)
        pieces.append(column_with(g, walker, b, column, kept, beside if column['neighbours'] else None))
    g.relocate(copy, rebuilt(b, field, pieces))
    return dict(columns=len(columns), dropped=dropped, **({'carried': carried} if carried else {}),
                **({'neighbours': dict(kept=near[0], dropped=near[1])} if any(near) else {}))


def shift_fragment_heights(g, p, mapping, dz):
    """A fracturing copy moved up or down by `dz`: its fractured mesh components' FragmentBoundsMinZ and
    FragmentBoundsMaxZ, which the map saves as world heights (Bar's inner wall, standing at z 16, saves -0.04 and
    400; its roof slab at z 400 saves 398 and 402), go with it. `mapping`: the copy's {original export: clone}.
    Returns the components changed."""
    walker = Walker(p, g)
    changed = []
    for old, new in mapping.items():
        if abs(dz) < 1e-6 or p.cls(old) != 'FracturedStaticMeshComponent':
            continue
        e = p.exports[old - 1]
        start = legacy_props.props_start(p.data, e, p.names) - e['off']
        data = bytearray(g.export_data(new))
        found = [f for f in (find_prop(walker, data, start, len(data), name + '[0]')
                             for name in ('FragmentBoundsMinZ', 'FragmentBoundsMaxZ')) if f]
        for _, _, at, _ in found:
            struct.pack_into('<f', data, at, struct.unpack_from('<f', data, at)[0] + dz)
        if found:
            g.relocate(new, bytes(data))
            changed.append(new)
    return changed


def edit_columns(g, p, gone, copies, fracturing=()):
    """Fracturing pieces' fragment columns (private/plans/done/cars-doors-ladders-plan.md, 6.3 and step G8). A column's
    DestructibleCache lists the pieces that go when it breaks (a wall's columns list its door's leaf and frame, 5 to 12
    of them), its FracActorCache the other fracturing pieces' columns beside it. Every hidden piece (`gone`, export
    indices) leaves every column, so breaking a wall no longer acts on a piece out of the level; and each copy in
    `copies` ([(original, copy) export indices, (location, rotation) of the original, of the copy]) is listed where its
    original's listing lands: each column that lists the original (a hidden wall's too: a door moved with its wall),
    carried by the copy's move, gives the copy an entry (the original's, its MinZ moved with it) in every column it
    covers by COLUMN_MATCH of a fracturing piece still in the map, or of a fracturing piece's copy made in this build
    (`fracturing`: [(original, copy)], their columns already moved by move_columns), unless that column lists the
    copy already. (No rule of the columns' own reproduces the bake's listing: a padded box of the piece misses or adds
    columns for most of Bar's.) Returns the manifest's section: {piece: {dropped, added, and neighboursDropped when
    any}} for each piece changed, a copy under '<original> copy <export>'."""
    walker = Walker(p, g)
    level = p.by_name['TheWorld.PersistentLevel']
    pieces, names, sources = {}, {}, {}
    for i in range(1, len(p.exports) + 1):
        if p.cls(i) in FRACTURING and p.exports[i - 1]['outer'] == level:
            e = p.exports[i - 1]
            start = legacy_props.props_start(p.data, e, p.names) - e['off']
            listing = fragment_columns(walker, p.data[e['off']:e['off'] + e['size']], start)
            if listing is not None:
                sources[i] = listing[1]
            if i in gone:
                continue
            b = g.export_data(i)
            parsed = fragment_columns(walker, b, start)
            if parsed is not None:
                pieces[i], names[i] = (b, parsed), p.name(i).split('.')[-1]
    for original, copy in fracturing:
        e = p.exports[original - 1]
        b = g.export_data(copy)
        parsed = fragment_columns(walker, b, legacy_props.props_start(p.data, e, p.names) - e['off'])
        if parsed is not None:
            pieces[copy], names[copy] = (b, parsed), '%s copy %d' % (p.name(original).split('.')[-1], copy)
    lists = {i: [[x['raw'] for x in c['entries'] if x['actor'] not in gone] for c in parsed[1]]
             for i, (b, parsed) in pieces.items()}
    beside = {i: [[x['raw'] for x in c['neighbours'] if x['actor'] not in gone] for c in parsed[1]]
              for i, (b, parsed) in pieces.items()}
    listed = {i: [{x['actor'] for x in c['entries']} for c in parsed[1]] for i, (b, parsed) in pieces.items()}
    dropped = {i: sum(len(c['entries']) for c in parsed[1]) - sum(len(x) for x in lists[i])
               for i, (b, parsed) in pieces.items()}
    apart = {i: sum(len(c['neighbours']) for c in parsed[1]) - sum(len(x) for x in beside[i])
             for i, (b, parsed) in pieces.items()}
    added = {}
    for original, copy, before, after in copies:
        dz = after[0][2] - before[0][2]
        done = set()
        for i, columns in sources.items():
            for k, column in enumerate(columns):
                for entry in column['entries']:
                    if entry['actor'] != original:
                        continue
                    box = moved_box(column['box'], before, after)
                    for j, (_, other) in pieces.items():
                        for n, target in enumerate(other[1]):
                            if ((j, n) not in done and copy not in listed[j][n]
                                    and overlap(box, target['box']) >= COLUMN_MATCH):
                                done.add((j, n))
                                lists[j][n].append(entry_for(entry, copy, dz))
                                added.setdefault(j, []).append(dict(column=n, copy=p.name(original).split('.')[-1]))
    out = {}
    for i, (b, (field, columns)) in pieces.items():
        if not dropped[i] and not apart[i] and i not in added:
            continue
        parts = [column_with(g, walker, b, c, new, near if c['neighbours'] else None)
                 for c, new, near in zip(columns, lists[i], beside[i])]
        g.relocate(i, rebuilt(b, field, parts))
        out[names[i]] = dict(dropped=dropped[i], added=added.get(i, []),
                             **({'neighboursDropped': apart[i]} if apart[i] else {}))
    return out
