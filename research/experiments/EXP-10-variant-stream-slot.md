# EXP-10: A variant record that adds a stream slot (plan)

Status (6 November 2026, 12:20): **passed in run 1.** A variant record that keeps URB_Bar's three streams and adds
`patch_exp10slot` in slot 2 loads, streams all four, and its wall stands in the game with high cover. This is slice
E0 of the first-editor plan (section 9). The plan below is as written before the run; the
result is under [Runs](#runs). The lab's test slot is back as EXP-08 left it.

patchtool's `map.streamSlot` was checked without the game first (`tools/patch/tests/test_ship_record.ps1`: 66 of 66
checks pass).

## Question

Does a variant record that keeps all of URB_Bar's streams and adds an edit patch, built on an empty template, in a
free `StreamingMaps` slot load, and stream every one of them?

## Why

The editor ships a variant as the base map under its own name, with a `DefaultMaps.ini` record of its own (plan,
section 7). That record keeps the base map's streams and adds the edit patch.

Until now, patchtool's `map.shipAs` put the patch in `StreamingMaps[1]`, in place of `patch_bar` (EXP-07, EXP-08).
That was right for two cases:
- patches built on `patch_bar`, which carry its actors;
- EXP-08's blank map, which wanted none of them.

An edit patch built on an empty template has none of `patch_bar`'s actors, so the record must stream both. We have
not tried adding a slot yet. Temple Ship shows why replacing slot 1 can't be the rule: its slot 1 is its arrival
cinematic (findings register T-08).

## Stream inventory (read only, 6 November 2026)

**Source.** LWR v2.06.03's `DefaultMaps.ini` in the parked LWR install:
- `<Steam common>\XCom-Enemy-Unknown.LWR\XEW\XComGame\Config\DefaultMaps.ini`;
- 163,644 bytes, SHA-256 `9a6629bc…`, CRLF, no BOM.

`switch_install.ps1 status` said `active=lab parked.LWR=lwr parked.Lab=absent`, so `XCom-Enemy-Unknown` is the lab
copy. Its file differs from LWR's in two places: URB_BarBlank's record (EXP-08, line 6) and the test slot (line 38).
Neither file was changed.

### URB_Bar (line 4, the file's first record)

| Field | Value |
| --- | --- |
| MapFamily, Name | `URB_Bar`, `URB_Bar` |
| DisplayName | `URB_Bar (Beta/Functionality Complete Urban Bar) \|0` |
| MissionType | `eMission_Abduction` |
| bInRotation | `True` |
| TimeOfDay | `eMissionTime_Night` |
| ShipType, eRegion, CouncilType | `eShip_None`, `eMissionRegion_NorthAmerica`, `eFCMType_None` |
| NewMap, InitialChance, InitialGain | `True`, 20, 1.04 |
| DynamicAliens[0], [1] | `eChar_None`, `eChar_None` |
| StreamingMaps[0] | `CIN_DropshipIntros` |
| StreamingMaps[1] | `patch_bar` |
| StreamingMaps[5] | `patch_hide_randomized_objects` |

- Every stream has `Loc=( X=0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 )`. Slots 2 to 4 are not written.
- The line has a tab between the two `DynamicAliens`, and it ends `) ) ) ` with a trailing blank.
- URB_Bar_Terror (line 67: terror site, night, no region) streams only slots 0 and 1, with the same two maps.
- No other record has `Name="URB_Bar"`. A commented-out line 275 holds a capture-and-hold test record.

The fields that matter to a variant record:
- `Name`, the map package;
- `DisplayName`, the key the game and LWR look a record up by;
- `MissionType`, which missions can pick it;
- `TimeOfDay`, which counts for map selection and for LWR's night missions (EXP-08);
- `bInRotation` and `eRegion`;
- the streams.

`MapFamily` stays `URB_Bar`, as patchtool keeps it. `IncrementHistory` logs it first, so the game's play history
probably counts the variant in URB_Bar's family; that has not been checked.

### TempleShip (line 175)

| Field | Value |
| --- | --- |
| MapFamily, Name | `templeship`, `TempleShip` |
| DisplayName | `TempleShip  (Art Complete Temple Ship)`: two blanks, no `\|N` |
| MissionType | `eMission_Final` |
| bInRotation | `True` |
| TimeOfDay | `eMissionTime_None` |
| eRegion | `eMissionRegion_None` |
| StreamingMaps[0] | `TempleShip_Stream` |
| StreamingMaps[1] | `CIN_TP12A_ArriveTempleShip` |
| StreamingMaps[5] | `patch_hide_randomized_objects` |

`"free"` gives TempleShip slot 2 and keeps the cinematic.

### Across LWR's 188 records

- **The highest slot is 5.** The slots used are 0, 1, 2, 3 and 5; slot 4 is never used.
- **Slot 5 is always `patch_hide_randomized_objects`** (119 records), and nothing else is ever in slot 5.
- **Sparse indices are the norm.** 120 of the 188 records skip an index: every record with slot 5 skips slot 4, and
  18 records stream only slots 0 and 5. The index sets:

  | Slots | Records |
  | --- | --- |
  | 0, 1, 5 | 65 |
  | 0, 1, 2 | 34 |
  | 0, 1, 2, 5 | 23 |
  | 0, 1 | 23 |
  | 0, 5 | 18 |
  | 0, 1, 2, 3, 5 | 11 |
  | 0 | 6 |
  | 0, 1, 2, 3 | 5 |
  | 0, 5, 2 | 2 |
  | 0, 2 | 1 |
- **Up to five streams per record.** 11 records have five; 101 have three.
- **Slots out of order in the text.** URB_LiquorStore (line 13, abduction) and DLC1_3_Gangplank (line 124,
  "Landed Battleship (Urban)") write slot 2 after slot 5. So LWR added a slot the way patchtool now does.
- **Slot 0 is in every record.** Three non-tactical records give it `MapName=""` (lines 248, 255 and 258: an MP
  record, `CB2_MP_Blank` and `Command1`).
- **Slot 1 is not always a patch.** It is something else in 47 of the 161 records that have it:
  - the dropship intro (26) or the fastrope intro (9);
  - a mission stream: `*_CovExt` (7), `*_script` (2), the tutorial's;
  - a cinematic: Temple's `CIN_TP12A_…` and a DLC one.

  The old slot-1 rule would have cut all of those, so T-08 is not only Temple's.
- **What `"free"` picks** (the lowest slot not written): 1 for 27 records, 2 for 88, 3 for 57 and 4 for 16. It
  never picks 0. For URB_Bar and TempleShip it is 2.
- **The syntax varies.** `Get-StreamSlots` reads all of these forms, and the check script covers each:
  - 24 records write `StreamingMaps[n]=(MapName=` without blanks;
  - line 222 (URB_ResearchOutpost_EWI, covert extraction) gives two bare names (`MapName=CIN_FastropeIntros`);
  - line 124 ends its last entry with a comma (`), )`, then six tabs).
- **One map name, several records.** 65 map names have more than one record, one per mission type (URB_PierA has
  four). 48 of them stream different maps in different records, and for 38 the free slot differs between records.
  patchtool takes the first record with the base map's `Name`, so for those maps the base record must be chosen by
  `DisplayName`. URB_Bar has one record.

### How the game loads the streams (lab logs, read only)

`StreamingMaps` is a dynamic array (`var init array<init StreamMapData> StreamingMaps` in `XComMapMetaData`,
decompiled `XComMapManager.uc` line 64). An index the record doesn't write is an empty entry.

The lab's `Launch.log` files (`XEW\XComGame\Logs`) show two phases. 71 logs travel to URB_Bar or a renamed copy of it.
68 of them show both phases, and the other three crashed while loading (two are EXP-03 run 3b's missing patch, the
third is from 4 November 11:51).

1. **The seamless travel loads the first slots.** Each gets `StartLoadingDestination: Requesting additional map X`,
   then `SeamlessTravel: loaded additional map X`.
   - For URB_Bar's record, those are slots 0 and 1 (`CIN_DropshipIntros`, `patch_bar`).
   - For the original Commercial Alley record (slots 0, 1, 2, 5), they were slots 0, 1 and 2 (log opened 3 November
     19:28).

   So the travel takes the slots before the first gap, or at least more than two.
2. **After the load, the rest.** `XGLevel` calls `XComMapManager.AddStreamingMaps` with the record's DisplayName
   (decompiled `XGLevel.uc` line 1024). It logs `AddStreamingMap: Re-using already loaded streaming map X` for those
   already loaded, then `AddStreamingMap: Streaming patch_hide_randomized_objects at X=0.000 Y=0.000 Z=0.000
   (blocking)`.

URB_Bar's own record therefore already has a gap before slot 5, and the game handles it. What EXP-10 adds is a
filled slot 2, written after slot 5.

**What shows that `patch_bar` streamed.** When it does, the log lists 28 of its actors as
`DevOnline: Checking patch_bar.TheWorld:PersistentLevel.<actor>`:
- 3 PointLight, 2 XComLadder, 15 XComLevelActor and 8 XComRebuildWorldDataVolume;
- among them `XComLadder_15` and `XComLadder_11`, its two hidden ladders.

This is from a run with URB_Bar's own streams (EXP-03's route 3, log opened 3 November 19:45:59). These lines are the
concrete sign that
`patch_bar`'s actors are in the world. The game itself can't show it: EXP-03's control showed that the bar's ladders
still climb and the dumpsters still give high cover without `patch_bar`. (EXP-08's `patch_exp08blank` got no such
lines, so their absence for our own patch would mean nothing.)

## The spec

[`tools/patch/examples/exp10slot.json`](../../tools/patch/examples/exp10slot.json), patch `patch_exp10slot`:

| Field | Value | Why |
| --- | --- | --- |
| `base` | `""`, an empty map | The patch has no `patch_bar` actors, so they can come only from `patch_bar`'s own stream. |
| `map.name` | `URB_Bar` | The base map. |
| `map.shipAs` | `URB_BarSlot` | The variant map. |
| `map.displayName` | `URB_BarSlot (EXP-10 stream slot) \|0` | The variant record, out of rotation. |
| `map.streamSlot` | `"free"` | Slot 2. |
| `seed` | `false` | The blocks stand on ground-level tiles, as EXP-04's did without seeds. `URB_BarSlot.upk` is then a plain copy of the original, so the stream layout is the only new factor. |
| `objects` | two visible `CoverPatch.High2x2` blocks with high cover | They make a 2 × 4 dark wall in front of the dumpsters: tiles x 1–2, y 9–12 (world x −2688..−2496, y −1056..−672). |

- The first block is EXP-04's, at tile (2, 10), seen in game on 3 November.
- The second is `exp04b.json`'s second block, next to it at (−2592, −768), turned 90°.
- patchtool adds `XComMapEdIntro_903`, which gives `URB_BarSlot` URB_Bar's dropship intro (F-45).

**`t3d` dry run.** `t3d` of this spec was run into a scratch work folder, not `<lab>`. It wrote:
- five actors: the two blocks, their two rebuild volumes and the intro, with suffix 900;
- a `ship.json` with `"streamSlot": "free"`.

**The record patchtool will write**, after URB_Bar's (as lines 5 and 6). `test_ship_record.ps1` builds it from the
real line: URB_Bar's line with `Name="URB_BarSlot"`, the new DisplayName and `bInRotation=False`, ending:

```
..., StreamingMaps[5]=( MapName="patch_hide_randomized_objects", Loc=( X=0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 ) ), StreamingMaps[2]=( MapName="patch_exp10slot", Loc=( X=0, Y=0, Z=0 ), Rot=( Pitch=0, Yaw=0, Roll=0 ) ) ) 
```

## Steps

### Build and deploy (Claude, with the game closed)

**The test slot.** The game's first mission loads a fixed DisplayName,
`URB_CommercialAlley_EWI (Commercial Alley Redux) |0` (EXP-03). So the lab plays a variant through that record, the
test slot: lab `DefaultMaps.ini` line 38 now, and line 40 after this deploy. It currently loads `URB_BarBlank`, with
`CIN_DropshipIntros`, `patch_exp08blank` and `patch_hide_randomized_objects` (EXP-08).

`-Stream` edits only one slot, so two commands make the test slot stream what URB_BarSlot's record streams. From the
repository root:

```
pwsh -File tools\patch\patchtool.ps1 all tools\patch\examples\exp10slot.json -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0' -Slot 2
pwsh -File tools\patch\patchtool.ps1 stream -Map patch_bar -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0' -Slot 1
```

1. **The first command** builds the patch on the hidden desktop, cooks it, and deploys it as
   `CookedPCConsole\patch_exp10slot.upk`. Then:
   - With nothing to seed, the seed step puts a plain copy of the original URB_Bar into the lab as
     `URB_BarSlot.upk`.
   - It copies URB_Bar's 7 landing zones under the new name, and writes URB_BarSlot's record. Its summary should say
     `StreamingMaps[2] added for patch_exp10slot`.
   - `-Stream` then gives the test slot `Name="URB_BarSlot"` and adds its `StreamingMaps[2]`.
2. **The second command** points the test slot's `StreamingMaps[1]` back at `patch_bar`, from `patch_exp08blank`.
   `patch_bar` has no ship file, so the Name stays `URB_BarSlot`. The step makes `<lab>\patchtool\patch_bar\logs`
   for its log.
3. **Check (read only)** that both lines stream the same maps:

   ```
   Select-String -LiteralPath <Steam common>\XCom-Enemy-Unknown\XEW\XComGame\Config\DefaultMaps.ini -Pattern 'Name="URB_BarSlot"' | ForEach-Object { "$($_.LineNumber): " + ([regex]::Matches($_.Line, 'StreamingMaps\[\d+\]=\(\s*MapName="[^"]*"').Value -join ' | ') }
   ```

   Both lines (the record and the test slot) should list, in this order:
   - slot 0, `CIN_DropshipIntros`;
   - slot 1, `patch_bar`;
   - slot 5, `patch_hide_randomized_objects`;
   - slot 2, `patch_exp10slot`.

### In the game (played by hand, with screenshots taken)

As in EXP-03 to EXP-08:
1. Claude starts `<lab>\bin\GameDriver.exe hotkey <lab>\looks F9` if it isn't running already, and
   `GameDriver.exe waitlook <lab>\looks <seen>` in the background. Claude sends no input.
2. The lab copy is started as usual: Steam, the launcher, Enemy Within. Then a new campaign, with Ironman,
   tutorial and autosave off. The first mission loads the test slot, so URB_BarSlot.
3. F9 is pressed at these moments:
   - during the dropship landing;
   - once the squad is down;
   - with the camera on the 2 × 4 wall, by the dumpsters near the map's west edge (around (−2600, −960));
   - optionally, while hovering a tile beside the wall, to show its cover shields.
4. No save is needed. If one is made, WSL2's hypervisor must be off (EXP-03).
5. Claude reads the shots, and reads the lab's `Launch.log` without changing it.

## Pass criteria

All from one fresh load. A load from a save doesn't count: a save carries the world data (EXP-03).

1. **The map loads.** The log has:
   - `XComMapManager::IncrementHistory:  (0) URB_Bar, URB_BarSlot, URB_CommercialAlley_EWI (Commercial Alley Redux) |0`;
   - then `SeamlessTravel to: URB_BarSlot`;
   - and the mission starts.

   There is no crash and no `Couldn't find file for package`. A missing stream is fatal on a fresh load (EXP-03 run
   3b).
2. **Every stream loads.**
   - `CIN_DropshipIntros`, `patch_bar` and `patch_exp10slot` each get a `Requesting additional map` line and a
     `loaded additional map` line. The expected path is the travel, taking slots 0 to 2.
   - If `patch_exp10slot` comes through `AddStreamingMap: Streaming patch_exp10slot …` instead, it still streamed.
     Record which path it took.
   - `AddStreamingMap: Streaming patch_hide_randomized_objects at X=0.000 Y=0.000 Z=0.000 (blocking)` appears, as in
     every URB_Bar run.
3. **The new objects appear.**
   - The F9 shot shows the dark 2 × 4 wall in front of the dumpsters.
   - The patch's own script ran: `XComMapEd: XComMapEdIntro_903 intro: … now plays URB_Bar's case (3) for
     URB_BarSlot`.
4. **`patch_bar`'s own content is there, once.**
   - The log has the 28 `DevOnline: Checking patch_bar.TheWorld:PersistentLevel.…` lines, with `XComLadder_15` and
     `XComLadder_11` among them, as in the EXP-03 run with URB_Bar's own streams.
   - No `patch_exp10slot.TheWorld:PersistentLevel.XComLadder_…` line appears: the patch carries no copy of them.
5. **`patch_hide_randomized_objects` streams** (criterion 2). What it hides has not been looked at, so there is no
   in-game check for it.
6. **The intro plays.**
   - The dropship lands at the start (the cutscene shows), which is the F-45 fix at work.
   - LWR's mutator finds the copied landing zones: `XComLZMutator: CurMapName = URB_BarSlot` and
     `XComLZMutator: DataArray.Length = 7`.

**Optional, not needed to pass.** EXP-03's check C: a soldier sees an enemy (`DropSectoid`) through a metal fence.
`patch_bar`'s Kismet makes metal fences see-through, so this would show `patch_bar` working in the game. It has no
control run.

## Known risks

- **The travel may stop at a fixed count.** If it takes only slots 0 and 1, `patch_exp10slot` comes later, through
  `AddStreamingMaps` after the load (blocking), as slot 5 does. It still streams, but anything in it that must exist
  before the level's start events could run late. `XComMapEdIntro` retries for 30 s, so watch the intro.
- **Slot 2 comes after slot 5 in the text.** The config reader sets array entries by index, and LWR's URB_LiquorStore
  and DLC1_3_Gangplank records are written the same way. We have not seen those records play, though.
- **Two patches over one map.** `patch_bar` (Firaxis's build) and `patch_exp10slot` (our UDK, with `XComMapEd` cooked
  in) stream together.
  - Different XComUDK builds already mix on this map: `patch_hide_randomized_objects` is one (EXP-03).
  - Duplicate NetIndex errors were recorded only when separately cooked patches share edited classes, and
    `patch_bar` has none of ours.
  - Look for NetIndex errors in the log anyway.
- **patch_bar's blockers stay where they are.** Its hidden dumpster blockers at (−2688, −1344) and (−2304, −1344) and
  its hidden walkable tiles now stand beside an edit patch. The nearest edge of our blocks is 288 units (3 tiles) from
  the blockers' centres.
- **The test slot is not the record.** As in EXP-07 and EXP-08, it differs from URB_BarSlot's record in three fields:
  - its DisplayName;
  - `TimeOfDay`: Day;
  - `eRegion`: none.

  The streams are what EXP-10 tests, and step 3 checks that they match. The record itself is out of rotation: only a
  mission that picks it would load it.
- **The test slot keeps `StreamingMaps[2]`.** No patchtool step removes a slot. Until the entry goes, every later
  test-slot run also streams `patch_exp10slot`. To remove it, either:
  - restore the test slot's line from the backup patchtool made before EXP-10's first edit
    (`<lab>\patchtool\backups\DefaultMaps.ini.<time>`);
  - or take the entry out by hand.
- **The base record is found by Name.** patchtool finds the base record by `Name`. That works for URB_Bar, whose
  `Name` is unique, but not for 65 other maps (see the inventory). The editor's build must choose the record by
  DisplayName.

## Runs

### Run 1 (6 November 2026, 12:09 to 12:15): passed

**Deploy (12:09 to 12:10), with the game closed.** The two commands from the steps:
- The build took 27 s on the hidden desktop. All 5 actors were imported and saved (`patch_exp10slot.udk`, 20,556
  bytes).
- The cook took 9 s, with only the known `HQSound_MCMusic` error. `patch_exp10slot.upk` (27,655 bytes) was deployed
  with the cook's SHA-256.
- `URB_BarSlot.upk` is a plain copy of URB_Bar (0 tiles seeded), and URB_Bar's 7 landing zones were copied.
- Step 3's check: the record (line 6) and the test slot (line 40) both stream 0 `CIN_DropshipIntros`, 1 `patch_bar`,
  5 `patch_hide_randomized_objects` and 2 `patch_exp10slot`, in that order.

**In the game.** A new campaign was started; the first mission loaded the test slot. Six F9 shots, in
`<lab>\looks`:

| Shot | What it shows |
| --- | --- |
| `look-121357.png` | The night dropship landing over the bar's street. |
| `look-121408.png` | Turn 1 with LWR's tutorial offer: the squad is down. |
| `look-121411.png` | The squad by the box truck, with Thunder-I (a SHIV) selected. |
| `look-121432.png` | The wall: a dark box between the parked SUV and the dumpsters, where the spec puts it. |
| `look-121458.png` | The SHIV's move preview beside the wall, with no cover shields. |
| `look-121529.png` | A soldier's move preview (Hans Graf) beside the wall: high-cover shields on its sides. |

- **The missing shields were the SHIV's.** On the fifth shot all cover seemed broken; on the sixth, changing to a
  soldier fixed it. SHIVs don't take cover, so their move preview shows no shields anywhere. With a soldier selected,
  the wall gives high cover, as EXP-04's block did.
- **The wall is a plain black box.** That is the mesh, not the streams: `CoverPatch.High2x2` is made to be hidden and
  has a plain material (EXP-04 saw the same). The editor places the game's own art, which shows its real materials
  (EXP-05).

**The log** (the lab's `Launch.log`, opened 12:13:26 and closed 12:15:36 when the game was quit; read only). Each pass
criterion:
1. **The map loads.** Line 1782 has
   `IncrementHistory:  (0) URB_Bar, URB_BarSlot, URB_CommercialAlley_EWI (Commercial Alley Redux) |0`, and line 1899
   `SeamlessTravel to: URB_BarSlot`. There is no `Couldn't find file` and no crash.
2. **Every stream loads, and the travel took slots 0 to 2.**
   - At 12.85 s it requested `CIN_DropshipIntros`, `patch_bar` and `patch_exp10slot` (lines 2293 to 2295). It loaded
     them at 24.67 to 24.74 s (lines 2597 to 2599).
   - After the load, `AddStreamingMap` re-used those three (lines 4432 to 4434) and streamed
     `patch_hide_randomized_objects` (blocking, line 4435).
   - So the travel did not stop at two slots: it takes the slots before the first gap, which is now slot 3. Slot 2,
     written after slot 5 in the text, is read by its index.
3. **The new objects appear.** The wall is in the fourth and sixth shots. The log checks the patch's five actors
   (`DevOnline: Checking patch_exp10slot.TheWorld:PersistentLevel.…`, lines 4391 to 4395). At 29.50 s the intro
   script logged `XComMapEdIntro_903 intro: SeqCond_SwitchString_8 in Main_Sequence now plays URB_Bar's case (3) for
   URB_BarSlot`, then `renamed 1 case(s) of 4 switch(es) after 0.0000 s`.
4. **`patch_bar`'s content is there, once.** There are 28 `DevOnline: Checking patch_bar.…` lines: 3 PointLight,
   2 XComLadder, 15 XComLevelActor and 8 XComRebuildWorldDataVolume, with `XComLadder_15` and `XComLadder_11`.
   No `patch_exp10slot` ladder appears.
5. **`patch_hide_randomized_objects` streams** (point 2).
6. **The intro plays.** The dropship landed (first shot). LWR's mutator logged `XComLZMutator: CurMapName =
   URB_BarSlot`, matched the 7 copied entries and logged `DataArray.Length = 7`.

**NetIndex.** The log has only the five duplicate-NetIndex errors every start logs (camera and engineering
properties, before any map) and their five removals at the travel. The run before
(`Launch-backup-2026.11.06-12.13.26.log`) has the same ten. None names our classes or `patch_bar`'s.

**Cleanup.** After the game closed, the lab's `DefaultMaps.ini` was put back from patchtool's backup
`DefaultMaps.ini.20261106-120931-2`, taken before the test-slot edit. The live file differed from it only at line 40.
- The test slot again loads URB_BarBlank with `patch_exp08blank`, as EXP-08 left it.
- The file as the run had it is kept as `<lab>\patchtool\backups\DefaultMaps.ini.20261106-exp10-run1-after`.
- These stay in the lab, and nothing loads them: URB_BarSlot's own record (line 6, out of rotation), its 7 landing
  zones, `URB_BarSlot.upk` and `patch_exp10slot.upk`.

**What it settles.**
- T-08's fix works in the game for URB_Bar. `"free"` keeps every stream of the base record and adds the patch.
- An edit patch built on an empty template streams beside `patch_bar`, whose actors load once.
- Not covered: Temple Ship, whose renamed map's mission start and progression are plan M4; and choosing the base
  record by DisplayName, which the editor's build still has to do.
