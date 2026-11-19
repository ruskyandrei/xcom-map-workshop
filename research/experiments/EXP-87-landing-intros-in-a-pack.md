# EXP-87: a map pack's landing intros, without a copy per map

Date: 19 November 2026. Status: **passed** (LWR map packs; [F-45](../findings-register.md),
[F-142](../findings-register.md)). A map pack's maps can't stream the game's own intro: a map whose name the intro
does not know gets no landing, and the grounded Skyranger stays hidden for the whole battle. One intro copy for the
whole pack works: each map's name added as one more case of its base map's switch. Export map pack now writes one
such copy for each kind of intro its maps use (runs E).

Played unattended on the parked LWR 3.00.00 beta 15 lab copy where it stands (`hidden_game.py --game`), with
`Workshop_test_pack` (`Pinkbar` and `URB_Bar_X62`, both variants of URB_Bar, and `CSmallScout__Farm_ec8f`) and its
card rewritten for each layout. Each run: the map opened with Play in game's commands and the test squad, no aliens;
a shot every 3 to 4 s for 20 s after the intro's stream comes in, two after the intro ends, then one of URB_Bar's
landing place (560, -2683) with the fog lifted.

## Why each build has its own intro

- The game seats the squad in the Skyranger and fires `SeqEvent_OnTacticalIntro` with `WorldInfo.GetMapName()`, the
  loaded map file's name (`XGBattle.PlayCinTacticalIntro`, the same in beta 15's XComGame as in the game's).
- The landings are in the streamed `CIN_DropshipIntros` (or `CIN_FastropeIntros`, or the alien bases'
  `CIN_TP05A_EnteringAlienBase`): Switch String nodes pick each map's flight by that exact name (F-45, F-76). A Build
  therefore makes `<Intro>_<Map>.upk`, a copy of the intro with the base map's case naming the build's map.
- Nothing in beta 15 maps a pack map's name to another: its mod code does not touch the intro's cases, and a card
  line's `MapFamily` (ours give the base map, as the game's own lines do) is read only for EWI_MeldTutorial's council
  type. LWR's guide has new maps stream the game's `CIN_DropshipIntros` as it is.
- A copy is the whole intro: the game's `CIN_DropshipIntros.upk` is 5.8 MB and a build's copy 6.05 MB. Of its
  8.9 MB of object data, animations (2.1 MB), meshes (2.9 MB), sounds (1.2 MB) and textures (1.2 MB) are shared by
  every map's landing; the switches and the rest of the Kismet are a few hundred KB. A copy cut down to one map's
  landing would be little smaller.

## Runs

| Run | Intro streamed | Intro done after the map is up | Seen |
| --- | --- | --- | --- |
| N1 `URB_Bar_X62` | the game's `CIN_DropshipIntros` (the copy taken out) | 0.9 s | No landing: the squad stands at the landing from the first frame. **The grounded Skyranger is not drawn for the whole battle**: only its baked shadow on the street. |
| R1 `Pinkbar` | its own copy | 18.2 s | The Skyranger flies in and lands; after the intro it stands at the landing. |
| S1 `URB_Bar_X62` | one copy for the pack | 18.2 s | As R1. |
| S2 `Pinkbar` | the same copy | 18.2 s | As R1. |
| S3 `CSmallScout__Farm_ec8f` | the same copy | 9.3 s | The crash site's landing (shorter than the bar's): the Skyranger close up, a cut, then the squad at its landing with the grounded Skyranger beside it. |

The Skyranger stays hidden in N1 because URB_Bar's own Kismet hides the grounded Skyranger when the intro starts
(`CIN_HideForIntro`) and shows it when the intro says it is finished (`CIN_IntroFinished`). A map name with no case
falls through to `CIN_DS_Stop`, which ends the intro without saying so.

The pack's copy (`CIN_DropshipIntros_Workshop_test_pack.upk`, 6.06 MB, made by a lab script from the game's intro):
in `SeqCond_SwitchString_8` the cases `URB_Bar_X62` and `Pinkbar` added after `URB_Bar`'s, in
`SeqCond_SwitchString_6` `CSmallScout__Farm_ec8f` after `CSmallScout_Farm`'s; each new case's output link is a copy
of its base case's (the same actions). The farm build moves its landing (its own copy moves `SeqAct_SetLocation_58`);
the lab copy did not, so S3's flight went to the farm's old landing place; the run's shots, taken close up, don't
show where it set down. S3 settles that the crash sites' switch takes an added case as the bars' does.

## What the runs settle

- A pack map needs an intro that names it: without one there is no landing and, on maps that hide the grounded
  Skyranger for the intro (URB_Bar does), no Skyranger at all (F-142).
- One copy can serve every map of a pack: a case per map, its output the base map's. Maps of the same base share the
  base's flight, so they can share a copy only when they fly it alike (no landing moved, or moved the same way).

## Runs E: a pack made by Export map pack

Since these runs Export map pack writes the pack-wide copies itself ([manager.py](../../tools/viewer/manager.py)
`_shared_intros`, [intro_copy.py](../../tools/bake/intro_copy.py) `pack_copy`). `Intro test pack` was exported on a
test server from five builds: `Pinkbar` and `URB_Bar_X62` (URB_Bar), the farm (its landing moved), an alien base
(`AlienBase01_AlienBa_680d`) and a temple ship map (`TempleShip_TempleIm_2001`). It holds two intro files where the
builds had four copies (16.8 MB for 28.7 MB):

| File | Size | Maps |
| --- | --- | --- |
| `CIN_DropshipIntros_Intro_test_pack_6615.upk` | 6.06 MB | `Pinkbar`, `URB_Bar_X62`, the farm (with its moved `SeqAct_SetLocation_58`) |
| `CIN_TP05A_EnteringAlienBase_Intro_test_pack_6615.upk` | 10.76 MB | the alien base |
| none | | the temple ship: its records stream the game's `CIN_TP12A_ArriveTempleShip`, which no build copies |

`pack.ps1 install` put it into the beta 15 copy the card way (the earlier test folder taken out first: it held maps
of the same names). Each map opened with Play in game's commands and the test squad: the bars and the farm without
aliens, the alien base and the temple ship with them (missions of those kinds may wait for their aliens).

| Run | Intro done after the map is up | Seen |
| --- | --- | --- |
| E1 `Pinkbar` | 18.2 s | The Skyranger lands; it stands at the landing after. |
| E2 `URB_Bar_X62` | 18.1 s | As E1. |
| E3 the farm | 9.2 s | The crash site's landing, by trees and fire, then the squad at its landing. The intro's streaming point (`SMEDIS`, the flight's rig) is at (-902.6, 7580.5), against (-1881.6, 5021.5) in S3, whose copy did not move the flight: 979 and 2559 units off, exactly the build's move of the flight from (-1265, 4319) to (-286, 6878). |
| E4 the alien base | 24.1 s | The entrance: the squad comes down the ropes into the base; then the battle starts, the squad at the ropes. (A variant the entrance does not name never starts its battle: F-76.) |
| E5 the temple ship | 26.1 s | The game's own arrival: the Skyranger's ramp inside the ship, the squad on the walkway, "Temple Content Loading" while `TempleShip_Stream` comes in; then the battle ("End the alien invasion"). |

- One pack file per kind of intro its maps stream: the Skyranger's landings for the bars and the farm, the
  entrance for the alien base; the temple ship needs none. A pack with a fast-rope map would have a third (the same
  switches, not played here).
- A moved flight goes into the pack's copy and is flown (E3).

Left in the beta 15 copy (no restore after experiments): the pack folder `Intro_test_pack`; the lab's pack-wide copy
of S1-S3 with its three maps is in `<lab>\pack-test\exp87`, the per-map copies of runs N and R in
`XEW\XComGame\held-intro-copies`, both outside `CookedPCConsole`.

Shots (in `private/shots/EXP-87`): for each run, 3 and 6 s into the intro, 4 s after it, and URB_Bar's landing
place.
