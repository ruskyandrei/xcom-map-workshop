# Cover and line of sight: what the game does, and what the editor can predict

15 November 2026. The user asked whether the editor could show cover and line of sight without a game start. Two
static reads of the exe copy and the decompiled scripts were made for it the same day, by two agents, each checked
against the maps' baked data; nothing was run in the game. The full write-ups, with every address and confidence:

- [cover-build.md](cover-build.md): how the tile build decides a tile's cover and its blocking bits from the
  level's collision.
- [line-of-sight.md](line-of-sight.md): how the game decides that one unit sees another, the step-out, squadsight
  and flanking.

This note is the summary, a second check of the bit order, and what follows for the editor. The scripts read were
LWR's `XComGame`; the native code is the same exe for plain Enemy Within and LWR.

## 1. The short answer

**Both are tile data.** A battle decides cover, step-outs, flanking and sight inside sight radius from three things
a map carries for each tile: its static flags, its cover flags and its cover location. No collision is traced when
a soldier looks or shoots inside sight radius.

So there are two cases for the editor:

| Tiles | What the editor needs | State |
| --- | --- | --- |
| **The map's own**, where a project changed nothing | Only the map's baked tile data, which the editor's tools already read ([world_grid.py](../../tools/upk/world_grid.py)) | Cover, step-outs, blocked edges, flanking and sight can be shown from it today, by the rules below |
| **Edited places** (the game works these tiles out again when the battle starts) | The tile build's rule run on the project's pieces: a predictor | The rule is read; one part of it is checked on geometry and not yet exact (section 4) |

## 2. The rules in brief

### What a tile carries

| Data | Bits |
| --- | --- |
| Static flags | pathing blocked toward −X `0x2`, +X `0x4`, −Y `0x8`, +Y `0x10`, down `0x20`, up `0x40`; sight blocked toward the same six, `0x80` to `0x1000`; floor `0x2000`, sloped `0x4000`; occupied `0x8000`, partly `0x10000` |
| Cover flags | cover toward north (+Y) `0x1`, south (−Y) `0x2`, "east" (**−X**) `0x4`, "west" (**+X**) `0x8`; the same four as low cover `0x10` to `0x80`; step-out to the left `0x100` to `0x800` and to the right `0x1000` to `0x8000`; diagonal `0x10000`; climb onto `0x20000` to `0x100000`; climb over `0x200000` to `0x1000000` |
| Cover location | the mean of the points 40 back from each wall, clamped to the tile |

Two things the earlier notes had wrong: the blocking bits are `0x7E` and `0x1F80` (the script's constants `0x3F`
and `0xFC0` are one bit low, and the game's own queue test uses them), and the cover table's East is −X.

### How cover is built (the tile build and the battle's rebuild, one rule)

1. **Occupied**: a box of 96 × 96 × 64 in the tile meets the simple collision of a level piece that counts
   (`XComLevelActor` and its children, `XComFracLevelActor`; the mesh needs a BodySetup).
2. **Floor**: one line down through the tile's middle, onto a piece that can be stepped on, with a normal whose z
   is over 0.7. Under 0.9848 (about 10° off flat) it is a sloped floor, which gets no cover. A tile fully occupied,
   or under a fully occupied one, has no floor (standing room).
3. **Directions tried**: on a flat floor tile, only toward a neighbour that is occupied or off the grid (all four
   when the tile itself is partly occupied).
4. **Cover that way**: a thin box (2 × 2 × 16) swept 124 units from the tile's middle at 44 to 60 over the floor.
   It must hit a piece that gives cover, squarely enough, within 88 of the tile's middle, with valid floor under
   the point 40 back from the wall.
5. **High or low**: the piece's `CoverForceFlag` if set; else the same sweep 96 over the floor: a hit there is
   high cover, none is low.
6. **Step-out sides**: clear lines 96 to the side at two heights, a clear line forward from there, and a floor
   within 20 of the same height.
7. **Climb** (low cover only): clear at 88 over the floor, then what stands beyond the wall: nothing over 32 high
   is climb over, else climb onto.
8. **Blocked edges**: from 64 over the floor, a tiny box swept 96 to each side and 56 up and down, once for
   pathing and once for sight (only pieces with `bBlockUnitVisibility` stop the sight sweep).

The full build and the rebuild run the same functions. A rebuilt tile loses only what the build alone writes: the
level's edge marks and diagonal cover. A build's rebuild volumes take a map's diagonal cover that way wherever they
reach (findings register F-149, seen in the game).

### How sight is decided

- **Inside sight radius** (the unit's radius in metres × 64, plus 48): each unit keeps a map of the tiles it sees.
  The map is made by walking a ray of tiles from the unit's **eye tile** (one level over its floor tile) to every
  tile in reach. A step from one tile to the next is stopped when either tile has its sight bit toward the other.
  Nothing else is read: no collision, no units, no smoke.
- **Step-out**: the cover flags say which sides of each cover direction a unit can lean to. A step-out is sight
  from the tile to that side, at the unit's eye level. A target is also seen at its own step-out tiles on the side
  facing the viewer.
- **Beyond sight radius** (squadsight): a line check against the simple collision of level pieces that have
  `bBlockUnitVisibility`. This is the one path that reads geometry.
- **Flanked**: the target is in cover, the attacker sees it, and for **every** cover direction of the target the
  attacker is not on that cover's side. On the grid: (attacker tile − target tile) · direction ≤ 0 for each.
- **Cover's worth**: of the target's cover directions, the one most squarely between it and the attacker counts,
  high or low by its low bit. Plain EW 40 high and 20 low; LWR's ini 50 and 30. Height advantage is 192 units
  (three levels).
- Smoke and the cutaway do not change sight.

## 3. Checks

All offline, against baked data. The agents' checks are in their notes; the bit order was checked again apart from
them, with the repository's own decoder, on URB_Bar (24,336 tiles):

| Check | Result |
| --- | --- |
| A blocking bit between two tiles of which neither is occupied, without its mirror on the other tile | 0, for all six pairs of bits as read |
| The same with the masks as the notes had them (one bit lower) | 197, 302 and 1,826 (pathing X, Y, Z); 84, 137 and 1,750 (sight) |
| Bit `0x1` | 4 tiles, the PathBlockingVolume's |
| Cover bit toward an occupied or off-grid neighbour as read (N +Y, S −Y, E −X, W +X), on tiles not themselves occupied | 83 of 83, 53 of 53, 68 of 68, 59 of 59; none explained only by the opposite neighbour |
| Cover on a tile with no floor flag; low cover without its direction | 0; 0 |

From the cover note: on CSmallScout_Farm the same structure holds (0 exceptions in 1,550 direction bits), and its
8 diagonal tiles match the diagonal table.

**The game has already shown the sight rule twice**, before it was read:
- F-29: copied walls with full collision did not block sight wherever their tiles had no bits in the baked data,
  and did once the tiles were rebuilt (EXP-07 runs 5 to 12). A sight rule that traced collision would have
  stopped at them.
- F-25: a hidden wall kept blocking the squadsight probe (`WorldTrace`, check type 4) until its
  `bBlockUnitVisibility` was cleared (EXP-07 run 4): the line-check path and its filter, as read.

Also explained now: F-49 (a piece lifted a level over the floor gives no cover): the cover sweep runs 44 to 60 over
the floor and passes under it.

## 4. How exact a prediction can be

| What | From | How sure |
| --- | --- | --- |
| Cover shields, step-out sides, climb marks, blocked edges on the map's own tiles | read straight from the baked data | exact: it is the game's data |
| Sight, step-out sight and flanking between any two tiles of the map's own | the ray walk and the flank rule over that data | the rule is read end to end and fits F-29 and F-25; **not yet compared with a battle tile by tile** |
| Cover location on edited tiles | the predictor, from simple collision | 209 of 213 tiles within 0.1 unit on URB_Bar (the cover note's spot-check) |
| High or low on edited tiles | the predictor | 199 of 209; the misses are likely flags held by archetypes in other packages |
| Step-outs, climb marks, blocked edges on edited tiles | the predictor | read in full, **not checked on geometry** |
| Occupied tiles' own bits | the predictor | open: how a sweep that starts inside a collision hull behaves decides them |

What can't be predicted from a map alone: what changes in a battle (a destroyed piece opens sight after its tiles
are rebuilt; a unit standing on a step-out tile takes it away).

## 5. Open points

From both notes; the ones that would change a tile's result first.

1. A sweep that starts inside a hull, and per-triangle pieces: decides the bits of occupied tiles (about a third
   of blocked pairs with an occupied tile are one-sided).
2. The 4 cover locations off by 34.8 (all destructible props) and the 10 high or low misses of the spot-check.
3. Step-out, climb and the low-cover ramp rule on geometry.
4. The ray walk compared with a battle: the one question here that an in-game run would settle, and a short one
   (a soldier on a known tile, the tiles it is predicted to see against the enemies it is offered).
5. The hit chance's native side (`CalcHitChance`, `ShotInit`): that a flanked target loses its cover value is
   from the script's shot summary.
6. Static bits `0x100000` (the rule misses a condition on 152 tiles), `0x200000`, `0x40000` (no writer found).
7. A steep ray downward skips its last crossing; the unset local in the unit check when a target's tile word is 0.

## 6. Scripts in the lab

`<lab>\re\cover\`: `bake.py` (loads a map's stores), `check.py`, `check2.py`, `spot.py` (the geometric
spot-check), `tiles.py`, `bits.py`. `<lab>\re\sight\`: `sight_ref.py` (the sight rule in Python: the walk, a
viewer's word, step-outs, can-see), `check_bits.py`, `check_cover.py`, and exe reading helpers (`execslots.py`
names the virtual slot each native's thunk ends in). None is in the repository yet: the ones the tile preview
needs come in with it, with tests (the plan).
