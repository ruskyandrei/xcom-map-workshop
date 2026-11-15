# How XCOM: Enemy Within decides line of sight, step-outs and flanking

> Copied into the repo on 15 November 2026 from the lab folder `<lab>\re\sight`, where the disassembly dumps
> and the helper and check scripts it names stay (section 8). How the bits it reads are built is in
> [cover-build.md](cover-build.md); what both mean for the editor is in [cover-and-sight.md](cover-and-sight.md).

Static reading of the exe copy (`<lab>\re\XComEW-copy.exe`, image base 0x400000) and of the decompiled scripts,
15 November 2026. Nothing was run. Every claim carries a confidence: **high** (read end to end and consistent with
data), **medium**, **low**. Addresses are the real functions (the `exec…` thunks are named where useful).

The decompiled scripts in `<lab>\reference\XComGame-decompiled` are **LWR's XComGame** (EW's package with LWR's
patches: for example `UIUnitGermanMode.uc:177` and `XComCheatManager.uc:507` call
`BaseMutator.Mutate("LWR…")`). The native code is the same exe for plain EW and LWR, so everything below marked
"native" holds for both; script details may differ in plain EW.

## 0. The short answer

- **Inside sight radius, sight is a walk over tiles that reads only the baked (or rebuilt) static flags**: six bits
  per tile, one per direction. No collision trace is made, no dynamic flag is read, units do not block. (high)
- Each viewer owns a **tile map of 16-bit words** ("which tiles I see, and from where"). It is recomputed when the
  viewer's tile changes or tiles under it are rebuilt. `CanSeeActorToActor` only looks the target's tile up in it. (high)
- **Step-out** is baked too: the cover flags say on which sides of each cover direction a unit may lean. The map
  holds one bit per source tile (own tile and up to four neighbours). (high)
- **Beyond sight radius** (squadsight) and with `bUseLineChecks`, sight is a physical line check against the
  collision of level actors, with its own filter. (high for the path, medium for the filter's details)
- **Flanking** is geometry on cover directions, plus "the attacker sees the target"; it needs the target's baked
  cover flags and cover location. (high for the natives read; the native hit chance itself was not followed)

## 1. Map data the query side reads

| Data | Where | Used for |
| --- | --- | --- |
| Static flags `0x80, 0x100, 0x200, 0x400, 0x800, 0x1000` | static store (container store 1) | sight blocked toward −X, +X, −Y, +Y, −Z, +Z |
| Static flag `0x2000` (floor) | same | floor tile of a unit, the hand-down to the tile above/below, step-out validity |
| Static flags `0x8000`, `0x10000` | same | "seen" marking of blocking tiles for the fog; `IsAdjacentTileVisible` |
| CoverFlags bits `0x1..0x8` (N, S, E, W), `0x10..0x80` (low), `0x100..0x800` (peek left), `0x1000..0x8000` (peek right), `0x10000` (diagonal) | cover store (store 2) | cover directions, step-outs, cover height, flanking |
| CoverLocation | store 4 | the point the flank test measures from |
| Dynamic flag `0x2` (tile blocked by a unit) | dynamic store, run time only | a step-out tile taken by another unit is no step-out |
| Collision of XComLevelActor / XComFracLevelActor / PathBlockingVolume | the level | only the line-check paths (squadsight, `bUseLineChecks`, `WorldTrace`) |

**Direction bits.** Read at the ray walk (`0xFA9F2B`–`0xFA9FF9`) and again, independently, at
`IsAdjacentTileVisible`'s worker (`0xC66A90`). (high)

| Direction | Sight bit | Pathing bit (= sight bit >> 6) | Cover direction |
| --- | --- | --- | --- |
| −X | `0x80` | `0x2` | East (`COVER_East` 0x4) |
| +X | `0x100` | `0x4` | West (`COVER_West` 0x8) |
| −Y | `0x200` | `0x8` | South (0x2) |
| +Y | `0x400` | `0x10` | North (0x1) |
| −Z (down) | `0x800` | `0x20` | |
| +Z (up) | `0x1000` | `0x40` | |

- So the sight set is `0x1F80` and the pathing set `0x7E`. The script's constants (`WORLD_PATHING_ANY_DIR_BLOCKED =
  0x3F`, `WORLD_VIS_ANY_DIR_BLOCKED = 0xFC0`) are one bit lower than what the code tests; `RebuildTileDataExtents`
  uses the script's values for its "has any bit" test (native-code-notes), which therefore misses `0x1000` alone.
  The pathing column is by data only (below), not read from pathing code. (sight bits high, pathing bits medium)
- **"East" is −X in the world.** The direction table (`0x1C1B050`, 4 entries of 0x54 bytes; its vectors are filled
  at start-up by `0x1372580` from `0x1C1AFDC`) gives: North (0, 1, 0), South (0, −1, 0), East **(−1, 0, 0)**,
  West **(1, 0, 0)**, although the entry names read "East (+X)" / "West (−X)" and `GetCoverDirection(DX, DY)`
  (`0x59F370`) maps (1, 0) to East. `GetWorldDirection` (`0xC2FEB0`) returns entry+0x20. This settles the "E and W
  look swapped" note in native-code-notes: they are. (high; data agrees 100 %, below)
- Entry layout: +0 name, +4 cover bit, +8 low bit, +0xC peek-left bit, +0x10 peek-right bit, +0x14 climb-onto bit,
  +0x18 climb-over bit, +0x1C static pathing bit (N 0x10, S 0x8, E 0x2, W 0x4), +0x20 direction, +0x2C peek-right
  direction, +0x40 24.0, +0x44 124.0 (cover test length; 135.74 in the diagonal table `0x1C1B1A0`), +0x48 DX, +0x4C DY.
- `GetPeekRightDirection` = entry+0x2C: N (−1, 0, 0), S (1, 0, 0), E (0, −1, 0), W (0, 1, 0).
  `GetPeekLeftDirection` = the negative: N (1, 0, 0), S (−1, 0, 0), E (0, 1, 0), W (0, −1, 0). (high)

**Checked against URB_Bar's baked data** (`check_bits.py`, `check_cover.py`; container14.bin, 24,336 tiles):
- A sight bit is mirrored by the opposite bit on the neighbour it points at in 498 of 646 (−X), 498 of 638 (+X),
  690 of 835 (−Y), 690 of 841 (+Y), 630 of 704 (−Z), 630 of 669 (+Z) cases. Tested against a wrong axis the same
  bits mirror in 84 to 121 of about 650 to 830.
- All 697 unmirrored bits have an occupied tile (`0x8000`) on one side or both (685 with the neighbour occupied, 12
  with only the tile itself); none sits between two unoccupied tiles. The walk tests both tiles, so a one-sided bit
  blocks just the same.
- Every tile with a horizontal sight bit has the pathing bit of the same direction (+X 638, −X 658, −Y 845, +Y 842
  tiles; "sight only": 0). The vertical pair was not counted this way.
- Every floor tile (2,162) has `0x800` and `0x20`: a floor blocks sight and paths downward.
- Every cover direction bit has its static pathing bit with East = −X: N 195 of 195, S 197 of 197, E 169 of 169,
  W 160 of 160. About two thirds also have the sight bit (the rest is cover you can see over or through).
- Of 799 baked peek bits, the tile the code steps out to has a floor in 797.
- Unexplained: 4 tiles with bit `0x1` (flags `0x803F` at (10, 17, 0..1) and (39, 17, 0..1)), which is the
  PathBlockingVolume pattern `0x3F` of native-code-notes; under the real bit layout that pattern blocks pathing in
  every direction but up and sets the unused bit 0.

## 2. Unit to unit sight

### 2.1 `CanSeeActorToActor(From, To, out Info, bCheckRange = true, CoverDirection = -1, ViewerIndex = -1, bIgnoreStealth = false)`

Thunk `0xC07E00`, virtual slot 0x1D0 of UXComWorldData (`0x1ADA868`) = **`0x895090`**. Read end to end. (high)

1. Null actor: log, return false. `From == To`: return true.
2. `ViewerIndex < 0`: find `From` in `Viewers` (`this+0x178`). `Info.bVisibleFromDefault = false`,
   `Info.AdditionalFlags = 0`.
3. `From` must be an XComLocomotionUnitPawn in the viewer list, else flag `0x4`, return false.
   `ViewerUnit = pawn+0x560`.
4. `Dist = |From.Location − To.Location|` (3D, the two pawns' locations, actor+0x54).
   `bInRange = Dist ≤ ViewerUnit.GetSightRadius() × 64 + 48` (`GetSightRadius` is unit vtable 0x474 = `0x9167F0`,
   an int at unit+0x1FC, metres; 27 for nearly every character in LWR's `DefaultGameCore.ini`).
   When in range, `bCheckRange` is forced to true.
5. If `To` is a unit pawn and its unit `IsSavedCivilian()` (vtable 0x654): return false.
6. Unless both units have a pawn (unit+0x2BC) **and** `bInRange`: if `bCheckRange`, fail (flag `0x4`, and `0x800`
   when out of range). With `bCheckRange` false the function goes on out of range, by line checks (step 9).
7. Target unit bit 20 of unit+0x2D0 set: flag `0x8`, not visible (which bool this is was not identified; low).
   Else `Target.IsHiding(ViewerUnit)` (vtable 0x4B8) and not `bIgnoreStealth`: flag `0x10`, not visible.
8. `Dir = normal(To.Location − From.Location)`.
9. The checks, each through `0x8626D0` (2.2), in this order:
   - **default**: source = the viewer's `DefaultVisibilityCheckTile` / `…Location` (unit+0x12CC / +0x12C0), mask 1.
     If seen: `SetInfo(dist², CoverDirection, eNoPeek)` and `Info.bVisibleFromDefault = true`.
   - `CoverDirection ≥ 0` and the viewer has cover that way (`CoverDirectionInfo[d].bHasCover`):
     only if `CoverDirectionInfo[d].CoverDirection · Dir > 0` (the target is on the cover's side), try the **left
     peek** (if `bHasPeekaround`), then the **right peek**, each with its own mask (table `0x1C1BF9C`:
     N left 0x10 right 0x08; S 0x08, 0x10; E 0x02, 0x04; W 0x04, 0x02). Both are tried even when the default saw it.
   - otherwise (`CoverDirection == -1`, or no cover that way): for the four cover directions in order, **only while
     nothing has been seen yet**, try left then right peek of each direction that has cover. No dot test in this
     branch. With −1 the mask byte read from the table is 0 (the bytes before its first entry), which in the tile
     map path means "any source bit" (2.2). With a named direction that has no cover the loop runs with that
     direction's two masks, whatever direction each peek belongs to (a quirk; the callers read never do this).
   - `SetInfo` (`0xB08E80`) keeps the candidate with the smallest squared 2D distance from the source location to
     the target unit's location: `AdditionalFlags |= 7`, `bVisible`, `CoverDirection`, `PeekSide`,
     `PeekToTargetDist` (which holds a **squared** distance; it starts at FLT_MAX in `CheckTargetSquadsight` and the
     unit's defaults, a caller passing 0 would never get it filled).
10. Flags at the end: `0x400` when `ViewerUnit.BioelectricSkinRange × 64 ≥ Dist` (unit+0x1124), `0x80` seen or `0x4`
    not seen, `0x800` when out of range. Return seen.

`UpdateVisibility` (`0x509E60`) is not the tile solver: per viewer it runs `0xC5DEF0`, which calls
`CanSeeActorToActor(viewer, other, info, true, d, -1, sameTeam)` once per cover direction `d` the viewer has cover in
(or once with −1 when it has none), for every other viewer, and files the result in the units' visible-enemy and
visible-friend lists. (high)

### 2.2 One source against one target unit: `0x8626D0`

Arguments: viewer index, peek side, source tile, source location, viewer unit, From, target unit, To, mask, flags,
`bUseMap` (the caller's `bCheckRange`), the tactical GRI's object at +0x260 (only tested for null; taken to be the
trace manager, low). Read end to end. (high)

Target places tested, results OR-ed:
- the target's default tile / location, if its `bDefaultTileValid`;
- for each of the **target's** four cover directions that has cover and whose direction `c` satisfies
  `c · normal(From.Location − To.Location) ≥ 0` (the cover faces the viewer): the target's left peek tile / location
  and its right peek tile / location, where it has them. A target leaning out is seen where it leans.

Each place is tested one of two ways:
- **`bUseMap` (inside sight radius): tile map.** `word = ViewerMap[viewer].Get(tile)` (`0xD92E60`: the per-viewer
  store at native world data +0x8124, 0x8064 bytes per viewer, chunks of 3 × 3 × 2 tiles as the static store, a
  16-bit word per tile at chunk+4+2i, present byte at chunk+0x28+i).
  Seen = `word & mask` when the mask is not 0, else `(word & 0xFF) != 0`.
  Quirk: for the **default place only**, when the whole word is 0 the code leaves its local unset (`0x8628D1` →
  `0x862901` reads `[esp+0x188]` before any write). Treat as not seen. (the read is high; what the stack holds is
  unknowable statically)
- **not `bUseMap` (squadsight): line check.** `Trace(Hit, sourceLocation, placeLocation, extent 0, CheckType 4,
  SourceActor = From)` (`0x619670`, section 6). Seen = no hit, or the hit actor is `To`.

So inside sight radius the question "does A see B" is: **is B's eye tile, or one of B's step-out tiles on the side
facing A, marked in A's map with the bit of A's source tile.**

### 2.3 The viewer's tile map (the real sight rule)

Chain, all read (high; that `0xCD1ED0` is the per-frame update is by its content, medium): `0xCD1ED0` keeps each
`ViewerInfo.Tile`; a change queues a job
(`0x96FEB0` → `0xCE8B00` → job constructor `0xA25620`); the solver step `0xFC7D30` hands the job to 8 workers, one per
octant (`0xB3B580` sets a worker up, `0xEC4620` solves, `0xFA9870` walks one ray); `0x6ECB70` merges the 8 results
into the viewer's store and then runs `0xC5DEF0` (2.1) for that viewer. The rebuild consumer `0x46C700` also queues
viewers (`0x46DBB7`), so a rebuilt tile changes sight.

**Viewer tile and radius.**
- `ViewerInfo.Tile` (ViewerInfos at `this+0x184`, 0x30 bytes each) = `GetFloorTileForPosition(Actor.Location +
  PositionOffset)` (`0xB4F1C0`); a flying unit (bit 22 of unit+0x2D0) uses the plain tile of the location lowered by
  its cylinder's height; with no floor found, the plain tile. The pawn registers with no offset
  (`XComUnitPawnNativeBase.uc:264`).
- `GetFloorTileZ(x, y, z)` (`0xD45A70`): the first of z, z−1, z−2 with `0x2000`; else z+1 if it has it; else z.
- `RegisterActor` (`0x890DB0`): `SightRadius = metres × 64` (float), `SightRadiusRaw = metres`,
  `SightRadiusTiles = trunc(metres × 64 / 96)` (27 m → 1,728 units → 18 tiles). The tick refreshes them from
  `GetSightRadius()`. For a viewer whose unit `IsMine()` (vtable 0x494) under a condition not identified, the radius
  is quartered and ViewerInfo bit 1 set (low; not followed).
- The job's source: `(TileX, TileY, TileZ + 1)`, or `TileZ` on the top level. **Rays start one level above the
  floor tile: the eye tile.** (`0xA2586C`)

**Sources.** The own eye tile, mask `0x01`, plus up to four step-out tiles: for each cover direction with cover and
each side with `bHasPeekaround` (section 3), the peek tile's X and Y **at the viewer's own eye level**, if inside the
world and not listed yet. Masks: tile at **+Y `0x02`, −Y `0x04`, −X `0x08`, +X `0x10`**.

**Targets** (`0xEC4620`). With R = `SightRadiusTiles` and signs (sx, sy, sz) per octant (table `0x1AF08D0`), for
d = R−1 down to 0 the three faces of the cube shell at distance d: z = z0 + sz·d with x and y over 0..d steps, then
y = y0 + sy·d, then x = x0 + sx·d, clipped to the world. A tile is traced only if
`(96·Δx)² + (96·Δy)² < SightRadius²` (2D, tile centres, strict; `0xEC49F0`). So the tiles looked at are those with
**max(|Δx|, |Δy|, |Δz|) ≤ R − 1 and 2D distance below the radius**; there is no other height limit. Every target
gets its own ray from every source; tiles passed on the way are not marked. The worker copies the static (and
dynamic) flags of its box first (at most 21³ tiles), so a ray reads a snapshot.

**The ray walk `0xFA9870(worker, src, Δ, target, mask, …)`**, in eighths of a tile, integers only:

```
ax, ay, az = 8|Δx|, 8|Δy|, 8|Δz|;   sx, sy, sz = sign(Δx), sign(Δy), sign(Δz)
steep = (|Δx| + |Δy|) / |Δz| < 1.0          (float; false when Δz = 0)
px, py = 8·srcX + 4, 8·srcY + 4;   pz = 8·srcZ + (8 if steep else 4)
cur = src;   new = src
exy = ay − ax;   exz = az − ax;   eyz = ay − az
repeat ax + ay + az times, stopping when blocked:
    if exy < 0:
        if exz < 0:  px += sx; new.x = px / 8; exy += 2ay; exz += 2az      (an X step)
        else:        pz += sz; new.z = pz / 8; exz −= 2ax; eyz += 2ay      (a Z step)
    else:
        if eyz < 0:  pz += sz; new.z = pz / 8; exz −= 2ax; eyz += 2ay      (a Z step)
        else:        py += sy; new.y = py / 8; exy −= 2ax; eyz −= 2az      (a Y step)
    if new != cur:
        s = the step just made (axis and sign)
        blocked = static[cur] & bit(s)  |  static[new] & bit(−s)
        if not blocked: cur = new
```
`bit()` is the table of section 1. Nothing else is tested: not `0x8000`, not the dynamic flags (the worker's copy of
them, worker+0x91A8, is only prefetched), not the tiles' contents. (high)

In the steep case (more levels than tiles apart) the walk starts at the top of the source tile and ends on the top
face of the target tile, which the integer division counts as the tile above. So a steep ray **upward** crosses the
source's ceiling at its first Z step and also the target's ceiling at its last; a steep ray **downward** never makes
the last crossing, from the tile above the target into the target, so that one boundary is not tested. Both only
show where a floor lies directly over an eye tile. (the arithmetic is high; medium that it matters in play)

**Marking** (word array, 2 bytes per tile):
- Not blocked: `word[target] |= mask | 0xFF00`. Then, for the tile **above** if `static[target]` lacks `0x1000` and
  `static[above]` lacks `0x800`, and for the tile **below** if `static[target]` lacks `0x800` and `static[below]`
  lacks `0x1000`: `word[neighbour] |= 0xFF00`, and `|= mask` too **when that neighbour is a floor tile (`0x2000`)**.
- Blocked, and the tile the ray was entering has `0x8000` or `0x10000`: that tile and the tiles above and below it
  get `0xFF00` only (the fog shows the wall; no unit is seen there).

**Merge** (`0x6ECB70`): when all 8 octants are done the viewer's store is cleared and every non-zero word OR-ed in.

`sight_ref.py` is this rule in Python. On URB_Bar, for 2,625 pairs of standable floor tiles inside radius: 43 % have
direct sight, the walk disagrees with its reverse in 13 pairs (it is not exactly symmetric), 56 pairs are seen only
through a step-out.

### 2.4 What `bUseLineChecks` and `bUseLineChecksForFOW` change

- `CanSeeActorToLocation(From, Loc, bUseLineChecks)` (`0xC68ED0`) = `CanSeeActorToTile(From, tile(Loc), …)`.
- `CanSeeActorToTile` (`0xBDC4B0`), **without** line checks: the viewer's word at exactly that tile; bit 1 = from the
  default place, else the peek masks per cover direction, filling the unit's `PositionDirectionInfo` (unit+0x13AC).
  No range test of its own: a tile outside the solver's reach simply has no word. (high for the head of the
  function; the rest skimmed)
- **With** line checks (`0xBDD07C`): `Trace(viewer's DefaultVisibilityCheckLocation → the tile's point, extent 0,
  CheckType 4, From)`, then the same from each peek location; seen = no hit. The tile map is not read. (medium; the
  target point's computation was not read)
- `bUseLineChecksForFOW` (bit 19 of `this+0x40`): no native test of it was found by pattern scans for the common
  encodings, and no script reads it. Taken as unused. (low-medium) Bit 17 `bUseSingleThreadedSolver` and bit 20
  `bDrawVisibilityChecks` are read by the solver.

## 3. Step-out (peek) and squadsight

### 3.1 `CacheVisibilityDataForTile(X, Y, Z, out Data, optional Unit)`: `0x6E5E00` (slot 0x234), read (high)

`CachedVisibilityQueryData` is 0x19C bytes: four `CoverDirectionPeekData` of 0x60 (LeftPeek +0, RightPeek +0x28,
CoverDirection +0x50, bHasCover +0x5C; a `PeekAroundInfo` is bHasPeekaround +0, PeekaroundLocation +4,
PeekaroundDirectionFromCoverPt +0x10, PeekTile +0x1C), then DefaultVisibilityCheckLocation +0x180,
DefaultVisibilityCheckTile +0x18C, bDefaultTileValid +0x198. A unit keeps one at unit+0x1140
(`VisibilityQueryCache`), filled by `CacheCoverDirectionPeekInfo` (`0xFD9030`, unit vtable 0x630) for the floor tile
under the unit's location; the solver's job gets its own for the viewer's tile (with no unit).

1. `P` = centre of tile (X, Y, Z). `(fx, fy, fz) = GetFloorTileForPosition(P)`.
2. `DefaultVisibilityCheckTile = (fx, fy, fz + 1)` (fz on the top level);
   `DefaultVisibilityCheckLocation` = that tile's centre, 96 above the floor level's bottom.
   `bDefaultTileValid` = the tile is inside the world. (`GetFloorTileForPosition` always gives a tile: with no
   floor near, `fz` is the tile's own level.)
3. `Cover = GetCoverPoint(position of the floor tile)` (slot 0x1F4). None: no cover directions, done.
   With a unit: `Unit.CanUseCover(false)` (vtable 0x584) must hold, else done.
4. No peeks at all when the unit's character object (unit+0x2B8) has the value 1 at +0x1DC (not identified; low).
5. For i = 0..3 (N, S, E, W), `bit = 1 << i`:
   - `bHasCover = Cover.Flags & bit`; `CoverDirection = GetWorldDirection(bit, Flags & 0x10000)`.
   - **Left peek** when `Flags & bit` and `Flags & (bit << 8)`; **right peek** when `Flags & (bit << 12)`:
     - `PeekDir` = CoverDirection turned by yaw −90° (left) or +90° (right): the table of section 1.
     - `PeekaroundLocation = DefaultVisibilityCheckLocation + 96 · PeekDir + 32 · CoverDirection`
       (32 = 96 × ⅓: a third of a tile toward the cover).
     - `PeekTile = tile(PeekaroundLocation)`.
     - Dropped when `GetFloorTileForPosition(PeekaroundLocation)` finds no floor, or when that floor tile or the
       tile above it has dynamic flag `0x2` (a unit stands there) and it is not this unit's own claim (with no unit
       given: always dropped).

So **which sides a unit can lean to is baked** (CoverFlags peek bits; how the bake decides them is the cover step's
side). At run time only "is there a floor" and "does another unit stand there" are added.

### 3.2 How the query uses it

- The viewer's map has a bit per source tile (2.3), so "seen from the default place" and "seen from the left of
  North cover" are separate lookups of the same word.
- `bVisibleFromDefault`: the default lookup hit. `PeekSide` and `CoverDirection`: the nearest hitting source
  (smallest squared 2D distance from the source location to the target). `PeekToTargetDist`: that squared distance.
- A peek counts for a shot at a target only for a cover direction whose vector has a positive dot with the direction
  to the target (2.1 step 9), when the caller names the direction (as the unit lists' update does).
- The peek source is traced **from the peek tile at the viewer's eye level** like any other source: sight from a
  step-out is exactly sight from standing one tile to the side. The 32-unit forward offset of `PeekaroundLocation`
  only matters to the line-check path and to the distance compare.

### 3.3 Squadsight: `CheckTargetSquadsight(ViewerPawn, TargetPawn, out Info)`: `0x75A580` (slot 0x1C4), read (high)

- Resets `Info` (CoverDirection −1, PeekToTargetDist FLT_MAX). The target unit must be `IsAliveAndVisible`-like
  (vtable 0x4C8; the name is from the thunk order, medium).
- Calls `CanSeeActorToActor(viewer, target, Info, bCheckRange = **false**, d, -1, false)` for each cover direction d
  the viewer has cover in, or once with −1; ORs the results; stores `Info` in the viewer unit's list (unit+0x16B0).
- Effect (2.1 steps 4 and 6): **inside sight radius the tile map decides; outside it, line checks decide**
  (default place first, then the peeks). There is no squadsight range limit in this function.
- Script (`XGUnit.ProcessVisibilityWithVisInfo`, `XGUnit.uc:9418`): `CheckTargetSquadsight`, then also
  `CanSeeActorToLocation(pawn, enemy.Location, true)` (a line check to the enemy's location) as a second way to be
  visible; when that holds and the enemy is in cover and not flying, it adds the flanker (section 4).

## 4. Flanking and cover in a shot

### 4.1 Is the target flanked by this attacker: natives, read (high)

`IsFlankedBy(Enemy)` (`0x104F610`, unit vtable 0x4AC) and `IsFlankedBy_EnemyAtLocation(Enemy, Loc)` (`0xB99F40`,
0x4B0) share the preconditions and then call `0x102DCB0`:

- `Enemy.CanFlank()` (`0xDFCD80`): not `IsMeleeOnly`, not critically wounded, a script event returns true (not
  identified), and bit 24 of unit+0x2D0 clear (not identified; low).
- The target: not critically wounded; `IsInCover()` (`0xC37820`: bit 1 of unit+0x2D0, taken to be "holds claimed
  cover", and `GetCoverPoint` at its cover-query location finds a point); the same bit 24 clear.
  `CanBeFlanked()` (`0x73FBF0`) is exactly these three.
- Different teams.
- **The enemy sees the target** (`0x102DD8A`–`0x102DEE1`): if the target stands on the tile asked about, the cached
  `GetDirectionInfoForTarget` (vtable 0x63C); else `CanSeeActorToTile(enemyPawn, targetTile, false)` when the target
  place is within the enemy's sight radius, or with line checks when beyond it and the enemy's character has
  +0x2C0 set (taken to be squadsight; low), else no.
- `Cover = GetCoverPoint(target's cover-query location)` (`0xA3E0D0`: the pawn's feet, or the claimed cover place).
- **Flanked when `DoesFlankCover(EnemyLoc, Cover)`**; or, when the enemy has cover itself, for the enemy's cover
  direction most toward the target (largest positive dot): from its left step-out place
  `EnemyLoc + 100 · PeekLeftDir` (if its cover flags have that peek), then from its right one. Otherwise not flanked.

`DoesFlankCover(PointA, Cover)` (`0xAF0B40`): for **every** direction i in `Cover.Flags & 0xF`:
`DoesFlank(PointA, Cover.CoverLocation + 4 · Dir_i, Dir_i)` must be true. One cover direction that still stands
between the attacker and the target means not flanked.

`DoesFlank(A, B, DirB)` (`0xD256D0`), with `FlankingAngle` = 180 (unit+0x1134, script default) and
`FLANKINGTOLERANCE` = 3:
```
v = B − A flattened to 2D and normalised;   angle = acos(clamp(v · DirB, −1, 1)) in degrees
if angle ≥ FlankingAngle/2 + 3:      false
if angle ≤ FlankingAngle/2:          true
else:  true when sin(angle − FlankingAngle/2) × |B − A|2D < 52
```
`DirB` points from the unit to its cover. In words: **a cover direction is flanked when the attacker is not on the
cover's side of the line through the unit across that direction**, with a 52-unit, 3-degree allowance. On the grid
(attacker and cover location at tile centres, 96 apart, B pushed 4 toward the cover): direction d of a target at tile
T is flanked by an attacker at tile A exactly when `(A − T) · d ≤ 0`. The baked CoverLocation is within a few units
of the floor location on URB_Bar (offsets 0, ±2, ±4, a few 9.2), so the grid rule holds there. (medium for the
grid shortcut; the functions are high)

`IsFlankedByLoc(Loc)` (`0xFCB9F0`) = `DoesFlankCover(Loc, own cover point)`: the geometry only, no sight, no
preconditions.

Script (LWR's): `XGUnit.HasEnemyAsFlanker(kEnemy)` (`XGUnit.uc:4001`) = `IsFlankedByLoc(kEnemy.Location)`, or the
enemy is in `m_arrFlankingUnits`, or `IsFlankedBy(kEnemy)`; `m_arrFlankingUnits` is filled in
`ProcessVisibilityWithVisInfo` when `IsFlankedBy(self) || IsFlankedByLoc(Location)`.

### 4.2 Cover value against an attacker: `UpdateCoverBonuses(Attacker)`: `0xD8CB30` (unit vtable 0x574), read (high for the cover part)

- Own cover point at the cover-query location. Needs `CanUseCover` and `Flags & 0xF`.
- **With an attacker**: of the directions the unit has cover in, the one whose vector has the **smallest dot** with
  `normal(own pawn location − attacker's pawn location)` (the cover most squarely between them). That direction's
  cover is **high** when its low bit (`bit << 4`) is clear, **low** when set.
- With no attacker: high if any direction is high, else low if any is low.
- Value: high `HIGH_COVER_BONUS` (game core +0x1D4), low `LOW_COVER_BONUS` (+0x1D0), plus perks; smoke adds 20
  (unit flag bits 13 and 10, two kinds), height +10 with a perk, and so on. No cover: air evade (+0x1DC) or the
  no-cover value (+0x1E0).
- Values: script defaults (plain EW's) `LOW_COVER_BONUS = 20`, `HIGH_COVER_BONUS = 40`, `FLANKING_CRIT_BONUS = 50`
  (`XGTacticalGameCore.uc:3115`); **LWR's `DefaultGameCore.ini`: 30, 50, 50** (lines 1399–1406 of the install's
  copy; `SW_FLANK_CRIT=100`, `AIR_EVADE_DEF=30`, `HUNKER_BONUS=1.3`). The lab's `lwr-copy` holds only the mutator's
  package and source, no ini.

### 4.3 Height and other map-dependent terms

- `HasHeightAdvantageOver(Target)` (`0x6B00B0`, vtable 0x53C): `own GetLocation().Z − Target.GetLocation().Z ≥ 192`
  (pawn locations; three levels of 64). (high)
- Distance to target (`m_fDistanceToTarget`) feeds range modifiers (`CLOSE_RANGE = 15`, `AIM_CLIMB` in the ini).
- **Not followed**: `XGAbility_Targeted.CalcHitChance` (thunk `0x875E70`, class slot 0x410), `ShotInit` (0x404), which
  sets `m_bHasFlank` and `m_bHasHeightAdvantage`, and `XGTacticalGameCore.CalcBaseHitChance`. Their vtable was not
  found, so "a flanked target loses its cover value" is taken from the script's shot summary
  (`XGAbility_Targeted.GetShotSummary`, which lists cover from `m_iCurrentCoverValue` and treats
  `HasEnemyAsFlanker` as "cover does not count") and not read in the native. (medium)

## 5. The visibility map and the fog

- The same per-viewer words serve everything: `IsLocationVisibleToTeam(Loc, Team)` (`0xAFA410`, slot 0x240) is true
  when any unit-pawn viewer of that team has a non-zero low byte at `tile(Loc)`. (high)
- The high byte `0xFF` marks tiles "seen" without being standing places: the neighbours above and below a seen
  tile, and occupied tiles that stopped a ray. Taken to drive the fog texture; the texture code was not read. (medium)
- `TileData.VisibilityFlags` / `Viewers` are the script's view of a tile; the native keeps the words per viewer.
- `QueryCanSeeLocationTiles` (`0xA663F0`) and `GetCanSeeLocationTiles` use the same stores (they reference the
  per-viewer store); not read further.

## 6. `IsAdjacentTileVisible`, line checks, smoke, the cutaway, destroyed pieces

**`IsAdjacentTileVisible(From, To)`** (thunk `0x6C50B0`, slot 0x1E4 = `0x54BB20`, worker `0xC66A90`), read (high):
`f = static[tile(From)]`, `Δ = tile(To) − tile(From)`. Blocked when `f` has `0x8000` without `0x10000` (a fully
occupied tile), or has the bit of any non-zero component of Δ: Δx > 0 `0x100`, < 0 `0x80`; Δy > 0 `0x400`, < 0
`0x200`; Δz > 0 `0x1000`, < 0 `0x800`. Returns not blocked. **Only the From tile is read**, not the neighbour.
Callers: `XGAction_TakeDamage.uc:319`, `XGUnitNativeBase.uc:2772`.

**The line check `0x619670(Hit, Start, End, Extent, CheckType, SourceActor)`**; `WorldTrace` (`0x725B50`, slot
0x26C) is this with a zero extent and no source actor. (high for the structure, medium for class details)
1. Actors: the collision octree's overlap walk around the segment's midpoint, radius 0.6 × its length (bounding
   boxes, one result per actor, at most 16 hits kept).
2. Per `CheckType` a filter (jump table `0x619E6C`): 0 and 1 `0x9BA250`, 2 `0x6855F0` plus interactive and
   destructible actors, 3 `0xF61F70` (cover interface), **4 = sight: `0x10C0F70`**:
   - an actor with `CollisionType` COLLIDE_NoCollision (+0x9D = 1) counts only if it is an
     XComInteractiveLevelActor without bit 5 at +0x398 (by field order `bWasTouchActivated`; low);
   - a PathBlockingVolume only with bit 0 at +0x1FC (the bit that also gives it the sight bits in the rebuild);
   - an XComLevelActor only with `VisibilityBlockingData.bBlockUnitVisibility` (+0x1DC bit 0, default true);
   - an XComFracLevelActor only with the same flag (+0x25C bit 0);
   - never an XComPawn or XComUnitPawnNativeBase; never `SourceActor`.
3. The component tested: an XComLevelActor's StaticMeshComponent (+0x1D0) if its mesh has a BodySetup (an
   XComDestructibleActor with bit 1 at +0x24C is skipped: by field order `bIgnoreForPathing`, low; a destructible
   skeletal mesh actor uses its own component); an XComFracLevelActor's component (+0x1D4) under the same BodySetup
   condition; a PathBlockingVolume's brush (+0x1E4). **Any other actor class is never tested**: plain
   StaticMeshActors, BlockingVolumes, terrain.
4. `Component.LineCheck(Hit, End, Start, Extent, 0x860D3)` (vtable +0x1A0): no `TRACE_ComplexCollision`, so simple
   collision (for some actors the mesh's two simple-collision switches are forced on for the call; when that
   applies to CheckType 4 was not followed). Hits are sorted and the first returned.

**Smoke.** No effect on sight: the walk reads no dynamic or volume data, and the line-check filter knows no smoke.
Smoke is a defence bonus (+20 per kind in `UpdateCoverBonuses`; LWR's shot summary shows the same). (high)

**The cutaway.** No effect on gameplay sight. `Helpers.isVisibilityBlocked` is called only by camera code
(`XComCamera.uc:161`, `XGCameraView.uc:465`). Hidden or cut meshes change no static flag. `XComTraceManager.
IsVisibilityTrace`'s thunk (`0xF2C770`) is a stub shared with other natives. (high)

**Destroyed pieces.** A destroyed prop's `SetStaticMesh(None)` calls the tile rebuild over its bounds (F-101); the
rebuild recomputes the sight bits of the queued tiles and its consumer re-queues the viewers (`0x46DBB7`), so sight
opens after the rebuild, by the same rule. As F-29 says, only tiles with some bit in `0xFFF` get re-checked. (medium:
the chain's two ends are read, the rebuild's writing of sight bits is the other agent's subject)

## 7. Unresolved

1. Native `CalcHitChance` / `ShotInit` / `CalcBaseHitChance` (XGAbility_Targeted's vtable not found): where exactly
   flank removes cover and what else of the map enters the hit chance.
2. Unit bools: bit 20 of unit+0x2D0 (never seen), bit 24 (cannot flank or be flanked), bit 1 (in cover); the script
   event inside `CanFlank`; character +0x1DC == 1 (no peeks) and +0x2C0 (squadsight?).
3. `RegisterActor`'s quartered radius and ViewerInfo bit 1 (`bHasSeenXCom`?): the condition was not followed.
4. The uninitialised local in `0x8626D0` when the target's default tile word is 0.
5. `bUseLineChecksForFOW`: no reader found; not proven unused.
6. `CanSeeActorToTile`'s line-check target point and the rest of that function; `QueryCanSeeLocationTiles`,
   `GetCanSeeLocationTiles`; the fog texture's use of the `0xFF00` byte.
7. The octant boxes' edges: a ray's last steep Z step, or a neighbour above the box, reads outside the copied box
   (stale worker memory). Not expected to matter away from the map's top.
8. Bit `0x1` of the static flags and the PathBlockingVolume pattern `0x3F` / `0xFC0` under the real bit layout
   (it leaves `0x1000`, sight upward, clear).
9. The pathing bits' directions are from data (mirror counts and the cover table), not from the pathing code.
10. The line-check filter's class details (interactive actor bit, destructible bit) are named by field order only.

## 8. Files in `<lab>\re\sight\`

| File | What |
| --- | --- |
| `sight.md` | this |
| `RESUME.md` | work order, state, next steps |
| `sight_ref.py` | the tile sight rule in Python (`walk`, `viewer_word`, `peeks`, `can_see`) with sanity numbers on URB_Bar |
| `check_bits.py` | direction bits against a container's static flags (mirror counts, pathing against sight) |
| `check_cover.py` | cover flags and cover locations against the static flags and the peek directions |
| `rd.py` | read floats, ints, bytes, strings at a virtual address of the exe copy |
| `castcls.py` | name the class a `Cast<T>` / `StaticClass` helper is for |
| `execslots.py` | a class's natives → the virtual slot or direct call their thunks end in (`slots_XGUnit.txt`) |
| `findvt.py` | find a virtual table by a slot's function containing an immediate |
| `scanimm.py` | where a 4-byte immediate occurs in code, by function |
| `fn_<va>_<name>.txt`, `exec/*.txt` | disassembly dumps of every function named above |

Virtual tables used: UXComWorldData `0x1ADA868`; the unit class (XGUnit) `0x1AEC218`; the solver worker's inner table
`0x1ADF56C` (slot 0xC `0x7AA250` → `0xEC4620`).
