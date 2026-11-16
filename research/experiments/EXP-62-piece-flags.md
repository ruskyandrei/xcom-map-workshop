# EXP-62: the piece flags not played yet, in one run

Date: 16 November 2026. The piece flags plan's remaining in-game probes (P7), at the user's ask, in one project on
URB_Bar: each flag on its own (case C), roles turned on and a prop's pathing gate opened (D), Floor on (E), a ladder
(F), a door (G), damage (H) and a save and reload (J). EXP-60 played the mouse on (Temple Ship's arches) and EXP-61
every flag off on a statue ([F-114](../findings-register.md)). Each edited piece has an unedited one of the same kind
beside it or nearby.

## What was read (offline)

From [native/piece-flags.md](../native/piece-flags.md), sections 1 and 2, and [native/cover-build.md](../native/cover-build.md):
- **Blocks walking** is what the occupancy step and the pathing sweep read. Off, the tile isn't occupied, and the
  cover step looks for cover only toward an occupied tile, so a piece with walking off and cover on probably gives
  none; the cover step's lateral pathing bit may still block an edge.
- **Gives cover** is what the cover sweep reads; off, the piece still occupies its tile and blocks crossings.
- **Blocks sight** is what the sight sweep reads; off, units see through, while walking and cover are unchanged.
- **A prop's pathing gate** (`bIgnoreForPathing`) makes the pathing, cover and sight sweeps pass the prop. Turning
  Blocks walking on opens it.
- **A ladder** never occupies a tile, and its walking flag sets only whether the pathing sweep meets it. The cover
  step's height test counts a ladder whatever its flags say, so a ladder may still give cover.
- **A door's** blocking also follows its open or shut state (the Build warns: untried).
- A flag is a setting, not collision: a shot meets what collides, whatever Blocks sight says (not tried).

## The project

`EXP-62 piece flags` (URB_Bar, [exp62_project.py](../../tools/editor/examples/exp62_project.py), in the editor's
project store), a quick build (`URB_Bar_X62-20261116-154600`; the map's SHA-256 starts `6ec0278db462`). It compiles
with the one expected warning (`flags-door`) and a note (`flags-wall`, for the fences that stop blocking sight).
Overview (`EXP-62-row.png`), the boxes (`EXP-62-boxes.png`), the fences (`EXP-62-fences.png`), the hedges
(`EXP-62-hedges.png`), the bar's west wall (`EXP-62-west-wall.png`) and the controls on its north wall
(`EXP-62-north-wall.png`).

**Copies on the pavement in front of the bar** (top at 16; the middle row is y −192 to −96; west to east):

| Place | What stands there | Built as | Flags | The prediction |
| --- | --- | --- | --- | --- |
| B0 | a box stack (`BoxStackA`, 75 tall), tile x −1632 to −1536, the control | `XComDestructibleActor_528` | as the map has them | no way into its tile; low cover beside it |
| BW | the same, x −1344 to −1248 | `XComDestructibleActor_529` | Blocks walking off | units stand in its tile; probably no cover from it |
| BC | the same, x −1056 to −960 | `XComDestructibleActor_530` | Gives cover off | no way into its tile; no cover beside it |
| BF | the same, x −768 to −672 | `XComDestructibleActor_531` | Floor on | its top (75 over the pavement) may be offered as a place to stand, if a soldier can get up |
| F0 | a tall fence (`FenceTall192`, 128 tall, two tiles) on the tile edge y −192, x −480 to −288, the control | `XComDestructibleActor_532` | as the map has them (Gives cover off) | stand on both sides, no crossing, no cover, no sight across |
| FC | the same, x −96 to 96 | `XComDestructibleActor_533` | Gives cover on | as F0, with high cover toward it on both sides |
| FS | three such fences in a line, x 288 to 864 | `XComDestructibleActor_534` to `_536` | Blocks sight off | no crossing, no cover, sight across |

**The map's own pieces, where they stand:**

| Place | Pieces | Flags | The prediction |
| --- | --- | --- | --- |
| H | the hedge south of the car park, east (bushes `XComDestructibleActor_212`, `_213`, `_239`, 36 tall) | Blocks walking on; the Build opened their pathing gate (`bIgnoreForPathing` false) | their tiles occupied: no standing in the hedge |
| H0 | the hedge west of it (`_197`, `_210`, `_211`) | as the map has them (walking off, gate shut) | units stand in it |
| D | the bar's west door (`XComInteractiveLevelActor_4`) | Blocks walking and Blocks sight off | not known: a path through it shut, and sight through it, or the door's own state deciding |
| D0 | the back door on the north wall (`XComInteractiveLevelActor_26`) | as the map has them | as the map has it |
| L | the ladder on the west wall (`XComLadder_3`) | Blocks walking off (its sight and mouse are off in the map already; it has no cover setting) | it still climbs; it may still give cover beside it (the height test) |
| L0 | the ladder on the north wall (`XComLadder_4`) | as the map has them | as the map has it |

Read back offline from the built map with a fresh reader: every place has the flags above. The hedge's three bushes
save `bAlwaysConsiderForCover` true and `bIgnoreForPathing` false on the actor; the door saves walking, cover and
sight off; the ladder saves walking off. The Build rebuilt two tile regions round the pieces edited in place (the
hedge; the west wall's door and ladder: 152 tiles seeded) and the copies' tiles as copies get them. The ladder's top
tile (12, 23, 6) is queued first in the rebuild and its foot (11, 23, 0) after, so its climb keeps both links.

A parking block's "partly on" (the gate shut, walking on) can't be seen on this map: the blocks are 12 tall, under
what the tile build reads. The hedge tests opening the gate instead.

## Run 1

What the run adds over the offline checks (Play in game, with Enable saving for step 10):
1. **BW:** can a soldier move into its tile, inside the boxes? With one beside it, is there a shield toward it?
2. **BC:** its tile isn't a destination. A soldier beside it gets no shield toward it (B0's neighbours get a low one).
3. **BF:** with the cursor over its top, is the top offered as a destination, and can a soldier get up there from
   beside it? (B0's isn't.)
4. **FC and F0:** a soldier on either side of FC gets a full shield toward it; beside F0, none. Neither can be crossed.
5. **FS:** a soldier in the middle row north of FS, about the middle of its six tiles, and an alien south of it in the
   street: is the alien seen and can it be shot? If a shot is taken across it, does it hit the fence? (F0 blocks the
   view.)
6. **H and H0:** can a soldier move into H's tiles? Into H0's, as the map has it?
7. **D and D0:** with D shut, does a path go through it without opening it? Can a soldier see through it? Open it
   and shut it again: the same after? D0 for comparison.
8. **L and L0:** a soldier climbs up L (a route up). Beside L, is there a shield toward it? L0 for comparison.
9. **Damage:** a grenade or shots at B0, BW and BC: do the edited boxes break as the control does? Is anything left
   blocking a tile after?
10. **Save and reload:** after steps 1 to 8, save (say which slot), load it, and check BW, FC and H again. The save
    also lets the tiles be read offline (`tools/lab/save_tiles.py`: floor, occupied and the other bits per tile).
11. Anything odd: a crash, a unit at an odd height, a piece drawn wrong.

## Result

**Run 1 passed, with two answers the plan didn't predict** (16 November 2026, played by the user). The user: "H does
not block walking", "L works normally", "D soldiers walks in through door (without opening or kicking open)", and
"everything else seems to work as expected, save made". So B0, BW, BC, BF, F0, FC and FS, the damage and the save
and reload did what the list says.

The user's save, read with `tools/lab/save_tiles.py` against the built map (tiles counted from the game's corner,
`baked -> saved`):
- **H, Blocks walking on, worked in the tiles but doesn't block.** The hedge's tiles (x 15 to 21, y 0 to 3) are
  partly occupied (`0x8000` with `0x10000`), with their floor kept and no crossing bit; the control hedge's are free,
  as baked. A 36-unit bush meets only the low occupancy box (28 to 92 over the level's bottom), not the upper one, so
  the floor stays, and it is under the crossing sweep (64 over the floor), so no crossing is blocked: units walk into
  a partly occupied tile. Blocks walking stops units only on a piece that reaches the crossing sweep, like the box
  stacks. What opening a prop's pathing gate does to the sweeps is still unseen: this hedge, like the parking
  blocks, is too low for them.
- **D, walking and sight off on a door, works on the shut door.** The edge through it, between tiles (11, 28) and
  (12, 28), has lost its pathing bits (`0x4` and `0x2`) and its sight bits (`0x100` and `0x80`) on both sides: the
  shut door blocks neither walking nor sight, and the soldier walked through it without opening it. Sight through it
  and the door after opening and shutting it were not reported apart.
- **L, Blocks walking off on a ladder, changed no tile.** Its foot (11, 23, 0) and top (12, 23, 6) tiles are as
  baked, the top's link bit included, and it climbs (the user). Whether it still gives cover beside it was not told
  apart.
- **BF, Floor on:** its tile (21, 18) is fully occupied with no floor at level 0, and the tile over it (level 1) has a
  floor: the box's top is floor. Whether a soldier got up there was not told apart from "as expected".
- **BW, Blocks walking off:** its tile (15, 18) is not occupied, as baked: units stand in it. B0's and BC's tiles are
  occupied, and each fence marks the tiles on both sides of its edge occupied with their floors kept (EXP-59's B).
  Not explained: B0 and BC each show four occupied tiles (two across, both rows of the edge y −192), where one box
  stack stands in one tile; BW and BF don't.
- Changed besides: two tiles inside the bar behind its front wall, (12, 22) and (13, 22), lost their pathing and sight
  bits toward the wall, and (13, 22) its occupancy. Most likely the grenades thrown at the boxes broke the front
  windows there; not checked.

What it settles for the editor: Blocks walking, Gives cover, Blocks sight and Floor each do what the panel says on a
copy; a door's walking and sight flags open a shut door; a ladder still climbs with walking off. Two limits to say:
Blocks walking on a low piece (under 64 over the floor) only marks its tiles partly occupied and stops no one, and
the door's walking and sight flags override its shut state.
