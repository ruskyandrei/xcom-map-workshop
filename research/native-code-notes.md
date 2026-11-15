# XComEW.exe native code notes

Findings from reading the game's native code, read-only, on a copy of the exe (`<lab>\re\XComEW-copy.exe`;
never the install's exe, never patched). Started 4 November 2026 for F-29 (EXP-07).

## Tools

| File | What it does |
| --- | --- |
| `tools/re/pe.py` | Small PE helper: sections, address ↔ file offset, string search, absolute and call references, function bounds |
| `tools/re/natives.py` | Maps every script-callable native to its code address (`natives.py <exe copy> <out.tsv>`) |
| `tools/re/dis.sh` | Disassembles an address range with Visual Studio's `dumpbin` (`dis.sh 0x006A68C0 0x006A6A40`) |
| `tools/re/fn.py`, `dfn.sh` | A function's bounds; `dfn.sh <va>` disassembles the whole function |
| `tools/re/refs.py`, `findcls.py`, `gpsc.py` | Callers and references of an address; where a class's `GetPrivateStaticClass` is pushed; which class such a function returns |
| `tools/re/vt.py`, `vtdiff.py` | Virtual table slots; slots where two tables differ |
| `tools/re/clsname.py` | Maps `PrivateStaticClass` pointers to class names (`clsname.py -a dump.txt` annotates a dump) |
| `tools/re/scan214*.py`, `scan1e4.py`, `scanhidden.py`, `scanmask.py` | One-off scans for flag tests at fixed member offsets (cutaway and cursor work) |
| `tools/re/comps.py`, `tools/upk/wdparse.py` | A package export's Components; the world data container's static tile store |

No download was needed: `dumpbin.exe` ships with Visual Studio 2022
(`SDK\ScopeCppSDK\vc15\VC\bin`). The exe is a plain 32-bit image (base `0x400000`, code `0x401000`–`0x13942B9`)
whose code section can be read directly.

**The native map** is `<lab>\re\natives.tsv`: 3,340 natives (class, function, address, table entry).
- UE3 registers each class's natives as pairs of a name string and a function pointer, in `.data`.
- The name is the class and function run together, for example `"UXComWorldDataexecRebuildTileData"`.
- An `exec…` function unpacks the script parameters, then usually makes a virtual call to the real code.

**`UXComWorldData`'s virtual function table** is at `0x1ADA868`. Slots seen so far:

| Slot | Function | Address |
| --- | --- | --- |
| `0x148` | GetTileCoordinatesFromPosition | `0x5D0730` |
| `0x210` | RebuildTileDataExtents (queues tiles) | `0xE6ECB0` |
| `0x21C` | ClearTileBlockedByUnitFlag (likely) | `0xFAB690` |
| `0x220` | SetTileBlockedByUnitFlag | `0x54F0A0` |
| `0x224` | SetTileBlockedByUnitFlagAtLocation | `0xEE18E0` |
| `0x248` | SetIsWaterTile | `0xE12900` |

## World data tile storage

`UXComWorldData+0xD8` points to the native world data. Tiles are kept in two flag stores:

| Store | Offset | Written by |
| --- | --- | --- |
| Static flags | `+0xC0` | the bake and the rebuild; `SetIsWaterTile` sets or clears bit 27 (`0x8000000`) |
| Dynamic flags | `+0x403EC` | `SetTileBlockedByUnitFlagAtLocation` sets bit 1 (`0x2`); `ClearTileBlockedByUnitFlag` clears it |

- Both stores share the get-flags helper `0x745380` and the set-flags helper `0x914FB0`, called as
  `(X, Y, Z, &flags)` with `this` set to the store.
- The static store is split into chunks of 3 × 3 × 2 tiles. The chunk index is `(Z/2)·[+0x20] + (Y/3)·[+0x24] + X/3`
  (strides at store `+0x20` and `+0x24`); the chunk count is at `+0x10` and the chunk pointers at `+0x64`.
- In a chunk, each tile's flag word sits at `+4 + 4·i`, and a "present" byte at `+0x4C + i`. Here
  `i = (X%3) + 3·((Y%3) + 3·(Z%2))`.
- A missing chunk or a zero "present" byte reads as flags 0.
- Logical size, as script sees it: `NumX × NumY × NumZ = NumTiles` (URB_Bar: 52 × 39 × 12 = 24,336). The visibility
  map index is the plain grid index `X + NumX·Y + NumX·NumY·Z`.

## Why runtime geometry doesn't block line of sight (F-29)

`RebuildTileDataExtents` (`0xE6ECB0`) clamps the box to the world, converts it to tiles and loops over X, Y and Z.
It adds a tile to the rebuild work set (native world data `+0x48450`, insert helper `0xBA2850`) **only if the tile's
static flags have a bit in `0xFFF`** (`test al,3Fh` / `test eax,0FC0h`). Empty tiles are never queued, so geometry
added at run time is never seen on them.
- At level 0 every tile has floor flags, so the ground is always re-checked. That's why the copies give cover and
  block movement there.
- Above the ground, only tiles the bake marked (where the map had something) are re-checked. This matches EXP-07
  runs 5 to 10 exactly.
- None of the natives script can call sets those 12 bits. `SetIsWaterTile` uses bit 27 and the unit-blocking natives
  use the dynamic store. Only the bake and the rebuild's own processing write them.
- The work set's consumer is `0x46C700` (about 5.6 KB). Its per-tile step checks static bits `0x2000`, `0x4000` and
  `0x10000`, and calls `0xA0A2B0`, `0xF0D8F0` and `0xE1F390`. The geometry itself is found earlier, in its stage 2:
  see "How the rebuild decides a tile is occupied" below.
- `BuildWorldData` (`0x68FFB0`) crashes when called in the game (EXP-07 run 6).

So a map remix needs those bits seeded in the map's baked data on the tiles its new pieces cross. Then the game's own
rebuild computes them properly, as it already does where the old bar stood.

## How the rebuild decides a tile is occupied (F-80)

Read from the disassembly on 10 November 2026 (static reading of the exe copy, nothing run), after cover blocks gave
no cover in EXP-31. Confidence high for the functions read, unless marked.

> **Corrected on 15 November 2026** by the full read of the cover step ([native/cover-build.md](native/cover-build.md)).
> Where this section and that note differ, the note is right:
> - the occupancy box's centre is 28 above the tile's position, not at it;
> - a tile's position is measured from `WorldBounds.Min`, one unit outside the level volume on every axis;
> - the cover sweep is a box of half-extent (1, 1, 8), and the cover table's E is toward −X, its W toward +X;
> - `0x72A840` is `SingleLineCheck` and does not decide low cover: a second sweep 96 over the floor under the cover
>   point does (a hit there is high cover);
> - the neighbour-height comparisons (under 20, under 32) are the peek's floor test and the climb-over test;
> - the PathBlockingVolume's `0x3F` and `0xFC0` are stale masks: the blocking bits are `0x7E` and `0x1F80`.

- **Stage 2 of the consumer `0x46C700`** calls `0xCF2470(tile, 0, 1)` for each tile, and again `(tile, 1, 0)` when
  the tile got `0x8000`. (`0xF0D8F0` only reads the neighbours' flags; `0xA0A2B0` is the floor-detail step, with
  three line checks of flags `0x860C0` and a test of `bIsValidDestination` at `0xA0ADD7`; `0xE1F390` runs on tiles
  with `0x20000` and tests for XComLevelActor and XComFracLevelActor. The last two: medium confidence.)
- **Occupancy, `0xA58810`**, with a box of half-extent 48 × 48 × 32 at the tile's centre (the second call 20 × 20 × 16,
  16 higher):
  - a PathBlockingVolume overlapping it sets bits `0x3F` (and `0xFC0` with the volume's +0x1FC bit 0);
  - then the actors near it, from the collision hash (`GWorld+0x12C`: the octree, vtable `0x19629D8`; slot +0x18
    `0x6C79B0`, called with radius 76 and its overlap flag 1, so the walk `0x457C60`). It keeps a primitive whose
    **bounding box** (Bounds.Origin ± BoxExtent, prim+0x5C and +0x68) is within the radius of the query point
    (`0x457D06` to `0x457DB5`), one result per actor; the actor's location isn't read, nor any hidden or collision
    flag (only being in the octree counts; what puts a primitive there wasn't read). An actor counts only if it
    implements `XComCoverInterface` and its `ConsiderForOccupancy` is true (for an XComLevelActor
    `bAlwaysConsiderForCover`, +0x1E0 bit 2, true by default);
  - **for an XComLevelActor, its StaticMeshComponent's StaticMesh must have a BodySetup** (`StaticMesh+0xD4`, the test
    at `0xA58D56`), and its bounds' half-extents must all be at least 2 (or the half-extent along X or Y at least 192:
    constants at `0x186910C` and `0x186C1BC`). Otherwise the actor is skipped before any collision test;
  - then the component's `PointCheck` (`0xAD5CB0`, vtable +0x19C) with the box and flags `0x860D3`: a hit sets
    `0x8000` (occupied). Anything found near at all sets `0x20000`.
- **The floor**, when something was near: `MultiLineCheck` (`0x9F2630`) with flags `0x860C0`, a zero extent (the
  global at `0x1C74514` is never written), from 30 above the tile down 64. A hit on an actor without `bPathColliding`
  (+0xAC bit 3) is skipped; a hit with `bCanStepUpOn` (+0xA0 bit 27) and a normal steeper than 0.7 is a floor (`0x2020`,
  `0x6020` below 0.9848); a hit without `bCanStepUpOn` ends the search with no floor.
- **Simple or per-triangle collision.** `0x20000` is `TRACE_ComplexCollision` (both component checks test it; the line
  check also takes `0x100`). Neither `0x860C0` nor `0x860D3` has it, so a static mesh uses its simple collision when
  `UseSimpleBoxCollision` (+0x10C, box checks) or `UseSimpleLineCollision` (+0x110, line checks) is on, and with a
  null BodySetup that path returns no hit, with no fallback to the triangles. Only with both flags off do the checks
  use the triangles; and the occupancy test above still wants the BodySetup.
- **Hidden actors.** Nothing read on this path tests `bHidden` (+0xA0 bit 9), a component's `HiddenGame` (+0x13C),
  `CoverForceFlag` (+0x1F8) or `bIgnoreForCover`, the octree walk included; EXP-31 run 3 confirms it in the game:
  hidden cover blocks block and give cover.
- **Where a tile's floor and cover are looked for (F-82).** Read on 10 November 2026 after an invisible floor gave
  the tile below it half cover (EXP-32 run 1).
  - A tile's position (world data vtable `0x1ADA868`, slot 0x158, `0xD5B5E0`) is its centre, 32 over the bottom of
    its level: (ox + 96X + 48, oy + 96Y + 48, oz + 64Z + 32), the origin read from `UXComWorldData+0x48`. So the floor
    trace above is one line through the tile's centre, from 62 over the level's bottom to 2 under it (high
    confidence).
  - The floor-detail step `0xA0A2B0` looks for cover in four directions (table `0x1C1B050`, 0x54 bytes each: N +Y,
    S −Y, E, W; which directions it tests comes from `0xF0D8F0`, not decoded; the E and W vectors set up at
    `0x1372580` look swapped, unresolved). Its trace (`0xC6E980`, then `0x619670`, flags `0x860D3`) starts 52 over
    the tile's floor hit and runs 124 units sideways at that height, so it reaches 28 past the neighbour's centre.
    Whether it sweeps a box is unresolved (the caller passes 32, 16, 16; the helper builds 1, 1, 8).
  - A hit on an actor that implements `XComCoverInterface` and whose `ShouldIgnoreForCover` is false (for an
    XComLevelActor `bIgnoreForCover`, +0x1E0 bit 6; `0xA0A849` to `0xA0A868`) gives cover that way, high by default.
    It is low (half) cover when the actor's `CoverForceFlag` is Low (`0xA0AFC6`) or a follow-up line check (`0x72A840`,
    flags `0x860C0`, endpoints not read) finds a top that is a valid destination (`bIsValidDestination`, +0x1E0 bit 5,
    `0xA0ADD7`; low set at `0xA0AE04`). `CoverIgnoreFlag` then filters it (`0xA0B05B` to `0xA0B12C`). Pawns are left
    out (`0xA0BBCD`).
  - Bits: the store at +0x8130 gets cover N 0x1, S 0x2, E 0x4, W 0x8 and low cover N 0x10 to W 0x80 (`0xA0BD0D`); the
    static flags get N 0x10, S 0x8, E 0x2, W 0x4 (`0xA0BC8B`). Comparisons with a neighbour's floor height (under 20
    at `0xA0B6D5`, under 32 at `0xA0BB4E`) set other bits whose meaning wasn't found.
  - Medium confidence for this step, except where marked. The game's own hidden ladder helpers save
    `bIgnoreForCover` True (URB_Bar's `XComLadder` actors in EXP-01's property dump).
- **Sloped floors get no cover (F-81).** The floor-detail step `0xA0A2B0` runs only on tiles with `0x2000` and without
  `0x4000` (the floor trace sets `0x4000` where the floor's normal is steeper than 0.9848, about 10°). The baked data
  agrees: on CSmallScout_Farm 23 of 680 sloped floor tiles have direction bits (all at level 0, themselves occupied,
  by the map's edge), against 1,444 of 4,102 flat ones; CLrgScout_ForestTrench 36 of 676 against 1,893 of 7,291. No
  sloped tile where units walk on the farm's ramps has any.
- Actor bit positions used here (from XEW Engine.upk's export order, anchored by `SetHidden` `0x57D9D0` and
  `SetCollision` `0x407440`): +0xA0 bit 9 `bHidden`, bit 17 `bWorldGeometry`, bit 27 `bCanStepUpOn`; +0xA8 bit 7
  `bCollideActors`, bit 10 `bBlockActors`; +0xAC bit 3 `bPathColliding`; +0x9D the `CollisionType` byte (1 is no
  collision).

## How a destroyed prop loses its collision and cover (F-101)

Read on 13 November 2026 for the cover blocks that break with their group.
- A prop's damage states are script states (`_Pristine`, `_Damaged`, `_Destroyed`, `Dead`). `_Destroyed` runs the
  prop's `DestroyedEvents`; with none it keeps its mesh and collision.
- `XComDestructibleActor_Action_Hide.Activate` (the class's vtable `0x1AB2E18`, slot 0x130, `0x99EF00`): marks the
  action activated, calls the actor's `SetStaticMesh` with no mesh (the actor's vtable `0x1ABA2B0`, slot 0x3E4), then
  `GotoState('Dead')` (slot 0x124).
- The actor's `SetStaticMesh` (`0xAD86E0`): keeps the component's old bounds, sets the component's mesh (the
  component's slot 0x2C8), and with no mesh calls `DisableCollision` (slot 0x3DC, `0x460E80`). Then, if there is
  world data (`0x922BF0`), it calls its slot 0x210 with the bounds (the old ones when the mesh is gone) widened by
  the constants at `0x1C1BF68`: taken as the tile rebuild over that box (medium confidence; not followed).
- `SyncChildStates` (slot 0x3FC, `0xABC400`) moves each of `AffectedChildren` by `GotoState`, not through
  `ApplyDamageToMe`: a child whose toughness is `bInvincible` still follows its parent.

## Static flag bits seen so far

The whole table as read on 15 November 2026 ([native/cover-build.md](native/cover-build.md), sections 5 and 6, with
each bit's confidence):

| Bit | Meaning | Source |
| --- | --- | --- |
| `0x1` | nothing: set only on PathBlockingVolume tiles, by the stale mask `0x3F` | `0xCF2B25` |
| `0x2`, `0x4`, `0x8`, `0x10`, `0x20`, `0x40` | **pathing blocked** toward −X, +X, −Y, +Y, down, up | `0xE1F390` |
| `0x80`, `0x100`, `0x200`, `0x400`, `0x800`, `0x1000` | **sight blocked** toward −X, +X, −Y, +Y, down, up | `0xE1F390`; read back by the sight ray walk `0xFA9870` |
| `0x2000`, `0x4000` | floor; sloped floor (normal z under 0.9848) | `0xCF28DC` |
| `0x8000` | occupied (`IsTileOccupied`) | `0xB13330`, `0xCF2AFD` |
| `0x8000` set, `0x10000` clear | fully occupied (`IsTileFullyOccupied`); with `0x10000` the upper middle of the tile is free | `0x4C3120`, `0xCF2B0B` |
| `0x20000` | something in the collision octree within 76 of the tile's position; the blocking step runs only on these | `0xCF2B17` |
| `0x80000` | one or two levels above a floor tile | `0xD57FC7` |
| `0x100000`, `0x200000` | 2 × 2 standing room; a drop of two levels or more beside the tile (both medium confidence) | `0x905C56`, `0xD8F7BB` |
| `0x400000` | the floor's actor is a valid destination | `0xCF2945` |
| `0x800000` to `0x4000000` | the +X, −X, +Y, −Y neighbour is outside the level volume (the full build only) | `0x9F8680` |
| `0x8000000` | water (`SetIsWaterTile`) | `0xE12900` |

The script's constants `WORLD_PATHING_ANY_DIR_BLOCKED` (`0x3F`) and `WORLD_VIS_ANY_DIR_BLOCKED` (`0xFC0`), the
rebuild's queue test (`0xE6ECB0`, any bit of `0xFFF`) and the PathBlockingVolume branch use masks one bit lower
than the bits the code writes. So a tile whose only blocking bit is `0x1000` (sight blocked upward) is not queued,
and `0x1` is free: it queues a tile and means nothing, which is what `seed_tiles.py`'s default seed relies on.

Examples from URB_Bar's baked data:

| Tile | Flags |
| --- | --- |
| empty air at level 1 | `0x000A0000` |
| next to a wall at level 1 | `0x000B8008`, `0x000B8208` |
| ground tile | `0x00522820`, `0x00422C30` |

## How the static store is saved in the map (`XComWorldDataContainer`)

URB_Bar's container (`TheWorld.PersistentLevel.XComLevelVolume_4.XComWorldData_0.XComWorldDataContainer_14`) is
882,780 bytes and is compressed chunk 25, the last one in `URB_Bar.upk`. Its native data starts with the static store:

| Field | URB_Bar |
| --- | --- |
| 12 bytes of property header | |
| u32 chunk count | 1,404 (18 × 13 × 6 chunks of 3 × 3 × 2 tiles) |
| TArray<int> chunk order | 1,404 entries, a permutation of 0..1403 |
| i32 NumX, NumY, NumZ | 52, 39, 12 |

Then, for each chunk: u32 sequence number, u32 tile count (18, or 6 at the x = 51 edge), i32 X, Y, Z (the chunk's
tile origin), u32 18, then 18 × (u32 flags, u8 present). The tile order is `i = (X%3) + 3·((Y%3) + 3·(Z%2))`, as in the
code. In URB_Bar all 24,336 tiles are present, and the store ends at byte 165,704 of the blob. Another store follows.

The decoded flags match the run logs exactly: every see-through tile in EXP-07 runs 5 to 10 has low 12 bits 0, and
every blocking one has some.

`tools/upk/seed_tiles.py` writes a copy of a map with a seed bit (default `0x1`) set on chosen tiles whose low 12 bits
are 0. It re-encodes only the changed blocks, as literal LZO1X runs, so all uncompressed offsets stay put. It updates
the chunk's compressed size in the chunk table, then decodes the written file and compares it byte for byte. The
game's rebuild then recomputes the seeded tiles from the geometry. The hidden bar's tiles show this: their baked bits
are cleared by the rebuild once the bar is hidden.

## The rest of the container: pathing links

After the static store come eight more chunked stores and two u32 fields, to the exact end of the blob. In URB_Bar:

| Store | Offset | Chunks saved | Element per tile (then u8 present) |
| --- | --- | --- | --- |
| 2 | 165,704 | 205 | u32, likely CoverFlags |
| 3 | 189,914 | 304 | FloorTileData (below) |
| 4 | 825,888 | 205 (the same list as store 2) | FVector, the cover location |
| 5 | 879,618 | 13 | TArray<XComInteractPoint>, 40 bytes each: FVector, three i32 (a rotation, order unverified), i32 InteractiveActor, FName socket, i32 ModifyTileStaticFlags |
| 6 to 8 | 882,692 | 0 | unknown, likely fire, smoke and poison |
| | 882,752 | | u32 0, u32 0 |
| 9 | 882,760 | 0 | unknown; ends at 882,780 |

- Every store: u32 chunk count (1,404), TArray<i32> of the chunk indices saved (in another order), i32 NumX, NumY,
  NumZ. Then, for each saved chunk in ascending index: u32 index, u32 present count, i32 X, Y, Z, u32 18 and
  18 × (element, u8 present). Store 1 is the same with every chunk saved.
- Absent tiles hold leftover bytes, but always an empty list.
- The 12-byte header is the NetIndex (7,576) and the FName None.

**Floor element:** FVector FloorLocation, FVector FloorNormal, TArray<PathingTraversalData> Neighbors,
u8 RampDirection, i32 FloorActor, i32 FloorVolume (export indices).
- A neighbour record is i32 TileX, TileY, TileZ, f32 cost (1.0 or 1.414), i32 PathObject, TArray<u8> TraversalTypes
  and TArray<FVector> Positions.
- URB_Bar has 2,495 floor tiles and 14,584 links. 48 links have a path object: doors (KickDoor, Landing), low walls
  (ClimbOver, Landing) and the two ladders (ClimbLadder, Landing), one link each way.
- `XComLadder_3` (export 13740): (11, 23, 0) → (12, 23, 6) through (−1696, 336, 24) and (−1604, 336, 402); back
  through (−1604, 336, 500.9) and (−1696, 336, 24). `XComLadder_4` (13741): (33, 33, 0) ↔ (33, 32, 6).

**In memory**, from the code:
- The floor store is at native world data `+0x10194` (chunk pointers at `+0x101F8`).
- Its elements are `0x30` bytes (Neighbors at `+0x20`, RampDirection at `+0x2C`), with present bytes at chunk
  `+0x364`.
- PathingTraversalData is `0x2C` bytes (PathObject at `+0x10`, TraversalTypes at `+0x14`, Positions at `+0x20`).

**Does the runtime rebuild keep path-object links?** It drops them and makes ladder links anew, for every ladder
whose foot and top tiles have a floor (see "How ladder links are made" below). The guess from EXP-07 run 17, that
only the patch level's ladders count, was wrong.
- From the code: in the rebuild consumer's Neighbors step (step 5, `0x46D78F`), each tile of the work set goes
  through `0x905780`. If the tile's static flags have bit `0x2000`, it copies the floor tile and empties its
  Neighbors (`0x5952A0`, TArray::Empty), writes the tile back (`0xC46790`) and adds plain links only (PathObject 0,
  no types or positions). `0x777580` then replaces the tile's DropDown link. Nothing seen re-adds ladder, door or
  wall links.
- In the game (EXP-07 run 13): `XComLadder_4`'s links at (33, 33, 0), a tile with bit `0x2000` inside the hider's
  rebuild box, survived, and the hidden ladder could still be climbed. So something keeps or re-adds them, or that
  reading misses a branch.
- Run 15 moved `XComLadder_3`'s links to (34, 20, 0) ↔ (34, 21, 6), inside the copier's and the seeds' rebuild
  boxes, and the ladder still couldn't be climbed.
- Run 16 probed A* paths at load and 5 s later. The moved links gave a 1-tile climb at load and no path after the
  rebuild; the hidden `XComLadder_4`'s gave a 1-tile climb both times. So the reading above holds for links in the
  baked data, and something re-adds ladder links from where the ladders stood at load (not found in the code yet).
  Run 17 tests baking the ladder's new place into the map instead (`tools/upk/bake_actor.py`).
- Run 17: the baked ladder (standing in its new place from load) lost its links the same way. The north climb was
  re-made by `patch_bar`'s hidden `XComLadder_15`, which the hider had hidden and made non-colliding. So the ladder
  step finds its ladders without collision, by a list or an actor iterator; which ladders it takes (the patch
  level's, or those tagged `XComLadder`) is still open.

`tools/upk/world_links.py` lists the links and moves one path object's links (turned and moved like a copy, or given
explicitly), keeping the container's size.

If the container ever had to grow (for example a link on a tile in an unsaved chunk), these would change:
- in the blob: the store's chunk list (count and new index), the new chunk record in index order, and its present
  count;
- in the package: the container export's SerialSize, which sits in the export table inside compressed chunk 0. So
  chunk 0 is re-encoded, and every later chunk's compressed offset in the chunk table shifts.
- Also the container chunk's table entry (both sizes) and its own header (totals and block list).
- The container is the last export and the last chunk, so no export offsets move.

## How ladder links are made

Read from the native code on 4 November 2026 (static reading of an exe copy; the agent's full notes and dumps are in
the lab folder `re\ladder\`; the write-up is now [native/ladder-links.md](native/ladder-links.md)). Checked against URB_Bar's baked ladder links, which it reproduces
exactly.

- **One function makes every ladder link: `0x777580`** (the "DropDown" step named above). Both the editor's full
  build and the runtime rebuild call it:
  - full build (`BuildWorldData`, vtable slot `0x144` = `0x988D40`): once, for all ladders, after every tile's
    Neighbors are built;
  - runtime rebuild (consumer `0x46C700`, step 5, `0x46D99E`): once per tile of the work set, right after
    `0x905780` rebuilds that tile's Neighbors, and only for ladders whose **foot** tile is that tile.
- **Ladders are found with `TActorIterator<AXComLadder>`** (`0x8329A0`): every actor of every level in the world (the
  base map, `patch_bar`, our patch), filtered by `IsA(XComLadder)` and not pending kill. Nothing else is checked: not
  bHidden, collision, bStatic, Tag, eType, the level or the rebuild box. XComWorldData keeps no ladder list.
- **The two points**, with `fwd` the ladder's rotated local X and `h = GetHeight()` (the mesh's bounds height,
  476.9 for `LadderMetalA_448`):
  - top `T = Location + 76·fwd + (0, 0, h + 8)`;
  - foot `B = Location − 16·fwd + (0, 0, 8)`.
- **Conditions:** tile(T), or the tile below it, needs static flag `0x2000` (floor; what `IsPositionOnFloor`
  returns), and tile(B) needs `0x2000` itself. Nothing is checked for blocking.
- **The links:** [ClimbLadder, Landing] both ways, path object the ladder.
  - The down link is stored on the top tile, whose DropDown links are removed.
  - The up link is appended to the foot tile; it ends at the top tile's floor height.
- **Order matters at run time.** If the top tile is rebuilt after the foot tile, its Neighbors are emptied again and
  the down link is lost (medium confidence). Rebuilding just the foot tile last makes both links again.

What this explains in EXP-07: a ladder moved by script or by bake gets no climb when its top tile has no floor after
the rebuild (run 19: the new top tile (34, 21, 6) lost its floor). `patch_bar`'s hidden `XComLadder_15` keeps the
north climb because its top tile keeps its floor.

## How the building cutaway works

Read from the decompiled scripts and the native code on 4 November 2026 (the agent's full notes and dumps are in the
lab folder `re\cutaway\`; the write-up is now [native/building-cutaway.md](native/building-cutaway.md)).

- **The chain.** A pawn touching or leaving a floor volume runs `XComPawnIndoorOutdoorInfo.CheckForFloorVolumeEvents`.
  It sets `CurrentBuildingVolume` and the floor numbers from the volumes' `CachedBuildingVolume` and `FloorNumber`, and
  calls `XGLevel.OnActorUpdateBuildingVisibility` (also through `XComTacticalGRI.NotifyOfEvent` events 0 and 3).
  - In mouse mode it loops over all `XComBuildingVolume`s (AllActors) and calls `ShowFloor(k)` from the cursor's
    cutdown height, using `Floors[i].fCenterZ` and `fExtent` (`CacheFloorCenterAndExtent`).
  - Otherwise it calls `ShowFloor` on the pawn's building with its lowest floor number, or `HideFloors` when nobody
    is inside. `m_bAllowBuildingReveal` must be set (default true).
- **`ShowFloor(n)`** (`0x5FAAA0`, worker `0x10C72D0`) uses only `Floors[i].m_aCachedActors`. It hides the floors above
  n and cuts down the entries whose `CutdownFloor` is above n. It returns early when n is the floor last shown, so
  after changing the caches while a floor is shown, `HideFloors_ScriptDebug(false)` resets it.
- **Each piece changes only through its own `XComFloorComponent`**, which acts only when attached (in the actor's
  `Components`, so it has an Owner). It hides or cuts the actor's main mesh. No per-actor material parameters are
  set.
- **Cutting down and the camera cut-out** also need `bCutoutMask` on that main mesh component (the bar's placed
  pieces have it saved as true). Hiding whole floors doesn't.
- **`RebuildCachedActors`** empties the caches and takes only actors that touch the floor volumes and share their
  level package, which is why it found none of our script-spawned copies (they are in the persistent level).
- `XGLevel.m_arrBuildings` is only used by the AI, the layout and `HideAllFloors`.
- The stubs' trap: a decompiled reference such as `FloorComponent=XComFloorComponent'Default__X.FloorComponent0'`
  without a `begin object` resolves to None, and a subclass's compiled `Components` array (with None in it)
  replaces the game parent's at load. Declare inherited subobjects in the stubs, and check compiled defaults
  (`Components`) of new subclasses.

## How the mouse cursor picks a tile

Read on 4 November 2026 (notes in the lab folder `re\cutaway\cursor\`; now
[native/mouse-cursor.md](native/mouse-cursor.md)).

- The mouse cursor doesn't trace itself; `XCom3DCursor.PerformTrace` serves the pad cursor.
- `XComTacticalHUD.GetMousePickActor` runs `TraceActors` (`0x8A5730`) along the mouse ray. It filters nothing for
  hidden or cut meshes, so cut-away roofs are still hit. (Only `Helpers.isVisibilityBlocked`, for line of sight,
  respects the cutaway.)
- The script skips hits on pieces with `bIgnoreFor3DCursorCollision`, steep wall faces and points outside the level.
- A walkable hit outside every building volume in `XComTacticalHUD.m_arrBuildingVolumes` wins at once. Otherwise a
  lower hit replaces a higher one while the higher one is above the requested floor.
- `XComTacticalHUD` and `XCom3DCursor` fill their `m_arrBuildingVolumes` once, in `PostBeginPlay`, with AllActors.
- `bCutoutMask` (needed to cut walls down) has no script setter; the only native write is at component load. Routes:
  write it into a copy class's compiled defaults, or spawn copies from a template that carries it.

## Cover and line of sight (F-111)

Read on 15 November 2026 by two agents; the dumps and scripts are in the lab folders `re\cover\` and `re\sight\`.
The write-ups are [native/cover-build.md](native/cover-build.md) and
[native/line-of-sight.md](native/line-of-sight.md); [native/cover-and-sight.md](native/cover-and-sight.md) is the
summary, with the checks and the open points.

- **Per-tile order**, the same in the full build (`0x988D40`) and the rebuild consumer (`0x46C700`): occupancy and
  floor `0xCF2470` (→ `0xA58810`); standing room `0xD57E90`; directions to try `0xF0D8F0`; cover `0xA0A2B0`;
  blocking bits `0xE1F390`; interact points `0x7E8E30`; neighbours `0x905780`; ladders `0x777580`. Build only:
  diagonal cover seeds `0xE4B630` and the edge bits `0x9F8680`. The rebuild clears a queued tile first (`0x8670E0`).
- **The world trace `0x619670`** takes a check type: 1 cover, 2 cover with ladders, interactive pieces and sturdy
  props, 3 pathing, 4 sight (`bBlockUnitVisibility`). It only ever tests XComLevelActor and its children,
  XComFracLevelActor, pawns and PathBlockingVolumes, with flags `0x860D3` (simple collision). `0xC6E980` is its box
  sweep; `0x72A840` is the engine's `SingleLineCheck`.
- **The cover tables** are `0x1C1B050` (straight) and `0x1C1B1A0` (diagonal), four entries of 0x54 bytes: the cover,
  low, peek, climb and static bits, the direction, the peek-right direction, the test length.
- **Sight**: `CanSeeActorToActor` is `0x895090` (slot 0x1D0), its one-source test `0x8626D0`; a viewer's tile map
  is made by the octant solver `0xEC4620` and the ray walk `0xFA9870` and kept per viewer at native world data
  +0x8124; `CacheVisibilityDataForTile` `0x6E5E00`; `CheckTargetSquadsight` `0x75A580`; `IsAdjacentTileVisible`
  `0x54BB20` (worker `0xC66A90`).
- **Flanking**: `IsFlankedBy` `0x104F610` → `0x102DCB0`; `DoesFlankCover` `0xAF0B40`; `DoesFlank` `0xD256D0`;
  `UpdateCoverBonuses` `0xD8CB30`; `HasHeightAdvantageOver` `0x6B00B0`. The unit class's virtual table is
  `0x1AEC218`.

## The map's record (F-105)

Read on 14 November 2026 for the mission types plan; the dumps are in
`<lab>\re\scratch-mapmanager\`. Addresses are the real functions, not the script thunks.

- **The stored record** is one static `XComMapMetaData` at `0x1D42558` (0x58 bytes). `SetCurrentMapMetaData`
  (`0x6B06C0`) only copies into it. Besides the script thunk, `GetMapCommandLine` and the checkpoint serializer
  (`0x722B10`: saves the display name, and on load looks it up and stores the record) write it.
- **`GetCurrentMapMetaData`** (`0xBE4900`) returns the stored record when its `DisplayName` is not empty (the
  test at `0xBE4927`). Otherwise it takes the loaded map's name and calls `GetMapInfosFromMapName` (`0xCD47A0`): a
  case-insensitive compare on `Name` over the `Maps` array in order, no test of `MissionType` or `bInRotation`.
  It takes element 0 and stores it. No URL option is read.
- **`GetMapCommandLine`** (`0xF9EB80`) finds the record with `GetMapInfoFromDisplayName` (`0x523D90`: the first
  record whose `DisplayName` matches, case-insensitive), builds `"%s %s?game=XComGame.XComTacticalGame"`
  (`servertravel` when seamless, else `open`) and stores the record (the call at `0xF9ECF2`), even when the lookup
  found none. Then, in order: `?LoadingFromStrategy=1` or `?LoadingFromShell=1`; `?Meld=1` when there is no
  description or its script event `ShouldSpawnMeldCanisters()` is true; `?CapturePoints=1` when there is no
  description or `[desc+0x288]` is 6; `?RadarArrays=1` when it is 5 or 6 (`+0x288` is taken to be
  `m_iMissionType`); `?StreamingMap%d=%s` for each of the record's streams after the script event
  `GetRequiredGlamCamMaps` has added its cinematics.
- **Who reads the options.** The map content loader (`0xFD3840`) tests only whether `Meld`, `CapturePoints` and
  `RadarArrays` are there, and adds the `[Content.MapContent]` packages for `$MELD`, `$CAPTUREPOINTS` and
  `$RADARARRAYS`. `StreamingMap<n>` is read by seamless travel's `StartLoadingDestination` (`0xFAFF60`, a preload
  only) and by `AddStreamingMapsFromURL`, which the script calls only when the URL has `LoadingSave`.
- **`AddStreamingMaps`** (plain body `0x64B920`, behind a CEG stub) looks the record up by display name and adds
  each stream with its place and rotation; **`AddStreamingMapsFromURL`** (`0x4C5740`) adds `StreamingMap0` to
  `StreamingMap39` at the origin. With `bAllowDropshipIntro` false both skip names with `CIN_DropshipIntros` or
  `CIN_FastropeIntros` (but not `CIN_DROPSHIPINTROS_INTRO` itself) and `CIN_TP12A_ARRIVETEMPLESHIP`.
- Not proven: which plain body belongs to which CEG stub (matched by signature and strings); that the `Maps`
  array keeps the file's order.

## Open

- Done: the game loads the re-encoded package, and the rebuild registers geometry on seeded tiles (EXP-07 run 11).
- Done on 15 November 2026: what each of the low bits means (the table above).
- The open points of the cover and sight reads are listed in [native/cover-and-sight.md](native/cover-and-sight.md).
