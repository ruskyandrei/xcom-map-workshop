# EXP-76: a made upper floor and roof over a room of made walls (custom geometry plan, M5, run E)

Date: 18 November 2026. Status: **played, two passes**: the slabs load, look right, are walked on and break near the blast, and saving keeps them; the room is cut away from inside on floor 0 but not on floor 1, and the cursor takes the made floor on floor 0 ([F-128](../findings-register.md)). Part of the custom geometry plan's stage M5 (branch
`fracturing-wall-poc`): floor and roof slabs made from numbers. Each is a copy of one of the game's fracturing slabs
with its own mesh (tools/bake/frac_slab.py), columns by the slabs' rule, and the donor's floor flags. Played
unattended in the lab copy (the hidden game, the game-test skill), checking only what is new.

## What is new

- A slab made from numbers: its fragments (half tiles cut on a diagonal, whole and double tiles), its top and
  underside on its donor's materials, a collision box for each solid strip round its holes.
- A made upper floor: units walk on it, it is floor where there is standing room over it, and a hole in it is no
  floor.
- A made roof: in its building's top floor, cut away with it when the cursor is inside, and (the donor's flags) taking
  no clicks.
- A break in a slab: what falls, and what the tiles over and under it become.

## The project

`EXP-76 floors and roofs` ([exp76_project.py](../../tools/editor/examples/exp76_project.py)) is in a test server's
scratch store. Its map, `EXP76FloorsAndRoofs`, is built with the lighting baked, on URB_Bar's parking lot (floor 0).
Game tiles count from the map's corner (-2785, -1921, -1), so tile centres are at x -2737 + 96 i, y -1873 + 96 j.

| Piece | Where | What |
| --- | --- | --- |
| Room | x -1728 to -1344, y -1056 to -768; a doorway in its south side at x -1632 to -1536 | four made walls (the bar's inside wall), two storeys, joined at the corners |
| Floor | over the whole room, its top at 194; a hole at x -1536 to -1440, y -960 to -864 | a copy of the bar's upstairs floor (`XComFracLevelActor_17`), made from numbers |
| Roof | over the whole room, its top at 386 | a copy of the bar's roof (`XComFracLevelActor_3`), made from numbers |
| Building | the room's footprint: floor 1 from -16 to 192, floor 2 from 192 to 384, floor 3 (the roof's) from 384 to 576 | as the Room with a roof tool makes it since the first pass (it was -16 to 208 and 208 to 400) |
| Lone roof | x -1152 to -960, y -1056 to -864, its top at 386, nothing under it | a roof standing in the air |
| Long floor | x -1728 to -768, y -1440 to -1152, its top at 194, nothing under it | a floor ten tiles by three, for the second pass's check 6 |

The room's tiles: x centres -1681, -1585, -1489, -1393; y centres -1009, -913, -817. The doorway's tile is
(-1585, -1009). The hole's tile is (-1489, -913).

## Run E (hidden game, with saving)

1. **Load**: the battle starts on `EXP76FloorsAndRoofs`, with no crash and no error naming a slab.
2. **The look**:
   - from the default camera outside, the roof's top and the room;
   - from overhead with the fog off, the lone roof;
   - the roof's top on its donor's gravel material, lit, with no holes or flicker.
3. **Under the floor**: a soldier walks in through the doorway, (-1585, -1105) to (-1585, -1009), then to (-1681, -817):
   - he stands on the ground floor (z about 0);
   - the camera's floor shows the ground, with the floor and roof cut away over him;
   - a shot looking up at the hole from the ground.
4. **On the floor**: a soldier is put on the upper floor at (-1681, -1009), storey 1 (`aim ... --floor 1`, then
   TeleportToCursor) and walks to (-1393, -817), storey 1:
   - he stands at about 194 and the walk is a path over the slab;
   - he cannot be sent onto the hole's tile (-1489, -913) on storey 1 (no floor there): "did not move", or he ends
     beside it.
5. **The roof takes no clicks**: the cursor aimed inside the room on the ground floor lands at about 0, and aimed on
   storey 1 at about 194, never on the roof (386). Read with ShowCursorLoc.
6. **A break in the floor**: from the upper floor, a grenade on (-1393, -1009), storey 1 (two tiles from the hole):
   - the floor holed there, and what falls;
   - whether the walls under it and the roof over it stay (F-127);
   - a soldier standing on a floor tile that breaks (put him on (-1393, -817), storey 1, and throw at his tile):
     does the game drop him to the ground below and keep him in play (T-47: the game's landing event fires for a prop
     whose mesh swaps, and has not been seen for a fragment gone from a floor)?
   - the soldier on the floor sent onto the broken tile: does the game still take it as floor?
   - a soldier on the ground under it;
   - the save's tiles if needed (tools/lab/save_tiles.py).
7. **Save and load**: a quicksave after the break, then a load. The hole the grenade made is still there, and the
   soldiers stand where they stood.

## Run E, second pass (on the rebuilt map)

Only what the first pass left: the room's building rebuilt with floors breaking at 192 and 384 and a roof floor, and
the long floor added.

3. **Cut away**: a soldier inside the room on the ground, the camera's floor 0: the made floor and the roof are not
   drawn, as the bar's upper floor and roof are not with a soldier inside it. Floor up once: the made floor drawn, the
   roof not. Floor up again: both drawn.
5. **The cursor inside**: from a soldier near the room, aimed inside it on floor 0, the cursor lands on the ground
   (about 64 by ShowCursorLoc); on floor 1, on the made floor (about 258); never on the roof unless on the roof's
   floor.
6. **How far a grenade breaks a made floor**: a soldier put on the long floor at (-1009, -1297) (about 264), a
   grenade on (-1681, -1297), its west end. Read the floor afterwards with the cursor on (-1681, -1297),
   (-1489, -1297), (-1297, -1297), (-1105, -1297) and (-817, -1297): which tiles are still floor (about 258) and
   which read the ground. Expected, as the game's own rule: the tiles within the blast's reach (two or three tiles)
   broken, the east end standing. A shot from low along it.
7. **Save and load**: a quicksave after the break, then a load: the hole is still there, and the soldiers stand where
   they stood.

## Result

### Run E, second pass (18 November 2026)

Played unattended in the lab copy on the rebuilt map (the room's floors breaking at 192 and 384, a roof floor, the
long floor). Pictures are in `<lab>\hidden-runs\exp76-runE2`.

3. **Cut away: floor 0 passed, floor 1 failed.**
   - Floor 0, a soldier on the ground in the room: neither the made floor nor the roof is drawn and the walls are cut
     to their lower storey; the soldiers inside are drawn whole (in the first pass they showed as outlines under the
     slabs). The fix of 0ef5535 took.
   - Floor 1, the view raised one floor with the soldier still inside: the room is drawn whole, its walls full height
     and the gravel roof over it (the top-down picture shows the roof, no hole). Expected: the made floor drawn, the
     roof not. Floor 2 looks the same.
5. **The cursor inside: failed, as in the first pass.** On floor 0 the cursor reads 258 on the room's tiles (the made
   floor's top, 194, and a unit's 64) from inside the room and from outside it; on floors 1 and 2 it reads 450 (the
   roof). A soldier put there with TeleportToCursor on floor 0 stood on the made floor; walk orders with the cursor at
   258 still walked soldiers on the ground.
   - Cause, as far as known: URB_Bar's cursor floors are four map-wide volumes breaking at 210, 402 and 594 (the
     export's cursorVolumes), 16 over the room's floors, because the bar's own floors stand 16 up (its upper floor's
     top is at 210). Floor 0's cursor looks down from 210 and meets the made floor at 194 first; floor 1's from 402
     meets the roof at 386. The camera's floor then puts the cursor in the room's floor 2, so nothing is cut on floor
     1. The room's building has floor volumes of its own at 192 and 384 (buildings.py makes one for each floor box),
     and the cursor does not follow them. [F-128](../findings-register.md).
6. **How far a grenade breaks a made floor: passed, only near the blast.** A soldier stood on the long floor at
   (-1009, -1297), z 264. A grenade on its west end burst at (-1647, -1302). Afterwards the three west tiles had no
   floor (-1681 and -1585 read 128, -1489 the ground at 64; their centres up to 158 from the blast) and every tile
   from -1393 east was still floor (258; 254 from the blast and beyond). The soldier stayed on the slab, and the side
   picture shows the slab ending short of its west end. So the room's whole floor going in the first pass was the
   blast's reach covering the whole room, as the game's rule has it.
   - Not looked into: the two west tiles read 128, a surface 64 over the ground, after the break.
7. **Save and load: passed.** A quicksave after the break and its load: every soldier stood where he had, and the
   long floor read the same tile by tile.

### Run E, first pass (18 November 2026)

Played unattended in the lab copy (the game-test skill). Pictures are in `<lab>\hidden-runs\exp76-runE`.

1. **Load: passed.** No crash; the slabs appear only in the routine "Cooking Convex" lines.
2. **The look: passed** (still pictures). The roof sits flush on the room, its gravel top lit as the lot is, with no
   holes; the lone roof stands whole in the air. The room's made walls look nearly black from outside (a side
   observation, not judged).
3. **Under the floor: the walk passed, the cut-away failed.** A soldier walked in through the doorway and across the
   room on the ground. With soldiers inside on the camera's floor 0, the walls were cut to their lower storey, but the
   made floor stayed drawn as a lid over the room and the roof over it. The look up at the hole was not seen.
   - Cause: the Room with a roof tool made the building's floors break at 208 and 400, and the slabs' boxes are 192
     to 194 and 382 to 386. The game lists a piece in a floor only when its bottom is more than 20 under the floor's
     top, so the slabs were in no floor. URB_Bar breaks at 192 and 384 over its ground, with a roof floor; its
     upstairs floor is listed on floor 1, its roof on floor 2. Fixed (0ef5535): the tool's floors now match, and the
     compiler warns of a made slab in no floor of its building.
4. **On the floor: passed.** A soldier put on the made floor stood at about 264 (its top 194) and walked across it.
   Aimed at the hole's tile, the cursor fell to the ground; sent there, he dropped through the hole to the ground,
   so the hole is no floor.
5. **The roof takes no clicks: failed**, by the same cause as check 3: inside the room the cursor's floor 0 landed
   on the made floor and floor 1 on the roof (both drawn, so both take clicks).
6. **A break in the floor: the whole floor went.**
   - A grenade on (-1393, -1009) on the made floor: every one of the room's twelve tiles lost floor (the cursor read
     the ground on all of them; the quicksave's tiles agree: no floor at that level in the room), and no slab was left
     drawn. The roof stayed whole and still floor, with a soldier on it; the wall by the blast broke at its top.
   - The game damages every column of a fracturing piece within the blast's radius of its centre, each listed
     fragment losing the full damage ([frac-neighbours.md](../native/frac-neighbours.md), ApplyDamage). From the
     blast, even the room's farthest floor tile is about 280 units off, so the whole floor was probably within reach;
     the second pass's long floor shows whether a made floor breaks only within it.
   - T-47: a soldier standing on the made floor two tiles from the blast lost his floor. The game logged "Extended
     Base tile is not a floor tile" and "Debugged invalid location", put him on the ground below, and he was still in
     play, with his moves, on the next turn.
7. **Save and load: not done** (the run was paused): the quicksave was written, the load not made.
