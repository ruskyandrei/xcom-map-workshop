# Findings register

Every detail found so far that a placed or spawned object needs in order to behave like one of the game's own, plus
the toolchain's traps. Each finding has an ID, a status and its fix. The experiment notes
(`research/experiments/EXP-*.md`) keep the run-by-run story and point here by ID; new findings get the next free ID.

Statuses:
- **Open**: not solved.
- **Fixed**: a fix is in place but hasn't been confirmed in game yet.
- **Verified**: confirmed in game; the run that showed it is named.
- **Accepted**: a known limit we live with for now.

## Open now

- F-119: a moved landing left the grounded Skyranger's dust effect (Bar's `Emitter_0`) where the landing was; fixed
  offline in export 35 (18 November: the dust is the Skyranger's `dust` and moves with it); not looked at in the
  game. Under Long War the mutator destroys that dust on every load anyway (F-120), so this matters for plain EW.
- F-117, F-118: a variant replacing Commercial Alley Redux now keeps the first mission's record name, and Replace
  comments out only the base map's records the variant has records for, so the first mission always has a map
  (fixed offline, 17 November); not played in a new campaign.
- T-42: custom visible walls and terrain have a credible route from the generated cover-box writer, but need a
  general mesh/collision writer and fresh lighting. The farm ramp is an ordinary static mesh; native-style custom
  fracturing is a separate gap (EXP-66, read-only audit, 16 November). 17 November: a fracturing wall made from
  numbers is built (branch `fracturing-wall-poc`), and EXP-67 passed its look and its break in the game: the user
  called the proof of concept successful (one tile at its doorway: F-116).
- F-116 (the doorway part): a one-tile doorway with no door gives cover toward its sides, by the game's own rule; a
  door in it is not tried.
- F-113 (its sight part): whether a hidden high cover block stops sight at eye level is unchecked; in EXP-59 run 1
  the user saw and shot across a one-tile wall, most likely by leaning round its ends.
- F-55: rebaking and whole-map dynamic lighting have credible routes, but need native-data/rendering proofs
  and fidelity/performance checks (EXP-15; separate lighting research).
- T-10: a UDK-free patch builder is plausible from compiled templates, but still needs a writer and in-game
  qualification (EXP-12; dependency-replacement assessment).
- F-48: editor placement must be qualified by piece recipe; source maps use off-corner pivots and non-cardinal/full
  rotations, while current tools impose additional limits (EXP-09, read-only audit). EXP-11 run 1: static pieces
  with full rotations and off-centre pivots stand exactly as posed, and the places moved or deleted pieces left open
  up (run 2).
- F-49: a piece lifted a level (64 units) above the floor gives no cover there (EXP-11 run 1). The viewer marks such
  pieces.
- F-50: effects the map placed around a piece (emitters, lights, decals) stay behind when the piece is moved or
  deleted (EXP-11 run 2: the fog pod's green smoke).
- F-51: Temple Ship's doorway walls aren't drawn in the lab: in the test slot (EXP-14 runs 1 and 1b, also unedited)
  and in the real mission from a tactical save (run 2). Run 3 checks a normal start from the HQ.
- F-52: copies looked bluer than the map's baked pieces (EXP-14 runs 1 and 4). The cause is Temple's sky light, a
  units-only fill in `CompositeDynamic` that every light environment takes. Fixed (run 7); the default for every
  copy and spawned piece since run 8 (`XComMapEdSkyFree`). Damage brought it back (runs 10 and 11). Since run 12
  the sky light is moved to the units' channel instead: passed in the game (a grenade keeps the tone, the soldiers
  look normal).
- F-53: the psi device copies give no cover at their ends (EXP-14 run 1). This is likely the piece's shape and
  lower lean; the sides are not yet checked.
- F-54: copies made after loading a tactical save from before the patch don't block or give cover (EXP-14 run 2).
  The save's own tile data replaces our rebuild. A fresh start works (run 4); check variants that way.
- F-45 again: no Build variant had a dropship intro (EXP-20 run 8). Verified in EXP-20 run 9: the Build streams the
  variant's own intro copy (`intro_copy.py`), and the Skyranger lands.
- F-59: Builds of maps other than Bar and Temple Ship (several records and intros, no `TriggerVolume_0`, pieces that
  cast no shadow) are fixed offline; a copy's rebuild volume cloned from another volume class is still to be played.
- F-77: on Act1_IntroLevel a rebuild volume is cloned from its lightmass importance volume; EXP-30 run 2 played the
  build (the car gone), standing on its tiles not shown (the grid's edge).
- F-78: Act1_IntroLevel alone crashed with no record; Play in game now puts a copy of its record in (offline), EXP-30
  run 3 to play.
- F-68: what the game makes of a fracturing piece that names no toughness (852 on the install's maps) wasn't worked
  out; the editor's Health line says so.
- F-69: fracturing pieces of their own (walls, storey floors) build since 9 November, their fragment columns carried
  with each copy and its neighbour and door listings kept only for pieces copied by the same move; EXP-28 run 1
  passed for a wall with its doors, a moved counter section and a deleted wall. Still to play: a wall's copy against
  other walls, and a copy moved by a storey.
- F-70: physics props build since 9 November as clones made in the map; Bar's corpses show in the game (EXP-28
  run 1). What their tag `deleteme` is for, and a clone that isn't a corpse lying flat, are open.
- F-71: a floor's copy gets floor only on tiles with standing room over them (EXP-28 run 1: 4 of 10 tiles, the rest
  under an air duct); the editor doesn't warn of it.
- T-20: a quick build (no bake) matches a full build everywhere but the lighting, offline; still to play one.
- T-26: a copy of a piece lit per vertex (CLrgScout_Stonewall's vine, Temple Ship's four door volumes) builds
  since 9 November but keeps its original's light: the relight writes textures only. Not played.
- F-06: LWR's landing zone can land the squad on our objects.
- F-85: LWR can replace the landing, pod and Meld points at battle start, and choose a scripted drop-in point
  when its action fires. EXP-43, EXP-51 and EXP-53 cover some of these paths.
- T-31, T-32: pieces from other maps look feasible by copying a piece and what it depends on into the map (the
  game's art is the same in every map, its shaders and textures shared); measured offline on 11 November. The
  transplanter is built, passes its offline test on every base map (T-31), and two plain props of other maps played
  in URB_Bar (EXP-37, quick build). Not in the editor yet; the plan is
  cross-map-assets-implementation-plan.md, X5 next.
- F-14 follow-ups: objects without glass have no way to start a fire yet. Our glass columns now log as damaged but
  never destroyed; check that broken windows still update line of sight.
- Fixed but still to confirm in game: F-05 (canisters and pods avoid our objects).
- EXP-07:
  - F-19 and F-20 (the hider skipped most of the bar) worked in run 2.
  - F-22 and F-23 are verified in run 3: the bar can be taken out of play completely, and a save and reload keeps
    it out.
  - F-25 (line of sight) and F-26 (a hidden door's "open door") are verified in run 4. Step 2, the hide test, passes.
  - F-27: the cutaway re-shows some of the switched-off bar's effects. It's caught by the hider's check, which now
    runs all mission.
  - F-21 (no roof and no way up once the bar's volumes are off): the likely cause is that the map-wide cursor volumes
    were taken out. The hider keeps them since step 3b; still to confirm.
  - F-24 (baked shadows left on the ground) is accepted for now.
  - F-28 (copied fractured walls render black) is fixed in run 4: the wall needs its own light environment.
  - F-29: copied walls let line of sight through wherever their tiles were empty in the map's baked data. The
    rebuild queues only tiles whose baked flags already have one of the low 12 bits (found in the native code).
    Verified in runs 11 and 12: patchtool seeds those bits in the lab's copy of the map at deploy.
  - F-30 (a moved ladder can't be climbed) is fixed in run 21: copies now take `bPathColliding`, so the copied
    roof is floor up to its edges, and the patch's hidden ladder gets its climb. F-33 (a door kicked twice) came
    back in run 20 from the hidden double door; run 21 moves hidden doors and ladders under the map (to confirm).
  - F-36 (a hider hid the copied doors) is verified in run 28 ("doors are in"). F-37 (copied doors are
    must-destroy) is fixed in run 29, but they still couldn't be opened. F-38 (copies never enter `_Pristine`, so
    neither doors nor windows work) and F-40 (`bInteractive` not copied) are verified: doors in run 30, windows in
    run 31. F-41 (cars off the tile grid block their end tiles) is fixed in run 32, to confirm. F-39 (a ladder's mesh copy took its foot tile, so no climb) is verified in
    run 30.
  - EXP-08:
    - F-46 (a gap in the ground meshes still has floor in the tile data, so units path across it) is open, set aside by the user.
    - F-47 (a copied second floor gets no floor tiles) is open, set aside by the user: run 3b's fix (no ceiling
      beams) didn't help. It is a script copy's: a floor copy made in the map, as the editor's Build makes it, gets
      floor tiles at a new level (EXP-27 run 1, 9 November).
    - F-43 (pieces at the play area's edge stay when a box hides the play area) looks fixed in run 1: no edge pieces
      in the user's shot.
    - F-44 is withdrawn: the corpses come with the pods.
    - F-45 (no dropship intro on a renamed map: the landing prefab's pieces, then the map-name switches in
      `CIN_DropshipIntros`) is verified in run 1c.
  - F-31 (the new building's roof doesn't cut away) is open: pawns do register inside the new building (run 16), so
    the cause is further on. F-32: a small copied piece can be lit unlike its neighbour.
- F-100: a map grown as it is had no floor over the map's own scenery in the new area: the scenery outside a play
  area has its collision turned off (the user's intro+ build, 13 November). Fixed offline the same day (the Build
  turns it on for the low pieces in the new area); to confirm in the game.
- F-102: Temple Ship's arches can't be clicked: Firaxis set `bIgnoreFor3DCursorCollision` on them. Turned off with
  the editor's Mouse picks it and played (EXP-60, 16 November): the arches can be clicked and stood on. Open: whether
  the floor under an arch can still be clicked where the arch's top is in the same cursor storey.
- T-37: a full build of a map grown with nothing else stops in the relight (`--receivers-near needs an edit`); a
  quick build, or a grown grid with anything made in the map, builds (16 November).
- F-114: the five piece flags (walking, cover, sight, floor, mouse) read from the game's scripts, its class defaults
  and every listed map (16 November); the editor's Flags edits them. Played: Mouse picks it on, on Temple Ship's
  arches (EXP-60); every flag off on a statue and its plinth, walked through and not picked (EXP-61); each flag alone
  on copies, a door, a ladder and a hedge (EXP-62). Blocks walking on a low piece stops no one: the editor says so
  (`flags-low`). Open: a prop's gate on a tall prop, a ladder's cover and a door after opening it are not played.
- F-115: the test squad's records follow the scripts (body from the armour, LWR's scanner and smoke charges in perk
  entries, units 7 and 8 behind the landing points). Verified in EXP-64 (16 November, LWR): the default six, two
  SHIVs, a MEC with both modules, the grapple, the four grenade kinds, flight, squadsight, eight units on a map and
  in a prefab test, and a save and load all passed. Plain Enemy Within's soldiers-only squad is not played.
- F-111: cover, step-outs, flanking and sight inside sight radius come from the tiles' data alone (read 15
  November, checked against baked data). Not compared with a battle yet: one short run of a soldier on a known
  tile would settle the sight walk.

## Rendering

### F-01: A borrowed mesh renders flat grey
**Verified** (EXP-05, try 2 in game, 22:02).
- Cause: the mesh alone comes without the materials the map assigns.
- Fix: copy the materials from the source actor or archetype too (`SetMaterial` per slot).

### F-02: Spawned copies of destructibles render black
**Verified** (EXP-05 run 5, 23:04).
- Cause 1: a straight copy of the archetype keeps `bUsePrecomputedShadows=TRUE` (from `StaticMeshActor`) with no
  lightmap of its own. The flag is `const` in script, and the game's `ForceDLELighting` doesn't change it.
- Cause 2: level actors don't tick (`bTickIsDisabled`), and an actor that doesn't tick doesn't tick its components,
  so the light environment never computes any light.
- Fix: `XComMapEdDestructible` (in `XComMapEd`). Its defaults turn the precomputed shadows off and give it a dynamic
  light environment, and it ticks.

### F-03: Paint per object
**Verified** (EXP-05 run 5).
- Fix: set `TintColor` and call `UpdateTintColor()` on both the car and its glass.

## Tiles, cover and placement
### F-114: Five flags on a piece decide how the game's tiles and mouse use it
**Open** (16 November 2026: read from the decompiled scripts, the game's script packages and the native reading of
the tile build; surveyed over the 153 listed maps; played in EXP-60, EXP-61 and EXP-62). A reference fact, and what
the editor's Flags group edits (piece flags plan). [native/piece-flags.md](native/piece-flags.md) has the detail.
- **The flags:** Blocks walking (`bAlwaysConsiderForCover`), Gives cover (`bIgnoreForCover` off), Blocks sight
  (`VisibilityBlockingData.bBlockUnitVisibility`), Floor (`bPathColliding` and `bCanStepUpOn`), Mouse picks it
  (`bIgnoreFor3DCursorCollision` off). Settings, the inputs the filters read; geometry and other pieces still count.
- **Classes:** a prop, a collectible, a ladder and a door are `XComLevelActor` children and read its flags; a
  fracturing piece has its own copies. A static mesh actor and a KAsset are never counted for walking, cover or
  sight, and the mouse never picks them; they can be floor. The mouse never reads a door's flag. A ladder never gives
  cover by the normal test.
- **Class defaults** (the game's `Default__` objects): props, ladders, doors and fracturing pieces save
  `bPathColliding` false, so they are no floor unless the map sets it; fracturing pieces also `bCanStepUpOn` false;
  doors `bInteractive` true.
- **A prop's gate:** `bIgnoreForPathing` makes every world trace pass a prop (pathing, cover, sight) but not the
  occupancy step. Turning any of the three on needs it cleared, which turns the others on unless they are written off.
- **The maps:** 29,523 drawn, colliding pieces of 925 meshes have walking, cover and sight off (bushes, rubble,
  signs, posters); the same TV mesh is set differently from place to place (10 of 13 maps with TVs set them more than
  one way). 65 actors take settings from an archetype in another package the map doesn't carry.
- **Played:** Mouse picks it on, written by the editor's Build on 68 of Temple Ship's level actors, the arches among
  them: the cursor lands on an arch and a soldier is sent onto it ([EXP-60](experiments/EXP-60-temple-arches-mouse.md),
  F-102). Every flag off on Act1_IntroLevel's statue and its plinth, where they stand: a soldier walks through
  them and the cursor passes them ([EXP-61](experiments/EXP-61-intro-statue-flags-off.md)).
  On URB_Bar's copies ([EXP-62](experiments/EXP-62-piece-flags.md)), each flag alone does what the panel says: a box
  stack with Blocks walking off is stood in, one with Gives cover off gives none, one with Floor on has its top as
  floor (the tile over it); tall fences give high cover with Gives cover on and are seen across with Blocks sight off.
  They break and save as the map's own. The bar's door with Blocks walking and Blocks sight off is walked through
  shut, without opening: its edge's pathing and sight bits are gone. The ladder with Blocks walking off climbs as
  before and changed no tile.
- **Blocks walking on a low piece stops no one** (EXP-62): a 36-unit hedge with it on (its gate opened) leaves its
  tiles partly occupied (the low occupancy box only, the floor kept) and under the crossing sweep, so units walk
  in. It stops units only on a piece that reaches the crossing sweep (64 over the floor). The editor names such a
  piece under its Blocks walking row and warns when a project turns it on (`flags-low`, piece flags P8).
- **Not known:** what opening the gate does to the sweeps on a prop tall enough to meet them (the hedge and the
  parking blocks are too low); whether a ladder still gives cover beside it; a door's flags after it is opened and
  shut; a shot across a fence with Blocks sight off; why EXP-62's control box stack and its Gives cover off copy
  each occupy four tiles. A low piece with its flags off can still change the floor under a cover location (plain
  engine traces).


### F-111: Cover, step-outs, flanking and sight inside sight radius are decided from the tiles' data alone
**Open** (15 November 2026: read from the exe copy and LWR's scripts, checked against baked data, not compared
with a battle; [native/cover-and-sight.md](native/cover-and-sight.md) has the summary, the checks and the open
points). A reference fact, not a defect.
- **Sight inside sight radius is a walk over tiles**, from the viewer's eye tile (one level over its floor tile),
  stopped where either tile of a step has its sight bit toward the other. No collision is traced, units don't
  block, smoke doesn't matter. Beyond sight radius (squadsight) it is a line check against level pieces with
  `bBlockUnitVisibility`. This is what F-29 and F-25 showed in the game before it was read.
- **The blocking bits are `0x7E` (pathing) and `0x1F80` (sight)**, in the order −X, +X, −Y, +Y, down, up. The
  script's `0x3F` and `0xFC0` are one bit low; the rebuild's queue test (any bit of `0xFFF`) uses them as they are.
- **The cover table's East is −X and its West +X** (cover flags `0x4` and `0x8`); North is +Y.
- **Step-out sides are baked** in the cover flags; a step-out is sight from the tile to that side.
- **Flanked** needs every cover direction of the target to have the attacker on its far side.
- **A tile's cover is built by one rule** in the game's editor and in the battle's rebuild: a thin box swept from
  the tile's middle at 44 to 60 over the floor, toward occupied neighbours only; high cover when the same sweep
  96 over the floor hits. F-49 (no cover from a piece lifted a level) follows from the sweep's height.
- For the editor: the map's own tiles can show cover, blocked edges, step-outs and sight from the baked data with
  no predictor. Edited tiles need the build's rule run on the project's pieces; on URB_Bar the rule gives the
  baked cover location on 209 of 213 tiles tried and high or low on 199 of 209. The plan is
  game-reference-plan.md.

### F-04: Spawned objects aren't in the tile data
**Verified** (EXP-05 run 5: cover shields beside the row).
- Cause: cover, pathing and visibility tiles are baked into the map. A spawned object isn't in them, so it gives no
  cover and units walk through it.
- Fix: `XComWorldData.RebuildTileDataExtents` over a box around the spawn (`RebuildExtent`, default 192 × 256 × 160
  half-size).

### F-05: Level-start placement doesn't see our objects (a Meld canister inside the row)
**Fixed**; timing verified (EXP-05 run 11); placement not yet seen over several missions.
- Symptom: a Meld canister spawned between cars 7 and 8 (run 10). The game never puts one inside things.
- Cause:
  - LWR places Meld canisters and alien pods (`XComLZMutator.XComMeldSpawnMutator` and `XComPodSpawnMutator`) on
    random tiles that the tile data calls open floor. They run in `XGBattle_SP.PostLevelLoaded`, about 0.15 s after
    our objects spawn.
  - Our tile rebuild ran on a 1 s timer, and rebuilds are spread over frames, 16 tiles a frame by default
    (`DEFAULT_REBUILD_TILE_RATE`). So ten cars were only in the tile data about two seconds after spawning.
- Fix: the spawner rebuilds its tiles in `PostBeginPlay`, in the frame it spawns, with the rate raised to 100000
  tiles an update; `WaitForTiles` sets it back to 16. Run 11: rebuild done at 28.33 s, mutators at 28.34 s.
- Check: `CheckPlacements` logs a WARNING for any canister, canister spawn point or unit inside a car, 1 s after
  spawning. It missed the squad in run 11 (F-06); the soldiers probably arrive later than that.

### F-06: LWR's landing zone can put the squad on our objects
**Open** (EXP-05 run 11, `look-001215.png`).
- Symptom: soldiers spawned on the car roofs, and the SHIV got wedged between two cars and couldn't move.
- Cause:
  - LWR's `XComLZMutator` picks one of a fixed list of landing zones per map (`XComLZMutator.ini`, `LZArray`: a
    start point and a facing).
  - It builds six spawn points in front of the chosen landing zone without looking at the tiles. The game then puts
    each unit at the nearest place it can stand, and a car roof counts.
  - URB_Bar has 7 landing zones. The one at (719, −1681) facing North makes spawn points at x 527–911,
    y −1201 to −1489. Those are the map's own start positions (`XComSpawnPoint_18`–`_23`), and they lie on our row
    (cars 3–5). That makes it about 1 mission in 7.
- Options:
  1. patchtool warns, or refuses, when an object covers a landing zone's spawn area or one of the map's
     `XComSpawnPoint`s;
  2. the editor moves or drops the landing zones it covers (EXP-06: move landing zone, spawns and pods);
  3. a mutator of our own that runs after LWR's and moves blocked spawn points.

  For the test patch, the row can simply move.

  The editor now warns when an added piece covers a soldier point (`landing-blocked`) and lets the author move
  the zone. A moved and an added zone played on the cleared Bar under LWR. The original car-row obstruction
  remains a separate case. [EXP-51](experiments/EXP-51-cleared-bar.md)

### F-85: When LWR uses the map's authored spawn points

**Partly observed in game.** The installed scripts and config were read on 11 November and checked again on
18 November 2026. A fresh SP battle dispatches the `PostLevelLoaded` mutators before the battle selects Meld
points and initialises pods. Scripted reinforcements use a later hook.

- **Landing.** On a matching map/mission/council line, the LZ mutator hides the recognised grounded dropship
  before it checks the zone kind and templates. Normal placement needs a frame, evac volume and six soldier
  templates. Covert extraction, capture and hold, and council extraction/rescue skip randomisation. A council
  bomb requires the bomb mutator. The cleared Bar with a moved landing and an extra LWR line played. The report
  does not distinguish individual landing observations. [EXP-51](experiments/EXP-51-cleared-bar.md)
- **Pods.** HQ assault, the final mission and an empty squad skip the normal rewrite. Insufficient generated
  locations leave ordinary map pods available. The alien base, battleship and overseer reserve the commander.
  Other crashed/landed UFOs try to place a commander before the remaining location count is checked. Both the
  small-map fallback and the UFO commander-location search have been observed. [EXP-43](experiments/EXP-43-blank-map-stage.md)
  [EXP-53](experiments/EXP-53-mission-kinds.md)
- **Meld.** An eligible mission and sufficient generated places allow the mutator to replace the map's points.
  The checked config requests three candidates. The battle then selects by spawn group, difficulty and roll.
  Meld appeared in the enlarged area in EXP-43 run 3. [EXP-43](experiments/EXP-43-blank-map-stage.md)
- **Scripted drop-ins.** When a `SeqAct_SpawnAlien` fires, the mutator can supply a temporary point near a
  soldier. The final mission, a running map named in `ExcludeMaps`, a missing or ambiguous action, or failure
  to find a soldier or location can leave the action using its own points. Wave groups have their own ordered
  destination/origin lists, and Long War's mutator leaves them alone: a wave group's destinations moved by a
  project are where its units dropped in (EXP-72 run 5). Where a scripted action's drop-in lands under the mutator,
  and on its own points with the variant in `ExcludeMaps`, is EXP-72 runs 3 and 4 (with the map's points as they
  were; a moved scripted point is not played).

The editor already writes the variant's landing lines. A per-variant scripted drop-in exclusion and an optional
pod/Meld runtime experiment remain in the private spawns plan. Deployment counts, exact placements and reload
behaviour for these proposed edits still need direct observation.

### F-126: A window in a made wall is climbed through, as the game's windows are
**Verified** (18 November 2026, EXP-73 run A: a soldier walked one tile through W1's window, sill 72, top 168).
- **What the game does.** A wall under a window is low cover (its tiles read 30 in LWR: cover 44-60 hits the wall,
  the high-cover sweep 88-104 passes through the opening), and the game's tile rebuild gives a low-cover tile its
  ClimbOver bit toward it (flags 0x200111 on W1's window tile, 0x1000888 on W2's): units vault through, as through
  the game's own windows. The walking sweep at 64 does meet the wall under the sill, so they don't walk through
  plainly; they climb.
- **What was wrong.** Stage M1's words (the piece panel's and the compiler's) said units can't walk through a window
  and took that from the game's glass; the run found the climb. Fixed the same day: a window with low cover under it
  says units climb through it (walls.js `openingPlay` gives `climb`; the compiler's window note says so).
- Also from the run: sight and shots pass through the window (a Sectoid 192 north targeted at 100% and killed); a
  doorway is walked through; a one-storey-high hole under an upper storey is walked under; a quarter-turned wall and
  a wall on a roof give high cover beside their solid tiles.

### F-125: Edited no-spawn volumes keep a pod's other aliens out; with their aliens switch off they let them in
**Verified** (18 November 2026, EXP-72 run 17: the volume edits of export 34).
- **What the game does.** `XComAlienPod.GetSpawnPoint` puts a pod's first alien on the pod's own place and each other
  one on a ring round it (radius 96 x N / 3 for N aliens), moved by `GetClosestValidLocation(..., bAvoidNoSpawnZones =
  true)` to the nearest valid place outside every `XComNoSpawnVolume` whose `AlienNoSpawnZone` is on. The first alien
  is never moved. The tiles carry no no-spawn flag (the Bar's tiles inside its volumes share no bit the rest lack), so
  the volumes are read as they stand.
- **Played.** `X72Volumes`, a build of URB_Bar: its five pods deleted, four copies of a deleted pod on its old pod
  places, Long War's pod and Meld mutators out of the lab loader. Pod 5, in `XComNoSpawnVolume_0` stretched to 7 by 7
  tiles, and pod 7, in a 7 by 7 copy of another volume, each had their second alien put on the first tile past the
  box's edge, 4 tiles out (run 6 had aliens within 1.3 tiles of those places with no volume there). Pod 6, in a 5 by 5
  copy with `AlienNoSpawnZone` off, had its other two on the ring a tile out, as had the control pod 8 with no volume.
  So a stretched volume (its `DrawScale3D` over the shared brush), a cloned one and the switch are all read as the
  Build writes them.
- **How to read it.** Before XCOM's first turn the game revealed all four pods and their aliens moved to cover, so
  where they stand at turn 1 says nothing. The places the game first worked out stay in the level as
  `XComSpawnPoint_Alien` actors (`getall XComSpawnPoint_Alien Location`), in pod order.
- **Not played:** civilians (`CivilianNoSpawnZone`), volumes under Long War's own pod and Meld placement, and plain
  Enemy Within.

### F-124: A moved bomb leaves its helper point behind, and Long War then places nothing
**Verified** (read offline on 18 November 2026, from the decompiled bomb mutator and the installed Slaughterhouse
stream; fixed in export 33 the same day and played in EXP-72 run 1).
- **What the mutator needs.** `XComBombMutator.FindBomb` counts the bomb, its button, its floor marker, five
  emitters, the nearest rebuild volume and the squad's visible point, and every `PointInSpace` within 128 units
  of the bomb across. With fewer than eleven it logs "can't find the bomb, skipping to defaults" and moves
  neither the bomb nor the power nodes.
- **What the editor moves.** Its bomb group is the first ten (`scene_metadata.mission_objects`). The stream's
  `PointInSpace_0` stands 2.5 units from the bomb across and 204.5 above it, and is not in the group. Five Kismet
  actions name it: the arrows pointing at the bomb, a camera look-at and a visibility viewer.
- **So.** A bomb moved by one tile (96 units) is still found. Moved two tiles or more, the count is ten: under
  Long War the bomb and its nodes play where the project put them, and the arrow and the camera point at where
  the bomb was. On plain Enemy Within the bomb plays where it is put either way, with the same stray arrow.
- **Fix, planned:** the helper joins the bomb's group in the next export, so it moves with the bomb and keeps its
  offset (the mutator itself puts it 206 units above the bomb). Long War then finds the bomb again and places it
  and the nodes itself wherever it finds a place for each, so the project's place becomes the fallback. A project
  saved with the bomb moved gets the helper's move when it opens.
- **Fixed** in export 33 (`scene_metadata.mission_objects`): every `PointInSpace` within 128 units across of the
  bomb joins its group with role `point`; a project saved with the bomb moved gets the helper's move when it opens.
- **Verified in EXP-72 run 1:** the bomb moved three tiles on URB_SlaughterhouseA; the mutator's log lists twelve
  actors found near it, `PointInSpace_0` among them, finds 8 nodes, moves the bomb to a place of its own with the
  helper 206 above it, and places each node; no "can't find" line. The arrow was not seen in the run's shot.

### F-103: A piece whose component is turned apart from its actor was refused for every copy
**Fixed in the tools, checked offline** (14 November 2026; not played in the game).
- **Found by:** the Landed Large UFO prefab (520 pieces, from another user), whose test was refused over one fence:
  `XComFracLevelActor_201` of `LSupplyShip_ForestGrove`, whose mesh component has `Rotation` (0, 16384, 0).
- **Cause:** the compiler's `component-offset` error dates from the UnrealScript copier, which could not set a
  component's own translation or turn. The Build has made every copy in the map itself since then, as a clone of
  the actor with every export under it, the component's `Translation` and `Rotation` among them.
- **How common:** in the 23 maps exported in the cache, 4 pieces (three `XComLevelActor`, one `XComFracLevelActor`).
- **Fix:** the refusal goes for every class the Build makes in the map (`compiler.NATIVE_CLASSES`) and for pieces of
  other maps; it stays for a class only the patch's copier would make (none builds today).
- **Checked offline:** the Large UFO's test project built (quick build, 460 copies). In the package the fence's
  clone has the donor's component values, its world vertices are the donor's moved by the copy's rigid move
  (largest difference 0.0000 units over 936 vertices), and its box is the one the compiler reported.
- **Not checked:** the game. The one point with a real doubt is whether the fence's fragment columns land on the
  tiles its turned mesh covers (`move_columns` moves them by the actor's move).

### F-102: Temple Ship's arches are floor but can't be clicked
**Fixed** (14 November 2026, read offline from the shipped `TempleShip.upk`; a modder's report relayed by the user.
The patched map is made, not played). **Played** with the editor's Flags (16 November 2026,
[EXP-60](experiments/EXP-60-temple-arches-mouse.md) run 1): Mouse picks it on for 40 arches and 28 other pieces, a
quick build; the cursor lands on an arch and a soldier is sent onto it and along it.
- What: soldiers can't be sent onto Temple Ship's arches with the mouse, though aliens walk on them and the grapple
  lands on them. The modder had lined the floors up with the cursor storeys, with no change.
- **Cause:** all 273 placed `KnuckleWorm_A` pieces (the arches, ten archetypes) save
  `bIgnoreFor3DCursorCollision = 1`, on an editor layer Firaxis named "Ignore by 3d Cursor". The mouse's pick ray
  (`XComTacticalHUD.GetMousePickActor`, [mouse-cursor.md](native/mouse-cursor.md)) skips such pieces and lands on
  whatever is under them. The arches' tiles are floor in the tile data, which is why pathing and the grapple work.
  The cursor storeys play no part: the hit is dropped before its storey is looked at.
  - The map's other pieces mostly have the flag too (walls, trim, pillars, the four `alienSectopodArch` pieces);
    the floors do not.
- **Fix:** first `tools/upk/cursor_pick.py` (retired 16 November 2026 for the editor's Mouse picks it; in the
  history before that day) cleared the byte on the matching placed pieces, a fixed-size edit (`package_edit.py`):
  273 bytes change, from 1 to 0, and the chunk table. The patched map is
  `dist/templeship-clickable-arches/TempleShip.upk` (SHA-256 `3270f434…183850`).
- What to expect, from the pick rules (not played):
  - with the cursor on a storey below the arch, a hit further down still wins, so the floor under an arch stays
    clickable and the cursor must go up a storey to stand on the arch;
  - where an arch's top lies in the same cursor storey as the floor under it, the arch wins wherever it is a valid
    tile, and the tiles under it become hard to click (likely why Firaxis turned the arches off). There the cursor
    storeys do matter;
  - hits on the arches' curves count only where they meet the tile's floor height
    (`IsPositionOnFloorAndValidDestination`).
- Not checked: what the editor's Build does with the flag on a copied arch (EXP-60 turned it on for the map's own
  pieces where they stand), and whether the floor under an arch can still be clicked where the arch's top is in the
  same cursor storey.
- **Correction (16 November 2026):** the flag holds for props, collectibles and ladders too, not only for
  `XComLevelActor` and `XComFracLevelActor`: the pick's tests are casts, and those classes inherit the mouse
  interface and the flag from `XComLevelActor`; only a door is tested apart and never reads it
  ([native/piece-flags.md](native/piece-flags.md), section 3; F-114). `cursor_pick.py` matched only the two
  classes it named.
- **Now (16 November 2026):** turn **Mouse picks it** on for the pieces in the editor's Flags; the Build writes it on
  each piece, any class but a door (EXP-60 played it on the arches). `cursor_pick.py` is retired.

## Damage and glass

### F-07: Explosions treat our cars exactly like the map's
**Verified** (EXP-05 runs 3 and 7). A reference fact, not a defect.
- Damage = the projectile's `WorldDamage` (35) × random 0.75–1.25 × distance falloff 0.5–1.
- `Toughness_SMALLCAR` gives 500 health. `_Damaged` begins below 75 %, `_Destroyed` at 0. One HE grenade takes about
  15–25.
- In run 7 the map's car and ours took the same damage from the same grenade.

### F-08: Health must be set after the archetype is copied
**Verified** (500/500 from run 4 on).
- Cause: `PostBeginPlay` runs during `Spawn`, before `CopyFrom` sets the toughness, so `TotalHealth` comes out wrong.
- Fix: `CopyFrom` sets `TotalHealth` and `Health` from the copied toughness.

### F-09: Damage and destruction actions act on their owner
**Verified** (EXP-05 run 14: car 7 burned down and its explosion damaged three of our cars, which caught fire).
- Cause: the archetype's `DamagedEvents` and `DestroyedEvents` actions act on the object they belong to.
- Fix: `CopyFrom` gives each copy its own action objects (`new(self) Class (Template)`).

### F-10: Glass needs fragment columns or damage breaks nothing
**Verified** (EXP-05 run 6).
- Cause: the editor bakes `FragmentColumns` into every placed `XComFracLevelActor`: one per world tile, with clipped
  bounds, the fragments sorted by height and the car for collateral damage. The archetype has none.
- Fix: `XComMapEdSpawner.BuildFragmentColumns` builds them at the first tile rebuild.

### F-11: Glass health must be sized for the mesh
**Verified** (EXP-05 run 10: 9 columns shattered, no errors).
- Symptom: every hit logged "CachedFrag.FragIndex >= ChunkHealth.Num" and "REBUILD PATHING!", and nothing broke.
- Cause: `ResetHealth()` runs in `PostBeginPlay`, before our glass has its mesh.
- Fix: `XComMapEdGlass.CopyFrom` calls `ResetHealth()` after `SetStaticMesh`.

### F-12: Firaxis-only settings can't be set from UDK script
**Accepted.** Firaxis added settings that UDK's compiler doesn't know: `bUseVertexColorDestruction`,
`EditorPaintedVisibleFragments` and the rain render channel set in `XComFracLevelActor.PostBeginPlay`. They keep
their defaults. No visible effect has been seen so far.

### F-68: What breaks a piece, and its health, come from the toughness it names
**Open** in part (9 November, offline: the install's 101 maps scanned, the game's decompiled script read in
`<lab>\reference\XComGame-decompiled`; `test_destruction.py`, `browser_smoke.check_destruction`). A reference fact
behind the editor's Destructible and Health lines (export 17, `scene_metadata.destruction`).
- **The toughness.** Each destructible piece names an `XComDestructibleActor_Toughness` cooked into the map
  (`GameData_Toughness.Toughness_METAL` and the like), directly or through its archetype. The install's maps have 23
  kinds, from 10 health (`GLASS`, `DECO`, `EXPLOSIVE`) to 500 (`SMALLCAR`, `TRUCKS`). `Toughness_INVINCIBLE` sets
  `bInvincible`; glass, decorations and foliage set `bFragile`. No placed actor sets `Health` or `TotalHealth` itself.
- **Props** (`XComDestructibleActor`, and the doors and collectibles built on it):
  - `PostBeginPlay` sets `TotalHealth` from the toughness, or with none (9 props on the install's maps) from the
    toughness class's default, 3.
  - `ApplyDamageToMe` takes no hit if the toughness is invincible, unless the hit is the one damage class it succumbs
    to. A non-fragile prop takes only hits whose damage type causes fracture: explosion, flame, laser, plasma, minigun,
    melee, nuke blast and drone suicide, not `XComDamageType_Bullet`. Each hit counts 0.75 to 1.25 of its damage
    (F-07).
  - A collectible blows itself up when it is first damaged (`BecomeDamaged`: its health plus 255 as explosion damage).
- **Fracturing pieces** (`XComFracLevelActor`, `XComDecoFracLevelActor`):
  - A hit whose damage type causes fracture, or any hit on a `bAlwaysFracture` piece, breaks off the parts within its
    radius (`BreakOffPartsInRadius`, then the native `ApplyDamage`). An explosion's hit counts 1000, a shot its
    `WorldDamage`.
  - The health of each part is kept in native code (`ResetHealth`, `ChunkHealth`, F-11).
- **Open:** 852 fracturing pieces on 44 maps name no toughness, ordinary walls and railings among them (URB_FastFood_EWI,
  URB_ResearchOutpost). What the native code gives them wasn't worked out; the editor shows "Unknown: no toughness
  set".

## Fire

### F-13: How map cars catch fire and explode
**Verified** (the user's police-car test, 23:40–23:43). A reference fact.
- Every explosion sets fires (intensity 2; 3 for alien weapons). Laser and plasma set intensity 1. AP grenades set
  none.
- After dealing its hits, `XComProjectile.DealSplashDamage` starts `DamageRadius / 96 + 1` fire volumes at random
  entries of `XComWorldData.PotentialFireColumns`. It does so only while the blast has left a tile rebuild running.
  - Destroyed glass columns add entries (native code), and so does a destroyed destructible (script).
  - While tiles rebuild, the volume waits 1 s before it is added.
- A fire on a car's tile deals `XComDamageType_AreaBurn` 8041 at the next turn change, which destroys the car.

### F-14: Our cars don't catch fire
**Verified** with a workaround (EXP-05 run 14): a grenade set car 7 alight, the next turn change burned it down, and
its explosion set three more of our cars alight. Was **Open** (EXP-05 runs 5–11: the map's cream car burned every time, ours never).
- Ruled out:
  - damage (F-07);
  - fire spots: our destroyed glass columns add them like the map's (runs 9–11).
- Fires are made on our cars, and then don't burn. Run 11: the grenade made 3 fire volumes. Two were on our car 9's
  glass, at (1697, −1297) and (1759, −1297), and one on the map car's, at (1775, −922). Only the map car burned.
- So the difference is in what a fire does once placed: fires only take on tiles the game counts as flammable
  (`IsLocationFlammable`).
- Run 12 (fire test build, 00:28): flammable tiles per height level.

  | | ground level (Z 0–64) | next level (Z 64–128) |
  |---|---|---|
  | map's cream car, as baked | 10/10 | 8/10 |
  | the same car after a runtime rebuild over it | 10/10 | 8/10 |
  | our cars before our rebuild (bare road) | 0–3 of 8–12 | 0–2 of 8–12 |
  | our cars after our rebuild | 8/8–12/12 | unchanged (0–2) |

  - A runtime rebuild doesn't strip flammability: the map car comes out the same.
  - Our rebuild does mark the ground level under our cars flammable, so the game treats our cars as flammable.
  - The level above stays unmarked for ours, while the map car has it.
  - Fires sit at window height (Z ≈ 157–160) and only take on a flammable tile there. So 3 of 3 fires took on the map
    car, and none of ours.
- Not the cause: the map car's placed properties are the archetype's (dumped from `URB_Bar.upk`), apart from
  location, rotation (yaw about −86°), tint, its own glass and baked lighting.
- Candidates:
  1. the rebuild keeps the baked flag where it exists and only adds ground-level flags itself, so the upper level can
     only come from the editor's bake;
  2. something about our glass or car makes the builder skip the upper level;
  3. orientation: ours face along Y, the map car along X.
- Run 13 (variant build, 00:37): every variant came out like our normal cars, so candidates 2 and 3 are ruled out.

  | car | ground level | level above |
  |---|---|---|
  | plain copy of the archetype (the game's own class) | 12/12 | 0/12 |
  | ours without glass | 8/8 | 0/8 |
  | ours turned like the map car | 14/15 | 0/15 |

- In the same run, a grenade put all 3 of its fires on the turned car's window-height columns; none burned before the
  game closed.
- **Cause (candidate 1):** a runtime tile rebuild marks only the ground-level tile under a flammable object. The
  window-height marks come only from the editor's bake; a rebuild keeps them where they exist but never adds them.
  This holds for anything we place at runtime, so it matters for remixed maps (EXP-07) too.
- **Workaround (built 00:41, deploys when the game closes; not yet tested):** our glass columns' bounds reach down
  below ground, so their centre, the fire spot, falls in the ground-level tile, which is marked. The top of the bounds
  is unchanged.
- Run 14 (00:43–00:46, `look-004557.png`):
  - The workaround puts our fire spots at ground level: 5 at Z 29.1, all counted flammable.
  - The grenade's 3 fires all went to the cream car's 3 spots (3 picks out of 8 spots; about an 8 % chance), so no
    fire landed on ours. The user's note: "no tire fires". Untested so far.
  - Side note: our columns now log as damaged but not destroyed ("1/0", "2/0"), where before they were both. Check
    that broken windows still update line of sight.
- Run 14, second grenade (log 223.88, `look-004705.png`, the user's note "WE HAVE FIRE!"): all 3 fires landed on
  car 7's columns at ground level, (1385, −1297, 29) and twice (1384, −1383, 29), and **car 7 burns**. The flames
  show on its side and windows, not just at the wheels. The workaround works for catching fire.
- Turn change (log 385.11, `look-005019.png`): AreaBurn 8041 destroyed car 7. Its explosion (241 from car 7) took
  cars 6 and 8 and the turned car to 250/500, into the damaged (burning) state. The user's note: "our car blew up and
  set off a chain reaction, others are on fire now, looks great!".
- Still open: a fix for objects without glass. Nothing else of ours makes fire spots, short of the object being
  destroyed.
- Also learned: the patch's `XComRebuildWorldDataVolume` makes the game rebuild a cube about 1036 units around the
  row at level start (`XGBattle.DoWorldDataRebuild`), which covers the cream car too. So the map car's tiles had
  been rebuilt at runtime in every earlier run as well.

## Saves

### F-15: Spawned objects need the same names on every load
**Verified** (EXP-05 run 15: the reload matched every saved car and glass by name). What it brings back is F-17.
- Cause: checkpoints find actors by name. A spawned actor's name comes from its class's counter, and classes in
  XComGame keep counting for the whole session (`XComFracLevelActor_25` on the first load, `_46` on the next).
  Classes in the patch's own package start from `_0` on every load.
- Fix: everything we spawn is a class from the patch package (`XComMapEdDestructible`, `XComMapEdGlass`).

### F-16: A reload must not leave duplicates
**Withdrawn** (EXP-05 run 15). The assumption was that a save brings back a second, damaged copy beside our fresh
one. It doesn't: the save recreates the object in place, under the same name (F-17). `RemoveIfRestored` is removed.

### F-17: A reload brings spawned objects back without their mesh
**Verified** (EXP-05 run 16, 09:55, `look-095539.png`): the wreck came back visible and giving cover, and the
burning car came back burning. The user's note: "looks good". Found in EXP-05 run 15 (`look-005426.png`).
- Symptom: after a save and reload, the burned-down cars were gone; only their fires were left. The user's notes:
  "on reload the car wrecks are gone, but the fire is still there" and "units can now path through that area so
  there's nothing there".
- Cause:
  - A save keeps only damaged destructibles and glass (`ShouldSaveForCheckpoint`: not `_Pristine`, or a damaged
    column).
  - On load it first matches records to the actors the map itself contains. A spawned one isn't among them, so it
    logs "Not Found … Recreating actor" and spawns the saved class under the saved name, replacing our fresh one in
    place.
  - The recreated actor has only class defaults plus the record: health, state, which damage and destruction actions
    had fired, and, for glass, the broken fragments and the columns. It has no mesh, materials or events. So it was
    invisible and had no collision, though its state (Dead, `_Damaged` with the saved health) and its fires were
    right.
  - Pristine cars aren't saved, so they come through untouched. That is why the first reload test passed (F-15).
- Fix:
  - `XComMapEdDestructible` and `XComMapEdGlass` override `PostBeginPlay`. A recreated object finds the spawner whose
    `Main` or `Partner` already points to it; that is never true during a normal spawn, because the spawner sets it
    after `Spawn` returns.
  - It then calls `RestoreLoaded`, which re-copies the archetype (mesh, materials, events, toughness, cover) and the
    paint, and rebuilds the tiles 0.5 s later. The game's own load code then applies the record on top: health, state,
    the wreck mesh swap, the fire and the broken glass.
  - Not `ApplyCheckpointRecord`: the game's takes no parameter, UDK's fracturing actor declares one with a record
    parameter, and the glass can't override both.
- Also: the Dead state normally stops ticking, so a car loaded straight into Dead would never compute its light
  environment, and its wreck would render black (F-02). `XComMapEdDestructible` keeps ticking in Dead.

- EXP-07 copies (**verified**, run 25, `look-154636.png`: "after a reload, walls still damage and burning as
  expected"): copier copies come back the same way, rebuilt in place under their saved names. Each copy class asks its
  copier from `PostBeginPlay` (`XComMapEdCopier.RestoreLoaded`), which copies the source onto it again before the record
  is applied. The log showed three walls and five destructibles restored. It relies on copies getting the same names on
  every load (they are spawned in the same order).

### F-18: On load, a wreck's explosion goes off again
**Verified** (EXP-05 run 17, 10:02, `look-100225.png`): after the reload, our wreck and the burning car 8 (250/500)
came back with no explosion during the load. The map's own wreck didn't re-explode either, so the replay was ours
alone. The user's note: "looks good". Found in EXP-05 run 16.
- Symptom: the white car 7 was burning at the save (`_Damaged`, 186/500); after the reload it was destroyed but
  looked intact. The user's note: "when i saved I think the white car was also burning but now it is not".
- Cause: applying a saved record replays the destruction actions that had fired (`Action.Load`, native), the
  explosion (`XComDestructibleActor_Action_RadialDamage`) included. At load, car 8's wreck dealt its 241 again
  (log 125.30) and took car 7 from 186 to −30.
  - The map's own wrecks don't do this (run 17); only our recreated ones did.
  - Copies made in the map (EXP-24 run 2, 8 November, Police Station): on load the game replays the two blast actions
    of every car destroyed before the save, the map's own (1059, 1070, 1071) and the copy (1096) alike, with no unit
    hurt and nothing new broken (all were wrecks already). So the map's own wrecks do replay, at least there; the
    copy acts as they do and needs no hold-back.
- Fix: `RestoreLoaded` calls `XComMapEdDestructible.HoldBackBlasts`, which takes the explosion actions out while the
  record is applied. `ReleaseBlasts` puts them back a second later, marked as fired if the save says they had. A car
  saved burning still explodes later.

## Removing map pieces (EXP-07)

### F-19: The map's destructibles are neither bStatic nor bNoDelete
**Verified** (EXP-07 run 2: 413 actors hidden, the bar gone from view). In run 1 the hider skipped all 306 destructible props inside the
bar, because it took only actors with one of those two flags as placed by the level.
- Fix: `XComMapEdHider.IsHideable` decides by class alone (meshes, fractured actors, doors, physics actors, emitters,
  decals) and still skips anything a patch spawned.

### F-20: Actor bounds come back empty for the level's walls and props
**Verified** (EXP-07 run 2). In run 1, `Actor.GetComponentsBoundingBox` gave an empty box for
the bar's walls, roof and props: 190 of them read as lying wholly below 40 units and were kept as "ground". It works
for spawned cars, so the engine call probably counts only some components, such as colliding or attached ones.
- Fix: `XComMapEdHider.ActorBox` builds the box from each primitive component's own `Bounds`. An actor with no
  bounds at all is placed by its location, never counted as ground, and logged.

### F-21: With the bar's volumes switched off, its roof stays hidden and can't be reached
**Open** (EXP-07 run 1, `look-102035.png`). The hider took the bar's building, floor and cursor volumes out of play
(no collision) but, after F-19 and F-20, hid almost none of the building. Then:
- the bar showed its ground floor working normally, but no roof;
- an alien pod stood on the roof, where the roof's tiles were still floor tiles;
- the camera couldn't rise to the roof level there, and no soldier could be sent up.

The user's note: "ground floor of the bar still exists and works normally, but there is no roof. there's still an
alien on the roof though even if it doesn't exist, but i can't zoom out to see it or send my soldier up there".
- Likely cause: the cutaway shows floors through the building and floor volumes, and the 3D cursor climbs through
  the cursor volumes. With them gone, the building may stay in its "first floor only" state and the cursor can't
  climb. This doesn't matter once the whole building is hidden; it matters if a remix keeps a building's volumes.
- Found 4 Nov (step 3b): URB_Bar's `XComCursorVolume_1..3` span the whole map, one per storey (z 0..210, 210..402,
  402..594), and their centres lie in the bar's box, so the hider took the cursor's upper storeys out map-wide. The
  hider now keeps cursor volumes (unless `bHideCursorVolumes`), and a remix brings its own building and floor
  volumes (patchtool's `building` field). To check in game: step 3b.

### F-22: Hidden pieces with no collision still fill their tiles and give cover
**Verified** (EXP-07 run 3, 10:34, `look-103456.png`): after the rebuild, the bar's ground level is 510 of 510 floor
tiles, with 0 occupied, 0 high cover and 4 low (at the box edge). Before, it had 263 occupied, 122 high and 92 low.
The user's note: "looks good now, no more cover or invisible walls". Which of the three run 3 changes did it is not
known: they went in together. Found in run 2. In run 2 the hider hid 413 actors: the bar's walls, roof, props,
doors and effects. The bar was gone from view, but units still pathed around the old walls, and those walls still
gave cover. The user's notes: "the navigation still seems to consider the old wall locations"; "also it still
counts as cover" (`look-102604.png`, `look-102701.png`).
- The rebuild did run, and it took out every floor above the ground (roof 300 → 0 floor tiles, tables and the
  bar top too) and the upper levels' cover. It left the ground-level cover (122 high, 92 low) and the occupied count
  at every level exactly as before. So floors come from traces, which our collision changes affected, while
  occupancy and cover come from something else.
- Lead: the rebuild's occupancy step goes through the cover interface (`ConsiderForOccupancy`, `ShouldIgnoreForCover`).
  Level and fractured actors default to `bAlwaysConsiderForCover=true`, and fractured walls count tiles by fragment
  column, which is how a wall that is blown open stops blocking.
- Run 3 tries, all at once:
  - `bAlwaysConsiderForCover` off and `bIgnoreForCover` on;
  - every fragment hidden;
  - every fragment column marked damaged and destroyed.

  It also logs the collision flags left on the first actor of each class, and traces a probe line through the old
  front wall (plain trace, box trace and `XComWorldData.WorldTrace`) before and after.

### F-23: Other streamed levels sit at the world origin, inside the bar's box
**Verified** (EXP-07 run 3: 407 hidden instead of 413, and the leftover "blue dots" gone). In run 2 the hider also hid emitters of other streamed levels: one set at
(0, 0, 0) and one placed symmetrically around the origin, most likely from `CIN_DropshipIntros`. The origin lies
inside the bar's box.
- Fix: only actors whose level (`Outer`) is the base map's persistent level or the patch's own are taken.

### F-24: The ground keeps the removed building's baked shadows
**Accepted for now** (EXP-07 run 2, `look-102604.png`). The kept floor slabs and pavement still show dark patches
where the walls, bar and tables stood, because their lightmaps were baked with the building in place.
- Ways out:
  - replace the ground pieces with dynamically lit copies (as for the cars, F-02);
  - cover them with new floor pieces;
  - or accept the shadows inside a new building that covers the old footprint.

### F-25: Hidden walls still block line of sight
**Verified** (EXP-07 run 4, 10:44, `look-104403.png`, `look-104416.png`). The probe's `WorldTrace` now passes the old
front wall (after hiding and after the rebuild), and a soldier is offered a squadsight shot across the cleared area.
The user's note: "I can see through everything normally I think". Found Confirmed in game in run 3 (10:38, `look-103810.png`). The user's
note: "yes LOS looks off, I should be able to see the drone here I think".
- Likely cause: level and fractured actors carry `VisibilityBlockingData.bBlockUnitVisibility`, true by default. The
  game's line of sight follows it rather than collision. In the log (run 3): The probe line through the old front wall (x −1056, y −120 to 400, z 64) hit
`XComDecoFracLevelActor_11` (`Core_384FacadeB`) at y 184 before hiding, with all three traces. After hiding and the
rebuild:
- `Trace` hits nothing, both as a line and as a box;
- `XComWorldData.WorldTrace` (check type 4) still hits the same piece at the same point.

So that trace ignores the collision flags, the hidden flag and the hidden fragments.
- Fix tried: the hider sets `bBlockUnitVisibility` off on every hidden level and fractured actor. The stub
  declares the member without `const`, so script can set it. The probe's `WorldTrace` should now pass.

### F-26: A hidden door still offers "open door"
**Verified** (EXP-07 run 4). The user's note: "no more door action". In run 3 a soldier standing where a bar door had been was offered the door
action, with no door there (`look-103810.png`). The user's note: "there's a "open door" action but no door".
- Cause: the hider removed the door's interaction points before rebuilding, and the rebuild's interaction step
  most likely added them back from the hidden door.
- Fix: as the game's own `XComInteractiveLevelActor.OnDisableInteractiveActor` does, the door goes to its
  `_Inactive` state before the rebuild. Its points are also removed again once the rebuild is done.

### F-27: The cutaway shows a switched-off building's effects again
**Fixed** (4 Nov), to confirm in the next run. In run 4, with the bar's building and floor volumes out of play, five
of its hidden emitters were shown again: `Emitter_4`, `_13`, `_14`, `_37` and `_45`, high on the back wall (z 333).
It happened at 61 s and again at 74 s, and the hider's check hid them again each time. They are the effects the
bar's floor volumes list (`m_aInclusionActors`), so the building's cutaway code still runs over those lists. The user
saw nothing.
- Fix: the hider's check now runs every 3 s for the whole mission, not just the first minute. It deactivates a
  re-shown emitter again too.

### F-28: Copied walls render flat black
**Verified fixed** (EXP-07 one-wall run 4, 11:31, `look-113151.png`; the user's note: "all walls appear lit now").
- Fix: `XComMapEdWall` makes its own `DynamicLightEnvironmentComponent` (`MyLightEnvironment`, in `Components`) and
  gives it to the fractured component, as `XComMapEdLevelPiece` does. The `LightEnvironment0` inherited from
  `FracturedStaticMeshActor` logged as enabled and dynamic, yet left the copy black.
- Cause: in the `XComFracLevelActor` stub, `Components(0)=…LightEnvironment0` is an unresolved reference (the
  compiler warns "Invalid property value in defaults"). So in our classes the inherited light environment was never
  in `Components` and never attached.
- Not needed: switching off environment shadowing, the static index buffer, or the lit overlay. All four fractured
  variants rendered lit.

Narrowed by run 3 (11:11, `look-111143.png`): the same mesh and materials copied as a plain static
mesh with a light environment (`XComMapEdLevelPiece`) render lit ("the wall on the left is lit properly"), and the
fractured copy beside it is black. So it is the fractured component's drawing path, not the materials.
- The game's own `FracturedStaticMeshActor` (decompiled from a copy of `Engine.upk`) never gives its fractured
  component a light environment: placed walls draw only with their baked lightmaps, so the lit-by-environment path
  may never have been used for fractured meshes.
- Run 4 tests, side by side: the wall's own fresh light environment (with a test point light next to it); no
  environment shadowing; the static index buffer (`XComMapEdWallStaticIB`); and, as the fallback, a lit plain-mesh
  overlay drawn while the wall is whole, with the fractured mesh shown from the first damage.
- Run 3's test light failed to spawn: `PointLightMovable` is `bNoDelete`, like every `Light`. `XComMapEdLight` (a
  plain `Actor` with a point light component) replaces it.

Earlier: the Dynamic channel didn't help (one-wall run 2, 11:06, `look-110627.png`; the user's note:
"wallls still seem to be black"). At load and 5 s later, the copy's lighting setup was as intended:
- the dynamic light environment is set, enabled and dynamic;
- precomputed shadows are off;
- the Dynamic channel is on. The Static channel reads False, though the defaults set it;
- ticking is on, and the state is the class's own.

So the setup isn't the cause. Next guess: the wall materials lack the light-environment shader variants, because
the cook kept only what the map used, and the walls only ever used lightmaps. Run 3 compares the same wall drawn
as a plain mesh (`XComMapEdLevelPiece`), which is how the working car copies are drawn, and adds a movable test
light. First seen in In EXP-07's one-wall test (run 1, 11:00 and 11:01,
`look-110024.png`, `look-110137.png`), the copied storefront (`XComMapEdWall`) was flat black, darker than the lit
floor, fire and windows around it. The user's note: "can't tell if lightning is not working or it's just dark".
Next to the lit fire it is plainly unlit.
- Likely cause: `XComFracLevelActor` takes only the Static lighting channel. The destructibles that light correctly
  as copies (the cars, the copied windows) take Static and Dynamic. The copy already has its dynamic light
  environment, precomputed shadows off and ticking on, as for F-02.
- Fix tried: `XComMapEdWall` takes the Dynamic channel too. The copier logs the first wall's lighting setup at load
  and 5 s later: environment, enabled, dynamic, precomputed shadows, channels, tick and state.

### F-29: Copied walls don't block line of sight
**Verified fixed** by seeding the map's baked tile data (runs 11 and 12, `look-125423.png`); cause found in EXP-07 one-wall run 5 (11:41, `look-114112.png`, `look-114300.png`). The copier's tile log
shows, for each wall, the rows where the game counts the tiles either side as seeing each other
(`IsAdjacentTileVisible`). Those are exactly the rows with no occupied tile at the wall on level 1 (unit height),
though `WorldTrace` hits the wall there. Both see-through spots the user found are on those rows.
- Level-1 occupancy by a wall appears almost only where a hidden base-map piece stood at that height: wall 1 0 of
  24 tiles, the others 13 to 17 of 15 to 18. At ground level every wall is occupied along its length.
- The fragment columns are the same on every copy, so the copies' own data isn't the cause.
- So a runtime rebuild (`RebuildTileDataExtents`) re-checks a tile above the ground only where the baked data had
  something. The plain-mesh copy only looked solid in run 3 because it stands over an old wall of the bar.
- Run 6: `XComWorldData.BuildWorldData` over the level volume, once after hiding, crashed the game 3.6 s in ("Fatal
  error!", 11:51). It can't be used in the game.
- Run 7: the game's wall and level-piece classes set the Firaxis-only `Actor.bStaticCollision`; its destructibles
  don't. Walls 1 and 4 turn it off (`XComMapEdWallNoStatic`), walls 3 and 4 turn off `bWorldGeometry`, and wall 5
  repeats run 5. Result: every wall matched run 5 row for row, so the flags aren't it.
- Run 8: every tile is stored (the visibility index is the plain grid index), and marking wall 1's tiles as water
  (`SetIsWaterTile`) before the rebuild changed nothing.
- Run 9: `UpdateBuildHeightTiles`, set before the rebuild, was read (the game cleared it) and changed nothing.
- Run 10: a destructible van side panel and an oven copied onto empty tiles beside wall 1 don't register above the
  ground either. So it's any geometry added at run time, whatever its class or flags.
- **Cause, from the native code** (`research/native-code-notes.md`): `RebuildTileDataExtents` queues a tile only if
  its baked static flags have a bit in `0xFFF`. Empty tiles are never re-checked, and no native that script can call
  sets those bits.
- **Fix (verified in the tile log, run 11, 12:33):** `tools/upk/seed_tiles.py` seeds bit `0x1` in the map's baked static
  flags on the tiles new pieces cross. Seeded wall 1 now blocks on every solid row, like the plain copy over an old
  wall, and the seeded van panel and oven are occupied above the ground. The unseeded walls 3–5 kept their holes.
  The seeded `URB_Bar.upk` is in the lab copy; the original is kept to restore.
- Built into patchtool (4 Nov, run 12): a spec with `map.name` gets its copies', spawns' and actors' tiles
  planned from the map inventory and seeded at deploy, and an `XComMapEdTileSeeds` actor rebuilds exactly those
  boxes at load (`tools/patch/README.md`, "Tile seeds").
- Seen in game (run 12, 12:54, `look-125423.png`): all five seeded walls block, and the user saw no aliens through
  them ("confirmed LOS blocking looks normal").

Seen first in run 4 (11:33, `look-113343.png`, 11:33, `look-113343.png`): a soldier at tile (21,23), against wall 5's west face,
sees through the wall and leans as if at a gap. The user's note: "it's only specifically this tile that allows LOS
through the wall, the one my cursor is on does not" (the cursor was at (21,22)). Wall 5 is the overlay variant: its
fractured mesh is hidden. The other walls weren't checked: no aliens were near enough. The leaning suggests the
cover data at that tile has a peek flag, as at a wall's end. Run 5 logs each copied wall's fragment columns and the
tile data along it: cover flags, occupancy, `IsAdjacentTileVisible` across it, and `WorldTrace` at two heights.

Earlier: verified for the plain-mesh copy (EXP-07 one-wall run 3, 11:13, `look-111343.png`; the user's note: "new wall
correctly blocks LOS, can see aliens to top left but not the ones on the right"). The fractured copy blocks all three
probe traces too: line, box and `WorldTrace` hit `XComMapEdWall_5` at x about −1836. Every copy is world geometry,
collides and blocks, and the walls block vision. So run 2's sighting most likely went past the wall's end or through
the storefront copy's windows. Still to see by eye on a fractured copy.

First seen (EXP-07 one-wall run 2, 11:06, `look-110627.png`). A soldier saw two aliens through the copied solid back
wall (`Core_384BackA`). The user's note: "I can see the two aliens in the top right through the wall but I shouldn't
be able to from here". The copies block movement and give cover (run 1), and the copier ran before the hider, so
they took the sources' intact vision flag (`bBlockUnitVisibility` true). Line of sight follows that flag (F-25).
Run 3 logs every copy's world-geometry, collision and vision flags, and traces probe lines through both back-wall
copies (plain trace, box trace and `XComWorldData.WorldTrace`).


### F-30: A moved ladder can't be climbed; a hidden one still can
**Fixed** (EXP-07 run 21, `look-145109.png`: "new ladder looks climable, old ladder is not anymore!"; climbing down
still to check). Found in step 3b run 13
(`look-131115.png`, `look-131217.png`).
- Cause: a ladder is two baked neighbour links in the map's world data (bottom tile ↔ top tile, traversal types
  climb ladder and landing, two positions, the ladder actor as path object). Moving the actor doesn't move them, and
  the runtime rebuild makes none for it. The hidden bar's other ladder kept its links, so it could still be climbed.
- Tried (run 15): `tools/upk/world_links.py` moves a path object's links in the map's baked data, and patchtool
  does that at deploy for every piece a copier moves (doors and ladders). The ladder still couldn't be climbed. The
  rebuild probably replaces the links of the tiles it processes (native notes), yet the hidden ladder's survive.
- Run 16 (A* probes, `XComWorldData.GetAStarPath`): the moved links are there at load (a 1-tile climb) and gone
  5 s later, after the tile rebuild. The hidden ladder's links survive. So the rebuild replaces the links of the
  tiles it processes and re-makes a ladder's links only where the ladder stood when the map loaded.
- Fix (run 17): `tools/upk/bake_actor.py` writes the ladder's new Location and Rotation into the lab's copy of the
  map, and patchtool (a `bake` object) moves its baked links with it. The block uses `XComLadder_4`, which was saved
  with a Rotation; `XComLadder_3`, saved without one, can't be turned this way, and goes under the map.
- Run 17: the baked ladder, standing in its new place from load, still lost its links at the rebuild. The north
  side's climb was re-made where the bar's ladder no longer stood, by `XComLadder_15`, a hidden ladder in the
  shipped `patch_bar` (our patch's base), which has one beside each of the bar's ladders (`_15` and `_11`).
- The native code (read after run 19, `research/native-code-notes.md`, "How ladder links are made"): the rebuild
  gives every ladder in the world a climb when its foot and top tiles have a floor, and checks nothing else about
  the ladder. So the run 17 guess that only the patch's ladders count was wrong; what failed at the new place was
  the top tile's floor.
- Tried (run 18): patchtool's `ladder` type places a hidden `XComLadder` in the patch at the new place, as
  `patch_bar` does. No climb either. So neither the patch level nor the tag decides it. The A* probes can't tell a
  ladder climb from an alien wall climb (JumpUp, WallClimb), so they only show whether the top can be reached.
- Run 19: after the rebuild the new ladder's top tile (34, 21, 6) has no floor, while the north side's top tile
  keeps its floor. The wall and parapet over both are the same; the patch's ladder reaches 20 units into its top
  tile with its collision on, while `XComLadder_15` has its collision taken off by the hider. Likely cause: a
  colliding ladder blocks its own top tile, and with no floor there the rebuild makes no climb.
- Run 20: collision wasn't it. The whole south edge row of the roof loses its floor, and the roof's floor after the
  rebuild comes from the copied ceiling beams (z 396.9), not the copied slab (z 402). Cause: copies didn't take
  `bPathColliding`, which `XComFracLevelActor` defaults to false and the editor set on the bar's slab; the rebuild
  only takes actors with it as floor.
- Fix (run 21): copies take `bPathColliding` and `bCanStepUpOn` from their sources. The whole roof then has floor
  at the slab's height, and the patch's hidden ladder (`ladder` object, `XComLadder_905`) gets its climb. The hider
  moves the hidden ladders under the map, so the old bar can't be climbed.
- What the block needs for a ladder, in the end: a pathing ladder (an `XComLadder`, hidden or not) whose foot and top
  tiles have floor after the rebuild. The visible ladder is only for looks; the bake isn't needed for the climb.
  A visible ladder that is a mesh copy rather than an `XComLadder` takes the foot tile, so there is no climb (F-39);
  a visible patch ladder object does both.
- Still to do: take `patch_bar`'s two hidden ladders out of (or move them in) our patch, so the old bar's sides can't
  be climbed; drop the links of other hidden pieces (doors, low walls). Copies can't take links along, since a link
  names the original actor.

### F-31: The new building's floors don't know the copies, so the roof doesn't cut away
**Fixed** (EXP-07 run 22, `look-151655.png`: "roof cuts away so i can see inside now"). The copies had no floor
component. Filling the caches (run 15) was needed but not enough. Walls aren't cut down yet (`bCutoutMask`). Found in run 13: `RebuildCachedActors` on the patch's building found none of
the copies, and the moved ladder stayed in the hidden bar's caches, so it cut out with the camera.
- Tried (run 15): the copier gives each copy its source's entry from the bar's baked floor caches (same floor, same
  cutdown floor) and takes moved pieces out of the bar's caches. The caches held them, and the roof still didn't cut
  away.
- Being inside comes from touching floor volumes (`XComPawnIndoorOutdoorInfo`). The baked floor tiles under the
  block also still name the bar's floor volumes.
- Run 16: pawns and the cursor register inside `XComBuildingVolume_9000`, on its floor volumes `_9001`, `_9003` and
  `_9004`. So the indoor state works. Runs 17 and 21: still no cutaway with a soldier inside.
- Cause (code read after run 21, `research/native-code-notes.md`, "How the building cutaway works"): `ShowFloor`
  hides and cuts each cached piece only through that piece's own attached `XComFloorComponent`. The wall and
  destructible copies had none: the UDK stubs named `FloorComponent0` without declaring it.
- Fix in test (run 22): the stubs declare it, and both copy classes now carry one. Cutting walls down and the
  camera cut-out also need `bCutoutMask` on the copy's mesh component (not yet set). Still to look at: the level's list of buildings (`XGLevel.InitFloorVolumes`
  collects `m_arrBuildings` at load) and the native visibility code.

### F-33: A soldier kicks a moved door twice
**Fix in test** (run 21). Run 19 looked fixed ("only happened once like it should"); run 20 kicked twice again. Found in run 18 (`look-142759.png`): "when I sent a soldier through the door, he did
his door kick animation twice".
- Cause (likely): two sets of kick links. Deploy moved the door's baked KickDoor links along (since run 15), and the
  rebuild makes kick links from the door's new interaction points too. In run 13, with the rebuild's links alone,
  the door worked normally.
- Fix (run 19): deploy no longer moves doors' baked links.
- Second cause (run 20): the bar's hidden double door (`XComInteractiveLevelActor_0`, `_1`) stands inside the new
  block's south wall, and the rebuild gives a door kick links wherever it stands, even with its interaction points
  removed. Fix in test (run 21): the hider moves hidden doors and ladders under the map.

### F-34: The cursor can't pick a tile inside the new building; it snaps to the roof
**Fixed** (EXP-07 run 23, `look-153008.png`: "can see and select tiles inside the building"; the log showed our building
was in neither list). Found in run 22 (`look-151655.png`): the roof cuts away, but "my cursor doesn't seem
to let me select a tile inside it just snaps to the roof".
- How the mouse picks: `XComTacticalHUD.GetMousePickActor` traces with `TraceActors`, which hits hidden, cut-away
  meshes. It skips pieces with `bIgnoreFor3DCursorCollision`, and a walkable hit outside every building in the HUD's
  list wins at once. The HUD and the cursor fill their building lists once at start.
- Likely causes: level-piece copies didn't copy `bIgnoreFor3DCursorCollision` (the bar's roof-level pieces have it), and
  our building, streamed in with the patch, may be missing from the lists, so a hit on our roof counts as outside.
- Fix in test (run 23): copies take the flag; the copier adds our building to both lists.

### F-35: The new building's walls aren't trimmed down in the cutaway
**Fixed** (EXP-07 runs 24 and 25: "walls appear to cut out normally now", "windows and door frames trim too"; `set`
is accepted, `get` reads back True). After F-31 the roof and upper floors hide, but the walls facing the camera stay full
height.
- Cause: trimming down and the camera cut-out need `bCutoutMask` on the piece's main mesh. The editor sets it on placed
  pieces; copies don't have it, and script can't set it (the UDK engine classes don't know it).
- Fix in test: the wall copies' main mesh is a class of their own, and the copier switches the property on for that
  class with the game's `set` console command, logging what `get` reads back. Window and door-frame copies aren't
  covered yet.

### F-36: A hider takes copied doors out of play
**Verified** (EXP-07 run 28, `look-162956.png`: "doors are in"). Found in run 27: the user's note was "most doors still missing (there is one in
the top)", and the entrance door was gone too.
- Cause: the copier made all six door copies (`XComMapEdDoor`, logged "copied door"), then the street hider hid five
  of them and moved them under the map. `IsHideable` skips our copy classes by name and missed the new one. A door copy
  is an `XComInteractiveLevelActor` to the class test that follows. The one left stood outside the hider's box.
- Fix: hiders skip `XComMapEdDoor`, and any actor whose class is in the `XComMapEd` package (`Class.Outer.Name`), so a
  later class can't fall into the same gap.

### F-37: Copied doors can't be opened
**Fixed** (EXP-07 run 29, to confirm). Found in run 28: the user's note was "doors are in, but ... can't open the
doors". The run 28 A* probes go round through the bar's own doors, never through the wing's.
- Cause: `XComInteractiveLevelActor.PostBeginPlay` calls the native `CacheMustDestroy` (`0xA5E740`). It sets
  `bMustDestroy`, then clears it if any `InteractionPoints` entry has a unit animation (byte +2 of the 28-byte
  `SocketInteraction`). On a copy that runs during `Spawn`, before the copy has any interaction points, so every
  copy is must-destroy and can't be opened.
- Also read: `IsDoor()` is `IconSocket == 0` (vtable 0x434, `0xAAAFF0`), which the copy takes from its source; spawned
  doors start in the auto state `_Pristine`, the only state whose `CanInteract` allows anything.
- Fix: `XComMapEdDoor.CopyFrom` works `bMustDestroy` out again after copying the interaction points. The stub drops
  `const` from it.

### F-38: Copied doors and windows don't work: the copies are in no state
**Verified** (EXP-07 run 30 for doors, `look-170659.png`: "ladder and doors work now nice"; run 31 for windows, with F-40). Found in run 29: "still can't go through doors or windows here", with the bar's
own doors and windows working ("but we can here").
- Cause: the game's doors and destructibles start in their auto state `_Pristine`
  (`XComDestructibleActor`; `XComInteractiveLevelActor` overrides it). A door can be opened only there:
  `CanInteract` is false outside it. A window can be broken through only there: `BreakWindow` checks
  `IsInState('_Pristine')` and a fragile toughness. Our script classes are compiled against the UDK stubs, which
  declare no states. The copies never enter the state, and run 29 logged the door copies' state as their class name
  (`XComMapEdDoor`).
- Fix: `XComMapEdDoor.CopyFrom` and `XComMapEdDestructible.CopyFrom` call `GotoState('_Pristine')` when the copy is in no
  state (`GetStateName() == Class.Name`), before turning ticking back on (the destructible's `BeginState` turns it
  off). The spawner's cars use the same `CopyFrom`, so they now start in `_Pristine`, as the game's do. That may
  bear on F-14.

### F-47: A copied second floor gets no floor tiles
**Open for script copies, set aside by the user** (EXP-08 runs 3 and 3b, 4 November 2026: "still can't get on the
second floor ... let's leave that for now as an open finding"). **Not met by copies made in the map**, which the
editor's Build makes: EXP-27 run 1 (9 November) raised a copy of Bar's sidewalk strip `XComLevelActor_21` to the bar's
floor 2 (surface 208), where the map has no floor, in the car park; the cursor landed on it and a soldier teleported
there stood on it and had a move range and a path along it. Such copies keep the saved properties script copies lack
(as EXP-24's van copies' cargo floors showed inside their buildings). Run 3 put a wood floor (two copies of
`URB_Bar_384CFloor`, tops at z 211 and 212) inside the block's 400-high shell as a second storey.
- The user: "can't seem to reach the second floor, cursor won't hit that floor so i can't even teleport to it".
- The log: every probe on the new storey (tiles (22, 22, 3), (21, 24, 3), (26, 19, 3)) is "on floor False", at load
  and 5 s later, although the tiles were seeded and rebuilt. So the inside ladder's top tile (21, 24, 3) and the one
  below it have no floor, and the game made no climb. The roof at z 402 still has its floor.
- Not missing collision: the wood floor's mesh has thin collision boxes over its whole footprint, as the roof slab
  has (`RB_BodySetup` `BoxElems`, 2 units thick).
- First guess, ruled out by run 3b: the headroom. The ceiling's I-beams (`XComLevelActor_4`, `BarCeilingIbeams`, z 362..397) collide as
  one convex hull covering the whole ceiling (about 980 × 1070, local z −38..−3), not as beams. Over a floor at 211
  that leaves 151 units, and the game marks no floor where a soldier can't stand. ComKit's storeys have about 190: its
  second-floor piece `Core_384FloorB` is at 208..210, the roof slab's underside at 398. (This hull is also why EXP-07
  run 20's roof had its floor at the beams' 396.9.)
- Run 3b left the I-beams out and put the floor's tops at 209.5 and 210.5, ComKit's height, with 188 units up to
  the roof slab. The user still couldn't get on the second floor, and the log is the same: every probe at level 3 is
  "on floor False", the ladder's top tile (21, 24, 3) and the one below have no floor, and the roof keeps its floor at
  402. So the headroom isn't it.
- What differs from the roof, which does get its floor on seeded tiles: the second floor is a plain-mesh copy
  (`XComMapEdLevelPiece`, of an `XComLevelActor`), the roof a fractured copy (`XComMapEdWall`). No plain-mesh copy
  has yet been seen giving a floor on a tile that the bake left without one (EXP-07 run 20's beams were on the bar's
  baked roof tiles). The copier's log also calls the top tile and the one below "occupied".
- To try next:
  - a fractured floor piece under the wood, as the floor-maker: URB_Bar's roof slab (`XComFracLevelActor_3`) or its
    porch strip (`Core_384FloorB`, the kit's second-floor piece), copied down as an `XComMapEdWall` and scaled to the
    two rectangles (hidden under the wood, so the stretch doesn't show);
  - the tile flags on (22, 22, 3) before and after the rebuild, to see what the rebuild writes there;
  - the same floor on a tile the bake marked as floor (inside the bar's old footprint, if a level there had one).

### F-46: A gap in the ground meshes doesn't stop movement
**Open** (EXP-08 run 2, 4 November 2026). Run 2's 4 × 4 hole (tiles x 3..6, y 27..30, no ground meshes at all):
- The user: "I couldn't actually put my cursor direct on it, but if i placed it on the other side the path showed over
  it". The game draws the hole as an even blue, which is what lies under the map.
- The copier's probes, at load, read the baked data: the paths went round the hole, or along its edge row. 5 s after
  load, after the rebuilds, the hole's middle tile (5, 29, 0) is "on floor True, floor z 0", and both A* paths cross
  it straight.
- Cause, likely: the tile rebuild gives every bottom-level tile a floor at the level volume's bottom (z 0), whatever
  stands there. Every level-0 tile is in the work set (see the native notes, F-29). The 3D cursor needs real
  geometry, so it can't land in the hole.
- Not the scaled ground pieces' collision: had it kept the full plane's size, the cursor would have landed on it.
- Related (run 1's log): URB_Bar's `PathBlockingVolume_0` at (39, 17) still steered the A* path at load, but 5 s
  later the path went straight through (39, 17). A path-blocking volume's effect is baked, and the rebuild drops it.
- Next: mark the hole's tiles as blocked with what the tile data does keep after a rebuild. Candidates:
  - `XComWorldData.SetTileBlockedByUnitFlagAtLocation`, the dynamic store the game uses for units;
  - `SetIsWaterTile` (bit 27);
  - an invisible blocker, which would give cover at the hole's edge.

### F-45: A map under a new name gets no dropship intro
**Verified again** (7 November 2026, EXP-20 run 9: "landing intro was working fine"). EXP-20 run 8 showed no landing. The editor's Build compiles
its patch `--stream-only`, without `map.shipAs`, so patchtool adds no `XComMapEdIntro`, and an M1 Build has no patch
at all. No Build variant had the intro. The patch's fix was verified in EXP-08 run 1c, 4 November 2026 ("the intro
works correctly now").
- Fix for the Build (`tools/bake/intro_copy.py`): the variant streams its own copy of the intro,
  `CIN_DropshipIntros_<variant>.upk`, in place of the original. In the copy, the base map's Switch String entry
  (`StringName`) names the variant. The exe finds the intro streams by the substring `CIN_DropshipIntros` (three places
  in the exe copy), so the copy's name keeps it at its start. In the log, `XComMapEdIntro_933`
renamed `URB_Bar`'s case (3) of `SeqCond_SwitchString_8` at load, on its first try (30.47 s). The intro started at
48.01 s. Found in run 1 ("there was no
landing"); run 1b fixed one cause, and the user still saw no Skyranger.
- How the intro works (`XGBattle.PlayCinTacticalIntro`, the `LevelCinematicIntro` state):
  - the game seats the squad in the `CinematicDropship` and fires `SeqEvent_OnTacticalIntro` with
    `WorldInfo.GetMapName()`;
  - that event's Kismet is in the streamed `CIN_DropshipIntros`, not in URB_Bar (read with
    `tools/upk/kismet_links.py` from the reference UDK's `CIN_DropshipIntros.udk`);
  - four Switch String nodes pick the landing by the exact map name. For `URB_Bar`, `SeqAct_SetLocation_84` puts the
    dropship (`SkeletalMeshActor_6`) at (560, −2683, 0) and fires `CIN_PlayDS_03`;
  - a name none of them knows falls through every `Default` case to `CIN_DS_Stop`, and there is no landing.
    URB_BarRemix (F-42) had none either; nobody noticed then.
  - URB_Bar's own Kismet only hides the grounded Skyranger for the intro (`CIN_HideForIntro`) and shows it after
    (`CIN_IntroFinished`).
- **Cause 1 (run 1): the landing prefab.** LWR's landing-zone mutator (`XComLZMutator.RespawnLZObjects`) spawns the
  landing zone's pieces with the map's own pieces as templates. Run 1's hider had switched off two of those:
  - `XComBuildingVolume_6`, the dropship's soldier-spawn volume, had lost its collision;
  - `XComLevelActor_6`, the `Drop_Zone` marker, was hidden.

  In run 1 the intro camera never moved. In run 1b, with them kept, it moved as in URB_Bar's runs: from
  (2365, 502, 842), the `SMEDIS` locations in the log.
- **Cause 2: the map name.**
- Fix:
  - `gen_exp08.py` keeps every actor whose archetype belongs to a landing prefab (`DGN_DropShipSoldierSpawn.*`,
    `VEH_Lv1Skyranger_MOD.Prefabs.*`): 14 in URB_Bar. The editor must treat them as gameplay pieces, not scenery.
  - The editor does (9 November 2026): the compiler refuses moving or deleting one (`landing-zone`; copies build),
    and the inspector marks them **Landing zone**. Since 13 November 2026 a move or delete builds, with the warning
    (the user: warn, don't block; map buildings plan, step E2b). One to six of each cached map's
    exported pieces (two in URB_Bar; the volumes are not exported pieces). Offline tests only; no in-game run needed,
    since nothing about the landing changes.
  - With `map.shipAs`, patchtool adds an `XComMapEdIntro`. At load it renames the base map's case
    (`IntroMapName`, here `URB_Bar`) in the running game's switches to the map's own name, so the base map's landing
    plays. It needs a stub of the game's `SeqCond_SwitchString` (in `unrealscript/XComGame-stubs.diff`).
  - It retries for up to 30 s, in case `CIN_DropshipIntros`' sequence joins after the patch loads. The log says when
    it renamed a case, or warns that it found none.

### F-44: Hidden physics bodies are still drawn (withdrawn)
**Withdrawn** (4 November 2026). Run 1 showed green corpses on the blank ground. The user: "they're just generated
by the AI pods that spawn there" (abduction pods come with corpses). URB_Bar's own 13 corpses (`KAsset`, `CivFlatB`)
were most likely hidden all along. Run 1b's change to the hider (stop the physics, detach the meshes) was taken out
again in run 1c.

### F-43: Pieces at the play area's edge stay when a box hides the play area
**Fixed** (EXP-08 run 1, deployed 4 November 2026, 19:11; to confirm in game).
- Cause: a hider takes an actor when the centre of its bounds is in its box. A box over the whole play area (52 × 39
  tiles) keeps everything whose centre lies outside, however far it reaches in. In URB_Bar, 40 such actors reach
  more than 8 units into the play area: the asphalt row north of it and column east of it (up to 384 units in), the
  sidewalk ring along the east and south edges, the bushes on the east sidewalk and a street sign. New ground laid
  there would overlap them.
- A piece's pivot is not its centre: `XComDestructibleActor_162`, a fence, has its pivot outside the play area and its
  centre inside, so the hider takes it anyway.
- Fix: `tools/patch/gen_exp08.py` lists the actors whose bounds centre is outside the box but which reach more than 8
  units in, and hides them by name (`alsoHide`). It keeps the grounded Skyranger, the squad's ship, 111 units in at
  the north edge. The new ground covers every original asphalt plane that reached in: 6 × 5 planes, not 6 × 4.

### F-42: A seeded base map can't be shared with the original map's record
**Verified** (4 November 2026, 18:07: `URB_BarRemix` loads with the wing, "everything looks good", and LWR's landing
zones work under the new name).
- Cause: patchtool seeds bit `0x1` on empty tiles of the base map so that the runtime rebuild re-checks them (F-29).
  A seeded tile that nothing rebuilds keeps the bit, and the game takes it as blocking. Our patches rebuild every
  seeded box at load (`XComMapEdTileSeeds`); the original record (`patch_bar`) doesn't. So the shipped bar would have
  phantom blockers on the seeded tiles if both records used one seeded URB_Bar.upk.
- Fix: a remix ships its seeded base map under a name of its own (`URB_BarRemix.upk`), with its own map record. The
  original file stays untouched. Map-name keyed config, such as LWR's landing zones (`DefaultLZMutator.ini`) and LW's
  map rules (`DefaultMiniMods.ini`), needs copies of the original's lines under the new name.

### F-41: A car placed off the tile grid blocks the tiles at its ends
**Fixed** (EXP-07 run 32, to confirm). Found in run 31: the roof car "no path to right against the car ... on the
front and back", and the north SUV "can't be reached properly from the front". The map's own compact gives cover at its
tail.
- Cause: URB_Bar's cars stand so that their bodies fill whole tiles: `XComDestructibleActor_20`'s bounds reach only 7-9
  units past its 3 x 2 tiles. Our cars stood where the screenshot put them, so their noses and tails reached 36-52
  units into the next tiles. The game took those tiles as blocked, and the nearest free tile was a tile away, out of
  cover.
- Fix: place cars on the grid, as the map does:
  - a compact's body is 294 x 160 units, its pivot 44 units behind the body's centre, so 3 x 2 tiles;
  - an SUV's is 384 x 182, so 4 x 2 tiles.

  Tile edges are at x = -2784 + 96·i and y = -1920 + 96·j. The body's centre goes on a tile edge across its even
  width and in the middle of its tiles along its odd length.
- Run 33: the spawner snaps a car to the grid itself from its bounds (`bSnapToTiles`), so a spec needn't work this
  out; the three cars go back to where the user circled them, snapped.

### F-40: Copied windows can't be run through: not interactive
**Verified** (EXP-07 run 31: "windows now can be smashed/run through correctly"). Found in run 30: "windoes still can't be pathed through though", with the door
copies working after F-38.
- Cause: URB_Bar's windows are `XComDestructibleActor`s from `ComKitWindows.Archetypes.ARC_ComKitWindow_*`
  archetypes, which set `bInteractive` (and a glass toughness). A copy is spawned from the class defaults and copies
  its source's properties; `bInteractive` is `const` in the game's class, so `CopyFrom` never copied it, and the copy
  was a non-interactive pane. The bar's own windows and the wing's sources set the same actor properties, and their
  mesh components set nothing else.
- Fix: the stub drops `const` from `bInteractive` and `bIgnoreForPathing`, and `XComMapEdDestructible.CopyFrom` copies
  both. It also logs each glass copy with its state.

### F-39: A ladder whose look is a mesh copy can't be climbed: its foot tile isn't walkable
**Verified** (EXP-07 run 30, `look-170659.png`: "ok ladder and doors work now nice"; the A* probe climbs at the
ladder's own tile). Found in run 29: "ladder still unusable", and the user's screenshot of the
foot: "that V means it's not a walkable tile".
- Cause: the wing's visible ladder was a copy of the bar's ladder as a plain mesh (`XComMapEdLevelPiece`, an
  `XComLevelActor`, collision off), with a hidden patch ladder beside it for the climb, as step 3b had. But step
  3b's visible ladder was the bar's real `XComLadder`, moved there. The level piece made the foot tile (31, 7)
  unwalkable. The game makes a ladder's climb only when its foot tile is floor (native `0x777580`). The run 29
  A* probe climbs one tile west, at (30, 7), and walks round the foot.
- Fix: one visible patch ladder object (a real `XComLadder` with URB_Bar's mesh), placed as URB_Bar's ladders stand.
  patchtool puts the patch's visible ladders in each hider's `KeepNames` and only the hidden ones in
  `HideInPlace`. The copier's `LadderFootRebuild` rebuilds each nearby ladder's foot tile last and logs what the
  climb needs there. `bCopyLadders` is still there, but not to be used for a climbable ladder.

### F-32: A small copied wall piece is lit differently from the long wall beside it
**Open** (EXP-07 run 15). The user's note: "odd lighting mis match between the corner wall bit and the rest of the
wall". Each copy has its own dynamic light environment, sampled around its own bounds, so a short corner return and
the 12-tile end wall next to it can get different light.

### F-48: Editor placement rules need qualification per piece recipe

**Open** for edited gameplay behavior. [EXP-09](experiments/EXP-09-editor-placement-audit.md) is a source/code audit,
not a new game verification. Bar has 822/966 visible actor pivots away from tile corners and 169 non-cardinal yaws;
Temple has 1,121/1,667 and 93 respectively. Both contain nonzero pitch/roll. Thus a universal pivot/cardinal-rotation
requirement is not supported by the authored map data. F-41 instead demonstrates the importance of a car's body
footprint, and F-39 of ladder endpoint floors. Current copier, seeding, link-moving and bake restrictions must be
extended and tested as tool limitations, with in-game feasibility deciding the final support matrix. The
first-editor plan defines the proposed runtime tests and snapping rules.

[EXP-11](experiments/EXP-11-static-placement.md) run 1 is the first such runtime test for static pieces:
- Ten street-light copies turned 15, 45 and 90 degrees in yaw, pitch and roll, and fog pods 24 and 48 units off the
  tile centres, stand exactly as the project has them (0.0000 units and 0 rotation units off, at load and 5 s later).
- The pods on the floor give cover.
- Run 2: the moved fog pod's old tile and the deleted lamp post's tile are open, and the railing's gap is there with
  its east neighbour standing.

### F-49: A piece lifted a level above the floor gives no cover

**Observed** (EXP-11 run 1); no fix needed, the editor warns.
- Symptom: of three fog pod copies, the one placed 64 units up (one tile level) gave no cover on the floor below or
  beside it. The two on the floor did.
- Cause (likely, not traced): the rebuilt tiles give cover where the piece's collision meets the tile level that
  units stand on. A piece a whole level up is clear of the floor level's tiles.
- In the editor: the viewer's tile grid turns a piece's tiles blue, with lines down to the floor, when its lowest
  point is more than 8 units above the saved floor under it. The readout says it "may give no cover". The user asked
  for this after the run.
- Not tested: smaller lifts (between 8 and 64 units), and whether a unit can stand on or under a lifted piece.

### F-50: Effects placed around a piece stay behind when it is moved or deleted

**Open for the light and the decals; the smoke fixed offline** (17 November 2026, export 30: an effect placed by a
prefab instance at whose own place one piece stands is carried by that piece, `scene_metadata.effect_metadata`,
`carriedHow: prefab`. URB_Bar's pod moved a tile east and two north and turned a quarter, built and read back: its
five smoke emitters stand around it as before. Not played.) Found in EXP-11 run 2.
- Symptom: the fog pod moved one tile east, but its green smoke kept rising from the old tile. The user's note: "can
  path through but there's some green smoke emitter still going".
- Cause: the map placed the smoke as separate actors around the pod, not as part of it:
  - five emitters (`Emitter_39`, `_43`, `_48`, `_49`, `_50`, archetypes `FX_AlienEnvironment_B.PRE_Pod_Smoke`
    `Arc0` to `Arc4`), with `PrefabInstance_12` at the pod's place;
  - the point light `PointLight_8`;
  - three decals (`DecalActor_6`, `_8`, `_10`).
  The viewer's export holds only mesh actors and lights, so neither the viewer's linked pieces nor the compiler know
  these belong with the pod. The project moved only the pod's mesh actor.
- Fix (to do):
  - Export emitters and decals: position, archetype or template, and prefab instance.
  - Link them to the piece they stand around, by prefab instance or by distance (the pod's smoke prefab instance
    sits on the pod's pivot), and show them in the viewer.
  - Compile them with the piece:
    - A delete hides them. The hider can already: `HideActor` deactivates an emitter and hides a decal.
    - A move hides them at the old place and makes new ones at the new place. A spawned emitter with the same
      template is enough; a decal needs a spawned `DecalActor`.
    - Baked lights can't move; a moved piece's light stays or goes, with a warning.
- Until then: delete or move such pieces knowing their effects stay.

### F-51: Temple Ship's doorway walls aren't drawn in the lab

**Set aside by the user** (6 November, after [EXP-14](experiments/EXP-14-temple-variant.md) runs 1 to 3c: "it may be
that's just normal in LWR or something"). Not the
edit: the walls are missing from the unedited `TempleShip` too (run 1b). Not the test slot either: run 2, the real
Temple mission loaded from the user's save, shows the same. (After run 1b the user set it aside as "how we load it";
run 2 reopened it.)
- Symptom: "the big walls with the doors seem to be invisible, we haven't modified those so something is wrong
  there". At the user's tile (33, 18, 7), cover shields stand where the wall should be, so the walls still collide.
- The pieces: the three `DoorwayBMain` destructibles on the line y −7584: `XComDestructibleActor_146` (x 1200, with
  the door `XComInteractiveLevelActor_1`), `_135` (x −1104) and `_188` (x 48, on the walk at z 192). All are in
  building 10698, floor 1, and none is hidden in the map.
- Ruled out:
  - The patch. The hider hid only `_206` and `_208` ("hid 2 of 2 exact targets"), the copies stand 6 or more tiles
    away, and the copier's cutout switch acts only on our own mesh classes.
  - Temple's Kismet. Its hide steps toggle the gate doors (`XComLevelActor_7` to `_10`), the Skyranger prefabs and,
    at the outro, the psi device `XComLevelActor_249`.
- Run 1b loaded the unedited `TempleShip` through the same test slot, with no patch. The walls were missing there
  too ("invisible in original map so yeah it's probably to do with how we load it").
- Run 2: the user's tactical save inside the real Temple mission (LWR v2.01.14), with the seeded map and the patch.
  "door walls are invisible like before".
- Also ruled out: LWR's `patch_hide_randomized_objects`, streamed in every run. Its Kismet hides only bombs, energy
  nodes and Meld containers, by archetype, class and layer.
- Run 3: the user's HQ save, the unedited map, a normal start. "right after intro, I could see the door walls, but
  then they disappeared", with a staggered camera on every mouse move until a save and reload; the walls stayed
  hidden. So the map draws them, and something hides them at run time once the battle starts.
- Likeliest (not verified): the game's building and prop hiding (`XGLevel.UpdatePropHidingAndBuildingHiding`, native,
  every tick), which hides a building's floors by the cursor's floor. The doorways are floor 1 of building 10698.
- Also ruled out as lab differences: the lab's console `Engine.upk` (LWR's own variant; it differs only in
  `Console.ConsoleCommand`) and the lab's own generated settings (graphics options only).
- Next: in run 3's Ironman save, the console's `ToggleBuildingAndPropHiding` and `ShowCursorFloor`.

### F-52: Copies look bluer than the map's baked pieces

**Fixed** ([EXP-14](experiments/EXP-14-temple-variant.md) run 7, 6 November): copies that take their light once
while the sky light is off, then keep it, match the map's own barriers ("looks great now!"), and the soldiers keep
the sky light. Since run 8 this is the default for every copy of a baked piece and every spawned piece
(`XComMapEdSkyFree`), on maps whose sky light lights units only but reaches light environments. Run 8 (the user's
project) is to confirm it in the game.

**Run 10: damage undoes it.** A grenade on a console copy turned it lavender again, because the game resets a
damaged piece's light environment (state change, mesh swap) and it takes its light with the sky light on. Since run
11, `XComMapEdSkyFree` watches the pieces' state, mesh, materials and fragments, and relights a changed one with the
sky light off for 0.3 s. To confirm in the game.

**Run 11: the relight didn't hold.** It ran at the hit (the pair went `_Pristine` to `_Damaged`) and the pair still
came out lavender. `_Damaged` turns the piece's tick on, and nothing else on this console. Either a ticking piece's
light environment keeps taking the sky light, or something resets it later. Not told apart.

**Since run 12, the sky light moves instead.** Such a sky light is switched off for good once a piece registers,
and an `XComMapEdUnitSky` with its brightness and colour lights the units on Gameplay_1 only (the units' channel,
as most maps' sky lights). Damage then has nothing to bring back. Also lost: the lower hemisphere (0.01 on Temple)
and the fill on whatever else the map lights live (doors, debris). **Passed in run 12:** a grenade on a console
left its tone as it was, and the soldiers looked normal.

First observed in runs 1 and 4.
- Symptom: the laser barrier copy "looks a bit more blue-ish than the rest of the map". In run 4, the barrier
  and core copies have a "weird blue-ish hue" next to the map's own barriers and cores.
- Cause (likely): a copy is spawned at run time, so it has no lightmap. It is lit by its own dynamic light
  environment on the dynamic channel (the log shows it enabled and dynamic). The map's pieces carry the lighting
  baked in the editor, bounced light included. Compare F-32, where two copies are lit unlike each other.
- Options:
  - The toolchain cannot yet attach newly baked lightmaps. Selected-receiver baking with surrounding scene
    data is a research option; a whole-map rebake is not always required (F-55).
  - A per-map setting for the copies' light environments (`AmbientGlow`, `AmbientShadowColor` and the like), tuned by
    eye, could bring the tone closer. Untested.
- Read from Temple's lights (run 4):
  - the direct lights that reach the copies include cyan doorway spotlights (139, 216, 229; brightness 0.5). Each
    barrier copy and core copy7 stand inside one's cone, at about 700 units;
  - the sky light was initially read as off; only BSP/Static/Dynamic are explicitly off (CompositeDynamic is
    inherited on; see run 5 and F-55 below);
  - the dominant light is warm;
  - the 1,190 lights Lightmass made from glowing surfaces reach none of the copies;
  - the light environment defaults have no tint.
  So the tint is likely those spotlights, without the warm bounce that the baked pieces carry.
- Our copies draw their light environment the engine's default way: one synthesized directional light, and a
  two-colour sky light for the rest. The game's doors (`XComInteractiveLevelActor`), which are lit the same live way
  among baked walls, use `bSynthesizeSHLight` and no synthesized directional light. Untested for our copies.
- Run 5 (deployed 6 November, 16:26): `CopyLights` on the copier sets each destructible copy's light environment.
  The settings are the draw mode, on/off environment shadowing and a glow, and tuned copies follow values the
  console's `set` changes. Six laser barrier copies compare them, beside the project's copies and the map's own
  barrier.
- Run 5 so far: both north copies are violet beside the map's own dark barrier, where no cyan light reaches. The likelier
  source is Temple's lavender sky light (110, 99, 156): its BSP, Static and Dynamic channels are off but
  `CompositeDynamic` stays on (the default), the setting that lights only light-environment objects (units, our copies).
  To be checked by turning it off from the console. A 0.1 grey `TuneGlow` applied live (logged) but showed no change.
- Run 5 result: `set SkyLightComponent Brightness 0` brought the copy to the original's brightness (value 0.21 to
  0.15; the original 0.15), though it stays bluer (hue 270 against 290). The soldiers were too dark without it.
  `TuneGlow (R=1,G=0,B=0,A=1)` turned nothing red: `AmbientGlow` has no visible effect. Copies whose settings were
  changed in play stopped following the sky light; the reattach is gone.
- Run 6 (deployed 16:43): copies leave out `CompositeDynamic`-only lights through their light environment's own
  channels, A (BSP, Static, Dynamic) and B (BSP, Static), side by side by the map's own barrier.
- Run 6 result: A is lavender as before, and B is black. A light environment takes lights only through the Dynamic
  channel, and the CompositeDynamic-only sky light comes with them, so channels can't leave it out.
- Run 7 (deployed 16:50): `bNoSkyLight` copies take their light once while the copier has the sky lights off for
  2 s at load (and after a save is loaded), then keep it (`bDynamic` off). The soldiers keep the sky light.
- Run 7 result: passes. Hue 283 and 286 against the original's 286 (was 266). A survey of sky lights in nine more maps:
  all light only units, and most use `Gameplay_1`, which our copies don't take. Temple's keeps the default
  `CompositeDynamic`, which every light environment takes (EXP-14).

### F-53: The psi device copies give no cover at their ends

**Open** ([EXP-14](experiments/EXP-14-temple-variant.md) run 1); likely the piece's shape, not checked in game.
- Symptom: at copy3's two end tiles, (22, 23) and (22, 26), no cover ("no cover behind", "no cover from the front
  either"). The copies stand as posed, collide and block, and the tile rebuild ran over them.
- The original `XComLevelActor_249` (scale 2.5, yaw 180, roll 2560, which is 14°) stands 16 units into its floor.
  In its baked tiles, the tiles beside its long sides have cover (`0x0808`, `0x4004`), and so does the tile off one
  end (`0x1101`). The copies have roll 779 (4.3°), as the project has them, and stand 4 units into the floor.
- Mesh slices at 64 and 96 units above the floor, the heights the cover test uses: the device fills its tile's width
  (6 to 10 units from the side edges), but stands 35 to 75 units back from its end edges. Copy3's end that matches
  the original's covering end is 8 to 25 units further back than the original's, because it leans less.
- Not yet checked: whether the copies' long sides give cover, and the game's own cover flags around a copy. A later
  run can log them with `XComWorldData.GetCoverPoint`.

### F-54: Copies made after loading a save from before the patch don't block or give cover

**Cause found in the log** ([EXP-14](experiments/EXP-14-temple-variant.md) run 2); **a fresh start verified** (run 4,
6 November, 16:06). With the same project as a new campaign's first mission, the cores and the laser barriers block
and give cover all around. The log shows each core's own tile fully occupied from the walk up.
- Symptom: two power core copies on Temple's walk "can be walked through and provide no cover". This was after
  loading the user's tactical save from inside the Temple mission, made in a game without the patch.
- The map's own power cores block and give cover. Their tiles are occupied (`0x8000`), and the tiles beside them
  have high cover (`0x4004`, `0x0101`). Both meshes, the core's and the laser barrier's (whose copies gave cover in
  run 1), have simple collision.
- The copies were placed exactly. Their flags say they collide, block and block vision, and the copier's, hider's
  and seeds' rebuilds finished.
- Cause: a tactical save holds its own copy of the map's tile data, and loading it puts that copy back. The tile
  data came from the game the save was made in, which had no copies and none of our seeds. The run 2 log shows it:
  - 11.36 s: the copier, hider and seeds queue their rebuilds (586 tiles);
  - 11.42 s: `Object XComWorldDataContainer Transient.XComOnlineEventMgr_0:Checkpoint_TacticalGame_0.XComWorldDataContainer_0`,
    the save's tile store, being read;
  - 11.57 to 11.67 s: `LOADING CHECKPOINT`;
  - 12.17 s: our rebuilds report finished;
  - 12.24 s: LWR's `XComBombMutator: DoWorldDataRebuild` rebuilds its own tiles.

  The checkpoint does not record the actors themselves: `Checkpoint_TacticalGame` lists `XComDestructibleActor` in
  `ActorClassesNotToDestroy`, so the copies stay, as the log's flags show. But their tiles are those of the save:
  open, with no cover.
- Not tested: a copy made at a fresh mission start (run 1's laser barriers gave cover), or a second rebuild a few
  seconds after a load (the copier's `LateRebuild`). A save made with the patch running kept the hidden bar out of
  play after a reload (EXP-07 run 3, F-22).
- Why saves made during a patched mission are fine: their tile store already has the pieces, as rebuilt
  (EXP-07 run 3 kept the hidden bar out of play after a reload).
- A save from before the patch can't be fully mended. A second rebuild after the load (the copier's `LateRebuild`)
  would redo the floor-level tiles, which have floor bits, but not the empty tiles above, whose seeds the save's
  tile store doesn't have (F-29).
- Practice: check variants from a fresh mission start (a Geoscape save), not from a tactical save made without the
  patch.

### F-55: Edited-map lighting needs native bake data or a qualified shared dynamic path

**Open** for a fix; read-only data verified on 6 November in
[EXP-15](experiments/EXP-15-lighting-data-audit.md). See the separate
[lighting research](map-lighting-research.md) for routes A/B and proposed experiments.

- Of 968 Bar and 1,707 Temple placed static/fractured component records, 930 and 1,651 have LOD-0 texture
  lightmaps. The checked native records use a normalized-color texture, a directional texture, atlas scale/bias
  and light GUIDs, plus separate shadow-map references. A generic RGB bake or a lighting-channel toggle is not
  a complete replacement.
- Both maps also contain volume-lighting samples: 1,743 and 8,941. All four current Temple copy pivots lie within
  stored sample spheres. This is a structural/geometric observation, not proof of runtime interpolation or of the
  copies receiving the samples. The suffix decoder's limits are recorded in EXP-15.
- Correction to F-52's earlier exclusion: Temple's sky light explicitly disables BSP/Static/Dynamic, but not
  CompositeDynamic; the latter is enabled in the game's base light default. Its influence must be isolated.
  The concurrently recorded EXP-14 run 5 reaches the same hypothesis; no fix is claimed by this audit.
- A selected-receiver bake can include surrounding geometry while updating only selected outputs; a full-map
  rebake is not theoretically necessary for every addition. Changed shadows/bounce on existing receivers must
  still be handled, and whole-room/map rebakes may be appropriate for major edits.
- Recommended gates: matched-pose/source-isolation tests; native lightmap attachment/encoding proof; in-place
  conversion of original components; then room-scale fidelity, performance, destruction and save/reload checks.
  Keep identities/gameplay intact and keep new texture data out of the shared original Lighting.tfc.

**Baker follow-up (6 November, EXP-16):** the Temple workaround now passes its recorded F-52 run-12 checks,
so baking is optional longer-term work. The separate
standalone baker design describes the scene adapter, CPU transport worker,
EW codec/native writer, staged proofs and packaged-user workflow.

- [EXP-16](experiments/EXP-16-baker-input-audit.md) measured 367,877 / 1,038,248 LOD-0 instance triangles and
  6,773,096 / 7,263,372 mapped rectangle texels for Bar / Temple; these are input-workload proxies, not bake times.
- All 116 / 119 unique lightmap-contribution GUIDs matched LightmapGuid, while the 2 / 1 shadow GUIDs matched
  LightGuid. Preserve the two associations separately.
- 131 / 213 2D LOD records have non-unit directional scale; maxima 5.83 / 16. The exact coefficient decoder,
  color space and native attachment remain unproven. Stage those compatibility tests before a large solver.
- Proposed first scope: stationary opaque static scenery with existing valid UVs, relighting an existing receiver
  before introducing newly serialized baked pieces. No baker/runtime/package injection was implemented here.

**Design review (6 November evening, EXP-16 run 2):** the codec tests now run on fixed-size edits of a derived map
and a variant texture cache, not behind the growing writer; UDK 2011-09 Lightmass is the encoder reference; a new
stage rebakes the receivers around runtime copies, the route to fixing F-24 without new exports.

- In both maps every `NormalizedAverageColor` slot scale is 1 and most texels have a largest channel of 1;
  `DirectionalMaxComponent` scales differ per channel (up to 16) and its channels correlate only 0.69–0.82. Reading:
  normalised colour times three directional intensities. A hypothesis, not a decoder.
- [`package_edit.py`](../tools/upk/package_edit.py) makes fixed-size edits in any compressed chunk and moves later
  chunks; whether the game accepts moved chunks is the next check (C0).
- [EXP-17](experiments/EXP-17-lighting-edits-in-game.md) in the game:
  - Run 1 passes C0 and C1: the rewritten map loads and the texture is read from `Lighting_7000.tfc` by its renamed
    cache FName. `NormalizedAverageColor` is the light's colour: the painted floor lit red with its pattern intact.
  - Run 2: the directional slot scale is linear, but the `DirectionalMaxComponent` value enters raised to a power of
    about 2–2.5, not linearly.
  - Run 3: the power is about 2.2 (sRGB-like; the 8/31 stripe matched, squaring would have matched 7/31). On the
    flat asphalt the three channels act as directional weights, not colours: red-only and green-only light it
    equally and nothing is tinted; blue read lower, but only beside the police car's baked shadow.
  - Run 4: on an open floor and on the asphalt (blue moved away from the car) the three channels weigh the same,
    and they add: grey 19/31 in all three matches one channel at full value; 24/31 and 15/31 scale as value^2.2
    summed over the channels. Run 3's low blue was the car's baked shadow.
- [EXP-18](experiments/EXP-18-udk-lightmass-calibration.md), UDK Lightmass calibration (unattended bakes on the
  hidden desktop): UDK writes EW's format; the three channels point along UE3's lightmap basis (azimuths 90°, 210°,
  330° in the tangent frame, 35° up); for one light each stores value^2.2 × scale ≈ (2.00 sin e + 0.24 cos² e) ×
  max(0, l·b). Brightness scales linearly; the colour texture holds the light's linear colour normalised to its
  largest channel, and the directional values carry that channel. Several lights add per colour: the colour texture
  is the summed coefficients' colour normalised, each directional value the largest colour channel of its
  coefficient. Point and spot lights (BakeCalib6 and 7, texel by texel) follow the same codec with the radial
  falloff (1 − (d/R)²)^F and the cone factor clamp((cos θ − cos outer)/(cos inner − cos outer), 0, 1)², and an
  elevation term that grows with the light's Lightmass source radius ρ: S(e, α) = 2 sin e (1 − 0.55 α²) +
  (0.114 + 1.84 α) cos² e, α = asin(ρ/d), 3–5% rms per texel for lights like the bar's. UDK's default ρ is 100;
  every point and spot light in `URB_Bar` sets 32.
- Our own bake in the game ([EXP-17](experiments/EXP-17-lighting-edits-in-game.md) runs 5 and 6):
  - Run 5 relit the bar's pool-table floor from its 52 lamps with our encoder, without shadows. It renders normally
    and matches the original where nothing blocks the light.
  - With soft shadows (Embree), the emissive surfaces' generated area lights and one bounce, 64% of the floor's lit
    texels are within 10% of the original (correlation 0.98). Dim floor beside objects comes out at about 0.8.
  - Run 6 shows that in the game as a checkerboard against the original. It passed: no checkerboard shows except
    faintly in the darkest floor, where the relit floor was at 0.4 of the original.
  - That came from spot lights' bounce. UDK bounce calibrations (EXP-18, BakeCalib8–11) match our bounce for
    directional and point lights, but Lightmass bounces spot light 3.5–8 times more and wider than their cones.
    Doubling spot cones for bounce sources brings the floor to 69% within 10%.
- The whole bar room relit (EXP-17 run 7, 178 components, offline so far): 23% of lit texels within 10% at first.
  - About a fifth of the room's texels lie inside geometry: floor under wall feet, fracture pieces' interior faces,
    wall pieces sunk into each other. Our trace made them black; Lightmass left them lit. They are left out of the
    relight now (`bounce.buried_texels`): 25%.
  - The environment light was about 4 times too bright on the roof and sidewalks. UDK BakeCalib12 (EXP-18): the
    colour decodes as sRGB, and Lightmass's environment is 0.266 of the radiance we assumed, on every receiver.
  - The one component with `StaticLightingHiddenByDefault`, a corner column inside the wall pieces, was baked lit
    as if they weren't there. It keeps its bake.
  - Walls, ceilings and ducts get most of their light indirectly, and ours is about 0.55–0.65 of the original there.
    EW's Lightmass settings are UDK's, apart from the emissive threshold for mesh area lights (0.5, UDK 0.01), so
    UDK bakes can calibrate this.
  - Per 192-unit cube the room would show a checkerboard (27% of texels in cubes within 10%), so run 7 was not
    deployed. Fitted scales on the bounce, or smoothing its sources, don't close the gap.
- So edits are relit as a change on the original bake (EXP-17 run 8): unchanged light stays EW's own, and our
  model's error only scales the change. Run 8 passed in the game: one ceiling spot switched off over the whole room
  takes away its pool of light (38% darker on screen there) and leaves the rest unchanged, without artifacts. The
  pool table's shadow, also taken away, lies almost entirely under the table, so it barely shows.
- A deletion made in the editor plays on the relit map (EXP-17 run 9, passed in the game: the table, the glass on
  it and the table's cover are gone, and the rug under it is evenly lit, brighter toward the windows as predicted,
  with no shadow of the table left): the compiler's exact hider in a
  plain streamed patch (`compiler.py --stream-only`), the variant relit without the pieces, and both in the test slot
  (`deploy_fixture.py --stream`). The pool table's shadow sits on a red rug under it, a dark rectangle with leg spots
  in the original bake; relit, the rug's middle goes from 0.028 to 0.076 (median) and the spots go.
  - A texel counts as buried only if it is buried both before and after an edit, so the floor inside a removed piece
    that stood on it is relit. Its light before must be computed, not set to zero: borderline texels elsewhere
    (54 on a wall 180 units away) flip with the edit, and zero there added a false change of 0.16.
  - A copy a patch places casts no shadow on the baked map: it is lit live, and its light environment has
    `bCastShadows` false (from `XComDestructibleActor`). The relight now adds copies as casters at their poses
    (`relight.py --edit-spec`, EXP-17 run 10, passed in the game: the moved table has a soft shadow around its base,
    the floor between it and the counter 25% darker on screen, and low cover from the seeds): the pool table moved
    into a lamp's pool leaves the floor
    under it near black (6.76 → 0.033), as the original bake had under it at its old place (0.028). A copy put back
    at its source's own pose changes at most 5 texels.
  - A relit variant takes the patch's tile seeds (`map.seedExternally`, `deploy_fixture.py --seed-plan`). Seeding it
    changes only its world data chunk, exactly as seeding the original map does.
  - A piece added from nothing works the same way, and the whole chain now runs from the editor (EXP-17 run 11,
    passed in the game): Build makes the variant package (`tools/editor/build.py`, 2 minutes 35 seconds for a copied
    claw machine) and `tools/lab/lab_install.py` installs it. The copy stands under a lamp at the counter's corner
    with a soft darkening of the floor around its base; the original stays at the wall. Most of an edit's receivers
    barely change: beyond 384 units no texel changed by more than 0.045, so relight now leaves those out with a quick
    reach test.
  - Lights missing from a receiver's light list did not explain anything here: those missing from the rug's list
    are spots that never reach it. Our model matches the rug's original light where the edit leaves it alone
    (original 1.05 times ours), so the light the deletion adds needs no calibration here.

### F-56: A copy where little direct light reaches comes out black

**Fixed** ([EXP-20](experiments/EXP-20-growing-writer.md) run 7, 7 November: the pairs are made in the map and baked
for their place, and the user found them lit). Was open again after
[EXP-14](experiments/EXP-14-temple-variant.md) run 15. It was set aside after runs 11 and
12 (6 November): it comes from this place in this map, and the user asked to leave it rather than work around it.
In run 15, from the editor's relit build, one of the low-cover pairs is near black (shot 12:21:45). Now that we bake
our own lighting, the user asks whether that can fix it.
- Our bake doesn't touch the copies yet. They are spawned by the patch at load and lit live by their light
  environments, so they get only the direct light that reaches them, never the bounce.
- **Two ways with our own bake:**
  - **A fill measured by the baker** (quick). The baker gathers the bounced light arriving at each copy, which the
    map's own pieces there get from their bake and a live-lit copy misses. The build passes it to the patch, and the
    copy's light environment takes it as a fill when the copy is made (`AmbientGlow`, or a hemisphere sky light on a
    channel only that copy takes). Not yet known: whether `AmbientGlow` works when set at load. Run 5's test set it
    during play, on a copy whose light had stopped updating.
  - **Copies baked themselves** (step L4 of the baker plan). The copy goes into the variant map as a real piece with
    lightmaps of its own, made by the growing package writer (also UDK-removal U2). That is the full fix, for this
    case and for a copy looking slightly different from its original anywhere.
- Symptom (run 11): of the user's south pair of alien consoles, laid on their sides and stacked back to back
  2.6 units apart, one is "completely black" and the other darker than the map's pieces. The north pair, stacked the
  same way, is lit.
- Not the cause: the stacking. Run 12 traced the lights from the bounds' closest point
  (`bTraceFromClosestBoundsPoint`) in case a light trace started inside the other console, and the console stayed
  black. That setting is taken back out (it lets a light behind a wall reach a piece standing against it).
- Cause: almost no direct light reaches the south place. Its nearest light (`PointLight_6`) is under the deck, and
  the others are near the end of their reach. The north place has four lights above it within 650 to 860 units. The
  map's own pieces there are lit by the light build's bounce, which a piece lit live doesn't get. The map gives units
  a fill for that, the sky light, and our pieces leave it out (F-52), so the side facing away from the little light
  that reaches is black.
- Options: move the piece where the map's lights reach it, or give our pieces a fill of their own (`AmbientGlow` on
  their light environments, set at load; not yet really tried: run 5's in-play test was on a copy that had stopped
  following light changes).
- 7 November: the copies baked themselves (baker step L4) now reach these pairs. The editor's Build makes groups that
  break together in the map too, linked there ([EXP-20](experiments/EXP-20-growing-writer.md) run 7, the temple
  project). It passed: the pairs are lit, and they break together.

### F-57: A copy made in the map isn't in the tile data
**Verified** (EXP-20 run 4b: the copy gives cover, and the mission loads).
- Symptom: in EXP-20 run 3 the user's soldier could walk into the lamp post copied as a new actor of the bar. The
  move cursor stood on its base.
- Cause:
  - The tiles are baked into the map (F-04), and a copy made by `tools/bake/native_copy.py` is in none of them.
  - At load the battle rebuilds only what its `XComRebuildWorldDataVolume`s cover, plus radar arrays and Meld
    containers (`XGBattle.DoWorldDataRebuild`). The bar has no such volume.
  - Above the ground, the rebuild re-checks only tiles with baked low bits (F-29).
- Fix (`native_copy.add_tiles`, on by default):
  - Seed bit 0x1 on the tiles the copy crosses above the ground, plus a ring of one tile and one level above. The
    bake marks those too: the original post's neighbours carry direction bits toward it at every level, and the tile
    over its top has a bit of its own.
  - Add an `XComRebuildWorldDataVolume` over them, cloned from one of the map's trigger volumes and retyped through
    new imports.
  - The battle rebuilds it at load and after a saved game loads.
- Open: `tools/upk/seed_map.py`'s plan for the editor's spawned copies seeds only the tiles a copy's box crosses,
  not that ring. Whether those copies' neighbours miss direction bits above the ground hasn't been checked.

### F-58: A piece taken out of the map's actor list is still listed elsewhere
**Verified** harmless (EXP-20 run 8, 7 November: the pool table and its glass gone, their tiles open, and no ghost in
the cutaway or after a save and reload).
- What: since 7 November the editor's Build hides a piece by setting its slot in the Level's actor list to 0
  (`native_copy.hide_pieces`), as a level designer's delete does. But its export stays in the package, and other
  objects still list it: the building's floor caches (`Floors[].m_aCachedActors`, their `ResidentActor`) and a
  visibility group (`XComVisGroupData`). A Kismet sequence could too.
- Why it should be harmless: those references load the actor, but the level attaches, ticks and iterates only the
  actors in its list, and the floor code acts only through attached components (native-code notes, `ShowFloor`).
- Risk: something that attaches or shows it again (a visibility toggle, a Kismet action). Then it would stand
  without its tiles, as a ghost.
- Fix if the game shows it: take it out of those lists too, as `AffectedChildren` already is.

### F-59: Builds assumed what Bar and Temple Ship have
**Fixed** offline (7 November, all-maps support); a Build of another map is still to be played.
- What: the first Build on another map (URB_PoliceStation: a plain piece moved, one deleted, on a test server)
  failed twice in the copy-and-relight step:
  - a copy's tile-rebuild volume is cloned from the map's `TriggerVolume_0` (`native_copy.add_rebuild_volume`), and
    URB_PoliceStation has no trigger volume at all;
  - the relight refused to remove a piece that casts no shadow (`no shadow caster named ...`): the piece moved has
    `CastShadow` off, so neither it nor its copy is a caster.
- Also: 65 of LWR's 95 battle maps have several `DefaultMaps.ini` records (one per mission they serve), and 13 of
  those stream different landing intros on different records; the Build refused any map without exactly one record.
- Fix:
  - `native_copy.rebuild_template` takes `TriggerVolume_0` where the map has it, else the first plain, unrotated
    volume of the persistent level by class: a rebuild volume of the map's own, a trigger volume, then
    `XComNoSpawnVolume` (URB_PoliceStation's `XComNoSpawnVolume_11`), `GameCameraBlockingVolume` and
    `XComCursorVolume`. The clone is retyped as before; properties its new class lacks are the risk. Of LWR's 95
    battle maps, 69 have a trigger volume and 25 fall back (`XComNoSpawnVolume` 20, `XComCursorVolume` 3,
    `GameCameraBlockingVolume` 2); the multiplayer blank `CB2_MP_Blank` has none, so a copy there is refused.
  - `relight.Scene` takes a removed piece that casts no shadow as removing nothing; a name the map doesn't have is
    still refused.
  - the Build writes one record per mission, with an intro copy per distinct intro
    (`build.config_lines`, `Build.intro_copies`); the lab's test slot plays the map's abduction record
    (`deploy_fixture.slot_record`).
- To confirm in the game: a Build of a map without `TriggerVolume_0` whose copy blocks and gives cover (the rebuild
  volume works when cloned from another class).

### F-60: A ladder copy loses its way down when its top tile is rebuilt after its foot
**Verified** (EXP-22 run 1, 8 November: a moved and a quarter-turned ladder both give a route up, and again after
a save and reload; no route shows where the moved one stood; run 2 on CSmallScout_Farm the same, with a near
helper taken out of `patch_farm`'s copy). The down link itself isn't seen in the game: a soldier
going down drops off the roof's edge, ladder or not (the user's note), so it is left to the A* probe.
- What: a ladder made in the map (`native_copy.py`) climbs only through the links the battle's tile rebuild makes for
  it. The rebuild makes both from the foot tile, and a top tile rebuilt later empties the down link again. A copy's
  own rebuild volume adds its foot before its top whenever the ladder faces +X or +Y (X runs outer, Z inner), and a
  patch's hidden ladder beside a moved one (F-30's `patch_bar` helpers) keeps the old place climbable.
- Cause: the rebuild's work set is one set in first-added order (research/native/ladder-links.md, G5).
- Fix:
  - a rebuild volume of sphere radius 24 over the linked top tile alone, first among the volumes the Build adds
    (`native_copy.tile_volume`); the Build simulates the rebuild order on the built map and refuses a ladder whose
    top would come after its foot (`ladder_order`);
  - the patch's helper ladder is taken out of the variant's copy of the patch (`stream_copy.py`), which the variant
    streams in its place;
  - the compiler refuses a ladder whose foot, or top, has no floor (`ladder-climb`).
- Not covered yet: LWR's mutator queues its own tiles before the map's volumes and isn't simulated; a ladder
  facing -X or -Y (the rebuild puts its top first anyway).

### F-61: A copy is in no wall's fragment columns, and a hidden piece stays in them
**Verified** (EXP-23 run 1, 8 November: the user's checks, breaking the wall beside a door copy among them, "everything
works as expected"; `test_native_copy.test_a_door_copy_joins_its_walls_columns_and_its_floors_cutaway`).
- What: a fracturing wall lists, per fragment column, the pieces that go when that column breaks
  (`FragmentColumns(k).DestructibleCache`): a door's leaf and frame in 8 to 12 columns of their wall, fences and
  wrecks in a car glass's. A copy made in the map is in none, so breaking the wall around a copied door would leave
  the door standing; a hidden piece stays listed, so breaking its wall acts on a piece out of the level (a latent M1
  gap for hidden fences and signs).
- Cause: the bake makes the lists, and no rule of the columns' own reproduces them (over Bar's 289 listed pieces, a
  padded box of the piece lists exactly the same columns for at most 42).
- Fix (`native_copy.edit_columns`): every hidden piece leaves every column; a door's copy takes its original's
  listing carried by its move: each listing column, moved with the copy, lists it in every column of a wall still in
  the map that it covers by half, with the original's MinZ.

### F-62: Copies made in the map are in no building floor's cutaway
**Verified** (EXP-23, 8 November: run 1, the door copies hide and cut down with the bar's other doors; run 3, on
URB_ResearchOutpost's floor 2, a copy from another building's ground floor among them; the same test).
- What: as F-31 for the patch's copies, a copy made in the map is in no floor's `m_aCachedActors`, so it doesn't hide
  or cut down with its floor; the compiler warned of it (`building-floor`).
- Fix (`native_copy.edit_floor_caches`): every copy whose original is in a floor's cutaway gets its original's entry
  in the floor whose floor volumes overlap the copy's box most (EXP-23 run 2: Police Station's floor volumes end on
  its back wall's line, where a door's centre lies on their face), as far above it as the original's listing is above the
  original's floor (CutdownFloor moved by as many floors); a copy standing in no building floor gets none, unless
  its original stands in none either (a ladder on a shed's outer wall, CSmallScout_Farm): then it keeps the
  original's listing. The copy
  has its original's floor component and `bCutoutMask` (cloned with it), which F-31 found the cutaway works through.
  The compiler's warning now says so: it can't tell which floor, since the export holds no floor volume boxes.

### F-63: A piece the map's Kismet names, moved or deleted, leaves its script acting on the hidden original
**Fixed** (8 November, refused by the compiler; `test_compiler.test_a_piece_the_maps_kismet_names_is_copied_not_moved_or_deleted`,
`test_links.test_bars_kismet_names_its_grounded_skyranger_and_drop_zone`).
- What: a map's Kismet names some placed pieces: Bar's and Police Station's landing hides the grounded Skyranger and
  its drop zone (`XComLevelActor_138` and `_6` on Bar) with a `SeqAct_ToggleHidden`. Both are scenery, so the
  editor built moves and deletes of them: the script then toggles the hidden original, and a moved copy stays drawn.
- Fix: export 15 records what of the package's Kismet names each piece (`referencedBy`: the op and link using the
  variable that holds it, or the sequence object and property); the compiler refuses moving or deleting such a piece
  (`mission-linked`) and allows copying it; the inspector marks it (Mission script). Since 13 November 2026 a move or
  delete builds, with the warning (map buildings plan, step E2b). On the five maps read (Bar,
  Police Station, the outpost, the farm, the forest trench) the Kismet names no ladder, door or car.

### F-64: A copied car's glass keeps its original's fragment columns where the original stands
**Verified** (EXP-24 run 1, 8 November: the user's check of a moved sedan and a turned copy of Bar's police car,
"looks good confirmed", with no `CachedFrag` or `REBUILD PATHING!` lines in the log;
`test_native_copy.test_a_car_copys_glass_columns_turn_and_move_with_it`,
`test_a_car_copys_glass_drops_column_entries_of_other_pieces`).
- What: a car's fractured glass lists, per fragment column, a box and the pieces that go when that column breaks
  (the body, a police car's parts, on some maps a fence or a neighbouring wreck: Police Station's car 1071 lists
  `XComDestructibleActor_1070`), and a broken column adds a fire spot (plan 7.2). Cloned with its car, the glass keeps
  those boxes at the original's place, and its entries for pieces outside the car still name the pieces round the
  original: breaking the copy's glass would break or set fire to things where the original stands.
- Fix (`native_copy.move_columns`, plan 7.2 and G8's glass half): each column's box carried with the copy's move (a
  quarter turn keeps it axis aligned), every MinZ raised by the storey shift, the fragment indices kept, the entries
  of the assembly's own members kept (the clone points them at the copies) and the others dropped, so a copy's glass
  doesn't break a fence at its new place (a known limit).

### F-65: A van's copy has no building of its own, and a moved or deleted van leaves its building behind
**Verified** (EXP-24 run 3, 8 November: soldiers walk into a turned delivery van copy's and a moved short van's cargo
areas, the copy's roof cuts away over a soldier inside, also after a reload, "looks good to me"; run 4 on Police
Station, a delivery van copied a quarter turn round, one moved and one deleted, passed the same day on a quick check;
`test_native_copy.test_a_van_copy_takes_its_building_and_floor_volumes_along`,
`test_a_deleted_vans_building_leaves_the_level_with_it`).
- What: a van (Bar's moving vans and delivery van, Police Station's delivery vans) is a car with an
  `XComBuildingVolume` and two `XComFloorVolume`s of its own (floor 0 its cargo area, floor 1 its roof), which list its
  parts, so its roof cuts away over a soldier inside. They have no mesh, so the export lists no object for them and the
  compiler's assembly is the parts alone: copying the parts gave a van with no cutaway, and moving or deleting one left
  its building and floor volumes where it stood, listing hidden parts.
- Fix (plan section 7.6): `native_copy.van_buildings` finds the van's building (more than half of its listed
  residents are the van's parts, as the compiler tells a van); it and its floor volumes are cloned with the parts,
  carried by their move (`moved_pose`: a quarter turn turns them); the copy keeps only the van's own residents (pieces
  under the original stay out) and its visibility groups are emptied (`edit_van_building`); a moved or deleted van's
  building and floor volumes leave the level's actor list (`hide_van_buildings`). The compiler gives a van's parts no
  `building-floor` note.
- The rebuild makes the copy's cargo floor into floor tiles, as the bake made the original's (F-47's question, for
  copies made in the map: they keep the saved properties script copies lacked). A soldier on a copy's roof wasn't
  looked at.

### F-66: Street Hurricane's moving vans climb by patch helpers, and their ladders aren't part of the van
**Open** (8 November, offline, EXP-25 run 6's planning). Not a bug in a copy yet: the compiler refuses the copy.
- What: URB_StreetHurricane_Terror's two moving vans (`PRE` moving van, 14 parts each, cabs `XComDestructibleActor_27`
  and `_230`) each have two `LadderVehicleA_256` ladders up their back (`XComLadder_1` to `_4`). The ladders are their
  own assemblies, not the van's (the compiler joins a van from its prefab's parts, and the ladders aren't in it). The
  map's floor data has no floor at their tops (the van's roof), so the climb comes from `patch_streethurricane`'s 4
  exact helpers (plan 3.6). A copy of a van with its ladders, even at the van's own place, fails the compiler's end
  check (`ladder-climb`: "its top tile ... has no floor in the map").
- So on that map a van copy has no ladders, and a moved van leaves its ladders standing (they would have to be moved
  with it by hand; their helpers then go with them as hides).
- Next, if wanted: join a van's ladders to its assembly where they stand against it, and let the compiler accept a
  ladder whose top is on the assembly's own roof, if the rebuild makes the copy's roof floor tiles (EXP-24 run 3
  showed it does for cargo floors; roofs weren't looked at). EXP-25 run 6 copies a sedan instead.

### F-67: A rebuild volume was cloned from a volume with no brush
**Fixed** (8 November, offline; `test_native_copy.RebuildTemplateBrush.test_a_volume_with_no_brush_is_passed_over`).
- What: EXP-25 run 4's first build on URB_Demolition_EWI failed at its first copy: `GameCameraBlockingVolume_0 has
  no brush`. The map has no trigger volume, so `rebuild_template` fell back by class (F-59) to its camera blocking
  volumes, which are plain volumes but have no brush model (`Brush` is none on the actor and its component), and the
  rebuild volume's size is its template's brush scaled.
- Fix: `rebuild_template` takes only a volume with a brush model; on Demolition that is `XComCursorVolume_0`.

### F-69: A wall's fragment columns also list its neighbours' columns, and a wall's copy keeps all its listings
**Verified** in the main (EXP-28 run 1, 9 November: the user's run of a wall copied with its doors, a counter section
moved and a wall deleted, "all seemed ok"; the log shows a blast on the wall copy taking its door copy and frame, and
a save and reload finding the broken copy by name). Not looked at: a wall's copy against other walls, a storey move.
([EXP-28](experiments/EXP-28-fracturing-physics.md);
`test_native_copy.test_a_wall_copy_takes_its_columns_and_the_doors_copied_with_it`,
`test_a_hidden_wall_leaves_its_neighbours_columns_and_a_door_copy_joins_a_walls_copy`). Found when fracturing pieces
of their own (walls, storey floors, roof slabs, a bar's counter) were switched on for the Build.
- What: each of a fracturing piece's `FragmentColumns` saves three lists: `FragCache` (its own fragments, by index),
  `DestructibleCache` (the pieces that go when the column breaks, F-61) and `FracActorCache` (`FracActor`,
  `ColumnIndex`: columns of other fracturing pieces beside it). Bar's 60 fracturing pieces have 1,037 columns and
  2,969 such neighbour listings; a car's glass has none, so the glass's recipe (F-64) never met them.
  - A clone of a wall keeps every listing: breaking a column of the copy would act on the pictures, shelves and
    doors on the original and on the original's neighbours' columns, where the original stands.
  - A hidden wall stays in its neighbours' `FracActorCache`, as a hidden piece stayed in `DestructibleCache` (F-61).
- No rule of the boxes reproduces the neighbour lists: every listed pair of columns touches or overlaps, but 663
  pairs of columns of different pieces less than half a unit apart aren't listed (44 of them overlap on all three
  axes), and 135 listings aren't mutual. So the lists are carried, not made anew.
  - **Rule found** (18 November 2026, the custom geometry plan's M3 audit,
    [frac-neighbours.md](native/frac-neighbours.md), [wall-joints.py](evidence/wall-joints.py)): column X of piece A
    lists column n of piece B when X's box touches or overlaps B_n's box cut to B's own vertex box grown by one unit
    (closed boxes). It gives the saved list exactly for 61,805 of 62,460 columns over 151 maps (601 listings missed,
    550 added of 131,507, between a few pieces per map that look moved after the lists were made); exact on URB_Bar
    (1,037 of 1,037). Only B's box is cut, so a top-storey column reaching above its piece is listed one way: the
    135. Columns lie on the piece's own grid (96 x 96 x 192 from its vertices' lowest corner less one unit).
  - What a listing does (the natives): a damaged column hands the same damage, up to the same height, to each
    listed column (`TakeCollateralDamage` -> `DamageColumn(..., false)`), one step, no further cascade.
- Fix (`native_copy.move_columns`, for every fracturing copy now, not only a car's glass; `edit_columns`):
  - a copy's `DestructibleCache` and `FracActorCache` keep the entries of its own assembly and of pieces copied in
    the same build by the same rigid move (`same_move`: a wall's door, the wall beside it), now naming those copies;
    the rest are dropped;
  - every hidden fracturing piece leaves every `FracActorCache`;
  - a door's copy joins the columns of a wall's copy too (the copies' columns are destinations), once: a column
    that lists it already is left alone. A hidden wall's listing still carries its door (a door moved with its wall,
    or to another).
- Kept to the grid: a fracturing piece builds only moved by whole tiles and storeys and turned by quarter turns
  (`compiler.single_grid_rule`, the page's recipe snap), since the columns are saved one to a tile and are carried
  rigidly. Other poses need the columns made anew.
- Known limits: a wall's copy placed against other walls lists none of them and is listed by none, so whatever the
  game does through `FracActorCache` (not worked out) doesn't pass between them; a piece hung on a wall's copy
  afterwards (not copied with it) isn't in its columns.
- Seen in the game (EXP-28 run 1): a wall copy's cover and sight blocking, breaking it, its doors going with it, a
  moved counter section, a deleted wall (its tiles free after the rebuild, read from the save), a save and reload
  with a broken copy. A storey floor's copy carries floor tiles where it has standing room (F-71).
- Also fixed (9 November, offline; `test_native_copy.test_a_storey_floor_copy_moved_up_takes_its_fragment_heights_along`):
  a fractured mesh component saves its fragments' lowest and highest world height (`FragmentBoundsMinZ`,
  `FragmentBoundsMaxZ`: Bar's inner wall, standing at z 16, saves -0.04 and 400; its roof slab at z 400 saves 398 and
  402). A copy moved up or down kept its original's; `native_copy.shift_fragment_heights` moves them with it. What
  the game reads them for wasn't worked out, and no copy moved by a storey has been played.

### F-70: Bar's corpses are physics props tagged `deleteme`; the game shows them
**Open** in part (EXP-28 run 1, 9 November: the map's corpses show in the game as green fogged bodies, two of them in
the user's screenshot, and the log checks both copies at each load; the user's "all seemed ok" covers the copied,
moved and deleted corpses without detail. Before the run, offline:)
- What: URB_Bar's 14 physics props (`KAsset`, the `CivFlat*` corpses of `CHH_FoggedMaleCivs.Rigidbodies`) all carry
  the tag `deleteme`. The game has a Kismet action that takes every actor with a tag (`SeqAct_RemoveActor`,
  XComGame: a `KAsset` is destroyed with `ForceDestroy`, anything else hidden), but URB_Bar's own Kismet has no such
  action, and no script read so far names the tag. F-44's note had Bar's own corpses "most likely hidden all along";
  what removes them, if anything does, wasn't found.
- So what a physics prop's copy does in the game is open on two counts: whether Bar's corpses show at all (a copy
  keeps the tag, so it shares their fate), and, where one shows, whether the clone rests at its pose and survives a
  save. The Build makes the clone (its skeletal mesh component, its physics asset and a light environment of its
  own; `test_native_copy.test_a_physics_prop_is_cloned_with_its_skeletal_mesh`); EXP-28 run 1 looks for the corpses
  at their marks and reads the log.
- Still open: what the tag is for, and a physics prop that isn't a corpse lying flat (does a clone rest at a pose
  given to it, and after a save).

### F-71: A floor's copy gets floor only on tiles with standing room over them
**Verified** (EXP-28 run 1, 9 November: the user couldn't put a soldier on a storey floor strip's copy; read from the
run's save with `tools/lab/save_tiles.py`).
- What: Bar's upstairs floor strip `XComFracLevelActor_17` (10 tiles by 1, top at 210) was copied 2 tiles north, over
  the front room, where the map has no floor at that height. After the game's tile rebuild, 4 of its 10 tiles have
  the floor bit (`0x2000`: tiles (19..22, 23, 3)) and 6 don't ((13..18, 23, 3)).
- Cause: over those six the level above, (13..18, 23, 4), is occupied in the map's own bake (`0x8000`): the
  ceiling's air duct (`BarCeilingAirDuctA`, drawn from z 342, 132 above the strip) hangs there. Over the other four
  only the ceiling's I-beams (from z 362, 152 above) and its lights are overhead. The rebuild gives no floor to a
  tile a soldier can't stand on.
- So: the rebuild does make floor from a fracturing floor's copy (as from a plain one, EXP-27), tile by tile. A
  floor copy under something hanging lower than about 150 units over it stays without floor there. Whether F-47
  (a script copy of a floor inside EXP-08's block, 151 and then 188 units under its ceiling) was this too can't be
  told from its notes: its run 3b had 188 units and still no floor.
- Not done: the editor doesn't warn of it. The saved tiles are in the export (`tactical`), so a floor copy's tiles
  could be checked against the occupied tiles over them.

## Starting a battle without a campaign (EXP-29)

### F-72: The game starts straight in a battle on a map, given `-EXEC=` and `open`
**Verified** (EXP-29 runs 1, 6 and 7, 9 November, in the lab copy through Steam).
- What: with `-EXEC=<file>` on its command line the game runs the file's console commands as it starts (it reads it
  from `XEW\Binaries`), and `open <Map>` in it loads the map as a battle: the Skyranger lands and turn 1 begins, with
  no campaign started and no map record changed. About half a minute from the launcher's click.
- Through Steam: `steam.exe -applaunch 200510 -EXEC=<file>` needs no launch option. Steam hands the argument to the
  game's stub, the launcher hands it to `XComEW.exe` (`-FROMLAUNCHER -EXEC=… -LANGUAGE=INT`). The launcher still asks
  which game.
- Which record: the first in `DefaultMaps.ini` whose Name is the map's. Its streams are streamed (the patch, the
  landing intro) and LWR's landing zones are looked up by the map's name, so a variant plays from a record of its own
  that is out of rotation (`bInRotation=False`), and a map of the game's needs nothing.
- The battle: `XComTacticalGame.m_bLoadingFromShell` is true when the URL doesn't say `LoadingFromStrategy`, and
  `XComTacticalGRI.InitBattle` then builds the battle from the profile's developer squad, with aliens of the game's
  choosing (`XGBattleDesc.Generate`). It is Firaxis's own path, and LWR's mutators, pods, meld and landing code run
  in it. The squad needs F-74.
- The map as the command line's first word (the engine adds `?LoadingFromShell=1?NoLoadingScreen=1`) wasn't tried:
  the launcher puts `-FROMLAUNCHER` first, so it would need a launch option.
- Used by: the editor's Play in game (`tools/viewer/gamelaunch.py`, `play.py`).
- Saving in it does not work (F-89).
- Not known: a whole battle and its end, whether the profile is ever written (it is the game's default
  one on this path), missions with a script of their own, plain Enemy Within.

### F-73: The console's `set` saves the class's config, layout and all
**Verified** (EXP-29 runs 2 to 6, 9 November).
- What: `set <Class> <Property> <Value>`, `get` and `getall` work in the shipped game. After a `set` the engine
  saves the class's config (its default object's `SaveConfig`), whatever property was set: `set XComContentManager
  bAllowJITLoad True` wrote the line into `XComContent.ini` and rewrote the content manager's whole section there in
  the engine's own layout; `set XComOnlineProfileSettings m_aSoldiers …`, a property that isn't config, wrote the
  class's `LoadoutSlots` out.
- So: a play's commands change the user's `XComContent.ini` for good unless it is put back. The editor keeps the file
  aside before a play and puts it back once the game has closed (`installs.backup_config`, `restore_config`; EXP-29
  run 7: the same hash as before).
- A `set` reaches the class's default object and every object of the class alive then, not one made later from
  values read earlier: the squad is built when the game starts, so setting `LoadoutSlots` in the file changes nothing
  (run 2).

### F-74: The squad of a battle started from the console has to be loaded and written by the commands
**Verified** (EXP-29 runs 1, 3, 4, 6 and 7, 9 November).
- What: started with `open` alone, the squad had no bodies and half of it no weapons (run 1).
  - Bodies: nothing on this path asks for the soldiers' content; the base does in a campaign, and Firaxis's shell did
    before its `open`. `XGBattle`'s own load for a restart (a URL with "restart" in it) comes before the battle's
    description exists (run 2).
  - Weapons: the developer squad (`XComOnlineProfileSettings.LoadoutSlots`) is two MEC troopers, a heavy and a
    support, and the MECs' gear comes out empty under Long War.
- Fix: two commands before `open`.
  - `set XComContentManager bAllowJITLoad True`: the content manager loads what is asked for and missing (`WARNING:
    JIT Loading Soldier_MaleKevlar.ARC_MaleKevlar`, and the weapons).
  - `set XComOnlineProfileSettings m_aSoldiers (…)`: the squad itself, in the text `getall` prints it in, six
    soldiers in a line of some 4,800 characters. Items are numbers in `XGGameData.EItemType`, which Long War
    renumbers (LWR: kevlar 59, carapace 60, frag grenade 81).
- Limit: the numbers are LWR's. Long War's are taken to be the same; for plain Enemy Within the editor sets no squad
  and the game's own plays (not tried).

### F-75: Long War's voice picker can run away, and the game then stops as it starts
**Accepted** (EXP-29 run 5, 9 November: the lab game stopped at start-up; avoided, not fixed).
- What: `Runaway loop detected (over 1000000 iterations)` in `XComContentManager.GetPossibleVoices`, called from
  `XGCharacterGenerator.CreateTSoldier` while the shell made the developer squad.
- Cause: the function keeps its loop counter in the first element of the list it fills, and removes voices from that
  list by value (`RemoveItem`); a voice whose number is the counter's takes the counter out. Which soldier meets it
  depends on its random country. The game's own four `LoadoutSlots` make the same four soldiers at every start and
  never meet it; six slots saved into `XComContent.ini` (F-73) did, at every start.
- So: no soldier is generated for a play (the squad is written out, F-74), and `LoadoutSlots` is never set. A game
  that stops this way starts again once `XComContent.ini` is deleted (the game makes it afresh).

### F-76: A variant of an alien base never leaves its intro: the entrance picks its scene by map name
**Verified** (10 November 2026: the user played aba1_test's rebuild with Play in game, "tested works"). Found by the user: Play in game on a quick build of
AlienBase01 (project aba1_test, `AlienBase01_Aba1Tes_da5a`) loaded the battle, then the camera stayed in a cutscene
that never started.
- The log: the map, its streams, the aliens and the squad all loaded; the two working plays before it (a Temple Ship
  variant, the EXP-26 Bar) log `Applying property m_bTacticalIntroDone for object XGBattle_SPAssault_0` 7 s and 22 s
  in, this one never did in its 30 s.
- Cause: the alien bases' intro, `CIN_TP05A_EnteringAlienBase` (streamed by both alien base records), starts on
  `SeqEvent_OnTacticalIntro`: cinematic mode on, `SetFOW 0`, then `SeqCond_SwitchString_1` ("Which alien base map are
  we in?") on the event's `MapName`, with cases `AlienBase01`, `AlienBase02` and `Default`. Only the two map cases lead
  on (a `SeqAct_SetLocation` for the squad's rig, then the matinee, whose end sets the battle's intro done and turns
  cinematic mode off). A variant's name matches neither, so nothing follows and cinematic mode stays on: F-45's cause
  in another package. Read with `tools/upk/kismet_links.py`.
- Scope: of every `CIN_` package LWR's records stream, only three switch on a map name: the two landings (F-45) and
  this one. Temple Ship's arrival (`CIN_TP12A_ArriveTempleShip`) has no switch, which is why its variants played.
  The exe doesn't name `CIN_TP05A_EnteringAlienBase` (it names the landings and `CIN_TP12A_ArriveTempleShip`); the
  script names it only in its built-in copy of the maps list.
- Fix: the Build's intro copies take it too (`INTROS` in `tools/editor/build.py` and `tools/bake/intro_copy.py`):
  the variant streams `CIN_TP05A_EnteringAlienBase_<variant>`, whose switch names the variant in the base map's case.
  `intro_copy.py` needed no other change (the copy keeps every export; entry 0 of 3 renamed).
- The log's `AActor::SetBase : Bone (Cabin) not found on SkeletalMeshActor_0` (the squad seated on the entrance's
  rig, which has no Skyranger cabin) is not the cause, as far as is known; whether it shows in the game's own alien
  base missions wasn't checked.
- Play in game still writes a variant's record as an abduction (`installs.plan_record`), as for every kind of map;
  the user is fine with that for map testing.

### F-77: The campaign's first map had no volume a rebuild volume could be cloned from
**Fixed** (10 November 2026, offline: `test_native_copy.RebuildTemplateIntro`, and the EXP-30 project built; not
played yet: [EXP-30](experiments/EXP-30-intro-map.md)). Found by the first Build on Act1_IntroLevel, once the map
browser listed it (testers asked for it, taking it for the campaign's first mission): a project deleting the police car
stopped in `native_copy.py` with "the map has no plain, unrotated volume with a brush to clone a rebuild volume from".
- Cause: a hidden or copied piece gets an `XComRebuildWorldDataVolume` cloned from a volume of the map
  (`rebuild_template`: `TriggerVolume_0`, else F-59's classes, each with a brush model, F-67). Act1_IntroLevel has no
  trigger, no-spawn or cursor volume, and its four camera blocking volumes have no brush.
- Fix: `LightmassImportanceVolume` is the last fallback class (`REBUILD_FALLBACKS`). Its export saves only what every
  brushed volume saves (`Brush`, `BrushComponent`, `CollisionComponent`, `Location`, `Tag`, `SavedSelections`,
  `bDirtyComponents`), none of its own; on the intro map that is `LightmassImportanceVolume_1`.
- EXP-30 run 2 (the user's play of that project): the car and its glass are gone and the battle's world data rebuild
  ran. Whether a soldier stands where the car stood isn't shown: those tiles are the last rows of the map's 19-row
  grid, at the playable area's edge.

### F-78: The tutorial's map, opened with no record, crashed the game
**Fixed** (10 November 2026, offline: `test_play.test_the_tutorial_map_alone_plays_with_a_copy_of_its_commented_out_record`;
not played yet: [EXP-30](experiments/EXP-30-intro-map.md) run 3). Found by the user in EXP-30 run 1: Play in game on
Act1_IntroLevel alone "opened for 1s but then the game crashed right away".
- What: the battle loaded (squad, four sectoid pods), then `Critical error` 8 s after `LoadMap`, at XComEW.exe
  0xafca98. Play in game installs nothing for a map alone, and LWR comments out both of this map's records, so the
  game found no record (`GetCurrentMapMetaData`) and streamed no intro.
- Cause, as far as the runs show: the missing record. The project of run 2, with a live copy of the abduction record,
  played (the intro streamed and ended at once), with the same tutorial Kismet in the map.
- Fix: `installs.install_map_record`: before a play of a map alone whose records the install comments out
  (`maplist.SWITCHED_OFF`), a live copy of its abduction record goes in after the commented-out one, out of rotation,
  with a comment line, kept in the install's ledger like a variant's record; the next play replaces it and Remove from
  game takes it out. While it is in, a game that opens Act1_IntroLevel by name (the tutorial) finds that record.

### F-79: A cover block crashed the game as the map loaded: its component's native data was the UDK's, not EW's
**Verified** (10 November 2026: the user played the rebuild, [EXP-31](experiments/EXP-31-cover-blocks.md) run 1, and
the map loaded; offline: `test_cover_blocks.BuiltInTheMap.test_the_mesh_components_native_data_is_the_maps_own`).
Found by the user: a
project on CSmallScout_Farm with a cover block stopped the game before the map finished loading,
`Bad import index 65535/334` in `Launch.log`; the same project without the block had played.
- Cause: the recipe gave the block's `StaticMeshComponent` the native data LWR's hidden helpers save (an empty
  LODData). `patch_policestation.upk` is UDK-cooked (licensee 0); the game's maps (licensee 64) save two mesh-swap LOD
  records and their two meshes after the LODData, 46 bytes for a component with no LOD. The game read 42 bytes past
  the component, into the next export, and took a reference out of them.
- Fix: the recipe's component saves the 46 bytes. The StaticMesh export saves the same fields in both kinds of
  package, and XComLevelActor and XComFloorComponent save no native data in either.
- Lesson: an export modelled on a UDK-cooked package (licensee 0) must be checked against the destination map's own
  exports of its class, not only against the UDK package's.

### F-80: Cover blocks gave no cover and let units through: the rebuild skips a level actor whose mesh has no BodySetup
**Verified** on level ground (10 November 2026, [EXP-31](experiments/EXP-31-cover-blocks.md) run 3: the user played
the rebuild, "works now", the blocks stop a soldier and give cover; offline:
`test_cover_blocks.BuiltInTheMap.test_each_box_has_a_body_setup_as_the_maps_own` and `GameBoxHull`). On a ramp the
block still gave no cover: F-81, the game's own rule.
Found by the user in EXP-31 run 1, once the map loaded (F-79): high blocks over a small rock (half cover) and over a
rock on a ramp changed nothing, and a block in the open neither stopped a soldier nor gave cover. Run 2, with the
first fix, was the same.
- Cause (read from the native code: [native code notes](native-code-notes.md), "How the rebuild decides a tile is
  occupied"): the tile rebuild's occupancy test (`0xA58810`) skips an XComLevelActor whose StaticMesh has no
  `BodySetup` before it tests any collision (`0xA58D56`), and the component's checks (flags `0x860D3` and `0x860C0`,
  not complex) use the mesh's simple collision while its `UseSimple...Collision` flags are on, finding nothing when
  there is no BodySetup. The box mesh the Build wrote had none: the writer had taken the triangles to be the
  fallback. LWR's `CoverPatch` boxes, the game's `FX_Utilities` boxes and nearly every mesh of the game's maps carry an
  `RB_BodySetup` with a convex hull in `AggGeom` (none with pre-cooked data).
- First fix, not enough (run 2): the mesh saved `UseSimpleBoxCollision` and `UseSimpleLineCollision` off, as the
  map's hay bales do, so the checks would use the triangles. The occupancy test still wants the BodySetup.
- Fix: each box mesh gets an `RB_BodySetup` of its own (`cover_blocks.body_setup_properties`), in its `BodySetup`
  property and native field: the version every map's RB_BodySetups save, one convex element of the box's eight corners
  laid out as the game's `FX_Utilities.Box_96x96x96` has its hull (a 96-unit box's is that hull float for float), no
  pre-cooked data; the flags back at their defaults. The meshes' half-extents (48 or more) pass the test's size rule.
- Hidden actors count: the collision hash's walk keeps primitives by their bounding box and tests no hidden flag
  (read after run 3), and the hidden blocks worked in run 3.

### F-81: A soldier on a sloped floor tile gets no cover, from the game's pieces or a cover block
**Explained: the game's own rule** (10 November 2026; [EXP-31](experiments/EXP-31-cover-blocks.md) run 3). Found by the
user: a high cover block over a rock on CSmallScout_Farm's ramp (by the UFO) gave no cover, at its first height and
again sunk into the ground, while blocks on level ground did; the user had noticed the game's own rock there gives
little cover too.
- Cause: the tile rebuild's floor-detail step (`0xA0A2B0`, where a floor tile's details are worked out) runs only on
  floor tiles without the sloped bit `0x4000`, which the floor trace sets where the floor is steeper than about 10°
  ([native code notes](native-code-notes.md), "How the rebuild decides a tile is occupied"). The ramp's tiles there
  are sloped (level 3, row y 4). The baked data agrees across maps: 3 to 5% of sloped floor tiles have cover direction
  bits (on the farm all at level 0 by the map's edge, themselves occupied) against 26 to 37% of flat ones, and none
  where units walk on the farm's ramps.
- Not the block's pivot: the octree walk that picks the actors near a tile keeps them by their bounding box (checked
  in the code after a guess that it used the actor's location, which a block's corner pivot would have missed).
- What a block can still do there: stop movement onto its own tiles (the occupancy test doesn't care about slope),
  and give cover to soldiers on flat tiles beside it. A way round worth trying later: an invisible flat floor plate
  over a sloped tile, so the floor trace finds a flat floor and the step runs (units would stand a little above the
  slope).
- The way round works: in [EXP-32](experiments/EXP-32-invisible-floor.md) run 1 soldiers on invisible floors over the
  ramp stood on a flat floor and got cover (with F-82 as a side effect).

### F-82: An invisible floor gave the tile below it half cover, like a step
**Verified** (10 November 2026, [EXP-32](experiments/EXP-32-invisible-floor.md) run 2: with the fix the tile below a
floor got no cover from it, and soldiers on the floors kept their cover). Found by the user in
[EXP-32](experiments/EXP-32-invisible-floor.md) run 1: invisible floors over CSmallScout_Farm's ramp worked, but the
tile downhill of a floor got half cover from it.
- Cause (native code, medium confidence; [native code notes](native-code-notes.md), "Where a tile's floor and cover
  are looked for"): the tile rebuild gives a flat floor tile cover where a sideways trace from 52 over its floor, 124
  units long, hits an actor with the cover interface that isn't ignored for cover, and half cover when that actor's top
  is a valid destination. A floor plate is both.
- No height avoids it there. The floor trace is one line through the tile's centre, so a plate is the tile's floor
  only with its top over the ground at the centre. The ramp rises about 50 units a tile, so even the lowest plate
  that works stands about 50 over the floor of the tile below, in that trace's path (52 over). A smaller plate wouldn't
  help either: the trace reaches past the plate tile's centre, which the plate must cover.
- Fix: a floor's actors save `bIgnoreForCover` True, as the game's own hidden ladder helpers do. The cover trace skips
  such an actor; the floor trace and the occupancy test don't read the flag.
- Checked in the game in EXP-32 run 2 (above).

### F-83: An invisible floor snapped 1 unit over the drawn ground wasn't found: the game traces the collision
**Verified** (10 November 2026, [EXP-32](experiments/EXP-32-invisible-floor.md) run 3: floors the editor fitted 1 unit
over the collision were found, and soldiers on them got cover; offline: `test_collision`, `check_cover` in the
browser smoke test). Found by
the user in [EXP-32](experiments/EXP-32-invisible-floor.md) run 2: three floors the editor had put 1 unit over
CSmallScout_Farm's ramp gave no cover; raised a few units by hand, they did.
- Cause: the floor trace meets a static mesh's simple collision (its BodySetup's convex hulls and boxes) when the mesh
  uses simple line collision, as cooked meshes do unless they save `UseSimpleLineCollision` False ([native code
  notes](native-code-notes.md), "Simple or per-triangle collision"). The ramp (`TornEarth.Meshes.SmallscoutRamps`) has
  ten hulls, and where the drawn ramp dips they stand over it: at the floors' tile centres the hulls' top is at 86.15,
  49.64 and 86.15 against the drawn 80.9, 48.0 and 83.6. A floor 1 unit over the drawn ramp was inside the hull, so the
  trace met the hull (a slope of normal z 0.935, under 0.9848: a sloped tile, no cover, F-81). The user's raised floors
  stood 1.1, 4.5 and 2.2 over the hulls, and all three worked.
- Fix: the editor reads the ground of an invisible floor from the game's collision: the server serves each mesh's
  line-check collision from the map's package (`GET /maps/<id>/collision.json`, `tools/viewer/collision.py`), and the
  page measures against it, one solid at a time, the way the floor trace takes it (a top looking up more than 0.7; a
  line starting inside a solid gets the solid's top). Placing a floor, its readout and Fit to ground all use it.
- Box elements' matrices are four planes saved W first, like every Plane in these packages; read in the usual order,
  the farm's backdrop boxes stood on end (found by the smoke test, fixed before use).
- Checked in the game in EXP-32 run 3 (above).

### F-84: A copy of `XComEW.exe` under the launcher's name quits when Steam's stub starts it; a stand-in launcher works
**Verified** (11 November 2026, the lab copy; no EXP file, the runs are below).
- What: the usual advice for skipping the launcher (keep `XEW\Binaries\Win32\XCOMLauncher.exe` aside and put a copy
  of `XComEW.exe` there under its name) did not work here. Started by the game's Steam stub
  (`Binaries\Win32\XComGame.exe`, which runs `XCOMLauncher.exe <the arguments>`), the copy ended within 200 ms, exit
  code 1 and no `Launch.log`: twice through Steam (`steam://rungameid/200510`) and once with the stub started by
  hand.
- The same file started by hand (`SteamAppId` and `SteamGameId` set to 200510) reached the main menu, with and
  without `-FROMLAUNCHER`, from its own folder, the game's root and `Binaries\Win32`. So neither the name, the
  arguments nor the folder alone ends it; what the stub does differently wasn't found. Without the two variables a
  start by hand logs up to the memory line and ends (`appRequestExit(1)`).
- It is reported to work on other machines (a user's Play in game went straight into the game with it). There the
  game runs as `XCOMLauncher.exe`, a name the editor's `installs.game_running` doesn't look for: it would not see
  the game running or closing (F-73's config put back too early, installs allowed while it runs). Not handled.
- Fix here: a stand-in launcher, `tools/lab/XComLauncherSkip.cs` (4.6 KB, built with `csc`), that starts the
  `XComEW.exe` beside it with `-FROMLAUNCHER` and its own arguments, as the real launcher does after the click, with
  no `-LANGUAGE=`. Through Steam in the lab copy: stub, stand-in, `XComEW.exe -FROMLAUNCHER -nostartupmovies
  -nohomedir -forcelogflush`, `LoadMap: XComShell`, `Initial startup: 3.14s`, closed normally (exit 0). The game runs
  as `XComEW.exe`, so nothing in the tools changes.
- In place in the lab copy and the LWR install, the real launcher kept beside it as `XCOMLauncher_backup.exe`. Undo:
  delete the stand-in and rename the backup back; Steam's file check also restores the launcher.
- **Play in game through the stand-in stopped at the main menu** (the user's play of farm+, 11 November 02:04, the
  lab copy). Steam's stub hands each argument on in quotes, the stand-in passed its command line on as it came, and
  the game reads a quoted `-EXEC` with the closing quote in the file's name. `Launch.log`: `Command line:
  -FROMLAUNCHER "-EXEC=XComMapWorkshop-play.txt" -nostartupmovies -nohomedir -forcelogflush`, then `ExecWarning:
  Can't find file '..\..\Binaries\XComMapWorkshop-play.txt"'`. So the play's commands never ran. Fixed: the stand-in
  hands the arguments on without their quotes (one with a space in it keeps them), as the real launcher must, since
  EXP-29's plays through it worked. Checked offline only, with a dummy `XComEW.exe` that writes its command line:
  `-FROMLAUNCHER -EXEC=XComMapWorkshop-play.txt -nostartupmovies -nohomedir "-LOG=my file.log"`. Rebuilt and put in
  both installs. Not played yet.
- The same play showed the game in a borderless window 2560 by 1317 on a 2560 by 1440 screen, the desktop showing
  under it: the lab copy's `XComEngine.ini` (saved 00:42 that night, during the launcher runs) had `ResY=1317`; six
  of its logs that night start at that height. What saved it wasn't found. Set back to 1440 by hand (a copy of the
  file from before beside it, `XComEngine.ini.before-resy-fix`).
- Not tried: the LWR
  install itself (same files, parked), a language other than the game's own setting. The LWR install now differs from
  the 3 November baseline manifest in these two files (`steam_launch_test.ps1`'s last report will say so).

### F-105: Which record a battle gets, and what a console `open` leaves out
**Open** (14 November 2026: read from the exe copy and the scripts for the
mission types plan, not seen in a run;
[native-code-notes.md](native-code-notes.md) "The map's record" has the addresses). A reference fact, not a defect.
- **One stored record.** `GetCurrentMapMetaData` returns the record the game has stored whenever that has a
  display name. A campaign stores it when it builds the travel line (`GetMapCommandLine`, which finds the record
  by display name); a loaded save stores it by its saved display name.
- **With nothing stored** (a console `open <Map>` from the start screen: F-72), it takes the first record in the
  file whose `Name` is the map, without looking at mission type or rotation, and stores that. No URL option picks
  a record. So a map with several records (41 of LWR's) plays its first on this path, and the others can't be
  reached without a change to the file.
- **Nothing clears the stored record** when another map opens: a second console `open` in the same game keeps the
  first battle's record.
- **Streams by display name.** The script then adds the streams with
  `AddStreamingMaps(GetCurrentMapMetaData().DisplayName)`, which looks the record up again by display name and takes
  the first match. Two records with one display name stream the first one's packages.
- **Content options.** The campaign's line is `open|servertravel <Name>?game=XComGame.XComTacticalGame`, then
  `?LoadingFromStrategy=1` or `?LoadingFromShell=1`, `?Meld=1` (when the description's
  `ShouldSpawnMeldCanisters` says so), `?CapturePoints=1` (data recovery), `?RadarArrays=1` (data recovery and
  covert extraction) and `?StreamingMap<n>=` for each stream. The map's loader adds the packages `XComContent.ini`
  lists for Meld, capture points and radar arrays only when the option is there. `?StreamingMap<n>=` preloads on
  a seamless travel and adds levels only on a save's load. Play in game's `open <Map>` carries none of these.
- Used by: the mission types plan (which record a play installs, the options on its `open` line).

### F-115: A squad written into the profile is taken as written; its body comes from its armour, and LWR keeps some charges in perk entries
**Verified** (16 November 2026: read from the decompiled scripts and LWR's tactical mutator; played in EXP-64 runs 1
to 4 on LWR, every check passed). The test squad's records (test squad plan, Q0); [test-squad-records.md](test-squad-records.md) has the detail.
- **Taken as written:** `XGPlayer.LoadSquad` sets each record's character and soldier as they are, its `aStats` the
  base stats; armour, weapon and item bonuses are added by the battle each turn, so a record holds none of them.
  `aAbilities` and `aProperties` are counts of the config row's entries, zeros included (`BuildCharacter`).
- **The body from the armour:** `MapSoldierToPawn` maps a fixed list of armours, chassis and MEC suits to pawns; any
  other armour spawns nothing, and the unit is missing without an error. A MEC is the soldier character with the MEC
  class in a MEC suit; a SHIV the tank character in a chassis, carrying its first large item only.
- **The loadout:** a soldier equips two large items; the pistol's place takes any item (the heavy's machine gun); the
  fourth small item and on go to a five-item backpack; an armour with the grapple property gives the grapple itself.
- **LWR's charges:** a battle scanner's charges come from `aUpgrades[8] >> 1` and a smoke grenade's one from
  `aUpgrades[44] >> 1`, not from the item; a MEC's frag grenades and medikits are set to none. Without the entries the
  item is carried with no charges and its ability is hidden.
- **Size:** units past the sixth land one tile behind a landing point (point `I % 6`), snapped to the nearest valid
  place; there is no cap in the scripts.
- **Class record:** `kSoldier.kClass.eType` is the HUD's class label and LWR's class; plays before the panel left it
  empty (a rookie's).
- **The old squad's gear is LWR's Gauss tier:** the item numbers EXP-29 run 6 took for the basic weapons (rifle 3,
  machine gun 5, sniper rifle 6, rocket launcher 7) are `eItem_AssaultRifle`, `eItem_LMG`, `eItem_SniperRifle` and
  `eItem_RocketLauncher`, which LWR's localisation names Gauss Assault Rifle, Gauss Autorifle, Gauss Long Rifle and
  Recoilless Launcher, and its `DefaultGameCore.ini` costs with elerium and alloys; LWR's starting rifle is
  `eItem_ExaltAssaultRifle` (cost row `iCash=-1`, not built). The default squad keeps the old six as they were; the
  panel shows their gear by the install's names.
- Fix: the test squad (squadrecords.py) writes each unit this way, checks its armour against the list, writes the
  charge entries for scanners and smoke grenades, the class record, and warns about what the game drops (a SHIV's
  other guns and items, a soldier's third large item, a MEC's grenades). Played in EXP-64 runs 1 to 4: every check
  passed.


## Buildings and the cutaway (prefabs and buildings plan)

Read offline for prefab-library-plan.md, stage B0, on 11 November 2026: from the install's
152 map packages with [audit_buildings.py](../tools/upk/audit_buildings.py), from the exe copy and from the
decompiled scripts. Reference facts for a building the Build makes from nothing; none has been seen in a run yet.

### F-86: How the game's maps save a building
**Open** (11 November 2026: the survey; EXP-44 is to show a building made to this pattern cuts away).
- **568 building volumes** in 108 packages; every base map has at least two, except `CB2_MP_Blank` and `Command1`.
  405 have floors: 11 with one, 317 with two, 60 with three, 16 with four, one with six. The 163 without are the
  dropship's volumes and volumes tagged `Group0` to `Group2` or `deleteme` (LWR's randomiser).
- **Two floors is a one-storey building**: the inside and the roof. Floors stack without a gap (391 of 471 pairs)
  and are most often 192 high (449 of 1,158 floor volumes; then 176, 240, 384, 256).
- **A floor has one floor volume as a rule** (708 of 895 floors) and up to nine. 28 floors have none.
- **Nothing is turned or scaled**: no building or floor volume has a rotation or a `DrawScale3D`.
- **Saved on a building**: its brush, `Floors`, and for some `ExternalMeshGroups` (212) and
  `VisGroupIdxToHideWhenOccluding` (182). **On a floor**: `FloorVolumes`, `m_aCachedActors` (808 of 895), and for
  some `m_aCachedEmitters` (133 floors, 684 emitters) and external mesh group names (213). A floor's centre and
  extent are never saved; the game works them out when the battle starts.
- **A floor volume's `FloorNumber`** is its floor's index plus one, in all 1,174.
- **Listed pieces by class**: `XComDestructibleActor` 18,595, `XComLevelActor` 11,551, the fracturing classes 2,538,
  doors and other interactive pieces 451, ladders 365, collectibles 280, physics props 196. **No `StaticMeshActor`
  is listed** (11,856 of them): the class has no floor component.
- **No piece saves a floor component of its own** (117 odd ones do): it comes from the class's defaults at load, so
  a piece that never stood in a building has one.
- **`XComStairVolume` is placed in no map.** `XComCursorVolume`: 2,365 in 95 maps, floors 1 to 6, 1,848 of them 192
  high, none turned; 22 maps have exactly four (one for each storey over the whole map), 90 are marked
  `m_bTreatAsStair`.
- **The tile grid is 768 high** in 62 of 96 maps, and up to 1,152.

### F-87: Which floors list a piece, and which pieces cut down: the game editor's rule
**Open** (11 November 2026: read from the exe copy, `RebuildCachedActors` `0x7DCA60` with `0x86C320`, `0x9D3550`
and `0x78AEB0`, and checked against the maps; EXP-44 and EXP-45 are to show listings made by it cut away).
- **Listed on a floor**: a piece that touches one of the floor's volumes and whose bottom is more than 20 units
  under that volume's top (the constant at `0x187D38C`). Only `XComLevelActor`, `XComFracLevelActor` and `KAsset`
  and their subclasses, of the volume's own level.
- **With `bCutoutMask`** on its main mesh component, a piece that counts for several floors is then taken off all
  but the lowest, and its `CutdownFloor` there is the index of the highest. Without the mask it stays listed on
  each, with no `CutdownFloor`.
- **What that does in play** ([building-cutaway.md](native/building-cutaway.md)): while floor `k` is shown, a piece
  listed at or under `k` with a `CutdownFloor` over `k` is cut down at the top of floor `k`. So a ground-floor wall
  that reaches the roof floor (`CutdownFloor` 1) is trimmed while the ground floor is shown and whole once the roof
  is shown too.
- **The maps agree in structure**: every one of the 4,327 entries with a `CutdownFloor` is a masked piece listed on
  one floor of its building, the `CutdownFloor` 1 to 3 over the floor's index (3,546, 673 and 108). Of 11,772
  masked pieces 97 are listed on two floors; of 22,703 without the mask 2,280 are on two to four.
- **And nearly in geometry**: with each piece's box taken from its mesh's vertices, the rule gives the saved listing
  for 29,222 of 33,828 (86%), and for 30,214 (89%) when a box within 2 units of a volume counts as touching. The
  game goes by the piece's collision, which is a little larger than its mesh; the rest are near misses of that kind,
  listings tuned by hand (a volume's inclusion and exclusion lists) and listings baked before a later edit.
- **`bCutoutMask` follows the mesh**: of 3,494 meshes among the listed pieces, 1,113 always have it, 2,089 never and
  292 both; taking each mesh's majority gets 32,312 of 33,976 pieces right (95%). It is saved on the placed
  component, so a piece taken from outside any building usually lacks it.
- For the Build: `audit_buildings.touched` and `listing` are this rule
  ([test_audit_buildings.py](../tools/upk/tests/test_audit_buildings.py)). F-104 adds the hand-made lists and the
  collide flag, and has the survey of 14 November.

### F-104: A UFO's roof stayed on its ground floor in a prefab: the maps' hand-made floor lists, and the collide flag
**Fixed** (14 November 2026: the Small Landed UFO prefab; read offline from the install's maps with
[audit_floor_rule.py](../tools/upk/audit_floor_rule.py); not seen in a run yet).
- What: the Small Landed UFO prefab (LSmallScout_River's UFO and its building) showed its roof with floor 1 shown, in
  the editor, and the Build would have listed it the same way: the hull `SSRoof` (`XComLevelActor_90`) and seven other
  roof pieces were on floors 1 and 2, so floor 1 never hid them.
- Cause, in two parts:
  - **The map tunes its UFO by hand.** LSmallScout_River's floor 1 volume has an exclusion list
    (`m_aExclusionActors`) naming exactly those eight pieces, and its floor 2 volume an inclusion list
    (`m_aInclusionActors`) naming the same eight. By F-87's rule alone the hull (drawn box z 236 to 524) counts for
    floor 1 too (top 374); the lists take it off. Such lists are common: 3,862 inclusions on 429 floor volumes and
    2,581 exclusions on 282, in 86 of the install's 153 packages.
  - **The editor and the Build carried a map's saved listing only for boxes exactly as the map had them** (moved by
    the piece's move, within half a unit). The prefab's building had been edited (36 lower, the roof floor 72 units
    taller), so its pieces went by the rule alone, without the lists.
- Fix: the source building is found by overlap now (the source's floors carried by the piece's move, each paired with
  the project floor it overlaps most, `sourceFloorMatch` in [floors.js](../tools/viewer/web/floors.js) and
  `source_floor_match` in [compiler.py](../tools/editor/compiler.py)), and each piece keeps what its map saved where
  the rule gives the same with the source's boxes as with the edited ones (the map buildings' `carriedListing` and
  `buildings.carried`). Built offline, the prefab's test stage lists the eight roof pieces on floor 2 only.
- **The rule also listed pieces that collide with nothing.** The game lists the actors in a floor volume's `Touching`
  list, and only an actor that collides touches one. Over the install (pieces of a listed class within 64 units of a
  building's floor volumes, the lists applied), the rule as it was gets 96.0% of the 33,976 listed pieces right and
  65.3% of the 7,672 unlisted ones; skipping the pieces that don't collide (`bCollideActors`, `CollideActors`) gives
  96.0% and 82.7%. The Build's `buildings.rule` skips them now; the editor does where an export says
  `collides: false` (exports and pieces made from 14 November on; older caches keep the old answer).
- Tried and dropped: the mesh's collision instead of its drawn box (simple hulls, their box, each hull, triangles):
  no better once the collide flag is in (95.1% and 82.3%); more slack across or none up and down: worse.
- Left: 1,316 unlisted pieces the rule still lists, 73% of them archetype placements whose collision settings live in
  another package the reader can't follow (34% among listed pieces), the rest likely listings saved before a later
  edit; and about 1,400 listed pieces it gets wrong, near misses of a few units and walls touching the next floor's
  bottom.

### F-88: What a building's and a cursor volume's flags do
**Open** (11 November 2026: read from the decompiled scripts; none tried in a run).
- **`IsUfo`** (29 buildings) is read only by the aliens' layout (`XGLayout`): the building's rectangle is marked as
  the UFO's, shrunk to 70% for three UFO types, and pods can be asked whether they are behind the UFO. It plays no
  part in the cutaway. A UFO hull cuts away as any building does.
- **`m_bIsInternalBuilding`** (2 buildings) marks a building inside another: a unit in both counts as in the inner
  one (`XComPawnIndoorOutdoorInfo.CheckForFloorVolumeEvents`).
- **`IsDropShip`** (2) marks the extraction volume; **`IsInside`** tells a spawn point it is indoors
  (`XComSpawnPoint.IsInside`); **`m_bAllowBuildingReveal`** off (15) stops `ShowFloor` altogether.
- **The cursor's floors** come from the cursor volumes alone (`XCom3DCursorForCursorVolumes`): its top floor is the
  highest `m_iFloorNumber` of any cursor volume in the map, and going up or down a floor looks only at the cursor
  volumes over the cursor's place. A map with no cursor volume gives the cursor one floor (`CB2_MP_Blank` has
  none). **`m_bTreatAsStair`** makes the cursor keep to the volume's floor as it leaves the volume by its top.
- **Stairs** are pieces and need no volume. The tile data has a ramp direction for each tile
  ([native-code-notes.md](native-code-notes.md)); how the rebuild sets it for a copied stair has not been read, and
  is left to EXP-45.

### F-89: Saving does not work in a battle started without a campaign (Play in game)
**Fixed offline, for plays with saving on** (EXP-43 runs 1 and 1b, 11 November 2026; the cause read on 15 November
and confirmed by [EXP-56](experiments/EXP-56-save-after-login.md) run 1 the same day: the same battle opened again
from the title screen, after its login, saved and loaded. The same day the editor got an **Enable saving** checkbox,
at the user's design: with it on, the game starts at its main menu and F5 there opens the battle. To play in
[EXP-57](experiments/EXP-57-enable-saving.md). A play with it off still can't be saved; most test plays don't need
to. The way not taken, a play that logs in by itself, is play-login-plan.md).
- **The fix** (play.py, gamelaunch.py, installs.py): a play with saving on starts the game with
  `XComMapWorkshop-start.txt` instead of the play's commands file. Its one line, `setbind F5 exec
  XComMapWorkshop-play.txt`, binds the key at once (`Engine.Input.SetBind`, read from the game's `Engine.upk`) and
  saves it to `XComInput.ini`; nothing is opened, so the game stays at its main menu and logs in there. F5 then runs
  the play's commands (its `set` lines and the battle's `open`). The play keeps `XComInput.ini` and `profile.bin`
  aside with `XComContent.ini` and puts them back once the game has closed: the logged-in game writes its profile,
  the play's test squad in it (the lab copy's `profile.bin` was rewritten at 11:58:14 in EXP-56 run 1). Long War's
  EXALT missions always have it on (F-109).
- What: in a battle started straight on a map (F-72's way, the editor's Play in game), Save shows the "saving"
  notice coming and going without end. The save file is written (the log shows both checkpoints copied and
  `General Checkpoint Async Work Finished`). Loading it from the load menu hangs the game, with nothing logged.
- On any map: the game's blank map `CB2_MP_Blank` (run 1) and URB_Bar's original layout (run 1b) alike.
- Not something a change broke: of the 38 logs the lab copy keeps of a start with `-EXEC` (8 to 11 November), only
  these two runs hold a save or a load. Every earlier save, EXP-37 to EXP-42's on 11 November among them, was in a
  campaign (a start without `-EXEC`, the map loaded with `LoadingFromStrategy=1`), and those save and load.
- ~~Likely cause: the battle has no campaign behind it (`m_bLoadingFromShell`).~~ Not that (15 November):
- **Cause (read, to confirm).** The game never logs in. On PC the start screen does it by itself: `UIShell.OnInit`
  sets a 0.1-second timer for `DelayedLogin`, which calls `XComOnlineEventMgr.BeginShellLogin(0)`; an ordinary start
  logs it about half a second after the start screen loads ("Using cached profile data instead of reading",
  "Obtained steam user stats"). A play's `open` line runs from `-EXEC` 0.1 seconds after the start screen loads,
  before its interface is up, so the login never happens. The login:
  - hands the Steam content interface the event manager's callbacks (`InitializeDelegates`: a save written, read,
    deleted, the save list read; kept in `OnlineSubsystemCommonImpl.ContentCache[0]`). Without them a save is written
    with nobody told when it ends: `OnWriteSaveGameDataComplete` never runs, so `CheckpointIsWritingToDisk` never
    clears and "SAVING..." stays; a load waits for `OnReadSaveGameDataComplete`, which never comes;
  - selects the storage device (`bHasStorageDevice`; `HasValidLoginAndStorage`, which the autosave manager's
    `SavingEnabled` asks);
  - reads the save list (the slot numbers). Without it a save goes to slot 1 whatever saves there are: EXP-53's
    EXALT runs wrote the lab copy's `save1` (when the game closed), beside saves 8 to 20.
  - A test battle left for the main menu does get the login (12 November's run on the prefab stage logs it).
  - EXP-56 starts the same battle after a login, by hand (`exec XComMapWorkshop-play.txt` from the main menu); if it
    saves and loads, a play has to open the battle after the login (its "If it passes" lists the ways).
- Before the fix: a run that needed a save and a reload was played from the lab's campaign test slot
  (`lab_install.py install`), not with Play in game.
- **The save a play leaves is broken** (EXP-56's try at 11:32, 15 November). The user left a test battle for the main
  menu (the login ran) and loaded from there the Slaughterhouse save the 10:45 play had left (moved to save999 by
  the editor): the map started loading and the game crashed 5 seconds in. The dump (`unreal-v8917-2026.11.15-11.32.33.dmp`)
  is a divide by zero (0xC0000094) at 0x4AB9DE in the exe copy's addresses (the game ran at base 0x5A0000), in the
  compressed-data reader: after the package tag 0x9E2A83C1 it divides by the chunk size it read, and it read 0. The
  file is 670 copies of the 1 KB save header and then the checkpoint data; a whole save (save9, save20) has its data
  at byte 1024. So the stuck write rewrites the header about once a frame (670 in the 11 seconds that play sat at
  "SAVING...") and writes the data only as the game closes. Every save a play leaves is like that while this stands.
- A play's save never keeps a campaign's slot (15 November, at the user's ask): before a play the editor copies the
  game's save1 to save9 aside (both save folders: the install's `XEW\XComGame\SaveData` and Documents'), and once the
  game has closed it takes any save in a low slot that changed and is a play's (game 0, its map opened with
  `LoadingFromShell=1`) out of the slot and puts back the copy it replaced ([playsaves.py](../tools/viewer/playsaves.py),
  `installs.keep_saves`/`restore_saves`, run by the play's watch, the next play and Remove from game). A broken one
  (no package tag at byte 1024) is set aside out of the game's folder, in the install's `XCOM Map Workshop\broken
  saves`, so the load list can't offer it; a whole one (none yet) goes to the play range, save999 down to save900. A
  play's save left from before is sorted the same way at the next play. (The first version, earlier on 15 November,
  moved every play save to save999 down, which put the broken one in the load list: the crash above.)
  - How the game names a new save: the highest number in its save list plus one (`GetNewSaveFileName` is behind the
    copy protection, 0xB6EAD0, so seen, not read). EXP-56 run 1's save after the login was save21, with save20 the
    highest and save1 and save6 free; a play without the login has an empty list and writes save1. So a play that has
    logged in never writes over a campaign's save, and a whole play save moved to save999 would make the campaign's
    next save save1000. So a whole play save now stays where the game wrote it; only one written over a save copied
    before the play (saved over it from the menu) moves to the slot after the highest, and that save goes back.
- The user, 11 November 2026: saving in a single-map test run need not be supported for now.
- 15 November 2026: Long War's EXALT missions save and reload as they start, so on this path they wait for good
  (F-109); fixing this would make them playable. The lab copy's `SaveData\save1` from those runs was last written
  when the game closed, not when the battle saved: the write starts (the "SAVING..." notice is shown once Steam's
  content interface takes it) and only ends at exit.

### F-90: On `CB2_MP_Blank` the squad starts on one tile and LWR places no pods
**Open** (EXP-43 run 1, 11 November 2026: seen in the run and in its log).
- What: all six soldiers start on the same tile, and the aliens are the map's own single pod.
- Cause: the map has no spawn points the squad's loader takes. The log has `FindSpawnGroup: Looking for spawn
  points with tag: None` and `Accessed None 'kSpawn'` in `XGPlayer.LoadSquad`; LWR's pod mutator then finds no
  player start, no random locations, and skips (F-85), leaving the map's `XComAlienPod` to play. The map's 12
  `XComSpawnPoint`s are a multiplayer map's.
- Cause confirmed offline: the 12 points take `UnitType` `MPTeamOne` and `MPTeamTwo` from their archetypes (the
  multiplayer landing prefabs); a soldier point has the class's own.
- Fixed in the Build (`tools/bake/shell.py`): a map with no soldier points gets URB_Bar's six, set on the
  multiplayer team-one points. EXP-43 run 2 showed the squad spread out.
- LWR's pods and Meld still don't come (run 2: two sectoids, no Meld). Its mutator finds the soldier points now,
  but keeps only map sections at least 29 tiles from the squad's centre, and a 36 by 36 grid with the squad near
  the middle has none (`Not enough sections left: 0`). On the same map made 54 by 54 tiles (EXP-43 run 3) its pods
  and Meld came, in the new area too.

### F-96: How the game picks the squad's landing (plain Enemy Within)
**Open** (13 November 2026: read from the exe copy and the packages, not seen in a run; [clear-map-p0-2026-11-13.md](evidence/clear-map-p0-2026-11-13.md)
read 1, [clear-audit-2026-11-13.json](evidence/clear-audit-2026-11-13.json)). A reference fact, not a defect.
- **The candidates** (`FindSpawnGroup` `0x465D00`, `GetSpawnGroupIndex` `0xB26F00`): the soldier and tank points
  (`GetUnitType` 0 or 1) in the archetype-to-instance maps of the level's `PrefabInstance`s, leaving out templates
  named `Doorway`. Each point is keyed by its `Tag`.
  - Only when no prefab instance holds one does every soldier point of the level count. This is how LWR's spawned
    points are found.
- **The pick**:
  - the group is the distinct tags, sorted by their text, at index `play count % count`;
  - `?SpawnGroup=Group<N>` picks the tag `Group<N>` if a group has it;
  - the index (or N) is also the Meld points' `m_iSpawnGroup` and the intro's `GroupNumber`.
- **The install** (97 base maps): the three-landing maps (22) tag them `Group0` to `Group2`, the two-landing ones (8)
  `Group0` and `Group1`; every one-landing map has a single tag. The cooked maps keep the prefab instances and
  their maps.
- **So**: a landing can be removed by taking its prefab instance (and its actors) out of the level. The groups after
  it then shift down an index, and their Meld and intro with them, unless their tags are renamed back into
  order. A landing can be added only with a cloned prefab instance as well as the ten actors, under a new tag.

### F-97: The dropship intro flies to a fixed place for each map and group
**Open** (13 November 2026: read from `CIN_DropshipIntros` and the script, not seen in a run; [clear-map-p0-2026-11-13.md](evidence/clear-map-p0-2026-11-13.md)
read 2). A reference fact, not a defect.
- **The rig.** The intro's whole rig (dropship, cameras, soldier stand-ins) is based on `SkeletalMeshActor_6`. A Set
  Location with a saved `LocationValue` and `RotationValue` puts it there.
  - The action is chosen by the map's name (52 maps), and on 29 multi-landing maps then by `GroupNumber` (0, 1, 2).
  - URB_Bar: (560, -2683, 0), yaw 191.
- **Not the landing.** The places are hand-set at the map's grounded Skyrangers: 99 of 139 within a tile, the Farm's
  exactly, Bar's 287 units ahead. They are not the landing's `PointInSpace`, player start or soldier points.
- **At the end** the soldiers are put back at their spawn points.
- **So**: a moved landing lands the squad at the new place, but the flight plays at the old one unless the variant's
  intro copy gets new values (a same-size write). Under LWR the intro always uses group 0's place.

### F-113: Cover blocks smaller than a tile do what the tile rebuild makes of them
**Verified** (15 November 2026, [EXP-59](experiments/EXP-59-small-cover-blocks.md) run 1, the user: "B did hold as a
wall"). Not a fault: what the editor's handles (any size in units,
cover-block-handles-plan.md) rely on.
- **What the game does.** Read in [native/cover-build.md](native/cover-build.md): a tile is occupied when its box (48
  each way, 28 to 92 over its level's bottom) meets a piece at least 4 units through, fully occupied (no floor)
  when the middle 40 x 40 from 60 to 92 does too; crossing to a neighbour is blocked by a sweep 64 over the floor
  toward its centre, with no thickness rule; cover is swept 44 to 60 over the floor along the lines through tile
  centres.
- **Played.** Six hidden high blocks on the Bar's pavement: whole tile, half a tile in a tile's middle, an 8-unit
  wall on a tile edge (it held as a wall: units on both sides, no crossing), a 24-unit block in a corner, a block 40
  high, and a 2-unit wall on an edge. The user: "it works fine". Discord S8 (an invisible cover wall) needs no new
  piece: a thin block on a tile edge.
- **The editor.** The panel's words (app.js `coverTiles`, `coverGameWords`) and the Build's `cover-thin` and
  `cover-short` warnings follow the rules above.
- **Open: sight.** The user could see and shoot across the 8-unit wall. Most likely by leaning round its ends (it
  is one tile long); whether a hidden high block stops sight at eye level hasn't been checked. EXP-59's notes give a
  check that tells the two apart.

### F-112: A test play of an EXALT mission had Sectoids, not EXALT
**Verified fixed** (15 November 2026: found in [EXP-57](experiments/EXP-57-enable-saving.md) run 2, the user's play
of a data recovery: "there was no exalt, everything was sectoids"; the cause read from the game's scripts; the fix
played in run 4 at 14:32, "57 is confirmed"). A fault of the editor.
- **Cause.** A battle started without a campaign gets its pods from `XGBattleDesc.GenerateAliens`: four pods (five on a
  terror site) of the profile's `m_eAlienType`, which every play set to `eChar_Sectoid` (`gamelaunch.ALIENS`). The
  campaign gives an EXALT mission EXALT pods; a play gave it Sectoids.
- **Fix.** The same function makes EXALT pods for an EXALT type (`XGGameData.IsExaltCharacterType`, types 24 to 31):
  the leader, one of the same and a sniper or heavy (`GetSupportAlien`'s alternative: a coin toss made once, so all
  the battle's pods get the same one). A play of data recovery, covert
  extraction or the EXALT raid now sets `eChar_ExaltOperative` (`missions.EXALT_KINDS`, `EXALT_ALIENS`;
  `play_setup`'s `aliens`, passed to `gamelaunch.play_text`). Long War doesn't rewrite pods in battle (its mutator
  reads a mission's pods on the strategy side only), so the game's own set-up stands. EXP-57 run 4 plays it.
- **Seen in run 4.** EXALT's units, weapons and looks loaded when first needed (the play has JIT loading on), and
  the reloaded battle had four pods of two operatives and a heavy, 12 EXALT soldiers. One Sectoid and one
  Chryssalid are listed outside the pods and weren't seen (every play's battle lists one Chryssalid: units the game
  keeps aside [inferred]). Long War's save and reload went through and the battle played.

### F-110: A test battle has no mission commander: no Outsider in a UFO, no Sectoid Commander in an alien base
**Accepted** (15 November 2026: EXP-53 runs 5 and 7, the user's plays of `CSmallScout_Quagmire`'s crashed UFO and
`AlienBase01`; the cause read from the game's and LWR's scripts). A limit of the test's aliens (the mission types plan,
decision 2), not a fault of the editor.
- **Seen.** The crashed small scout played well, but no command pod (the Outsider) stood in the UFO. The alien base
  played well, without its Sectoid Commander.
- **Cause.** `XComAlienPodManager` puts a commander in a pod only when the battle's description names one
  (`m_kAlienInfo.iMissionCommander`), and the campaign's alien squad is what names it. A battle started from the
  console has the test's pods (Sectoids, with Chryssalids for variety) and no commander. LWR's pod mutator still
  does its part: it found the UFO's building volume and picked a commander spawn point inside it ("found good random
  Commander spawn point"); on the alien base it kept the map's own.
- **So** a UFO building made in the editor can't be checked for its commander pod with Play in game (EXP-54's crashed
  UFO run looks at the spawn point in the log instead). The play window says no commander comes (`COMMANDER_NOTE`).
  Giving a test battle a commander (`set XGBattleDesc m_kAlienInfo ...`, as O-3's lines) is untried.

### F-109: EXALT missions started from the editor stop at "Mission Briefing: Please Wait" under Long War
**Fixed: data recovery played** ([EXP-57](experiments/EXP-57-enable-saving.md) run 2, 15 November 12:43: with saving
on, F5 at the main menu opened the battle and Long War's save and reload went through; covert extraction and the EXALT
raid take the same path, not played. Their plays have saving on since the evening of 15 November, F-89.
Seen 15 November 2026: EXP-53 runs 2, 3 and 7, the user's plays of `URB_PoliceStation`'s data recovery,
`URB_LiquorStore`'s covert extraction and `EWI_ExaltHQAssault`; read from their `Launch.log`s and LWR's
`LWRebalance.u`, decompiled from a copy).
- **Seen.** Each battle loads, the squad, the pods and the covert operative ("Debug McGee") spawn, the briefing's
  narration plays, and then the screen keeps "Mission Briefing: Please Wait" and "SAVING..." until the game is
  closed. The log stops after `--- SAVING CHECKPOINT ---` and `General Checkpoint Async Work Finished`. The other
  kinds played that day write no checkpoint at the start.
- **Cause.** Long War saves and reloads every EXALT battle as it starts. `RebalanceMutator.PostLevelLoaded` sets a
  timer for `ReloadExaltMission` on a battle not loaded from a save. Its `ReloadMissionState` shows LWR's string 173
  ("Mission Briefing: Please Wait", kept in `UICredits`' `m_arrCredits`), saves to the next autosave slot, waits
  until the checkpoint is serialised and written to disk, waits out the narration, and loads that save. After the
  load (`PostLoadSaveGame`) it runs its pre-mission setup and deletes the save. A battle started without a campaign
  never finishes writing a save (F-89), so the state waits for good.
- **Not a way round** (read again 15 November, at the user's ask to skip the save on EXALT maps):
  - Starting the battle as if loaded from a save (`bJustLoadedFromSaveGame` on the mutator) would skip the reload
    (`OnMapLoaded` then runs the turn-1 setup instead), but a play can't set it. A play's `set` lines run at the start
    screen, where the mutator loader loads no mutators (`XComMutatorLoader.GameInfoInitGame` loads them only for a
    battle or HQ), so Long War's class isn't in memory yet. `set` only finds objects already loaded (a find by name,
    no load: the handler at 0x10692D0), and this build has no console command that loads a package. Even set, only
    `LoadFinished`, which a load starts 3 seconds after, clears it. Left on for the whole battle, Long War ignores the
    game's `MaxBaseHP:` hook, which its wound penalties use on every HP change; the sneakers' warning and one perk's
    healing block (upgrade 146) are off; and the covert operative's command charges, set only on the way to the
    reload, aren't set. (EXALT HQ's reinforcements, noted here before, need the campaign's Skyranger size, so a
    play has none either way.)
  - Making the save fail at once is in a play's reach: `set XComOnlineEventMgr bUpdateSaveListInProgress True` (bit 8
    of the event manager's flags at +0x5F0) makes the native `SaveGame` (vtable +0x17C, 0xE8B5A0) and `LoadGame`
    (+0x184, 0xAB52D0) give up at once ("Save Failed: Cannot save while a save list update is in progress." and the
    same for a load), so Long War's wait would end. But its state starts with `DisableUI` (cinematic mode: no HUD,
    no input), and only the reload gives the controls back. The battle starts running only after its intro, and
    nothing else in the game turns cinematic mode off without input (pod reveals, kill cams; the cheat manager's
    `SetCinematicMode off`), so the battle would stay frozen.
- **What would fix it:** F-89 (saves in a battle started without a campaign). Done offline on 15 November: a play of
  data recovery, covert extraction or the EXALT raid under Long War always has saving on (`missions.SAVING_KINDS`),
  so the game starts at its main menu and F5 opens the battle after the login; Long War's save and reload then go
  through (EXP-57 run 2: data recovery, now marked played and working; the other two not played yet). Its pods were
  Sectoids then (F-112). Plain Enemy Within doesn't reload; it hasn't been tried.

### F-108: A moved stream actor turned by its archetype was read as unturned
**Fixed offline** (15 November 2026: seen in the stream copy's report while making
[EXP-55](experiments/EXP-55-moved-capture-point.md)'s project; no game run needed it). A fault of the toolchain.
- **Seen.** Police Station's data recovery encoder (`XComCapturePointActor_0` in `URB_PoliceStation_CNH`) saves no
  `Rotation` of its own; its archetype `ARC_Encoder_CapturePoint` turns it a quarter (yaw -16384). Export 24 reads it
  through the archetype, so the editor and the project have the quarter turn. `stream_copy.py` read only the actor's
  own property: its report said the move turned it from 0 to -16384, it wrote the turn as the actor's own, and the
  box the base map's tiles are rebuilt under at the old place was the mesh's box unturned.
- **In the game** the written turn was the one it already had, so the copy played the same. The old tile box was off
  by the turn: a near-square encoder about a tile across, so little of it.
- **Fixed.** `stream_copy.pose` reads Location and Rotation through the archetype (`Package.effective`) for the
  report, the old tile box and a base's pose; a turn that doesn't change is left to the archetype.
  `test_stream_copy.TurnedByItsArchetype` moves the encoder.

### F-107: A terror battle started from the console hangs at the loading screen: its civilians have no looks
**Fixed, played** (15 November 2026: the user's play of `hurr+` on `URB_StreetHurricane_Terror` as its Terror record,
01:21, hung at the loading screen until closed; read from its `Launch.log`. Played with the civilians' line at 01:32:
"launched and worked fine in game"; every terror play has the line since). The same as F-93's run 3 (12 November, a
terror-site record on the prefab stage), now on a real terror map, so the map was not the cause.
- **Seen in the log.** Long War's mutators ran and the squad and the pods spawned (`FIXDEPLOYMENT` names mission type
  9, the record's display name with `Terror`). Then 18 `XComCivilian`s spawned, each `RandomizeAppearance` reading
  empty `MaleHeads`, `MaleBodies`, `MaleHairs` (or the female ones) "out of bounds (0/0)", and the content manager
  logged `CacheRequiredArchetype: Requested missing Body content: Id=0` (Head, Hair and Unit the same). After that
  only Long War's `PostLevelLoaded` lines repeat, every 0.4 s, until the game is closed.
- **Cause.** The civilians' looks are the profile's `m_kCivilianContent`, which the campaign fills before a terror
  battle (`XGBattleDesc.BuildCivilianContent`) and a console `open` doesn't (the mission types plan, O-4). With none,
  every civilian asks for content 0, which never loads, and the battle waits for it.
- **Fixed.** The editor's line for it (`missions.civilian_content`: five civilians from the install's
  `DefaultContent.ini`, as `set XComOnlineProfileSettingsDataBlob m_kCivilianContent ...`), tried with
  `serve --try-mission-lines` (EXP-53 run 6), played: the battle started, the user played it, and the log shows the
  civilians loading their bodies (`Body_WrmCivFem_A`, `Body_ColdCivMale_D`, ...) with no empty lists. Its state is
  `works`, so every terror play now has it, and the terror kind reads "Played and working".
- **Left over, harmless so far.** The content manager still logs `Requested missing Unit content: Id=0` nine times
  as the civilians spawn; the battle didn't wait for it.

### F-106: Street Hurricane Terror's dropship lands in the middle of the map
**Fixed offline in the Build, to confirm in the game** (15 November 2026: seen by the user in a play of the project
`hurr+` on `URB_StreetHurricane_Terror`, played as its Council extraction; the cause read from the install's
`CIN_DropshipIntros`; the Build's fix the same day). A fault of the game's own data, not of the editor: it plays the
same on the map as the game has it, whatever the mission.
- **Seen.** The intro's Skyranger lands near the middle of the map and stays there through the battle. The squad
  stands at the map's own landing (the log's spawn points around (1936, -528)). The editor shows no Skyranger
  there, since the map has none there.
- **Cause.** The intro's switch on the map's name (`SeqCond_SwitchString_1`, entry 11, `URB_StreetHurricane_Terror`)
  leads to `SeqAct_SetLocation_34`, which saves a `RotationValue` (yaw -54249, the plain Hurricane's) but **no
  `LocationValue`**, and has no Location variable linked. So the rig's base, `SkeletalMeshActor_6` ("CineDummy"),
  is put at (0, 0, 0). On this map's grid (origin (-3456, -1152), 62 by 23 tiles) that is near the middle,
  (-480, -48). The scene leaves its dropship parked there, and only the soldiers are put back at their spawn points
  (F-97).
- **Only this map.** It is the one entry of the 81 in LWR's `CIN_DropshipIntros` with no place. The plain
  `URB_StreetHurricane` entry has one, (3181, -269, 6).
- **Where it should be.** The intro places sit on the map's grounded Skyranger: across the 168 places read for F-97,
  the median distance is 1.35 units and the median yaw difference 0. This map's grounded Skyranger
  (`XComLevelActor_91`) stands at (3813, -134, 1) with yaw 18468. That is not where the plain map's stands
  ((3178, -406, 0), yaw 11268), so the plain map's place would be wrong here.
- **Fixed in the Build.** A variant's intro copy (`intro_copy.py --map`, which the Build passes the base map) gives an
  entry of the base map that saves no place its landing's grounded Skyranger's place and yaw: here (3813.0, -134.4,
  0.6), yaw 18468. A landing the project moves moves it from there. A quick build of a copy of `hurr+` wrote it
  (the build's `intro` stage lists it as `filled`). A play of the map as the game has it installs nothing for its
  first record and keeps the fault.

### F-98: A moved grounded Skyranger and a turned evac volume in a Build
**Fixed offline, to confirm in the game** (13 November 2026: read; [clear-map-p0-2026-11-13.md](evidence/clear-map-p0-2026-11-13.md)
read 3; the relight's part fixed the same day).
- **The relight** takes its casters from the package it is run on, by each actor's saved place. The grounded
  Skyranger is a caster (texture lightmap, a shadow map).
  - A Skyranger moved in place before the relight shows no change: its old shadow stays and no new one falls.
  - The relight must get the move as a removed caster and a posed copy.
  - **Fixed:** `native_copy.py` hands the relight each piece with a mesh that `native_spawns.py` moved
    (`relight.py --moved-in-place ACTOR=old pose`).
    - The scene before the edit leaves it out where it now stands and has a posed copy of it at its old pose. The
      scene after is the map as written.
    - Its own lightmap and shadow maps keep their bake.
    - A build whose one change moves a landing is now baked; before, it kept the map's lighting.
    - Checked offline: URB_Bar baked with its landing moved six tiles east. 26 receivers were relit. The ground's
      shadow map (XComLevelActor_131) lost the Skyranger's shadow at the old place and has it at the new one.
      XComLevelActor_138 was skipped as moved in place. Not yet seen in the game.
- **Evac volumes save no turn.** All 143 landing evac volumes save `Rotation` (0, 0, 0), with the prefab's turn baked
  into the brush's vertices (Bar's 480 by 288; the Farm's west and east ones 288 by 480).
- **LWR turns them at run time.** It spawns them turned (`AdjRotation`: the line's quarter turns plus the volume's
  yaw minus the frame's) and re-inits the buildings; 335 of the base maps' 447 lines need a turn. A saved turn
  is a same-size write of the saved `Rotation`.
- **Other parts** lack a saved `Rotation` on about a third of landings (46 of 142 frames, 48 of 146 player starts);
  every one saves its `Location`.
- **Which Skyrangers a battle shows** (13 November 2026, read from XComLZMutator's decompiled script and the exports):
  - Under LWR, when the map has LZ lines, `HideDropShip` hides and destroys every actor of the grounded Skyranger
    prefab's archetypes (`PRE_SkyrangerGrounded_*` mesh, emitter and sound, `ARC_Skyranger_Ground_Periphery`), every
    landing's. A copy keeps its original's archetype, so it goes too. Only the baked shadow stays.
  - Act1_IntroLevel's Skyranger (`XComLevelActor_116`) and its idle emitter (`Emitter_4`) have no archetype: placed
    by hand, not from the prefab. LWR doesn't hide them.
  - The CsmallScout_Farm's three Skyrangers (one per landing group) are named by no script. Whether plain EW hides
    the ones of the groups it doesn't pick has not been read or seen.

### F-99: LWR's lines and the maps' own landings
**Verified** (13 November 2026: [audit_clear.py](../tools/upk/audit_clear.py) over the install's 97 base maps,
offline). A reference fact for the plan's one list of landing zones.
- **146 own landings** in 94 maps: 64 maps with one, 8 with two, 22 with three. 447 live lines for 83 of them; 41
  name a mission.
- **Matched by their six soldier points** placed by XComLZMutator's offsets:
  - 41 landings have a line within 4 units, frame too (URB_Bar's first line, 1.4);
  - 30 more have the points within 4 units with the frame elsewhere;
  - 27 have a line within half a tile, 25 within a tile and a half (CsmallScout_Farm's Group1 and Group2, 96 units:
    the line a tile off);
  - 8 have no line within that on a map with lines: the Terror copies of Bar, Commercial Alley and Commercial
    Street, Research Outpost EWI, the Rooftops pair and two Overseer maps;
  - 15 are on maps with no lines.
- **Where the line falls.** Of the lines, 71 are some landing's own (within 4 units).
- **13 maps tag their one landing `deleteme`.** It is still the only group, so it plays.

### F-100: A grown map's new area has no floor where only the map's scenery lies
**Fixed offline, to confirm in the game** (13 November 2026: the user's intro+ played, Act1_IntroLevel grown from 62
by 19 by 12 tiles to 95 by 25 by 18; read offline from the map with `tools/upk/props.py`; the fix the same day).
- **Seen in the game:** units can't walk in the new area, though the map's ground and pavements are drawn there at
  the old area's height. The squad of a landing zone there stands a little above the drawn ground.
- **Cause:** the pieces a map is seen against beyond its play area are saved with their collision off. In the grown
  area of Act1_IntroLevel (x 576 to 3743) every ground plane (`grassPlanes.AsphaltPlaneFlat`, XComLevelActor_13,
  _183, _184, _185, _188, _248, _273, _337, _375) and pavement (`EuroSidewalk*`, XComLevelActor_230, _231, _259,
  _260, _261, _262, _268, _270) saves `bCollideActors` 0 and `bPathColliding` 0 on the actor and `CollideActors` 0 and
  `BlockRigidBody` 0 on its mesh component. The same mesh inside the play area (XComLevelActor_181) saves none of
  them, so it takes the defaults and is floor. The backdrop buildings (`MidgroundBuildingGroup*`,
  StaticMeshActor_1 and _46) have collision off too.
- The Build's rebuild volume over the whole grid (shell.py `resize`) re-checks those tiles, and the game's trace
  finds nothing to stand on: no floor tile, so the soldiers keep the zone's height.
- The editor drew the zone as standing on a floor: its floor check (and the compiler's `landing-floor`) takes any
  map piece under a soldier tile.
- **Fix:** the Build's shell stage turns those four flags on (`shell.py walk_scenery`,
  `native_copy.make_walkable`). It does so for each listed level actor that saves `bCollideActors` false and meets
  all of these: no taller than 32, its bottom within a level of the grid's, reaching past the map's own far X or Y
  side. The intro+ build has 21 such pieces, all listed in the final package with the flags on.
- A copy of such a piece placed in the grid gets the same (`native_copy.build`): a backdrop plane laid as floor would
  otherwise be no floor, and its copy got no tiles either, since `collides` was false.
- The compiler's `scenery_floor` and the page's zone notes take those pieces as floor for a landing zone. The
  backdrop's buildings (StaticMeshActor, 2,400 high) stay as they are.
- **Again on CsmallScout_Farm** (the user's farm++, 13 November, grown to 91 tiles along Y, ground laid).
  - The play area's ground is at -128, the grid's bottom. The new strip takes in a raised backdrop whose ground
    planes stand at 0 and are floor pieces already: no collision flags saved.
  - The rule took only pieces within a level of the grid's bottom, so none of these. It made the sky's ground plane
    (`Skybox.Meshes.GroundPlaneBlack`, at -224, 320,000 across) walkable instead.
  - The new tiles two levels up are open air with no low bit, which the rebuild passes over.
  - The ground laying put 21 planes at -128 under the raised backdrop: the only floor there, so units would walk
    under the ground they see.
  - **Fix:** low pieces anywhere within the grid's levels, those that are floor already too. Their tiles get the
    seed bit, the rebuild volume reaches their level, and no plane is laid in a block they cover. The rebuilt
    farm++ has no landing warning, 844 tiles queued and 9 planes laid.
- **Also seen:** intro+'s zone was saved with its ground 16 under the grid's bottom: fitted before the ground was
  snapped, and moved by whole levels from there, so `landing-outside` stayed. The zone gizmo now lands the ground on
  a level of the grid; a page check on a copy of intro+ moved it from z 48 to 64, and both notes went.
- **Checked:**
  - test_shell's GrownIntroScenery, test_native_copy's WalkableScenery and test_compiler's grown-area zone test,
    with both suites whole (69 and 123 tests);
  - the smoke's clear-map check on Bar, CSmallScout_Farm and Act1_IntroLevel.

### F-101: A cover block stayed as an invisible wall when the piece under it was destroyed
**Verified** (13 November 2026, the user's ask; EXP-52 run 1, played the same day, bar a save and a load).
- **Cause:** a cover block is a hidden `XComLevelActor`. The game's link between pieces that break together,
  `AffectedChildren`, names `XComDestructibleActor`s only, and a level actor has no damage states.
- **Fix:** a high or low cover block in a group with Break together on is built as a hidden prop
  (`cover_blocks.BREAKING`): an `XComDestructibleActor` with no archetype on the block's box mesh, with one destroyed
  event, the game's own `XComDestructibleActor_Action_Hide` (it takes the mesh away, which turns the collision off
  and has the tiles rebuilt: research/native-code-notes.md). Each breakable piece of the group lists it in
  `AffectedChildren`.
- It takes no damage of its own (a toughness with `bInvincible`), so a blast that leaves the piece standing leaves
  the cover too, and it damages nothing when it goes (`bDestroysSurroundingArea` off).
- One breakable piece is enough with a block, and it may be the map's own, left in place.
- Not covered: an invisible floor, and a block grouped with a wall or floor that breaks in parts (a fracturing
  piece is not a prop, so nothing can list the block). Since 18 November (custom walls M3 item 4, built offline, not
  played yet): a block or prop grouped with a wall made from numbers is listed in the wall's columns it stands by
  (`frac_walls.group_columns`), the game's list of what goes when a column breaks; the map's own walls and floors
  still can't list one.
- Every prop of the game's maps has an archetype and this one has none: it loads and plays (EXP-52 run 1).
- Not checked: a save and a load after a block went (Play in game's battles can't be saved).

### F-95: What editing the maps' own buildings depends on
**Verified** (13 November 2026: the survey of step E0 of the
map buildings plan, `audit_buildings.py --editing` over the install's
153 packages of the maps the editor lists; [EXP-50](experiments/EXP-50-map-buildings.md) played on Bar the same
day: a floor volume of the map stretched in place and a building of the map moved with its volumes both cut away in
the game as the editor shows).
- **407 building volumes have floors, all in base maps.** No streamed level has a building with floors (13 have
  floorless ones).
- **53 of them are vans' buildings** (29 maps; on URB_Bar four of its six), told as the compiler tells a van: most of
  the pieces its floors list are placed by one prefab with a car body.
- **16 buildings have a floor with no floor volume** (28 floors; F-86's count). They stay fixed.
- **338 buildings in 94 maps are left to edit**: base level, not a van's, a volume on every floor.
- **Not every volume is a box.** 19 building volumes and 241 of 1,178 floor volumes have a brush of more than six
  sides, a box with notches or an L (URB_Bar's main building: five of its eight floor volumes, the largest of 36
  sides); 108 buildings have at least one. Their world box is their bounds. Moved, such a volume keeps its shape;
  stretched by `DrawScale3D` its notches would stretch too, so the Build puts a plain box in its place.
- **Nothing else names them**: no Kismet names a building or floor volume with floors, and no export's properties
  reference one but its own building's `Floors` (every object reference of every export walked).
- No building with floors carries a tag other than its class's, and no floor has two volumes with the same box.
- 29 are UFOs (`IsUfo`).

### F-94: Generated area lights travel with glowing pieces between maps

**Verified** (12 November 2026, [EXP-49](experiments/EXP-49-prefab-area-lights.md)). A generated light can be
transplanted from its donor package and cloned for each prefab placement. Its `Owner` resolves to the destination's
`WorldInfo`, and its pose follows the verified emitter. Four live lights read back for three imported props. The
unlisted templates were excluded from both sides of the bake. XCOM loaded the baked fixture and showed a pool of
light on the asphalt below the visible floodlight.

### F-93: A prefab test with no aliens, no Meld and a sky crashed the game as the battle started
**Fixed** (12 November 2026: found in two runs of the user's, 18:51 and 19:00, the Farm UFO prefab; run 4, 19:18,
played: "worked this time").
- What: the stage loaded and showed, the squad spawned, then `Critical error` 3.7 s later, an access violation
  reading address 0x40 at XComEW.exe 0xcbca98 (at its own base; 0xf9ca98 as loaded), called from 0xb14118: **the
  addresses of EXP-30 run 1** (F-78), where a map with no record crashed with aliens on the map. Run 2 the user saw,
  for a split second, "an elongated mesh stretching out below, possibly from a soldier". The changes since the last
  good run (17:59): no lines (the planes hidden as before), two sky domes, the profile's alien type `eChar_None` (no
  pods, as the log shows) and the record's `MissionType=eMission_None` (no Meld, as the log shows).
- Cause, most likely: the record's kind. A map with no record reads as `eMission_None` too, and crashed at the same
  place. Not ruled out: an empty alien squad, the sky domes.
- Also found: the upper dome's copy seeded all 23,534 tiles of levels 1 to 17 (its box holds the grid), 32 s of the
  quick build's 44 and a rebuild of every tile at load, though the dome collides with nothing. Run 2 had that fixed
  and still crashed, so it is not the cause.
- Run 3 (19:04, a terror-site record, no Meld there either): no crash, but the battle never left the loading
  screen (the user closed it after a minute). The log: the game spawned a Chryssalid and a Sectoid with no squad,
  civilians with no looks (`XComCivilian.RandomizeAppearance` out of bounds: no civilian content on this path), the
  overmind divided by zero, then LWR's mutator re-ran its "loaded" step every 0.4 s. A terror site needs content a
  test doesn't load: out.
- Fix so far: `native_copy.collides`: a copy that collides with nothing seeds no tiles. The test's record is an
  abduction again (`installs.TEST_MISSION`), so Meld comes back, and the profile's alien type stays `eChar_None`:
  run 4 tells the two suspects apart (no crash: the record's kind was the cause; a crash: the empty alien squad).
- Run 4 (19:18, an abduction record, no aliens, the sky, the hidden ground): played, about five minutes, a normal
  exit. The log: LWR's pod mutator found no pods, its Meld mutator spawned Meld. So the cause was the record's
  `eMission_None`; an empty alien squad, the sky domes and the hidden ground play. Meld in tests stays open.

### F-92: A UFO's building made from nothing could not be built on the blank map
**Fixed** (12 November 2026: seen offline in a stage build of the Farm UFO prefab, fixed the same day; not looked at
in the game).
- What: the Build's light stage stopped with "bad property name" in `buildings.clone_volume`, setting the new
  building volume's `DrawScale3D`. It did so at 12 levels as at 18: every T2 test of a prefab with a UFO.
- Cause: the clone's edit sets `IsUfo`, a name the blank map's package doesn't have; the grower adds it, but the
  walker that then sets `Location` and `DrawScale3D` knew the map's own names only and could not walk past it.
  A plain building (no `IsUfo`) was not affected.
- Fix: `clone_volume` sets those two with a walker of the grower's names (the map's, then the ones added). The
  Farm UFO stage builds; its building volume reads back with `IsUfo` and both floors.

### F-91: The bake took a recipe light's source radius as 100, where the light saves 32
**Fixed** (12 November 2026: seen offline, writing the point light recipe, and fixed the same day at the user's
word; not looked at in the game).
- What: `native_lights.recipe_source_radius` looks for `lightSourceRadius` or a `lightmass` record at the top of
  the factory's recipe, finds neither (the recipe keeps `LightSourceRadius` 32 inside its component's
  `LightmassSettings`), and falls back to UDK's default, 100. The relight then bakes a recipe spot or point light
  with a source radius of 100 while the light written to the map says 32, as every placed light of the surveyed
  maps does. A copied light takes its template's own value, so only recipe lights differ.
- Effect, expected: softer shadow edges from a recipe light than from a copy of a placed one with the same
  values. EXP-26's recipe spot was baked this way and accepted.
- Cause: the writer was written before the factory, against a stand-in recipe with `lightSourceRadius` at its
  top (its test's), and the two never agreed on where the value lives. No test ran the real recipe that way.
- Fix: `recipe_source_radius` reads the value the recipe's component saves. Recipe spot and point lights now bake
  with 32, as copies of placed lights do; a baked recipe spot's shadow edges come out a little sharper than
  before. Checked with the real factory on the Bar (`test_native_lights.py`).

### F-123: A copied ambient sound and its original report one NetIndex in the log
**Accepted** (EXP-70 run 2, 17 November 2026).
- **Seen.** The game's log says `Error: (AddNetObject) Objects AmbientSoundSimple_5 and AmbientSoundSimple_0 have
  duplicate NetIndex 0` when the map loads and again after a save's load. `_5` is the project's copy of `_0`.
- **Cause.** A copy is cloned from its original's export, NetIndex and all. The index names an object to the network
  code, which a single-player battle doesn't use for a map's ambient sounds.
- **Effect.** None seen: both play as set (volume, reach and pitch each its own), before the save and after the load.
- **If it ever matters** (multiplayer maps): give a clone the next free NetIndex of its package.

### F-122: A particle parameter saved as a number where the system reads a vector is read
**Verified** (EXP-70 run 2, 17 November 2026).
- **The question.** 18% of the values the game's maps save on their effects are a number (`PSPT_Scalar`) under a name
  the particle system reads through a vector distribution. Is such a value live, or left over?
- **Seen.** A copy of URB_Bar's steam with Brightness 5 saved as a number is a bright white cloud; its twin with the
  map's 0.05 is a faint grey wisp. The same holds for a parameter the effect didn't save: a copy given Spawn 8 as a
  new entry is far denser.
- **So.** The editor's slider for such a value changes what plays, and the drawn likeness reads it as the number on
  each axis (`effects_sim.js sample`).
- **An earlier reading was wrong.** From the unedited map's pictures the steam at 0.05 looked too light for that
  value to count, and the likeness was first made to ignore it. The steam is lit by the scene as well: its colour
  parameter is what it glows with.

### F-121: A piece or effect from a third map could be staged with an earlier map's imports
**Fixed** (17 November 2026, offline, found while preparing EXP-69; not seen in the game).
- **Seen.** One build of EXP-69's project (effects and sounds of six maps into URB_Bar) staged URB_Boulevard's
  fountain sound with its node's class `Engine.SoundNodeWave` where the donor's is `Engine.SoundNodeAmbient`: the
  node read as a wave holding no sound data, so the copy had nothing to play. The same edit staged again came out
  right.
- **Cause.** The transplanter keeps, for each donor, which of the destination's imports stands for each of the donor's
  (`transplant.Destination.import_of`), and kept them by `id(donor)`. The staging opens one donor after another; once
  an earlier donor is freed a later one can get its id, and is then given the earlier map's imports for its own wherever
  the import numbers meet: classes, archetypes and outers named wrong. Whether it happens depends on how memory is
  reused, so one run differs from the next.
- **Reach.** Any build bringing pieces or effects from three or more maps, since the cross-map pieces (X4). Where the
  two maps' import tables agree at the numbers met (the low numbers, Core's and Engine's classes, often do) nothing
  shows; where they don't, a brought object can be of the wrong class. The cross-map experiments (EXP-37 to EXP-42)
  passed in the game; whether any of their builds met it is not known.
- **Fix.** The imports are kept by the donor's file (a donor with no file by the donor itself, held). A regression test
  gives two donors one id (`test_transplant.ImportsKeptByDonor`); EXP-69's edit staged five times as the Build stages
  it gives every brought object (141) its donor's class and archetype.

### F-120: Under Long War the Skyranger is gone after a reload, its shadow left on the ground
**Accepted** (17 November 2026, EXP-68 run 1: Long War's own behaviour, not the build's).
- **Seen.** In EXP-68's battle on a variant of URB_Bar, the Skyranger stood at its landing at the start; after a save
  and reload it was gone, its shadow still on the ground.
- **Cause.** Long War's landing-zone mutator (`XComLZMutator`) runs `HideDropShip` whenever a battle's level loads,
  whatever landing it picks: it hides and destroys every actor of the grounded Skyranger's prefab by archetype (the
  ship `PRE_SkyrangerGrounded_*`, its emitter, its idle sound after stopping it, and the dust
  `ARC_Skyranger_Ground_Periphery`). The ship seen at the start is the intro's dropship, in the streamed
  `CIN_DropshipIntros`, parked where its flight ends. A reload doesn't stream the intro again (the log shows no
  `AddStreamingMap` for it, though the travel names it), and the mutator's `PostLoadSaveGame` runs `HideDropShip`
  again. The shadow is baked into the ground's lightmap from the map's own grounded ship.
- **Evidence.** The lab game's logs: EXP-68 (`URB_Bar_X68`) and an unedited map (`URB_OfficePaper_EWI`, 15 November)
  show the same sequence on a reload. Mutator source: `XComLZMutator.uc` (`HideDropShip`, `PostLoadSaveGame`), kept in
  `private/research/evidence/upstream/`.
- **Plain EW** has no mutator: the map's Kismet hides the grounded ship for the intro (`CIN_HideForIntro`) and shows it
  after (`CIN_IntroFinished`), and nothing hides it on a load, so it most likely stays (not played).
- Not the editor's to fix: a ship of the variant's own would stand at the map's landing even when Long War picks
  another, and beside the intro's parked dropship at the start.

### F-119: A moved landing leaves the grounded Skyranger's dust where the landing was
**Fixed** (17 November 2026, found offline in FX3's clear and landing check; fixed offline in export 35 on
18 November; not seen in the game).
- **Seen.** A cleared Bar with its landing moved four tiles east and turned (`clear_bar_project.py`'s first zone), built
  quick and read back: the grounded Skyranger (`XComLevelActor_138`), its idle lights (`Emitter_78`) and its idle sound
  (`AmbientSoundSimpleToggleable_0`) moved by one transform, from (560, -2971) to (-188, -1521), but `Emitter_0`
  (`P_Skyranger_Ground_Periphery`, the dust the map's script hides for the intro and shows after it) stayed at
  (512, -2112). The editor's Effects view draws it there too, so the view and the Build agree.
- **Cause.** The landing's move (`native_spawns.py`) carries the actors the landing names by role (export 22's
  `landingRole`: the Skyranger, its emitter, its sound, the spawn points); the dust is a landing actor only by its
  archetype (`native_copy.LANDING_EXTRA`, `effects_metadata.LANDING_EXTRA`), which keeps it through a clear but gives
  it no role, so nothing moves it.
- **Fix to try.** Carry `LANDING_EXTRA` actors with the moved landing by the Skyranger's transform, give them a role in
  the export (say `dust`) so the page shifts their markers with the zone, and look in the game at a moved landing after
  the intro.
- **Fixed** in export 35 (18 November 2026): `scene_metadata.landing_metadata` lists the dust with the nearest
  grounded Skyranger (within 2,500 units) as role `dust`, so `native_spawns.plan` moves it with the ship, its lights
  and its sound, and the page shifts its marker with the zone. `test_native_spawns` BarMoved reads it back at its new
  place (15 actors moved). Not looked at in the game: under Long War the mutator destroys it on every load anyway
  (F-120), and the hidden game has not played plain Enemy Within.

## Toolchain

### F-117: A variant replacing Commercial Alley Redux left a new campaign's first mission with no map
**Fixed** (17 November 2026, offline: `test_manager` `test_a_variant_replacing_the_first_missions_map_takes_its_record_name`
and `test_a_packs_scripts_give_the_first_missions_name_to_the_variant_that_replaces_its_map`; not played).
- **Seen.** A user installed a map pack with its `Install.cmd`: 15 maps made with 0.5.2, each replacing its
  original, one of them a variant of `URB_CommercialAlley_EWI`. A new campaign's first mission didn't start.
- **Cause.** The first mission asks for its map by the record's DisplayName,
  `URB_CommercialAlley_EWI (Commercial Alley Redux) |0` (`XGGeoscape.TakeFirstMission` calls `DetermineMap`, EXP-03),
  although that record is in rotation. A replacing variant kept the base map's DisplayName only on records out of
  rotation (council and story missions), so its abduction record took a name of its own, and replacing commented the
  original's record out. No live record had the name, and the travel falls back to `Command1` (EXP-03, route 2). The
  pack's scripts and the editor's Install in the game (Replace) both did it: both take the records from
  `installs.rotation_plan`.
- **Fix.** `installs.FIRST_MISSION` names that record (LWR's name, and plain EW's guessed one without ` |0`). In replace
  mode the variant's record that stands for it keeps that DisplayName and stays in rotation (`rotation_plan`,
  `_rotation_from_build`); the record counts as asked for by name (`byName`, `firstMission`), and the Replace
  warnings say the variant plays the first mission. Beside the original (Additional) nothing changes: the original
  keeps the first mission. The user's pack was mended by hand, with that record's DisplayName changed in its
  `pack.json`; a pack made before the fix needs the same.
- A replacing variant whose build has no abduction record left the first mission without a map too: F-118.

### F-118: Replacing commented out the base map's records for missions the variant has no record for
**Fixed** (17 November 2026, offline: `test_manager` `test_a_variant_for_other_missions_leaves_the_first_missions_record_in_use`
and `test_a_packs_scripts_leave_the_records_its_maps_have_none_for_in_use`; not played).
- **Cause.** A build has records for its project's missions only (mission types plan, D4), but Replace commented
  out every record of the base map: the editor's install by the base map's name (`_sync_off`), a pack's script by
  the `Name` field. A mission the variant has no record for lost the map altogether: harmless for a rotation
  mission (other maps serve it), but a mission that asks for its map by name found none. A variant of
  `URB_CommercialAlley_EWI` for covert extraction only left a new campaign's first mission with no map (F-117),
  and one leaving out a council mission left that mission with none.
- **Fix.** A rotation install records the base map's records its build has records for (`standsFor`, from
  `recordMissions`); only those are commented out (`installs.replaced_records`, `_sync_off`), and the others stay in
  use. An install written before `standsFor` still replaces every record of its base map. A pack lists them in
  `pack.json` (`switch`, the display names `Install.cmd` comments out; `keep`, the ones it leaves), and a pack from
  before `switch` comments out every one. The Replace warnings name the missions left to the original (and say when
  the original plays the first mission); the project manager works them out from the last build's records. The Game
  maps window marks only the replaced records.

### T-45: The game crashes as it starts when Windows sees no mouse
**Fixed in the tool** (18 November 2026, five hidden starts from 09:09, EXP-72 run 11's two among them; no EXP file).
- **What**: every hidden start from 09:09 crashed about 3.3 seconds in, before the main menu, URB_Bar's plain start
  too. `Launch.log` ends `Init: XAudio2Device initialized.` and then `Critical error ... Address = 0x11fb6b8 [in
  ...\XComEW.exe]`. DXVK's log stops before `Creating device`, and DXVK's mode options (`d3d9.modeCountCompatibility`,
  a forced refresh rate and aspect ratio) changed nothing. The same starts worked at 04:08.
- **Cause**: the dump shows an access violation reading address 0 at `XComEW.exe+0x31b6b8`. The code there is the
  client's input set-up: `IDirectInput8::CreateDevice(GUID_SysMouse, &device, NULL)`, then `device->SetDataFormat`
  without a check that a device came back. At the time Windows had no mouse and no keyboard: `GetSystemMetrics
  (SM_MOUSEPRESENT)` was 0, and the HID mice and keyboards were not present (switched to another computer, asleep or
  unplugged). So CreateDevice gave no device and the next call read through nothing.
- **Fix**: `tools/lab/hidden_game.py` counts Windows' raw input devices before it starts the game. With a mouse or
  keyboard missing it puts a stand-in `dinput8.dll` beside the game for the run (`tools/lab/StandInInput.c`, built
  into `<lab>\\bin` by `build_stand_in_input.py`). The game imports `DirectInput8Create` from `DINPUT8.dll` by name,
  so it loads that DLL first. The DLL hands every call to Windows' own `dinput8.dll` and gives a still mouse or
  keyboard (attached, never moving, no key down) where Windows has none, and writes what the game got to
  `<out>\\input.log`. Without the DLL, no mouse stops the run with the reason. The `game-test` skill says so under
  "Before a run".
- **Verified** (18 November 2026, the mouse and keyboard there, the stand-ins forced by `--stand-in-input`): outside
  the game a 32-bit check (`tools/lab/tests/StandInInputCheck.cs`) got both stand-ins and every call the game makes
  answered. In the game, URB_Bar started to turn 1 with the squad and the interface drawn; `input.log` showed the
  stand-in mouse asked for twice and the keyboard once; `goto` moved a soldier two tiles, and Escape opened the
  pause menu. A start with the devices really gone hasn't been played; the DLL takes the same path then (Windows'
  CreateDevice fails, the stand-in is given).
- A player's own game has a mouse, so this only stops unattended runs.

### T-46: In a hidden run, every load of a save with aliens in the battle crashes: DXVK's texture budget
**Fixed** (18 November 2026, EXP-72 runs 12 to 16; the mouse was a wrong lead).
- **What**: in a hidden run the game crashed about 1.4 seconds after a save's `LoadMap ... LoadingFromShell=1`, just
  after `XGBattle_SP.PostLoadSaveGame`, with an access violation, nothing in `Launch.log` and no dump: Long War's
  reload of Police Station's data recovery (runs 12 and 13) and a quicksave loaded from the pause menu on URB_Bar
  (run 14, a traced rerun, and a rerun with the mouse and keyboard there and no stand-in). The battles started and
  played; only the loads crashed.
- **Not the mouse**: the first runs had no mouse in Windows (the stand-in, T-45), and every load that had worked
  before had a real mouse, which pointed there. But the load crashed with the real mouse too, and the same load of a
  battle **without aliens** went through (run 15). Every load that had worked (EXP-70, EXP-71, the 17 November save
  checks) was of a battle without aliens; every one that crashed had aliens, and Long War's pod mutator's own pods.
  In a visible game Long War's reload of a data recovery with aliens had gone through (EXP-57 runs 2 and 4).
- **Where**: the stand-in DLL's crash log (`--crash-log`, below) named it: a thread of the game's own (not the one
  that made DirectInput) read address 0x61300001 at `XComEW.exe+0xf1331`, from code at `+0x222ee6` and `+0x300639`
  under the thread's start at `+0xed9ed8`; `edx` held 0x61300000, a block of memory no longer there.
- **Cause** [inferred from the fix]: DXVK, which the hidden runs need (T-43), keeps only so much texture memory
  mapped in a 32-bit game (`d3d9.textureMemory`, 100 MB by default) and unmaps the rest; a load of a battle with
  aliens brings in many textures at once, and a thread of the game's then read one DXVK had unmapped. Which texture
  and which thread is not read.
- **Fix** ([hidden_game.py](../tools/lab/hidden_game.py) `dxvk_config`): every hidden run gives DXVK its own
  `<out>\dxvk.conf` (`DXVK_CONFIG_FILE`) with `d3d9.textureMemory = 0`, the budget off. Also `--crash-log`: the
  stand-in DLL stands beside the game in any case and logs the run's first faults to `<out>\input.log` (thread,
  code, module and offset, what it touched, registers, the module addresses on that thread's stack).
- **Verified**: run 16, the same Bar quicksave and load with aliens, went through twice, once with the setting given
  from outside and once through the tool's own file (`Found config file: <out>\dxvk.conf` in DXVK's log; 18 units
  read back after the load). Before it every load with aliens had crashed (six of six).
- **Known gap**: with the budget off the game's textures all stay mapped in its 32-bit address space; a long
  session might run out of it. Not seen in runs of a few minutes.

### T-44: Police Station's Data recovery never begins on the Play in game path: its covert operative copies a SHIV
**Fixed** (18 November 2026: EXP-72 runs 12 and 13 began; runs 5, 10 and 11 had not).
- **What**: on URB_PoliceStation's Data recovery (EXALT, `eMission_CaptureAndHold`) the loading movie never stopped.
  Long War never saved and "Mission Started" never came: `why=PostLevelLoaded` repeated every 0.39 seconds for four
  minutes. The same on the editor's variant and on the map as installed, with saving on (as an EXALT mission needs
  under Long War, F-109), and with the mission's open-line options too (run 11).
- **Cause** (read from the game's script and the logs): with no campaign behind the battle,
  `XGBattle_SPCovertOpsExtraction.SpawnCovertOperative` makes the stand-in operative with `CreateDebugCovertOperative
  (squad member 0)`, which copies that unit's looks (`XComHumanPawn(kTemplate.GetPawn()).m_kAppearance`). The editor's
  test squad had "Tracks", a SHIV (`iType=3`), first. A SHIV's pawn is no human pawn, so the copy read nothing
  (`Accessed None 'm_kPawn'`), and the operative asked for a body, head, hair and voice of id 0
  (`CacheRequiredArchetype: Requested missing ... content: Id=0`), which don't exist. The battle waited for them on
  its loading screen. A MEC trooper's pawn is a human pawn (`XComMecPawn extends XComHumanPawn`), so only a SHIV does
  this. Data recovery's battle class inherits covert extraction's, so both kinds have it. The two starts that began
  on 15 November had a soldier first.
- **Fix** (play.py, missions.py, squadrecords.py): a play of a kind with a covert operative (data recovery, covert
  extraction) lands the squad's first soldier or MEC trooper first, and the play's notes say who and why. With only
  SHIVs the play goes ahead and says the battle will stay on its loading screen.
- **Verified**: run 12 (the editor's squad with Iron Fist first): no `m_kPawn` warning and no content of id 0; the male
  operative took Iron Fist's head and hair; the loading movie stopped at 8.3 seconds, Long War saved at 15.0, and
  "Mission Started" came at 16.4. Run 13 (six soldiers) the same. Both then crashed in Long War's reload, a separate
  matter of the hidden runs (T-46, fixed: DXVK's texture budget).

### T-43: The game runs on a hidden desktop only through DXVK; there it draws, takes console commands by window messages and saves its own shots
**Verified** (17 November 2026, the lab copy, five starts; no EXP file).
- **With DXVK it runs.** DXVK 3.1.1's 32-bit `d3d9.dll` (DirectX 9 over Vulkan) beside `XComEW.exe`, the same start:
  compatibility level 2/2/4 as on the screen, the main menu after 3.8 seconds, still running when the timeout ended it.
  - A battle: `-EXEC=<file>` with `set XComContentManager bAllowJITLoad True` and `open URB_Bar` loaded the map and
    stood at turn 1 with the squad and the interface drawn, 75 seconds after the start.
  - Commands: a helper on the same desktop posted `WM_KEYDOWN`/`WM_KEYUP` to the game's window (class
    `LaunchUnrealUWindowsClient`): backslash, the command's keys, Enter. The log shows each (`Console Command Use:
    shot`, `togglefow`), and the fog was gone in the next picture. No window is in front on that desktop
    (`GetForegroundWindow` is 0) and the game doesn't mind. Only keys were posted: no mouse, and no character that
    needs Shift (an underscore), which a commands file run with `exec` gets round.
  - Pictures: the game's own `shot` writes `XComGame\Screenshots\PCConsole\ScreenShotNNNNN.bmp` at the asked size
    (1280 by 720, though the window's client area was 1024 by 576) and they show the game as it looks on the screen.
    `PrintWindow` from outside gives a black picture.
  - Left as it was: the DLL is out of the lab copy again (DXVK is unpacked in `<lab>\dxvk`), `XComContent.ini` put
    back after the battle (F-73). Steam's shader cache for the game got DXVK's pipelines.
  - **The tool** (17 November, later): [tools/lab/hidden_game.py](../tools/lab/hidden_game.py) puts the DLL in for
    the run, starts the game through [GameRemote.cs](../tools/lab/GameRemote.cs) on the desktop `XComLab-Game`, does
    a list of steps (wait, wait for a log line, a console command, a key, a shot) and puts back the DLL and every
    config file the run changed (`XComContent.ini`, and `XComInput.ini` too). Three runs with it:
    - the main menu: Right twice and Enter opened Options, so menus go by the keyboard;
    - a battle on URB_Bar: the log's `m_bTacticalIntroDone` came 21 seconds in and the first shot at 73 showed turn
      1; a console command written to a file and run by a typed `exec <file>` worked (`ToggleFOW`: the bar's inside
      showed in the next shots; a `getall` with a wrong property name was answered in the log); Tab picked the next
      soldier (his name and weapon in the shot), E three times and G four turned and pulled back the camera.
  - **No mouse there.** Posted `WM_MOUSEMOVE` and button messages at the main menu's Options button did nothing (no
    highlight, no screen), and `SetCursorPos` and `GetCursorPos` are refused on a desktop that isn't the one shown
    (error 5), so the game has no cursor to move. Pointing goes by the camera instead (below).
  - **Turns played there** (17 November, evening; URB_Bar, the default LWR test squad, two sessions of
    `hidden_game.py --serve` with steps sent as the answers came back):
    - Where the mouse is: the game's `UIMouseCursor.m_v2MouseLoc` stays 0,0 (a timer reads it from the interface ten
      times a second, so `set` doesn't hold), and the tile under the picture's top left corner is where its 3D cursor
      goes, every frame. Edge scrolling stays off (the mouse never left its first place).
    - Pointing at a tile: with the camera straight down on the active soldier (`SetOverheadCameraParameters <fov>
      1256 -89`), the corner's tile lies 1440 × tan(fov / 2) world units from him, in the direction of the camera's
      yaw plus 72° (`SetCameraYaw`; yaw 0 gave the tile 96,288 from him, 90 gave -288,96, 180 gave -96,-288, 270 gave
      288,-96). The cursor's place read back (`getall XCom3DCursor Location`) was the asked tile each time, once the
      camera had stopped turning.
    - A look-at (`ViewLocation`) is no way to point: while one is up the camera hides the cursor
      (`m_bHiddenOverride`) and no path is built.
    - The order: `Right_Mouse_Button_Press` and `Right_Mouse_Button_Release` as two console commands. The log:
      "Alpha moved 2 tiles", and his place was the tile's (1583,911, then 1391,1103 by `hidden_game.py goto`). The
      controller's `A_Button_Press` does nothing while the mouse is on (the game drops controller events then), and
      `UseController` stops the game at "Please Reconnect Controller".
    - **The game's own squad for this path can't walk**: its soldiers stand and show, but their animation trees have
      no movement node (`Accessed None 'Animations'` in `PostInitAnimTree` as they spawn), so an ordered move starts
      and never ends (`XGAction_Move_Direct`, `Accessed None 'MovementNode'` every frame) and the console stops
      answering. With the test squad's records (`--squad`) the soldiers walk.
    - Aliens: `DropSectoid` with the cursor aimed (`hidden_game.py aim`) put a Sectoid on that tile.
    - A shot: key 1 opened Standard Shot on it (100% to hit), Enter fired; the log has the hit, 9 damage and the
      death.
    - A grenade: its key opened the view aimed at the thrower's own tile, and Tab did not move it; the same camera
      commands while the view was open moved the aim onto the Sectoid (the view stays on the thrower), Enter threw,
      a second Enter answered the box about a friendly unit in the blast. The log: 29 damage and the Sectoid's
      death, 16 to the soldier beside it.
    - The turn: `EndTurn` ran the aliens' turn (15 seconds) and XCOM's turn 2 began with a pod revealed.
    - Read back: `getall XGUnit m_bInCover`, `m_iCurrentCoverValue` (50 for the one soldier in cover) and
      `CurrentCoverPointFlags`; `getall XGUnit m_arrVisibleEnemies` printed nothing for anyone (an array `getall`
      doesn't print, or nobody in sight: not told apart).
  - **A ladder, a roof and the inside of the bar** (17 November, later; a third session):
    - The storey the cursor picks on is the mouse wheel's count, `XCom3DCursor.m_iRequestedFloor`:
      `Mouse_Scroll_Up` and `Mouse_Scroll_Down` as console commands change it by one and it stays (the F and C keys
      did nothing). On 0 the pick over a building goes through its cut-away roof to the ground floor inside (URB_Bar
      at 431,1199: height 81); on 1 the same tile read 221, on 3 the bar's roof (335,1103: 466).
    - Up the ladder: Alpha, teleported beside the ladder at 432,1296 (`TeleportToCursor` with the cursor aimed, then
      Tab round to him again), was ordered to the roof tile 335,1103 on storey 3: "Alpha moved 5 tiles", and he
      stood at height 472 on the roof above the ladder (the shot shows him there). The game took the ladder by
      itself. Orders to 431,1199 on storey 1 and to tiles the pick could not reach gave no move: the first has no
      path (the readout's `PathActionEmpty: True`), though the cursor stood on it.
    - Inside the bar: Delta, teleported to -241,1103 on storey 0, walked to -433,1007 ("Delta moved 2 tiles") and
      the shot shows him on the bar's floor between the counters, the roof cut away. A tile with a counter on it
      (47,1199: height 148) took no order. Bravo's order to -145,1295 ended on the pavement outside the fence, in
      cover (value 50): that tile is outside, the bar's floor starts north of it.
    - After a move the game goes on to the next soldier, and one who has no move left is not in Tab's round any
      more. A look-at (`ViewLocation`, then `RemoveLookAt`) still serves to take a picture of a place.
    - Aiming at a roof from 26 tiles away failed (the aim's correction ran off: "59 tiles away"); from three tiles
      it held. `hidden_game.py`'s `--floor` set the storey to 3 and back to 0 in a fourth, short session.
  - **Sounds** (17 November, night; a session on URB_Bar without aliens):
    - The console's `ListWaves` writes the sounds playing now to the log, a line each: whether it started, a time,
      the volume, the wave and the actor it belongs to. At the landing: the dropship's idle (0.09), two ambience
      loops and the music of the sound manager (0.18, 0.60, 0.60). `ListSounds` lists loaded waves only and
      `ListAudioComponents` every component, playing or not: neither says what is heard.
    - The game hears from the camera, not from the place it looks at. The map's five `AmbientSoundSimple` have a
      reach of 300 to 1000 (`getall SoundNodeAmbient RadiusMin`, `RadiusMax`, `SoundSlots` give radii and wave), the
      play camera stands 1256 from what it looks at, and none of the five was in the list with the camera looking
      straight at them.
    - With the camera brought closer (`ViewLocation` at the sound, `SetOverheadCameraParameters 70 <distance> -45`)
      the bar's music (`SoundBarMuzak.BarMuzakStereo`, radii 550 and 1000) was listed at 0.60 from 400, 0.40 from
      700, 0.27 from 800, 0.07 from 950 and not at all from 1256; the machine hum on the roof (radii 100 and 300) at
      0.32 from 150. So the list follows the radii, and 0.60 is a full ambient sound here.
    - `hidden_game.py listen <folder> <x> <y> <z> [--distance <d>]` does this and prints the list.
    - Nothing was recorded: the list is the engine's own account of what plays, not a recording.
    - **Muted for the run** (later the same night): `GameRemote` mutes the game's audio session (Core Audio,
      `ISimpleAudioVolume.SetMute` on the session of the game's process on the default output) as soon as it exists,
      1.5 seconds after the start, and unmutes it before ending the game, because Windows keeps an application's
      mute for its next start. A battle on URB_Bar run so: "sound muted", `ListWaves` answered as before (two
      ambience loops 0.18 and 0.60, the music 0.60), "sound unmuted (1 session)". Not heard by anyone: that the
      speakers were silent rests on Windows taking the mute. A run ended from outside keeps the mute until the next
      run ends by itself or the mixer is used.
  - **Saving and loading** (17 November, night; `hidden_game.py --saving`, URB_Bar without aliens): the start F-89
    found for the editor's Enable saving works there too. The game stood at its main menu, logged in ("Obtained
    steam user stats" 3.7 seconds in), F5 as a posted key ran the battle's commands and the map loaded. Alpha
    walked to -2257,1009; F10 quicksaved (the log's checkpoint lines, the save in the load list as "QUICKSAVE");
    he walked on to -2065,1009; Escape, Down twice, Enter opened Load Game with the quicksave first, Enter and
    Enter again at "Confirm load game" loaded it (`LoadMap: URB_Bar?...LoadingFromShell=1`), and 60 seconds later
    he stood at -2257,1009 again, the others where they were. An order after the load moved him ("Alpha moved 3
    tiles"). The run put back the config it changed (`XComLZMutator.ini` and `XComMaps.ini` too, which the load
    wrote), `profile.bin`, and `save8`, the slot the quicksave had taken from an older save.
    - An order onto a tile with a prop (the cursor's height 128 there) ended on a tile beside it, twice.
  - Not tried: stairs inside a building, a climb down, more than one game at once, the LWR install.
- **Without DXVK it doesn't**, the first two starts:
- What: `XComEW.exe` started by `HiddenRun` on a private desktop (`SteamAppId` and `SteamGameId` set to 200510,
  `-FROMLAUNCHER -nostartupmovies -nohomedir -forcelogflush -windowed -ResX=1280 -ResY=720`) logged `Failed to get
  Caps bits info from the D3D Object`, pixel and vertex shader version 0, compatibility level 0, and then nothing
  more: it stood for 70 seconds (a box nobody sees, as in T-01) until the timeout ended it.
- With `-dx11` added it took the DirectX 11 path (`Shader platform (RHI): PC-D3D-SM5`) and stopped after 3 seconds:
  `Failed to compile global shader FResolveVertexShader` (`Common.usf(789,55)`: undeclared identifier
  `ViewportPositionScaleBias`). The shipped game has no DirectX 11 shaders, so T-01's way out is closed for it.
- The second start rewrote the lab copy's `XComEngine.ini` (its compatibility levels unchanged: 2, 2, 4) and left a
  crash dump in its `Logs`.

### F-116: A wall's end on a tile edge reaches a unit into the next tile; a one-tile doorway with no door gives cover toward its sides
**Fixed** for the ends (17 November 2026; seen in [EXP-67](experiments/EXP-67-fracturing-wall-poc.md) run 1); the
doorway's cover is the game's own rule, **open**.
- **Seen.** In EXP-67 run 1 the user found "a tile that was acting like an invisible cover/blocker near the custom
  door gap": with the move cursor on the doorway's tile, its picture shows a shield toward each side of the doorway.
- **Cause.** The game counts its tiles from a unit under the grid the pieces stand on (`WorldBounds.Min`,
  [cover-build.md](native/cover-build.md)), and its occupancy test is a box the size of the whole tile against each
  piece's collision (section 2). So a solid whose side lies on a piece-grid edge reaches one unit into the tile column
  beyond it, and that tile is marked partly occupied (`0x8000` with `0x10000`): every direction gets a cover test
  there, and its neighbours test toward it. The custom wall's doorway side at x −96 and its east end at x 192 did
  this. The game's test, run on the wall's own triangles (all fragments standing), marks the doorway's column (game
  tile x 28) and the column past the east end (x 31) partly occupied on both sides at every level, and the user's
  save shows both so at level 1, where the wall still stood. The doorway's tile then gets cover toward both of its
  sides, each 47 to 49 units from its centre. The twin, whose ends stand inside its tiles, marks exactly its own.
- **The game's walls.** Their inside walls end 8 short of their tile edges: on URB_Bar, URB_PoliceStation and
  URB_CommercialStreet no wall end lies within 6 units past a tile boundary. Their openings' sides do lie on the
  edges (242 of the openings in seven URB maps' fracturing walls; the bar's `URB_BarIntWallA` has its jambs'
  collision boxes exactly there, 176 tall as ours), and their doorway tiles are partly occupied likewise (24 of 26
  measured). But 68 of the 74 spilled doorway tiles measured have a door in them, and 67 of those carry no cover. No
  open one-tile doorway at ground level was found in the game's fracturing walls to compare with.
- **Fix.** [frac_wall.py](../tools/bake/frac_wall.py): a wall's numbers are its tile edges, and its solid stops
  8 short of each end (`RECIPE['endInset']`, `solid_wall`), as the donor's −376 and 184 for −384 and 192. The
  compiler's box for the copy and the shortest wall (40) follow; an opening's sides stay where they are given, as the
  game's do. Checked: the same test on the rebuilt custom wall marks its own four columns only, the doorway's
  included; test_frac_wall, test_frac_walls and test_compiler_generated.
- **Open.** The doorway tile's cover follows from the game's own rule for a tile between two pieces of wall. The
  game's doorways hold doors; whether a door in this one (a copy of one of the bar's) takes the cover away is not
  tried. Since the same day the editor draws a made wall as it is built, so the doorway shows there and a door can be
  placed in it. The user then put a door in it (EXP-67, run 2): "doors seem to work well in the custom walls too";
  their pictures show it shut beside a soldier in cover and open with a soldier at the doorway. Whether the doorway
  tile still gives cover with the door in it was not told apart.

### T-42: Generated geometry is currently box-specific; custom visible walls and terrain need another authoring path
**Open** (16 November 2026; [EXP-66](experiments/EXP-66-custom-geometry-feasibility.md), read-only audit and code
inspection, no new visible mesh played).
- The existing cover-block writer creates new cooked meshes and BodySetups, confirmed in game in EXP-31/EXP-32.
  It writes hidden boxes with a fixed triangle collision tree, one overlapping UV channel, no bound section material
  and no component texture lightmap. It is not a general mesh importer.
- The farm's `TornEarth.Meshes.SmallscoutRamps` is a StaticMesh: 1,123 vertices, 1,788 triangles, two UV channels and
  ten simple collision elements. Replacing this slope does not require native Terrain/Landscape support.
- A visible-mesh writer needs qualified material binding, render/collision geometry, lightmap UVs and allocation,
  actor flags and tile rebuilding. `relight.prepare_component` has fresh lighting but requires an allocated LOD-0
  texture lightmap. An opening must remain open in collision and pass the game's tiled movement/headroom checks.
- Custom fracturing also needs native fragment topology, component state and the actor's fragment columns and
  neighbours (F-69). Four sampled Bar wall meshes have 30-77 fragments; reading/carrying their data does not author
  it for a changed shape. Whole-panel destruction is a possible intermediate experiment, not yet qualified.
- Checked: [repeatable audit](evidence/custom-geometry-audit.py), [measurements](evidence/custom-geometry-audit.json)
  and the existing cover-block suite (36 tests passed, no skips). F-81/F-83 still constrain terrain floor and cover.
- Next evidence needed: a visible generated primitive, a wall aperture and a terrain wedge, with full lighting,
  movement, cover, sight, building cutaway where applicable, and save/reload checked in game.
- **Review, 16 November 2026** (read only: the notes below and a scratch count on URB_Bar and CSmallScout_Farm,
  which the audit script is to take over; nothing built or played):
  - Collision is two things. Every tactical test (occupied, floor, cover, the walking and sight bits) reads a mesh's
    simple collision, its BodySetup's hulls, and never its triangles
    ([cover-build.md](native/cover-build.md), sections 2, 4 and 5; F-80, F-83). So one hull for each convex solid of
    a generated shape decides play, and a wall cut into boxes at its openings has hulls that cannot span one. The
    triangle tree only has to be sound data.
  - The triangle tree is regular: 6-byte nodes, 8-byte triangles, and on all 579 static meshes of the two maps the
    node count is the smallest power of two that gives at most five triangles a node (11 triangles: 4 nodes; 5,118:
    1,024; 5,166: 2,048). The cover box's 12 triangles and 4 nodes fit. How the triangles are sorted into the nodes
    is not read yet.
  - The lighting list has one item more: the dominant light. Of the two maps' components with a texture lightmap,
    all but five either have a shadow map of the dominant light or list irrelevant lights, the dominant light among
    them in 470 of the 499 lists. A generated piece needs one or the other, as well as its lightmap.
  - Breaking a generated wall a panel at a time rests on what the Build already makes: a destructible prop whose one
    destroyed event hides it, taking its collision and cover (the breaking cover block, F-101). Shown, with a
    toughness that takes damage, it is not played yet.
- **What one of the game's fracturing walls is** (16 November 2026, read only, a scratch count; the user asked
  whether a generated wall can look and break as the game's do, and for a proof of concept of that first):
  - `URB_Bar_FRAC.Meshes.URB_BarIntWallB_FRACTURED` (560 by 24 by 400, 902 triangles) has six sections: each side's
    face in two (lower and upper storey), one for the trims (skirting, cornice, end caps, 4 units proud), one for
    the faces inside the wall. The mesh's sections name no material: the component's `Materials` does, with a
    `DestroyedMaterials` list beside it (the same names with `_Destroyed`). Its vertex colours are one value; 25 of
    the Bar's 44 fracturing meshes have varying ones.
  - Its 30 fragments are irregular chunks about 100 by 100 through the whole thickness, each saving its centre,
    box, the fragment across each face with the shared area, three flags and an outward direction; all can be
    destroyed, none is a root, there is no core, and EW's added index is -1 on every one. The actor is an
    `XComDecoFracLevelActor` with a toughness of the game's table (`GameData_Toughness.Toughness_MASONRY`, health
    80), rubble meshes and impact effects.
  - `FragmentColumns`: one for each tile along the wall and each storey of 192 (18 here). `FragCache` holds
    `{FragIndex, MinZ}` for each fragment in the column, sorted by `MinZ` on every column of three maps (2,520).
  - "The fragments whose box overlaps the column's box" gives exactly the saved list on 951 of URB_Bar's 1,037
    columns and 934 of URB_PoliceStation's 1,172, the misses going both ways (a rule on the true shape would miss
    so against one on the boxes). On CSmallScout_Farm, whose fracturing pieces are the UFO's, it gives 24 of 311:
    those follow something else. Unlike the neighbours' lists (F-69), a column's own fragments look derivable.
  - Not known: what the game's code expects of a fracturing mesh beyond its saved data, and whether its checks go
    through the triangle tree a fragment at a time (then the tree's order matters for these, as it does not for a
    plain piece).
- **The proof of concept, built** (17 November 2026, offline: the custom geometry plan's section 0, stages F0 to F3;
  [EXP-67](experiments/EXP-67-fracturing-wall-poc.md) prepared, not played):
  - The audit over the install's 151 maps ([frac-wall-audit.py](evidence/frac-wall-audit.py),
    [its numbers](evidence/frac-wall-audit-2026-11-17.json)): every one of 25,209 static and 1,679 fracturing meshes
    is written back from its numbers byte for byte (tools/bake/gen_mesh.py). On all 664 fracturing meshes the node
    count follows the static rule, the last node is zero padding, and a collision triangle's fourth value is its
    section's slot times the fragment count plus its fragment (858,183 of 858,183). The collision triangles are the
    index buffer's on 646 of them, never in its order; the inner nodes narrow on all but 50 of 249,031 (the byte
    rule is read, its rounding is not pinned).
  - The columns of the 644 placed walls (246 meshes named "wall"): 13,392 columns. The box rule gives 11,069 of the
    11,463 a tile long and a storey tall, 11,074 of all; every column of 521 walls. The rule on the true shape is
    worse (8,409). A column's `MinZ` is its fragment's lowest corner (57,112 of 57,112, within 0.01) and `FragCache`
    is sorted by it (13,392). The component's `FragmentBoundsMinZ` and `MaxZ` are the fragments' world heights (620
    and 621 of 621) and `NumResourceIndices` the index count (644 of 644).
  - Built on that (tools/bake/frac_wall.py, frac_walls.py): a wall from its numbers on the donor's six slots, its
    cross-section and texture repeats, Voronoi fragments with their inside faces, records and neighbours, lightmap
    coordinates, one collision box for each solid round its openings; in the map, the donor's clone given the mesh,
    its body setup, the component's numbers and painted colours (the donor's LOD 0 overrides all 1,053 of its
    vertices' colours), its columns by the box rule, lit from nothing. The twin (the donor's size) has its box,
    30 fragments; the custom wall (four tiles, a doorway) 27 and 3 boxes. Every fragment is closed, the neighbours
    mutual, every triangle faces out; the built map reads back whole and its export shows the walls on the donor's
    materials.
  - Left as they are, for the run to judge: the tree's nodes don't narrow (every check tests every triangle); the
    lightmap packing leaves about 30% of its square unused; the columns' lists of props and neighbouring walls are
    empty (F-69).
  - **EXP-67 run 1 passed** (17 November 2026, played by the user: "all checks out in game"): the twin looks like
    the reference beside it, all three break under rifle fire and grenades, cover, sight and walking through the
    doorway and the holes, and a save and reload with them broken. One tile at the custom wall's doorway acted as
    invisible cover (F-116, its end part fixed). By the plan's section 0.2, both questions pass. Run 2: a door in
    the custom wall's doorway works. The user: "I think the POC was successfull". Still to learn, for walls beyond
    the proof of concept: recipes for other walls (outside walls, other heights), joints and corners (the columns'
    neighbour lists), walls inside buildings (cutaway), and whether a door takes the doorway tile's cover away.

### T-41: Map grid snapped back on maps past 128 tiles at their own size
**Fixed** (16 November 2026, seen by the user on a temple map).
- **Seen.** On TempleShip the rail's Map grid drew a larger grid while a handle was dragged, then snapped back to the
  map's own size on release, and nothing changed. The blue (Y) handle did worse: it jumped down to 128 as soon as it
  moved, and on release left a hidden `grid: [45, 128]` in the project, smaller than the map, which the Build refuses.
- **Cause.** TempleShip's own grid is 45 by 203 by 15 tiles, and the editor capped a project's grid at 128 tiles a
  side (`STAGE_GRID_MAX`) whatever the map's own size. Every size dragged on it kept the 203, so `project.js
  validStage` turned it down and the stage went back to none. The drag's bounds put the Y handle's limit (128) under
  its floor (203), so the clamp gave 128. The compiler refused the same sizes. AlienBase01 (63 by 168) had the same
  bug; no other map in the cache is past 128.
- **Fix.** Each axis now goes up to 128 tiles or 30 levels, or the map's own where that is more (`project.js
  stageMax`, `compiler.py stage_max`). The drag bounds, the checks as a stage is set, loaded or recovered, and the
  compiler use it. `sortState` checks only the stage's shape, because its size was already checked against the map,
  so a save keeps the larger grid. The same day, at the user's word, the limit went up to 256 tiles a side, and the
  prefab builder's "largest map the editor makes" with it. TempleShip now grows to 256 across and deep, and up to
  30 levels. No map of the game's is past 256, so the own-size rule only matters again if the limit comes down.

### T-40: The output-name check took the lab's earlier tests of a project for someone else's files
**Fixed** (16 November 2026, seen by the user in the build queue: temple_improved failed at once).
- **Seen.** "The build would write names that are taken: patch_templeship_templeim_2001 (… in XCom-Enemy-Unknown's
  CookedPCConsole)". The file was the lab's patchtool deploy of the same project (EXP-14, 7 November), from before
  the editor could install, and the build would not even have written it: no edit of the project makes a patch.
  24 projects were refused the same way (the EXP-11 to EXP-28 projects, Large remix, Loot check), each by its own
  earlier test's map, patch or intro copy that the bake fixtures' installer or patchtool had put in the lab copy.
  EXP-65's first refusal was this too. Play in game and the campaign install refused those files as well.
- **Cause.** The ownership check of the output names plan (stage N1, earlier the same day) counts a file in
  CookedPCConsole as a stranger's unless the editor's own ledgers note it, and the lab's deploys noted theirs in the
  lab's ledgers only. The Build also checked the patch's name whether or not it writes a patch.
- **Fix.** build.py checks the patch's name only when the edit makes one. In the lab copy (its marker, with the lab
  setting set) a file the lab's deploy tools put there (installs.lab_deploys: the bake fixtures' deployed.json with
  its hash, patchtool's deployed.txt and seeded.txt) is a soft claim (outputnames.Claims: it doesn't stop the
  project's build, and still keeps a new project from the name), and an install replaces it if it still has the
  bytes the lab gave it, keeping it in that change's backup folder (`labFiles`) and putting it back when the editor's
  file comes out. Anywhere else nothing changes. test_build, test_play and test_outputnames check it.

### T-39: A Job Object's count of active processes drops before they have ended
**Fixed** (16 November 2026, found while building the build queue's containment, stage Q0).
- **Seen.** A contained build tree (procs.py) killed with `TerminateJobObject`: the job's `ActiveProcesses` read 0 at
  once, while the processes still answered as alive for about 10 to 16 ms more (waiting on them had not yet returned).
- **Cause.** Windows takes a process out of the job's count when it is told to end, not when it has.
- **Fix.** `Contained.drain` remembers every process it has seen in the job (its id and creation time) and waits
  until the count is 0 and each of them has ended. test_procs checks the grandchild is gone, not merely told to go.

### T-38: A leftover process holding a build's output pipe kept the server's build running
**Fixed** (16 November 2026, found by the build queue's Q0 tests with a stand-in build; not seen with a real build).
- **Seen.** A stand-in build.py that started a child and exited left the server's build `running` for as long as the
  child lived.
- **Cause.** The server followed a build by reading its output to the end, and a child inherits that pipe: the end
  never came while the child lived, so the job never ended and the build slot stayed taken.
- **Fix.** Since the build queue's stage Q0 (builds.py) a watcher waits for build.py itself, gives its leftover
  processes 15 seconds, then kills the rest of its tree, which closes the pipe; the build ends only once every process
  of it has gone (test_builds: a good build waits for its leftover processes). Builds are contained process trees
  (procs.py), so the server's own death ends them too (EXP-65 run 4).

### T-37: A full build of a map grown with nothing else stops in the relight
**Open** (16 November 2026, found while checking the piece flags plan's Build routes; not fixed).
- **Seen.** A scratch project on URB_Bar whose only change is a grid grown from 52 by 39 to 56 by 39 tiles: its quick
  build is made, its full build stops with `relight.py: error: --receivers-near needs an edit`.
- **Cause.** The Build's light stage sends a project that changes nothing in the map but its size to `relight.py`
  with the patch spec as `--edit-spec` and with `--receivers-near`. The spec has no objects, and with no copy, hide,
  light edit or landing moved the relight has no edit to model, so it refuses the option.
- **Not affected.** A grown grid with anything made in the map: cover blocks, buildings, a cleared map and pieces'
  flags take the lighting-unchanged route (`native_copy.py` without baking); copies, hides and light edits give the
  relight its edit.
- **Fix.** Not made. The likely one: a resize alone takes the lighting-unchanged route too (the ground planes a
  grown grid lays read the original's lightmaps).

### T-36: A map whose level volume falls a unit short of its tiles was exported without a tile grid
**Fixed** (16 November 2026: a tester's report from 0.5.2, a project on CSmallScout_Roadhouse that moved a van;
export 25 the same day, export 26, the game's own grid, after it).
- **Seen.** The Build stopped with "nothing of the project can be built: its one edit is left out (the export of
  CSmallScout_Roadhouse has no tile grid, which a van needs)". Every piece of a grid family (vans, among others)
  needs the grid for its pose rule, so no such piece of the map could be moved.
- **Cause.** The export takes the grid's corner from the level volume's box and its size from the tile header, and
  dropped the grid when the box missed the header's whole tiles by more than one unit on any side. Roadhouse's box
  is 5470.996 wide for 57 tiles of 96 (5472): 1.004 short on the far side. Act1_IntroLevel is short by exactly 1
  and passed.
- **The corner is the one every tool uses.** On all 31 maps in the lab's cache (Roadhouse included), the floors
  the map saves sit one unit below the tile centres counted from the box's low corner, the same on every map, so
  the box's corner keeps the relation every map has, and only the far side falls short. (The game's own tiles
  start a unit lower, at `WorldBounds.Min`: native/cover-build.md and below. The box's corner is where the maps'
  pieces stand: two lattices, a unit apart.)
- **Fix.** First `scene_metadata.GRID_SLACK`: the box could miss by up to 2 units (export 25). The reported project
  then compiled with all ten of its moves, and one off-grid warning: its van moved 8 units. Then, the same day, the
  game's own record (export 26, below): every map with tile data gets its grid from what it saves, and the slack is
  gone. The reported project compiles the same on export 26.
- **The three tall maps** had no grid until export 26: their boxes are taller than their levels (CBattleship_01 and
  DLC2_2_Deluge 32 units over, DLC2_3_Furies 16). Their levels count from the bottom as on every other map: every
  saved floor lies in the level it was saved under only for a corner within a few units of the bottom (a corner
  counted down from the top puts them in the wrong levels).
- **The game's own record.** The level volume's XComWorldData has `WorldBounds` (the grid with one unit more on
  every side, which `shell.py` already writes when it resizes a grid) and `NumX`, `NumY`, `NumZ`. Over the 143
  installed packages with tile data, its numbers equal the tile header's, its low corner is one unit below the
  box's, and every map's saved floors sit at the centres of the tiles counted from it, across and along (up, from
  2 units under a level's bottom to 62 over it). Since export 26 `scene_metadata.game_grid` reads it for the export
  and for the Build's `native_copy.level_grid`, which had counted the levels from the box, rounded: 16 on
  CBattleship_01, where the game has 15. `tools/upk/tests/test_game_grid.py` checks every map the editor lists (it
  runs with every suite, as the release does). Its notes say where a map's box is off (seven maps, for example
  "the level volume's box is 32 units taller than its 15 levels").
- **Two lattices.** The maps' pieces stand on the box's lattice, not the game's (pieces at a tile corner or centre
  of either, counted 16 November: URB_Bar 94 and 0, CSmallScout_DirtRoad 299 and 0, CLrgScout_DeepWoods 368 and 0,
  URB_TruckStop_EWI 316 and 1), so every piece of a map stands a unit off its tiles in X and Y. The game's tile
  build lets them: a wall on the box's lines reaches a unit into the next tile's box and does not fill it (how far
  in a piece must reach isn't known exactly; F-113's 4 units are how thick it must be, not how far in). The editor
  places on the box's lattice, which keeps what it places in line with the map's pieces. One consequence: a
  quarter-turned grid piece is turned about a corner of the box's lattice while the Build turns its tile data by
  whole tiles (about a corner of the game's), so its carried tile data lands 2 units off it, within the same tiles;
  turning about the game's corner instead would put the piece 2 units out of line with the walls round it. Not seen
  in a game run.
- **Two corners** (export 26, editor-contracts.md section 3): `tileGrid.origin` stays the box's corner for placing,
  and `tileGrid.tiles` is the game's. A point's tile counts from the game's corner (a ladder's ends, a mission
  object's, a soldier's spot, the floor under a piece placed, `save_tiles.py --box`, the Build's model of the
  rebuild queue); the rules for boxes keep the box's corner, as they were played (the floor a flat piece gives,
  the cover block panel's tiles, the Build's seeds and rebuild volumes), because how the game treats a piece a unit
  into a tile isn't known exactly. Checked on 16 November: the 52 saved projects and 18 example projects compile to
  the same specs and reports as before; three Builds (cover blocks on Bar, the blank map grown, Bar cleared and
  resized) come out byte for byte the same.

### T-35: A staged piece of another map is in every tool's scene unless told otherwise
**Fixed** (11 November 2026: seen while building the relight of pieces from other maps, plan step X8).
- `transplant.py` stages a piece of another map under the level and leaves it out of the level's actor list, where
  its home map has it. The game never spawns it (EXP-37). The bake's tools don't read the actor list: the shadow
  casters (`shadows.caster_triangles`), the receivers near an edit (`relight.receivers_near`) and the shadow-map
  receivers walk every export under the level.
- So a staged lamp post was a shadow caster of the bar at the police station's coordinates, and removing it as an
  edit would have made its far-off box a place the edit changed.
- Fix: `relight.Scene(ignore_casters=...)` leaves the staged actors out of both scenes without recording them as
  an edit, and `relight.py --foreign-copy COPY=STAGED` leaves their components out of the receivers.
- A second fact of the same build: a folder's `tfc-folder.txt` pointed at the staged map's folder, which has no
  cache of its own, only such a file. `package.link_caches` now follows it to the folder it names.

### T-34: Long War took a property out of a struct's field chain
**Open** (11 November 2026: read from the LWR install's `XComStrategyGame.upk` while building the property schema).
A reference fact, not a defect.
- A struct's properties are linked in a chain (its first field, then each field's next). In LWR's
  `XGFacility_Engineering.CheckpointRecord_XGFacility_Engineering`, `m_arrFoundryProjects` points past
  `m_arrAlloyProjects`: the property's export is still there, under the struct, and no chain reaches it.
- So a reader that takes a struct's properties from the chain alone misses one. `tools/upk/schema.py` takes them
  from the exports under the struct, and only the order (which matters for a struct saved as plain bytes) from the
  chain; a plain-bytes struct with a property outside its chain is an error.

### T-33: An export's properties were read 4 bytes early when the bytes there looked like a tag
**Fixed** (11 November 2026, offline: `test_a_kind_whose_name_carries_a_number_is_not_a_tag`; the walk of all 150
Firaxis-cooked packages, 1,408,360 exports, now ends each at its closing None). Found by that walk.
- `props.props_start` finds where a component's properties begin by trying the places they can begin and taking
  the first that reads as a tag. `EWI_ExaltHQAssault_Stream`'s `TriggerVolume_0.BrushComponent_15` read as one 4
  bytes early: its net index a valid name, the first property's name where the number would be, and that name's
  number (0) the place in the name table of a property kind.
- A kind's name is a plain name, with number 0; in the false reading the "number" was the real kind's name index.
  The check now asks for that zero.
- One export of the install was affected, a brush component of a stream. Every tool that reads properties goes
  through this function, so the bake suite was run again.

### T-32: Firaxis's levels import art only from packages loaded before them
**Open** (11 November 2026: read from the install's packages and config with `tools/upk/audit_cross_map.py`; how
the engine loads a companion is a reading, not run). A reference fact, not a defect;
cross-map-assets-plan.md 2.4, 2.5 and 3.2.
- What the 150 Firaxis-cooked maps and streams import that isn't a class: materials, textures, physical materials, a
  skeletal mesh and archetypes of `EngineMaterials` (124 packages), `PhysicalMaterials` (121), `GEN_MaterialParents`
  (107), `UI_Cover` and `UI_Range` (95 each), `XComEngineMaterials` (67), `HotButton` (8), `FX_Weather` (5). Each is
  held by `Startup.upk` (the `[Engine.StartupPackages]` list cooked into one package) or by a script package
  (`XComGame.upk`, `Engine.upk`), which carries the art its classes' defaults name.
- No map imports art from a package that is only a file on disk.
- Thirteen levels (the tutorial's two sublevels, eight cinematics, `DLC1_2_CnfndLight_Stream`, `Soldier2Spotted`,
  `SurvivorReturnsMC`) import voice lines (58 `SoundNodeWave`s) that only their `<level>_LOC_INT.upk` holds, beside
  an `ObjectReferencer`. So the engine loads that companion before the level. None is a battle's base map.
- What it means for us: a donor map's imports are good in any map (added as they are); and a package of our own can
  only feed a map's imports if it is loaded first, for which the companion is the one route Firaxis uses per level.
- LWR's own content packages (`LWRFX.upk`, `LWRPictures.upk`, `LWRRange.upk`: uncooked, licensee 0) are loaded by
  name from its scripts at run time, which a map's imports are not.

### T-31: The game's art is the same bytes in every map that holds it; shaders and textures are shared
**Open** (11 November 2026: measured offline with `tools/upk/audit_cross_map.py`, result in
`research/evidence/cross-map-assets-audit-2026-11-11.json`; no transplanted piece has been built or played). A
reference fact; cross-map-assets-plan.md section 2.
- The library: 150 Firaxis-cooked packages (96 base maps, 54 streams) hold 5,771 distinct static meshes, 664
  fracturing meshes, 740 materials, 2,895 material instances, 5,763 textures and 2,538 destructible archetypes under
  the game's asset packages. A base map holds 22 to 429 static meshes, 249 at the median.
- The same object in two maps (each base map against the next, 318,982 comparisons): 317,628 differ only in the
  numbering of names and object references, the file offsets of bulk data, and in materials the `LightingGuid`,
  `ParentLightingGuid` and a base material's last four bytes (one value per package).
  - 490 have another size, nearly all 25 bytes: one more bool property saved by one cook than by another, on
    archetypes' components. Such a path has an older and a newer form across the install.
  - 864 have other bytes: destructible archetypes with a reference to a differently named object (448), cubemap
    faces' last 16 bytes (198, a GUID per cook), material instances with four bytes of one of two values (162),
    static meshes with one reference empty in one map (29), class default objects and three particle objects.
- Shaders: no package has a `ShaderCache` export. All 784 base materials (740 `Material`, 44 `DecalMaterial`) have
  their ID in `RefShaderCache-PC-D3D-SM3.upk`, the 180 that one package alone holds among them.
- Textures: 4,376 name `Textures.tfc`, 140 `CharTextures.tfc`, 1,247 are whole in their package; none names the
  numbered caches.
- LWR's 87 patch maps (licensee 0) hold modder copies under some of the game's names (157 static meshes) and are
  left out of the above.
- Measured later the same day with scratch scripts (not yet in the audit; the implementation plan's X0 adds them):
  - an asset's export-table entry (flags, export flags, net count, package GUID) and its net index are the same in
    every map: 7,194 objects and 581 asset packages over three pairs, bar `FX_Shared`'s GUID in one pair and the
    class defaults under `XComGame`. An asset package's entry carries its original package's net count;
  - every lightmap and shadow-map texture of twelve maps names the shared `Lighting` cache or is whole in its
    package;
  - only 13 of 130 asset classes keep a name, a reference or an offset beyond their tagged properties (six pairs):
    the texture classes, `Material`, `DecalMaterial`, `MaterialInstanceConstant`, `StaticMesh`,
    `FracturedStaticMesh`, `SkeletalMesh`, `SoundNodeWave`, `StaticMeshComponent`, `Model`, `Polys`;
  - property types can be read exactly from the script packages' export tables (an array's element is the export it
    holds): 71,563 properties, 4,035 arrays; URB_Bar's 10,603 arrays all typed and of the size their kind gives,
    bar an editor-only property.
- Later still, the same day: those four are in the repository and run on the whole install (the audit's
  `entriesOfSharedObjects`, `bakedTextureCaches`, `fieldsBeyondProperties` and `walk`), and they hold: 13 of 158
  classes keep numbers beyond their properties; every entry field is the same bar `FX_Shared`'s GUID and the
  `XComGame` package's net count; 18,513 baked textures name `Lighting`, 24 are whole in their package. The
  property count above took in functions' parameters; classes and structs have 24,925 properties and 2,293 arrays.
- **The transplanter is built** (`tools/bake/transplant.py`, with `tools/upk/schema.py`, `typed_props.py` and
  `native_fields.py`) and its oracle run over every base map against the next: of 318,982 shared objects, one
  map's bytes renumbered are the other's for 316,830 (302,067 exactly, 14,414 but for values one cook writes
  differently, 349 of plain classes). The rest is known: 490 of another size, 448 archetypes naming an object the
  other map lacks, 29 meshes with one material reference kept by one cook only, 24 class defaults with a net index
  of the map, 3 particle modules, and 1,158 objects of four classes whose native data has no layout yet
  (`FracturedStaticMesh`, `SkeletalMesh`, `Model`, `Polys`: refused when asked for).
- What one cook writes differently from another, and no renumbering explains: a material's `LightingGuid` and
  `ParentLightingGuid`, the last value of its compiled resource (a base material's last four bytes; in a material
  instance before its static parameters), and a 2D texture's cache GUID (a cubemap's faces).
- URB_Bar grown with two props of URB_PoliceStation (31 exports, staged: under the level, in no actor list) reads
  back as intended, offline.
- The copier (`native_copy.py`, unchanged) clones a staged actor as it clones one of the map's own, with seeds and
  a rebuild volume. A variant with a lamp post of URB_PoliceStation and an alien wall of CAbductor_Cliffside in the
  bar's car park is built and in the lab's test slot; our own exporter draws both from it with their materials.
  **Played and passed** ([EXP-37](experiments/EXP-37-foreign-props.md) run 1, 11 November): both draw with their
  own materials, stop a unit, give cover and come back after a save and reload. So the game takes a transplanted
  piece for one of the map's own, a base material new to the map finds its shaders, and the donors' baked textures
  are read from the shared cache. A full build's light for such a piece and the other families are still ahead.
- What it means: a piece can be copied from its home map into another with its dependencies, by renumbering alone,
  and it finds its shaders and textures there. Still to show in the game: a transplanted visible mesh drawing with
  its own material (EXP-37). The work is laid out in
  cross-map-assets-implementation-plan.md.

### T-30: A build stopped when a deleted piece stood outside the map's tiles (the tutorial map's backdrop pieces)
**Fixed** (11 November 2026, offline: `test_pieces_outside_the_maps_tiles_are_hidden_and_copied_without_a_rebuild`,
the reporting project rebuilt here; not played). Found from a user's build report (editor 0.4.0, plain EW,
`Act1_IntroLevel`, project TutorialPlus: 12 deletes, 5 copies, a quick build).
- What: `native_copy.py` ended with `ValueError: the hidden piece at [-3358.822, -3265.26, -1630.897, -1440.922, 16.0,
  143.629] crosses no tile of the map`, and the build failed at the light stage.
- Cause: the map's level volume runs y -1248..576 (62 x 19 x 12 tiles from x -5377). `StaticMeshActor_10` and
  `StaticMeshActor_9` stand at y -1631..-1441, two tiles past its edge, so with the quarter-tile margin and the ring
  of one tile they still reach no tile. `hide_tiles` raised for that instead of adding no rebuild volume. The other
  ten deletes and the five copies (two of them reaching past the edge, but crossing tiles) were fine.
- Fix: a piece outside the tiles has nothing to re-check. `hide_tiles` and `add_tiles_box` return None for such a box;
  the piece is still taken out of the Level's list (or the copy or cover block still made), with no rebuild volume
  and no seeds, and its manifest section's `tiles` (and a hidden piece's `volume`) is None.
- Not covered: a ladder copy outside the tiles (its top tile's volume, `tile_volume`) is untouched; a full (baked)
  build of the project was not run, only the quick build the report made.

### T-29: The viewer cut masked props away by their colour texture's alpha (the farm's tractors drew as glass)
**Fixed** (10 November 2026, offline: `test_material_rules` (`test_what_an_opacity_mask_input_samples`,
`test_a_masked_cut_out_follows_the_opacity_mask_input`), the Farm re-exported and looked at; a viewer-only fault, the
game never had it). Found by the user: CSmallScout_Farm's tractors (`VEH_commercial.Mesh.TractorB`) showed only
their glass and a few orange lights in the editor.
- Cause: the viewer drew every `BLEND_Masked` material with the colour texture's alpha as its cut-out
  (`materials.profile`: `diffuse-alpha`). The game cuts by whatever the parent material wires to its OpacityMask input.
  - MINST_Tractor's parent, `GEN_MaterialParents.Obsolete_Materials.PROP_Objects_Old`, has an `OpacityMask` static
    switch, off for the tractor. Its cooked OpacityMask input is blanked (cooking keeps parameter nodes and blanks
    links to the rest), but the tractor is solid in the game while 99.6% of `Tractor_DIFF`'s alpha is under the 0.333
    clip, so with the switch off nothing is cut. Five more of that parent's 15 materials lost over 90% the same way
    (dairy tanks, blue pipes, a vent).
  - `GEN_MaterialParents.Master_Materials.PROP_Objects`, the common prop parent (240 materials on the exported maps),
    wires its OpacityMask straight to the `Spc_Ems_Mpc_Opc` texture sample's alpha (`MaskA`). Its colour alpha is
    unrelated: 12 of its materials lost over 90% to it (133 pieces on the exported maps: the farm's metal lamps,
    the tutorial's bike, a facade door, street lamps), and the others were drawn with the wrong mask (trash piles
    showed a brown smudge their real mask leaves out).
- Fix (export 19): `materials.opacity_input` reads what a cooked material's OpacityMask input samples: a texture
  parameter with one masked channel. The exporter cuts by that channel (`packed-alpha`, the colour drawn without its
  alpha), draws a material whose `OpacityMask` switch is off solid, and otherwise keeps the colour's alpha
  (PROP_DifOpc_Nrm, foliage, CarLift with its switch on). On the Farm 24 materials now cut by their packed mask and the
  tractor, lamps and trash piles draw right.

### T-28: A component with no mesh but a shadow map stopped a full build's shadow relight
**Fixed** (10 November, offline: `test_shadowmaps.MeshlessReceiver`, and the tester's project rebuilt to the end;
not played). Found by a tester on 0.3.1 (bug report `DLC1_1_LowFr_FILPBu_81c4-report.zip`, plain EW): a full build
of DLC1_1_LowFriends with 41 copies and 16 hidden pieces stopped in the relight.
- What: `relight.relight_shadow_maps` raised "TheWorld.PersistentLevel.XComLevelActor_16.StaticMeshComponent_166 has
  no static mesh in this package" from `component_box` (the quick reach test), which stands outside the per-receiver
  `try`, so one receiver stopped the whole relight.
- Cause: that component names no `StaticMesh` (None) and has no lightmap, yet keeps a shadow map of the dominant
  light (`ShadowMap2D`, export 6788). `shadowmaps.dominant_receivers` listed it as a receiver.
- Fix: `dominant_receivers` and `relight.receivers_near` leave out a component with no static mesh in the package (it
  draws no surface to relight).
- Checked: the tester's project (from the report) built here with `tools/editor/build.py` on the same map (same
  SHA-256), exported into a scratch cache: 168 lightmaps written, 98 shadow maps, no failed receiver (18 skipped: the
  16 hidden pieces and two by the exclusion rule).
- The tester needs a release with the fix (0.3.1 has neither T-27's nor this one's); release 0.4.0 has both.

### T-27: A lighting texture kept wholly inside the map stopped a full build
**Fixed** (10 November, offline: `test_fixture.TextureWithoutCacheName`, and the user's failed build rerun to the
end; not played). Found by the user: a full build of URB_StreetOverpass with 13 copies stopped in "Make the edit in
the map and bake its lighting".
- What: `native_copy.py` failed cloning the copies' lighting textures: `lightmap_fields.texture_fields` raised
  "Texture has no own 8-byte TextureFileCacheName" (from `grow_fixture.clone_texture`).
- Cause: `XComDestructibleActor_18` (a copied piece) has a shadow map for `SpotLightToggleable_2` whose texture,
  `ShadowMapTexture2D_173` (1024 x 1024 G8, `NeverStream`), keeps all 11 mips inline and saves no
  `TextureFileCacheName` at all. The reader required one on every lighting texture. The audit reader already read it
  (cache None). Across the install's EW maps, 25 shadow-map textures in 10 shipped maps save no cache name
  (Act1_IntroLevel 4, DLC2_3_Furies 2, URB_Bar 1, URB_FastFood 1, URB_Highway1 4, URB_HighwayBridge 4,
  URB_HighwayFallen 1, URB_OfficePaper 1, URB_StreetHurricane 3, URB_StreetOverpass 4); after the fix every one reads.
- Fix: `texture_fields` accepts a texture with no cache name when no live mip lies in a cache (`cache` and
  `cacheNameOffset` None), and refuses one that has cached mips but no name; `lighting_fixture.Fixture.redirect` treats
  such a texture as one kept inside the package (edited in place, never moved to the variant cache) instead of
  refusing it as "not in Lighting.tfc".
- Checked: the build's own `native_copy.py --bake` command, rerun on the shipped map, finished (13 copies, 4 min); the
  copy's clone `ShadowMapTexture2D_299` stays inside the map with no cache name. The test writes the texture in place
  and reads it back.
- Still open: the shadow relight rewrites only the dominant directional light's shadow maps, so a copy keeps its
  original's shadow maps for other lights (here the spotlight's), as every copy does.

### T-26: A piece lit per vertex couldn't be copied or moved by a build
**Fixed** (9 November, offline; `test_native_copy.VertexLit` and `BulkOffsets`, and a copy full-built on each map;
not played). Found while checking T-25.
- What: a full build that copied CLrgScout_Stonewall's vine (`XComDestructibleActor_124`) stopped in
  `native_copy.lighting_textures`: "is vertex lit: its lightmap holds inline data the copy can't move". The compile
  report had no error or warning for it, so the editor let the edit be made and the build failed. A quick build
  never asked, and made a clone whose lightmap still named the original as its owner and pointed at the
  original's samples.
- Where: of the 96 listed maps here, only that vine and Temple Ship's four `AlienDoorVolume_96x96x256` pieces
  (`XComLevelActor_0`, `_2`, `_3`, `_4`: hidden volumes at the alien doors) have a mesh component with a vertex
  lightmap (lightmap type 1).
- The record, in the mesh component's own LOD data after the light GUIDs: the owner (the component itself), the
  directional samples' bulk record (8 bytes a vertex: 184 for the vine, 24 for a door volume), three scale vectors
  (36 bytes), the simple samples' bulk record (empty in all five). Each bulk record is inline and holds the
  absolute offset of its payload, 16 bytes on, as a texture's inline mips do. None has a lightmap in a mesh-swap
  record.
- Fix: `lightmap_fields` locates the owner and the bulk records; `native_copy.clone_assembly` gives the clone its
  own copy (the owner remapped to the clone, the bulk offsets moved to where the clone lies, as
  `grow_fixture.clone_texture` moves a texture's), in both kinds of build; after the write
  `check_vertex_lightmaps` reads every clone back, so a clone relocated later can't leave its offsets behind. A
  vertex lightmap in a mesh-swap record is refused.
- Still open: the relight writes texture lightmaps only, so the copy keeps the light of the place its original
  stands in (the relight lists it as skipped, "has no LOD-0 texture lightmap"); it does cast its shadow from its
  new place. For the door volumes this shows nothing: they are hidden. A vertex relight would compute the
  samples at the vertices and write them in place (the record's size wouldn't change).

### T-25: Two more maps whose full build stopped while reading the shadow casters
**Fixed** (9 November, offline; `test_props.py`, `test_shadows_bounce.Casters`, and a copy full-built on each map;
not played). Found by the scan made for T-24.
- CLrgScout_Stonewall: `CemeteryFoliage.Meshes.VineTop_2` (`XComDestructibleActor_124.StaticMeshComponent_1002`) is
  a caster whose `LightMapCoordinateIndex` is 1 while the mesh has one UV channel; it is lit per vertex (lightmap
  type 1), so nothing rasterises it. `lightmap_texels.component_mesh` raised "has no UV channel 1" for the shadow
  casters and for a piece's box alike.
  - Fix: `component_mesh` gives such a mesh with `uv` None; `rasterise` refuses it with the same message.
- URB_CommercialStreet_Terror: the properties of `StaticMeshActor_19.StaticMeshComponent_115` (a tree outside the
  tiles) couldn't be read ("Read of 8 bytes outside payload"), and `shadows.is_caster` asks for them outside its
  `try`.
  - Cause: the component's net index is 2315, and the map's name table has None at 2315. `props.props_start`
    tries the offsets a property block can start at and took those 4 bytes for the closing None, so the properties
    were read from 4 bytes early.
  - Fix: the closing None must be the plain name (number 0); here the first property's name stands where the
    number would be.
  - How far it reached: of 2,757,592 exports in the install's 3,052 readable packages, the start changes for 54,
    and each of them failed to read before and reads now. Among them, besides this tree: a light component each
    in CSmallScout_DirtRoad, EWI_ChryssalidHive, Addon_GollopChamber, Addon_PowerGenerator, Static_Barracks,
    patch_xcomhq-mp and XComShell; a floor component each in patch_alienbase2, patch_battleship_roof and
    patch_truckstop; a mesh component each in Act1_IntroLevel, Static_ScienceLabs, patch_clean_overlook,
    patch_researchoutpost and patch_rooftopconstr; the rest particle modules, emitters, a sprite, a light
    environment and prefabs' mesh components.
- After both fixes the caster read passes on every map package of the install but the lab's own `patch_exp05`
  (its borrowed meshes).
- Not checked: what the editor and the builds made of those lights and floor components while they couldn't be
  read. Maps exported before this keep what they had: the export version stays 18.

### T-24: A mesh's colour stream can be longer than its vertex stream
**Fixed** (9 November, offline; `test_formats.test_colour_stream`, and the reported project full-built here; not
played).
- What: a full build of URB_FastFood failed on another computer with `FormatError: Invalid colour stream`, whatever
  the edit (the report's was one copied car). It failed the same way here: the map file is the same.
- Cause: `FX_Cloth.Flags.Flag_B` (and `Flag_A`) saves 180 vertex colours for 90 vertices, the 90 colours twice
  over; the rest of the mesh reads as usual (its indices go to 89). `mesh.read_mesh` wanted exactly one colour per
  vertex. The relight reads every shadow caster, the flags among them, so the whole build stopped; the export only
  left the cloth out with a diagnostic, which is why the editor showed nothing wrong.
- Where: the two flag meshes only, in ten of the install's 456 map packages: URB_FastFood, URB_OfficePaper (both
  also as _EWI), URB_OfficePaper_Terror, URB_LiquorStore, URB_SlaughterhouseA, URB_Boulevard_Euro, and
  EWI_ChryssalidHive (there not a caster).
- Fix: the stream is checked against its own header and read as far as the vertices go (it is indexed by vertex);
  a shorter one is refused. Exports made from now on draw the flags' cloth.

### T-23: A tactical save holds the game's tile flags, readable without the game
**Fixed** (9 November; `test_save_tiles.py`, and EXP-28 run 1's save).
- What: until now, what the game's tile rebuild made of an edit (floor, occupied, cleared) was known only from what
  the user saw, or from probes a patch logged. A tactical save holds the battle's static tile store in the layout of
  the map's `XComWorldDataContainer` (`wdparse.py`): a 1,024-byte header, then compressed chunks as a cooked
  package's (tag `0x9E2A83C1`, LZO1X blocks), and in the decompressed data the store's header (the chunk count
  twice, the chunk order, the grid's dims). The dims alone occur elsewhere in a save too.
- Tool: [`tools/lab/save_tiles.py`](../tools/lab/save_tiles.py) `<save> <map.upk> --tiles … | --box …` prints each
  tile's flags, baked and saved, with F for a floor and O for occupied. It answered both of EXP-28 run 1's open
  reports (F-71, and the deleted wall's tiles) from one save.
- Not read: the stores after the static one (floor heights, pathing links), which the container's parser
  (`world_links.py`) would take the same way.

### T-22: A fractured mesh's painted fragments were read as object references
**Fixed** (9 November, offline; the wall tests of F-69 compare the copy's array with the original's).
- What: `FracturedStaticMeshComponent.EditorPaintedVisibleFragments` is saved as an array of 4-byte values holding
  bytes of 0 and 1 (16843009 is four set bytes). `native_copy.Walker.refs` takes any array of 4-byte values for
  object references, so a clone would have rewritten a value that happened to equal the export number of one of the
  clone's own exports (only numbers such as 1, 256, 257, 65536 can occur, so no build so far was affected).
- Fix: the property is in `NOT_REFERENCES`, with the brush and deco arrays found the same way.

### T-21: The viewer's export lists actors a build took out of the Level
**Open** (9 November, offline; a reading of our own variants only). Found while checking EXP-26 run 1's build.
- What: exported back into a scratch cache, the run 1 variant still lists `SpotLight_3` (deleted) and the lamp post
  `XComLevelActor_37` at its old place (moved: the build hides the original and makes a copy), neither marked hidden.
  The variant's persistent Level doesn't list either (`native_copy.level_actors`), and lists every edited and new
  actor, so the build is right.
- Cause: export.py reads every actor export of the package, whether or not the Level's actor list holds it. A
  shipped map holds them all; a Build's variant leaves a deleted or hidden actor's export in place and takes it out of
  the list only (native_copy's hides, native_lights' deletes).
- Fix (not made): mark or skip actors the Level doesn't list when exporting, so variant checks don't need the Level
  list. Until then, variant checks read the Level list for deletes and hides.

### T-20: A build's bake changes only its map's lighting
**Fixed** (9 November, offline; not yet played). A reference fact behind the editor's Quick build (`build.py --quick`),
which skips the bake to build in seconds.
- What: a quick and a full build of the same project revision (temple_improved, revision 13 of Temple Ship: 33 copies,
  7 hides, 14 break groups) were compared export by export.
  - The world data (the tiles: cover, movement, line of sight) is byte for byte the same.
  - native_copy.py's record of the edit is the same in both, export numbers aside: copies, tiles, rebuild volumes,
    hides, ladders, wall columns, floor cutaways, vans and break groups.
  - Every other difference outside the lighting is a shifted reference or net index. The full map's 66 extra lightmap
    textures shift the numbers of every export and net index after them (T-15).
  - What really differs is the lighting: lightmap and shadow map textures, and the lightmap part of 242 mesh
    components (their tagged properties are the same, references aside).
- Cause: in native_copy.py, `--bake` switches only the copies' own lighting textures, the extra lights that reach them
  and the relight; the edit itself is made the same way either way.
- Fix: Quick build runs native_copy.py without `--bake`, so its pathing and cover are a full build's. Its lighting is
  wrong: the copies read their originals' lightmaps (EXP-20 run 2), cast no shadows, and hidden pieces leave theirs
  (F-24). Still to confirm in the game: a quick build plays as the full build does, apart from the light.

### T-19: Police Station's standalone police light bars weren't part of their sedans
**Verified** (EXP-24 run 2, 8 November: the sedan moved with its light bar, none left where it stood, and the deleted
sedan took its light bar along, "all looks good to me"; `test_compiler.test_a_part_the_glass_names_at_the_bodys_place_joins_the_car`,
`test_links.test_police_stations_car_glass_names_its_car_and_its_standalone_light_bar`, `browser_smoke.check_light_bar`).
- What: four of Police Station's sedans (`XComDestructibleActor_1056`, `_1059`, `_1062`, `_1072`) carry a police light
  bar (`ARC_SedanBPoliceAddon`, `_468` to `_471`) 2 units from the body that no prefab places with them, so the
  editor and the compiler took the sedan without it: moving the sedan would leave the light bar floating where it
  stood, and its glass's copy would drop the light bar's column entries.
- Cause: assemblies were joined by prefab, partner and door frame; only the glass's fragment columns name these
  parts (plan 2.3 and 3.3).
- Fix: export 16 records, for each fracturing piece, what its columns break (`breaks`;
  `scene_metadata.fragment_breaks`); `compiler.assemblies` joins to a car each XComDestructibleActor its glass names
  that stands at the body's place (within `PART_AT`, 8 units). On the seven maps in the cache exactly these four
  join. The page gives a pasted light bar its sedan copy's link tag (`app.js` `copyTag`).

### T-18: The Build couldn't size a door leaf
**Fixed** (8 November; `test_native_copy.test_a_door_leafs_box_comes_from_its_skeletal_mesh`).
- What: copying, moving or deleting a door failed in `native_copy.piece_box`: the leaf's `StaticMeshComponent` has no
  mesh ("has no static mesh in this package").
- Cause: a door leaf draws a skeletal mesh and saves an unused static mesh component beside it (plan 2.2).
- Fix: `piece_box` takes a skeletal component's mesh in its reference pose (the door closed); components without a
  static mesh have no lighting textures and get no extra lights (plan step G4).

### T-17: A project on a map whose package and records differ in case couldn't build
**Fixed** (8 November, found preparing EXP-22 run 2; `test_compiler.test_a_map_whose_package_and_records_differ_in_case`).
- Symptom: none seen yet; the compiler would have refused every edit on CSmallScout_Farm.
- Cause: the package is `CsmallScout_Farm.upk`, its records say `Name="CSmallScout_Farm"`. A project takes the
  record's name (the map browser's id, which Builds look records up by), the export and its pieces the package's
  (`sourcePackage`). The compiler compared them exactly: a `source-mismatch` for the project, a `level` error for
  each piece, and no assemblies.
- Also: `CIN_DropshipIntros` names the farm's landing `CsmallScout_Farm`, and `intro_copy.py` matched the record's
  case, so EXP-22 run 2's first build had no intro copy and would have landed no Skyranger (F-45 again).
- Fix: the compiler matches the map's name whatever its case and finds the pieces, assemblies and helpers under the
  package's own (`Compiler.package`); the spec keeps the record's name for the records. `intro_copy.same_map`
  renames a switch entry naming the map in any case (`test_intro_copy.test_a_map_named_in_another_case_is_renamed_too`).
  The landing zones and MiniMods rules use the records' case.

### T-16: The viewer drew pink where it found no colour texture
**Fixed** in the viewer's export 14 (8 November); checked by a scan of every map, not yet by eye on each.
- Symptom: pink pieces (the viewer's diagnostic colour) across LWR's maps: the user saw pink trees and wreckage on
  a crashed UFO map (CLrgScout_ForestTrench).
- Scan: every piece the 95 maps and their streamed packages draw, by the exporter's own rules (meshes read, textures
  not decoded). 2,810 visible pieces on 79 maps were pink, from five causes:
  - colour textures the compiled shaders sample under names the `_DIFF` rule missed (`pineBranchSplit` on burning
    pines, `Rough_Debris` on burning logs). The alien wreck debris (1,350 pieces on 29 maps) samples only
    `T_Alien_Destroyed`, a packed mask that draws as green blotches: it takes charred metal by kind instead;
  - diffuse parameters under other names (`Diffuse_Map`, `Diffuse Map A | CMod Mask`, `StaticScreenTexture`);
  - LWR's patch packages (`patch_clean_*`, `patch_<map>`) carry the materials of their pieces as stubs: an export
    with only its texture GUIDs and lighting GUID, no parent, no parameters. The game resolves them by path from the
    map, which is loaded first (the alien crates on the supply ship maps, the debris tiles on Nuked City);
  - fractured meshes' inside faces have no material (car glass, abductor railings): the game draws them only where
    a fragment has broken off;
  - materials whose colour is computed in shaders the cook stripped (the marsh bottom, burnt debris, water planes),
    or that live in another package (the highway bridge's cables).
- Fix: `export.diffuse_parameter`, `export.compiled_colour`, `materials.approximate_colour` (a colour by kind, else
  neutral grey, flagged in Import notes), `Exporter.section_material` (stubs and imports from the map's exporter,
  interiors hidden, other missing materials grey). After it the scan finds no pink piece; 35 visible pieces draw
  neutral grey and 1,811 a colour by kind (1,350 of them the alien wreck debris).
- Left: burning trees show their unburnt texture; colours by kind are guesses.

### T-15: Clones that keep their originals' net indices are duplicates to the game
**Verified** (EXP-20 run 6: no net-index error names a clone; the 10 left are the engine's own, as in older logs).
- Symptom: the game logs `Error: (AddNetObject) ... have duplicate NetIndex` at every load for each cloned
  component, shadow map and texture, and `RemoveNetObject` errors at a save and reload (EXP-20 runs 3 and 4b). It
  carries on regardless.
- Cause: `native_copy.py` gave only the new actors a fresh net index. Every other clone kept its original's.
- What the map holds: net indices are counted per top-level package. In URB_Bar's own space, 1,948 objects share
  index 0, and the game reports none of them. The rest are unique and below the package's net object count (7,578),
  except one dominant light component at 12,804.
- Fix: `package_grow.Grower.fresh_net_index` gives a clone whose original has an index above 0 the package's next,
  and the count grows. `native_copy.py` and `grow_fixture.clone_texture` use it for every clone. A clone inside a
  forced-export package is refused, since those count their own.
- Run 5's log: fixed for textures, shadow maps, damage actions and cues, but not for components.
  - A component's data starts with its template owner class (an empty reference, 0), and its net index comes after.
  - The writer read the 0 at the start and skipped the clone as unregistered.
  - The net index is the 4 bytes just before the tagged properties, for actors (after the state frame), components
    and plain objects alike. `native_copy.py` passes that place since the run.

### T-14: A read across a compressed chunk boundary hangs the game's loader
**Verified** (EXP-20 run 4b: the same content, cut only where an item starts, loads).
- Symptom: EXP-20 run 4 hung while loading the mission, twice. Windows logged it as "stopped responding", and the
  log stopped where the load began.
- Cause, most likely: `tools/upk/package_grow.py` cut its appended data into 1 MB chunks wherever the cut fell.
  - In run 4 a cut split one export-table entry's 4-byte field across two chunks. The game's loader serves a read
    from one chunk only.
  - The cooked maps never split a read: in URB_Bar no export's data and no table entry crosses a chunk boundary.
  - In runs 1–3 the cut fell between fields by chance.
- Fix:
  - The writer cuts appended chunks only where an export's data or a table starts.
  - Its write check refuses any export's data or table that crosses a boundary.
- A tool that grows or re-chunks a package must keep this rule.

### T-13: patchtool refused an editor spec with exactly one copy

**Fixed** (7 November 2026; [EXP-17](experiments/EXP-17-lighting-edits-in-game.md) run 11).
- Symptom: the first build of an added piece (one copy, no hides) stopped at patchtool's spec check: "boxes needs one
  box per name in from". Earlier editor specs had two copies (run 10) or none (run 9).
- Cause: `Read-Spec` read `boxes` through `Opt`, a function. PowerShell unrolls a list a function returns, so a list
  of one box came back as that box's six numbers, and six is not one.
- Fix: the copy's `boxes` property is read directly. The same spec then passed `t3d` (18 tiles planned) and the
  build.
- Not covered: other list-of-lists properties read through `Opt` would unroll the same way; `boxes` is the only one
  today.

### T-12: Pasting two copies of one original gave them one name, and the save merged them

**Fixed** (6 November 2026; [EXP-14](experiments/EXP-14-temple-variant.md) run 9).
- Symptom: the user stacked two copies of an alien console and pasted the pair. Revision 4 saved one actor,
  `XComDestructibleActor_60_copy11`, with one pose and its template's mesh component listed twice. The compiler
  refused it (`template-changed`).
- Cause: `pasteSnapshot` named each pasted piece `<its original>_copy<the paste's serial>`. Two pieces copied from one
  original got the same name, and the project groups an actor's pieces by name.
- Fix: each pasted actor takes a serial of its own (the paste's first serial still tags its prefab groups).
  [`browser_smoke.py`](../tools/viewer/tests/browser_smoke.py) pastes a piece twice, then pastes both copies together,
  and checks four actors with names of their own and no repeated component. It fails against the old code (three
  actors) and passes on both maps.
- Projects saved before the fix keep the merged actor. Revision 4's lost console was rebuilt for EXP-14 run 9 from the
  paste's shift.

### T-11: patchtool took a test slot named after the base map for the base map's record

**Fixed** (6 November 2026; [EXP-14](experiments/EXP-14-temple-variant.md) run 2).
- Symptom: the redeploy at 15:28 rebuilt the Temple variant's record (`DefaultMaps.ini` line 184) from the test slot
  (line 42), with map family `URB_Bar` and an abduction. Before, it had been made from Temple's own record (line 182,
  `eMission_Final`).
- Cause: run 1b had named the test slot `TempleShip`. `Set-ShipConfig` takes the first `Maps=` line named after the
  base map as its record, and line 42 comes first.
- Fix: `Set-ShipConfig` skips the line `-Stream` points, which is never the base map's own record.
  [`test_ship_record.ps1`](../tools/patch/tests/test_ship_record.ps1) covers it with a test slot named `TempleShip`
  in a copy of LWR's config: 69 of 69 checks pass. A `deploy` at 15:39 rebuilt line 184 from Temple's own record.
- Not covered: a test slot named after the base map when patchtool is run without `-Stream`. It still takes the
  first line with that name.

### T-10: A standalone patch writer can target compiled helper settings, but is unproven

**Open** (6 Nov, [EXP-12](experiments/EXP-12-standalone-toolchain-audit.md), read-only audit).
The [dependency assessment](dependency-replacement-feasibility.md) separates direct cooked-file reading, which
our viewer already performs, from UDK's editor, script compiler and cooker roles.

- EXP-11's cooked patch embeds 14 classes and 107 functions. Its four placed helpers total 2,243 serialized bytes,
  all tagged properties with no native tail. Their property shapes, array counts/sizes and scalar values match
  the source map. Cooking embeds dependencies; decompression alone cannot replace it.
- Proposed first backend: preserve a qualified cooked template's code/object identities and write supported
  helper properties, then reuse the existing base-map seeding and variant configuration steps.
- Missing: variable-size property and name-table writing, offset/dependency validation, template provenance and
  versioning, and game checks including save/reload and coexistence with other patches. The current EXP-11
  package has not yet passed its own gameplay check.
- This could remove UDK from ordinary layout builds. Rebuilding helper code would still require UDK until an
  independent compiler/linker exists. Existing floor, lighting, cutaway and piece-family limitations remain.

### T-09: UDK can't save a package name over 30 characters

**Verified** (6 Nov, [EXP-11](experiments/EXP-11-static-placement.md): the 30-character
`patch_urb_bar_exp11static_b7f3` saved without the dialog). The editor named a project's patch
`patch_<map>_<project name>_<id>`, which came to 39 characters for EXP-11 (`patch_urb_bar_exp11staticplacement_b7f3`).
UDK's Save As then shows a warning: `Filename '…' is too long; this may interfere with cooking for consoles. Unreal
filenames should be no longer than 30 characters.` The hidden build kept meeting the dialog until its save timed out
after 3 minutes; nothing was saved.

- **Fix:**
  - The viewer names a new project's output so that both names fit in 30 characters (`project.js` `outputNames`):
    at most 12 characters of the map's name, then as much of the project's name as fits, then 4 digits of its id.
  - The compiler refuses longer names and says to save the project as a new one.
  - patchtool refuses a spec `name` or `map.shipAs` over 30 characters before it opens the editor.
- Projects made before the fix keep their names (no migration before the tool is public); saving one under a new
  name (Save as…) gives it short ones.

### T-08: Renamed-map registration assumes stream slot 1 is replaceable

**Verified** (6 Nov, [EXP-10](experiments/EXP-10-variant-stream-slot.md) run 1, on URB_Bar). Read-only check in
[EXP-09](experiments/EXP-09-editor-placement-audit.md): `Set-ShipConfig` in patchtool unconditionally substituted the
patch into `StreamingMaps[1]`. In the recorded Temple Ship map configuration that slot contains
`CIN_TP12A_ArriveTempleShip`; the old rule would replace its arrival cinematic. No Temple deployment was attempted.

- **Wider than Temple.** In LWR v2.06.03's `DefaultMaps.ini`, slot 1 holds an intro, a mission stream or a cinematic
  rather than a patch in 47 of 161 records with streams. Slots are sparse in 120 of 188 records (URB_Bar: 0, 1, 5).
  - Slot 5 is `patch_hide_randomized_objects` in 119 records.
  - In the lab's Bar logs, the travel loads only the slots before the first gap. Slot 5 arrives later through
    `AddStreamingMap`.
- **Fix:**
  - The spec field `map.streamSlot` takes a slot number (default 1, as before) or `"free"`: the lowest slot the base
    record does not use, added to the shipped record so every stream stays. That is slot 2 for both Bar and Temple.
  - patchtool warns when a numbered slot replaces a stream that is not a `patch_*` map.
  - Checked without the game: `tools/patch/tests/test_ship_record.ps1`, 66 of 66 against LWR's real records.
- **Verified in game** (EXP-10 run 1):
  - URB_BarSlot's record kept slots 0, 1 and 5 and added `patch_exp10slot` in slot 2.
  - The travel loaded slots 0 to 2, and `patch_hide_randomized_objects` streamed after the load.
  - `patch_bar`'s 28 actors loaded once, the intro played, and the patch's wall stood in the game with high cover.
- **Still to do:** before a Temple build profile is verified, test the renamed map's mission initialization and
  progression (plan M4).
- **Choosing the base record.** 65 map names have several records, and for 38 of them the free slot differs between
  records. patchtool takes the first record with the map's `Name`, so the editor must choose the base record by
  `DisplayName`. That is fine for URB_Bar.

### T-01: The authoring editor on the hidden desktop needs DirectX 11
**Verified** (3 Nov). With DirectX 9 it stops at a "floating point render targets" box, because DirectX 9 finds no
hardware on an undisplayed desktop. patchtool passes `-dx11` there.

### T-02: Everything that drives the editor runs on the hidden desktop
**Verified.** Window lookups and window messages only reach windows on the caller's own desktop. So patchtool runs
its whole build step there (HiddenRun), not just the editor.

### T-03: The cooker can't run on the hidden desktop
**Verified.** `UDK.com CookPackages` exits 3 there, with no log, with or without a console. patchtool cooks on the
user's desktop without a window.
- Never give it a new console: a new console opens in Windows Terminal, on the user's desktop.

### T-04: Changed scripts stop the editor at a prompt nobody sees
**Verified** (00:20, 4 Nov: patchtool compiled the changed scripts itself, then built). Extended 01:05: a failed
make deletes the packages it was rebuilding (`XComGame.u`, `XComMapEd.u`). The check only compared existing packages,
so the next build opened the editor into the prompt again. It now also counts a missing package as stale, going by
`EditPackages` in `UDKEngine.ini`.
- Symptom: "the editor did not open in 3 tries".
- Cause: the editor asks to recompile when a `.uc` file is newer than its package, and on the hidden desktop the
  question is invisible.
- Fix: patchtool runs `UDK.com make` first when any package is older than its sources.

### T-05: Game functions must be declared in the UDK-side stubs
**Verified.** The authoring XComGame classes are stubs. Any game function the patch calls must be declared there with
the game's exact name and signature; the body doesn't matter. Added so far in `XComDestructibleActor` and
`XComWorldData`:
- `ApplyDamageToMe`;
- `RebuildTileDataExtents`, `IsRebuildingTiles`, `SetRebuildTileProcessRate`, `IsLocationFlammable`.

The real code is in `<lab>\reference\XComGame-decompiled\`, and LWR's mutators are in
`<lab>\reference\XComLZMutator-decompiled\`.

### T-06: The game log runs behind
The game writes `Launch.log` only when its buffer fills: about a minute behind during play, and longer when the game
sits idle. An F9 look can come before the log lines for what it shows.

### T-07: Saving crashes while WSL2's hypervisor runs
**Accepted.** A save crashes (Address 0x0) because of the exe's CEG CPU check, not the mods. Either test without
saving (autosave off), or turn the hypervisor off yourself (`bcdedit /set hypervisorlaunchtype off`, reboot; `auto`
restores it). The copy protection's stored values must never be patched. Since 7 November 2026 the hypervisor is
off on the test PC, so game checks can save.
