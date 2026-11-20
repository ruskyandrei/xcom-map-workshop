"""The tables and small helpers the compiler shares with its edit families (review finding 23).

The compiler (compiler.py) and each edit family in a module of its own (spawn_edits.py) import this module; a family
never imports the compiler (tools/repo/structure.json, `compiler families`). The compiler takes every name of __all__
with `from compiler_tables import *`, so compiler.FAMILIES and the rest are these same objects: a test that changes
compiler.FAMILIES['spawn'] in place changes what the spawn family reads too.

What is here: each table or helper that more than one of them reads, the compiler and a family or two families (a
family whose methods are still the Compiler's counts as one). A table or helper only the compiler reads stays in
compiler.py; one only a family reads is that family's, in its module once it has one.
"""
import json
import math
import sys
from itertools import product
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parents[1]))     # tools/paths.py (review finding 54)
import paths  # noqa: E402

paths.use('viewer', 'bake')     # export_math; the Build's looks
from export_math import multiply, transform  # noqa: E402
import looks  # noqa: E402

__all__ = ['FRAC_WALL_END_INSET', 'FRAC_SLAB_LOOKS', 'MADE_KINDS', 'GROUND_LOOKS', 'donor_shape', 'wall_heights',
           'made_wall_along', 'FRAC_WALL_BOTTOM', 'FRAC_WALL_TOPS', 'FAMILIES', 'CLASS_FAMILY', 'ASSEMBLY_FAMILIES',
           'FLOOR_THICK', 'HEADROOM', 'EFFECT_KINDS', 'TILE', 'STOREY', 'QUARTER', 'POSE_SLACK', 'EPS_LOCATION',
           'IDENTITY', 'tile_corner', 'game_round', 'short', 'keyable', 'target_key', 'world_box', 'original_key',
           'union', 'tidy', 'turned', 'LibraryError', 'STAGE_MAPS', 'map_building_id']

# A fracturing wall made from numbers (custom geometry plan, section 0): its numbers are its tile edges, and its solid
# stops this short of each end (tools/bake/frac_wall.py RECIPE['endInset']; test_frac_walls checks they agree)
FRAC_WALL_END_INSET = 8.0
# a floor or roof slab made from numbers (custom geometry plan, M5: tools/bake/frac_slab.py, slab_looks.json): its
# looks, each with the heights of its plate in its donor's frame
FRAC_SLAB_LOOKS = {look['id']: (look['recipe']['bottom'], look['recipe']['top']) for look in json.loads(
    (Path(__file__).resolve().parents[1] / 'bake' / 'slab_looks.json').read_text(encoding='utf-8'))['looks']}
MADE_KINDS = ('fracWall', 'fracSlab')    # made from numbers: their own mesh, columns and box


def _ground_looks():
    """A ground shape's looks (custom geometry plan, M6: tools/bake/ground_looks.json, ground.LOOKS), each its patch's
    thickness."""
    path = Path(__file__).resolve().parents[1] / 'bake' / 'ground_looks.json'
    return {look['id']: float(look.get('recipe', {}).get('thickness', 8.0))
            for look in json.loads(path.read_text(encoding='utf-8'))['looks']}


# ground shapes made from numbers (M6: tools/bake/ground.py): their looks, each its patch's thickness
GROUND_LOOKS = _ground_looks()


def donor_shape(kind, numbers):
    """The recipe of a made piece whose look is named by its donor (looks.resolve, from the catalogues; a wall's
    shaped for its storeys, frac_wall.shaped), None for a look id or none, and False for a donor look no catalogue
    holds (the Build measures it from its donor then)."""
    look = numbers.get('look') if isinstance(numbers, dict) else None
    if not isinstance(look, dict):
        return None
    try:
        resolved = looks.resolve(kind, look)
    except looks.LookError:
        return False
    if kind != 'wall':
        return resolved['recipe']
    import frac_wall
    try:
        return frac_wall.shaped(dict(numbers, look=resolved))
    except ValueError:
        # (a wall taller than its look is made: the Build stacks pieces of it, made_split)
        return frac_wall.shaped(dict({k: v for k, v in numbers.items() if k != 'storeys'}, look=resolved))


def wall_heights(wall):
    """A made wall's bottom, top, free ends' inset and its faces' half thickness in its frame (an end running through
    reaches that far past its tile edge: frac_wall.end_insets): its look's (donor_shape), or the Bar's inside wall's
    for a look id or a donor look no catalogue holds."""
    R = donor_shape('wall', wall)
    if R:
        return float(R['bottom']), float(R['top']), float(R['endInset']), float(R['half'])
    return FRAC_WALL_BOTTOM, FRAC_WALL_TOPS[1 if wall.get('storeys') == 1 else 2], FRAC_WALL_END_INSET, FRAC_WALL_END_INSET


def made_wall_along(wall, start=None, end=None):
    """A made wall's box in its frame for world_box: its x range in from its ends (`start` and `end`, the free ends'
    inset when left out). A wall in a donor's look adds its y and z, its look's half thickness and heights (the made
    wall is its look's, not its template mesh's, height: a donor whose bottom is over its pivot is made lower); a look
    id's y and z are its template's (x0, x1 only)."""
    bottom, top, inset, half = wall_heights(wall)
    x0 = float(wall['x0']) + (inset if start is None else start)
    x1 = float(wall['x1']) - (inset if end is None else end)
    R = donor_shape('wall', wall)
    if not R:
        return (x0, x1)
    low, high = (-half, half)
    try:
        import frac_wall
        low, high = frac_wall.extent(R)
    except (ImportError, AttributeError, KeyError, TypeError, ValueError):
        pass
    return (x0, x1, float(low), float(high), bottom, top)


# a made wall's bottom and its top by its storeys (one or two), over the floor it stands on (its numbers' z 0), for
# a look id or a donor look no catalogue holds (wall_heights): a doorway reaches the bottom
FRAC_WALL_BOTTOM = -16.0
FRAC_WALL_TOPS = {1: 192.0, 2: 384.0}
# Every piece is in one family (private/plans/done/cars-doors-ladders-plan.md, section 3.4), which says whether the Build makes
# it, how it may be posed, and, while it isn't built, the milestone its refusal names. A piece of an assembly (a car's
# parts, a door's leaf and frame, a ladder: assemblies()) takes the assembly's family, any other piece its class's.
# `grid`: the pose rule (grid_move): whole tiles, whole storeys and quarter turns from where the original stands, where
# what the map saves per tile maps exactly; any other pose builds with an off-grid warning (since 10 November 2026).
# `what`: how a refusal names the family. Destructible props joined M1 on 6 November 2026 (EXP-13), and collectibles
# (destructible props that are mission loot, such as the power cores) the same day. Ladders build since 8 November
# 2026, brought forward from M2 (EXP-22 runs 1 and 2), doors with a frame the same day (EXP-23 runs 1 to 3), cars too
# (EXP-24 runs 1 and 2) and vans (EXP-24 runs 3 and 4: the Build takes a van's building along). Frameless doors
# use the same native door recipe (EXP-39). Fracturing pieces and physics props were switched on on 9 November
# 2026 at the user's word, before a game run (EXP-28): a fracturing piece keeps the grid move, since the Build carries
# its per-tile fragment columns with it; `builds` off again brings back each one's refusal.
FAMILIES = {
    'scenery': dict(builds=True, milestone=1, grid=False, what='scenery'),
    'destructible': dict(builds=True, milestone=1, grid=False, what='a destructible prop'),
    'collectible': dict(builds=True, milestone=1, grid=False, what='a collectible'),
    'ladder': dict(builds=True, milestone=2, grid=True, what='a ladder'),
    'door': dict(builds=True, milestone=2, grid=True, what='a door'),
    'frameless-door': dict(builds=True, milestone=2, grid=True, what='a door without a frame'),
    'car': dict(builds=True, milestone=2, grid=True, what='a car'),
    'van': dict(builds=True, milestone=2, grid=True, what='a van'),
    'fracturing': dict(builds=True, milestone=3, grid=True, what='a fracturing piece'),
    'physics': dict(builds=True, milestone=3, grid=False, what='a physics prop'),
    'other': dict(builds=False, milestone=3, grid=False, what='another kind of piece'),
    # lights belong to no milestone: `note` is what the page shows in place of the milestone line while the family is
    # off (plan 3.4). Switched on 9 November, at the user's word after EXP-26 run 1, before runs 2 to 6.
    'light': dict(builds=True, milestone=None, grid=False, what='a light',
                  note='Light edits are drawn and saved; the Build makes them once their game test passes.'),
    # a building made from nothing (private/plans/done/prefab-library-plan.md, 5.1 and stage B1): on since EXP-44 passed
    # (11 November 2026); `builds` off again brings back the refusal with its note
    'building': dict(builds=True, milestone=None, grid=False, what='a building made from nothing',
                     note='Buildings are saved; the Build makes them once their game test passes.'),
    # effects (Emitter actors) and ambient sounds moved, turned, copied or deleted in the same map (the effects and
    # sounds plan, stage FX3): on since EXP-68 passed (17 November 2026); `builds` off again brings back the refusal,
    # which an experiment's build lifts with --family, and the page offers their edits only where they build
    # (families.json; viewer.py serve --family)
    'effect': dict(builds=True, milestone=None, grid=False, what='an effect',
                   note='Effects are moved, copied and deleted where the effect family builds.'),
    'sound': dict(builds=True, milestone=None, grid=False, what='an ambient sound',
                  note='Ambient sounds are moved, copied and deleted where the sound family builds.'),
    # an effect's or a sound's values (the effects and sounds plan, stage FX5: an effect's size, starting state and
    # particle parameters; a sound's radii, volume, pitch and starting state): a gate of their own, so the moves,
    # they build for every project since EXP-70 passed (runs 1 and 2, 17 November 2026: every value loads and plays as
    # set, a number where the system reads a vector and an added parameter are read, a save and its load keep them);
    # the page offers the values where they build
    'effect-values': dict(builds=True, milestone=None, grid=False, what='an effect\'s values',
                          note='An effect\'s size, starting state and parameters.'),
    'sound-values': dict(builds=True, milestone=None, grid=False, what='a sound\'s values',
                         note='A sound\'s reach, volume, pitch and starting state.'),
    # lens flares (LensFlareSource actors) moved, turned, copied or deleted (the effects and sounds plan, stage FX6b):
    # they build for every project since EXP-71 passed (17 November 2026: a flare moved, deleted, copied and brought
    # from another map draws where it is put and comes back after a load); the page offers their edits where the
    # family builds (families.json)
    'flare': dict(builds=True, milestone=None, grid=False, what='a lens flare',
                  note='Lens flares are moved, copied and deleted where the flare family builds.'),
    # the base map's pods, Meld points and drop-in points moved, turned, given values, copied and deleted (the editor
    # spawns plan, SP6 and SP7): builds since EXP-72 runs 6 to 8 passed (18 November 2026)
    'spawn': dict(builds=True, milestone=None, grid=False, what='a spawn point',
                  note='Spawn points are moved and their values changed where the spawn family builds.'),
}
CLASS_FAMILY = {'XComLevelActor': 'scenery', 'XComOpacityFadeLevelActor': 'scenery',
                'StaticMeshActor': 'scenery', 'XComDestructibleActor': 'destructible',
                'XComCollectible': 'collectible', 'XComLadder': 'ladder', 'XComInteractiveLevelActor': 'door',
                'XComFracLevelActor': 'fracturing', 'XComDecoFracLevelActor': 'fracturing', 'KAsset': 'physics'}
# The families of assemblies (assemblies()): an edit of one names all its pieces, with one grid move.
ASSEMBLY_FAMILIES = ('ladder', 'door', 'frameless-door', 'car', 'van')
# A flat piece the project adds is expected to give floor (added_floors): no more than FLOOR_THICK high, and with
# HEADROOM clear over a tile (F-71: about 150 units; the game gives no floor to a tile a soldier can't stand on)
FLOOR_THICK, HEADROOM = 40.0, 150.0
# the kinds an effect record is: an effect (Emitter), an ambient sound or a lens flare (compiler.EFFECT_CLASSES)
EFFECT_KINDS = ('effect', 'sound', 'flare')
# The pose rule (plan section 3.2)
TILE, STOREY, QUARTER = 96.0, 64.0, 16384
POSE_SLACK = 0.5         # how far a grid move may miss a whole tile, storey (units) or quarter turn (rotation units)
EPS_LOCATION = 1e-4      # the document's location precision
IDENTITY = transform([0, 0, 0], [0, 0, 0], [1, 1, 1])


def tile_corner(grid):
    """The corner the game counts a map's tiles from, [x, y, z] (the export's tileGrid.tiles, export 26: its world
    data's WorldBounds' low corner); for an older export, a unit under tileGrid.origin, as on every installed map
    (private/plans/done/game-grid-plan.md). None without a grid. A point's tile (a ladder's ends, a mission object's,
    a soldier's spot) is counted from it, as the game counts it; placing (snap, the lines, the grid rule) and the
    rules for boxes (the floor a flat piece gives) keep tileGrid.origin, the level volume's corner, where the maps'
    own pieces stand on whole tiles."""
    if not grid:
        return None
    if grid.get('tiles'):
        return [float(v) for v in grid['tiles'][:3]]
    origin = grid.get('origin')
    return [float(v) - 1 for v in origin[:3]] if origin else None


def game_round(n):
    """Half away from zero, as tools/viewer/resolver.py rounds."""
    return math.floor(n + 0.5) if n >= 0 else math.ceil(n - 0.5)


def short(path):
    return path.split('.')[-1]


def keyable(v):
    """Whether a value read from a record can be a key: a JSON string, number, true, false or null, never a list or an
    object (a hand-edited or newer project's; looking one up in a table would raise TypeError)."""
    return not isinstance(v, (list, dict))


def target_key(target):
    """A target {package, level, actor}'s key into the export's tables, or None when it is no such object or a part of
    it is a list or an object (such a target names nothing)."""
    if not isinstance(target, dict):
        return None
    key = (target.get('package'), target.get('level'), target.get('actor'))
    return key if all(keyable(v) for v in key) else None


def world_box(obj, meshes, location, rotation, along=None):
    """The world box [x0, x1, y0, y1, z0, z1] of one component placed at the actor pose given. `along` (x0, x1) puts
    the mesh's x range in its own frame in place of its bounds' (a fracturing wall made from numbers on the component's
    materials, tools/bake/frac_wall.py: its section, so its y and z, are the template's); a whole box (x0, x1, y0, y1,
    z0, z1) in its frame stands for its bounds (a slab made from numbers, frac_slab.local_box)."""
    b = list(meshes[obj['mesh']]['bounds'])
    if along is not None and len(along) == 6:
        b = [(along[2 * k] + along[2 * k + 1]) / 2 for k in range(3)] + [(along[2 * k + 1] - along[2 * k]) / 2 for k in range(3)]
    elif along is not None:
        b[0], b[3] = (along[0] + along[1]) / 2, (along[1] - along[0]) / 2
    m = multiply(transform(location, rotation, obj['scale']), obj.get('componentTransform') or IDENTITY)
    pts = []
    for sx, sy, sz in product((-1, 1), repeat=3):
        v = [b[0] + sx * b[3], b[1] + sy * b[4], b[2] + sz * b[5]]
        pts.append([sum(m[i][k] * v[k] for k in range(3)) + m[i][3] for i in range(3)])
    return [min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts),
            min(p[2] for p in pts), max(p[2] for p in pts)]


def original_key(t):
    """The viewer's key for an original piece in a group: its target."""
    return 'orig|%s|%s|%s' % (t.get('package'), t.get('level'), t.get('actor'))


def union(boxes):
    return [min(b[0] for b in boxes), max(b[1] for b in boxes), min(b[2] for b in boxes), max(b[3] for b in boxes),
            min(b[4] for b in boxes), max(b[5] for b in boxes)]


def tidy(v, places=4):
    v = round(v, places)
    return 0.0 if v == 0 else v


def turned(v, turns):
    """(x, y) turned by `turns` quarter turns of yaw, as the game turns an actor (+yaw takes X towards Y,
    export_math.transform)."""
    x, y = v[0], v[1]
    for _ in range(turns % 4):
        x, y = -y, x
    return x, y


class LibraryError(ValueError):
    """A piece of another map can't be had. `code`: no-library, donor-missing, donor-changed or not-placeable."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


# the maps whose size a project may set: the bare maps that a new prefab or a new map starts from (tools/bake/shell.py)
STAGE_MAPS = ('CB2_MP_Blank',)


def map_building_id(building):
    """A map building's id in a project: made from its actor, the same each time the map is opened (web/project.js
    mapBuildingId)."""
    return 'map:%s.%s' % (building.get('level') or 'PersistentLevel', short(building['actor']))
