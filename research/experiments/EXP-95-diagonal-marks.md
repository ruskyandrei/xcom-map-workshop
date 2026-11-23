# EXP-95: diagonal cover marked by hand, in the game

Date: 23 November 2026. Status: **played: six checks of seven passed; one copied corner, (53, 40, 0), had no cover in the game, explained the same day: a meld container Long War placed at random beside it reworked its tile, not the Build** ([F-162](../findings-register.md)). Played unattended in the lab copy (the game-test skill), one pass of each check and a second take of the one that failed.

## The questions

The plan for diagonal cover placed by hand (private/plans/done/diagonal-cover-by-hand-and-views-plan.md, stage M4,
and M5's one case; KNOWN-BUGS.md KB-20):

1. Does a tile the project marks at a wall give the cover the Build wrote for it?
2. A tile with two corners, one with a wall and one with nothing there: what does the game give, and show, toward
   the empty corner (the plan's decision 3: written as marked, high cover against nothing)?
3. Does a map's mark the project takes away give no cover?
4. A map's mark given a second corner where nothing stands?
5. The marks a copy of the scout's hull chunk carries, written from the page's records (`pageCarries`: the Build
   carries none of its own)?
6. Can a unit walk from the two-corner tile toward its empty corner?
7. Do a quicksave and its load keep the tiles as written?

## The map

CsmallScout_Farm, built quick from [exp95_diagonal_project.py](../../tools/editor/examples/exp95_diagonal_project.py)
at export 40 (project schema 7) as CsmallScout_Farm_X95. What the Build wrote (its manifest's `diagonalCover`):

| Tile | Corners marked | Cover flags written | A corner with no wall |
| --- | --- | --- | --- |
| (45, 40, 0), at the turned cover block | (1, -1) | 0x12002 | none |
| (47, 40, 0), the block's other side | (-1, 1), (1, 1) | 0x10109 | (1, 1) |
| (41, 22, 0), a scout corner | its own (-1, 1), and (1, -1) | 0x10103 | (1, -1) |
| (51, 42, 0) and (53, 40, 0), the copied chunk's | (-1, -1) | 0x14404 each | none |
| (39, 20, 0), a scout corner taken away | none | (the straight rule's: no diagonal cover) | |

Staged in the LWR 2.x lab copy with `lab_install.install(..., game=<the lab copy>)`, started hidden with `--map`, the
test squad, `--no-aliens` and `--saving`.

## Runs

One hidden run, LWR 2.06 in the lab copy, `--map`, the test squad, `--no-aliens`, `--saving`. Each soldier was put on
his tile (TeleportToCursor) and read after a full round of the soldiers (`XGUnit m_bInCover`,
`CurrentCoverPointFlags`, `m_iCurrentCoverValue`). The user's own campaign copy's game was open while the run began,
and was not touched.

1. **(45, 40, 0), at the block's wall: passed.** In cover, flags 0x12002 as written, cover 50 (high).
2. **(47, 40, 0), one corner at the wall and one with nothing there: passed.** In cover, flags 0x10109 as written,
   cover 50: the game takes the written word as it is, and the soldier reads as in high cover. Which way the ground
   shields point could not be seen (on the hidden desktop the cursor's shields are drawn off the picture).
3. **(39, 20, 0), a scout corner taken away: passed.** Not in cover, flags 0.
4. **(41, 22, 0), a scout corner given a second corner with no wall: passed.** In cover, flags 0x10103 as written.
5. **The copied chunk's corners: (51, 42, 0) passed, (53, 40, 0) failed.** (51, 42): in cover, flags 0x14404 as
   written. (53, 40): not in cover, flags 0, also after the soldier walked off it and back (the game reading the
   tile afresh).
6. **A walk from the two-corner tile toward its empty corner and back: passed.** One tile each way, no wall.
7. **A quicksave and its load: passed.** Every soldier read the same after the load.

The quicksave read against the built package (a scratch reader over `world_links.parse_store`): (53, 40, 0) was built
with static 0x53a822, cover 0x14404 and its cover location, and the save holds static 0x53a820 (bit 0x2 gone) and no
cover word or cover location: the battle worked the tile out again, without its mark. (51, 42, 0) and the other
marked tiles are in the save as built. Tiles round (53, 40) changed too: (52, 39) and (53, 39) lost their low bit,
(53, 39) its cover, and (54, 39) went from 0x522820 to 0x422924 with straight cover 0x8808. By the Build's own reading
of the volumes (`native_copy.rebuild_order`) no rebuild volume reaches (53, 40, 0): the nearest, the copy's fitted
volume over x 53 to 54 and y 38 to 39, stops 0.08 of a tile short of y 40, and so does the one short of (51, 42),
which kept its mark. The levels over both marks are reached alike.

## What it shows

- A mark the project makes is written as marked and the game plays it: high cover from the written word, a corner
  with no wall included (it plays as high cover against nothing, as the plan's decision 3 chose), and a map's mark
  taken away gives none.
- A copy's carried marks are written as the page carried them, and both are in the game as written until the
  battle starts. The one lost was reworked by a meld container Long War put at tile (55, 39, 0), whose rebuild box
  (± 144 across, ± 64 up) takes it (F-162): under Long War, a random container beside any diagonal tile takes its
  cover for that mission. Read the same day from the save: the streamed patch levels' rebuild volumes, which the
  Build's reading leaves out, rework their tiles too (KNOWN-BUGS.md KB-22).

## Tools

- `lab_install.install` refused the build ("no record for CsmallScout_Farm"): the project named the map by its
  file's case. Fixed the same day (deploy_fixture matches whatever the case), and the experiment's script names the
  map as the install's records do.
- The cursor would not take the exact middles of (39, 20) and (41, 22) from `aim`; a point inside each, off its
  middle, did.
