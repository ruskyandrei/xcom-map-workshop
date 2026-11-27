# EXP-99: the time of day built without a bake, in the game

Date: 27 November 2026. Status: **played: every check passed** ([F-200](../findings-register.md)). Played unattended
in the lab copy (the game-test skill), one pass of each check and one second take.

## The questions

The game-likeness plan's stage T-S3 (the sun plan's S3) shows in the game what stage T-S2's Build makes of a project's
time of day, before the baker traces the sun's shadows again (T-S4):

1. Does a map whose sun or moon and sky light the Build set in place show the new light: on the map, on the soldiers,
   through a save and load?
2. With the light turned, does the game take the new direction from the light actor's `Rotation` alone (the
   component saves no `CachedParentToWorld`, F-200)?
3. How wrong do the map's old baked shadows and bounce look under it?

## The maps

URB_Bar built quick by [exp99_project.py](../../tools/editor/examples/exp99_project.py) from an export 45 of Bar in a
scratch cache, read from the lab copy, twice under the same name URB_Bar_Day_99a1:

- **kept**: the time bar at 10:00 with the light keeping the moon's direction (80.7 degrees up): the moon's (66, 69,
  136) at 1.1 made (255, 250, 180) at 1.0, the sky light made the curve's 10:00 sky, the record's time Day;
- **turned**: 13:00, the light (255, 245, 215) at 1.1 at 56 degrees up on the same side (the light travels toward
  game -X, +Y).

Each staged in the lab copy with `lab_install.install(..., game=<the lab copy>)`; the folder Steam ran held the user's
LWR v3 copy, never touched. LWR 2.06 in the lab copy. Each started hidden with `--map URB_Bar_Day_99a1` and the test
squad, the kept one with saving on; the three likeness cameras of URB_Bar (`likeness.py steps URB_Bar`) set beside the
game's shots of plain Bar from the same cameras, taken earlier in the same copy.

## Runs

1. **Kept.**
   - The map loads: turn 1, the squad on the south car park. The game holds the Build's values: `getall` reads the
     light's Rotation, colour (255, 250, 180) at 1.0 and the sky light (125, 129, 108) at 0.5. Passed.
   - Day light: in all three frames the blue night is gone; lit pavement, roads and cars read a pale warm white. Mean
     colours (45, 35, 65), (43, 39, 72), (45, 43, 81) for plain Bar against (64, 59, 62), (64, 64, 68), (76, 79, 79);
     a lit pavement went from (84, 73, 114) to (137, 136, 121). Passed.
   - The sky light on the soldiers: close shots show natural colours on the lit side (skin, the flags' whites, an
     olive pack) and a dark grey with a faint blue on the shaded side (30, 34, 48), nowhere deep blue. Passed.
   - Save and load: a quicksave, then the save loaded ("Tactical Skirmish (Alien Abduction Site), 1 turn in"); the
     first camera's frame before and after is the same (mean 64.3, 58.9, 62.0 against 64.2, 58.8, 62.1), the light's
     values unchanged. Passed.
   - The shade (noted): the baked shade is dark with a weak cool tint, its blue some 10 to 13 above red and green:
     beside the bar's wall (26, 28, 39) against plain Bar's (24, 18, 44), the kitchen floor (36, 37, 49) against
     (36, 35, 60). It reads as cool grey, not night.
2. **Turned.**
   - The map loads: turn 1; the game reads the Rotation (-10194, 24213) and the colour (255, 245, 215) at 1.1. Passed.
   - The new direction on moving things: seen from straight above (the camera's axes measured by moving the view
     along each), all five soldiers' shadows fall the same way, toward -X, +Y; under the kept moon they fell each its
     own way. The shadow's length tells the lights apart less well than expected: the units' composite shadows are
     long under either light (about 0.62 and 0.73 of a soldier's height; their light environment's MinShadowAngle is
     80). The second take divided the same cameras' frames of the two runs: the vehicles' faces toward the light are
     brighter turned (a blue car's side 1.35 times, a white SUV's 1.29, a box truck's rear 1.38) while a taxi's roof
     (0.99) and the static pavement (0.96) stay even. Passed: moving things take the direction from the Rotation.
   - The old shadows: the bar's baked shadow is still a band about a tile wide straight under its wall and awning,
     and the box truck keeps only a thin dark rim, beside the soldiers' long shadows in the same frames: the static
     shadows are the moon's, in direction and length. As expected before T-S4.
   - The first camera's frame, for the record: mean (73.7, 63.1, 53.9), warmer than the kept run's.

## What else was seen

- The lab copy's test slot record kept the base map's `TimeOfDay` (Night), not the package's Day: the lab's staging
  (deploy_fixture's slot record) made the slot's record from the base map's own. The save was labelled 8:00 PM; the
  light showed no difference. The editor's own Play in game, installs and map packs carry the package's records (T-S2's
  tests). Fixed after the run: the lab's staging gives the slot's record the package's time of day.
- Bar's wood floor's blue sheen of the night map fades in both day Builds (its blue 48.9 to 38.1 and 32.4, its red
  near 60 to 69): the sun does not light it, as F-184 has it, and the sheen follows something the time of day changes
  (F-184's open part).
- The third camera's box truck is another mesh in the turned run: LWR's randomized objects.

## What it settles

The Build's time of day without a bake works in the game: colours, the sky light, the records' time, the direction on
moving things, through a save and load. What a turned light leaves wrong is the baked shadows (and a faint cool
bounce), which T-S4's baker traces again (EXP-100).
