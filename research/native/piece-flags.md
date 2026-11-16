# Piece flags: the settings that decide how the game's tiles and mouse use a placed piece

16 November 2026. The piece flags plan's stage P0 (the plan is private). Read-only: the decompiled XComGame scripts
(`<lab>\reference\XComGame-decompiled`, LWR's; the declarations used here are plain EW's too), the game's own script
packages (`XComGame.upk`, `Engine.upk`, `Core.upk` of the install: their `Default__` objects read with
`tools/viewer/package.py`), the native reading in [cover-build.md](cover-build.md), and a survey of every listed map
([audit_piece_flags.py](../../tools/upk/audit_piece_flags.py), output
[piece-flags-audit-2026-11-16.json](../evidence/piece-flags-audit-2026-11-16.json)). Nothing was run in the game.
The policy the editor uses is [piece_flags.py](../../tools/viewer/piece_flags.py); findings register F-114.

## 1. The five settings

| Setting (editor) | Property | What reads it | Confidence |
| --- | --- | --- | --- |
| Blocks walking | `bAlwaysConsiderForCover` (the cover interface's `ConsiderForOccupancy`) | the occupancy step (`0xA58810`) and the pathing sweep (world trace type 3) | high (code) |
| Gives cover | `bIgnoreForCover`, the other way round (`ShouldIgnoreForCover`) | the cover sweep (world trace types 1 and 2) | high (code) |
| Blocks sight | `VisibilityBlockingData.bBlockUnitVisibility` | the sight sweep (world trace type 4), beyond sight radius the line checks, and a floor tile's upward bit | high (code) |
| Floor | `bPathColliding`, with `bCanStepUpOn` | the floor line (`0xCF2470` step 6) | high (code) |
| Mouse picks it | `bIgnoreFor3DCursorCollision`, the other way round | `XComTacticalHUD.GetMousePickActor` (script) | high (script) |

These are the inputs the filters read. Geometry, collision, other pieces and the special traces below decide the
finished tiles; a setting is not a prediction of them.

## 2. Classes

From the decompiled scripts:

- `XComLevelActor extends StaticMeshActor`, implements `XComCoverInterface` and `IMouseInteractionInterface`.
  Children: `XComOpacityFadeLevelActor`, `XComLadder`, `XComDestructibleActor` (implements `Destructible`).
  `XComDestructibleActor`'s children: `XComCollectible`, and `XComDestructibleSkeletalMeshActor` (abstract), whose
  child is **`XComInteractiveLevelActor`, the doors**. So a door is an `XComLevelActor` too.
- `XComFracLevelActor extends FracturedStaticMeshActor`, implements `XComCoverInterface`, `Destructible` and
  `IMouseInteractionInterface`. Child: `XComDecoFracLevelActor`. It declares its own copies of the cover flags,
  `bIgnoreFor3DCursorCollision` and `VisibilityBlockingData`.
- `StaticMeshActor` and `KAsset` implement neither interface.

The class defaults, as the game's script packages save them (each class with what it takes from its parents; a bool
no default saves is false):

| Class | walking flag | ignore cover | block sight | `bPathColliding` | `bCanStepUpOn` | ignore mouse | other |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `XComLevelActor`, `XComOpacityFadeLevelActor` | true | false | true | true | true (Actor) | false | `bIsValidDestination` true |
| `XComDestructibleActor`, `XComCollectible` | true | false | true | **false** | true | false | `bIgnoreForPathing` false, `bInteractive` false |
| `XComInteractiveLevelActor` | true | false | true | false | true | false | **`bInteractive` true** |
| `XComLadder` | true | false | true | **false** | true | false | |
| `XComFracLevelActor`, `XComDecoFracLevelActor` | true | false | true | **false** | **false** | false | `bIsValidDestination` true |
| `StaticMeshActor`, `KAsset` | (none) | (none) | (none) | **false** (Actor) | true (Actor) | (none) | |

So a prop, a ladder, a door and a fracturing piece are no floor unless the map saves `bPathColliding` (and for a
fracturing piece `bCanStepUpOn`) on it or its archetype; a static mesh actor neither.

### What each class's settings decide

From [cover-build.md](cover-build.md), sections 2, 4 and 5:

| Class | Walking | Cover | Sight | Floor | Mouse |
| --- | --- | --- | --- | --- | --- |
| level piece | occupancy and pathing sweep | the cover sweep | the sight sweep; a floor tile's upward bit | yes | yes |
| prop, collectible | occupancy; the pathing sweep only with the gate open | the cover sweep, gate open; never when `bInteractive` (the variant taken to be the props', by field order) | the sight sweep, gate open; a floor tile's upward bit, gate or not | yes | yes (the cast holds for children) |
| door | as a prop, and its open or shut state | as a prop; its own test also asks a virtual not yet named | as a prop, and its state | yes | **never read** |
| fracturing piece | yes (its own field) | yes | yes | yes | yes |
| ladder | the pathing sweep only: occupancy leaves ladders out by class | **no**: the normal cover sweep leaves ladders out | yes | yes | yes |
| static mesh actor, KAsset | never | never | never | yes | never picked (no interface) |

**The prop's gate.** An `XComDestructibleActor` (doors included) with `bIgnoreForPathing` is skipped by every world
trace: the pathing, cover and sight sweeps at once. The occupancy step does not read it. So such a prop with its
walking flag on still occupies tiles but is passed by the pathing sweep: half on. Turning walking, cover or sight on
needs the gate open (`bIgnoreForPathing` written false, also where it is inherited), which turns the other two on
as well unless they are written off. The editor's planner (`piece_flags.plan`) writes those companions; where a
role is half on and opening the gate would change it, it asks for an explicit value instead.

**Exceptions** the settings don't control:
- the height test of the cover step (trace type 2) admits a ladder, every door and a prop with a `Toughness` that
  is not `bFragile`, whatever their cover flag says; so does the climb test;
- the cover step adds a lateral pathing bit toward each cover direction, so a piece with walking off and cover on
  can still block an edge;
- a floor hit on an actor with `bPathColliding` but without `bCanStepUpOn` ends the floor search with no floor;
- `bIsValidDestination` decides whether a unit may end its move on the floor;
- the filtered traces need the mesh's BodySetup (simple collision); the floor line and the mouse use other traces.

## 3. The mouse

`XComTacticalHUD.GetMousePickActor` walks the mouse ray's hits (`TraceActors`, every class) and:
1. skips a hit without `IMouseInteractionInterface`: a static mesh actor, a KAsset;
2. for any hit that is not an `XComInteractiveLevelActor`: skips it when `XComLevelActor(hit)` or
   `XComFracLevelActor(hit)` has `bIgnoreFor3DCursorCollision`. Those are casts, so they hold for every child
   class: **props, collectibles and ladders too**;
3. a door is tested apart and its flag is never read.

**Correction.** [mouse-cursor.md](mouse-cursor.md) said `XComDestructibleActor` lacks the interface, and
`cursor_pick.py` took only `XComLevelActor` and `XComFracLevelActor`. A prop inherits the interface and the flag from
`XComLevelActor`; the cast in step 2 reads it. Both are corrected (F-102).

## 4. Where the settings come from

A placed actor saves only what differs from its archetype. The editor resolves each setting up the chain: the actor,
its archetypes in the map (a prefab's or a shared asset's, cooked into the map as exports), then the class default
from the script packages (`XComGame.Default__XComLevelActor` and up through `Engine.Default__StaticMeshActor`,
`Default__Actor`). A struct (`VisibilityBlockingData`) is resolved field by field: one saved without
`bBlockUnitVisibility` takes the field from further up. An archetype in another package that the map doesn't carry
can't be read: the class default is then assumed, and the editor says so.

Over the 153 listed maps (audit below): 95,874 settings saved by the actors, 133,199 by archetypes in the map,
564,653 from the class defaults, 455 assumed (65 actors, one or so per map, most of them `XComLevelActor_1` or
`_5`), none unreadable.

## 5. The survey

[audit_piece_flags.py](../../tools/upk/audit_piece_flags.py) over the install's listed maps (`library.donors`: one
base map package per map the editor lists, its persistent level, each actor once; streamed patches not read). Every
file's name, size and SHA-256 are in the output.

- 153 maps, 110,523 actors of the flag classes: level pieces 50,972, props and collectibles 42,070, static mesh
  actors and KAssets 12,633, fracturing pieces 3,660, doors 733, ladders 455.
- Drawn, colliding pieces (a mesh, not hidden, colliding): 88,614. Walking off 33,537; cover off 37,387; **walking,
  cover and sight all off 29,523 (925 meshes)**, of which the mouse skips 3,706.
- Props with the gate (`bIgnoreForPathing`, saved or inherited): 9,338, of which 8,823 have walking and cover off
  too.
- TVs (a mesh name holding "TV"): 156 pieces of 6 meshes in 13 maps; in 10 maps the TVs are set more than one way,
  in 6 one TV mesh is. URB_Bar: `TV_BarRow` x5 with walking, cover, sight and mouse off; `StoreTV_B_Off` x4 with
  walking and cover off and sight on; `StoreTV_B` x2 with walking on, cover off, sight on.
- Ladders: 455; sight off 301; walking, cover and sight off 15. Every ladder has cover n/a (section 2) and Floor off.

Against the earlier survey (the plan's section 1.3, 16 November, not kept as a tool): its 153 maps, its TVs (156 of
6 meshes in 13 maps), its ladders (455, 301, 15) and its 65 actors with an external archetype are the same. Its
counts of walking off (38,580) and cover off (43,396) were over every piece; these are over drawn, colliding
pieces only. Its 29,312 pieces with three off (937 meshes) and 3,568 with the mouse off differ from 29,523 (925) and
3,706 by the drawn test (here: a mesh component not `HiddenGame`, the actor not `bHidden`) and by ladders, whose
cover is never a setting. The game-grid survey's 143 maps (T-36) are the listed maps that have a tile grid of their
own (`test_game_grid.py` keeps those).

## 6. Not known

1. Only `bIgnoreForCover` on a colliding piece (invisible floors, F-82) and `bBlockUnitVisibility` off (blockers,
   EXP-58) have been played. Walking off on a visible, colliding piece rests on the reading and on the maps' own.
2. Two steps of the cover build are plain engine traces (the floor under the cover location, the step-out's floor),
   not the filtered trace: a low piece with its flags off can still change cover where it lies.
3. How the game's damage finds pieces was not read; the flags writer leaves collision alone.
4. The seven classes sharing `0xBCCFA0` (the variant with `bInteractive`) were not named one by one, nor the door's
   virtual at +0x434.
5. A prop made solid that the map saved with `bIgnoreForPathing`: by the reading it needs that cleared too (the
   planner does); not played.
