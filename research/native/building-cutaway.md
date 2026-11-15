# Building cutaway in XCOM: Enemy Within: how it works, and what EXP-07's script-built building is missing

> Copied into the repo on 4 November 2026 from the lab folder `<lab>\re\cutaway`. The helper scripts it names are now in
> `tools/re/`; the disassembly dumps (`*.txt`) stay in the lab, since they are decoded game code.

Read-only reverse engineering of `XComEW.exe` (copy at `<lab>\re\XComEW-copy.exe`) and the decompiled
XComGame scripts. Disassembly dumps and helper scripts are in `<lab>\re\cutaway\`.

## Short answer

The cutaway works from **`Floors[i].m_aCachedActors`** alone. A building cuts a piece only through **that piece's own
`XComFloorComponent`, which must be attached to the piece** (in its `Components`, so that it has an `Owner` and
ticks). Cutting *down* (walls trimmed at floor height) and the camera-facing *cut-out* also need **`bCutoutMask=true`
on the piece's main mesh component**.

The compiled `XComMapEd.u` gives `XComMapEdWall` and `XComMapEdDestructible` **no attached FloorComponent**, because
of the UDK stubs. Their class defaults have `None` where the FloorComponent belongs:

| Class default (`<lab>\author\UDK-2011-09\UDKGame\CookedPC\XComMapEd.u`) | Components |
| --- | --- |
| `Default__XComMapEdWall` | `[None, FracturedStaticMeshComponent0, None, MyLightEnvironment]` |
| `Default__XComMapEdDestructible` | `[StaticMeshComponent0, None, MyNEWLightEnvironment]` |
| `Default__XComMapEdLevelPiece` | `[StaticMeshComponent0, FloorComponent0, MyLightEnvironment]` (has one) |
| game's `Default__XComFracLevelActor` (XComGame.upk) | `[LightEnvironment0, FracturedStaticMeshComponent0, FloorComponent0]` |
| game's `Default__XComLevelActor` | `[StaticMeshComponent0, FloorComponent0]` |
| game's `Default__XComDestructibleActor` | `[StaticMeshComponent0, FloorComponent0, MyNEWLightEnvironment]` |

Cause: the UDK stubs `XComFracLevelActor.uc` and `XComDestructibleActor.uc` (in
`<lab>\author\UDK-2011-09\Development\Src\XComGame\Classes\`) reference
`XComFloorComponent'Default__XComFracLevelActor.FloorComponent0'` (and the destructible's) without declaring the
subobject with `begin object`. The reference resolves to None. The subclass then saves its whole `Components` array,
with None in it, and at load that saved array replaces the game parent's. The stub `XComLevelActor.uc` does declare
`FloorComponent0`, so level-piece copies have one.

So every wall, roof slab, deco wall and destructible copy is skipped. `ShowFloor` reaches it, but its
FloorComponent is missing or detached, and the calls do nothing. Confidence: high (class-default data read
directly; native gates read in the code below).

## 1. The chain, from the pawn to the mesh

### Script side

1. A pawn touches or untouches a floor volume. `XComPawn.Touch`/`UnTouch` call
   `IndoorInfo.ParentTouchedOrUntouched`. The 3D cursor and `XComBuildingVisPOI` have their own IndoorInfo.
2. `XComPawnIndoorOutdoorInfo.CheckForFloorVolumeEvents` recomputes several values from `CurrentFloorVolumes`,
   using each volume's `CachedBuildingVolume` and `FloorNumber`:
   - `CurrentBuildingVolume`;
   - `iCachedCurrentFloorNumber` (highest FloorNumber) and `iCachedLowestFloorNumber` (lowest);
   - `m_bShouldRevealFloors` (AND of `m_bUseForBuildingReveal`).

   Then:
   - when the indoor state changes → `BuildingVisActor.OnChangedIndoorStatus()` → `XComPawn.NotifyTacticalGameOfEvent(0)`;
   - when the lowest floor changes → `OnChangedFloor()` → `NotifyTacticalGameOfEvent(3)`, plus Kismet
     `SeqEvent_OnUnitChangedIndoors`;
   - **always**, it calls `XGLevel.OnActorUpdateBuildingVisibility(m_kBuildingVisParam)` directly
     (eType 1 = unit, 2 = cursor, 4 = POI).
3. `NotifyTacticalGameOfEvent` → `XComTacticalGRI.NotifyOfEvent(EEvent, kLevel.m_kBuildingVisParam)` calls the
   delegates registered for that event. The listeners are:
   - `XGLevel.Init`: `RegisterTacticalDelegate(OnActorUpdateBuildingVisibility, 0)` and `(…, 3)`;
   - `XComTacticalSoundManager` (indoor/outdoor sound only).
4. `XGLevel.OnActorUpdateBuildingVisibility(Params)`:
   - **Mouse mode** (`ShouldUseMouseStyleReveals`: mouse active, our turn, no pod reveal or Kismet look-at) →
     `OnActorUpdateBuildingVisibilityForMouse`. This loops over **all** `XComBuildingVolume`s with AllActors (not
     `m_arrBuildings`):
     - cursor `m_iRequestedFloor == 0` → `ShowFloor(1)`;
     - otherwise → `ShowFloor(k+1)`, where k is the highest floor whose `fCenterZ - fExtent <= cursor.m_fBuildingCutdownHeight - 16`.

     This needs `Floors[i].fCenterZ`/`fExtent`, which `CacheFloorCenterAndExtent` fills.
   - **Pad / keyboard mode**: kBVolume is `IndoorInfo.CurrentBuildingVolume` (inside) or `PreviousBuildingVolume`.
     - The cursor (eType 2) returns early.
     - The building must have `m_bAllowBuildingReveal` (default true), and the event must be from team 8 or a
       visible unit.
     - Unit inside, alive, `m_bShouldRevealFloors` → `kBVolume.ShowFloor(IndoorInfo.GetLowestFloorNumber())`.
     - Otherwise → `ShowFloor(min(activePawnFloor, HighestOccupiedFloor+1))`, or `HideFloors(true)` when nobody is
       inside. `GetHighestOccupiedFloor` uses `XComFloorVolume.ContainsValidUnit()` (its `Touching`).

### Native side (addresses in the copy)

| Step | Function | What it does |
| --- | --- | --- |
| `XComBuildingVolume` vtable | `0x1AC8C70` | slots: 0x3E8 CacheFloorCenterAndExtent, 0x3EC CacheBuildingVolumeInChildrenFloorVolumes `0x43F5E0`, 0x3F0 RebuildCachedActors `0x7DCA60`, 0x3F4 CacheStreamedInActors `0x54E240`, 0x3F8 ChangeExternalMeshHidingGroups, 0x404 ShowFloor `0x5FAAA0`, 0x408 HideFloors `0x5E6630`, 0x40C RevealAllFloors `0xA6B3E0` |
| ShowFloor(n) | `0x5FAAA0` | returns if `n == LastShownFloor` (+0x230), if `bDebuggingThisBuilding` (+0x22C bit 0x40) or if `!m_bAllowBuildingReveal` (bit 0x8); otherwise calls the worker |
| worker | `0x10C72D0` (this, n) | idx = n-1. Cut height = max top and min bottom of `Floors[idx].FloorVolumes`' bounds (n out of range: the building's own bounds). For every floor i from top to bottom it calls the per-floor function with `bHide = (n != 0) && (i > idx)`. Then it stores `LastShownFloor` (n, or `Floors.Num` when n <= 0), `fCurrentCutdownHeight` and `fCurrentCutoutHeight`, and updates ExternalMeshHidingGroups |
| per floor | `0xE88FC0` (Floor*, i, idx, bHide, top, bottom) | for each `m_aCachedActors[j]`: drops the entry if the actor is None; otherwise `Actor->SetPrimitiveCutdownFlag(CutdownFloor > idx && i <= idx)` (vtable 0x18C), then `Actor->ChangeVisibilityAndHide(!bHide, top, bottom)` (vtable 0x1C4). Emitters in `m_aCachedEmitters`: vtable 0x150(bHide) |
| HideFloors(b) | `0x5E6630` | = worker(0): shows everything (the "un-cut" state) |

`ShowFloor(0)`, which a FloorNumber of 0 would produce, reveals all. Your floor volumes have FloorNumber 1, 1, 2, 3
(from `patch_exp07block-add.t3d`), which is right.

### Per piece (XComLevelActor vtable `0x1AB66F0`, XComFracLevelActor vtable `0x1AB9AA0`; script subclasses use the same native vtable)

| Function | Level actor | Frac actor | Behaviour |
| --- | --- | --- | --- |
| SetPrimitiveCutdownFlag (0x18C) | `0x507B40` | `0x9E6CE0` | level actor: only if the FloorComponent exists and `CanUseCutout()`, then `FloorComponent.SetTargetCutdown(b)`; frac actor: the FloorComponent call only |
| ChangeVisibilityAndHide (0x1C4) | `0x4F35D0` | `0xCD3900` | needs the FloorComponent (+0x1D8 / +0x254). Calls `FloorComponent.SetTargetHidden(!bShow)`. If the mesh has `bShouldCutout` or `bShouldCutdown`, it marks the vis and height state changed and enables the owner's tick. Then `FloorComponent.SetTargetVisHeights(top, bottom)` |
| CanUseCutout (0x1B4) | `0xA15DB0` | `0x4D6B80` | = **main mesh `bCutoutMask`** (PrimitiveComponent +0x13C bit 0x10) |
| SetPrimitiveCutdownFlagImm (0x194) | | `0x8C5000` | only if `CanUseCutout()`: sets mesh `bShouldCutdown` (bit 0x80) and updates the render state (`bCutdownScanup`, bit 0x20, picks the path) |
| SetPrimitiveCutoutFlagImm (0x198) | | `0xAE86F0` | sets mesh `bShouldCutout` (bit 0x40) |
| SetPrimitiveHidden (0x19C) | `0x8D5FD0` | `0x42E850` | main mesh component's vtable 0x274 (hidden-game) |
| SetPrimitiveVisHeight (0x1A8) | | `0xF62060` | writes mesh fCutdownMaskHeight +0x88, fCutoutMaskHeight +0x84, fOpacityMaskHeight +0x8C, fPreviousOpacityMaskHeight +0x90 |

The cutaway works only on the actor's **main** mesh component: `StaticMeshComponent` +0x1D0, or
`FracturedStaticMeshComponent` +0x1D4. An extra component, such as the XComMapEdWall `Overlay` mesh, is never cut or
hidden.

### XComFloorComponent (vtable `0x1AC3BC0`, size 0x6C; flags at +0x58)

- SetTargetCutdown `0xE832E0`, SetTargetCutout `0xFBAD40`, SetTargetHidden `0xC51A90`: each does something **only
  if `Owner` (+0x4C) is set**. It stores the target bit, marks the state changed, enables the owner actor's tick
  (`AActor::SetTickIsDisabled(false)` `0x7D1580`, skipped for bStatic or bDeleteMe actors) and sets
  `bComponentNeedsTick`.
- SetTargetVisHeights `0xAB5600` stores the two heights.
- Tick `0x7C5110` (vtable 0x148) picks the target opacity-mask height:
  - hidden: a constant;
  - cutout: the cutout height;
  - cutdown: the cutdown height;
  - otherwise: the default.

  Then it calls `PreTransition` `0x9E9D70` (cutdown and cutout flags on, unhide before a fade-in), fades through the
  owner's `SetPrimitiveVisFadeValues`, and ends in `OnFinishedFadeTransition` `0xD6C470`. That sets the final
  cutdown and cutout flags and heights, and `SetPrimitiveHidden(bHidden)`.
- EW's real XComFloorComponent has **no `OwnerMeshComponents`**. That property exists only in the UDK stub
  `XComFloorComponent.uc`, an older declaration. The real one drives the owner actor's virtual functions. The stub
  property is saved in `Default__XComMapEdLevelPiece.FloorComponent0` and skipped at load as unknown. It is harmless.
- **No material parameters are set per actor in this path.** The heights and flags go onto PrimitiveComponent fields,
  and the renderer passes them to the material. The copies reuse the sources' materials, so the materials are not
  the problem.

PrimitiveComponent layout, from the Engine.upk property order (the vis-height writes above confirm it): +0x84
fCutoutMaskHeight, +0x88 fCutdownMaskHeight, +0x8C fOpacityMaskHeight. Bitfield +0x13C: HiddenGame 0x4,
bCutoutMask 0x10, bCutdownScanup 0x20, bShouldCutout 0x40, bShouldCutdown 0x80.

### The camera-facing cut-out (XComCutoutBox)

- `XGLevel.LoadInit` spawns `XComCutoutBox`. Its `Tick` calls the native `UpdateActors`, vtable 0x3E4 → `0xEF2970`.
- That function takes the box actor's own **`Touching`** list and keeps only actors with **`CanUseCutout()`**, which
  is `bCutoutMask`. It then cuts them out through `SetPrimitiveCutoutFlag` and the FloorComponent.
- So the copies need, all three: collision that touches the box, `bCutoutMask`, and an attached FloorComponent.

## 2. How the set of pieces is chosen

- **Only `Floors[i].m_aCachedActors`**, read by ShowFloor's per-floor function. `CutdownFloor` decides cutdown.
  - Not the floor volumes' Touching at show time.
  - Not `m_arrBuildings`.
  - Not a separate visibility manager.
- Firaxis's editor bakes the caches. At run time two natives change them:
  - **RebuildCachedActors** (`0x7DCA60`) **empties** each floor's actors and emitters, then for each floor volume
    calls `0x86C320`. That function requires the volume's `m_bUseForBuildingReveal` or `m_bNonEnterableBuildingPiece`,
    then collects:
    - actors in the floor volume's **`Touching`** list, that are XComLevelActor, XComFracLevelActor or KAsset, in the
      **same outermost package (map/level) as the floor volume** (`0x915D80` walks Outer), with
      `bottom < volume top - k`; DecalActors with no Z test;
    - emitters inside the volume;
    - plus `m_aInclusionActors` and minus `m_aExclusionActors` (same package check).

    It then sets `CutdownFloor` (`0x78AEB0`) **only for actors with `CanUseCutout()`** (bCutoutMask).

    Nothing in the exe calls it except script, and no shipped script calls it.
  - **CacheStreamedInActors** (`0x54E240` → `0x8D4020`) **appends** to the caches and never clears them.
    - It skips the persistent level.
    - It looks only at streamed levels whose `WorldInfo.bRecacheBuildingActorsAtRunTime` is set (WorldInfo +0x214
      bit 0x80; the bit order is confirmed by bBegunPlay = 0x1000 in `0xEDA76B`).
    - There it adds each XComLevelActor, XComFracLevelActor or KAsset with `bottom < volume top - k` (Z only, with
      CutdownFloor 0), plus DecalActors and Emitters.

    It runs once, in `XGBattle.Running.BeginState` → `FixupStreamingBuildingVis` (and the `RebuildBVs` cheat). For
    your building it does nothing: a level saved by UDK has no such WorldInfo flag.

## 3. What each piece needs

1. **An attached XComFloorComponent**, in the actor's `Components` and the `FloorComponent` property, so that
   `Owner` is set and it ticks. All cutting and hiding goes through it. *Missing on XComMapEdWall and
   XComMapEdDestructible.*
2. **`bCutoutMask=true` on the main mesh component**. It is needed:
   - for cutdown: XComLevelActor's `SetPrimitiveCutdownFlag` and XComFracLevelActor's `SetPrimitiveCutdownFlagImm`;
   - for the camera cut-out box;
   - for RebuildCachedActors to give a CutdownFloor.

   Hiding upper floors does **not** need it. Copy `bCutdownScanup` too if the source has it.
3. An **entry in `Floors[i].m_aCachedActors`** with the right `CutdownFloor`. Your copier does this.
4. Not bStatic (true for the copies), so the owner's tick can be enabled. Collision (CollideActors) so the cut-out box
   and floor volumes can touch it.
5. The building: `m_bAllowBuildingReveal=true` and `bDebuggingThisBuilding=false` (the defaults). Floor volumes with
   `FloorNumber` >= 1 and `CachedBuildingVolume` set (`CacheBuildingVolumeInChildrenFloorVolumes` sets only
   `CachedBuildingVolume`, +0x22C; it never sets FloorNumber). Floor centres from `CacheFloorCenterAndExtent`.
   All of this is done.
6. **Not needed:** `m_arrBuildings`, `OwnerMeshComponents`, `VisibilityId`, `PreviewEnvironmentShadowing`,
   `bPathColliding`, `bCanStepUpOn`. These play no part in the cutaway.
   - `m_arrBuildings` is used by `HideAllFloors`, `GetBuildings`, `IsInsideBuilding`, `GetBuildingByUnit` and
     XGLayout (AI and pod placement).
   - It is filled once by `XGLevel.InitFloorVolumes` (AllActors) in `Init`/`LoadInit`. A building in a level that
     streams in later is missing from it. Script can `AddItem` it.

## 4. What is collected only once

| Data | When | A later building or piece |
| --- | --- | --- |
| `m_arrBuildings`, floor-volume `CachedBuildingVolume`, floor centres | `XGLevel.InitFloorVolumes` at Init/LoadInit (AllActors) | missed; call `CacheBuildingVolumeInChildrenFloorVolumes`, `CacheFloorCenterAndExtent`, and `m_arrBuildings.AddItem` (your copier does the first two) |
| `m_aCachedActors` | editor bake; `CacheStreamedInActors` once at battle start (flagged streamed levels only) | missed; fill by script (works), or `RebuildCachedActors` (clears first; needs Touching and the same package) |
| tactical delegates | `XGLevel.Init` | independent of buildings |
| XComCutoutBox targets | every tick, from Touching | dynamic |
| FloorComponent attach | actor init, from Components | **class data**: fix it in the class defaults |

`ShowFloor` returns early when `n == LastShownFloor`. After changing a cache while a floor is shown, call
`HideFloors_ScriptDebug(false)` (worker(0), which resets LastShownFloor), so that the next update reapplies it.

## Confidence

| Point | Confidence |
| --- | --- |
| The event chain, `ShowFloor` and the per-floor logic | high |
| FloorComponent gates (needs `Owner`), and `bCutoutMask` gates for cutdown and the cut-out box | high |
| PrimitiveComponent bit mapping | high (offset maths checked against the vis-height writes) |
| Missing FloorComponent in XComMapEdWall and XComMapEdDestructible | high (read from the package) |
| The FloorComponent property itself after load (None, or an inherited template) | not checked; either way it is not attached |
| `RebuildCachedActors`' same-package rule | high |
| The copies spawned into the persistent level (UE3 spawns into `Owner`'s level, else the current/persistent level; the copier passes no Owner) | medium |
| `bRecacheBuildingActorsAtRunTime` bit | medium-high |
| `IndoorInfo.IsInside` native | not read (vtable call) |
