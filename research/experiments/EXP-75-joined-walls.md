# EXP-75: made walls that meet, a door in a made wall, a room in a building (custom geometry plan, M3, run C)

Date: 18 November 2026. Status: **prepared**. The custom geometry plan's stage M3 (branch `fracturing-wall-poc`):
made walls that meet join (an L's longer wall runs through to the other's far face, the other butts on its face; a T's
stem stops on the through wall's face), a made wall and the fracturing pieces it touches list each other's columns
by the game's rule (so a break passes between them), a door standing in a made wall's doorway is listed in its
columns, the Room tool, and made walls listed in the floors of the building they stand in by their own boxes. Played
unattended in the lab copy (the hidden game, the game-test skill): only what is new since EXP-73 and EXP-74, and
what they left open.

## What is new

- Corners and T joints of made walls: the corner square filled by the wall that runs through; the joint's look from
  both sides (gaps, flicker, trims, light) and the tiles round it (the corner square reaches 7 units into the tile
  outside an L's corner, as the game's corners do; offline, the game's occupancy rule).
- Breaks passing on: joined made walls, a made wall on another, and a made wall touching the map's own pieces list
  each other's columns (research/native/frac-neighbours.md): the game hands a damaged column's damage to each listed
  column, one step.
- A door copied into a made wall's doorway is listed in the wall's columns (it goes when the wall round it breaks).
- A room in a building made in the editor: its walls in the building's floors by the game editor's rule for their
  own boxes (both floors, with the CutdownFloor the rule gives).
- A made wall on the bar's roof: listed in the bar's building's roof floor.

## The project

`EXP-75 joined walls` ([exp75_project.py](../../tools/editor/examples/exp75_project.py)), in a test server's scratch
store; the map `EXP75JoinedWalls`, built with the lighting baked. Copies of URB_Bar's inside wall
(`XComDecoFracLevelActor_17`), two storeys unless said. Game tiles count from the map's corner (-2785, -1921, -1):
tile centres at x -2737 + 96 i, y -1873 + 96 j.

| Wall | Where | What |
| --- | --- | --- |
| A, B | parking lot (floor 0): A along x from (-1344, -672) to (-1056, -672); B from A's far end south to (-1056, -864) | an L at (-1056, -672): A runs through (8 past the corner's line), B butts on A's face |
| D, E | lot: D along x from (-960, -672) to (-480, -672), a doorway at x -864 to -768; E from D's line at x -672 south to (-672, -960) | a T at (-672, -672): E's end stops on D's face |
| Room | lot: x -1728 to -1440, y -1056 to -768; a doorway in its south side at x -1632 to -1536 | four walls joined at the corners (south and north run through); a building made round it, floor 1 from 0 to 208, floor 2 from 208 to 400 |
| F | pavement before the bar (floor 16), along x from (-1536, -192) to (-1152, -192), a doorway at x -1440 to -1344 | the bar's door `XComInteractiveLevelActor_6` and its frame copied into the doorway |
| G | the bar's roof (floor 400), along x from (-1440, 384) to (-1152, 384), a doorway at x -1344 to -1248 | in the bar's building's roof floor |
| W1a, W1b | lot: along x from (-1344, -1248) to (-1056, -1248); W1b 192 higher | a one-storey wall and another standing on it; they list each other's columns |

## Run C (hidden game)

1. **Load**: the battle starts on `EXP75JoinedWalls`; no crash, no error naming a made wall, the door copy or the
   building.
2. **The L's corner** (A and B at (-1056, -672)): close shots from outside (north-east) and inside (south-west): no gap
   or slit at the corner, no flicker where the faces meet, the trims (skirting, cornice) meeting or butting cleanly,
   the light even across the joint. For the user's eye as well.
3. **The T** (D and E at (-672, -672)): close shots from both sides of the stem: E's end against D's face, no gap.
4. **Tiles at the L**: on the inside corner tile (-1105, -721) high cover north and east (50 each), and a soldier walks
   into it from (-1201, -721). On the outside corner tile (-1009, -625): its cover flags (none expected), and a soldier
   walks into it.
5. **Tiles at the T**: on (-721, -721) and (-625, -721) high cover north (D) and toward the stem (east, west).
6. **A break at the corner**: a grenade on (-1009, -721) (beside B's top, under A's end): both walls holed at the joint
   (A's corner columns and B's first ones), as the break passes between them; whether any part is left floating.
7. **The door in F**: a soldier walks through F's doorway (from (-1393, -241) to (-1393, -145)); then a grenade by F's
   doorway on (-1393, -241): the door and its frame go with the wall round them.
8. **The room in its building**: a soldier walks in through its doorway (from (-1585, -1105) to (-1585, -1009)); with
   him inside, shots from the default camera: the room's near walls cut down (or hidden) floor by floor as the bar's
   walls are when a soldier is in the bar (compare one shot of a soldier in the bar); the camera's floor raised and
   lowered.
9. **The wall on the roof** (G): from the default camera, is G drawn (EXP-73's roof wall wasn't seen)? A soldier put on
   the roof at (-1297, 431) walks straight south through G's doorway to (-1297, 335).
10. **The wall on a wall** (W1a, W1b): a grenade by W1a on (-1201, -1297): does W1b break with it now, or stay in the
    air (F-127)?
11. **One of the game's own walls** (F-127's control): a grenade beside the bar's inside wall `XComDecoFracLevelActor_17`
    (along y at x -1056, y 680 to 1240, floor 16), on a tile next to its foot inside the bar: is its upper storey left
    standing over a hole broken through its lower one, as the made walls' were?

## Result

Not played yet.
