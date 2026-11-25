# Forum and wiki notes (3 November 2026)

Read through Claude in Chrome on 3 November 2026. These are claims made by the original authors in 2013–2015, not results reproduced here. Dates are the post dates.

Sources:

- Nexus forum thread [R&D XCOM Map Alterations](https://forums.nexusmods.com/topic/1104408-rd-xcom-map-alterations/): 48 pages, 474 posts, September 2013 to October 2015. Pages 7–48 were read in full. Pages 1–6 are covered by the wiki's Maps page.
- Nexus wiki: [Modding with the UDK](https://wiki.nexusmods.com/index.php/Modding_with_the_UDK_-_XCOM:EU_2012), [Developer Console](https://wiki.nexusmods.com/index.php/Developer_Console_-_XCOM:EU_2012), [Maps](https://wiki.nexusmods.com/index.php/Maps_-_XCOM:EU_2012), [Spawn Points](https://wiki.nexusmods.com/index.php/Spawn_Points_-_XCOM:EU_2012) and [Units deployment](https://wiki.nexusmods.com/index.php/Units_deployment_-_XCOM:EU_2012).
- Reddit [After some testing…](https://www.reddit.com/r/Xcom/comments/1vj21eh/after_some_testing/) (AllHailShadow726, August 2026). Claude in Chrome, the built-in browser and WebFetch all refused Reddit. The post, its comments and its two screenshots were pasted in instead. See the last section.

## Line of sight (the main open risk)

- **New cover on open ground does not block sight.** LiQuiD911, 11 March 2015: streaming an object onto existing cover can turn that cover into sight-blocking cover.
- **Rebuild volumes move cover, not sight-blocking.** LiQuiD911, 10 January 2015: `XComRebuildWorldDataVolume` placed cover at the new position, added no sight-blocking there, and removed the sight-blocking at the old position.
- **The bomb blocks sight only in some directions.** LiQuiD911, 28 February 2015: when streamed onto `CB2_MP_Blank`, it blocked sight only where the original map had other objects next to it.
- **Rebuilt walls stay see-through.** LiQuiD911, 26 April 2015: calling `ResetHealth`/`ResetVisibility` on a fractured wall restored the wall, but it did not block sight.
- **Proposed workaround, untested.** johnnylump, 7 February 2015: a hidden smoke-like volume using `XGTacticalGameCoreData.EVolumeEffect_BlocksSight`, created the way the `AddSightBlock` console command does (`CreateVolumeByType`). Also see `XGVolume.SetSightBlocking`. There is a stated limit of 255 volumes, which includes fire and smoke.

## Textures, materials and packaging

- **Missing cache textures crash the game.** LiQuiD911, 6 July 2015: "If you place any object that has a texture not present in the xcom TFC the game will crash." A stub texture loaded on a level that lacks it also crashed (28 January 2015).
- **EU maps were partly restored in EW (April 2015):**
  - Copy the EU `Textures`, `Lighting` and `CharTextures` caches under new names.
  - Rewrite each `TextureFileCacheName` to the new name.
  - At High texture quality some textures render black; Low quality fixes this. So the embedded low-resolution mips work while the references to high-resolution cache mips do not.
- **Materials without a cached shader fall back to the default material.** The log lines are:
  - `Missing cached shader map for material …, compiling.`
  - `Can't compile … with seekfree loading path on console, will attempt to use default material instead.`

  These are the lines to search for in the A0–A5 art tests. Drakous79 saw the same thing for a licensee-0 UDK material on 12 October 2014. Hex-editing the licensee field to Firaxis's value crashed with `Serial size mismatch`.
- **Adding name-table entries breaks embedded textures.** wghost81, 13 April 2015: new entries shift the absolute bulk-data offsets in the file. Any binary patcher must recalculate them.
- **NetIndex** (wghost81, April 2015):
  - It is the first four bytes of each export's serialized data, which UPKUtils called `PrevObjRef`.
  - It is unique within the original (pre-cook) package, and objects from different packages collide.
  - Duplicates log `(AddNetObject) … duplicate NetIndex`. By Long War beta 15 they caused visible bugs, such as the move-path preview not showing on Museum maps.
- **Uncooked map packages did not work for this.** LiQuiD911, 7 January 2015: a static mesh did not show in an uncooked map. Copy the cooked output from UDK's CookedPC folder, not from Content.
- **Asset stubs only resolve to content that is already loaded.** LiQuiD911, 16 January 2015: they do not force their package to load.

## Runtime content loading (a possible art route)

- **Meshes can be loaded by path at runtime.** `XComContentManager.GetGameContent("Package.Group.Name")` returns content, and `XComDestructibleActor.SetStaticMesh(...)` swaps meshes (LiQuiD911, 4 March 2015). `XComAlienPod.PostBeginPlay` uses the same call for `CHH_FoggedMaleCivs.Meshes.CivAlienPod`.
- **Packages can be loaded globally.** The wiki says custom content packages can be loaded through `DefaultContent.ini` (`Package=…`).
- **Possible variant:** together these suggest keeping custom meshes in a separate package rather than cooking them into every map. It belongs in the art matrix, once the texture-cache rules are understood.

## Pods, spawns and deployment (from the wiki, from wghost81's code reading)

- **Where pods come from.** They are placed from `XComAlienPod` actors in the map, and the number of those actors caps the number of pods.
- **Filtering:**
  - `GetPossibleSpawns` keeps only pods with `bUse` set that are in `Group0`.
  - `bCommanderPod` marks commander placements. Without one, the commander pod goes to the farthest point.
  - `CustomStartLocations` (an array of `XComSpawnPoint`) overrides the 3×3 spread around the pod's location.
  - `PathNodes` and `LoopType` give patrols.
  - Type 2 marks a secondary pod.
- **Pods on maps without placeholders:**
  - The wiki suggests `XComAlienPodManager.SpawnAllPodAliens` has fallbacks that would create aliens "even on totally empty map".
  - johnnylump (10 September 2014) says vanilla spawns no aliens without placeholders, and only Long War's random pods place them anyway.
  - EXP-05 should settle which is true under LWR.
- **Initialization order** (`XGBattle` state `Initing`):
  1. `InitDescription`
  2. `InitLevel`
  3. `PostLevelLoaded`: `InitMeldContainers` and `InitCapturePoints`.
  4. `InitPlayers`: `XComAlienPodManager.InitPods`, then `XGAIPlayer.LoadSquad` → `CreateSquad` → `XGOvermind.Init`, which runs `XGDeployAI.DeployPods` and then `InitWaveSystem`.
- **Soldier start points:**
  - `PlayerStart_N` is linked to six `XComSpawnPoint` actors by `Tag` (`Group0`, `Group1`, …).
  - Meld spawn points (`XComMeldContainerSpawnPoint`) use the same tag.
  - Kismet chooses the group on multi-entrance maps.
- **Reinforcements:**
  - EXALT, capture-and-hold and HQ waves are a placed `XComWaveSystem` actor.
  - Council missions use Kismet: `SeqEvent_RoamingAlienNumberSet`, `SeqAct_AlienContent_Request` and `SeqAct_SpawnAlien`.
- **`DynamicAliens[]` in DefaultMaps only loads pawn content.** Spawning an alien whose content is not loaded crashes (Amineri, 2013) or produces an invisible pawn (LiQuiD911, January 2015).
- **Kismet-spawned civilians.** `SeqAct_SpawnCivilian` with team `eTeam_All` behaves like a VIP. Civilians moved onto the XCOM team did not regain action points.

## The landing zone and base-map actors

- **The landing zone was a prefab** (`DGN_DropShipSoldierSpawn`). Cooking flattens it into ten actors: `PlayerStart`, `PointInSpace`, the `XComBuildingVolume` (the real extraction zone), the `XComLevelActor` highlight, and six spawn points.
- **The Skyranger and its shadow are part of the base map.**
- **`SeqAct_RemoveActor` removes the exact actor or every actor with a given `Tag`.** Base-map landing-zone actors meant for removal carry `Tag=deleteme`.
- **Some base maps ignore streamed spawn points:** Trainyard, TrainStation, IndustrialOffice, CemeteryGrand and StreetOverpass. One cause is that `PlayerStart`, `XComBuildingVolume` and `PointInSpace` have `bStatic`/`bNoDelete` set.
- **`XComLZMutator` runs before the map's Kismet.** That is why it can override landing-zone selection on UFO maps but not on heavily scripted rescue and EXALT missions.
- **Spawn points can come from the stream.** A base map that has no spawn points will not run an abduction unless a stream supplies them (LiQuiD911, 6 September 2014).

## Shell-map facts relevant to EXP-06

- **Floors live in world data, not meshes.** The ground in `CB2_MP_Blank` is 16 square tiles placed as level actors. Units can path across a removed tile but cannot end a move on it.
- **Clearing actors leaves cover and shadows behind.** Zeroing entries in `TheWorld.PersistentLevel`'s actor list removes those actors without a crash. Their cover stays until a rebuild volume covers it, and their shadows stay.
- **Shadows are baked per square sector.** Each map has one `DominantDirectionalLightComponent`, and it holds a ShadowMap.
- **The two volumes have different jobs.** `XComLevelVolume.XComWorldData` bounds where aliens spawn and creates a "wall of darkness". `WorldBounds` sets the red border and camera limits, in multiples of 96. Moving `WorldBounds.Min` shifts the cover data while the meshes stay put.
- **There is a test for "inside the map".** `XGLevelVolume.EncompassesPoint`. `FindClosestValidLocation` can fail silently and return its input unchanged.

## Configuration

- **`StreamingMaps[]` indices can be sparse.** `StreamingMaps[100]` worked (wghost81, 18 May 2015), so a tool can append at a high index without renumbering.
- **Council missions are tied to hard-coded display names.** `XGFundingCouncil.BuildMission` uses fixed DisplayName strings. LWR's `XGFundingCouncil_Mod.FixDisplayName` finds the configured entry by substring (`InStr`), so extra text such as ` |4` after a name still matches. What `|N` means is still unknown.
- **Map selection is native and uses the per-profile map counts.**
  - Removing or commenting out a `Maps=` line stops a map being used.
  - Setting `bInRotation=false` had no visible effect in one vanilla test (wiki Maps page). The flag count in the research report is therefore not proof of what rotates.
- **DefaultMaps changes went to the generated `XComMaps.ini`.** Older reports edited the generated file in My Games and noted that it is rebuilt on every launch.

## Testing aids

- **The console needs a patched `Engine.upk`.** EW disables the console natively, and Long War's console patch rewrites `Engine.IsConsoleAllowed` (the shipped `Engine.upk.renamethistoenableconsole`).
  - The console key is `\`.
  - Per the wiki, the console only works when the game starts without a `-language=` argument, in English. Multiplayer refuses it.
- **Useful commands:** `show volumes`, `show collision`, `ShowDebug` (cursor location), `ShowCursorLoc`, `teleportToCursor`, `toggleFOW`, `show postprocessing`, `showlog`, `DumpMapCounts` and `ResetMapCounts`.
- **`DefaultCheats.ini` has a `WinHQAssault` command set.** Its commands are `set xcomwavesystem m_benabled false`, `set seqact_delayvictory bNoLongerDelayed true` and `killaliens`. They can switch off waves or end a mission during tests.

## Prior art status

- **LiQuiD911's UDK repository is still up.** [iiiLiQuiDiii/UDK](https://github.com/iiiLiQuiDiii/UDK) was last pushed on 6 July 2015.
- **The earlier stubs repository is gone.** `iiiLiQuiDiii/XComGame-Map-Stubs` returns 404.
- **The October 2015 wave-system override is not in the repository.** It was `patch_override_wave_system.upk` plus `DefaultWaveSystem.ini`, an INI-driven reinforcement system, posted only as a Dropbox link that was not checked. Its author reported that `DisableEvent` and `OnGroupActivated` did not work. It is not in this install.
- **LiQuiD911 found the UDK editor unstable.** The editor often froze while loading `Engine.u` with this tree and could take about ten restarts to open (6 July 2015).

## The August 2026 Reddit thread (from a paste)

What the author says:

- **Cover depends on collision.** Cover is tied to the collision of the mesh the cover actor uses, not to the visible geometry. So any custom mesh with proper collision can give working cover.
- **Tools.** The UDK 2011-09 build (the one used for EU voice mods), plus actor classes ripped from the game files, plus INI edits. No other coding is needed.
- **Plans.** The author intended to publish those classes after trying destructibles.
- **Update 1:** "Custom maps are in fact possible". No details are given.
- **Update 2:** custom textures rendered without the game crashing. No method is given.
- **Where the real discussion is.** The author is in the LWR Discord and has talked to the LWR developers and to people in Beaglerush's community.
- **A disputed claim.** Asked whether custom cover was impossible before, the author said yes, as far as they knew.

What the two screenshots show:

- **The base is a Firaxis map.** It is a stock night street map with fog, a taxi, a red SUV and street lamps. Both pictures show a layer added on top of a Firaxis base map, not a map built from scratch.
- **A new box gives cover.** A box on the pavement, about two tiles across with a recess in the top, shows cover shields to the units beside it.
- **Line of sight is not shown.** Nothing in the pictures shows whether the box blocks sight or shots.
- **The box's texture may be the default material.** It has a blue-and-white checker. That looks like the engine's default material, which the game uses when a material can't be compiled. A 2015 post describes missing elements turning into "LightGrey+Violet" placeholders. This is a guess from the picture; the checker may also be a deliberate test texture.

How this compares with the 2015 record:

- **The cover finding matches LiQuiD911's.** In January 2015 a cube with no collision box gave no cover, while a re-imported pickup truck gave half or full cover. The 90 installed `patch_*` maps already add cover actors. Custom cover was therefore possible before; the new parts are the claims about whole maps and textures.
- **Still unanswered by this thread:**
  - Whether the box blocks sight on open ground.
  - Whether a map with no Firaxis base underneath gets working world data.
  - How the textures were packaged.
  - Whether materials compile.
  - Whether it all works in the campaign and through save/load.
- **No public release found.** One web search on 3 November 2026 found nothing released by the author.
