"""Cover blocks and invisible floors: hidden pieces that give cover or a floor to stand on, made in the variant map by
the editor's Build from a recipe.

Long War Rebalance's patch maps add cover where a map lacks it with hidden pieces: an XComLevelActor drawing a plain
box mesh, hidden in the game (bHidden), its collision on (its class default's), and its CoverForceFlag set to high or
low cover (URB_PoliceStation's patch has six: CoverPatch.highcover, Cover2x4...; tools/viewer/README.md, "What the
missions stream"). A cover block is that piece, made the way light_factory.py makes a recipe spot light: from
construction rules and the destination package alone, so it builds on any install, plain Enemy Within included. No
LWR file is read; LWR's helpers are only what the recipe was checked against (tests/test_cover_blocks.py).

For each block:
- a box StaticMesh of the block's own size (box_mesh), under a forced-export package of our own (PACKAGE), shared by
  the blocks of one size: 24 vertices (four to a face), 12 triangles, one section, the triangles' collision tree,
  laid out as the cooked boxes are: LWR's CoverPatch meshes and the game's own FX_Utilities boxes share every field,
  the collision tree's nodes included (any half of a box's faces spans the whole box, so each node is the whole box).
  Its simple collision is an RB_BodySetup of its own (body_setup_properties), as LWR's boxes, the game's FX_Utilities
  boxes and nearly every mesh of the game's maps have one: a convex hull of the box's eight corners in AggGeom, laid
  out as the game's FX_Utilities.Box_96x96x96 has it (RECIPES 'bodySetup'), and no pre-cooked data (none of the maps'
  own have any: the game cooks it as the map loads). The first blocks played had no BodySetup at all and gave no cover
  nor stopped a unit, and neither did a second build with the simple-collision flags off: the game's tile rebuild
  skips a level actor whose mesh has no BodySetup before it tests any collision (F-80, research/native-code-notes.md);
- the actor (RECIPES: an XComLevelActor with its StaticMeshComponent and XComFloorComponent, the properties LWR's
  helpers save: hidden, not a destination and not climbable onto, the cover forced high or low, and for low cover a
  VisibilityBlockingData that lets units see over it), at the block's corner and rotation, with fresh name numbers and
  net indices;
- its tiles as a copy gets them (native_copy.add_tiles_box: seeds where the map's baked tiles have nothing, and a
  rebuild volume), so the game's tile rebuild gives cover there.

An invisible floor (kind 'floor', EXP-32) is the same piece made walkable: a plate two units thin under its location
(its top), not hidden from the floor trace, a valid destination, no cover forced, and ignored for cover
(bIgnoreForCover, as the game's own hidden ladder helpers save it): the tile rebuild gives a tile cover where a
sideways trace from 52 over its floor hits a cover actor, so a plate standing a step over its downhill neighbour gave
that tile half cover (EXP-32 run 1); that trace skips an actor ignored for cover, and the floor trace doesn't look at
the flag (research/native-code-notes.md). It is made of one actor per tile cell
(cells), so no plate is 4 tiles across: the tile rebuild's occupancy test skips a level actor whose mesh is under 4
units thick only while it is under 384 units across (research/native-code-notes.md), and a floor must not fill the
tiles it carries.

A cover block in a group that breaks together (its `breakGroup`, the group's number) is made as a hidden destructible
prop instead (BREAKING), on the same box mesh and in the same tiles: when a breakable piece of its group is destroyed
the game destroys it too, and its cover and collision go (native_copy.link_children lists it in those pieces'
AffectedChildren). It takes no damage of its own.

A blocker (kind 'block', recipe version 2, Discord feedback S6) is the high block's hidden box with no cover: its tiles
are occupied, so units can't walk into it, but it is ignored for cover and forces none, so no unit beside it gets
cover, and units see past it.

A block is the compiler's: dict(name, kind 'high' | 'low' | 'floor' | 'block', version (its recipe's, 1 when absent),
location (its corner, on the floor; a floor's top), rotation [pitch, yaw, roll], size [x, y] (units along its own axes),
heights [z0, z1] (below and above its location), box (its world box), and breakGroup for a block that breaks with its
group).
The mesh spans x 0..size[0], y 0..size[1], z z0..z1 in the actor's frame.

The relight leaves the blocks out: a hidden actor casts no baked shadow (shadows.py), and its mesh component has no
lightmap (an empty LODData).
"""
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'upk'))
sys.path.insert(0, str(HERE))
import light_factory  # noqa: E402

PACKAGE = 'XComMapEdCover'
LEVEL = 'TheWorld.PersistentLevel'
FORCED_EXPORT = 0x1
UNIT = struct.unpack('<f', struct.pack('<f', 0.99999994))[0]     # the unit length the cooked hulls save

# Version 1, checked on 10 November 2026 against LWR's hidden cover helpers in patch_policestation.upk (its
# XComLevelActor_0, high cover on CoverPatch.highcover, and XComLevelActor_2, low cover on CoverPatch.Cover2x4): the
# same classes, archetypes, export flags, preambles, properties and their order (tests/test_cover_blocks.py). The mesh
# component's native data is the map's own, not the patch's: an empty LODData, then the two empty mesh-swap LOD
# records and their two meshes that Enemy Within's maps (licensee 64) save after it (lighting_records.component_record).
# The patch, cooked by the UDK (licensee 0), saves the LODData alone; built that way in a map, the game read 42 bytes
# past the component and stopped as the map loaded ("Bad import index", F-79). Imports and properties are written as light_factory's recipes are; two
# more kinds: 'enum' ([enum, value]: a ByteProperty saving a name) and 'objects' (an object array).
RECIPES = {
    1: {
        'imports': [
            ['XComGame', 'Core', 'Package'],        # the cooked maps hold it as an export (resolved by _imports)
            ['Engine', 'Core', 'Package'],
            ['XComGame.XComLevelActor', 'Core', 'Class'],
            ['XComGame.XComFloorComponent', 'Core', 'Class'],
            ['Engine.StaticMeshComponent', 'Core', 'Class'],
            ['Engine.StaticMesh', 'Core', 'Class'],
            ['Engine.RB_BodySetup', 'Core', 'Class'],
            ['XComGame.Default__XComLevelActor', 'XComGame', 'XComLevelActor'],
            ['XComGame.Default__XComLevelActor.StaticMeshComponent0', 'Engine', 'StaticMeshComponent'],
            ['XComGame.Default__XComLevelActor.FloorComponent0', 'XComGame', 'XComFloorComponent'],
        ],
        'actor': {
            'class': 'XComGame.XComLevelActor', 'name': 'XComLevelActor', 'archetype': None,
            'flags': 0x0207000100000000,        # RF_HasStack, the three load flags, RF_Transactional
            # light_factory's state frame; the word it calls latentAction is cooker noise in the placed actors
            # (URB_Bar's level actors save 44 values there, LWR's two helpers 0x6D and 0x76): 0, as the spot recipe
            'preamble': {'kind': 'stateFrame', 'probeMask': 0xFFFFFFFF, 'latentAction': 0, 'stateStack': 0,
                         'codeOffset': -1},
            'properties': [
                ['FloorComponent', 'object', '$floor'],
                ['VisibilityBlockingData', 'struct VisibilityBlocking', '$visibility'],     # low cover only
                ['bCanClimbOnto', 'bool', '$climb'],                # blocks: False; a floor: the default
                ['bIsValidDestination', 'bool', '$destination'],    # blocks: False; a floor: the default
                ['bIgnoreForCover', 'bool', '$ignore'],             # blocks: the default; a floor: True
                ['CoverForceFlag', 'enum', ['ECoverForceFlag', '$force']],     # a floor: none
                ['StaticMeshComponent', 'object', '$mesh'],
                ['Location', 'Vector', '$location'],
                ['Rotation', 'Rotator', '$rotation'],
                ['bHidden', 'bool', True],
                ['Tag', 'name', 'XComLevelActor'],
                ['CollisionComponent', 'object', '$mesh'],
            ],
        },
        'mesh': {
            'class': 'Engine.StaticMeshComponent', 'name': 'StaticMeshComponent',
            'archetype': 'XComGame.Default__XComLevelActor.StaticMeshComponent0',
            'flags': 0x0007000100000000,
            'preamble': {'kind': 'component', 'templateOwnerClass': 0},
            'properties': [
                ['StaticMesh', 'object', '$staticMesh'],
                ['ReplacementPrimitive', 'object', 0],
                ['LightingChannels', 'struct LightingChannelContainer', [['bInitialized', 'bool', True],
                                                                         ['Static', 'bool', True]]],
            ],
            # an empty LODData (a count: no lightmap, no shadow maps), then EW's two mesh-swap LOD records, empty (17
            # bytes each: two shadow-map arrays, lightmap type 0, no vertex colours, no light GUIDs), and their two
            # meshes, none: 46 bytes, as the map's own components with no LOD save them
            'tail': '00' * 46,
        },
        # the box StaticMesh's own properties: its BodySetup (saved also in its native data), as LWR's boxes save it;
        # the simple-collision flags at their defaults (on), as theirs and the game's boxes
        'box': {
            'properties': [
                ['BodySetup', 'object', '$bodySetup'],
            ],
        },
        # each box's RB_BodySetup, under its mesh: the map's own RB_BodySetups' entry (flags 0x0007000000000000), the
        # version every one of them saves, and one convex element laid out as the game's FX_Utilities.Box_96x96x96 has
        # its hull (URB_PoliceStation): its corners as 0 (the box's low end) or 1 (its high end) on each axis, the
        # triangles over them, the edge and face directions and the face planes' normals as the game saves them; the
        # planes' distances, the permuted corners and the element's box follow from the box (body_setup_properties)
        'bodySetup': {
            'class': 'Engine.RB_BodySetup', 'name': 'RB_BodySetup', 'number': 1,
            'version': 34079889,
            'corners': [[1, 1, 0], [1, 0, 0], [0, 0, 0], [1, 1, 1], [1, 0, 1], [0, 1, 0], [0, 1, 1], [0, 0, 1]],
            'triangles': [0, 2, 1, 0, 5, 2, 1, 3, 0, 1, 4, 3, 7, 1, 2, 7, 4, 1, 6, 0, 3, 6, 5, 0, 6, 2, 5, 6, 7, 2, 7, 3,
                          4, 7, 6, 3],
            'edges': [[-UNIT, 0.0, 0.0], [0.0, -UNIT, 0.0], [0.0, 0.0, UNIT]],
            'faceNormals': [[0.0, -0.0, -UNIT], [UNIT, 0.0, 0.0], [0.0, -UNIT, 0.0]],
            'planeNormals': [[0.0, -0.0, -UNIT], [UNIT, 0.0, 0.0], [0.0, -UNIT, 0.0], [-0.0, UNIT, 0.0],
                             [-UNIT, 0.0, -0.0], [0.0, 0.0, UNIT]],
        },
        'floor': {
            'class': 'XComGame.XComFloorComponent', 'name': 'XComFloorComponent',
            'archetype': 'XComGame.Default__XComLevelActor.FloorComponent0',
            'flags': 0x0007000100000000,
            'preamble': {'kind': 'component', 'templateOwnerClass': 0},
            'properties': [['OwnerMeshComponents', 'objects', ['$mesh']]],
        },
        # what each kind saves; 'cell': a kind made of one actor per cell of about that size (cells), each at its
        # cell's centre on a mesh of one cell centred on it, or None for one actor at the corner on the whole box
        'kinds': {
            'high': {'force': 'CoverForce_High', 'visibility': None, 'climb': False, 'destination': False, 'ignore': None,
                     'cell': None},
            'low': {'force': 'CoverForce_Low', 'visibility': [['bBlockUnitVisibility', 'bool', False]], 'climb': False,
                    'destination': False, 'ignore': None, 'cell': None},
            'floor': {'force': None, 'visibility': None, 'climb': None, 'destination': None, 'ignore': True, 'cell': 96.0},
        },
    },
}


# A block that breaks with its group (the block's `breakGroup`; private/plans/done/breaking-cover-blocks-plan.md):
# the same hidden piece made as a destructible prop, so the game's own link between pieces that break together
# (AffectedChildren, native_copy.link_children) can name it. XComDestructibleActor extends XComLevelActor, so the
# cover properties are recipe 1's. What differs, each by a recipe of the same version number:
# - the actor's class, and no floor component (the game's placed props save none);
# - DestroyedEvents: one event, an XComDestructibleActor_Action_Hide under the actor, at time 0. A destroyed prop
#   keeps its mesh and collision unless an event takes them; Hide's Activate calls the actor's SetStaticMesh(none),
#   which turns its collision off and hands its old bounds to the world data, then GotoState('Dead') (the exe at
#   0x99EF00 and 0xAD86E0). URB_Bar has 116 placed props with that one event;
# - a toughness of its own under the actor with bInvincible: ApplyDamageToMe returns at once, so the block takes no
#   damage itself and goes only with its group (SyncChildStates moves it by GotoState);
# - bDestroysSurroundingArea False: a prop that breaks damages what stands at its place (DamageSurroundingArea).
# Laid out as URB_Bar's placed props save theirs (XComDestructibleActor_223: the state frame, the events array of one
# struct holding Action alone, the action's and a toughness's data a net index and their properties). The game's
# props all have an archetype; this one has none, as recipe 1's level actor (the class default object).
# One more property kind: 'events' (an array of DestructibleActorEvent structs, each saving its Action alone).
BREAKING = {
    1: {
        'imports': [
            ['XComGame', 'Core', 'Package'],
            ['Engine', 'Core', 'Package'],
            ['XComGame.XComDestructibleActor', 'Core', 'Class'],
            ['XComGame.XComDestructibleActor_Action_Hide', 'Core', 'Class'],
            ['XComGame.XComDestructibleActor_Toughness', 'Core', 'Class'],
            ['Engine.StaticMeshComponent', 'Core', 'Class'],
            ['XComGame.Default__XComDestructibleActor', 'XComGame', 'XComDestructibleActor'],
            ['XComGame.Default__XComDestructibleActor.StaticMeshComponent0', 'Engine', 'StaticMeshComponent'],
        ],
        'actor': {
            'class': 'XComGame.XComDestructibleActor', 'name': 'XComDestructibleActor', 'archetype': None,
            'flags': 0x0207000100000000,
            'preamble': {'kind': 'stateFrame', 'probeMask': 0xFFFFFFFF, 'latentAction': 0, 'stateStack': 0,
                         'codeOffset': -1},
            'properties': [
                ['DestroyedEvents', 'events', ['$action']],
                ['bDestroysSurroundingArea', 'bool', False],
                ['Toughness', 'object', '$toughness'],
                ['VisibilityBlockingData', 'struct VisibilityBlocking', '$visibility'],     # low cover only
                ['bIsValidDestination', 'bool', False],
                ['CoverForceFlag', 'enum', ['ECoverForceFlag', '$force']],
                ['StaticMeshComponent', 'object', '$mesh'],
                ['Location', 'Vector', '$location'],
                ['Rotation', 'Rotator', '$rotation'],
                ['bHidden', 'bool', True],
                ['Tag', 'name', 'XComLevelActor'],
                ['CollisionComponent', 'object', '$mesh'],
            ],
        },
        # recipe 1's mesh component under the prop's own template
        'mesh': {
            'class': 'Engine.StaticMeshComponent', 'name': 'StaticMeshComponent',
            'archetype': 'XComGame.Default__XComDestructibleActor.StaticMeshComponent0',
            'flags': 0x0007000100000000,
            'preamble': {'kind': 'component', 'templateOwnerClass': 0},
            'properties': [
                ['StaticMesh', 'object', '$staticMesh'],
                ['ReplacementPrimitive', 'object', 0],
                ['LightingChannels', 'struct LightingChannelContainer', [['bInitialized', 'bool', True],
                                                                         ['Static', 'bool', True]]],
            ],
            'tail': '00' * 46,
        },
        # plain objects under the actor: their data is a net index, then their properties
        'action': {
            'class': 'XComGame.XComDestructibleActor_Action_Hide', 'name': 'XComDestructibleActor_Action_Hide',
            'archetype': None, 'flags': 0x0007000100000000, 'preamble': {'kind': 'object'},
            'properties': [],
        },
        'toughness': {
            'class': 'XComGame.XComDestructibleActor_Toughness', 'name': 'XComDestructibleActor_Toughness',
            'archetype': None, 'flags': 0x0007000100000000, 'preamble': {'kind': 'object'},
            'properties': [['bInvincible', 'bool', True]],
        },
        # the kinds that can break with a group, and what each saves (recipe 1's values)
        'kinds': {
            'high': {'force': 'CoverForce_High', 'visibility': None},
            'low': {'force': 'CoverForce_Low', 'visibility': [['bBlockUnitVisibility', 'bool', False]]},
        },
    },
}


# Version 2 (15 November 2026, Discord feedback S6): version 1 and one kind more, 'block', a blocker: the high block's
# hidden box that blocks movement but gives no cover. The tile rebuild's occupancy test reads neither CoverForceFlag
# nor bIgnoreForCover (it wants the cover interface's ConsiderForOccupancy, bAlwaysConsiderForCover, true by default),
# so its tiles are still occupied; the cover trace skips an actor ignored for cover (F-82), so no unit beside it gets
# cover (research/native-code-notes.md). It forces no cover, isn't climbed onto nor a destination (the blocks' False),
# and lets units see past it (low cover's VisibilityBlockingData). Everything else is version 1's, byte for byte: the
# kinds version 1 has make the same exports by either version. Its breaking block saves bIgnoreForCover too, where
# the level actor saves it (between bIsValidDestination and CoverForceFlag), and only for the blocker.
BLOCKER = {'force': None, 'visibility': [['bBlockUnitVisibility', 'bool', False]], 'climb': False, 'destination': False,
           'ignore': True, 'cell': None}
RECIPES[2] = json.loads(json.dumps(RECIPES[1]))
RECIPES[2]['kinds']['block'] = dict(BLOCKER)
BREAKING[2] = json.loads(json.dumps(BREAKING[1]))
_props = BREAKING[2]['actor']['properties']
_props.insert(next(i for i, p in enumerate(_props) if p[0] == 'CoverForceFlag'), ['bIgnoreForCover', 'bool', '$ignore'])
BREAKING[2]['kinds']['block'] = {'force': None, 'visibility': BLOCKER['visibility'], 'ignore': True}
del _props


def recipe(version):
    if isinstance(version, bool) or not isinstance(version, int) or version not in RECIPES:
        raise ValueError(f'unknown cover block recipe version {version!r} (this factory knows {sorted(RECIPES)})')
    return RECIPES[version]


def recipe_digest(version):
    """SHA-256 of a recipe's canonical JSON (the tests pin it: a version once checked stays as it is)."""
    text = json.dumps(recipe(version), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def breaking_recipe(version):
    """The recipe of a block that breaks with its group, of the same version number as the block's own."""
    recipe(version)
    if version not in BREAKING:
        raise ValueError(f'cover block recipe version {version!r} has no block that breaks with a group')
    return BREAKING[version]


# ---------------------------------------------------------------- the box mesh
# the collision tree of a 12-triangle box: four compact nodes, each the whole box (as every cooked box has them)
KDOP_NODES = bytes.fromhex('808080808080' * 3 + '000000000000')
# a face: its normal's axis and sign; its corners go round (u, v) = the other two axes in order
FACES = ((0, -1), (0, 1), (1, -1), (1, 1), (2, -1), (2, 1))


def _sub(a, b):
    return [x - y for x, y in zip(a, b)]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _packed(v, w):
    """A unit vector as the vertex buffer packs it: each axis a byte (-1 0, 0 127, 1 255), then `w`."""
    return bytes(int(x * 127.5 + 127.5) for x in v) + bytes([w])


def box_geometry(lo, hi):
    """(vertices [(position, normal, tangent, uv)], triangles [(a, b, c)]) of the box lo..hi: four vertices to a face,
    each face two triangles wound as UE3's front faces are (cross(b - a, c - a) against the outward normal, as the
    cooked boxes have them)."""
    verts, tris = [], []
    for axis, sign in FACES:
        u, v = [a for a in range(3) if a != axis]
        n, t = [0, 0, 0], [0, 0, 0]
        n[axis], t[u] = sign, 1
        base = len(verts)
        for cu, cv in ((0, 0), (1, 0), (1, 1), (0, 1)):
            p = [0.0, 0.0, 0.0]
            p[axis] = float(hi[axis] if sign > 0 else lo[axis])
            p[u], p[v] = float((lo[u], hi[u])[cu]), float((lo[v], hi[v])[cv])
            verts.append((p, n, t, (float(cu), float(1 - cv))))
        a, b, c, d = range(base, base + 4)
        front = sum(x * y for x, y in zip(_cross(_sub(verts[b][0], verts[a][0]), _sub(verts[c][0], verts[a][0])), n))
        tris += [(a, c, b), (a, d, c)] if front > 0 else [(a, b, c), (a, c, d)]
    return verts, tris


def _axes(rotation):
    """UE3's X, Y and Z axes of a rotator (pitch, yaw, roll in rotator units), as rows: a point (x, y, z) in the actor's
    frame is at location + x X + y Y + z Z."""
    sp, sy, sr = (math.sin(a * math.tau / 65536) for a in rotation)
    cp, cy, cr = (math.cos(a * math.tau / 65536) for a in rotation)
    return [[cp * cy, cp * sy, sp], [sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp],
            [-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp]]


def cells(block, cell):
    """A block's cells of about `cell` across (its size over the nearest whole number of cells, at least one): (the
    cell box's half size [hx, hy, hz], [the cells' centres in the world, x first, then y]), each at half the block's
    height."""
    size, (z0, z1) = [float(v) for v in block['size']], [float(v) for v in block['heights']]
    n = [max(1, round(v / cell)) for v in size]
    step = [size[k] / n[k] for k in range(2)]
    axes = _axes([int(v) for v in block['rotation']])
    location = [float(v) for v in block['location']]
    centres = []
    for v in range(n[1]):
        for u in range(n[0]):
            c = [step[0] * (u + 0.5), step[1] * (v + 0.5), (z0 + z1) / 2]
            centres.append([round(location[k] + sum(c[a] * axes[a][k] for a in range(3)), 4) for k in range(3)])
    return [step[0] / 2, step[1] / 2, (z1 - z0) / 2], centres


def mesh_name(lo, hi):
    """The box mesh's name: its size and heights, so blocks of one size share it (Box_192x96_m12_96)."""
    def num(x):
        x = round(float(x), 3)
        s = ('%g' % abs(x)).replace('.', 'p')
        return ('m' if x < 0 else '') + s
    return 'Box_%sx%s_%s_%s' % (num(hi[0] - lo[0]), num(hi[1] - lo[1]), num(lo[2]), num(hi[2]))


def box_mesh_native(lo, hi, guid, at, body_setup=0):
    """A cooked box StaticMesh's native data (what follows its tagged properties), laid out as tools/viewer/mesh.py
    reads it, then the fields after LOD 0. `at` is the logical offset the data's first byte will have (the raw
    triangles' empty inline bulk data points just after its own record); `body_setup` its RB_BodySetup's export."""
    verts, tris = box_geometry(lo, hi)
    centre = [(a + b) / 2 for a, b in zip(lo, hi)]
    half = [(b - a) / 2 for a, b in zip(lo, hi)]
    out = bytearray(struct.pack('<7f', *centre, *half, sum(h * h for h in half) ** 0.5))
    out += struct.pack('<i', body_setup)                            # its BodySetup
    out += struct.pack('<6f', *lo, *hi)                             # the collision tree's root bounds
    out += struct.pack('<ii', 6, 4) + KDOP_NODES
    out += struct.pack('<ii', 8, len(tris)) + b''.join(struct.pack('<4H', a, b, c, 0) for a, b, c in tris)
    out += struct.pack('<2i', 18, 0)                                # internal version, no source data
    out += struct.pack('<i', 0) + struct.pack('<i', 0)              # no optimisation settings; not simplified
    out += struct.pack('<i', 1)                                     # one LOD
    out += struct.pack('<4i', 0, 0, 0, at + len(out) + 16)          # raw triangles: empty, inline
    out += struct.pack('<i', 1) + struct.pack('<4i4Ii', 0, 1, 1, 1, 0, len(tris), 0, len(verts) - 1, 0)
    out += struct.pack('<i', 1) + struct.pack('<2i', 0, len(tris)) + b'\0'
    out += struct.pack('<2I', 12, len(verts)) + struct.pack('<ii', 12, len(verts))
    out += b''.join(struct.pack('<3f', *p) for p, _, _, _ in verts)
    out += struct.pack('<4I', 1, 12, len(verts), 0) + struct.pack('<ii', 12, len(verts))
    out += b''.join(_packed(t, 0x80) + _packed(n, 0xFF) + struct.pack('<2e', *uv) for _, n, t, uv in verts)
    out += struct.pack('<2I', 0, 0)                                 # no vertex colours
    out += struct.pack('<I', len(verts))
    indices = [i for tri in tris for i in tri]
    out += struct.pack('<ii', 2, len(indices)) + struct.pack(f'<{len(indices)}H', *indices)
    # empty wireframe and adjacency index buffers and double-sided shadow flags; the thumbnail's angle and distance
    # and no high-resolution source; the lighting GUID; vertex positions version 1; the streaming texture factors;
    # and the closing 1 the cooked boxes all have
    out += struct.pack('<ii', 2, 0) + struct.pack('<ii', 2, 0) + struct.pack('<ii', 1, 0) + bytes(20)
    out += guid + struct.pack('<i', 1)
    out += struct.pack('<i', 4) + struct.pack('<4f', max(b - a for a, b in zip(lo, hi)), 0.0, 0.0, 0.0)
    out += struct.pack('<i', 1)
    return bytes(out)


def _f32(v):
    return struct.unpack('<f', struct.pack('<f', v))[0]


def convex_hull(lo, hi, spec):
    """The box lo..hi's convex element from a recipe's 'bodySetup': dict(VertexData [x, y, z], PermutedVertexData,
    FacePlaneData ([w, x, y, z]: as the game saves a Plane, its distance first), FaceTriData, EdgeDirections,
    FaceNormalDirections, ElemBox [min, max, valid])."""
    verts = [[float((lo, hi)[c[a]][a]) for a in range(3)] for c in spec['corners']]
    if len(verts) % 4:
        raise ValueError("a convex element's corners come in fours")
    permuted = []
    for k in range(0, len(verts), 4):
        four = verts[k:k + 4]
        for a in range(3):
            permuted.append([four[3][a], four[0][a], four[1][a], four[2][a]])
    planes = []
    for n in spec['planeNormals']:
        a = next(x for x in range(3) if n[x])
        corner = hi if n[a] > 0 else lo
        planes.append([_f32(n[a] * corner[a])] + list(n))
    return dict(VertexData=verts, PermutedVertexData=permuted, FaceTriData=list(spec['triangles']),
                EdgeDirections=[list(e) for e in spec['edges']], FaceNormalDirections=[list(f) for f in spec['faceNormals']],
                FacePlaneData=planes, ElemBox=[[float(v) for v in lo], [float(v) for v in hi], 1])


def body_setup_properties(g, lo, hi, spec):
    """An RB_BodySetup's tagged properties for the box lo..hi, closed by None: PreCachedPhysDataVersion, then
    AggGeom (KAggregateGeom) with one ConvexElems element (KConvexElem: its arrays of immutable structs and ints saved
    raw, ElemBox a Box)."""
    def tag(name, kind, size, struct_name=None):
        out = struct.pack('<iiiiii', g.name(name), 0, g.name(kind), 0, size, 0)
        return out + (struct.pack('<ii', g.name(struct_name), 0) if struct_name else b'')

    def array(name, fmt, items):
        payload = struct.pack('<i', len(items)) + b''.join(struct.pack('<' + fmt, *(x if isinstance(x, list) else [x]))
                                                           for x in items)
        return tag(name, 'ArrayProperty', len(payload)) + payload
    none = struct.pack('<ii', g.name('None'), 0)
    h = convex_hull(lo, hi, spec)
    box = struct.pack('<6fB', *h['ElemBox'][0], *h['ElemBox'][1], h['ElemBox'][2])
    elem = (array('VertexData', '3f', h['VertexData']) + array('PermutedVertexData', '4f', h['PermutedVertexData'])
            + array('FaceTriData', 'i', h['FaceTriData']) + array('EdgeDirections', '3f', h['EdgeDirections'])
            + array('FaceNormalDirections', '3f', h['FaceNormalDirections'])
            + array('FacePlaneData', '4f', h['FacePlaneData'])
            + tag('ElemBox', 'StructProperty', len(box), 'Box') + box + none)
    convex = struct.pack('<i', 1) + elem
    agg = tag('ConvexElems', 'ArrayProperty', len(convex)) + convex + none
    return (tag('PreCachedPhysDataVersion', 'IntProperty', 4) + struct.pack('<i', spec['version'])
            + tag('AggGeom', 'StructProperty', len(agg), 'KAggregateGeom') + agg + none)


# ---------------------------------------------------------------- the destination's objects
def recipe_imports(g, rec):
    """The recipe's imports in the destination ({path: index}, made): found by class, name and outer, else added; a
    top-level package the map holds as an export (the cooked maps' XComGame) is that export."""
    found, made = {}, []
    for path, class_package, class_name in rec['imports']:
        parent, _, name = path.rpartition('.')
        outer = found[parent] if parent else 0
        index = g.find_import(class_name, name, outer)
        if index is None and not parent and class_name == 'Package':
            exports = [k for k, e in enumerate(g.entries, 1)
                       if e.outer == 0 and g.name_of(e.name_index, e.name_number) == name
                       and light_factory.class_of(g, e.cls) == 'Package']
            index = exports[0] if exports else None
        if index is None:
            index = g.add_import(class_package, class_name, outer, name)
            made.append(index)
        found[path] = index
    return found, made


def _property(g, name, kind, value, values):
    def fill(v):
        return values[v[1:]] if isinstance(v, str) and v.startswith('$') else v
    if kind == 'enum':
        enum, item = value[0], fill(value[1])
        return (struct.pack('<iiiiii', g.name(name), 0, g.name('ByteProperty'), 0, 8, 0)
                + struct.pack('<ii', g.name(enum), 0) + struct.pack('<ii', g.name(item), 0))
    if kind == 'objects':
        refs = [fill(v) for v in value]
        payload = struct.pack('<i', len(refs)) + b''.join(struct.pack('<i', r) for r in refs)
        return struct.pack('<iiiiii', g.name(name), 0, g.name('ArrayProperty'), 0, len(payload), 0) + payload
    if kind == 'events':
        # an array of DestructibleActorEvent structs, each its tagged properties: Action alone, then None
        payload = struct.pack('<i', len(value)) + b''.join(
            light_factory.tagged_property(g, 'Action', 'object', fill(v)) + struct.pack('<ii', g.name('None'), 0) for v in value)
        return struct.pack('<iiiiii', g.name(name), 0, g.name('ArrayProperty'), 0, len(payload), 0) + payload
    if kind.startswith('struct '):
        inner = _properties(g, fill(value), values)
        return (struct.pack('<iiiiii', g.name(name), 0, g.name('StructProperty'), 0, len(inner), 0)
                + struct.pack('<ii', g.name(kind.split(' ', 1)[1]), 0) + inner)
    return light_factory.tagged_property(g, name, kind, fill(value))


def _properties(g, specs, values):
    out = bytearray()
    for name, kind, value in specs:
        if isinstance(value, str) and value.startswith('$') and values.get(value[1:]) is None:
            continue        # a property the kind doesn't save (high cover's VisibilityBlockingData)
        if kind == 'enum' and isinstance(value[1], str) and value[1].startswith('$') and values.get(value[1][1:]) is None:
            continue        # an enum the kind doesn't save (a floor's CoverForceFlag)
        out += _property(g, name, kind, value, values)
    return bytes(out + struct.pack('<ii', g.name('None'), 0))


def export_template(g, p, cls, outer=None, outer_class=None):
    """A map export of class `cls` to copy an export-table entry from: a top-level forced-export package (outer 0) or
    a static mesh."""
    for i in range(1, len(p.exports) + 1):
        parent = p.exports[i - 1]['outer']
        if p.cls(i) == cls and (outer is None or parent == outer) \
                and (outer_class is None or p.cls(parent) == outer_class) \
                and (cls != 'Package' or g.entries[i - 1].get('<I', 40) & FORCED_EXPORT):
            return i
    under = f' under a {outer_class}' if outer_class else ''
    raise ValueError(f'the map has no {cls} export{under} to take an entry from')


def _package(g, p, meshes):
    """Our forced-export package (PACKAGE), its entry copied from one of the map's own (class, flags, export flags),
    with its own net object count (its meshes are numbered 1 up, then their body setups) and a GUID from its
    contents."""
    data = struct.pack('<i', -1) + struct.pack('<ii', g.name('None'), 0)
    index = g.add_export(export_template(g, p, 'Package', outer=0), data, number=0, name_index=g.name(PACKAGE))
    e = g.entries[index - 1]
    if e.get('<I', 44) != 1:
        raise ValueError('the map\'s forced-export packages count net objects for more than one generation')
    e.put('<I', 48, 2 * len(meshes) + 1)
    guid = hashlib.md5(('%s|%s' % (PACKAGE, ','.join(meshes))).encode()).digest()
    e.data[52:68] = guid
    return index


def add_blocks(g, p, blocks, version=1):
    """The cover `blocks` (the compiler's) made in the map being grown (`g`, over the pristine map `p`), each by its
    own recipe version (its `version`, else `version`): a box mesh for each size, then each block's actors and
    components (one actor at its corner, or a floor's one per cell), and its tiles. Returns (actors to add to the
    level: each block's actors and its rebuild volume, records: dict(name, kind, actor, component, floor (its first
    actor's), mesh (export indices), location, rotation (the block's), box, tiles, cells: [dict(actor, component,
    floor, location)])). A block with a `breakGroup` is a prop (BREAKING): its record carries breakGroup, its floor is
    None and its one cell has its `action` and `toughness` exports too. A later version only adds kinds, so the
    imports, meshes and body setups are the newest version's, the same as any older one's."""
    import native_copy
    if not blocks:
        return [], []
    versions = [b.get('version', version) for b in blocks]
    rec = recipe(max(versions))
    kinds_of = [recipe(v)['kinds'] for v in versions]
    level = p.by_name.get(LEVEL)
    if level is None or p.cls(level) != 'Level':
        raise ValueError(f'the map has no {LEVEL}')
    breaking_versions = [v for b, v in zip(blocks, versions) if b.get('breakGroup')]
    breaking = breaking_recipe(max(breaking_versions)) if breaking_versions else None
    for b, v, kinds in zip(blocks, versions, kinds_of):
        if b['kind'] not in kinds:
            raise ValueError(f'{b["name"]}: no cover block kind {b["kind"]!r} in recipe version {v}')
        if b.get('breakGroup') and b['kind'] not in breaking_recipe(v)['kinds']:
            raise ValueError(f'{b["name"]}: a cover block of kind {b["kind"]!r} can\'t break with a group')
    found, made = recipe_imports(g, rec)
    breaking_found = recipe_imports(g, breaking)[0] if breaking else {}
    shapes, placed = {}, []
    for b in blocks:
        lo, hi = [0.0, 0.0, float(b['heights'][0])], [float(b['size'][0]), float(b['size'][1]), float(b['heights'][1])]
        if not all(h > l for l, h in zip(lo, hi)):
            raise ValueError(f'{b["name"]}: an empty box {lo}..{hi}')
        cell = recipe(b.get('version', version))['kinds'][b['kind']]['cell']
        if cell:
            half, centres = cells(b, cell)
            lo, hi = [-v for v in half], list(half)
        else:
            centres = [[float(v) for v in b['location']]]
        shapes.setdefault(mesh_name(lo, hi), (lo, hi))
        placed.append((mesh_name(lo, hi), centres))
    package = _package(g, p, sorted(shapes))
    mesh_template = export_template(g, p, 'StaticMesh')
    body_template = export_template(g, p, 'RB_BodySetup', outer_class='StaticMesh')
    spec = rec['bodySetup']
    meshes = {}
    for net, (name, (lo, hi)) in enumerate(sorted(shapes.items()), 1):
        guid = hashlib.md5(('%s.%s' % (PACKAGE, name)).encode()).digest()
        index = len(g.entries) + 1
        head = struct.pack('<i', net) + _properties(g, rec['box']['properties'], dict(bodySetup=index + 1))
        data = head + box_mesh_native(lo, hi, guid, g.next_offset() + len(head), body_setup=index + 1)
        if g.add_export(mesh_template, data, number=0, name_index=g.name(name)) != index:
            raise RuntimeError('the box mesh did not get the planned index')
        g.entries[index - 1].put('<i', 8, package)
        g.entries[index - 1].put('<i', 0, found['Engine.StaticMesh'])
        body = (struct.pack('<i', len(shapes) + net) + body_setup_properties(g, lo, hi, spec)
                + struct.pack('<i', 0))                 # no pre-cooked hull data, as the map's own
        if g.add_export(body_template, body, number=spec['number'], name_index=g.name(spec['name'])) != index + 1:
            raise RuntimeError("the box mesh's body setup did not get the planned index")
        g.entries[index].put('<i', 8, index)
        g.entries[index].put('<i', 0, found[spec['class']])
        meshes[name] = index
    actors, records = [], []
    for b, (shape, centres), kinds in zip(blocks, placed, kinds_of):
        kind = kinds[b['kind']]
        made = []
        if b.get('breakGroup'):
            # a block that breaks with its group: a hidden prop with its Hide action and toughness (BREAKING; its
            # newest version's exports, its own version's kind)
            actor = _breaking_block(g, breaking, breaking_found, level, b, meshes[shape],
                                    breaking_recipe(b.get('version', version))['kinds'][b['kind']])
            made.append(dict(actor=actor, component=actor + 1, floor=None, location=centres[0], action=actor + 2,
                             toughness=actor + 3))
            centres = []
        for at in centres:
            actor = len(g.entries) + 1
            values = dict(floor=actor + 2, mesh=actor + 1, staticMesh=meshes[shape], force=kind['force'],
                          visibility=kind['visibility'], climb=kind['climb'], destination=kind['destination'],
                          ignore=kind['ignore'], location=at,
                          # saved only when turned, as the cooked actors save it (LWR's high helper saves none)
                          rotation=[int(v) for v in b['rotation']] if any(b['rotation']) else None)
            for spec, index, outer in ((rec['actor'], actor, level), (rec['mesh'], actor + 1, actor),
                                       (rec['floor'], actor + 2, actor)):
                cls = found[spec['class']]
                data = (light_factory.preamble(spec, cls, g.next_net_index(outer))
                        + _properties(g, spec['properties'], values) + bytes.fromhex(spec.get('tail', '')))
                archetype = found[spec['archetype']] if spec['archetype'] else 0
                if g.new_export(cls, outer, spec['name'], data, archetype=archetype, flags=spec['flags']) != index:
                    raise RuntimeError('the cover block exports did not get the planned indices')
            made.append(dict(actor=actor, component=actor + 1, floor=actor + 2, location=at))
        tiles = native_copy.add_tiles_box(g, p, b['box'])
        # (a block at a slanted corner gives diagonal cover where the project marks it: diagonal_keep, KB-20)
        # a block outside the map's tiles has none (tiles is None): it is made, with no rebuild volume
        actors += [c['actor'] for c in made] + ([tiles['volume']['export']] if tiles else [])
        records.append(dict(name=b['name'], kind=b['kind'], actor=made[0]['actor'], component=made[0]['component'],
                            floor=made[0]['floor'], mesh=meshes[shape], location=[float(v) for v in b['location']],
                            rotation=[int(v) for v in b['rotation']], box=b['box'], tiles=tiles, cells=made,
                            **({'breakGroup': int(b['breakGroup'])} if b.get('breakGroup') else {})))
    return actors, records


def _breaking_block(g, rec, found, level, block, static_mesh, kind=None):
    """A block that breaks with its group, made by the BREAKING recipe `rec` (`kind`: what its kind saves, else rec's):
    the actor, then its mesh component, its Hide action and its toughness, at the next four export indices. Returns
    the actor's."""
    kind = kind or rec['kinds'][block['kind']]
    actor = len(g.entries) + 1
    values = dict(mesh=actor + 1, action=actor + 2, toughness=actor + 3, staticMesh=static_mesh, force=kind['force'],
                  visibility=kind['visibility'], ignore=kind.get('ignore'), location=[float(v) for v in block['location']],
                  rotation=[int(v) for v in block['rotation']] if any(block['rotation']) else None)
    for spec, index, outer in ((rec['actor'], actor, level), (rec['mesh'], actor + 1, actor),
                               (rec['action'], actor + 2, actor), (rec['toughness'], actor + 3, actor)):
        cls = found[spec['class']]
        net = g.next_net_index(outer)
        head = struct.pack('<i', net) if spec['preamble']['kind'] == 'object' else light_factory.preamble(spec, cls, net)
        data = head + _properties(g, spec['properties'], values) + bytes.fromhex(spec.get('tail', ''))
        archetype = found[spec['archetype']] if spec['archetype'] else 0
        if g.new_export(cls, outer, spec['name'], data, archetype=archetype, flags=spec['flags']) != index:
            raise RuntimeError('the breaking cover block exports did not get the planned indices')
    return actor
