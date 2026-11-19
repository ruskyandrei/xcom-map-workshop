# EXP-82: the map's own fracturing pieces built broken (custom geometry editing plan, E6)

Date: 19 November 2026. Status: **run A played: the broken roofs, the map's own and a made one, are drawn with
their holes ([F-138](../findings-register.md) verified); the wall's hole is drawn and walked through; the cover and
the line of sight through it were not settled (shelves stand behind it); a broken column copy is drawn broken**. The custom geometry editing plan's stage E6 (decision D-5): the
blasts of E5 on the map's own fracturing pieces, the Build writing the fragments they reach as
EditorPaintedVisibleFragments and DestroyedChunks on the piece's component, with those the map already paints out
(tools/bake/made_blasts.py, native_copy.py `blasts_in_place`, `break_component`). Played unattended in the lab copy
(the game-test skill): only what is new.

## What is new

EXP-81 run A showed the game draws a made wall's painted-out fragments gone and its tiles treat the hole as open
(walk, cover, line of sight). New here:
- the arrays written on a component of the map's own, where it stands, its tiles worked out again by a rebuild volume
  over them (as a flag change's are: EXP-60..62);
- the arrays on a moved piece's copy and an added copy of a map piece that already paints a fragment out;
- [F-138](../findings-register.md)'s fix candidate: two roofs whose components keep their fragments
  (`bPreventChunkRemoval`), built broken with the setting turned off: in EXP-81 a made roof's painted-out fragments
  were drawn.

## The project

`EXP-82 map breaks` ([exp82_project.py](../../tools/editor/examples/exp82_project.py)), in a test server's scratch
store; the map `EXP82MapBreaks`, a quick build (no baked light). Game tiles count from the map's corner
(-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

| Piece | Where | What |
| --- | --- | --- |
| The bar's inside wall `XComDecoFracLevelActor_17` | where the map has it: along y from 680 to 1240 on the tile line x -1057, two storeys | one blast of one tile at its foot (the world's (-1056, 1007, 76)): 2 of its 30 fragments saved painted out, a hole from y about 930 to 1062, from the floor to about 170 up |
| The corner column `XComFracLevelActor_5` | moved a tile, to (816, 48, 16) | one blast of two tiles at its foot: 17 of its 29 fragments knocked out, 18 out with the one the map paints out |
| An added copy of that column | (720, 432, 16) | the same blast |
| The bar's roof `XComFracLevelActor_3` | where the map has it, (-1056, 576, 400) | one blast of two tiles: 7 of its 81 fragments, a hole from x -1536 to -1152, y 672 to 1056; `bPreventChunkRemoval` turned off |
| A made roof (the bar's roof's look, 4 by 3 tiles) | over the car park, x -1920 to -1536, y -1440 to -1152, its top at 194 | one blast of one tile at its middle (-1728, -1296): 5 of its 15 fragments; `bPreventChunkRemoval` turned off |

The quick build's log: `broken (in place) XComDecoFracLevelActor_17: 2 of its 30 fragments knocked out by its blasts`,
17 of 29 on each column copy, `broken (in place) XComFracLevelActor_3: 7 of its 81 fragments ...; bPreventChunkRemoval
turned off`, and the made roof `15 fragments (5 knocked out by its blasts; bPreventChunkRemoval turned off)`.

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
6. **The bar's roof** (F-138): seen from above the building with no unit inside, the hole from x -1536 to -1152,
   y 672 to 1056 drawn, the bar's inside seen through it.
7. **The made roof** (F-138): seen from above and from below, a hole at its middle (-1728, -1296), the lot seen through
   it from above.

## Result

Run A, played unattended in the lab copy (the game-test skill), staged by the editor's Play in game on a dry-play
test server: the squad of the play file, invincibility on, Sectoid pods. Pictures are in
`<lab>\hidden-runs\exp82-runA` with the agent's report; the shots below were checked against it.

- **Check 1, load: passed.** `LoadMap: EXP82MapBreaks` and the intro with no crash; no error names the broken pieces (the made
  roof, renamed XComFracLevelActor_207, only in the routine "Cooking Convex" line).
- **Check 6, the bar's roof: passed** (F-138). With the cursor's floor raised (the cutaway shows only a building's floor 1
  while the cursor is on floor 0), the gravel roof has one jagged hole where it was broken, about 300 off its middle
  as planned, and the bar's inside (its tiled wall, a fridge, the floor) is seen through it.
- **Check 7, the made roof: passed** (F-138). It stands inside the car park's box truck, which hides most of it from above;
  with the map's level actors hidden for the shot, the slab stands alone with a five-sided hole at its middle and the
  rest whole.
- **Check 2, the wall's hole: passed.** From inside the bar, close, from both sides: a hole at the wall's foot about a tile and
  a third wide, the far room seen through it.
- **Check 3, walk: passed; cover: not settled.** The tiles just past the hole (x -1009) are not floor: liquor shelves and menu
  boards stand against the wall's other face (the cursor reads 148 to 209 there). A move to (-913, 1007) went
  straight through the hole (the soldier stood behind the bar, the combat log one move). On the hole's tile the
  soldier had high cover toward the wall (cover value 30), as on the tile beside it where the wall is whole: the
  shelves behind the hole may give it.
- **Check 4, line of sight: not settled.** From the hole's tile the shot view offered no target on a Sectoid at (-913, 1007)
  behind the shelves; from the far side a soldier one tile from it could shoot it. A hole with nothing behind it
  would settle it; EXP-81's made wall passed both, cover and sight, on open ground.
- **Check 5, the columns: one copy seen broken.** A brick column copy is drawn with its lower part gone, a ragged slanting
  edge in the air with the street under it, and its upper part stands as drawn (it does not fall). Which copy that
  was, and the other one's look, were not settled in the time.

Findings:
- [F-138](../findings-register.md) verified: with `bPreventChunkRemoval` turned off, a roof's painted-out fragments
  are drawn gone, on the map's own roof and on a made one.
- Placement: the made roof was put where the car park's box truck stands; a later run puts such a piece clear of the
  map's props.
