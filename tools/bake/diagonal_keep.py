"""Tiles with diagonal cover near a Build's change, written by the Build instead of the battle's rebuild (diagonal
cover plan, stages D1 to D3; findings register F-149, F-152, F-153, F-154).

The battle's rebuild takes a tile's diagonal cover for good (F-149). A rebuild volume told what changed
(native_copy.add_rebuild_volume, `changed`) leaves the diagonal tiles in its box out of the rebuild, and the Build
writes them here, against the built map's pieces (tile_world.World of the written package: the hidden pieces out of
the level's list, the copies in):

- **Next to a change** (`tiles`: the change does not stand on them, D1). Nothing on such a tile changes (the change
  keeps a quarter tile off it, so its occupancy, floor and standing room are as the bake has them); this writes what
  the change can alter:
  - its twelve blocking bits (tile_build.blocking) and the cover step's static bits;
  - its cover: the diagonal cover the game's build gives a seeded tile (tile_rule.cover), flags and location;
  - its links: a plain link (no traversal types) to a tile the change leaves with no floor, or toward which the
    tile's pathing bits now block, is dropped (no plain link exists without both in the bake: 0 of about 55,600,
    F-152); a typed link (a vault, a jump, a drop, a ladder) to a tile with no floor is dropped; no link is added.
  The tiles round it are worked out as the battle will (tile_build's first pass and standing room) for its step-outs
  and its links. Bits the passes here do not make (the 2-by-2 bit, the drop bit, the edge bits) stay as the bake
  has them.
- **Under a change** (`whole`: the change stands on them, D2), worked out whole as the game's full build would make
  them: pass 1 (occupancy, floor), pass 2 (standing room, cover, blocking bits), the link step and the ladders
  (tile_links, F-154). The tiles round one are as the battle will have them: worked out where its rebuild takes them
  (rebuild_order), the bake's where it leaves them. A seeded tile is worked out as the build works out a seeded
  tile (its four diagonals only), so a change that takes its corner away takes its cover with it, as a full build
  would.
- **Carried corners** (D2): a tile a copy of one of the map's own pieces stands on (`candidates`,
  native_copy.diagonal_candidates) with no seed, written whole with diagonal cover where the copy carries a seed
  there (its tile on the original had diagonal cover) and a diagonal gives cover at the new place, as on a seeded
  tile: the designers' marks move with their pieces. A piece with no place of its own in the map carries nothing
  (the finder that once decided those, F-153, took door openings for corners: KB-20).
- **The project's marks** (`edit`, native_copy.diagonal_edit: diagonal cover placed by hand, private/plans/todo/
  diagonal-cover-by-hand-and-views-plan.md, section 3.3): each marked tile written whole with diagonal cover along
  its marked corners only (mark_cover): a corner's wall as the game's rule finds it, and a corner with no wall
  written as marked; each of the map's marked tiles the project takes it from (`removed`) written whole by the
  straight rule, as the game's build makes a tile without its seed.
  A rebuild volume that would reach a carried corner or a mark is made as several that do not (refit, rebuild_fit),
  its place in the level's list kept.

  write(path, tiles, whole, candidates, edit)   writes them into the package at `path`; returns the record
"""
import os
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
STATIC, COVER, FLOOR_STORE, LOCATION, INTERACT = 0, 1, 2, 3, 4
# a plain link's step and the pathing bits that would block it (no link without a floor and none of these)
PATH_BITS = {(-1, 0): 0x2, (1, 0): 0x4, (0, -1): 0x8, (0, 1): 0x10}
# the static bits no pass here makes, kept on a whole tile as the bake has them: the stale low bit (the Build's seed),
# the edge bits and water (research/evidence/tile-build-check.py's MASK, less the two the link step makes)
KEPT_BITS = 0x1 | 0x7800000 | 0x8000000
STANDING_ROOM = 2                   # the tiles over a floor tile its rebuild marks (native_copy.STANDING_ROOM)
LINK_LEVELS = 11                    # the link step reads the 3 by 3 columns round a tile, 11 levels down and up


def _order(t):
    return (t[2], t[1], t[0])


def _floor_record(raw):
    """A floor store element's fields (world_links.parse_element's) from its bytes."""
    value, _ = world_links.parse_element('floor', raw, 0)
    return value


def _encode_floor(rec):
    return world_links.encode_floor(rec)


def _link_blocked(flags, dx, dy):
    """Whether a tile's pathing bits block its step (dx, dy) (a diagonal: either of its two straight parts)."""
    if dx and dy:
        return bool(flags & PATH_BITS[(dx, 0)] or flags & PATH_BITS[(0, dy)])
    return bool(flags & PATH_BITS[(dx, dy)])


def _named(types):
    return [world_links.TRAVERSAL[k] if k < len(world_links.TRAVERSAL) else k for k in types]


class Loaded:
    """A package's tile data and pieces as the writers read them: `model` (world_grid.decode's), `flags` {tile:
    static}, `cover`, `location`, `interact`, `floors` {tile: dict(loc, normal, actor (a tile_world.Piece where the
    world has it), record)}, `world`, `corner`, `dims`."""

    def __init__(self, p):
        import native_copy
        self.p = p
        grid = native_copy.level_grid(p)
        self.corner = (grid['tx'], grid['ty'], grid['tz'])
        _, blob = world_grid.container_of(p)
        self.model = world_grid.decode(blob)
        self.dims = tuple(self.model['dims'])
        stores = self.model['stores']
        self.flags = {t: struct.unpack('<I', raw)[0] for t, (raw, present) in stores[STATIC].items() if present}
        self.cover = {t: struct.unpack('<I', raw)[0] for t, (raw, present) in stores[COVER].items() if present}
        self.location = {t: struct.unpack('<3f', raw) for t, (raw, present) in stores[LOCATION].items() if present}
        self.interact = {t: world_links.parse_element('interact', raw, 0)[0]
                         for t, (raw, present) in stores[INTERACT].items() if present}
        self.world = tile_world.World(p)
        pieces = {pc.actor: pc for pc in self.world.pieces}
        self.floors = {}
        for t, (raw, present) in stores[FLOOR_STORE].items():
            if present:
                rec = _floor_record(raw)
                self.floors[t] = dict(loc=rec['loc'], normal=rec['normal'], actor=pieces.get(rec['actor'], rec['actor']),
                                      record=rec)

    def view(self):
        """A fresh tile_rule.Tiles over the package's flags and floors (copies: the passes write into it)."""
        return tile_rule.Tiles(self.corner, self.dims, dict(self.flags), dict(self.floors))


# ---------------------------------------------------------------- next to a change (D1)

def plan(p, tiles, loaded=None):
    """What the tiles next to a change become: ({tile: dict(static, cover, location, links (the floor record's new
    list), dropped (the links taken out))}, the container's model), worked out against `p`'s pieces (a package as
    the Build wrote it)."""
    ld = loaded or Loaded(p)
    view = ld.view()
    out = {}
    for t in sorted(tiles, key=_order):
        if t not in ld.floors or not view.inside(t):
            continue
        # the tiles round it as the battle's rebuild will make them: pass 1, then standing room, in its order
        around = [(t[0] + dx, t[1] + dy, t[2] + dz) for dz in (-1, 0, 1, 2) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                  if (dx, dy, dz) != (0, 0, 0) and view.inside((t[0] + dx, t[1] + dy, t[2] + dz))]
        here = tile_rule.Tiles(view.corner, view.dims, dict(view.flags), dict(view.floor))
        for n in sorted(around, key=_order):
            if n not in tiles:
                tile_build.first_pass(ld.world, here, n)
        for n in sorted(around, key=_order):
            if n not in tiles:
                tile_build.standing_room(here, n)
        old = ld.flags[t]
        here.flags[t] = old & ~BLOCK_BITS
        bits = tile_build.blocking(ld.world, here, t)
        cover = tile_rule.cover(ld.world, here, t, True)
        static = (old & ~BLOCK_BITS) | bits | cover['static']
        rec = ld.floors[t]['record']
        links, dropped = [], []
        for l in rec['links']:
            u = tuple(l['to'])
            dx, dy = u[0] - t[0], u[1] - t[1]
            no_floor = not here.flag(u) & tile_rule.FLOOR
            plain = not l['types']
            if no_floor or plain and (dx or dy) and _link_blocked(static, dx, dy):
                dropped.append(dict(to=list(u), types=_named(l['types']), why='no floor there' if no_floor else 'blocked'))
                continue
            links.append(l)
        out[t] = dict(static=static, cover=cover['flags'], location=cover['location'], links=links, dropped=dropped,
                      before=dict(static=old, cover=ld.cover.get(t)))
    return out, ld.model


# ---------------------------------------------------------------- under a change, and new corners (D2, D3)

def _region(view, t, down, up):
    """The 3 by 3 columns about a tile, `down` levels under it to `up` over it, in the grid."""
    return [(t[0] + dx, t[1] + dy, z) for z in range(t[2] - down, t[2] + up + 1) for dy in (-1, 0, 1)
            for dx in (-1, 0, 1) if view.inside((t[0] + dx, t[1] + dy, z))]


def find_new(ld, candidates, marked):
    """The carried corners among `candidates` ({tile: 'carried'}, native_copy.diagonal_candidates) without a seed
    (`marked`), against the built map, its tiles round each worked out afresh: a carried tile where a diagonal gives
    cover (the seeded rule: the map's mark carried with its piece). {tile: 'carried'}."""
    out = {}
    probe = tile_rule.Tiles(ld.corner, ld.dims, {}, {})       # (pass 1 reads no other tile)
    if not isinstance(candidates, dict):
        candidates = dict.fromkeys(candidates, 'carried')
    for c in sorted(set(candidates) - set(marked), key=_order):
        kind = candidates[c]
        if not probe.inside(c):
            continue
        f = tile_build.first_pass(ld.world, probe, c)
        if not f & tile_rule.FLOOR or f & tile_rule.RAMP:
            continue
        here = ld.view()
        tile_build.first_pass(ld.world, here, c)
        around = [n for n in _region(here, c, 1, STANDING_ROOM) if n != c]
        for n in sorted(around, key=_order):
            tile_build.first_pass(ld.world, here, n)
        for n in sorted(around + [c], key=_order):
            tile_build.standing_room(here, n)
        if not tile_rule.candidate(here, c):
            continue
        if tile_rule.cover(ld.world, here, c, True)['flags'] & 0xF:
            out[c] = kind
    return out


def toward(i):
    """The way TABLE's diagonal `i` faces, (sx, sy) in game axes."""
    dd = tile_rule.TABLE[i]['dd']
    return [round(dd[0] / tile_rule.S), round(dd[1] / tile_rule.S)]


def mark_cover(world, view, t, bits):
    """A tile the project marks with diagonal cover toward the corners `bits` names (cover bits 0x1 to 0x8), each half
    cover where `bits` has its low bit too (0x10 to 0x80) and full where not: its cover worked out as the game's build
    works out a seeded tile, along those corners only (tile_rule.cover), with each corner's height as the mark says
    (the wall's own decides nothing; full cover never climbs). A marked corner where the rule finds no wall is written
    as marked: its cover bit, its height, no step-outs, no climbing, no blocking bit, its point
    tile_rule.NO_WALL_POINT from the tile's middle toward the corner (the plan's decision 3: the game gives the unit
    cover that way, against nothing). dict(flags, static, location, parts, noWall: the indices into TABLE of the
    corners with no wall)."""
    dirs = [i for i, e in enumerate(tile_rule.TABLE) if bits & e['cover']]
    c = tile_rule.cover(world, view, t, True, directions=dirs)
    no_wall = [i for i in dirs if tile_rule.TABLE[i]['name'] not in c['parts']]
    flags, location = c['flags'], c['location']
    if no_wall:
        points = [r['point'] for r in c['parts'].values()]
        p0 = view.position(t)
        z = float(view.floor[tuple(t)]['loc'][2])
        for i in no_wall:
            dd = tile_rule.TABLE[i]['dd']
            flags |= tile_rule.TABLE[i]['cover']
            points.append((p0[0] + dd[0] * tile_rule.NO_WALL_POINT, p0[1] + dd[1] * tile_rule.NO_WALL_POINT, z))
        mean = [sum(pt[k] for pt in points) / len(points) for k in range(3)]
        location = tuple(float(min(max(mean[k], p0[k] - lim), p0[k] + lim)) for k, lim in enumerate((44.0, 44.0, 32.0)))
    for i in dirs:
        e = tile_rule.TABLE[i]
        flags = flags | e['low'] if bits & e['low'] else flags & ~(e['low'] | e['onto'] | e['over'])
    return dict(c, flags=flags, location=location, noWall=no_wall)


def plan_whole(ld, tiles, diagonal, rebuilt, marks=None):
    """Tiles a change stands on worked out whole (passes 1 and 2, F-152 and F-153; the link step and the ladders,
    F-154), against the built map, the tiles round each as the battle will have them: worked out where its rebuild
    takes them (`rebuilt`, rebuild_order's set), the bake's where it leaves them. A tile of `diagonal` (a seed's, a
    carried corner, a mark) is worked out as the build works out a seeded tile: its four diagonals only, or a mark's
    (`marks` {tile: cover bits}) its marked corners only (mark_cover), the flag alone where it has no cover worked out
    (cover-build.md section 3); any other gets the straight rule. {tile: dict(static, cover, location, floor (a floor
    record, or None for none), before, noWall (a mark's corners with no wall, as (sx, sy)), noFloor (a diagonal tile
    with no floor of its own: the flag alone))}."""
    import tile_links
    out = {}
    tiles = set(tiles)
    marks = marks or {}
    for t in sorted(tiles, key=_order):
        view = ld.view()
        cover, location = dict(ld.cover), dict(ld.location)
        built = sorted((u for u in _region(view, t, LINK_LEVELS, LINK_LEVELS) if u in rebuilt or u in tiles),
                       key=_order)
        for u in built:
            tile_build.first_pass(ld.world, view, u)
        near = {u: bool(view.flag(u) & tile_build.NEAR) for u in built}
        for u in built:
            if u == t:
                tile_build.standing_room(view, t)
                if tile_rule.candidate(view, t):
                    chosen = (mark_cover(ld.world, view, t, marks[t]) if t in marks
                              else tile_rule.cover(ld.world, view, t, t in diagonal))
                else:
                    chosen = dict(flags=tile_rule.DIAGONAL if t in diagonal else 0, static=0, location=None,
                                  noFloor=t in diagonal)
                view.flags[t] = view.flag(t) | chosen['static']
                if near[t]:
                    view.flags[t] = view.flag(t) | tile_build.blocking(ld.world, view, t)
                result = chosen
            else:
                result = tile_build.second_pass(ld.world, view, u, near[u])
            cover[u] = result['flags'] if result else 0
            if result and result['location']:
                location[u] = result['location']
            else:
                location.pop(u, None)
        # standing room from a floor under it that the battle leaves alone (the full build's mark, made before the
        # step takes that floor away: a floor record without the flag counts)
        for n in range(1, STANDING_ROOM + 1):
            b = (t[0], t[1], t[2] - n)
            if b not in built and view.inside(b) and (b in view.floor or view.flag(b) & tile_rule.FLOOR):
                view.flags[t] = view.flag(t) | tile_build.ROOM
        old = ld.flags.get(t, 0)
        static = (view.flag(t) & ~KEPT_BITS & ~(tile_links.STAND2X2 | tile_links.DROP2)) | (old & KEPT_BITS)
        view.flags[t] = static
        # the link step, the 2-by-2 and drop bits, the ladders
        m = tile_links.Map.__new__(tile_links.Map)
        m.p, m.corner, m.dims = ld.p, view.corner, view.dims
        m.static, m.cover, m.coverloc, m.interact = view.flags, cover, location, ld.interact
        m.floor = {u: dict(loc=f['loc'], normal=f['normal']) for u, f in view.floor.items()}
        pr = tile_links.Predictor(m, ld.world, ld.p)
        links = pr.tile(t)
        if pr.stand2x2(t):
            static |= tile_links.STAND2X2
        if t in pr.drop_bits:
            static |= tile_links.DROP2
        view.flags[t] = static
        lists = {t: links}
        pr.ladders(lists)
        links = [dict(to=l['to'], cost=l['cost'], obj=l['obj'], types=list(l['types']), pos=l['pos'])
                 for l in lists.get(t, [])]
        floor = None
        if t in view.floor:
            f = view.floor[t]
            rec = ld.floors[t]['record'] if t in ld.floors else None
            actor = f['actor'].actor if isinstance(f['actor'], tile_world.Piece) else int(f['actor'] or 0)
            floor = dict(loc=tuple(f['loc']), normal=tuple(f['normal']), links=links, ramp=rec['ramp'] if rec else 0,
                         actor=actor, volume=rec['volume'] if rec else 0)
        out[t] = dict(static=static, cover=cover[t], location=location.get(t), floor=floor,
                      before=dict(static=old, cover=ld.cover.get(t), links=len(ld.floors[t]['record']['links'])
                                  if t in ld.floors else None),
                      noWall=[toward(i) for i in chosen.get('noWall') or []], noFloor=bool(chosen.get('noFloor')))
    return out


def refit(path, forbidden):
    """Every rebuild volume of the package at `path` whose reach takes a tile of `forbidden` made as several that
    take none (rebuild_fit.fit over the tiles it reached), in its place in the level's actor list; the package
    written again. Returns [dict(volume, into: how many)]."""
    import lighting_records as lighting
    import native_copy
    import package_grow
    import rebuild_fit
    p = lighting.Package(Path(path))
    grid = native_copy.level_grid(p)
    corner = (grid['tx'], grid['ty'], grid['tz'])
    dims = (grid['nx'], grid['ny'], grid['nz'])
    template = native_copy.rebuild_template(p)
    g = package_grow.Grower(str(path))
    into, record = {}, []
    for v in native_copy.level_actors(p):
        if v <= 0 or p.cls(v) != 'XComRebuildWorldDataVolume':
            continue
        c, r = native_copy.volume_sphere(p, v)
        reach = rebuild_fit.span(c, r, corner, dims)
        if not any(all(reach[k][0] <= t[k] <= reach[k][1] for k in range(3)) for t in forbidden):
            continue
        need = (reach[0][0], reach[0][1], reach[1][0], reach[1][1], reach[2][0], reach[2][1])
        made = []
        for cube in rebuild_fit.fit(need, forbidden):
            centre, radius = rebuild_fit.pose(cube, corner)
            one = native_copy.add_volume(g, p, native_copy.reach_box(p, template, centre, radius),
                                         'XComRebuildWorldDataVolume', template)
            made.append(one['mapping'][one['template']])
        into[v] = made
        record.append(dict(volume=p.name(v).split('.')[-1], into=len(made)))
    if not into:
        return []
    level = p.by_name['TheWorld.PersistentLevel']
    data = bytearray(g.export_data(level))
    _, at, listed = native_copy.actor_list(p, data)
    after = [b for a in listed for b in (into[a] or [0] if a in into else [a])]
    struct.pack_into('<i', data, at + 4, len(after))
    data[at + 8:at + 8 + 4 * len(listed)] = struct.pack(f'<{len(after)}i', *after)
    g.relocate(level, bytes(data))
    tmp = Path(str(path) + '.refit')
    g.write(str(tmp))
    del g, p
    os.replace(tmp, path)
    return record


# ---------------------------------------------------------------- writing

def _store(model, hybrid, whole):
    stores = model['stores']
    for t, r in hybrid.items():
        stores[STATIC][t] = (struct.pack('<I', r['static']), 1)
        stores[COVER][t] = (struct.pack('<I', r['cover']), 1)
        if r['location'] is not None:
            stores[LOCATION][t] = (struct.pack('<3f', *r['location']), 1)
        raw, present = stores[FLOOR_STORE][t]
        rec = _floor_record(raw)
        rec['links'] = r['links']
        stores[FLOOR_STORE][t] = (_encode_floor(rec), present)
    for t, r in whole.items():
        stores[STATIC][t] = (struct.pack('<I', r['static']), 1)
        stores[COVER][t] = (struct.pack('<I', r['cover']), 1)
        stores[LOCATION][t] = ((struct.pack('<3f', *r['location']), 1) if r['location'] is not None
                               else (bytes(world_grid.SIZES['vector']), 0))
        stores[FLOOR_STORE][t] = ((_encode_floor(r['floor']), 1) if r['floor'] is not None
                                  else (bytes(world_grid.SIZES['floor']), 0))


def write(path, tiles, whole=(), candidates=(), edit=None):
    """The package at `path` with its diagonal tiles next to a change (`tiles`) and under one (`whole`) written, the
    carried corners among `candidates` ({tile: 'carried'}: find_new) written whole, and the project's diagonal cover
    (`edit`, native_copy.diagonal_edit: its marks written whole along their corners, the map's marked tiles it
    removes written whole by the straight rule), its rebuild volumes refitted round the carried corners and the
    marks. Returns the record, each part there only when it has something: written [{tile, static, cover, location,
    before, dropped}], whole [{tile, static, cover, location, links, before}] (newCorner 'carried' on a carried one;
    a mark's with mark (its corners, as (sx, sy)), and noWall (those with no wall) and noFloor where so; a removed
    one's with removed), refitted [{volume, into}], left (tiles next to a change with no floor of their own: their
    seed's flag alone, as the bake has it), rebuilt (tiles a volume told nothing of the change still takes), outside
    (marks off the grid, left out); {} for nothing written."""
    import lighting_records as lighting
    import native_copy
    import package_grow
    p = lighting.Package(Path(path))
    marks = dict(edit['marks']) if edit else {}
    removed = set(edit['removed']) if edit else set()
    marked = set(native_copy.diagonal_tiles(p)) - removed
    ld = Loaded(p)
    corner = ld.corner
    new = find_new(ld, candidates, marked | set(marks)) if candidates else {}
    refitted = []
    keep = set(new) | set(marks)
    if keep:
        rebuilt = set(native_copy.rebuild_order(p))
        if any(t in rebuilt for t in keep):
            # the carried corners and the marks and the tiles over them no change stands on, and every seeded tile
            # the volumes leave alone now, with the tiles over it
            forbidden = keep | {(x, y, z + n) for x, y, z in keep for n in range(1, STANDING_ROOM + 1)
                                if (x, y, z + n) not in candidates}
            forbidden |= {(x, y, z + n) for x, y, z in marked for n in range(STANDING_ROOM + 1)
                          if (x, y, z + n) not in rebuilt}
            forbidden = {t for t in forbidden if all(0 <= t[k] < ld.dims[k] for k in range(3))}
            del ld, p
            refitted = refit(path, forbidden)
            p = lighting.Package(Path(path))
            ld = Loaded(p)
    rebuilt = set(native_copy.rebuild_order(p))
    under = (set(whole) | set(new) | set(marks) | removed) - rebuilt
    hybrid, model = plan(p, set(tiles) - under - rebuilt - removed, ld)
    for t, r in hybrid.items():           # the tiles round a whole tile see these as written
        ld.flags[t], ld.cover[t] = r['static'], r['cover']
    planned = plan_whole(ld, under, marked | set(new) | set(marks), rebuilt, marks)
    if hybrid or planned:
        _store(model, hybrid, planned)
        index, blob = world_grid.container_of(p)
        encoded = world_grid.encode(model)
        if encoded[:world_links.HEADER] != blob[:world_links.HEADER]:
            raise ValueError('the container was not written back with its header')
        g = package_grow.Grower(str(path))
        g.relocate(index, encoded)
        tmp = Path(str(path) + '.diagonal')
        g.write(str(tmp))
        del g, p, ld
        os.replace(tmp, path)

    def hexed(v, width):
        return None if v is None else '%0*x' % (width, v)
    written = [dict(tile=list(t), static=hexed(r['static'], 7), cover=hexed(r['cover'], 6),
                    location=[round(v, 2) for v in r['location']] if r['location'] else None,
                    before=dict(static=hexed(r['before']['static'], 7), cover=hexed(r['before']['cover'], 6)),
                    dropped=r['dropped']) for t, r in sorted(hybrid.items())]
    whole_record = []
    for t, r in sorted(planned.items()):
        one = dict(tile=list(t), static=hexed(r['static'], 7), cover=hexed(r['cover'], 6),
                   location=[round(v, 2) for v in r['location']] if r['location'] else None,
                   links=len(r['floor']['links']) if r['floor'] else None,
                   before=dict(static=hexed(r['before']['static'], 7), cover=hexed(r['before']['cover'], 6),
                               links=r['before']['links']))
        if t in new:
            one['newCorner'] = 'carried'
        if t in marks:
            one['mark'] = [toward(i) for i, e in enumerate(tile_rule.TABLE) if marks[t] & e['cover']]
            half = [toward(i) for i, e in enumerate(tile_rule.TABLE) if marks[t] & e['low']]
            if half:
                one['half'] = half
            # (its middle in the world, as the project names it: the page finds its mark's record by it)
            one['at'] = [round(corner[k] + size * (t[k] + 0.5), 2) for k, size in enumerate((96.0, 96.0, 64.0))]
        if t in removed:
            one['removed'] = True
        if r['noWall']:
            one['noWall'] = r['noWall']
        if r['noFloor'] and t in marks:
            one['noFloor'] = True
        whole_record.append(one)
    out = {}
    if written:
        out['written'] = written
    if whole_record:
        out['whole'] = whole_record
    left = sorted(list(t) for t in tiles if t not in hybrid and t not in under and t not in rebuilt)
    if left:
        out['left'] = left
    if refitted:
        out['refitted'] = refitted
    taken = sorted(list(t) for t in (set(whole) | set(tiles) | set(marks)) & rebuilt)
    if taken:
        out['rebuilt'] = taken
    if edit and edit.get('outside'):
        out['outside'] = edit['outside']
    return out
