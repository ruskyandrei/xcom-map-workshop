# EXP-87: a map pack's landing intros, without a copy per map

Date: 19 November 2026. Status: **passed** (LWR map packs; [F-45](../findings-register.md),
[F-142](../findings-register.md)). A map pack's maps can't stream the game's own intro: a map whose name the intro
does not know gets no landing, and the grounded Skyranger stays hidden for the whole battle. One intro copy for the
whole pack works: each map's name added as one more case of its base map's switch.

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

- Not done here: Export map pack still puts each build's own copy in the pack. A pack-wide copy would also have to
  carry each map's moved flight (the build's report names the actions it moved) and fall back to a map's own copy
  where two maps of the same base fly differently.

Left in the beta 15 copy (no restore after experiments): `Workshop_test_pack` streams the lab's pack-wide copy; the
three per-map copies are in `XEW\XComGame\held-intro-copies`, outside `CookedPCConsole`.

Shots (in `private/shots/EXP-87`): for each run, 3 and 6 s into the intro, 4 s after it, and URB_Bar's landing
place.
