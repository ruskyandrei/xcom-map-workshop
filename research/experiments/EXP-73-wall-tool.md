# EXP-73: walls drawn with the wall tool (custom geometry plan, M1, run A)

Date: 18 November 2026. Status: **run A passed**, bar two checks left open (below). The custom geometry plan's stage M1 (branch `fracturing-wall-poc`):
walls are drawn in the editor on any map (the wall tool), the donor brought from URB_Bar where the map hasn't it.
This run is what the offline checks cannot answer, played unattended in the lab copy (the hidden game, the game-test
skill): only what is new since EXP-67.

## What is new

- A made wall on a map that isn't the Bar: its donor staged from URB_Bar (offline: `StagedDonor` in
  [test_frac_walls.py](../../tools/bake/tests/test_frac_walls.py) builds two on URB_PoliceStation).
- A made wall turned a quarter: its columns along y.
- A window: an opening off the floor (sill 72, top 168), which the game's sweeps should make low cover with sight
  through it and no walking (the compiler's and the panel's words, by `research/native/cover-build.md`).
- A wall with an empty slot: an opening over its whole lower storey leaves the lower faces' sections with no
  triangles; the game has not loaded a section of none before.
- A made wall on an upper level (a roof).
- A made wall's height free of its donor's storeys (it stands on the floor at 14.5 here, which the donor's lattice
  from the Bar would put 46 lower).

## The project

`EXP-73 wall tool` (URB_PoliceStation, [exp73_project.py](../../tools/editor/examples/exp73_project.py), in a test
server's scratch store; the map `EXP73WallTool`, built with the lighting baked). Four copies of URB_Bar's inside wall
(`XComDecoFracLevelActor_17`), as the wall tool makes them (the piece at the wall's start, on a tile corner, standing
on the floor). Game tiles are counted from the map's corner (-1729, -2497, -49): tile centres at x -1681 + 96 i,
y -2449 + 96 j.

| Wall | Where | Openings | Tiles beside it (centres) |
| --- | --- | --- | --- |
| W1 | along x, y -2112, x -1440 to -1056, z 14.5 | window in its 2nd tile (x -1344 to -1248), doorway in its 3rd (-1248 to -1152) | south row y -2161, north row y -2065; its tiles x -1393 (solid), -1297 (window), -1201 (doorway), -1105 (solid) |
| W2 | along y (a quarter turn), x -1152, y -2400 to -2208 | window in its 1st tile (y -2400 to -2304) | west column x -1201, east x -1105; its tiles y -2353 (window), -2257 (solid) |
| W3 | along x, y -2400, x -1440 to -1344, one tile | open over its whole lower storey (to 200) | south y -2449, north y -2353; x -1393 |
| W4 | on the roof, along x, y -1248, x -384 to -96, z 466 | doorway in its middle tile (x -288 to -192) | south y -1297, north y -1201; x -337, -241 (doorway), -145 |

The compiler warns of the three doorways (no door in them: a unit there has cover toward its sides); that is the
game's rule and known (F-116), not checked again.

## Run A (hidden game)

Checks, each passed, failed or unclear:
1. **Load**: the battle starts on the variant; no crash, no mesh error in `Launch.log` (W3's empty sections).
2. **Look**: a shot of each wall where it stands (W1 from both sides): drawn whole, lit, the window and doorways open.
3. **Window** (W1): a soldier on (-1297, -2161) has low cover toward the wall (north); an alien dropped on
   (-1297, -1969) is seen and can be shot at through the window; nobody walks through it.
4. **Doorway** (W1): a soldier walks from (-1201, -2161) to (-1201, -2065) through it. A soldier on (-1393, -2161) has
   high cover toward the wall.
5. **Quarter turn** (W2): a soldier on (-1201, -2257) has high cover toward the wall (east); on (-1201, -2353), low
   cover (its window).
6. **Empty slot** (W3): it is drawn (the upper storey over the open lower one); a soldier walks from (-1393, -2449) to
   (-1393, -2353) under it.
7. **Upper level** (W4): a soldier on the roof at (-337, -1297) has high cover toward the wall; walks through the
   doorway to (-241, -1201).
8. **Break**: a grenade against W1 and one against W4: holes, rubble, the destroyed material, nothing left floating.
9. **Save**: a quicksave after the breaks, for the tiles round the walls (read with `save_tiles.py` afterwards).

## Result

**Run A** (18 November 2026, the hidden game on `EXP73WallTool`, the test squad, an Opus agent by the game-test skill;
its out folder `<lab>/hidden-runs/exp73-runA`: report, shots, Launch.log, the quicksave). Cover values are LWR's: high
50, low 30.

1. **Load: passed.** The battle started; the four walls (`XComMapEdGeo.FracWall_*`) appear in `Launch.log` only in the
   routine convex-cooking lines every fracturing piece of the map has; no error names them. W3's empty sections load.
2. **Look: passed for W1 and W2; W3 and W4 partly.** W1 from both sides drawn whole and lit, its window a waist-high
   sill with the opening above, its doorway open to the floor; W2 drawn and lit, its window a notch in its end tile.
   W3's upper block drawn and lit; no shot shows the space under it (check 6 walked under it). W4 was not seen from
   the default camera or from the north (the roof's cut-away or the station's parapet: not worked out); after the
   blast it shows from the south.
3. **Window (W1): cover, sight and shot passed; walking failed as written, and that is the game's rule.** On
   (-1297, -2161): low cover north (30), its flags with the ClimbOver bit; the Sectoid on (-1297, -1969) targeted
   through the window at 100% and killed. On turn 2 a soldier moved from (-1297, -2161) to (-1297, -2065) through the
   window: a climb, as through the game's windows (F-126). The panel's and compiler's words were wrong, not the wall.
4. **Doorway (W1): passed.** A soldier walked from (-1201, -2161) to (-1201, -2065); on (-1393, -2161) high cover north
   (50).
5. **Quarter turn (W2): passed.** On (-1201, -2257) high cover east (50); on (-1201, -2353) low cover east (30) with
   ClimbOver (its window).
6. **Empty slot (W3): passed.** A soldier walked from (-1393, -2449) to (-1393, -2353) under its upper storey; no error.
7. **Upper level (W4): passed.** On the roof (-337, -1297) high cover north (50); the move to (-241, -1201) went one
   diagonal step at the doorway's west edge (a straight walk through the doorway was not tried).
8. **Break: holes, fire, rubble; whether anything floats is open.** Grenades at (-337, -1297) and (-1393, -2161): those
   tiles read no cover afterwards, fire on both walls, rubble on the roof, the rest of each wall standing. Soldiers
   stood in front of W1's first tile in the after-shots, so whether its upper storey was left over a hole can't be
   told; the quicksave's tiles (save_tiles.py) show W1's first tile still occupied above the ground (79 to 207), so
   its lower storey wasn't holed through there. No crash, no error after either blast.
9. **Save: passed.** A quicksave after the breaks wrote and the game ran on.

Left open, for later runs: a straight walk through W4's doorway, and a break that holes a made wall's lower storey
right through under its upper one (does the upper storey fall: run C's corner grenade looks at it). W4's hiding from
the default camera goes to run C (walls in and on buildings).
