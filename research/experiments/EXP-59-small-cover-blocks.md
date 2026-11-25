# EXP-59: cover blocks smaller than a tile

Date: 15 November 2026. The editor's cover blocks now size in units with handles in the view
(cover-block-handles-plan.md). This experiment plays
what the game makes of blocks smaller than a tile, which so far is read from its code only. If B acts as a wall, it
is also Discord feedback S8, an invisible cover wall (the Discord feedback list, kept locally).

## What was read (offline)

From [native/cover-build.md](../native/cover-build.md), the full read of the tile rebuild's cover step. The panel's
words and the Build's warnings follow it (app.js `coverTiles`, compiler `THIN_COVER` and `COVER_SWEEP`):
- **Standing.** A tile is occupied when its box, 48 each way across and 28 to 92 over its level's bottom, meets a
  piece at least 4 units through every way. It is fully occupied, with its floor taken away, when the middle 40 × 40
  from 60 to 92 meets the piece too. The Bar's pavement is 16 over its level's bottom, so the middle is about 44 to
  76 over the pavement.
- **Walls.** A tile's crossing to a neighbour is blocked by a sweep from 64 over its floor to the neighbour's centre.
  It has no thickness rule.
- **Cover.** A sweep 44 to 60 over the floor, along the line from the tile's centre toward a neighbour, meeting the
  piece within 88 of the centre. A tile looks only toward an occupied neighbour, or every way when it is partly
  occupied itself.
- **Sight.** The same sweep as walls, for pieces whose `VisibilityBlockingData` blocks sight (the high recipe's
  does).

## The project

`EXP-59 small cover blocks` (URB_Bar, [exp59_project.py](../../tools/editor/examples/exp59_project.py), in the
editor's project store), a quick build with no warnings but the two expected (`cover-short` for D, `cover-thin` for
E). Six high cover blocks along the middle row of the pavement in front of the bar (y −192 to −96, top at 16), with
two free tiles between places and a free row on either side (overview (`EXP-59-overview.png`),
east (`EXP-59-east.png`), west (`EXP-59-west.png`)):

| Place | What stands there | Built as | The panel's prediction |
| --- | --- | --- | --- |
| F | control: a whole-tile high block, x 672 to 768 | `XComLevelActor_469` | no way into its tile; high cover in the 4 tiles round it |
| A | 48 × 48 in the middle of the tile x 384 to 480 (corner 408, −168) | `XComLevelActor_470` | units can't stand in the tile; high cover in the 4 tiles round it |
| B | a wall 8 through, a tile long, on the edge x 96 (from 92 to 100) | `XComLevelActor_471` | units stand on both sides; no crossing between the two tiles; high cover toward it on both; no sight across |
| C | 24 × 24 in the south-west corner of the tile x −288 to −192 (corner −288, −192) | `XComLevelActor_472` | units stand in its tile and walk past; no cover from it |
| D | a tile across, its top 40 over the pavement, x −576 to −480 | `XComLevelActor_473` | units stand in its tile and walk through it; no cover from it |
| E | a wall 2 through, a tile long, on the edge x −864 (from −865 to −863) | `XComLevelActor_474` | fills no tile and gives no cover, but no crossing between the two tiles (and maybe no sight across) |

Nearby: two disabled-parking signs stand at the kerb (south row), one between F and A and one just south-east of B.
They may give cover toward the south in the tiles beside them; read each shield's direction.

To play it: open `EXP-59 small cover blocks` in the editor (its last build is in place) and use Play in game.

## Run 1

What the run adds over the offline checks (west of a place is screen right in the overview, x falling):
1. **F (control):** its tile isn't a destination; a soldier on any of the four tiles round it gets a full shield
   toward it.
2. **A:** its tile isn't a destination. A soldier on each of the four tiles round it gets a full shield toward A.
3. **B:** both tiles beside the wall are destinations. A path from one to the other goes round the wall's ends (a
   move straight across costs more than one tile). A soldier on either tile gets a full shield toward the wall. With
   a soldier on one side and an alien on the other, the wall blocks the view.
4. **C:** its tile is a destination. Paths go past it as if nothing were there. No shield toward it from its own tile
   or from the tiles west and south of it.
5. **D:** its tile is a destination; a soldier can stand in the block and walk through it. No shield toward it.
6. **E:** both tiles beside it are destinations. A path from one to the other goes round it. No shield on either
   side. Note whether it blocks the view across.
7. Anything odd: a crash, a visible box, a unit standing at an odd height.

## Result

**Run 1 passed** (15 November 2026, played by hand), in the editor and the game, and B held as a wall, though
units could see and shoot through it. So the six places did what the panel says, B among them: units stood on both sides of the
8-unit wall and couldn't cross between the two tiles. Discord S8 (an invisible cover wall) is done by it
([F-113](../findings-register.md)).

Open: **sight across B.** Units could see and shoot across it. Two readings, not told apart by this run:
- **Leaning round its ends** (most likely). B is one tile long, and a unit beside a wall with high cover toward it
  steps out to either side ([line-of-sight.md](../native/line-of-sight.md), section 3), so it sees and shoots past
  the wall's ends, as past any short wall or a single high crate. The soldier in the run was up against it, and no
  longer high block was tried for sight.
- **A hidden high block doesn't stop sight at eye level.** The high recipe saves no `VisibilityBlockingData` (the
  class default, which blocks), and the game reads sight from the eye tiles' bits, one level above the floor
  (line-of-sight.md, section 2.3). No run has checked a hidden high block's sight yet (EXP-31 expected it, not
  played).

A check that tells them apart: a high wall three tiles long, a soldier two tiles back from its middle and an alien
two tiles beyond it, in line (no step-out reaches round the wall's ends).
