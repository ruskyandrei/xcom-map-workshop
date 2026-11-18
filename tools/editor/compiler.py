"""The editor's compiler for static pieces (first-editor plan, slice E3).

Turns a saved project (research/editor-contracts.md, schema 1 to 3) and the viewer export of its source map into a
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
carries the per-tile data by the exact move, untested in the game off the grid). Each family is refused until it passes
in the game (ladders, doors with a frame, cars and vans did on 8 November; lights were switched on on 9 November, see
below); `enable` (--family) builds one for an experiment before that. A door's frame edited without its leaf is
a destructible prop of its own. Copies of an assembly carry its family, its id and its grid move to the Build.

Fracturing pieces (walls, storey floors, roof slabs: XComFracLevelActor, XComDecoFracLevelActor) and physics props
(KAsset) build for every project since 9 November 2026: the user switched both on before any game run of them
(research/experiments/EXP-28-fracturing-physics.md: its run 1 passed the same day), so that issues are fixed as they
are found. A fracturing piece is no assembly, but it is checked against the grid move (single_grid_rule): its fragment
columns are saved one to a tile and the Build carries them with the copy, which is exact only for whole tiles, whole
storeys and quarter turns (off the grid: the off-grid warning). A physics prop takes any pose. The Build makes both in the map itself (NATIVE_CLASSES).

Anything else is refused with an error, never built partly or approximately: families not built yet (they name their
milestone), assemblies edited in part, pieces of other levels than the base map's, components offset
from their actor, and records the export lacks. A build is allowed only when the report has no errors.

Lights (private/plans/done/editor-lights-plan.md, L6) are the `light` family: an original placed light moved, turned, changed,
switched off or deleted, a copy of one, or a spot light made from the built-in recipe; and the generated area lights a
moved, copied or deleted glowing piece takes along (its association: export 18's `emitterAttachment`, or the project's
`areaLightBindings`). They go into one `lights` object of the spec, which native_split hands to the Build's writer.
light_rule says which lights may be edited. The family builds for every project since 9 November: the user switched
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
effect_override and effect_add check each against the export's `can` and `why` (export 28) and write the spec's
`effects` and `sounds` objects (moves, deletes, copies), which native_split hands to the Build's writer
(tools/bake/native_effects.py, native_sounds.py); a copy of another map's comes from the library (foreign_effect,
stage FX4) and the Build stages it as a piece of another map. An effect's own pose, delete or follow none takes it out of its
piece's carrying (`carriedEffects`). Both families build for every project since EXP-68 passed (17 November 2026);
a stream's are view only.

Lens flares (LensFlareSource actors; stage FX6b) are the `flare` family, made the same way: an override moves, turns
or deletes one in place, an added record with `kind: flare` copies one (this map's, or another map's through the
library), and they go into the spec's `flares` object, which the Build's tools/bake/native_flares.py makes. A flare
has no values object (its template and colour stay as the map has them). The family builds where it is enabled
(`enable`, --family flare) until its game check.

Rotators are rounded to whole rotation units half away from zero, as the viewer's resolver rounds (game_round); the
report gives each pose's rounding. Each copy's world box (its mesh bounds, turned by the full rotation and scaled) is
in the spec for seed planning; each target's box before the edit is in the report.
"""
import argparse
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
import spawns  # noqa: E402

COMPILER_VERSION = 3
SCHEMA = 'xcom-map-workshop/project'
# 2: pieces' flags (piece flags plan); 3: effects and sounds (overrides and added records of their own: the effects and
# sounds plan, Part C); 4: the spawns plan's (`spawnRules`, SP8; the base map's spawn points' records, SP6 and SP7).
# A project of schema 1 to 3 builds as it did.
SCHEMA_VERSION = 4
READ_VERSIONS = (1, 2, 3, 4)
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
# the spawn points an edit may change (the export's `spawns` kinds), each kind's values, and what a value may be
SPAWN_EDIT_KINDS = ('pod', 'meld', 'dropIn')
SPAWN_VALUE_KEYS = {'pod': ('commander', 'secondary', 'use'), 'meld': ('difficulty', 'destroyedOnTurn', 'spawnGroup'),
                    'dropIn': ()}
SPAWN_WORDS = {'pod': 'a pod', 'meld': 'a Meld point', 'dropIn': 'a drop-in point'}
# the kinds a project copies (SP7: an added record of `kind` pod or meld)
SPAWN_COPY_KINDS = ('pod', 'meld')
CLASS_FAMILY = {'XComLevelActor': 'scenery', 'XComOpacityFadeLevelActor': 'scenery',
                'StaticMeshActor': 'scenery', 'XComDestructibleActor': 'destructible',
                'XComCollectible': 'collectible', 'XComLadder': 'ladder', 'XComInteractiveLevelActor': 'door',
                'XComFracLevelActor': 'fracturing', 'XComDecoFracLevelActor': 'fracturing', 'KAsset': 'physics'}
# The families of assemblies (assemblies()): an edit of one names all its pieces, with one grid move.
ASSEMBLY_FAMILIES = ('ladder', 'door', 'frameless-door', 'car', 'van')
# A flat piece the project adds is expected to give floor (added_floors): no more than FLOOR_THICK high, and with
# HEADROOM clear over a tile (F-71: about 150 units; the game gives no floor to a tile a soldier can't stand on)
FLOOR_THICK, HEADROOM = 40.0, 150.0
# the map's own low scenery past its far sides, on a grid the project grows, is made walkable by the Build (F-100;
# native_copy.SCENERY_LOW, shell.py scenery_to_walk): a level actor no taller than this, within the grid's levels
SCENERY_LOW = 32.0
# The cursor's floors (the export's cursorVolumes, export 20): a building's floor should start within CURSOR_NEAR of
# where one starts. A map with none gets CURSOR_STOREYS even storeys of CURSOR_STOREY from the Build (shell.py).
CURSOR_NEAR, CURSOR_STOREY, CURSOR_STOREYS = 32.0, 192.0, 4
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
# Milestone M1's classes (research/editor-contracts.md, section 6), and the milestone each other class names.
M1_CLASSES = ('XComLevelActor', 'StaticMeshActor', 'XComDestructibleActor', 'XComCollectible')
MILESTONE = {c: FAMILIES[f]['milestone'] for c, f in CLASS_FAMILY.items() if not FAMILIES[f]['builds']}
# The export a project's edits build from (plan 4.1): export 18 has each light's GUIDs and bake membership and the
# area lights' glowing pieces, without which a moved piece could leave its glow's light behind.
EXPORT_MINIMUM = 18
# Effects and sounds (the effects and sounds plan, Part C): their records name actors of the export's `effects` and
# `sounds` (export 28, effects_metadata.py), each with what an edit may do with it (`can`, `why`). EFFECT_CLASSES:
# what each kind is (a lens flare, `flares`, since stage FX6b). An effect that is moved or new is listed by
# each upper floor (index 1 up) one of whose boxes holds its place within EFFECT_SLACK (buildings.SLACK; plan Part D):
# the report's note says which floors it joins and leaves.
EFFECTS_EXPORT = 28
EFFECT_CLASSES = {'effect': ('Emitter',),
                  'sound': ('AmbientSound', 'AmbientSoundSimple', 'AmbientSoundSimpleToggleable', 'AmbientSoundMovable'),
                  'flare': ('LensFlareSource',)}
EFFECT_KINDS = ('effect', 'sound', 'flare')
# each kind's object of the spec and of the native edit (its lane), and what the messages call one
EFFECT_LANES = (('effect', 'effects'), ('sound', 'sounds'), ('flare', 'flares'))
EFFECT_WORDS = {'effect': 'an effect', 'sound': 'a sound', 'flare': 'a lens flare'}
EFFECT_SLACK = 2.0
# the values objects (plan Part C): `follow` (an effect's carrying by the piece it stands on: 'none' once it is moved
# by itself, 'auto' to follow again) is FX3's; the others are stage FX5's, behind the effect-values and sound-values
# families: an effect's `scale` (a multiplier on the size the map gives it), `startsOn` and `parameters` ([{name,
# value}]: a scalar, a vector [x, y, z] or a colour [r, g, b, a], each 0 to 1, by the kind its effect saves it in, else
# by its system's parameter); a sound's `radiusMin`, `radiusMax`, `volume` and `pitch` ([least, most]) and `startsOn`
EFFECT_VALUE_KEYS = {'effect': ('scale', 'startsOn', 'parameters', 'follow'),
                     'sound': ('radiusMin', 'radiusMax', 'volume', 'pitch', 'startsOn')}
EFFECT_FOLLOW = ('none', 'auto')
# what a value may be (refused outside: nothing the game's maps come near; the page's handles and sliders stay well
# inside): an effect's size multiplier, a parameter's magnitude, a sound's radius, volume and pitch
EFFECT_SCALE = (1 / 64, 64.0)
PARAMETER_MAX = 1e6
SOUND_RADIUS_MAX = 65536.0
SOUND_VOLUME_MAX = 16.0
SOUND_PITCH = (1 / 16, 16.0)
# the particle parameter types the editor writes, by the kind of value: what a saved entry's type takes, and the type
# a parameter the effect doesn't save gets from its system's distribution
PARAMETER_TYPES = {'PSPT_Scalar': 'scalar', 'PSPT_Vector': 'vector', 'PSPT_Color': 'colour'}
DISTRIBUTION_TYPES = {'scalar': 'PSPT_Scalar', 'vector': 'PSPT_Vector'}
# Pieces' flags (piece flags plan, P4): read from the export's pieceFlags (export 27; a piece of another map from its
# library record), checked with piece_flags.plan, and built by the Build's writer from the package itself (native_copy
# set_roles). A piece this wide or tall (units) with walking, cover or sight turned off is noted (flags-wall).
FLAGS_EXPORT = 27
FLAGS_WALL = 192.0
LIGHT_METADATA = 1
# The light values an edit may set (plan 9.1), with their ranges (plan 4.2); the cone angles are spot lights' only.
LIGHT_KEYS = ('color', 'brightness', 'radius', 'falloffExponent', 'innerConeAngle', 'outerConeAngle', 'enabled')
CONE_KEYS = ('innerConeAngle', 'outerConeAngle')
LIGHT_RANGES = dict(brightness=(0.0, 100.0), radius=(1.0, 16384.0), falloffExponent=(0.1, 64.0),
                    innerConeAngle=(0.0, 89.0), outerConeAngle=(0.0, 89.99))
# The built-in recipes for lights a map has no template for (plan 3.3, 4.9): kind -> version -> starting values.
# (a point light's, light_factory.POINT_RECIPES, are for prefabs: a prefab's lights are recipe lights, so they need
# no map; prefab plan 5.5. A point light has no cones.)
LIGHT_RECIPES = {'spot': {1: dict(color=[255, 255, 255], brightness=1.0, radius=1024.0, falloffExponent=2.0,
                                  innerConeAngle=0.0, outerConeAngle=44.0, enabled=True)},
                 'point': {1: dict(color=[255, 255, 255], brightness=1.0, radius=1024.0, falloffExponent=2.0, enabled=True)}}
RECIPE_ACTOR = {'spot': 'SpotLight', 'point': 'PointLight'}
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
RECIPE_ROTATION = {'spot': [-16384, 0, 0],      # pointing down, as a placed SpotLight's class default
                   'point': [0, 0, 0]}
# An unresolved area light this near an edited piece's old box (units) is named in a warning (plan 4.8)
AREA_NEAR = 64.0
# The pose rule (plan section 3.2)
TILE, STOREY, QUARTER = 96.0, 64.0, 16384
POSE_SLACK = 0.5         # how far a grid move may miss a whole tile, storey (units) or quarter turn (rotation units)
FRAME_MATCH = 1.0        # how far a door's frame stands from its leaf (units): they stand at one place
PART_AT = 8.0            # how far a car's part its glass names stands from the body (units; Police Station's light bars: 2)
INSTANCE_MATCH = 1.0     # how far apart two parts' moves may be and still be one copy of an assembly (units)
# The game counts every collectible in the level's actor list at the end of a mission as loot, an intact one as its
# item and a damaged or destroyed one as the damaged item (XGBattle.CollectLoot, the native CollectCollectibles). The
# Build's copy is a collectible in that list; a piece it hides is taken out of the list.
COLLECTIBLE = 'XComCollectible'
# A piece in a building floor's cutaway (its m_aCachedActors): the Build puts its copy in the cutaway of the floor it
# stands in (tools/bake/native_copy.py edit_floor_caches, plan step G7). From export 15 the export holds the floor
# volumes' boxes and the compiler tells whether the copy stands in a floor (floor_note); before, it can't.
FLOOR_NOTE = ("%s is in a building floor's cutaway: its copy joins the cutaway of the floor it stands in, and has none "
              "outside every building")
LOOT_NOTES = {
    'add': '%s copies a collectible: the copy counts as mission loot too, as the original does',
    'move': '%s is a collectible (mission loot): moved, it still counts once',
    'delete': '%s is a collectible (mission loot): deleted, it no longer counts',
}
# An added piece naming a partner that isn't a car's is refused with the car's milestone.
PARTNER_MILESTONE = FAMILIES['car']['milestone']
NAME_BASE = 900
# UDK's Save As stops at a warning for package names over 30 characters (findings register T-09).
NAME_LIMIT = 30
# the names Windows keeps for devices (CON, NUL, COM1...): no file can have one, with any extension
DEVICE_NAMES = {'CON', 'PRN', 'AUX', 'NUL', *('COM%d' % i for i in range(1, 10)), *('LPT%d' % i for i in range(1, 10))}
ACTOR_NAME = re.compile(r'^[A-Za-z_]\w*$')
# Pieces that can break in the game and be linked to break together: destructible props (collectibles build as such).
BREAKABLE = ('XComDestructibleActor', 'XComCollectible')
# Cover blocks that break with their group (the Build makes them as hidden props), blockers too; an invisible floor
# does not.
BREAKING_COVERS = ('high', 'low', 'block')
EPS_LOCATION = 1e-4      # the document's location precision
IDENTITY = transform([0, 0, 0], [0, 0, 0], [1, 1, 1])
# The landing zone's pieces (F-45): LWR's landing-zone mutator (XComLZMutator.RespawnLZObjects) spawns the landing zone
# with the map's own pieces of these prefabs as templates (the dropship's soldier-spawn markers, the grounded Skyranger),
# so a moved or deleted one (hidden in the variant) breaks the landing. They are gameplay pieces, not scenery: they can
# be copied, never moved or deleted, and the editor's floor brush leaves them alone (private/plans/done/floor-brush-plan.md,
# 3.4 and 4.4). Told by archetype, the prefab the piece was placed from.
LANDING_PREFIXES = ('dgn_dropshipsoldierspawn.', 'veh_lv1skyranger_mod.prefabs.')
# Copies the editor's Build makes as new actors of the variant map (tools/bake/native_copy.py, baker step L4): every
# M1 class, linked in the map when they break together. A collectible's copy is a collectible, so it counts as
# mission loot as its original does (the copier's copy, XComMapEdDestructible, would not). The Build also takes the
# hidden pieces out of the map itself, so an M1 edit needs no patch. Fracturing pieces and physics props are made there
# too (9 November 2026): the copier has no recipe for either on its own.
NATIVE_CLASSES = ('XComLevelActor', 'XComOpacityFadeLevelActor', 'StaticMeshActor', 'XComDestructibleActor', 'XComCollectible',
                  'XComFracLevelActor', 'XComDecoFracLevelActor', 'KAsset')


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


def finite(v, n):
    return isinstance(v, list) and len(v) == n and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                                                       and math.isfinite(x) for x in v)


def world_box(obj, meshes, location, rotation):
    """The world box [x0, x1, y0, y1, z0, z1] of one component placed at the actor pose given."""
    b = meshes[obj['mesh']]['bounds']
    m = multiply(transform(location, rotation, obj['scale']), obj.get('componentTransform') or IDENTITY)
    pts = []
    for sx, sy, sz in product((-1, 1), repeat=3):
        v = [b[0] + sx * b[3], b[1] + sy * b[4], b[2] + sz * b[5]]
        pts.append([sum(m[i][k] * v[k] for k in range(3)) + m[i][3] for i in range(3)])
    return [min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts),
            min(p[2] for p in pts), max(p[2] for p in pts)]


def is_landing(obj):
    """Whether an export's piece is one of the map's landing-zone pieces (LANDING_PREFIXES, by its archetype)."""
    return str(obj.get('archetype') or '').casefold().startswith(LANDING_PREFIXES)


def landing_actors(scene):
    """The actors (paths) of the map's own landing-zone pieces: its base level's pieces is_landing tells."""
    return sorted({o['actor'] for o in scene.get('objects') or [] if o.get('layer') == 'base' and is_landing(o)})


def original_key(t):
    """The viewer's key for an original piece in a group: its target."""
    return 'orig|%s|%s|%s' % (t.get('package'), t.get('level'), t.get('actor'))


def member_key(m):
    """The viewer's key for a group member: an added piece by its output name ({added}), an original by its target
    ({package, level, actor}), another group by its id ({group}: groups nest; prefab plan 5.4), one of the project's
    buildings by its id ({building}; plan 5.4a); None if it is none. A light is a member as a piece is."""
    if isinstance(m, dict) and set(m) == {'building'} and isinstance(m['building'], str):
        return 'building|' + m['building']
    if isinstance(m, dict) and set(m) == {'group'} and isinstance(m['group'], str):
        return 'group|' + m['group']
    if isinstance(m, dict) and set(m) == {'added'} and isinstance(m['added'], str):
        return 'added|' + m['added']
    if isinstance(m, dict) and set(m) == {'package', 'level', 'actor'} and all(isinstance(v, str) for v in m.values()):
        return original_key(m)
    return None


def union(boxes):
    return [min(b[0] for b in boxes), max(b[1] for b in boxes), min(b[2] for b in boxes), max(b[3] for b in boxes),
            min(b[4] for b in boxes), max(b[5] for b in boxes)]


def tidy(v, places=4):
    v = round(v, places)
    return 0.0 if v == 0 else v


def is_identity(m):
    return all(abs(m[i][j] - IDENTITY[i][j]) < 1e-6 for i in range(4) for j in range(4))


# ---------------------------------------------------------------- the pose rule (plan section 3.2)
def turned(v, turns):
    """(x, y) turned by `turns` quarter turns of yaw, as the game turns an actor (+yaw takes X towards Y,
    export_math.transform)."""
    x, y = v[0], v[1]
    for _ in range(turns % 4):
        x, y = -y, x
    return x, y


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


def source_floor_match(buildings, floors, before, location, rotation):
    """The source building a building of the project comes from, as seen from one piece taken from that source: the
    source's buildings (an export's: floors with boxes {min, max}) carried by the piece's move (from its source pose
    `before` {location, rotation} to `location`, `rotation`, a whole number of quarter turns), each floor paired with
    the project floor its boxes overlap most. `floors`: the project building's ([{boxes: [[x0, y0, z0, x1, y1, z1]]}]).
    The source building chosen is the one that overlaps the project building most, and it must pair its floors with
    distinct project floors (one at least). Returns dict(building, floor_map: [project floor or None per source floor],
    moved: the source's floors carried, [[[x0, y0, z0, x1, y1, z1]]]) or None. The boxes may have been edited since:
    the piece keeps what its map saved where the rule agrees (buildings.carried). web/floors.js sourceFloorMatch is
    the twin; both pass tests/source_floor_match_cases.json."""
    pitch, yaw, roll = [(a - b + 32768) % 65536 - 32768 for a, b in zip(rotation, before['rotation'])]
    turns = game_round(yaw / QUARTER)
    if max(abs(pitch), abs(roll), abs(yaw - turns * QUARTER)) > POSE_SLACK:
        return None
    origin = [*turned(before['location'][:2], turns), before['location'][2]]
    shift = [v - origin[k] for k, v in enumerate(location)]

    def move(point):
        return [v + shift[k] for k, v in enumerate((*turned(point[:2], turns), point[2]))]

    def carry(box):
        a, b = move(box['min']), move(box['max'])
        return [min(v, w) for v, w in zip(a, b)] + [max(v, w) for v, w in zip(a, b)]

    def meet(p, q):
        n = 1.0
        for j in range(3):
            n *= max(0.0, min(p[j + 3], q[j + 3]) - max(p[j], q[j]))
        return n

    best = None
    for b in buildings:
        if not b.get('floors'):
            continue
        moved = [[carry(x) for x in f.get('boxes') or []] for f in b['floors']]
        floor_map, used, total, fine = [], set(), 0.0, True
        for boxes in moved:
            pick, most = None, 0.0
            for j, g in enumerate(floors):
                got = sum(meet(x, y) for x in boxes for y in g['boxes'])
                if got > most:
                    pick, most = j, got
            if pick is not None and pick in used:
                fine = False
            if pick is not None:
                used.add(pick)
            floor_map.append(pick)
            total += most
        if not fine or not used or (best and total <= best[0]):
            continue
        best = (total, dict(building=b, floor_map=floor_map, moved=moved))
    return best[1] if best else None


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
            # a van's own building lists its parts, and whatever else touches its floor volumes (on Bar, a skid
            # mark under one); a car parked in a building is a small part of that building's pieces
            van = any(m and len(m & set(members)) * 2 > len(m) for m in owned)
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
        if owned and any(len(owned & members) * 2 > len(owned) for members in vans.values()):
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
        return ('the export of %s has no area-light associations (which glowing piece made each generated light): %s'
                % (scene.get('name'), how))
    return None


def light_rule(light):
    """None for a light an edit may change, else why it is view only (plan 3.2). The page shows the same verdicts
    (families.json `lightRules`)."""
    role, kind = light.get('role'), light.get('kind')
    if light.get('layer') != 'base':
        return "it is a light of a streamed level (a patch's own)"
    if role == 'area':
        return 'it was made by the bake for a glowing surface: it follows its glowing piece'
    if role == 'toggleable':
        who = ', '.join(light.get('referencedBy') or []) or 'a destructible'
        return 'it is lit live and switched by %s; moving it means relighting its shadow maps (a later step)' % who
    if role in ('dominant', 'sky') or kind in ('directional', 'sky'):
        return 'it is the sun, moon or sky: these come with the time of day, a later step'
    if role != 'static' or kind not in ('point', 'spot'):
        return 'it is not a placed point or spot light'
    if 'lightmapGuid' not in light or 'bakedInto' not in light:
        return 'the export lacks its light data (export 18)'
    if light.get('referencedBy'):
        return "it is named by the map's Kismet (%s)" % '; '.join(light['referencedBy'])
    if light.get('channels'):
        return 'it lights only the lighting channels it picks'
    if not light.get('bakedInto'):
        return 'it is in no lightmap: the bake never used it'
    return None


def light_values(light):
    """A light record's editable values in the package's terms (plan 9.1): colour bytes, not the export's 0-1."""
    out = dict(color=[int(round(v * 255)) for v in (light.get('color') or [1, 1, 1])[:3]],
               brightness=light.get('brightness'), enabled=bool(light.get('enabled')))
    if light.get('kind') in ('point', 'spot'):
        out.update(radius=light.get('radius'), falloffExponent=light.get('falloffExponent'))
    if light.get('kind') == 'spot':
        out.update(innerConeAngle=light.get('innerConeAngle'), outerConeAngle=light.get('outerConeAngle'))
    return out


# an error's `record` when it is one piece's: that piece is left out, the build goes on (Compiler.error)
PIECE_RECORD = re.compile(r'^(overrides|added)\[\d+\]$')


def light_value_problem(key, value):
    """Why a submitted light value is out of its range (plan 4.2), or None."""
    if key == 'color':
        if not (isinstance(value, list) and len(value) == 3 and all(isinstance(v, int) and not isinstance(v, bool)
                                                                      and 0 <= v <= 255 for v in value)):
            return 'color must be three whole numbers 0 to 255'
        return None
    if key == 'enabled':
        return None if isinstance(value, bool) else 'enabled must be true or false'
    lo, hi = LIGHT_RANGES[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return '%s must be a number' % key
    if not lo <= value <= hi:
        return '%s must be %g to %g' % (key, lo, hi)
    return None


def reach_box(location, radius):
    return [tidy(v, 3) for c in location for v in (c - radius, c + radius)]


def rotator_of(m):
    """The rotator [pitch, yaw, roll] (whole units, -32768..32767) of a 4 x 4 transform's rotation (export_math's
    convention: its columns are the rotator's X, Y and Z axes)."""
    x = [m[i][0] for i in range(3)]
    pitch = math.atan2(x[2], math.hypot(x[0], x[1]))
    yaw = math.atan2(x[1], x[0])
    roll = math.atan2(-m[2][1], m[2][2])
    unit = lambda a: int(game_round(a * 32768 / math.pi)) % 65536  # noqa: E731
    return [(v + 32768) % 65536 - 32768 for v in (unit(pitch), unit(yaw), unit(roll))]


def moved_light_pose(location, rotation, move):
    """A light's pose carried by a rigid move (rigid_move: the owner's before to after): lightAfter = M · lightBefore.
    A move that only turns about Z adds its turn to the light's yaw, keeping its stored rotator exactly otherwise."""
    loc = [tidy(sum(move[i][k] * location[k] for k in range(3)) + move[i][3]) for i in range(3)]
    if all(abs(move[i][2] - (1.0 if i == 2 else 0.0)) < 1e-9 for i in range(3)):
        dyaw = game_round(math.atan2(move[1][0], move[0][0]) * 32768 / math.pi)
        return loc, [int(rotation[0]), int(rotation[1]) + int(dyaw), int(rotation[2])]
    return loc, rotator_of(multiply(move, transform([0, 0, 0], rotation, [1, 1, 1])))


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
        self.break_copies, self.break_originals, self.group_report = {}, [], []
        self.moves = []          # each assembly's copy: id, family, members (labels), turns, translation
        # light edits (plan 9.5): the spec's `lights` object, and what each piece edit does to the area lights
        self.light_ops = dict(deletes=[], changes=[], adds=[], area=[])
        self.owner_edits = []    # (kind, owner actor path, owner entity, rigid move or None, where)
        self.covers = []         # cover blocks: the spec's `covers` object (cover_add)
        self.ladder_jobs = []    # moved and copied ladders whose climb is still to be checked (ladder_climbs)
        self.cover_members = set()   # their group member keys ('added|' and the output name)
        self.cover_by_member = {}    # member key -> its block in self.covers
        self.light_members = set()   # the same for the lights the project adds
        # effects and sounds (the effects and sounds plan, Part C): the spec's `effects` and `sounds` objects (moves,
        # deletes, copies), the group member keys of the ones the project adds, and the effects a record of the
        # project's own takes from the piece that carries them (they leave carriedEffects)
        self.effect_ops = {k: dict(moves=[], deletes=[], copies=[], values=[]) for k in EFFECT_KINDS}
        # the base map's spawn points moved or given values (the editor spawns plan, SP6): the spec's `spawns` object
        self.spawn_ops = dict(moves=[], deletes=[], copies=[], values=[])
        self.pod_index = None      # the next free pod index for a copy (free_pod_index)
        self.effect_members = set()
        self.effect_own = set()
        self.new_buildings = []      # buildings made from nothing: the spec's `buildings` object (buildings())
        self.building_edits = []     # the map's own buildings changed or deleted: the spec's `buildingEdits` object
        self.floor_sources = {}
        self.donor_buildings = {}
        self.untried_foreign = {}    # (package folded, actor path) of the pieces of other maps built untried
        # pieces' flags (piece flags plan): the map's own pieces whose flags change where they stand (the spec's
        # `pieceFlags` object), the actors whose floor such an edit takes away or gives, and the report's counts
        self.flag_edits = []
        self.floor_off, self.floor_on = set(), {}
        self.flag_counts = dict(requested=0, applied=0, leftOut=0, roles={r: 0 for r in piece_flags.ROLES}, companions=0)

    # ---------------------------------------------------------------- diagnostics
    def error(self, code, message, **where):
        row = dict(code=code, message=message, **where)
        (self.left_out if PIECE_RECORD.match(str(where.get('record') or '')) else self.errors).append(row)

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
        self.spawn_actors = {r['actor']: r for r in self.scene.get('spawns') or [] if isinstance(r, dict) and r.get('actor')}
        self.building_names = {b.get('id'): b.get('name') for b in self.scene.get('buildings') or []}
        self.object_boxes = None
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
        cls = parts[0]['actorClass']
        if cls.endswith('Volume'):
            self.error('not-a-piece', '%s is a mesh of the map\'s %s, which is no piece: a volume is not moved or '
                       'copied (the level volume holds the map\'s tile data)' % (short(actor), cls), actorClass=cls, **where)
            return None
        return self.untried()

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
        self.donor_buildings[donor_key] = record.get('buildings', [])
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

    # ---------------------------------------------------------------- pieces' flags (piece flags plan)
    def flags_valid(self, rec, where):
        """Whether a record's `flags` (if any) is well formed: an object of known roles, each strictly true or false,
        never empty. A malformed one leaves the record out, as any malformed field does."""
        if 'flags' not in rec:
            return True
        f = rec['flags']
        if isinstance(f, dict) and f and all(k in piece_flags.ROLES for k in f) and all(isinstance(v, bool) for v in f.values()):
            return True
        self.error('malformed', 'flags must name walking, cover, sight, floor or mouse, each true or false (it has %r)'
                   % (f,), **where)
        return False

    def flag_plan(self, src, flags, name, where, box=None):
        """(the request applied, piece_flags.plan) of a piece's flags against its settings as the export has them, or
        (None, None) with a warning when they can't be checked (the piece is built without them). Roles the class
        doesn't have are noted and dropped; a request a prop's gate makes ambiguous (a hand-edited file: the page
        asks) is a warning and nothing of it is built. box: the piece's world box where it ends up (a copy's), else
        the one where it stands."""
        self.flag_counts['requested'] += 1
        record = src.get('pieceFlags')
        cls = src.get('actorClass')
        if not record:
            why = ('the flags are not a setting of %s %s' % ('an' if str(cls)[:1] in 'AEIOUX' else 'a', cls)
                   if piece_flags.family_of(cls) is None else
                   'its export predates pieces\' flags (export %d): open the map in the editor to prepare it again, then '
                   'build' % FLAGS_EXPORT)
            self.warn('flags-unavailable', '%s\'s flags are not built: %s' % (name, why), **where)
            self.flag_counts['leftOut'] += 1
            return None, None
        raw, assumed = piece_flags.raw_of(record)
        plan = piece_flags.plan(cls, raw, flags, assumed)
        for role, why in sorted(plan['unsupported'].items()):
            self.note('flags-unsupported', '%s: %s is not built (%s)' % (name, piece_flags.LABELS.get(role, role), why),
                      role=role, **where)
        if plan['conflicts']:
            self.warn('flags-conflict', '%s\'s flags are not built: %s' % (name, '; '.join(plan['conflicts'].values())),
                      **where)
            self.flag_counts['leftOut'] += 1
            return None, None
        for role, why in sorted(plan['unmet'].items()):
            self.note('flags-limited', '%s: %s' % (name, why), role=role, **where)
        applied = {k: v for k, v in flags.items() if k not in plan['unsupported']}
        if not applied:
            self.flag_counts['leftOut'] += 1
            return None, None
        changed = [r for r in piece_flags.ROLES if plan['after'][r] != plan['before'][r]]
        if record.get('collides') is False and changed:
            self.note('flags-no-collision', '%s collides with nothing, so no trace of the game meets it: its %s take effect '
                      'only if it gets collision (the Build\'s floor for low scenery on a grown map gives some)'
                      % (name, ' and '.join(piece_flags.LABELS[r] for r in changed)), **where)
        elif record.get('bodySetup') is False and any(r in changed for r in ('walking', 'cover', 'sight')):
            self.note('flags-limited', '%s\'s mesh has no simple collision (BodySetup): the pathing, cover and sight sweeps '
                      'pass through it whatever its flags say' % name, **where)
        opened = [r for r in ('walking', 'sight') if plan['after'][r] == 'off' and plan['before'][r] != 'off']
        if cls == 'XComInteractiveLevelActor' and opened:
            self.note('flags-door', '%s is a door with %s off: units %s through it when it is shut too'
                      % (name, ' and '.join(piece_flags.LABELS[r] for r in opened),
                         ' and '.join(dict(walking='walk', sight='see')[r] for r in opened)), **where)
        if box is None:
            box = self.boxes([src], src['location'], src['rotation']) if src.get('mesh') in self.meshes else None
        if flags.get('walking') is True and plan['after']['walking'] in ('on', 'partial') and record.get('collides') is not False \
                and piece_flags.low_piece(box, (tile_corner(self.scene.get('tileGrid')) or [None] * 3)[2]):
            corner = tile_corner(self.scene.get('tileGrid'))[2]
            reach = box[5] - (corner + piece_flags.LEVEL * math.floor((box[4] + 8 - corner) / piece_flags.LEVEL))
            self.warn('flags-low', '%s is too low for Blocks walking to stop anyone: it reaches %d over the bottom of its '
                      'level, under the %d the game\'s tiles need, so its tiles are only partly occupied and units still '
                      'walk into them' % (name, round(reach), piece_flags.STOPS_FROM), **where)
        if box and any(plan['after'][r] == 'off' and plan['before'][r] != 'off' for r in ('walking', 'cover', 'sight')) \
                and (cls in ('XComFracLevelActor', 'XComDecoFracLevelActor') or max(box[1] - box[0], box[3] - box[2], box[5] - box[4]) > FLAGS_WALL):
            self.note('flags-wall', '%s is a large piece (or a fracturing wall) that no longer blocks %s: units may walk or see '
                      'through what looks solid' % (name, ' or '.join(piece_flags.LABELS[r].split()[-1] for r in ('walking', 'cover', 'sight')
                                                                     if plan['after'][r] == 'off' and plan['before'][r] != 'off')), **where)
        self.flag_counts['applied'] += 1
        self.flag_counts['companions'] += len(plan['companions'])
        for r in changed:
            self.flag_counts['roles'][r] += 1
        return applied, plan

    def stationary_flags(self, target, parts, flags, where):
        """An original's flags changed where it stands (no move): the spec's `pieceFlags` entry, written in the map by
        the Build (native_copy set_roles), with its box for the tiles it rebuilds."""
        src, name = parts[0], short(target['actor'])
        applied, plan = self.flag_plan(src, flags, name, where)
        if applied is None:
            return
        box = self.boxes(parts, src['location'], src['rotation'])
        if plan['after']['floor'] == 'off' and plan['before']['floor'] == 'on':
            self.floor_off.add(target['actor'])
            owned = sum(1 for f in ((self.scene.get('tactical') or {}).get('floorTiles') or []) if f.get('actor') == target['actor'])
            if owned:
                self.warn('flags-floor', '%s is no floor now: the %d tiles it is the floor of lose it unless another piece '
                          'gives floor there; the landing, mission and ladder checks count without it' % (name, owned),
                          tiles=owned, **where)
        elif plan['after']['floor'] == 'on' and plan['before']['floor'] != 'on':
            self.floor_on[target['actor']] = (name, box)
        self.flag_edits.append(dict(name=name, target=target['actor'], flags=applied, box=[tidy(v, 3) for v in box],
                                    tiles=plan['tiles'], actorClass=src['actorClass']))
        self.entities.append(dict(kind='flags', target=target['actor'], actorClass=src['actorClass'], flags=applied,
                                  before=plan['before'], after=plan['after'], writes=[list(w) for w in plan['writes']],
                                  companions=plan['companions'], tiles=plan['tiles']))

    def copy_flags(self, copy, src, flags, name, where):
        """A copy's flags (a moved original's, an added piece's): its request goes with the copy, which the Build
        writes once it is made."""
        applied, plan = self.flag_plan(src, flags, name, where, copy.get('box'))
        if applied is None:
            return
        copy['flags'] = applied
        copy['floorAfter'] = plan['after']['floor'] if src.get('pieceFlags', {}).get('collides') is not False else None
        copy['flagPlan'] = dict(before=plan['before'], after=plan['after'], companions=plan['companions'],
                                writes=[list(w) for w in plan['writes']])

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

    def boxes(self, parts, loc, rot):
        return union([world_box(p, self.meshes, loc, rot) for p in parts])

    # ---------------------------------------------------------------- ladders (plan section 5)
    def cursor_storeys(self):
        """The cursor's floors of the map: [(floor, [x0, y0, z0, x1, y1, z1])], or None when the export predates them
        (export 20). A map with no cursor volumes, or a cleared one, gets the ones the Build's shell stage gives it:
        even storeys from the tile grid's bottom over the whole map, the last one up to the grid's top. A map as it
        is that keeps its own and is given a larger grid has them as shell.py grow_cursors leaves them: those
        reaching the old far X or Y side stretched to the new one, and with more levels even storeys over the whole
        grid from the top of its own up to the new top, with the floors after its highest. Stair volumes are left
        out. web/floors.js cursorStoreys is the twin."""
        if (self.scene.get('exporterVersion') or 0) < 20:
            return None
        volumes = self.scene.get('cursorVolumes') or []
        own = [(v.get('floor'), list(v['box']['min']) + list(v['box']['max'])) for v in volumes if v.get('box') and not v.get('stair')]
        grid = self.scene.get('tileGrid') or {}
        if not grid.get('origin'):
            return own
        if (own or volumes) and not getattr(self, 'cleared', False):
            return self.grown_storeys(own, grid)
        bottom = float(grid['origin'][2])
        levels = (getattr(self, 'stage_grid', None) or grid['dimensions'])[2]
        top = bottom + levels * grid['size'][2]
        # (a grid made taller gets a storey more for each 192 units: shell.py clones the last)
        storeys = max(CURSOR_STOREYS, round((top - bottom) / CURSOR_STOREY))
        return [(n + 1, [-1e9, -1e9, bottom + CURSOR_STOREY * n, 1e9, 1e9,
                         max(top, bottom + CURSOR_STOREY * (n + 1)) if n == storeys - 1 else bottom + CURSOR_STOREY * (n + 1)])
                for n in range(storeys)]

    def grown_storeys(self, own, grid):
        """The map's own cursor floors `own` [(floor, box)] on the project's grid (cursor_storeys; shell.py
        grow_cursors is what the Build does)."""
        stage = getattr(self, 'stage_grid', None)
        if not stage:
            return own
        o, n, size = grid['origin'], grid['dimensions'], grid['size']
        old = [o[k] + n[k] * size[k] for k in range(3)]
        new = [o[k] + stage[k] * size[k] for k in range(3)]
        out = []
        for floor, b in own:
            b = list(b)
            for k in (0, 1):
                if b[k + 3] >= old[k] - 1.0 and new[k] > b[k + 3]:
                    b[k + 3] = new[k]
            out.append((floor, b))
        if own and new[2] > old[2] + 1e-3:
            top = max(b[5] for _, b in own)
            highest = max(f or 0 for f, _ in own)
            if new[2] > top + 32.0:
                count = max(1, round((new[2] - top) / CURSOR_STOREY))
                for k in range(count):
                    bottom = top + CURSOR_STOREY * k
                    out.append((highest + 1 + k, [o[0], o[1], bottom, new[0], new[1],
                                                  new[2] if k == count - 1 else bottom + CURSOR_STOREY]))
        return out

    def added_floors(self):
        """The floor the copies made so far are expected to give (prefab plan, stage B2): ({tile: the copy's label},
        {tile: (the copy's label, what hangs over it)}). A copy counts when it is flat (no more than FLOOR_THICK
        high): each tile whose centre it covers, at the level of its top, is floor if nothing else the project adds
        hangs less than HEADROOM over it there (F-71: the game gives no floor to a tile without standing room);
        the second answer holds the tiles that fail that. It is a guess from the drawn boxes: the game goes by the
        piece's collision, and whether a piece can be stood on is the piece's own."""
        grid = self.scene.get('tileGrid') or {}
        origin, dims = grid.get('origin'), grid.get('dimensions')
        if not origin:
            return {}, {}
        # the levels as the project has them: a grid grown up has floor on its new levels too (once stage() has run)
        levels = max(dims[2], (getattr(self, 'stage_grid', None) or [0, 0, 0])[2]) if dims else None
        waiting = {id(job[0]) for job in self.ladder_jobs}
        # (a copy whose flags make it no floor, and that collides, gives none: piece flags plan, 6.1)
        flat = [c for c in self.copies if c.get('box') and not c.get('ladder') and c.get('actorClass') != 'XComLadder'
                and id(c) not in waiting and c.get('floorAfter') != 'off']
        # the map's own pieces the project's flags make floor where they stand
        flat += [dict(box=[b[0], b[1], b[2], b[3], b[4], b[5]], label=name) for name, b in getattr(self, 'floor_on', {}).values()]
        # an invisible floor is made to carry floor (EXP-32): a plate with its top at its place
        flat += [c for c in self.covers if c.get('kind') == 'floor']
        tiles, blocked = {}, {}
        for c in flat:
            b = c['box']
            if b[5] - b[4] > FLOOR_THICK:
                continue
            z = int(math.floor((b[5] + 2.0 - origin[2]) / 64.0))
            if z < 0 or (levels and z >= levels):
                continue
            for x in range(int(math.ceil((b[0] - origin[0]) / 96.0 - 0.5)), int(math.floor((b[1] - origin[0]) / 96.0 - 0.5)) + 1):
                for y in range(int(math.ceil((b[2] - origin[1]) / 96.0 - 0.5)), int(math.floor((b[3] - origin[1]) / 96.0 - 0.5)) + 1):
                    cx, cy = origin[0] + 96.0 * (x + 0.5), origin[1] + 96.0 * (y + 0.5)
                    over = next((o for o in flat if o is not c and o['box'][0] <= cx <= o['box'][1] and o['box'][2] <= cy <= o['box'][3]
                                 and b[5] + 8.0 < o['box'][4] < b[5] + HEADROOM), None)
                    if over:
                        blocked[(x, y, z)] = (c['label'], over['label'])
                    else:
                        tiles[(x, y, z)] = c['label']
        return tiles, blocked

    def floor_headroom(self):
        """The warning for a flat piece the project adds with less than standing room over some of its tiles (F-71)."""
        _, blocked = self.added_floors()
        by_piece = {}
        for tile, (label, over) in sorted(blocked.items()):
            by_piece.setdefault((label, over), []).append(list(tile))
        for (label, over), tiles in sorted(by_piece.items()):
            self.warn('floor-headroom', '%s has %s less than %d units over %d of its tiles: the game gives no floor to a tile a '
                      'soldier can\'t stand on, so they won\'t be walked on' % (label, over, HEADROOM, len(tiles)), tiles=tiles[:12])

    def ladder_ends(self, name, src, loc, rot, where):
        """A ladder copy's climb at its pose (ladders.ends against the export's original floor tiles and the floor the
        project's own flat pieces are expected to give, added_floors): dict(foot, top) tiles, top being the linked top
        tile T′ that the Build rebuilds first, or None with the warning ladder-climb (the ladder is built all the same,
        as a piece with no climb: the check goes by drawn boxes, and warns rather than refuses). An end that counts on
        a floor the project adds is warned of (ladder-new-floor): that floor is made by the game's rebuild, where the
        piece can be stood on. Run by ladder_climbs, once every copy, cover block and the stage are known."""
        grid = self.scene.get('tileGrid') or {}
        extent = ladders.extent_z(dict(meshes=self.meshes), src)
        if not self.floors or not grid.get('origin') or extent is None:
            self.warn('ladder-climb', 'the export of %s has no floor data to check %s\'s ends against: it is built with no '
                      'climb of its own' % (self.map, name), family='ladder', **where)
            return None
        new, _ = self.added_floors()
        # (the floor of a piece the project's flags make no floor is gone: floor_now)
        floors = self.floors & self.floor_now() if self.floor_off else self.floors
        e = ladders.ends(loc, rot, extent, tile_corner(grid), floors | set(new))
        if e['climbs']:
            counted = sorted({new[t] for t in (tuple(e['footTile']), tuple(e['linkedTop'])) if t not in floors})
            if counted:
                self.warn('ladder-new-floor', '%s climbs to or from a floor this project adds (%s): it will climb if the game '
                          'makes floor of that piece' % (name, ', '.join(counted)), family='ladder', **where)
        if not e['climbs']:
            missing = ' and '.join({'foot': 'its foot tile %s' % e['footTile'],
                                    'top': 'its top tile %s or the one below it' % e['topTile']}[w] for w in e['why'])
            self.warn('ladder-climb', '%s may not climb there: %s %s no floor in the map or under a flat piece of this '
                      'project, and the game makes a ladder\'s climb only between floors' % (name, missing, 'have' if len(e['why']) > 1 else 'has'),
                      family='ladder', ends=dict(foot=e['footTile'], top=e['topTile']), **where)
            return None
        return dict(foot=e['footTile'], top=e['linkedTop'])

    def ladder_climbs(self):
        """Each moved or copied ladder's climb (ladder_ends), worked out once the project's copies, cover blocks and
        stage are all known: a ladder may stand on a floor a later record adds, or on a level the grid grew by. The
        map's own ladders that stay are checked too where a flags edit takes a floor away (flags-floor)."""
        jobs, self.ladder_jobs = self.ladder_jobs, []
        for copy, name, src, loc, rot, where in jobs:
            copy['ladder'] = self.ladder_ends(name, src, loc, rot, where)
        if not self.floor_off:
            return
        grid = self.scene.get('tileGrid') or {}
        if not grid.get('origin'):
            return
        lost = {tuple(f['tile']) for f in ((self.scene.get('tactical') or {}).get('floorTiles') or [])
                if f.get('actor') in self.floor_off}
        gone = {e['target'] for e in self.entities if e['kind'] in ('delete', 'move')}
        for o in self.scene.get('objects') or []:
            if o.get('actorClass') != 'XComLadder' or o.get('actor') in gone or o.get('layer') != 'base':
                continue
            extent = ladders.extent_z(dict(meshes=self.meshes), o)
            if extent is None:
                continue
            e = ladders.ends(o['location'], o['rotation'], extent, tile_corner(grid), self.floors)
            ends = [t for t in (e.get('footTile'), e.get('linkedTop')) if t is not None]
            if any(tuple(t) in lost for t in ends):
                self.warn('flags-floor', '%s climbs to or from a floor that a flags edit takes away: it may no longer climb'
                          % short(o['actor']), actor=o['actor'], ends=dict(foot=e.get('footTile'), top=e.get('linkedTop')))

    def flag_ladders(self):
        """The map's own ladders that stay and climb whose foot or top tile is near a piece whose tile flags change
        where it stands (its box with a quarter tile and a tile round it, from the ground to the level over its top):
        the Build rebuilds their top tile first and their foot after, as a moved ladder's, so the climb keeps both its
        links (native_copy.flags_in_place). [{actor, foot, top}], sorted."""
        edits = [e for e in self.flag_edits if e['tiles']]
        grid = self.scene.get('tileGrid') or {}
        if not edits or not self.floors or not grid.get('origin'):
            return []
        corner = tile_corner(grid)
        near = [(math.floor((b[0] - 24.0 - corner[0]) / 96.0) - 1, math.floor((b[1] + 24.0 - corner[0]) / 96.0) + 1,
                 math.floor((b[2] - 24.0 - corner[1]) / 96.0) - 1, math.floor((b[3] + 24.0 - corner[1]) / 96.0) + 1,
                 math.floor((b[5] - corner[2]) / 64.0) + 1) for b in (e['box'] for e in edits)]
        gone = {e['target'] for e in self.entities if e['kind'] in ('delete', 'move')}
        out = []
        for o in self.scene.get('objects') or []:
            if o.get('actorClass') != 'XComLadder' or o.get('layer') != 'base' or o.get('actor') in gone:
                continue
            extent = ladders.extent_z(dict(meshes=self.meshes), o)
            if extent is None:
                continue
            e = ladders.ends(o['location'], o['rotation'], extent, corner, self.floors)
            if not e['climbs']:
                continue
            ends = [tuple(e['footTile']), tuple(e['linkedTop'])]
            if any(x0 <= t[0] <= x1 and y0 <= t[1] <= y1 and t[2] <= z1 for t in ends for x0, x1, y0, y1, z1 in near):
                out.append(dict(actor=short(o['actor']), foot=list(e['footTile']), top=list(e['linkedTop'])))
        return sorted(out, key=lambda l: l['actor'])

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
    def spawn_of(self, target):
        """The base map's spawn point a target {package, level: base, actor} names (export 33's `spawns` record), or
        None."""
        if not isinstance(target, dict) or target.get('level') != 'base' or not isinstance(target.get('actor'), str):
            return None
        if str(target.get('package')).casefold() not in (str(self.map).casefold(), str(getattr(self, 'package', '')).casefold()):
            return None
        return self.spawn_actors.get(target['actor'])

    def spawn_values(self, rec, record, name, where):
        """An override's `spawn` values checked against the point's kind: (values that differ from the map's, ok). A
        pod's `commander`, `secondary` and `use` are true or false; a Meld point's `difficulty` is Easy or Hard, its
        `destroyedOnTurn` a whole number from -1 (never) to 99 and its `spawnGroup` one from 0 to 99. A key of another
        kind is an error; one of no kind is noted and carried. A value the map has already builds nothing."""
        values = rec.get('spawn')
        if values is None:
            return {}, True
        if not isinstance(values, dict):
            self.error('malformed', 'the spawn values of %s must be an object' % name, **where)
            return {}, False
        kind = record['kind']
        allowed = SPAWN_VALUE_KEYS.get(kind, ())
        known = {k for keys in SPAWN_VALUE_KEYS.values() for k in keys}
        out, ok = {}, True
        for key, value in sorted(values.items()):
            if key not in known:
                self.note('unknown-field', 'spawn value %r of %s is not one this editor knows; it is carried and not '
                          'built' % (key, name), **where)
                continue
            if key not in allowed:
                self.error('spawn-values', '%s is %s, which has no %s' % (name, SPAWN_WORDS.get(kind, kind), key), **where)
                ok = False
                continue
            good = (isinstance(value, bool) if key in ('commander', 'secondary', 'use') else
                    value in ('Easy', 'Hard') if key == 'difficulty' else
                    isinstance(value, int) and not isinstance(value, bool) and (-1 <= value <= 99 if key == 'destroyedOnTurn'
                                                                                else 0 <= value <= 99))
            if not good:
                self.error('spawn-values', '%s: %s %r is not a value it can have (%s)' % (name, key, value, dict(
                    commander='true or false', secondary='true or false', use='true or false', difficulty='Easy or Hard',
                    destroyedOnTurn='a whole number from -1, never, to 99', spawnGroup='a whole number from 0 to 99')[key]),
                    **where)
                ok = False
                continue
            have = ((record.get('values') or {}).get(key) or {}).get('value')
            if have != value:
                out[key] = value
        return out, ok

    def spawn_override(self, target, rec, where, record):
        """A base pod, Meld point or drop-in point moved, turned or given values (the editor spawns plan, SP6), in
        place: the Build keeps its actor, so what names it (Kismet, wave groups, pod events by index) still does."""
        kind, name = record.get('kind'), short(target['actor'])
        for f in sorted(set(rec) - {'target', 'location', 'rotation', 'deleted', 'spawn'}):
            self.note('unknown-field', 'field %r is not part of the override of a spawn point and is ignored' % f, **where)
        if kind not in SPAWN_EDIT_KINDS:
            self.error('spawn-view-only', '%s is %s, which the editor shows but doesn\'t change' % (
                name, missions.object_words(record) if kind else 'a spawn record'), **where)
            return
        if not self.builds('spawn'):
            self.error('family', '%s is %s edit. %s' % (name, SPAWN_WORDS[kind], FAMILIES['spawn']['note']),
                       family='spawn', **where)
            return
        if record.get('listed') is False:
            self.error('spawn-unlisted', '%s is not in the level\'s actor list, so the game never has it: there is '
                       'nothing to %s' % (name, 'delete' if rec.get('deleted') is True else 'move'), **where)
            return
        if rec.get('deleted') is True:
            self.spawn_delete(target, rec, where, record)
            return
        if record.get('unread'):
            self.error('spawn-unread', '%s: the export could not read its values (%s), so the Build leaves it as it is'
                       % (name, record['unread']), **where)
            return
        values, ok = self.spawn_values(rec, record, name, where)
        if not ok:
            return
        moved = False
        if 'location' in rec or 'rotation' in rec:
            p = self.pose(dict(location=rec.get('location', record['location']),
                               rotation=rec.get('rotation', record['rotation'])), where)
            if not p:
                return
            loc, rot, rounding = p
            moved = not (all(abs(a - b) < EPS_LOCATION for a, b in zip(loc, record['location']))
                         and rot == [int(v) for v in record['rotation']])
            if moved:
                if record.get('links'):
                    self.note('spawn-links', '%s moves; %s stay where the map has them' % (name, ', '.join(sorted(
                        {'its %s %s' % (lk.get('property'), short(str(lk.get('actor') or ''))) for lk in record['links']}))[:240]),
                        **where)
                self.spawn_ops['moves'].append(dict(name=name, actorClass=record['actorClass'], kind=kind, location=loc,
                                                    rotation=rot, before=dict(location=list(record['location']),
                                                                              rotation=list(record['rotation']))))
                self.entities.append(dict(kind='spawn', op='move', target=target['actor'], actorClass=record['actorClass'],
                                          location=loc, rotation=rot, rotationRounding=tidy(rounding, 6)))
        if values:
            self.spawn_ops['values'].append(dict(name=name, actorClass=record['actorClass'], kind=kind, spawn=values))
            self.entities.append(dict(kind='spawn', op='values', target=target['actor'], actorClass=record['actorClass'],
                                      spawn=values))
        if not moved and not values:
            self.note('unchanged', '%s is as the map has it; nothing to build for it' % name, **where)

    @staticmethod
    def spawn_names(record):
        """What names a base spawn point, in words, as export 33 reads its map: the Kismet that uses it (directly or
        through an object list), a wave system's place, a pod event for its index, another actor's typed reference, and
        what lists it by name."""
        out = []
        for u in record.get('uses') or []:
            by = short(str(u.get('by') or ''))
            how = u.get('how')
            out.append('%s (%s)' % (by, {'direct': 'Kismet', 'indirect': 'Kismet, through an object list',
                                         'wave': 'a wave system\'s place', 'event': 'a pod event for its index',
                                         'typed': 'its %s' % u.get('property', 'reference')}.get(how, how or 'a use')))
        out += ['%s (lists it by name)' % short(str(r)) for r in record.get('referencedBy') or []]
        return sorted(set(out))

    def spawn_delete(self, target, rec, where, record):
        """A base pod, Meld point or drop-in point deleted (the editor spawns plan, SP7): built only when nothing names
        it (spawn_names) and its uses were read; otherwise warning spawn-delete-named, and the point stays."""
        name = short(target['actor'])
        for f in sorted(set(rec) & {'location', 'rotation', 'spawn'}):
            self.note('unknown-field', '%s is deleted, so its %s is ignored' % (name, f), **where)
        names = self.spawn_names(record)
        if record.get('unread') or names:
            why = ('the export could not read what uses it (%s)' % record['unread'] if record.get('unread') else
                   '%s %s' % ('; '.join(names[:4]) + ('; and %d more' % (len(names) - 4) if len(names) > 4 else ''),
                              'names it' if len(names) == 1 else 'name it'))
            self.warn('spawn-delete-named', '%s stays: %s, and a deleted point would leave %s pointing at nothing'
                      % (name, why, 'that' if len(names) <= 1 else 'them'), actor=target['actor'], **where)
            return
        self.spawn_ops['deletes'].append(dict(name=name, actorClass=record['actorClass'], kind=record['kind']))
        self.entities.append(dict(kind='spawn', op='delete', target=target['actor'], actorClass=record['actorClass']))

    def free_pod_index(self):
        """The next pod index no pod of the variant has and no pod event names (a copy's, SP7): above every index the
        base map's pods and its streams' save, every event the export's uses name, and the copies made so far."""
        if self.pod_index is None:
            used = [-1]
            records = list(self.scene.get('spawns') or [])
            for s in (self.scene.get('streams') or {}).values():
                if isinstance(s, dict):
                    records += list(s.get('missionObjects') or []) + list(s.get('spawns') or [])
            for r in records:
                if not isinstance(r, dict):
                    continue
                if r.get('kind') == 'pod':
                    v = ((r.get('values') or {}).get('podIndex') or {}).get('value')
                    if isinstance(v, int) and not isinstance(v, bool):
                        used.append(v)
                for u in r.get('uses') or []:
                    if u.get('how') == 'event' and isinstance(u.get('podId'), int):
                        used.append(u['podId'])
            self.pod_index = max(used) + 1
        index, self.pod_index = self.pod_index, self.pod_index + 1
        return index

    def spawn_add(self, rec, where):
        """A copy of one of the map's pods or Meld points (the editor spawns plan, SP7): the Build clones the template
        (with its components) under the level and sets the copy's own values; a pod's copy gets a free pod index
        (free_pod_index). A copy is made only from a plain template: a pod with no commander or secondary flag, no
        forced type and no link to another actor (so the copy takes no patrol, volume or contingent link); any Meld
        point."""
        out = rec['actor']
        name = short(out)
        kind = rec.get('kind')
        for f in sorted(set(rec) - {'id', 'actor', 'kind', 'from', 'location', 'rotation', 'spawn'}):
            if f in ('components', 'template', 'cover', 'light', 'flags', 'prefab', 'partner', 'tinted', 'effect', 'sound'):
                self.error('malformed', '%s is a copy of %s, so it has no %s' % (name, SPAWN_WORDS[kind], f), **where)
                return
            self.note('unknown-field', 'field %r is not part of an added spawn point and is ignored' % f, **where)
        if not isinstance(rec.get('id'), str) or not rec['id']:
            self.error('malformed', '%s has no id' % name, **where)
            return
        src = rec.get('from')
        template = self.spawn_of(src)
        if template is None:
            self.error('missing', '%s copies %s, which is no spawn point of this map\'s export'
                       % (name, short(str((src or {}).get('actor')))), **where)
            return
        tname = short(src['actor'])
        if template.get('kind') != kind:
            self.error('malformed', '%s says it is %s but copies %s, which is %s' % (
                name, SPAWN_WORDS[kind], tname, SPAWN_WORDS.get(template.get('kind'), template.get('kind'))), **where)
            return
        if not self.builds('spawn'):
            self.error('family', '%s is a copy of %s. %s' % (name, SPAWN_WORDS[kind], FAMILIES['spawn']['note']),
                       family='spawn', **where)
            return
        if template.get('listed') is False or template.get('unread'):
            self.error('spawn-copy-template', '%s copies %s, %s' % (name, tname, 'which is not in the level\'s actor list'
                       if template.get('listed') is False else 'whose values the export could not read (%s)'
                       % template['unread']), **where)
            return
        v = lambda key: ((template.get('values') or {}).get(key) or {}).get('value')  # noqa: E731
        if kind == 'pod':
            why = [w for w, bad in (('the commander\'s place', v('commander')), ('a secondary pod', v('secondary')),
                                    ('of a forced alien type', v('forceType')),
                                    ('linked to %s' % ', '.join(sorted(short(str(lk.get('actor'))) for lk in template.get('links') or [])),
                                     template.get('links'))) if bad]
            if why:
                self.error('spawn-copy-template', '%s copies %s, which is %s: a copy is made only from a plain pod'
                           % (name, tname, ' and '.join(why)), **where)
                return
        values, ok = self.spawn_values(rec, template, name, where)
        if not ok:
            return
        p = self.pose(rec, where)
        if not p:
            return
        loc, rot, rounding = p
        copy = dict(id=rec['id'], name=name, source=tname, kind=kind, actorClass=template['actorClass'], location=loc,
                    rotation=rot)
        if kind == 'pod':
            copy['podIndex'] = self.free_pod_index()
        if values:
            copy['spawn'] = values
        self.spawn_ops['copies'].append(copy)
        self.entities.append(dict(kind='spawn', op='add', entity=out, id=rec['id'], actorClass=template['actorClass'],
                                  template=src['actor'], location=loc, rotation=rot, rotationRounding=tidy(rounding, 6),
                                  **({'podIndex': copy['podIndex']} if kind == 'pod' else {}), **({'spawn': values} if values else {})))

    def light_of(self, target):
        """The export's light a target {package, level, actor} names, or None."""
        if not isinstance(target, dict):
            return None
        return self.lights.get((target.get('package'), target.get('level'), target.get('actor')))

    def overrides(self):
        known = {'target', 'location', 'rotation', 'deleted', 'flags'}
        gated = {}      # an assembly's records: id -> (assembly, {actor: (target, record, where, parts)})
        for k, rec in enumerate(self.doc.get('overrides') or []):
            where = dict(record='overrides[%d]' % k)
            if not isinstance(rec, dict):
                self.error('malformed', 'not a record', **where)
                continue
            target = rec.get('target')
            if isinstance(target, dict) and isinstance(target.get('actor'), str):
                where['target'] = target['actor']
            effect = self.effect_of(target)
            if effect is not None:
                self.effect_override(target, rec, where, effect)
                continue
            light = self.light_of(target)
            if light is not None:
                self.light_override(target, rec, where, light)
                continue
            spawn = self.spawn_of(target)
            if spawn is not None:
                self.spawn_override(target, rec, where, spawn)
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
            if not self.flags_valid(rec, where):
                continue
            parts = self.piece(target, where, deleting=rec.get('deleted') is True)
            if not parts:
                continue
            if 'flags' in rec:
                if rec.get('deleted') is True:
                    self.note('flags-deleted', '%s is deleted, so its flags are not built' % short(target['actor']), **where)
                elif not self.pose_moves(rec, parts[0]):
                    # the piece where the map has it (flags alone, or its own pose): its flags written in place, and
                    # nothing else to build for the record (its assembly's move rule doesn't apply to flags)
                    self.stationary_flags(target, parts, rec['flags'], where)
                    continue
            family, assembly = self.family_of(target['actor'], parts)
            if assembly and family in ASSEMBLY_FAMILIES:
                gated.setdefault(id(assembly), (assembly, {}))[1][target['actor']] = (target, rec, where, parts)
            elif not self.builds(family) and rec.get('deleted') is True:
                # a delete empties the piece's slot in the level's list and needs nothing of its family (Clear map
                # plan, section 6)
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
        """The kinds of mission the project adds (its `missions` entries that name a kind)."""
        listed = self.doc.get('missions')
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
            self.owner_edits.append(('delete', target['actor'], target['actor'], None, where))
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
        self.floor_note(name, src, new, where, old)
        self.owner_edits.append(('move', target['actor'], target['actor'],
                                 rigid_move(src['location'], src['rotation'], loc, rot), where))
        self.copies.append(dict(order=(0, target['actor']), source=name, label='move:' + name, location=loc, rotation=rot, box=new,
                                member=original_key(target), actorClass=src['actorClass'], ladder=None,
                                **{k: v for k, v in extra.items() if k != 'helpers'}))
        if rec.get('flags'):
            self.copy_flags(self.copies[-1], src, rec['flags'], name, where)
        if ladder:
            self.ladder_jobs.append((self.copies[-1], name, src, loc, rot, where))
        self.hides.append(dict(name=name, label='move:' + name, box=old))
        self.entities.append(dict(kind='move', target=target['actor'], actorClass=src['actorClass'], location=loc,
                                  rotation=rot, rotationRounding=tidy(rounding, 6), oldBox=[tidy(v, 3) for v in old],
                                  newBox=[tidy(v, 3) for v in new], **extra))

    def floor_at(self, box, now=True):
        """(building, floor index) whose floor volumes overlap `box` [x0, x1, y0, y1, z0, z1] most, or None (as the
        Build's native_copy.floor_at finds it): among the floors as the project has them (now), or as exported."""
        best, most = None, 0.0
        for building, index, boxes in (self.floor_boxes_now() if now else self.floor_boxes) or []:
            got = 0.0
            for v in boxes:
                inter = 1.0
                for j in range(3):
                    inter *= max(0.0, min(box[2 * j + 1], v['max'][j]) - max(box[2 * j], v['min'][j]))
                got += inter
            if got > most:
                best, most = (building, index), got
        return best

    def floor_boxes_now(self):
        """self.floor_boxes with the map's buildings as the project has them (map buildings plan): a changed one's
        boxes from its record, a deleted one's gone; a record the compiler passes over (map_buildings) changes nothing."""
        if self.floor_boxes is None or getattr(self, '_floor_boxes_now', None) is not None:
            return self.floor_boxes if self.floor_boxes is None else self._floor_boxes_now
        records = {}
        for b in self.doc.get('buildings') or []:
            rep = b.get('replaces') if isinstance(b, dict) else None
            if isinstance(rep, dict) and str(rep.get('package')).casefold() == self.map.casefold() and rep.get('level') == 'base' and isinstance(rep.get('actor'), str):
                records.setdefault(rep['actor'], b)
        usable = self.map_buildings()
        out, done = [], set()
        for name, index, xs in self.floor_boxes:
            rec = records.get(name)
            if rec is None or name not in usable or usable[name][1]:
                out.append((name, index, xs))
                continue
            if name in done:
                continue
            done.add(name)
            if rec.get('deleted'):
                continue
            for k, f in enumerate(rec.get('floors') or []):
                good = [x for x in (f.get('boxes') if isinstance(f, dict) else None) or []
                        if isinstance(x, list) and len(x) == 6 and all(isinstance(v, (int, float)) for v in x)]
                out.append((name, k, [dict(min=list(x[:3]), max=list(x[3:])) for x in good]))
        self._floor_boxes_now = out
        return out

    def floor_note(self, name, src, box, where, old):
        """The building-floor warning for the copy of `src` (a moved piece's, or an added one) standing in `box`, its
        original in `old`: the Build puts the copy of a piece in a floor's cutaway in the cutaway of the floor it stands
        in (plan step G7), or keeps the original's when neither stands in a floor volume (a ladder on an outer wall).
        A van's parts say nothing: their own building goes with them (plan section 7.6)."""
        if (self.assemblies.get(src.get('actor')) or {}).get('family') == 'van':
            return
        if self.floor_boxes is None:
            if src.get('floors'):
                self.note('building-floor', FLOOR_NOTE % name, **where)
            return
        there = self.floor_at(box)
        if src.get('floors') and there is None and self.floor_at(old, now=False) is not None:
            self.note('building-floor', "%s is in a building floor's cutaway; its copy stands in no building floor, so no "
                      "cutaway hides it" % name, **where)
        elif not src.get('floors') and there is not None:
            self.warn('building-floor', "%s is in no building floor's cutaway (it has no floor component); its copy stands "
                      "in floor %d of %s but won't hide or cut down with it" % (name, there[1] + 1, short(there[0])),
                      **where)

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
                 'template', 'cover', 'flags', 'kind', 'effect', 'sound'}
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
                # a pod or a Meld point copied (the editor spawns plan, SP7)
                self.spawn_add(rec, where)
                continue
            if 'kind' in rec:
                # an effect, a sound or a flare copied (the effects and sounds plan, Part C)
                self.effect_add(rec, where)
                continue
            if 'effect' in rec or 'sound' in rec:
                self.error('malformed', '%s copies a piece, so it has no effect or sound values' % short(out), **where)
                continue
            for f in sorted(set(rec) - known):
                self.note('unknown-field', 'field %r is not part of an added piece and is ignored' % f, **where)
            if not self.flags_valid(rec, where):
                continue
            if 'flags' in rec and ('template' in rec or 'cover' in rec or self.light_of(rec.get('from')) is not None):
                self.error('malformed', '%s is a cover block, a floor or a light, whose flags are its own: a record of one '
                           'has no flags' % short(out), **where)
                continue
            if isinstance(rec.get('template'), dict) and rec['template'].get('kind') == 'cover':
                self.cover_add(rec, where)
                continue
            if 'cover' in rec:
                self.error('malformed', '%s has cover values but is not a cover block' % short(out), **where)
                continue
            if 'template' in rec or self.light_of(rec.get('from')) is not None:
                self.light_add(rec, where)
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
        """A copy of a template at its pose."""
        extra = extra or {}
        out = rec['actor']
        loc, rot, rounding = pose
        src = parts[0]
        self.loot(src, short(out), 'add', where)
        if not extra.get('assembly') and self.single_grid_rule(short(out), src, loc, rot, where) is None:
            return
        new = self.boxes(parts, loc, rot)
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
                        self.copy_area_light(light, rec['from']['actor'], out, move, donor)
        else:
            self.floor_note(short(out), src, new, where, self.boxes(parts, src['location'], src['rotation']))
            self.owner_edits.append(('copy', rec['from']['actor'], out,
                                     rigid_move(src['location'], src['rotation'], loc, rot), where))
        self.copies.append(dict(order=(1, out), source=name, label=short(out), location=loc, rotation=rot, box=new,
                                member='added|' + out, actorClass=src['actorClass'], ladder=None, **extra))
        if rec.get('flags'):
            self.copy_flags(self.copies[-1], src, rec['flags'], short(out), where)
        if extra.get('family') == 'ladder':
            self.ladder_jobs.append((self.copies[-1], short(out), src, loc, rot, where))
        self.floor_sources[short(out)] = src
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
        if set(rec['template']) != {'kind', 'version'} or version not in COVER_RECIPES:
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

    # ---------------------------------------------------------------- lights (plan 4.2)
    def light_gate(self, name, where):
        """The family's refusal while it doesn't build (plan 3.4): True when the edit may go on."""
        if self.builds('light'):
            return True
        self.error('family', '%s is a light edit. %s' % (name, FAMILIES['light']['note']), family='light', **where)
        return False

    def submitted_light(self, values, kind, where, name):
        """The submitted light values `values` checked (plan 4.2): dict, or None with an error."""
        if not isinstance(values, dict):
            self.error('malformed', '%s: "light" must be an object of light values' % name, **where)
            return None
        bad = sorted(set(values) - set(LIGHT_KEYS))
        if bad:
            self.error('malformed', '%s: %s %s not a light value (they are %s)' % (
                name, ', '.join(bad), 'is' if len(bad) == 1 else 'are', ', '.join(LIGHT_KEYS)), **where)
            return None
        if kind != 'spot' and set(values) & set(CONE_KEYS):
            self.error('light-value', '%s is a %s light, which has no cone' % (name, kind), **where)
            return None
        values = dict(values)
        for key in sorted(values):
            why = light_value_problem(key, values[key])
            value = values[key]
            if why and key in LIGHT_RANGES and isinstance(value, (int, float)) and not isinstance(value, bool) \
                    and math.isfinite(value) and key not in CONE_KEYS:
                # a number outside its range: built at the nearest value in range, and said (plan R3)
                lo, hi = LIGHT_RANGES[key]
                values[key] = min(max(value, lo), hi)
                self.note('light-clamped', '%s: its %s is %g, outside %g to %g; built as %g'
                          % (name, key, value, lo, hi, values[key]), key=key, stored=value, built=values[key], **where)
            elif why and key in CONE_KEYS and isinstance(value, (int, float)) and not isinstance(value, bool) \
                    and math.isfinite(value):
                continue        # (the two cone angles are taken together, below)
            elif why:
                self.error('light-value', '%s: %s' % (name, why), key=key, **where)
                return None
        cone = [values.get(k) for k in CONE_KEYS]
        if any(k in values and light_value_problem(k, values[k]) for k in CONE_KEYS):
            # a cone out of range lights as its effective cone (a map's stored 100 lights as 89.99): built as that
            from lights import storable_cone
            inner, outer = cone
            if inner is None or outer is None:
                key = CONE_KEYS[0 if inner is not None else 1]
                lo, hi = LIGHT_RANGES[key]
                built = {key: min(max(values[key], lo), hi)}
            else:
                built = dict(zip(CONE_KEYS, storable_cone(inner, outer)))
            for key, value in built.items():
                if value != values[key]:
                    self.note('light-clamped', '%s: its %s is %g, outside %g to %g; built as %g'
                              % (name, key, values[key], *LIGHT_RANGES[key], value), key=key, stored=values[key],
                              built=value, **where)
                values[key] = value
        return values

    def light_after(self, name, kind, before, submitted, where):
        """Every raw value after the edit, the inherited ones as stored (a stored 580-degree cone stays 580): dict, or
        None with an error when an inherited value is malformed or an edited cone's inner is wider than its outer."""
        after = dict(before, **submitted)
        for key in LIGHT_KEYS:
            if key not in after or key in submitted:
                continue
            value = after[key]
            if key == 'color':
                ok = isinstance(value, list) and len(value) == 3
            elif key == 'enabled':
                ok = isinstance(value, bool)
            else:
                ok = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            if not ok:
                self.error('light-value', '%s: its stored %s (%r) is not a value the Build can keep' % (name, key, value),
                           key=key, **where)
                return None
        if kind == 'spot' and set(submitted) & set(CONE_KEYS) and after['innerConeAngle'] > after['outerConeAngle']:
            self.note('light-clamped', '%s: its inner cone (%g) is wider than its outer cone (%g); built with the inner '
                      'cone at %g' % (name, after['innerConeAngle'], after['outerConeAngle'], after['outerConeAngle']),
                      key='innerConeAngle', stored=after['innerConeAngle'], built=after['outerConeAngle'], **where)
            after['innerConeAngle'] = after['outerConeAngle']
            submitted['innerConeAngle'] = after['innerConeAngle']
        return after

    def light_override(self, target, rec, where, light):
        """An original light moved, turned, changed, switched off or deleted (plan 4.2)."""
        name = short(target['actor'])
        for f in sorted(set(rec) - {'target', 'location', 'rotation', 'deleted', 'light'}):
            self.note('unknown-field', 'field %r is not part of an override and is ignored' % f, **where)
        if target['package'].casefold() != self.map.casefold():
            self.error('level', '%s is a light of %s, not of %s' % (name, target['package'], self.map), **where)
            return
        why = light_rule(light)
        if why:
            self.error('light-view-only', '%s is view only: %s' % (name, why), **where)
            return
        before = light_values(light)
        kind = light['kind']
        if rec.get('deleted') is True:
            if not self.light_gate(name, where):
                return
            self.light_ops['deletes'].append(dict(name=name, label='delete:' + name, kind=kind, role=light['role'],
                                                  reach=reach_box(light['location'], light['radius'])))
            self.entities.append(dict(kind='light', op='delete', target=target['actor'], lightClass=light['actorClass'],
                                      bakedInto=len(light.get('bakedInto') or [])))
            return
        if not {'location', 'rotation', 'light'} & set(rec):
            self.error('malformed', 'a light override is deleted, or gives a pose or light values', **where)
            return
        p = self.pose(dict(location=rec.get('location', light['location']),
                           rotation=rec.get('rotation', light['rotation'])), where)
        if not p:
            return
        loc, rot, rounding = p
        submitted = self.submitted_light(rec.get('light', {}), kind, where, name)
        if submitted is None:
            return
        after = self.light_after(name, kind, before, submitted, where)
        if after is None:
            return
        changed = {k: v for k, v in submitted.items() if v != before.get(k)}
        moved = not (all(abs(a - b) < EPS_LOCATION for a, b in zip(loc, light['location']))
                     and rot == [int(v) for v in light['rotation']])
        if not changed and not moved:
            self.note('unchanged', '%s is as the map has it; nothing to build for it' % name, **where)
            return
        if not self.light_gate(name, where):
            return
        entry = dict(name=name, label='change:' + name, kind=kind, role=light['role'], location=loc, rotation=rot,
                     set=changed, light=after,
                     before=dict(before, location=list(light['location']), rotation=[int(v) for v in light['rotation']]),
                     reach=dict(before=reach_box(light['location'], before['radius']),
                                after=reach_box(loc, after['radius'])))
        self.light_ops['changes'].append(entry)
        self.entities.append(dict(kind='light', op='change', target=target['actor'], lightClass=light['actorClass'],
                                  location=loc, rotation=rot, rotationRounding=tidy(rounding, 6), set=sorted(changed),
                                  bakedInto=len(light.get('bakedInto') or []),
                                  reaches=self.reaching(loc, after)))

    def light_add(self, rec, where):
        """A copy of an original light, or a spot light made from the built-in recipe (plan 3.3, 4.9)."""
        out = rec['actor']
        name = short(out)
        template = rec.get('template')
        if template is not None:
            if 'from' in rec or 'components' in rec:
                self.error('malformed', '%s is both a copy (from) and a recipe light (template)' % name, **where)
                return
            kind, version = (template.get('kind'), template.get('version')) if isinstance(template, dict) else (None, None)
            if kind not in LIGHT_RECIPES or version not in LIGHT_RECIPES[kind]:
                self.error('light-recipe', '%s is made from a recipe this compiler doesn\'t know (%r); its versions are %s'
                           % (name, template, {k: sorted(v) for k, v in LIGHT_RECIPES.items()}), **where)
                return
            values = rec.get('light')
            wanted = [k for k in LIGHT_KEYS if k in LIGHT_RECIPES[kind][version]]
            if not isinstance(values, dict) or set(values) != set(wanted):
                self.error('malformed', '%s: a recipe light carries every light value (%s)' % (name, ', '.join(wanted)),
                           **where)
                return
            submitted = self.submitted_light(values, kind, where, name)
            if submitted is None:
                return
            if kind == 'spot' and submitted['innerConeAngle'] > submitted['outerConeAngle']:
                self.note('light-clamped', '%s: its inner cone (%g) is wider than its outer cone (%g); built with the '
                          'inner cone at %g' % (name, submitted['innerConeAngle'], submitted['outerConeAngle'],
                                                submitted['outerConeAngle']), key='innerConeAngle',
                          stored=submitted['innerConeAngle'], built=submitted['outerConeAngle'], **where)
                submitted['innerConeAngle'] = submitted['outerConeAngle']
            p = self.pose(dict(location=rec.get('location'), rotation=rec.get('rotation', RECIPE_ROTATION[kind])), where)
            if not p or not self.light_gate(name, where):
                return
            loc, rot, rounding = p
            source = dict(template=dict(kind=kind, version=version))
            after, actor_class = submitted, RECIPE_ACTOR[kind]
        else:
            light = self.light_of(rec.get('from'))
            src = rec['from']
            if src['package'].casefold() != self.map.casefold() or src['level'] != 'base':
                self.error('level', '%s copies a light of %s level %s; only the base map\'s own lights copy'
                           % (name, src['package'], src['level']), **where)
                return
            why = light_rule(light)
            if why:
                self.error('light-view-only', '%s copies %s, which is view only: %s' % (name, short(src['actor']), why),
                           **where)
                return
            if sorted(rec.get('components') or []) != [light['component']]:
                self.error('template-changed', '%s names components %s, but its template now has %s'
                           % (name, rec.get('components'), [light['component']]), **where)
                return
            kind = light['kind']
            submitted = self.submitted_light(rec.get('light', {}), kind, where, name)
            if submitted is None:
                return
            after = self.light_after(name, kind, light_values(light), submitted, where)
            p = self.pose(rec, where)
            if after is None or not p or not self.light_gate(name, where):
                return
            loc, rot, rounding = p
            source = {'from': short(src['actor'])}
            actor_class = light['actorClass']
        self.light_members.add('added|' + out)
        self.light_ops['adds'].append(dict(source, name=name, label=name, kind=kind, role='static', location=loc,
                                           rotation=rot, light=after, guidSeed='%s|%s' % (self.doc.get('id'), name),
                                           reach=reach_box(loc, after['radius'])))
        self.entities.append(dict(kind='light', op='add', entity=out, id=rec.get('id'), lightClass=actor_class,
                                  template=rec.get('template') or (rec.get('from') or {}).get('actor'),
                                  location=loc, rotation=rot, rotationRounding=tidy(rounding, 6),
                                  reaches=self.reaching(loc, after)))

    # ---------------------------------------------------------------- effects and sounds (the effects and sounds plan)
    def effect_of(self, target):
        """The export's effect, sound or flare a target {package, level, actor} names (its record with `kind`), or
        None."""
        if not isinstance(target, dict):
            return None
        return self.effect_actors.get((target.get('package'), target.get('level'), target.get('actor')))

    def effect_values(self, rec, kind, name, where, source=None, systems=None):
        """A record's values object checked (the effects and sounds plan, Part C): (follow or None, values or None,
        ok). `follow` is stage FX3's ('none': it doesn't follow the piece it stands on; 'auto': it does); `values` the
        others (stage FX5), checked against `source` (the export record of the effect or sound they are set on, or
        that a copy copies) and `systems` (its particle systems' records), as the Build's writer takes them: an
        effect's {scale, startsOn, parameters: [{name, type, value}]}, a sound's {radiusMin, radiusMax, volume,
        pitch, startsOn}. Refused: a malformed value, one outside what a value may be, a parameter its effect neither
        saves in a kind the editor writes nor its system offers in one kind, and values while their family doesn't
        build (effect-values, sound-values). A lens flare has no values object at all (its template and colour stay
        as the map has them)."""
        what = EFFECT_WORDS[kind]
        other = next((k for k in ('effect', 'sound') if k != kind and k in rec), None)
        if other:
            self.error('malformed', '%s is %s, so it has no %s values' % (name, what, other), **where)
            return None, None, False
        if kind == 'flare':
            if 'flare' in rec:
                self.error('malformed', '%s is a lens flare, whose template and colour stay as the map has them: it '
                           'has no values' % name, **where)
                return None, None, False
            return None, None, True
        values = rec.get(kind)
        if values is None:
            return None, None, True
        if not isinstance(values, dict):
            self.error('malformed', '%s: "%s" must be an object of %s values' % (name, kind, kind), **where)
            return None, None, False
        bad = sorted(set(values) - set(EFFECT_VALUE_KEYS[kind]))
        if bad:
            self.error('malformed', '%s: %s %s not %s value (they are %s)' % (
                name, ', '.join(bad), 'is' if len(bad) == 1 else 'are', what, ', '.join(EFFECT_VALUE_KEYS[kind])), **where)
            return None, None, False
        follow = values.get('follow')
        if follow is not None and follow not in EFFECT_FOLLOW:
            self.error('malformed', '%s: follow must be one of %s' % (name, ', '.join(EFFECT_FOLLOW)), **where)
            return None, None, False
        given = {k: v for k, v in values.items() if k != 'follow'}
        if not given:
            return follow, None, True
        gate = kind + '-values'
        if not self.builds(gate):
            self.error('family', '%s sets its %s. %s' % (name, ', '.join(sorted(given)), FAMILIES[gate]['note']),
                       family=gate, **where)
            return None, None, False
        source = source or {}
        if not (source.get('can') or {}).get('values'):
            why = (source.get('why') or {}).get('values') or 'the export doesn\'t say its values can change'
            self.error('effect-view-only', '%s\'s values can\'t be set: %s' % (name, why), **where)
            return None, None, False
        out = {}
        number = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        if 'startsOn' in given:
            if not isinstance(given['startsOn'], bool):
                self.error('malformed', '%s: startsOn is true or false' % name, **where)
                return None, None, False
            out['startsOn'] = given['startsOn']
        if kind == 'effect':
            if 'scale' in given:
                v = given['scale']
                if not number(v) or not EFFECT_SCALE[0] <= v <= EFFECT_SCALE[1]:
                    self.error('malformed', '%s: its size is a multiplier of %g to %g of the size the map gives it'
                               % (name, EFFECT_SCALE[0], EFFECT_SCALE[1]), **where)
                    return None, None, False
                out['scale'] = float(v)
            if 'parameters' in given:
                params = self.effect_parameters(given['parameters'], name, where, source, systems)
                if params is None:
                    return None, None, False
                if params:
                    out['parameters'] = params
            return follow, out, True
        have = source.get('values') or {}
        for key in ('radiusMin', 'radiusMax'):
            if key in given:
                v = given[key]
                if not number(v) or not 0 <= v <= SOUND_RADIUS_MAX:
                    self.error('malformed', '%s: %s is 0 to %g units' % (name, key, SOUND_RADIUS_MAX), **where)
                    return None, None, False
                out[key] = float(v)
        lo, hi = out.get('radiusMin', have.get('radiusMin')), out.get('radiusMax', have.get('radiusMax'))
        if ('radiusMin' in out or 'radiusMax' in out) and number(lo) and number(hi) and lo > hi:
            self.error('malformed', '%s: its inner radius (%g) is beyond its outer one (%g)' % (name, lo, hi), **where)
            return None, None, False
        for key, (least, most) in (('volume', (0.0, SOUND_VOLUME_MAX)), ('pitch', SOUND_PITCH)):
            if key not in given:
                continue
            v = given[key]
            if (not isinstance(v, list) or len(v) != 2 or not all(number(x) for x in v) or v[0] > v[1]
                    or v[0] < least or v[1] > most):
                self.error('malformed', '%s: %s is [least, most], each %g to %g' % (name, key, least, most), **where)
                return None, None, False
            out[key] = [float(x) for x in v]
        return follow, out, True

    def effect_parameters(self, given, name, where, source, systems):
        """An effect's parameters ([{name, value}]) as the writer takes them ([{name, type, value}]), or None with an
        error: a parameter the effect saves keeps the type it is saved in (a scalar, vector or colour entry; the
        first of the name, as the game reads it), one it doesn't is added in the kind its system's distribution of
        that name has (all of them one kind)."""
        if not isinstance(given, list):
            self.error('malformed', '%s: parameters is a list of {name, value}' % name, **where)
            return None
        saved = {}
        for prm in source.get('parameters') or []:
            if prm.get('name') and prm['name'] not in saved:
                saved[prm['name']] = prm
        offers = {}
        system = (systems or {}).get(source.get('system')) if source.get('system') else None
        for o in (system or {}).get('offers') or []:
            offers.setdefault(o['name'], set()).add(o['kind'])
        number = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        out, seen = [], set()
        for prm in given:
            if not isinstance(prm, dict) or set(prm) != {'name', 'value'} or not isinstance(prm['name'], str) or not prm['name']:
                self.error('malformed', '%s: each parameter is {name, value}' % name, **where)
                return None
            pname = prm['name']
            if pname in seen:
                self.error('malformed', '%s sets parameter %s twice' % (name, pname), **where)
                return None
            seen.add(pname)
            if pname in saved:
                type_ = saved[pname].get('type')
                if type_ not in PARAMETER_TYPES:
                    self.error('effect-view-only', '%s\'s parameter %s is of type %s, which the editor keeps as the map '
                               'has it' % (name, pname, type_), **where)
                    return None
            elif len(offers.get(pname, ())) == 1:
                type_ = DISTRIBUTION_TYPES[next(iter(offers[pname]))]
            elif pname in offers:
                self.error('effect-view-only', '%s\'s system reads parameter %s both as a number and as a vector, so it '
                           'is kept as the map has it' % (name, pname), **where)
                return None
            else:
                self.error('malformed', '%s\'s system has no parameter %s%s' % (
                    name, pname, '' if system else ' (its system didn\'t resolve)'), **where)
                return None
            v, shape = prm['value'], PARAMETER_TYPES[type_]
            ok = (number(v) and abs(v) <= PARAMETER_MAX if shape == 'scalar'
                  else isinstance(v, list) and len(v) == 3 and all(number(x) and abs(x) <= PARAMETER_MAX for x in v)
                  if shape == 'vector'
                  else isinstance(v, list) and len(v) == 4 and all(number(x) and 0 <= x <= 1 for x in v))
            if not ok:
                self.error('malformed', '%s: parameter %s is %s' % (name, pname, dict(
                    scalar='a number', vector='three numbers [x, y, z]',
                    colour='a colour [r, g, b, a], each 0 to 1')[shape]), **where)
                return None
            out.append(dict(name=pname, type=type_, value=float(v) if shape == 'scalar' else [float(x) for x in v]))
        return out

    def effect_value_warnings(self, name, kind, values, source, where, copy=False):
        """The warnings for an effect's or sound's values (decision 9: what may behave oddly in the game): one that
        starts off with nothing to switch it on, and values the map's script changes too."""
        if not values:
            return
        users = ' '.join(source.get('referencedBy') or []) if not copy else ''
        starts = values.get('startsOn', source.get('startsOn'))
        if 'startsOn' in values and starts is False and 'Toggle' not in users:
            self.warn('effect-starts-off', '%s starts off, and nothing in the map\'s script switches it on' % name,
                      **where)
        elif 'startsOn' in values and 'Toggle' in users:
            self.warn('mission-linked', '%s is switched on and off by the map\'s Kismet (%s): what it starts as lasts '
                      'until the script switches it' % (name, '; '.join(source['referencedBy'][:4])), **where)
        if values.get('parameters') and 'SetParticleSysParam' in users:
            self.warn('mission-linked', '%s\'s parameters are set by the map\'s Kismet too (%s): what the script sets '
                      'replaces these when it runs' % (name, '; '.join(source['referencedBy'][:4])), **where)

    def effect_gate(self, kind, name, where):
        """The family's refusal while it doesn't build: True when the edit may go on."""
        if self.builds(kind):
            return True
        self.error('family', '%s is %s edit. %s' % (name, EFFECT_WORDS[kind], FAMILIES[kind]['note']), family=kind,
                   **where)
        return False

    def effect_usable(self, rec, can, name, where):
        """Whether the export says an edit may `can` (move, copy, delete) the effect or sound `rec`: True, or False
        with the export's reason as an error."""
        if (rec.get('can') or {}).get(can):
            return True
        if 'can' not in rec:
            self.error('export-version', '%s: this map\'s export predates the effects and sounds data (export %d): '
                       'prepare it again' % (name, EFFECTS_EXPORT), minimum=EFFECTS_EXPORT, **where)
            return False
        why = (rec.get('why') or {}).get(can) or 'the export doesn\'t say it can'
        self.error('effect-view-only', '%s can\'t be %s: %s' % (
            name, dict(move='moved', copy='copied', delete='deleted')[can], why), **where)
        return False

    def effect_listing(self, location):
        """[(building path, floor index)]: the upper floors (index 1 up) one of whose boxes, as the project has them,
        holds `location` within EFFECT_SLACK: where the Build lists a moved or new effect (plan Part D)."""
        out = []
        for name, index, boxes in self.floor_boxes_now() or []:
            if index >= 1 and any(all(b['min'][a] - EFFECT_SLACK <= location[a] <= b['max'][a] + EFFECT_SLACK
                                      for a in range(3)) for b in boxes):
                out.append((name, index))
        return out

    def effect_floor_note(self, name, rec, location, where):
        """The note (not a warning) saying which floors' cutaways a moved or new effect joins and leaves: listed, it
        hides when its floor is cut away. A sound is in no floor's list."""
        if self.floor_boxes is None:
            return
        old = {(self.building_names.get(f.get('building')), f.get('floor')) for f in (rec or {}).get('floors') or []}
        new = set(self.effect_listing(location))
        words = lambda fs: ', '.join('floor %d of %s' % (k + 1, short(str(b))) for b, k in sorted(fs, key=str))
        joins, leaves = new - old, old - new
        if joins or leaves:
            self.note('effect-floors', '%s%s%s' % (name, ' joins the cutaway of %s' % words(joins) if joins else '',
                                                   ('%s leaves the cutaway of %s' % (',' if joins else '', words(leaves)))
                                                   if leaves else ''),
                      joins=[[short(str(b)), k] for b, k in sorted(joins, key=str)],
                      leaves=[[short(str(b)), k] for b, k in sorted(leaves, key=str)], **where)

    def effect_script(self, name, rec, what, where):
        """The warning for an edit of an effect or sound the mission's script names (export 15's referencedBy): the
        script acts on the original, wherever it is, and not on a copy."""
        if rec.get('referencedBy'):
            self.warn('mission-linked', '%s is named by the map\'s Kismet (%s): %s' % (
                name, '; '.join(rec['referencedBy'][:4]), what), **where)

    def effect_override(self, target, rec, where, effect):
        """An original effect or sound moved, turned or deleted (the effects and sounds plan, Part C), in place: the
        Build keeps its actor, so what names it still does."""
        kind, name = effect['kind'], short(target['actor'])
        for f in sorted(set(rec) - {'target', 'location', 'rotation', 'deleted', 'effect', 'sound', 'flare'}):
            self.note('unknown-field', 'field %r is not part of the override of %s and is ignored' % (f, EFFECT_WORDS[kind]),
                      **where)
        if target['level'] != 'base' or str(target['package']).casefold() != self.map.casefold():
            self.error('effect-view-only', '%s is %s of %s level %s, which the editor shows but doesn\'t change'
                       % (name, EFFECT_WORDS[kind], target['package'], target['level']), **where)
            return
        if not self.effect_gate(kind, name, where):
            return
        follow, values, ok = self.effect_values(rec, kind, name, where, effect, self.scene.get('effectSystems'))
        if not ok:
            return
        ops = self.effect_ops[kind]
        if rec.get('deleted') is True:
            if not self.effect_usable(effect, 'delete', name, where):
                return
            self.effect_own.add(target['actor'])
            self.effect_script(name, effect, 'it is taken out of the level, so what the script does with it does '
                               'nothing', where)
            ops['deletes'].append(dict(name=name, actorClass=effect['actorClass'], location=list(effect['location'])))
            self.entities.append(dict(kind=kind, op='delete', target=target['actor'], actorClass=effect['actorClass']))
            return
        if values:
            # its values, set on the actor in place (stage FX5)
            self.effect_value_warnings(name, kind, values, effect, where)
            ops['values'].append(dict(name=name, actorClass=effect['actorClass'], **{kind: values}))
            self.entities.append(dict(kind=kind, op='values', target=target['actor'], actorClass=effect['actorClass'],
                                      **{kind: values}))
        if 'location' not in rec and 'rotation' not in rec:
            if follow is None:
                if not values:
                    self.error('malformed', 'the override of %s is deleted%s' % (
                        EFFECT_WORDS[kind], ' or gives a pose' if kind == 'flare' else ', gives a pose or values'), **where)
            else:
                # follow alone: carrying as the map has it ('auto') or not ('none', where it stands)
                if follow == 'none' and effect.get('carriedBy'):
                    self.effect_own.add(target['actor'])
                    self.note('effect-detached', '%s stays where it is when %s moves' % (
                        name, short(effect['carriedBy'])), **where)
                elif not values:
                    self.note('unchanged', '%s is as the map has it; nothing to build for it' % name, **where)
            return
        p = self.pose(dict(location=rec.get('location', effect['location']),
                           rotation=rec.get('rotation', effect['rotation'])), where)
        if not p:
            return
        loc, rot, rounding = p
        moved = not (all(abs(a - b) < EPS_LOCATION for a, b in zip(loc, effect['location']))
                     and rot == [int(v) for v in effect['rotation']])
        if follow == 'auto' and effect.get('carriedBy'):
            self.error('malformed', '%s follows %s (follow auto), so it has no pose of its own'
                       % (name, short(effect['carriedBy'])), **where)
            return
        if not moved:
            if not values:
                self.note('unchanged', '%s is as the map has it; nothing to build for it' % name, **where)
            return
        if not self.effect_usable(effect, 'move', name, where):
            return
        # its own pose: the piece it stood on no longer takes it along (plan Part C, ownership and precedence)
        self.effect_own.add(target['actor'])
        if effect.get('carriedBy'):
            self.note('effect-detached', '%s has a place of its own, so it no longer moves with %s'
                      % (name, short(effect['carriedBy'])), **where)
        self.effect_script(name, effect, 'the script still acts on it where it stands now (and a Matinee can put it '
                           'back where it was)', where)
        if kind == 'effect':
            self.effect_floor_note(name, effect, loc, where)
        ops['moves'].append(dict(name=name, actorClass=effect['actorClass'], location=loc, rotation=rot,
                                 before=dict(location=list(effect['location']), rotation=list(effect['rotation']))))
        self.entities.append(dict(kind=kind, op='move', target=target['actor'], actorClass=effect['actorClass'],
                                  location=loc, rotation=rot, rotationRounding=tidy(rounding, 6)))

    def effect_add(self, rec, where):
        """A copy of one of the map's effects, sounds or lens flares (the effects and sounds plan, Part C): the Build
        clones the actor and what it owns (its component, light environment and own cue) and shares the system, the
        wave or the flare's template. A copy of
        another map's (`from` names a base map other than this one: stage FX4) comes from the library
        (foreign_effect): the Build stages its donor actor with what it needs (transplant.stage_edit) and clones that."""
        out = rec['actor']
        name = short(out)
        kind = rec.get('kind')
        for f in sorted(set(rec) - {'id', 'actor', 'kind', 'from', 'location', 'rotation', 'effect', 'sound', 'flare'}):
            if f in ('components', 'template', 'cover', 'light', 'flags', 'prefab', 'partner', 'tinted'):
                self.error('malformed', '%s is a copy of %s, so it has no %s' % (
                    name, EFFECT_WORDS.get(kind, 'an effect'), f), **where)
                return
            self.note('unknown-field', 'field %r is not part of an added effect, sound or lens flare and is ignored' % f,
                      **where)
        if kind not in EFFECT_KINDS:
            self.error('malformed', '%s: kind must be one of %s' % (name, ', '.join(EFFECT_KINDS)), **where)
            return
        if not isinstance(rec.get('id'), str) or not rec['id']:
            self.error('malformed', '%s has no id' % name, **where)
            return
        src = rec.get('from')
        donor, systems = None, None
        if (isinstance(src, dict) and src.get('level') == 'base' and isinstance(src.get('package'), str)
                and isinstance(src.get('actor'), str) and src['package'].casefold() != self.map.casefold()):
            source, donor, systems = self.foreign_effect(src, name, where)
            if source is None:
                return
        else:
            source = self.effect_of(src)
            if source is None:
                self.error('missing', '%s copies %s, which is no effect, sound or lens flare of the export'
                           % (name, short(str((src or {}).get('actor')))), **where)
                return
        if source['kind'] != kind:
            self.error('malformed', '%s says it is %s but copies %s, which is %s' % (
                name, kind, short(src['actor']), source['kind']), **where)
            return
        if src['level'] != 'base':
            self.error('effect-view-only', '%s copies %s of %s level %s; only a base map\'s own are copied'
                       % (name, short(src['actor']), src['package'], src['level']), **where)
            return
        if not self.effect_gate(kind, name, where):
            return
        follow, values, ok = self.effect_values(rec, kind, name, where, source,
                                                systems if donor else self.scene.get('effectSystems'))
        if not ok:
            return
        if follow is not None:
            self.note('unknown-field', '%s is a copy, which no piece carries: its follow is ignored' % name, **where)
        p = self.pose(rec, where)
        if not p or not self.effect_usable(source, 'copy', name, where):
            return
        loc, rot, rounding = p
        self.effect_members.add('added|' + out)
        if kind == 'effect':
            self.effect_floor_note(name, None, loc, where)
        if source.get('referencedBy'):
            self.note('effect-script-copy', '%s is a copy of %s, which its map\'s Kismet names: the copy is an ordinary '
                      '%s, which the script doesn\'t switch on or off' % (
                          name, short(src['actor']), 'lens flare' if kind == 'flare' else kind), **where)
        if (values or {}).get('startsOn', source.get('startsOn')) is False:
            self.warn('effect-starts-off', '%s is a copy of %s, %s: nothing switches the copy on' % (
                name, short(src['actor']), 'set to start off' if (values or {}).get('startsOn') is False
                else 'which starts off and waits for the script to switch it on'), **where)
        self.effect_value_warnings(name, kind, {k: v for k, v in (values or {}).items() if k != 'startsOn'}, source,
                                   where, copy=True)
        if source.get('landingActor') or source.get('landingRole'):
            # Long War's landing mutator (XComLZMutator.HideDropShip) destroys every actor made from the grounded
            # Skyranger's archetypes when a battle loads, and a copy keeps its source's archetype (F-120)
            self.warn('effect-landing-copy', '%s is a copy of %s, one of the landing\'s actors: under Long War the '
                      'landing mutator takes out every actor made like the landing\'s when the battle loads, the copy '
                      'among them (plain Enemy Within keeps it)' % (name, short(src['actor'])), **where)
        copy = dict(id=rec['id'], name=name, source=short(src['actor']), actorClass=source['actorClass'], location=loc,
                    rotation=rot)
        if values:
            copy['values'] = values
        if donor:
            # the Build stages the donor's actor in the map (transplant.stage_edit) and clones the staged one
            copy['donor'] = donor
            row = self.donor_report.setdefault(donor['package'], dict(donor, pieces=[]))
            if short(src['actor']) not in row['pieces']:
                row['pieces'].append(short(src['actor']))
        self.effect_ops[kind]['copies'].append(copy)
        self.entities.append(dict(kind=kind, op='add', entity=out, id=rec['id'], actorClass=source['actorClass'],
                                  template=src['actor'], location=loc, rotation=rot,
                                  rotationRounding=tidy(rounding, 6), **({'donor': donor} if donor else {})))

    def foreign_effect(self, src, name, where):
        """(record, donor, systems) of the effect, ambient sound or lens flare of another map a copy names (the effects
        and sounds plan, stage FX4; a flare since FX6b): its export 28 record as the library reads it from its map (library.effect), its donor
        {package, sha256} for the Build's staging and its system's record ({key: record}); (None, None, None) with an
        error. What the library can't bring is
        refused (a landing's actor, one riding on another, one whose closure the transplant refuses); one only the
        foreign gate holds back (FOREIGN_FAMILIES, which has listed effects and sounds since EXP-69, and lists no
        lens flare until its game check) is built as any copy, as the pieces of a kind not brought before are
        (FOREIGN_SOFT)."""
        if self.library is None:
            self.error('no-library', '%s copies %s of %s, and this build has no library of other maps\' pieces'
                       % (name, short(src['actor']), src['package']), **where)
            return None, None, None
        try:
            template, entry = self.library.effect(src)
        except LibraryError as error:
            self.error(error.code, str(error), **where)
            return None, None, None
        if not entry['placeable'] and entry.get('blocked') != 'family':
            self.error('not-placeable', '%s copies %s of %s, which can\'t be placed in another map: %s'
                       % (name, short(src['actor']), template['source']['package'], entry['reason']), **where)
            return None, None, None
        source = template['source']
        return (template['record'], dict(package=source['package'], sha256=source['sha256']),
                template.get('systems') or {})

    def reaching(self, location, values):
        """How many of the base map's pieces a light's radius reaches at `location` (the report's estimate of what a
        full build relights; plan 4.2): object boxes within its radius."""
        if self.object_boxes is None:
            self.object_boxes = []
            meshes = self.scene.get('meshes') or {}
            for o in self.scene.get('objects') or []:
                if o.get('layer') == 'base' and o.get('mesh') in meshes and o.get('location') is not None:
                    try:
                        self.object_boxes.append(world_box(o, meshes, o['location'], o['rotation']))
                    except (KeyError, TypeError, ValueError, IndexError):
                        continue
        r2 = float(values.get('radius') or 0) ** 2
        n = 0
        for b in self.object_boxes:
            d2 = sum(max(b[2 * k] - location[k], 0, location[k] - b[2 * k + 1]) ** 2 for k in range(3))
            n += d2 <= r2
        return n

    # ---------------------------------------------------------------- area lights following their pieces (plan 4.8)
    def copy_area_light(self, light, owner, entity, move, donor=None):
        lname = short(light['actor'])
        name = '%s_%s' % (lname, short(entity))
        location, rotation = moved_light_pose(light['location'], light['rotation'], move)
        seed = '%s|%s|%s' % (self.doc.get('id'), lname, short(entity))
        if donor:
            seed += '|' + donor['package']
        op = dict(op='copy', name=name, light=lname, owner=short(owner), ownerEntity=short(entity),
                  label='area-copy:' + name, location=location, rotation=rotation, guidSeed=seed,
                  reach=dict(before=None, after=reach_box(location, light['radius'])))
        if donor:
            op['donor'] = donor
        self.light_ops['area'].append(op)
        self.entities.append(dict(kind='light', op='area-copy', target=light['actor'], owner=owner,
                                  ownerEntity=entity, lightClass=light['actorClass']))

    def area_bindings(self):
        """The effective glowing piece of each area light: {light actor path: (owner actor path or None, where it came
        from)}: the project's areaLightBindings, else the export's verified association. Bad bindings are errors."""
        out = {}
        for light in self.scene.get('lights') or []:
            if light.get('role') != 'area' or light.get('layer') != 'base':
                continue
            att = light.get('emitterAttachment') or {}
            owner = (att.get('owner') or {}).get('target') if att.get('status') == 'verified' else None
            out[light['actor']] = (owner.get('actor') if owner else None, 'export' if owner else att.get('status'))
        records = self.doc.get('areaLightBindings')
        if records is None:
            return out
        if not isinstance(records, list):
            self.error('malformed', '"areaLightBindings" must be a list')
            return out
        seen = set()
        for k, rec in enumerate(records):
            where = dict(record='areaLightBindings[%d]' % k)
            target = rec.get('target') if isinstance(rec, dict) else None
            light = self.light_of(target)
            if not isinstance(rec, dict) or not isinstance(target, dict) or 'owner' not in rec:
                self.error('area-binding', 'a binding names an area light (target) and its owner (or null)', **where)
                continue
            where['target'] = str(target.get('actor'))
            if light is None or light.get('role') != 'area' or light.get('layer') != 'base':
                self.error('area-binding', '%s is not an area light of %s\'s base level in the export'
                           % (short(str(target.get('actor'))), self.map), **where)
                continue
            if light['actor'] in seen:
                self.error('area-binding', '%s is bound twice' % short(light['actor']), **where)
                continue
            seen.add(light['actor'])
            owner = rec['owner']
            if owner is None:
                out[light['actor']] = (None, 'kept')
                continue
            ot = owner.get('target') if isinstance(owner, dict) else None
            parts = self.actors.get((ot.get('package'), ot.get('level'), ot.get('actor'))) if isinstance(ot, dict) else None
            if (not parts or ot.get('level') != 'base' or str(ot.get('package')).casefold() != self.map.casefold()
                    or not any(p.get('component') == owner.get('component') for p in parts)):
                self.error('area-binding', '%s is bound to a piece that is not a base-level piece of %s in the export'
                           ' (or not its component)' % (short(light['actor']), self.map), **where)
                continue
            out[light['actor']] = (ot['actor'], 'project')
        return out

    def derive_area_lights(self):
        """The area lights the piece edits take along (plan 4.8), once from the final piece state: a moved original's
        lights move with it (rigid_move of the owner), a deleted one's go, each copy of an owner gets a copy of each
        of its lights at the copy's place. An edited piece that may own an area light whose glowing piece isn't
        settled (ambiguous or unmatched, and not bound in the project) is an error: assign or keep it fixed."""
        if not self.owner_edits:
            return
        bound = self.area_bindings()
        owned = {}
        for light, (owner, _) in bound.items():
            if owner:
                owned.setdefault(owner, []).append(light)
        lights = {l['actor']: l for l in self.scene.get('lights') or [] if l.get('role') == 'area'}
        by_id = {l.get('id'): l for l in lights.values()}
        for kind, owner, entity, move, where in self.owner_edits:
            parts = self.actors.get((self.package, 'base', owner)) or []
            # the lights this piece may have emitted whose glowing piece isn't settled (neither bound nor kept fixed)
            maybe = sorted({lid for o in parts for lid in o.get('areaLights') or []})
            unsettled = []
            for lid in maybe:
                rec = by_id.get(lid)
                if rec is None:
                    continue
                owner_now, why = bound.get(rec['actor'], (None, None))
                if owner_now is None and why != 'kept':
                    unsettled.append(short(rec['actor']))
            if unsettled and self.cleared and kind == 'delete':
                # a cleared map's Build takes out every area light whose glowing piece isn't settled (clear_level)
                unsettled = []
            if unsettled:
                # (a warning since plan R4: the piece's edit is built, and the light stays as the map has it)
                self.note('area-light-unresolved', '%s may be the glowing piece of %s, whose glowing piece isn\'t settled '
                          '(the matcher found it %s): the light stays where the map has it. Assign it or keep it fixed '
                          '(the light\'s inspector) to settle it' % (short(owner), ', '.join(unsettled),
                                                                    'ambiguous or unmatched'), **where)
                continue
            mine = sorted(owned.get(owner, []))
            if not mine:
                self.near_unknown(parts, where)
                continue
            if not self.builds('light'):
                # (a warning since plan R4: the piece's edit is built, and its light stays as the map has it)
                self.note('family', '%s glows: %s it would take its generated light%s (%s) along, which stay%s where '
                          'the map has %s. %s' % (
                              short(owner), {'move': 'moved,', 'delete': 'deleted,', 'copy': 'copied,'}[kind],
                              '' if len(mine) == 1 else 's', ', '.join(short(m) for m in mine),
                              's' if len(mine) == 1 else '', 'it' if len(mine) == 1 else 'them',
                              FAMILIES['light']['note']), family='light', **where)
                continue
            for light_path in mine:
                light = lights[light_path]
                if kind == 'copy':
                    self.copy_area_light(light, owner, entity, move)
                    continue
                lname = short(light_path)
                before_reach = reach_box(light['location'], light['radius'])
                if kind == 'delete':
                    op = dict(op='delete', name=lname, light=lname, owner=short(owner), ownerEntity=short(owner),
                              label='area-delete:' + lname, location=list(light['location']),
                              rotation=[int(v) for v in light['rotation']], guidSeed=None,
                              reach=dict(before=before_reach, after=None))
                else:
                    loc, rot = moved_light_pose(light['location'], light['rotation'], move)
                    op = dict(op=kind, name=lname, light=lname, owner=short(owner), ownerEntity=short(entity),
                              label='area-move:' + lname, location=loc, rotation=rot, guidSeed=None,
                              reach=dict(before=before_reach, after=reach_box(loc, light['radius'])))
                self.light_ops['area'].append(op)
                self.entities.append(dict(kind='light', op='area-' + kind, target=light_path, owner=owner,
                                          ownerEntity=entity, lightClass=light['actorClass']))

    def near_unknown(self, parts, where):
        """Warns of unmatched area lights (no candidate glowing piece) near an edited piece (plan 4.8): their glow may
        be this piece's, which the matcher couldn't tell from its materials."""
        try:
            box = self.boxes(parts, parts[0]['location'], parts[0]['rotation'])
        except (KeyError, TypeError, ValueError, IndexError):
            return
        near = []
        for light in self.scene.get('lights') or []:
            att = light.get('emitterAttachment') or {}
            if light.get('role') != 'area' or att.get('status') != 'unmatched' or att.get('candidates'):
                continue
            if all(box[2 * k] - AREA_NEAR <= light['location'][k] <= box[2 * k + 1] + AREA_NEAR for k in range(3)):
                near.append(short(light['actor']))
        if near:
            self.note('area-light-near', '%s stands by %s, generated light%s whose glowing piece the export couldn\'t '
                      'find: if it glows from this piece, it stays where it is' % (
                          short(parts[0]['actor']), ', '.join(near), '' if len(near) == 1 else 's'), **where)

    def groups(self):
        """The user's groups (research/editor-contracts.md, section 2). Only "break together" reaches the game: each
        such group with two or more breakable pieces gets a number, given to its copies (breakGroups) and to the base
        map's own pieces left in place (breakOriginals), which the copier links at load. A cover block (high or low,
        not an invisible floor) of such a group breaks with it: it takes the group's number (its `breakGroup`), is
        built as a hidden prop (tools/bake/cover_blocks.py) and goes when a breakable piece of the group is
        destroyed; with a block one breakable piece is enough, and it may be the map's own. A locked group's moving as one
        is the editor's alone, and so is nesting: a member that is another group ({group}) must name a group of the
        project that is in no other group and does not hold this one (group-nesting), and takes no part in breaking
        together, which is over a group's own pieces. Nor do a light or one of the project's buildings ({building};
        prefab plan 5.4a), which only move with their group in the editor; a building named must be the project's
        (group-member, a warning: the member is ignored)."""
        # (`prefab`: the prefab a group was placed from, a label the editor keeps; nothing of it reaches the game)
        known = {'id', 'locked', 'breakTogether', 'members', 'prefab'}
        copies = {c['member']: c for c in self.copies}
        covers = self.cover_members
        deleted = {original_key(r['target']) for r in self.doc.get('overrides') or []
                   if isinstance(r, dict) and isinstance(r.get('target'), dict) and r.get('deleted') is True}
        linked = {}   # member key -> the group that links it
        made = {b.get('id') for b in self.doc.get('buildings') or [] if isinstance(b, dict) and b.get('deleted') is not True}
        # the map's own buildings that can be edited, by the id made from their actor, record or none (map buildings
        # plan, section 2); a deleted one is no member
        gone = {b.get('id') for b in self.doc.get('buildings') or [] if isinstance(b, dict) and b.get('deleted') is True}
        made |= {map_building_id(b) for b, why in self.map_buildings().values() if why is None} - gone
        records = self.doc.get('groups', [])
        if not isinstance(records, list):
            self.error('malformed', '"groups" must be a list of groups')
            return
        number = 0
        # nesting: each group named as a member is a group of the project, in one group at most, and in no loop
        ids = {rec['id'] for rec in records if isinstance(rec, dict) and isinstance(rec.get('id'), str)}
        holder = {}
        for k, rec in enumerate(records):
            if not isinstance(rec, dict) or not isinstance(rec.get('members'), list):
                continue
            for m in rec['members']:
                if not (isinstance(m, dict) and set(m) == {'group'} and isinstance(m['group'], str)):
                    continue
                where = dict(record='groups[%d]' % k, group=rec.get('id'))
                if m['group'] not in ids or m['group'] == rec.get('id'):
                    self.error('group-nesting', 'a group names the group %s as a member, which is %s'
                               % (m['group'], 'itself' if m['group'] == rec.get('id') else 'not a group of the project'), **where)
                elif m['group'] in holder:
                    self.error('group-nesting', 'the group %s is a member of two groups; a group is in one at most' % m['group'], **where)
                else:
                    holder[m['group']] = rec.get('id')
        for start in sorted(holder):
            seen, at = set(), start
            while at in holder and at not in seen:
                seen.add(at)
                at = holder[at]
            if at in seen:
                self.error('group-nesting', 'the group %s is inside itself, through the groups it is in' % start, group=start)
                break
        for k, rec in sorted(enumerate(records), key=lambda e: str(e[1].get('id') if isinstance(e[1], dict) else '')):
            where = dict(record='groups[%d]' % k)
            members = rec.get('members') if isinstance(rec, dict) else None
            keys = [member_key(m) for m in members] if isinstance(members, list) else []
            if not isinstance(rec, dict) or not isinstance(rec.get('id'), str) or len(keys) < 2 or not all(keys) \
                    or len(set(keys)) != len(keys) or any(not isinstance(rec.get(f, False), bool) for f in ('locked', 'breakTogether')):
                self.error('malformed', 'a group needs an id, two or more different members ({added}, {package, level, '
                           'actor}, {group} or {building}) and true or false for locked and breakTogether', **where)
                continue
            where['group'] = rec['id']
            for f in sorted(set(rec) - known):
                self.note('unknown-field', 'field %r is not part of a group and is ignored' % f, **where)
            entry = dict(id=rec['id'], locked=rec.get('locked', True), breakTogether=rec.get('breakTogether', False),
                         number=0, copies=[], originals=[], blocks=[], notBreakable=[])
            self.group_report.append(entry)
            for m in members:
                if 'building' in m and m['building'] not in made:
                    self.warn('group-member', 'the group names the building %s, which is neither one of the project\'s '
                              'buildings nor one of the map\'s; it is ignored' % m['building'], **where)
            if not entry['breakTogether']:
                continue
            links = []   # (kind, member key, label): a copy, or an original left in place (by its short name)
            blocks = []  # member keys of its cover blocks, which break with it
            for m, key in zip(members, keys):
                if 'group' in m:
                    continue   # a group inside it breaks by its own option
                if 'building' in m or key in self.light_members or key in self.effect_members \
                        or ('actor' in m and ((m['package'], m['level'], m['actor']) in self.lights
                                              or (m['package'], m['level'], m['actor']) in self.effect_actors)):
                    continue   # a building's boxes, a light, an effect or a sound move with the group in the editor;
                    # they don't break
                if key in deleted:
                    continue   # it isn't there to break
                if key in linked:
                    self.warn('group-member', '%s is in two groups that break together; it breaks with group %s only'
                              % (short(m.get('added') or m.get('actor')), linked[key]), **where)
                    continue
                if key in covers:
                    if self.cover_by_member[key]['kind'] in BREAKING_COVERS:
                        blocks.append(key)
                    else:
                        entry['notBreakable'].append(short(m['added']))     # an invisible floor stays
                    continue
                if key in copies:
                    c = copies[key]
                    if c['actorClass'] in BREAKABLE:
                        links.append(('copy', key, c['label']))
                    else:
                        entry['notBreakable'].append(c['label'])
                    continue
                if 'added' in m:
                    self.warn('group-member', 'group member %s is not built (see its own error), so it can\'t break with the group'
                              % short(m['added']), **where)
                    continue
                parts = self.actors.get((m['package'], m['level'], m['actor']))
                if not parts or m['level'] != 'base' or m['package'].casefold() != self.map.casefold():
                    self.warn('group-member', 'group member %s is not a piece of %s\'s base level in the export, so it can\'t break '
                              'with the group' % (short(m['actor']), self.map), **where)
                    continue
                if parts[0]['actorClass'] in BREAKABLE:
                    links.append(('original', key, short(m['actor'])))
                else:
                    entry['notBreakable'].append(short(m['actor']))
            for name in entry['notBreakable']:
                self.note('group-unbreakable', '%s moves with its group but can\'t break with it (only props and cover '
                          'blocks break)' % name, **where)
            if len(links) < (1 if blocks else 2):
                self.note('group-unbreakable', 'the group breaks together but has %d breakable piece(s), so nothing is linked'
                          '%s' % (len(links), ' (a cover block goes when a prop of its group is destroyed)' if blocks else ''),
                          **where)
                continue
            # a cover block is made in the map, so its group is linked there even when its props are all the map's own
            if not blocks and not any(kind == 'copy' for kind, _, _ in links):
                self.warn('group-not-linked', 'the group\'s breakable pieces are all the map\'s own, left in place; the patch '
                          'links pieces only through its copies yet, so move or copy one of them', **where)
                continue
            number += 1
            entry['number'] = number
            for kind, key, label in links:
                linked[key] = rec['id']
                if kind == 'copy':
                    self.break_copies[key] = number
                    entry['copies'].append(label)
                else:
                    self.break_originals.append(dict(name=label, group=number))
                    entry['originals'].append(label)
            for key in blocks:
                linked[key] = rec['id']
                self.cover_by_member[key]['breakGroup'] = number
                entry['blocks'].append(self.cover_by_member[key]['name'])
                for e in self.entities:
                    if e.get('kind') == 'add' and 'added|' + e['entity'] == key:
                        e['actorClass'] = 'XComDestructibleActor'    # built as a hidden prop

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
            # Ladders: each ladder copy's foot tile and linked top tile (None for other copies); the Build rebuilds the top
            # tile first, so the climb keeps both its links (plan section 5.2).
            if any(c.get('ladder') for c in copies):
                copy['ladders'] = [c.get('ladder') for c in copies]
            # Break groups (the user's groups with "break together"): a number per copy, 0 for none.
            if self.break_copies:
                copy['breakGroups'] = [self.break_copies.get(c['member'], 0) for c in copies]
            if self.break_originals:
                copy['breakOriginals'] = sorted(self.break_originals, key=lambda o: (o['group'], o['name']))
            copy['extra'] = ['bLogTiles=False']
            objects.append(copy)
        elif self.break_originals:
            # no copy to carry them: the map's own pieces that break with a cover block of their group
            objects.append(dict(type='breakOriginals',
                                originals=sorted(self.break_originals, key=lambda o: (o['group'], o['name']))))
        hides = sorted(self.hides, key=lambda h: h['name'])
        if hides:
            # The hider's own place doesn't matter in exact mode: the middle of what it hides, at its lowest point.
            loc = union([h['box'] for h in hides])
            objects.append(dict(type='hide', exact=True, location=[tidy((loc[0] + loc[1]) / 2), tidy((loc[2] + loc[3]) / 2), tidy(loc[4])],
                                alsoHide=[h['name'] for h in hides], labels=[h['label'] for h in hides],
                                boxes=[[tidy(v, 3) for v in h['box']] for h in hides]))
        if any(self.light_ops.values()):
            # Light edits (plan 9.5): made in the map by the Build's writer (native_split moves them there)
            ops = self.light_ops
            objects.append(dict(type='lights', deletes=sorted(ops['deletes'], key=lambda d: d['name']),
                                changes=sorted(ops['changes'], key=lambda d: d['name']),
                                adds=sorted(ops['adds'], key=lambda d: d['name']),
                                area=sorted(ops['area'], key=lambda d: (d['light'], d['op'], d['name']))))
        if self.covers:
            # cover blocks (cover_add): made in the map by the Build's writer (native_split moves them there)
            objects.append(dict(type='covers', blocks=sorted(self.covers, key=lambda c: c['name'])))
        for kind, key in EFFECT_LANES:
            ops = self.effect_ops[kind]
            if any(ops.values()):
                # effects, sounds and lens flares (the effects and sounds plan, Part D): moved in place, deleted from
                # the level's list and copied in the map by the Build's writer (native_split moves them there)
                objects.append(dict(type=key, moves=sorted(ops['moves'], key=lambda d: d['name']),
                                    deletes=sorted(ops['deletes'], key=lambda d: d['name']),
                                    copies=sorted(ops['copies'], key=lambda d: d['name']),
                                    values=sorted(ops['values'], key=lambda d: d['name'])))
        if any(self.spawn_ops.values()):
            # the base map's spawn points moved or given values (the editor spawns plan, SP6): made in the map by the
            # Build's writer (native_split moves them there; tools/bake/native_spawns.py)
            objects.append(dict(type='spawns', moves=sorted(self.spawn_ops['moves'], key=lambda d: d['name']),
                                values=sorted(self.spawn_ops['values'], key=lambda d: d['name']),
                                deletes=sorted(self.spawn_ops['deletes'], key=lambda d: d['name']),
                                copies=sorted(self.spawn_ops['copies'], key=lambda d: d['name'])))
        if self.flag_edits:
            # the map's own pieces whose flags change where they stand (piece flags plan): written in the map by the
            # Build's writer (native_split moves them there), each with its box for the tiles it rebuilds
            # (and the map's ladders near them, whose top tiles the Build rebuilds first)
            near = self.flag_ladders()
            objects.append(dict(type='pieceFlags', pieces=sorted(self.flag_edits, key=lambda e: e['name']),
                                **({'ladders': near} if near else {})))
        if self.new_buildings:
            # buildings made from nothing: made in the map by the Build's writer (native_split moves them there)
            objects.append(dict(type='buildings', buildings=self.new_buildings))
        if self.building_edits:
            # the map's own buildings changed or deleted: edited in place by the Build's writer (buildings.edit)
            objects.append(dict(type='buildingEdits', edits=self.building_edits))
        name = re.sub(r'[^\x20-\x7E]|"|\|', '', self.doc.get('name') or '').strip() or 'variant'
        # The streamed patches' pieces the Build takes out of its copies of them ({stream: [actor]}): a moved or
        # deleted ladder's helpers (G6).
        extra = dict(streamHides={k: sorted(v) for k, v in sorted(self.stream_hides.items())}) if self.stream_hides else {}
        # a mission's objects moved in their streams (Part E): {stream: [move]}, moved in place in the stream's copy
        if self.stream_moves:
            extra['streamMoves'] = {k: sorted(v, key=lambda m: m['actor']) for k, v in sorted(self.stream_moves.items())}
        # a cleared map (Clear map plan, section 7): the Build's clear_level takes out what the editor never showed,
        # over the grid as the project has it
        if self.cleared:
            extra['cleared'] = dict(grid=self.stage_grid or list(self.scene['tileGrid']['dimensions'][:3]))
            box = self.outside_box() if self.keep_outside else None
            if box:
                extra['cleared']['keepOutside'] = box
        # the effects the map's pieces carry (export 23; tools/bake/native_effects.py): each follows its piece's move,
        # copy or delete in the Build ({piece: [effect]}, short names), but for one the project moves, deletes or
        # detaches itself (the effects and sounds plan, Part C: a record of its own takes it from its piece)
        carried = {}
        for e in self.scene.get('effects') or []:
            if e.get('carriedBy') and e['actor'] not in self.effect_own:
                carried.setdefault(e['carriedBy'].rsplit('.', 1)[-1], []).append(e['actor'].rsplit('.', 1)[-1])
        if carried:
            extra['carriedEffects'] = {k: sorted(v) for k, v in sorted(carried.items())}
        # the project's landing zones (section 4): the variant's LZArray lines, and the map's own landings moved
        # the project's spawn rules (spawns plan, SP8): the Build writes the variant's ExcludeMaps line
        if getattr(self, 'spawn_rules', None):
            extra['spawnRules'] = dict(self.spawn_rules)
        if self.zones is not None:
            extra['landingZones'] = dict(zones=self.zones, own=spawns.own_slots(self.zones, self.own_count),
                                         ownLandings=self.own_count)
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

    def map_buildings(self):
        """The export's own buildings (export 21 has their actors): {actor path: (record, why it stays fixed or None)}.
        Fixed: a building with no floors, a van's (it goes with the van), one with a floor that has no floor volume
        or a volume without a box (F-86, F-95), and a patch's. Older exports have none."""
        if getattr(self, '_map_buildings', None) is not None:
            return self._map_buildings
        out = {}
        for b in self.scene.get('buildings') or [] if (self.scene.get('exporterVersion') or 0) >= 21 else []:
            if not isinstance(b, dict) or not b.get('actor') or not isinstance(b.get('name'), str):
                continue
            floors = b.get('floors') or []
            why = None
            if not floors:
                why = 'it has no floors'
            elif b.get('van'):
                why = "it is a van's own building, which goes with the van"
            elif any(not f.get('volumes') for f in floors):
                why = 'a floor of it has no floor volume'
            elif any(len(f.get('boxes') or []) != len(f['volumes']) for f in floors):
                why = 'a floor volume of it has no box'
            elif not str(b.get('id')).isdigit():
                why = "it is a patch's"
            out[b['name']] = (b, why)
        self._map_buildings = out
        return out

    def buildings(self):
        """The project's `buildings` (optional; prefab plan 5.1; map buildings plan, sections 2 and 3).
        - Buildings made from nothing, each {id, name, kind: 'building' | 'ufo', floors: [{boxes: [[x0, y0, z0, x1,
          y1, z1]]}]}, floor 0 first, the boxes in world units and unturned. The Build makes a building volume and a
          floor volume for each box, and lists in each floor the pieces standing in it (tools/bake/buildings.py).
          A copied actor whose source building the building comes from (source_floor_match: the source's floors
          carried by the copy's move overlap the building's, their boxes edited or not) keeps what its map saved
          where the rule agrees with the source's boxes and with the building's (`carry`, buildings.carried): the
          map's hand-made inclusion and exclusion lists come along (a UFO's roof listed on its roof floor only).
        - The map's own buildings changed (`replaces` the map's building volume, each floor's `volumes` beside its
          boxes) or deleted (`deleted`): the Build edits them in place (buildings.edit). One the compiler can't use is
          passed over with a warning (building-replaces) and stays as exported; one unchanged (every box within
          BUILDING_SAME of its volume's, the same kind) builds nothing.
        Nothing here stops a Build but a record that can't be read (building-shape): a box outside the tile grid, two
        floors that meet, a floor away from the cursor's floors are warnings, and for the map's buildings only where a
        box changed (the map's own overlaps, as exported, are not reported)."""
        items = self.doc.get('buildings')
        if not items:
            return
        shape = ('each building must be {"id", "name", "kind": "building" or "ufo", "floors": [{"boxes": [[x0, y0, '
                 'z0, x1, y1, z1]]}]}, each floor with at least one box that has room in it; one of the map\'s has '
                 '"replaces": {"package", "level", "actor"} and each floor "volumes" as long as its boxes, or is '
                 '{"id", "replaces", "deleted": true}')

        def number(v):
            return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

        def well_formed(b):
            if not isinstance(b, dict) or not isinstance(b.get('id'), str) or not b['id'] \
                    or not isinstance(b.get('name', ''), str):
                return False
            rep = b.get('replaces')
            if rep is not None and not (isinstance(rep, dict) and set(rep) == {'package', 'level', 'actor'}
                                        and all(isinstance(v, str) for v in rep.values())):
                return False
            if 'deleted' in b:
                return b['deleted'] is True and rep is not None and 'floors' not in b
            if b.get('kind', 'building') not in BUILDING_KINDS:
                return False
            floors = b.get('floors')
            if not isinstance(floors, list) or not 1 <= len(floors) <= BUILDING_FLOORS_MAX:
                return False
            for f in floors:
                boxes = f.get('boxes') if isinstance(f, dict) else None
                if not isinstance(boxes, list) or not boxes:
                    return False
                for x in boxes:
                    if not (isinstance(x, list) and len(x) == 6 and all(number(v) for v in x)
                            and all(x[k + 3] - x[k] >= 1 for k in range(3))):
                        return False
                volumes = f.get('volumes')
                if rep is None and volumes is not None:
                    return False
                if rep is not None and not (isinstance(volumes, list) and len(volumes) == len(boxes) and all(
                        v is None or (isinstance(v, str) and v) for v in volumes)):
                    return False
            return True
        if not isinstance(items, list) or not all(well_formed(b) for b in items) \
                or len({b['id'] for b in items}) != len(items):
            self.error('building-shape', shape)
            return
        if not self.builds('building'):
            self.error('family', 'the project has %s. %s' % (FAMILIES['building']['what'], FAMILIES['building']['note']),
                       family='building')
            return
        grid = self.scene.get('tileGrid') or {}
        dims, origin, size = grid.get('dimensions'), grid.get('origin'), grid.get('size')
        if not (dims and origin and size):
            self.error('building-grid', 'the export of %s has no tile grid, which a building needs' % self.map)
            return
        count = list(getattr(self, 'stage_grid', None) or dims[:3])
        lo = [float(v) for v in origin[:3]]
        hi = [lo[k] + count[k] * size[k] for k in range(3)]
        storeys = self.cursor_storeys()

        def meet(a, b):
            return all(min(a[k + 3], b[k + 3]) - max(a[k], b[k]) > BUILDING_OVERLAP for k in range(3))

        # every box after the edit: dict(building id, label, floor, box, changed, own: the map's, authored)
        boxes, replaced, gone = [], set(), set()
        exported = self.map_buildings()
        for b in items:
            if b.get('replaces') is None:
                self.new_building(b, boxes)
                continue
            rep = b['replaces']
            where = dict(building=b['id'])
            found = exported.get(rep['actor']) if rep['package'].casefold() == self.map.casefold() and rep['level'] == 'base' else None
            why = found[1] if found else ('the export of %s has no buildings\' actors (export 21): prepare it again'
                                          % self.map if (self.scene.get('exporterVersion') or 0) < 21
                                          else 'it is not one of the map\'s buildings')
            if not why and rep['actor'] in replaced:
                why = 'an earlier record names it'
            if why:
                self.warn('building-replaces', 'the record for the map\'s building %s is passed over: %s; the building '
                          'stays as the map has it' % (short(rep['actor']), why), **where)
                continue
            replaced.add(rep['actor'])
            e = found[0]
            label = b.get('name') or e['actor']
            old = [[dict(volume=short(v), box=list(x['min']) + list(x['max'])) for v, x in zip(f['volumes'], f['boxes'])]
                   for f in e['floors']]
            if b.get('deleted'):
                gone.add(rep['actor'])
                if e.get('referencedBy'):
                    self.warn('mission-linked', "the map's building %s is named by the map's Kismet (%s): deleted, its "
                              "script acts on a volume out of the level" % (label, '; '.join(e['referencedBy'])), **where)
                self.building_edits.append(dict(id=b['id'], actor=e['actor'], name=label, deleted=True, old=old,
                                                kind='ufo' if e.get('isUfo') else 'building', moved=False))
                continue
            own_volumes = {v['volume']: v['box'] for f in old for v in f}
            floors, used = [], set()
            for k, f in enumerate(b['floors']):
                vols = []
                for v in f['volumes']:
                    if v is not None and (v not in own_volumes or v in used):
                        self.warn('building-replaces', 'floor %d of the map\'s building %s names the floor volume %s, '
                                  'which is %s: its box gets a new volume' % (
                                      k + 1, label, v, 'named twice' if v in used else 'not one of the building\'s'), **where)
                        v = None
                    if v is not None:
                        used.add(v)
                    vols.append(v)
                floors.append(dict(boxes=[[tidy(float(x), 3) for x in box] for box in f['boxes']], volumes=vols))
            same_box = lambda box, v: v is not None and all(abs(box[j] - own_volumes[v][j]) <= BUILDING_SAME for j in range(6))
            unchanged = (len(floors) == len(old) and (b.get('kind', 'building') == 'ufo') == bool(e.get('isUfo'))
                         and all(sorted(filter(None, f['volumes'])) == sorted(v['volume'] for v in o) and len(f['volumes']) == len(o)
                                 and all(same_box(x, v) for x, v in zip(f['boxes'], f['volumes'])) for f, o in zip(floors, old)))
            for k, f in enumerate(floors):
                for x, v in zip(f['boxes'], f['volumes']):
                    boxes.append(dict(building=b['id'], label=label, floor=k, box=x, own=True, authored=False,
                                      changed=not same_box(x, v),
                                      bottom=own_volumes[v][2] if v is not None else None))
            if unchanged:
                continue
            if e.get('referencedBy'):
                self.warn('mission-linked', "the map's building %s is named by the map's Kismet (%s): it is edited in "
                          "place, so the script still finds it, but moved or resized it may act differently"
                          % (label, '; '.join(e['referencedBy'])), **where)
            self.building_edits.append(dict(id=b['id'], actor=e['actor'], name=label, deleted=False,
                                            kind=b.get('kind', 'building'), floors=floors, old=old,
                                            moved=moved_whole(old, floors)))
        # the map's buildings left as exported (fixed ones too), and the ones of no record
        for path, (e, why) in exported.items():
            if path in replaced:
                continue
            for k, f in enumerate(e.get('floors') or []):
                for x in f.get('boxes') or []:
                    boxes.append(dict(building=map_building_id(e), label=e['actor'], floor=k, own=True, authored=False,
                                      box=list(x['min']) + list(x['max']), changed=False))
        if (self.scene.get('exporterVersion') or 0) < 21:
            # an older export: the map's floor volumes by building name (export 15)
            for name, index, xs in self.floor_boxes or []:
                for x in xs:
                    boxes.append(dict(building='map|' + name, label=short(name), floor=index, own=True, authored=False,
                                      box=list(x['min']) + list(x['max']) if isinstance(x, dict) else list(x), changed=False))
        # the warnings, for each changed or new box
        said = set()
        for n, item in enumerate(boxes):
            if not item['changed']:
                continue
            x, k, label = item['box'], item['floor'], item['label']
            where = dict(building=item['building'], floor=k, box=x)
            if any(x[j] < lo[j] - 0.5 or x[j + 3] > hi[j] + 0.5 for j in range(3)):
                self.note('building-outside', 'floor %d of the building %s reaches outside the map\'s tile grid: the '
                          'game has no tiles there' % (k + 1, label), **where)
            for m, other in enumerate(boxes):
                if m == n or (other['building'] == item['building'] and (other['floor'] == k or item['authored'])):
                    continue
                if (min(m, n), max(m, n)) in said or not meet(x, other['box']):
                    continue
                said.add((min(m, n), max(m, n)))
                whose = ('the same building' if other['building'] == item['building'] else
                         "the map's own building %s" % other['label'] if other['own'] and not other['changed']
                         else 'the building %s' % other['label'])
                self.warn('building-overlap', 'floor %d of the building %s overlaps floor %d of %s: a piece in both is '
                          'listed by both, and a unit there may see either floor cut away' % (k + 1, label, other['floor'] + 1, whose),
                          **where)
            starts = sorted({round(c[2], 2) for _, c in storeys or []
                             if min(c[3], x[3]) - max(c[0], x[0]) > 0 and min(c[4], x[4]) - max(c[1], x[1]) > 0})
            # (a map box at its volume's own height, moved sideways or stretched across, is as the map had it)
            same_height = item.get('bottom') is not None and abs(item['bottom'] - x[2]) <= BUILDING_SAME
            if starts and not same_height and not any(abs(x[2] - z) <= CURSOR_NEAR for z in starts):
                self.warn('building-cursor', 'floor %d of the building %s starts at %g, away from where the cursor\'s '
                          'floors start there (%s): the mouse wheel would not stop at this storey'
                          % (k + 1, label, x[2], ', '.join('%g' % z for z in starts)), starts=starts, **where)
        if self.errors:
            self.new_buildings, self.building_edits = [], []

    def new_building(self, b, boxes):
        """A building made from nothing (buildings()): into self.new_buildings, with `carry` {copy label: dict(saved:
        [[floor, CutdownFloor]] as its map saved them, floors: its source building's boxes carried by the copy's move,
        floor_map: the building's floor for each of those)} for the copies whose source building it comes from
        (source_floor_match); its boxes into `boxes`."""
        label = b.get('name') or b['id']
        carry = {}
        for copy in self.copies:
            source = self.floor_sources.get(copy['label'])
            if source is None:
                continue
            donor = copy.get('donor')
            originals = self.donor_buildings.get(donor['package'].casefold(), []) if donor else (self.scene.get('buildings') or [])
            before = dict(location=source.get('floorLocation', source['location']), rotation=source['rotation'])
            match = source_floor_match(originals, b['floors'], before, copy['location'], copy['rotation'])
            if match:
                carry[copy['label']] = dict(
                    saved=[[f['floor'], f['cutdownFloor']] for f in source.get('floors', []) if f['building'] == match['building']['id']],
                    floors=[[[tidy(v, 3) for v in x] for x in f] for f in match['moved']], floor_map=match['floor_map'])
        for k, f in enumerate(b['floors']):
            for x in f['boxes']:
                boxes.append(dict(building=b['id'], label=label, floor=k, box=[float(v) for v in x], own=False,
                                  authored=bool(carry), changed=True))
        self.new_buildings.append(dict(id=b['id'], name=b.get('name') or '', kind=b.get('kind', 'building'),
                                       **({'carry': carry} if carry else {}),
                                       floors=[dict(boxes=[[tidy(float(v), 3) for v in x] for x in f['boxes']])
                                               for f in b['floors']]))

    def stage(self):
        """The project's `stage` (optional): `grid` [nx, ny] or [nx, ny, nz], the map's tile grid made that many tiles
        from its own corner (prefab plan 5.11; the Build's shell stage resizes it) and, with nz, that many levels from
        its own bottom (5.6b), `ground` (false: lay no ground over the new area), `lines` (true: the ground drawn as a
        grid, its planes hidden and a white line on every tile edge; 5.11) and `hideGround` (true: the planes hidden, no
        lines). A map as it is, the blank map among them, only grows (the user, 13 November 2026: any map, where
        before only the blank map); a cleared project's grid (Clear map plan, section 6) may also be smaller in any of
        the three, from 1 tile or level. Each is at most STAGE_GRID_MAX tiles or STAGE_LEVELS_MAX levels, or the map's
        own where that is more (stage_max).
        Sets self.stage_grid to [nx, ny, nz] when the grid differs from the map's, else None."""
        self.stage_grid = None
        stage = self.doc.get('stage')
        if stage is None:
            return
        grid = stage.get('grid') if isinstance(stage, dict) else None
        if not (isinstance(grid, list) and len(grid) in (2, 3) and all(isinstance(v, int) and not isinstance(v, bool) for v in grid)) \
                or any(stage.get(k) not in (None, True, False) for k in ('ground', 'lines', 'hideGround')):
            self.error('stage-shape', 'the project\'s map size must be {"grid": [tiles across, tiles deep]} or '
                                      '{"grid": [tiles across, tiles deep, levels]}, with an optional "ground", '
                                      '"lines" and "hideGround", each true or false')
            return
        bare = self.map in STAGE_MAPS
        grows_only = not getattr(self, 'cleared', False)
        own = (self.scene.get('tileGrid') or {}).get('dimensions')
        if not own:
            self.error('stage-grid', 'the export of %s has no tile grid to resize' % self.map)
            return
        if not bare and any(stage.get(k) is not None for k in ('lines', 'hideGround')):
            self.note('stage-ground', '"lines" and "hideGround" are the blank map\'s; on %s they do nothing' % self.map)
        if getattr(self, 'cleared', False) and stage.get('ground') is not None:
            self.note('stage-ground', '"ground" does nothing on a cleared map: it lays no ground')
        grid = list(grid[:2]) + [grid[2] if len(grid) == 3 else own[2]]
        if grows_only and (grid[0] < own[0] or grid[1] < own[1]):
            self.error('stage-grid', '%s can be made larger, not smaller, until it is cleared: %d by %d tiles against its '
                       'own %d by %d' % ('the blank map' if bare else self.map, grid[0], grid[1], own[0], own[1]),
                       grid=grid, own=own[:2])
            return
        most = stage_max(own)
        if not (1 <= grid[0] <= most[0] and 1 <= grid[1] <= most[1]):
            self.error('stage-grid', 'the map can be from 1 to %d tiles across and 1 to %d deep (asked: %d by %d)'
                       % (most[0], most[1], grid[0], grid[1]), grid=grid, own=own[:3])
            return
        lowest = own[2] if grows_only else 1
        if not lowest <= grid[2] <= most[2]:
            self.error('stage-grid', 'the map can be from %d up to %d levels high (asked: %d)'
                       % (lowest, most[2], grid[2]), grid=grid, own=own[:3])
            return
        if grid != list(own[:3]):
            self.stage_grid = grid
            if grows_only and not bare:
                words = []
                if grid[:2] != list(own[:2]):
                    words.append('the Build lays more of the map\'s ground over the new area only where it is laid as '
                                 'planes, and makes the map\'s own low scenery there (ground, pavements) walkable; '
                                 'elsewhere lay floors')
                if grid[2] > own[2]:
                    words.append('the cursor reaches the new levels by storeys the Build adds over the whole grid, above '
                                 'the map\'s own cursor volumes')
                self.note('stage-grown-map', '%s made larger as it is: %s' % (self.map, '; '.join(words)),
                          grid=grid, own=own[:3])

    def spawn_rules_mark(self):
        """The project's `spawnRules` (schema 4; spawns plan, SP8): left out or null, scripted drop-ins play as the
        install plays them; {"dropIns": "placed"}, Long War's scripted drop-ins land where placed: the Build adds the
        variant to its drop-in mutator's ExcludeMaps list (DefaultRandomSpawns.ini). Anything else is refused
        (spawn-rules): a newer editor's rule this one can't build."""
        self.spawn_rules = None
        rules = self.doc.get('spawnRules')
        if rules is None:
            return
        if rules != {'dropIns': 'placed'}:
            self.error('spawn-rules', 'the project\'s spawn rules must be {"dropIns": "placed"} or left out; it has %s, '
                       'which this editor can\'t build' % json.dumps(rules)[:160])
            return
        self.spawn_rules = dict(dropIns='placed')

    def spawn_rules_notes(self):
        """Notes on the spawn rule (spawns plan, SP8): dropins-placed says what it covers, the scripted actions that
        drop aliens in at points of the map and of the streams of the missions the variant keeps (export 33's `uses`),
        and that wave systems are never moved by Long War; dropins-base-excluded, with no rule, that the install's
        ExcludeMaps names the base map (the Chryssalid Hive) but not the variant, which has a name of its own."""
        variant = self.out['shipAs']
        if self.spawn_rules:
            actions = set()
            for r in self.scene.get('spawns') or []:
                if isinstance(r, dict) and r.get('kind') == 'dropIn':
                    actions.update(('the map', a) for a in scripted_users(r))
            for _, _, stream, objects in self.kept_streams():
                for o in objects:
                    if o.get('kind') == 'dropIn':
                        actions.update((stream, a) for a in scripted_users(o))
            labels = [m.get('label') or 'mission %d' % (i + 1) for i, m in self.kept_missions()]
            labels += ['%s (added)' % missions.label(k) for k in sorted(self.added_kinds())]
            places = sorted({where for where, _ in actions})
            covers = ('%d scripted %s in %s' % (len(actions), 'action' if len(actions) == 1 else 'actions', ', '.join(places))
                      if actions else 'every scripted drop-in (the export finds no scripted action dropping aliens in)')
            self.note('dropins-placed', 'Scripted drop-ins land where placed: the Build adds %s to Long War\'s ExcludeMaps list '
                      '(DefaultRandomSpawns.ini), for %s of %s (%s), and Long War\'s drop-in mutator gives them neither its '
                      'overwatch nor its reveal; wave systems\' drop-ins are never moved by Long War. Plain Enemy Within '
                      'plays them where placed already, and the Build writes nothing there'
                      % (variant, covers, 'the one mission' if len(labels) == 1 else 'every mission', ', '.join(labels)),
                      actions=len(actions), missions=labels)
            return
        game = getattr(self.library, 'game', None)
        if not isinstance(game, (str, Path)) or not game:
            return
        viewer = str(Path(__file__).resolve().parents[1] / 'viewer')
        if viewer not in sys.path:
            sys.path.append(viewer)
        import spawnrules
        try:
            found = spawnrules.rules(game)
        except (OSError, ValueError):
            return
        if found.get('dropIns') == 'active' and spawnrules.excluded(found, self.map) and not spawnrules.excluded(found, variant):
            self.note('dropins-base-excluded', 'Long War\'s ExcludeMaps names %s, so its drop-in mutator leaves the map\'s '
                      'scripted drop-ins where placed; %s has a name of its own, and Long War moves them near the squad '
                      'there unless the project leaves them where placed (the Spawns view\'s flyout)' % (self.map, variant))

    def cleared_mark(self):
        """The project's `cleared` (Clear map plan, section 6): true says the Build takes out what the editor never
        showed and puts one rebuild volume over the whole grid. The pieces themselves go by their delete records."""
        cleared = self.doc.get('cleared', False)
        if cleared not in (True, False):
            self.error('cleared-shape', '"cleared" must be true or false')
            cleared = False
        self.cleared = cleared is True
        # `clearKeepsOutside` (the Clear map window's "Keep the scenery outside the play area"): the clear left the
        # pieces wholly outside the play area, and the Build's clear_level leaves the lights, emitters, decals and
        # lens flares placed outside it (outside_box). Without `cleared` it says nothing.
        keeps = self.doc.get('clearKeepsOutside', False)
        if not isinstance(keeps, bool):
            self.error('cleared-shape', '"clearKeepsOutside" must be true or false')
            keeps = False
        self.keep_outside = self.cleared and keeps is True
        if self.cleared:
            # LWR's patch levels for the map: every piece of them out of the variant's copies (section 7, step 4).
            # The mission's own streamed levels are left.
            for stream, info in sorted((self.scene.get('streams') or {}).items()):
                if info.get('kind') == 'lwr':
                    for o in info.get('objects') or []:
                        self.stream_hides.setdefault(stream, set()).add(short(o['actor']))

    def outside_box(self):
        """What a clear that keeps the scenery outside the play area counts as the play area, across: [x0, y0, x1, y1],
        the map's level volume (playableBounds, in the viewer's basis [x, up, y]) and the grid as the project has it
        together. A piece or an actor wholly outside it stays."""
        b, g = self.scene.get('playableBounds') or {}, self.grid_box()
        boxes = ([[b['min'][0], b['min'][2], b['max'][0], b['max'][2]]] if b.get('min') and b.get('max') else []) \
            + ([[g[0], g[1], g[3], g[4]]] if g else [])
        if not boxes:
            return None
        return [float(min(v[0] for v in boxes)), float(min(v[1] for v in boxes)),
                float(max(v[2] for v in boxes)), float(max(v[3] for v in boxes))]

    def grid_box(self):
        """The tile grid as the project has it: [x0, y0, z0, x1, y1, z1], or None without one."""
        grid = self.scene.get('tileGrid') or {}
        if not grid.get('origin') or not grid.get('dimensions'):
            return None
        o, size = grid['origin'], grid.get('size') or [TILE, TILE, STOREY]
        dims = getattr(self, 'stage_grid', None) or grid['dimensions']
        return [float(o[0]), float(o[1]), float(o[2]), float(o[0]) + dims[0] * size[0], float(o[1]) + dims[1] * size[1],
                float(o[2]) + dims[2] * size[2]]

    def stage_outside(self):
        """The warning for the project's pieces and cover blocks wholly outside a grid the project sized
        (stage-outside): counted, the first few named. A piece is outside when the middle of its box's floor is
        outside the grid's sides, or its box reaches no level of the grid (a piece sunk into the ground, or reaching
        over its top, still stands in it). Lights and building floors are left out: a light lights anything, and a
        floor box beyond the grid only covers a place with no tiles (the user, 14 November 2026: warnings only for
        what can cause a problem in the game)."""
        if not self.stage_grid:
            return
        g = self.grid_box()

        def outside(b):
            x, y = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
            return not (g[0] <= x <= g[3] and g[1] <= y <= g[4]) or b[5] < g[2] or b[4] > g[5]
        out = []
        for c in self.copies:
            if outside(c['box']):
                out.append(c['label'].split(':', 1)[-1])
        for c in self.covers:
            if c.get('box') and outside(c['box']):
                out.append(c['name'])
        if out:
            self.warn('stage-outside', '%d of the project\'s pieces stand outside the %d by %d by %d '
                      'grid: there are no tiles there to stand on or take cover by (%s%s)'
                      % (len(out), self.stage_grid[0], self.stage_grid[1], self.stage_grid[2], ', '.join(out[:5]),
                         ', ...' if len(out) > 5 else ''), count=len(out), names=out[:12])

    # ---------------------------------------------------------------- landing zones (Clear map plan, section 4)
    def landing_zones(self):
        """The project's landing zones (`landingZones`, optional): checked for shape (a malformed list is an error,
        nothing to build from), then warned of: a soldier point over no floor (landing-floor), a piece the project
        puts on one (landing-blocked), a zone outside the grid (landing-outside), more zones than the map has landings
        of its own (landing-lwr-only), a zone that plays nowhere (landing-unused), none (landing-none). Without the
        list, the map's own landings are checked the same way on a cleared or resized project. Sets self.zones (the
        list, tidied, or None) and self.own_count."""
        self.zones = None
        own = spawns.own_landings(self.scene)
        self.own_landings_found = own
        self.own_count = len(own)
        raw = self.doc.get('landingZones')
        if raw is None:
            if self.cleared or self.stage_grid:
                self.check_zones([dict(o['zone'], id='own%d' % (k + 1)) for k, o in enumerate(own)], own=True)
            return
        if not isinstance(raw, list):
            self.error('landing-shape', '"landingZones" must be a list of landing zones')
            return
        bad = [k for k, z in enumerate(raw) if not spawns.valid_zone(z)]
        for k in bad:
            self.error('landing-shape', 'landing zone %d is not {id, location: [x, y, z], direction, kind, ...}' % (k + 1),
                       record='landingZones[%d]' % k)
        ids = [z.get('id') for z in raw if isinstance(z, dict)]
        if len(set(ids)) != len(ids):
            self.error('landing-shape', 'two landing zones have the same id')
        if bad or len(set(ids)) != len(ids):
            return
        self.zones = [tidy_zone(z) for z in raw]
        if not self.zones:
            self.warn('landing-none', 'the project has no landing zone: LWR gets no line for the map, and a plain '
                      'install plays the map\'s own landing where it stands')
            return
        slots = spawns.own_slots(self.zones, self.own_count)
        lwr_only = [k + 1 for k in range(len(self.zones)) if k not in slots and self.zones[k].get('lwr', True) is not False]
        nowhere = [k + 1 for k in range(len(self.zones)) if k not in slots and self.zones[k].get('lwr', True) is False]
        if lwr_only:
            self.warn('landing-lwr-only', '%s %s under Long War only: a plain install plays the map\'s %d landing%s of '
                      'its own, at the zones marked Plain EW' % (zone_words(lwr_only), 'plays' if len(lwr_only) == 1 else 'play',
                                                                self.own_count, '' if self.own_count == 1 else 's'),
                      zones=lwr_only)
        marked = [k + 1 for k, z in enumerate(self.zones) if z.get('ew') is True]
        if spawns.explicit(self.zones) and len(marked) > self.own_count:
            self.warn('landing-ew-extra', '%d zones are marked Plain EW, and the map has %d landing%s of its own: %s '
                      'play%s under Long War only' % (len(marked), self.own_count, '' if self.own_count == 1 else 's',
                                                      zone_words(marked[self.own_count:]),
                                                      's' if len(marked) - self.own_count == 1 else ''),
                      zones=marked[self.own_count:])
        if len(slots) < self.own_count:
            self.warn('landing-ew-fewer', 'a plain install also lands at %d of the map\'s own landing%s where the map has '
                      '%s: only %d zone%s %s marked Plain EW' % (
                          self.own_count - len(slots), '' if self.own_count - len(slots) == 1 else 's',
                          'it' if self.own_count - len(slots) == 1 else 'them', len(slots), '' if len(slots) == 1 else 's',
                          'is' if len(slots) == 1 else 'are'),
                      missing=self.own_count - len(slots))
        if nowhere:
            self.warn('landing-unused', '%s %s no line for Long War and %s none of the map\'s own landings, so %s '
                      'never played' % (zone_words(nowhere), 'has' if len(nowhere) == 1 else 'have',
                                        'is' if len(nowhere) == 1 else 'are', 'it is' if len(nowhere) == 1 else 'they are'),
                      zones=nowhere)
        self.check_zones(self.zones)

    def kept_missions(self):
        """The base map's missions the variant keeps (mission types plan, D1): [(index, the export's mission)]: the
        document's `missions` entries that name a record ({record: i}), else every mission of the export."""
        found = [m for m in self.scene.get('missions') or [] if isinstance(m, dict)]
        listed = self.doc.get('missions')
        if not isinstance(listed, list):
            return list(enumerate(found))
        return [(e['record'], found[e['record']]) for e in listed
                if isinstance(e, dict) and isinstance(e.get('record'), int) and 0 <= e['record'] < len(found)]

    def kept_streams(self):
        """Each stream of the missions the variant keeps with its objects (export 24): [(label, index or kind, stream,
        objects)], the kept records' streams, then an added kind's donor stream (export 33: the added bomb's
        Slaughterhouse stream) where no kept record streams it already."""
        streams = self.scene.get('streams') or {}
        out, named = [], set()
        for index, mission in self.kept_missions():
            label = mission.get('label') or 'mission %d' % (index + 1)
            for name in mission.get('streams') or []:
                named.add(name)
                objects = (streams.get(name) or {}).get('missionObjects') or []
                if objects:
                    out.append((label, index, name, objects))
        for kind in sorted(self.added_kinds()):
            donor = (self.scene.get('donors') or {}).get(kind)
            if isinstance(donor, dict) and donor.get('stream') and donor['stream'] not in named and donor.get('missionObjects'):
                out.append(('%s (added)' % missions.label(kind), kind, donor['stream'], donor['missionObjects']))
        return out

    def missions_check(self):
        """What an edit means for the map's missions (private/plans/done/mission-types-plan.md): a note for a map the
        game knows by its whole name (missions.NAMED_MAPS: the Build's records can't keep it, plan Part B), and, for
        each mission the variant keeps, its stream's objects (export 24) against the edit (C3): mission_objects."""
        why = missions.named_map(self.map) or (missions.named_map(self.package) if self.package != self.map else None)
        if why:
            self.note('named-map', '%s is known by its name in the game\'s script, which a variant can\'t keep: %s.'
                      % (self.map, why))
        self.mission_list()
        self.mission_objects()
        self.spawn_places()
        self.spawn_rules_notes()

    def mission_list(self):
        """The project's `missions` (D1, optional): an error when it is no list, is empty or has an entry the Build can't
        write (the package would have no record to play); a warning for a UFO mission on a map with no UFO building
        (mission-ufo: Long War puts the commander's pod in the UFO's building volume, O-5), a note for a bomb mission
        added (mission-bomb: Long War's mutator places it; plain Enemy Within plays Slaughterhouse's places)."""
        listed = self.doc.get('missions')
        if listed is None:
            return
        records = len([m for m in self.scene.get('missions') or [] if isinstance(m, dict)])
        if not isinstance(listed, list) or not listed:
            self.error('missions', 'the project\'s missions must be a list of at least one: with none the Build writes no '
                       'record to play')
            return
        bad = [k + 1 for k, e in enumerate(listed) if not missions.valid_entry(e, records)]
        if bad:
            self.error('missions', 'mission%s %s of the project\'s list %s neither one of the base map\'s %d records nor a '
                       'kind a record alone gives a map (%s)' % ('' if len(bad) == 1 else 's', numbers(bad),
                                                              'is' if len(bad) == 1 else 'are', records,
                                                              ', '.join(missions.ADDED_KINDS)))
            return
        kinds = {e['kind'] for e in listed if 'kind' in e}
        if kinds & {'Crash', 'LandedUFO'}:
            gone = {e['actor'] for e in self.building_edits if e.get('deleted')}
            ufo = any(b.get('kind') == 'ufo' for b in self.new_buildings) or any(
                e.get('isUfo') and e.get('name', e.get('actor')) not in gone and e.get('actor') not in gone
                for e in self.scene.get('buildings') or [])
            if not ufo:
                self.warn('mission-ufo', 'the project is for a UFO mission and the map has no UFO building: Long War puts '
                          'the commander\'s pod in the UFO, so place a UFO prefab')
        if 'Special/Bomb' in kinds:
            self.note('mission-bomb', 'the bomb mission streams %s: Long War\'s bomb mutator places its bomb and power '
                      'nodes on the map; plain Enemy Within would play them where Slaughterhouse has them'
                      % missions.BOMB_STREAM)

    # a mission's objects that a soldier, the operative or a VIP must reach, or that stand for an objective: a warning
    # when the edit leaves one over no floor or inside a piece (C3); drop-in points and pods only get a note (Long War
    # places most of its drop-ins and pods itself)
    MISSION_REACHED = {'capturePoint', 'radar', 'bomb', 'powerNode', 'use', 'soldier', 'landing', 'operative', 'vip'}
    MISSION_SPAWNS = {'dropIn', 'pod'}

    def mission_objects(self):
        """C3, for each mission the variant keeps (kept_missions) and each stream of it that has objects: a warning
        (mission-object) for an objective, a landing's or soldier's point, the operative's or a VIP's point that had
        floor under it before the edit and has none now (the map's saved floor tiles that stay, and the floor the
        project's flat copies give), or that a copy of the project stands on; a warning (mission-capture) for a capture
        volume with none of its floor tiles left; a note (mission-spawns) for the drop-in points and pods that lose
        their floor; on a cleared map, a note (mission-cleared) that the stream's objects stand where the original map
        had them. Warnings only: the Build goes on. Each names its mission (mission, missionIndex) and the object's
        stream and actor, for the build window's list by mission."""
        grid = self.scene.get('tileGrid') or {}
        origin = grid.get('origin')
        kept = self.kept_streams()
        if not origin or not kept:
            return
        size = grid.get('size') or [TILE, TILE, STOREY]
        before = {tuple(f['tile']) for f in ((self.scene.get('tactical') or {}).get('floorTiles') or [])}
        added, _ = self.added_floors()
        now = self.floor_now() | set(added)
        corner = tile_corner(grid)      # an object's tile as the game counts it
        tile = lambda p, dz=0: (int(math.floor((p[0] - corner[0]) / size[0])), int(math.floor((p[1] - corner[1]) / size[1])),  # noqa: E731
                                int(math.floor((p[2] - corner[2]) / size[2])) + dz)
        under = lambda p, floors: tile(p) in floors or tile(p, -1) in floors  # noqa: E731
        solid = [c for c in self.copies if c.get('box') and c.get('actorClass') != 'XComLadder' and c['box'][5] - c['box'][4] > FLOOR_THICK]
        seen = set()
        g = self.grid_box()
        for label, index, name, objects in kept:
            where = dict(mission=label, missionIndex=index) if isinstance(index, int) else dict(mission=label, missionKind=index)
            donor = not isinstance(index, int)
            unmoved = [o for o in objects if self.moved_object(name, o)[1] is None]
            if self.cleared and unmoved and not donor:
                self.note('mission-cleared', '%s: %s of %s stand where the original map had them, on a cleared map: '
                          'place them, or drop the mission' % (label, '%d objects' % len(unmoved) if len(unmoved) != len(objects)
                                                              else 'the %d objects' % len(objects), name), stream=name, **where)
            lost = []
            for o in objects:
                p, offset = self.moved_object(name, o)
                key = (index, name, o.get('actor'))
                if key in seen:
                    continue
                seen.add(key)
                short = str(o.get('actor') or '').rsplit('.', 1)[-1]
                what = missions.object_words(o)
                if o.get('actorClass') == 'XComCapturePointVolume' and o.get('box'):
                    d = offset or [0, 0, 0]
                    b = dict(min=[o['box']['min'][k] + d[k] for k in range(3)], max=[o['box']['max'][k] + d[k] for k in range(3)])
                    inside = lambda t: (b['min'][0] <= origin[0] + (t[0] + 0.5) * size[0] <= b['max'][0]  # noqa: E731
                                        and b['min'][1] <= origin[1] + (t[1] + 0.5) * size[1] <= b['max'][1]
                                        and b['min'][2] - size[2] <= origin[2] + t[2] * size[2] <= b['max'][2])
                    had = [t for t in before if inside(t)] if offset is None else [None]
                    if had and not any(inside(t) for t in now):
                        self.warn('mission-capture', '%s: %s (%s) has none of its %d floor tiles left: no soldier can '
                                  'stand in it to capture it' % (label, what, short, len(had)),
                                  stream=name, actor=o.get('actor'), **where)
                    continue
                kind = o.get('kind')
                if kind not in self.MISSION_REACHED and kind not in self.MISSION_SPAWNS:
                    continue
                if o.get('role') in ('effect', 'rebuild', 'visible', 'waypoint', 'volume', 'point'):
                    continue
                if donor:
                    # an added kind's object stands where its own map has it until placed: its fallback place
                    # (Long War plays it there when it finds no place of its own), checked on this map as it is
                    if kind in ('bomb', 'powerNode') and offset is None:
                        out_grid = g is not None and not (g[0] <= p[0] <= g[3] and g[1] <= p[1] <= g[4])
                        inside = next((c for c in solid if c['box'][0] <= p[0] <= c['box'][1] and c['box'][2] <= p[1] <= c['box'][3]
                                       and c['box'][4] < p[2] + STOREY and c['box'][5] > p[2] - 24), None)
                        why = ('off the map\'s grid' if out_grid else 'over no floor' if not under(p, now)
                               else 'inside %s' % inside['label'].split(':', 1)[-1] if inside else None)
                        if why:
                            self.warn('mission-donor-place', '%s: %s (%s) still stands where %s has it, which here is %s: Long '
                                      'War plays it there when it finds no place of its own; place it on the map'
                                      % (label, what, short, name, why), stream=name, actor=o.get('actor'), **where)
                        continue
                # (moved, it needs floor where it stands now, whatever the map had there)
                bare = (under(p, before) or offset is not None) and not under(p, now)
                on = next((c for c in solid if c['box'][0] <= p[0] <= c['box'][1] and c['box'][2] <= p[1] <= c['box'][3]
                           and c['box'][4] < p[2] + STOREY and c['box'][5] > p[2] - 24), None)
                if kind in self.MISSION_SPAWNS:
                    if bare or on: lost.append(o)
                    continue
                if bare:
                    self.warn('mission-object', '%s: %s (%s) has no floor under it now: %s' % (
                        label, what, short, missions.object_risk(o)), stream=name, actor=o.get('actor'), **where)
                if on:
                    self.warn('mission-object', '%s: %s (%s) is inside %s now: %s' % (
                        label, what, short, on['label'].split(':', 1)[-1], missions.object_risk(o)),
                        stream=name, actor=o.get('actor'), **where)
            if lost:
                count = {}
                for o in lost: count[o['kind']] = count.get(o['kind'], 0) + 1
                words = ', '.join('%d %s' % (n, missions.object_words(dict(kind=k), plural=n != 1)) for k, n in sorted(count.items()))
                self.note('mission-spawns', '%s: %s of %s stand over no floor or inside a piece now (Long War places '
                          'most drop-ins and pods itself; plain Enemy Within uses them where they stand)'
                          % (label, words, name), stream=name, **where)

    def projected_spawns(self):
        """The base map's spawn points as the variant will have them (export 33: scene.json's `spawns`): [(record,
        location)], a point a delete record takes out left out. Spawns plan, SP5; the base point edits (SP6, SP7) move,
        copy and delete them here."""
        gone = {e['target'] for e in self.entities if e['kind'] == 'delete' or (e['kind'] == 'spawn' and e['op'] == 'delete')}
        moved = {e['target']: e['location'] for e in self.entities if e['kind'] == 'spawn' and e['op'] == 'move'}
        valued = {e['target']: e['spawn'] for e in self.entities if e['kind'] == 'spawn' and e['op'] == 'values'}
        with_values = lambda r, values: dict(r, values=dict(r.get('values') or {}, **{  # noqa: E731
            k: {'value': v, 'from': 'project'} for k, v in (values or {}).items()})) if values else r
        out = [(with_values(r, valued.get(r['actor'])), moved.get(r['actor'], r['location'])) for r in self.scene.get('spawns') or []
               if isinstance(r, dict) and isinstance(r.get('location'), list) and r.get('actor') not in gone]
        # (a copy: its template's record under its own name, with its values; never one the map had)
        for e in self.entities:
            if e['kind'] == 'spawn' and e['op'] == 'add':
                t = self.spawn_actors.get(e['template'])
                if t:
                    out.append((with_values(dict(t, actor=e['entity'], copied=True), e.get('spawn')), e['location']))
        return out

    def spawn_places(self):
        """The base map's pods and Meld points against the edit (spawns plan, SP5): a pod or Meld point's place is usable
        when it is in the grid, over floor (the map's that stays, or the project's own) and in no solid piece of the
        project. Warnings: spawn-pod-places when fewer pod places are usable than the map had (plain Enemy Within, and
        the missions Long War's pod mutator leaves alone, put a pod at each: fewer places than pods can lose one);
        spawn-meld-group when a Meld spawn group loses every usable hard point, or every point, it had. A note,
        spawn-outside, counts the points a resized grid leaves outside. Each names the variant's mission (its one, or
        every one) and the first point it is about, for the build window's "show"."""
        grid = self.scene.get('tileGrid') or {}
        records = self.projected_spawns()
        if not grid.get('origin') or not grid.get('dimensions') or not records:
            return
        size = grid.get('size') or [TILE, TILE, STOREY]
        corner = tile_corner(grid)
        tile = lambda p, dz=0: (int(math.floor((p[0] - corner[0]) / size[0])), int(math.floor((p[1] - corner[1]) / size[1])),  # noqa: E731
                                int(math.floor((p[2] - corner[2]) / size[2])) + dz)
        before = {tuple(f['tile']) for f in ((self.scene.get('tactical') or {}).get('floorTiles') or [])}
        added, _ = self.added_floors()
        now = self.floor_now() | set(added)
        o, dims = grid['origin'], grid['dimensions']
        box_before = [o[0], o[1], o[0] + dims[0] * size[0], o[1] + dims[1] * size[1]]
        g = self.grid_box()
        box_now = [g[0], g[1], g[3], g[4]]
        solid = [c for c in self.copies if c.get('box') and c.get('actorClass') != 'XComLadder' and c['box'][5] - c['box'][4] > FLOOR_THICK]
        inside_box = lambda p, b: b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]  # noqa: E731
        in_piece = lambda p: any(c['box'][0] <= p[0] <= c['box'][1] and c['box'][2] <= p[1] <= c['box'][3]  # noqa: E731
                                 and c['box'][4] < p[2] + STOREY and c['box'][5] > p[2] - 24 for c in solid)
        under = lambda p, floors: tile(p) in floors or tile(p, -1) in floors  # noqa: E731
        was = lambda r: not r.get('copied') and inside_box(r['location'], box_before) and under(r['location'], before)  # noqa: E731
        usable = lambda p: inside_box(p, box_now) and under(p, now) and not in_piece(p)  # noqa: E731
        labels = [m.get('label') or 'mission %d' % (i + 1) for i, m in self.kept_missions()]
        labels += ['%s (added)' % missions.label(k) for k in sorted(self.added_kinds())]
        where = dict(mission=labels[0] if len(labels) == 1 else 'Every mission of the variant')
        name = lambda r: str(r.get('actor') or '').rsplit('.', 1)[-1]  # noqa: E731

        pods = [(r, p) for r, p in records if r.get('kind') == 'pod']
        had = [r for r, _ in pods if was(r)]
        has = [r for r, p in pods if usable(p)]
        if len(has) < len(had):
            lost = next((r for r, p in pods if was(r) and not usable(p)), None) or had[0]
            self.warn('spawn-pod-places', '%s: %d of the map\'s pod places are usable now, where %d were (in the grid, over '
                      'floor, in no piece of the project), %s among those lost: plain Enemy Within, and the missions Long '
                      'War\'s pod mutator leaves alone, put a pod at each place, and with fewer places than pods it can '
                      'lose one' % (where['mission'], len(has), len(had), name(lost)), actor=lost.get('actor'),
                      before=len(had), now=len(has), **where)

        groups = {}
        for r, p in records:
            if r.get('kind') == 'meld':
                group = ((r.get('values') or {}).get('spawnGroup') or {}).get('value', 0)
                groups.setdefault(group if isinstance(group, int) else 0, []).append((r, p))
        for group, points in sorted(groups.items()):
            hard = lambda r: str(((r.get('values') or {}).get('difficulty') or {}).get('value', '')).endswith('Hard')  # noqa: E731
            had_any = [r for r, _ in points if was(r)]
            has_any = [r for r, p in points if usable(p)]
            had_hard = [r for r in had_any if hard(r)]
            has_hard = [r for r in has_any if hard(r)]
            if had_any and not has_any:
                self.warn('spawn-meld-group', '%s: Meld spawn group %d has none of its %d usable points left (in the grid, '
                          'over floor, in no piece of the project): when the mission picks this group it places no '
                          'canister' % (where['mission'], group, len(had_any)), actor=had_any[0].get('actor'),
                          group=group, **where)
            elif had_hard and not has_hard:
                self.warn('spawn-meld-group', '%s: Meld spawn group %d has none of its %d usable hard points left (in the '
                          'grid, over floor, in no piece of the project): the mission places a hard canister of the group '
                          'first, and without one it places fewer' % (where['mission'], group, len(had_hard)),
                          actor=had_hard[0].get('actor'), group=group, **where)

        if self.stage_grid:
            out = [r for r, p in records if r.get('kind') in ('pod', 'meld') and not r.get('copied') and inside_box(r['location'], box_before)
                   and not inside_box(p, box_now)]
            if out:
                count = {}
                for r in out: count[r['kind']] = count.get(r['kind'], 0) + 1
                words = ' and '.join('%d %s' % (n, ('pod' if k == 'pod' else 'Meld point') + ('s' if n != 1 else ''))
                                     for k, n in sorted(count.items(), key=lambda kv: kv[0] != 'pod'))
                self.note('spawn-outside', '%s of the map stand outside the grid as the project sizes it, %s among them'
                          % (words, name(out[0])), actor=out[0].get('actor'), count=len(out), **where)

    def check_zones(self, zones, own=False):
        """Warnings for zones' places: outside the grid, over no floor, a piece of the project on a soldier point, and
        a grid too small for LWR's pods (stage-small, F-90)."""
        g = self.grid_box()
        if g is None:
            return
        grid = self.scene['tileGrid']
        # a soldier's spot's tile as the game counts it (tile_corner)
        corner, size = tile_corner(grid), grid.get('size') or [TILE, TILE, STOREY]
        label = (lambda k: "the map's landing %d" % (k + 1)) if own else (lambda k: 'landing zone %d' % (k + 1))
        floors = self.floor_now()
        added, _ = self.added_floors()
        scenery = self.scenery_floor()
        # each zone's own landing, where it is one (a landing with no frame keeps its own points until its zone moves)
        found = getattr(self, 'own_landings_found', None) or []
        mine = {k: found[k] for k in range(min(len(zones), len(found)))} if own else \
            {k: found[j] for j, k in enumerate(spawns.own_slots(zones, len(found)))}
        far = []
        for k, z in enumerate(zones):
            at = spawns.place(z)
            points = [p for p, _ in spawns.soldier_spots(z, mine.get(k))]
            ground = spawns.ground(z)
            if any(not (g[0] <= p[0] <= g[3] and g[1] <= p[1] <= g[4] and g[2] <= p[2] <= g[5]) for p in points + [at['frame'][0]]):
                self.warn('landing-outside', '%s is outside the tile grid: its soldiers would stand where there are no '
                          'tiles' % label(k), zone=z['id'])
                continue
            bare, blocked = [], []
            for n, p in enumerate(points):
                # (its ground's level: a ground up to a unit under a level's start is in it, as the maps' floors are
                # a unit over the game's corner; 2 over the level volume's, as before)
                tile = (int(math.floor((p[0] - corner[0]) / size[0])), int(math.floor((p[1] - corner[1]) / size[1])),
                        int(math.floor((ground + 1.0 - corner[2]) / size[2])))
                if (tile not in floors and tile not in added
                        and not any(b[0] <= p[0] <= b[1] and b[2] <= p[1] <= b[3] and abs(b[5] - ground) <= 20.0
                                    for b in scenery)):
                    bare.append(n + 1)
                for c in self.copies:
                    b = c['box']
                    if c.get('actorClass') == 'XComLadder' or b[5] - b[4] <= FLOOR_THICK:
                        continue
                    if b[0] <= p[0] <= b[1] and b[2] <= p[1] <= b[3] and b[4] < ground + HEADROOM and b[5] > ground + 8:
                        blocked.append((n + 1, c['label'].split(':', 1)[-1]))
                        break
            if bare:
                self.warn('landing-floor', '%s: soldier point%s %s %s over no floor of the map or the project: lay floor '
                          'there, or the squad lands on nothing (F-46)'
                          % (label(k), '' if len(bare) == 1 else 's', numbers(bare), 'is' if len(bare) == 1 else 'are'),
                          zone=z['id'], points=bare)
            if blocked:
                who = sorted({b for _, b in blocked})
                self.warn('landing-blocked', '%s: %s stand%s on soldier point%s %s, where a soldier lands (F-06)'
                          % (label(k), ', '.join(who), 's' if len(who) == 1 else '', '' if len(blocked) == 1 else 's',
                             numbers([n for n, _ in blocked])), zone=z['id'])
            # LWR's pod mutator keeps only map sections at least POD_DISTANCE tiles from the squad's middle (F-90)
            mx, my = sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)
            reach = max(math.hypot(x - mx, y - my) for x in (g[0], g[3]) for y in (g[1], g[4]))
            if reach < POD_DISTANCE * size[0]:
                far.append(k)
        if far and (self.cleared or self.stage_grid):
            self.warn('stage-small', 'no part of the grid is %d tiles from %s: LWR places no pods or Meld there for a '
                      'squad landing at %s (F-90)' % (POD_DISTANCE, ', '.join(label(k) for k in far),
                                                      'it' if len(far) == 1 else 'them'), zones=[zones[k]['id'] for k in far])

    def scenery_floor(self):
        """The boxes of the map's own low scenery the Build makes walkable on a grid the project grows (F-100;
        shell.py scenery_to_walk): its level actors no taller than SCENERY_LOW, within the grid's levels (from a
        quarter level under its bottom: not the sky's ground plane), reaching past the map's own far X or Y side, and
        not deleted or moved. A raised backdrop counts as the ground does (CsmallScout_Farm's plateau). The map's saved
        floor tiles stop at its own grid, so a soldier point over one of these counts as floor. The Build turns on the
        collision of those that have it off and puts their tiles in the rebuild's queue. (The export doesn't say which
        collide: a piece of debris that collides but is no floor counts here too.)"""
        if not getattr(self, 'stage_grid', None) or self.cleared:
            return []
        grid = self.scene.get('tileGrid') or {}
        origin, dims = grid.get('origin'), grid.get('dimensions')
        if not origin or not dims:
            return []
        x1, y1 = origin[0] + TILE * dims[0], origin[1] + TILE * dims[1]
        levels = self.stage_grid[2] if len(self.stage_grid) > 2 else dims[2]
        bottom, top = origin[2] - STOREY / 4, origin[2] + STOREY * levels
        gone = {e['target'] for e in self.entities if e['kind'] in ('delete', 'move')} | self.floor_kept_off()
        boxes = []
        for o in self.scene.get('objects') or []:
            if o.get('actorClass') != 'XComLevelActor' or o.get('actor') in gone or o.get('mesh') not in self.meshes:
                continue
            b = world_box(o, self.meshes, o['location'], o['rotation'])
            if b[5] - b[4] <= SCENERY_LOW and b[4] >= bottom and b[5] <= top and (b[1] > x1 or b[3] > y1):
                boxes.append(b)
        return boxes

    def floor_kept_off(self):
        """The map's own pieces whose Floor the project's flags turn off or keep off (explicit Floor off): the Build's
        floor for low scenery on a grown map leaves them as they are (F-100 gives way to the user's flags)."""
        return {e['target'] for e in self.flag_edits if e['flags'].get('floor') is False}

    def floor_now(self):
        """The map's saved floor tiles whose piece is still where it was: a deleted or moved piece takes its floor
        with it (a moved one's copy gives floor where it lands: added_floors)."""
        gone = {e['target'] for e in self.entities if e['kind'] in ('delete', 'move')} | getattr(self, 'floor_off', set())
        return {tuple(f['tile']) for f in ((self.scene.get('tactical') or {}).get('floorTiles') or [])
                if f.get('actor') not in gone}

    def run(self):
        spec = None
        if self.check_document():
            problem = light_metadata_problem(self.scene) if self.has_edits() else None
            if problem:
                self.error('export-version', problem, minimum=EXPORT_MINIMUM)
        if not self.errors and self.map is not None:
            self.index_export()
            self.cleared_mark()
            self.spawn_rules_mark()
            self.overrides()
            self.added()
            self.derive_area_lights()
            self.groups()
            self.stage()
            self.ladder_climbs()
            self.floor_headroom()
            self.buildings()
            self.landing_zones()
            self.missions_check()
            self.stage_outside()
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
                                  lights=dict(deleted=len(self.light_ops['deletes']), added=len(self.light_ops['adds']),
                                              changed=len(self.light_ops['changes']), area=len(self.light_ops['area'])),
                                  **{key: dict(moved=len(self.effect_ops[kind]['moves']),
                                               deleted=len(self.effect_ops[kind]['deletes']),
                                               added=len(self.effect_ops[kind]['copies']),
                                               valued=len(self.effect_ops[kind]['values'])
                                               + sum(1 for c in self.effect_ops[kind]['copies'] if c.get('values')))
                                     for kind, key in EFFECT_LANES},
                                  spawns=dict(moved=len(self.spawn_ops['moves']), valued=len(self.spawn_ops['values']),
                                              added=len(self.spawn_ops['copies']), deleted=len(self.spawn_ops['deletes'])),
                                  flags=dict(self.flag_counts, inPlace=len(self.flag_edits),
                                             onCopies=sum(1 for c in self.copies if c.get('flags')))),
                      errors=self.errors, warnings=self.warnings, notes=self.notes, stageGrid=getattr(self, 'stage_grid', None),
                      cleared=getattr(self, 'cleared', False), clearKeepsOutside=getattr(self, 'keep_outside', False),
                      landingZones=getattr(self, 'zones', None),
                      ownLandings=getattr(self, 'own_count', None),
                      spawnRules=getattr(self, 'spawn_rules', None),
                      buildings=[dict(id=b['id'], name=b['name'], kind=b['kind'], floors=len(b['floors']))
                                 for b in self.new_buildings],
                      mapBuildings=[dict(id=e['id'], actor=e['actor'], **({'deleted': True} if e['deleted'] else
                                                                           dict(floors=len(e['floors']), moved=e['moved'])))
                                    for e in self.building_edits],
                      entities=sorted(self.entities, key=lambda e: (e['kind'], e.get('op') or '', e.get('target') or e.get('entity'),
                                                                    e.get('ownerEntity') or '')),
                      groups=self.group_report, assemblies=sorted(self.moves, key=lambda m: m['id']),
                      families=sorted(f for f in FAMILIES if self.builds(f)),
                      donors=[dict(d, pieces=sorted(d['pieces'])) for _, d in sorted(self.donor_report.items())])
        return spec, report


class LibraryError(ValueError):
    """A piece of another map can't be had. `code`: no-library, donor-missing, donor-changed or not-placeable."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Library:
    """The library of other maps' pieces as the compiler asks it (tools/viewer/library.py): the scan's index in the
    cache, and a piece's record, exported from the install on first request."""

    def __init__(self, cache, game):
        self.cache, self.game = cache, game
        self.index = None
        self.shared = {}        # library.piece's: the install's maps listed once, each map opened once

    def record(self, target, sky=False):
        """(the piece record, its index entry) of a target {package, level, actor}; LibraryError otherwise. `sky`: a sky
        dome (every mesh a Skybox one), which the library leaves out, is taken too: a test stage's backdrop (prefab plan
        5.11)."""
        viewer = str(Path(__file__).resolve().parents[1] / 'viewer')
        if viewer not in sys.path:
            sys.path.append(viewer)
        import library
        from projects import ProjectError
        index, entries, donors = self.load()
        try:
            record = library.piece(self.cache, self.game, dict(package=target['package'], level=target['level'],
                                                               actor=short(target['actor'])), self.shared)
        except ProjectError as error:
            code = error.extra.get('code')
            if code == 'donor-missing':
                raise LibraryError('donor-missing', 'the game install has no map %s, which %s comes from'
                                   % (target['package'], short(target['actor'])))
            if code == 'piece-missing':
                raise LibraryError('donor-changed', 'the map %s has no piece %s any more'
                                   % (target['package'], short(target['actor'])))
            raise LibraryError('not-placeable', error.message)
        known = donors.get(record['source']['package'].casefold())
        if known is None or known['sha256'] != record['source']['sha256']:
            raise LibraryError('donor-changed', 'the map %s is not the file the library was scanned from: scan the '
                               'library again' % record['source']['package'])
        entry = entries.get(record.get('key'))
        if entry is None and sky and record['objects'] and all(
                (record['meshes'].get(o.get('mesh')) or {}).get('name', '').startswith('Skybox.') for o in record['objects']):
            entry = dict(placeable=True, actorClass=record['objects'][0]['actorClass'])
        if entry is None:
            raise LibraryError('not-placeable', '%s of %s is not a piece the library lists'
                               % (short(target['actor']), record['source']['package']))
        return record, entry

    def load(self):
        """(index, {key: entry}, {package folded: donor}), read once; LibraryError when it was never scanned."""
        viewer = str(Path(__file__).resolve().parents[1] / 'viewer')
        if viewer not in sys.path:
            sys.path.append(viewer)
        import library
        if self.index is None:
            index = library.load_index(self.cache)
            if index is None:
                raise LibraryError('no-library', 'the library of other maps\' pieces has not been scanned: open the '
                                   'Add panel\'s "All maps" and scan, then build again')
            self.index = (index, {e['key']: e for e in index['entries']},
                          {d['package'].casefold(): d for d in index['donors']})
        return self.index

    def effect(self, target):
        """(the template, its index entry) of an effect or ambient sound of another map, `target` {package, level,
        actor} (library.effect: its export 28 record, its system or waves); LibraryError otherwise. The donor must be
        the file the library was scanned from, and the effect one the library lists as it is now."""
        _, entries, donors = self.load()       # (the viewer's folder on the path first)
        import library
        from projects import ProjectError
        try:
            template = library.effect(self.cache, self.game, dict(package=target['package'], level=target['level'],
                                                                  actor=short(target['actor'])), self.shared)
        except ProjectError as error:
            code = error.extra.get('code')
            if code == 'donor-missing':
                raise LibraryError('donor-missing', 'the game install has no map %s, which %s comes from'
                                   % (target['package'], short(target['actor'])))
            if code == 'effect-missing':
                raise LibraryError('donor-changed', 'the map %s has no effect, ambient sound or lens flare %s any more'
                                   % (target['package'], short(target['actor'])))
            raise LibraryError('not-placeable', error.message)
        known = donors.get(template['source']['package'].casefold())
        if known is None or known['sha256'] != template['source']['sha256']:
            raise LibraryError('donor-changed', 'the map %s is not the file the library was scanned from: scan the '
                               'library again' % template['source']['package'])
        entry = entries.get(template['key'])
        if entry is None or entry.get('family') != template['kind']:
            raise LibraryError('not-placeable', '%s of %s is not an effect, sound or lens flare the library lists'
                               % (short(target['actor']), template['source']['package']))
        return template, entry


# a project's larger tile grid (Compiler.stage): most of the game's own maps are under 100 tiles a side, but not all
# (TempleShip is 45 by 203, AlienBase01 63 by 168); the editor makes up to 256 (the user, 16 November 2026; 128
# before), and a map past it keeps its own as its limit (stage_max)
STAGE_GRID_PLAYED, STAGE_GRID_MAX = 70, 256
# levels: the game's own maps go to 18 (1,152 units, the tallest of its 96: prefab plan 5.6b); the editor makes up to
# 30 (1,920 units; the user, 14 November 2026)
STAGE_LEVELS_PLAYED, STAGE_LEVELS_MAX = 18, 30


def stage_max(own):
    """The most a project's grid may be on each axis for a map whose own grid is `own` [nx, ny, nz]: STAGE_GRID_MAX
    tiles across and deep and STAGE_LEVELS_MAX levels, or the map's own where that is more, so a map is never past
    the limit at its own size and can still be made larger (project.js stageMax is the twin)."""
    return [max(limit, int(own[k]) if own and len(own) > k else 0)
            for k, limit in enumerate((STAGE_GRID_MAX, STAGE_GRID_MAX, STAGE_LEVELS_MAX))]
# the maps whose size a project may set: the bare maps that a new prefab or a new map starts from (tools/bake/shell.py)
STAGE_MAPS = ('CB2_MP_Blank',)
# a project's buildings made from nothing (Compiler.buildings): the kinds, the most floors (a CutdownFloor is a byte;
# the game's own buildings have at most 5), and how far two boxes may reach into each other before they overlap
BUILDING_KINDS = ('building', 'ufo')
BUILDING_FLOORS_MAX = 10    # (ten floors of three levels fill a 30-level grid)
BUILDING_OVERLAP = 0.5
# a map building's box is unchanged when every coordinate is within this of its volume's box in the export (the page
# rounds a box to three decimals; the export does not): web/project.js BUILDING_SAME and buildings.SAME are the twins
BUILDING_SAME = 0.01


# LWR's pod mutator keeps only map sections this many tiles from the squad's middle (F-90): stage-small
POD_DISTANCE = 29


def tidy_zone(z):
    """A landing zone as the spec carries it: the keys it has, the place to four decimals (web/project.js
    tidyLandingZone)."""
    out = dict(id=z['id'], location=[tidy(float(v)) for v in z['location']], direction=z['direction'],
               kind=z.get('kind') or 'normal')
    for k in ('missionType', 'councilType'):
        if z.get(k):
            out[k] = z[k]
    if z.get('alternate'):
        out['alternate'] = dict(location=[tidy(float(v)) for v in z['alternate']['location']],
                                direction=z['alternate']['direction'])
    if z.get('lwr') is False:
        out['lwr'] = False
    if z.get('ew') is True:
        out['ew'] = True
    if z.get('other'):
        out['other'] = z['other']
    return out


def numbers(ns):
    """1, 2 and 5 / 3 to 7: a list of numbers in words."""
    ns = sorted(ns)
    if len(ns) > 2 and ns == list(range(ns[0], ns[-1] + 1)):
        return '%d to %d' % (ns[0], ns[-1])
    return ', '.join(str(n) for n in ns[:-1]) + (' and ' if len(ns) > 1 else '') + str(ns[-1])


def zone_words(ns):
    return 'landing zone%s %s' % ('' if len(ns) == 1 else 's', numbers(ns))


def map_building_id(building):
    """A map building's id in a project: made from its actor, the same each time the map is opened (web/project.js
    mapBuildingId)."""
    return 'map:%s.%s' % (building.get('level') or 'PersistentLevel', short(building['actor']))


def moved_whole(old, floors):
    """Whether a map building's floors (dict(boxes, volumes)) are its old ones (dict(volume, box) each) moved
    together: every old volume kept on its floor, every box its old one carried by one move of whole quarter turns
    and a translation that is not nothing. A building moved whole leaves its visibility groups behind."""
    if len(old) != len(floors):
        return False
    pairs = []
    for f, o in zip(floors, old):
        boxes = {v['volume']: v['box'] for v in o}
        if len(f['volumes']) != len(o) or set(f['volumes']) != set(boxes):
            return False
        pairs += [(boxes[v], x) for v, x in zip(f['volumes'], f['boxes'])]
    for turns in range(4):
        def carried(box):
            corners = [turned((box[i], box[j]), turns) for i in (0, 3) for j in (1, 4)]
            return [min(c[0] for c in corners), min(c[1] for c in corners), box[2],
                    max(c[0] for c in corners), max(c[1] for c in corners), box[5]]
        first = carried(pairs[0][0])
        shift = [pairs[0][1][j] - first[j] for j in range(3)]
        if all(all(abs(x[j] - (carried(b)[j] + shift[j % 3])) <= BUILDING_SAME for j in range(6)) for b, x in pairs):
            return turns != 0 or any(abs(v) > BUILDING_SAME for v in shift)
    return False


def scripted_users(record):
    """The scripted actions that drop units at a spawn point (export 33's `uses`: a SeqAct_SpawnAlien naming it, or
    an object list holding it that feeds such actions), as web/spawn_rules.js scriptedUsers reads them."""
    out = []
    for u in record.get('uses') or []:
        if not isinstance(u, dict):
            continue
        if u.get('how') == 'direct' and u.get('byClass') == 'SeqAct_SpawnAlien':
            out.append(u.get('by'))
        elif u.get('how') == 'indirect':
            out += list(u.get('then') or [u.get('by')])
    return list(dict.fromkeys(a for a in out if a))


def compile_project(doc, scene, enable=(), library=None, foreign=()):
    """(spec or None, report) for a project document and the export of its source map. `enable`: families to build
    although FAMILIES doesn't yet (an experiment's build). `library` (a Library): where pieces of other maps come
    from; `foreign`: families whose pieces from other maps build although FOREIGN_FAMILIES doesn't list them."""
    return Compiler(doc, scene, enable, library, foreign).run()


def stream_only(spec):
    """The spec as a plain streamed patch: the base map is shipped by something else, a relit variant of it
    (tools/bake/relight.py, deployed by tools/bake/deploy_fixture.py --stream, EXP-17), so `map` keeps only the base
    map's name and origin, and patchtool ships no copy of its own. Its tile seeds go into that variant
    (`map.seedExternally`; deploy_fixture.py --seed-plan), not into the lab's base map."""
    out = dict(spec)
    out['map'] = dict(name=spec['map']['name'], origin=spec['map']['origin'], seedExternally=True)
    out['editor'] = dict(spec['editor'], streamOnly=True)
    return out


def native_split(spec):
    """(patch spec, native edit): the spec without what the Build does in the variant map itself, and that as
    tools/bake/native_copy.py takes it: `copies` (actor, location, rotation, label, box, and breakGroup when the copy
    breaks with a group) of NATIVE_CLASSES, `breakOriginals` (the base map's pieces left in place that break with
    those groups, {name, group}) and `hides` (the exact hider's targets, {name, label, box}). A copy of an assembly
    (a car, a door, a ladder: always made in the map) also carries its `family` and `assembly`, and `assemblies` lists
    each assembly's grid move ({id, family, members, turns, translation}), `covers` the cover blocks (the spec's
    `covers` blocks: name, kind, location, rotation, size, heights, box, and breakGroup for a block that breaks with
    a group; the spec's `breakOriginals` object carries such a group's map pieces when the project has no copy), `buildings` the buildings made from nothing
    (id, name, kind, floors of boxes), `buildingEdits` the map's own buildings changed or deleted (id, actor, name, kind,
    deleted, moved, floors of boxes and volumes, old: each floor's volumes and their boxes as exported); a ladder copy
    carries its `ladder` ends
    ({foot, top} tiles), and `streamHides` ({stream: [actor]}) the streamed patches' pieces to take out of the
    variant's copies of them (a moved or deleted ladder's helpers), `lights` the light edits (plan 9.5: deletes,
    changes, adds and the area lights the piece edits take along), and `effects`, `sounds` and `flares` the effects',
    sounds' and lens flares' lanes (each `moves`, `deletes`, `copies` and `values`; the effects and sounds plan, Part D). A group with a copy of another class stays
    the copier's whole, with its base-map pieces. What is left for the patch, if anything, is built by patchtool; with
    nothing left the Build makes no patch."""
    out, natives, originals, hides, moves = dict(spec, objects=[]), [], [], [], []
    lights, covers, buildings, edits, piece_flags_, flag_ladders = None, [], [], [], [], []
    effect_lanes = {}
    stream_hides = out.pop('streamHides', None)
    stream_moves = out.pop('streamMoves', None)
    cleared, zones = out.pop('cleared', None), out.pop('landingZones', None)
    spawn_rules = out.pop('spawnRules', None)
    carried = out.pop('carriedEffects', None)
    for obj in spec['objects']:
        if obj.get('type') == 'buildings':
            buildings += obj['buildings']
            continue
        if obj.get('type') == 'buildingEdits':
            edits += obj['edits']
            continue
        if obj.get('type') == 'covers':
            covers += obj['blocks']
            continue
        if obj.get('type') == 'pieceFlags':
            piece_flags_ += obj['pieces']
            flag_ladders += obj.get('ladders') or []
            continue
        if obj.get('type') == 'breakOriginals':
            originals += obj['originals']
            continue
        if obj.get('type') == 'lights':
            lights = {k: obj[k] for k in ('deletes', 'changes', 'adds', 'area')}
            continue
        if obj.get('type') in ('effects', 'sounds', 'flares', 'spawns'):
            effect_lanes[obj['type']] = {k: obj.get(k) or [] for k in ('moves', 'deletes', 'copies', 'values')}
            continue
        if obj.get('type') == 'hide' and obj.get('exact'):
            boxes = obj.get('boxes') or [None] * len(obj['alsoHide'])
            labels = obj.get('labels') or obj['alsoHide']
            hides += [dict(name=n, label=l, box=b) for n, l, b in zip(obj['alsoHide'], labels, boxes)]
            continue
        if obj.get('type') != 'copy':
            out['objects'].append(obj)
            continue
        n = len(obj['from'])
        classes = obj.get('classes') or [None] * n
        groups = obj.get('breakGroups') or [0] * n
        members = obj.get('assemblies') or [''] * n
        families = obj.get('families') or [''] * n
        donors = obj.get('donors') or [None] * n
        untried = obj.get('untried') or [False] * n
        flags = obj.get('flags') or [None] * n
        # a piece of another map is always made in the map: nothing else can bring what it needs; so is a copy of a
        # class the Build has not been tried on (the patch's copier has no recipe for it either)
        # (and a copy with flags: only the writer sets them)
        in_map = [classes[k] in NATIVE_CLASSES or bool(members[k]) or bool(donors[k]) or untried[k] or bool(flags[k])
                  for k in range(n)]
        copier_groups = {groups[k] for k in range(n) if groups[k] and not in_map[k]}
        native = [k for k in range(n) if in_map[k] and groups[k] not in copier_groups]
        for k in native:
            natives.append(dict(actor=obj['from'][k], location=obj['poses'][k]['location'],
                                rotation=obj['poses'][k]['rotation'], label=obj['labels'][k], box=obj['boxes'][k],
                                **({'breakGroup': groups[k]} if groups[k] else {}),
                                **({'donor': donors[k]} if donors[k] else {}),
                                **({'untried': True} if untried[k] else {}),
                                **({'flags': flags[k]} if flags[k] else {}),
                                **({'family': families[k], 'assembly': members[k]} if members[k] else {}),
                                **({'ladder': obj['ladders'][k]} if (obj.get('ladders') or [None] * n)[k] else {})))
        made = {members[k] for k in native if members[k]}
        moves += [m for m in obj.get('assemblyMoves') or [] if m['id'] in made]
        stay = [o for o in obj.get('breakOriginals') or [] if o['group'] in copier_groups]
        originals += [o for o in obj.get('breakOriginals') or [] if o['group'] not in copier_groups]
        keep = [k for k in range(n) if k not in native]
        if keep:
            rest = dict(obj)
            for f in ('from', 'poses', 'labels', 'boxes', 'classes', 'breakGroups', 'families', 'assemblies', 'ladders',
                      'donors', 'untried', 'flags'):
                if f in obj:
                    rest[f] = [obj[f][k] for k in keep]
            rest.pop('assemblyMoves', None)
            if 'breakOriginals' in obj:
                rest['breakOriginals'] = stay
                if not stay:
                    del rest['breakOriginals']
            rest['location'] = rest['poses'][0]['location']
            out['objects'].append(rest)
    native = dict(copies=natives, breakOriginals=originals, hides=hides)
    if lights:
        native['lights'] = lights
    if covers:
        native['covers'] = covers
    if piece_flags_:
        native['pieceFlags'] = piece_flags_
        if flag_ladders:
            native['pieceFlagLadders'] = flag_ladders
    if buildings:
        native['buildings'] = buildings
    if edits:
        native['buildingEdits'] = edits
    if moves:
        native['assemblies'] = moves
    if stream_hides:
        native['streamHides'] = stream_hides
    if stream_moves:
        native['streamMoves'] = stream_moves
    if cleared:
        native['cleared'] = cleared
    if zones is not None:
        native['landingZones'] = zones
    if spawn_rules:
        native['spawnRules'] = spawn_rules
    if carried:
        native['carriedEffects'] = carried
    native.update(effect_lanes)
    return out, native


def find_export(cache, doc, minimum=EXPORT_MINIMUM):
    """The export (scene.json) of the project's source map in a viewer cache and its data: one with the project's
    SHA-256 (the cache names folders <first 16 hex digits>-v<exporter version>-map, and a later export of the same
    version <...>-map-<suffix>: export.py publishes beside an existing one) and exporter version `minimum` or
    newer (export 18 has the light data every edit needs: plan 4.1), preferring the exporter version the project was
    edited on among those, then the newest. A project edited on an older export takes the newest that qualifies."""
    src = doc.get('source') or {}
    sha = str(src.get('sha256') or '')
    folder = Path(cache) / str(src.get('map'))
    found = []
    for scene in folder.glob('*-map*/scene.json'):
        m = re.match(r'^([0-9a-f]{16})-v(\d+)-map(?:-[A-Za-z0-9_]+)?$', scene.parent.name)
        if m and len(sha) == 64 and sha.startswith(m.group(1)) and int(m.group(2)) >= minimum:
            found.append((int(m.group(2)) == src.get('exporterVersion'), int(m.group(2)), scene.stat().st_mtime_ns, scene))
    for *_, scene in sorted(found, reverse=True):
        with open(scene, encoding='utf-8') as f:
            data = json.load(f)
        if (data.get('source') or {}).get('sha256') == sha:
            return scene, data
    raise SystemExit('no export of %s with SHA-256 %s at version %d or newer in %s: prepare the map (re-export it: the '
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
        export, scene = find_export(args.cache, doc)
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
