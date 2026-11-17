# EXP-70: effect and sound values

Date: 17 November 2026. The effects and sounds plan's game check after stage FX5 (its EXP-E, section 7.2), in one
project on URB_Bar, under Long War (the lab copy). Plain EW is not played in this run. An effect's size, starting
state and particle parameters and a sound's reach, volume, pitch and starting state wait for this run: their families
(`effect-values`, `sound-values`) are off in the compiler, and this project's build lifts them (`--family`).

## What the offline checks settled

Read back from the built map (`URB_Bar_X70`, a quick build: values change no baked light) with a fresh reader, as
export 28 reads a map, so the run doesn't need to show them:
- each value is on the actor's own exports, as set: the beam's two parameters (its Brightness kept a number where its
  system reads a vector, as the map saved it), the steam's and the vapour's DrawScale multiplied (the vapour's uneven
  DrawScale3D, 0.6 by 1 by 1, kept), the big steam's component saving `bAutoActivate` false, each copy's own
  parameters (the second copy's Spawn a new entry at the end of its list), the sounds' nodes and `bAutoPlay`;
- what the project doesn't set is as the map has it: the beam's twin, the vapour's neighbours, the third copy, the
  steam's other entries byte for byte (a value set to what it is already leaves the bytes as they were: the writer's
  tests);
- a copy's values are on the copy: its source and the other copies keep theirs.

What only the game can show: what each value does when it plays. Whether a number set where the system reads a
vector brightens the beam (the game's maps do it on 18% of their saved values; plan 2.2), whether a new parameter
entry is read, whether an effect saved to start off stays off with nothing to start it, whether a simple sound saved
not to play stays silent (its class plays by default and has no switch of its own), and how pitch, volume and reach
sound.

## The project

`EXP-70 effect and sound values` (URB_Bar, [exp70_project.py](../../tools/editor/examples/exp70_project.py), in the
editor's project store), a quick build. It compiles with two warnings, both meant: the big steam and the car's idle
start off with nothing in the map's script to switch them on. Marked shots: `EXP-70-carpark.png`, `EXP-70-close.png`
([EXP-70-shots.json](EXP-70-shots.json)).

| No. | What | Set | The prediction |
| --- | --- | --- | --- |
| 1 | a headlight beam (Emitter_24, a parked car's pair) | colour red (1.5, 0.1, 0.1), Brightness 0.5 to 2 (a number where its system reads a vector) | red, and brighter than its twin (Emitter_46) beside it, which is as it was |
| 2 | steam (Emitter_16, drawn at half size) | three times its size | a wider, taller plume where it was |
| 3 | alien vapour (Emitter_21, drawn at 0.6 by 0.6, 1, 1) | three times its size | larger than its four neighbours, the same shape |
| 4 | the big steam (Emitter_3) | starts off | no steam there, the whole mission |
| 5 | a copy of steam 2 | colour green (0.2, 1.5, 0.2) | green steam at half size |
| 6 | a copy of steam 2 | Spawn 4 (a parameter the steam doesn't save) | denser steam than 7 |
| 7 | a copy of steam 2 | nothing | steam as the map has it, at half size |
| 8 | the pickup's idle (AmbientSoundSimple_0) | pitch 1.6, heard fully within 600, fading out by 2,000 (it was 300 to 750) | higher, heard from further off |
| 9 | a car's idle (AmbientSoundSimple_3, CarTaxiIdle) | not to play from the start | silent |
| 10 | a copy of the pickup's idle, the car park's far corner | pitch 0.6, volume 0.5 | lower and quieter, heard within 750 |

## Run 1

What the run adds (Play in game from the editor, on the project):
1. **The effects (1 to 7):** each as predicted? In particular: is beam 1 brighter than its twin, or only red (a number
   where a vector is read may be ignored)? Is copy 6 denser than copy 7? Is anything missing, doubled or drawn as a
   grey or chequered square?
2. **The sounds (8 to 10):** with the camera over each (and, if one seems silent, with a soldier beside it: the
   listener question EXP-68 and EXP-69 left open): 8 higher and heard further off than before, 9 silent, 10 low and
   quiet.
3. **Save and reload** once: all as before (the big steam still off, the car's idle still silent).
4. Anything odd.

## Result

**Run 1** (17 November 2026, unattended: the game-test skill's hidden game in the lab copy, `URB_Bar_X70` installed
as Play in game installs it, opened by name; the same camera places on the unedited URB_Bar for comparison). Every
value the project set is what the game loaded (`getall`), and what could be seen or heard behaved as predicted;
three things could not be judged by eye.

| No. | Result |
| --- | --- |
| 1 | **Passed for the colour.** The beam's cone on the ground is saturated red where the unedited map's is warm white, the same size; the twin's warm white shows only as a haze at the red cone's edge. Brighter: **not judged** (by eye a colour change and a brightness change can't be told apart). The game holds Brightness 2.0 as a number (`PSPT_Scalar`) and Color (1.5, 0.1, 0.1). |
| 2 | **Larger, yes; three times not measurable.** A grey wisp about a tile and a half across where the unedited map shows none to the eye: the steam is very dim at night (its Brightness 0.05). The game holds DrawScale 1.5 (0.5 in the unedited map). |
| 3 | **Passed.** A wide green cloud over about two tiles on its side of the alien power source, much larger than its neighbours' wisps, the same soft shape; a small puff in the unedited map. DrawScale 1.8 with DrawScale3D (0.6, 1, 1). |
| 4 | **Passed, by the game's state.** The plume is too small and dim to show in either map's pictures; the game holds its component `bAutoActivate = False` and `bIsActive = False` (`True` in the unedited map). |
| 5 | **Passed.** A small, faint green wisp on the pavement; the game holds its Color (0.2, 1.5, 0.2). |
| 6, 7 | **Loaded; denser not judged.** All three copies are active, and copy 6's list has its fourth entry, Spawn 4.0, so the new entry loads; but copies 6 and 7, at half size and Brightness 0.05, can't be seen at night. |
| 8 | **Passed.** The game lists it at 0.60 from 200 and 400 units, 0.43 from 1,000 and 0.30 from 1,300: full volume inside 600 and a straight fade to 2,000 (0.6 × (1 − 400/1,400) = 0.43), so heard far beyond its old 750. Pitch 1.6 read from `getall` only (the game's list has no pitch). |
| 9 | **Passed.** Not listed from 200 or 100 units; the game holds `bAutoPlay = False`. A simple sound saved not to play stays silent. |
| 10 | **Passed.** 0.30 from 200 units, half of 8's 0.60 there, and 0.17 from 500; pitch 0.6, volume 0.5. |

- The game hears from the camera (the game-test skill's sound checks, findings register T-43), which settles the
  listener question EXP-68 and EXP-69 left open: what a player hears depends on the camera's distance from the sound.
- Save and reload: not done (a battle started this way can't be saved or loaded).
- Not settled by this run: whether a number set where the system reads a vector (item 1's Brightness, as the game's
  maps do) changes the brightness, and whether a parameter added that the effect didn't save (item 6's Spawn) changes
  what it plays (the entry loads). Both need an effect bright enough to judge, each value set alone.
- The run's pictures and logs stay in the lab's hidden-runs folder; nothing from them is checked in.
