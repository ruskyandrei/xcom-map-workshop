# EXP-03: rebuilt patch in the game (record)

This file is the record for EXP-03 in the investigation plan.

**Status (3 November 2026, 20:55):** the control (run 3c) matches the patched runs: these checks can't detect `patch_bar` on this map ([what the control shows](#what-the-control-shows)). The lab copy's `DefaultMaps.ini` still has the control entry (no `patch_bar` stream). Earlier status:

**Status (3 November 2026, 20:05):**
- **Route 3 works.** A new campaign's first mission loads `URB_Bar` and streams `patch_bar` (run 1, 19:46). Routes 1 and 2 went back to HQ; the decompiled strategy code explains why ([below](#why-every-attempt-went-back-to-hq)).
- **Saving crashes the game.** Steam's copy protection (CEG) in `XComEW.exe` checks the CPU signature, and WSL2's hypervisor changes it ([below](#crash-on-saving-the-ceg-cpu-check-and-the-hypervisor)). The LWR install has the identical exe.
- **Next.** The checks are redone without a save, with autosave off in the lab copy's options.

## What `patch_bar` does to `URB_Bar`

`URB_Bar` and `URB_Bar_Terror` stream `patch_bar` as `StreamingMaps[1]` (`DefaultMaps.ini`). `URB_Bar` also streams `patch_hide_randomized_objects`, whose embedded XComUDK is a different build (`f9b68768…`). So the shipped mission already mixes two XComUDK builds. The full property dump is [`EXP-01/patch_bar-shipped-level-props.txt`](EXP-01/patch_bar-shipped-level-props.txt).

Coordinates are in map units (96 per tile):

| Change | How | Where |
|---|---|---|
| Two new ladders | `XComLadder_11` and `XComLadder_15`, each with a point light and a world-data rebuild volume | (−1656, 336) and (436, 1276) |
| Dumpster high cover | On `SeqEvent_LevelLoaded`, `SeqAct_GetActorsTouchingVolume` finds `ARC_Dumpster_A` inside rebuild volumes 11 and 0. Hidden `XComLevelActor_1`/`_3` force high cover (`CoverForce_High`), and `SeqAct_AddDestructibleActorEvent` destroys each blocker when its dumpster is destroyed. | (−2688, −1344) and (−2304, −1344) |
| See-through metal fences | `SeqAct_GetAllActors` by archetype (`ARC_MetalFence`, `ARC_MetalFence192_DESTRO`, `ARC_MetalFence192Cap_Destro`), then `SeqAct_SetLOSBlocking`. Its `bBlockUnitVisibility` defaults to false, so fences stop blocking unit sight. | all such fences |
| Existing ladders re-registered | `SeqAct_GetAllActors` (`ARC_LadderMetalA_448`, `ARC_LadderVehicleA_256`), then `SeqAct_SetScale3D` to (1, 1, 1.001) | all such ladders |
| Hidden walkable tiles at z ≈ 100 | 13 hidden `XComLevelActor`s with floor components, plus rebuild volumes | around (−2112…−2220, −1140…−1260), (−2496…−2592, 852…972) and (1824…1920, 1332…1452) |

## Set-up

- **Console.** The lab copy's `XEW\XComGame\CookedPCConsole\Engine.upk` was replaced with LWR's `Engine.upk.renamethistoenableconsole`. The original is kept at `<lab>\snapshots\exp03\Engine.upk.lwr` and matches the baseline. Keys (`XComInput.ini`): `\` opens the one-line console, `~` the full one. It works through the normal launcher (attempt 1b).
- **Launch.** Through Steam, the EU stub and the launcher (click Enemy Within), with `-nohomedir` from the wrapper. Direct launch (`launch=direct` in the marker) was tried and removed after the 1a crash.
- **Tactical cheats.** `ShowCursorLoc`, `TeleportToCursor`, `ToggleFOW`, `UnlimitedMoves`, `DebugCover`, `DebugClimbOnto`/`DebugClimbOver`, `ToggleInvincibility`, `killaliens` and `DropSectoid`.
- **Streaming log.** `Suppress=DevStreaming` is commented out in the lab copy's generated `XComEngine.ini`, so the log should show which streams load. The original is `XComEngine.ini.exp03-orig`.
- **Getting onto the map (route 3).** See [below](#route-3-the-first-mission-entry-pointed-at-urb_bar). The lab copy's `DefaultMaps.ini` differs from the shipped file in one entry; `DefaultMiniMods.ini` is the shipped file again.
- **Patch variants.** `tools\lab\swap_patch.ps1 status|shipped|rebuilt|none`:
  - **`shipped`:** the shipped `patch_bar.upk`, saved to `<lab>\snapshots\exp03\patch_bar.shipped.upk` and checked against the baseline (`000891c1…`).
  - **`rebuilt`:** the EXP-01 PC cook, `<lab>\builds\exp01-cook-2026-11-03\PC\patch_bar.udk`.
  - **`none`:** no file, as the control.

## Procedure

Every run starts from the same tactical save. The variant is swapped between runs, with the game closed.

**Each run** (no saves while the hypervisor is on, see [the save crash](#crash-on-saving-the-ceg-cpu-check-and-the-hypervisor)):
1. Start a new campaign in the lab copy: Ironman off, tutorial off, autosave off (game options). Choose the country.
2. The first mission loads `URB_Bar`. Do the checks there, then quit without saving.

With the hypervisor off, saving works (confirmed 19:58: save "Classic Game 3 … Operation Fatal Moon"). A save can't replace the new campaign, though: it carries the patched world data ([below](#tactical-saves-carry-the-world-data)).

**Cheats that work in EW (from the decompiled `XComTacticalCheatManager`):**
- **`ToggleInvincibility` (or `TakeNoDamage`).** Your soldiers take no damage: `XGUnit.CanTakeDamage` and `SetUnitHP` honour the flag for the human team.
- **`killaliens 1`.** Kills every alien but one (`bAllButOne`), so the mission doesn't end. Plain `killaliens` ends it.
- **`ShowCursorLoc`, `TeleportToCursor` and `ToggleFOW`.** These work as named.
- **`UnlimitedMoves` doesn't work in EW.** It sets the EU-era `m_iMoves` once. EW counts actions with `m_iMovesActionsPerformed` (`GetRemainingActions`, two per turn), so it has no effect.
- **Doing the checks without moving.**
  - **Ladders.** The path preview in move mode shows whether a path climbs the ladder.
  - **Dumpster cover.** Hovering the tile next to a dumpster shows the cover shield (full means high cover).

| # | Check | Expected with the patch |
|---|---|---|
| A | The new ladders at (−1656, 336) and (436, 1276) | A soldier can climb each one |
| B | The two dumpsters at (−2688, −1344) and (−2304, −1344) | A soldier next to one gets high cover (full shield) |
| C (optional) | A metal fence | A soldier sees an enemy through it (`DropSectoid` puts one at the cursor) |

Screenshots: Steam's F12. After run 1, the lab `Launch.log` should show `SeamlessTravel: loaded additional map patch_bar` (or `XComMapManager::AddStreamingMap`).

## Runs

| Run | Variant | Result |
|---|---|---|
| 1a (19:17) | shipped; direct launch; console | Crash after continent selection ([below](#1a-crash-on-a-new-campaign-with-direct-launch)) |
| 1b (19:22) | shipped; launcher; console; `ForceMission_URB_Bar` | The forced mission travelled to `Command1` (HQ) |
| 1c (19:28) | shipped; route 2, `URB_Bar` the only abduction map | The first mission travelled to `Command1` |
| 1d (19:31) | shipped; route 2 plus a day copy of `URB_Bar` | The first mission travelled to `Command1` |
| 1e (19:46) | shipped; route 3 | `URB_Bar` loaded and `patch_bar` streamed (`IncrementHistory: (0) URB_Bar, URB_Bar, URB_CommercialAlley_EWI (Commercial Alley Redux) |0`, then `SeamlessTravel: loaded additional map patch_bar`). Crashed when the user saved, before the checks |
| 1 (19:58–20:15) | shipped; route 3; hypervisor off, save **Classic Game 3 … Operation Fatal Moon** on landing | **A:** the path preview from the soldier to the roof at (−1393, 335, 466) climbs the ladder at about (−1656, 336), where `XComLadder_11` sits. **B:** next to the dumpster at (−2688, −1344), cursor (−2641, −1201, 64), tile (1, 7, 1) shows full shields (high cover). **A2:** the path preview to the roof at (431, 1007, 466), tile (33, 30, 7), climbs the ladder at about (436, 1276), where `XComLadder_15` sits. Screenshots from the user. |
| 2a (20:10–20:13) | rebuilt (EXP-01 PC cook), **loaded from the run 1 save, so not valid** ([below](#tactical-saves-carry-the-world-data)) | Same as run 1. **A** and **A2:** both path previews, from the same cursor spots, climb the ladders. **B:** full shields at tile (1, 7, 1). Two were red this time: `XComActionIconManager.IsLocationFlanked` marks cover that a living enemy in firing range flanks, which depends on where the aliens stand, not on the patch. The shield shape (`Game_CoverHigh` vs `Game_CoverLow`) is the cover height. |
| 3a (20:14–20:20) | none, **loaded from the run 1 save, so not valid** | Same as run 1: both ladders climb, full shields at the dumpster. `patch_bar` was in the travel URL (`StreamingMap1=patch_bar`), but nothing streamed it and no error was logged. |
| 3b (20:19 and 20:25) | no file, new campaign | **Crash while loading.** The fresh load requests the entry's streaming maps, and a missing one is fatal: `appError called: Couldn't find file for package patch_bar requested by async loading code` (dumps `unreal-v8917-2026.11.03-20.18.46.dmp` and `…20.23.17.dmp`). The save load in 3a skipped it silently. So "no file" is no control for a fresh load. |
| 3c (20:30–20:50) | file shipped, but `patch_bar` removed from the EXP03 entry's `StreamingMaps` (backup of the route 3 file: `<lab>\snapshots\exp03\DefaultMaps.ini.route3`), new campaign. The log shows only `CIN_DropshipIntros` and `patch_hide_randomized_objects` streamed. | **A:** with a soldier at the foot of the ladder, the user put the cursor on the roof at (−1393, 431, 466), tile (14, 24, 7), and the path climbs the ladder. **A2:** checked by Claude with `GameDriver` (`ViewLocation`, `TeleportToCursor`, floor keys V/B, zoom G). With the soldier at the foot, (431, 1295, 80), roof tile (32, 30, 7) reports `PathActionEmpty: False`, and the path line runs up the ladder. **So both ladders climb without the patch.** After `TeleportToCursor`, the unit's paths stay stale until it is reselected (the user tabbed to another soldier and back). The first "no route" at (33, 30, 7) came from that, not from the map. **B:** a soldier, standing by the left dumpster at (−2688, −1344), shows the full-shield cover icon on his unit flag. Hovering (−2353, −1201), tile (4, 7, 1), by the right dumpster shows full-height shields. **So both dumpsters give high cover without the patch.** |

### What the control shows

- **No difference.** All three checks come out the same with and without `patch_bar` on a fresh load: both ladders climb and both dumpsters give high cover.
- **What that means.** The base map already behaves this way, so these checks can't show the patch's effect. Its ladders, `CoverForce_High` blockers and rebuild volumes either repeat what the baked world data already has, or fix cases these checks don't reach: a specific approach to a ladder, cover after the dumpster is damaged, the hidden tiles at z ≈ 100. Runs 1 and 2a show that the shipped and rebuilt packages both load and stream without errors. EXP-01 already showed their exports are byte-identical.
- **Next.** For a test that can tell, the patch has to change something the base map doesn't have. For example, a rebuilt `patch_bar` with an added prop and cover blocker in the open street, checked against the shipped one. That is an authoring step (UDK), beyond EXP-03's "rebuild the existing patch".
| 2b | rebuilt, new campaign | pending |

### Tactical saves carry the world data

- **The finding.** The control run loaded from the run 1 save showed every patch effect without a `patch_bar` file. Its checkpoint load lists `Checkpoint_TacticalGame_0.XComWorldDataContainer_0`: a tactical save stores the tile data (pathing, ladder routes, cover heights). Loading restores the data as saved, including what the patch's rebuild volumes, ladders and cover actors had put there. The save restores 145 actors (units, AI, pods, battle state), but no actor from `patch_bar`.
- **Consequence for EXP-03.** The checks are tile data, so runs loaded from a save test the save, not the patch. Each run must start a new campaign (the first mission loads `URB_Bar` fresh). Run 1 is valid: it was a fresh load, and its save was made in the same session.
- **Consequence for the mission editor.** A mission's world data is frozen into saves made on it. Changing a patch or a map later doesn't change missions already saved, and a save made with a patch keeps working without the patch file, at least for these effects.

## Crash on saving: the CEG CPU check and the hypervisor

- **What happened (1e).** The user opened the save screen on landing (the log loads `UILibrary_MapImages_SF`). About 4 s later the game crashed: `Fatal error! Address = 0x0`. Dump `XEW\XComGame\Logs\unreal-v8917-2026.11.03-19.45.59.dmp`; `cdb` output in `<lab>\logs\exp03-crash-1946*.txt` and `exp03-crash-cpuid-data.txt`.
- **Same fault as 1a.** The return address is `0x0d780c7f` in both dumps.
- **The code at that address is a CEG thunk.** At `0x0d780c50` a stub saves the registers, jumps into a function it has just decrypted (at `0x0d780d70`), and after the return zeroes that function again (`rep stos`) before going back to `XComEW.exe`. That is how Steam's Custom Executable Generation (CEG) runs its protected functions.
- **The decrypted function is a CPU check.**
  - It runs `cpuid` (leaf 1) and compares eax, ebx, ecx and edx with values stored in `XComEW.exe`'s `.rdata` (VA `0x01888a3c`, file offset `0x1737230`), under masks at `0x01888a5c`.
  - On a mismatch it calls a routine that ends at address 0.
  - Both dumps hold the same stored values, and the lab and LWR executables are byte-identical (sha256 `51d4cdbc…`). Steam wrote the values when it generated this copy of the exe.

| CPUID(1) | Stored (mask) | At the crash | Difference |
|---|---|---|---|
| eax | this CPU's signature (`0fffffff`) | the same | none |
| ebx | this CPU's value (`00ffffff`) | the same | none |
| ecx | `7ffafbff` (`ffffffff`) | `fffaf38b` | bit 31 (hypervisor present) set; VMX, SMX, DS-CPL, DTES64, SDBG cleared |
| edx | `bfebfbff` (`ffffffff`) | `bfcbfbff` | bit 21 (debug store) cleared |

- **The difference is a hypervisor.** `esi = 80200874` at the crash is exactly the OR of those differences. A hypervisor runs on this PC: `HypervisorPresent` is true and VBS status is 2 (running), with Memory Integrity off. The optional features `VirtualMachinePlatform` and `Microsoft-Windows-Subsystem-Linux` are enabled, and `wslservice` and `vmcompute` were running: WSL2 starts it. The stored values are the same CPU without a hypervisor, as it was when Steam generated the exe.
- **When the check runs.** It runs from a per-frame call in `XComEW.exe` (it takes a float, like `Tick(DeltaTime)`). Both crashes came when the game was saving: 1a at campaign start in HQ, 1e from the save screen. The lab copy has never written a save game; its `SaveData` holds only `profile.bin`.
  - In 1b the user played a whole first mission and reached HQ without a crash.
  - So the check is tied to saving, or at least isn't constant.
- **Corrections.**
  - 1a was not caused by direct launch.
  - LWR itself should crash the same way on saving while the hypervisor is on. That's untested: the last LWR save is from 23 February 2026.
- **Ways round it, none applied:**
  - **No saves during EXP-03.** Route 3 needs none.
  - **Hypervisor off.** Run `bcdedit /set hypervisorlaunchtype off` from an elevated prompt, then reboot. WSL2 then doesn't work until `bcdedit /set hypervisorlaunchtype auto` and another reboot. This is the user's own system setting.
  - **Not used.** Steam's "Verify integrity of game files" might regenerate the exe, but it would also restore every LWR file in the active folder. Editing the stored values would bypass the copy protection; not done.
- **Shared profile.** Steam itself rewrites `steam_autocloud.vdf` in the shared `SaveData` at each launch (19:45:57). The game's own files there (`profile.bin`, saves) were untouched.

## Why every attempt went back to HQ

The strategy code was decompiled from copies of the lab's packages with [`tools/upk/UeDecompile.cs`](../../tools/upk/UeDecompile.cs). It's a command-line front end to UE Explorer 1.6.2's library, `Eliot.UELib`. Decompiled packages: `XComStrategyGame.upk`, `XComGame.upk`, `LWRebalance.u` and `MiniModsCollection.u`.

- **The first mission's map is hard-coded.** `XGGeoscape.TakeFirstMission` calls `DetermineMap`. For a first abduction mission, that sets the display name `"URB_CommercialAlley_EWI (Commercial Alley Redux) |0"`, whatever the map list holds. Route 2 had commented that entry out, so the native lookup found no map (no `XComMapManager::IncrementHistory` line), and the travel fell back to `Command1`. The day copy (1d) couldn't help. The time-of-day explanation recorded after 1c was wrong.
- **The cheat uses the vanilla display name.** `ForceMission_URB_Bar` calls `ForceAbductionMission("URB_Bar (Beta/Functionality Complete Urban Bar)")`. LWR's `DefaultMaps.ini` names that map `"URB_Bar (Beta/Functionality Complete Urban Bar) |0"`, so `XComMapManager.GetMapInfoFromDisplayName` fails.
  - LWR's `RebalanceMutator.RedirectStrandedMissions` (run from `MissionStart`) then calls `DetermineMap` again. For a cheated mission, that keeps the name it has. Hence the log line `mission 1 was on '…', no longer in the map list; now '…'` with the same name twice, and the travel to `Command1`.
  - The other `ForceMission_*` cheats probably fail the same way wherever LWR added the ` |0` suffix.
  - `ForceAbductionMission(string)` itself is not an exec function, so the right name can't be typed in the console.
- **LWR's MiniMods map organizer is not involved.** `MiniModsCollection.MapOrganizer` watches `GEOSCAPE().m_arrMissions` from HQ. For each abduction that is neither scripted nor cheated, it compares `m_eDifficulty` with `AbductionMapRules`, and `ReplaceMapFor` re-picks a map when the difficulty is too high for it.
  - It never sees the first mission, which launches before HQ, or a cheated one.
  - Before this was read, its `URB_Bar` rule in the lab copy had been raised from `eMissionDiff_Moderate` to `eMissionDiff_VeryHard`. That edit was reverted, and `DefaultMiniMods.ini` matches the baseline again.
  - `ReplaceMapFor` loops (`goto`) until it draws an allowed map. Trimming the abduction list (as route 2 did) could make HQ hang once an abduction is generated whose difficulty no remaining map allows.

## Route 3: the first-mission entry pointed at `URB_Bar`

- **The edit.** The lab copy's `DefaultMaps.ini` is the shipped file again (from `<lab>\snapshots\exp03\DefaultMaps.ini.orig`, checked against the baseline), with one entry changed. The abduction entry whose display name is `URB_CommercialAlley_EWI (Commercial Alley Redux) |0` (line 35) now carries `URB_Bar`'s fields:
  - `MapFamily` and `Name` `URB_Bar`;
  - `StreamingMaps` `CIN_DropshipIntros`, `patch_bar` and `patch_hide_randomized_objects`;
  - region none, time of day still Day;
  - a `; EXP03:` comment line above it.
- **Kept as shipped.** The display name and the real `URB_Bar` entry (line 4) are unchanged.
- **What should happen.** A new campaign's first mission loads `URB_Bar` and streams `patch_bar`. `IncrementHistory` should log `URB_Bar, URB_Bar, URB_CommercialAlley_EWI (Commercial Alley Redux) |0`.

## Earlier attempts in detail

### 1a: crash on a new campaign with direct launch

- **What happened.** The user started a new campaign in the lab copy, launched directly (`-FROMLAUNCHER -nostartupmovies -nohomedir`, no `-LANGUAGE`) with the console `Engine.upk`. The game crashed about 4 s after HQ (`Command1`) had loaded the starting soldiers, just after the continent was chosen.
  - **Log:** `=== Critical error: === Fatal error! Address = 0x0`.
  - **Dump:** `XEW\XComGame\Logs\unreal-v8917-2026.11.03-19.17.35.dmp`, read offline with WinDbg's `cdb` (x86, no symbol downloads); output in `<lab>\logs\exp03-crash-1917*.txt`.
- **What the dump shows.** `c0000005`, an attempt to execute address 0. The caller is code at `0x0d780c7f`, outside every loaded module (runtime-unpacked memory); the frame below returns into `XComEW.exe`.
- **Cause (found at 1e).** Steam's CEG CPU check fails because a hypervisor is running ([above](#crash-on-saving-the-ceg-cpu-check-and-the-hypervisor)). At the time it was blamed on direct launch, which was then dropped. That was wrong: 1e crashed the same way through the launcher.
- **Log warnings seen but not judged.** 88× "Can't find file for package 'XComUIShell'" while HQ loads. They also appear in the working runs.

### 1b: launcher route, console, `ForceMission_URB_Bar`

- **Getting to HQ worked.** No crash on a new campaign: the stub and launcher route, with the console `Engine.upk` and `-nohomedir`, works.
- **The console works through the launcher**, so the "no `-LANGUAGE`" claim doesn't apply here. The log shows `Ucross Console Command Use: killaliens` (first mission `URB_CommercialAlley_EWI`, which streamed `patch_commercialalley_ewi` and `patch_commercialalley_carflank`) and `Ucross Console Command Use: ForceMission_URB_Bar`.
- **The forced mission went to HQ.** It appeared in mission control (`MAPFRAME URB_Bar … on UIMissionControl_AbductionSelection_0`). On launch, LWR logged `mission 1 was on 'URB_Bar (Beta/Functionality Complete Urban Bar)', no longer in the map list` and the game did `SeamlessTravel to: Command1`. The user was left on the HQ globe with no UI or sound.

### 1c and 1d: route 2, `URB_Bar` as the only abduction map

- **The edit.** The other 44 abduction lines in `DefaultMaps.ini` were commented out and `URB_Bar`'s region set to none. In 1d a day copy of the `URB_Bar` entry was added (display name `URB_Bar (EXP03 day copy) |0`). The generated `XComMaps.ini` carried both entries.
- **Result.** Both first missions travelled to `Command1`, with no `IncrementHistory` line. In the working run (19:22, full list), `IncrementHistory: (0) URB_CommercialAlley_EWI …` came right before `SeamlessTravel to: URB_CommercialAlley_EWI`.
