"""A map's baked tile data (its XComWorldDataContainer) written anew, for a tile grid of another size
(private/plans/done/prefab-library-plan.md, 5.11; EXP-43 run 3).

The container is nine chunked tile stores (research/native-code-notes.md, "How the static store is saved in the map"
and "The rest of the container"; world_links.py reads them). Here it is taken apart into tiles and put together
again:

  model = decode(blob)          the header, the grid's size and, for each store, {tile: (element bytes, present)}
                                and its chunk list
  encode(model)                 the container's bytes; encode(decode(blob)) is blob, byte for byte
  grow(model, nx, ny, origin, floor, nz)
                                the model of a grid that reaches further in x and y from the same corner,
                                and higher (nz levels)
  resize(model, nx, ny, origin, floor, nz)
                                any size, each axis smaller, the same or larger, from the same corner and bottom
                                (private/plans/done/clear-map-plan.md, section 7 step 5): shrink() for the
                                axes that get smaller, then grow() for the ones that get larger

How a store is laid out, as the game's maps have it and encode() writes it: the count of all the grid's chunks (3 by
3 by 2 tiles each); the list of the chunks saved, x slowest, then y, then z; the grid's size; then each saved chunk
in ascending index: its index, its count of present tiles, its tile origin, 18, and 18 elements each followed by a
present byte. A chunk is saved when it has a present tile, or (the first store) always.

grow() keeps every tile the map has as it is, but for the tiles of the far edges it grows past, which become
inner tiles, and gives each new tile what a tile of bare ground has in the map itself:
- its static flags: the commonest value among the map's tiles of the same kind (the same level, and the same place
  across the grid: on the near edge, next to it, inside, next to the far edge, on it, in x and in y);
- on the ground level, floor data by rule (flat_floor): the floor's place, a normal straight up, a link to each of
  the eight tiles around it that the grid has, and the floor piece `floor(x, y)` names;
- nothing in the other stores (cover, interaction points).
Where no ground is laid (`floor` None), a new ground-level tile is written as open air with the seed bit set
(seed_tiles.py's: the battle's rebuild then checks it), and has no floor data: floor pieces a project puts there
give it a floor as they do anywhere.
check_bare() says how far those two rules give the map's own tiles back: on the game's blank map, every tile but
those about its few pieces.

shrink() is grow() the other way. Tiles past the new far edges and above the new top leave every store. The tiles
that become the new far edges and the ones next to them take the edge's flags by the same rule: a tile whose flags
are the commonest for its old place (bare_flags) gets the commonest for its new place, and any other keeps the
flags the bake gave it for what stands there; the new top level is a top level to that rule (on the blank map and
URB_Bar the top level's commonest flags are those of every level from the fourth up, so only the edges change). A
floor link to a tile outside the grid is cut, and the floor's
link count with it, so a floor written by rule (flat_floor) on a new edge comes out as flat_floor for the new grid.
shrink() after grow() back to the first size gives the map's own tiles, but the order of a chunk list that had entries
out of turn (grow() numbers the chunks anew) and, where grow() wrote no ground (`floor` None), the ground flags of
the tiles on the two far edges: the edge ground's flags are nowhere in the grown model, whose new ground is open air
(see the tests).

The game works a tile out again when the battle starts wherever a rebuild volume covers it (XGBattle's rebuild), so
what is written for new ground is a starting state of the same shape as the bake's, not the last word.

  python -B tools/upk/world_grid.py check <map.upk>      the round trip, and how bare ground is given back
"""
import collections
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'viewer'))
import world_links  # noqa: E402

CHUNK = (3, 3, 2)
TILE = (96.0, 96.0, 64.0)
SEED = 0x1      # seed_tiles.SEED_DEFAULT: a low bit that puts a tile in the rebuild's queue
SIZES = dict(flags=4, vector=12, floor=37, interact=4, empty=0)    # an absent tile's element, in bytes
FLOOR_STORE = world_links.FLOOR_STORE
NORMAL = bytes.fromhex('0000000000000000ffff7f3f')      # the bake's "straight up": (0, 0, 0.99999994)
# the eight tiles around a floor tile, in the order the bake lists them
AROUND = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, 1), (1, 1), (1, -1), (-1, -1))


def decode(blob):
    """The container as a model: dict(header (the 12 bytes), dims, middle (the two u32 between stores 8 and 9),
    stores [{tile: (element bytes, present)}], always [bool]: the stores that save every chunk)."""
    wd = world_links.parse_container(blob)
    stores, always, orders = [], [], []
    for s in wd['stores']:
        orders.append(list(s['order']))
        tiles = {}
        for c in s['chunks']:
            for t in c['tiles']:
                tiles[t['tile']] = (bytes(blob[t['off']:t['end'] - 1]), t['present'])
        stores.append(tiles)
        always.append(len(s['chunks']) == s['nchunks'] and s['nchunks'] > 0)
    return dict(header=bytes(blob[:world_links.HEADER]), dims=tuple(wd['dims']), middle=wd['middle']['values'],
                stores=stores, always=always, orders=orders)


def chunks_of(dims):
    return tuple(-(-dims[k] // CHUNK[k]) for k in range(3))


def encode_store(kind, dims, tiles, always, listed=None):
    """`listed`: the chunk list as the map had it. The game's own lists run x slowest, then y, then z, but for a
    store that saves only some chunks a few entries stand out of turn (a set written in its own order), so a store
    whose chunks are the map's keeps the map's list."""
    n = chunks_of(dims)
    if always:
        saved = {(cx, cy, cz): None for cx in range(n[0]) for cy in range(n[1]) for cz in range(n[2])}
    else:
        # a chunk the model holds tiles of is saved as the map saved it, present tiles or not
        saved = {(x // 3, y // 3, z // 2): None for (x, y, z) in tiles}
    index = lambda c: c[0] + n[0] * (c[1] + n[1] * c[2])     # noqa: E731
    order = [index(c) for c in sorted(saved)]               # x slowest, then y, then z
    if listed is not None and sorted(listed) == sorted(order):
        order = listed
    out = [struct.pack('<II', n[0] * n[1] * n[2], len(order)), struct.pack('<%di' % len(order), *order),
           struct.pack('<3i', *dims)]
    blank = bytes(SIZES[kind])
    for c in sorted(saved, key=index):
        origin = (c[0] * 3, c[1] * 3, c[2] * 2)
        body, count = [], 0
        for i in range(18):
            raw, present = tiles.get((origin[0] + i % 3, origin[1] + (i // 3) % 3, origin[2] + i // 9), (blank, 0))
            count += present
            body.append(raw + bytes([present]))
        out.append(struct.pack('<IIiiiI', index(c), count, *origin, 18))
        out.extend(body)
    return b''.join(out)


def encode(model):
    out = [model['header']]
    for k, kind in enumerate(world_links.KINDS):
        if k == world_links.MIDDLE_AFTER:
            out.append(struct.pack('<II', *model['middle']))
        out.append(encode_store(kind, model['dims'], model['stores'][k], model['always'][k],
                                (model.get('orders') or [None] * 9)[k]))
    return b''.join(out)


def place(v, n):
    """Where a tile stands across a grid of n: 0 on the near edge, 1 next to it, 2 inside, 3 next to the far edge,
    4 on it."""
    return 0 if v == 0 else 4 if v == n - 1 else 1 if v == 1 else 3 if v == n - 2 else 2


def bare_flags(model):
    """{(place in x, place in y, level): the commonest static flags of the map's present tiles of that kind}."""
    nx, ny, _ = model['dims']
    seen = collections.defaultdict(collections.Counter)
    for (x, y, z), (raw, present) in model['stores'][0].items():
        if present:
            seen[(place(x, nx), place(y, ny), z)][raw] += 1
    return {k: c.most_common(1)[0][0] for k, c in seen.items()}


def flat_floor(x, y, dims, origin, actor):
    """The floor data of a bare ground tile (x, y, 0) in a grid of `dims` whose corner is `origin`: the bake's floor
    place (a unit short of the tile's centre in x and y, at the grid's bottom), its normal, a link to each tile
    around it that the grid has (1 across an edge, 1.414 across a corner, no path object), no ramp, the floor piece
    `actor` (an export index), no floor volume."""
    links = []
    for dx, dy in AROUND:
        tx, ty = x + dx, y + dy
        if 0 <= tx < dims[0] and 0 <= ty < dims[1]:
            links.append(struct.pack('<iiifi', tx, ty, 0, 1.0 if not (dx and dy) else 1.414, 0) + bytes(8))
    loc = struct.pack('<3f', origin[0] + TILE[0] * x + TILE[0] / 2 - 1, origin[1] + TILE[1] * y + TILE[1] / 2 - 1,
                      origin[2])
    return loc + NORMAL + struct.pack('<I', len(links)) + b''.join(links) + b'\0' + struct.pack('<ii', actor, 0)


def floor_actor(raw):
    return struct.unpack_from('<i', raw, len(raw) - 8)[0]


def check_bare(model, origin):
    """How far the two rules for bare ground give the map's own tiles back: dict(flags (tiles, same), floor (ground
    tiles with floor data, same), odd: the tiles either rule misses, as [x, y, z])."""
    dims = model['dims']
    rule = bare_flags(model)
    odd, flags, floors = set(), [0, 0], [0, 0]
    for (x, y, z), (raw, present) in model['stores'][0].items():
        if not present:
            continue
        flags[0] += 1
        if rule[(place(x, dims[0]), place(y, dims[1]), z)] == raw:
            flags[1] += 1
        else:
            odd.add((x, y, z))
    for (x, y, z), (raw, present) in model['stores'][FLOOR_STORE].items():
        if not present:
            continue
        floors[0] += 1
        if z == 0 and flat_floor(x, y, dims, origin, floor_actor(raw)) == raw:
            floors[1] += 1
        else:
            odd.add((x, y, z))
    return dict(flags=flags, floor=floors, odd=sorted(odd))


def grow(model, nx, ny, origin, floor, nz=None):
    """The model of a grid of nx by ny tiles, and nz levels (None: the map's), from the same corner, at the same
    height. `floor(x, y)` is the export index of the floor piece under a new ground tile; `floor` None says no ground
    is laid there. The grid grows upward only, so every tile keeps its index; a new level gets the flags of the map's
    top level for the same place across the grid (the maps' upper levels are open air, the top one no different from
    those under it). Raises ValueError for a grid smaller than the map's in any direction."""
    ox, oy, oz = model['dims']
    nz = oz if nz is None else nz
    if nx < ox or ny < oy or nz < oz:
        raise ValueError('the grid can grow, not shrink: %d by %d by %d against the map\'s %d by %d by %d'
                         % (nx, ny, nz, ox, oy, oz))
    dims = (nx, ny, nz)
    rule = bare_flags(model)
    stores = [dict(s) for s in model['stores']]
    # the tiles that change: every new one, and the old far edges where the grid grows past them
    changed = [(x, y) for x in range(nx) for y in range(ny)
               if x >= ox or y >= oy or (nx > ox and x >= ox - 2) or (ny > oy and y >= oy - 2)]
    for x in range(nx):
        for y in range(ny):
            for z in range(oz, nz):
                stores[0][(x, y, z)] = (rule[(place(x, nx), place(y, ny), oz - 1)], 1)
    for x, y in changed:
        new = x >= ox or y >= oy
        for z in range(oz):
            key = (place(x, nx), place(y, ny), z)
            old = stores[0].get((x, y, z))
            # an old tile keeps flags the bake gave it for what stands there; only a bare edge tile's are taken anew
            if new and floor is None and z == 0 and oz > 1:
                air = struct.unpack('<I', rule[(key[0], key[1], 1)])[0]
                stores[0][(x, y, z)] = (struct.pack('<I', air | SEED), 1)
            elif new or old[0] == rule[(place(x, ox), place(y, oy), z)]:
                stores[0][(x, y, z)] = (rule[key], 1)
        old = stores[FLOOR_STORE].get((x, y, 0))
        if new and floor is None:
            continue
        if new:
            stores[FLOOR_STORE][(x, y, 0)] = (flat_floor(x, y, dims, origin, floor(x, y)), 1)
            if (x, y, 1) not in stores[FLOOR_STORE]:
                stores[FLOOR_STORE][(x, y, 1)] = (bytes(SIZES['floor']), 0)
        elif old and old[1] and old[0] == flat_floor(x, y, model['dims'], origin, floor_actor(old[0])):
            stores[FLOOR_STORE][(x, y, 0)] = (flat_floor(x, y, dims, origin, floor_actor(old[0])), 1)
    return dict(model, dims=dims, stores=stores, orders=None)     # the chunks are numbered anew


def cut_links(raw, dims):
    """A floor element (`raw`, without its present byte) with its links to tiles outside a grid of `dims` cut, and
    its link count with them; the element itself when none is."""
    v, end = world_links.parse_element('floor', raw, 0)
    if end != len(raw):
        raise ValueError('a floor element of %d bytes parses to %d' % (len(raw), end))
    kept = [raw[l['off']:l['end']] for l in v['links'] if all(0 <= l['to'][k] < dims[k] for k in range(3))]
    if len(kept) == len(v['links']):
        return raw
    return raw[:v['list_off']] + struct.pack('<I', len(kept)) + b''.join(kept) + raw[v['list_end']:]


def shrink(model, nx, ny, nz=None):
    """The model of a grid of nx by ny tiles and nz levels (None: the map's), none of them larger than the map's,
    from the same corner and bottom, so every kept tile keeps its (x, y, z):
    - a tile past the new far x or y edge or above the new top leaves every store;
    - a kept tile whose place across the grid changes (the new far edges and the tiles next to them) or that is on
      the new top level takes the rule's flags for its new place when its flags are the rule's for its old place
      (bare_flags; the top level is its own place in z), and keeps its own otherwise, as grow() does the other way;
    - a floor link to a tile outside the new grid is cut (cut_links).
    The chunk lists are kept where the grid has as many chunks as before (encode() keeps a list only where it names
    the chunks saved), and numbered anew otherwise."""
    ox, oy, oz = model['dims']
    nz = oz if nz is None else nz
    if not (1 <= nx <= ox and 1 <= ny <= oy and 1 <= nz <= oz):
        raise ValueError("shrink makes a grid smaller: %d by %d by %d against the map's %d by %d by %d"
                         % (nx, ny, nz, ox, oy, oz))
    dims = (nx, ny, nz)
    rule = bare_flags(model)
    stores = [{t: v for t, v in s.items() if t[0] < nx and t[1] < ny and t[2] < nz} for s in model['stores']]
    for (x, y, z), (raw, present) in stores[0].items():
        old = (place(x, ox), place(y, oy), z)
        new = (place(x, nx), place(y, ny), oz - 1 if z == nz - 1 else z)
        if old != new and raw == rule.get(old) and new in rule:
            stores[0][(x, y, z)] = (rule[new], present)
    floors = stores[FLOOR_STORE]
    for t, (raw, present) in floors.items():
        floors[t] = (cut_links(raw, dims), present)
    orders = model.get('orders') if chunks_of(dims) == chunks_of(model['dims']) else None
    return dict(model, dims=dims, stores=stores, orders=orders)


def resize(model, nx, ny, origin, floor, nz=None):
    """The model of a grid of nx by ny tiles and nz levels (None: the map's), from the same corner, at the same
    height: each axis smaller, the same or larger. The axes that get smaller are cut first (shrink()), then the ones
    that get larger are grown (grow(), with `origin` and `floor` as it takes them), so a grid larger on every axis is
    grow()'s and one smaller on every axis shrink()'s. The corner and the bottom never move: every kept tile keeps
    its (x, y, z) and every link its tiles."""
    dims = tuple(model['dims'])
    nz = dims[2] if nz is None else nz
    if min(nx, ny, nz) < 1:
        raise ValueError('a grid of %d by %d by %d tiles' % (nx, ny, nz))
    cut = (min(dims[0], nx), min(dims[1], ny), min(dims[2], nz))
    if cut != dims:
        model = shrink(model, *cut)
    if (nx, ny, nz) != cut:
        model = grow(model, nx, ny, origin, floor, nz)
    return model


def container_of(p):
    found = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'XComWorldDataContainer']
    if len(found) != 1:
        raise ValueError('expected one XComWorldDataContainer, found %d' % len(found))
    e = p.exports[found[0] - 1]
    return found[0], bytes(p.data[e['off']:e['off'] + e['size']])


def main():
    from package import Package
    if len(sys.argv) != 3 or sys.argv[1] != 'check':
        raise SystemExit(__doc__)
    p = Package(sys.argv[2])
    index, blob = container_of(p)
    model = decode(blob)
    same = encode(model) == blob
    print('%s: %d bytes, grid %s; written again: %s' % (p.name(index).rsplit('.', 1)[-1], len(blob), model['dims'],
                                                       'the same bytes' if same else 'DIFFERENT'))
    volume = next(i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'XComLevelVolume' and p.effective(i, 'Brush', 0) > 0)
    import scene_metadata
    origin = scene_metadata.volume_bounds(p, volume)['min']
    r = check_bare(model, [round(v) for v in origin])
    print('bare ground by rule: flags %d of %d tiles, floor data %d of %d ground tiles; %d tiles differ'
          % (r['flags'][1], r['flags'][0], r['floor'][1], r['floor'][0], len(r['odd'])))
    if not same:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
