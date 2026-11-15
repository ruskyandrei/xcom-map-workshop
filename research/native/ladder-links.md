# How XComWorldData makes ladder links (XComEW.exe, read-only)

> Copied into the repo on 4 November 2026 from the lab folder `<lab>\re\ladder`. The helper scripts it names are now in
> `tools/re/`; the disassembly dumps (`*.txt`) stay in the lab, since they are decoded game code.

4 November 2026. Static reading of `<lab>\re\XComEW-copy.exe`. Nothing was run or patched.
Disassembly dumps are in this folder (`dis_*.txt`). `clsname.py` maps `PrivateStaticClass` pointers to class names
(`python clsname.py -a dump.txt` annotates a dump).

## Summary

- **One function makes every ladder link: `0x777580`.** The notes called it "DropDown". It is a
  `UXComWorldData` thiscall taking `const TTile*`. Both the full build and the runtime rebuild call it:
  - full build: `UXComWorldData` vtable slot `0x144` = `0x988D40`, reached from `execBuildWorldData` `0x68FFB0`;
  - runtime rebuild: consumer `0x46C700`, step 5, at `0x46D99E`.
- **It finds ladders with an actor iterator, `TActorIterator<AXComLadder>`** (`operator++` = `0x8329A0`).
  - The iterator walks every actor of every level in `GWorld->Levels`: the persistent map and every streamed level
    that has been added to the world.
  - It keeps `IsA(XComLadder)` actors (subclasses too) and skips objects with ObjectFlags bit `0x2_00000000`,
    most likely RF_PendingKill.
  - It does **not** check bHidden, collision, bStatic, Tag, eType, Outer/level or the rebuild box. There is no
    ladder list.
- **Tiles:** with `fwd` = the ladder's rotated local X axis and `h` = `GetHeight()`:
  - top point `T = Location + 76·fwd + (0,0,h+8)`;
  - bottom point `B = Location − 16·fwd + (0,0,8)`.
- **Conditions:**
  - The top tile needs static flag `0x2000` (floor), either in tile(T) or in the tile below it (Z−1, only when
    Z−1 ≥ 1).
  - The bottom tile, tile(B), needs `0x2000` itself. There is no fallback for the bottom.
  - Nothing is checked for blocking.
- **Runtime versus bake:**
  - The bake calls the function once, with tile (−1,−1,−1) meaning "all ladders", after every tile's Neighbors are
    built.
  - The runtime rebuild calls it once for every tile in its work set, right after `0x905780` rebuilds that tile's
    Neighbors. It handles **only ladders whose bottom tile is that tile**.

## Addresses

| What | Address |
| --- | --- |
| `AXComLadder` StaticClass pointer | `0x1D422C4` (GetPrivateStaticClass `0xF515C0`, init `0xB22C30`) |
| `AXComLadder` vtable | `0x1AC6BA0` (InternalConstructor `0xF11430`) |
| `GetHeight` (vtable slot `0x3DC`) | `0xBD6AB0`; exec stub `0x977470` |
| Bounds helper used by GetHeight | `0x104E4D0`: component `[ladder+0x208]` Bounds (Origin `+0x5C`, Extent `+0x68`) united with Location `[+0x54]` |
| Local top point `(0,0,h)` / world if arg | `0xC3ADD0(out, bWorld)` |
| Local origin `(0,0,0)` / world Location if arg | `0x5FB270(out, bWorld)` |
| LocalToWorld from Location `+0x54`, Rotation `+0x60`, DrawScale `+0x6C`, DrawScale3D `+0x70` | `0xB3ACC0` |
| `TActorIterator<AXComLadder>::operator++` | `0x8329A0` |
| **Ladder link builder** | **`0x777580`** (to `0x77832E`) |
| Full build (BuildWorldData, vtable `0x144`) | `0x988D40`; ladder call at `0x98A415` with (−1,−1,−1) (`or esi,-1` at `0x98A217`) |
| Runtime consumer step 5 per tile | `0x46D965` → `0x905780(tile)`, then `0x46D99E` → `0x777580(tile)` |
| IsPositionOnFloor implementation (vtable `0x16C`) | `0x56E7B0`: returns `staticflags(tile(pos)) & 0x2000` |
| Static floats | `(76,0,8)` at `0x1D42DA0` (from `0x186A008`, `0x186C780`); `(−16,0,8)` at `0x1D42D94` (`0x18722D8`) |

Other `XComLadder` class users, not needed here:
- `0x6855F0` and `0x9BA250`: trace-hit filters inside the world-data trace `0x619670`. `0x9BA250` rejects ladders;
  `0x6855F0` accepts them.
- `0xA58810`: a similar trace filter.
- `0xBD6D40`: `Cast<AXComLadder>`.
- `0x848950`: a vtable entry at `0x1AEC850`; not read.

## Pseudo-C of `0x777580`

The lab copy has a pseudo-C reconstruction of the function. It is left out here, since it is
decoded game code; the summary above and the answers below say what it does.

**Checked against the bake (high confidence).** URB_Bar's baked XComLadder_4 links are
`(432,1312,24)→(432,1220,402)` (up) and `(432,1220,500.872)→(432,1312,24)` (down). XComLadder_3 has the same
pattern along X. They match the code exactly:
- Location ≈ (432, 1296, 16), yaw −90°, so fwd = −Y;
- h = 476.872;
- the top point at z 500.9 falls in tile Z 7, which has no floor, so the code steps down to Z 6;
- the up link lands at the top tile's FloorLocation.Z, 402.

So the bake used this same function.

## Answers

### 1. How ladders are found (high confidence)

`TActorIterator<AXComLadder>` (`0x8329A0`):
- It walks `GWorld->Levels` (`[GWorld+0x44]` data, `+0x48` count) and each level's `Actors` (`[level+0x3C]`,
  `+0x40`).
- In levels other than `[GWorld+0x50]` it starts at actor index 1 (it skips each sublevel's first actor).
- It filters with `IsA(AXComLadder)` (class chain at `+0x34`/`+0x48`) and `!(ObjectFlags & 0x2_00000000)`.

So every ladder in the base map, `patch_bar` and our patch level is visited, as long as its level is in the world.
XComWorldData keeps no ladder list.

### 2. What a ladder must meet (high confidence)

Only the tile tests below. Not checked: bHidden, bCollideActors/SetCollision, bStatic, Tag, eType, which level it is in,
and whether it lies inside the rebuild box.
- In the runtime rebuild, the ladder's **bottom tile must be a tile of the work set**.
- That tile must sit at level 0 or carry one of the low 12 bits (those bits are what queue a tile).

Pending-kill (destroyed) ladders are skipped.

### 3. Top and bottom tiles (high confidence)

`h = GetHeight()`, which is `max(Bounds.Max.Z, Loc.Z) − min(Bounds.Min.Z, Loc.Z)` of the component at `+0x208`.
Points are local offsets put through LocalToWorld:

| Point | Formula |
| --- | --- |
| Top | `Location + 76·fwd + (0,0,h+8)` |
| Bottom | `Location − 16·fwd + (0,0,8)` |

The script's ±52 in GetPath is used only for the unit's movement, not here.

Requirements, all on **static flag `0x2000`**, which is what `IsPositionOnFloor` returns:
- **Top:** tile(Top) has `0x2000`, or, if not, the tile one below has it (only when that tile's Z is at least 1). The
  link then targets the lower tile.
- **Bottom:** tile(Bottom) has `0x2000`.

Nothing is checked for blocking, cover or line of sight.

Both links have cost 1.0 and the types `[ClimbLadder, Landing]`. Adding the down link removes every DropDown link on
the top tile.

### 4. Bake versus runtime (high confidence on the code, medium on the effect)

| | Full build (`0x988D40`, BuildWorldData) | Runtime rebuild (step 5 of `0x46C700`) |
| --- | --- | --- |
| How it calls the builder | once, `(−1,−1,−1)` = all ladders | once per tile in the work set, with that tile |
| When | after the Neighbors of every tile are built | right after `0x905780` rebuilds that tile's Neighbors |
| Which ladders | all | only those whose bottom tile is that tile |

Consequences at runtime:
- **Ladders are relinked only when their bottom tile is rebuilt.** A ladder whose top tile is rebuilt but whose
  bottom tile isn't loses its down link for good.
- **Order hazard.** The work set is filled X outer, Y middle, Z inner (`0xE6ECB0`). If the top tile comes later in
  the work set than the bottom tile, `0x905780` empties the top tile's Neighbors afterwards, and the down link
  (top → bottom) is lost. The up link survives.
  - XComLadder_15: the top tile (33,32,6) has a smaller Y than the bottom tile (33,33,0), so the top is processed
    first and both links survive.
  - At the new place, the bottom (34,20,0) comes before the top (34,21,6), so the down link would be lost. The up
    link would not.
  - Medium confidence: this assumes the TSet keeps insertion order.

## The runs, read against this

| Run | Result | Explained? |
| --- | --- | --- |
| 13 | Links at (33,33,0) survive | Yes. They are rebuilt by XComLadder_4 itself and by `patch_bar`'s XComLadder_15, whose bottom tile is (33,33,0) and is in the work set. |
| 15/16 | Moved links at (34,20,0) are wiped and nothing remakes them | Yes. `0x905780` empties them, and no ladder has its bottom tile at (34,20,0). |
| 17 | North climb is remade by the hidden, non-colliding XComLadder_15 | Yes. Hidden and collision are not checked, and its own tiles give (33,33,0) ↔ (33,32,6) exactly. |
| 17/18 | XComLadder_4 at (528,48,16) yaw +90 and XComLadder_905 at (524,68,14) yaw +90 get no climb | See below. |

For the last row, both ladders give the bottom tile (34,20,0) and a top point at z ≈ 500, in tile (34,21,7), which
steps down to (34,21,6). Both ladders are visited, and the bottom tile is processed: its baked link was wiped, which
shows that. So the only test left that can fail is a floor test:
- most likely **no `0x2000` on (34,21,7) or (34,21,6) after the rebuild**, meaning the copied roof gives no floor
  there;
- or, less likely, no `0x2000` on (34,20,0).

Run 18 changed the ladder and nothing changed, which fits a cause in the tiles, not in the ladder. This is an
inference: the flags at the new place were not read.

## What is left

- Not checked: why the rebuild does or doesn't give the copied roof a floor bit. The leads are:
  - the floor and trace steps `0xA0A2B0`, `0xF0D8F0` and `0xE1F390`;
  - the world-data trace `0x619670`, which has a switch on trace type and class filters for XComCoverInterface,
    XComInteractiveLevelActor, XComDestructibleActor and XComLadder;
  - the trace filter `0xA58810`, which checks XComLevelActor, XComFracLevelActor and XComPawn.
- What the byte at Actor `+0x9D` means. When it equals 1, both trace filters ignore the actor. Not identified.
- `0x848950` was not read.

## Recommendation

1. **Probe the exact native conditions** after `IsRebuildingTiles()` turns false. Use the ladder's own numbers:
   `fwd = vector(Rotation)`, `T = Location + 76*fwd + vect(0,0,8) + vect(0,0,1)*GetHeight()`,
   `B = Location - 16*fwd + vect(0,0,8)`.
   - Log `IsPositionOnFloor(T)`, `IsPositionOnFloor(T - vect(0,0,64))` and `IsPositionOnFloor(B)`.
   - The link exists only if the last one is true and either of the first two is true.
2. **If the top is false:** make the copied roof give tile (34,21,6) a floor.
   - The tile must be in the work set (seeded) and the rebuild's floor step must accept the copy.
   - Or turn the ladder so that its top point lands over a tile that already has a floor.
3. **To make sure of the down link:** once the main rebuild has finished, call `RebuildTileDataExtents` again on a
   box that holds only the bottom tile. Centre it on the bottom tile with extent about (16,16,16).
   - This reruns `0x905780` and `0x777580` for that tile with the final flags and makes both links.
   - It leaves the top tile alone.

## The rebuild's work set, and a ladder copy's order (8 November 2026, step G5)

Read from the executable copy for the cars, doors and ladders plan (step G5), by a
helper agent and reviewed here; its full notes and dumps stayed in the session's scratch folder. Nothing was run in
the game. It corrects recommendation 3 above for copies made in the map: there, every rebuild is queued by
`XGBattle.DoWorldDataRebuild` in one frame, and a second request for the foot tile changes nothing.

**One shared work set** (high confidence):
- `execRebuildTileData` (`0x9C26B0`) → vtable `+0x214` (`0x9E9B00`), which only builds the extents (XY, XY, Z) →
  `0xE6ECB0`. That loops X outer, Y middle, Z inner over the clamped box and adds each tile whose static flags have a
  bit in `0xFFF` to one `TSet` at native world data `+0x48450`. It does nothing else.
- A tile already in the set is found (`0xE3A160`, `TSet::FindId`) and written back in its own slot
  (`0xE6F019`–`0xE6F036`): not moved, not added twice. A new tile is appended (`0xBA2850`, `TSparseArray::Add`).
- Nothing removes single elements (a scan of every use of the set's offsets: add, iterate, empty, reset,
  destructor, constructor, serialise), so the set never has holes and **its order is the order in which each tile
  was first added**. Nothing re-sorts it.
- When a call makes the set grow, it logs `WorldData: Restarting work queue (was %d, now %d tiles)` and restarts the
  consumer at stage 1 over the whole set (`0xE6F080`–`0xE6F0C4`). `IsRebuildingTiles()` (`0x85F5D0`) is `Num > 0`.

**The consumer** `0x46C700`, called only from the world data's tick (`0xCD1ED0`) while the set isn't empty, at most
`RebuildTileProcessRate` (native `+0x50534`) tiles a tick across its stages. Each stage is a full pass over the set in
slot order:
1. setup;
2. clear each tile's stores (`0x8670E0`), then re-add its interaction points (`0x5AD910`);
3. static flags and floor;
4. `0x7E8E30` (probably cover);
5. Neighbors (`0x905780`), then ladders (`0x777580`);
6. notify, then empty the set (`0x434F50`) and go back to stage 0.

Stages 2 to 4 finish for every tile before stage 5 begins, so the floor flags the ladder step tests are final; only
the order of tiles within stage 5 matters.

**What that means for a ladder** (inferred from the above, high confidence):
- The ladder keeps both links when its linked top tile T′ (tile(T), or the tile below it) is first added **before**
  its foot tile F, or is never in the set.
- When one volume adds both, T′ comes first for a ladder facing −X, or −Y; it comes after for +X or +Y, and when T′
  and F fall in one tile column (Z runs inner, and the foot is lower).
- **A second volume over the foot tile, after the copy's own, does nothing**: the copy's volume (a cube of half-size
  `SphereRadius`, bigger than its brush) has already added F.
- **A small volume over T′ alone, before every volume that reaches F in the level's actor list, works**: T′ takes the
  earlier slot whatever comes after. The Build can check the order exactly, from the volumes in actor order and the
  baked flags (only tiles with a bit in `0xFFF` are added).
- Calls before `DoWorldDataRebuild` come first: after a saved game loads, a broken door's
  `XComInteractiveLevelActor.OnLoadInteract` queues its tiles. The map's container saves the set too (taken to be
  the `u32 0` at 882,752 in URB_Bar, so empty there; inferred, medium-high).

**Interaction points** (store 5, native `+0x2025C`): stage 2 clears a tile's points (`0x82E1D0`), then `0x5AD910` adds
points back from a radius query of the world's collision hash around the tile's centre (radius 135.76; taken to be
`ActorRadiusCheck`), not from an actor iterator. A hit counts only if it is an `XComInteractiveLevelActor` in
`'_Pristine'`. So a door taken out of the level's actor list, never put in the collision hash, should get no points
back (inferred, medium-high; F-26's check in the game confirms it).
