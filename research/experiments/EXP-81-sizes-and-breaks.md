# EXP-81: made walls and floors past the game's sizes, and made walls and roofs built broken (custom geometry editing plan, E4 and E5)

Date: 19 November 2026. Status: **run A played: five checks passed; the made roof's painted-out fragments are drawn
in the game ([F-138](../findings-register.md)); a grenade on a made roof slab left it looking whole**. The custom geometry editing plan's stages E4 (any size: the Build
cuts a made wall into walls of at most 16 tiles joined end to end and its look's storeys stacked, and a floor or roof
into slabs of at most 16 by 16 side by side, tools/bake/made_split.py) and E5 (Break: blasts saved on a made piece,
the Build writing the fragments they knock out as EditorPaintedVisibleFragments and DestroyedChunks, as the game's
maps save the pieces their designers painted out, tools/bake/made_blasts.py). Played unattended in the lab copy (the
game-test skill): only what is new.

## What is new

- A wall longer than 16 tiles is two copies joined end to end: their joint ends reach the line (`line`), they list
  each other's columns, and the texture runs on across the joint (offline: the diamond tiles continue in the editor).
- A wall taller than its look is its look's walls stacked, the upper on the lower's top.
- A floor or roof larger than 16 tiles is slabs side by side listing each other's columns.
- A made wall and a made roof built broken: fragments saved painted out, never seen in the game on a made piece. Not
  known: whether the game draws them gone, whether the tile rebuild treats them as gone (units walk and see through
  a wall's hole, a roof's hole has no floor), and what breaking the rest does next to the hole.

## The project

`EXP-81 sizes and breaks` ([exp81_project.py](../../tools/editor/examples/exp81_project.py)), in a test server's
scratch store; the map `EXP81SizesAndBreaks`, a quick build (no baked light). On URB_Bar's car park (floor 0), its cars
and vans deleted. Copies of URB_Bar's inside wall (`XComDecoFracLevelActor_17`, in its own look: dark wood panelling
under brick on one side, diamond tiles on the other) and roof (`XComFracLevelActor_3`). Game tiles count from the
map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j.

| Piece | Where | What |
| --- | --- | --- |
| L | along x from (-1920, -1152) to (384, -1152), two storeys | 24 tiles: walls of 16 and 8 joined end to end, the joint at x -384 |
| T | along x from (576, -1152) to (864, -1152) | four storeys: two two-storey walls, the upper standing on the lower's top (400 up), its top 784 over the lot |
| B | along x from (-1536, -672) to (-1152, -672), two storeys | one blast of one tile at x -1344, 60 up: 4 of its 20 fragments saved painted out |
| Room | x 0 to 384, y -768 to -480, one storey (top 192), a doorway in the south side at x 192 to 288 | its roof on its walls' tops (192), one blast of one tile at its middle (192, -624): 3 of its 15 fragments out; a building round it (floor 0 from -16 to 192, floor 1 from 192 to 384) |
| F | roof slab at 192 over the lot, x -1920 to 0, y -1440 to -1248 | 20 by 2 tiles: slabs of 16 by 2 and 4 by 2 side by side, the joint at x -384 |

## Run A (hidden game)

1. **Load**: the battle starts on `EXP81SizesAndBreaks`; no crash, no error naming a made piece.
2. **L's joint** (x -384, y -1152): close shots from both sides at the joint: no gap or slit, the panelling, brick and
   diamond tiles running on across it, the light even.
3. **A break across L's joint**: a grenade on the tile by the joint, (-433, -1105) or (-337, -1105): both pieces
   holed round the joint (the break passes between them).
4. **T**: it stands four storeys tall (to about 784), the joint between its pieces (about 384 to 400 up) with no gap.
   A grenade at its foot, on (719, -1105): its lower piece holed; is the upper piece left standing (as the game's walls
   keep their upper part, EXP-75)?
5. **B's hole** (x about -1440 to -1248, low): drawn at load, from both sides. A soldier walks from (-1393, -721)
   through it to (-1393, -625) (and, if not, from (-1297, -721) to (-1297, -625)); the cover on the hole's tile
   (-1393, -721) and on (-1489, -721) beside it (the wall there whole: high cover expected); line of sight through the
   hole (the shot view from one side at a target on the other).
6. **The roof's hole** (tiles about x 143 and 239, y -625 and -721): drawn from above. A soldier put on the roof (its
   top 194) beside the hole, at (47, -625): does he walk onto the hole's tiles (143, -625) on the roof's level, or not
   (no floor there)? A soldier walks into the room through its doorway, from (239, -817) to (239, -721).
7. **A break across F's joint** (x -384): a soldier put on F at (-625, -1297); a grenade at (-433, -1297) on F's level:
   both slabs broken round the joint.

## Result

Run A, played unattended in the lab copy (the game-test skill), staged by the editor's Play in game on a dry-play
test server: the Abduction mission, the squad "EXP-64 six", invincibility on, Sectoid pods (two of them in the room).
Pictures are in `<lab>\hidden-runs\exp81-runA` with the agent's report; the shots below were checked against it.

1. **Load: passed.** `LoadMap: EXP81SizesAndBreaks` and the intro with no crash. The Build's renamed pieces
   (XComDecoFracLevelActor_18 to _26, XComFracLevelActor_206 to _208) appear only in the routine "Cooking Convex"
   lines.
2. **L's joint: passed.** From both sides, high and low, the joint can't be found: the tiled face's diamonds run on
   in one even row and the grid lines without a break, and the brick-and-panelling face is one face, evenly lit.
3. **A break across L's joint: passed.** A grenade by the joint took the lower storey away on both sides of x -384;
   the upper storey stayed spanning the hole, as the game's walls do (EXP-75).
4. **T: passed.** Four storeys stand, the joint a solid dark band at 400 up with nothing seen through it. A grenade
   at its foot took nearly all the lowest storey away; the lower piece's upper storey and the whole upper piece stood
   over the hole.
5. **B's hole: passed.** Drawn from both sides as a jagged hole down to the ground, the lot seen through it. A soldier
   walked through it (one tile, (-1393, -721) to (-1393, -625)); on the hole's tile he had no cover (cover value 0),
   on the tile beside it high cover toward the wall (cover value 50); a shot through it from three tiles hit (100%).
6. **The roof: its hole is not drawn (failed); a soldier on the roof: unclear; the doorway walk passed.** Seen from
   above the building, close and from the north, the roof's paving runs on unbroken over its middle, where 3 of its
   15 fragments are saved painted out; nothing of the room is seen through it. The cursor never picked the roof's top
   (every readback on cursor floors 1 to 3 was the room's floor, 64), so no soldier was put on it. A soldier walked in
   through the doorway.
7. **A break across F's joint: unclear.** A soldier stood on F (264 up) and a grenade was thrown onto F's level by the
   joint; afterwards both slabs looked whole from above and low, and he still stood there. Whether the grenade burst
   on F was not settled.

Findings:
- [F-138](../findings-register.md): the made roof's painted-out fragments are drawn. Its component, a copy of the
  bar's roof's, keeps its fragments (`bPreventChunkRemoval`); B's wall's donor has no such setting, and the copy of the
  bar's upstairs floor (no such setting either) broke visibly in EXP-76. Check 7 fits the same reading. Fix
  candidate: a piece built broken has the setting turned off; played in [EXP-82](EXP-82-map-breaks.md).
- The cursor not picking a made roof that is a building's floor 1 at 194 (in EXP-76 and EXP-80 one at 194 was
  picked, F-135): not looked into; a `--saving` run and save_tiles.py would tell whether its tiles are floor.
