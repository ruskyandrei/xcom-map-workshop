"""Source building/floor caches for inspection; no guessed spatial membership."""
from itertools import product
import math
import struct
from export_math import transform


TILE_SIZE = [96, 96, 64]
# how far the level volume's box may sit from the game's record (a unit inside WorldBounds on every side) before the
# grid's notes say so; the installed maps' boxes are within 0.002 of it at the low corner
BOX_NOTE = 0.01


def level_list(p):
    """The persistent level's actor list as a set of export indices (export 33: the effects, the spawn points and the
    mission objects read it here; tools/bake/native_copy.level_actors is the Build's ordered copy). None where the
    package has no persistent level or its native data does not start with the list."""
    level = p.by_name.get("TheWorld.PersistentLevel")
    if level is None:
        return None
    try:
        _, end = p.properties(level)
        owner, count = struct.unpack_from("<ii", p.data, end)
        if owner != level or not 0 <= count < 1_000_000:
            return None
        return set(struct.unpack_from("<%di" % count, p.data, end + 8))
    except (ValueError, struct.error):
        return None


def tile_header(p, container):
    """The tile counts [nx, ny, nz] in the header of a world data container's first store."""
    r = p.native(container)
    chunks, order = r.count(), r.count()
    if chunks != order: raise ValueError('Tile chunk/order counts disagree')
    r.take(order*4)
    dims = list(r.unpack('3i'))
    if not all(0 < v <= 100000 for v in dims): raise ValueError('Invalid tile dimensions')
    return dims


def world_record(p, volume):
    """The grid a level volume's world data saves (XComWorldData's WorldBounds and NumX, NumY, NumZ): dict(low, high,
    counts), or None when it saves none that reads (no world data, no valid WorldBounds, a count missing)."""
    world = p.effective(volume, 'WorldData', 0)
    if not world or world <= 0 or world > len(p.exports):
        return None
    raw = p.effective(world, 'WorldBounds')
    counts = [p.effective(world, k) for k in ('NumX', 'NumY', 'NumZ')]
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != 25 or not raw[24] or not all(isinstance(v, int) and v > 0 for v in counts):
        return None
    v = struct.unpack('<6f', raw[:24])
    if not all(math.isfinite(x) for x in v):
        return None
    return dict(low=list(v[:3]), high=list(v[3:]), counts=counts)


def game_grid(p, box=None):
    """The map's tile grid as the game has it (private/plans/done/game-grid-plan.md), or None for a package with no
    tile data. dict(origin, tiles, dimensions, size, source, notes), every corner in game axes [x, y, z]:
    - tiles: the corner the game counts its tiles from, its world data's WorldBounds' low corner (a tile's centre is
      tiles + (96x + 48, 96y + 48, 64z + 32): research/native/cover-build.md; every map's saved floors sit there);
    - origin: the level volume's box's low corner, a unit over `tiles` on every axis, where the maps' own pieces stand
      on whole tiles: the corner the editor places by (snap, the lines, the turn pivot, the grid rule) and every
      project and prefab is saved against. `box` (dict(min, max), game axes) is the box as the caller works it out,
      so its numbers stay its own; read from the volume when None. Where the box can't be had, tiles plus a unit;
    - dimensions: the tile counts of the tile data (NumX, NumY, NumZ say the same on every installed map);
    - source: 'world-data', or 'level-volume' where the map saves no grid of its own (WorldBounds, the counts): the
      box's corner and the tile data's counts, the game's corner a unit under it as on every installed map;
    - notes: what disagrees (the counts with the record, the box with it), for the caller to report. They never take
      the grid away: a map with tile data always has one."""
    containers = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'XComWorldDataContainer']
    if not containers:
        return None
    dims = tile_header(p, containers[0])
    notes = []
    volumes = [i for i in range(1, len(p.exports) + 1) if p.cls(i) == 'XComLevelVolume' and p.effective(i, 'Brush', 0) > 0]
    records = [(i, world_record(p, i)) for i in volumes]
    records = [(i, r) for i, r in records if r]
    if box is None and len(volumes) == 1:
        box = volume_bounds(p, volumes[0])
    if len(records) > 1 and box is not None:
        # (none of the installed maps has more than one: the one whose corner is the box's)
        records.sort(key=lambda ir: sum(abs(ir[1]['low'][k] + 1 - box['min'][k]) for k in range(3)))
    record = records[0][1] if records else None
    if record is None:
        if box is None:
            raise ValueError('the map saves no tile grid of its own and has no level volume to take one from')
        origin = [float(v) for v in box['min']]
        notes.append('the map saves no tile grid of its own (its world data\'s WorldBounds and tile counts): the grid '
                     'is its level volume\'s, the game\'s corner taken a unit under the volume\'s as on every installed map')
        return dict(origin=origin, tiles=[v - 1 for v in origin], dimensions=dims, size=list(TILE_SIZE),
                    source='level-volume', notes=notes)
    tiles = [float(v) for v in record['low']]
    if record['counts'] != dims:
        notes.append('the map\'s world data counts %s tiles and its tile data holds %s: the grid is the tile data\'s'
                     % (' by '.join(map(str, record['counts'])), ' by '.join(map(str, dims))))
    if box is None:
        origin = [v + 1 for v in tiles]
    else:
        origin = [float(v) for v in box['min']]
        if any(abs(origin[k] - tiles[k] - 1) > BOX_NOTE for k in range(3)):
            notes.append('the level volume\'s corner is not a unit inside the world data\'s bounds (%s against %s)'
                         % ([round(v, 3) for v in origin], [round(v, 3) for v in tiles]))
        for k, (more, less, what) in enumerate((('wider', 'narrower', 'tiles across'), ('longer', 'shorter', 'tiles along'),
                                                ('taller', 'lower', 'levels'))):
            over = (box['max'][k] - box['min'][k]) - dims[k] * TILE_SIZE[k]
            if abs(over) > BOX_NOTE:
                notes.append('the level volume\'s box is %g units %s than its %d %s: the grid is the game\'s'
                             % (round(abs(over), 3), more if over > 0 else less, dims[k], what))
    return dict(origin=origin, tiles=tiles, dimensions=dims, size=list(TILE_SIZE), source='world-data', notes=notes)


def tile_grid(p, bounds, warn):
    """The export's `tileGrid` (game_grid) for a level volume's box in the viewer's basis (bounds: dict(min, max),
    [x, z, y]), its notes reported through `warn`; None for a package with no tile data."""
    box = dict(min=[bounds['min'][0], bounds['min'][2], bounds['min'][1]],
               max=[bounds['max'][0], bounds['max'][2], bounds['max'][1]])
    try:
        grid = game_grid(p, box)
    except (ValueError, struct.error, IndexError) as error:
        warn('XComWorldData', f'Tile grid unavailable: {error}')
        return None
    if grid is None:
        return None
    for note in grid.pop('notes'):
        warn('XComWorldData', f'Tile grid: {note}')
    return grid


def saved_floor_tiles(p, container, dimensions=None):
    """The baked floor tiles of a world data container, with their owning actors."""
    import world_links
    reader = p.native(container)
    blob, offset = reader.take(reader.end - reader.pos), 0
    for kind in ('flags', 'flags', 'floor'):
        store = world_links.parse_store(blob, offset, kind)
        if dimensions is None:
            dimensions = store['dims']
        if tuple(store['dims']) != tuple(dimensions):
            raise ValueError('Floor/grid dimensions disagree')
        offset = store['end']
    floors = []
    for chunk in store['chunks']:
        for tile in chunk['tiles']:
            if not tile['present']:
                continue
            value = tile['value']
            location, normal = value['loc'], value['normal']
            if not all(math.isfinite(v) for v in (*location, *normal)):
                raise ValueError('Nonfinite floor record')
            if not all(0 <= tile['tile'][k] < dimensions[k] for k in range(3)):
                raise ValueError('Floor outside tile dimensions')
            floors.append(dict(tile=list(tile['tile']), location=list(location), normal=list(normal),
                               actor=p.name(value['actor']) if value['actor'] else None))
    return floors


def tactical_metadata(p, objects, meshes, grid, warn):
    """Saved base-map floors and a reversible inspection view, not live navigation."""
    if not grid: return None
    for i, export in enumerate(p.exports, 1):
        if p.cls(i) != 'XComWorldDataContainer': continue
        try:
            floors = saved_floor_tiles(p, i, grid['dimensions'])
            if not floors: return None
            # Horizontal half-tile margins enclose cell edges; vertical clearance
            # reveals the room contents while cutting the tall surrounding shell.
            lo=[min(f['location'][k] for f in floors)-grid['size'][k]/2 for k in range(3)]
            hi=[max(f['location'][k] for f in floors)+grid['size'][k]/2 for k in range(3)]
            hi[2]+=160
            view_min=[lo[0],lo[2],lo[1]];view_max=[hi[0],hi[2],hi[1]]
            shell=False
            for obj in objects:
                layers={v.casefold() for v in obj.get('editorLayers',[])}
                if 'periphery' in layers: role='backdrop';shell=True
                elif 'hallway roofs' in layers: role='roof'
                elif layers & {'hiddenwalls','trigger blocks'}: role='helper'
                else:
                    b=meshes[obj['mesh']]['bounds'];m=obj['matrix'];points=[]
                    for x,y,z in product((-1,1),repeat=3):
                        v=[b[0]+x*b[3],b[2]+z*b[5],b[1]+y*b[4]]
                        points.append([sum(m[k*4+j]*v[k] for k in range(3))+m[12+j] for j in range(3)])
                    intersects=all(min(v[k] for v in points)<=view_max[k] and max(v[k] for v in points)>=view_min[k] for k in range(3))
                    role='interior' if intersects else 'backdrop'
                obj['sceneryRole']=role
            return dict(source='original-baked-floor-data',floorTiles=floors,
                        focusBounds=dict(min=view_min,max=view_max),
                        recommendedView='interior' if shell else 'full',
                        notes='Original saved floor surfaces; mission state and runtime navigation are not evaluated')
        except (ValueError,struct.error,IndexError) as error:
            warn(p.name(i),f'Original floor surfaces unavailable: {error}')
            return None
    return None


def volume_bounds(p, actor):
    brush = p.effective(actor,"Brush",0)
    if brush <= 0: return None
    bounds = p.native(brush).unpack("7f")
    scale = [v*p.effective(actor,"DrawScale",1) for v in p.effective(actor,"DrawScale3D",[1,1,1])]
    matrix = transform(p.effective(actor,"Location",[0,0,0]),p.effective(actor,"Rotation",[0,0,0]),scale)
    corners = []
    for signs in product((-1,1),repeat=3):
        v = [bounds[k]+signs[k]*bounds[k+3] for k in range(3)]
        corners.append([sum(matrix[j][k]*v[k] for k in range(3))+matrix[j][3] for j in range(3)])
    return dict(min=[min(v[j] for v in corners) for j in range(3)],
                max=[max(v[j] for v in corners) for j in range(3)])


def prefab_members(p, warn=None):
    """Placed actor -> the prefab instance that placed it (a car's body, glass and light bar share one).

    A cooked PrefabInstance's native data is its ArchetypeToInstanceMap (counted archetype/instance
    reference pairs) and then PI_ObjectMap (counted pairs), checked to fill the payload exactly.
    """
    members = {}
    for index, name in enumerate(p.paths, 1):
        if p.cls(index) != "PrefabInstance" or not name.startswith("TheWorld.PersistentLevel."): continue
        try:
            r = p.native(index)
            pairs = [r.unpack("ii") for _ in range(r.count())]
            r.take(r.count() * 8)
            if r.pos != r.end: raise ValueError("PrefabInstance native data size mismatch")
            for _, instance in pairs:
                if instance > 0: p.name(instance); members[instance] = name.rsplit(".", 1)[-1]
        except ValueError as error:
            if warn: warn(name, error)
    return members


def kismet_references(p, warn=None):
    """Placed actor (export index) -> what of the package's Kismet names it, sorted (private/plans/done/cars-doors-ladders-plan.md,
    3.5): the op that uses it, with the link, where a variable holds it ("SeqAct_ToggleHidden_1 Target"), else the
    sequence object that names it, with the property ("SeqEvent_Touch_0 Originator"). Read from every sequence
    object's own object properties and object arrays (an array of other 4-byte values whose entries all happen to be
    the level's actors would read as references too). URB_Bar's Kismet hides its grounded Skyranger and drop zone
    (XComLevelActor_138 and _6) with a SeqAct_ToggleHidden at the landing."""
    level = p.by_name.get("TheWorld.PersistentLevel")
    def sequence(i): return p.cls(i).startswith("Seq") or p.cls(i) in ("Sequence", "PrefabSequence")
    def placed(i): return 0 < i <= len(p.exports) and p.exports[i-1]["outer"] == level and not sequence(i)
    def text(raw):
        n = struct.unpack_from("<i", raw)[0] if len(raw) >= 4 else 0
        if n > 0: return raw[4:4+n-1].decode("latin-1")
        if n < 0: return raw[4:4-2*n-2].decode("utf-16-le")
        return ""
    named, users = {}, {}
    for i in range(1, len(p.exports)+1):
        if not sequence(i) or p.exports[i-1]["outer"] <= 0: continue
        try:
            props = p.properties(i)[0]
            for (key, slot), item in props.items():
                kind, value = item["kind"], item["value"]
                found = []
                if kind == "ObjectProperty" and isinstance(value, int):
                    found = [value]
                elif kind == "ArrayProperty" and isinstance(value, bytes) and len(value) >= 8:
                    n = struct.unpack_from("<i", value)[0]
                    if n > 0 and len(value) == 4+4*n:
                        found = list(struct.unpack_from(f"<{n}i", value, 4))
                        if not all(placed(v) for v in found): found = []
                prop = key if not slot else f"{key}[{slot}]"
                for v in found:
                    if placed(v): named.setdefault(i, []).append((v, prop))
                if key == "VariableLinks" and kind == "ArrayProperty":
                    for row in p.structs(value):
                        linked = row.get(("LinkedVariables", 0), {}).get("value")
                        desc = row.get(("LinkDesc", 0), {}).get("value")
                        for var in p.refs(linked) if linked else []:
                            users.setdefault(var, []).append(
                                "%s %s" % (p.name(i).rsplit(".", 1)[-1], text(desc) if isinstance(desc, bytes) else ""))
        except Exception as error:
            if warn: warn(p.name(i), f"Kismet references not read: {error}")
    out = {}
    for i, refs in named.items():
        for actor, prop in refs:
            out.setdefault(actor, set()).update(users.get(i) or ["%s %s" % (p.name(i).rsplit(".", 1)[-1], prop)])
    return {actor: sorted(v) for actor, v in out.items()}


def fragment_breaks(p, actors, warn=None):
    """Fracturing actor (export index) -> the pieces its fragment columns break, sorted export indices (export 16;
    private/plans/done/cars-doors-ladders-plan.md, 2.3 and 3.3): every DestructibleActor of its FragmentColumns' DestructibleCache.
    A car's glass names its body and parts (and on Police Station a neighbouring fence or wreck), a wall its doors.
    The compiler joins a destructible that a car's glass names and that stands at the car body's place to the car:
    Police Station's standalone police light bars, which no prefab places with their sedans."""
    out = {}
    for i in actors:
        try:
            named = set()
            for column in p.structs(p.own(i, "FragmentColumns")):
                cache = column.get(("DestructibleCache", 0), {}).get("value")
                for entry in p.structs(cache) if isinstance(cache, bytes) else []:
                    actor = entry.get(("DestructibleActor", 0), {}).get("value")
                    if isinstance(actor, int) and actor > 0: named.add(actor)
            if named: out[i] = sorted(named)
        except Exception as error:
            if warn: warn(p.name(i), f"fragment columns not read: {error}")
    return out


# What the game's damage does to a piece (export 17), from the toughness it names: an XComDestructibleActor_Toughness
# cooked into the map (GameData_Toughness.Toughness_METAL and the like; 23 kinds on the install's 101 maps, from 10
# health for glass to 500 for cars and trucks), with its Health and flags. The game's script
# (<lab>\reference\XComGame-decompiled):
# - XComDestructibleActor (props, and the doors and collectibles built on it): PostBeginPlay sets TotalHealth to the
#   toughness's Health, or with none to the toughness class's default, 3 (Default__XComDestructibleActor_Toughness in
#   LWR's XComGame.upk). ApplyDamageToMe takes hits off it; a toughness with bInvincible takes none.
# - XComFracLevelActor (walls, floors, windows): hits break off the parts in their radius, in native code that reads the
#   toughness (ResetHealth, ApplyDamage). 852 of the install's fracturing pieces name no toughness, ordinary walls and
#   railings among them; what the native code does then wasn't worked out.
# Other classes (XComLevelActor, StaticMeshActor, ladders) have no toughness and no health.
PROP_CLASSES = frozenset({'XComDestructibleActor', 'XComInteractiveLevelActor', 'XComCollectible'})
FRACTURE_CLASSES = frozenset({'XComFracLevelActor', 'XComDecoFracLevelActor'})
DEFAULT_TOUGHNESS_HEALTH = 3
TOUGHNESS_FLAGS = ('bInvincible', 'bFragile', 'bSuccumbsToDamage', 'bImmuneToAreaBurnDamage')


def destruction(p, actor):
    """What the game's damage does to an actor (export 17): None when it has no health, else
    kind: 'prop' (one health for the whole piece) or 'fracture' (it breaks a part at a time);
    toughness: the toughness's name (Toughness_METAL), None when it names none;
    health: the toughness's Health, the class default for a prop that names none (defaulted), None where unknown
    (a fracturing piece with no toughness, a toughness this package only imports);
    flags: the toughness's flags that are set, as the game names them (bFragile, bInvincible, ...)."""
    cls = p.cls(actor)
    try:
        ref = p.effective(actor, 'Toughness', 0) or 0
    except ValueError:
        ref = 0
    if cls in FRACTURE_CLASSES: kind = 'fracture'
    elif cls in PROP_CLASSES or ref: kind = 'prop'
    else: return None
    record = dict(kind=kind, toughness=None, health=None, defaulted=False, flags=[])
    if ref:
        record['toughness'] = p.name(ref).rsplit('.', 1)[-1]
        if ref > 0:   # cooked into the map (an import's values are in another package)
            record['health'] = p.effective(ref, 'Health', DEFAULT_TOUGHNESS_HEALTH)
            record['flags'] = [flag for flag in TOUGHNESS_FLAGS if p.effective(ref, flag, False)]
    elif kind == 'prop':
        record.update(health=DEFAULT_TOUGHNESS_HEALTH, defaulted=True)
    return record


def cursor_volumes(p):
    """The level's cursor volumes (XComCursorVolume): [dict(name, floor: its m_iFloorNumber, box: its world box,
    stair: m_bTreatAsStair)], by floor and height. They tell the cursor which floor a height is (the mouse wheel's
    floors; findings register F-88), apart from any building's floor volumes."""
    out = []
    for index, name in enumerate(p.paths, 1):
        if p.cls(index) != "XComCursorVolume" or not name.startswith("TheWorld.PersistentLevel."):
            continue
        box = volume_bounds(p, index)
        if box:
            out.append(dict(name=name, floor=p.effective(index, "m_iFloorNumber", 0) or 0, box=box,
                            stair=bool(p.effective(index, "m_bTreatAsStair", False))))
    return sorted(out, key=lambda v: (v["floor"], v["box"]["min"][2], v["name"]))


# effects (export 23): the Emitter actors, placed particle systems. A mesh piece carries an effect that stands at its
# own place (Location within EFFECT_SAME units on every axis) when it is the only such piece: the Build moves, copies
# and deletes the effect with it (tools/bake/native_effects.py). An effect at two pieces' place or more is no piece's
# (TempleShip's vortex at the world's origin, the tutorial's police lights on a car body and its glass).
EFFECT_PIECES = ("XComLevelActor", "StaticMeshActor", "XComDestructibleActor", "XComFracLevelActor",
                 "XComInteractiveLevelActor")
EFFECT_SAME = 2.0


def effect_metadata(p):
    """The persistent level's effects (export 23; the user, 13 November 2026: the export carries them for the editor's
    effects to come): [dict(actor (path), location, rotation, scale (DrawScale3D times DrawScale), template (the
    particle system's path or None), listed (in the level's actor list), hidden (bHidden), prefab (its prefab
    instance's name or None), carriedBy (the piece's path, or None), carriedHow ('place': EFFECT_SAME's rule; 'prefab':
    the effect is placed by a prefab instance at whose own place exactly one mesh piece stands, as the fog pod's five
    smoke emitters stand around the pod (F-50; the effects and sounds plan, stage FX6b); None))], by actor."""
    origins = {}

    def at_origin(prefab):
        # the pieces standing at a prefab instance's own place
        if prefab not in origins:
            instance = p.by_name.get("TheWorld.PersistentLevel." + prefab)
            at = p.effective(instance, "Location", [0.0, 0.0, 0.0]) if instance else None
            origins[prefab] = [] if at is None else [n for n, where in pieces if all(abs(where[k] - at[k]) <= EFFECT_SAME for k in range(3))]
        return origins[prefab]
    level = p.by_name.get("TheWorld.PersistentLevel")
    if level is None:
        return []
    listed = level_list(p) or set()
    members = prefab_members(p)
    pieces, effects = [], []
    for index, name in enumerate(p.paths, 1):
        if not name.startswith("TheWorld.PersistentLevel.") or p.exports[index - 1]["outer"] != level:
            continue
        cls = p.cls(index)
        if cls in EFFECT_PIECES and index in listed:
            pieces.append((name, p.effective(index, "Location", [0.0, 0.0, 0.0])))
        elif cls == "Emitter":
            effects.append(index)
    out = []
    for index in effects:
        location = [float(v) for v in p.effective(index, "Location", [0.0, 0.0, 0.0])]
        component = p.effective(index, "ParticleSystemComponent", 0) or 0
        template = p.effective(component, "Template", 0) if component > 0 else 0
        on = [n for n, at in pieces if all(abs(at[k] - location[k]) <= EFFECT_SAME for k in range(3))]
        prefab = str(members[index]).rsplit(".", 1)[-1] if index in members else None
        how = "place" if len(on) == 1 else None
        # no piece at its own place, or several: the one piece at its prefab's place carries it
        if how is None and prefab and index in listed and len(at_origin(prefab)) == 1:
            on, how = at_origin(prefab), "prefab"
        out.append(dict(actor=p.paths[index - 1], location=location,
                        rotation=[int(v) for v in p.effective(index, "Rotation", [0, 0, 0])],
                        scale=[float(v) * float(p.effective(index, "DrawScale", 1.0)) for v in p.effective(index, "DrawScale3D", [1.0, 1.0, 1.0])],
                        template=p.name(template) if template else None, listed=index in listed,
                        hidden=bool(p.effective(index, "bHidden", False)),
                        prefab=prefab, carriedBy=on[0] if how and index in listed else None,
                        carriedHow=how if how and index in listed else None))
    return sorted(out, key=lambda e: e["actor"])


# the landing's prefabs (private/plans/done/clear-map-plan.md, section 4; F-96): a landing is a PrefabInstance of
# the soldier-spawn dropship prefab (its ten actors, roles by archetype as spawns.ARCHETYPES), the grounded Skyranger
# a PrefabInstance of the Skyranger prefab (its mesh, an emitter, a sound and a PointInSpace)
LANDING_TEMPLATE = "DGN_DropShipSoldierSpawn.Prefabs."
SKYRANGER_TEMPLATE = "VEH_Lv1Skyranger_MOD.Prefabs."
LANDING_ROLES = {
    "SoldierSpawns_DrpshipVol_12Arc0": "frame", "SoldierSpawns_DrpshipVol_Arc0": "volume",
    "SoldierSpawns_DrpshipVol_2Arc0": "playerStart", "SoldierSpawns_DrpshipVol_12Arc1": "point",
    "SoldierSpawns_DrpshipVol_Arc1": "soldier1", "SoldierSpawns_DrpshipVol_Arc2": "soldier2",
    "SoldierSpawns_DrpshipVol_Arc3": "soldier3", "SoldierSpawns_DrpshipVol_Arc4": "soldier4",
    "SoldierSpawns_DrpshipVol_Arc5": "soldier5", "SoldierSpawns_DrpshipVol_7Arc0": "soldier6",
}
SKYRANGER_ROLES = {"XComLevelActor": "mesh", "Emitter": "emitter", "PointInSpace": "point"}


def prefab_pairs(p, index):
    """A cooked PrefabInstance's ArchetypeToInstanceMap: [(archetype ref, instance ref)] (prefab_members' reading)."""
    r = p.native(index)
    pairs = [r.unpack("ii") for _ in range(r.count())]
    r.take(r.count() * 8)
    if r.pos != r.end:
        raise ValueError("PrefabInstance native data size mismatch")
    return pairs


def landing_metadata(p, warn=None):
    """The map's own landings (export 22): [dict(prefab, group, actors, skyranger)], in the order the game numbers
    them (their soldier points' tags sorted as text: Group0, Group1, ...). Each actor: dict(role, path, actorClass,
    archetype, location, rotation, tag, savesRotation); `skyranger` the nearest grounded Skyranger's prefab
    (dict(prefab, actors), roles mesh, emitter, sound, point) or None. The landing's actors have no mesh but the
    frame, so the export's pieces don't show them."""
    level = "TheWorld.PersistentLevel."
    landings, skyrangers = [], []
    for index, name in enumerate(p.paths, 1):
        if p.cls(index) != "PrefabInstance" or not name.startswith(level) or name.count(".") != 2:
            continue
        template = p.effective(index, "TemplatePrefab")
        template = p.name(template) if isinstance(template, int) and template else ""
        if not (template.startswith(LANDING_TEMPLATE) or template.startswith(SKYRANGER_TEMPLATE)):
            continue
        try:
            pairs = prefab_pairs(p, index)
        except ValueError as error:
            if warn:
                warn(name, error)
            continue
        actors = []
        for arch, inst in pairs:
            if inst <= 0 or not p.name(inst).startswith(level) or p.name(inst).count(".") != 2:
                continue
            cls, short = p.cls(inst), p.name(arch).split(".")[-1] if arch else ""
            role = LANDING_ROLES.get(short) if template.startswith(LANDING_TEMPLATE) else \
                SKYRANGER_ROLES.get(cls, "sound" if cls.startswith("AmbientSound") else cls)
            if role is None:
                continue
            location = p.own(inst, "Location")
            rotation = p.own(inst, "Rotation")
            tag = p.effective(inst, "Tag")
            actors.append(dict(role=role, path=p.name(inst), actorClass=cls, archetype=p.name(arch) if arch else None,
                               location=[float(v) for v in location] if location else [0.0, 0.0, 0.0],
                               rotation=[int(v) for v in rotation] if rotation else [0, 0, 0],
                               tag=str(tag) if tag else None, savesRotation=rotation is not None))
        record = dict(prefab=name.rsplit(".", 1)[-1], template=template, actors=sorted(actors, key=lambda a: a["role"]))
        (landings if template.startswith(LANDING_TEMPLATE) else skyrangers).append(record)
    for landing in landings:
        tags = sorted({a["tag"] for a in landing["actors"] if a["role"].startswith("soldier") and a["tag"]})
        landing["group"] = tags[0] if len(tags) == 1 else (tags or [None])[0]
        import spawns
        frame = spawns.frame_of(landing)      # a landing with no frame: where the fitted zone's would stand
        near = None
        if frame:
            for sky in skyrangers:
                mesh = next((a for a in sky["actors"] if a["role"] == "mesh"), None)
                if mesh:
                    d = math.hypot(mesh["location"][0] - frame[0][0], mesh["location"][1] - frame[0][1])
                    if near is None or d < near[0]:
                        near = (d, sky)
        landing["skyranger"] = near[1] if near and near[0] < 2500 else None
    return sorted(landings, key=lambda l: (str(l["group"]), l["prefab"]))


def plain_box(p, volume):
    """Whether a volume's brush is a plain box: six polygons (its Polys) whose corners are the eight corners of its
    bounds. A notched or L-shaped floor volume (F-95: 241 of the install's 1,178) has more; moved, it keeps its shape,
    stretched it would stretch its notches, so the Build puts a plain box in its place. None where it does not read."""
    model = p.effective(volume, "Brush", 0) or 0
    polys = next((k for k in p.children.get(model, []) if p.cls(k) == "Polys"), None) if model > 0 else None
    if polys is None: return None
    try:
        _, end = p.properties(model)
        origin, extent = struct.unpack_from("<3f", p.data, end), struct.unpack_from("<3f", p.data, end + 12)
        _, at = p.properties(polys)
        count, most = struct.unpack_from("<ii", p.data, at)
        if not 0 <= count <= most < 100000: return None
        at += 12
        corners = set()
        for _ in range(count):
            at += 48
            n = struct.unpack_from("<i", p.data, at)[0]
            for k in range(n):
                v = struct.unpack_from("<3f", p.data, at + 4 + 12 * k)
                corner = tuple(0 if abs(v[j] - (origin[j] - extent[j])) <= 0.5 else 1 if abs(v[j] - (origin[j] + extent[j])) <= 0.5
                               else None for j in range(3))
                if None in corner: return False
                corners.add(corner)
            at += 4 + 12 * n + 4 + 4 + 8 + 4 + 16 + 36 + 8
        return count == 6 and len(corners) == 8
    except (ValueError, struct.error):
        return None


def building_metadata(p, objects, kismet=None):
    """The level's building volumes: [dict(id: the export index, name: its path, actor: its short name, level, isUfo,
    referencedBy: what of the package's Kismet names it or its floor volumes (kismet_references'), floors: [dict(index,
    volumes: names, plain: whether each is a plain box (plain_box), bottom, top, boxes, members)])]; each object's
    `floors` gets its listings. Export 21 added actor, level, isUfo, referencedBy and plain (the editor's map buildings,
    private/plans/done/map-buildings-editable-plan.md, E0b); the export adds `van` (compiler.van_buildings)."""
    kismet = kismet or {}
    buildings = []
    by_actor = {}
    for obj in objects:
        obj["floors"] = []
        by_actor.setdefault(obj["actor"],[]).append(obj)
    for index,name in enumerate(p.paths,1):
        if p.cls(index) != "XComBuildingVolume" or not name.startswith("TheWorld.PersistentLevel."):
            continue
        floors, named = [], set(kismet.get(index, []))
        for fi,row in enumerate(p.structs(p.effective(index,"Floors"))):
            def value(key, default=None): return row.get((key,0),{}).get("value",default)
            refs = [r for r in p.refs(value("FloorVolumes")) if r > 0] if value("FloorVolumes") else []
            for ref in refs: named.update(kismet.get(ref, []))
            boxes = [b for ref in refs if ref>0 and (b:=volume_bounds(p,ref))]
            top = max(b["max"][2] for b in boxes) if boxes else None
            bottom = min(b["min"][2] for b in boxes) if boxes else None
            members = []
            for entry in p.structs(value("m_aCachedActors")):
                ref = entry.get(("ResidentActor",0),{}).get("value",0)
                if ref<=0: continue
                cutdown = entry.get(("CutdownFloor",0),{}).get("value",0)
                member = dict(actor=p.name(ref),cutdownFloor=cutdown)
                members.append(member)
                for obj in by_actor.get(member["actor"],[]):
                    obj["floors"].append(dict(building=str(index),floor=fi,cutdownFloor=cutdown))
            # boxes: the floor volumes' world boxes, for a copy's floor (the compiler's, as native_copy.floor_at)
            floors.append(dict(index=fi,volumes=[p.name(r) for r in refs],plain=[plain_box(p,r) for r in refs],
                               bottom=bottom,top=top,boxes=boxes,members=members))
        buildings.append(dict(id=str(index),name=name,actor=name.rsplit(".",1)[-1],level=name.split(".")[1],
                              isUfo=bool(p.effective(index,"IsUfo",False)),referencedBy=sorted(named),floors=floors))
    return buildings


# ---------------------------------------------------------------- a mission stream's objects (export 24)
# private/plans/done/mission-types-plan.md, C1: the objects of a mission's stream that its script and the game's
# handlers count on, each with a kind, where it stands, what lists it and the group it moves with. The bomb and its
# power nodes are found as Long War's bomb mutator finds them (XComBombMutator: by archetype, the node's parts and
# the rebuild volumes within 128 units in x and y), so a group is what that mutator would move together.
MISSION_CLASSES = {
    "XComSpawnPoint_Alien": "dropIn", "XComAlienPod": "pod", "PlayerStart": "landing",
    "XComCapturePointActor": "capturePoint", "XComCapturePointVolume": "capturePoint", "XComRadarArrayActor": "radar",
    "XComInteractiveLevelActor": "use", "XComWaveSystem": "wave", "TriggerVolume": "trigger",
    "XComRebuildWorldDataVolume": "rebuild", "XComSquadVisiblePoint": "visible", "XComMeldContainerSpawnPoint": "meld",
}
# XComSpawnPoint's UnitType (XGGameData.EUnitType) -> kind: the covert operative's point, a VIP's (a civilian the
# mission escorts), loot, the landing's soldiers; other types are plain points
UNIT_KINDS = {10: "operative", 6: "vip", 4: "loot", 0: "soldier", 7: "soldier"}
UNIT_TYPES = ("UNIT_TYPE_Soldier", "UNIT_TYPE_Tank", "UNIT_TYPE_Alien", "UNIT_TYPE_AlienInUFO", "UNIT_TYPE_Loot",
              "UNIT_TYPE_Animal", "UNIT_TYPE_Civilian", "UNIT_TYPE_Player", "UNIT_TYPE_MPTeamOne", "UNIT_TYPE_MPTeamTwo",
              "UNIT_TYPE_CovertOperative")
BOMB_PARTS = {("XComLevelActor", "ARC_AlienBomb_XLA"): "bomb", ("XComInteractiveLevelActor", "ARC_IA_HotButtonColumnHigh"): "button",
              ("XComLevelActor", "ARC_largeWaypoint_Floor"): "waypoint", ("Emitter", "ARC_facingWaypoint"): "effect",
              ("Emitter", "ARC_Alien_Bomb_Destroyed"): "effect", ("Emitter", "ARC_Alien_Bomb_Active"): "effect",
              ("Emitter", "ARC_Alien_Bomb_Inactive"): "effect", ("Emitter", "ARC_Alien_Bomb_Exploding"): "effect"}
NODE_PARTS = {("XComInteractiveLevelActor", "ARC_IA_HotButtonColumnLow"): "button",
              ("Emitter", "ARC_Energy_Node_Inactive"): "effect", ("Emitter", "ARC_Energy_Node_Active"): "effect"}
NEAR_2D = 128.0     # XComBombMutator: a node's parts and a rebuild volume belong to it within this, in x and y


def _unit_type(value):
    if isinstance(value, int): return value
    if isinstance(value, str) and value in UNIT_TYPES: return UNIT_TYPES.index(value)
    return 0


def _ref_array(p, raw, keep):
    try: return [r for r in p.refs(raw) if keep(r)]
    except Exception: return []      # noqa: BLE001


def mission_objects(p, warn=None):
    """A mission stream's objects (C1): [dict(actor, actorClass, kind, location, rotation, archetype (its short name),
    tag, unitType (an XComSpawnPoint's), box (a volume's {min, max}), referencedBy (what lists it: the stream's Kismet,
    a wave system's groups, a capture volume), group (the group it moves with, or None), role (its part in the
    group))], by actor. Kinds: MISSION_CLASSES's, an XComSpawnPoint's by its unit type (UNIT_KINDS, else "point"),
    the bomb and a power node ("bomb", "powerNode") and their parts ("part"). Group ids: "bomb",
    "node:<the node's actor>", "capture:<the volume's actor>".
    Export 33 (SP1): each record also carries SpawnReader.record's listed, savesRotation, based, values, other, links
    and uses; a PointInSpace within NEAR_2D of the bomb joins its group (role "point"), as XComBombMutator.FindBomb
    collects it (F-124)."""
    level = p.by_name.get("TheWorld.PersistentLevel")
    if level is None: return []
    reader = SpawnReader(p, warn)
    kismet = reader.kismet
    out, by_index = [], {}

    def record_of(index, kind, unit=None):
        record = reader.record(index, kind)
        record.pop("landing", None)
        record.update(unitType=unit, referencedBy=list(kismet.get(index, [])), group=None, role=None)
        return record

    found = []
    for index, name in enumerate(p.paths, 1):
        if p.exports[index - 1]["outer"] != level: continue
        cls = p.cls(index)
        arch = p.exports[index - 1]["arch"]
        short = p.name(arch).rsplit(".", 1)[-1] if arch else None
        kind = MISSION_CLASSES.get(cls) or ("pod" if cls.startswith("XComAlienPod") else None)
        unit = None
        try:
            if cls == "XComSpawnPoint":
                unit = _unit_type(p.effective(index, "UnitType", 0))
                kind = UNIT_KINDS.get(unit, "point")
            if (cls, short) in BOMB_PARTS:
                kind = "bomb" if BOMB_PARTS[(cls, short)] == "bomb" else kind or "part"
            elif (cls, short) == ("XComLevelActor", "ARC_AlienEnergyNode_XLA"):
                kind = "powerNode"
            elif (cls, short) in NODE_PARTS:
                kind = kind or "part"
            if kind is None: continue
        except Exception as error:      # noqa: BLE001
            if warn: warn(name, f"mission object not read: {error}")
            continue
        found.append((index, kind, unit))
    reader.collect_incoming([i for i, _, _ in found])
    for index, kind, unit in found:
        try:
            record = record_of(index, kind, unit)
        except Exception as error:      # noqa: BLE001
            if warn: warn(p.name(index), f"mission object not read: {error}")
            continue
        out.append(record)
        by_index[index] = record

    def near(a, b): return math.hypot(a[0] - b[0], a[1] - b[1]) <= NEAR_2D

    def nearest(test, centre):
        found = [r for r in out if test(r) and r["group"] is None and near(r["location"], centre)]
        return min(found, key=lambda r: math.hypot(r["location"][0] - centre[0], r["location"][1] - centre[1])) if found else None

    rebuild = lambda r: r["actorClass"] == "XComRebuildWorldDataVolume"  # noqa: E731
    # the bomb: its parts by archetype, its rebuild volume and visible point within reach (one bomb a stream)
    bomb = next((r for r in out if r["kind"] == "bomb"), None)
    if bomb:
        bomb.update(group="bomb", role="bomb")
        for r in out:
            role = BOMB_PARTS.get((r["actorClass"], r["archetype"]))
            if role and r is not bomb: r.update(group="bomb", role=role)
        for test, role in ((rebuild, "rebuild"), (lambda r: r["actorClass"] == "XComSquadVisiblePoint", "visible")):
            hit = nearest(test, bomb["location"])
            if hit: hit.update(group="bomb", role=role)
        # every PointInSpace within reach (FindBomb's ArrPoints; it needs one): the arrow's and camera's helper,
        # 2.5 units across and 204.5 above the bomb on Slaughterhouse's stream
        for index, name in enumerate(p.paths, 1):
            if p.cls(index) != "PointInSpace" or p.exports[index - 1]["outer"] != level or index in by_index: continue
            try:
                at = p.effective(index, "Location", [0.0, 0.0, 0.0])
                if not near(at, bomb["location"]): continue
                helper = record_of(index, "part")
            except Exception as error:      # noqa: BLE001
                if warn: warn(name, f"the bomb's helper point not read: {error}")
                continue
            helper.update(group="bomb", role="point")
            out.append(helper)
            by_index[index] = helper
    # each power node: its button and emitters within reach, and the nearest rebuild volume within reach
    for node in [r for r in out if r["kind"] == "powerNode"]:
        gid = "node:" + node["actor"].rsplit(".", 1)[-1]
        node.update(group=gid, role="node")
        for r in out:
            role = NODE_PARTS.get((r["actorClass"], r["archetype"]))
            if role and r["group"] is None and near(r["location"], node["location"]): r.update(group=gid, role=role)
        hit = nearest(rebuild, node["location"])
        if hit: hit.update(group=gid, role="rebuild")
    # each capture point: the volume, the actor it captures (the volume names it), the capture actors standing in it
    # and the rebuild volume nearest the captured actor
    for index, volume in [(i, r) for i, r in list(by_index.items()) if r["actorClass"] == "XComCapturePointVolume"]:
        gid = "capture:" + volume["actor"].rsplit(".", 1)[-1]
        volume.update(group=gid, role="volume")
        centre = volume["location"]
        try: captured = p.effective(index, "m_kActorBeingCaptured", 0) or 0
        except Exception: captured = 0      # noqa: BLE001
        if captured > 0 and p.exports[captured - 1]["outer"] == level:
            target = by_index.get(captured)
            if target is None:
                target = record_of(captured, "capturePoint")
                out.append(target)
                by_index[captured] = target
            target.update(group=gid, role="captured")
            target["referencedBy"].append(f"{volume['actor'].rsplit('.', 1)[-1]} m_kActorBeingCaptured")
            centre = target["location"]
        box = volume["box"]
        for r in out:
            if r["actorClass"] == "XComCapturePointActor" and r["group"] is None:
                inside = box and all(box["min"][k] - 1 <= r["location"][k] <= box["max"][k] + 1 for k in range(2))
                if inside or near(r["location"], centre): r.update(group=gid, role="actor")
        hit = nearest(rebuild, centre)
        if hit: hit.update(group=gid, role="rebuild")
    # wave systems: the drop-in points their groups name
    for index, record in list(by_index.items()):
        if record["actorClass"] != "XComWaveSystem": continue
        short = record["actor"].rsplit(".", 1)[-1]
        try:
            for s, row in enumerate(p.structs(p.own(index, "m_arrAlienSets"))):
                for w, wave in enumerate(p.structs(row.get(("Waves", 0), {}).get("value"))):
                    for g, group in enumerate(p.structs(wave.get(("Groups", 0), {}).get("value"))):
                        for key in ("SpawnPoints", "OriginationPoints"):
                            for ref in _ref_array(p, group.get((key, 0), {}).get("value"), lambda r: r in by_index):
                                by_index[ref]["referencedBy"].append(f"{short} set {s + 1} wave {w + 1} group {g + 1} {key}")
        except Exception as error:      # noqa: BLE001
            if warn: warn(record["actor"], f"wave groups not read: {error}")
    for r in out: r["referencedBy"] = sorted(set(r["referencedBy"]))
    return sorted(out, key=lambda r: r["actor"])


# ---------------------------------------------------------------- spawn points and who uses them (export 33)
# private/plans/todo/editor-spawns-implementation-plan.md, SP1: the base map's pods, Meld points, drop-in points,
# soldier and other points, starts, alien path nodes and no-spawn volumes, each with its values and where each came
# from, its outgoing links and what uses it. A mission stream's pods, Meld points and drop-ins carry the same through
# mission_objects. Read only.
LEVEL_PATH = "TheWorld.PersistentLevel"
SPAWN_BASE_CLASSES = ("XComMeldContainerSpawnPoint", "XComSpawnPoint", "XComSpawnPoint_Alien", "PlayerStart",
                      "XComAlienPathNode", "XComNoSpawnVolume")
# a family's values: (name in the export, the game's property, the type's zero where no default saves one). Names
# from the game's scripts (<lab>\reference\XComGame-decompiled: XComAlienPod, XComMeldContainerSpawnPoint,
# XComSpawnPoint, XComSpawnPoint_Alien), checked on URB_Bar's pods and Meld points on 18 November 2026.
SPAWN_VALUES = {
    "pod": (("podIndex", "PodIndex", 0), ("commander", "bCommanderPod", False), ("secondary", "bSecondaryPod", False),
            ("use", "bUse", False), ("numAliens", "NumAliens", 0), ("aliensMin", "NumAliens_Min", 0), ("aliensMax", "NumAliens_Max", 0),
            ("podGroup", "m_iPodGroup", 0), ("forceType", "ForceAlienType", False), ("alienType", "AlienType", None),
            ("triggerOnView", "bTriggerOnViewPod", False), ("neverActivate", "bNeverActivate", False)),
    "meld": (("difficulty", "m_eDifficulty", "eMeldContainerDifficulty_Easy"), ("destroyedOnTurn", "m_iDestroyedOnTurn", 0),
             ("spawnGroup", "m_iSpawnGroup", 0), ("countdownWhenSeen", "m_bBeginCountdownWhenSeen", False)),
    "dropIn": (("behaviour", "m_eBehavior", "EAIBehavior_None"), ("forcePlacement", "m_bForcePlacement", False),
               ("kismetOnly", "bKismetSpawnOnly", False), ("seekRadius", "fSeekRadius", 0.0)),
    "point": (("unitType", "UnitType", "UNIT_TYPE_Soldier"),),
    # a no-spawn volume's two switches (export 34: XComNoSpawnVolume, both true in the class's default)
    "noSpawn": (("aliens", "AlienNoSpawnZone", True), ("civilians", "CivilianNoSpawnZone", True)),
}
# enum values shown without their enum's prefix (the writer puts it back: SP6)
ENUM_PREFIX = {"m_eDifficulty": "eMeldContainerDifficulty_", "m_eBehavior": "EAIBehavior_"}
# what an actor saves that is no value or link of its own: placing, drawing, collision and the editor's own
PLUMBING = frozenset({
    "Location", "Rotation", "Tag", "Base", "RelativeLocation", "RelativeRotation", "bDirtyComponents", "bEdShouldSnap",
    "CreationTime", "CollisionComponent", "CylinderComponent", "Components", "LightEnvironment", "PodMesh",
    "CenterpieceMesh", "NavGuid", "DrawScale", "DrawScale3D", "Brush", "BrushComponent", "Layer", "bHidden", "Name",
    "ObjectArchetype", "bCollideActors", "bBlockActors", "bPathColliding", "bHiddenEd", "bHiddenEdGroup", "Sprite",
    "GoodSprite", "BadSprite", "Arrow", "nextNavigationPoint", "PathList", "MaxPathSize", "Cost", "bForceNoStrafing",
    "VisitedWeight", "bestPathWeight", "VolumeTreeNode", "bHasCrossLevelPaths", "NetworkID", "bDestinationOnly",
    "bMustBeReachable", "bBlocked", "bOneWayPath", "bNoAutoConnect", "bNotBased", "bTempNoCollide", "bPathsChanged",
    "bAlreadyVisited", "bHasUnresolvedCrossLevelPaths", "EditorProbeCollision", "PathIndex", "BlockedFlag", "Owner",
})
ROLE_ORIGIN = {"SpawnPoints": "destination", "OriginationPoints": "origin"}


def spawn_family(cls):
    """Which SPAWN_VALUES family a class's values are read by, or None."""
    if cls.startswith("XComAlienPod"): return "pod"
    if cls == "XComMeldContainerSpawnPoint": return "meld"
    if cls == "XComSpawnPoint_Alien": return "dropIn"
    if cls == "XComSpawnPoint": return "point"
    if cls == "XComNoSpawnVolume": return "noSpawn"
    return None


def _short(path):
    return str(path).rsplit(".", 1)[-1]


def _sequence(p, i):
    c = p.cls(i)
    return c.startswith("Seq") or c in ("Sequence", "PrefabSequence")


def _link_text(raw):
    n = struct.unpack_from("<i", raw)[0] if isinstance(raw, (bytes, bytearray)) and len(raw) >= 4 else 0
    if n > 0: return raw[4:4 + n - 1].decode("latin-1")
    if n < 0: return raw[4:4 - 2 * n - 2].decode("utf-16-le")
    return ""


def _ref_values(p, item, keep):
    """The export references an ObjectProperty or an array of plain references holds, kept by `keep` (an array of
    other 4-byte values whose entries all happen to pass would read as references too: kismet_references' rule)."""
    kind, value = item["kind"], item["value"]
    if kind == "ObjectProperty" and isinstance(value, int):
        return [value] if keep(value) else []
    if kind == "ArrayProperty" and isinstance(value, (bytes, bytearray)) and len(value) >= 8:
        n = struct.unpack_from("<i", value)[0]
        if n > 0 and len(value) == 4 + 4 * n:
            found = list(struct.unpack_from(f"<{n}i", value, 4))
            if all(keep(v) for v in found): return found
    return []


def kismet_uses(p, warn=None):
    """Placed actor (export index) -> what of the package's Kismet uses it, structured (export 33): [dict(by (the
    sequence object's short name), byClass, how, link)], how one of
    - 'direct': an action whose variable link holds the actor (URB_PierA_Stream's SeqAct_SpawnAlien_4 SpawnPoints),
      or a sequence object that names it itself (an event's Originator);
    - 'indirect': an object-list action stands between (SeqAct_AccessObjectList "Object List"); `then` names the
      actions its other variables feed;
    - 'variable': a variable holds it and no action reads that variable.
    The walk is kismet_references' (sequence objects' own object properties and plain reference arrays)."""
    level = p.by_name.get(LEVEL_PATH)

    def placed(i): return 0 < i <= len(p.exports) and p.exports[i - 1]["outer"] == level and not _sequence(p, i)
    named, users, links = {}, {}, {}
    for i in range(1, len(p.exports) + 1):
        if not _sequence(p, i) or p.exports[i - 1]["outer"] <= 0: continue
        try:
            for (key, slot), item in p.properties(i)[0].items():
                for v in _ref_values(p, item, placed):
                    named.setdefault(i, []).append((v, key if not slot else f"{key}[{slot}]"))
                if key == "VariableLinks" and item["kind"] == "ArrayProperty":
                    for row in p.structs(item["value"]):
                        linked = row.get(("LinkedVariables", 0), {}).get("value")
                        desc = _link_text(row.get(("LinkDesc", 0), {}).get("value"))
                        for var in p.refs(linked) if linked else []:
                            users.setdefault(var, []).append((i, desc))
                            links.setdefault(i, []).append(var)
        except Exception as error:      # noqa: BLE001
            if warn: warn(p.name(i), f"Kismet uses not read: {error}")
    out = {}
    for i, refs in named.items():
        for actor, prop in refs:
            rows = out.setdefault(actor, [])
            if not users.get(i):
                how = "variable" if p.cls(i).startswith("SeqVar") else "direct"
                rows.append(dict(by=_short(p.name(i)), byClass=p.cls(i), how=how, link=prop))
                continue
            for op, desc in users[i]:
                use = dict(by=_short(p.name(op)), byClass=p.cls(op), how="direct", link=desc)
                if "ObjectList" in p.cls(op):
                    use["how"] = "indirect"
                    use["then"] = sorted({_short(p.name(o)) for v in links.get(op, []) if v != i
                                          for o, _ in users.get(v, []) if o != op})
                rows.append(use)
    for actor, rows in out.items():
        seen, unique = set(), []
        for r in rows:
            key = (r["by"], r["how"], r["link"])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        out[actor] = unique
    return out


def wave_uses(p, warn=None):
    """Placed actor -> its places in the level's wave systems (export 33): [dict(how='wave', by, set, wave, group,
    index, role)], set/wave/group/index counted from 1, role 'destination' (a group's SpawnPoints) or 'origin' (its
    OriginationPoints, paired with a destination by index: XComWaveSystem.SpawnGroup)."""
    level = p.by_name.get(LEVEL_PATH)
    out = {}
    for index, name in enumerate(p.paths, 1):
        if p.cls(index) != "XComWaveSystem" or p.exports[index - 1]["outer"] != level: continue
        try:
            for s, row in enumerate(p.structs(p.own(index, "m_arrAlienSets"))):
                for w, wave in enumerate(p.structs(row.get(("Waves", 0), {}).get("value"))):
                    for g, group in enumerate(p.structs(wave.get(("Groups", 0), {}).get("value"))):
                        for key, role in ROLE_ORIGIN.items():
                            raw = group.get((key, 0), {}).get("value")
                            for k, ref in enumerate(_ref_array(p, raw, lambda r: r > 0) if raw else []):
                                out.setdefault(ref, []).append(dict(how="wave", by=_short(name), set=s + 1, wave=w + 1,
                                                                    group=g + 1, index=k + 1, role=role))
        except Exception as error:      # noqa: BLE001
            if warn: warn(name, f"wave groups not read: {error}")
    return out


def pod_events(p, defaults=None, warn=None):
    """Pod index -> the package's SeqEvent_OnRevealPod events that fire for it (XComAlienPodManager: an event fires
    for the pod whose PodIndex is its thisPodID; one that saves none has the class's, 0): [dict(by, podId,
    staticOnly)]."""
    out = {}
    for i, name in enumerate(p.paths, 1):
        if p.cls(i) != "SeqEvent_OnRevealPod": continue
        try:
            if defaults is not None:
                pod, _ = defaults.value(i, "thisPodID", 0)
                static, _ = defaults.value(i, "staticMapPodsOnly", False)
            else:
                pod, static = p.own(i, "thisPodID", 0), p.own(i, "staticMapPodsOnly", False)
            out.setdefault(int(pod or 0), []).append(dict(by=_short(name), podId=int(pod or 0), staticOnly=bool(static)))
        except Exception as error:      # noqa: BLE001
            if warn: warn(name, f"pod event not read: {error}")
    return out


class SpawnReader:
    """What a package says of its spawn points, read once: the level's list, the class defaults, the Kismet's uses,
    the wave systems', the pod events, and typed references between placed actors (export 33)."""

    def __init__(self, p, warn=None, defaults=None):
        self.p, self.warn = p, warn
        self.level = p.by_name.get(LEVEL_PATH)
        self.listed = level_list(p)
        if defaults is None:
            try:
                import effects_metadata
                defaults = effects_metadata.Defaults(p)
            except Exception:       # noqa: BLE001
                defaults = None
        self.defaults = defaults
        self.kismet = kismet_references(p, warn)
        self.kismet_uses = kismet_uses(p, warn)
        self.waves = wave_uses(p, warn)
        self.events = pod_events(p, defaults, warn)
        self.incoming = {}

    def placed(self, i):
        p = self.p
        return 0 < i <= len(p.exports) and p.exports[i - 1]["outer"] == self.level and not _sequence(p, i)

    def collect_incoming(self, wanted):
        """Typed references to the actors `wanted` from every placed actor's own saved properties: {target: [dict(by,
        byClass, property)]}. A wave system's groups are read by wave_uses, not here."""
        p, wanted = self.p, set(wanted)
        for i, path in enumerate(p.paths, 1):
            if not self.placed(i) or p.cls(i) == "XComWaveSystem": continue
            try:
                props = p.properties(i)[0]
            except Exception:       # noqa: BLE001
                continue
            for (key, slot), item in props.items():
                if key in PLUMBING: continue
                for v in _ref_values(p, item, lambda r: r in wanted or self.placed(r)):
                    if v in wanted and v != i:
                        self.incoming.setdefault(v, []).append(dict(by=_short(path), byClass=p.cls(i), property=key))

    def value(self, index, key, zero):
        """(value, from): from 'saved' (the actor's own), 'archetype', 'class' (the class's default, or the type's
        zero where none saves it) or 'unknown'."""
        if self.defaults is None:
            item = self.p.properties(index)[0].get((key, 0))
            return (item["value"], "saved") if item is not None else (zero, "unknown")
        value, source = self.defaults.value(index, key, zero)
        return value, {"actor": "saved", "table": "class", "unresolved": "unknown"}.get(source, source)

    def values(self, index, family):
        out = {}
        for name, key, zero in SPAWN_VALUES.get(family, ()):
            value, source = self.value(index, key, zero)
            if isinstance(value, str) and key in ENUM_PREFIX and value.startswith(ENUM_PREFIX[key]):
                value = value[len(ENUM_PREFIX[key]):]
            if isinstance(value, (bytes, bytearray)): value = value.hex()
            out[name] = {"value": value, "from": source}
        return out

    def links(self, index):
        """The actor's outgoing typed references to placed actors (a pod's PathNodes, ConstrainedMovementVolume,
        ContingentPods, TriggeredPods, CoverGoToPoints; a drop-in's kSeekActor): [dict(property, actor)]."""
        p, out = self.p, []
        for (key, slot), item in p.properties(index)[0].items():
            if key in PLUMBING: continue
            for v in _ref_values(p, item, lambda r: r != 0):
                if self.placed(v): out.append(dict(property=key, actor=p.name(v)))
        return out

    def uses(self, index, pod_index=None):
        """[dict(by, how, ...)]: the Kismet's (kismet_uses), the wave systems' (wave_uses), the pod events for its
        index, and typed references from other actors (how 'typed', with the property)."""
        out = [dict(u) for u in self.kismet_uses.get(index, [])]
        out += [dict(u) for u in self.waves.get(index, [])]
        if pod_index is not None:
            out += [dict(how="event", **u) for u in self.events.get(pod_index, [])]
        out += [dict(how="typed", **u) for u in self.incoming.get(index, [])]
        return out

    def record(self, index, kind, landing=None):
        """The record an actor gets (export 33), with `unread` (why) where its values could not be read."""
        p = self.p
        name, cls = p.name(index), p.cls(index)
        arch = p.exports[index - 1]["arch"]
        own = p.properties(index)[0]
        location = [float(v) for v in p.effective(index, "Location", [0.0, 0.0, 0.0])]
        rotation = [int(v) for v in p.effective(index, "Rotation", [0, 0, 0])]
        tag = p.effective(index, "Tag")
        base = own.get(("Base", 0))
        based = None
        if base is not None and isinstance(base["value"], int) and base["value"] > 0:
            rel = own.get(("RelativeLocation", 0))
            relrot = own.get(("RelativeRotation", 0))
            based = dict(base=p.name(base["value"]), relativeLocation=[float(v) for v in rel["value"]] if rel else None,
                         relativeRotation=[int(v) for v in relrot["value"]] if relrot else None)
        family = spawn_family(cls)
        record = dict(actor=name, actorClass=cls, kind=kind, location=location, rotation=rotation,
                      savesRotation=("Rotation", 0) in own, based=based,
                      listed=None if self.listed is None else index in self.listed,
                      archetype=_short(p.name(arch)) if arch else None, tag=str(tag) if tag else None,
                      box=volume_bounds(p, index) if cls.endswith("Volume") else None,
                      values={}, other=[], links=[], uses=[], landing=landing)
        try:
            record["values"] = self.values(index, family) if family else {}
            known = {key for _, key, _ in SPAWN_VALUES.get(family, ())}
            record["links"] = self.links(index)
            linked = {lk["property"] for lk in record["links"]}
            record["other"] = sorted({k for k, _ in own if k not in PLUMBING and k not in known and k not in linked}) if family else []
            pod = record["values"].get("podIndex", {}).get("value") if family == "pod" else None
            record["uses"] = self.uses(index, pod if isinstance(pod, int) else None)
        except Exception as error:      # noqa: BLE001
            record["unread"] = str(error)
            if self.warn: self.warn(name, f"spawn values not read: {error}")
        return record


def spawn_kind(p, index, cls):
    """A base record's kind: pod, meld, dropIn, start, pathNode, noSpawn, or an XComSpawnPoint's by its unit type
    (UNIT_KINDS: soldier, operative, vip, loot; else point). None for a class that is no spawn point."""
    if cls.startswith("XComAlienPod"): return "pod"
    if cls == "XComSpawnPoint":
        return UNIT_KINDS.get(_unit_type(p.effective(index, "UnitType", 0)), "point")
    return {"XComMeldContainerSpawnPoint": "meld", "XComSpawnPoint_Alien": "dropIn", "PlayerStart": "start",
            "XComAlienPathNode": "pathNode", "XComNoSpawnVolume": "noSpawn"}.get(cls)


def spawn_metadata(p, landings=None, warn=None, reader=None):
    """The base level's spawn points (export 33; SP1): [dict(actor, actorClass, kind, location, rotation, savesRotation,
    based (a saved Base: dict(base, relativeLocation, relativeRotation)), listed (in the level's actor list; None where
    the list doesn't read), archetype, tag, box (a volume's), values ({name: dict(value, from)}), other (saved
    properties the reader doesn't know, by name), links (outgoing: [dict(property, actor)]), uses (incoming:
    kismet_uses, wave_uses, pod events, typed), referencedBy (the strings the page shows), landing (the landing
    prefab's name for the actors landing_metadata owns, so the page draws the zone and no marker), unitType (an
    XComSpawnPoint's), unread (where its values could not be read))], by actor. `landings`: landing_metadata's."""
    level = p.by_name.get(LEVEL_PATH)
    if level is None: return []
    reader = reader or SpawnReader(p, warn)
    owned = {a["path"]: l["prefab"] for l in (landings or []) for a in l.get("actors", [])}
    found = []
    for index, name in enumerate(p.paths, 1):
        if p.exports[index - 1]["outer"] != level: continue
        cls = p.cls(index)
        if not (cls.startswith("XComAlienPod") or cls in SPAWN_BASE_CLASSES): continue
        try:
            kind = spawn_kind(p, index, cls)
        except Exception as error:      # noqa: BLE001
            kind = "point" if cls == "XComSpawnPoint" else None
            if warn: warn(name, f"spawn point kind not read: {error}")
        if kind: found.append((index, kind))
    reader.collect_incoming([i for i, _ in found])
    out = []
    for index, kind in found:
        try:
            record = reader.record(index, kind, owned.get(p.name(index)))
        except Exception as error:      # noqa: BLE001
            record = dict(actor=p.name(index), actorClass=p.cls(index), kind=kind, location=[0.0, 0.0, 0.0],
                          rotation=[0, 0, 0], values={}, other=[], links=[], uses=[], landing=owned.get(p.name(index)),
                          unread=str(error))
            if warn: warn(p.name(index), f"spawn point not read: {error}")
        if p.cls(index) == "XComSpawnPoint":
            try: record["unitType"] = _unit_type(p.effective(index, "UnitType", 0))
            except Exception: record["unitType"] = None      # noqa: BLE001
        refs = list(reader.kismet.get(index, []))
        refs += ["%s set %d wave %d group %d %s" % (u["by"], u["set"], u["wave"], u["group"],
                                                     "SpawnPoints" if u["role"] == "destination" else "OriginationPoints")
                 for u in reader.waves.get(index, [])]
        refs += ["%s %s" % (u["by"], u["property"]) for u in reader.incoming.get(index, [])]
        record["referencedBy"] = sorted(set(refs))
        out.append(record)
    return sorted(out, key=lambda r: r["actor"])


BOMB_DONOR = "URB_Slaughterhouse_Stream"


def donor_objects(path, warn=None):
    """The bomb donor's mission objects (export 33, review item 7): {"Special/Bomb": dict(stream, package,
    missionObjects)} read from the install's URB_Slaughterhouse_Stream (`path`, export.stream_package's), without its
    pieces; {} where the package isn't there or doesn't read."""
    from pathlib import Path
    from package import Package
    if path is None or not Path(path).is_file(): return {}
    path = Path(path)
    try:
        objects = mission_objects(Package(path), warn)
    except Exception as error:      # noqa: BLE001
        if warn: warn(BOMB_DONOR, f"bomb donor not read: {error}")
        return {}
    return {"Special/Bomb": dict(stream=BOMB_DONOR, package=path.name, missionObjects=objects)}
