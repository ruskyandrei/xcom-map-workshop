"""The tiles the battle's rebuild will work out again near a Build's changes, written as it will leave them, for what
the game reads of them before that rebuild runs (findings register F-157).

XGBattle's start places every player's units (InitPlayers: the terror civilians on the map's cover points within 960
units of a pod, a pod's other aliens on the nearest valid places) before it runs the rebuild over the rebuild volumes
(DoWorldDataRebuild). A Build used to leave the tiles its changes alter as the bake had them, for that rebuild to
work out: a deleted piece's floors and cover points stayed, and a civilian could start on a deleted UFO's roof, in
the air. This writes those tiles from passes 1 and 2 of the game's tile build (tile_build: occupancy, floor, standing
room, cover, the blocking bits) against the built map's pieces (tile_world.World of the written package: the hidden
pieces out of the level's list, the copies in), and seeds each tile it writes (the low bit the rebuild's queue test
reads), so the battle's rebuild still works it out and has the last word.

Which tiles: those a rebuild volume reaches (native_copy.rebuild_order, every tile of its reach) that lie
- near a change: the tiles a change's box stands on (native_copy.changed_tiles; the boxes the Build's rebuild volumes
  were made for, the grower's `change_boxes`), with a tile round them in x and y, a level under and two over (the
  cover, the blocking bits and the standing room a piece alters reach that far), or
- round a floor whose piece the Build took out of the level (a cleared map's pieces have no box of their own),
and whose stored state the passes change (the static flags but the seed bit, the floor's place and piece, the cover
flags and place); the others keep their bytes. The diagonal tiles and the two tiles over each lie outside every
volume's reach (native_copy.rebuild_spares) and are never written here: diagonal_keep writes those it must.

A written tile keeps the static bits no pass makes (the seed, the edge bits, water; the 2-by-2 and drop bits while
it has a floor), and its floor's links, ramp byte and floor volume while its floor stays where it was (the rebuild
works its links out again; nothing reads them before it). No cover and no floor take the bake's form: no element.

  apply(p, boxes)   the container's model with them written, and the record (native_copy.rewrite_tiles
                    writes the map)
"""
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import diagonal_keep  # noqa: E402
import tile_build  # noqa: E402
import tile_links  # noqa: E402
import tile_rule  # noqa: E402
import tile_world  # noqa: E402
import world_grid  # noqa: E402
import world_links  # noqa: E402

STATIC, COVER, FLOOR_STORE, LOCATION = 0, 1, 2, 3
SEED = world_grid.SEED
KEPT_BITS = diagonal_keep.KEPT_BITS
LINK_BITS = tile_links.STAND2X2 | tile_links.DROP2      # made by the link step, which does not run here
AROUND = (1, 1, 2)          # the tiles round a change: this many each way in x and y, a level under, two over
SAME = 0.5                  # a floor or cover place moved less than this is the same place


def around(tiles, dims):
    """The tiles of `tiles` with those round each (AROUND), in a grid of `dims`."""
    r, under, over = AROUND
    out = set()
    for x, y, z in tiles:
        out.update((x + dx, y + dy, z + dz) for dz in range(-under, over + 1) for dy in range(-r, r + 1)
                   for dx in range(-r, r + 1))
    return {t for t in out if all(0 <= t[k] < dims[k] for k in range(3))}


def _actor(value):
    return value.actor if isinstance(value, tile_world.Piece) else int(value or 0)


def _same(a, b):
    return (a is None) == (b is None) and (a is None or all(abs(a[k] - b[k]) < SAME for k in range(3)))


def plan(ld, tiles):
    """What the passes make of `tiles` (a diagonal_keep.Loaded `ld`, the package as the Build wrote it): passes 1 and 2
    over them in the build's order (x fastest, then y, then z; pass 1 over all before pass 2), the tiles round them
    as stored. {tile: dict(static, cover, location, floor (a floor record or None), before)} for the tiles whose state
    that changes."""
    view = ld.view()
    order = sorted(tiles, key=diagonal_keep._order)
    for t in order:
        tile_build.first_pass(ld.world, view, t)
    near = {t: bool(view.flag(t) & tile_build.NEAR) for t in order}
    covers = {t: tile_build.second_pass(ld.world, view, t, near[t]) for t in order}
    out = {}
    for t in order:
        static = view.flag(t)
        # standing room from a floor under it kept as stored (a floor record without the flag counts, as for a whole
        # diagonal tile)
        for n in range(1, diagonal_keep.STANDING_ROOM + 1):
            b = (t[0], t[1], t[2] - n)
            if b not in tiles and view.inside(b) and (b in view.floor or view.flag(b) & tile_rule.FLOOR):
                static |= tile_build.ROOM
        old = ld.flags.get(t, 0)
        static = (static & ~KEPT_BITS & ~LINK_BITS) | (old & KEPT_BITS) | (old & LINK_BITS if static & tile_rule.FLOOR
                                                                         else 0)
        result = covers[t]
        cover = result['flags'] if result else 0
        location = tuple(result['location']) if cover and result['location'] is not None else None
        stored = ld.floors.get(t)
        made = view.floor.get(t)
        floor = None
        if made is not None:
            kept = stored is not None and _same(stored['loc'], made['loc']) and _actor(stored['actor']) == _actor(made['actor'])
            rec = stored['record'] if stored is not None else None
            floor = dict(loc=tuple(made['loc']), normal=tuple(made['normal']), links=rec['links'] if kept else [],
                         ramp=rec['ramp'] if kept else 0, actor=_actor(made['actor']),
                         volume=rec['volume'] if rec is not None else 0)
        before_cover = ld.cover.get(t, 0)
        before_location = ld.location.get(t) if before_cover else None
        changed = ((static & ~SEED) != (old & ~SEED) or cover != before_cover or not _same(location, before_location)
                   or (floor is None) != (stored is None)
                   or floor is not None and (not _same(floor['loc'], stored['loc'])
                                             or floor['actor'] != _actor(stored['actor'])))
        if changed:
            out[t] = dict(static=static | SEED, cover=cover, location=location, floor=floor,
                          before=dict(static=old, cover=before_cover, location=before_location,
                                      floor=tuple(stored['loc']) if stored is not None else None))
    return out


def _store(model, planned):
    """The planned tiles into the container's model; a tile with no cover or floor loses that element where the store
    has it (none is added for it)."""
    stores = model['stores']

    def put(k, t, raw):
        if raw is not None:
            stores[k][t] = (raw, 1)
        elif t in stores[k]:
            stores[k][t] = (bytes(world_grid.SIZES[world_links.KINDS[k]]), 0)

    for t, r in planned.items():
        put(STATIC, t, struct.pack('<I', r['static']))
        put(COVER, t, struct.pack('<I', r['cover']) if r['cover'] else None)
        put(LOCATION, t, struct.pack('<3f', *r['location']) if r['location'] is not None else None)
        put(FLOOR_STORE, t, world_links.encode_floor(r['floor']) if r['floor'] is not None else None)


def count(planned, queued):
    """The record's counts for the planned tiles (`queued`: the tiles the rebuild's queue held before)."""
    out = dict(written=len(planned), seeded=sum(t not in queued for t in planned), floorsTaken=0, floorsMade=0,
               floorsMoved=0, coverTaken=0, coverMade=0, coverChanged=0)
    for r in planned.values():
        had, has = r['before']['floor'] is not None, r['floor'] is not None
        out['floorsTaken'] += had and not has
        out['floorsMade'] += has and not had
        out['floorsMoved'] += had and has and not _same(r['before']['floor'], r['floor']['loc'])
        had, has = bool(r['before']['cover']), bool(r['cover'])
        out['coverTaken'] += had and not has
        out['coverMade'] += has and not had
        out['coverChanged'] += had and has and (r['cover'] != r['before']['cover']
                                                or not _same(r['location'], r['before']['location']))
    return {k: v for k, v in out.items() if v or k == 'written'}


def apply(p, boxes):
    """The tile data of the package `p` (as the Build wrote it) with the tiles near its changes (`boxes`: world [x0,
    x1, y0, y1, z0, z1], the grower's change_boxes) and round its taken-out pieces' floors as the battle's rebuild
    will leave them (see the module's notes): (the container's model with them stored, the record), or (None, {})
    when nothing changes. The record is count's, with `considered` (the tiles worked out) and `seconds`. The Build
    clears the tiles' references to taken-out actors on the same model and writes it once (native_copy.rewrite_tiles):
    this reads which floors those pieces held, so it comes first."""
    import native_copy
    start = time.time()
    reach = native_copy.rebuild_order(p, queued=False)
    if not reach:
        return None, {}
    ld = diagonal_keep.Loaded(p)
    gone = native_copy.taken_out(p)
    stale = {t for t, f in ld.floors.items() if f['record']['actor'] in gone}
    grid = native_copy.level_grid(p)
    near = native_copy.changed_tiles(boxes, grid) if boxes else set()
    tiles = around(near | stale, ld.dims) & set(reach)
    planned = plan(ld, tiles) if tiles else {}
    if not planned:
        return None, {}
    queued = set(native_copy.rebuild_order(p))
    _store(ld.model, planned)
    return ld.model, dict(count(planned, queued), considered=len(tiles), seconds=round(time.time() - start, 1))
