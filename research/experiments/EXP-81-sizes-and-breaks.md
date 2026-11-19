# EXP-81: made walls and floors past the game's sizes, and made walls and roofs built broken (custom geometry editing plan, E4 and E5)

Date: 19 November 2026. Status: **run A prepared**. The custom geometry editing plan's stages E4 (any size: the Build
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

Not yet played.
