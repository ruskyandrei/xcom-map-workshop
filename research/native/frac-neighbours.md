# Fracturing pieces' neighbour lists: what the game does with `FracActorCache`, and how the lists are made

18 November 2026. The custom geometry plan's stage M3, item 1 (the plan is private). Read-only: the decompiled
XComGame scripts (`<lab>\reference\XComGame-decompiled`, LWR's), a disassembly of `XComEW.exe`
(`<lab>\re\XComEW-copy.exe`, with the helpers in `tools/re/`: `natives.py`'s table `<lab>\re\natives.tsv`, `refs.py`,
`dfn.sh`), and a survey of every listed map's placed fracturing pieces
([wall-joints.py](../evidence/wall-joints.py), output
[wall-joints-2026-11-18.json](../evidence/wall-joints-2026-11-18.json)). The disassembly dumps stay in the lab.
Nothing was run in the game. Findings register F-69 (the lists) and F-116 (a solid's end against the tiles).

## Short answer

- **A neighbour listing passes damage on, one step.** When a blast damages one of a fracturing piece's columns
  (`DamageColumn` with cascading allowed), the column hands the same damage, up to the same height, to every column
  its `FracActorCache` lists: each named piece's `TakeCollateralDamage(FromActor, ColumnIdx, MaxZ, DamageAmount)`,
  whose script calls `DamageColumn(ColumnIdx, MaxZ, DamageAmount, false)`. That neighbour column's fragments from
  the bottom up to `MaxZ` lose the same health; it marks itself damaged or destroyed and may drop cover debris. It
  does not cascade further. Nothing in the path rechecks support or rebuilds tiles from the list itself: the
  neighbour simply takes the hit.
- So two pieces that list each other break together at their joint: a blast that reaches one side's joint column
  breaks the other side's joint column too, up to the same height. Pieces that don't list each other each break only
  where the blast sphere reaches their own columns. That is today's state between a made wall and anything else.
- **The lists follow one rule** (new; F-69 found no rule of boxes): column X of piece A lists column n of piece B
  when X's box touches or overlaps B_n's box cut to B's own bounds (its vertices' box) grown by one unit, as closed
  boxes (touching counts). It gives exactly the saved list for 61,805 of 62,460 columns over the 151 maps
  (131,507 listings: 601 missed, 550 added, nearly all between a few pieces of a map that were moved or added after
  the lists were made). Only B's box is cut, so the lists are not mutual where a column's box reaches above or below
  its piece (a wall's top storey column over a floor slab): that is F-69's 135 one-way listings on URB_Bar.
- The columns themselves are laid on the piece's own grid: 96 x 96 x 192 cells counted from its vertices' lowest
  corner less one unit, not the level's tile corner (a piece exactly 12 tiles long gets a thirteenth column one unit
  long). Each column's box is cut to the piece's extent along the wall and to its listed fragments across it.

## 1. The script side

`XComFracLevelActor` (decompiled):

```
struct native FracActorCacheEntry { var() XComFracLevelActor FracActor; var() int ColumnIndex; };
struct native FragmentColumn { var() Box Bounds; var() init array<init FragmentCacheEntry> FragCache;
    var() init array<init DestructibleCacheEntry> DestructibleCache;
    var() init array<init FracActorCacheEntry> FracActorCache;
    var bool bCoverDebrisPlaced; var transient bool bDamaged; var transient bool bDestroyed; };
native simulated function ApplyDamage(Vector Origin, float Radius, int Damage);
simulated event BreakOffPartsInRadius(...) { SetTickIsDisabled(false); ApplyDamage(Origin, Radius, LastHitInfo.Damage); }
native function DamageColumn(int ColumnIdx, float MaxZ, int DamageAmount, optional bool bAllowCascade = true);
simulated event TakeCollateralDamage(Actor FromActor, int ColumnIdx, float MaxZ, int DamageAmount)
{ DamageColumn(ColumnIdx, MaxZ, DamageAmount, false); }
```

`TakeDirectDamage` and `TakeSplashDamage` reach `BreakOffPartsInRadius` for damage types that fracture.
`XComDestructibleActor` has its own `TakeCollateralDamage(Actor FromActor, int DamageAmount)`, which the
`DestructibleCache` entries get. No script reads `FracActorCache` itself: only the natives do.

## 2. The natives (addresses in the exe copy)

| What | Address | How found |
| --- | --- | --- |
| `execApplyDamage` | `0x00DB2A10` | natives.tsv; calls the virtual at vtable `+0x3F8` |
| `execDamageColumn` | `0x0043D500` | natives.tsv; calls the virtual at vtable `+0x3FC` |
| `ApplyDamage` (implementation) | `0x00E60F50` | the slot before `DamageColumn` in both vtables (`0x01AB9E98`, `0x01ABA2A0`) |
| `DamageColumn` (implementation) | `0x009F9BC0` | the one function that uses the `TakeCollateralDamage` name twice; its pointer is at `+0x3FC` in the XComFracLevelActor and XComDecoFracLevelActor vtables |
| `eventTakeCollateralDamage`, the fracturing piece's (4 arguments) | `0x00D3F310` | reads the FName `0x01D3E560`; the destructible's 2-argument one is `0x00983530` |
| FName `TakeCollateralDamage` | `0x01D3E560` | set from the wide string `L"TakeCollateralDamage"` (`0x01A91EA0` and copies) by the name tables' start-up code |

The actor's columns are the TArray at `this+0x2C8` (count `+0x2CC`), 0x44 bytes each: `Bounds` (0x1C),
`FragCache` (`+0x1C`, 12-byte entries: FragIndex, MinZ, MaxZ), `DestructibleCache` (`+0x28`, 8 bytes: actor, MinZ),
`FracActorCache` (`+0x34`, 8 bytes: actor, ColumnIndex), and the bits at `+0x40` (1 bCoverDebrisPlaced, 2 bDamaged,
4 bDestroyed). A per-fragment health array is at `this+0x1D8` (count `+0x1DC`). The actor's bools at `this+0x258`
match the script's order (4 bAlwaysFracture, 8 bAlwaysDestroyColumns, 0x200 bUseRigidBodyCollisionForCover,
0x800 bNeedsDamageResolution); the filter box `LastFilterBox` is at `this+0x278`.

### 2.1 `ApplyDamage(Origin, Radius, Damage)` (`0x00E60F50`)

- `MaxZ = Origin.Z + Radius`.
- Each column whose `Bounds` lies within `Radius` of `Origin` (squared distance from the point to the box) and
  inside `LastFilterBox` gets `DamageColumn(i, MaxZ, Damage, true)`; one outside the filter box is only noted (its
  centre goes in a list at `this+0x230`). When no column was damaged, a second pass damages every column in the
  sphere regardless of the filter box.

### 2.2 `DamageColumn(ColumnIdx, MaxZ, DamageAmount, bAllowCascade)` (`0x009F9BC0`)

1. A bad index logs an error and returns.
2. Over the column's `FragCache`, lowest first: each fragment loses `DamageAmount` health from the per-fragment
   health array. The loop ends at the first fragment whose MinZ is over `MaxZ` (unless bAlwaysDestroyColumns; a
   further test on a value the component returns for the fragment, and one against the filter box's heights, gate
   it: not fully decoded). One that reaches zero is queued to break (`this+0x234`), the column is marked
   **damaged**, and if its MinZ lies within 30 units of the column's bottom, **destroyed**.
3. A damaged column is added to the actor's damaged-columns list (`this+0x240`) and the actor gets
   bNeedsDamageResolution. When a fragment broke: bUseRigidBodyCollisionForCover is cleared, and when the bottom
   broke with nothing left standing there, the virtual at `+0x400` (cover debris) runs once and sets
   bCoverDebrisPlaced.
4. **The cascade**, only when `bAllowCascade`, the column is damaged and the actor isn't bAlwaysFracture:
   - when a fragment broke in this call, each `DestructibleCache` actor gets `TakeCollateralDamage(this,
     DamageAmount)` (its MinZ isn't checked here);
   - each `FracActorCache` entry's piece gets `TakeCollateralDamage(this, ColumnIndex, MaxZ, DamageAmount)` (the
     event inlined: `FindFunctionChecked` on the name, then `ProcessEvent`), which runs that piece's
     `DamageColumn(ColumnIndex, MaxZ, DamageAmount, false)`: steps 1 to 3 there, no further cascade.

Not followed: what the damage resolution then does with the damaged-columns list (fragments hidden, tiles
rebuilt), which is the same for a column damaged directly or through a neighbour.

## 3. The lists over the maps

[wall-joints.py](../evidence/wall-joints.py) tests the rule on every column and classifies the walls' joints.
At joints between two pieces the rule gives both sides' listings exactly: 609 of 609 L corners, 162 of 162 T joints,
97 of 98 end-to-end joints. Each joint column lists the other wall's joint column(s) at its own storey and the
storeys above and below (their boxes touch at the storey line), and usually the column one tile further along one
of them (a T's stem end straddles two of the through wall's columns); lists are mutual there.

## 4. What it means for made walls

- A made wall's columns can be given lists by the same rule against any other fracturing piece, the map's own
  included, and the map piece's columns can be given entries naming the made wall's columns (`ColumnIndex` is an
  index into the other piece's `FragmentColumns`; `native_copy.edit_columns` already rewrites map pieces' columns).
  Then a blast at the joint breaks both sides there, as the game's own joints do.
- Touching boxes count, so two ends meeting exactly at a line are listed; a made writer should compare with a small
  tolerance rather than rely on float equality.
- A listing passes the full damage on, so listing more columns than the rule gives would spread breaks further than
  the game's walls do.
