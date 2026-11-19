# EXP-85: a map pack card of ours on LWR 3.00.00 beta 15

Date: 19 November 2026. Status: **passed but for the picture on the Geoscape's screens, which waits for a run by
hand** (LWR map packs, stages C2b and C9). The game reads a card written by
[pack_card.py](../../tools/upk/pack_card.py), finds the maps in the pack's folder, plays one as a new campaign's first
mission, and finds a map's own picture in it. A pack made by Export map pack did the same (runs C below). **A
lighting cache inside the pack's folder is not found** ([F-140](../findings-register.md)); exported packs put it
beside the folder, and since [EXP-86](EXP-86-lighting-inside-the-map.md) carry it inside each map instead.

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

## The exported pack (C9)

`Workshop test pack` v1, made by Export map pack on a test server from three projects in a scratch store:
`pinkbar` (Additional, a picture of its own uploaded to the project, full build), `EXP-62 piece flags` (Replace, full
build) and `farm++` (Additional, a crashed small scout's map, quick build; the farm's records include LWR's own
ship type 10, a number with no enum name). The zip held the folder `Workshop_test_pack` (maps, intro copies, card
`LWRMapPack_9328.upk`, README) and the two lighting caches beside it. `pack_test.py put` copied it in as a player
would.

| Run | Done | Seen |
| --- | --- | --- |
| C1 | `Pinkbar` opened directly | `card 9328 'Workshop test pack v1 by the workshop' (format 1): 4 map line(s), 2 picture line(s), 15 LZ line(s)`; `looked for 4 map file(s), 0 missing`; `merged - class defaults 3 added, 1 replaced`: the Replace map's line took `URB_Bar (Beta/Functionality Complete Urban Bar) \|0` from the game's record; all four lines `used`, the farm's ship-10 line too; `15 LZ line(s) from map packs added`; the bar's baked light drawn with its cache beside the folder. |
| C2 | The first-mission card on `Pinkbar`; a new campaign by the console; base location chosen with Enter (Random) | The base location screen came up this time (in run B it did not: that campaign started at another point of the flow); the first mission's loading screen; `mission start (from a save False): map file 'Pinkbar'; the game's map line 'URB_CommercialAlley_EWI (Commercial Alley Redux) \|0' (file 'Pinkbar', type 2); streamed levels: CIN_DropshipIntros_Pinkbar patch_bar`; the battle on the pink bar. |
| C3 | The mission ended with `killaliens`, the summary passed by Enter, back to the base | Mission completed, six aliens dead, both Meld canisters; the campaign went on to the base. (`KillAllElse`, tried first, destroys every pawn but the selected one, the soldiers too, and the game crashed loading the summary: the test's fault.) |
| C4 | At the base: `Mutate LWRPack Sectoid`, `Mutate LWRMapTest Pinkbar`, `Mutate LWRMapTest Peek Pinkbar MapPicture` | `LWRMapTest: mission 1 moved from 'DLC1_2_CnfndLight (Abduction) \|8' to 'Pinkbar (Beta/Functionality Complete Urban Bar) \|0'`, its command line streaming the pack's intro copy and patch; Peek: `step 2 (texture MapPicture): 2 ms, found (Texture2D), map NOT loaded`. The map's own picture, written by the Build, is found by LWR's lookup without loading the map. |

The run stopped there: Mission Control opens only by a mouse click (its key, Q, did nothing at the base in these
runs), and the mission alert, where LWR draws the picture (`MAPFRAME`), is on the Geoscape.

## Left

- **The picture on the mission alert and in squad select** (the map's own on `Pinkbar`, a borrowed one on
  `URB_Bar_X62`), with the log's `MAPFRAME ... image 512x256`: a run by hand, the copy switched in. In the game's
  console on the Geoscape: `Mutate LWRPack Sectoid`, then `Mutate LWRMapTest Pinkbar`, then wait for the alert.
- A UFO map in a mission of its own (the farm's line is used; its bounty line not seen), a pack's folder changed
  between runs (a map taken out, a newer version, two packs with one name), a save loaded.

The exported pack's folder and its two cache files are still in the beta 15 copy (no restore after experiments); the
first-mission card was taken out.

Shots (in `private/shots/EXP-85`): the bar's floor with the cache in the pack's folder and in `CookedPCConsole`, the
first mission's loading screen, the first mission on our map; for C9 the base location screen, the first mission on
the pink bar, the mission won.
