# EXP-98: a map's fog and grade changed by the Build, in the game

Date: 27 November 2026. Status: **played: every check passed** ([F-173](../findings-register.md),
[F-174](../findings-register.md)). Played unattended in the lab copy (the game-test skill), one pass of each check.

## The questions

The game-likeness plan's stage C5a proves the Build's half of the map's atmosphere before any control is built: the
risk of C5 is in the Build and the game.

1. Does a map whose WorldInfo's height fog (`XComHeightFog`) the Build wrote again, its members over those the map
   saves, show that fog in the game?
2. Does one whose post-process settings (`DefaultPostProcessSettings`) it wrote again show that grade?
3. Do both hold with a Long War patch level streamed in?

## The maps

URB_Bar built quick by [exp98_project.py](../../tools/editor/examples/exp98_project.py) from an export 43 of Bar in a
scratch cache, twice under the same name URB_Bar_Atmos_98a7:

- the fog's (`--look fog`): density 0.6 (Bar's own 0.015), height 600, falloff 1, the most it covers 0.95, both colours
  a strong red (0.85, 0.08, 0.06). By the editor's sums some 40% of a near floor and 80% of the far map are hidden at
  the game's camera;
- the grade's (`--look grade`): Scene_Colorize 0.6, 1.4, 0.6, and Bar's blue lift in the shadows taken out.

Both read back offline with the export's reader (tools/viewer/atmosphere.py): the fog's seven changed members (the
density and the height added; the map saved neither), the grade's two with their override flags, everything else as
Bar's. Both stream LWR's `patch_bar` and `patch_hide_randomized_objects`, as Bar's own records do. Each staged in the
lab copy with `lab_install.install(..., game=<the lab copy>)`; the folder Steam ran held the user's LWR v3 copy, never
touched. LWR 2.06 in the lab copy.

## Runs

Each started hidden with `--map URB_Bar_Atmos_98a7` and the test squad, the interface hidden and the fog of war
lifted, then shot from the three likeness cameras of URB_Bar (`likeness.py steps URB_Bar`: ub-1 over the bar and the
street, ub-2 over the kitchen and the road, ub-3 over the car park), each set beside the base map's shot from the same
camera taken earlier in the same copy.

1. **The red fog.**
   - The map loads: turn 1, the squad at a landing zone, under a red haze. Passed.
   - The fog shows: in all three every surface is washed strongly red against the base map's blue night; the near
     part of each picture (the bar's floor, the pavement) still shows its detail through it, the far part (the street
     and the car park beyond the lamp posts) is near flat red. The frames' mean colours went from (45, 35, 65),
     (43, 38, 72) and (45, 43, 80) to (150, 32, 52), (147, 31, 55) and (149, 35, 63); the far quarter is some 25
     redder than the near. Passed.
   - The patch level: the log streams `patch_bar` and `patch_hide_randomized_objects` with the map's intro copy as
     the map loads. Passed.
2. **The green grade.**
   - The map loads: turn 1. Passed.
   - The grade shows: in all three the whole picture is clearly green against the base's blue: the bar's wood
     yellow-green, the pavements and roads dark green, Bar's blue lift in the shadows gone, strong colours still
     told apart (the blue police car, the red carpets). Mean colours (27, 50, 25), (26, 54, 29) and (27, 60, 33). The
     interface is green too: the game grades the whole frame. Passed.

## The editor's view of the same members

The editor's Game look with the same members put over URB_Bar's own (`likeness.py editor --atmosphere`), from the
same three cameras, against the game's shots of the two Builds:

- the red fog: mean colours (155, 39, 64), (152, 37, 68) and (155, 44, 76) against the game's (150, 32, 52), (147, 31,
  55) and (149, 35, 63), the far quarter redder than the near by about 20 in both;
- the green grade: (32, 64, 30), (28, 61, 33) and (33, 74, 38) against (27, 50, 25), (26, 54, 29) and (27, 60, 33):
  the editor's a little brighter, as its light is without them (the map's baked light is track B).

One difference was the editor's: a figure on Bar's car park drawn with an unlit material stayed dark under the red
where the game's faded into it. Unlit materials now take the fog, and see-through ones take it by their blend
(F-174); the same shot again shows it red.

## What it shows

- The Build's half of a map's atmosphere works: the game takes the fog and the grade from the map's WorldInfo as the
  Build writes them, with the members the map saved kept and the new ones added, and a Long War patch level streamed
  in changes nothing of it. Stage C5b (the controls) can build on it.
- The editor's sums for the fog and the grade give the game's colours for the same members, so what the Game look
  shows of a project's atmosphere is what the game will show.
