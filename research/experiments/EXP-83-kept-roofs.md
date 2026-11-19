# EXP-83: broken roofs kept whole in battle, and one let break further (F-139)

Date: 19 November 2026. Status: **run A prepared**. A roof or floor the game keeps whole (its component's
`bPreventChunkRemoval`: the bar's roof, 61 of the 63 slab components of the slab audit) draws every fragment whatever
is painted out ([F-138](../findings-register.md)). Since EXP-82 such a piece built broken had the setting turned off,
which lets it break further in battle, as the game's own roofs and floors never do. Now it stays whole by default: the
Build keeps the setting and points its component at a copy of its mesh with the fragments out cut away
([F-139](../findings-register.md); tools/bake/made_blasts.py `cut`, frac_walls.py `cut_copy`); the editor's Breaks
further in battle asks for the setting off instead. Played unattended in the lab copy (the game-test skill): only
what is new.

## What is new

- A map piece drawing a mesh of our own forced-export package (`XComMapEdCut`): the bar's roof mesh with 7 fragments'
  triangles left out, its vertices, body setup and tagged properties the original's, with the setting on.
- The tiles over a hole that the mesh has, not the painted array (the rebuild volume over the roof works them out
  again from the game's collision).
- A grenade on a roof that keeps its fragments, and on one that was let go (not played before: F-138's note).
- Read on the side, not a check: what a soldier does when a map roof breaks under him. On a made floor it was seen in
  EXP-76 run E ([T-47](../findings-register.md)): the game put him on the ground below and he played on.

## The project

`EXP-83 kept roofs` ([exp83_project.py](../../tools/editor/examples/exp83_project.py)), in a test server's scratch
store; the map `EXP83KeptRoofs`, a quick build (no baked light). Game tiles count from the map's corner
(-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

| Piece | Where | What |
| --- | --- | --- |
| The bar's roof `XComFracLevelActor_3` | where the map has it, (-1056, 576, 400): x -1632 to -480, y 96 to 1248, its top at 402 | one blast of two tiles at the world's (-1344, 864): 7 of its 81 fragments, a hole from x -1536 to -1152, y 672 to 1056; kept whole, drawing `Roof_BarrierSmallFloor_FRACTURED_Cut_e262673416` |
| The roof's other piece `XComFracLevelActor_7` | (96, 672, 400), a quarter turn: x -480 to 768, y 0 to 1248 | one blast of one tile at its far corner, the world's (720, 1150): 2 of its 98 fragments; Breaks further in battle, the setting turned off. It holds the roof's air-conditioning units at x -48 and 42, y 432 and 912 |

The quick build's log: `broken (in place) XComFracLevelActor_3: 7 of its 81 fragments knocked out by its blasts, 7
painted out in all; kept whole in battle, drawing Roof_BarrierSmallFloor_FRACTURED_Cut_e262673416 (the hole cut into a
copy of its mesh)`, and `broken (in place) XComFracLevelActor_7: 2 of its 98 fragments knocked out by its blasts, 2
painted out in all; bPreventChunkRemoval turned off`.

## Run A (hidden game)

The cutaway shows a building's roof only while the cursor's floor is raised (`aim ... --floor 3`, EXP-82).

1. **Load**: the battle starts on `EXP83KeptRoofs`; no crash, no error naming the roof or the cut mesh.
2. **The bar's roof's hole** (the cut mesh): seen from above with the cursor's floor raised, a jagged hole round
   (-1344, 864), the bar's inside seen through it, as in EXP-82.
3. **The hole's tiles are open**: the cursor on the hole's tile (-1297, 815) on a raised floor reads the bar's floor
   below, not the roof's 402; on the roof's tile (-1297, 431) beside it, the roof's height. A soldier put on the roof
   tile stands there.
4. **The bar's roof stays whole**: a soldier on the roof at (-1009, 431) throws a grenade at (-1201, 335) on the roof;
   shots from above before and after: no new hole where it burst (the hole of check 2 as it was).
5. **The other piece breaks further, and a soldier on it**: a soldier on (239, 623) on `XComFracLevelActor_7` throws a
   grenade at (239, 719) beside him. Passed if the roof is holed where it burst. Read on the side: where the soldier
   stands after (`getall XGUnit Location`: about 402 up, or on the bar's floor below, as in EXP-76 run E), and what the
   air-conditioning units at (47, 431) and (-49, 431) look like.

## Result

Not yet played.
