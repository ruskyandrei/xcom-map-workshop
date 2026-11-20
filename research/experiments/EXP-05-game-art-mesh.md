# EXP-05: Place a piece of the game's own art (plan)

Status (3 November 2026, 22:05): **Route B passed.** A patch can show the base map's own art with its real game
materials, borrowed from memory at level start.

Every finding from these runs, with its status and fix, is listed in
[`research/findings-register.md`](../findings-register.md) (IDs F-xx and T-xx). This file keeps the run-by-run story.

## Route B build (21:40–21:50)

- **New script package `XComMapEd`** in the authoring UDK:
  - `Development\Src\XComMapEd\Classes\XComMapEdBorrowedMesh.uc` extends `DynamicSMActor` (placeable). It has
    `var() string MeshPath`.
  - In `PostBeginPlay` it calls `FindObject(MeshPath, class'StaticMesh')`, then `SetStaticMesh` and
    `LightEnvironment.SetEnabled(true)`. It logs `XComMapEd: ...` either way.
  - It has no collision.
  - Registered as `+NonNativePackages` and `+EditPackages` in `DefaultEngine.ini` (backup
    `<lab>\exp05\DefaultEngine.ini.orig`). `UDK.com make`: 0 errors, 0 warnings.
- **Checked against the game's `Engine.upk`:**
  - `DynamicSMActor` has `StaticMeshComponent` and `LightEnvironment`.
  - `StaticMeshComponent.SetStaticMesh(StaticMesh, optional bool)` and `LightEnvironment.SetEnabled(bool)` have the
    same signatures as in UDK.
- **patchtool's new object type, `borrow`:** `meshPath`, plus an optional placeholder `mesh` (default
  `CoverPatch.High2x2`), `yaw`, `scale` and `extra`.
- **Editor quirk found:** `MAP IMPORTADD` silently drops the first actor in the file when that actor is non-static.
  - Tested with our class, with `XComMapEdProbeInterp` (an `InterpActor` subclass) and with two copies of our
    class: the first copy was dropped.
  - A `Note` or `XComLevelActor` first is kept.
  - patchtool now writes a `Note` first when the spec starts with a borrow.
  - `ACTOR ADD CLASS=...` from the command box crashes the editor.
- **Mesh bounds, read from `URB_Bar.upk`:** `VEH_CompactCarB.Meshes.CarCompactB` spans z −1.9..105.6,
  x −80..80 and y −103..191. Its pivot is at ground level near one end, so it is about 3 tiles long and 2 wide.
- **Spec and deploy:**
  - `tools/patch/examples/exp05.json` places the car at (−2592, −960, 4), where EXP-04's block stood. If the borrow
    fails, the dark High2x2 placeholder shows instead.
  - `patchtool all` took 26 s. The cooked `patch_exp05.upk` (69,926 bytes) carries the `XComMapEd` class and the
    actor with `MeshPath = 'VEH_CompactCarB.Meshes.CarCompactB'`.
  - Lab `DefaultMaps.ini` line 36 now streams `patch_exp05` (it was `patch_exp04`).

## Try 1 in game (21:52): right mesh, flat grey

- **Log.** `ScriptLog: XComMapEd: XComMapEdBorrowedMesh_900 now shows VEH_CompactCarB.Meshes.CarCompactB`, 1.4 s
  after `SeamlessTravel: loaded additional map patch_exp05`. The log has no material warnings.
- **What it looks like.** Screenshots: the user's two shots (`<lab>\exp05\look1.webp`; crops `look1-car.png`
  and `look1-suv.png`).
  - The car's shape is right and it sits on the ground, about 3 tiles long.
  - It renders flat grey/white with no texture: tyres the same grey as the body. Compare the map's own SUV, which is
    textured.
  - The windows are open, with the seats visible through them.
- **Why.** In `URB_Bar.upk` the car's materials sit on the components, not on the mesh:
  - the prefab archetype `VEH_CompactCarB.Prefab.PRE_CompactCarB.PRE_CompactCarB_Arc1` (an `XComDestructibleActor`)
    has `StaticMeshComponent0` referencing `VEH_CompactCarB.Materials.VEH_CompactCarB`;
  - each placed car (for example `XComDestructibleActor_20.StaticMeshComponent_150`) wears its own tinted instance,
    `VEH_CompactCarB_Tinted`.
  - The bare mesh shows no reference to its material, so it falls back to the plain default material.
  - The glass is a separate `FracturedStaticMesh` (`CarCompactBGlass_FRACTURED`) on another prefab actor (`_Arc0`),
    hence the open windows.

## Try 2 (built 21:57): copy the materials too

- **Class change.** `XComMapEdBorrowedMesh` gained:
  - `CopyFromPath`: an actor or archetype in memory whose first static mesh component's mesh and materials are
    copied;
  - `MaterialPaths`: materials by element.
- **Tool change.** patchtool's `borrow` gained `copyFrom` and `materials`.
- **The two cars in `patch_exp05`:**
  - Car A at (−2592, −960) copies from the prefab archetype.
  - Car B at (−2592, −560) names the mesh and `VEH_CompactCarB.Materials.VEH_CompactCarB` directly.
  - Both are untinted, so their paint may be the base colour.

## Question

Can a patch show a mesh from the game's own art, such as a car or a dumpster, with its real materials?
EXP-04 used `CoverPatch.High2x2`, a plain block made by a modder.

## What the installed patches tell us (static scan of all 90 `patch_*.upk`)

Scan script: `python tools/upk/scan_patch_art.py`. Pass a folder and a glob to scan other packages.

- **51 static meshes appear in the patches, all modder-built.** They are mostly `CoverPatch.*` blocks and
  `LadderMetal.*` ladders. A few look like game art: `Eurosedan_DESTRO`, `MercSUV_DESTRO`, `VEH_DestroyedHull.*`,
  `AlienCrate`, `treeCover.*`. Their `SourceFilePath` shows they were imported from FBX files in 2015 (copies, not
  game objects).
- **The patches carry no textures or base materials.** They hold only 7 material instances, each with no `Parent`.
  The only material imports in all 90 are `EngineMaterials.DefaultMaterial`, `DefaultDiffuse`, `DefaultNormal` and
  `DefaultParticle`. So the car-like meshes in patches render with the default material, or are hidden or
  collision-only. This matches the 2014–15 reports that new materials "fall back to DefaultMaterial".
- **Kismet mesh swaps are unused.** No installed patch uses `SeqAct_ReplaceActorMesh`, `SeqAct_LoadContent` or
  `SeqAct_SetMesh`, although `XComUDK` defines the first two.
- **Firaxis does not reference art across packages either.** Its own mission streams (`URB_CommercialAlley_CovExt`,
  `URB_PierA_Terror_CovExt`) import no art; each carries its own few meshes.
- **The base map holds the art.** Environment art isn't in standalone packages: all 2,980 packages in
  `CookedPCConsole` are maps, units, weapons, voices and so on. Each map carries its own art under the original
  package names. `URB_Bar.upk` holds 324 static meshes, 252 material instances, 108 materials and 593 textures, e.g.
  `Dumpster_A.Meshes.Dumpster_A`, `VEH_CompactCarB.Meshes.CarCompactB` and `VEH_SedanB.*`.
- **How the swap actions load content.**
  - `SeqAct_ReplaceActorMesh` loads through `XComContentManager.GetGameContent(tag)`, and the tags come from
    `[Content.GameContentTags]` in `DefaultContent.ini` (uniforms, weapons and the like). It can't reach map art
    by path.
  - `SeqAct_LoadContent` uses `RequestObjectAsync(path)`, which loads by path from a package on disk.

- **What the Uncooker's author says about copies** (`research/evidence/upstream/XCOM-Uncooker/README.md`, Known
  issues and FAQ):
  - EW can't compile materials at runtime.
  - Cooking strips a material's node graph, so uncooked materials are only partly rebuilt, and many render black.
  - Materials recooked from our UDK count as new even when they are the game's own, so they need compiling. A cooked
    copy of a game mesh plus its materials therefore falls back to the default material in the game, unless LWCE's
    executable patches 3 and 4 (runtime compilation) are applied.
- **Runtime mesh swaps need a movable actor.** The modder's swap actions (`SeqAct_ReplaceActorMesh`, and
  `XComMapCleaner`'s `SeqAct_ReplaceMesh`) act on `XComDestructibleActor` and call `SetStaticMesh` and then
  `ForceDLELighting`. The placeholder should be that class, or another non-static actor, and it gets dynamic lighting,
  not lightmaps.

## Routes to test, cheapest first

### Route B: borrow the mesh from the loaded base map (most promising)

While URB_Bar is loaded, its meshes are in memory under their original names, so `DynamicLoadObject("Dumpster_A.Meshes.Dumpster_A", class'StaticMesh')` should find them without touching disk.

1. **Add a small Kismet action to `XComUDK`**, for example `SeqAct_SetMeshByPath(Target, PathToMesh)`. It works
   like `SeqAct_ReplaceActorMesh`, but loads the mesh with `DynamicLoadObject` and logs whether it was found.
2. **Build the patch with two parts:**
   - a no-collision `XComLevelActor` or `StaticMeshActor` with a placeholder mesh, which the action swaps for the
     game mesh on Level Loaded;
   - a hidden `CoverPatch` block giving the gameplay shape: collision and cover. The visual mesh stays purely
     cosmetic, the same split the installed patches use (hidden cover blocks plus `UDK_NO_COLLISION` meshes).
3. **Check in game:** is the mesh visible, with real materials and correct lighting? Does it cast shadows? Is the
   placement right? Does the cover from the proxy still hold?
4. **The limit:** this only offers meshes the base map (or another loaded stream) already contains. For a map
   editor that is still a large palette: 324 meshes for URB_Bar.

### Route A: cook a copy of the mesh into the patch

1. **Export** the mesh, its material instances, parent materials and textures with the uncooker (the reference UDK
   from EXP-02).
2. **Cook** them into the patch.
3. **Risks:** materials, shaders and textures. This is the documented fallback-to-default problem, and the
   separately named texture caches are untested. It is useful for using art from other maps, so it is worth one try
   after Route B.

### Route C: reference the mesh without cooking it in

Cook the patch so the mesh stays an import from another package. Firaxis never does this. The risk is a load error
or crash if the import can't be resolved. Try it last, and only with a save at hand.

## Pass criteria

- The game mesh is visible with its real materials: no default-material checkerboard.
- Collision and cover come from the proxy as in EXP-04.
- There are no errors in `Launch.log`.
- Saving and reloading mid-mission keeps the swapped mesh.

## Try 2 in game (22:02, first F9 look): both cars textured

- **Log:**
  - `XComMapEdBorrowedMesh_900 now shows VEH_CompactCarB.Meshes.CarCompactB with the materials of
    VEH_CompactCarB.Prefab.PRE_CompactCarB:PRE_CompactCarB_Arc1.StaticMeshComponent0`
  - `XComMapEdBorrowedMesh_901 now shows VEH_CompactCarB.Meshes.CarCompactB`, with its material named directly
  - Both lines come 1 s after the patch loaded. There are no material warnings.
- **Screenshot:** `<lab>\exp05\look2.png` (crops `look2-carA.png` and `look2-carB.png`).
  - Both cars are fully textured: tyres with tread, wheel rims, headlights, grille, wipers, door trim and seats.
  - Car A, under the street lamp, looks cream-white; car B looks silver-blue in the night light. The paint is the
    base colour, because neither gets the per-car tint (`VEH_CompactCarB_Tinted`) that the map's own cars wear.
  - The windows are open, since the glass is a separate fractured mesh.
- **Both ways work:**
  - copying mesh and materials from an archetype in memory (`copyFrom`);
  - naming the mesh and material paths directly (`meshPath` + `materials`).
  The archetype copy is the easier one to write in a spec.

### What this means

- **New layouts can reuse any art the base map has loaded**, with Firaxis's own compiled materials, and nothing new
  is cooked into the patch. URB_Bar alone has 324 meshes. The patch carries only the 1 KB actors and the `XComMapEd`
  class.
- **Still to do:**
  - **Collision and cover.** Pair each borrow with a hidden cover patch, or test switching collision on for the
    borrowed mesh itself and rebuilding world data.
  - **Paint tint.** Borrow a placed car's tinted instance, or make a `MaterialInstanceConstant` at run time with the
    borrowed material as parent and set its colour parameter. A runtime instance of an existing material needs no
    new shader. The same mechanism with texture parameters is the "new texture on an existing material" test.
  - **Glass and other prefab parts.** These are `FracturedStaticMesh` pieces (`XComFracLevelActor`).
  - **Save and reload mid-mission.** `PostBeginPlay` should run again on load, but this is untested.
  - **Other base maps,** and art from a map other than the base one: Route A or C.

## Step 2: real cars, spawned from the map's own archetypes (built 22:14)

- **Goal (user, 22:05).** Make the borrowed car a working map piece, with paint and cover. Also: a line of 10 cars
  to throw grenades at (does the glass shatter, do they burn), to use as cover, and to save and reload.
- **What URB_Bar's own cars are.** Each is two actors built from the prefab
  `VEH_CompactCarB.Prefab.PRE_CompactCarB`:
  - the body `_Arc1`, an `XComDestructibleActor`:
    - `Toughness = GameData_Toughness.Toughness_SMALLCAR` and `CoverForceFlag = CoverForce_Low`;
    - 3 damaged and 5 destroyed events (swap mesh, effects, sound, damage over time);
    - `HidingPartner` set to the glass;
  - the glass `_Arc0`, an `XComFracLevelActor` with `Toughness_GLASS` and `bAlwaysFracture`, placed 2 units
    behind the body.
  - Placed cars set `TintColor` (`LinearColor`). URB_Bar's are (0.41, 0, 0.02), (0.77, 0.71, 0.42) and
    (0.48, 0.48, 0.48). All sit at z 0.
- **Can they be spawned?**
  - `XComLevelActor` sets `bStatic=false` and `bMovable=true`; `XComFracLevelActor` sets `bNoDelete=false`. So both
    can be spawned at run time with the archetype as template: `Spawn(class, , , loc, rot, ActorTemplate, true)`.
  - The event actions are `export editinline`, not instanced, and act on their outer (`within
    XComDestructibleActor`). A spawned car would share the archetype's actions, so the spawner gives each car its
    own copies with `new(car) Action.Class (Action)`.
- **Saves.** `Checkpoint_TacticalGame` records `XComDestructibleActor` and `XComFracLevelActor`; a destructible
  only once it is no longer pristine. Both classes are in `ActorClassesNotToDestroy`. Records are matched by actor
  path, so a reload might bring back a damaged copy beside a freshly spawned one. The spawner checks after 5 s and
  removes its own car if another of the same archetype sits within 16 units.
- **New class `XComMapEdSpawner`:**
  - It finds `ArchetypePath` (and `PartnerPath`) in memory and spawns them, the partner at `PartnerOffset`.
  - It sets `HidingPartner` and copies the actions.
  - If `bTint`, it sets `TintColor` and calls `UpdateTintColor()`.
  - After 1 s it calls `XComWorldData.RebuildTileDataExtents(Location, RebuildExtent)`. This needed a one-line
    declaration added to the editor's `XComWorldData` stub, copied from the game's class (backup
    `<lab>\exp05\XComWorldData.uc.orig`).
  - patchtool type `spawn`: `archetype`, `partner`, `partnerOffset`, `tint`, `rebuildExtent`, `yaw`.
- **Where.** `tools/upk/map_layout.py` (new) maps URB_Bar's ground-level occupancy from actor bounds:
  `<lab>\exp05\urb_bar-layout.png`. The level volume `XComLevelVolume_4` spans x −2784..2208 and
  y −1920..1824 (tiles 0..51 × 0..38), which confirms the grid origin. The only clear strip inside it big enough
  for 10 cars side by side is tiles x 29–47, y 5–7 (world x 0..1824, y −1440..−1152, asphalt at z 0). It continues
  the parked row of SUVs and a sedan at y ≈ −1150.
- **Patch `patch_exp05cars`:**
  - spec `tools/patch/examples/exp05cars.json`: 10 spawners at x = 91 + 182·i, y −1334, yaw 0, each with its own
    tint, plus one rebuild volume over the strip;
  - `patchtool all` took 29 s and the cook is 74,452 bytes;
  - the lab `DefaultMaps.ini` line 36 now streams `patch_exp05cars`.

### Cars, run 1 in game (22:16, F9 look `<lab>\looks\look-221625.png`)

- **Log.** At 23.85 s, 1 s after `loaded additional map patch_exp05cars`, all 10 spawners logged
  `spawned XComDestructibleActor_N` and `XComFracLevelActor_N` from the prefab archetypes. At 24.83 s all 10
  logged `rebuilt tile data around ...`. There are no script warnings from XComMapEd.
- **Screenshot.**
  - Ten cars stand side by side in the strip, with headlights and the right shape.
  - Cover shields show at the cursor tile next to a car, and the move path routes around the row.
  - The cars render **nearly black**. Spawned at run time they have no lightmap, and the destructible's light
    environment (`MyNEWLightEnvironment`) is disabled by class default. Firaxis's `ForceDLELighting()` (enable the
    light environment, attach it, ignore lightmap data) is what `SeqAct_ReplaceActorMesh` calls after a mesh swap.
- **Fix, built 22:17:** the spawner calls `ForceDLELighting()` on the spawned destructible. It is cooked (74,484
  bytes) but not deployed: the game is running, and patchtool won't write to the game folder while it runs.

### Cars, run 2 (22:21, F9 look `look-222101.png`): still dark; spawned names are stable

- **The patch with `ForceDLELighting()` loaded, and all cars still render nearly black.**
- **The spawned actors got the same names as in run 1** (`XComDestructibleActor_9`, `_24`, `_25`, `_109`, `_144`,
  `_147`, `_153`, `_155`, `_156`, `_163`; glass `XComFracLevelActor_25` ... `_43`). Spawning fills gaps in the
  persistent level's numbering, in the same order each time. `--- LOADING CHECKPOINT ---` (the start-of-mission
  checkpoint) then "Checks" exactly these names. So save records should land on our cars by name.
- **Suspected cause.** The template's mesh component has `bUsePrecomputedShadows`, which is `const` in script. The
  map's static lights may then skip it even with a light environment.
- **Next build (cooked 22:24, deploy after the game is closed):** `LightMode` per spawner, two cars per mode from
  x 0 upwards:
  - 0: none;
  - 1: `ForceDLELighting` at spawn;
  - 2: 0.5 s later, `ForceDLELighting` plus `bDynamic`, `ReattachComponent` and `ResetEnvironment`;
  - 3: as 2, plus `AmbientGlow` (0.25, 0.25, 0.28);
  - 4: as 2, plus `bSynthesizeSHLight` and shadows.

### Cars, run 2 continued (22:24, F9 look `look-222443.png`): the grenade did nothing to them

- **The user's note (typed into the game console):** "Threw a grenade and it doesn't appear to have done damage to
  the black cars. Even the windows are intact."
- **The map's own sedan next to the row burned.**
- **Log at 184.08:** the HE grenade logged 4 × `Ucross FracLevelActor Damage Type:XComDamageType_Explosion /
  Amount:35` and 5 × `Ucross Damage Type ... 35`. These come from LWR's logging in `ApplyDamageToMe`, via
  `XComProjectile.DealSplashDamage` → native `XComDamageType.DealDamage`. The lines don't name the actors.
- **Timing.** The spawns happen at the world's first BeginPlay ("Bringing World URB_Bar up for play" at 26.99 s,
  spawns at 27.15 s), before `XGLevel.OnStreamingFinished` → `InitFractureSystems()`. So a missed fracture-system
  registration is not obviously the cause.
- **Next build (deployed 22:29):** the lighting comparison, plus `WatchMain`, which logs every change in a spawned
  car's `Health` or state. The next grenade then shows whether explosions reach our cars at all.
- **Idea to try if they don't.** Object-path shadowing: place the cars in the patch as level actors whose archetype
  path matches the map's (`VEH_CompactCarB.Prefab.PRE_CompactCarB.PRE_CompactCarB_Arc1`), through a stub archetype
  in the authoring UDK, so that at load the game may use its own in-memory archetype. The authoring content already
  carries same-path copies made by the modder (for example `VEH_SedanB.Materials.MINST_SedanB` and
  `VEH_SedanB.Meshes.SedanBFull`).

### Cars, run 3 (22:45–22:46, F9 looks `look-224556.png`, `look-224637.png`): damage reaches them; no relighting works

- **Lighting.** All ten cars are equally black, whatever their `LightMode` (0–4). Not even the ambient glow of mode 3
  shows, so the light environment doesn't reach the mesh at all.
- **Why.** The game's `XComDestructibleActor.ForceDLELighting`, decompiled with `UeDecompile.exe`, only does three
  things:
  - `LightEnvironment.SetEnabled(true)`;
  - `StaticMeshComponent.SetLightEnvironment(LightEnvironment)`;
  - `StaticMeshComponent.bIgnoreLightMapData = true`.

  The copied component keeps `bUsePrecomputedShadows=TRUE` from `StaticMeshActor`'s defaults, and that flag is
  `const` in script. The borrowed cars of try 2 rendered properly because their own class, a `DynamicSMActor`,
  defaults to `bUsePrecomputedShadows=FALSE`, with its light environment set from the start.
- **Grenade.** The HE grenade preview outlined the spawned cars red as targets ("Targets: 4"). After the throw
  (log 952.65), `WatchMain` logged:
  - `XComDestructibleActor_24` 500 → 479;
  - `_25` 500 → 485;
  - `_109` 500 → 482.

  All three stayed `_Pristine`. So explosions do reach them.
  - `Toughness_SMALLCAR` gives 500 health, and the same goes for the map's own compact cars (their instances set no
    health of their own).
  - The damaged state begins below 75 % (`DestructibleActorDamagedThreshold`), so one grenade is far from enough.
  - The car that burned was `XComDestructibleActor_33`, a `PRE_SedanBWreckA` (a pre-wrecked sedan), so it is not
    comparable.
- **Glass.** Four `FracLevelActor Damage Amount:35` lines, but the user saw the windows intact. Whether a grenade
  breaks the windows of the map's own compact cars is still to be checked as a baseline.
- **Fix (built and cooked 22:52, deployed 22:53 after the user quit the game):**
  - New class `XComMapEdDestructible extends XComDestructibleActor` in `XComMapEd`. Its defaults set
    `bUsePrecomputedShadows=false`, `bForceDirectLightMap=false` and the light environment (enabled, dynamic).
  - `CopyFrom(archetype)` takes from the archetype: mesh, materials, damaged and destroyed events (with its own copies
    of the actions), toughness and health, cover and visibility flags, tag and tint.
  - The spawner uses it for every destructible archetype. The `LightMode` comparison is removed.
  - The cooked map exports the new class.

### Cars, run 4 (22:55, F9 look `look-225525.png`): the new class spawns but is still black

- **Spawns.** `XComMapEdDestructible_0` to `_9` were spawned with their glass. Each has health 500 of 500, state
  `_Pristine`. The start checkpoint checks them by name.
- **Still dark.** All ten cars look as before. The two nearest the street lamp show a faint tint, so a little light
  does reach them. So `bUsePrecomputedShadows` was not the cause, or not the only one.
- **New suspect: ticking.** `XComLevelActor` (and `XComFracLevelActor`) default to `bTickIsDisabled=true`. Actor.uc
  says that then "this Actor and all of its components are not ticked". A light environment computes its lighting
  in its tick, so it never gets any. The map's own destructibles call `ForceDLELighting` only in states where they
  tick. `DynamicSMActor`, the skip cars' class, ticks normally.
- **Fix (built 22:56, deployed 22:57):** `XComMapEdDestructible` sets `bTickIsDisabled=false` and calls
  `SetTickIsDisabled(false)` after `CopyFrom`.

### Cars, run 5 (23:04, F9 look `look-230412.png`): lit and painted

- **Result.** All ten cars render properly lit, each in its own paint:
  - red, cream, grey, blue, green, orange;
  - near-black (tint 0.02 as specified), white, teal, purple.

  They sit next to the map's own cars without standing out. The user's note: "NICE!".
- **So the cause was ticking.** The light environment only computes light while its actor ticks, and level actors
  don't tick. `bUsePrecomputedShadows=false` is probably needed as well; it was set in both runs.
- **Still to test:**
  - glass breaking from a grenade, compared with one of the map's own compact cars;
  - cover;
  - save/reload (names are stable: `XComMapEdDestructible_0`–`_9`).
- **Cover (23:05, F9 look `look-230540.png`): works.** The move preview to a tile beside the row, between the white
  and the near-black car, shows cover shields on the sides facing the spawned cars. More shields appear along the
  row, by the orange car. The shields look like the half (low) ones, which matches `CoverForce_Low`. So the tile
  rebuild picks up the spawned cars as cover.

### Cars, run 5 continued (23:06–23:07, F9 looks `look-230642.png`, `look-230721.png`): the map's car burns, ours don't

- **The throw.** One HE grenade (log 216.42) reached our cars 7–9 and the map's own cream compact car
  `XComDestructibleActor_20`, which has the same archetype.
- **The map's car caught fire.** Ours only lost health: 500 → 485, 484 and 480, still `_Pristine`.
- **The damage code, decompiled (`XComDestructibleActor.ApplyDamageToMe`):**
  - damage = the projectile's `WorldDamage` (35) × random 0.75–1.25 × distance falloff 0.5–1;
  - `_Damaged` (fire) begins below 75 % of `TotalHealth`, and `_Destroyed` at 0;
  - `Toughness_SMALLCAR` is 500 for both kinds of car.

  So the grenade alone can't set a car alight.
- **The difference is the glass.** Every placed `XComFracLevelActor` carries baked `FragmentColumns`: the cream car's
  glass `XComFracLevelActor_10` has 6. Each column is the glass inside one world tile, with:
  - `Bounds`, the fragment boxes clipped to the tile, over Z 61.1–253.1;
  - `FragCache`, its fragment indices sorted by `MinZ`;
  - `DestructibleCache`, the car (`XComDestructibleActor_20`, MinZ −2.9).

  The archetype `PRE_CompactCarB_Arc0` has no columns. So our glass gets the splash damage
  (`TakeSplashDamage` → `BreakOffPartsInRadius` → native `ApplyDamage`), but there is nothing for it to break. The
  glass has `bAlwaysFracture`, which makes its hit damage 1000. That damage most likely reaches the car as collateral
  damage through `DestructibleCache` (`TakeCollateralDamage` → `ApplyDamageToMe`), which would be what sets a placed
  car alight.
- **Fix (built 23:15, deployed 23:16):** `XComMapEdSpawner.BuildFragmentColumns` gives the spawned glass columns at
  the first tile rebuild:
  - one column per world tile (from `XComWorldData.WorldBounds.Min`, 96-unit cells) that the fragment boxes
    (`GetFragmentBox`) cover;
  - bounds clipped as in the baked data;
  - the fragments sorted by `MinZ`;
  - our car in `DestructibleCache`.

  `WatchMain` now also logs the glass's visible-fragment count.
- **Tooling.** The cooker won't run on the hidden desktop (exit 3, no log, within a second), so patchtool builds there
  and cooks on the normal desktop without a window.
- **Save/reload, first check (user, 23:08; log `Launch-backup-2026.11.03-23.17.56.log`): works for undamaged cars.**
  - The save was made at 164 s, before that session's grenade (214 s). The reload at 321 s brought URB_Bar back.
  - The spawners made the same `XComMapEdDestructible_0`–`_9` again. The checkpoint loaded 149 + 10 actors.
  - The cars came back at 500/500 `_Pristine`, as they were at the save. No "restored at its spot" removals, so no
    duplicates. The user saw it working.
  - A grenade after the reload (340 s) took car 7 to 471 and car 8 to 486.
  - Still to check: whether damage persists, with a save made after the cars are damaged.

### Cars, run 6 (23:19, F9 look `look-231948.png`): the glass breaks; the cars still don't burn

- **Columns built.** Each spawned glass got 6–9 fragment columns over its 21 fragments, with the car for collateral
  damage. Cars 3–5 get 8–9 columns, since their tile-grid offset differs.
- **The glass breaks.** One HE grenade (log 61.12) shattered the windows of cars 8 and 9 (`XComFracLevelActor_41` and
  `_43` went from 21 to 7 visible fragments); the screenshot shows their windows open.
- **The cars don't burn.** Cars 7–9 lost 19–26 health and stayed `_Pristine`. The map's cream compact car next to
  them burned again. So the columns' collateral path isn't what sets a placed car alight. That fits the decompiled
  `ApplyDamageToMe`, which ignores collateral damage (`XComDamageType_DestructibleActorClear`) to a non-fragile car if
  that damage type doesn't cause fracture.
- **The user's note:** "threw grenade, can't tell if it did anything to our new cars".
- **Next build (cooked and deployed 23:27):**
  - `XComMapEdDestructible.ApplyDamageToMe` logs every hit (type, amount, causer, health, state) before the game
    applies it. The stub `XComDestructibleActor.uc` gained the declaration; backup in
    `<lab>\exp05\XComDestructibleActor.uc.orig`.
  - Spawner 909 has `WatchRadius=700`. It logs the start values and every change of the map's own destructibles
    nearby, including the cream car `XComDestructibleActor_20`, with their last damage.

    This tells whether the map's car starts the mission damaged (from the save) or takes more damage per grenade.

### Cars, run 7 (23:29, F9 look `look-232918.png`): the map's car and ours take the same damage

- **Start.** A fresh mission start (checkpoint with 8 actors). All ten spawned cars are 500/500 `_Pristine`. The
  watched map destructibles are also at full health:
  - cream compact car `XComDestructibleActor_20`: 500/500, `Toughness_SMALLCAR`;
  - two `ARC_ParkingBlock`: 80/80, `Toughness_MASONRY`.
- **One HE grenade (log 39.23–41.63):**
  - each of cars 7–9 got one hit, `XComDamageType_Explosion`, amount 35, from `XComProjectile_FragGrenade_0`;
  - they went to 485, 487 and 483 health and stayed `_Pristine`;
  - their glass went from 21 to 16, 14 and 14 visible fragments;
  - the map's cream car went 500 → 481 and stayed `_Pristine` (its last damage: Explosion, 19, from the same
    grenade).
- **So the map's car got no special treatment.** Yet the screenshot shows flames on the cream car's hood. That isn't
  its damaged state, which it never entered.
  - After `DealDamage`, `XComProjectile.DealSplashDamage` (decompiled) creates `DamageRadius / 96 + 1` fires
    (`m_kVolumeMgr.CreateVolumeByType(3, ...)`), when the damage type sets fires.
  - Each fire is placed at a random entry of `XComWorldData.PotentialFireColumns`. That list is filled when things
    break.
  - This fits the warnings "Attempt to remove element N in an 1-element array 'PotentialFireColumns'" seen earlier.
  - So the flames are most likely a fire started next to the car. That fire would burn the car over the next turns,
    matching the user's experience that cars "explode a couple of turns later".
- **Next:** end the turn a couple of times and watch which cars the fires burn. The log records health and state
  changes for the cream car and for ours.

### Cars, run 8 (23:35–23:37): a grenade at the middle of the row

- **Throw.** HE grenade at log 66.01, aimed at the middle of our row, away from the map's cars.
- **Damage.** One hit each on cars 4–7 (Explosion, 35):
  - health went to 483, 474, 471 and 478, all still `_Pristine`;
  - the glass of cars 4, 5 and 6 was all but wiped out (21 → 1, 0 and 0 visible fragments); car 7's glass didn't
    change.
- **Not yet known:** whether a fire started on our cars. The F9 look `look-233610.png` was taken before the log
  caught up, so it doesn't settle it. The game writes its log in batches, about a minute behind.
- **After the blast (23:38, F9 look `look-233805.png`):** no fire anywhere on our row. The orange and near-black cars
  (5 and 6) visibly have no glass left. So far, fire has started only on the map's cream car, three times out of
  three, and never on ours.
  - Possible causes: where fires go depends on per-tile data that the map bakes and our tile rebuild doesn't recreate
    (for example "flammable" tiles); or fires are rolled at random and land near the map's objects.
  - Next checks:
    - whether a burning map car actually explodes a few turns later (end turns with the cream car burning);
    - logging where the fire volumes appear (`m_kVolumeMgr`).

### Glass names change between loads, so saves would lose broken windows (found 23:40; fix cooked 23:43)

- **What happened.** At 266 s the user restarted the mission in the same game session. The cars came back as
  `XComMapEdDestructible_0`–`_9` again, but the glass came back as `XComFracLevelActor_46`–`_57` instead of `_25`–`_43`.
  The same happened at the 23:08 reload in session 23:03.
- **Why.** A new actor's name comes from its class's counter. `XComFracLevelActor` is in XComGame, which stays loaded
  for the whole session, so its counter runs on. `XComMapEdDestructible` is in the patch's own package, which is
  loaded afresh with each map, so its counter starts from 0 again.
- **The effect.** Checkpoints find actors by name. A save made on one load and loaded on another would miss the
  spawned glass, so broken windows would come back intact. The first reload test passed only because no glass was
  broken at that save.
- **Fix:** `XComMapEdGlass extends XComFracLevelActor`, in XComMapEd.
  - The spawner uses it for fracturing archetypes. `CopyFrom` takes the mesh (`SetStaticMesh`), materials, fragment
    bounds, shadow flag, toughness, `bAlwaysFracture`, impact settings, cover and visibility flags, tag and tint.
  - It can't set the Firaxis-only `bUseVertexColorDestruction`, `EditorPaintedVisibleFragments` or the rain render
    channel, which UDK's compiler doesn't know.
  - To check in game: the glass looks and breaks as before, and broken windows survive a reload.

### How cars "catch fire and explode" (user's police-car test, 23:40–23:43, F9 looks `look-234013.png` to `look-234317.png`)

- **What the user saw.** An HE grenade (log 307.56) at a map police car. Turn 1: on fire. Turn 2: "flames are spreading
  on the car". Turn 3: "car exploded".
- **The log.**
  - At the blast: one glass hit and two destructible hits, Explosion 35 each, then "Attempt to remove element 2 in an
    2-element array 'PotentialFireColumns'".
  - At the next turn change (alien turn 2, 483.48): `XComDamageType_AreaBurn` hit two destructibles and one glass for
    **8041** each, which destroys them. That is the explosion.
- **The mechanism.** The full decompiled XComGame is now in `<lab>\reference\XComGame-decompiled\`.
  - `XComDamageType.DamageTypeSetsFires`: every Explosion sets fires (intensity 2, or 3 for alien weapons); laser
    and plasma set intensity 1.
  - `XComProjectile.DealSplashDamage`: once `DealDamage` has dealt the hits, it starts `DamageRadius / 96 + 1` fire
    volumes at random entries of `XComWorldData.PotentialFireColumns`, if there are any.
  - In script, only a destroyed `XComDestructibleActor` adds an entry. All the other entries come from native code.
  - A fire on a car's tile then deals AreaBurn 8041 at the next turn change.
- **Why our cars never burn.** The mid-row throw (log 66–68 s) logged no `PotentialFireColumns` warning and started no
  fire, so most likely no entries were collected for our cars.
- **Next build (deployed 23:46):**
  - each hit on our cars logs the fire spots collected so far, with their positions;
  - glass changes log how many of the glass's columns are damaged and destroyed.

  One throw at our row and one at a map car will show what adds fire spots for the map's cars but not for ours.

### Cars, run 9 (23:49, F9 look `look-234954.png`): our glass adds fire spots; the new glass class needs chunk health

- **Glass names.** `XComMapEdGlass_0`–`_9`: the glass class from 23:44 works, and its names will match on every load.
- **The user's notes:** AP grenades don't start fires, and only one HE grenade was available. They threw it so that it
  hit cars 7–9 and the map's cream car.
- **Fire spots (log 73.13).** When the hits on our cars began, the blast had collected 5 spots:
  - 2 on our glass: (1571, −1383, 160.4) and (1697, −1383, 160.4);
  - 3 on the cream car's glass: (1684, −924), (1775, −922), (1829, −985), at Z 157.1.

  These are the centres of destroyed glass columns. So the native code adds a spot for each destroyed
  `FragmentColumn`, and our columns qualify. The fire again landed on the cream car: the fires go to random spots, and
  3 of the 5 were the cream car's.
- **New error.** For each of our glasses: 4 × `AXComFracLevelActor::CachedFrag.FragIndex >= ChunkHealth.Num` and
  `REBUILD PATHING!`. Our windows looked intact in the shot.
  - Cause: `ChunkHealth` gets sized by `ResetHealth()` in `FracturedStaticMeshActor.PostBeginPlay`. Our glass gets its
    mesh after spawning, so it had no chunk health.
  - Fix (cooked 23:51, deployed 23:51:38): `XComMapEdGlass.CopyFrom` calls `ResetHealth()` after
    `SetStaticMesh`.
  - The log of that session confirms it: our glass logged no change in visible fragments at all. Yet its columns
    still counted as destroyed, which is where the fire spots on our glass came from.

### Cars, run 10 (23:52–23:59, F9 looks `look-235431.png` to `look-235841.png`): glass breaks, still no fire, a Meld canister inside the row

- **Glass.** The `ResetHealth()` fix works. One HE grenade (log 142.05) hit cars 5–7:
  - visible fragments fell 21 → 5, 21 → 0 and 21 → 11;
  - 9 columns were destroyed;
  - the cars lost 18, 23 and 15 of 500 health;
  - no ChunkHealth errors.
- **Fire spots.** The blast collected 6 spots, all on our glass: x ≈ 949 and ≈ 1385, at Z 160.4. The user saw no fire,
  then threw a second grenade at the row: still no fire.
- **What the code says** (decompiled `XComProjectile.DealSplashDamage`, `XComDamageType.DamageTypeSetsFires`,
  `XGVolumeMgr.CreateVolumeByType`):
  - Explosion damage always sets fires, at intensity 2.
  - Fires are made only if the blast left a tile rebuild running (`IsRebuildingTiles()`). It did here: the log shows
    "WorldData: Restarting work queue (… now 41 tiles)" right after the hits.
  - While tiles rebuild, a fire volume waits 1 s before the game adds it (`CheckDelayAddVolumes`).
  - Grenades don't check flammability. The flamethrower does (`XComWorldData.IsLocationFlammable`), and that check is
    native.
  - So either no fire volume was made at our spots, or it was made and burnt nothing because the game doesn't count our
    car's tiles as flammable. Run 11 logs both: every new `XGVolume`, `IsLocationFlammable` at each fire spot, and a
    flammable count over our cars and over the map's car `XComDestructibleActor_20`.
- **Meld canister inside the row.** LWR places Meld canisters with `XComLZMutator.XComMeldSpawnMutator` (package
  `XComLZMutator.u`, decompiled to `<lab>\reference\XComLZMutator-decompiled\`). It replaces the map's canister
  spawn points with random tiles that pass `XComWorldData.IsPositionOnFloorAndValidDestination`.
  - It runs in `XGBattle_SP.PostLevelLoaded`, together with the pod and landing-zone mutators, just before
    `InitMeldContainers` and `InitPlayers`.
  - Log: our cars spawned at 24.30, the mutators ran at 24.45, and our tile rebuild only ran at 25.25. So the mutator saw
    the strip under the cars as open road. `XComMeldContainerActor_0` sat at (1487, −1297), between cars 7 and 8.
  - Rebuilds also run over several frames: 16 tiles a frame by default (`DEFAULT_REBUILD_TILE_RATE`), so ten cars take
    about two seconds.
- **Fix (run 11).**
  - The spawner rebuilds its tiles in `PostBeginPlay`, in the same frame it spawns, with the rate raised to 100000 tiles
    an update.
  - `WaitForTiles` logs when the rebuild has finished and sets the rate back to 16.
  - `CheckPlacements`, at 1 s, logs any Meld canister, canister spawn point or unit that ended up inside a car.

### Cars, run 11 (00:10–00:13, F9 looks `look-001215.png`, `look-001300.png`): placement fix in time; squad on the cars; still no fire

- **Tile timing (F-05).** The spawners rebuilt at 28.20 and the rebuild finished at 28.33. LWR's mutators ran at
  28.34, so they now see the cars. No WARNING from `CheckPlacements` for canisters.
- **Squad on the cars (F-06).** LWR's landing-zone mutator picked the zone at (719, −1681) facing North. Its six spawn
  points (x 527–911, y −1201 to −1489) lie on cars 3–5. Soldiers stood on the roofs, and the SHIV was wedged between
  two cars and couldn't move.
  - The user's note: "does that meld fix also apply to my guys spawning on top of the cars, and the shiv somehow
    floating in between and can't move ?"
  - `CheckPlacements` (1 s after spawning) didn't flag the soldiers, so they probably arrive later than that.
- **Flammability (F-14).** Sampled points that the game counts as flammable:
  - each of our cars: 18 of 54;
  - the map's cream car `XComDestructibleActor_20`: 48 of 72;
  - the two parking blocks: 0 of 3 and 3 of 3.
- **Grenade at the corner (log 107.66–110.15).** It hit cars 7–9 and the map's cream car. The user's note: "hit the
  cars in the corner again, only some fire on the map one as usual".
  - 8 fire spots: 5 on our glass at Z 160.4, 3 on the cream car's at Z 157.1.
  - None counts as flammable, the cream car's included, yet the cream car burned.
  - The fire volumes (logged at 110.15): `XGVolume_0` at (1697, −1297, 160) and `XGVolume_2` at (1759, −1297, 160),
    both on our car 9's glass, and `XGVolume_1` at (1775, −922, 157) on the cream car's. Only the cream car burned.
  - So fires are made on our cars and don't take. The lead is the cars' upper tiles not being flammable (see F-14).

### Fire test build (deployed 00:21, 4 Nov; not yet run)

- **What it logs (F-14):**
  - our cars' flammable tiles per height level, before and after our rebuild;
  - the watched map destructibles' tiles per height level.
- **Control.** Spawner 909 has `bRebuildWatched=True`. Once our rebuild is done, it rebuilds the tiles over the cream
  car and the two parking blocks, then logs their tiles again.
- **The test.**
  1. Start a mission on the bar map. If the squad lands on the row (F-06), restart.
  2. Throw an HE grenade at the corner, so it hits cars 8–9 and the cream car.
  3. Press F9.
- **Reading it.** If the cream car loses flammable tiles after the runtime rebuild and stops catching fire, runtime
  rebuilds don't produce flammability.

### Cars, run 12 (00:28–00:30, F9 look `look-003035.png`): the fire test

- **Landing zone** at (−2257, 1199), away from the row; no squad on the cars.
- **Flammable tiles per height level:**
  - Our cars before our rebuild: ground level 0–3 of 8–12, next level 0–2.
  - Our cars after it: ground level 8/8–12/12; next level unchanged.
  - The map's cream car: ground 10/10, next 8/10, the one above 1/10.
  - After the runtime rebuild over the cream car (`bRebuildWatched`, 30.14 s): identical. The parking blocks were
    identical too.
- **Grenade (log 76.51).**
  - It hit cars 7–9 and the cream car (500 → 472).
  - Our glass broke too: cars 8 and 9 each lost 2 columns (21 → 7 visible fragments).
  - When our cars were hit, the list held 3 fire spots, all on the cream car's glass. Our glass broke after those
    hits, so the log doesn't show whether its columns added spots.
  - 3 fire volumes, all on the cream car, which burns on turn 2 in the shot.
- **Conclusion (F-14).**
  - A runtime rebuild doesn't remove flammability.
  - Our cars get the ground level marked flammable but not the level above, where the fires sit.
  - Candidates and the next variant build are in the register.

### Fire variants build (deployed 00:36, 4 Nov; not yet run)

- **Car 7** (x 1365) is a plain copy of the archetype (`bPlainCopy`, new spawner option). It renders black.
- **Car 8** (x 1547) has no glass.
- **An 11th car**, red, at (1150, −1008) north of the row's right end, is turned to yaw −86 like the cream car
  (`rebuildExtent` 256 × 192 × 160).
- **Reading it.** The "flammable tiles under ... after the rebuild" lines show per variant whether the level above the
  ground gets marked (F-14). A grenade afterwards checks it against real fire.

### Cars, run 13 (00:37–00:40, F9 looks `look-003907.png`, `look-004004.png`): the variants rule out class, glass and orientation

- **Landing zone** at (−1105, −1297), away from the row.
- **After the rebuilds, flammable tiles by level (ground / level above):**
  - plain copy `XComDestructibleActor_9`: 12/12, 0/12;
  - car without glass: 8/8, 0/8;
  - turned red car: 14/15, 0/15;
  - our other cars: all on the ground, 0–2 above;
  - the cream car, after the runtime rebuild over it: 10/10, 8/10.
- **Conclusion (F-14).** A runtime rebuild marks only the ground-level tile under a flammable object. The map's
  window-height marks come from the editor's bake.
- **The user's throw (log 167.24).**
  - It hit car 6, the plain copy, the car without glass, car 9, the turned red car and the cream car: 15–18 damage
    each.
  - Glass broke on the plain copy's car and on the turned car (2 columns each).
  - All 3 fire volumes landed on the turned car's glass, at window height (Z 160): (1199, −1009), (1202, −1063) and
    (1250, −1009).
  - No burn followed before the game closed (log 280 s): no AreaBurn hit, and no look after the throw. That fits
    F-14: those tiles aren't marked flammable.
- **Workaround (built and cooked 00:41; deploys when the game closes).**
  - `BuildFragmentColumns` lowers the bottom of each column's bounds to `2 × (car bottom + 32) − top`. That puts the
    centre, where a destroyed column's fire starts, in the ground-level tile.
  - The spec is back to ten normal cars plus the turned red car.

### Cars, run 14 (00:43–00:46, F9 look `look-004557.png`): ground-level fire spots work; the fires went elsewhere

- **Landing zone** at (911, 1199), away from the row.
- **The grenade (log 80.87–83.01).** It hit cars 8 and 9 and the cream car. Our glass broke (21 → 11 and 7 visible
  fragments).
- **Fire spots.** 8 in all: our 5 at Z 29.1, all counted flammable, and the cream car's 3 at Z 157.1. So the
  workaround puts our spots where the tiles are flammable.
- **Fires.** All 3 went to the cream car's spots (two at the same spot), so none landed on ours. The cream car burns
  on turn 2 in the shot. The user's note: "no tire fires".
- **Still to test.** A throw at the middle of the row, away from the cream car, so that every fire spot is ours.
- **Side effect to check.** Our columns now count as damaged but not destroyed ("1/0 of 6", "2/0 of 6"); before
  the change they were both. Destroyed columns may be what updates line of sight through broken windows.
- **Second grenade (log 223.88, F9 look `look-004705.png`): our car burns.**
  - It broke the glass of cars 7–9 (car 7: 21 → 6 visible fragments).
  - All 3 fires went to car 7's ground-level spots: (1385, −1297, 29), and (1384, −1383, 29) twice.
  - The look shows car 7 (white) burning, with flames along its side and windows. The user's note: "WE HAVE FIRE!".
  - Next: the turn change should destroy it with AreaBurn and set off its explosion (F-09).
- **Turn change (log 385.11, F9 look `look-005019.png`, turn 4): car 7 burns down and sets off a chain reaction.**
  - `XComDamageType_AreaBurn` 8041 destroyed car 7. Its destroyed events then went off: its explosion dealt 241 to
    cars 6 and 8 and to the turned red car.
  - All three dropped to 250/500 and into `_Damaged`, the burning state; the shot shows them on fire. The cream car
    burned down at the same turn change.
  - The user's note: "our car blew up and set off a chain reaction, others are on fire now, looks great!".
  - So F-09 (our copies of the destruction actions) and F-14 (fire) are verified.

### Cars, run 15 (00:52–00:54, F9 look `look-005426.png`): save and reload with destroyed cars

- **Before the save.** A grenade and the turn change destroyed cars 6–9 (chain explosions, log 81.8–91.4). Car 5 and
  the turned car were `_Damaged` and burning.
- **After the reload, the user's notes:** "on reload the car wrecks are gone, but the fire is still there" and "units
  can now path through that area so there's nothing there". The look shows fires and scorch marks on bare road.
- **Log.**
  - The checkpoint "Checks" the map's own actors.
  - For each damaged or destroyed car and glass of ours it logs "Not Found XComMapEdDestructible_6 … Recreating
    actor". The saved names match (F-15).
  - The spawners then report cars 6–9 Dead (0/500), car 5 `_Damaged` 199, the turned car `_Damaged` 48. The states
    are right, but the recreated actors are bare class defaults, with no mesh.
- **Finding F-17 and its fix** (deployed 01:06): see the register.
- **Tooling.** The first try of the fix overrode `ApplyCheckpointRecord`, which fails to compile against UDK's
  `FracturedStaticMeshActor` (it takes a record parameter there). That failed make deleted `XComGame.u` and
  `XComMapEd.u`, so the next build stuck at the editor's hidden prompt. patchtool now treats missing packages as stale
  (T-04).

### Cars, run 16 (09:53–09:55, F9 look `look-095539.png`): the restore fix works; a wreck explodes again on load

- **Restore (F-17).** Each recreated car and glass logged "restored … after a load", at its own spot.
  - The look shows car 8's wreck visible and giving cover, and car 9 burning (`_Damaged`, 239).
  - The user's note: "looks good".
- **Replayed explosion (F-18).**
  - While its record was applied, car 8's wreck re-fired its explosion (241, log 125.30). That destroyed car 7, which
    had been burning at 186.
  - The user's note: "when i saved I think the white car was also burning but now it is not".
- **Fix** built 09:57: the explosion actions are held back while the record is applied.

### Cars, run 17 (09:59–10:02, F9 look `look-100225.png`): save and reload with wrecks and fires works

- **Before the save.** A grenade, then the turn changes: car 9 burned down. Its explosion took car 8 to 250 (burning)
  and destroyed a parking block. The map's cream car burned down too.
- **After the reload.**
  - All our cars logged "restored … after a load".
  - Car 8 came back `_Damaged` 250 and burning; car 9 came back Dead, as a wreck.
  - No explosion fired during the load, from ours or from the map's wreck (F-18 verified).
  - The look shows both wrecks and the burning car. The user's note: "looks good".
