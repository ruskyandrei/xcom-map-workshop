# EXP-88: the review fixes in the game

Date: 20 November 2026. Status: **played; one failure** ([F-143](../findings-register.md): a cover block grouped
with a made wall keeps its cover when the wall goes). The whole-editor review's fixes on branch `editor-review-fixes`
that change what reaches the game, played unattended in the lab copy (LWR) with the game-test skill: one pass of each
check, one second take for the one that stayed unclear.

## What was checked

1. **A made wall's break group reaches the Build** (review finding 36,
   [the ledger](../../changelog/entries/2026-11-20-made-wall-break-group-reaches-the-build.md)): before, the Build
   left out the made wall's break group, so a group of a made wall and one prop, or a made wall and a cover block,
   stopped the Build, and with two props none was tied to the wall's columns.
2. **A copy with "Mouse picks it" off builds and loads** (finding 37, first case,
   [the ledger](../../changelog/entries/2026-11-20-walker-reads-the-growers-names.md)): before, the Build stopped in
   `link_children` on URB_HighwayFallen.
3. **Changed lights build and show** (finding 37, second case): before, the Build stopped in `native_lights.apply` on
   CsmallScout_Farm for a point light's falloff exponent.
4. **A moved piece's shadow after a baked Build** (finding 44, the relight's part,
   [the ledger](../../changelog/entries/2026-11-20-relight-workers-cache-key-and-zero-sizes.md)): the dominant
   light's shadow-map test now reads a source angle of 0 as 0.
5. **A prefab with a made wall and a broken copy through Test in game** (finding 6,
   [the ledger](../../changelog/entries/2026-11-20-made-pieces-kept-in-prefabs.md)): before, a prefab saved from a
   selection lost the made wall's numbers and the copy's blasts.

## The projects

Made by [exp88_projects.py](../../tools/editor/examples/exp88_projects.py) in a test server's scratch store (scratch
settings: the game install read, the lab copy as the install Play in game writes into; scratch cache, projects and
builds), each compiled with no error and nothing left out, built on the test server (its Build) and staged with Play in
game on that server started with `--dry-play`; each game started with the play file it wrote.

| Project | Map | What | Build |
| --- | --- | --- | --- |
| `EXP-88 wall groups` | URB_Bar | the car park (its cars and vans deleted, as in EXP-84); three one-storey made walls along x at y -1152, each in a group with Break together: A (x -2016 to -1632) and a copy of the ATM `XComDestructibleActor_4` against its north face; B (x -1344 to -864) and two copies of the trash can `XComDestructibleActor_0`, at its west and east tiles; C (x -672 to -288) and a high cover block over the tile north of its third tile | quick |
| `EXP-88 mouse off copy` | URB_HighwayFallen | a copy of the sedan wreck `XComDestructibleActor_80` with its glass (one assembly), 480 south of the original, "Mouse picks it" off on both | quick |
| `EXP-88 farm lights and shadow` | CsmallScout_Farm | `PointLight_5` (a burning crate's glow in the crash trench) falloff exponent 2 to 12; `PointLight_6` (the next crate's) switched off; the tractor `XComDestructibleActor_153` moved five tiles east, (-1, -1) to (479, -1) | baked |

The farm project holds checks 3 and 4 in one baked build. Check 3 was asked as a quick build, but a quick build leaves a
changed light's pool baked as it was and changes only what the game lights live (`build.QUICK_LIGHTS`), so it could
not show the check's criterion; the baked build runs `native_lights.apply` too.

Check 5 was made in the page: a made wall and a broken copy (one blast through its middle) of URB_Bar's inside wall
`XComDecoFracLevelActor_17`, pasted side by side, saved as a prefab from the selection (schema 4, both kept), opened
in the prefab builder, and its Test in game run (Bake off) on the `--dry-play` server.

The Builds: walls 4 s, mouse 5 s, farm 30 s (`baked: true`, 55 lightmaps written, 18 shadow maps, 2 lights changed),
prefab test 6 s. The walls build's manifest lists the ATM's copy in six of wall A's columns, the west can in two of
wall B's, the east can in four of wall B's (its other end), and the cover block in six of wall C's.

## Results

1. **A made wall's break group: A passed, B passed, C failed.** The battle loaded on the walls build with no error
   naming a made piece. Each wall was blasted by an HE grenade at its south face, behind the piece on its north side.
   - A: the wall went whole, and the ATM with it (its health 0, not drawn after, fires where both stood); the log shows
     three of the wall's column clears (`XComDamageType_DestructibleActorClear`) reaching the ATM's actor.
   - B: the grenade at the west end broke the wall's west part; a column clear reached the west can, and both cans
     went (health 0): the east one through the group's own link between props, while its wall part, the east end,
     still stands. No prop was left standing in the air.
   - C: the wall went whole, and the log has six column clears of 500 reaching the block's actor; the block stayed. Its
     health read 3 before and after, and three units on the tiles round its tile, one put there after the wall had
     gone, each read high cover (50) toward it alone. The block is built invincible (it is meant to go only through
     its group's props), so the columns' damage does nothing to it ([F-143](../findings-register.md)).
2. **A copy with "Mouse picks it" off: build and load passed; the cursor unclear.** The Build wrote the flag on both
   copies ("mouse off: bIgnoreFor3DCursorCollision=true (added)") and the battle loaded; the copy stands whole on the
   road at its place, 480 south of the original. The hidden run's cursor follows the stand-in mouse but snaps to a
   tile's floor, and a car's tiles are refused: aimed at each car, the cursor went to a tile by its end, the same way
   for both; aimed at those tiles (the second take) it read the floor's height by each (512 and 518), neither car
   lifting it. Settling it needs a real mouse over a piece whose top the cursor can rise onto.
3. **Changed lights: passed.** Against the map as it is (a bare run, the same cameras): the switched-off crate's
   orange glow is gone from the trench wall and the ground round it, and the crate with falloff 12 lights a smaller,
   dimmer pool. Measured on top views, the red in rings round each crate fell by 3 to 9 levels (of about 50), green
   and blue within 2, a patch away from both the same.
4. **A moved piece's shadow: passed.** In the map as it is the tractor's moon shadow runs from it toward the lower
   left of a top view, as the other tractor's does. In the build the difference between the two top views shows two
   shadow-shaped patches, one from the old place and one from the new, the same way as the others: at the old place
   the bluish moonlight is back (blue up by 8.5 levels), at the new place there is a shadow (blue down by 4.4), the
   other tractor's shadow and a control patch the same. No shadow is left at the old place.
5. **A prefab with a made wall and a broken copy: passed.** Test in game built the made wall from its numbers (20
   fragments, its own 12 columns) and the broken copy with 5 of its 30 fragments knocked out by its blast, on the
   blank stage. In the game, from both sides: the long wall with a ragged hole through its middle, from the foot to
   two thirds up, and beside it the made wall whole, four tiles long and two storeys high, as in the builder.

## Pictures (in `<lab>\hidden-runs\exp88-*`, not committed)

- Check 1: the three walls from the north before (the ATM against A, a can at each end of B, C bare); after A's
  grenade, A and the ATM gone, fires on the lot; after B's, B's west part broken with fires at its foot, its east part
  standing, no can; after C's, no wall between B and the end of the lot, units round an empty tile, each with a high
  cover shield.
- Check 2: the copy whole on the open road beside the railing; the original among the other cars with the road's blood
  decals round it.
- Check 3: top views of the two crates in the map as it is and in the build, brightened side by side: the orange on the
  upper trench wall gone, the lower crate's pool smaller.
- Check 4: top views of the tractors' ground in both runs, brightened, and their difference: two shadow-shaped patches
  from the old and the new place, the same way as the other tractor's shadow.
- Check 5: the builder with the two walls; in the game, the two walls on the sky stage from both sides.

## Side notes

- A prefab test's stage has no landing intro: a hidden run started on one waits for "Mission Started", not
  `m_bTacticalIntroDone` (the first start waited 240 s for it and ended).
- Test in game left every piece out with `no-library` until the scratch cache's library was scanned for the stage's
  maps; the test says so in its window, as it should.
