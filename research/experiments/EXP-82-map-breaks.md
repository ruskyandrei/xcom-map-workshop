# EXP-82: the map's own fracturing pieces built broken (custom geometry editing plan, E6)

Date: 19 November 2026. Status: **run A prepared**. The custom geometry editing plan's stage E6 (decision D-5): the
blasts of E5 on the map's own fracturing pieces, the Build writing the fragments they reach as
EditorPaintedVisibleFragments and DestroyedChunks on the piece's component, with those the map already paints out
(tools/bake/made_blasts.py, native_copy.py `blasts_in_place`, `break_component`). Played unattended in the lab copy
(the game-test skill): only what is new.

## What is new

EXP-81 run A showed the game draws a made wall's painted-out fragments gone and its tiles treat the hole as open
(walk, cover, line of sight). New here:
- the arrays written on a component of the map's own, where it stands, its tiles worked out again by a rebuild volume
  over them (as a flag change's are: EXP-60..62);
- the arrays on a moved piece's copy and an added copy of a map piece that already paints a fragment out.

## The project

`EXP-82 map breaks` ([exp82_project.py](../../tools/editor/examples/exp82_project.py)), in a test server's scratch
store; the map `EXP82MapBreaks`, a quick build (no baked light). Game tiles count from the map's corner
(-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

| Piece | Where | What |
| --- | --- | --- |
| The bar's inside wall `XComDecoFracLevelActor_17` | where the map has it: along y from 680 to 1240 on the tile line x -1057, two storeys | one blast of one tile at its foot (the world's (-1056, 1007, 76)): 2 of its 30 fragments saved painted out, a hole from y about 930 to 1062, from the floor to about 170 up |
| The corner column `XComFracLevelActor_5` | moved a tile, to (816, 48, 16) | one blast of two tiles at its foot: 17 of its 29 fragments knocked out, 18 out with the one the map paints out |
| An added copy of that column | (720, 432, 16) | the same blast |

The quick build's log: `broken (in place) XComDecoFracLevelActor_17: 2 of its 30 fragments knocked out by its blasts`,
and 17 of 29 on each column copy.

## Run A (hidden game)

1. **Load**: the battle starts on `EXP82MapBreaks`; no crash, no error naming the pieces.
2. **The wall's hole**: drawn from both sides of the wall (x -1105 and x -1009 side, at y 1007, low), the floor
   seen through it.
3. **Walk and cover**: a soldier put on (-1105, 1007) walks to (-1009, 1007) through the hole; the cover on
   (-1105, 1007) (none from the wall expected) and on (-1105, 1103) beside it (the wall whole there: high cover
   expected).
4. **Line of sight**: a Sectoid dropped on (-961, 1007) and a soldier on (-1201, 1007): the shot view shows the shot
   through the hole.
5. **The columns**: both copies, (816, 48) and (720, 432), drawn with their lower part gone (as the editor draws them);
   what the part above does (stands as drawn, or falls).

## Result

Not yet played.
