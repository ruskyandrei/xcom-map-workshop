# EXP-80: the cursor's own floors over made floors and roofs (custom geometry plan, M5b)

Date: 18 November 2026. Status: **played** (runs G and H: the cursor's floors in the room passed; out of buildings the mouse's own rule decides, F-135). Part of the custom geometry plan's stage M5b (branch
`fracturing-wall-poc`): the fix for [F-128](../findings-register.md). Played unattended in the lab copy (the hidden
game, the game-test skill), checking only what is new.

## What is new

The Build gives each made floor and roof cursor floors of its own (tools/bake/made_cursors.py). URB_Bar's four
map-wide cursor volumes (breaking at 210, 402 and 594) are taken out and stand again round the made slabs. Over the
room the floors break at 194 and 386, the made floor's and the roof's tops (run G); after run G, at 190 and 380, 2
under their undersides (run H). In EXP-76 run E the cursor of floor 0 landed on the made floor and floor 1 drew the
room whole.

## The project

EXP-76's project, `EXP-76 floors and roofs` ([exp76_project.py](../../tools/editor/examples/exp76_project.py)),
built again with the lighting baked: its map `EXP76FloorsAndRoofs` now carries 48 cursor volumes, 12 of them over the
made slabs. Game tiles count from the map's corner (-2785, -1921, -1), so tile centres are at x -2737 + 96 i,
y -1873 + 96 j. ShowCursorLoc reads a floor 64 over its top (a unit's height): the ground 64, the made floor 258,
the roof 450, the bar's upper floor 274.

| Piece | Where | Cursor floors over it after the Build |
| --- | --- | --- |
| Room | x -1728 to -1344, y -1056 to -768; doorway tile (-1585, -1009); a hole in its floor at tile (-1489, -913) | run G: 0 to 194, 194 to 386, 386 to 594, 594 to 768; run H: 0 to 190, 190 to 380, 380 to 594, 594 to 768 |
| Long floor | x -1728 to -768, y -1440 to -1152, top 194, nothing under it | run G: 0 to 194, 194 to 402, ...; run H: 0 to 190, 190 to 402, ... |
| Lone roof | x -1152 to -960, y -1056 to -864, top 386, nothing under it | run G: 0 to 210, 210 to 386, 386 to 594, ...; run H: 0 to 210, 210 to 380, 380 to 594, ... |
| Everywhere else | | the map's: 0 to 210, 210 to 402, 402 to 594, 594 to 768 |

## Run (hidden game)

1. **Load**: the battle starts, with no crash.
2. **The cursor in the room** at (-1681, -817) and (-1393, -913), from a soldier outside it:
   - floor 0 reads 64 (the ground), not 258;
   - floor 1 reads 258 (the made floor);
   - floor 2 reads 450 (the roof).
3. **Cut away**: a soldier walks in through the doorway onto (-1681, -817), on the ground. Camera floor 0: neither
   the made floor nor the roof drawn (as in run E). Floor up once: the made floor drawn and the roof not. Floor up
   again: both drawn.
4. **The map's floors elsewhere are kept**: on the bar's upper floor strip at tile (-1105, 143) (the export's floor
   tiles: `XComFracLevelActor_17`, top 210), floor 1 reads 274; on open
   ground west of the room at (-1873, -913), floor 0 reads about 64.
5. **Across the room's edge**: the cursor on floor 1 at (-1393, -913) (258), then on (-1297, -913) just east of the
   room, then back: what each reads, and nothing sticks.
6. **The long floor**: at (-1009, -1297), floor 0 reads 64 (the ground under it) and floor 1 reads 258.

Passed: checks 2, 3 and 6 read as written, check 4 as the map was, check 5 back to 258.

Run H (after run G's fix, the floors 2 under the slabs' undersides) adds:

7. **The lone roof**: at (-1009, -913), floor 1 reads 64 (the roof is now on floor 2) and floor 2 reads 450.
8. **Plain URB_Bar**: the bar's upper floor strip at (-1105, 143), floor 1, for check 4's reading.

## Result

Played unattended in the lab copy with saving on (the game-test skill). Pictures are in `<lab>\hidden-runs\exp80-runG`,
`exp80-runH` and `exp80-runH-bar`.

### Run G (18 November 2026, the floors breaking at the slabs' tops)

1. **Load: passed.**
2. **The cursor in the room: passed.** At (-1681, -817) and (-1393, -913) floors 0, 1 and 2 read 64, 258 and 450 (in
   run E floor 0 had read the made floor and floor 1 the roof).
3. **Cut away: floor 0 passed; floor 1 as the game's rule has it.**
   - With a soldier on the ground in the room, camera floor 0, neither the made floor nor the roof is drawn.
   - Camera floor 1 with the cursor elsewhere (the hidden game's still mouse sits at a corner of the screen): the room
     is drawn whole, roof and all, as in run E.
   - Camera floor 1 with the cursor held on a room tile: the roof is cut away. Whether the made floor is drawn could
     not be told from the straight-down pictures the hidden game can take with the cursor held (the soldier under it
     was drawn in full, the room's inside dark).
4. **The map's floors elsewhere: open ground passed (64); the bar's upper floor strip read 80**, aimed from 7.4 and
   11.7 tiles (run H: 274 from 4 tiles, as on plain URB_Bar).
5. **Across the room's edge: passed** (258, 64, 258: nothing sticks).
6. **The long floor: failed.** Floor 0 read 258, the long floor's top, where the ground (64) was meant; floor 1 258.

### Run H (19 November 2026, the floors 2 under the slabs' undersides)

1. **Load: passed.**
2. **The long floor: floor 0 still reads 258** (floor 1 258). The floors under it have nothing to do with it: out of
   every building the mouse takes the first walkable top on its ray at once, whatever the storey, as it does the
   game's overpasses and canopies ([F-135](../findings-register.md)).
3. **The cursor in the room: passed again**, 64, 258 and 450 at both tiles.
4. **The lone roof: floor 1 passed (64); floor 2 read 64 too**, the ground: its top is no walkable floor as far as the
   pick shows (F-135).
5. **Cut away with a soldier on the made floor: unclear.** He was put on it (standing at 264, its top 194), but the
   pictures could not show the slab: the hidden game holds the cursor only under its own straight-down camera, and a
   low camera moves the cursor off the room. By the game's rule the made floor is drawn on floor 1 with the cursor in
   the room: the cursor's floor-1 volume there ends at 380, so the room's building shows its floors 0 and 1
   (`ShowFloor(2)`; [building-cutaway.md](../native/building-cutaway.md)). With the cursor elsewhere on floor 1 the
   room is drawn whole because every building is cut by the cursor volume at the cursor's place, the map's there
   (its top 402, less 16: 386), and the room's roof floor starts at 384 (F-128).
6. **The bar's upper floor strip: 274** from 4 tiles, the strip's top (210) under the cursor.
8. **Plain URB_Bar: 274** at the same tile, so the build keeps the map's own floors there; run G's 80 was the aim's
   distance.

So the made floors' own cursor floors work where the game's cursor floors decide, in a building: in the room each
storey picks the ground, the made floor and the roof. A made floor or roof in no building is picked on every storey,
as the game's own outdoor tops are; the compiler now warns of it (`slab-outdoors`).
