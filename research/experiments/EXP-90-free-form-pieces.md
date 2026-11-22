# EXP-90: made pieces in the free form in the game

Date: 21 November 2026. Status: **run 1 played: the mitred corner, the thick and tall walls, the turned floor and the texture mapping passed; the turned wall broke in its middle, away from the blast ([F-145](../findings-register.md) failed); a wall standing in a tile row takes those tiles ([F-146](../findings-register.md)); a tile a floor covers under about a third of is no floor ([F-147](../findings-register.md))**. The custom geometry improvements plan's
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

Run 1, 21 November 2026, unattended in the lab copy (LWR), the editor's test squad, the Abduction mission (four
Sectoid pods), invincibility on and the fog lifted. One pass of each check; one second take (check 5). The out folder's
report and the shots were read against each other.

1. **A, a wall off the tile lines: walking and cover passed; the window's vault unclear; the break passed for what was
   seen.** Beside its south face the soldiers' cover read 50, 30 and 0 at x -1873, -1777 and -1681: high, low and none,
   as the compiler's grid crossings said (whole wall, window, doorway). A soldier walked into the doorway's tile and on
   through it. The wall stands inside the tile row centred y -1105, and the tiles of that row it covers can't be stood
   on: the one its west part covers (64.75 of 96) and the window's ([F-146](../findings-register.md)). A soldier walked
   past its end (the game put him 44 off the tile's centre, against the wall's end). No move told a vault through the
   window from a walk round. An HE grenade by its west end broke its lower storey round the blast (the window's and the
   west tile could be stood on after, the cover there went to 0); its upper storey stood over the gap, as F-127; the
   east jamb was not read.
2. **B, a fractional floor: standing passed, the cursor passed on a whole tile, a tile it covers in part is no floor;
   the break passed for B, its passing to A unclear.** The cursor landed on B's top (z 258) over the tile B covers whole
   and on the ground over tiles it covers 29% and 24%; a soldier put on B stood at z 264, and ordered onto the 29% tile
   went down to the ground ([F-147](../findings-register.md)). With soldiers standing under B the cursor stayed on the
   ground at every storey. A grenade on B's top took B whole and what stood of A with it; A's upper storey was inside
   the blast too, so the passing of the break can't be told.
3. **C, a mitred corner at a free angle: sight and cover at the corner passed; the turned wall's break failed; one wall
   broken away from the other passed.** A Sectoid inside the corner, under two tiles from a soldier at its outside tile,
   was not offered in his shot view (two farther Sectoids were). That outside tile, under C1's end, gave high cover (50);
   the outside tile by C2's end is blocked. An HE grenade landed on the pavement about 120 south-east of C1's start: C1's
   first part (to about 160 along it, 120 to 140 from the blast) stood, its middle (about 160 to 270 along it, 190 to 270
   from the blast) was gone, and its corner part stood with C2 ([F-145](../findings-register.md)).
4. **D, heights and a thick wall: passed.** All four stood, the 600-tall ones at their height with the look's bands
   repeated (D2) or one face over the height (D3). One HE grenade at D3's foot took the lowest storey of both D3 and D2,
   the rest of each standing over the gap, as the game's walls do (F-127); D3, one 600-tall mesh, broke like D2's two
   stacked pieces. A soldier walked through D4's 48-thick doorway in one tile.
5. **E, a floor turned 20 degrees: a soldier on it passed; the cursor near its corners as warned, in part (unclear).**
   A soldier put on it stood at z 264. Over tiles on it the cursor landed on its top; over one tile inside the box round
   it and off the floor, (-433, -1393), it landed at the floor's height once (aimed from the north-east) and on the
   ground when aimed from the floor itself, and the soldier ordered there went to the ground; over (-145, -1201) and
   (-433, -1201), also in the box, it landed on the ground. Reading the built cursor volumes over E would settle what
   they cover.
6. **F, a texture mapping under baked light: passed.** The mapped wall shows its look's materials at a much smaller
   repeat with the rows on a slant, on both faces and bands; it and the unmapped wall beside it are lit alike by the
   map's baked light, with no black, blotch or seam.

Side notes: the A grenade's alien turn ran at once when every soldier had acted; a `SAVING...` badge showed for a while
in turn 2 (no save was asked for). The parked lab copy was used (`--game`, and the test server's `--install`): the
folder Steam runs held the LWR3 copy.

## Afterwards, offline: the relight with two mappings (the plan's 5.8)

The project built baked twice, F1 with its mapping and with it taken out (21 November 2026): of 199 relit pictures one
differs, F1's lightmap (`XComDecoFracLevelActor_19`, 9,358 of 32,160 texels, mean 0.78 of 255, at most 25); the same
project built twice gives the same 199 pictures, so the relight is repeatable. The cause is the lightmap's form, not a
texture read: a texel's light is stored in its tangent frame (`lightmap_texels.rasterise` frames, `codec.coefficients`),
and a mesh's tangents follow its texture coordinates, so a turned mapping turns the frame and the stored numbers with it.
The game reads them back in that frame: F1 and F2 look lit alike in check 6. The albedo is one value per material
(`albedo.Albedo`: a diffuse texture's mean), and a made piece is relit in every build, never taken from the piece cache
(`relight.PieceCache`: copies are always relit), so the mapping needs no place in the cache's key.

## After the run (offline, 21 and 22 November)

- B's and E's collision and cursor volumes read from the built package, against the game's floor trace through each
  tile's centre: a made floor is a tile's floor only where it covers the tile's centre, and E's readings near its
  corners are those of tiles it covers in part, not of the box its cursor floors stood in
  ([F-147](../findings-register.md)). The editor now says which tiles a made floor is floor on, and a turned floor's
  cursor floors stand in steps.
- A's tiles: a wall over a tile's middle meets the game's occupancy box there and takes the tile; its window's tile
  is no one's, so nothing vaults through it ([F-146](../findings-register.md)). The editor now reads such a wall's
  openings so and notes the tiles it takes.
