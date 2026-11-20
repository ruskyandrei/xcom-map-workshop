"""A map that is little more than a level and a tile grid, given what a battle and the Build need of it
(private/plans/done/prefab-library-plan.md, 5.10; EXP-43).

The game's blank map, CB2_MP_Blank, loads as a single-player battle (EXP-43 run 1), but it lacks three things every
other map has:
- **soldier spawn points**: its XComSpawnPoints are a multiplayer map's (UnitType MPTeamOne and MPTeamTwo, from
  their archetypes), so the squad's loader finds none, the six soldiers start on one tile and LWR's pod mutator gives
  up (findings register F-90);
- **cursor volumes**: without one the cursor has a single floor (F-88);
- **a plain volume with a brush**: the Build clones one for every rebuild volume it adds (native_copy.py,
  rebuild_template), so it refuses a copy on such a map.

equip() brings them from another map of the install (the donor, URB_Bar unless told otherwise) with the transplanter
(transplant.py), which stages each as an actor under the level, and then places some of them:
- the donor's soldier spawn points (XComSpawnPoints with no UnitType of their own or their archetype's: the landing
  prefab's six), set on the map's own multiplayer team-one points and added to the level's actor list;
- the donor's cursor volumes, moved as one so that they cover the map's tile grid (stretched by DrawScale3D on an
  axis where the grid is longer than they are), and added to the level's actor list. In height they are made even
  storeys of 192 units from the grid's bottom (STOREY), the last one reaching the grid's top: the donor's own
  heights are its own building's (URB_Bar's first is 210 high), and a building made on the map from nothing goes
  by whole storeys (prefab plan, stage B2);
- the donor's rebuild template, left staged: native_copy.py finds it by its class and clones it.

A project that makes a building from nothing (buildings.py) needs two more templates, asked for with --building: a
building volume with floors and a plain floor volume. They are left staged too, their lists of the donor's pieces
and volumes cut by the transplanter.

needs() says which of these a map lacks; a map that lacks none is left alone.

--grid NX NY also makes the map's tile grid that many tiles, from the same corner (resize; prefab plan 5.11), and
--levels NZ that many levels high, from the same bottom (prefab plan 5.6b: the game's own maps go to 18; the editor
asks for up to 30 since 14 November 2026, which has not been played).

--grid-lines draws the ground as a grid (prefab plan 5.11, "a see-through grid"): the map's ground planes, its own
and the ones laid for a larger grid, are hidden in the game (bHidden: their collision stays, so the ground is still
stood on, as EXP-32's invisible floors are), and a white road line from the donor (URB_Bar's RoadPaintWhite_1536,
LINE) is laid along every tile edge, a row of copies to an edge, the last one shortened to end at the grid's edge.
--hide-ground hides the planes the same way and lays no lines (the game draws its own tile grid under the cursor).
--ambient-light lights prefab tests at runtime with a neutral sky light and an overhead directional light.

--clear is for a cleared map (private/plans/done/clear-map-plan.md, section 7, step 2): the map's own cursor volumes
are taken out of the level's actor list and the donor's are brought in their place, made even storeys over the whole
grid as the blank map's are. A grid with fewer storeys than the donor has cursor volumes lists only as many.

A map as it is that keeps its own cursor volumes and is given a larger grid (grow_cursors; the user, 13 November
2026): each of its volumes that reaches the grid's far X or Y side is stretched to the new one (the rest, fitted to
a building, keep their places), and with more levels the map's topmost plain volume is cloned into even storeys over
the whole grid from the top of its own up to the grid's new top, numbered on from its highest floor.

  python -B tools/bake/shell.py <map.upk> <out dir> [--donor URB_Bar] [--cooked <CookedPCConsole>] [--grid NX NY]
                                [--levels NZ] [--grid-lines | --hide-ground] [--ambient-light] [--building] [--clear]

Writes <out>/<map>.upk (it reads the game's texture caches through package.link_caches) and <out>/shell.json.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE.parent / 'viewer'))
sys.path.insert(0, str(HERE))
import props as legacy_props  # noqa: E402
import buildings  # noqa: E402
import native_copy  # noqa: E402
import native_lights  # noqa: E402
import package_grow  # noqa: E402
import scene_metadata  # noqa: E402
import schema as schema_module  # noqa: E402
import transplant  # noqa: E402
from package import Package, link_caches  # noqa: E402

LEVEL = 'TheWorld.PersistentLevel'
DONOR = 'URB_Bar'
STOREY = 192.0      # a cursor storey on a map that is given its cursor volumes: three levels of the tile grid
SQUAD = 6
# the grid's line (--grid-lines): a flat white road line of URB_Bar, 1,536 long (16 tiles) along its X, 16 wide,
# centred on its pivot; it blocks nothing
LINE, LINE_LENGTH, LINE_LIFT = 'XComLevelActor_366', 1536.0, 1.0
AMBIENT_UPPER, AMBIENT_LOWER = 0.55, 0.4
STAGE_SUN_BRIGHTNESS = 1.25


def actors(p, cls):
    level = p.by_name.get(LEVEL)
    return [i for i in p.children.get(level, []) if p.cls(i) == cls] if level else []


def listed(p):
    """The export indices in the level's actor list (a staged or a deleted actor is under the level and not in it)."""
    import struct
    level = p.by_name[LEVEL]
    _, end = p.properties(level)
    owner, count = struct.unpack_from('<ii', p.data, end)
    return set(struct.unpack_from('<%di' % count, p.data, end + 8))


def soldier_points(p):
    """The level's soldier spawn points: XComSpawnPoints whose UnitType is the class's own (neither the point nor its
    archetype sets one), in the level's actor list, by name."""
    live = listed(p)
    found = [i for i in actors(p, 'XComSpawnPoint') if i in live and p.effective(i, 'UnitType') is None]
    return sorted(found, key=lambda i: p.name(i))


def needs(p, building=False):
    """What the map `p` lacks of what equip() brings: a list of 'soldiers', 'cursor', 'template', and with `building`
    (the project makes a building from nothing) 'building' and 'floor', the two volumes buildings.py clones."""
    out = []
    if not soldier_points(p):
        out.append('soldiers')
    if not [i for i in actors(p, 'XComCursorVolume') if i in listed(p)]:
        out.append('cursor')
    try:
        native_copy.rebuild_template(p)
    except ValueError:
        out.append('template')
    if building:
        bt, ft = buildings.templates(p)
        out += [what for what, found in (('building', bt), ('floor', ft)) if found is None]
    return out


def grid_box(p):
    volumes = actors(p, 'XComLevelVolume')
    if len(volumes) != 1:
        raise ValueError('expected one XComLevelVolume, found %d' % len(volumes))
    b = scene_metadata.volume_bounds(p, volumes[0])
    return [*b['min'], *b['max']]


def squad_places(p, count=SQUAD):
    """Where the soldier points go: the map's own multiplayer team-one points' places, else a block of tiles by its
    player start."""
    points = sorted((i for i in actors(p, 'XComSpawnPoint') if p.effective(i, 'UnitType') == 'UNIT_TYPE_MPTeamOne'),
                    key=lambda i: p.name(i))
    places = [list(p.own(i, 'Location')) for i in points if p.own(i, 'Location')]
    if len(places) >= count:
        return places[:count]
    starts = actors(p, 'PlayerStart')
    if not starts or not p.own(starts[0], 'Location'):
        raise ValueError('the map has neither %d multiplayer spawn points nor a player start to put the squad by' % count)
    x, y, z = p.own(starts[0], 'Location')
    return [[x + 96 * (k % 3), y + 96 * (k // 3), z] for k in range(count)]


def set_location(walker, g, p, index, location):
    e = p.exports[index - 1]
    data = bytearray(g.export_data(index))
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    g.relocate(index, bytes(native_copy.set_vector(walker, g, data, start, 'Location', location)))


def fit(lo, hi, grid_lo, grid_hi):
    """A span lo..hi made to cover grid_lo..grid_hi: (scale, new lo). A span long enough moves the least that covers
    the grid, by whole units, and keeps its length; a shorter one is stretched to the grid exactly."""
    if hi - lo >= grid_hi - grid_lo - 1e-3:
        move = grid_lo - lo if lo > grid_lo else grid_hi - hi if hi < grid_hi else 0.0
        return 1.0, lo + float(round(move))
    return (grid_hi - grid_lo) / (hi - lo), grid_lo


def place_volume(walker, g, p, index, spans, like=None, props=None):
    """The unturned, unscaled volume `index` given a new span on some axes: `spans` {axis: (scale, new lo)}. Its
    Location is set, and its DrawScale3D where an axis is stretched. A clone made in `g` (not in `p`) names the
    volume it was cloned from as `like`: its brush and the layout of its data are that one's. `props` sets integer
    properties too ({name: value}). Returns dict(location, scale, box)."""
    import struct
    source = like or index
    origin, extent = native_copy.brush_bounds(p, source)
    location = list(p.own(source, 'Location', [0.0, 0.0, 0.0]))
    scale = [1.0, 1.0, 1.0]
    for k, (s, lo) in spans.items():
        scale[k] = s
        location[k] = lo - s * (origin[k] - extent[k])
    e = p.exports[source - 1]
    data = bytearray(g.export_data(index))
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    data = native_copy.set_vector(walker, g, data, start, 'Location', location)
    if scale != [1.0, 1.0, 1.0]:
        data = native_copy.set_vector(walker, g, data, start, 'DrawScale3D', scale)
    for name, value in (props or {}).items():
        data = native_lights.set_property(walker, g, data, start, name, 'IntProperty', None, struct.pack('<i', value))
    g.relocate(index, bytes(data))
    box = [location[k] + scale[k] * (origin[k] - extent[k]) for k in range(3)] + \
          [location[k] + scale[k] * (origin[k] + extent[k]) for k in range(3)]
    return dict(location=location, scale=scale, box=box)


def set_span(walker, g, p, index, spans, like=None, props=None):
    """The unturned volume `index` given new world spans on some axes, {axis: (lo, hi)}, the other axes kept as they
    are: its Location and DrawScale3D set, its DrawScale kept. A clone made in `g` names its source as `like` (its
    brush, place and scale are that one's). `props` sets integer properties too. Returns the new box."""
    source = like or index
    origin, extent = native_copy.brush_bounds(p, source)
    location = list(p.own(source, 'Location', [0.0, 0.0, 0.0]))
    whole = p.own(source, 'DrawScale', 1.0)
    scale = list(p.own(source, 'DrawScale3D', [1.0, 1.0, 1.0]))
    for k, (lo, hi) in spans.items():
        scale[k] = (hi - lo) / (2.0 * extent[k] * whole)
        location[k] = lo - whole * scale[k] * (origin[k] - extent[k])
    e = p.exports[source - 1]
    data = bytearray(g.export_data(index))
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    data = native_copy.set_vector(walker, g, data, start, 'Location', location)
    data = native_copy.set_vector(walker, g, data, start, 'DrawScale3D', scale)
    for name, value in (props or {}).items():
        data = native_lights.set_property(walker, g, data, start, name, 'IntProperty', None, struct.pack('<i', value))
    g.relocate(index, bytes(data))
    return [location[k] + whole * scale[k] * (origin[k] - extent[k]) for k in range(3)] + \
           [location[k] + whole * scale[k] * (origin[k] + extent[k]) for k in range(3)]


def grow_cursors(walker, g, p, own, old, box):
    """The map's own cursor volumes `own` on its grid made larger as it is, from the box `old` to `box` ([x0, y0, z0,
    x1, y1, z1]; the corner and the bottom are the same). A volume reaching the old far X or Y side (within a unit) is
    stretched to the new one; the others, fitted to a building, stay. A turned volume stays as it is. With more
    levels, the topmost plain volume (not a stair; the highest floor, the widest of those) is cloned into even storeys
    of STOREY over the whole grid, from the top of the map's plain volumes up to the new top (the last reaching it),
    with the floors after the map's highest: the cursor reaches the new levels (F-88: its floors are the volumes').
    Returns (the clones, to add to the level's list; the report)."""
    report = dict(stretched=[], turned=[], storeys=[])
    sized = []
    for index in own:
        name = p.name(index).rsplit('.', 1)[-1]
        if any(p.own(index, 'Rotation', [0, 0, 0])):
            report['turned'].append(name)
            continue
        lo, hi = native_copy.brush_box(p, index)
        sized.append((index, lo, hi))
        spans = {k: (lo[k], box[k + 3]) for k in (0, 1) if hi[k] >= old[k + 3] - 1.0 and box[k + 3] > hi[k] + 1e-3}
        if spans:
            set_span(walker, g, p, index, spans)
            report['stretched'].append(name)
    plain = [(i, lo, hi) for i, lo, hi in sized if not p.effective(i, 'm_bTreatAsStair')]
    clones = []
    if box[5] > old[5] + 1e-3 and plain:
        top = max(hi[2] for _, _, hi in plain)
        floor = max(p.effective(i, 'm_iFloorNumber') or 0 for i, _, _ in plain)
        source = max(plain, key=lambda s: (p.effective(s[0], 'm_iFloorNumber') or 0,
                                           (s[2][0] - s[1][0]) * (s[2][1] - s[1][1])))[0]
        if box[5] > top + 32.0:
            n = max(1, round((box[5] - top) / STOREY))
            for k in range(n):
                bottom = top + STOREY * k
                up = box[5] if k == n - 1 else bottom + STOREY
                made = native_copy.clone_actor(g, p, source, p.own(source, 'Location', [0.0, 0.0, 0.0]), [0, 0, 0])
                placed = set_span(walker, g, p, made['actor'], {0: (box[0], box[3]), 1: (box[1], box[4]), 2: (bottom, up)},
                                  like=source, props={'m_iFloorNumber': floor + 1 + k})
                clones.append(made['actor'])
                report['storeys'].append(dict(floor=floor + 1 + k, box=placed,
                                              clone=p.name(source).rsplit('.', 1)[-1]))
    return clones, report


def set_props(g, p, index, like=None, vectors=None, bools=None):
    """An actor's vectors ({name: [x, y, z]}) and booleans ({name: bool}) set, in `g`; a clone made in `g` names the
    actor it was cloned from as `like` (its data's layout). The walker knows the names added so far (bHidden and
    DrawScale3D can be new to the map)."""
    source = like or index
    e = p.exports[source - 1]
    data = bytearray(g.export_data(index))
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    walker = native_copy.Walker(p, g)
    for name, value in (vectors or {}).items():
        data = native_copy.set_vector(walker, g, data, start, name, value)
    for name, value in (bools or {}).items():
        data = native_lights.set_property(walker, g, data, start, name, 'BoolProperty', None, b'\x01' if value else b'\x00')
    g.relocate(index, bytes(data))


def configure_stage_light(g, p, actor, brightness, extra=()):
    """Give a stage light neutral colour and runtime lighting on static and dynamic meshes."""
    component = p.own(actor, 'LightComponent')
    data = g.export_data(component)
    start = native_lights.props_start(p, component)
    walker = native_copy.Walker(p, g)
    # Match XComMapEdSun's channels. The donor sky light is normally limited to units.
    channels = struct.pack('<ii', g.name('None'), 0)
    for name in ('bInitialized', 'BSP', 'Static', 'Dynamic', 'CompositeDynamic'):
        channels = native_lights.set_property(walker, g, channels, 0, name, 'BoolProperty', None, b'\x01')
    classification = struct.pack('<ii', g.name('LAC_DYNAMIC_AND_STATIC_AFFECTING'), 0)
    guids = native_lights.light_guids(p.path.stem + '|' + p.name(actor) + '|stage-light')
    white = b'\xff' * 4
    for name, kind, subtype, value in (
        ('LightingChannels', 'StructProperty', 'LightingChannelContainer', channels),
        ('LightAffectsClassification', 'ByteProperty', 'ELightAffectsClassification', classification),
        ('Brightness', 'FloatProperty', None, struct.pack('<f', brightness)),
        ('LightColor', 'StructProperty', 'Color', white),
        ('LightGuid', 'StructProperty', 'Guid', guids['LightGuid']),
        ('LightmapGuid', 'StructProperty', 'Guid', guids['LightmapGuid']),
        ('UseDirectLightMap', 'BoolProperty', None, b'\x00'),
        ('CastShadows', 'BoolProperty', None, b'\x00'),
        ('CastStaticShadows', 'BoolProperty', None, b'\x00'),
        ('CastDynamicShadows', 'BoolProperty', None, b'\x00'),
        *extra,
    ):
        data = native_lights.set_property(walker, g, data, start, name, kind, subtype, value)
    g.relocate(component, bytes(data))


def grid_lines(g, p, line, box):
    """The grid's lines (--grid-lines): copies of the staged `line` along every tile edge of the grid `box` ([x0, y0, z0,
    x1, y1, z1]), LINE_LIFT over its bottom; a row's last copy shortened (DrawScale3D along its length) to end at the
    grid's edge. Returns the copies (export indices)."""
    import math
    made = []
    z = box[2] + LINE_LIFT
    for axis in (0, 1):         # rows along x (at each y edge), then along y (at each x edge)
        across, along = 1 - axis, axis
        length = box[along + 3] - box[along]
        pieces = max(1, math.ceil(length / LINE_LENGTH - 1e-6))
        for edge in range(round((box[across + 3] - box[across]) / 96.0) + 1):
            at_across = box[across] + 96.0 * edge
            for k in range(pieces):
                span = min(LINE_LENGTH, length - k * LINE_LENGTH)
                centre = box[along] + k * LINE_LENGTH + span / 2
                location = [0.0, 0.0, z]
                location[along], location[across] = centre, at_across
                copy = native_copy.clone_actor(g, p, line, location, [0, 16384 * axis, 0])['actor']
                if span < LINE_LENGTH - 1e-3:
                    set_props(g, p, copy, like=line, vectors={'DrawScale3D': [span / LINE_LENGTH, 1.0, 1.0]})
                made.append(copy)
    return made


def ground_plane(p, model, origin):
    """The map's ground plane, if its ground is one: the XComLevelActor its ground tiles name most, when that is a
    flat piece (no more than 16 units thick) lying at the grid's bottom over a whole number of tiles, at least two
    by two. Returns (actor, tiles wide, tiles deep, {(block x, block y): actor} of the planes of that size), or None:
    URB_Bar's ground tiles name the bar's own floor slab most, 16 units up, which is no ground to lay elsewhere."""
    import world_grid
    named = {}
    for (x, y, z), (raw, present) in model['stores'][world_grid.FLOOR_STORE].items():
        if present and z == 0:
            named[world_grid.floor_actor(raw)] = named.get(world_grid.floor_actor(raw), 0) + 1
    planes = {}
    for actor in named:
        if actor > 0 and p.cls(actor) == 'XComLevelActor' and p.own(actor, 'Location'):
            try:
                box = native_lights.mesh_box(p, p.own(actor, 'StaticMeshComponent', 0), {})
            except Exception:  # noqa: BLE001  a piece whose mesh does not read is no plane
                continue
            w, d = (box[1] - box[0]) / 96.0, (box[3] - box[2]) / 96.0
            if (box[5] - box[4] <= 16.0 and abs(box[5] - origin[2]) <= 8.0 and min(w, d) >= 1.99
                    and abs(w - round(w)) < 0.01 and abs(d - round(d)) < 0.01):
                planes[actor] = (round(w), round(d), box[0], box[2])
    if not planes:
        return None
    template = max(planes, key=lambda a: named[a])
    wide, deep = planes[template][:2]
    block = lambda v, o, n: int((v - o + 1.0) // (n * 96.0))     # noqa: E731
    have = {(block(x0, origin[0], wide), block(y0, origin[1], deep)): a
            for a, (w, d, x0, y0) in planes.items() if (w, d) == (wide, deep)}
    return template, wide, deep, have


def scenery_to_walk(p, grid, nx, ny, nz, floor_off=()):
    """The map's own low ground in the area a grid grows over, which the Build makes walkable (F-100): each listed
    level actor no taller than native_copy.SCENERY_LOW whose box lies within the grid's levels (from a quarter
    level under its bottom to its top: the sky's ground plane, under the world, is not) and reaches into the new
    area (inside the grid of nx by ny tiles and past the far X or far Y side of the map's own `grid`, level_grid's),
    and that either saves its collision off (Act1_IntroLevel's backdrop: made walkable) or is a floor piece already
    (it collides and keeps bPathColliding: CsmallScout_Farm's raised backdrop, two levels over its play area's
    ground). A piece that collides but is no floor (debris saved with bPathColliding off) is left out, and so is one
    named in `floor_off` (short names: the project's flags turn or keep its Floor off; piece flags plan, 6.2).
    Returns [(export, world box, whether its collision is to be turned on)]."""
    import seed_map
    live = listed(p)
    grown = dict(grid, nx=nx, ny=ny)
    x1, y1 = grid['ox'] + 96.0 * grid['nx'], grid['oy'] + 96.0 * grid['ny']
    bottom, top = grid['oz'] - seed_map.FLOOR / 4, grid['oz'] + seed_map.FLOOR * nz
    out = []
    floor_off = set(floor_off)
    for i in sorted(live):
        if i <= 0 or p.cls(i) not in native_copy.SCENERY_CLASSES or not native_copy.has_mesh(p, i):
            continue
        if p.name(i).rsplit('.', 1)[-1] in floor_off:
            continue
        off = p.effective(i, 'bCollideActors', True) is False
        if not off and not (native_copy.collides(p, i) and p.effective(i, 'bPathColliding', True) is not False):
            continue
        box = native_copy.piece_box(p, i, p.own(i, 'Location', [0.0, 0.0, 0.0]), p.own(i, 'Rotation', [0, 0, 0]))
        # the new area is past the map's own far X or far Y side (the corner never moves)
        if (box[5] - box[4] <= native_copy.SCENERY_LOW and box[4] >= bottom and box[5] <= top
                and native_copy.in_grid(box, grown) and (box[1] > x1 or box[3] > y1)):
            out.append((i, box, off))
    return out


def scenery_tiles(box, origin, nx, ny):
    """The tiles a walkable piece of scenery (its world `box`) gives floor on: those whose centre it covers, at the
    level of its top (the floor stands in the level its surface is in). [(x, y, z)]."""
    import math
    import seed_map
    z = int(math.floor((box[5] + 2.0 - origin[2]) / seed_map.FLOOR))
    xs = range(max(0, int(math.ceil((box[0] - origin[0]) / 96.0 - 0.5))), min(nx, int(math.floor((box[1] - origin[0]) / 96.0 - 0.5)) + 1))
    ys = range(max(0, int(math.ceil((box[2] - origin[1]) / 96.0 - 0.5))), min(ny, int(math.floor((box[3] - origin[1]) / 96.0 - 0.5)) + 1))
    return [(x, y, z) for x in xs for y in ys]


def resize(walker, g, p, nx, ny, ground=True, nz=None, floor_off=()):
    """The map's tile grid made nx by ny tiles and nz levels (None: the map's), from the same corner and bottom
    (prefab plan 5.11; the levels 5.6b; a smaller grid, clear-map plan 7.5): each axis smaller, the same or larger,
    and the corner and the bottom never move, so every kept tile keeps its index:
    - ground, with `ground` and where the map's ground is a plane (ground_plane): each block of the new area that
      has none gets a clone of it (it reads the original's lightmap). Otherwise nothing is laid, and the new
      ground-level tiles are written as open air for the battle to check: the project lays its own floor. Pieces
      past a smaller grid's edges, ground planes among them, stay where they are;
    - the tile data written anew (tools/upk/world_grid.py resize: every tile the map has inside the grid kept, bare
      ground for the new area, open air on the new levels; the tiles past a smaller grid's edges and top dropped,
      its new far edges given the edge's flags and the links that leave it cut);
    - the world data's NumX, NumY, NumZ, NumTiles and WorldBounds;
    - the level volume stretched or shrunk to the new grid (its Location and DrawScale3D; its brush is not
      rewritten);
    - the map's own low scenery in the new area made walkable (scenery_to_walk, F-100): the ground planes and
      pavements it is seen against beyond its play area save their collision off, and the battle would find no floor
      on them. Their collision goes on (native_copy.make_walkable), the tiles they give floor on get the seed bit
      (scenery_tiles: a new tile above the bottom level is open air, which the rebuild passes over), and no ground
      plane is laid in a block one of them covers (it would be a floor under the scenery's: units would walk under
      CsmallScout_Farm's raised backdrop). A piece the edit deletes or moves is taken out of the level afterwards
      and changes nothing; one whose Floor the project's flags turn off (`floor_off`) is left as the map has it;
    - a rebuild volume over the whole grid's ground and the levels over it, so the battle works those tiles out
      again when it starts. It is three levels high, or up to the level over the highest walkable scenery: the
      rebuild passes over a tile whose flags have none of the low bits (native-code-notes.md, F-29), as the new
      levels' open air has none, and what a project puts up there is seeded by the Build's seeds stage.
    The cursor volumes are the caller's (they are fitted to the grid in any case). Returns (the actors to add to the
    level's list, the report)."""
    import struct
    import seed_map
    import world_grid
    grid = native_copy.level_grid(p)
    nz = grid['nz'] if nz is None else nz
    if min(nx, ny, nz) < 1:
        raise ValueError('a grid of %d by %d by %d tiles' % (nx, ny, nz))
    origin = [float(round(grid[k])) for k in ('ox', 'oy', 'oz')]
    # the corner the game counts the tiles from (WorldBounds', a unit under the volume's): the tile data's floor places
    corner = [float(round(grid[k])) for k in ('tx', 'ty', 'tz')]
    container, blob = world_grid.container_of(p)
    model = world_grid.decode(blob)
    # the map's own scenery the new area takes in, made walkable below (F-100)
    scenery = scenery_to_walk(p, grid, nx, ny, nz, floor_off)
    # the ground planes: by the block of tiles each lies over
    plane = ground_plane(p, model, origin) if ground else None
    add, laid, template, covered = [], [], None, []
    if plane:
        template, wide, deep, have = plane
        location, rotation = p.own(template, 'Location'), p.own(template, 'Rotation', [0, 0, 0])
        home = next(k for k, a in have.items() if a == template)
        for bx in range(-(-nx // wide)):
            for by in range(-(-ny // deep)):
                # only a block that reaches the new area: a gap in the map's own ground (URB_Bar has three under the
                # bar) is left as it is
                if (bx, by) in have or (min((bx + 1) * wide, nx) <= grid['nx'] and min((by + 1) * deep, ny) <= grid['ny']):
                    continue
                at = [location[0] + (bx - home[0]) * wide * 96.0, location[1] + (by - home[1]) * deep * 96.0, location[2]]
                # a block whose middle walkable scenery covers has its floor there, at the scenery's height
                cx = origin[0] + 96.0 * (bx * wide + min(wide, nx - bx * wide) / 2.0)
                cy = origin[1] + 96.0 * (by * deep + min(deep, ny - by * deep) / 2.0)
                if any(b[0] <= cx <= b[1] and b[2] <= cy <= b[3] for _, b, _ in scenery):
                    covered.append([bx, by])
                    continue
                clone = native_copy.clone_actor(g, p, template, at, rotation)
                have[(bx, by)] = clone['actor']
                add.append(clone['actor'])
                laid.append(at)
    # a block the planes don't reach (the map's own ground has a gap there) names no floor piece
    grown = world_grid.resize(model, nx, ny, corner,
                              (lambda x, y: have.get((x // wide, y // deep), 0)) if plane else None, nz)
    # the tiles the walkable scenery gives floor on: put in the rebuild's queue
    seeded = 0
    for _, box, _ in scenery:
        for tile in scenery_tiles(box, origin, nx, ny):
            raw, present = grown['stores'][0].get(tile, (None, 0))
            if raw is None:
                continue
            flags = struct.unpack('<I', raw)[0]
            if not flags & 0xFFF:
                grown['stores'][0][tile] = (struct.pack('<I', flags | world_grid.SEED), 1)
                seeded += 1
    g.relocate(container, world_grid.encode(grown))
    # the world data's own numbers
    volume = next(i for i in actors(p, 'XComLevelVolume') if p.own(i, 'Brush', 0) > 0)
    world = p.own(volume, 'WorldData', 0)
    e = p.exports[world - 1]
    data = bytearray(g.export_data(world))
    start = legacy_props.props_start(p.data, e, p.names) - e['off']
    bounds = bytearray(p.own(world, 'WorldBounds'))
    # (the maps' bounds reach a unit past the grid on every side)
    struct.pack_into('<2f', bounds, 12, origin[0] + 96.0 * nx + 1.0, origin[1] + 96.0 * ny + 1.0)
    if nz != grid['nz']:
        struct.pack_into('<f', bounds, 20, origin[2] + seed_map.FLOOR * nz + 1.0)
    numbers = [('NumX', nx), ('NumY', ny)] + ([('NumZ', nz)] if nz != grid['nz'] else []) + [('NumTiles', nx * ny * nz)]
    for name, value in numbers:
        data = native_lights.set_property(walker, g, data, start, name, 'IntProperty', None, struct.pack('<i', value))
    data = native_lights.set_property(walker, g, data, start, 'WorldBounds', 'StructProperty', 'Box', bytes(bounds))
    g.relocate(world, bytes(data))
    lo, hi = native_copy.brush_box(p, volume)
    spans = {0: ((96.0 * nx) / (hi[0] - lo[0]), origin[0]), 1: ((96.0 * ny) / (hi[1] - lo[1]), origin[1])}
    if nz != grid['nz']:
        spans[2] = ((seed_map.FLOOR * nz) / (hi[2] - lo[2]), origin[2])
    stretched = place_volume(walker, g, p, volume, spans)
    top = origin[2] + 3 * seed_map.FLOOR
    if scenery:     # up to the level over the highest walkable scenery's
        import math
        high = max(b[5] for _, b, _ in scenery)
        top = max(top, origin[2] + seed_map.FLOOR * (math.floor((high + 2.0 - origin[2]) / seed_map.FLOOR) + 2))
    rebuild = native_copy.add_rebuild_volume(g, p, [origin[0], origin[0] + 96.0 * nx, origin[1], origin[1] + 96.0 * ny,
                                                    origin[2] - seed_map.REBUILD_PAD, top])
    add.append(rebuild['export'])
    for index, _, off in scenery:
        if off:
            native_copy.make_walkable(g, p, index)
    walked = [p.name(i).rsplit('.', 1)[-1] for i, _, off in scenery if off]
    floors = [p.name(i).rsplit('.', 1)[-1] for i, _, off in scenery if not off]
    return add, dict(walkableScenery=walked, sceneryFloors=floors, sceneryTilesSeeded=seeded,
                     **({'floorKeptOff': sorted(floor_off)} if floor_off else {}),
                     blocksUnderScenery=covered, laidPlanes=[have[k] for k in have if have[k] in add] if plane else [],
                     before=[grid['nx'], grid['ny'], grid['nz']], grid=[nx, ny, nz],
                     groundPlane=p.name(template).rsplit('.', 1)[-1] if template else None, planesLaid=len(laid),
                     ground='laid' if plane else 'not asked for' if not ground else 'none: the map\'s ground is no plane',
                     containerBytes=[len(blob), len(world_grid.encode(grown))], levelVolume=stretched,
                     rebuildVolume=dict(bounds=rebuild['bounds'], extent=rebuild['rebuildExtent']))


def equip(map_path, out, cooked=None, donor=DONOR, schema=None, grid=None, ground=True, building=False, levels=None,
          lines=False, hide=False, ambient=False, clear=False, floor_off=()):
    """The map with what needs() says it lacks, and with its tile grid made `grid` (nx, ny) tiles and `levels`
    levels high when those are given and larger, written as <out>/<map>.upk. Returns the report (also
    <out>/shell.json): dict(map, donor, needs, brought {what: [staged actor]}, placed, resized, written, shelled). A
    map that lacks nothing and keeps its grid is left alone: nothing is written. With `clear` (a cleared map) the map's
    own cursor volumes are taken out and the donor's brought in their place (report: clearedCursors). `floor_off`
    names the map's pieces whose Floor the project's flags turn off: a grown grid's scenery floor leaves them as they
    are (resize)."""
    map_path, out = Path(map_path), Path(out)
    cooked = Path(cooked) if cooked else map_path.parent
    before = Package(map_path)
    lacking = needs(before, building)
    if clear and 'cursor' not in lacking:
        lacking.append('cursor')
    size = native_copy.level_grid(before)
    grid = list(grid) if grid else [size['nx'], size['ny']]
    levels = levels or size['nz']
    if (tuple(grid), levels) == ((size['nx'], size['ny']), size['nz']):
        grid = None
    report = dict(map=str(map_path), donor=None, needs=lacking, brought={}, placed=[], resized=None, written=None)
    hide = hide or lines
    if not lacking and not grid and not hide and not ambient:
        return report
    source, staged, donor_path = map_path, {}, None
    if lacking or lines or ambient:
        donor_path = transplant.donor_file(cooked, donor)
        if schema is None:
            schema = schema_module.Schema(schema_module.build(cooked))
        d = transplant.Donor(donor_path, schema)
        dp = d.p
        roots = {}
        if 'soldiers' in lacking:
            roots['soldiers'] = soldier_points(dp)[:SQUAD]
            if len(roots['soldiers']) < SQUAD:
                raise ValueError('%s has fewer than %d soldier spawn points' % (donor_path.name, SQUAD))
        if 'cursor' in lacking:
            roots['cursor'] = sorted(actors(dp, 'XComCursorVolume'), key=lambda i: dp.effective(i, 'm_iFloorNumber') or 0)
            if not roots['cursor']:
                raise ValueError('%s has no cursor volumes' % donor_path.name)
        if 'template' in lacking:
            roots['template'] = [dp.by_name[LEVEL + '.' + native_copy.rebuild_template(dp)]]
        if lines:
            if LEVEL + '.' + LINE not in dp.by_name:
                raise ValueError('%s has no %s, the grid line' % (donor_path.name, LINE))
            roots['line'] = [dp.by_name[LEVEL + '.' + LINE]]
        if ambient:
            live = listed(dp)
            skies = [i for i in actors(dp, 'SkyLight') if i in live]
            if len(skies) != 1:
                raise ValueError('%s must have one SkyLight to supply the stage fill' % donor_path.name)
            roots['ambient'] = skies
        if 'building' in lacking or 'floor' in lacking:
            bt, ft = buildings.templates(dp)
            if bt is None or ft is None:
                raise ValueError('%s has no building volume and floor volume to clone' % donor_path.name)
            if 'building' in lacking:
                roots['building'] = [bt['actor']]
            if 'floor' in lacking:
                roots['floor'] = [ft]
        dest = transplant.Destination(map_path)
        shared = {}
        for what, group in roots.items():
            for root in group:      # one by one: none names another
                r = transplant.bring(dest.g, dest, d, [root], shared)
                staged.setdefault(what, []).append(r['staged'][dp.name(root)].rsplit('.', 1)[-1])
        source = out / 'staged' / map_path.name
        source.parent.mkdir(parents=True, exist_ok=True)
        dest.g.write(str(source))
        link_caches(source.parent, map_path.parent)

    # second pass: the grid resized, and the staged actors that are to be in the battle placed and listed
    p = Package(source)
    g = package_grow.Grower(str(source))
    walker = native_copy.Walker(p, g)
    add = []
    if ambient:
        index = p.by_name[LEVEL + '.' + staged['ambient'][0]]
        configure_stage_light(g, p, index, AMBIENT_UPPER, (
            ('LowerBrightness', 'FloatProperty', None, struct.pack('<f', AMBIENT_LOWER)),
            ('LowerColor', 'StructProperty', 'Color', b'\xff' * 4),
        ))
        add.append(index)
        # Use the blank map's overhead light live, so it also reaches copies with inherited lightmaps.
        live = listed(p)
        sun, = [i for i in actors(p, 'DirectionalLight') if i in live]
        set_props(g, p, sun, bools={'bStatic': False, 'bMovable': True})
        configure_stage_light(g, p, sun, STAGE_SUN_BRIGHTNESS, (
            ('bForceDynamicLight', 'BoolProperty', None, b'\x01'),
            ('bHasLightEverBeenBuiltIntoLightMap', 'BoolProperty', None, b'\x00'),
            ('bPrecomputedLightingIsValid', 'BoolProperty', None, b'\x00'),
        ))
        report['ambientLight'] = dict(actor=p.name(index), brightness=AMBIENT_UPPER, lowerBrightness=AMBIENT_LOWER,
                                      directional=p.name(sun), directionalBrightness=STAGE_SUN_BRIGHTNESS)
    for name, place in zip(staged.get('soldiers', []), squad_places(p)):
        index = p.by_name[LEVEL + '.' + name]
        set_location(walker, g, p, index, place)
        add.append(index)
        report['placed'].append(dict(actor=name, location=place))
    box = grid_box(p)
    old = list(box)
    if grid:
        more, report['resized'] = resize(walker, g, p, int(grid[0]), int(grid[1]), ground, int(levels), floor_off)
        add += more
        box = [box[0], box[1], box[2], box[0] + 96.0 * grid[0], box[1] + 96.0 * grid[1],
               box[5] if levels == size['nz'] else box[2] + 64.0 * levels]
    if hide:
        import world_grid
        origin = [float(round(v)) for v in box[:3]]
        found = ground_plane(p, world_grid.decode(world_grid.container_of(p)[1]), origin)
        # every listed piece of the ground plane's mesh: the planes the ground tiles name, and any lying off the grid
        # (the blank map has one 2,500 units away)
        mesh = p.effective(p.own(found[0], 'StaticMeshComponent', 0), 'StaticMesh') if found else None
        live = listed(p)
        own = sorted(i for i in actors(p, 'XComLevelActor') if mesh and i in live
                     and p.effective(p.own(i, 'StaticMeshComponent', 0), 'StaticMesh') == mesh)
        laid = (report['resized'] or {}).pop('laidPlanes', [])
        for index in own:
            set_props(g, p, index, bools={'bHidden': True})
        for index in laid:
            set_props(g, p, index, like=found[0], bools={'bHidden': True})
        report['hiddenGround'] = dict(planes=len(own) + len(laid))
        if lines:
            line = p.by_name[LEVEL + '.' + staged['line'][0]]
            made = grid_lines(g, p, line, box)
            add += made
            report['gridLines'] = dict(lines=len(made), hiddenPlanes=len(own) + len(laid),
                                       line=dict(donor=donor, actor=LINE))
    elif report['resized']:
        report['resized'].pop('laidPlanes', None)
    # the cursor volumes cover the grid: the ones brought, and the map's own when its grid grew (grow_cursors); a
    # cleared map's own are taken out of the level's list (the donor's even storeys stand in their place)
    live = listed(p)
    brought = [p.by_name[LEVEL + '.' + name] for name in staged.get('cursor', [])]
    own_cursors = [i for i in actors(p, 'XComCursorVolume') if i in live and i not in brought]
    if clear:
        if own_cursors:
            native_copy.empty_slots(g, p, set(own_cursors))
        report['clearedCursors'] = sorted(p.name(i).rsplit('.', 1)[-1] for i in own_cursors)
        own_cursors = []
    # a grid with fewer storeys than the donor has cursor volumes lists only as many (the rest stay staged, unlisted)
    storeys = max(1, round((box[5] - box[2]) / STOREY))
    brought = sorted(brought, key=lambda i: (p.effective(i, 'm_iFloorNumber') or 0, p.name(i)))[:storeys]
    if grid and own_cursors:
        more, report['grownCursors'] = grow_cursors(walker, g, p, own_cursors, old, box)
        add += more
    cursor = brought
    if cursor:
        boxes = [native_copy.brush_box(p, i) for i in cursor]
        lo = [min(b[0][k] for b in boxes) for k in range(3)]
        hi = [max(b[1][k] for b in boxes) for k in range(3)]
        spans = {k: fit(lo[k], hi[k], box[k], box[k + 3]) for k in range(2)}
        # the ones brought are made even storeys from the grid's bottom, in the order of their floors; a grid taller
        # than they reach gets more, clones of the last with the floors after it (the maps' cursor floors go to 6: 18
        # levels are six storeys; the editor's 30 levels are ten)
        order = list(brought)
        clones = []
        if order and storeys > len(order):
            last = order[-1]
            floor = p.effective(last, 'm_iFloorNumber') or len(order)
            for k in range(storeys - len(order)):
                made = native_copy.clone_actor(g, p, last, p.own(last, 'Location', [0.0, 0.0, 0.0]), [0, 0, 0])
                clones.append((made['actor'], last, floor + 1 + k))
        for index, (vlo, vhi) in zip(cursor, boxes):
            span = (1.0, vlo[2])
            if index in order:
                n = order.index(index)
                bottom = box[2] + STOREY * n
                top = max(box[5], bottom + STOREY) if n == storeys - 1 else bottom + STOREY
                span = ((top - bottom) / (vhi[2] - vlo[2]), bottom)
            placed = place_volume(walker, g, p, index, {0: spans[0], 1: spans[1], 2: span})
            report['placed'].append(dict(actor=p.name(index).rsplit('.', 1)[-1],
                                         floor=p.effective(index, 'm_iFloorNumber'), **placed))
        vlo, vhi = boxes[cursor.index(order[-1])] if clones else (None, None)
        for n, (index, last, floor) in enumerate(clones, len(order)):
            bottom = box[2] + STOREY * n
            top = max(box[5], bottom + STOREY) if n == storeys - 1 else bottom + STOREY
            placed = place_volume(walker, g, p, index, {0: spans[0], 1: spans[1],
                                                        2: ((top - bottom) / (vhi[2] - vlo[2]), bottom)},
                                  like=last, props={'m_iFloorNumber': floor})
            report['placed'].append(dict(actor='%s (a clone of %s)' % (index, p.name(last).rsplit('.', 1)[-1]),
                                         floor=floor, **placed))
        add += brought + [index for index, _, _ in clones]
    if add:
        native_copy.add_to_level(g, p, add)
    target = out / map_path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    report['written'] = g.write(str(target))
    link_caches(out, map_path.parent)
    report.update(brought=staged, shelled=str(target))
    if donor_path:
        report['donor'] = dict(map=donor_path.stem, file=str(donor_path), sha256=transplant.sha256(donor_path))
    (out / 'shell.json').write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8', newline='\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('map')
    parser.add_argument('out')
    parser.add_argument('--donor', default=DONOR)
    parser.add_argument('--cooked', help='where the donor is looked for; by default the folder the map is in')
    parser.add_argument('--grid', nargs=2, type=int, metavar=('NX', 'NY'),
                        help='make the tile grid this many tiles, from the same corner')
    parser.add_argument('--levels', type=int, metavar='NZ', help='make the tile grid this many levels high, from the same bottom')
    parser.add_argument('--grid-lines', action='store_true', help='hide the ground planes and lay a white line along every tile edge')
    parser.add_argument('--hide-ground', action='store_true', help='hide the ground planes (still stood on), no lines')
    parser.add_argument('--ambient-light', action='store_true', help='add a neutral runtime fill light for a prefab test')
    parser.add_argument('--no-ground', action='store_true', help='lay no ground over the new area')
    parser.add_argument('--building', action='store_true',
                        help='also bring a building volume and a floor volume to clone, where the map has none')
    parser.add_argument('--clear', action='store_true',
                        help='a cleared map: take out its own cursor volumes and bring even storeys over the grid')
    parser.add_argument('--floor-off', action='append', default=[], metavar='ACTOR',
                        help="a piece whose Floor the project's flags turn off: a grown grid's scenery floor leaves it "
                             'as it is (repeat for more)')
    args = parser.parse_args()
    report = equip(args.map, args.out, args.cooked, args.donor, grid=args.grid, ground=not args.no_ground,
                   building=args.building, levels=args.levels, lines=args.grid_lines, hide=args.hide_ground,
                   ambient=args.ambient_light, clear=args.clear, floor_off=args.floor_off)
    if not report['shelled' if 'shelled' in report else 'written']:
        print('%s lacks nothing: left alone' % Path(args.map).name)
        return
    if report['needs']:
        print('%s lacked %s; from %s: %s' % (Path(args.map).name, ', '.join(report['needs']), report['donor']['map'],
                                             '; '.join('%s %s' % (k, ', '.join(v)) for k, v in report['brought'].items())))
    if report['resized']:
        r = report['resized']
        print('grid %s -> %s: ground %s (%d planes), tile data %d -> %d bytes, %d pieces of scenery made walkable, '
              '%d floor already, %d tiles queued'
              % (r['before'], r['grid'], r['ground'], r['planesLaid'], *r['containerBytes'],
                 len(r.get('walkableScenery') or []), len(r.get('sceneryFloors') or []), r.get('sceneryTilesSeeded', 0)))
    print('written %s' % report['shelled'])


if __name__ == '__main__':
    main()
