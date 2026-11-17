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

Not played yet.
