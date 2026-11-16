# Mouse cursor over the cut-away copies: how it picks, and why it lands on our roof

> Copied into the repo on 4 November 2026 from the lab folder `<lab>\re\cutaway\cursor`. The helper scripts it names are now in
> `tools/re/`; the disassembly dumps (`*.txt`) stay in the lab, since they are decoded game code.

Read-only reverse engineering of `XComEW.exe` (copy) and the decompiled XComGame scripts. Dumps and helper scripts
are in this folder; the helpers are reused from `..\` (dfn.sh, vt.py, refs.py).

## 1. How the mouse cursor picks its tile

With the mouse, `XCom3DCursorMouseForCursorVolumes.CursorSnapToFloor` **does no tracing**. It only reads the cursor
volume of `m_iRequestedFloor` to set `m_fBuildingCutdownHeight`. `PerformTrace` and `TraceCursorVolume` serve the
pad cursor. The location comes from this chain:

1. `XComTacticalInput.Mouse_CheckForPathing` calls `GetAdjustedMousePickPoint(kPickPoint, unit.m_bIsFlying, true)`,
   then `Cursor.CursorSetLocation(kPickPoint)`.
2. `GetAdjustedMousePickPoint`, for a unit that does not fly, uses `XComHUD.CachedHitLocation`. It snaps that to the
   tile's centre, with **Z = `XComWorldData.GetFloorZForPosition(CachedHitLocation)`**.
3. `CursorSetLocation` → `getValidLocation` → `GetClosestValidCursorPosition` (`0x733E30` → `0xEE2980`). That
   function only clamps the point into the level volume. It never searches the tile column, so the world data does
   not pull the cursor to the highest floor.
4. **`CachedHitLocation` comes from `XComTacticalHUD.GetMousePickActor`** (script, each PostRender):
   `foreach TraceActors(class'Actor', …, mouse ray)`. For each hit, nearest first:
   - skip actors without `IMouseInteractionInterface`. XComLevelActor and XComFracLevelActor have it, and so does
     every child class: XComDestructibleActor, XComCollectible, XComLadder and the doors (XComInteractiveLevelActor)
     inherit it from XComLevelActor. StaticMeshActor and KAsset don't. (Corrected 16 November 2026: this said
     XComDestructibleActor lacks it; [piece-flags.md](piece-flags.md), section 3.)
   - for non-interactive actors:
     - **skip `XComLevelActor`/`XComFracLevelActor` with `bIgnoreFor3DCursorCollision`** (casts: props, collectibles
       and ladders too; a door is tested apart and never reads it);
     - skip points outside the LevelVolume;
     - skip hits whose normal.Z < 0.2 (walls).
   - `iHitFloor = Cursor.WorldZToCursorFloor(hit)` (from cursor volumes);
     `pathable = WorldData.IsPositionOnFloorAndValidDestination(hit + 1z)`.
   - **The first hit that is pathable and outdoors wins at once** (`IsPointOutdoors` = no XComBuildingVolume in
     `XComTacticalHUD.m_arrBuildingVolumes` contains it).
   - Otherwise a later hit replaces the best only when:
     - `iBestFloor > m_iRequestedFloor && iHitFloor < iBestFloor`; or
     - it is on the same floor, and it is pathable while the best is not (or it is a pawn).

     All other hits are skipped.
5. **`TraceActors` does not skip hidden or cut primitives.**
   - `TraceActors` (`0x8A5730`) calls `MultiLineCheck` (`0x9F2630`) with flags 0x209B. It drops only actors with
     `bDeleteMe` and those of the wrong class.
   - There is no HiddenGame, bShouldCutdown or cutout test.
   - The only cutaway-aware trace is `Helpers.isVisibilityBlocked` (`0x9D9C80` → `0x8DD620`). It skips an
     XComLevelActor or XComFracLevelActor whose main mesh is HiddenGame, and asks `IsPositionVisible` (slot 0x1E4,
     frac version `0x4246D0`: hidden → not visible; bShouldCutout and above fCutdownMaskHeight → not visible).
     It is for line of sight, not the mouse.
   - So **a cut-away (hidden) roof is still hit by the mouse ray**. The game gets past its own roofs only through the
     rules in step 4.

## 2. Why our roof catches it, and the game's does not

- Firaxis marks the bar's roof-level `XComLevelActor`s with **`bIgnoreFor3DCursorCollision=1`**. Examples:
  `XComLevelActor_72` (z 396) and `_75` (z 400), the floor-2 "include" pieces (dumped from
  `URB_Bar-decompressed.upk`).
  - **`XComMapEdLevelPiece.CopyFrom` and `CopyFromFrac` do not copy `bIgnoreFor3DCursorCollision`** (only
    `XComMapEdWall.CopyFrom` does).
  - So the ceiling and roof level-piece copies are picked even when hidden.
- The roof slab `XComFracLevelActor_3` itself has the flag false in the bar. Since run 21 its copy is pathable (roof
  tiles became floor). It is handled only by the floor rule: a lower hit replaces it only while its cursor floor
  (z 402: cursor volume 2/3 boundary, 210..402 / 402..594) is above `m_iRequestedFloor`.
  - If `IsPointOutdoors` were true for it, it would win at once. That needs our point to be outside every volume in
    the HUD's list. `m_arrBuildingVolumes` is filled **once**, by AllActors in the HUD's PostBeginPlay, so a building
    in a level that streams in later can be missing from it.
  - The bar's `XComBuildingVolume_0` is a single box (x -1859..925, y -157..1411, z -128..640) that contains our
    building. So this branch is unlikely here, but the list is worth keeping right.
- Not involved: the cursor does not trace for tiles, and the world data does not pick the top floor tile.
  `bCutoutMask` and the FloorComponent state do not affect the mouse trace.

Confidence:

| Point | Confidence |
| --- | --- |
| Pick algorithm | high (script) |
| No hidden filter in TraceActors | high for the TraceActors and MultiLineCheck bodies; medium that the octree line check (hash vtable 0x10) has none either; not read |
| Level-piece copies lack the flag | high |
| Which exact hit wins in the user's view | medium; I could not see the view (a `bDebugMouseTrace` cheat run would show it) |

## 3. Setting `bCutoutMask` / `bCutdownScanup` on a spawned copy

- **No script-callable native sets them.** The flags are PrimitiveComponent bits +0x13C 0x10 and 0x20.
  - The only code that writes bit 0x10 is `0xB840C0`. It runs inside component load or creation (callers `0xA9DCF0`,
    `0xFBE170`), not as an exec function.
  - `SetPrimitiveCutoutFlag`/`CutdownFlag` set `bShouldCutout`/`bShouldCutdown`, not the mask.
- These routes work without UDK knowing the property:
  1. **Write the tag into the compiled class defaults.** Add `bCutoutMask` (BoolProperty=1), and `bCutdownScanup`
     where the source has it, to `Default__XComMapEdWall.FracturedStaticMeshComponent0` (and to
     `Default__XComMapEdLevelPiece.StaticMeshComponent0`) in `XComMapEd.u`. That means adding the names to the name
     table. Every spawn copies it. If some sources lack it, use a second class without it.
  2. **Spawn from a template.** `Spawn(class'XComMapEdWall', , , P, R, Template)` copies every property, components
     included, from a placed template of the *same class*. The template can be a hidden XComMapEdWall in the patch
     level with the tag written into its FSMC by patchtool. `new(Outer) class'FracturedStaticMeshComponent'(Source.FracturedStaticMeshComponent)`
     also copies everything. But the actor's main component property is `const`, and the cutaway uses only that
     component, so this alone does not help.
  3. The `set` console command (`set FracturedStaticMeshComponent bCutoutMask true`) would hit **every** FSMC and the
     class default, not only ours. It may also be refused in the shipping build for non-config properties. Untested
     and risky.
- After setting the mask on a component that is already attached, reattach it (`ReattachComponent`), so that the
  render state picks it up.
