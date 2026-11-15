"""Ladders: where a ladder's climb starts and ends, whether the map's floors let it climb, and the hidden ladders of
streamed patches that stand in for one (private/plans/done/cars-doors-ladders-plan.md, sections 2.1, 3.6 and 5.2;
research/native/ladder-links.md).

The rebuild makes a ladder's two links from its foot tile: the foot tile (the tile of B = L − 16·fwd + (0, 0, 8)) must
have floor, and the top tile (the tile of T = L + 76·fwd + (0, 0, h + 8), h = 2 × (the mesh's bounds extent z + 1)), or
the tile below it, must have floor too: that one is the linked top tile T′, which gets the down link. These reproduce
Bar's baked links exactly. LWR's patches hold hidden ladders beside some of a map's own (patch_bar's XComLadder_11 and
_15 beside Bar's two): one whose ends are a map ladder's, or the nearest within half a tile, goes with that ladder, and
must go when it moves or is deleted, or the old place still climbs.

The compiler checks a copied or moved ladder's ends (ladder-climb) and hides its helpers (G6); the Build puts a rebuild
volume over the copy's T′ first (native_copy.py); the editor marks the ends (web/ladders.js is the twin of ends())."""
import math

TOP_REACH, FOOT_BACK, END_LIFT = 76.0, 16.0, 8.0     # units: along the ladder's facing, and up
TILE_SIZE = (96.0, 96.0, 64.0)
NEAR = 48.0          # how far a near helper may stand from its ladder (half a tile)
TURN = 65536


def points(location, rotation, extent_z):
    """(top T, foot B): the climb's two points, for a ladder at `location` turned `rotation` (rotator units; pitch and
    roll are 0 on every ladder seen) whose mesh's bounds extent in z is `extent_z`."""
    yaw = rotation[1] * 2 * math.pi / TURN
    fx, fy = math.cos(yaw), math.sin(yaw)
    h = 2 * (extent_z + 1)
    top = (location[0] + TOP_REACH * fx, location[1] + TOP_REACH * fy, location[2] + h + END_LIFT)
    foot = (location[0] - FOOT_BACK * fx, location[1] - FOOT_BACK * fy, location[2] + END_LIFT)
    return top, foot


def tile_of(point, origin, size=TILE_SIZE):
    """The tile (x, y, z) a world point falls in, on the grid whose corner is `origin` (x, y, z)."""
    return tuple(int(math.floor((point[k] - origin[k]) / size[k])) for k in range(3))


def ends(location, rotation, extent_z, origin, floors):
    """A ladder's ends against `floors` (a set of tiles with floor: the export's floorTiles): dict(top, foot (points),
    topTile, footTile, linkedTop (T′: the top tile, or the one below it, with floor; None if neither has), footFloor,
    climbs, why (what is missing: 'foot', 'top'))."""
    top, foot = points(location, rotation, extent_z)
    t, f = tile_of(top, origin), tile_of(foot, origin)
    below = (t[0], t[1], t[2] - 1)
    linked = t if t in floors else below if below in floors else None
    why = [w for w, ok in (('foot', f in floors), ('top', linked is not None)) if not ok]
    return dict(top=list(top), foot=list(foot), topTile=list(t), footTile=list(f),
                linkedTop=list(linked) if linked else None, footFloor=f in floors, climbs=not why, why=why)


def floor_tiles(scene):
    """The tiles of the export's original floor data (its tactical floorTiles), as a set."""
    return {tuple(f['tile']) for f in ((scene.get('tactical') or {}).get('floorTiles') or [])}


def extent_z(scene, obj):
    bounds = ((scene.get('meshes') or {}).get(obj.get('mesh')) or {}).get('bounds')
    return float(bounds[5]) if bounds else None


def helpers(scene):
    """The streamed patches' hidden ladders that stand in for the map's own: {map ladder actor: [dict(stream, actor,
    match ('exact': its foot and top tiles are the ladder's; 'near': the nearest within half a tile), distance)]}.
    Each hidden ladder goes with one map ladder at most: its exact one, else the nearest."""
    grid = scene.get('tileGrid') or {}
    origin = grid.get('origin')
    if not origin:
        return {}
    size = grid.get('size') or TILE_SIZE
    base = [o for o in scene.get('objects') or [] if o.get('actorClass') == 'XComLadder' and o.get('layer') == 'base'
            and o.get('sourcePackage') == scene.get('name')]

    def tiles(o):
        e = extent_z(scene, o)
        if e is None:
            return None
        top, foot = points(o['location'], o['rotation'], e)
        return tile_of(top, origin, size), tile_of(foot, origin, size)

    mine = {o['actor']: tiles(o) for o in base}
    out = {}
    for stream, info in sorted((scene.get('streams') or {}).items()):
        seen = set()
        for o in info.get('objects') or []:
            if o.get('actorClass') != 'XComLadder' or not o.get('hidden') or o['actor'] in seen:
                continue
            seen.add(o['actor'])
            theirs = tiles(o)
            dist = {b['actor']: math.hypot(o['location'][0] - b['location'][0], o['location'][1] - b['location'][1])
                    for b in base}
            exact = [a for a in dist if theirs is not None and mine[a] == theirs]
            near = [a for a in dist if dist[a] <= NEAR]
            if exact:
                actor, match = min(exact, key=dist.get), 'exact'
            elif near:
                actor, match = min(near, key=dist.get), 'near'
            else:
                continue
            out.setdefault(actor, []).append(dict(stream=stream, actor=o['actor'], match=match,
                                                  distance=round(dist[actor], 2)))
    return out
