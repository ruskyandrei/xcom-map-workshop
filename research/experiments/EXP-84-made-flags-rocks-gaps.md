# EXP-84: flags on made pieces, a rock shaped by its points, and three gap cases

Date: 19 November 2026. Status: **run A played: every check passed**; the strip over a gap the whole wall long stood after a grenade at the floor, as a made wall's upper storey does ([F-127](../findings-register.md)). The short game run before the custom geometry
branch (`fracturing-wall-poc`) goes into main, asked by the user: what the branch built since its last runs and never
played. Played unattended in the lab copy (the game-test skill): only what is new.

## What is new

- Flags on made pieces (the change ledger, 19 November: "Flags on made walls, floors and ground"): a made wall with
  Gives cover off, one with Blocks sight off; a ground block made on a static mesh actor (which the Build makes a level
  piece) with Gives cover off. Each beside a control made the same with its flags as made.
- A rock shaped by its points (the look picker and rock points plan, R1 to R3): its footprint grown a tile east by
  three of its points pulled out, as the editor's blue points do. Its hull, mesh and collision are made as a seeded
  rock's (played in EXP-77 and EXP-79); what is new is the shape.
- Gaps (the change ledger, 19 November: "Gaps are one kind"): a doorway with the threshold Add gap leaves (8 over the
  floor) and a game door in it; a gap cut through a wall's top (a notch); one gap the whole wall long, leaving a strip
  under it and one over it.

## The project

`EXP-84 made flags rocks gaps` ([exp84_project.py](../../tools/editor/examples/exp84_project.py)), in a test
server's scratch store; the map `EXP84MadeFlagsRocksGaps`, a quick build (no baked light: made pieces get one even
light). URB_Bar's car park, its cars and vans deleted. Walls are copies of URB_Bar's inside wall
(`XComDecoFracLevelActor_17`); the blocks and the rock are made on URB_CommercialAlley's asphalt plane
(`StaticMeshActor_50`). Game tiles count from the map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i,
y -1873 + 96 j.

| Piece | Where | What |
| --- | --- | --- |
| N | y -1152, x -2016 to -1536, on the lot (0) | a one-storey wall, flags as made (the control) |
| C | y -1152, x -1344 to -864 | a one-storey wall, Gives cover off |
| S | y -1152, x -672 to -192 | a one-storey wall, Blocks sight off |
| G0 | x -1920 to -1728, y -864 to -768 | a block 64 tall, flags as made (the control) |
| G | x -1440 to -1248, y -864 to -768 | a block 64 tall, Gives cover off |
| R | footprint x -960 to -672, y -864 to -672 | a rock 96 tall: two foot points and a middle one pulled out into the tile (-721, -721) |
| D | y -192, x -1536 to -1152, on the pavement (16) | a two-storey wall, a doorway at x -1440 to -1344 from 8 to 160, the bar's door `XComInteractiveLevelActor_6` and its frame in it |
| T | y -384, x 0 to 384 | a one-storey wall (192), a gap at x 96 to 192 from 72 up through its top |
| W | y -384, x 576 to 960 | a two-storey wall (384), one gap the whole wall long from 72 to 168 |

## Run A (hidden game)

1. **Load**: the battle starts on `EXP84MadeFlagsRocksGaps`; no crash, no error naming a made piece.
2. **Cover off on a made wall**: a soldier on (-1777, -1201), south of N's middle, is in cover (the control); one on
   (-1105, -1201), south of C's middle, is not. Read `XGUnit m_bInCover` and `CurrentCoverPointFlags` (or the cover
   shield in a shot). Passed if N gives cover there and C none.
3. **Sight off on a made wall**: a Sectoid dropped on (-433, -1105), north of S's middle, and a soldier on
   (-433, -1297), two tiles south: the shot view (key 1) offers the Sectoid as a target. The control: a Sectoid on
   (-1777, -1105) behind N and a soldier on (-1777, -1297): not offered. Passed if S is seen through and N is not.
4. **Cover off on a made block on a static mesh actor**: a soldier on (-1873, -913), south of G0, is in cover (low);
   one on (-1393, -913), south of G, is not. Passed if G0 gives cover and G none.
5. **The rock's moved points**: a shot of R from the south-east shows the arm reaching east; a soldier on
   (-625, -721), east of the arm, is in cover (the seeded rock's edge would be a tile and a half away). A move order
   onto (-721, -721), under the arm: read where he ends. Passed if he is in cover beside the arm and the arm is drawn.
6. **A door over a threshold**: a soldier on (-1393, -241) walks to (-1393, -145) through D's doorway. Passed if the
   door opens and he goes through; a shot of the shut door's foot (from the side, low) shows no gap under it.
7. **A notch**: a shot of T; a soldier on (143, -433) goes to (143, -337) through the notch. Passed if the notch is
   drawn from 72 to the top and he climbs through it.
8. **A gap the whole wall long**: a shot of W shows the strip under and the strip over; a soldier on (719, -433) goes
   to (719, -337) through it; then a grenade at (815, -433), against the wall. Passed if both strips are drawn, he
   climbs through, and the grenade breaks the strips near it with no crash.

## Result

Run A, 19 November 2026, unattended in the lab copy (LWR), one pass of each check and one second take (check 8); the
out folder's report and the shots were read against each other. Invincibility was on and the fog lifted.

1. **Load: passed.** The battle started on `EXP84MadeFlagsRocksGaps`; no error names a made piece (the log's only
   lines about them are the usual notes as the game cooks the made walls' collision).
2. **Cover off on a made wall: passed.** South of N a soldier reads `m_bInCover` True, cover value 50 (high), the
   shield drawn; south of C, False, 0, no shield.
3. **Sight off on a made wall: passed.** From two tiles south of S, the shot view offers the Sectoid behind it (drawn
   as an outline through the wall, 69%, its high cover shield). From two tiles south of N, the Sectoid behind it is
   not offered; the soldier's targets are the Sectoids by S, 14 tiles away.
4. **Cover off on a made block on a static mesh actor: passed.** South of G0, in cover, value 30 (low), the half
   shield drawn; south of G, not in cover, 0.
5. **The rock's moved points: passed.** The rock is drawn as a low mound with a lobe reaching east (very dark under
   the quick build's even light: seen on a brightened copy of the shot). A soldier on (-625, -721), east of the arm,
   is in low cover (30); without the moved points the rock's edge would be a tile and a half from him. Read on the
   side: a soldier sent onto (-721, -721) climbed onto the arm and stands on its top, 78 over the lot.
6. **A door over a threshold: passed.** The soldier went through D's doorway in one tile, the door opening; in a low
   shot before, the shut door stands on the threshold strip with no gap under it.
7. **A notch: passed.** T is drawn with the notch one tile wide from about 72 through its top; the soldier crossed
   through it in one tile, in low cover on both sides (the notch's sill).
8. **A gap the whole wall long: passed for what it asked, the upper strip standing.** Both strips are drawn and the
   soldier crossed through. An HE grenade at (815, -433) broke the lower strip along its whole length, with no
   crash. The strip over the gap stood whole, fire on its top, over the open gap (a second, closer shot the same).
   W's numbers give 4 fragments under the gap and 12 over it (offline, `frac_wall.cells`), so the upper strip can
   break; the burst at the floor left it as it leaves a made wall's upper storey over a hole it breaks
   ([F-127](../findings-register.md): the game's own walls do the same). A burst at the strip's height was not played.

Side notes, not checks: the map's two pod Sectoids ended on one spot against S's south face after the first drop; a
car by the Skyranger and one at the lot's west edge stand outside the deleted part of the car park.
