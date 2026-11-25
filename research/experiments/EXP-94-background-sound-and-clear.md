# EXP-94: a cleared map given another map's background sound, in the game

Date: 22 November 2026. Status: **played: both runs passed: the cleared Bar plays DeepWoods' forest bed everywhere
and after a load, its two rat triggers' events stay off, a quicksave loads; with the background sound set to none it
loads and plays no bed** ([F-159](../findings-register.md), [F-160](../findings-register.md)). Played unattended in the lab copy (the
game-test skill), one pass of each check.

## The questions

1. Does a map whose level-loaded sound the Build pointed at a bed brought from another map (its cue, looping node
   and wave copied in as assets: F-160) load and play that bed, also after a save and a load?
2. Are a cleared map's touch triggers out, their events off (F-159), in the game?
3. Does a map whose background sound is set to none load and stay quiet?

## The maps

URB_Bar cleared by [clear_bar_project.py](../../tools/editor/examples/clear_bar_project.py) (every piece deleted as
the editor's Clear map deletes them, `cleared`, no `clearKeepsTriggers`), built quick from an export 39 of Bar in a
scratch cache, twice under the same name URB_Bar_Cleared_c1ea:

- run 1's: `--sound SoundAmbience-NorthAmerica.ForestAmbienceCue`: the transplant stage brought the cue from
  CLrgScout_DeepWoods (3 objects, 557 KB), the map's `SeqAct_PlaySound_0` points at it (read back offline);
- run 2's: `--sound none`: `SeqAct_PlaySound_0` with no cue.

Both: no trigger volume or sight point on the level's list, `SeqEvent_Touch_0` and `_1` (Bar's rats) `bEnabled`
false (read back offline). Each staged in the lab copy with `lab_install.install(..., game=<the lab copy>)`; the
folder Steam ran held a campaign copy, whose game was open throughout and never touched. Started hidden
with `--map`, the test squad and `--no-aliens` (run 1 with `--saving`). LWR 2.06 in the lab copy.

## Runs

1. **The forest bed** (run 1).
   - The map loads: turn 1, six soldiers by the Skyranger at z 176 (x 527 to 911, y -1489 to -1201). Passed.
   - The bed plays: `listen` at a soldier's place (911, -1297, 176) and 37 tiles away (-1500, 1400, 176), each from
     400 units: both lists hold `SoundAmbience-NorthAmerica.ForestAmbience` at 0.60, owned by the tactical sound
     manager, as a bed played for the player is; neither holds Bar's `LightWindAndTraffic` or `FlyingPaperLoop`
     (besides: the combat soundtrack, and the Skyranger's idle at the landing). Passed.
   - The rats' triggers: `SeqEvent_Touch_0` and `_1` read `bEnabled` False and `TriggerCount` 0. Their volumes
     still exist as objects (`getall TriggerVolume Location` prints both, at their places): taken off the level's
     list, not out of the package. Passed.
   - A quicksave and its load: F10 saved; Load Game listed the quicksave first; "Save File Loaded: ... 1 turn in",
     the six soldiers where they were, and `listen` at the first place again lists ForestAmbience at 0.60. Passed.
   - Seen besides, not checked further: on the load the log says "Extended Base tile is not a floor tile" for each
     soldier (the cleared map has no floor under the landing; they kept their places), and the Skyranger is not
     drawn after the load though its idle sound still lists.
2. **No background sound** (run 2).
   - The map loads: turn 1, six soldiers at z 176 (another of the map's starts: x -2449 to -2161, y -49 to 335).
     Passed.
   - No bed plays: `getall SeqAct_PlaySound PlaySound` reads `SeqAct_PlaySound_0.PlaySound = None`; `listen` at a
     soldier's place and 35 tiles away lists the combat soundtrack and, by the Skyranger, its idle, and no
     `SoundAmbience` wave. Passed.

## What it shows

- A sound bed brought from another map as assets (its cue, node and wave, under their own package) loads with the
  map, plays for the player across the map at the volume a bed plays at, and plays again after a load: the editor
  can give any map with a background sound any of the 26 beds.
- A cleared map's touch triggers stay out in the game: their events read off, and nothing set them off.
- A map's level-loaded sound with no cue plays nothing and harms nothing: "none" is a background sound the editor can
  offer.
