# How XComWorldData computes cover and the blocking bits (XComEW.exe, read-only)

> Copied into the repo on 15 November 2026 from the lab folder `<lab>\re\cover`, where the disassembly dumps
> (`dis_*.txt`, annotated `dis_*.ann.txt`) and the helper and check scripts it names stay. What it means for the
> editor, and a second check of its bit order, are in [cover-and-sight.md](cover-and-sight.md).

15 November 2026. Static reading of `<lab>\re\XComEW-copy.exe` (image base `0x400000`); nothing was run or
patched, no game file was written. In the annotated dumps `[F+xx]` is a stack slot named by its offset from esp
after the prologue.

Confidence marks: **high** = read end to end and consistent with the baked data (and, where said, with the geometric
spot-check); **medium** = read, not or only partly checked; **low** = inferred.

The decompiled scripts in `<lab>\reference\XComGame-decompiled` are **LWR's** XComGame (they carry
`BaseMutator.Mutate("…")` hooks and `AddMutator("XComMutator.XComMutatorLoader")`). The constants and native
declarations used here are the same in plain EW; the exe is shared by both.

## 0. Corrections to what was known

| Was | Is | Confidence |
| --- | --- | --- |
| Static bits `0x3F` pathing, `0xFC0` visibility | **Pathing `0x7E`, visibility `0x1F80`.** Bit order in both: −X, +X, −Y, +Y, down, up: pathing `0x2, 0x4, 0x8, 0x10, 0x20, 0x40`; visibility `0x80, 0x100, 0x200, 0x400, 0x800, 0x1000`. Bit `0x1` is set by nothing but the stale masks. The script constants `0x3F` / `0xFC0`, the rebuild's queue test (`0xE6ECB0`) and the PathBlockingVolume branch of the occupancy step (`0xCF2B25`) still use the old masks | high (`0xE1F390`; both maps: `0x29040` ceilings, `0x522820` ground, volume tiles `0x803F`) |
| "East" is +X | **Cover bit `0x4` (COVER_East) is cover toward −X, `0x8` (COVER_West) toward +X.** The table's name strings say "East (+X)" and its tile deltas say +X, but its direction vectors, the direction mask and the baked data all say −X | high (data: 68 of 68 and 108 of 108 tiles; spot-check) |
| The follow-up check `0x72A840` decides low cover | It is `UWorld::SingleLineCheck`, used twice: to refine the wall point, and to find **the floor under the cover location**. High or low is decided by a second sweep 96 over that floor | high |
| The sweep is 32 × 16 × 16 or 1 × 1 × 8 | **A box of half-extent (1, 1, 8)**: `0xC6E980` ignores its first and third size arguments and halves the second | high (spot-check: wall point = hull surface − 1) |
| Tile position = 96-grid centre | The grid origin is `WorldBounds.Min` (`UXComWorldData+0x48`), which lies **one unit outside** the level volume on every axis (URB_Bar −2785, −1921, −1; farm −2497, −3553, −129). Position = origin + (96x + 48, 96y + 48, 64z + 32) (`0xD5B5E0`) | high |
| Occupancy box at the tile's centre | Its centre is **28 above the tile position** (base height 24 + 4): the big box spans 28 to 92 over the level's bottom, the small one 60 to 92 | high for the code (`0xA589AB`–`0xA589DD`), not checked on geometry |

## 1. Order of work for one tile

The full build (`BuildWorldData`, vtable slot `0x144` = `0x988D40`) and the runtime rebuild (consumer `0x46C700`)
call the **same per-tile functions in the same order**, each pass over all tiles before the next (high):

| Pass | Function | What |
| --- | --- | --- |
| (build only) | `0xE4B630` | every `XComCoverSeed` actor with `bDiagonalCover` (+0x1D0 bit 0): cover flags of its tile \|= `0x10000` |
| 1 Occupancy | `0xCF2470(tile, 0, 1)`, then `(tile, 1, 0)` if the tile got `0x8000` | occupied, partial, near, floor (section 2) |
| 2 Cover and blocking | `0xD57E90` | standing room: may take the floor away; marks the two tiles above with `0x80000` |
| | floor volume, water volume | not cover |
| | `0xF0D8F0` → `0xA0A2B0` | cover (sections 3 and 4), only on a tile with `0x2000` and without `0x4000` |
| | `0xE1F390` | the 12 blocking bits (section 5), only on a tile with `0x20000` |
| 3 Interactions | `0x7E8E30` | each interact point on the tile ORs its `ModifyTileStaticFlags` into the static flags |
| 4 Neighbors | `0x905780` (+ `0xD8F610`), build only `0x9F8680`, then ladders `0x777580` | links; bits `0x100000`, `0x200000`; edge bits |

Calls: build `0x9898F7`, `0x9899F3`, `0x989CAB`, `0x98A14F`, `0x98A177`, `0x98A1A0`, `0x98A25F`, `0x98A302`,
`0x98A399`, `0x98A415`; rebuild `0x46C969`, `0x46C9B3`, `0x46CE73`, `0x46D222`, `0x46D218`/`0x46D238`, `0x46D25B`,
`0x46D69F`, `0x46D965`, `0x46D99E`.

**Differences between build and rebuild** (high for the code):
- The rebuild works only on queued tiles (a bit in `0xFFF`), and first **clears** each one's static flags, cover
  flags, floor data, cover location and interact points (`0x8670E0`).
- So a rebuilt tile loses what only the build writes: the **edge bits** `0x800000`–`0x4000000` (`0x9F8680`) and
  **COVER_Diagonal** (`0xE4B630`): a rebuilt diagonal tile gets straight cover by this reading. In the game
  (22 November 2026, findings register F-149) CSmallScout_Farm's eight rebuilt diagonal tiles had no cover at all:
  the facing test of section 4, step 2 (0.71) turns a wall at 45 degrees (0.7071) down in every straight direction.
- A rebuilt tile keeps `0x80000` only if the floor tile under it is rebuilt too (it is the lower tile's step that
  sets it).
- Everything else follows one rule. The bake and the rebuild differ only through what is in the collision octree
  at the time and through actor state (destroyed props, doors).

## 2. Occupancy and floor (`0xCF2470`, `0xA58810`, `0xD57E90`)

`0xCF2470(tile, bSmall, bFloor)`; P = tile position.

1. **Box.** Big call: half-extent (48, 48, 32) about P. Small call: (20, 20, 16) about P + (0, 0, 16).
   `0xA58810` then moves the box's centre up by 28 for the component check.
2. **PathBlockingVolumes first** (`0xA58865`–`0xA588E7`): if one overlaps the box (`0x5B2670`), the tile is occupied,
   gets `0x3F` (and `0xFC0` when the volume's +0x1FC bit 0 is set) and nothing else is looked at (no `0x20000`).
   Baked: URB_Bar's four volume tiles are `0x803F`.
3. **Octree query** (`GWorld+0x12C`, slot +0x18) about P with radius extent + 28 (76, or 48): any result sets
   **`0x20000`** ("something near").
4. Each result (one per actor) counts when (filter case 0, `0xA58A0C`):
   - the actor implements `XComCoverInterface` and `ConsiderForOccupancy()` (interface slot +0x8) is true;
   - small call only: not an `XComUnitPawnNativeBase`; an `XComInteractiveLevelActor` only if its virtual +0x434
     returns false (not identified);
   - its component: an XComLevelActor's `StaticMeshComponent` (+0x1D0), whose mesh needs a **BodySetup** and bounds
     half-extents all ≥ 2 (or X or Y ≥ 192); an XComLadder is left out; an XComFracLevelActor's component (+0x1D4,
     BodySetup needed); an XComDestructibleSkeletalMeshActor's +0x190 or +0x36C; an XComPawn's +0x368;
   - the component's `PointCheck` (slot +0x19C) with the box and flags `0x860D3` hits.
5. Big call: hit → **`0x8000`**. Small call: no hit → **`0x10000`** (so `0x8000` alone = fully occupied, `0x8000 |
   0x10000` = partly: the 40 × 40 box 60 to 92 over the level's bottom is free).
6. **Floor** (big call, something near, no blocking volume): `MultiLineCheck` (`0x9F2630`), zero extent, flags
   `0x860C0`, from P + 30 down to P − 34. Hits in order: skip an actor without `bPathColliding` (+0xAC bit 3); an
   actor without `bCanStepUpOn` (+0xA0 bit 27) ends the search with no floor; with it and normal z > 0.7 the floor
   is found: **`0x2020`**, plus **`0x4000`** when normal z < 0.9848, plus **`0x400000`** when the actor is an
   XComLevelActor with `bIsValidDestination` (+0x1E0 bit 5) or an XComFracLevelActor with its own (+0x258 bit 7).
   Floor data: location and normal of the hit, the actor.
7. **Standing room** (`0xD57E90`, pass 2, floor tiles): the tiles one and two above get **`0x80000`**. The floor
   (`0x2000`, `0x4000`, `0x20`) is taken away again when the tile is fully occupied, has a floor and is not a ramp,
   or when the tile one above is fully occupied. `0x400000` and the floor data stay.

Confidence: high for the code. Baked: `0x400000` without `0x2000` only on fully occupied tiles (330 of 330, 1,713
of 1,713); `0x4000` exactly where the floor normal's z < 0.9848 (680 of 680); no floor under a fully occupied tile.

## 3. Which directions are tested (`0xF0D8F0`)

Only on a tile with `0x2000` and without `0x4000` (ramps get no cover).

- Cover flags already have `0x10000` (a diagonal seed): all four **diagonals**, table B.
- Else, from the tile's static flags: fully occupied → none; partly occupied → all four; otherwise a direction is
  tested when **the neighbour that way is occupied (`0x8000`) or off the grid**: bit 1 ↔ (x, y+1), bit 2 ↔ (x, y−1),
  bit 4 ↔ **(x−1, y)**, bit 8 ↔ **(x+1, y)**.

Confidence: high. Baked: on tiles not themselves occupied, 0 direction bits toward a neighbour that is in the grid
and not occupied (URB_Bar 263 bits, farm 578 bits); every one has its neighbour as read.

## 4. Cover for one direction (`0xA0A2B0(tile, mask, bDiagonal)`)

### Tables (`0x1C1B050` straight, `0x1C1B1A0` diagonal; 4 entries of 0x54 bytes; vectors filled by `0x1372580`, `0x1372680`)

| i | Cover bit | Low | PeekLeft | PeekRight | ClimbOnto | ClimbOver | Static bit | Direction d (straight) | Right vector R | d (diagonal) | R (diagonal) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 N | `0x1` | `0x10` | `0x100` | `0x1000` | `0x20000` | `0x200000` | `0x10` | (0, 1) | (−1, 0) | (−s, s) | (−s, −s) |
| 1 S | `0x2` | `0x20` | `0x200` | `0x2000` | `0x40000` | `0x400000` | `0x8` | (0, −1) | (1, 0) | (s, −s) | (s, s) |
| 2 E | `0x4` | `0x40` | `0x400` | `0x4000` | `0x80000` | `0x800000` | `0x2` | **(−1, 0)** | (0, −1) | (−s, −s) | (s, −s) |
| 3 W | `0x8` | `0x80` | `0x800` | `0x8000` | `0x100000` | `0x1000000` | `0x4` | **(1, 0)** | (0, 1) | (s, s) | (−s, s) |

s = 0.7071. Start offset (0, 0, 24); trace length **124** (straight), **135.744** (diagonal). The table's tile delta
(+0x48) is (0, 1), (0, −1), **(+1, 0)**, **(−1, 0)**: for E and W it points away from d (used only in step 8).

### Steps

Names: P0 = tile position; F = the tile's floor location (x and y are P0's); S = (F.x, F.y, F.z + 52);
E = S + d · length.

1. **Main sweep** (`0xA0A606`): `0xC6E980` → world trace `0x619670`, **type 1**, box half-extent (1, 1, 8), from S
   to E (so 44 to 60 over the floor). No hit → no cover that way. H = the nearest hit; H.Location is the box's
   centre at contact (the surface less 1 along d).
2. **Facing** (`0xA0A7F4`): |normal(H) · d| must be ≥ **0.71**.
3. H's actor must implement the cover interface with `ShouldIgnoreForCover()` false (the trace filter already
   asks this).
4. **Refine** (`0xA0A9B8`): `SingleLineCheck` (engine trace, flags `0x860C0`, extent (1, 1, 8)) from (S.x, S.y,
   H.z) to H.Location. If it hits something that is not a cover-interface actor asking to be ignored, the wall point
   W becomes that hit's location; else W = H.Location.
5. **Cover location candidate** Q = W − **40** · d (`0xA0AA87`). (For a hit on an `XComUnitPawnNativeBase`:
   Q = S + 20 · d, `0xA0AF47`.) Q's x and y must lie strictly inside P0 ± 48, else no cover: the wall point must be
   within 88 of the tile position.
6. **Floor under Q** (`0xA0AD99`): `SingleLineCheck`, zero extent, flags `0x860C0`, from (Q.x, Q.y, P0.z) down
   36 (to 4 under the level's bottom). No hit → no cover. A hit on an XComLevelActor without `bIsValidDestination`,
   or an XComFracLevelActor without its own → no cover. zQ = the hit's z.
7. **High or low.** f = H's actor's `GetCoverForceFlag()` (slot +0x1C; 0 default, 1 high, 2 low):
   - f = 2 → low; f = 1 → high;
   - f = 0: the same box sweep **96 over zQ** (88 to 104), from (S.x, S.y) to (E.x, E.y), world trace **type 2**
     (`0xA0AED3`). A hit on a cover-interface actor whose force flag is not Low → **high**; else **low**.
8. Low only (`0xA0AFE3`–`0xA0B03B`): if the tile at (tile + table delta) is a ramp (`0x4000`) whose floor actor is
   H's actor → no cover.
9. **Ignore flag** g = `GetCoverIgnoreFlag()` (slot +0x20, same enum): g = 1 and high → no cover; g = 2 and low →
   no cover.
10. Flags so far: cover bit, plus the low bit when low.
11. **Peeks**, side 0 (left, sign −1) and side 1 (right, sign +1); all world traces type 1, zero extent:
    - from (Q.x, Q.y) to (Q.x, Q.y) + sign · R · **96**, at zQ + **96** and at zQ + **60**: both must be clear
      (`0xA0B2A9`, `0xA0B3A8`);
    - A = (Q.x, Q.y) + sign · R · **68** at zQ + 96; from A to A + d · **96** must be clear (`0xA0B511`);
    - `SingleLineCheck` (flags `0x860C0`) from A down to zQ − 20 must hit; the tile holding (hit + 4 up) must have
      `0x2000`; |hit.z − zQ| < **20** (`0xA0B5DB`–`0xA0B6E5`);
    - then PeekLeft (side 0) or PeekRight (side 1) is set. Left of N is +X, left of S is −X, left of E (−X) is
      +Y, left of W (+X) is −Y.
12. **Climb**, low cover only (`0xA0B711` on). Runs when H's actor is an XComFracLevelActor or an
    XComDestructibleActor (onto allowed), or when `CanClimbOnto()` (slot +0x14) or `CanClimbOver()` (slot +0x10)
    is true (onto allowed = CanClimbOnto):
    - world trace type 2, zero extent, from (Q.x, Q.y, zQ + **88**) to + d · 96: any hit → no climb bit;
    - B = W + d · **68**; world trace type 2 from (B.x, B.y, zQ + **160**) down to zQ + **12**;
    - no hit, or a hit less than **32** from zQ → **ClimbOver**; else (something stands there at least 32 high) →
      **ClimbOnto** if onto is allowed. Never both.
13. If any flag: static flags \|= the entry's static bit (not when H's actor is an `XComLocomotionUnitPawn`);
    cover flags \|= the flags; (Q.x, Q.y, zQ) is added to a sum.

After the four directions: **cover location** = the mean of the summed points, each coordinate clamped to
P0 ± (44, 44, 32) (`0xA0BD99`–`0xA0BFA6`, store at native +0x181F8).

### The world trace `0x619670(hit, start, end, extent, type, ignoreActor)`

- Candidates: octree query about the segment's midpoint, radius 0.6 × its length. At most 16 hits are kept, sorted
  (`0xF054D0`), the first returned.
- Filter by type:
  - **1** (and 0), `0x9BA250`: `CollisionType` (+0x9D) ≠ 1, not an XComLadder, implements the cover interface,
    `ShouldIgnoreForCover()` false.
  - **2**, `0x6855F0`: as 1, but an XComLadder passes, so does any XComInteractiveLevelActor, and an
    XComDestructibleActor whose `Toughness` (+0x284) is set and not `bFragile` (+0x40 bit 0).
  - **3** (pathing), `0xF61F70`: `CollisionType` ≠ 1; if it has the cover interface, `ConsiderForOccupancy()` must
    be true; not an XComUnitPawnNativeBase, XComLevelVolume, XComCutoutBox, XComCursorVolume or XComBuildingVisPOI.
    A hit whose tile is a ramp with that actor as its floor does not count.
  - **4** (visibility), `0x10C0F70`: with `CollisionType` 1 only an XComInteractiveLevelActor whose +0x398 bit 5 is
    clear; a PathBlockingVolume needs +0x1FC bit 0; an XComLevelActor needs
    `VisibilityBlockingData.bBlockUnitVisibility` (+0x1DC bit 0); an XComFracLevelActor its own (+0x25C bit 0);
    never an XComPawn or XComUnitPawnNativeBase.
- The actor passed as `ignoreActor` is skipped. An XComDestructibleActor with `bIgnoreForPathing` (+0x24C bit 1)
  is skipped for every type.
- Component traced: XComLevelActor → its StaticMeshComponent, only with a mesh that has a BodySetup (else a
  destructible skeletal actor's +0x190 / +0x36C); XComFracLevelActor → +0x1D4 with BodySetup; XComPawn → +0x368;
  PathBlockingVolume → +0x1E4. **Any other actor class is never hit.**
- The check is the component's `LineCheck` (slot +0x1A0) with flags `0x860D3` (no complex-collision bit): a box
  sweep uses the mesh's simple collision when `UseSimpleBoxCollision`, a zero-extent one when
  `UseSimpleLineCollision`. Types 0 to 2 with `UseRigidBodyCollisionForCover()` true (slot +0x18) force both
  flags on for the check (`0x619BE6`).

Confidence: steps 1 to 7, 9, 10, 13 and the location: **high** (see the checks). Steps 8, 11, 12: **medium**
(read in full; baked data agrees in structure only). Filters: high for the code; the +0x398 bit and the +0x434
virtual are not named.

## 5. The blocking bits (`0xE1F390(tile, tileData)`)

Runs on every tile whose static flags had `0x20000` at the start of pass 2.

- Start: with a floor (after the standing-room step), the floor location + (0, 0, **64**) (ramp: + 32, and the
  ramp's floor actor is ignored); without a floor, the tile position.
- Six directions, each one segment from the start: −X, +X, −Y, +Y **96** long; down, up **56** long.
- Per direction two sweeps of a box of half-extent **(1, 1, 0.5)** through `0xC6E980` / `0x619670`:
  **type 3 → the pathing bit**, **type 4 → the visibility bit** (both always run).
- Ramp tiles: the four lateral directions are skipped along the slope (normal has only an X part → ±X skipped;
  only a Y part → ±Y skipped) and all four when the slope is neither.
- At the end a floor tile gets `0x20`, and `0x800` when its floor actor is an XComLevelActor or XComFracLevelActor
  with `bBlockUnitVisibility`.
- The cover step adds a lateral pathing bit toward each cover direction (step 13), on the cover tile only.
- A PathBlockingVolume tile gets `0x3F` (+ `0xFC0`) by the stale masks: bits `0x1`–`0x20` (+ `0x40`–`0x800`).

So a bit is **one tile's own reading** of the segment toward its neighbour; nothing writes the neighbour's opposite
bit. The neighbour-height comparisons the notes could not name (under 20, under 32) are not blocking: they are the
peek floor test and the climb-over test (section 4, steps 11 and 12).

Confidence: high for the code and the bit order. Baked: between two floor tiles the bits mirror exactly in URB_Bar
(64 pathing pairs, 52 visibility pairs, 0 one-sided); where one tile is occupied about a third are one-sided
(start heights differ, starts inside solids, cover's one-sided bit). No visibility bit without its pathing bit in
URB_Bar; 574 on the farm (pieces that block sight without counting for occupancy).

## 6. Other static flag bits

| Bit | Meaning | Where | Confidence |
| --- | --- | --- | --- |
| `0x1` | nothing; set only with the stale `0x3F` on PathBlockingVolume tiles | `0xCF2B25` | high |
| `0x2000` / `0x4000` | floor / sloped floor | `0xCF28DC` | high |
| `0x8000` / `0x10000` | occupied / the upper middle is free | `0xCF2AFD`, `0xCF2B0B` | high |
| `0x20000` | the octree had something within 76 of the tile position; gates the blocking step | `0xCF2B17` | high |
| `0x40000` | not set by any code found; absent from the six maps looked at | scan `scanset.py` | medium |
| `0x80000` | one or two levels above a floor tile | `0xD57FC7` | high (0 floor tiles' upper tiles lack it) |
| `0x100000` | 2 × 2 standing room: floors at (x, y), (x+1, y), (x, y+1), (x+1, y+1) without bits `0x12`, `0x14`, `0x0A` | `0x905C56` | medium (URB_Bar: 1,302 agree, 152 rule only, 1 flag only: a condition is missing) |
| `0x200000` | the drop-down search found a drop of two levels or more beside the tile | `0xD8F7BB` | medium |
| `0x400000` | the floor's actor is a valid destination | `0xCF2945` | high |
| `0x800000`, `0x1000000`, `0x2000000`, `0x4000000` | the +X, −X, +Y, −Y neighbour's position is outside the level volume (build only) | `0x9F8680` | high (all tiles but the last one of the grid) |
| `0x8000000` | water | notes | |

## 7. Checks against baked data

Scripts: `bake.py` (loader), `check.py`, `check2.py`, `tiles.py`, `bits.py`, `spot.py`. Outputs: `check_*.txt`,
`check2_*.txt`, `spot_URB_Bar.txt`, `bits.txt`.

| Check | URB_Bar (52 × 39 × 12, 644 cover tiles) | CsmallScout_Farm (67 × 70 × 17, 1,426 cover tiles) |
| --- | --- | --- |
| low without its direction; peek without direction; climb without low; onto with over; cover off a flat floor; cover on a fully occupied tile | 0 of 721 direction bits | 0 of 1,550 |
| direction bit without the static bit as read (N `0x10`, S `0x8`, E `0x2`, W `0x4`) | 0 | 0 |
| bit `0x4`: neighbour x−1 occupied or off grid / x+1 | 68 of 68 / 6 | 108 of 108 / 17 |
| bit `0x8`: neighbour x+1 / x−1 | 59 of 59 / 8 | 208 of 208 / 49 |
| direction bits toward a free neighbour (tile not occupied) | 0 | 0 |
| cover location outside position ± (44, 44, 32) | 0 of 644 | 0 of 1,426 |
| single-direction tiles: location offset across the direction | 0 on all 567 | 0 on 1,296 of 1,304 (the rest diagonal) |
| COVER_Diagonal | none | 8 tiles round the UFO; bit ↔ direction as table B says on all 8 |
| peek set and the side tile as read has a floor (same level ± 1) | 797 of 799 | 2,245 of 2,247 |
| visibility bit without pathing bit | 0 of 6,382 | 574 of 20,644 |
| floor / floor pairs with a blocking bit, one-sided | 0 of 116 | 35 of 225 (slopes) |

**Geometric spot-check** (`spot.py`, URB_Bar, the map's own pieces with simple collision, pieces saved with
`bIgnoreForCover` left out): rays for the sweep of step 1 on the 247 single-direction cover tiles that are not
themselves occupied. 213 met a hull; on **209 the baked cover location equals (hull surface − 1 − 40) along d to
0.1 unit** (the other 4 all start on an XComDestructibleActor, off by 34.8). High or low by step 7 (first hit's
`CoverForceFlag`, else a sweep 96 up, pieces forced Low left out) agrees on **199 of 209** (4 high predicted and
low baked, 6 the other way). 34 tiles met no simple hull (per-triangle or streamed pieces).

## 8. What a predictor needs

- **Grid:** `WorldBounds.Min`, NumX/Y/Z.
- **Per actor:** class (XComLevelActor and its children XComDestructibleActor / XComInteractiveLevelActor,
  XComFracLevelActor, XComLadder, PathBlockingVolume, pawns; anything else never blocks or covers, but can be a
  floor), transform, `CollisionType`, `bAlwaysConsiderForCover` (ConsiderForOccupancy), `bIgnoreForCover`,
  `CoverForceFlag`, `CoverIgnoreFlag`, `bUseRigidBodyCollisionForCover`, `bCanClimbOver`, `bCanClimbOnto`,
  `bIsValidDestination`, `VisibilityBlockingData.bBlockUnitVisibility`, `bCanStepUpOn`, `bPathColliding`;
  destructibles: `bIgnoreForPathing`, `Toughness.bFragile`; the volume's +0x1FC bit 0; `XComCoverSeed.bDiagonalCover`.
- **Per mesh:** BodySetup present, its hulls and boxes, `UseSimpleBoxCollision` (every box sweep and the occupancy
  check), `UseSimpleLineCollision` (floor, peek and climb lines), the triangles when a flag is off, bounds
  half-extents (the ≥ 2 rule).
- **Engine traces** (floor, refine, floor under Q, peek floor) go through the octree and meet any blocking
  primitive, not only the classes above.

## 9. Unresolved

1. Exact engine behaviour of a sweep that **starts inside** a hull or crosses per-triangle collision: decides the
   bits of occupied tiles (the one-sided third in section 5). Not read.
2. The 4 spot-check tiles whose first hull is an XComDestructibleActor yet the game's wall point is 34.8 further:
   not explained (the flag was read from the map's own exports only; an archetype in another package may carry
   `bIgnoreForPathing` or `bIgnoreForCover`).
3. The 10 high/low disagreements of the spot-check: likely flags on archetypes in other packages, or per-triangle
   pieces; not followed.
4. Peek and climb (steps 11, 12) and the ramp rule (step 8) are not checked on geometry.
5. `0x100000`: the rule read misses a condition (152 tiles). `0x200000`: read in part. `0x40000`: no writer found.
6. XComInteractiveLevelActor +0x398 bit 5 and its virtual +0x434; PathBlockingVolume +0x1FC bit 0: not named.
7. The occupancy box's +28 is read from the code only.
8. What puts a primitive into the collision octree (so into every query here) was not read.
