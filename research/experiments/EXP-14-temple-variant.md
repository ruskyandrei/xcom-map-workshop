# EXP-14: The user's Temple Ship project in the game, through the test slot (plan)

Status (6 November 2026, 15:12): **runs 1 and 1b done.** In run 1:
- The variant loads and plays, the copies stand as posed, exactly the targets are hidden and the laser barriers give
  cover.
- Three findings: Temple's doorway walls aren't drawn (F-51), the copies look bluer than the baked scene (F-52), and
  the psi device copies give no cover at their ends (F-53).

Run 1b shows that the walls are missing from the unedited map in the test slot too. F-51 is therefore not caused by
the edit, and it is set aside.

**Run 2 (15:31):** revision 3 (power cores in place of the psi devices), loaded from the user's save inside the real
Temple mission.
- The patch loaded and the copies stood as posed.
- The walls were still missing, so F-51 isn't from the test slot.
- The core copies could be walked through and gave no cover (F-54, likely the save's tile data).

**Run 3 (set up 15:35):** the user's HQ save, with the unedited Temple, started normally.

**Run 4 (16:06):** revision 3 again, as a new campaign's first mission. **Passes:** the power cores and the laser
barriers block, give cover all around and can be walked around. F-54 is confirmed: a fresh start keeps the patch's
tile rebuild. What's left is the copies' bluer tone (F-52), worked through below.

**Run 5 (deployed 16:26):** the copies' light side by side. Six more laser barrier copies, each with its own light
setting, stand by the project's barriers and by one of the map's own. Two can be changed live from the console.
Temple's lavender sky light, which lights only live-lit objects, is a large part of the tint. The glow does
nothing.

**Run 6 (16:44):** the copies try to leave that sky light out by lighting channel. That can't be done: variant A
still takes it, and B takes no light at all.

**Run 7 (16:51): passes.** The copies take their light once, while the copier has the sky light off for 2 s at
load, and keep it. They match the map's own pieces ("looks great now!"), and the soldiers keep their usual light.

**Run 8 (deployed 17:13):** the user's `temple_improved` project again, with the rule now generic: every copy of a
baked piece leaves out a units-only sky light by default (`XComMapEdSkyFree`). The project needs no change.

**Run 9 (deployed 17:56):** revision 4 of the project: four alien consoles laid on their sides in place of the power
cores. One was lost by a viewer paste bug (T-12), so it is rebuilt for the build.

**Run 10 (deployed 18:03):** revision 5, the user's re-save with the fixed viewer: the four consoles as four actors,
compiled straight from the saved file. A grenade on a console copy turns it lavender again: damage resets its light.

**Run 11 (deployed 18:18):** the same project. Pieces whose state, mesh, materials or
fragments change take their light again, with the sky light off for 0.3 s. The relight ran at the hit, and the hit
consoles still came out lavender. One of the other pair is black (F-56).

**Run 12 (deployed 18:39):** no more switching. Temple's sky light is switched off for good, and a copy of it on
Gameplay_1 (the units' channel, as most maps' sky lights) lights the units. Our pieces trace their lights from the
closest point of their bounds. **F-52 passes:** a grenade leaves the console's tone as it was, and the soldiers look
normal. The black console stays black: almost no direct light reaches its place (F-56).

**Run 13 (deployed 19:36):** revision 6, with the editor's new groups. Each stacked pair is a locked group that
breaks together in the game: the north consoles, and a new south pair of alien low covers. The links are made at
load. One grenade hit one low cover without damaging it, so there was nothing to pass on yet. Redeployed at 19:40
with each hit's outcome logged.

**Run 14 (deployed 19:42):** revision 7. Both places now have a stacked pair of alien low covers, each a locked group
that breaks together.

The user edited a Temple Ship project in the viewer, `temple_improved`, and asked for an in-game check. It is the
first Temple variant. The plan puts Temple variants in milestone M4, after an audit of the final mission: its stream
ownership (T-08), arrival, gates, ending and checkpoints. This run goes ahead of that audit, on the test slot, to see
the pieces in the game. It is not a check of a playable final mission.

## Question

1. Does a Temple Ship variant load when the first mission's test slot points at it, with Temple's streams?
2. If it does, do the project's edits stand as the viewer drew them, with the cover the pieces give?

## The project (the user's)

`temple_improved`, id `20012b82-ea6d-4d22-8fdb-c6ac64cdc379`, revision 2, on TempleShip (SHA-256 `029bedca…`).
Output names `TempleShip_TempleIm_2001` and `patch_templeship_templeim_2001`.

| What | Piece | Where (x, y, z) | Rotation (units) |
| --- | --- | --- | --- |
| Added | `XComDestructibleActor_9_copy4`, from `XComDestructibleActor_9` (AlienBaseLaserB) | (1197.6, −6994.1, 0) | 0 |
| Added | `XComDestructibleActor_9_copy5`, the same | (−1105.9, −6989.5, 0) | 0 |
| Added | `XComLevelActor_249_copy2`, from `XComLevelActor_249` (PsiGallopDeviceLOD) | (47.0, −5743.5, 187.8) | yaw 32768, roll 779 |
| Added | `XComLevelActor_249_copy3`, the same | (47.2, −7013.9, 187.8) | yaw −289, roll 779 |
| Deleted | `XComDestructibleActor_206` (AlienLowCoverA) | (1200, −7056, 0) | — |
| Deleted | `XComDestructibleActor_208` (AlienLowCoverA) | (−1104, −7056, 0) | — |

- The two laser barriers stand roughly where the two low covers were, which are deleted.
- **Compile** ([`tools/editor/compiler.py`](../../tools/editor/compiler.py)): 2 deleted, 4 added, no errors. It
  compiles only since destructible props joined M1 ([EXP-13](EXP-13-destructible-props.md)).
- **Two warnings:** the psi device is part of a building floor (building 10699, floor 0), so its copies are not in
  that floor's cutaway, and the cutaway won't hide them.
- **The deploy spec** is [`tools/patch/examples/templeimproved.json`](../../tools/patch/examples/templeimproved.json):
  the compiled spec plus two fields for this experiment.
  - `map.timeOfDay` `None`, Temple's record's, so the test slot plays it as Temple's record does. patchtool took
    only Day or Night before; it now also takes None.
  - `map.intro` `false`: there is no dropship-intro helper. Temple arrives by its own cinematic, and
    `CIN_DropshipIntros` is not streamed here.
- **Dry run** (no lab files touched):
  - `t3d` gives the copier (4 pieces, each to its own pose), the exact hider (2 targets) and the tile seeds (4 boxes,
    280 tiles).
  - `seed_map.py apply` on a scratch copy of TempleShip seeded 146 of the 280 tiles (134 already had low bits), and
    verified them. This is the first seeding of a map other than the Bar.

## Build and deploy (6 November, 14:42, game closed)

```
pwsh -File tools\patch\patchtool.ps1 all tools\patch\examples\templeimproved.json -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0' -Slot 2
pwsh -File tools\patch\patchtool.ps1 stream -Map TempleShip_Stream -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0' -Slot 0
pwsh -File tools\patch\patchtool.ps1 stream -Map CIN_TP12A_ArriveTempleShip -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0' -Slot 1
```

- The first command puts `TempleShip_TempleIm_2001.upk` into the lab, seeded, and adds its record after
  TempleShip's. The record is not in rotation and streams the patch in slot 2. LWR has no landing zones for
  TempleShip, so none are copied.
- It also points the test slot at the variant: `Name`, `TimeOfDay` None, and slot 2.
- The two `stream` steps give the test slot Temple's slot 0 (`TempleShip_Stream`) and slot 1 (the arrival
  cinematic) in place of the Bar's. Slot 5, `patch_hide_randomized_objects`, is in Temple's record too.
- The test slot keeps its own `MapFamily` (URB_Bar) and `MissionType` (abduction): the first mission is an
  abduction.

**Done:**
- **Build:** 21 s on the hidden desktop: 3 actors (copier, hider, tile seeds), 10,085 bytes.
- **Cook:** 8 s, with only the known `HQSound_MCMusic` error. `patch_templeship_templeim_2001.upk` is 132,910 bytes.
- **Deploy:** `TempleShip_TempleIm_2001.upk` is TempleShip with 146 of the 280 planned tiles seeded (the other 134
  already had low bits).
  - patchtool warns that `DefaultLZMutator.ini` has no landing zones for TempleShip, as expected; none were written.
- **The record** is at `DefaultMaps.ini` line 184: TempleShip's, renamed, not in rotation, with the patch in slot 2.
- **The test slot**, line 42, now has:
  - `Name="TempleShip_TempleIm_2001"`, `TimeOfDay=eMissionTime_None`;
  - streams 0 `TempleShip_Stream`, 1 `CIN_TP12A_ArriveTempleShip`, 5 `patch_hide_randomized_objects` and
    2 `patch_templeship_templeim_2001`, the same as the record;
  - its own `MapFamily="URB_Bar"` and `MissionType=eMission_Abduction`.
- **Backups:** `<lab>\patchtool\backups\DefaultMaps.ini.20261106-144211` (before the record), `-144211-2`
  (before the test slot's Name, slot 2 and time of day), `-144250` (before slot 0) and `-144250-2` (before slot 1).

**Where to look.** The game's cursor readout (`Cursor @ (x, y, z) ... (tile x, tile y, level)`, found in EXP-11) uses
the map's grid. On Temple Ship the grid starts at (-2112, -9408, -384). The readout's z is 64 units above the floor
under the cursor, so its level is one above the floor's tile: the ground (z 0) reads level 7, and the raised walk the
psi devices stand on (floor z 192) reads level 10. Corrected during run 1, from the shots; the plan had 6 and 8.

| Piece | Tile (x, y, level) |
| --- | --- |
| Laser barrier `XComDestructibleActor_9_copy4` | (34, 25, 7) |
| Laser barrier `XComDestructibleActor_9_copy5` | (10, 25, 7) |
| Hidden low cover `XComDestructibleActor_206` | (34, 24, 7), next to copy4 |
| Hidden low cover `XComDestructibleActor_208` | (10, 24, 7), next to copy5 |
| Psi device `XComLevelActor_249_copy3` | (22, 24, 10) and (22, 25, 10) |
| Psi device `XComLevelActor_249_copy2` | (22, 37, 10) and (22, 38, 10) |

## What may go wrong

- The map is Temple's, but the mission is an abduction. The squad's start, the arrival cinematic's Kismet, the
  aliens and the objectives may not work.
- If the mission does not start, a run 1b points the test slot at TempleShip itself, the plan's no-op alias. That
  tells a Temple-in-the-test-slot problem from a patch problem.

## In the game (the user drives, Claude looks)

A new campaign; the first mission loads the test slot. Shots (F9), as far as the mission allows:
1. What the mission start shows: the arrival, where the squad stands.
2. The south end (y about −7000): the two laser barriers where the low covers were, and the psi devices.
3. A soldier beside a laser barrier: its cover shields.
4. A psi device copy close up: its height and tilt, and whether it blocks.

## Pass criteria

1. **The map loads.** `IncrementHistory` names `TempleShip_TempleIm_2001`; `TempleShip_Stream`, the arrival
   cinematic and the patch load; no crash.
2. **The copies stand as posed:** `copied 4 of 4 pieces, each to its own pose`, and at most 0.01 units and 0
   rotation units off, at load and 5 s later.
3. **Exactly the targets are hidden:** `hid 2 of 2 exact targets`, with no warning.
4. **The shots match the project**, and the laser barriers give cover.
5. **Recorded, not required:** how the mission starts and plays as an abduction on Temple's map (for M4).

## Afterwards

Nothing is put back. The next experiment's deploy sets the test slot's fields itself; EXP-13's sets the Bar's
streams and time of day. The variant's record and `TempleShip_TempleIm_2001.upk` stay. The record is not in
rotation.

## Runs

### Run 1 (6 November, 14:44 to 14:52)

A new campaign, whose first mission loaded the test slot. The user drove and pressed F9 for shots, with notes typed in
the console. Claude read the shots and the log (the lab's `Launch.log`, opened 14:44:10, closed 14:52:37 when the
user quit; read only).

**The log:**
- `IncrementHistory` names `TempleShip_TempleIm_2001` (the test slot). `TempleShip_Stream`, the arrival cinematic and
  the patch load at travel, and `patch_hide_randomized_objects` is streamed in after them. No crash.
- `copied 4 of 4 pieces, each to its own pose`: 0.0000 units and 0 rotation units off, at load and 5 s later. All
  four copies collide, block and block vision.
- `hid 2 of 2 exact targets` (`XComDestructibleActor_206` and `_208`), with collision off.
- The copier (4 copies, pad 96), the hider (2 targets) and the tile seeds (4 boxes, 280 tiles) each rebuilt their
  tiles, and the rebuilds finished.
- One new warning: the game cooked the psi device's convex collision at scale 1 for the spawned copy
  ("set PreCachedPhysScale on the mesh"). The copy's scale (2.5) is set just after it spawns. Nothing seen in game
  points to it.

**In the game:**
- The arrival cinematic played ("yes the intro landing cinematic worked"). The mission starts as an abduction on
  Temple's map: "Neutralize hostile targets", turn 1.
- **Laser barriers** (14:50:49): "the new piece here seems correct with the right cover spots". It "looks a bit more
  blue-ish than the rest of the map" (F-52).
- **Door walls** (14:46:14 and 14:51:25): "the big walls with the doors seem to be invisible"; "this is where the
  missing door wall is", at tile (33, 18, 7). Cover shields stand on the line where the walls should be, so the walls
  still collide. They are the three `DoorwayBMain` pieces on the line y −7584 (F-51). The patch does not touch them.
- **Psi device copy3** (14:51:58 and 14:52:18): "this new chair thing seems right, but it has no cover behind", and
  "no cover from the front either", at tiles (22, 23, 10) and (22, 26, 10), its two ends (F-53).

**Pass criteria:**
1. **Passes.** The map loads, with Temple's streams and the patch.
2. **Passes.** The copies stand as posed.
3. **Passes.** Exactly the targets are hidden.
4. **Passes in part.** The shots match the project, and the laser barriers give cover. The psi devices give none at
   their ends, which may be their shape (F-53).
5. **Recorded:** the abduction starts on Temple's map, after the arrival cinematic, with the squad together at the
   south end. The doorway walls are missing (F-51). The run ended on turn 1, so the aliens and the rest of the
   mission weren't seen.

### Run 1b (deployed 15:08): the unedited TempleShip in the test slot

To tell whether the missing walls come from the edit or from running Temple's map in the test slot, the test slot
(`DefaultMaps.ini` line 42) loads `TempleShip` itself. That is the lab's unedited `TempleShip.upk`, with SHA-256
`029bedca…`, the same as the project's source. It has the same streams (0 `TempleShip_Stream`, 1 the arrival
cinematic, 5 `patch_hide_randomized_objects`) and the same time of day, map family and mission type, but no patch:
slot 2 is gone.
- The edit was made by a script that changes only that line and checks that the rest of the file is byte for byte
  the same.
- Backup: `<lab>\patchtool\backups\DefaultMaps.ini.20261106-150847-exp14-run1b-before`.
- If the walls are missing here too, the cause is Temple's map in the test slot, not the edit.

**Result (shot 15:11:18).** The walls are missing here too. The cursor was on the walk by the doorway at tile
(23, 18, 10). The user's note: "invisible in original map so yeah it's probably to do with how we load it, can close
that concern for now. I might try and get a save from before an actual temple mission in the campaign to test
instead next". F-51 comes from loading Temple's map in the test slot, as the first mission's abduction, and is set
aside. A later check of Temple variants can run from a campaign save taken before the real Temple mission, with
Temple's own record (line 182) pointed at the variant.

### Run 2 (deployed 15:29): revision 3 from the user's Temple save

**The project, revision 3** (saved 15:17). The psi device copies are gone. In their place are two copies of the power
core `XComCollectible_56` (`PowerCore2`), which builds in M1 since this afternoon. The other edits are as before.

| What | Piece | Where (x, y, z) | Rotation | Readout tile (x, y, level) |
| --- | --- | --- | --- | --- |
| Added | `XComCollectible_56_copy6` | (51.1, −5803.5, 190.8) | yaw −32768 | (22, 37, 10) |
| Added | `XComCollectible_56_copy7` | (50.1, −6955.5, 194.0) | 0 | (22, 25, 10) |
| Added | `XComDestructibleActor_9_copy4` (laser barrier) | (1197.6, −6994.1, 0) | 0 | (34, 25, 7) |
| Added | `XComDestructibleActor_9_copy5` (laser barrier) | (−1105.9, −6989.5, 0) | 0 | (10, 25, 7) |
| Deleted | `XComDestructibleActor_206`, `_208` (low covers) | (±, −7056, 0) | — | (34, 24, 7), (10, 24, 7) |

**Compile:** 2 deleted, 4 added, no errors. Two `collectible` warnings: the core copies break at their first damage,
as the map's cores do, but are not loot. The spec is [`templeimproved.json`](../../tools/patch/examples/templeimproved.json),
with `map.timeOfDay` `None` and `map.intro` `false` as before.

**Build and deploy** (`patchtool all ... -Slot 2 -Force`; `-Force` because run 1's patch was there, which is backed
up first):
- 21 s build and an 8 s cook, with only the known `HQSound_MCMusic` error. The patch is 133,265 bytes, and its
  script has the collectible change ("copied collectible").
- `TempleShip_TempleIm_2001.upk` is seeded on 128 of 250 planned tiles; the other 122 already had low bits.
- `DefaultMaps.ini` line 184 (the record) and line 42 (the test slot) stream the patch in slot 2 again. A fresh
  campaign's first mission is the variant again, as in run 1.

**The user's save.** The user put a save from an older campaign in the shared profile
(`My Games\...\SaveData\save1`, 15:12). It is from LWR v2.01.14, Ironman, Impossible, game 199, saved 23 January
2026. It is a tactical save inside the Temple mission. Its header holds the map to open:
`open TempleShip?...StreamingMap0=TempleShip_Stream?StreamingMap1=CIN_TP12A_ArriveTempleShip?StreamingMap2=?...
StreamingMap5=patch_hide_randomized_objects?LoadingSave`.
- A loaded save streams the maps its URL names (`XComTacticalGame` `PendingMatch`: `AddStreamingMapsFromURL`), not
  those of `DefaultMaps.ini`. Its checkpoint also names the map's actors under `TempleShip`, so the map has to keep
  that name.
- **The save's checksums** are UE3's `appMemCrc` (MSB-first CRC-32):
  - the header's over its used bytes (527, the length at offset 1016, the CRC at 1020);
  - the body's (from offset 1024) at offset 519.
  Both recomputed exactly from the user's file.

**Setup** (scratch script `temple_save_setup.py`, lab only):
1. **The lab's `TempleShip.upk` is now the seeded variant** (SHA-256 `543c2cd6…`).
   - The original was checked (`029bedca…`) and backed up first to
     `<lab>\patchtool\backups\TempleShip.upk.20261106-152949-original`.
   - While it stays, Temple's map must load with the patch, which rebuilds the seeded tiles. Without the patch,
     the 128 seeded tiles would block (F-42), as they would through Temple's own record (line 182) or run 1b's
     setup. Put the backup back to undo it.
2. **The lab's `SaveData\save6`** is a copy of the user's save with `StreamingMap2=patch_templeship_templeim_2001`
   in its URL.
   - The header grew to 557 bytes and its CRC was recomputed. The body and its CRC are unchanged.
   - It was re-parsed and both CRCs checked. The user's own `save1` is untouched (SHA-256 `f4f4ae25…`, the same
     before and after).

**What to look at:**
1. **The save loads**, from the older LWR version, with no crash. The log should show the patch streamed in, and:
   - `copied 4 of 4 pieces`, with two `copied collectible` lines;
   - `hid 2 of 2 exact targets`;
   - the seeds' rebuild.
2. **The doorway walls (F-51)** at tile (33, 18, 7) and along y −7584: are they drawn in the real mission?
3. **The power cores** at (22, 25, 10) and (22, 37, 10): pose, cover, and, if the user likes, one shot at a copy.
   It should blow up at the first hit, as the map's own cores do.
4. **The laser barriers and the deleted low covers**, as in run 1.

**Result (15:31 to 15:33; one shot, 15:33:34).** The save loaded without a crash: "End the alien invasion", turn 1,
in the older LWR campaign.
- The log has `LoadMap: TempleShip?...StreamingMap2=patch_templeship_templeim_2001`. The patch streamed in.
- Both cores logged `copied collectible ... breaks at its first damage; not loot`, then `copied 4 of 4 pieces`,
  0.0000 units off.
- `hid 2 of 2 exact targets`, and the copier, hider and seed rebuilds all finished. All four copies collide, block
  and block vision.

The user's note at copy7, tile (22, 25, 10): "door walls are invisible like before and the power cores I placed can
be walked through and provide no cover".
- **The walls (F-51)** are missing in the real mission too, so the test slot is not the cause.
- **The cores (F-54).** The map's own power cores block and give cover: their tiles are occupied, and the tiles
  beside them have high cover (`0x4004`, `0x0101`). Both meshes have simple collision. The likely cause: a tactical
  save holds the map's tile data, and loading it puts back the data from a game without the patch, over our rebuild
  (the checkpoint is read at 11.60 s; the rebuilds were queued at 11.36 s). Not verified.

**Lab files after run 2.**
- `TempleShip.upk` was put back to the original at 15:35 for run 3, after both hashes were checked.
- `SaveData\save6` (the edited save) stays.

**A patchtool fault found here (T-11), fixed.** The redeploy at 15:28 took the test slot for "TempleShip's record",
since run 1b had named the test slot `TempleShip`. It rebuilt the variant's record (line 184) from it, with map
family `URB_Bar` and an abduction. The record isn't in rotation, so nothing loaded it. After the fix, a `deploy` at
15:39 rebuilt line 184 from Temple's own record (line 182). It is the same as run 1's, and no other line changed.

### Run 3 (set up 15:35): the user's HQ save, the unedited Temple, started normally

The user added a second save to the shared profile, `save_before_temple`. It is a Geoscape save from the same
campaign (LWR v2.01.14, Ironman, game 199, "2:23 am April 6 2031"), before the Temple mission starts. It opens
`Command1`, so the Temple's map is picked from `DefaultMaps.ini` when the mission starts, and the mission starts fresh
(no tactical checkpoint).
- **The user's question:** with the unedited map and a normal start, are the doorway walls drawn?
- **Setup** (scratch script `temple_hq_setup.py`, lab only):
  - the lab's `TempleShip.upk` is the original again;
  - Temple's own record (line 182: `TempleShip`, `eMission_Final`, in rotation; the only Final record in rotation)
    is untouched;
  - the save is copied byte for byte to the lab's `SaveData\save7` (SHA-256 `338a7dc8…`).
- **A note for variants:** `XGPlayer` reorders the squad's spawn points when the map's display name contains
  "TempleShip". Pointing Temple's own record at a variant keeps that display name.
- **Next:** if this run shows the walls, a run from the same save with Temple's record (line 182) pointed at the
  variant. A normal start also avoids F-54.

**Result (15:40 to 15:44; the user's account, no shots).** The log (opened 15:40:17, closed 15:44:33) shows this
order:
- 7 s: a Temple tactical save loaded and was left;
- 29 s: the HQ save loaded;
- 73 s: `SeamlessTravel to: TempleShip`, a fresh mission with `TempleShip_Stream` and the arrival cinematic;
- 177 s: back to the menu, and at 182 s the Ironman save of the mission was loaded;
- 257 s: the game exited.

The user's notes:
- "right after intro, I could see the door walls"
- "but then they disappeared and my game started behaving weirdly, moving in odd staggered ways every time i moved
  the mouse or panned the camera"
- "I saved and reloaded and that made the weird staggered auto-movement of the camera go away, but the walls and doors
  stayed invisible"
- "it was the original unedited map"

What this tells us about F-51:
- The map draws the walls, and something hides them at run time after the intro. The likeliest candidate is the
  game's building and prop hiding (`XGLevel.UpdatePropHidingAndBuildingHiding`, native, every tick). It hides a
  building's floors and walls by the cursor's floor. The doorway walls are floor 1 of building 10698, and the camera
  stagger fits a cursor jumping between floors. Not verified.
- Ruled out as lab differences: the lab's `Engine.upk` is LWR's console variant
  (`Engine.upk.renamethistoenableconsole`). Export by export, it differs from LWR's normal one only in
  `Console.ConsoleCommand`. The lab's own generated settings (`-nohomedir`) differ from the user's live profile only
  in graphics options and in sections it hasn't written out. The other lab-only files are our patches and maps. The
  save itself is from an older LWR (v2.01.14); the lab runs the current one.

**Lab state after run 3:**
- `SaveData\save7` is now the Ironman save of the mission (15:44, "Operation Avenger (Temple Ship Assault)").
- `save6` (run 2's edited save) is gone: the game keeps one save per Ironman campaign, and all are game 199.
- The user's HQ save in the shared profile is unchanged (SHA-256 `338a7dc8…`), so it can be copied in again.

**Next check (no deploy needed):** load `save7`. In the console:
- `ToggleBuildingAndPropHiding`: do the walls come back? Run it again to switch the hiding back on.
- `ShowCursorFloor`: which building floor does the cursor report by the doorways?

Then F9.

**Run 3b (15:51 to 15:54, `save7`, the console).**
- The log has `ToggleBuildingAndPropHiding` three times (at 43, 55 and 56 s). The user: "Toggle prop hiding did not
  make the walls show".
- Shot 15:53:41 (`ShowCursorFloor`) reads "Cursor @ (1103.40, -7728.70, 64.00) Inside : XComBuildingVolume_10", just
  south of the doorway line. The walls are not drawn, and cover shields stand on their line.
- The bottom of the screen reads "LWR v2.06.03": the lab runs LWR 2.06.03, and the save is from 2.01.14.

So the building and prop hiding (by floor) is not what hides them. Also ruled out:
- the logs show no damage to any doorway piece in runs 3 and 3b;
- `TempleShip_Stream` holds no pieces (8 exports: an empty sequence and an `XComVisGroupData`);
- building volume 10 (two floors) has no external mesh groups and no vis groups to hide.

The next candidate is the cutout box (`XComCutoutBox`). It cuts out and cuts down walls around the cursor with a
material mask, at a height worked out from the building's lowest floor while the cursor is inside a building. That
path is separate from the prop hiding. A mask set below the walls would leave them colliding (the shields) but not
drawn, and cinematics don't use it, which fits "visible after the intro".

**Run 3c (the same session, the console).**
1. With the cursor where the readout doesn't say "Inside: XComBuildingVolume_10", the walls are still not drawn
   ("no").
2. `CutoutBoxWidth 0` (logged at 279 s): no change ("no").
3. `DumpCutoutActors` (logged at 292 s) wrote nothing to the log while the game ran. The game's log runs behind
   (T-06); to be read after it closes.

So neither the building hiding nor the cutout box hides the walls. They are hidden once, after the intro, whatever
the cursor does. Also read, without finding the cause:
- Temple's Kismet hides the gate doors (`XComLevelActor_7` to `_9` at y −2064, `_10` at y 5520) when a gate opens,
  not these walls. These are the doorway pieces `XComDestructibleActor_135`, `_146` and `_188` with the interactive
  doors `XComInteractiveLevelActor_15`, `_1` and `_0` on y −7632.
- LWR 2.06.03's `RebalanceMutator` (decompiled from a copy in `<lab>\reference\lwr-copy`) has Temple code:
  `TempleReveal` (wakes pods), `OpenDoors` (opens a door by a unit), `TempleDelayOnLoad` (grenades), spawn and cover
  helpers, and `SetupUFORoof` (keeps units off UFO roofs). None hides level pieces, and none of its `SetHidden` calls
  touches them.

Nothing in the lab differs from the user's live LWR 2.06.03 except the console `Engine.upk` and graphics settings.
So the hiding is most likely what LWR 2.06.03 (or the game itself) does on the Temple, not our tools. A patch-side
probe that logs the doorway pieces' hidden flags over time would show how they are hidden.

### Run 4 (deployed 16:01): revision 3 as a new campaign's first mission, a fresh start

**Why:** F-54 says run 2's cores could be walked through because the tactical save put back its own tile data, from
a game without the patch, over our rebuild. A fresh mission start has no checkpoint to load, so the tiles should be
the ones the patch rebuilt. This run checks that, with the same project (revision 3) through the test slot, as in
run 1.

**What changed for this run:**
- `XComMapEdCopier.LogCopyTiles` now starts at the copy's base (`B.Min.Z + 8`; it was `+ 80`). It logs, for every
  destructible copy, whether each tile under its box is occupied (`o`) and fully occupied (`F`). From 80 units up, it
  skipped the tile a core on the raised walk stands in, so run 2's log couldn't show it.
- [`templeimproved.json`](../../tools/patch/examples/templeimproved.json) sets `bLogTiles=True` on the copier. That is
  already the default; the spec now says it.

**Build and deploy** (16:01, game closed), the same command as run 2:
```
pwsh -File tools\patch\patchtool.ps1 all tools\patch\examples\templeimproved.json -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0' -Slot 2 -Force
```
- Script: `make` with 0 errors. Build 20 s, cook 8 s, with only the known `HQSound_MCMusic` error. The patch is
  133,470 bytes (run 2's was 133,265).
- `TempleShip_TempleIm_2001.upk` is seeded on 128 tiles, as in run 2.
- The record (line 184) and the test slot (line 42) already streamed the patch; nothing else in `DefaultMaps.ini`
  changed.
- **Checked after the deploy:**
  - Line 42 has `Name="TempleShip_TempleIm_2001"` and `TimeOfDay=eMissionTime_None`.
  - It streams `TempleShip_Stream`, `CIN_TP12A_ArriveTempleShip`, `patch_hide_randomized_objects` and
    `patch_templeship_templeim_2001`.
  - It keeps `MapFamily="URB_Bar"` and the abduction.
  - The deployed patch has `bLogTiles=True`.
  - The lab's `TempleShip.upk` is the original (`029bedca…`). The variant loads from its own file.

**What to look at:** a new campaign; the first mission loads the variant after the arrival cinematic. Shots (F9):
1. **The power cores** at readout tiles (22, 25, 10) and (22, 37, 10). Do they block a soldier's path (the move
   preview goes around them)? Do the tiles beside them show cover shields?
2. **The laser barriers** at (34, 25, 7) and (10, 25, 7), as in run 1.
3. If the user likes, one shot at a core: it should blow up at the first hit, as the map's own cores do.

**In the log:**
- `copied 4 of 4 pieces`, with two `copied collectible` lines.
- One `tiles under ... XComMapEdDestructible ... levels a..b` line for each core, followed by `level N:` lines. The
  log's levels are grid levels, one below the readout's, so a core on the walk stands in grid level 9.
- If the cores' tiles read `o` in the log but the cores don't block in the game, then something besides F-54 is at
  work.

**Result (16:06, the game still running; the user's own four screenshots, no F9).**
- The log (opened 16:06:49):
  - `IncrementHistory` names `TempleShip_TempleIm_2001`;
  - both cores logged `copied collectible`;
  - `copied 4 of 4 pieces` and `hid 2 of 2 exact targets`;
  - the copier, hider and seed rebuilds finished at 25.36 s.
- The new tile lines (29.63 s) show each core's own tile fully occupied (`oF`) at grid levels 9, 10 and 11:
  (22, 37) and (22, 25). The tiles around them on the walk are occupied at level 9. Each barrier's tiles are fully
  occupied at levels 6 and 7: x 33 to 35 (copy4) and 9 to 11 (copy5), at y 24 and 25.
- The user: "they appear fine now, provide cover all around and can be walked around. same with the laser
  batteries. only thing that would be nice to improve is their weird blue-ish hue".
  - The user's shots 1 and 2 are the copies: a laser barrier, bluish violet in a warm dark corner, and a core. Shots
    3 and 4 are the map's own pieces: a bank of three barriers by a bright light, and a core.

**Pass criteria:** 1 to 3 pass, as in run 1. Criterion 4 passes: the pieces match the project and give cover. Their
tone doesn't match the map's (F-52).

**Why the copies look bluer (F-52), read from the map and the game's packages:**
- A copy has no baked lighting. It is lit live by its light environment, which takes the direct light of the
  map's lights near it, as a unit is lit. The map's own pieces carry the editor's light build, with the warm light
  bounced off the ship's floors and walls.
- The warm-dark corners around the copies are mostly that bounce. The direct lights that reach the copies are:
  - two cyan spotlights per doorway on the line y −7623 (colour 139, 216, 229; brightness 0.5; radius 1472; a 45°
    cone, pointing north and south and 50° down). `SpotLight_44` has barrier copy4 27 to 29° off its axis, at 675
    units. `SpotLight_40` has copy5 the same way, and `SpotLight_41` has core copy7, at 707 units;
  - greenish-white spotlights by the south wall (240, 255, 195 and 255, 235, 178; brightness 0.7);
  - greenish points (113, 125, 97) and dim orange ones (154, 85, 62) by the cores.
- The cyan doorway spotlights are likely what tips the copies toward blue: little else at the copies is that bright.
- Not the cause:
  - the sky light (110, 99, 156; brightness 0.3) has the BSP, Static and Dynamic channels all off;
  - the map's dominant light is warm (203, 167, 123; brightness 6);
  - the 1,190 lights that Lightmass made from glowing surfaces have a radius of 160, and none reaches a copy;
  - the light environment's defaults (`Engine.upk`, `XComDestructibleActor`) have a near-black ambient shadow and
    no ambient glow.
- How the copy's light is drawn: our copies keep the engine's default. The strongest light comes as one synthesized
  directional light, and the rest as a two-colour "sky light" (upper and lower half). The game's own movable level
  pieces lit this way, `XComInteractiveLevelActor` (doors), use a different setting: no synthesized directional
  light, and all the light as a spherical-harmonic light (`bSynthesizeSHLight`), which the engine describes as
  higher-quality secondary lighting.

**What could make them stand out less (not yet tried):**
1. The game's door setting for our copies' light environments (SH light, no synthesized directional light).
2. A per-map warm ambient for the copies (`AmbientGlow`, and `AmbientShadowColor` for the side away from the
   light), tuned by eye against the map's own pieces.
3. Both, side by side: several barrier copies in one corner, each with one setting, so one run compares them.

A baked lightmap for a copy would need a lighting build of the map, which the toolchain can't do (F-52).

### Run 5 (deployed 16:26): the copies' light, side by side (F-52)

**Why:** run 4's copies have a "weird blue-ish hue". Run 4's reading of Temple's lights points to the cyan doorway
spotlights, without the warm bounce that the baked pieces carry. This run tries the light settings that could bring
the copies closer, side by side, in one mission.

**What changed:**
- [`XComMapEdDestructible.uc`](../../unrealscript/XComMapEd/Classes/XComMapEdDestructible.uc): `SetLighting(Mode,
  bBooleanShadow, Glow)` sets the copy's light environment, then calls `ResetEnvironment` and reattaches the mesh.
  - Mode 0 is the engine's default (a synthesized directional light and a two-colour sky light).
  - Mode 1 is the game's door setting: no synthesized directional light, all of it as an SH light.
  - `bBooleanShadow` shadows the map's lights by the static world with an on/off test. That's the engine's default,
    which `XComDestructibleActor` turns off.
  - `Glow` is the light environment's `AmbientGlow`.
  - `LightingText` reads the settings back for the log.
- [`XComMapEdCopier.uc`](../../unrealscript/XComMapEd/Classes/XComMapEdCopier.uc): `CopyLights(i)` gives copy i a
  setting. A copy with `bTuned` follows `TuneMode`, `bTuneBooleanShadow` and `TuneGlow` instead. The copier checks
  them every half second, so the console's `set XComMapEdCopier ...` changes the tuned copies while the game runs (the
  game accepts `set`, F-35).
  - It logs `lit <copy> (<label>) mode ...` for each copy at load and after a load.
  - It logs `5 s after load, <copy> ...` with the settings read back, and `tune changed: ...` on each change.
- [`exp14light.json`](../../tools/patch/examples/exp14light.json): written by hand from the project's compiled spec
  (`temple_improved` revision 3).
  - It has the same four copies and the same two hidden low covers, plus six laser barrier copies
    (`XComDestructibleActor_9`, yaw 0, on floor the baked tiles show free).
  - It ships as `TempleShip_EXP14Light`. The project's own record and patch stay.

| Copy | Readout tiles (x, y; level 7) | Light |
| --- | --- | --- |
| `XComDestructibleActor_9_copy4` (the project's) | 33 to 35, 24 to 25 | engine default: the control, east |
| `lighttest_sh` | 31 to 33, 27 to 28 | mode 1, the game's door setting |
| `lighttest_sh_shadow` | 36 to 38, 27 to 28 | mode 1, with on/off environment shadowing |
| `XComDestructibleActor_9_copy5` (the project's) | 9 to 11, 24 to 25 | engine default: the control, west |
| `lighttest_glow` | 8 to 10, 27 to 28 | engine default, with a warm glow (0.06, 0.035, 0.03) |
| `lighttest_tuned_west` | 12 to 14, 27 to 28 | tuned |
| `lighttest_default_north` | 40 to 42, 57 to 58 | engine default, just south of the map's own barrier `XComDestructibleActor_9` |
| `lighttest_tuned_north` | 40 to 42, 64 to 65 | tuned, just north of it |

The two cores keep the engine's default. The tuned copies start as mode 1 with no environment shadowing and no glow,
like `lighttest_sh`. The console changes them:
- `set XComMapEdCopier TuneGlow (R=0.06,G=0.035,B=0.03,A=1)`: a warm glow. Larger numbers are brighter, and the
  ratio of R, G and B is the tint.
- `set XComMapEdCopier TuneMode 0`: the engine's default draw (`1` for the door setting).
- `set XComMapEdCopier bTuneBooleanShadow True`: on/off environment shadowing.

**Build and deploy** (16:26, game closed):
```
pwsh -File tools\patch\patchtool.ps1 all tools\patch\examples\exp14light.json -Stream 'URB_CommercialAlley_EWI (Commercial Alley Redux) |0' -Slot 2
```
- `make`: 0 errors and 0 warnings. A 20 s build and a 9 s cook, with only the known `HQSound_MCMusic` error. The patch
  is 137,211 bytes, and its cooked copier has the 10 `CopyLights` entries and `TuneMode` 1.
- `TempleShip_EXP14Light.upk` is TempleShip with 310 of the 674 planned tiles seeded (364 already had low bits).
- `DefaultMaps.ini`:
  - line 184 is the new record, not in rotation, with the patch in slot 2;
  - the project's record moved to line 186, unchanged;
  - the test slot (line 42) now names `TempleShip_EXP14Light` and streams the new patch in slot 2. Its slots 0, 1 and
    5 (`TempleShip_Stream`, the arrival cinematic, `patch_hide_randomized_objects`) are as before.
  - Backups: `<lab>\patchtool\backups\DefaultMaps.ini.20261106-162621` and `-2`.

**What to look at** (a new campaign; the first mission loads the test). F9 at each:
1. **East**, by copy4: copy4 (default), `lighttest_sh` and `lighttest_sh_shadow`. Which sits best with the floor and
   walls around it?
2. **West**, by copy5: copy5 (default), `lighttest_glow` and `lighttest_tuned_west`.
3. **North**, at the map's own barrier between `lighttest_default_north` and `lighttest_tuned_north`: does either
   copy match the baked one?
4. **Tuning:** `set` commands as above, with an F9 after each, until a tuned copy matches. Both tuned copies follow.

**Not yet known:**
- whether changing the draw mode and the glow while the game runs takes effect (`ResetEnvironment` is the engine's
  call for it; the log reads the settings back);
- whether `set` takes a struct value such as `TuneGlow`.

If the tuned copies don't change, the fixed settings still compare.

**In progress (16:28 onwards; the game running).**
- The log has `copied 10 of 10 pieces` and a `lit` line for each copy, with the settings read back 5 s later as set.
- The console's `set` works on the copier, struct values too: `TuneMode 0` and `1` (154.75 and 159.88 s) and
  `TuneGlow (R=0.1,G=0.1,B=0.1,A=1)` (202.42 s). Each relit the two tuned copies.
- Shots 16:32:44 and 16:32:49, with the note "tried using the TuneGlow and nothing appears to have changed here".
  - They look like the north group: a dark, warm grey barrier (likely the map's own `XComDestructibleActor_9`)
    between two violet copies.
  - No cyan light reaches that spot: only orange (154, 85, 62) and greenish ones (113, 125, 97; 150, 176, 110). So
    the cyan doorway lights aren't the whole cause.
- **A likelier cause:** Temple's sky light (110, 99, 156, a lavender; brightness 0.3) switches off only its BSP,
  Static and Dynamic channels. A light's default channels also include `CompositeDynamic` (UDK `LightComponent.uc`),
  so it keeps that one. Lightmass's generated area lights use the same setting to light only objects lit live by a
  light environment. So the sky light is a lavender fill for units and our copies, which the baked pieces never get.
  Not yet verified: the next check turns it off from the console (`set SkyLightComponent Brightness 0`).

**Result of run 5 (16:28 to about 16:40; shots 16:32:44, 16:32:49 and 16:38:57; the log read while the game ran).**
- `set XComMapEdCopier TuneGlow (R=1,G=0,B=0,A=1)` (531.68 s) logged as applied to both tuned copies, and nothing
  turned red. `AmbientGlow` has no visible effect here, at least when set in play.
- `set SkyLightComponent Brightness 0` (556.87 s). The user: "turning the skylight brightness to 0 did make the lower
  piece look a bit better. still blue tinted but doesn't stand out as much now", and "the soldiers were too dark
  without it, but the items looked much better".
- Mean colour of each barrier's body, from the full-size shots:

| Barrier | Sky light on (16:32:44) | Sky light off (16:38:57) |
| --- | --- | --- |
| `lighttest_default_north` (lower copy) | (37, 24, 54): hue 266, saturation 0.56, value 0.21 | (27, 15, 39): hue 270, saturation 0.61, value 0.15 |
| the map's own `XComDestructibleActor_9` | (36, 26, 39): hue 289, saturation 0.33, value 0.15 | (36, 25, 38): hue 290, saturation 0.33, value 0.15 |
| `lighttest_tuned_north` (upper copy) | (37, 24, 53) | (37, 24, 53): unchanged |

- With the sky light off, the lower copy is exactly as bright as the original, but bluer and more saturated. It
  still stands within reach of a cyan spotlight (`SpotLight_38`, about 1,180 units).
- The tuned copy didn't follow the sky light's change. Its settings had been changed in play four times, each with
  `ResetEnvironment` and a reattach of its mesh. The untouched lower copy did follow, so the in-play changes likely
  froze that copy's light. Run 6 no longer reattaches the mesh.

**So:** the sky light is a lavender fill for live-lit objects only (`CompositeDynamic`). The copies should leave it
out, and the soldiers keep it.

### Run 6 (deployed 16:43): the copies leave out the sky light, by lighting channel

**What changed** (the user: "Can we disable the skylight for our placed items only?"):
- `XComMapEdDestructible.SetLighting` takes `Channels`, which sets the light environment's own lighting channels
  (`bOverrideOwnerLightingChannels`, `OverriddenLightingChannels`):
  - **A (1):** BSP, Static and Dynamic: every placed light, and dynamic ones such as explosions, but not lights that
    are only in `CompositeDynamic`;
  - **B (2):** BSP and Static only, in case the engine lets `CompositeDynamic` lights into any environment that has
    the Dynamic channel.
  It no longer reattaches the mesh, and `LightingText` logs the mesh's and the environment's channels.
- `XComMapEdCopier`: `CopyLights(i)` has `Channels`, and the tune values have `TuneChannels`.
- [`exp14light.json`](../../tools/patch/examples/exp14light.json): the same places as run 5, with no tuned copies.

| Copy | Readout tiles (x, y; level 7) | Light |
| --- | --- | --- |
| `XComDestructibleActor_9_copy4` (the project's) | 33 to 35, 24 to 25 | as before: the control, east |
| `east_a` | 31 to 33, 27 to 28 | A |
| `east_b` | 36 to 38, 27 to 28 | B |
| `XComDestructibleActor_9_copy5` (the project's) | 9 to 11, 24 to 25 | as before: the control, west |
| `west_a_sh` | 8 to 10, 27 to 28 | A, with the door draw (mode 1) |
| `west_b_sh` | 12 to 14, 27 to 28 | B, with the door draw (mode 1) |
| `north_a` | 40 to 42, 57 to 58 | A, just south of the map's own barrier |
| `north_b` | 40 to 42, 64 to 65 | B, just north of it |
| core `XComCollectible_56_copy7` | 22, 25 (level 10) | A |
| core `XComCollectible_56_copy6` | 22, 37 (level 10) | B |

**Build and deploy** (16:42 to 16:43, game closed; `patchtool all ... -Slot 2 -Force`):
- `make`: 0 errors and 0 warnings. A 22 s build and an 8 s cook. The cook has the known `HQSound_MCMusic` error and a
  "Mismatched Guid while merging guid caches" warning, from rebuilding a patch of the same name.
- The patch is 139,290 bytes, and its copier has the 10 `CopyLights` entries.
- The seeded map, the record (line 184) and the test slot (line 42) were already right and are unchanged.

**What to look at** (a new campaign; leave the sky light on):
1. **North:** `north_a` and `north_b` against the map's own barrier between them.
2. **East and west:** the A and B copies against the project's copies 4 and 5 (the controls).
3. **The cores** (A at (22, 25), B at (22, 37)).
4. **The soldiers keep their usual light.**

**In the log:** a `lit` line for each copy, and 5 s later its mesh and environment channels read back. If neither
variant drops the lavender, the engine doesn't choose its lights by these channels, and the next step is another
way: per-copy light lists, or the sky light itself.

**Result of run 6 (16:44; the user's own shot of the north group).** The user: "The lower one is lit up like before
and upper one is all black. The lower one looked good when I set the skylight brightness to 0 in game".
- `north_a` (A: BSP, Static and Dynamic) is lit as before, lavender included.
- `north_b` (B: BSP and Static) is black.
- The log reads both settings back as set:
  - the meshes' channels are Dynamic only (`(init Dynamic)`; the defaults' Static doesn't stick, as for the walls in
    F-28);
  - the environments' channels are `(init BSP Static Dynamic)` and `(init BSP Static)`.
- So a light environment takes the map's lights only through the Dynamic channel, and takes the
  `CompositeDynamic`-only sky light with them. Channels can't keep the sky light off our copies alone.

### Run 7 (deployed 16:50): the copies take their light once with the sky light off

**What changed:**
- `XComMapEdCopier`: `CopyLights(i)` has `bNoSkyLight`. At load, `LightWithoutSky` gives those copies a full update,
  even off screen (`InvisibleUpdateTime` 0, `MinTimeBetweenFullUpdates` 0.1), then switches every `SkyLight` off
  (`SetEnabled(false)` and brightness 0).
- `SkyFreeTime` (2 s) later, `SkyBackOn` fixes those copies' light (`bDynamic` off) and switches the sky lights back on
  at their brightness.
- After a save is loaded, the restored copies do the same once.
- The soldiers lose the sky light for those 2 s only, during the load.
- [`exp14light.json`](../../tools/patch/examples/exp14light.json): the same places as before.

| Copy | Readout tiles (x, y; level 7) | Light |
| --- | --- | --- |
| `XComDestructibleActor_9_copy4` (the project's) | 33 to 35, 24 to 25 | as before (with the sky light): the control, east |
| `east_nosky` | 31 to 33, 27 to 28 | without the sky light |
| `east_nosky_sh` | 36 to 38, 27 to 28 | without the sky light, door draw (mode 1) |
| `XComDestructibleActor_9_copy5` (the project's) | 9 to 11, 24 to 25 | as before: the control, west |
| `west_nosky` | 8 to 10, 27 to 28 | without the sky light |
| `west_nosky_sh` | 12 to 14, 27 to 28 | without the sky light, door draw |
| `north_nosky` | 40 to 42, 57 to 58 | without the sky light, just south of the map's own barrier |
| `north_nosky_sh` | 40 to 42, 64 to 65 | without the sky light, door draw, just north of it |
| both cores | (22, 25) and (22, 37), level 10 | without the sky light |

**Build and deploy** (16:49 to 16:50; the game closed at about 16:49):
- `make`: 0 errors and 0 warnings. A 20 s build and an 8 s cook, with the known error and the guid-cache warning.
- The patch is 143,381 bytes. The record and the test slot are unchanged.

**What to look at** (a new campaign; leave the sky light on):
1. **North:** do the two copies now look like the map's own barrier between them, as with the sky light off in run 5?
2. **East and west:** the sky-free copies against copies 4 and 5 (the controls), and mode 0 against the door draw.
3. **The cores.**
4. **The soldiers keep their usual light** once the mission shows.

**In the log:** `sky lights off for 2 s while 8 copies take their light: SkyLight_0 (brightness 0.3, now enabled False
brightness 0)`, then `sky lights back on (1); the light of 8 copies is fixed as taken`.

**Result of run 7 (16:51 to 16:54; shots 16:53:36 to 16:53:56).**
- The log:
  - `copied 10 of 10 pieces` (31.05 s);
  - `sky lights off for 2.0000 s while 8 copies take their light: SkyLight_0 (brightness 0.3000, now enabled False
    brightness 0.0000)`;
  - `sky lights back on (1); the light of 8 copies is fixed as taken` (33.46 s).
- The user's note on the 16:53:36 shot: "looks great now!". The barrier copies in it have the scene's warm brown.
- 16:53:42: the power core copy beside a soldier is a natural dark grey.
- 16:53:47, the north group: both copies look like the map's own barrier between them. Mean colour of each body:

| Barrier | Run 5 (sky light reached the copies) | Run 7 |
| --- | --- | --- |
| lower copy (`north_nosky`, mode 0) | hue 266, saturation 0.56, value 0.21 | hue 283, saturation 0.57, value 0.11 |
| the map's own `XComDestructibleActor_9` | hue 289, saturation 0.33, value 0.15 | hue 286, saturation 0.36, value 0.14 |
| upper copy (`north_nosky_sh`, door draw) | hue 267, saturation 0.55, value 0.21 | hue 286, saturation 0.52, value 0.12 |

  The hue now matches; the copies are a little darker and more saturated. The door draw is marginally closer.
- 16:53:56: the squad on the start platform, normally lit. The soldiers kept the sky light.
- Not checked: whether a copy with fixed light still takes dynamic lights (explosions).

**Sky lights in other maps** (read from the cooked maps with a scratch survey; units-only fills everywhere):

| Map | Sky light | Its channels |
| --- | --- | --- |
| TempleShip | 0.3, (110, 99, 156) | `CompositeDynamic` only (BSP, Static and Dynamic switched off) |
| URB_Bar | 0.75, (89, 107, 160) | `Gameplay_1` only (`CompositeDynamic` switched off too) |
| URB_Boulevard, URB_HighwayBridge | 0.5, (61, 91, 160) | `Gameplay_1` only |
| URB_CommercialAlley | 1, (74, 80, 136) | `Gameplay_1` only |
| URB_PierA | 1, (107, 136, 193) | `Gameplay_1` only |
| AlienBase01, AlienBase02 | 0.5 and 0.75, blue-violet | `Gameplay_1` only |
| DLC1_2_CnfndLight, DLC2_2_Deluge, EWI_HQAssault, EWI_ChryssalidHive | none | — |

Every sky light found lights only units: none lights the baked world. Most use `Gameplay_1`, which our copies' meshes
(`Dynamic` only) don't share, and no tint was ever seen on the Bar. Temple's keeps the engine's default
`CompositeDynamic`, which every light environment takes. So the fix is generic in rule but acts on Temple-like maps:
leave out a sky light that lights no baked surface (no BSP or Static channel) but reaches light environments
(`CompositeDynamic` or `Dynamic`). Copies of pieces the map itself lights live (doors, `XComInteractiveLevelActor`)
should keep it, since their originals have it too.

### Run 8 (deployed 17:13): the user's project with the generic rule

The user asked to apply the fix to all map edits, not per copy.

**What changed:**
- [`XComMapEdSkyFree.uc`](../../unrealscript/XComMapEd/Classes/XComMapEdSkyFree.uc) (new): one per level. Pieces
  register with `Add`.
  - It looks at the map's sky lights once. It leaves out only one that lights no baked surface (BSP and Static off)
    but reaches light environments (`CompositeDynamic` or `Dynamic`), and logs every sky light it finds and its choice.
  - When there is one, the registered pieces' light environments update even off screen while it is switched off for
    2 s. Then their light is fixed as taken (`bDynamic` off), and the sky light goes back on at its brightness.
  - Pieces added during a pass join it; after a save is loaded, the restored pieces start another.
  - On a map with no such sky light (most maps, whose sky light is in `Gameplay_1`) nothing changes and nothing is
    fixed.
- `XComMapEdCopier` registers every copy of a baked piece: destructibles, walls and plain level pieces. Copied doors
  keep the sky light, since the map lights its own doors the same live way. Base-map pieces moved as themselves keep
  their baked light. `bKeepSkyLight=True` opts out.
- `XComMapEdSpawner` registers its spawned pieces the same way, with its own `bKeepSkyLight`.
- Removed the settings the trials showed to be of no use: the glow, the lighting-channel override, the console tuning
  and the per-copy sky option. `CopyLights` keeps the draw mode and the on/off shadowing for trials.
- [`exp14light.json`](../../tools/patch/examples/exp14light.json) is regenerated in the new form: the test barriers
  compare the draw modes, and every copy leaves out the sky light.

**Build and deploy** (17:13, game closed; `patchtool all tools\patch\examples\templeimproved.json -Stream ... -Slot 2
-Force`):
- `make`: 0 errors and 0 warnings. A 21 s build and an 8 s cook, with the known error and the guid-cache warning.
- The patch is 142,979 bytes and holds `XComMapEdSkyFree`. 128 tiles are seeded.
- The test slot (line 42) is back on `TempleShip_TempleIm_2001` with its patch in slot 2 (backup
  `DefaultMaps.ini.20261106-171321`).

**What to look at** (a new campaign):
1. The power cores and laser barriers match the map's own, as in run 7.
2. The soldiers keep their usual light.
3. If the mission allows, an explosion next to a copy: does the flash light it? A copy's light is now fixed after load.

**In the log:** `sky light SkyLight_0 ... channels (CompositeDynamic ): lights units only and reaches light
environments; our pieces leave it out`, then `sky lights off (1)` and `sky lights back on (1); the light of 4 light
environments is fixed as taken`.

**Not checked in the game:** a Bar edit. By its channels (`Gameplay_1` only) the Bar's sky light isn't left out, so
copies there keep their light as before and nothing is fixed; the log line says so.

### Run 9 (deployed 17:56): revision 4, four consoles in place of the power cores

**The project, revision 4** (saved 17:50). The power cores are gone. In their place, the user laid two copies of the
alien console `XComDestructibleActor_60` (`alienConsoleB3`) on their sides (roll −16384), stacked back to back at the
north core's place, and pasted the pair at the south core's place. The laser barriers and the two deleted low covers
are as before.

**The compiler refused it** (`template-changed`): `XComDestructibleActor_60_copy11` named its template's mesh
component twice. This is T-12, a viewer bug:
- The paste named each pasted piece after its original plus one serial per paste. Both consoles of the pair are copies
  of `XComDestructibleActor_60`, so both pasted ones were named `XComDestructibleActor_60_copy11`.
- The project keeps an actor's pieces together by name, so the save merged them into one actor: one pose, the mesh
  listed twice. The fourth console's pose was lost.

**Rebuilt for this build** (the user's project file is unchanged; scratch copy `r4-repaired\project.json`):
- copy11 has the same rotation as copy9, so the paste was a plain shift, (3.1728, −1246.0316, 0.3462).
- Applied to copy10, it gives the lost console: `XComDestructibleActor_60_copy12` at (52.3618, −7009.2446,
  248.6395), rotation (0, −32375.874, −16384).
- copy11 keeps one component.

| Added | Where (x, y, z) | Rotation |
| --- | --- | --- |
| `XComDestructibleActor_60_copy9` | (49.0918, −5760.6284, 248.2933) | (0, 392.126, −16384) |
| `XComDestructibleActor_60_copy10` | (49.189, −5763.213, 248.2933) | (0, −32375.874, −16384) |
| `XComDestructibleActor_60_copy11` | (52.2646, −7006.66, 248.6395) | (0, 392.126, −16384) |
| `XComDestructibleActor_60_copy12` (rebuilt) | (52.3618, −7009.2446, 248.6395) | (0, −32375.874, −16384) |
| laser barriers `XComDestructibleActor_9_copy4`, `_copy5` | as before | as before |

**Compile:** 0 moved, 2 deleted, 6 added, no warnings. The spec is
[`templeimproved.json`](../../tools/patch/examples/templeimproved.json). Its `editor` block says revision 4; the
fourth console comes from the repair above, not from the saved file.

**Build and deploy** (17:56, game closed; `patchtool all ... -Slot 2 -Force`):
- `make`: 0 errors and 0 warnings. A 20 s build and an 8 s cook, with the known error and the guid-cache warning.
- The patch is 144,228 bytes, with the copier placing 6 pieces. 146 tiles are seeded.
- The test slot (line 42) streams the project's patch as before.

**What to look at** (a new campaign):
1. The four consoles, two at each core place: as posed, lit like the map's own pieces, blocking and giving cover.
2. The laser barriers as before.
3. The soldiers keep their usual light.

**The saved project still has the merged actor.** After the viewer fix, either the south pair is pasted again from the
north one and saved, or the project is written as revision 5 with the rebuilt console.

### Run 10 (deployed 18:03): revision 5, the consoles re-pasted with the fixed viewer

The user reloaded the viewer (with the T-12 fix), pasted the south pair again and saved revision 5 (18:02). The south
pair is now two actors, `XComDestructibleActor_60_copy12` at (47.1094, −7012.8936, 248.1795) and `_copy13` at
(47.0122, −7010.309, 248.1795). The north pair (`_copy9`, `_copy10`), the laser barriers and the two deleted low
covers are as in revision 4.
- **Compile** (straight from the saved file): 0 moved, 2 deleted, 6 added, no warnings.
- **Build and deploy** (18:02 to 18:03; `patchtool all ... -Slot 2 -Force`): an 8 s cook with the known error and the
  guid-cache warning; the patch is 144,228 bytes, the copier places 6 pieces, and 146 tiles are seeded. The test slot
  (line 42) streams the project's patch.
- **What to look at:** as run 9.

**Result of run 10 (18:04 onwards; the user's own shot).** The user: "if I hit one of these with a grenade (has to be
right on top of, or "inside" the new double console pieces) they revert back to the blueish lighting". The shot shows
a hit console copy violet again, beside a console that wasn't hit, which kept the map's tone.
- The log, at every load (the user reloaded at 194, 260 and 342 s):
  - `sky light SkyLight_0 ... channels (CompositeDynamic ): ... our pieces leave it out`;
  - `sky lights off (1)`, then `back on (1); the light of 6 light environments is fixed as taken`.
- The grenades:
  - 284.39 s: `XComMapEdDestructible_1` and `_2` (the south pair) each hit for 35, both `_Pristine`;
  - 322.29 s: `_1` hit again, already `_Damaged` at 55 health; `_2` at 83, still `_Pristine`.
- The game's `XComDestructibleActor` (decompiled) moves a damaged piece to `_Damaged` and `_Destroyed`, and its native
  code swaps the mesh through the damage events. A light environment reset that way takes its light again, with the
  sky light on: the fix of run 7 holds only until then.

### Run 11 (deployed 18:18): copies take their light again after damage

**What changed:** `XComMapEdSkyFree` watches the pieces it has lit.
- Each watched piece has a look: its state; for a destructible, its mesh and materials (damage can lay a damage
  material on); for a fractured piece, its count of visible fragments.
- Every 0.25 s, a piece whose look has changed takes its light again with the sky light off for 0.3 s
  (`InPlayTime`). The load-time pass is 2 s, as before.
- Each relight is logged: `<piece> changed (<before> -> <now>); it takes its light again`.
- The soldiers lose the sky light for those 0.3 s, during the explosion that caused the change.

**Build:** `make` with 0 errors and 0 warnings, and an 8 to 9 s cook (146,663 bytes). The spec is unchanged
(revision 5). Deployed at 18:18, when the game closed: the patch has the cook's SHA-256, 146 tiles are seeded, and
line 42 already streams it.

**What to look at:** a grenade on a console copy, as in run 10. Does the copy keep (or get back within a moment) the
map's tone? Is the soldiers' brief dimming noticeable?

**Result of run 11 (18:21 onwards; the user's two shots).** The user: "threw a grenade and the cosoles on the left
stayed blue after impact", and the console on the right "seems to be completely black", while the one next to it "seems
to have some light compared to it".
- The log:
  - at load (22.20 s to 24.43 s), the 2 s pass for 6 light environments, as in run 10;
  - while the grenade was aimed (47.68 s to 50.71 s), four relights: the aiming lays its area highlight
    (`UI_Range.Materials.M_HitByAOE`) on the consoles in its radius and takes it off again, and the watch counted that
    as a change. The soldiers lost the sky light for 0.2 s each time;
  - at the hit (53.68 s), `XComMapEdDestructible_3` and `_0` (copies 9 and 10, the north pair) went `_Pristine` to
    `_Damaged`. Both were relit, and the sky light was back on at 53.91 s.
- So the relight ran at the moment of damage, and the pair still came out lavender.
- `XComDestructibleActor_60` has no damage events of its own, only destroyed events (an effect, a sound, a mesh swap).
  So `_Damaged` changes nothing on it but the state, and the state turns the actor's tick on (`_Pristine` turns it
  off). Two readings, not told apart:
  - the light environment of a ticking piece keeps taking the sky light, fixed or not;
  - something resets it later, with no change the watch could see.
- The south pair (copies 12 and 13) wasn't hit in this run, and one of the two is black. The pair is stacked back to
  back, 2.6 units apart. A light environment traces its lights from the centre of its bounds, and the engine's own
  note on `bTraceFromClosestBoundsPoint` says this fails for an object "likely embedded in shadow casting objects".
  With the sky light out, a piece whose every light is blocked has nothing left (F-56). This is the likely cause, not
  a proven one.
- The user asked whether 4 checks a second scale with the pieces: they did, one look (a few names) per piece every
  0.25 s, all in one frame. Run 12 drops the watch.

### Run 12 (deployed 18:39): the sky light moves to the units' channel; pieces trace from their bounds

**What changed** in [`XComMapEdSkyFree`](../../unrealscript/XComMapEd/Classes/XComMapEdSkyFree.uc):
- **The swap.** When the first piece registers, each sky light that lights no baked surface but reaches light
  environments (the same test as before) is switched off for good. A new
  [`XComMapEdUnitSky`](../../unrealscript/XComMapEd/Classes/XComMapEdUnitSky.uc) lights the units in its place:
  - the same brightness and colour (0.3, (110, 99, 156));
  - one channel, Gameplay_1. The units' meshes have it (`XComUnitPawn`: Dynamic and Gameplay_1 in tactical), our
    pieces don't, and most maps' own sky lights use it;
  - no lower hemisphere: it is const and can't be set in play. Temple's is 0.01.
- **No more switching:** no timed sky-off, no watch, no dimming of the soldiers.
- **The pieces' light:** each registered piece's light environments trace from the closest point of their bounds
  (`bTraceFromClosestBoundsPoint`), update freely for 2 s at load and then keep their light.
- **Log:** each sky light and the choice, the swap (`switched off; XComMapEdUnitSky_0 lights the units in its place`)
  and the fixed light.

**Known side effect:** whatever else the map lights live (its doors, debris) also loses the lavender fill.

**Build:** `make` with 0 errors and 0 warnings. The cooked patch is 145,767 bytes, with `XComMapEdUnitSky` and its
component, and without the watch. A `-Force` build of the patch map, as the cook stops with a fatal error when the
scripts are older than their sources. The spec is unchanged (revision 5). Deployed at 18:39 when the game closed (the
cook's SHA-256, 146 tiles seeded, line 42 unchanged).

**What to look at** (a new campaign):
1. All four consoles in the map's tone. Is the black one lit now?
2. A grenade on a console: does it keep that tone?
3. The soldiers keep their light, lavender fill included.
4. The doors: do they look different from before?

**Result of run 12 (18:42 onwards; the user's shot).** The user: "threw a grenade and it didn't change the lighting
on the piece so that fix works", and "Soldiers seemed normal". But "The black piece was still black though".
- The log at load:
  - `SkyLight_0 ... channels (CompositeDynamic ): ... units take it on Gameplay_1 instead`;
  - `SkyLight_0 switched off; XComMapEdUnitSky_0 lights the units in its place: brightness 0.3000 colour 110,99,156
    channels (Gameplay_1 ); lower hemisphere left out (0.0100 252,144,171)`;
  - 2.3 s later, `the light of 6 light environments is fixed as taken`.
- **F-52 passes:** the copies keep the map's tone through damage, and the units keep the sky light.
- **F-56, the cause revised.** Tracing from the bounds' closest point changed nothing, so the stacking isn't the cause.
  The lights around the two places differ (offsets from each pair, from the map's inventory):

| Light | From the south pair (black) | From the north pair (lit) |
| --- | --- | --- |
| `PointLight_6` (orange, 0.2, radius 1000) | 252 north, **143 below**: under the deck | 998 south, 143 below |
| `PointLight_11`, `_52` (orange, 0.2, radius 1000) | 725 north, 180 up: about 820 away | 525 south, 180 up: about 650 away |
| `PointLight_72` (orange, 0.3, radius 1000) | 1,825 north: out of reach | 575 north, 353 up: about 675 away |
| `PointLight_19` (green, 0.3, radius 2000) | 1,628 north, 775 up: about 1,800 away | 378 north, 775 up: about 860 away |
| `SpotLight_41`, `_42` (cyan doorway spots) | 611 to 638 south, 246 up, aimed 50° down | out of reach |

  - The south pair's nearest light is under the deck, and the rest are near the end of their reach. The north pair
    has four lights above it within 650 to 860 units.
  - The map's own pieces there are lit by the light build's bounce. A piece lit live gets only the direct light, and
    without the sky light's fill the side facing away from the little that reaches is black. Units get the fill (the
    sky light), and so did our pieces before run 7, in lavender.
- The closest-point tracing is taken back out of the source (not yet built): it didn't help, and it lets a light behind
  a wall reach a piece standing against it.
- **Next options:** move the pair where the map's lights reach it, or give our pieces a fill of their own. Such a fill
  could be `AmbientGlow` on their light environments, set at load. Run 5's in-play glow test showed nothing, but that
  copy had stopped following light changes, so it is not yet really tried.
- **Left as it is:** the user asked not to work around a problem that comes from one place in one map.

### Run 13 (deployed 19:36): revision 6, the stacked pairs as groups that break together

**The project, revision 6** (saved 19:35), made with the editor's groups (CHANGELOG, "Editor groups").
- North: the two alien consoles `XComDestructibleActor_60_copy9` and `_copy10`, stacked back to back as before.
- South: the console pair is gone. In its place, two copies of the low cover `XComDestructibleActor_28`
  (`AlienLowCover.Meshes.AlienLowCoverA`), `_copy14` and `_copy15`.
- Each pair is a locked group with **Break together in the game** on.
- As before: the laser barriers `XComDestructibleActor_9_copy4` and `_copy5`, and the two deleted low covers `_206`
  and `_208`.

**Compile:** 0 moved, 2 deleted, 6 added, no warnings. The report numbers the groups: 1 for the low covers (`_copy14`,
`_copy15`), 2 for the consoles. The copy object gets `breakGroups [1, 1, 2, 2, 0, 0]` (the copies in the order
`_28_copy14`, `_28_copy15`, `_60_copy10`, `_60_copy9`, then the barriers). The T3D writes them as the copier's
`BreakGroups(0)` to `(5)`. The spec is [`templeimproved.json`](../../tools/patch/examples/templeimproved.json).

**Build and deploy** (19:36, game closed; `patchtool all ... -Slot 2 -Force`):
- `make` with 0 errors and 0 warnings, a 21 s build and an 8 s cook (the known error and warning).
- The patch is 149,444 bytes. 146 tiles are seeded, and the test slot (line 42) streams it as before.

**What to look at** (a new campaign):
1. A grenade on one half of a pair. Does the other half break with it: damaged together, then destroyed together?
2. After one pair is destroyed, the cover and movement around it, beside the explosion and beyond it.
3. The log: `break group 1:` and `break group 2:` at load, and `its break partner ... goes from ... to ...` at the hit.
4. If possible, a save and a reload after one pair is damaged, and then a hit on it.

**Result of run 13 (19:37 to 19:39; the log).** The user: "done things, look good, I grenaded one of a pair".
- At load, both links:
  - `break group 1: XComMapEdDestructible_0 in _Pristine; XComMapEdDestructible_1 in _Pristine` (the low covers);
  - `break group 2: XComMapEdDestructible_2 ...; XComMapEdDestructible_3 ...` (the consoles).
- The grenade (80.30 s) hit `XComMapEdDestructible_1`, a low cover, at 110 of 110 health, `_Pristine`. Its partner
  `_0` took no hit (it sits behind it).
- No partner line followed, so the hit left `_1` in `_Pristine`. The game damages a piece at 3/4 of its health or less
  (82 of 110), and scales a grenade's damage by chance and by distance. The run 11 consoles went `_Damaged` at their
  first grenade. This one did less than 28, but the log gave no health after the hit.
- **Not yet tested:** a hit that changes a piece's state.
- **Redeployed at 19:40:** each hit now logs its outcome:
  `after the hit: health <h> of <t> state <s>; its break partners follow` (or `... stay as they are`). It is the same
  project and spec (149,600 bytes; `make` with 0 errors and 0 warnings).
- **Next:** two grenades on one half of a pair, or a rocket, to see it damaged and then destroyed with its partner.

### Run 14 (deployed 19:42): revision 7, a low-cover pair at each place

**The project, revision 7** (saved 19:41).
- North: the consoles are gone. In their place is a pasted copy of the south group: `XComDestructibleActor_28_copy16`
  and `_copy17`, stacked as the south pair (rolled −16384, yaws 32768 and 0). The paste kept the group's lock and
  "Break together" (a new group, `228fe3dc`).
- South: `_copy14` and `_copy15`, as in revision 6 (group `2fb1947e`).
- As before: the laser barriers `XComDestructibleActor_9_copy4` and `_copy5`, and the deleted low covers `_206` and
  `_208`.

**Compile:** 0 moved, 2 deleted, 6 added, no warnings. Group 1 is the north pair and group 2 the south pair:
`breakGroups [2, 2, 1, 1, 0, 0]` for `_copy14`, `_copy15`, `_copy16`, `_copy17` and the barriers.

**Build and deploy** (19:42, game closed; `patchtool all ... -Slot 2 -Force`):
- `make` with 0 errors and 0 warnings, and an 8 s cook (the known error and warning).
- The patch is 149,581 bytes. 128 of the 268 planned tiles are seeded (140 already were), and line 42 is unchanged.
- Each hit logs its outcome (since 19:40).

**What to look at:** as run 13. Two grenades on one half of a pair (or a rocket): the log's `after the hit` lines,
and `its break partner ... goes from ... to ...` once a hit damages or destroys it. Then the cover around a
destroyed pair.

### Run 15 (installed 12:18, 7 November): revision 7 from the editor's Build, relit by our baker

This is step L1 of the baker plan (baker design, section 13): Temple is the
second map our baker relights, after the bar. The project is revision 7, as in run 14. What is new: the map itself.
- **Built** by the editor's Build at 12:04 (build `TempleShip_TempleIm_2001-20261107-120402`, about 5 minutes).
  - Compile: 2 deleted and 6 added, as in run 14.
  - The patch was built and cooked by patchtool (146,675 bytes).
  - `relight.py` relit `TempleShip_TempleIm_2001` with `--receivers-near 1024`.
  - The map was seeded on 128 of 268 planned tiles.
- **The relight:**
  - 318 receivers lie within 1024 units of an edit, and the quick test kept 177.
  - 7 lightmaps were rewritten, with 146 unchanged and 24 skipped. Of the skipped, 2 are the deleted low covers and
    22 have their lightmaps inside the map package (no mips in the cache; plan step L2).
- **The 7 rewritten lightmaps:**
  - the two flip floors where the deleted low covers stood, now under the laser barriers (`XComLevelActor_165` and
    `_41`, at x ±1152);
  - the two box structures under the low-cover pairs (`XComLevelActor_1042` and `_1043`);
  - the two low fences beside the pairs (`XComDestructibleActor_313` and `_331`);
  - a main-floor piece beside the pair at y −5808 (`XComLevelActor_798`).

  The previews (in the build's work folder, `lit\*.png`) show the low cover's rectangular shadow gone from each flip
  floor, with the barrier's shadow in its place.
- **Installed** by `lab_install.py install` at 12:18, after two installer changes (CHANGELOG, 7 November):
  - The installer replaced run 14's two lab files, patchtool's `patch_templeship_templeim_2001.upk` and its seeded
    `TempleShip_TempleIm_2001.upk`. Both were backed up to `<lab>\bake-fixtures\backups\*.20261107-121857`.
  - The test slot (line 42) plays the variant as an abduction with `URB_Bar`'s family, Temple's three streams and the
    patch in slot 2, as in runs 1 to 14.
  - The three lab files match the package byte for byte.

**What to look at** (a new campaign; the first mission is Temple, after the arrival cinematic). F9 at each:
1. **Each laser barrier**, either side of the first hall past the doorways (readout tiles (34, 25, 7) and
   (10, 25, 7)). The floor around it should show the barrier's own shadow and no leftover shadow of the low cover it
   replaced.
2. **Each low-cover pair** on its raised block on the centre line (readout tiles (22, 25, 10) and (22, 37, 10)). The
   block's top should show the pair's shadow.
3. **Nothing else changed:** no dark patches, bright seams or blocky edges on those floors, blocks and fences, or
   anywhere else in the hall.
4. **The log:** `copied 6 of 6 pieces`, `hid 2 of 2 exact targets`, and both break groups.

The doorway walls (F-51) stay hidden, as in every Temple run; that isn't ours.

**Result (12:21 to 12:22; six shots, 12:21:38 to 12:22:00): passes.** The user: "everything looks right".
- The shots show both laser barriers on their floors and both low-cover pairs on the raised walk. There's no leftover
  low-cover shadow, and nothing in the hall stands out.
- One low-cover pair is near black (shot 12:21:45), darker than the walk around it. That is F-56, the copies' live
  light, not the bake. A copy is still lit live by its light environment, and little direct light reaches that
  place. The map's own pieces there are lit by the bake's bounce.
- So step L1 passes. Our baker relit a second map, with Temple's 1,190 emissive area lights and two bounces, and
  the game shows no fault from the bake.
- **Next:** the user asked whether our own baking can fix the black pair (F-56); see the findings register.
