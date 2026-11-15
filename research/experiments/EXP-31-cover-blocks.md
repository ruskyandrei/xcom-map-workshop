# EXP-31: cover blocks (invisible pieces that give cover)

Date: 10 November 2026. The user asked for a new kind of piece in the Add panel: invisible, giving cover, as some of
LWR's patches add it (URB_PoliceStation's), in sizes 1 × 1, 1 × 2 and 4 × 4 or of any size. The first version copied
LWR's own helper out of `patch_policestation.upk`; the user asked why it should need LWR's patch at all, so plain
Enemy Within can have them too, and the Build now makes the blocks from a recipe of its own.

## What LWR's patches do

URB_PoliceStation's `patch_policestation` places six hidden `XComLevelActor`s on plain box meshes of a `CoverPatch`
package (`highcover`, `Cover2x4`, `CoverSmallCar`, `floor2`). Each is hidden (`bHidden`), not a destination and not
climbable onto, its cover forced (`CoverForceFlag` `CoverForce_High` on `highcover`, `CoverForce_Low` on the others),
and the low ones carry a `VisibilityBlockingData` with `bBlockUnitVisibility` off. Collision is the class default's.
Cover in the game comes only through `XComCoverInterface`, which level actors implement and volumes don't: a cover
block has to be such an actor.

## What changed (offline)

- The editor: Add, Kind **Cover**, one entry, **Cover block** (a 1 × 1 block of high cover: at first six ready-made
  sizes, but the user found them needless with the size and cover set in the piece panel); the piece panel's **Cover
  block** section sets width and length (1 to 16 tiles) and the cover. A project saves a block as an added piece with `template`
  {kind: cover, version: 1} and `cover` {width, length, height}, its location the block's corner on the floor.
- The compiler (`COVER_RECIPES`): a block is whole tiles from its corner, from 12 units below the floor to 96 above
  it (high) or 84 (low), as LWR's `highcover` and `Cover2x4` stand; the spec's `covers` object goes to the Build's
  writer.
- The Build (`tools/bake/cover_blocks.py`): per block an `XComLevelActor` with its `StaticMeshComponent` and
  `XComFloorComponent`, built from a versioned recipe with LWR's helpers' properties, on a box `StaticMesh` of the
  block's size written by the Build under a package of its own (`XComMapEdCover`); seeds and a rebuild volume over
  its tiles, as a copy gets. The box has an `RB_BodySetup` of its own with its convex hull, as LWR's boxes do (since
  F-80: the first version had none, and the game's tile rebuild skipped the blocks). A project with cover blocks alone keeps the map's lighting (a
  hidden actor casts no baked shadow).
- Checked against LWR's helpers (`tests/test_cover_blocks.py`): a box of a helper's size has the helper's mesh layout,
  faces and windings, normals and fields after LOD 0; the built actors save the helpers' properties in their order,
  with their classes, archetypes, export flags and state frames (but the cooker's noise word). The project
  `Cover test` (URB_Bar, a 3 × 4 low block on the sidewalk, then also a car deleted) built quick and full.

## The first play crashed as the map loaded (F-79)

The user added a cover block to a project on CSmallScout_Farm (`farm+`: a copy of a destructible, and a 1 × 2 high
block, which the turn handles had tipped onto its side: roll -16384) and pressed Play in game: the game stopped before
the map finished loading. `Launch.log`: `Critical: appError called: Bad import index 65535/334` during the map's load.
The build before (the copy alone) had played.

- Every object reference in the new exports' properties and in the export and import tables was in range, so the
  bad index came from native data read past an export's end.
- The mesh component's native data was LWR's helper's: an empty LODData, 4 bytes. LWR's patch is cooked by the UDK
  (licensee 0); the game's own maps (licensee 64) save two mesh-swap LOD records and their two meshes after the
  LODData (`audit_lighting.component_record`): every StaticMeshComponent of CSmallScout_Farm, URB_Bar and
  URB_PoliceStation with no LOD saves 46 bytes there. In a licensee-64 map the game read 42 bytes past our component,
  into the floor component after it.
- The rest matches the map's own: the StaticMesh export saves the same fields in both (88 bytes after LOD 0 in every
  one-LOD mesh of the three maps and the patch), and the maps' XComLevelActors and XComFloorComponents save no native
  data, nor do ours.
- Fix: the recipe's component saves the 46 bytes (recipe version 1 changed in place: it had never been released).
  The tests now check the component's native data against the map's own components, and the actor and floor
  component against the map's. `farm+` rebuilt (quick): every new export reads whole with the native readers.

## Run 1 (10 November 2026): the map loads, but the blocks gave no cover (F-80)

The user played the F-79 rebuild of `farm+` (CSmallScout_Farm, quick build), with three high blocks by then
(`CoverBlock_copy2` to `_copy4`, each still tipped onto its side, roll -16384: a pillar a tile across and two tall):
- the map loaded and the battle started: F-79 verified;
- a block over a small rock that gives half cover, and one over a rock on a ramp (where the game's own cover is
  poor), changed nothing: the soldier's cover shields there were as without them;
- a block in the open: the soldier's move cursor went onto its tile, with no cover shields beside it, so it neither
  blocked movement nor gave cover.

Cause and fix: [F-80](../findings-register.md). The box mesh had no `BodySetup` and the default simple-collision
flags, so the game's line and box checks found nothing; it now saves `UseSimpleBoxCollision` and
`UseSimpleLineCollision` off, as the map's hay bales do, and those checks use its triangles. `farm+` rebuilt
(quick, 3 blocks).

## Run 2 (10 November 2026): still no cover with the simple-collision flags off

The user played the `farm+` rebuild with the first F-80 fix (the box meshes' `UseSimpleBoxCollision` and
`UseSimpleLineCollision` off; the install held that build, checked by its hash and the flags in the installed map):
the block in the open still let the move cursor onto its tile, with no cover shields beside it. The user also said
the blocks' roll is on purpose: tipped onto its side, a 1 × 2 block is the only way to make one two tiles tall.

The native code ([F-80](../findings-register.md), [native code notes](../native-code-notes.md)): the tile rebuild's
occupancy test skips a level actor whose mesh has no BodySetup, whatever its flags. The box meshes now get an
`RB_BodySetup` with the box's convex hull, laid out as the game's `FX_Utilities.Box_96x96x96`; the flags are back at
their defaults. `farm+` rebuilt (quick, 3 blocks).

A block's height in storeys, so a tall block needn't be tipped over, is for later (the user's run 2 remark).

## Run 3 (10 November 2026): blocks work on level ground; not on the ramp (F-81)

The user played the `farm+` rebuilds with the box meshes' BodySetup (F-80's second fix): "works now. at least for the
level ones". The block over the small rock (`CoverBlock_copy3`, a 1 × 2 high block stood on end) gives full cover
shields on its sides, and the move cursor no longer goes onto its tile. F-80 verified on level ground; hidden blocks
count (nothing in the code tests `bHidden`).

The block on the ramp by the UFO (`CoverBlock_copy4`, first at z 88.9, then sunk to z -3.2 into the slope) gave no
cover either way. No save was made, so read offline:
- the ramp's floor tiles there (level 3, row y 4) carry the sloped bit `0x4000`; the game's floor-detail step skips
  sloped tiles, and across the farm no sloped tile where units walk has any cover bits (F-81): the game's own rule,
  as the user suspected;
- first guess, wrong: that the tile rebuild finds the actors near a tile by their location (a block's pivot is its
  corner, a storey below the ramp's floor when sunk). The code keeps them by their bounding box; a split of each
  block into one actor per tile cell, written for that guess, was taken out again.

## Run 4 (to do): bigger blocks, low cover, and a reload

On URB_Bar or the farm's level ground, a quick build is enough (cover, pathing and line of sight are as a full build's):
- a 1 × 2 low block on open ground, a 4 × 4 high block (its far tiles too), and a low block turned a quarter;
- in the game: a soldier moved beside each block gets the shield of its cover (full for high, half for low), cannot
  walk through it, and nothing is drawn there; units see over the low one, not through the high one;
- a save loaded after (the rebuild runs again on load).

Marked editor shots for the run (mark_shots.py) and the user drives, as usual. Not yet played.
