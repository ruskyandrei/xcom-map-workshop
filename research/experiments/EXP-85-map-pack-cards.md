# EXP-85: a map pack card of ours on LWR 3.00.00 beta 15

Date: 19 November 2026. Status: **the first look passed** (LWR map packs, stage C2b): the game reads a card written
by [pack_card.py](../../tools/upk/pack_card.py), finds the maps in the pack's folder and plays one as a new
campaign's first mission. **One thing failed: a lighting cache inside the pack's folder is not found**
([F-140](../findings-register.md)). The picture on the mission screens, the Geoscape's own choice of a pack map and a
pack made by Export map pack are still to run.

Played unattended on the parked beta 15 lab copy, run where it stands (`hidden_game.py --game <beta 15 copy>`; the
copy was not switched in), with [pack_test.py](../../tools/lab/pack_test.py) putting the pack in and reading the log.

## The pack

Put together by hand: two builds' files in one folder, `WorkshopTest`, with a card `LWRMapPack_4242.upk` holding the
builds' own record and landing lines. First `Pinkbar` and `URB_Bar_X54` (four map lines, nine landing lines), then
`Pinkbar` and `URB_Bar_X62` (two map lines, fourteen landing lines). All are variants of URB_Bar built on LWR 2.x.

## Runs

| Run | Done | Seen |
| --- | --- | --- |
| A0 | The copy as it is, to the main menu | `looked for map pack cards LWRMapPack_0000 to 9999 in 542 ms: 0 found`. The scan runs as the main menu loads. |
| A1, A2 | The pack put in; `Pinkbar` opened with Play in game's commands and the test squad, no aliens; `Mutate LWRMapTest Packs` | `card 4242 'Workshop Test v1' (format 1): 4 map line(s), 0 picture line(s), 9 LZ line(s)`; `looked for 4 map file(s), 0 missing`; `merged - class defaults 4 added, 0 replaced`; each line `the game finds it` and, from `Packs`, `used`; `mission start (from a save False): map file 'Pinkbar'; the game's map line 'Pinkbar (pinkbar) \|0' (file 'Pinkbar', type 2)`; the map's intro copy and patch streamed from the pack's folder; `9 LZ line(s) from map packs added`. The battle started: six soldiers of the test squad with their gear, standing at a landing. |
| - | `URB_Bar_X54` opened directly | Its first line is a terror mission; without aliens the battle did not start in 300 s. A fault of the test's choice, not of the pack: a terror mission needs its pods. Not followed up. |
| L1 | `URB_Bar_X62` with `URB_Bar_X62_Lighting.tfc` in the pack's folder; three fixed camera places | The made floor in the bar is not drawn (black) and the baked light is missing. |
| L0 | The same with the cache deleted | The three pictures equal L1's (no pixel differs by more than 16 of 255). |
| L3 | The cache in `CookedPCConsole` itself | The floor and the baked light are drawn: 15% and 8% of the pixels of two pictures differ from L1's. |
| L2 | The map's 39 textures naming the cache `WorkshopTest\URB_Bar_X62_Lighting`, the cache in the folder | As L1: the floor is not drawn. |
| B | The caches in `CookedPCConsole`; `pack_test.py first-mission URB_Bar_X62`; a new campaign | `card 9999 'First mission test'`; `merged - class defaults 2 added, 1 replaced`; the loading screen of the first mission (Commercial Alley's picture: the line has that map's display name and the map no picture of its own); `mission start (from a save False): map file 'URB_Bar_X62'; the game's map line 'URB_CommercialAlley_EWI (Commercial Alley Redux) \|0' (file 'URB_Bar_X62', type 2); streamed levels: CIN_DropshipIntros_URB_Bar_X62 patch_bar`; `14 LZ line(s) from map packs added`; the battle on our map with the game's own first squad and LWR's tutorial question. |

## What the runs settle

- The card format is right: package, names, every property. The game's log counts the lines the card holds.
- Maps, intro copies and patches are found in a folder under `CookedPCConsole`.
- A lighting cache is found only in `CookedPCConsole` itself (F-140). A pack is therefore its folder and its cache
  files beside the folder.
- The test squad's gear works on beta 15.
- `Mutate LWRMapTest Packs` works in a battle. `Peek` wants the Geoscape.
- A campaign can be started without the mouse: the New game screen's Start button runs
  `open Command1?game=XComStrategyGame.XComHeadQuartersGame?Difficulty=1`, which the console takes at the main menu.
  The intro movie is skipped with Escape and the first mission launched with Enter. No continent is asked for on
  this path.
- A line with the first mission's display name and another file replaces the game's record in the merge, so a card
  can put any pack map in front of a tester minutes after New game.
- At a direct open the mission start line lists no streamed levels (they are added after it); in a campaign it does.

## Left

The picture of a pack map on the mission alert and in squad select; an abduction moved to a pack map on the Geoscape
(`Mutate LWRMapTest <name>`); a Replace line; a UFO map; a pack's folder changed between runs (a map taken out, a
newer version, two packs with one name); a save loaded. They wait for a pack made by Export map pack.

The pack's folder and its two cache files are still in the beta 15 copy (no restore after experiments); the
first-mission card was taken out.

Shots (in `private/shots/EXP-85`): the bar's floor with the cache in the pack's folder and in `CookedPCConsole`, the
first mission's loading screen, the first mission on our map.
