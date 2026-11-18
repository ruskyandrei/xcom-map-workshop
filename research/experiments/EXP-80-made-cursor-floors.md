# EXP-80: the cursor's own floors over made floors and roofs (custom geometry plan, M5b)

Date: 18 November 2026. Status: **prepared**. Part of the custom geometry plan's stage M5b (branch
`fracturing-wall-poc`): the fix for [F-128](../findings-register.md). Played unattended in the lab copy (the hidden
game, the game-test skill), checking only what is new.

## What is new

The Build gives each made floor and roof cursor floors of its own (tools/bake/made_cursors.py). URB_Bar's four
map-wide cursor volumes (breaking at 210, 402 and 594) are taken out and stand again round the made slabs. Over the
room the floors break at 194 and 386, the made floor's and the roof's tops. In EXP-76 run E the cursor of floor 0
landed on the made floor and floor 1 drew the room whole.

## The project

EXP-76's project, `EXP-76 floors and roofs` ([exp76_project.py](../../tools/editor/examples/exp76_project.py)),
built again with the lighting baked: its map `EXP76FloorsAndRoofs` now carries 48 cursor volumes, 12 of them over the
made slabs. Game tiles count from the map's corner (-2785, -1921, -1), so tile centres are at x -2737 + 96 i,
y -1873 + 96 j. ShowCursorLoc reads a floor 64 over its top (a unit's height): the ground 64, the made floor 258,
the roof 450, the bar's upper floor 274.

| Piece | Where | Cursor floors over it after the Build |
| --- | --- | --- |
| Room | x -1728 to -1344, y -1056 to -768; doorway tile (-1585, -1009); a hole in its floor at tile (-1489, -913) | 0 to 194, 194 to 386, 386 to 594, 594 to 768 |
| Long floor | x -1728 to -768, y -1440 to -1152, top 194, nothing under it | 0 to 194, 194 to 402, ... |
| Lone roof | x -1152 to -960, y -1056 to -864, top 386, nothing under it | 0 to 210, 210 to 386, 386 to 594, ... |
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
