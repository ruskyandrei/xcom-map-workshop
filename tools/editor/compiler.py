"""The editor's compiler for static pieces (first-editor plan, slice E3).

Turns a saved project (research/editor-contracts.md, schema 1 to 4: READ_VERSIONS) and the viewer export of its source map into a
patchtool spec (tools/patch/README.md) plus a report. The spec is a snapshot of one project revision: the same
project and export always give the same spec, byte for byte.

  python tools/editor/compiler.py <project.json> --cache <viewer cache> --out <spec.json> [--report <report.json>]
  python tools/editor/compiler.py <project.json> --export <scene.json> --out <spec.json>

With --stream-only, the spec has no `map.shipAs`: the patch streams into a map someone else ships, a relit variant of
the base map (tools/bake/deploy_fixture.py --stream), which also takes the patch's tile seeds (`map.seedExternally`,
deploy_fixture.py --seed-plan).

What it builds (milestone M1: static scenery and props, XComLevelActor and StaticMeshActor, and destructible props,
XComDestructibleActor, of the base map; a destructible's copy keeps its toughness, cover and damage and destruction
events, as XComMapEdDestructible. Collectibles, XComCollectible, such as the UFO power cores, build as destructible
props too. The editor's Build makes every M1 copy in the map itself (native_split), where a collectible's copy is a
collectible and counts as loot, and takes hidden pieces out of the map, so a deleted collectible no longer counts; the
report says what each edit does to the loot):
- an original moved or turned: hidden exactly where it stood, and copied to its new pose;
- an original deleted: hidden exactly;
- an added piece: a copy of its template at its pose.
All copies go in one XComMapEdCopier with absolute poses (a location and a full rotator each), listed before one
XComMapEdHider with exact targets, so every source is read before anything is hidden (plan section 6, item 7).
The user's groups reach the game through their "break together" option only: the copier links each such group's
breakable pieces (its copies, and the map's own pieces of it left in place), so that damage to one takes the others
with it. A group's lock is the editor's alone.

Every piece is in a family (FAMILIES; private/plans/done/cars-doors-ladders-plan.md, section 3.4). Ladders, doors, cars and vans
are assemblies (assemblies(): a car's parts, a door's leaf and its frame, a ladder alone): an edit names all of an
assembly's pieces with one move. On the grid (grid_move: whole tiles, whole storeys and quarter turns from the
original) everything the map saves per tile maps exactly; since 10 November 2026 any other pose builds too, with an
off-grid warning naming the nearest pose on the grid (the user took the editor's snapping limits away; the Build
carries the per-tile data by the exact move). A family builds once it has passed in the game (ladders, doors with a
frame, cars and vans did on 8 November; lights were switched on on 9 November, see below); `enable` (--family) builds
one that doesn't (FAMILIES' `builds`) for an experiment. A door's frame edited without its leaf is
a destructible prop of its own. Copies of an assembly carry its family, its id and its grid move to the Build.

Fracturing pieces (walls, storey floors, roof slabs: XComFracLevelActor, XComDecoFracLevelActor) and physics props
(KAsset) build for every project since 9 November 2026: the user switched both on before any game run of them
(research/experiments/EXP-28-fracturing-physics.md: its run 1 passed the same day), so that issues are fixed as they
are found. A fracturing piece is no assembly, but it is checked against the grid move (single_grid_rule): its fragment
columns are saved one to a tile and the Build carries them with the copy, which is exact only for whole tiles, whole
storeys and quarter turns (off the grid: the off-grid warning). A physics prop takes any pose. The Build makes both in the map itself (NATIVE_CLASSES).

Anything else is never built partly or approximately: families not built yet (they name their milestone),
assemblies edited in part, pieces of other levels than the base map's, components offset from their actor, and
records the export lacks. A record of that kind, or one that is malformed, is left out and named (the report's
`leftOut`) and the rest builds; an error (a document or export the compiler can't read, a project that would build
nothing) stops the build: the Build goes on only when the report has no errors.

Lights (private/plans/done/editor-lights-plan.md, L6) are the `light` family: an original placed light moved, turned, changed,
switched off or deleted, a copy of one, or a spot light made from the built-in recipe; and the generated area lights a
moved, copied or deleted glowing piece takes along (its association: export 18's `emitterAttachment`, or the project's
`areaLightBindings`). They go into one `lights` object of the spec, which native_split hands to the Build's writer.
light_rule says which lights may be edited. The family's checks are in light_edits.py, its own module. The family builds for every project since 9 November: the user switched
it on after EXP-26 run 1 (a full build on Bar), before its runs 2 to 6, so that issues are fixed as they are found
(FAMILIES['light']['builds'] off again brings back the refusal with its note). Every project with edits needs an export with the light data (export 18 and its area-light
matcher: light_metadata_problem), since moving a piece can move the light its glow makes.

Cover blocks (since 10 November 2026) are added pieces made from the editor's own recipe (`template` {kind: cover,
version}, `cover` {type, size: [x, y], heights: [z0, z1]}): invisible pieces that give high or low cover (`type`
'high' or 'low'), `size` units across from their corner `location` and from `z0` to `z1` over it, as the editor's
handles size them (since 15 November; private/plans/done/cover-block-handles-plan.md; cover_shape). An invisible
floor is one of `type` 'floor', {type, size}: a thin walkable plate whose top is at `location` (EXP-32); a blocker
(`type` 'block', recipe version 2) blocks movement and gives no cover. Older records give whole tiles, {width,
length, type, height}, as LWR's patches place them (COVER_RECIPES), and the first ones {width, length, height: 'high'
| 'low'}, one tile tall. They go into one `covers`
object of the spec (each block's corner, rotation, size, heights and world box), which native_split hands to the
Build's writer (tools/bake/cover_blocks.py: hidden level actors on box meshes, made from a recipe as LWR's own helpers
are, on any install).

Effects and sounds (the effects and sounds plan, stage FX3; project schema 3) are the `effect` and `sound` families:
an original Emitter or ambient sound moved, turned or deleted in place (an override of its actor), a copy of one (an
added record with `kind` and `from`), and an effect a piece carries kept where it is (`effect.follow: none`).
effect_override and effect_add (effect_edits.py, the family's own module) check each against the export's `can` and
`why` (export 28) and write the spec's
`effects` and `sounds` objects (moves, deletes, copies), which native_split hands to the Build's writer
(tools/bake/native_effects.py, native_sounds.py); a copy of another map's comes from the library (foreign_effect,
stage FX4) and the Build stages it as a piece of another map. An effect's own pose, delete or follow none takes it out of its
piece's carrying (`carriedEffects`). Both families build for every project since EXP-68 passed (17 November 2026);
a stream's are view only.

Lens flares (LensFlareSource actors; stage FX6b) are the `flare` family, made the same way: an override moves, turns
or deletes one in place, an added record with `kind: flare` copies one (this map's, or another map's through the
library), and they go into the spec's `flares` object, which the Build's tools/bake/native_flares.py makes. A flare
has no values object (its template and colour stay as the map has them). The family builds for every project since
EXP-71 (17 November 2026).

Rotators are rounded to whole rotation units half away from zero, as the viewer's resolver rounds (game_round); the
report gives each pose's rounding. Each copy's world box (its mesh bounds, turned by the full rotation and scaled) is
in the spec for seed planning; each target's box before the edit is in the report.
"""
import argparse
import copy
import json
import math
import re
import sys
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'viewer'))
from export_math import multiply, transform  # noqa: E402
import ladders  # noqa: E402
import missions  # noqa: E402
import piece_flags  # noqa: E402
# (the Build's looks, after the viewer's and editor's own modules, so no module of the Build's stands in for one of them)
if str(HERE.parent / 'bake') not in sys.path:
    sys.path.append(str(HERE.parent / 'bake'))
import looks  # noqa: E402,F401  (the made family's; read through the compiler by its tests: compiler.looks)
import spawns  # noqa: E402
# the tables and helpers the compiler shares with its edit families: compiler_tables.__all__ (compiler.FAMILIES
# and the rest are its objects); the spawn family, and its table the compiler reads; the effects family, and its
# tables others read through the compiler (prefab_stage, the viewer's twin constants test)
from compiler_tables import *  # noqa: E402,F401,F403
from spawn_edits import SPAWN_COPY_KINDS, SpawnEdits  # noqa: E402
from effect_edits import (EFFECT_SCALE, EFFECT_WORDS, PARAMETER_MAX, SOUND_PITCH, SOUND_RADIUS_MAX,  # noqa: E402,F401
                          SOUND_VOLUME_MAX, EffectEdits)
# the lights family, and its tables and helpers others read through the compiler (prefab_stage, the viewer's
# families and twin constants, the tests)
from light_edits import (LIGHT_RANGES, LIGHT_RECIPES, light_rule, light_value_problem, rotator_of,  # noqa: E402,F401
                         LightEdits)
# the pieces' flags family (nothing reads its tables through the compiler)
from flag_edits import FlagEdits  # noqa: E402
# the made walls, floors, roofs and ground shapes family, and its tables and helpers others read through the compiler
# (the tests, the bake suite's agreement test, an example)
from made_edits import (FRAC_SLAB_MAX_TILES, FRAC_WALL_LOOKS, FRAC_WALL_MIN_LENGTH, WALL_SWEEPS,  # noqa: E402,F401
                        MadeEdits, opening_play, wall_joins)
# the buildings family (made from nothing, and the map's own changed or deleted), and its tables and helpers others
# read through the compiler (the tests, the viewer's prefab builder test)
from building_edits import BUILDING_FLOORS_MAX, BuildingEdits, moved_whole, source_floor_match  # noqa: E402,F401
# the map grid, the clear, landing zones, missions and spawn places, and the tables others read through the compiler
# (the tests, the viewer's prefab builder test)
from mission_edits import STAGE_GRID_MAX, STAGE_LEVELS_MAX, MissionEdits, stage_max  # noqa: E402,F401
# the user's groups (which of them break together), and its helper others read through the compiler (the tests)
from group_edits import GroupEdits, member_key  # noqa: E402,F401
# the floors (the cursor's, the floor the copies give, ladders' climbs, building floors, the map's floor tiles
# still there; nothing reads its tables through the compiler)
from floor_edits import FloorEdits  # noqa: E402
# the native edit (native_split, a function of the spec alone, and the classes whose copies it makes in the map)
# and the library of other maps' pieces as the compiler asks it (Library): modules of their own, named again here
# for what reads them through the compiler (the Build, the prefab stage, the tests, the examples' generators and
# the compile recorder, which records each native_split through this name)
from native_edit import NATIVE_CLASSES, native_split  # noqa: E402,F401
from piece_lookup import Library  # noqa: E402

COMPILER_VERSION = 3
# a floor or roof slab made from numbers (custom geometry plan, M5: tools/bake/frac_slab.py, slab_looks.json): the
# look of one that names none; its looks are FRAC_SLAB_LOOKS (compiler_tables), its sizes the made family's
FRAC_SLAB_DEFAULT_LOOK = 'roof'


# ground shapes made from numbers (M6: tools/bake/ground.py), copying a plain piece (GROUND_CLASSES); a slope steeper
# than about 10 degrees is sloped (F-81: no cover on it) and past 45 no floor; their shapes and sizes are the made
# family's
GROUND_DEFAULT_LOOK = next(iter(GROUND_LOOKS))
GROUND_CLASSES = ('XComLevelActor', 'StaticMeshActor', 'XComOpacityFadeLevelActor')
GROUND_SLOPED, GROUND_STEEP = math.degrees(math.acos(0.9848)), 45.0


def slab_heights(slab):
    """A made slab's bottom and top in its donor's frame: its look's, or a free-form slab's own (z0, z1)."""
    if slab.get('free') == 1:
        return float(slab['z0']), float(slab['z1'])
    R = donor_shape('slab', slab)
    if R:
        return float(R['bottom']), float(R['top'])
    look = slab.get('look', FRAC_SLAB_DEFAULT_LOOK)
    return FRAC_SLAB_LOOKS[look if isinstance(look, str) else FRAC_SLAB_DEFAULT_LOOK]


PATCH_LIFT = 3.0    # a patch's top over the ground it lies on (ground.PATCH_LIFT; F-137)


def ground_thickness(g):
    """A ground patch's thickness: its look's."""
    R = donor_shape('ground', g)
    if R:
        return float(R.get('thickness', 8.0))
    look = g.get('look', GROUND_DEFAULT_LOOK)
    return GROUND_LOOKS.get(look if isinstance(look, str) else GROUND_DEFAULT_LOOK, 8.0)


def ground_box(g):
    """A ground shape's box in its mesh's frame (ground.local_box): a free-form shape's its own numbers'."""
    if g.get('free') == 1:
        return tuple(float(g[k]) for k in ('x0', 'x1', 'y0', 'y1', 'z0', 'z1'))
    if g['shape'] == 'patch':
        z = (PATCH_LIFT - ground_thickness(g), PATCH_LIFT)     # (a little over the ground it lies on)
    else:
        z = (0.0, float(g['height']))
    return (float(g['x0']), float(g['x1']), float(g['y0']), float(g['y1'])) + z


def ground_slope(g):
    """A ramp's slope in degrees (ground.slope): its rise (its height, or a free-form ramp's z1 - z0) over its run."""
    if g.get('shape') != 'ramp':
        return 0.0
    rise = float(g['z1']) - float(g['z0']) if g.get('free') == 1 else float(g['height'])
    return math.degrees(math.atan2(rise, float(g['x1']) - float(g['x0'])))
SCHEMA = 'xcom-map-workshop/project'
# 2: pieces' flags (piece flags plan); 3: effects and sounds (overrides and added records of their own: the effects and
# sounds plan, Part C); 4: the spawns plan's (`spawnRules`, SP8; the base map's spawn points' records, SP6 and SP7).
# A project of schema 1 to 3 builds as it did.
SCHEMA_VERSION = 4
READ_VERSIONS = (1, 2, 3, 4)
# The families whose pieces can come from another map (private/plans/done/cross-map-assets-implementation-plan.md): plain
# scenery since EXP-37; destructible props, collectibles, fracturing pieces, doors (one actor: a leaf, or a door
# without a frame) and physics props since EXP-39 (11 November 2026); ladders since EXP-40 run 2 the same day; effects
# and ambient sounds since EXP-69 (17 November 2026; the effects and sounds plan's FX4).
FOREIGN_FAMILIES = ('scenery', 'destructible', 'collectible', 'fracturing', 'door', 'frameless-door', 'physics', 'ladder',
                    'effect', 'sound', 'flare')
# The assemblies that can come whole from another map (the library lists each as one entry: a car's body, glass and
# parts; a door's leaf and frame), since EXP-40 run 1 (11 November 2026), and a van (its parts, with its own building
# and floor volumes, which the transplanter stages with them) since EXP-42 the same day.
FOREIGN_ASSEMBLIES = ('car', 'door', 'van')
# Ways of bringing a piece that wait for their game check; the library marks such an entry `held` and blocked
# 'check', and a build lifts it with --foreign-family check. None today: both passed EXP-41 (11 November 2026):
# - 'links': a prop that lists other pieces it takes down with it (AffectedChildren) comes with the list emptied;
# - 'prefab': a piece whose archetype is in a Prefab comes with the Prefab as a shell (transplant.SHELLS).
FOREIGN_UNCHECKED = ()
# the library's verdicts on a piece of another map that the compiler builds all the same (the user, 14 November 2026:
# don't leave out): hidden in its own map, linked to other pieces, of a family not brought before, waiting for a game
# test. 'closure' (it needs something that can't be brought) stays a piece left out. FOREIGN_WORDS: the ones that can
# show in the game, warned of (foreign-held); none says it is untried (the user, 16 November 2026).
FOREIGN_SOFT = ('hidden', 'assembly', 'family', 'check')
FOREIGN_WORDS = {'hidden': '%s of %s is hidden in its own map (a helper, not something to see)',
                 'assembly': '%s of %s is linked to other pieces in its own map (a car\'s body and its glass, a prop and '
                             'what it turns into)'}
# The export a project's edits build from (plan 4.1): export 18 has each light's GUIDs and bake membership and the
# area lights' glowing pieces, without which a moved piece could leave its glow's light behind.
EXPORT_MINIMUM = 18
# each kind of effect record's object of the spec and of the native edit (its lane); the effects family's own tables
# are in effect_edits.py
EFFECT_LANES = (('effect', 'effects'), ('sound', 'sounds'), ('flare', 'flares'))
# the version of the export's light metadata a project's edits need (light_metadata_problem)
LIGHT_METADATA = 1
# Cover blocks (tools/bake/cover_blocks.py): whole tiles across, `width` along the block's X and `length` along its Y
# from its corner (the record's location, on the floor), and from 12 units below that floor to 96 above it (high
# cover) or 84 (low cover), as LWR's own CoverPatch.highcover and Cover2x4 helpers stand (URB_PoliceStation's patch),
# each tile of `height` past the first adding `heightStep` to the top (a block two tiles tall stands 192 high, as the
# user's block stood on end did). An invisible floor ('floor', EXP-32) is a plate two units thin under its location
# (its top), one tile tall only ('flat'): under 4 units thick, the tile rebuild's occupancy test skips it, so it carries
# a floor without filling its tiles (research/native-code-notes.md). Version 2 (15 November 2026, Discord feedback S6)
# adds the blocker ('block'): the high block's box, which blocks movement and gives no cover (cover_blocks.py).
# A version only ever adds types; a block keeps the version it was saved with.
COVER_RECIPES = {1: dict(heights={'high': [-12.0, 96.0], 'low': [-12.0, 84.0], 'floor': [-2.0, 0.0]}, maxTiles=16,
                         maxHeight=8, heightStep=96.0, flat=['floor'])}
COVER_RECIPES[2] = dict(COVER_RECIPES[1], heights=dict(COVER_RECIPES[1]['heights'], block=[-12.0, 96.0]))
COVER_KEYS = ('width', 'length', 'type', 'height')
# Since 15 November 2026 (private/plans/done/cover-block-handles-plan.md) a record may give its size in units, as the
# editor's handles make it: {type, size: [x, y], heights: [z0, z1]} (below and above its floor), or an invisible
# floor's {type: 'floor', size: [x, y]} (its plate is the recipe's). Any recipe version reads it: the Build's box mesh
# is made at any size.
COVER_SIZE_KEYS = ('type', 'size', 'heights')
# The game's tile rebuild (research/native/cover-build.md, sections 2 and 4): its occupancy test skips a piece under
# THIN_COVER through any way unless it is THIN_WIDE across; its cover sweep runs COVER_SWEEP over a tile's floor.
THIN_COVER, THIN_WIDE = 4.0, 384.0
COVER_SWEEP = (44.0, 60.0)


def cover_span(recipe):
    """The most a block's heights may be apart: the tallest block of whole tiles (the recipe's bottom to its high top
    and seven more tiles)."""
    z0, z1 = recipe['heights']['high']
    return int(z1 - z0 + recipe['heightStep'] * (recipe['maxHeight'] - 1))


def cover_shape(cover, recipe):
    """A cover record's (type, [x, y] units, [z0, z1] below and above its floor), or None when it is malformed: a record
    of whole tiles ({width, length, type, height}) or of units ({type, size, heights}; a floor's {type, size})."""
    def number(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    if not isinstance(cover, dict) or cover.get('type') not in recipe['heights']:
        return None
    kind, flat, across = cover['type'], cover['type'] in recipe['flat'], recipe['maxTiles'] * TILE
    if set(cover) == set(COVER_KEYS):
        def whole(v, top):
            return isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= top
        if not (whole(cover['width'], recipe['maxTiles']) and whole(cover['length'], recipe['maxTiles'])
                and whole(cover['height'], 1 if flat else recipe['maxHeight'])):
            return None
        z0, z1 = recipe['heights'][kind]
        return kind, [cover['width'] * TILE, cover['length'] * TILE], [z0, z1 + recipe['heightStep'] * (cover['height'] - 1)]
    if set(cover) != ({'type', 'size'} if flat else set(COVER_SIZE_KEYS)):
        return None
    size = cover['size']
    if not (isinstance(size, list) and len(size) == 2 and all(number(v) and 0 < v <= across for v in size)):
        return None
    if flat:
        return kind, [float(v) for v in size], [float(v) for v in recipe['heights'][kind]]
    heights = cover['heights']
    if not (isinstance(heights, list) and len(heights) == 2 and all(number(v) and abs(v) <= across for v in heights)
            and 0 < heights[1] - heights[0] <= cover_span(recipe)):
        return None
    return kind, [float(v) for v in size], [float(v) for v in heights]
FRAME_MATCH = 1.0        # how far a door's frame stands from its leaf (units): they stand at one place
PART_AT = 8.0            # how far a car's part its glass names stands from the body (units; Police Station's light bars: 2)
INSTANCE_MATCH = 1.0     # how far apart two parts' moves may be and still be one copy of an assembly (units)
# The game counts every collectible in the level's actor list at the end of a mission as loot, an intact one as its
# item and a damaged or destroyed one as the damaged item (XGBattle.CollectLoot, the native CollectCollectibles). The
# Build's copy is a collectible in that list; a piece it hides is taken out of the list.
COLLECTIBLE = 'XComCollectible'
LOOT_NOTES = {
    'add': '%s copies a collectible: the copy counts as mission loot too, as the original does',
    'move': '%s is a collectible (mission loot): moved, it still counts once',
    'delete': '%s is a collectible (mission loot): deleted, it no longer counts',
}
NAME_BASE = 900
# UDK's Save As stops at a warning for package names over 30 characters (findings register T-09).
NAME_LIMIT = 30
# the names Windows keeps for devices (CON, NUL, COM1...): no file can have one, with any extension
DEVICE_NAMES = {'CON', 'PRN', 'AUX', 'NUL', *('COM%d' % i for i in range(1, 10)), *('LPT%d' % i for i in range(1, 10))}
ACTOR_NAME = re.compile(r'^[A-Za-z_]\w*\Z')
# The landing zone's pieces (F-45): LWR's landing-zone mutator (XComLZMutator.RespawnLZObjects) spawns the landing zone
# with the map's own pieces of these prefabs as templates (the dropship's soldier-spawn markers, the grounded Skyranger),
# so a moved or deleted one (hidden in the variant) breaks the landing. They are gameplay pieces, not scenery: they can
# be copied, never moved or deleted, and the editor's floor brush leaves them alone (private/plans/done/floor-brush-plan.md,
# 3.4 and 4.4). Told by archetype, the prefab the piece was placed from.
LANDING_PREFIXES = ('dgn_dropshipsoldierspawn.', 'veh_lv1skyranger_mod.prefabs.')


def blast_words(n):
    """'its blast (Break in its panel) knocks out' or 'its N blasts (...) knock out', for the notes on broken pieces
    (custom geometry editing plan, E5 and E6)."""
    return ('its blast (Break in its panel) knocks out' if n == 1
            else 'its %d blasts (Break in its panel) knock out' % n)


def battle_words(keeps, further):
    """What a broken piece does in battle, for its note: a piece the game keeps whole (`keepsPieces`, the export's:
    most roofs and floors) stays whole, its hole cut into a copy of its mesh (F-139), unless its `breaksFurther` asks
    it to break further (F-138); any other breaks further, as the game's walls do."""
    if keeps and further:
        return "; it breaks further in battle (Breaks further in battle), which the game's own roofs and floors don't"
    if keeps:
        return ("; it stays whole in battle, as the game keeps its roofs and floors: the Build cuts the hole into a copy "
                "of its mesh (Breaks further in battle lets it break)")
    return ''


def finite(v, n):
    return isinstance(v, list) and len(v) == n and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                                       and math.isfinite(x) for x in v)


def is_landing(obj):
    """Whether an export's piece is one of the map's landing-zone pieces (LANDING_PREFIXES, by its archetype)."""
    return str(obj.get('archetype') or '').casefold().startswith(LANDING_PREFIXES)


def landing_actors(scene):
    """The actors (paths) of the map's own landing-zone pieces: its base level's pieces is_landing tells."""
    return sorted({o['actor'] for o in scene.get('objects') or [] if o.get('layer') == 'base' and is_landing(o)})


def is_identity(m):
    return all(abs(m[i][j] - IDENTITY[i][j]) < 1e-6 for i in range(4) for j in range(4))


# ---------------------------------------------------------------- the pose rule (plan section 3.2)
def grid_move(src_location, src_rotation, location, rotation, origin):
    """How a pose moves its original: dict(turns, translation, valid, why). The move takes a point x of the original to
    R(x) + translation, R the nearest whole number of quarter turns of yaw (`turns`, 0 to 3). It is valid (`why`
    empty) when pitch and roll are unchanged, the yaw changes by whole quarter turns, Z by whole storeys, and in X and Y
    the move maps the tile grid (corner `origin`) onto itself: a whole-tile move combined with a quarter turn about a
    tile corner. Everything the map saves per tile then maps exactly."""
    dyaw = rotation[1] - src_rotation[1]
    turns = game_round(dyaw / QUARTER)
    why = []
    if abs(rotation[0] - src_rotation[0]) > POSE_SLACK or abs(rotation[2] - src_rotation[2]) > POSE_SLACK:
        why.append('pitch or roll')
    if abs(dyaw - turns * QUARTER) > POSE_SLACK:
        why.append('quarter turns')
    r, o = turned(src_location, turns), turned(origin, turns)
    t = [location[0] - r[0], location[1] - r[1], location[2] - src_location[2]]
    if any(abs(v - game_round(v)) * TILE > POSE_SLACK for v in ((o[0] + t[0] - origin[0]) / TILE, (o[1] + t[1] - origin[1]) / TILE)):
        why.append('whole tiles')
    if abs(t[2] / STOREY - game_round(t[2] / STOREY)) * STOREY > POSE_SLACK:
        why.append('whole storeys')
    return dict(turns=turns % 4, translation=t, valid=not why, why=why)


def nearest_grid_pose(src_location, src_rotation, location, rotation, origin):
    """The valid pose (grid_move) nearest a proposed one, as (location, rotation): the nearest quarter turn, the
    nearest storey, and in X and Y the nearest of the places c + 96·(i, j), c = o − R(o − L0). The editor's recipe snap
    is the same function."""
    turns = game_round((rotation[1] - src_rotation[1]) / QUARTER)
    ro = turned((origin[0] - src_location[0], origin[1] - src_location[1]), turns)
    c = (origin[0] - ro[0], origin[1] - ro[1])
    xy = [c[k] + TILE * game_round((location[k] - c[k]) / TILE) for k in range(2)]
    z = src_location[2] + STOREY * game_round((location[2] - src_location[2]) / STOREY)
    return ([tidy(xy[0]), tidy(xy[1]), tidy(z)],
            [int(src_rotation[0]), int(src_rotation[1]) + turns * QUARTER, int(src_rotation[2])])


def rigid_move(src_location, src_rotation, location, rotation):
    """The rigid move M taking an actor from its source pose to a pose (transform(pose) = M · transform(source)), as a
    4 × 4 matrix. The parts of one copy of an assembly share it."""
    a = transform(src_location, src_rotation, [1, 1, 1])
    b = transform(location, rotation, [1, 1, 1])
    inverse = [[a[j][i] for j in range(3)] + [-sum(a[j][i] * a[j][3] for j in range(3))] for i in range(3)] + [[0, 0, 0, 1]]
    return multiply(b, inverse)


def same_moves(moves, slack=INSTANCE_MATCH):
    """Whether rigid moves are one: the same turn (within about ten rotation units) and translations within `slack`."""
    return all(all(abs(m[i][j] - moves[0][i][j]) < 1e-3 for i in range(3) for j in range(3))
               and all(abs(m[i][3] - moves[0][i][3]) <= slack for i in range(3)) for m in moves[1:])


# ---------------------------------------------------------------- assemblies (plan section 3.3)
def assemblies(scene, package):
    """The map's assemblies: {actor path: assembly}, each a dict of family, members (actor paths, sorted), pivot (the
    piece that names it: a car's body, a door's leaf, the ladder) and leaves (a door's leaves). Pieces of the base level
    of `package` are joined by their prefab instance, their partner (a car's body names its glass), a car's parts
    (an XComDestructibleActor standing at the body's place, within PART_AT, that the glass's fragment columns break:
    export 16's `breaks`; Police Station's standalone light bars, which no prefab places) and a door's leaf to its
    frame: the XComDestructibleActor standing at the leaf's place whose mesh is named after the leaf's plus `_Frame`
    (they reference each other nowhere). A group with a door leaf is a door ('frameless-door' with no frame),
    one with a partner a car ('van' when most of the pieces a building's floors list are its own). A ladder is an
    assembly of its own unless it is in one of those. Other groups (a pool table's prefab) are no assembly: their pieces
    build one by one."""
    objs = {}
    for o in scene.get('objects', []):
        if o.get('sourcePackage') == package and o.get('layer') == 'base':
            objs.setdefault(o['actor'], o)
    parent = {a: a for a in objs}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def join(a, b):
        parent[find(a)] = find(b)

    prefabs = {}
    for a, o in sorted(objs.items()):
        if o.get('prefab'):
            prefabs.setdefault(o['prefab'], []).append(a)
        if o.get('partner') in objs:
            join(a, o['partner'])
            for n in objs[o['partner']].get('breaks') or []:
                part = objs.get(n)
                if (n != a and part and part['actorClass'] == 'XComDestructibleActor'
                        and all(abs(x - y) <= PART_AT for x, y in zip(part['location'], o['location']))):
                    join(n, a)
    for members in prefabs.values():
        for m in members[1:]:
            join(members[0], m)
    meshes = scene.get('meshes') or {}
    mesh_name = lambda o: short((meshes.get(o.get('mesh')) or {}).get('name') or '')
    frames = {}
    for a, o in sorted(objs.items()):
        if o['actorClass'] == 'XComDestructibleActor' and mesh_name(o).endswith('_Frame'):
            frames.setdefault(mesh_name(o)[:-len('_Frame')], []).append(a)
    for a, o in sorted(objs.items()):
        if o['actorClass'] == 'XComInteractiveLevelActor':
            for f in frames.get(mesh_name(o), []):
                if all(abs(p - q) <= FRAME_MATCH for p, q in zip(objs[f]['location'], o['location'])):
                    join(a, f)
    groups = {}
    for a in sorted(objs):
        groups.setdefault(find(a), []).append(a)
    owned = [{m['actor'] for f in b.get('floors') or [] for m in f.get('members') or []} for b in scene.get('buildings') or []]
    out = {}
    for members in groups.values():
        leaves = [a for a in members if objs[a]['actorClass'] == 'XComInteractiveLevelActor']
        bodies = [a for a in members if objs[a].get('partner') in objs]
        if leaves:
            frameless = not any(objs[a]['actorClass'] == 'XComDestructibleActor' for a in members)
            entry = dict(family='frameless-door' if frameless else 'door', members=members, pivot=leaves[0], leaves=leaves)
        elif bodies:
            van = any(piece_flags.van_building(m, members) for m in owned)
            entry = dict(family='van' if van else 'car', members=members, pivot=bodies[0], leaves=[])
        else:
            for a in members:
                if objs[a]['actorClass'] == 'XComLadder':
                    out[a] = dict(family='ladder', members=[a], pivot=a, leaves=[])
            continue
        for a in members:
            out[a] = entry
    return out


def van_buildings(scene, package=None):
    """The ids of the export's buildings that are vans' own (assemblies' rule: most of the pieces its floors list are
    one van's), which go with the van when it is moved or deleted and are never edited on their own."""
    package = package or scene.get('name')
    vans = {}
    for assembly in assemblies(scene, package).values():
        if assembly['family'] == 'van':
            vans[assembly['pivot']] = set(assembly['members'])
    out = set()
    for b in scene.get('buildings') or []:
        owned = {m['actor'] for f in b.get('floors') or [] for m in f.get('members') or []}
        if any(piece_flags.van_building(owned, members) for members in vans.values()):
            out.add(b['id'])
    return out


def light_metadata_problem(scene):
    """Why an export can't build a project's edits (plan 4.1), or None: older than export 18, without its light
    metadata, or without the area-light matcher's associations."""
    version = scene.get('exporterVersion') or 0
    how = ('re-export it (the map browser\'s Prepare, or python tools/viewer/viewer.py export '
           '"<game>/XEW/XComGame/CookedPCConsole/%s.upk" --scope map) and restart the editor' % scene.get('name'))
    if version < EXPORT_MINIMUM:
        return 'the export of %s is version %s, older than export %d, which has the light data edits need: %s' % (
            scene.get('name'), version, EXPORT_MINIMUM, how)
    meta = scene.get('lightMetadata')
    if not isinstance(meta, dict) or (meta.get('version') or 0) < LIGHT_METADATA:
        return 'the export of %s has no light metadata: %s' % (scene.get('name'), how)
    if not meta.get('areaMatcher'):
        # (review finding 31: the matcher is missing from the exporter itself, so exporting again alone gives the same)
        why = next((d.get('message') for d in scene.get('diagnostics') or ()
                    if isinstance(d, dict) and d.get('source') == 'area lights'), None)
        return ('the export of %s has no area-light associations (which glowing piece made each generated light): %s. '
                'Exporting it again gives the same until the editor\'s Python packages are mended (install the editor '
                'again); then %s' % (scene.get('name'), why or 'the area-light matcher could not be loaded when it was '
                                     'made', how))
    return None


# an error's `record` when it is one piece's: that piece is left out, the build goes on (Compiler.error)
PIECE_RECORD = re.compile(r'^(overrides|added)\[\d+\]$')


class Compiler:
    def __init__(self, doc, scene, enable=(), library=None, foreign=()):
        """`enable`: families built although FAMILIES doesn't build them yet (an experiment's build of a family before
        it is switched on). `library`: where a piece of another map is looked up (Library; None: such a piece is an
        error). `foreign`: families whose pieces from other maps build although FOREIGN_FAMILIES doesn't list them
        yet."""
        self.doc, self.scene = doc, scene
        self.enable = set(enable)
        self.library, self.foreign = library, set(foreign)
        self.donors = {}            # (package folded, actor path) -> the copy's donor {package, sha256}
        self.donor_area_lights = {}
        self.donor_report = {}      # package -> dict(package, sha256, pieces)
        unknown = self.enable - set(FAMILIES)
        if unknown:
            raise ValueError('no families %s (they are %s)' % (sorted(unknown), ', '.join(FAMILIES)))
        self.errors, self.warnings, self.notes, self.entities = [], [], [], []
        # the pieces left out of the build (plan "sturdier prefabs", R4): an error that names one piece's record
        # (an override or an added piece) leaves that piece out and the build goes on; `errors` are the document's
        self.left_out = []
        self.copies, self.hides = [], []
        # walls, floors, roofs and ground shapes made from numbers (custom geometry plan): the made copies add records
        # for the family's checks, and the blasts of each cut piece's whole: their own module (review finding 23)
        self.made_edits = MadeEdits(self)
        self.blast_edits = []       # the map's own pieces broken where they stand: [dict(name, target, blasts)] (E6)
        # the user's groups that break together: the break group of each copy, of each of the map's own pieces left
        # in place and of each made wall, and the report's groups: their own module (review finding 23)
        self.group_edits = GroupEdits(self)
        self.moves = []          # each assembly's copy: id, family, members (labels), turns, translation
        # light edits (plan 9.5): the spec's `lights` object, what each piece edit does to the area lights, and the
        # group member keys of the lights the project adds: their own module (review finding 23)
        self.light_edits = LightEdits(self)
        self.covers = []         # cover blocks: the spec's `covers` object (cover_add)
        # the floors: the cursor's, the floor the copies give, the moved and copied ladders whose climb is still to
        # be checked, the building floor a copy stands in and the map's floor tiles still there: their own module
        # (review finding 23)
        self.floor_edits = FloorEdits(self)
        self.cover_members = set()   # their group member keys ('added|' and the output name)
        self.cover_by_member = {}    # member key -> its block in self.covers
        # effects, sounds and lens flares (the effects and sounds plan, Part C): the spec's `effects`, `sounds` and
        # `flares` objects, the group member keys of the ones the project adds, and the effects a record of the
        # project's own takes from the piece that carries them: their own module (review finding 23)
        self.effect_edits = EffectEdits(self)
        # the base map's spawn points moved, given values, copied and deleted (the editor spawns plan, SP6 and SP7):
        # their own module (review finding 23)
        self.spawn_edits = SpawnEdits(self)
        # buildings made from nothing and the map's own changed or deleted (the spec's `buildings` and `buildingEdits`
        # objects), with the sources of the copies whose floors they read: their own module (review finding 23)
        self.building_edits = BuildingEdits(self)
        self.untried_foreign = {}    # (package folded, actor path) of the pieces of other maps built untried
        # pieces' flags (piece flags plan): the map's own pieces whose flags change where they stand (the spec's
        # `pieceFlags` object), the actors whose floor such an edit takes away or gives, and the report's counts:
        # their own module (review finding 23)
        self.flag_edits = FlagEdits(self)
        # what run()'s stages work out, in its order (review finding 23): check_document the map's package (it keeps
        # this value when the stage doesn't run: a document that stops earlier). The map grid, the clear, the drop-in
        # rule, the landing zones and the missions: their own module, which keeps what its stages work out
        self.package = ''
        self.mission_edits = MissionEdits(self)

    # ---------------------------------------------------------------- diagnostics
    def error(self, code, message, **where):
        row = dict(code=code, message=message, **where)
        (self.left_out if PIECE_RECORD.match(str(where.get('record') or '')) else self.errors).append(row)

    def leave_out(self, code, message, **where):
        """A part of the document this compiler can't read or build (a binding, a group, a building, the map size, the
        spawn rule, the cleared mark, a landing zone, the missions list or an entry of it): left out with a row that
        says what the Build does instead, and the rest of the project builds. Only what leaves nothing to build from
        is an error (error(): the schema, the source, the names, an export without the data the Build needs)."""
        self.left_out.append(dict(code=code, message=message, **where))

    def warn(self, code, message, **where):
        """Something that can cause a problem in the game: a piece that can't be walked on, climbed or hidden as it
        should, a landing on nothing, a mission script acting on the wrong actor. Never that a thing is untried (the
        user, 16 November 2026: what ships is usable)."""
        self.warnings.append(dict(code=code, message=message, **where))

    def note(self, code, message, **where):
        """Something the report keeps that can cause no problem in the game (the user, 14 November 2026: warnings only
        for what can): how a piece looks (its light, its tint), loot counts, a field ignored, an edit that changes
        nothing. The report's `notes`; the editor shows only the warnings."""
        self.notes.append(dict(code=code, message=message, **where))

    def loot(self, src, name, kind, where):
        """Warns when an edit touches a collectible: what happens to its loot (LOOT_NOTES)."""
        if src['actorClass'] == COLLECTIBLE:
            self.note('collectible', LOOT_NOTES[kind] % name, **where)

    # ---------------------------------------------------------------- the source
    def check_document(self):
        d = self.doc
        self.map = None
        if d.get('schema') != SCHEMA or d.get('schemaVersion') not in READ_VERSIONS:
            self.error('schema', 'not a project of schema %s version %s (it says %r version %r)'
                       % (SCHEMA, ' or '.join(map(str, READ_VERSIONS)), d.get('schema'), d.get('schemaVersion')))
            return False
        if d.get('mode') != 'edit':
            self.error('mode', 'only edit projects build (mode %r)' % d.get('mode'))
        src, out = d.get('source') or {}, d.get('output') or {}
        self.map = src.get('map')
        if not isinstance(self.map, str) or not ACTOR_NAME.match(self.map):
            self.error('source', 'the project names no source map')
            self.map = None
            return False
        have = (self.scene.get('source') or {}).get('sha256')
        if src.get('sha256') != have:
            self.error('source-mismatch', 'the export is of another %s package (SHA-256 %s, the project was made on %s); '
                       'rebind the project before building' % (self.map, have, src.get('sha256')))
            return False
        # A map's package and its records can name it in two cases (CsmallScout_Farm.upk, Name="CSmallScout_Farm"):
        # the project takes the record's (the map browser's id), the export and its pieces the package's.
        if str(self.scene.get('name') or '').casefold() != self.map.casefold():
            self.error('source-mismatch', 'the export is of %s, not %s' % (self.scene.get('name'), self.map))
            return False
        self.package = self.scene['name']
        # names of any length up to UDK's limit (a new project's map name keeps to 24, so that its patch fits: the
        # Save dialog's allocation, tools/viewer/outputnames.py; a project from before 16 November may have up to 30)
        for key in ('shipAs', 'patch'):
            if not isinstance(out.get(key), str) or not re.match(r'^[A-Za-z][A-Za-z0-9_]*$', out[key]):
                self.error('output', 'output.%s must be a package name (letters, digits and _, starting with a letter)' % key)
            elif len(out[key]) > NAME_LIMIT:
                self.error('output', 'output.%s %s is longer than %d characters, which UDK cannot save; '
                           'save the project as a new one to get shorter names' % (key, out[key], NAME_LIMIT))
            elif out[key].upper() in DEVICE_NAMES:
                self.error('output', 'output.%s %s is a name Windows keeps for a device; save the project as a new '
                           'one under another name' % (key, out[key]))
        if self.errors:
            return False
        names = [out['shipAs'].lower(), out['patch'].lower(), self.map.lower()]
        if len(set(names)) < 3:
            self.error('output', 'the variant, its patch and the base map need three different names')
            return False
        self.out = out
        return True

    def index_export(self):
        self.actors = {}
        for obj in self.scene.get('objects', []):
            key = (obj.get('sourcePackage'), obj.get('layer'), obj.get('actor'))
            self.actors.setdefault(key, []).append(obj)
        grid = self.scene.get('tileGrid') or {}
        o = grid.get('origin') or [0, 0, 0]
        self.origin = [game_round(o[0]), game_round(o[1])]
        self.grid_origin = [float(o[0]), float(o[1])] if grid.get('origin') else None
        self.assemblies = assemblies(self.scene, self.package)
        # ladders (plan section 5): the original floor tiles their ends are checked against, and the streamed patches'
        # hidden ladders that stand in for the map's own (ladders.helpers), hidden with them (stream copies, G6)
        self.floors = ladders.floor_tiles(self.scene)
        # the building floors' volume boxes (export 15; None before): the floor a copy stands in (floor_note)
        self.floor_boxes = None
        if (self.scene.get('exporterVersion') or 0) >= 15:
            self.floor_boxes = [(b['name'], f.get('index', k), f.get('boxes') or []) for b in self.scene.get('buildings') or []
                                for k, f in enumerate(b.get('floors') or [])]
        self.ladder_helpers = ladders.helpers(self.scene)
        self.stream_hides = {}
        # a mission's objects moved in their stream (mission types plan, Part E): {stream: [{actor, location, rotation,
        # old, kind, group}]}, moved in place in the variant's copy of the stream (tools/bake/stream_copy.py --moves)
        self.stream_moves = {}
        # the map's lights by the key pieces use (plan 4.2), and the scene's objects by id (area-light owners)
        self.lights = {}
        for light in self.scene.get('lights') or []:
            self.lights.setdefault((light.get('sourcePackage'), light.get('layer'), light.get('actor')), light)
        self.by_id = {o.get('id'): o for o in self.scene.get('objects') or []}
        # the map's effects, sounds and lens flares by the key pieces use (export 28), the streams' too (view only)
        self.effect_actors = {}
        for kind, key in (('effect', 'effects'), ('sound', 'sounds'), ('flare', 'flares')):
            layers = [self.scene.get(key) or []] + [(s or {}).get(key) or [] for s in (self.scene.get('streams') or {}).values()]
            for rec in (r for layer in layers for r in layer):
                self.effect_actors.setdefault((rec.get('sourcePackage'), rec.get('layer'), rec.get('actor')), dict(rec, kind=kind))
        # the base map's spawn points by actor path (export 33's `spawns`)
        self.spawn_edits.index(self.scene)
        self.building_names = {b.get('id'): b.get('name') for b in self.scene.get('buildings') or []}
        # the map's meshes, and those of the pieces of other maps as they are looked up (foreign_piece)
        self.meshes = dict(self.scene.get('meshes') or {})
        # the assemblies of other maps' pieces: (package, actor) -> assembly, one dict for all its parts
        self.foreign_assemblies = {}

    # ---------------------------------------------------------------- families
    def builds(self, family):
        return FAMILIES[family]['builds'] or family in self.enable

    def family_of(self, actor, parts):
        """(family, assembly or None) of a base-map actor."""
        a = self.assemblies.get(actor)
        if a:
            return a['family'], a
        if parts[0].get('partner'):      # naming a partner the export lacks: a car all the same
            return 'car', None
        return CLASS_FAMILY.get(parts[0]['actorClass'], 'other'), None

    def untried(self, code=None, message=None, **where):
        """The extra a copy carries when the Build has not made its kind before (the user, 14 November 2026: build,
        don't leave out). It is built as any copy; if making it fails, the Build leaves these copies out and builds
        the rest (build.py drop_untried). A warning goes with it only for what can go wrong in the game (`message`):
        never one that says it is untried (the user, 16 November 2026: what ships is usable)."""
        if message:
            self.warn(code, message, **where)
        return dict(untried=True)

    def class_untried(self, actor, parts, where):
        """The extra for a move or a copy of a class with no family of its own, or None (with an error) for one that
        is no piece at all: a volume. A map's level volume draws some of its meshes and holds its tile data; a copy
        of it would be a second level volume, and its hide would take the map's own out."""
        if self.not_a_piece(actor, parts, where, 'moved or copied'):
            return None
        return self.untried()

    def not_a_piece(self, actor, parts, where, what):
        """True (with the error that leaves the record out) for a mesh of a volume, which is no piece: it is never
        `what` (moved or copied; deleted, which would hide the map's level volume and its tile data with it)."""
        cls = parts[0]['actorClass']
        if not cls.endswith('Volume'):
            return False
        self.error('not-a-piece', '%s is a mesh of the map\'s %s, which is no piece: a volume is not %s (the level '
                   'volume holds the map\'s tile data)' % (short(actor), cls, what), actorClass=cls, **where)
        return True

    def refuse(self, family, actor, parts, where, assembly=None):
        """The error for a piece (or an assembly) of a family that isn't built yet."""
        m = FAMILIES[family]['milestone']
        if family == 'car' and not assembly:
            text = '%s names %s as its partner (a car\'s body and its glass), which builds from milestone M%d' % (
                short(actor), short(parts[0]['partner']), m)
        elif assembly:
            others = [short(x) for x in assembly['members'] if x != actor]
            text = '%s is %s%s, which builds from milestone M%d' % (
                short(actor), 'part of ' if others else '', FAMILIES[family]['what'], m)
            if others:
                text += ' (with %s)' % ', '.join(others)
        else:
            cls = parts[0]['actorClass']
            text = '%s is %s %s, which builds from milestone M%d' % (short(actor), 'an' if cls[0] in 'AEIOUX' else 'a', cls, m)
        self.error('milestone', text, milestone=m, family=family, **where)

    def piece(self, target, where, foreign=False, deleting=False):
        """The export's components of a target {package, level, actor} of the base map, or None (with an error).
        With `foreign` (an added piece's template), a piece of another map's level is taken from the library. With
        `deleting`, a component offset from its actor is no matter: the actor is taken out whole."""
        if not isinstance(target, dict) or not all(isinstance(target.get(k), str) for k in ('package', 'level', 'actor')):
            self.error('malformed', 'the record names no {package, level, actor}', **where)
            return None
        if target['package'].casefold() != self.map.casefold() and target['level'] == 'base' and foreign:
            parts = self.foreign_piece(target, where)
            if parts is None:
                return None
        elif target['package'].casefold() != self.map.casefold() or target['level'] != 'base':
            self.error('level', '%s is in %s level %s; M1 builds only the base map\'s own pieces'
                       % (short(target['actor']), target['package'], target['level']), **where)
            return None
        else:
            parts = self.actors.get((target['package'], target['level'], target['actor']))
        if not parts:
            self.error('missing', '%s is not in the export of %s' % (target['actor'], self.map), **where)
            return None
        if not ACTOR_NAME.match(short(target['actor'])):
            self.error('name', '%s is not a name patchtool can give' % target['actor'], **where)
            return None
        for p in parts:
            # a component turned or shifted apart from its actor: a copy made in the map itself is a clone of the
            # actor with its components, so it keeps the offset (plan R2); the patch's copier can't set one
            if (not deleting and p.get('actorClass') not in NATIVE_CLASSES and not self.is_foreign(target)
                    and not is_identity(p.get('componentTransform') or IDENTITY)):
                self.error('component-offset', '%s has a component offset from its actor, which a copy of %s %s '
                           'doesn\'t take yet' % (p['component'], 'an' if p['actorClass'][0] in 'AEIOUX' else 'a',
                                                  p['actorClass']), **where)
                return None
            if p['mesh'] not in self.meshes:
                self.error('missing', '%s has no mesh in the export' % p['component'], **where)
                return None
        return parts

    def is_foreign(self, target):
        return isinstance(target, dict) and isinstance(target.get('package'), str) \
            and target['package'].casefold() != self.map.casefold()

    def foreign_piece(self, target, where):
        """The components of a piece of another map, from the library's record of it (its meshes join self.meshes),
        or None (with an error). The copy's donor is kept for add()."""
        if self.library is None:
            self.error('no-library', '%s is a piece of %s, and this build has no library of other maps\' pieces'
                       % (short(target['actor']), target['package']), **where)
            return None
        try:
            record, entry = self.library.record(target, sky=self.doc.get('stage') is not None and self.map in STAGE_MAPS)
        except LibraryError as error:
            self.error(error.code, str(error), **where)
            return None
        # (an entry only the family gate holds back is checked against this build's gate below)
        soft, held = None, False
        if not entry['placeable'] and entry.get('blocked') == 'check' and 'check' in self.foreign:
            pass        # held for a game check only, and this build is that check's
        elif not entry['placeable'] and entry.get('blocked') in FOREIGN_SOFT and entry['blocked'] != 'family':
            # the library's own verdicts (hidden in its map, linked to other pieces, waiting for a game test): a
            # refusal until 14 November 2026, built since; a warning only for what the game shows (FOREIGN_WORDS)
            held = True
            if entry['blocked'] in FOREIGN_WORDS:
                soft = FOREIGN_WORDS[entry['blocked']] % (short(target['actor']), record['source']['package'])
        elif not entry['placeable'] and entry.get('blocked') != 'family':
            self.error('not-placeable', '%s of %s can\'t be placed in another map: %s'
                       % (short(target['actor']), record['source']['package'], entry['reason']), **where)
            return None
        whole = record.get('assembly')
        family = whole['family'] if whole else CLASS_FAMILY.get(entry['actorClass'], 'other')
        if not (FAMILIES[family]['builds']
                and (family in (FOREIGN_ASSEMBLIES if whole else FOREIGN_FAMILIES) or family in self.foreign)):
            held = True         # a kind of piece not brought from another map before
        if held:
            self.untried_foreign[(target['package'].casefold(), target['actor'])] = self.untried(
                'foreign-held', soft, **where)
        self.meshes.update(record['meshes'])
        # where the piece stands on its home map's tile grid, said on this map's: the pose rule (whole tiles, storeys
        # and quarter turns from the original) then reads as for one of the map's own pieces
        parts = record['objects']
        donor_key = target['package'].casefold()
        self.building_edits.donor_buildings[donor_key] = record.get('buildings', [])
        if record.get('grid') and self.grid_origin is not None:
            shift = [float(a) - b for a, b in zip(self.scene['tileGrid']['origin'][:3], record['grid'])]
            parts = [dict(o, floorLocation=o['location'], location=[v + d for v, d in zip(o['location'], shift)]) for o in parts]
        elif FAMILIES[family]['grid']:
            self.error('pose', '%s of %s keeps to the tile grid, and %s has no grid to place it on'
                       % (short(target['actor']), record['source']['package'],
                          self.map if self.grid_origin is None else record['source']['package']), **where)
            return None
        package = record['source']['package']
        self.donors[(target['package'].casefold(), target['actor'])] = dict(package=package,
                                                                             sha256=record['source']['sha256'])
        self.donor_area_lights[donor_key, target['actor']] = (record.get('areaLights') or {}).get(target['actor'], {})
        # an assembly's parts are edited as one, as the map's own are (assembly_added); a ladder is one of its own
        if whole or family == 'ladder':
            a = whole or dict(family='ladder', members=[target['actor']], pivot=target['actor'], leaves=[])
            kept = self.foreign_assemblies.setdefault((package.casefold(), a['pivot']), dict(a))
            self.foreign_assemblies[(target['package'].casefold(), target['actor'])] = kept
        return [o for o in parts if short(o['actor']) == short(target['actor'])]

    # ---------------------------------------------------------------- poses
    def pose(self, rec, where):
        loc, rot = rec.get('location'), rec.get('rotation')
        if not finite(loc, 3) or not finite(rot, 3):
            self.error('malformed', 'the pose needs location [x, y, z] and rotation [pitch, yaw, roll]', **where)
            return None
        whole = [game_round(r) for r in rot]
        if any(abs(v) > 2 ** 31 - 1 for v in whole):
            self.error('malformed', 'the rotation is out of range', **where)
            return None
        return [tidy(v) for v in loc], whole, max(abs(w - r) for w, r in zip(whole, rot))

    def boxes(self, parts, loc, rot, along=None):
        return union([world_box(p, self.meshes, loc, rot, along) for p in parts])

    # ---------------------------------------------------------------- ladders (plan section 5)
    def hide_helpers(self, actor, where):
        """The streamed patches' hidden ladders that stand in for a map ladder moved or deleted (ladders.helpers): each
        goes into its stream's hides, so the old place doesn't climb. A near one (not at the ladder's own ends) is a
        warning, so a wrong match shows."""
        found = self.ladder_helpers.get(actor) or []
        for h in found:
            self.stream_hides.setdefault(h['stream'], set()).add(short(h['actor']))
            if h['match'] == 'near':
                self.warn('ladder-helper', '%s goes with %s\'s helper %s in %s, the hidden ladder %g units from it with other '
                          'ends: check its old place in the game' % (short(actor), short(actor), short(h['actor']),
                          h['stream'], h['distance']), **where)
        return ['%s.%s' % (h['stream'], short(h['actor'])) for h in found]

    # ---------------------------------------------------------------- records
    def overrides(self):
        known = {'target', 'location', 'rotation', 'deleted', 'flags', 'blasts', 'breaksFurther'}
        gated = {}      # an assembly's records: id -> (assembly, {actor: (target, record, where, parts)})
        for k, rec in enumerate(self.doc.get('overrides') or []):
            where = dict(record='overrides[%d]' % k)
            if not isinstance(rec, dict):
                self.error('malformed', 'not a record', **where)
                continue
            target = rec.get('target')
            if isinstance(target, dict) and isinstance(target.get('actor'), str):
                where['target'] = target['actor']
            effect = self.effect_edits.effect_of(target)
            if effect is not None:
                self.effect_edits.effect_override(target, rec, where, effect)
                continue
            light = self.light_edits.light_of(target)
            if light is not None:
                self.light_edits.light_override(target, rec, where, light)
                continue
            spawn = self.spawn_edits.spawn_of(target)
            if spawn is not None:
                self.spawn_edits.spawn_override(target, rec, where, spawn)
                continue
            if isinstance(target, dict) and target.get('level') == 'stream':
                self.stream_override(target, rec, where)
                continue
            if 'light' in rec:
                self.error('malformed', '%s is not a light of the export, so it has no light values' % short(
                    str((target or {}).get('actor'))), **where)
                continue
            if 'spawn' in rec:
                self.error('malformed', '%s is no spawn point of the base map, so it has no spawn values' % short(
                    str((target or {}).get('actor'))), **where)
                continue
            if 'effect' in rec or 'sound' in rec or 'flare' in rec:
                self.error('malformed', '%s is no effect, sound or lens flare of the export, so it has no %s values' % (
                    short(str((target or {}).get('actor'))), next(k for k in EFFECT_KINDS if k in rec)), **where)
                continue
            for f in sorted(set(rec) - known):
                self.note('unknown-field', 'field %r is not part of an override and is ignored' % f, **where)
            if not self.flag_edits.flags_valid(rec, where):
                continue
            parts = self.piece(target, where, deleting=rec.get('deleted') is True)
            if not parts:
                continue
            if 'breaksFurther' in rec and 'blasts' not in rec:
                self.note('unknown-field', '%s: breaksFurther goes with blasts; with none it is ignored'
                          % short(target['actor']), **where)
            if 'blasts' in rec:
                # one of the map's fracturing pieces broken (custom geometry editing plan, E6)
                if not self.made_edits.blasts_valid(rec, parts, where):
                    continue
                if rec.get('deleted') is True:
                    self.note('blasts-deleted', '%s is deleted, so its blasts are not built' % short(target['actor']), **where)
                elif not self.pose_moves(rec, parts[0]):
                    self.blast_edits.append(dict(name=short(target['actor']), target=target['actor'], blasts=rec['blasts'],
                                                 **({'breaksFurther': True} if rec.get('breaksFurther') else {})))
                    self.note('map-broken', "%s is built broken: %s the fragments "
                              "they reach, saved with those the map paints out, as the game's maps save them%s"
                              % (short(target['actor']), blast_words(len(rec['blasts'])),
                                 battle_words(parts[0].get('keepsPieces'), rec.get('breaksFurther'))), **where)
                    if 'flags' not in rec:
                        continue
            if 'flags' in rec:
                if rec.get('deleted') is True:
                    self.note('flags-deleted', '%s is deleted, so its flags are not built' % short(target['actor']), **where)
                elif not self.pose_moves(rec, parts[0]):
                    # the piece where the map has it (flags alone, or its own pose): its flags written in place, and
                    # nothing else to build for the record (its assembly's move rule doesn't apply to flags)
                    self.flag_edits.stationary_flags(target, parts, rec['flags'], where)
                    continue
            family, assembly = self.family_of(target['actor'], parts)
            if assembly and family in ASSEMBLY_FAMILIES:
                gated.setdefault(id(assembly), (assembly, {}))[1][target['actor']] = (target, rec, where, parts)
            elif not self.builds(family) and rec.get('deleted') is True:
                # a delete empties the piece's slot in the level's list and needs nothing of its family (Clear map
                # plan, section 6); a volume's mesh is no piece, and its delete is left out as its move is
                if family != 'other' or not self.not_a_piece(target['actor'], parts, where, 'deleted'):
                    self.override(target, rec, where, parts)
            elif not self.builds(family) and family == 'other':
                extra = self.class_untried(target['actor'], parts, where)
                if extra:
                    self.override(target, rec, where, parts, extra=extra)
            elif not self.builds(family):
                self.refuse(family, target['actor'], parts, where)
            else:
                self.override(target, rec, where, parts)
        for assembly, recs in sorted(gated.values(), key=lambda e: e[0]['pivot']):
            self.assembly_overrides(assembly, recs)
        self.stream_groups()

    def pose_moves(self, rec, src):
        """Whether an override's pose (if it gives one) moves the piece from where the export has it."""
        if 'location' not in rec and 'rotation' not in rec:
            return False
        loc, rot = rec.get('location', src['location']), rec.get('rotation', src['rotation'])
        if not finite(loc, 3) or not finite(rot, 3):
            return True         # malformed: the move path says so
        return not (all(abs(tidy(a) - b) < EPS_LOCATION for a, b in zip(loc, src['location']))
                    and [game_round(r) for r in rot] == [int(v) for v in src['rotation']])

    def stream_override(self, target, rec, where):
        """A mission object moved in its stream (mission types plan, Part E): the target names the stream as its
        package, `level: "stream"`, and one of the stream's mission objects (export 24's missionObjects). It is moved in
        place in the variant's copy of the stream, so every reference to it holds (Kismet variables, wave groups, the
        handlers' lists). A delete takes it out of the copy's level as a ladder's helper is taken out (stream_copy.py
        --hide), with a warning: the mission's script counts on it."""
        stream, actor = target.get('package'), target.get('actor')
        info, donor = self.stream_info(stream)
        if donor is not None and donor not in self.added_kinds():
            self.error('stream-donor', '%s names %s, the stream an added %s takes its objects from: only a project that '
                       'adds that mission moves them (the Missions item of the Project menu)' % (
                           short(str(actor)), stream, missions.label(donor).lower()), **where)
            return
        if not isinstance(info, dict) or info.get('kind') != 'mission':
            self.error('stream', '%s names %s, which is no mission stream of %s in the export' % (
                short(str(actor)), stream, self.map), **where)
            return
        found = next((o for o in info.get('missionObjects') or [] if o.get('actor') == actor), None)
        if found is None or not ACTOR_NAME.match(short(str(actor))):
            self.error('stream-actor', '%s is not one of the mission objects of %s: only those are moved in a stream'
                       % (short(str(actor)), stream), stream=stream, **where)
            return
        name = short(actor)
        if rec.get('deleted') is True:
            self.warn('mission-object-deleted', '%s (%s) is taken out of the variant\'s copy of %s: the mission\'s script '
                      'counts on it, so the mission may not end as it should' % (missions.object_words(found), name, stream),
                      stream=stream, actor=actor, **where)
            self.stream_hides.setdefault(stream, set()).add(name)
            return
        location, rotation = rec.get('location'), rec.get('rotation')
        if not (finite(location, 3) and isinstance(rotation, list) and len(rotation) == 3
                and all(isinstance(v, int) and not isinstance(v, bool) for v in rotation)):
            self.error('malformed', 'a mission object\'s move needs a location of three numbers and a rotation of '
                       'three whole numbers', stream=stream, **where)
            return
        for f in sorted(set(rec) - {'target', 'location', 'rotation'}):
            self.note('unknown-field', 'field %r is not part of a mission object\'s move and is ignored' % f, **where)
        self.stream_moves.setdefault(stream, []).append(dict(
            actor=name, location=[float(v) for v in location], rotation=[int(v) for v in rotation],
            old=dict(location=list(found.get('location') or [0, 0, 0]), rotation=list(found.get('rotation') or [0, 0, 0])),
            kind=found.get('kind'), group=found.get('group')))
        self.entities.append(dict(kind='move', target=actor, op='stream', stream=stream))

    def added_kinds(self):
        """The kinds of mission the project adds (its `missions` entries that name a kind; missions_kept)."""
        listed = self.mission_edits.missions_kept()[0]
        return {e['kind'] for e in listed if isinstance(e, dict) and isinstance(e.get('kind'), str)} if isinstance(listed, list) else set()

    def stream_info(self, stream):
        """(a stream's export entry, None) for one of the export's mission streams; for the stream an added kind takes
        its objects from (export 33: scene.json's `donors`, the bomb's Slaughterhouse stream) where the export streams
        no such package itself, (an entry of its objects, the kind); else (what the export has, None)."""
        info = (self.scene.get('streams') or {}).get(stream) if isinstance(stream, str) else None
        if isinstance(info, dict) and info.get('kind') == 'mission':
            return info, None
        for kind, donor in sorted((self.scene.get('donors') or {}).items()):
            if isinstance(donor, dict) and donor.get('stream') == stream:
                return dict(kind='mission', missionObjects=donor.get('missionObjects') or []), kind
        return info, None

    def stream_groups(self):
        """A warning (mission-group-split) for a mission object's group (a capture point with its volume, a bomb or a
        power node with its button, emitters and rebuild volume) whose members were not all moved by one offset: LWR's
        handlers and the mission's script expect them together."""
        for stream, moves in sorted(self.stream_moves.items()):
            objects = (self.stream_info(stream)[0] or {}).get('missionObjects') or []
            by = {m['actor']: m for m in moves}
            for group in sorted({m['group'] for m in moves if m.get('group')}):
                members = [o for o in objects if o.get('group') == group]
                offsets = set()
                for o in members:
                    m = by.get(short(o['actor']))
                    old = o.get('location') or [0, 0, 0]
                    offsets.add(tuple(round(m['location'][k] - old[k], 1) for k in range(3)) if m else (0.0, 0.0, 0.0))
                if len(offsets) > 1:
                    self.warn('mission-group-split', '%s of %s was not moved as one: its %d parts stand apart now, which '
                              'the mission\'s script and Long War\'s handlers don\'t expect' % (
                                  missions.group_words(group), stream, len(members)), stream=stream, group=group)

    def moved_object(self, stream, o):
        """Where a mission object stands with the project's moves: (location, its offset from the export's place, or
        None when it isn't moved)."""
        m = next((x for x in self.stream_moves.get(stream) or [] if x['actor'] == short(str(o.get('actor')))), None)
        old = o.get('location') or [0, 0, 0]
        if not m:
            return old, None
        return m['location'], [m['location'][k] - old[k] for k in range(3)]

    def override(self, target, rec, where, parts, extra=None):
        """An original moved (a copy at its new pose and an exact hide) or deleted (an exact hide). `extra`: the
        family and assembly of a piece edited with its assembly."""
        extra = extra or {}
        src = parts[0]
        name = short(target['actor'])
        named = sorted({r for o in parts for r in o.get('referencedBy') or []})
        if named:
            # the map's Kismet acts on the original (plan section 3.5): moved or deleted, its script acts on a piece out
            # of the level and misses the copy. A warning, not a refusal (map buildings plan, section 3: the user)
            self.warn('mission-linked', "%s is named by the map's Kismet (%s): moved or deleted, its mission script acts "
                      "on the hidden original, not on the copy" % (name, '; '.join(named)), **where)
        if any(is_landing(o) for o in parts):
            self.warn('landing-zone', "%s is one of the map's landing-zone pieces (%s): LWR's landing-zone mutator spawns "
                      "the landing from the original pieces, so moved or deleted the dropship's landing breaks (F-45)"
                      % (name, src.get('archetype')), **where)
        old = self.boxes(parts, src['location'], src['rotation'])
        ladder = extra.get('family') == 'ladder'
        if rec.get('deleted') is True:
            self.loot(src, name, 'delete', where)
            if ladder:
                extra = dict(extra, helpers=self.hide_helpers(target['actor'], where))
            self.light_edits.owner_edits.append(('delete', target['actor'], target['actor'], None, where))
            self.hides.append(dict(name=name, label='delete:' + name, box=old))
            self.entities.append(dict(kind='delete', target=target['actor'], actorClass=src['actorClass'],
                                      oldBox=[tidy(v, 3) for v in old], **extra))
            return
        if 'location' not in rec and 'rotation' not in rec:
            self.error('malformed', 'an override is either deleted or gives a pose', **where)
            return
        p = self.pose(dict(location=rec.get('location', src['location']), rotation=rec.get('rotation', src['rotation'])), where)
        if not p:
            return
        loc, rot, rounding = p
        same = all(abs(a - b) < EPS_LOCATION for a, b in zip(loc, src['location'])) and rot == [int(v) for v in src['rotation']]
        if same:
            self.note('unchanged', '%s is at its own pose; nothing to build for it' % name, **where)
            return
        self.loot(src, name, 'move', where)
        if ladder:
            extra = dict(extra, helpers=self.hide_helpers(target['actor'], where))
        if not extra.get('assembly') and self.single_grid_rule(name, src, loc, rot, where) is None:
            return
        new = self.boxes(parts, loc, rot)
        self.floor_edits.floor_note(name, src, new, where, old)
        self.light_edits.owner_edits.append(('move', target['actor'], target['actor'],
                                 rigid_move(src['location'], src['rotation'], loc, rot), where))
        self.copies.append(dict(order=(0, target['actor']), source=name, label='move:' + name, location=loc, rotation=rot, box=new,
                                member=original_key(target), actorClass=src['actorClass'], ladder=None,
                                **{k: v for k, v in extra.items() if k != 'helpers'}))
        if rec.get('flags'):
            self.flag_edits.copy_flags(self.copies[-1], src, rec['flags'], name, where)
        if rec.get('blasts'):
            # (a moved piece broken: its copy made in the map carries the blasts, in its own frame: E6)
            self.copies[-1]['blasts'] = rec['blasts']
            if rec.get('breaksFurther'):
                self.copies[-1]['breaksFurther'] = True
            self.note('map-broken', "%s is built broken: %s the fragments they "
                      "reach, saved with those the map paints out, as the game's maps save them%s"
                      % (name, blast_words(len(rec['blasts'])), battle_words(src.get('keepsPieces'), rec.get('breaksFurther'))),
                      **where)
        if ladder:
            self.floor_edits.ladder_jobs.append((self.copies[-1], name, src, loc, rot, where))
        self.hides.append(dict(name=name, label='move:' + name, box=old))
        self.entities.append(dict(kind='move', target=target['actor'], actorClass=src['actorClass'], location=loc,
                                  rotation=rot, rotationRounding=tidy(rounding, 6), oldBox=[tidy(v, 3) for v in old],
                                  newBox=[tidy(v, 3) for v in new], **extra))

    def assembly_overrides(self, assembly, recs):
        """The records of one assembly's originals: all deleted, or all moved by one grid move (plan section 3.3)."""
        family, pivot, members = assembly['family'], assembly['pivot'], assembly['members']
        first = sorted(recs)[0]
        where = recs[first][2]
        if family == 'door' and not set(assembly['leaves']) & set(recs):
            # a door's frame without its leaf is a destructible prop of its own (an open doorway)
            for actor in sorted(recs):
                self.override(*recs[actor])
            return
        if not self.builds(family):
            self.refuse(family, pivot if pivot in recs else first, recs[first][3], where, assembly)
            return
        deleted = [a for a in sorted(recs) if recs[a][1].get('deleted') is True]
        missing = [a for a in members if a not in recs]
        what = FAMILIES[family]['what']
        if missing:
            self.split_overrides(recs, '%s %s without %s: %s moves, copies and deletes as one (turn on Linked pieces). '
                                 'Each part is edited on its own, and still names the others where they were'
                                 % (short(first), 'is deleted' if recs[first][1].get('deleted') is True else 'moves',
                                    ', '.join(short(a) for a in missing), what), family, where)
            return
        if deleted and len(deleted) != len(recs):
            self.split_overrides(recs, '%s: some of its parts are deleted and others moved; %s moves, copies and '
                                 'deletes as one. Each part is edited on its own' % (short(pivot), what), family, where)
            return
        aid = '%s:%s' % ('delete' if deleted else 'move', short(pivot))
        if deleted:
            for actor in members:
                self.override(*recs[actor], extra=dict(family=family, assembly=aid))
            return
        poses = {}
        for actor in members:
            target, rec, w, parts = recs[actor]
            if 'location' not in rec and 'rotation' not in rec:
                self.error('malformed', 'an override is either deleted or gives a pose', **w)
                return
            src = parts[0]
            p = self.pose(dict(location=rec.get('location', src['location']), rotation=rec.get('rotation', src['rotation'])), w)
            if not p:
                return
            poses[actor] = (src, p[0], p[1])
        if all(all(abs(a - b) < EPS_LOCATION for a, b in zip(loc, src['location'])) and rot == [int(v) for v in src['rotation']]
               for src, loc, rot in poses.values()):
            self.note('unchanged', '%s is at its own pose; nothing to build for it' % short(pivot), family=family, **where)
            return
        if not same_moves([rigid_move(src['location'], src['rotation'], loc, rot) for src, loc, rot in poses.values()]):
            self.split_overrides(recs, '%s\'s parts don\'t move together: %s moves as one (turn on Linked pieces). '
                                 'Each part is moved on its own' % (short(pivot), what), family, where)
            return
        move = self.grid_rule(family, pivot, *poses[pivot], where)
        if move is None:
            return
        self.moves.append(dict(id=aid, family=family, members=['move:' + short(a) for a in members], turns=move['turns'],
                               translation=[tidy(v) for v in move['translation']],
                               **({'grid': False} if move.get('grid') is False else {})))
        for actor in members:
            self.override(*recs[actor], extra=dict(family=family, assembly=aid))

    def split_overrides(self, recs, message, family, where):
        """An assembly edited in part (a refusal until 14 November 2026): a warning, and each record built as a
        piece of its own."""
        extra = self.untried('assembly-split', message, family=family, **where)
        for actor in sorted(recs):
            self.override(*recs[actor], extra=dict(extra))

    def grid_rule(self, family, actor, src, loc, rot, where):
        """The grid move of a piece of a grid family (plan section 3.2); off the grid, with grid False and an
        off-grid warning naming the nearest pose on the grid. None (with an error) when the export has no tile grid."""
        if not FAMILIES[family]['grid']:
            return dict(turns=0, translation=[0, 0, 0])
        if self.grid_origin is None:
            self.error('pose', 'the export of %s has no tile grid, which %s needs' % (self.map, FAMILIES[family]['what']),
                       family=family, **where)
            return None
        move = grid_move(src['location'], src['rotation'], loc, rot, self.grid_origin)
        if not move['valid']:
            near_loc, near_rot = nearest_grid_pose(src['location'], src['rotation'], loc, rot, self.grid_origin)
            self.warn('off-grid', '%s stands off the tile grid (this pose misses %s from where its original stands). It '
                      'builds where it stands, but what the map saves per tile for %s (its cover and floor, fracture '
                      'columns, a ladder\'s climb) maps exactly only for whole tiles, whole storeys and quarter turns, '
                      'with its pitch and roll. The nearest pose on the grid is %s, turned %s' % (short(actor), ', '.join(move['why']), FAMILIES[family]['what'],
                                            near_loc, near_rot), family=family,
                      nearest=dict(location=near_loc, rotation=near_rot), **where)
            move = dict(move, grid=False)
        return move

    def single_grid_rule(self, name, src, loc, rot, where):
        """The grid move of a piece that is no assembly but whose class's family keeps the pose rule (a fracturing
        piece: its fragment columns are saved one to a tile, and the Build carries them with the copy), as grid_rule
        gives it. A piece of a family without the rule takes any pose. The family is the class's: a door's
        frame edited without its leaf is a destructible prop of its own."""
        return self.grid_rule(CLASS_FAMILY.get(src['actorClass'], 'other'), name, src, loc, rot, where)

    def added(self):
        known = {'id', 'actor', 'from', 'components', 'location', 'rotation', 'prefab', 'partner', 'tinted', 'light',
                 'template', 'cover', 'flags', 'kind', 'effect', 'sound', 'generated', 'blasts', 'breaksFurther'}
        gated = {}      # an assembly's copies: id -> (assembly, [(source actor, record, where, parts, pose)])
        for k, rec in enumerate(self.doc.get('added') or []):
            where = dict(record='added[%d]' % k)
            if not isinstance(rec, dict):
                self.error('malformed', 'not a record', **where)
                continue
            out = rec.get('actor')
            if not isinstance(out, str) or not ACTOR_NAME.match(short(out)):
                self.error('malformed', 'the added piece has no output name', **where)
                continue
            where['entity'] = out
            if rec.get('kind') in SPAWN_COPY_KINDS:
                # a pod, a Meld point or a no-spawn volume copied (the editor spawns plan, SP7)
                self.spawn_edits.spawn_add(rec, where)
                continue
            if 'kind' in rec:
                # an effect, a sound or a flare copied (the effects and sounds plan, Part C)
                self.effect_edits.effect_add(rec, where)
                continue
            if 'effect' in rec or 'sound' in rec:
                self.error('malformed', '%s copies a piece, so it has no effect or sound values' % short(out), **where)
                continue
            for f in sorted(set(rec) - known):
                self.note('unknown-field', 'field %r is not part of an added piece and is ignored' % f, **where)
            if 'breaksFurther' in rec and 'blasts' not in rec:
                # (as an override's: a copy's breaksFurther goes with its blasts; a made piece's is in `generated`)
                self.note('unknown-field', '%s: breaksFurther goes with blasts; with none it is ignored' % short(out),
                          **where)
            if not self.flag_edits.flags_valid(rec, where) or not self.made_edits.generated_valid(rec, where):
                continue
            if 'flags' in rec and ('template' in rec or 'cover' in rec or self.light_edits.light_of(rec.get('from')) is not None):
                self.error('malformed', '%s is a cover block, a floor or a light, whose flags are its own: a record of one '
                           'has no flags' % short(out), **where)
                continue
            if 'template' in rec and not isinstance(rec['template'], dict):
                # a recipe is {kind, version}: anything else (null, a list, a name) names none, and the record is left
                # out, its `from` too, if it has one
                self.error('malformed', '%s names its recipe as %s, not {kind, version}' % (short(out), json.dumps(rec['template'])[:80]),
                           **where)
                continue
            if isinstance(rec.get('template'), dict) and rec['template'].get('kind') == 'cover':
                self.cover_add(rec, where)
                continue
            if 'cover' in rec:
                self.error('malformed', '%s has cover values but is not a cover block' % short(out), **where)
                continue
            if 'template' in rec or self.light_edits.light_of(rec.get('from')) is not None:
                self.light_edits.light_add(rec, where)
                continue
            if 'light' in rec:
                self.error('malformed', '%s copies a piece, not a light, so it has no light values' % short(out), **where)
                continue
            if rec.get('tinted'):
                # (a refusal until 14 November 2026: the copy is made, in its template's own colours)
                self.note('tint-dropped', '%s is a tinted copy: the Build makes no tint yet, so it is built in its '
                          'template\'s own colours' % short(out), **where)
            parts = self.piece(rec.get('from'), where, foreign=True)
            if not parts:
                continue
            comps = sorted(p['component'] for p in parts)
            if sorted(rec.get('components') or []) != comps:
                self.error('template-changed', '%s names components %s, but its template now has %s'
                           % (short(out), rec.get('components'), comps), **where)
                continue
            if self.is_foreign(rec['from']):
                # a piece of another map, always made in the map; a part of an assembly goes with its assembly
                p = self.pose(rec, where)
                assembly = self.foreign_assemblies.get((rec['from']['package'].casefold(), rec['from']['actor']))
                if p and assembly:
                    gated.setdefault(id(assembly), (assembly, []))[1].append((rec['from']['actor'], rec, where, parts, p))
                elif p:
                    self.add(rec, where, parts, p)
                continue
            family, assembly = self.family_of(rec['from']['actor'], parts)
            if assembly and family in ASSEMBLY_FAMILIES:
                p = self.pose(rec, where)
                if p:
                    gated.setdefault(id(assembly), (assembly, []))[1].append((rec['from']['actor'], rec, where, parts, p))
                continue
            extra = None
            if not self.builds(family) and family == 'other':
                extra = self.class_untried(rec['from']['actor'], parts, where)
                if extra is None:
                    continue
            elif not self.builds(family):
                self.refuse(family, rec['from']['actor'], parts, where)
                continue
            if rec.get('partner'):
                extra = self.untried('partner-dropped', '%s names a partner but its template is no assembly the Build '
                                     'knows: it is copied as a piece of its own' % short(out), **where)
            p = self.pose(rec, where)
            if p:
                self.add(rec, where, parts, p, extra=extra)
        for assembly, items in sorted(gated.values(), key=lambda e: e[0]['pivot']):
            self.assembly_added(assembly, items)

    def add(self, rec, where, parts, pose, extra=None):
        """A copy of a template at its pose. A made wall or floor past the sizes the game is known to take is cut
        into pieces (split_made), each added here as a copy of its own (`piece` its number, `member` and `whole` the
        whole's)."""
        extra = dict(extra or {})
        piece, member, whole = extra.pop('piece', None), extra.pop('member', None), extra.pop('whole', None)
        out = rec['actor']
        loc, rot, rounding = pose
        src = parts[0]
        made = rec.get('generated')
        if made and made['kind'] == 'ground' and src['actorClass'] not in GROUND_CLASSES:
            self.error('malformed', "%s copies a %s: a ground shape is made on a plain piece's copy (%s)"
                       % (short(out), src['actorClass'], ', '.join(GROUND_CLASSES)), **where)
            return
        if made and made['kind'] != 'ground' and src['actorClass'] not in ('XComFracLevelActor', 'XComDecoFracLevelActor'):
            self.error('malformed', "%s copies a %s: only a fracturing piece's copy is made from numbers"
                       % (short(out), src['actorClass']), **where)
            return
        if not piece:
            self.loot(src, short(out), 'add', where)
        # (a made wall's height is free: its columns are made for where it stands, so only its tiles and quarter turns
        # follow its template's)
        ruled = [loc[0], loc[1], src['location'][2]] if made and made['kind'] in MADE_KINDS else loc
        # (a ground shape keeps to the map's tiles by its numbers, not to its donor's place: the game's ground planes
        # stand off the tile grid, scaled, and are no rule for it)
        # (a piece of a made wall or floor stands where the whole's place puts it)
        if (made and made['kind'] == 'ground') or piece:
            pass
        elif not extra.get('assembly') and self.single_grid_rule(short(out), src, ruled, rot, where) is None:
            return
        if made and made['kind'] in MADE_KINDS and not piece:
            pieces = self.made_edits.made_pieces(made)
            if len(pieces) > 1:
                self.made_edits.split_made(rec, where, parts, pose, extra, pieces)
                return
        # a wall made from numbers stands in its own box, not its template's: its solid, its ends in from its tile edges
        along = made_wall_along(made['wall']) if made and made['kind'] == 'fracWall' else None
        if made and made['kind'] == 'fracSlab':
            # (a slab made from numbers stands in its footprint, between its look's heights)
            s = made['slab']
            along = (s['x0'], s['x1'], s['y0'], s['y1']) + slab_heights(s)
        if made and made['kind'] == 'ground':
            along = ground_box(made['ground'])
        # (a piece made from numbers is made at scale 1, whatever its donor's: the Build sets its copy's scale to 1,
        # frac_walls.unscale)
        drawn = [dict(p, scale=[1.0, 1.0, 1.0]) for p in parts] if made else parts
        new = self.boxes(drawn, loc, rot, along)
        name = short(rec['from']['actor'])
        donor = self.donors.get((rec['from']['package'].casefold(), rec['from']['actor']))
        if (rec['from']['package'].casefold(), rec['from']['actor']) in self.untried_foreign:
            extra = dict(extra, untried=True)
        if donor:
            # A foreign piece keeps its inherited lightmaps on a quick build and carries its live area lights.
            extra = dict(extra, donor=donor)
            row = self.donor_report.setdefault(donor['package'], dict(donor, pieces=[]))
            if name not in row['pieces']:
                row['pieces'].append(name)
            if not any(w['code'] == 'foreign-quick-light' for w in self.notes):
                self.note('foreign-quick-light', 'pieces from other maps keep the light of the map they come from: '
                          'they can look too dark or too bright where they stand')
            area = self.donor_area_lights[rec['from']['package'].casefold(), rec['from']['actor']]
            if area.get('unresolved'):
                self.note('foreign-area-light-unresolved', '%s of %s has generated lights with uncertain ownership: %s'
                          % (name, donor['package'], ', '.join(short(light) for light in area['unresolved'])), **where)
            if area.get('lights'):
                if not self.builds('light'):
                    # (a warning since plan R4: the copy is made, without the lights it would take along)
                    self.note('family', '%s glows and would take its generated area lights along; it is copied without '
                              'them. %s' % (name, FAMILIES['light']['note']), family='light', **where)
                else:
                    move = rigid_move(src.get('floorLocation', src['location']), src['rotation'], loc, rot)
                    for light in area['lights']:
                        self.light_edits.copy_area_light(light, rec['from']['actor'], out, move, donor)
        elif not piece or piece == 1:
            # (a made piece's pieces: once, for the whole)
            if not (made and made['kind'] == 'ground'):
                # (a ground shape is listed in the building it stands in by its own box, as a made wall is)
                self.floor_edits.floor_note(whole or short(out), src, new, where, self.boxes(parts, src['location'], src['rotation']))
            self.light_edits.owner_edits.append(('copy', rec['from']['actor'], out,
                                     rigid_move(src['location'], src['rotation'], loc, rot), where))
        self.copies.append(dict(order=(1, out), source=name, label=short(out), location=loc, rotation=rot, box=new,
                                member=member or 'added|' + out, actorClass=src['actorClass'], ladder=None, **extra))
        if whole:
            self.copies[-1]['whole'] = whole
        if rec.get('generated') and piece and piece > 1:
            # (the notes are the whole's, said with its first piece)
            self.copies[-1]['generated'] = rec['generated']
            if rec['generated']['kind'] == 'fracWall':
                self.made_edits.walls.append((self.copies[-1], dict(where)))
                self.made_edits.parts[short(out)] = drawn
            else:
                self.made_edits.slabs.append((self.copies[-1], dict(where)))
        elif rec.get('generated'):
            # a fracturing wall made from numbers on the template's materials (custom geometry plan, section 0)
            self.copies[-1]['generated'] = rec['generated']
            if rec['generated']['kind'] == 'fracWall':
                self.made_edits.walls.append((self.copies[-1], dict(where)))
                self.made_edits.parts[short(out)] = drawn
                if not piece:
                    self.made_edits.wholes.append((self.copies[-1], dict(where)))
                self.note('generated-wall', "%s is a fracturing wall made from numbers on %s's materials: it breaks "
                          'in parts, and a break passes to the fracturing pieces it touches and from them to it, as '
                          "the game's walls pass theirs on" % (whole or short(out), name), **where)
            elif rec['generated']['kind'] == 'ground':
                gd, slope = rec['generated']['ground'], ground_slope(rec['generated']['ground'])
                self.note('generated-ground', "%s is a ground %s made from numbers on %s's material: %s; it doesn't break"
                          % (short(out), gd['shape'], name, 'it stands in the way and gives cover by its height, as the '
                             "game's rocks do" if gd['shape'] == 'rock' else 'units walk on it'), **where)
                if slope > GROUND_STEEP:
                    self.warn('ground-steep', '%s: its slope (%d degrees) is no floor: units can\'t stand on it'
                              % (short(out), round(slope)), **where)
                elif slope > GROUND_SLOPED:
                    self.note('ground-sloped', '%s: its slope (%d degrees) is walked, but its tiles are sloped: a unit on '
                              'it gets no cover, as on every slope of the game\'s steeper than about 10 degrees'
                              % (short(out), round(slope)), **where)
            elif rec['generated']['kind'] == 'fracSlab':
                self.made_edits.slabs.append((self.copies[-1], dict(where)))
                self.note('generated-slab', "%s is a floor or roof made from numbers on %s's materials: units walk on "
                          'it, it breaks in parts, and a break passes to the fracturing pieces it touches and from them '
                          'to it' % (whole or short(out), name), **where)
            if (rec.get('generated') or {}).get('blasts') or (piece == 1 and member and self.made_edits.broken_wholes.get(member)):
                self.note('made-broken', '%s is built broken: %s the fragments '
                          "they reach, saved as the game's maps save the pieces their designers painted out%s" % (
                              whole or short(out), blast_words(self.made_edits.broken_wholes.get(member) or len(rec['generated']['blasts'])),
                              battle_words(src.get('keepsPieces'), rec['generated'].get('breaksFurther'))),
                          **where)
        if rec.get('flags'):
            self.flag_edits.copy_flags(self.copies[-1], src, rec['flags'], short(out), where)
        if 'blasts' in rec and not rec.get('generated'):
            # a copy of one of the map's fracturing pieces broken (E6): its clone carries the blasts
            if self.made_edits.blasts_valid(rec, [src], where, name=short(out)):
                self.copies[-1]['blasts'] = rec['blasts']
                if rec.get('breaksFurther'):
                    self.copies[-1]['breaksFurther'] = True
                self.note('map-broken', "%s is built broken: %s the fragments "
                          "they reach, saved with those the map paints out, as the game's maps save them%s"
                          % (short(out), blast_words(len(rec['blasts'])), battle_words(src.get('keepsPieces'), rec.get('breaksFurther'))),
                          **where)
        if extra.get('family') == 'ladder':
            self.floor_edits.ladder_jobs.append((self.copies[-1], short(out), src, loc, rot, where))
        self.building_edits.floor_sources[short(out)] = src
        if piece:
            return      # (the whole's entity is split_made's)
        self.entities.append(dict(kind='add', entity=out, id=rec.get('id'), template=rec['from']['actor'],
                                  actorClass=src['actorClass'], location=loc, rotation=rot,
                                  rotationRounding=tidy(rounding, 6), newBox=[tidy(v, 3) for v in new], **extra))

    def assembly_added(self, assembly, items):
        """The copies of one assembly's pieces, sorted into copies of the whole by their moves: each copy names every
        piece once, with one grid move (plan section 3.3)."""
        family, pivot, members = assembly['family'], assembly['pivot'], assembly['members']
        items = sorted(items, key=lambda i: i[1]['actor'])
        if family == 'door' and not {i[0] for i in items} & set(assembly['leaves']):
            for _, rec, where, parts, pose in items:     # frames alone: destructible props of their own
                self.add(rec, where, parts, pose)
            return
        if not self.builds(family):
            first = items[0]
            self.refuse(family, pivot, first[3], first[2], assembly)
            return
        copies = []     # [(move, {source actor: [items]})]
        for item in items:
            src, (loc, rot, _) = item[3][0], item[4]
            move = rigid_move(src['location'], src['rotation'], loc, rot)
            for m, by_source in copies:
                if same_moves([m, move]):
                    by_source.setdefault(item[0], []).append(item)
                    break
            else:
                copies.append((move, {item[0]: [item]}))
        what = FAMILIES[family]['what']
        for _, by_source in copies:
            first = min((i for group in by_source.values() for i in group), key=lambda i: i[1]['actor'])
            where = first[2]
            twice = sorted(short(group[1][1]['actor']) for group in by_source.values() if len(group) > 1)
            missing = [a for a in members if a not in by_source]
            if twice:
                self.error('malformed', '%s and another copy of the same piece stand at one place: %s copies as one'
                           % (', '.join(twice), what), family=family, **where)
                continue
            if missing:
                # (a refusal until 14 November 2026: the parts that are here are copied as pieces of their own)
                extra = self.untried('assembly-split', '%s copies %s without %s: %s moves, copies and deletes as one '
                                     '(turn on Linked pieces). The parts copied are made as pieces of their own, and '
                                     'still name the original\'s other parts' % (
                                         short(first[1]['actor']), short(first[0]), ', '.join(short(a) for a in missing),
                                         what), family=family, **where)
                for group in by_source.values():
                    _, rec, w, parts, pose = group[0]
                    self.add(rec, w, parts, pose, extra=dict(extra))
                continue
            head = by_source[pivot][0]
            move = self.grid_rule(family, head[1]['actor'], head[3][0], head[4][0], head[4][1], head[2])
            if move is None:
                continue
            aid = 'add:' + short(head[1]['actor'])
            self.moves.append(dict(id=aid, family=family, members=sorted(short(by_source[a][0][1]['actor']) for a in members),
                                   turns=move['turns'], translation=[tidy(v) for v in move['translation']],
                                   **({'grid': False} if move.get('grid') is False else {})))
            for actor in members:
                _, rec, w, parts, pose = by_source[actor][0]
                self.add(rec, w, parts, pose, extra=dict(family=family, assembly=aid))

    # ---------------------------------------------------------------- cover blocks
    def cover_add(self, rec, where):
        """A cover block or invisible floor (COVER_RECIPES): its corner, size, heights and world box for the Build's
        writer."""
        out = rec['actor']
        name = short(out)
        version = rec['template'].get('version')
        if set(rec['template']) != {'kind', 'version'} or not keyable(version) or version not in COVER_RECIPES:
            self.error('cover-recipe', '%s is made from a cover recipe this compiler doesn\'t know (%r); its versions are %s'
                       % (name, rec['template'], sorted(COVER_RECIPES)), **where)
            return
        if any(k in rec for k in ('from', 'components', 'light', 'prefab', 'partner', 'tinted')):
            self.error('malformed', '%s is a cover block: it copies no piece and has no light values' % name, **where)
            return
        recipe, cover = COVER_RECIPES[version], rec.get('cover')
        if isinstance(cover, dict) and set(cover) == {'width', 'length', 'height'} and isinstance(cover['height'], str):
            cover = dict(width=cover['width'], length=cover['length'], type=cover['height'], height=1)   # the first records
        shape = cover_shape(cover, recipe)
        if shape is None:
            limit, tall = recipe['maxTiles'], recipe['maxHeight']
            self.error('malformed', '%s: a cover block has a type of %s and either a size across of up to %d units each way '
                       'and heights below and above its floor at most %d units apart (an invisible floor: a size alone), '
                       'or a width and a length of 1 to %d tiles and a height of 1 to %d tiles'
                       % (name, ' or '.join(sorted(recipe['heights'])), limit * TILE, cover_span(recipe), limit, tall), **where)
            return
        kind, size, (z0, z1) = shape
        p = self.pose(rec, where)
        if not p:
            return
        loc, rot, rounding = p
        lo, hi = [0.0, 0.0, z0], [size[0], size[1], z1]
        # what can go wrong in the game (section 1 of private/plans/done/cover-block-handles-plan.md)
        # (an invisible floor is a plate two units thin by design: that is how it carries a floor without filling it)
        if kind not in recipe['flat'] and min(size[0], size[1], z1 - z0) < THIN_COVER and max(size) < THIN_WIDE:
            self.warn('cover-thin', '%s is under %g units through: the game counts a piece that thin as filling no tile, '
                      'so on its own it gives no cover (it can still stop units crossing a tile edge it stands across)'
                      % (name, THIN_COVER), **where)
        elif kind in ('high', 'low') and (z1 <= COVER_SWEEP[0] or z0 >= COVER_SWEEP[1]):
            self.warn('cover-short', '%s stands from %g to %g over its floor: the game looks for cover %g to %g over the '
                      'floor beside a piece, so it gives none' % (name, tidy(z0, 2), tidy(z1, 2), *COVER_SWEEP), **where)
        m = transform(loc, rot, [1, 1, 1])

        def world(v):
            return [sum(m[i][k] * v[k] for k in range(3)) + m[i][3] for i in range(3)]
        corners = [world(v) for v in product(*zip(lo, hi))]
        box = [f(c[k] for c in corners) for k in range(3) for f in (min, max)]
        self.cover_members.add('added|' + out)
        self.covers.append(dict(name=name, label=name, kind=kind, version=version, location=loc, rotation=rot,
                                size=[hi[0], hi[1]], heights=[z0, z1], box=[tidy(v, 3) for v in box]))
        self.cover_by_member['added|' + out] = self.covers[-1]
        self.entities.append(dict(kind='add', entity=out, id=rec.get('id'), template=dict(rec['template']),
                                  cover=dict(cover), actorClass='XComLevelActor', location=loc, rotation=rot,
                                  rotationRounding=tidy(rounding, 6), newBox=[tidy(v, 3) for v in box]))

    # ---------------------------------------------------------------- the spec
    def spec(self):
        objects = []
        copies = sorted(self.copies, key=lambda c: c['order'])
        if copies:
            copy = dict(
                type='copy', location=copies[0]['location'], **{'from': [c['source'] for c in copies]},
                poses=[dict(location=c['location'], rotation=c['rotation']) for c in copies],
                labels=[c['label'] for c in copies],
                boxes=[[tidy(v, 3) for v in c['box']] for c in copies],
                classes=[c['actorClass'] for c in copies])
            # Assemblies (a car, a door, a ladder): each copy's family and assembly ('' for none), and each assembly's
            # grid move (its quarter turns and translation; grid false when it stands off the grid), for the manifest.
            # Pieces of other maps: each copy's donor ({package, sha256}; None for the map's own). The Build stages
            # them in the map before the copies are made (tools/bake/transplant.py).
            if any(c.get('donor') for c in copies):
                copy['donors'] = [c.get('donor') for c in copies]
            # Copies the Build has not been tried on (untried()): it leaves them out if it can't make them.
            if any(c.get('untried') for c in copies):
                copy['untried'] = [bool(c.get('untried')) for c in copies]
            if any(c.get('assembly') for c in copies):
                copy['families'] = [c.get('family') or '' for c in copies]
                copy['assemblies'] = [c.get('assembly') or '' for c in copies]
                copy['assemblyMoves'] = sorted(self.moves, key=lambda m: m['id'])
            # Pieces' flags (piece flags plan): each copy's request (None for one without), written by the Build's writer
            # once the copy is made, from the package's own settings.
            if any(c.get('flags') for c in copies):
                copy['flags'] = [c.get('flags') for c in copies]
            # Fracturing walls made from numbers (custom geometry plan, section 0): each copy's request (None for one
            # without), made by the Build's writer on the copy (tools/bake/frac_walls.py).
            if any(c.get('generated') for c in copies):
                copy['generated'] = [c.get('generated') for c in copies]
            # A moved piece of the map's broken by blasts (E6): each copy's (None for one without), on its clone.
            if any(c.get('blasts') for c in copies):
                copy['blasts'] = [c.get('blasts') for c in copies]
            # (and those asked to break further in battle, roofs and floors the game keeps whole)
            if any(c.get('breaksFurther') for c in copies):
                copy['breaksFurther'] = [bool(c.get('breaksFurther')) for c in copies]
            # Ladders: each ladder copy's foot tile and linked top tile (None for other copies); the Build rebuilds the top
            # tile first, so the climb keeps both its links (plan section 5.2).
            if any(c.get('ladder') for c in copies):
                copy['ladders'] = [c.get('ladder') for c in copies]
            # Break groups (the user's groups with "break together"): a number per copy, 0 for none.
            if self.group_edits.break_copies:
                copy['breakGroups'] = [self.group_edits.break_copies.get(c['member'], 0) for c in copies]
            # a made wall's break group: the group's pieces its columns list (frac_walls.group_columns)
            if self.group_edits.break_walls:
                copy['wallGroups'] = [self.group_edits.break_walls.get(c['member'], 0) for c in copies]
            if self.group_edits.break_originals:
                copy['breakOriginals'] = sorted(self.group_edits.break_originals, key=lambda o: (o['group'], o['name']))
            copy['extra'] = ['bLogTiles=False']
            objects.append(copy)
        elif self.group_edits.break_originals:
            # no copy to carry them: the map's own pieces that break with a cover block of their group
            objects.append(dict(type='breakOriginals',
                                originals=sorted(self.group_edits.break_originals, key=lambda o: (o['group'], o['name']))))
        hides = sorted(self.hides, key=lambda h: h['name'])
        if hides:
            # The hider's own place doesn't matter in exact mode: the middle of what it hides, at its lowest point.
            loc = union([h['box'] for h in hides])
            objects.append(dict(type='hide', exact=True, location=[tidy((loc[0] + loc[1]) / 2), tidy((loc[2] + loc[3]) / 2), tidy(loc[4])],
                                alsoHide=[h['name'] for h in hides], labels=[h['label'] for h in hides],
                                boxes=[[tidy(v, 3) for v in h['box']] for h in hides]))
        if any(self.light_edits.ops.values()):
            # Light edits (plan 9.5): made in the map by the Build's writer (native_split moves them there)
            ops = self.light_edits.ops
            objects.append(dict(type='lights', deletes=sorted(ops['deletes'], key=lambda d: d['name']),
                                changes=sorted(ops['changes'], key=lambda d: d['name']),
                                adds=sorted(ops['adds'], key=lambda d: d['name']),
                                area=sorted(ops['area'], key=lambda d: (d['light'], d['op'], d['name']))))
        if self.covers:
            # cover blocks (cover_add): made in the map by the Build's writer (native_split moves them there)
            objects.append(dict(type='covers', blocks=sorted(self.covers, key=lambda c: c['name'])))
        for kind, key in EFFECT_LANES:
            ops = self.effect_edits.ops[kind]
            if any(ops.values()):
                # effects, sounds and lens flares (the effects and sounds plan, Part D): moved in place, deleted from
                # the level's list and copied in the map by the Build's writer (native_split moves them there)
                objects.append(dict(type=key, moves=sorted(ops['moves'], key=lambda d: d['name']),
                                    deletes=sorted(ops['deletes'], key=lambda d: d['name']),
                                    copies=sorted(ops['copies'], key=lambda d: d['name']),
                                    values=sorted(ops['values'], key=lambda d: d['name'])))
        spawn_ops = self.spawn_edits.ops
        if any(spawn_ops.values()):
            # the base map's spawn points moved or given values (the editor spawns plan, SP6): made in the map by the
            # Build's writer (native_split moves them there; tools/bake/native_spawns.py)
            objects.append(dict(type='spawns', moves=sorted(spawn_ops['moves'], key=lambda d: d['name']),
                                values=sorted(spawn_ops['values'], key=lambda d: d['name']),
                                deletes=sorted(spawn_ops['deletes'], key=lambda d: d['name']),
                                copies=sorted(spawn_ops['copies'], key=lambda d: d['name'])))
        if self.flag_edits.edits:
            # the map's own pieces whose flags change where they stand (piece flags plan): written in the map by the
            # Build's writer (native_split moves them there), each with its box for the tiles it rebuilds
            # (and the map's ladders near them, whose top tiles the Build rebuilds first)
            near = self.floor_edits.flag_ladders()
            objects.append(dict(type='pieceFlags', pieces=sorted(self.flag_edits.edits, key=lambda e: e['name']),
                                **({'ladders': near} if near else {})))
        if self.blast_edits:
            # the map's own fracturing pieces broken where they stand (custom geometry editing plan, E6): their
            # components' painted fragments written in the map by the Build's writer (native_split moves them there)
            objects.append(dict(type='pieceBlasts', pieces=sorted(self.blast_edits, key=lambda e: e['name'])))
        if self.building_edits.new_buildings:
            # buildings made from nothing: made in the map by the Build's writer (native_split moves them there)
            objects.append(dict(type='buildings', buildings=self.building_edits.new_buildings))
        if self.building_edits.edits:
            # the map's own buildings changed or deleted: edited in place by the Build's writer (buildings.edit)
            objects.append(dict(type='buildingEdits', edits=self.building_edits.edits))
        name = re.sub(r'[^\x20-\x7E]|"|\|', '', self.doc.get('name') or '').strip() or 'variant'
        # The streamed patches' pieces the Build takes out of its copies of them ({stream: [actor]}): a moved or
        # deleted ladder's helpers (G6).
        extra = dict(streamHides={k: sorted(v) for k, v in sorted(self.stream_hides.items())}) if self.stream_hides else {}
        # a mission's objects moved in their streams (Part E): {stream: [move]}, moved in place in the stream's copy
        if self.stream_moves:
            extra['streamMoves'] = {k: sorted(v, key=lambda m: m['actor']) for k, v in sorted(self.stream_moves.items())}
        # a cleared map (Clear map plan, section 7): the Build's clear_level takes out what the editor never showed,
        # over the grid as the project has it
        if self.mission_edits.cleared:
            extra['cleared'] = dict(grid=self.mission_edits.stage_grid or list(self.scene['tileGrid']['dimensions'][:3]))
            box = self.mission_edits.outside_box() if self.mission_edits.keep_outside else None
            if box:
                extra['cleared']['keepOutside'] = box
        # the effects the map's pieces carry (export 23; tools/bake/native_effects.py): each follows its piece's move,
        # copy or delete in the Build ({piece: [effect]}, short names), but for one the project moves, deletes or
        # detaches itself (the effects and sounds plan, Part C: a record of its own takes it from its piece)
        carried = {}
        for e in self.scene.get('effects') or []:
            if e.get('carriedBy') and e['actor'] not in self.effect_edits.own:
                carried.setdefault(e['carriedBy'].rsplit('.', 1)[-1], []).append(e['actor'].rsplit('.', 1)[-1])
        if carried:
            extra['carriedEffects'] = {k: sorted(v) for k, v in sorted(carried.items())}
        # the project's landing zones (section 4): the variant's LZArray lines, and the map's own landings moved
        # the project's spawn rules (spawns plan, SP8): the Build writes the variant's ExcludeMaps line
        if self.mission_edits.spawn_rules:
            extra['spawnRules'] = dict(self.mission_edits.spawn_rules)
        if self.mission_edits.zones is not None:
            extra['landingZones'] = dict(zones=self.mission_edits.zones,
                                         own=spawns.own_slots(self.mission_edits.zones, self.mission_edits.own_count),
                                         ownLandings=self.mission_edits.own_count)
        return dict(
            **extra,
            name=self.out['patch'], base='',
            map=dict(name=self.map, origin=self.origin, shipAs=self.out['shipAs'],
                     displayName='%s (%s) |0' % (self.out['shipAs'], name[:80]), streamSlot='free'),
            nameBase=NAME_BASE,
            editor=dict(compiler=COMPILER_VERSION, project=self.doc.get('id'), revision=self.doc.get('revision'),
                        sourceSha256=self.doc['source']['sha256']),
            objects=objects)

    def has_edits(self):
        return any(self.doc.get(k) for k in ('overrides', 'added', 'areaLightBindings', 'buildings', 'cleared',
                                             'landingZones', 'stage', 'spawnRules'))

    # ---------------------------------------------------------------- the mission family's, by name
    def stage(self):
        """The project's larger grid (MissionEdits.stage), kept on the compiler for the tests that call it by name."""
        return self.mission_edits.stage()

    def cleared_mark(self):
        """The project's clear (MissionEdits.cleared_mark), kept on the compiler for a test that calls it by name."""
        return self.mission_edits.cleared_mark()

    # ---------------------------------------------------------------- the floor family's, by name
    def cursor_storeys(self):
        """The cursor's floors of the map (FloorEdits.cursor_storeys), kept on the compiler for the tests that call it
        by name."""
        return self.floor_edits.cursor_storeys()

    def added_floors(self):
        """The floor the project's copies are expected to give (FloorEdits.added_floors), kept on the compiler for the
        tests and an example's generator that call it by name."""
        return self.floor_edits.added_floors()

    def floor_now(self):
        """The map's saved floor tiles whose piece is still where it was (FloorEdits.floor_now), kept on the compiler
        for a test and the examples' generators that call it by name."""
        return self.floor_edits.floor_now()

    def floor_kept_off(self):
        """The map's own pieces whose Floor the project's flags keep off (FloorEdits.floor_kept_off), kept on the
        compiler for a test that calls it by name."""
        return self.floor_edits.floor_kept_off()

    def run(self):
        spec = None
        if self.check_document():
            problem = light_metadata_problem(self.scene) if self.has_edits() else None
            if problem:
                self.error('export-version', problem, minimum=EXPORT_MINIMUM)
        if not self.errors and self.map is not None:
            self.index_export()
            self.mission_edits.cleared_mark()
            self.mission_edits.spawn_rules_mark()
            self.overrides()
            self.added()
            self.made_edits.join_made_walls()
            self.made_edits.made_walls_stacked()
            self.made_edits.made_wall_openings()
            self.light_edits.derive_area_lights()
            self.group_edits.groups()
            self.mission_edits.stage()
            self.floor_edits.ladder_climbs()
            self.floor_edits.floor_headroom()
            self.building_edits.buildings()
            self.made_edits.made_slabs_in_floors()
            self.made_edits.made_slab_cursors()
            self.mission_edits.landing_zones()
            self.mission_edits.missions_check()
            self.mission_edits.stage_outside()
            # A moved original can also be another copy's template; only one hide per actor.
            seen = set()
            self.hides = [h for h in sorted(self.hides, key=lambda h: (h['name'], h['label'])) if not (h['name'] in seen or seen.add(h['name']))]
            if not self.errors:
                spec = self.spec()
        left_out = sorted(self.left_out, key=lambda e: (e.get('record') or '', e['code']))
        report = dict(compiler=COMPILER_VERSION, ok=not self.errors, project=self.doc.get('id'), revision=self.doc.get('revision'),
                      leftOut=left_out,
                      counts=dict(moved=sum(e['kind'] == 'move' for e in self.entities), deleted=sum(e['kind'] == 'delete' for e in self.entities),
                                  added=sum(e['kind'] == 'add' for e in self.entities), errors=len(self.errors), warnings=len(self.warnings),
                                  leftOut=len(self.left_out),
                                  lights=dict(deleted=len(self.light_edits.ops['deletes']), added=len(self.light_edits.ops['adds']),
                                              changed=len(self.light_edits.ops['changes']), area=len(self.light_edits.ops['area'])),
                                  **{key: dict(moved=len(self.effect_edits.ops[kind]['moves']),
                                               deleted=len(self.effect_edits.ops[kind]['deletes']),
                                               added=len(self.effect_edits.ops[kind]['copies']),
                                               valued=len(self.effect_edits.ops[kind]['values'])
                                               + sum(1 for c in self.effect_edits.ops[kind]['copies'] if c.get('values')))
                                     for kind, key in EFFECT_LANES},
                                  spawns={k: len(self.spawn_edits.ops[op]) for k, op in (
                                      ('moved', 'moves'), ('valued', 'values'), ('added', 'copies'), ('deleted', 'deletes'))},
                                  flags=dict(self.flag_edits.counts, inPlace=len(self.flag_edits.edits),
                                             onCopies=sum(1 for c in self.copies if c.get('flags')))),
                      errors=self.errors, warnings=self.warnings, notes=self.notes,
                      stageGrid=self.mission_edits.stage_grid, cleared=self.mission_edits.cleared,
                      clearKeepsOutside=self.mission_edits.keep_outside, landingZones=self.mission_edits.zones,
                      ownLandings=self.mission_edits.own_count, spawnRules=self.mission_edits.spawn_rules,
                      missions=self.mission_edits.missions_kept()[0] if self.map is not None else None,
                      buildings=[dict(id=b['id'], name=b['name'], kind=b['kind'], floors=len(b['floors']))
                                 for b in self.building_edits.new_buildings],
                      mapBuildings=[dict(id=e['id'], actor=e['actor'], **({'deleted': True} if e['deleted'] else
                                                                           dict(floors=len(e['floors']), moved=e['moved'])))
                                    for e in self.building_edits.edits],
                      entities=sorted(self.entities, key=lambda e: (e['kind'], e.get('op') or '', e.get('target') or e.get('entity'),
                                                                    e.get('ownerEntity') or '')),
                      groups=self.group_edits.report, assemblies=sorted(self.moves, key=lambda m: m['id']),
                      families=sorted(f for f in FAMILIES if self.builds(f)),
                      donors=[dict(d, pieces=sorted(d['pieces'])) for _, d in sorted(self.donor_report.items())])
        return spec, report


def compile_project(doc, scene, enable=(), library=None, foreign=()):
    """(spec or None, report) for a project document and the export of its source map. `enable`: families to build
    although FAMILIES doesn't yet (an experiment's build). `library` (a Library): where pieces of other maps come
    from; `foreign`: families whose pieces from other maps build although FOREIGN_FAMILIES doesn't list them. The document
    is left as it was: the compiler works on a copy (it writes the Build's request versions into its records: a rock's
    moved points and a plain piece; a caller that compiled and then saved the same document saved those, which the
    compiler refuses, EXP-84)."""
    return Compiler(copy.deepcopy(doc), scene, enable, library, foreign).run()


def stream_only(spec):
    """The spec as a plain streamed patch: the base map is shipped by something else, a relit variant of it
    (tools/bake/relight.py, deployed by tools/bake/deploy_fixture.py --stream, EXP-17), so `map` keeps only the base
    map's name and origin, and patchtool ships no copy of its own. Its tile seeds go into that variant
    (`map.seedExternally`; deploy_fixture.py --seed-plan), not into the lab's base map."""
    out = dict(spec)
    out['map'] = dict(name=spec['map']['name'], origin=spec['map']['origin'], seedExternally=True)
    out['editor'] = dict(spec['editor'], streamOnly=True)
    return out


class ExportMissing(LookupError):
    """No usable export of a project's source map in the viewer cache (find_export). `code` is what a failed Build
    says for it (build.py's "build failed code:" line, the build job's errorCode), so the page offers Prepare by it,
    never by the message's words (review finding 55)."""
    code = 'export-missing'


def find_export(cache, doc, minimum=EXPORT_MINIMUM):
    """The export (scene.json) of the project's source map in a viewer cache and its data: one with the project's
    SHA-256 (the cache names folders <first 16 hex digits>-v<exporter version>-map, and a later export of the same
    version <...>-map-<suffix>: export.py publishes beside an existing one) and exporter version `minimum` or
    newer (export 18 has the light data every edit needs: plan 4.1), preferring the exporter version the project was
    edited on among those, then the newest. A project edited on an older export takes the newest that qualifies.
    A candidate whose scene.json can't be read whole, or is not a scene of that package, version and scope
    (catalogue.read_scene: the check the map list and the cache's pruning make too), is passed over for the next one
    (review finding 17). ExportMissing when none qualifies."""
    import catalogue
    src = doc.get('source') or {}
    sha = str(src.get('sha256') or '')
    folder = Path(cache) / str(src.get('map'))
    found = []
    for scene in folder.glob('*-map*/scene.json'):
        m = catalogue.GENERATION.match(scene.parent.name)
        if m and m.group('scope') == 'map' and len(sha) == 64 and sha.startswith(m.group('digest')) \
                and int(m.group('version')) >= minimum:
            try:
                found.append((int(m.group('version')) == src.get('exporterVersion'), int(m.group('version')),
                              scene.stat().st_mtime_ns, scene))
            except OSError:
                continue
    for *_, scene in sorted(found, reverse=True):
        try:
            entry, data = catalogue.read_scene(scene.parent)
        except (OSError, ValueError):
            continue
        if entry['sha256'] == sha and entry['scope'] == 'map':
            return scene, data
    raise ExportMissing('no export of %s with SHA-256 %s at version %d or newer in %s: prepare the map (re-export it: the '
                        'map browser\'s Prepare, or python tools/viewer/viewer.py export '
                        '"<game>/XEW/XComGame/CookedPCConsole/%s.upk" --scope map) and restart the editor'
                        % (src.get('map'), sha, minimum, folder, src.get('map')))


def write_json(path, value):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(value, indent=2) + '\n')


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    a.add_argument('project', help='project.json')
    g = a.add_mutually_exclusive_group(required=True)
    g.add_argument('--cache', help='the viewer cache, to find the export by its SHA-256')
    g.add_argument('--export', help='the export (scene.json) of the source map')
    a.add_argument('--out', required=True, help='the patchtool spec to write')
    a.add_argument('--report', help='the report to write (default: next to the spec, <spec>-report.json)')
    a.add_argument('--stream-only', action='store_true',
                   help='a plain streamed patch, without shipAs: a relit variant ships the map (EXP-17)')
    a.add_argument('--family', action='append', default=[], choices=sorted(FAMILIES), metavar='FAMILY',
                   help='build this family although it isn\'t switched on yet (an experiment); repeat for more')
    a.add_argument('--game', help='the game install, for pieces of other maps (with --cache: the library is there)')
    a.add_argument('--foreign-family', action='append', default=[], choices=sorted(FAMILIES) + ['check'], metavar='FAMILY',
                   help='build this family\'s pieces from other maps although it isn\'t switched on yet; repeat')
    args = a.parse_args(argv)
    with open(args.project, encoding='utf-8') as f:
        doc = json.load(f)
    if args.export:
        export = Path(args.export)
        with open(export, encoding='utf-8') as f:
            scene = json.load(f)
    else:
        try:
            export, scene = find_export(args.cache, doc)
        except ExportMissing as error:
            print('not compiled: %s' % error)
            return 1
    library = Library(args.cache, args.game) if args.cache and args.game else None
    spec, report = compile_project(doc, scene, args.family, library, args.foreign_family)
    report['export'] = str(export)
    out = Path(args.out)
    rep = Path(args.report) if args.report else out.with_name(out.stem + '-report.json')
    write_json(rep, report)
    for d in report['errors']:
        print('error: %s%s' % ('%s: ' % (d.get('entity') or d.get('target') or d.get('record')) if d.get('record') else '', d['message']))
    for d in report['warnings']:
        print('warning: %s%s' % ('%s: ' % (d.get('entity') or d.get('target') or d.get('record')) if d.get('record') else '', d['message']))
    c = report['counts']
    if spec is None:
        print('not compiled: %d error(s); report %s' % (c['errors'], rep))
        return 1
    if args.stream_only:
        spec = stream_only(spec)
    write_json(out, spec)
    lights = c['lights']
    print('compiled %s revision %s: %d moved, %d deleted, %d added; lights: %d changed, %d deleted, %d added, %d area; '
          '%d warning(s); spec %s, report %s'
          % (doc.get('name'), doc.get('revision'), c['moved'], c['deleted'], c['added'], lights['changed'],
             lights['deleted'], lights['added'], lights['area'], c['warnings'], out, rep))
    return 0


if __name__ == '__main__':
    sys.exit(main())
