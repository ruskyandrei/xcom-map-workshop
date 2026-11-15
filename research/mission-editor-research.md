# XCOM: Enemy Within (LWR): mission editor research

Date: 2026-11-03. Scope: the installed game at `<Steam common>\XCom-Enemy-Unknown\XEW` (Long War + LWR) and what the community found online, 2013–2026.

This is the consolidated project reference, incorporating the follow-up investigation. The [verification report](<mission-editor-feasibility-update.md>) retains the detailed evidence and experiment matrix. Scope is single-player EW/LWR campaign integration; equivalent support in base Enemy Unknown has not been established. This research inspected files and public sources; **no game files were modified, UDK was not installed, and no newly authored mission was playtested**. Community demonstrations, local static observations and proposed experiments are distinguished below.

The initial investigation plan provides the detailed next steps: verified tool downloads, separate installations, baseline/profile isolation, experiments EXP-00 through EXP-12, acceptance criteria and scope decisions.

## Summary

- **A useful editor has a credible foundation; unrestricted new maps remain research-dependent.** Existing-map edits have the strongest evidence. Whole-layout replacement inside existing bounds and independent maps with new bounds need separate validation.
- **No official EU/EW SDK was identified.** The relevant community toolchain is **UDK September 2011**, matching package version 845 and engine build 8916; some installed game packages use build 8917. Matching versions is a starting point, not a guarantee of all native serialization compatibility.
- **The installation already uses community streaming levels.** With stub copies of XComGame classes, UDK can build levels containing XCOM gameplay actors, loaded through `StreamingMaps` in `DefaultMaps.ini`.
  - `CookedPCConsole` holds **90 `patch_*.upk` maps**. Active map records contain **323 patch-stream references to 87 distinct names**, with none missing on disk.
  - LiQuiD911's public project supplies corresponding patch-map sources and XComUDK actions. The installed patches contain cover actors, ladders, destructibles, static meshes, particle effects, rebuild volumes and Kismet. Matching names do not prove every installed file matches that public revision exactly.
- **Proven so far (2014–2015):**
  - Placing static meshes and XCOM actors.
  - Spawn points, alien spawns, Meld spawn points and no-spawn volumes.
  - Capture-point volumes, interactive actors and the EXALT wave system (prototype).
  - Mission logic in Kismet.
  - Runtime rebuild of cover and pathing for areas you change.
  - Moving the landing zone (LZ), bomb, power nodes and pods by script (mutators).
  - Bringing the four cut EU maps back into EW.
- **Map inspection already has a tool:** [XCOM Uncooker](https://github.com/chrishayesmu/XCOM-Uncooker) reconstructs EW maps, art and Kismet for viewing in UDK. It does not provide a complete playable round trip. Use a separate reference installation before considering a new exporter.
- **Custom materials have a documented route:** [LWCE's executable patches](https://github.com/chrishayesmu/XCOM-LW-CommunityEdition/blob/71d2164ca8d76883ff5afa24ee5062596c880088/Notes/exe_patches.md) enable runtime compilation. Those specific changes are absent from this installed executable. Their LWR compatibility, texture handling and shader persistence still need testing.
- **The hard parts are:** complete native world-data construction; independent collision, cover and LOS correctness; new texture/shader packaging; inherited lighting; campaign registration; and save/load behavior alongside LWR randomization. Local tile rebuilds do not establish that a fresh map can initialize all these systems.
- **Recommendation:** use **UDK 2011-09 and existing placeable stubs** as the initial authoring/compiler backend, with Uncooker for reference inspection. Add asset indexing, mission templates, validation, repeatable build/install tooling and focused runtime hooks. A standalone frontend can generate input for UDK without implementing its own cooker.
- **First step:** establish the baseline toolchain, then run the [risk experiments](#phase-1-risk-experiments-each-answers-a-yesno-question) before building a polished editor. The big unknown is a **brand-new map not built on a Firaxis base**, with world data built entirely at runtime.

---

## 1. What is in the install

### Engine and package versions

| Package group | Count | Version / licensee | Engine build | Cooker marker |
|---|---|---|---|---|
| Licensee-64 packages | 2,882 | 845 / **64** | 8916: 2,826; 8917: 56 | 721031 |
| Additional licensee-64 package | 1 | 845 / **64** | 8916 | 135 |
| UDK-format patch maps | 90 | 845 / **0** | 8916 | 135 |
| Other UDK-format packages | 20 | 845 / **0** | 8916 | 0 |

Total: **2,993 top-level `.upk`/`.u` files**, with all headers parsed successfully. Twelve core/startup files have an outer LZO wrapper, explaining the earlier incomplete count of 2,981. A licensee/cooker marker describes format metadata, not necessarily authorship. Full observations and file hashes are in the [installation audit](<evidence/installed-game-audit.json>).

Licensee-0 packages are:

- LWR script mods: `LWRebalance.u`, `XComMutator.u`, `XComLZMutator.u`, `Sightlines.u`, …
- LW and LWR content: `LongWar.upk`, `LWRPictures.upk`, `LWRFX.upk`, `Deployment.upk`
- All 90 `patch_*.upk` maps.

The game reads both formats. Stock UDK does not directly accept the Firaxis packages; Uncooker reconstructs compatible reference packages with some game-specific data omitted.

The LWR mods load through wghost81's **XComMutator** loader (`DefaultMutatorLoader.ini`: tactical and strategic mutator lists).

### What the installed patches prove, and what they do not

Across the 90 patches, export tables contain 845 `XComLevelActor`, 409 `XComRebuildWorldDataVolume`, 81 `XComLadder`, 90 `XComDestructibleActor`, 163 `StaticMesh`, 40 `SeqAct_SetLOSBlocking` and 43 `SeqAct_SetCover` entries. Counts include default objects and resources duplicated across packages, so they are not counts of unique assets or necessarily placed actors.

`patch_bar.upk` includes `CoverPatch.High2x2`, `CoverPatch.highcover` and `LadderMetal.Meshes.LadderMetalA_448`, plus rebuild volumes and Kismet. However, the 90 patches contain **no `Texture2D` or base `Material` exports**, and only 13 material-instance exports. They establish a stronger foundation for geometry and gameplay additions than for unrestricted new art.

Separately, `LWRPictures.upk` has 23 texture exports. UI textures do not establish streamed world-texture compatibility. The four top-level texture caches found are `Textures.tfc`, `Textures_startup.tfc`, `CharTextures.tfc` and `Lighting.tfc`; this inventory does not test additional cache names.

### How maps are configured

`XComGame/Config/DefaultMaps.ini` (`[XComGame.XComMapManager]`) has **188 `Maps=` entries**. Each entry sets:

- `MapFamily` / `Name`: the package name.
- `DisplayName`: used as a key by council missions.
- `MissionType`, `CouncilType`, `ShipType`, `TimeOfDay`, region and selection weights.
- `StreamingMaps[n]`: sublevels loaded on top of the base map.

Mission types in use (active entries only): Abduction 45, Crash 41, Special 31, Landed UFO 23, Terror 22, Capture-and-Hold 10, Covert Extraction 8, Alien Base 2, Multiplayer 2, plus single entries for Strategy, EXALT Raid, HQ Assault and Final. 153 of the 188 are in the random rotation.

The active records reference 87 distinct `patch_` names 323 times. `patch_hideroofs`, `patch_museum_multi` and `patch_streetoverpass` are installed but unreferenced in those records. A configuration merger must distinguish records sharing a base map but using different mission types, and preserve existing streams.

Firaxis builds mission *variants* by streaming a small level holding Kismet, objective actors and LZ prefabs onto a base map. Example: `URB_PierA_Terror` + `URB_PierA_Terror_CovExt`. Pods and spawns in a streamed level override the base map's. The community reuses the same mechanism for patches.

### What a Firaxis map contains (URB_Bar, 14,051 exports, 35 MB uncompressed)

- **Art:** seek-free cooking duplicates many required assets into map packages, while textures may use external caches. Asset availability depends on loaded packages and content-loading mechanisms; an editor should resolve actual dependencies rather than assume every asset is globally available or every map is completely isolated.
- **Gameplay actors:**
  - Cover and destruction: `XComLevelActor` 283, `XComDestructibleActor` 588 (with action objects and toughness), `XComFracLevelActor` 52, `XComInteractiveLevelActor` 10 (doors and windows), `XComLadder` 7.
  - Spawns and pods: `XComSpawnPoint` 24 (6 per LZ, grouped by `Tag`), `XComAlienPod_Abduction` 5, `XComMeldContainerSpawnPoint` 4.
  - Volumes: `XComNoSpawnVolume`, `XComFloorVolume` 24, `XComBuildingVolume` 11 (also the dropship/extraction volume), `XComCursorVolume`, `XComLevelVolume`.
  - Other: `XComCoverSeed`, `PrefabInstance` 28 (LZ/Skyranger prefabs), `XComMapInfo`, one Kismet `Sequence`.
- **Baked world data:** `XComLevelVolume_4.XComWorldData_0` has a 52×39×12 grid (24,336 tiles). Its container serializes to **882,780 bytes**. `CB2_MP_Blank` has a 36×36×12 grid (15,552 tiles) and a **480,504-byte** container, so even the blank map supplies native data. The container's internal layout has not been decoded by this research.
- **Grid dimensions:** [XComWorldData's public stub](https://github.com/iiiLiQuiDiii/UDK/blob/80be6f4c21b665e0c261bee224429cb36c3fc217/UDK-2011-09/Development/Src/XComGame/classes/XComWorldData.uc) defines **96-unit horizontal steps and 64-unit vertical steps**, with half steps of 48 and 32. Placement must also respect each map's origin.
- **Runtime world-data functions:** the installed `XComWorldData` exports `BuildWorldData`, `InitializeWorldData`, `RebuildTileData`, `RebuildTileDataExtents` and `UpdateFloorHeight`. Existing patch maps and the game's destruction/rebuild mechanisms support local updates; the presence of those functions does not establish that all of them perform a complete build in the retail executable.

The installed package also exports `IsRebuildingTiles`. The public [`SeqAct_BuildWorldData`](https://github.com/iiiLiQuiDiii/UDK/blob/80be6f4c21b665e0c261bee224429cb36c3fc217/UDK-2011-09/Development/Src/XComUDK/classes/SeqAct_BuildWorldData.uc) calls `GetWorldData().BuildWorldData(LevelVolume)`, assuming a world-data object already exists. No export of this action was found in the 90 installed patches. A callable native entry point does not prove that the retail implementation can allocate a fresh world, resize it or rebuild every required subsystem.

Likewise, [`SeqAct_SetLOSBlocking`](https://github.com/iiiLiQuiDiii/UDK/blob/80be6f4c21b665e0c261bee224429cb36c3fc217/UDK-2011-09/Development/Src/XComUDK/classes/SeqAct_SetLOSBlocking.uc) changes actor flags but does not itself rebuild data or validate sight lines. Collision, cover, visibility and projectile behavior need distinct tests.

### Mission vocabulary available in XComGame (1,123 classes)

- Spawns and pods: `XComSpawnPoint`, `XComSpawnPoint_Alien`, `XComAlienPod` (+ `_Abduction`, `_Terror`, `_Hunter`), `XComAlienPathNode`, `XComAlienSpawnVolume`, `XComNoSpawnVolume`.
- Objectives and volumes: `XComMeldContainerSpawnPoint`, `XComCapturePointVolume`/`Actor`, `XComRadarArrayActor`, `XComDamageVolume`, `XComStairVolume`, `XComFloorVolume`, `XComLevelBorder`.
- Mission logic: `XComSpecialMissionHandler_*` (Bomb, Extraction, DataRecovery, Rescue, HQAssault, ChrysHive, Templeship).
- About 150 XCOM Kismet actions, events and conditions, for example: `SeqAct_SpawnAlien`, `SeqAct_SpawnReinforcement`, `SeqAct_SpawnCivilian`, `SeqAct_DisplayMissionObjective`, `SeqAct_LoseBattle`, `SeqAct_WinBattleIfHuman`, `SeqAct_RebuildWorldData`, `SeqEvent_OnUnitKilled`, `SeqEvent_OnAlienPodKilled`, `SeqEvent_OnPlayerBeginTurn`, `SeqEvent_OnMissionVictory`.
- Battle classes per mission type: `XGBattle_SPAssault`, `_SPTerror`, `_SPCovertOpsExtraction`, `_SPCaptureAndHold`, …

---

## 2. How a mission runs (what an editor must produce)

1. **Strategy layer** picks a mission and a map.
   - `XComMapManager` picks from `DefaultMaps.ini` by `MissionType` and weights.
   - Council missions are chosen in `XGFundingCouncil.BuildMission` by **DisplayName**, which is hard-coded. LWR's `XComLZMutator.XGFundingCouncil_Mod` already extends this (`BuildExtendedMission`, `ChooseNextMissionByType`).
2. **Tactical load:** the base map plus `StreamingMaps` (dropship intro cinematic, mission stream, patches).
3. **Battle init:**
   - `XGBattle_SP` runs `InitPlayers`, then `XComAlienPodManager.InitPods`, which collects every placed `XComAlienPod*`.
   - The Overmind's deploy AI fills pods from the alien squad.
   - XCOM spawns at the LZ: `PlayerStart`, 6 `XComSpawnPoint`s with a group `Tag`, the dropship `XComBuildingVolume` that defines extraction, and the highlight `XComLevelActor`.
4. **Mission logic:** for abductions, terror and UFO missions it lives in script. For special missions it is Kismet in the stream plus `XComSpecialMissionHandler_*`, trigger volumes and the EXALT wave system.
5. **World data:** baked tiles are loaded, then rebuild volumes and destruction update them at runtime.

So a "mission" deliverable is:

- a level (geometry + art),
- gameplay actors,
- Kismet,
- a `DefaultMaps.ini` entry,
- optionally a strategy-layer hook if it isn't a plain abduction, terror or UFO mission.

### Campaign integration and persistence

The reviewed [`XGFundingCouncil_Mod`](https://github.com/wghost/XCOM-Mutators/blob/4f7845b2ca764efa514b1e692ff27d9661d5a06b/Src/XComLZMutator/Classes/XGFundingCouncil_Mod.uc) extends **bomb scenarios** using an existing bomb mission as its template. This is not a generic arbitrary-mission API. [`XComFCMutator`](https://github.com/wghost/XCOM-Mutators/blob/4f7845b2ca764efa514b1e692ff27d9661d5a06b/Src/XComLZMutator/Classes/XComFCMutator.uc) installs that replacement during new-game initialization; adding such a hook to an existing save needs a separate test.

The installed mutators randomize LZs, pods, Meld and bombs, so they may move designer-authored objects after loading. The public [`XComLZMutator`](https://github.com/wghost/XCOM-Mutators/blob/4f7845b2ca764efa514b1e692ff27d9661d5a06b/Src/XComLZMutator/Classes/XComLZMutator.uc) destroys/recreates LZ objects and restores them on save load. An editor needs stable object identifiers, saved objective/layout state, and an explicit policy for fixed versus randomized placements. Its six named spawn anchors do not establish support for every LWR squad size. These public 2015 sources must be checked against the installed LWR behavior before adaptation.

The installed `DefaultMutatorLoader.ini` explicitly requires both `LWRebalance.RebalanceMutator` entries to remain last; any installer must preserve that order.

Acceptance for normal gameplay means campaign selection, the intended squad/enemies, victory or failure, rewards, return to strategy, and save/load at relevant objective transitions. A debug tactical launch checks only part of this sequence.

---

## 3. Prior work and tools

| Item | What it gives you |
|---|---|
| **UDK 2011-09** ([Nexus 485](https://www.nexusmods.com/xcom/mods/485)) | Community-matched release for package version 845 / engine 8916; do not assume another UDK release is interchangeable. Setup and cooking notes: [UDK tutorials thread](https://forums.nexusmods.com/topic/5955538-udk-tutorials-tips-and-tricks/) (Drakous79, 2017). |
| **[iiiLiQuiDiii/UDK](https://github.com/iiiLiQuiDiii/UDK)** (2015) | XComGame stubs, `XComUDK` Kismet actions (`SeqAct_BuildWorldData`, `SeqAct_SetLOSBlocking`, `SeqAct_SetCover`, `SeqAct_LoadContent`, `SeqAct_ReplaceActorMesh`, `SquadVisiblePoint`, …), `XComMapCleaner`, asset stubs, and `.udk` sources corresponding to many installed patch names. Exact source/binary equivalence has not been established. Start here for authoring. |
| **[XCOM Uncooker](https://github.com/chrishayesmu/XCOM-Uncooker)** | Reconstructs EW maps/assets/Kismet for inspection in UDK. Evaluate before building a reference exporter. Latest published release found: [v1.1.0, 26 July 2024](https://github.com/chrishayesmu/XCOM-Uncooker/releases/tag/v1.1.0). Does not provide a playable round trip. |
| **[Long War Community Edition](https://github.com/chrishayesmu/XCOM-LW-CommunityEdition)** | Documents custom-material compilation patches and native-engine research. A source of specific techniques; its broad class replacement makes installing the entire mod alongside LWR a separate compatibility problem. |
| [wghost/UDK-EW](https://github.com/wghost/UDK-EW) | Dummy UnrealScript sources for compiling EW mods in UDK. |
| [wghost/XCOM-Mutators](https://github.com/wghost/XCOM-Mutators) | The mutator loader LWR uses (hooks patched into Engine, XComGame and XComStrategyGame). `XComLZMutator` (LZ, pod, Meld and bomb randomisation, council map selection) is in your install. |
| [wghost/UPKUtils](https://github.com/wghost/UPKUtils), [PatcherGUI](https://github.com/wghost/PatcherGUI) | Decompress, deserialise and binary-patch packages; add names, imports and exports. |
| UE Explorer (Eliot) | Decompiles XComGame classes. Source of the stub classes. |
| umodel / UE Viewer (Gildor) | Exports XCOM meshes, textures and fractured meshes for re-import (via Blender) into UDK. |
| Map mods | [X-COM Map Patches](https://www.nexusmods.com/xcom/mods/635), [Landed supply ship](https://www.nexusmods.com/xcom/mods/643) (a new mission *variant* from a crash map + cleaning patch), [Lost EU Maps](https://www.nexusmods.com/xcom/mods/575) / [REDUX](https://www.nexusmods.com/xcom/mods/879) (Jul 2026, tested with LWR, adds LZs), [Map patches for LW1.0](https://www.nexusmods.com/xcom/mods/780), [XCOM EW Map Pack](https://www.nexusmods.com/xcom/mods/453) (only re-assigns mission types to existing maps). |
| Research threads | [R&D XCOM Map Alterations](https://forums.nexusmods.com/topic/1104408-rd-xcom-map-alterations/) (48 pages, 2013–2015: the main record of what was tried), [R&D Maps](https://forums.nexusmods.com/topic/5936358-rd-maps/) (2017: Drakous79's plan for a from-scratch map, never finished). |

Historical demonstrations include:

- LiQuiD911's "overlay" test map: a streamed layer of re-imported cars giving cover, spawns, pods, civilians and EXALT objects on top of `CB2_MP_Blank`.
- New mission variants and cleaned versions of existing maps.

In an [August 2026 first-person report](https://www.reddit.com/r/Xcom/comments/1vj21eh/after_some_testing/), AllHailShadow726 describes custom geometry/cover on 8 August, claims custom-map success on 9 August, and reports custom textures rendering on 12 August. This is **author-reported prototype success**, not a reproduced campaign-ready release. The reviewed sources did not establish correct whole-map visibility/pathing, destruction and save/load together. No private Discord material was accessed and nobody was contacted.

### Uncooker integration details

Keep the Uncooker reference UDK separate from the authoring/script-building UDK: its setup replaces components. Reconstructed materials can be approximate and need manual replacements. Its [`XComWorldData.cs`](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/UnrealPackageLibrary/Unreal/ObjectSubtypes/XCom/XComWorldData.cs) reads the native pointer but does not write/remap it into the reconstructed package. Saving a viewed map therefore does not preserve the full native world dataset.

The [`command-line implementation`](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/XCOM-Uncooker/Program.cs) accepts input/output directories, skips `patch_` packages, and names four texture caches explicitly. Previewing all mod content and exchanging scenes with the authoring workspace require additional validation.

### Custom-material experiment entry point

[LWCE executable patch notes, patches 3 and 4](https://github.com/chrishayesmu/XCOM-LW-CommunityEdition/blob/71d2164ca8d76883ff5afa24ee5062596c880088/Notes/exe_patches.md) describe enabling runtime material compilation. A read-only scan of the installed `XComEW.exe` found **one original signature and zero modified signatures for each patch**. The [pattern audit](<evidence/executable-pattern-audit.json>) records offsets and the executable hash. This checks those specific signatures; it does not rule out every other shader modification.

Evaluate the focused material mechanism on an isolated test install before considering broader LWCE changes. Signature matches do not establish runtime compatibility. Record first-use shader hitches, cold-start/reload behavior, shader-cache persistence and texture serialization separately. No executable patches were applied during this research.

---

## 4. Capability matrix

| Capability | Status | Notes / source |
|---|---|---|
| Load UDK-built levels as streaming sublevels | **Proven, shipping** | 90 patch maps in this install. Rename `.udk` to `.upk`; cook for PCConsole. |
| Place XCOM gameplay actors (`XComLevelActor`, destructibles, ladders, volumes, spawn points) | **Proven** | Needs stub classes marked `placeable`, with XComGame listed as a **native** script package in UDK's `DefaultEngine.ini`. |
| New cover and pathing on new geometry | **Proven locally, with care** | Requires appropriate collision and rebuilding. Horizontal/vertical grid steps are 96/64 uu; align to the map origin. Whole-layout correctness remains a separate test. |
| Vision (LOS) blocking from new objects | **Partial** | Historical reports found problems with cover in open ground. Installed patches contain `SeqAct_SetLOSBlocking`, but the action changes flags without doing its own rebuild. Test LOS separately from cover icons. |
| Alien pods, alien spawns, civilians, Meld, EXALT objects, capture zones, wave system | **Proven (prototype)** | LiQuiD911, Jan–May 2015. |
| Mission logic via Kismet, including new custom Kismet actions | **Proven** | The `XComUDK` package is cooked into each patch map. |
| Move or randomise LZ, pods, Meld, bomb and nodes on existing maps by script | **Proven, shipping** | `XComLZMutator` and `DefaultLZMutator.ini` (453 LZ entries). `PlayerStart`, `XComBuildingVolume` and `PointInSpace` had `bStatic`/`bNoDelete` patched off. |
| Custom static meshes | **Proven** | `LadderMetal`, `CoverPatch` and re-imported vehicle meshes inside the patch maps. |
| Reuse existing Firaxis art | **Proven, dependency-sensitive** | Stub references can resolve to already-loaded copies. Donor streams and content-manager requests are additional avenues; arbitrary asset availability must be tested and indexed. |
| New textures | **Partial; newer success reported** | Installed UI textures and the August 2026 world-texture report are encouraging. Validate inline and custom-cache storage separately; the 90 installed patches contain no Texture2D exports. |
| New materials (shaders) | **Documented executable mechanism** | LWCE enables runtime compilation. Those two patches are absent here; LWR compatibility and reliable shader persistence are untested. Existing material instances remain a simpler starting point. |
| New skeletal meshes (doors, interactive objects) | **Unproven** | Interactive-actor code works; the art pipeline wasn't finished. |
| Brand-new map with no Firaxis base map | **Not reproduced here** | A newer author claims custom-map success, but independent initialization of a complete native world remains unverified. Test a bounded overlay and a standalone map separately. |
| Bigger maps than the base | **Unproven / hard** | `WorldBounds` and the tile grid come from the base map's `XComLevelVolume`. Objects outside it are decoration only. |
| Re-positioning a stream via `Loc=`/`Rot=` in DefaultMaps | **Debug only** | Offsets apply only from the debug skirmish menu, not in normal map rotation. |
| Several modders' UDK packages together | **Risky** | Duplicate NetIndex errors when separately cooked patches share edited classes. Use a unique script package per author and recook together. |
| Additional council scenarios in the campaign | **Concrete bomb-template example** | `XGFundingCouncil_Mod` provides a specific extension, not an arbitrary objective API. Test new-game and existing-save integration separately. |
| Inspect reconstructed Firaxis maps in UDK | **Available via Uncooker** | Maps, assets and Kismet can be inspected with reconstruction limits. Direct stock-UDK loading and a playable save-back round trip are different capabilities. |

---

## 5. Approaches

### A. UDK-hosted toolchain (recommended core)

UDK 2011-09 *is* the 3D editor: BSP, mesh placement, volumes, Lightmass, the Kismet graph editor and prefabs. We'd supply the XCOM layer:

- **Existing placeable stubs first**: use the public XComGame/XComUDK sources as the starting point. Generate additional stubs only where coverage is missing; the local property-table reader is not a complete class/dependency generator.
- **Reference inspection first**: evaluate XCOM Uncooker in a separate UDK installation. Add a T3D/reference exporter only for demonstrated gaps, using the local actor-property readers and umodel as needed. Validate transfers into the authoring workspace before depending on them.
- **Asset catalogue**: index actual object paths and package dependencies across the 2,993 top-level packages, which include scripts and other content as well as maps. Distinguish game assets, preview substitutes and new assets. Stub references must resolve to valid runtime content.
- **Mission templates** as UDK prefabs and Kismet snippets: LZ (PlayerStart + 6 spawn points + dropship volume + highlight), alien pod, Meld pair, bomb + nodes, capture-and-hold, EXALT wave, VIP.
- **Build and deploy script**:
  1. `make` scripts.
  2. Cook for PCConsole with a clean TFC.
  3. Rename `.udk` to `.upk` and copy into `CookedPCConsole`.
  4. Merge `DefaultMaps.ini` and LZMutator entries.
  5. Launch the game straight into the test map (console or debug skirmish).
- **Strategy hooks**: a mutator that registers new maps and mission types for council and special missions.

Store scene transforms/assets, tactical rules, campaign metadata and saved mission state separately in the editor project. Include stable object identifiers, fixed/randomized layout settings, objective transitions and package dependencies. The build manifest should identify the target game/mod version, any executable requirements, configuration changes and removal steps. This is a proposed authoring format, not a format the game already reads.

Validate custom assets in stages: existing assets → new static mesh with an existing material → new texture → new base material → skeletal/interactive/fractured asset. A mesh needs suitable XCOM actor settings and collision to behave as a gameplay prop; destruction and interactions require additional states, actions and points.

Downsides:

- UDK 2011 is old and crash-prone. "Engine.u loading freeze" was reported, and it is untested on Windows 11.
- Keep the reference and authoring installations separate; reconstruction is not a supported playable round trip.

### B. Runtime overlay mutator (good complement)

A mutator reads a per-map mission file (ini) at `PostLevelLoaded`. It spawns and moves actors (LZ, pods, spawn points, objectives, rebuild volumes, mesh swaps via `SetStaticMesh` and content loads) and runs light mission logic.

This could grow into an **in-game placement mode**: you place objects with the tactical cursor and the mode writes the ini. It's WYSIWYG in the real renderer, with no UDK needed for small edits. The LWR LZ, pod and bomb mutators already do a fixed version of this.

Limits:

- Art must be loaded or obtained through a tested content-loading route; arbitrary references are not guaranteed to work.
- No baked lighting.
- Static map actors need flag patches.
- Complex special missions are better done as streams.

### C. Standalone editor with its own package writer: not recommended

Replacing the compiler backend would require substantial UE3 v845 serialization/cooking work, including native world data, physics and shaders. That is a different and larger task than building a standalone interface.

A viable architecture to investigate is an external editor that **emits T3D / Kismet input for UDK**, using UDK as the compiler backend. Epic documents cooking through a [commandlet](https://docs.unrealengine.com/udk/Three/ContentCooking.html); reliable unattended scene import and saving still need a prototype. A standalone frontend can follow the initial UDK workflow once the output pipeline is validated.

### D. Binary patching of existing maps (legacy)

PatchUPK can edit existing actors and also add name/import/export entries, as described in its [documentation](https://github.com/wghost/UPKUtils/blob/9b2fd078a6f51ad2bd24aad9948378d2ce16edc2/doc/PatchUPK_Readme.txt). A complete actor insertion still needs valid level actor lists, references, native payloads and gameplay data. Table insertion is not itself a complete level-authoring pipeline.

---

## 6. Suggested plan

Use the detailed investigation plan as the execution reference. The phases below summarize its intent.

### Phase 0: setup

- Install UDK 2011-09 next to a copy of the `iiiLiQuiDiii/UDK` tree. Build the stubs and the `XComUDK` package.
- Set up a separate Uncooker reference UDK and evaluate inspection of one map and its Kismet. Do not apply its setup over the authoring installation.
- Open one of the patch maps from the repo (for example `patch_bar.udk`), cook it, and drop it into a **separate test copy** of the game install, not the live LWR install.
- Done when: a re-cooked `patch_bar` behaves the same as the shipped one.

### Phase 1: risk experiments (each answers a yes/no question)

The [verification report](<mission-editor-feasibility-update.md>) supplies the full eight-experiment matrix, beginning with the baseline patch rebuild in Phase 0. None of these gameplay tests has been performed in this research.

1. **One new prop:** place a custom static mesh on an existing map. Check appearance, collision, cover, LOS and any destruction independently.
2. **Custom art matrix:** compare a new texture on an existing material, inline versus separate-cache storage, and a new base material with the documented LWCE shader mechanism. Check cold starts, reloads, missing dependencies, compilation hitches and cache persistence.
3. **Whole-map overlay:** use `CB2_MP_Blank` within its existing 36×36×12 grid. Add/remove floors and walls; test multi-height pathing, ladders, cover/flanking, fog, shots, explosives, stale collision and mid-mission save/load.
4. **Persistent UDK map:** use its own `XComLevelVolume` without a borrowed container. Determine whether `BuildWorldData` can initialize the full world and record timing/failures. Successful initialization would justify separate size-expansion tests; it would not establish arbitrary map sizes.
5. **Standard mission through the campaign:** verify map selection, intended LWR squad/pods, victory, abort, rewards, return to strategy and save/load.
6. **One scripted objective:** test a bomb or extraction template with reinforcements and failure conditions. Save before/after objective transitions, and distinguish new-campaign support from existing-save support.
7. **LWR coexistence and installation:** test multiple authored maps, existing patches/mutators, fixed and randomized placements, repeated saves without duplication, and clean removal.

If the whole-layout overlay succeeds but standalone initialization fails, a bounded-shell editor remains useful with explicit size limits. If shaders remain unreliable, restrict the initial editor to a validated material palette. The first convincing milestone is one small authored encounter with a new cover prop, deliberate XCOM/alien placement, campaign victory and save/reload.

### Phase 2: tooling

Existing stubs and Uncooker evaluation → asset/dependency catalogue and any needed reference adapter → mission templates/validation → repeatable build/config merge/uninstall manifest → targeted lifecycle and strategy hooks. Extend the local readers where needed rather than assume they already form a complete exporter.

### Phase 3: front end (optional)

In-game overlay editor (approach B), or an external editor that emits T3D for the UDK backend.

---

## 7. Risks and open questions

- **UDK 2011-09 on Windows 11** (DX9, 32/64-bit): stability unknown. Keep a VM or fallback in mind.
- **Distribution:** reference inspection and redistributing game/third-party assets are separate concerns. Preserve source attribution and asset provenance; this research does not establish redistribution permissions.
- **LWR changes often** (`LWRebalance.u` and `XComGame.upk` changed in late Oct 2026). Keep editor output in its own packages and its own `DefaultMaps.ini` lines, and test against a copy of the install.
- **Map selection:** new maps compete through `InitialChance`, `InitialGain` and `NewMap`, plus a per-profile map history (`ResetMapCounts` and `DumpMapCounts` console commands).
- **Mod order and versioning:** preserve the two final LWR mutator entries, account for randomization and save restoration, and record the installed executable/package hashes. Existing support for additional map layers does not establish that custom-material or campaign-hook changes need no additional compatibility work.
- **Native world data:** Uncooker does not preserve the native pointer in its output, and an exported `BuildWorldData` function does not demonstrate full standalone-map initialization.
- **Evidence strength:** installed package contents are static evidence; historical and August 2026 demonstrations are community reports. No public end-to-end editor satisfying all requested capabilities was identified in the reviewed sources, which does not rule out unpublished work.

---

## 8. Local tools produced during this research (`tools/upk`)

Pure Python, no third-party dependencies. These are experimental v845 inspection tools, not complete native-object decoders or a cooker. The general readers handle package-chunk LZO; the installation audit additionally decodes headers inside fully compressed outer wrappers.

| Script | Use |
|---|---|
| `upkinfo.py <pkg> [summary\|imports\|exports\|names]` | Header, export class counts, import packages, full object lists. |
| `decomp.py <pkg> <out>` | Write a decompressed copy (LZO). |
| `props.py <pkg> <ObjectPath> […]` | Dump tagged properties of exports, including map actors (handles the actor state frame). For example: `props.py URB_Bar.upk TheWorld.PersistentLevel.XComAlienPod_Abduction_0` gives `NumAliens_Min=2`, `Location=(1598.8,1642.2,1.5)`. |
| `lzo1x.py` | LZO1X decompressor used by the above. |
| `audit_install.py <game_root> <output.json>` | Read-only inventory of all top-level EW package headers, all patch export tables, selected properties, map configuration, file hashes and the two documented material-patch signature counts. Refuses an output path inside the game installation. |

Use Python 3.11+ for the audit. The Windows Store `python.exe` alias did not run during this investigation; the installed uv-managed Python 3.12 interpreter did. See the [evidence README](<evidence/README.md>) for the exact working command and parser limitations.

## 9. Retained evidence

- [Installation audit](<evidence/installed-game-audit.json>): 2,993 package headers, 90 patches, 188 map records, selected properties and hashes. Final collection reported no package/property parsing errors.
- [Executable pattern audit](<evidence/executable-pattern-audit.json>): read-only results for all four documented LWCE executable signatures; no patches applied.
- [Public source manifest](<evidence/upstream/source-manifest.json>): 32 source files with exact commit URLs and SHA-256 values, retained unmodified alongside repository tree listings. Sources were inspected, not executed.
- [Detailed verification report](<mission-editor-feasibility-update.md>): source discussion, proposed project-data fields, architecture diagram and experiment acceptance criteria.
