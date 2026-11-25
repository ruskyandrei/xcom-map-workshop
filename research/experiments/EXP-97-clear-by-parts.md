# EXP-97: maps with one part cleared, in the game

Date: 24 November 2026. Status: **played: every check passed.** A map with only its triggers, effects, lights or pieces
cleared loads, plays, saves and loads, and in each the part is gone while the rest stays. Played unattended in the lab
copy (LWR 2.06; the game-test skill), one pass of each check and one second take of a picture.

## The questions

The clear-by-parts plan (private/plans/done/modular-clear-plan.md, section 7) asks only what the parts add: a clear of
every part was played in EXP-51 and EXP-94.

1. With its triggers alone cleared, does a crashed UFO map keep its pieces and play no narration where a soldier sees
   the power core and enters the ship?
2. With its effects alone cleared, does a map play none of its ambient sounds but the landing's, and does its rat
   trigger, whose emitters are gone, fire without harm?
3. With its lights alone cleared (a quick build), does the map load and save, and how does it look?
4. With its pieces alone cleared, does the map keep its sounds and triggers?

And for each, does a quicksave load (F-156's kind of crash: an actor taken out of the level and still named)?

## The maps

Built quick by the Build of this branch, each a project with one part cleared (schema 9's `cleared`) and nothing else
(the pieces' variant with every base-level piece deleted, as the page's clear deletes them), staged in the lab copy
with `lab_install.install(..., game=<the lab copy>)` while another copy was the one Steam ran:

| Variant | Base map | What the clear took (the manifest's cleared record) |
|---|---|---|
| DirtRoadTrig | CSmallScout_DirtRoad | 6 trigger volumes, the sight point (UFOPowerSighted); 6 touch events switched off |
| BarFx | URB_Bar | 68 emitters, 5 ambient sounds, 2 lens flares |
| BarLights | URB_Bar | 54 point lights, 62 spot lights, 1 toggleable spot light |
| BarPieces | URB_Bar | 964 pieces by records; 38 stains, 2 path-blocking volumes, 2 cover seeds by the clear |

Each started hidden with `--map`, the test squad, `--no-aliens` and `--saving`.

## Runs

0. **Control, CSmallScout_DirtRoad as it is.** A soldier teleported into the UFO by the power core: a talking head
   (Dr. Vahlen, then Dr. Shen) in the HUD's top right; the log loads two narration packages and plays
   `XComNarrative` conversation nodes 4 and 2; SeqEvent_Touch_8 (the UFO's area) counts 1.
1. **DirtRoadTrig.** Turn 1 reached. The six touch events read `bEnabled` False. The same teleport onto the same tile:
   no talking head in three shots over 16 seconds, no narration package or `XComNarrative` line after it (only the
   landing intro's line at the load plays, as on the map as it is), every touch event's count stays 0. A shot shows
   the hull, the crash site and the power core's column. The quicksave loads; the events still read off. Passed.
2. **BarFx.** Turn 1 reached. `listen` at the places of three of the map's ambient sounds (AmbientSoundSimple_0, _2
   and _3), 400 units away: none of the map's ambient sound actors plays, only the level's bed (its level-loaded sound, the same
   everywhere) and the music; at the Skyranger its idle plays (0.42). A soldier teleported into the rat trigger
   TriggerVolume_1: SeqEvent_Touch_0 counts 1, and the game goes on (its script set values on rat emitters no longer
   in the level). The quicksave loads. Passed. (The taken emitters and sounds are still objects of the package, their
   components not attached: nothing shows or plays.)
3. **BarLights.** Turn 1 reached. No point or spot light of the map is attached (the toggleable spot light is there as
   an object, its component not attached). With the fog off, the bar room's floor and counter are still lit warm by
   the baked light and the street keeps its night blue: the room doesn't look dark, as a quick build leaves it. The
   quicksave loads. Passed.
4. **BarPieces.** Turn 1 reached; the known "Extended Base tile is not a floor tile" line. AmbientSoundSimple_0 (a
   pickup truck's engine idle, at -852, -550) still plays at its place (0.47). The two rat events read `bEnabled` True before and after the load. From above:
   the grounded Skyranger over an empty grid, no ground. The quicksave loads. Passed.

Seen besides: the squad landed at other zones of Bar than the one first expected (the game picks one of seven);
patch_bar's three lights are streamed into the lights' and effects' variants (only the pieces' variant drops the patch
levels, by design); on BarPieces the soldiers stand at z 176 on nothing, as on any cleared Bar.

## What it shows

- A clear of one part takes that part out in the game and leaves the rest working: the narration of a UFO map's power
  core and entry gone with its triggers while its pieces and intro stay; the map's ambient sounds gone with its
  effects while the landing's stay; the lights gone with its lights while the baked light stays until a baked build;
  the sounds and triggers kept when only the pieces go.
- A script acting on emitters the clear took out does no harm (F-58's finding again, for a trigger kept with its
  emitters gone).
- Each kind of partial clear saves and loads.
- Pictures (two kept in private/shots/modular-clear: the control's talking head, the cleared map's none); the rest in
  the lab's hidden-runs folders mc-control-dirtroad, mc-DirtRoadTrig, mc-BarFx, mc-BarLights and mc-BarPieces.
