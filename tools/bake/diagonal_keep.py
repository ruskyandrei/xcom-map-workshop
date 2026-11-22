"""A tile with diagonal cover next to a Build's change, written by the Build instead of the battle's rebuild (diagonal
cover plan, stage D1; findings register F-149, F-152, F-153).

The battle's rebuild takes a tile's diagonal cover for good (F-149). A rebuild volume told what changed
(native_copy.add_rebuild_volume, `changed`) leaves out the diagonal tiles its change does not stand on: they are next
to it, held in the volume's box for their edges, cover and links. Nothing on such a tile changes (the change keeps a
quarter tile off it, so its occupancy, floor and standing room are as the bake has them); this writes what the change
can alter, worked out against the built map's pieces (tile_world.World of the written package: the hidden pieces out
of the level's list, the copies in):
- its twelve blocking bits (tile_build.blocking) and the cover step's static bits;
- its cover: the diagonal cover the game's build gives a seeded tile (tile_rule.cover), flags and location;
- its links: a plain link (no traversal types) to a tile the change leaves with no floor, or toward which the tile's
  pathing bits now block, is dropped (no plain link exists without both in the bake: 0 of about 55,600, F-152); a
  typed link (a vault, a jump, a drop, a ladder) to a tile with no floor is dropped; no link is added.
The tiles round it are worked out as the battle will (tile_build's first pass and standing room) for its step-outs and
its links. Bits the passes here do not make (the 2-by-2 bit, the drop bit, the edge bits) stay as the bake has them.

  write(path, tiles)          writes those tiles' entries into the package at `path`; returns the record
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import tile_build  # noqa: E402
import tile_rule  # noqa: E402
import tile_world  # noqa: E402
import world_grid  # noqa: E402
import world_links  # noqa: E402

BLOCK_BITS = 0x1FFE                 # the twelve blocking bits (cover-build.md section 5), the cover's static bits in them
STATIC, COVER, FLOOR_STORE, LOCATION = 0, 1, 2, 3
# a plain link's step and the pathing bits that would block it (no link without a floor and none of these)
PATH_BITS = {(-1, 0): 0x2, (1, 0): 0x4, (0, -1): 0x8, (0, 1): 0x10}


def _floor_record(raw):
    """A floor store element's fields (world_links.parse_element's) from its bytes."""
    value, _ = world_links.parse_element('floor', raw, 0)
    return value


def _encode_floor(rec):
    out = struct.pack('<3f', *rec['loc']) + struct.pack('<3f', *rec['normal'])
    out += struct.pack('<I', len(rec['links'])) + b''.join(world_links.encode_link(l) for l in rec['links'])
    return out + struct.pack('<Bii', rec['ramp'], rec['actor'], rec['volume'])


def _link_blocked(flags, dx, dy):
    """Whether a tile's pathing bits block its step (dx, dy) (a diagonal: either of its two straight parts)."""
    if dx and dy:
        return bool(flags & PATH_BITS[(dx, 0)] or flags & PATH_BITS[(0, dy)])
    return bool(flags & PATH_BITS[(dx, dy)])


def plan(p, tiles):
    """What the written tiles become: {tile: dict(static, cover, location, links (the floor record's new list),
    dropped (the links taken out))}, worked out against `p`'s pieces (a package as the Build wrote it)."""
    import native_copy
    grid = native_copy.level_grid(p)
    _, blob = world_grid.container_of(p)
    model = world_grid.decode(blob)
    stores = model['stores']
    flags = {t: struct.unpack('<I', raw)[0] for t, (raw, present) in stores[STATIC].items() if present}
    world = tile_world.World(p)
    pieces = {pc.actor: pc for pc in world.pieces}
    floors = {}
    for t, (raw, present) in stores[FLOOR_STORE].items():
        if present:
            rec = _floor_record(raw)
            floors[t] = dict(loc=rec['loc'], normal=rec['normal'], actor=pieces.get(rec['actor'], rec['actor']),
                             record=rec)
    view = tile_rule.Tiles((grid['tx'], grid['ty'], grid['tz']), model['dims'], dict(flags), dict(floors))
    out = {}
    for t in sorted(tiles, key=lambda t: (t[2], t[1], t[0])):
        if t not in floors or not view.inside(t):
            continue
        # the tiles round it as the battle's rebuild will make them: pass 1, then standing room, in its order
        around = [(t[0] + dx, t[1] + dy, t[2] + dz) for dz in (-1, 0, 1, 2) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                  if (dx, dy, dz) != (0, 0, 0) and view.inside((t[0] + dx, t[1] + dy, t[2] + dz))]
        here = tile_rule.Tiles(view.corner, view.dims, dict(view.flags), dict(view.floor))
        for n in sorted(around, key=lambda n: (n[2], n[1], n[0])):
            if n not in tiles:
                tile_build.first_pass(world, here, n)
        for n in sorted(around, key=lambda n: (n[2], n[1], n[0])):
            if n not in tiles:
                tile_build.standing_room(here, n)
        old = flags[t]
        here.flags[t] = old & ~BLOCK_BITS
        bits = tile_build.blocking(world, here, t)
        cover = tile_rule.cover(world, here, t, True)
        static = (old & ~BLOCK_BITS) | bits | cover['static']
        rec = floors[t]['record']
        links, dropped = [], []
        for l in rec['links']:
            u = tuple(l['to'])
            dx, dy = u[0] - t[0], u[1] - t[1]
            no_floor = not here.flag(u) & tile_rule.FLOOR
            plain = not l['types']
            if no_floor or plain and (dx or dy) and _link_blocked(static, dx, dy):
                dropped.append(dict(to=list(u), types=[world_links.TRAVERSAL[k] if k < len(world_links.TRAVERSAL) else k
                                                       for k in l['types']],
                                    why='no floor there' if no_floor else 'blocked'))
                continue
            links.append(l)
        out[t] = dict(static=static, cover=cover['flags'], location=cover['location'], links=links, dropped=dropped,
                      before=dict(static=old, cover=struct.unpack('<I', stores[COVER][t][0])[0]
                                  if t in stores[COVER] and stores[COVER][t][1] else None))
    return out, model


def write(path, tiles):
    """The diagonal tiles `tiles` of the package at `path` written (plan) and the package written again. Returns the
    record: [{tile, static, cover, location, dropped}] and the tiles left as the bake has them (no floor of their
    own: their seed's flag alone)."""
    import lighting_records as lighting
    import package_grow
    p = lighting.Package(Path(path))
    planned, model = plan(p, tiles)
    stores = model['stores']
    for t, r in planned.items():
        stores[STATIC][t] = (struct.pack('<I', r['static']), 1)
        stores[COVER][t] = (struct.pack('<I', r['cover']), 1)
        if r['location'] is not None:
            stores[LOCATION][t] = (struct.pack('<3f', *r['location']), 1)
        raw, present = stores[FLOOR_STORE][t]
        rec = _floor_record(raw)
        rec['links'] = r['links']
        stores[FLOOR_STORE][t] = (_encode_floor(rec), present)
    index, blob = world_grid.container_of(p)
    new = world_grid.encode(model)
    header = blob[:world_links.HEADER]
    if new[:world_links.HEADER] != header:
        raise ValueError('the container was not written back with its header')
    g = package_grow.Grower(str(path))
    g.relocate(index, new)
    tmp = Path(str(path) + '.diagonal')
    g.write(str(tmp))
    del g, p
    import os
    os.replace(tmp, path)
    record = [dict(tile=list(t), static='%07x' % r['static'], cover='%06x' % r['cover'],
                   location=[round(v, 2) for v in r['location']] if r['location'] else None,
                   before=dict(static='%07x' % r['before']['static'],
                               cover='%06x' % r['before']['cover'] if r['before']['cover'] is not None else None),
                   dropped=r['dropped']) for t, r in sorted(planned.items())]
    left = sorted(list(t) for t in tiles if t not in planned)
    return dict(written=record, left=left)
