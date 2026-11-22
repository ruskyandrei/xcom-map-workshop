# How XComWorldData makes a floor tile's neighbour links (XComEW.exe, read-only)

22 November 2026. Static reading of `<lab>\re\XComEW-copy.exe` (image base `0x400000`); nothing was run or patched,
no game file was written. The dumps and annotated dumps (`dis_*.txt`, `dis_*.ann.txt`) and the scratch scripts stay
in `<lab>\re\links`; the dump of `0x905780` is `<lab>\re\cover\dis_905780.ann.txt`. `[F+xx]` is a stack slot named
by its offset from esp after the prologue, as in [cover-build.md](cover-build.md), which this builds on (its section 1
is the order of work; this note is its pass 4).

Confidence marks: **high** = read end to end and reproduced bit for bit by the check (section 9); **medium** = read,
checked in part; **low** = inferred.

The check: [neighbour-links-check.py](../evidence/neighbour-links-check.py) predicts every floor tile's links of a
map from its baked tile data and its pieces, and compares them with the bake; its record over the install's 97 base
maps is [neighbour-links-2026-11-22.json](../evidence/neighbour-links-2026-11-22.json).

## 0. Corrections to what was known

| Was | Is | Confidence |
| --- | --- | --- |
| The runtime rebuild's `0x905780` "adds plain links only (PathObject 0, no types or positions)" (native-code-notes.md, "Does the runtime rebuild keep path-object links?") | `0x905780` makes **every** link but the ladders': plain links and, through four callees, ClimbOver, ClimbOnto, KickDoor, DropDown, JumpUp and WallClimb, with their positions and path objects. The full build and the rebuild run the same function (section 7) | high |
| The ladder step "removes every DropDown link on the top tile" (ladder-links.md, answer 3) | It removes the **first** DropDown link of the top tile only: its loop ends at the first it removes (`0x777C59`–`0x777C7D`) | high (the farm's ladder tops keep 8 DropDown links) |
| A ladder's height is the mesh's bounds height, `2 × (bounds extent z + 1)` (`tools/viewer/ladders.py`) | `GetHeight` reads the component's **Bounds**: the mesh's bounds box united with its collision's box, grown by 1 on every side (UE3's `UStaticMeshComponent::UpdateBounds`), then `max(Max.Z, Location.Z) − min(Min.Z, Location.Z)`. The old formula is up to 0.13 short on most ladders and 33 short on `SupplyShipLadder_448` (a mesh whose origin is not at its foot): 417.4 against 450.1 | high (all 896 baked ladder links) |
| Bit `0x100000`: 2 × 2 standing room, "a condition is missing" (cover-build.md, section 6, 152 tiles) | Read in full (section 5): the masks are as read, the tile's **own floor is not tested**, and the reads of the `+X` and `+Y` neighbours are not checked against the grid, so they **wrap** at the grid's edge | high (176,630 of 176,630 tiles, none either way) |
| Bit `0x200000`: "read in part" | The drop search (section 4.3) sets it on the tile when it gets two or more levels below the neighbour without being stopped, whether or not it finds a floor there | high (20,538 of 20,538) |

## 1. Functions and addresses

| What | Address |
| --- | --- |
| **The link step for one tile** (`this` = `UXComWorldData`, arg = `TTile*`) | **`0x905780`** (to `0x9069E8`) |
| ClimbOver / ClimbOnto | `0x78B680(tile, &N, coverFlags << 16, staticN, entry, entry.C & coverFlags, entry.D & coverFlags)` |
| KickDoor | `0xC0DE50(tile, &N, (entry.E & coverFlags) == 0)` |
| DropDown, and bit `0x200000` | `0xD8F610(tile, staticTile, &N, staticN, entry)` |
| JumpUp / WallClimb | `0xAA88C0(tile, staticTile, &N, staticN, entry, entry.F, entry.E)` (the last two unused) |
| Ladders (after the step) | `0x777580` ([ladder-links.md](ladder-links.md)) |
| Tile data getter (flags `+0x84`, cover flags `+0x88`, cover location `+0x30`, floor record `+0`, interact points `+0x78`, dynamic flags `+0x90`) | `0xE3E3F0(tile, out)` |
| Floor record get / set (the setter makes a missing chunk) | `0x46F020` / `0xC46790` (store at native `+0x10194`) |
| Tile position (centre, 32 over the level's bottom) | vtable `0x158` = `0xD5B5E0` |
| Tile index with the grid check (−1 outside) | vtable `0x17C` = `0xF647D0` |
| Floor height at a position: its tile's floor record z, else the position's z | vtable `0x168` = `0xF20E90`, through `0x160` = `0xB4F1C0` and `0x164` = `0xD45A70` (a tile with a floor answers itself) |
| `UWorld::MultiLineCheck` (stock: the collision hash's `ActorLineCheck`, sorted) | `0x9F2630(Mem, End, Start, Extent, TraceFlags, SourceActor, SourceLight)` |
| `UWorld::SingleLineCheck` | `0x72A840(Hit, SourceActor, End, Start, TraceFlags, Extent, SourceLight)` |
| `XComDestructibleActor` / `XComInteractiveLevelActor` StaticClass pointers | `0x1D3DE08` (getter `0x512FE0`) / `0x1D3DE20` |

Callers: full build `0x98A302` (every tile, by the tile iterator `0x428F10` / `0xF85110`), then `0x9F8680` for every
tile, then `0x777580` once for all ladders (`0x98A415`); runtime rebuild step 5, `0x46D965` (`0x905780`) and
`0x46D99E` (`0x777580` with that tile), per tile of the work set.

### The direction table (built on the stack at `0x9057D3`–`0x905A5A`, `[F+1C0]`, 8 entries of 0x24 bytes)

Each entry: dx, dy, 0 (the delta, passed as a tile), A = the tile's own pathing bit toward the neighbour, B = the
neighbour's bit back, C = the ClimbOver cover bit, D = the ClimbOnto cover bit, E = the cover bit, F = the low cover
bit (cover bits as cover-build.md section 4's table; its E is toward −X).

| i | (dx, dy) | A | B | C | D | E | F |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | (−1, 0) | `0x02` | `0x04` | `0x800000` | `0x80000` | `0x4` | `0x40` |
| 1 | (+1, 0) | `0x04` | `0x02` | `0x1000000` | `0x100000` | `0x8` | `0x80` |
| 2 | (0, −1) | `0x08` | `0x10` | `0x400000` | `0x40000` | `0x2` | `0x20` |
| 3 | (0, +1) | `0x10` | `0x08` | `0x200000` | `0x20000` | `0x1` | `0x10` |
| 4 | (−1, +1) | `0x12` | `0x0C` | (as 0) | | | |
| 5 | (+1, +1) | `0x14` | `0x0A` | (as 1) | | | |
| 6 | (+1, −1) | `0x0C` | `0x12` | (as 2) | | | |
| 7 | (−1, −1) | `0x0A` | `0x14` | (as 3) | | | |

For a diagonal, A and B are the two straight bits together; C to F are never read for one (no typed link is tried
on a diagonal).

## 2. The step for one tile (`0x905780`), in order

Names: T the tile, P its position, `stT` its static flags, `cf` its cover flags (store `+0x8130`), N a neighbour.

1. **Bit `0x100000`** (section 5), on any tile, floor or not.
2. Only a tile with **`0x2000`** goes on (`0x905D45`).
3. T's floor record is copied, its Neighbors **emptied** (`0x5952A0`, `TArray::Empty(8)`) and written back
   (`0xC46790`): every link of T is made anew below.
4. **Loop, dz outer** (−1, 0, +1), **direction i inner** (0 to 7, the table's order). N = T + (dx, dy, dz).
   - N outside the grid (vtable `0x17C`) → next.
   - **head** (`[F+50]`): when the tile above T exists (Z + 1 < NumZ), head = (its static flags & A) ≠ 0 and no unit
     on T (dynamic flag `0x2`); with no tile above (the grid's top level) head = 1. A unit on N (its dynamic `0x2`)
     clears head. (A third term, the tile above N with bit B and a unit on N, is set and cleared at once: dead.) In
     the full build no tile has a unit, so **head = the tile above T blocks that way, or T is on the top level**.
   - **blocked** (`[F+44]`) = (stT & A) ≠ 0 or (stN & B) ≠ 0.
   - **N has `0x2000`:**
     - **Diagonal** (i > 3): blocked \|= the **diagonal sweep** meets anything (section 3.1).
     - **step** (`[F+30]`) = 1; for dz ≠ 0 and T not a ramp (`0x4000`): step = N is a ramp, or (floor normals'
       dot > **0.996** and |zT − zN| < **32**) (`0x9064CB`–`0x90654D`; z the floor records' heights).
     - not blocked, not head, step → **a plain link** (section 3).
     - blocked or head, straight only: **ClimbOver / ClimbOnto** (`0x78B680`, section 4.1), then, when dz = 0 or
       |zN − zT| < 32, **KickDoor** (`0xC0DE50`, section 4.2).
     - straight, dz = 0: **JumpUp / WallClimb** (`0xAA88C0`, section 4.4).
   - **N without `0x2000`**, straight, dz = 0 only:
     - when Z > 0: **DropDown** (`0xD8F610`, section 4.3) if (T has no cover that way (E) and not head) or (T has cover
       and low cover that way (F)); then **ClimbOver / ClimbOnto** (`0x78B680`);
     - always: **JumpUp / WallClimb** (`0xAA88C0`).
5. In the full build, after every tile: the ladders (section 6).

So a tile's list is in this order: dz −1, 0, +1; within each, −X, +X, −Y, +Y, (−1, +1), (+1, +1), (+1, −1),
(−1, −1); per neighbour the plain link, or ClimbOver/ClimbOnto then KickDoor (the interact point's, then the
destructible's), or DropDown then ClimbOver/ClimbOnto; then JumpUp (and WallClimb); the ladders' links last.

Confidence: high. Every tile whose links match as a set matches in order too (324,522 of 324,522).

## 3. Plain links

A plain link: target N, **cost 1.0 straight, 1.414 diagonal** (`0x1875200`, `0x18721D8`; whatever dz), PathObject 0,
no traversal types, no positions (`0x906572`–`0x906766`).

The rule, all of it (with the build's head):
- N within the grid, with **`0x2000`**; dz −1, 0 or +1;
- T's bit toward N clear and N's bit back clear (both straight bits each, for a diagonal);
- **the tile above T** (Z + 1) clear of T's bit that way; T not on the grid's top level;
- dz ≠ 0: T is a ramp, or N is a ramp, or the two floors are parallel (dot > 0.996) and **less than 32 apart in
  height**;
- a diagonal: the sweep below meets nothing.

No corner tile is read for a diagonal: its corners are the sweep's. The grid's own bits do not see a step either:
the over-prediction the plain rule had (links missing for steps of about 56 and more, and diagonals with every flag
clear) is the step rule, the head rule and the sweep. Across levels, the plain links of six maps (Bar, farm, police
station, City, Stonewall, Wildfire) are 8,448 from or onto a ramp and 208 between flat floors (steps up to 24.5).

### 3.1 The diagonal sweep (`0x9062D5`–`0x9063B7`)

- `MultiLineCheck`, **a box of half-extent (24, 24, 4)** (statics at `0x1D42D84`, set from `0x1874FB8` = 24 and
  `0x1873FCC` = 4), trace flags **`0x860D3`**, no source actor;
- **from** (P.x, P.y, zT + 24) **to** (PN.x, PN.y, zN + 24), z the two floor heights (vtable `0x168`);
- any result at all blocks the diagonal.

With no source actor the flags should meet level geometry only (in UE3, as remembered, not read here, an actor that
is not world geometry passes `TRACE_Others` with `TRACE_Blocking` only when a source actor is blocked by it), which
the data bear out: the check meets the map's `bWorldGeometry` pieces through their
components that block a box (tile_world's 'engine' check) and agrees on 99.84% of the diagonals (1,815
disagreements in 1,111,854 sweeps); adding the pieces that are not world geometry makes it much worse (over ten
maps, 6,210 false blocks against 320). Which flags `0x80000` and `0x4000`/`0x2000` add (XCOM's own, tessellation,
terrain) was not read.

Confidence: the code high; the check medium (what it does not reproduce is in section 9).

## 4. Typed links

All typed links have **cost 1.0** and two traversal types, the second **Landing** (7), and two positions.

### 4.1 ClimbOver (2) and ClimbOnto (3) (`0x78B680`)

Only when T's cover flags hold the ClimbOver bit (C) or the ClimbOnto bit (D) that way (the cover step's climb test,
cover-build.md section 4, step 12); over when C is set, else onto.
- CL = T's **cover location** (store `+0x181F8`); O = **(108·dx, 108·dy, 0)** over, **(80·dx, 80·dy, 68)** onto.
- Target: over, the tile holding CL + O (`GetTileCoordinatesFromPosition`, no grid check); onto, N.
- The target needs `0x2000`. Over: |zTarget| − |zT| < 32 (the absolute heights' difference, as written:
  `0x78B929`); onto: zTarget − zT > 32.
- Positions **[CL, CL + O]**.
- **PathObject**: `SingleLineCheck`, flags `0x860C0`, zero extent, from P + L·(dx, dy) + (0, 0, 96) back to
  P + (0, 0, 96), L = 135.744 when `cf << 16` is not 0 (cover flags in their low 16 bits; every climbing tile) else
  124; when the hit's actor is an `XComDestructibleActor` (its children too) with **`bInteractive`** (`+0x24C` bit 2),
  it is the path object (a window), else 0.

Confidence: high (all 16,775 ClimbOnto and 3,992 ClimbOver links, 1,055 with a path object). Whether the absolute
heights' comparison ever differs from the difference's was not seen.

### 4.2 KickDoor (9) (`0xC0DE50`)

Two parts, both run:
1. **T's interact points** (store `+0x2025C`, the bake's store 5): the first point whose `ModifyTileStaticFlags`
   holds `0x2` with dx < 0, `0x4` with dx > 0, `0x8` with dy < 0 or `0x10` with dy > 0, its actor not passed by:
   one link, PathObject the point's actor. Passed by: an actor whose `+0x374` is over 6 (read as the count of its
   `InteractionPoints`, the array at `+0x370`: 56 points so passed by on the base maps, none of them baked) or whose
   `+0x398` bit 4 is set (`bTouchActivated` by the same layout: never met).
2. When T has **no cover that way**: `SingleLineCheck` (`0x860C0`, zero extent) from T's floor + (0, 0, 96) +
   124·(dx, dy, dz) back to T's floor + (0, 0, 96); a hit on an **`XComDestructibleActor` with `bInteractive` that is
   not an `XComInteractiveLevelActor`** gives a link, PathObject that actor.

Target N; positions **[P, PN + 8·u]**, u the unit vector from P to PN.

Confidence: high (all 1,172 KickDoor links: 824 from points, 348 from the line); the `+0x374` and `+0x398` names
medium.

### 4.3 DropDown (5), and bit `0x200000` (`0xD8F610`)

Down N's column, k = 0, −1, … −10 (levels below 0 skipped): T′ = (N.x, N.y, N.z + k), above = the tile over T′
(none on the top level).
- T′ fully occupied (`0x8000` without `0x10000`), T′ blocked upward (`0x40`), or the tile above blocked downward
  (`0x20`) → stop, no link.
- k < −1 → **T gets `0x200000`** (written at the end, `0xD8F8E3`).
- T′ has `0x2000` → found.

A link when found, and (T a ramp → more than one level down), and **|zT − zT′| > 32**: target T′, positions
**[P + 20·(dx, dy) − (0, 0, 4), PT′ + 16·(dx, dy) − (0, 0, 4)]**, PathObject 0.

Confidence: high (all 37,947 DropDown links; the bit on 20,538 of 20,538 tiles).

### 4.4 JumpUp (11) and WallClimb (10) (`0xAA88C0`)

Up both columns, k = 0 to 10, skipping k once N.z + k + 1 ≥ NumZ: Tk = (T.x, T.y, T.z + k), Nk = (N.x, N.y, N.z + k).
- Tk fully occupied → stop; k > 0 and (Tk blocked downward (`0x20`) or the last Tk blocked upward (`0x40`)) → stop.
- From the third level counted (the count of levels passed over 1): Nk has `0x2000` and either (Nk has no cover
  back toward T and neither the tile over Tk has T's bit that way nor the tile over Nk N's bit back) or (Nk has cover
  and low cover back toward T) → **JumpUp** to Nk, positions **[P, PNk]**.
- Else the climb goes on; *wall* stays set while every level passed has T's bit that way or N's bit back.
- With *wall* set, a second link follows, the same with **WallClimb** first: a WallClimb link always has its JumpUp
  twin.

Confidence: high (all 19,347 JumpUp and 14,637 WallClimb links).

## 5. Bit `0x100000` (`0x905ACC`–`0x905C71`)

Set on T (floor or not) when T has neither `0x4` nor `0x8`, and (x+1, y), (x, y+1), (x+1, y+1) all have `0x2000`,
the first without `0x12`, the second without `0x14`, the third without `0x0A`. The three reads are the store's
inline reads with no grid check: past the +X edge of a grid whose NX is a multiple of 3 the chunk index runs on into
the next chunk row, so (NX, y, z) reads (0, y + 3, z) (Stonewall's 9 edge tiles), and a slot past the grid in its
chunk reads 0. The masks look swapped from a 2 × 2 test (own `0xC` and the y+1 neighbour's `0x14`, where `0x14` and
`0xC` would face the square), but they are what the bake holds.

Confidence: high (176,630 of 176,630 tiles).

## 6. Ladders (`0x777580`), what this reading adds to [ladder-links.md](ladder-links.md)

- The top tile's **first** DropDown link goes, then the down link is appended.
- `GetHeight` uses the mesh component's Bounds as UE3 makes them (section 0), and the two points go through the
  ladder's whole matrix (Portent's `XComLadder_9`, rolled 1.7 degrees, needs it).
- Only z is checked against the grid; the column reads are raw (they wrap as in section 5).

Confidence: high (all 896 baked ladder links).

## 7. Full build against the runtime rebuild

The same `0x905780` and callees run in both; the differences:

| | Full build | Runtime rebuild |
| --- | --- | --- |
| Tiles | every tile | the work set, its stores cleared first (cover-build.md section 1) |
| Units | none: head is the tile above's bit | a unit on T, or on N, lifts the head rule for that link (so a unit standing below a ledge does not cut its neighbours off) |
| Ladders | once for all ladders, after every tile | per tile, the ladders whose foot is that tile, right after its links (the order hazard of ladder-links.md) |
| Typed links | made | made the same way, from the stores and traces of the moment: a door's KickDoor needs its interact points, which stage 2 re-adds from the collision hash |
| Bits `0x100000`, `0x200000` | set | set again on rebuilt tiles (their flags were cleared) |
| Edge bits (`0x9F8680`) | set | not set |

Confidence: high for the code; the units' part is not checked on data (no bake has units).

## 8. What a tile writer needs

- Per tile: static flags (of T, its neighbours, the tiles above them and down the columns), cover flags (T and the
  climbing columns' tiles), floor record heights and normals, cover locations, interact points (with their actors'
  `InteractionPoints` count and `bTouchActivated`).
- Traces against the pieces: the diagonal sweep (section 3.1, 'engine' with a box), and three zero-extent
  `0x860C0` lines for path objects (ClimbOver/ClimbOnto, KickDoor's second part), whose answer is only "the first hit
  is an interactive destructible".
- Per ladder: its matrix, its mesh's bounds and collision box.
- The order of section 2, if the list is to be byte for byte.

## 9. Checks against baked data

[neighbour-links-check.py](../evidence/neighbour-links-check.py), inputs the bake's own tile data, traces through
`tools/bake/tile_world.py`. A link matches when target, cost (to 0.001), types, path object and positions (to 0.1
unit) are equal.

| | Links baked | predicted | matched | tiles | tiles exact |
| --- | --- | --- | --- | --- | --- |
| URB_Bar | 14,584 | 14,590 | 14,584 | 2,162 | 2,156 |
| CsmallScout_Farm | 31,245 | 31,271 | 31,217 | 4,782 | 4,732 |
| URB_PoliceStation | 15,227 | 15,231 | 15,227 | 2,320 | 2,316 |
| CLrgScout_City | 25,612 | 25,612 | 25,612 | 3,978 | 3,978 |
| COverseer_Stonewall | 29,170 | 29,170 | 29,170 | 4,344 | 4,344 |
| CSupplyShip_Wildfire | 57,226 | 57,164 | 57,156 | 8,754 | 8,689 |
| **96 base maps** (Command1 has no level volume) | **2,140,357** | **2,140,508** | **2,139,524 (99.96%)** | **325,914** | **324,522** |

- 26 maps identical, 60 with every baked link predicted; the lowest URB_ConvienienceStore_Terror, 99.43%.
- **Typed links: 94,766 of 94,766** (ClimbOnto 16,775, ClimbOver 3,992, DropDown 37,947, JumpUp 19,347, WallClimb
  14,637, KickDoor 1,172, ClimbLadder 896). Bits `0x100000` and `0x200000`: exact on every map.
- Every miss is a plain link, all but two of them diagonals: the sweep (section 3.1) and the pieces it meets:

| Diagonal disagreement | Count | What is near (the check's guess) |
| --- | --- | --- |
| game blocked, the check's sweep met nothing | 426 | a `StaticMeshActor` saved `bCollideActors` False (bushes: Bar's six beside its east kerb) |
| | 184 + 122 | a destructible or level actor that is not world geometry |
| | 40 + 16 | skeletal meshes (interactive actors such as the farm's UFO door, KAssets): not read |
| | 32 | fracturing pieces (their fragments are not read: the police station's stair opening) |
| | 15 | another non-colliding piece |
| | 147 | nothing found (Act1_IntroLevel 32, the farm 13) |
| game passed, the check's sweep met a piece | 329 | an `XComLevelActor` face looking up (slopes: the farm's mirrored ramp by (58, 61), Wildfire's stacked ramps by (71, 21), Furies, the forest trenches) |
| | 247 + 108 + 5 | `XComDecoFracLevelActor` / `XComFracLevelActor` (the Terror variants' building cores; likely the game meets a fracturing piece by its fragments, the check by its mesh's collision) |
| | 85 + 2 | a piece the sweep starts inside |
| | 33 + 14 + 10 | other faces |

## 10. Unresolved

1. **The sweep's 1,815 disagreements** (0.16% of the diagonal sweeps): fracturing pieces' fragments and skeletal
   meshes are not modelled by `tile_world`; the non-colliding `StaticMeshActor`s that the bake's sweep evidently met
   are unexplained (their saved `bCollideActors` False: a property changed after the bake, or the editor's collision
   at bake time); the false blocks on slopes (faces looking up, starting inside) were not traced to a rule: skipping
   box elements, mirrored pieces' box elements or starting-inside hits each made the check worse.
2. AlienBase02 (58, 19, 6): the four links into it, from neighbours whose rule passes, are not baked; the tile sits
   under a PathBlockingVolume tile (`0x98FFF`). Not explained.
3. `+0x398` bit 4 (`bTouchActivated`) never met; `+0x374`/`+0x370` named by layout and by 56 points.
4. The units' part of the head rule (runtime only) is read, not checked.
5. The climb-over height test compares the absolute heights; no case seen where it differs from the difference.
6. A floor tile with no floor record (z = NZ of a grid of odd NZ, in the static store's last chunk layer) gets no
   links in the bake: the link step's tile iterator was taken to cover the grid only (seen, not read).
