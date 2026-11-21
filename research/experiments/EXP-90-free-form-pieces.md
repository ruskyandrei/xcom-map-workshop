# EXP-90: made pieces in the free form in the game

Date: 21 November 2026. Status: **prepared offline; the run is under way**. The custom geometry improvements plan's
game runs (its section 7, "What needs the game"): made walls and floors at any place, size, angle and height
(the free form: `fracWall` 5, `fracSlab` 4, numbers with `free: 1`), mitred corners, tall walls made both ways, a
thick wall, a turned floor, and a texture mapping. Everything else in the plan is checked offline. Played unattended
in the lab copy (the game-test skill), one pass of each check and at most one second take.

## The questions

1. A wall off the tile lines: do units walk past its end and through its doorway and window, what cover does it give,
   and does a grenade break it where it is hit?
2. A fractional floor against it: can a soldier stand on it, where does the cursor land, is a tile it covers only in
   part floor or not, and does a break pass between the floor and the wall?
3. Two walls at a free angle in a mitred corner: any gap to see or shoot through at the corner, the cover there, and
   does a grenade on a turned wall break it where it is hit and nowhere else ([F-145](../findings-register.md): the
   columns' rule for a turned wall is a guess)?
4. Walls of a height between storeys, 600 tall made by repeat and by stretch, and 48 thick: each stands, the tall ones
   break as one wall, the thick one's doorway is walked through.
5. A floor turned about the vertical: where the cursor lands near its corners (the compiler warns its cursor floor is
   the box round it) and a soldier on it.
6. A texture mapping under baked light: the mapped wall beside an unmapped one of the same look.

## The project

`EXP-90 free form pieces` ([exp90_projects.py](../../tools/editor/examples/exp90_projects.py)), in a test server's
scratch store; the map `EXP90FreeFormPieces`, a full baked Build. URB_Bar's car park (floor 0), its cars, vans and wheel
stops deleted (313 pieces); the map's landing puts the squad east of all of it (soldiers at x 528 to 912, y -1488 to
-1200). Walls are copies of URB_Bar's inside wall (`XComDecoFracLevelActor_17`, its own look: faces from -8 to 8, bottom
-16, a storey 192), floors of its upstairs floor (`XComFracLevelActor_17`, look `floor`, plate 192 to 194). Game tiles
count from the map's corner (-2785, -1921, -1): tile centres at x -2737 + 96 i, y -1873 + 96 j; the editor's tile lines
are the multiples of 96.

| Piece | Where (location, yaw) | What |
| --- | --- | --- |
| A | (-1889.75, -1111.5), 0 | wall 287.5 long, 400 tall (-16 to 384), its line 6.5 north of the game tiles' centre line y -1105; a window 64 to 136 along it, 72 to 168 up; a doorway 156 to 268 along it, to 160 up |
| B | (-1840.25, -1103.5), 0 | upper floor 230.5 by 170.25 against A's north face; a hole x 40.25 to 80.25, y 118.5 to 158.5 (world x -1800 to -1760, y -985 to -945, across the tiles' edge y -961) |
| C1 | (-1250.5, -1440.25), 5461 (30 degrees) | wall 384 long, one storey (-16 to 192) |
| C2 | (-917.9401, -1248.2606), 21845 (120 degrees) | wall 288 long, one storey, from C1's far end: a right-angled corner |
| D1 | (-1920, -576), 0 | wall 192 long, 260 tall (-16 to 244) |
| D2 | (-1536, -576), 0 | wall 192 long, 600 tall (-16 to 584), tall `repeat` |
| D3 | (-1152, -576), 0 | wall 192 long, 600 tall, tall `stretch` |
| D4 | (-768, -576), 0 | wall 288 long, two storeys, 48 thick (faces -24 to 24), a doorway 96 to 192 along it |
| E | (-400.5, -1440.25), 3641 (20 degrees) | upper floor 288 by 192 |
| F1 | (-480, -960), 0 | wall 288 long, two storeys, its faces mapped: 64 by 64 a repeat, turned 30 degrees |
| F2 | (0, -960), 0 | the same wall unmapped (the same seed) |

Where the game's lines between tile centres cross A (the compiler's `grid_crossings`): 16.75, 112.75 and 208.75 along
it, at x -1873, -1777 and -1681. So, as the compiler reads it: at x -1873 the wall is whole (high cover), at -1777 the
window (low cover, units vault through), at -1681 the doorway (units walk through, no cover: warned
`wall-doorway-no-door`). The same for D4's doorway at x -625.

C's corner is at (-917.94, -1248.26), on the tiles' edge between (-913, -1297) and (-913, -1201). The corner's inside
is west of it; C1 crosses the tiles (-1201, -1393), (-1105, -1393), (-1105, -1297), (-1009, -1297), (-913, -1297) and
C2 the tiles (-913, -1201), (-1009, -1201), (-1009, -1105), (-1009, -1009), (-1105, -1009) (tile centres within 56 of
a wall's line).

B over the tiles: columns x -1777 and -1681 whole, -1873 15.25 of 96, -1585 23.25; rows y -1009 whole, -1105 46.5 (A's
row, A's upper storey in it), -913 27.75. Wholly covered and clear of the hole: (-1681, -1009). In part:
(-1681, -913) 29%, (-1585, -1009) 24%, (-1873, -1009) 16%.

E's corners: (-400.5, -1440.25), (-129.87, -1341.75), (-195.54, -1161.33), (-466.17, -1259.83); the box round it x
-466.17 to -129.87, y -1440.25 to -1161.33. The tile (-337, -1297) is on it; (-433, -1393) and (-145, -1201) are inside
the box and off the floor.

## Offline

- **Compile**: no error, nothing left out. Warnings: A's and D4's doorways have no door (`wall-doorway-no-door`); B and
  E stand in no building (`slab-outdoors`); E is turned off the quarter turns (`slab-turned`: its cursor floor is the
  box round it). Note: D2 is made as two walls stacked (`made-split`). The mitre: C1's far end `{inset: 0, lean: -1}`,
  C2's near end `{inset: 0, lean: 1}` (a plane at 45 degrees to each, the right angle's bisector).
- **Build** (baked, 51 seconds): twelve made pieces, each its own mesh: A 27 fragments and 6 collision boxes, F1 and F2
  15 fragments each (different meshes from the one seed: the mapping), C1 13, C2 9, D1 6, D2's lower 10 and upper 6, D3
  16 (one 600-tall mesh), D4 21 fragments and 3 boxes, B 6 fragments and 4 boxes (round its hole), E 4. A and B list
  each other's columns where they meet (12 and 18 listings), C1 and C2 (28 and 28), D2's two parts (12 and 8). The
  made floors' cursor floors: 4 of the map's cursor volumes taken out, 36 made (8 over the made slabs). The relight lit
  the twelve from nothing and traced their own shadow maps (D1's bounce scale came out near 1.8 where the others' are
  0.09 to 0.86: noted, not followed).
- **Package read back** (`EXP90FreeFormPieces.upk`): `XComDecoFracLevelActor_18` (A), `_19` (F1), `_20` (F2), `_21`
  (C1, yaw 5461), `_22` (C2, yaw 21845, at (-917.9401, -1248.2606)), `_23` (D1), `_24` and `_25` (D2, the upper at
  400), `_26` (D3), `_27` (D4), `XComFracLevelActor_206` (B), `_207` (E, yaw 3641): each at its place and turn, a
  `FracturedStaticMesh` of its own (`XComMapEdGeo.FracWall_*` or `FracSlab_*`) with its `RB_BodySetup`, its fragment
  columns and its lightmap.

## The run (hidden game)

Staged by the editor's Play in game on a test server started with `--dry-play` (its install the parked lab copy), and
started with the play file it wrote. Out folder `<lab>\hidden-runs\exp90-1`; `report.md` there holds each step.

(Results follow as the checks are run.)
