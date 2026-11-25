# EXP-32: invisible floors, and cover blocks of any height

Date: 10 November 2026. After cover blocks worked on level ground (EXP-31 run 3): could a cover block be a floor
tile? Then an invisible floor to try, with width and length set like a block's, and a height
setting on cover blocks (a 1 × 2 block had been stood on end to make a tall one).

## What changed (offline)

- The editor: the Add panel's kind **Invisible** (was Cover) has **Cover block** and **Invisible floor**. A block's
  section has **Height** (1 to 8 tiles: each tile past the first adds 96 to the top, so two tiles stand 192 high, as
  the block on end did); a floor's has width and length only, its height being its Z (its top). A project saves
  `cover` {width, length, type, height}, `type` high, low or floor; the first records ({width, length, height: high or
  low}) open as one tile tall and save in the new form.
- The compiler (`COVER_RECIPES`): heights for `floor` [-2, 0] (a plate two units thin under its location),
  `maxHeight` 8, `heightStep` 96, `flat` [floor] (a floor is one tile tall only).
- The Build (`tools/bake/cover_blocks.py`): a floor is one hidden XComLevelActor per tile cell, at the cell's centre a
  unit under the top, on a shared 96 × 96 × 2 box mesh with its convex BodySetup; it saves none of the blocks'
  `CoverForceFlag`, `bCanClimbOnto` False or `bIsValidDestination` False (so the class defaults: a destination one can
  climb onto). A tall block is one actor, as before, its box taller.
- Why a floor is made this way, from the native code ([native code notes](../native-code-notes.md), "How the rebuild
  decides a tile is occupied"):
  - the tile rebuild's floor trace (a line from 30 above a tile's position down 64) takes a hit on an actor with
    `bCanStepUpOn` and a normal steeper than 0.7 as the tile's floor, and needs the mesh's simple collision (the
    BodySetup);
  - its occupancy test skips a level actor whose mesh is under 4 units thick unless it is 384 units across or more:
    a plate a tile across and 2 thin is skipped, so it gives a floor without filling the tile it carries. A floor 4
    tiles across in one piece would not be, hence one actor per tile.
- Checked: `test_cover_blocks.FloorsAndTallBlocks` (a 3 × 2 floor turned a quarter: six plates at the tiles' centres,
  hidden, without the cover and destination properties, their box the floor's; a block two tiles tall, one actor 204
  high), compiler tests (a tall block's and a floor's boxes, first records, refusals), `check_cover` in the browser
  smoke test (both entries, the Height field, a floor's panel and plate, saving), a first-form project opened on a
  test server. A scratch copy of `farm+` with a 3 × 2 floor (top at 96, over the ramp by the UFO) and a block two
  tiles tall built quick: six plates at the tiles' centres, every reference in range.

## Run 1: the game takes the plate as a floor; the tile below it gets half cover

Floors are placed in the editor and played (quick build). Things to look at:
- a floor in the open at ground height (control: nothing should change);
- a floor over sloped tiles (the farm's ramp by the UFO), its top level with the ramp's top: is it a flat floor in the
  game (F-81's way round), and does a soldier on it get cover from a block beside it?
- a floor as a ledge or bridge at a height a soldier can walk onto from (or reach by a ladder): can a soldier stand on
  it, and is it a valid destination?
- a block two tiles tall: high cover beside it, and it blocks sight.

Unknown before the game: exactly where a tile's position sits in its level (the floor trace runs from 30 above it
down 64; the function that gives it, world data vtable slot 0x158, wasn't read), so a plate's top may need to be near
the bottom of a level (as the maps' own floors are) to be found; whether a hidden floor confuses the cursor (the mouse
trace doesn't skip hidden pieces, so it should land on it).

Result (10 November, `farm+` played by hand with floors over the ramp by the UFO):
- The floors work: soldiers on them stand on a flat floor and get cover, which they don't on the ramp itself (F-81).
- Side effect: the tile downhill of a floor gets half cover from it, as from a step. The question was how low a floor
  can go and still work: a low one may leave the soldier on the ramp and a high one act as a step.
- Measured in the editor afterwards: the three floors' tops stood 0.2, 10.8 and 8.1 units over the ramp at
  their tiles' centres; the ramp rises about 50 units a tile there (25.1 and 75.1 at one floor's downhill and uphill
  edges).
- Read from the native code since ([native code notes](../native-code-notes.md), "Where a tile's floor and cover are
  looked for"): a tile's position is its centre, 32 over its level's bottom, so the floor trace is one line through
  the tile's centre from 62 over the level's bottom to 2 under it. A plate is the tile's floor when its top is over
  the ground at the centre and at most 62 over the level's bottom, so a top 1 unit over the ground at the centre is
  as low as it goes. The half cover comes from the tile below's cover trace (52 over its floor, 124 sideways) hitting
  the plate, which no height in that range avoids on this ramp: F-82, fixed with `bIgnoreForCover`.
- The editor since: a floor placed from the Add panel goes 1 unit over the ground at its first tile's centre; its
  section says how far its top stands over the ground at each tile's centre (or that it is below it), and **Fit to
  ground** puts it back 1 unit over the highest.

## Run 2: no step cover; floors snapped to the drawn ground aren't found

Rebuilt with the floors ignored for cover (F-82's fix), played by hand (10 November).
- First try: three floors placed with the editor's new snap (1 unit over the ground at the tile's centre) gave no
  cover (the shot shows the cursor beside the rock with no cover shields).
- Raised a little by hand, they worked, with cover shields by the rock, and the tile below a floor
  no longer got cover from it (F-82 verified).
- Measured afterwards: the raised floors' tops stand 6.3, 6.1 and 4.8 over the drawn ramp, but 1.1, 4.5 and 2.2 over
  the ramp's collision hulls, which stand 5.2, 1.6 and 2.6 over the drawn ramp at those tile centres. The game traces
  the hulls, so a floor 1 unit over the drawn ramp was inside them (F-83). The lowest a floor works is just over the
  collision at its tile's centre: 1.1 over it worked.
- The editor since: the ground of an invisible floor is the game's collision (`collision.json`), so a floor placed
  from the Add panel, its readout and Fit to ground go 1 unit over the hulls. On a test server the page's collision
  ground at the three tile centres is 86.15, 49.64 and 86.15 (the hulls' own, read offline), and Fit to ground puts the
  floors at 87.15, 50.64 and 87.15.

## Run 3: floors fitted to the collision are found

Floors were placed or fitted over the ramp with the editor reading the collision, rebuilt and played (10
November): that works. Floors 1 unit over the ramp's collision are the tiles' floors, and soldiers on them get
cover (F-83 verified).
