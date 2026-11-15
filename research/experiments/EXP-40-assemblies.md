# EXP-40: a car, a door with its frame and a ladder from other maps

Date: 11 November 2026. The game check of what [EXP-39](EXP-39-families.md) left out
(implementation plan, X9): assemblies (several pieces that are one
thing) and ladders, from maps other than the one edited. One piece of each stands in URB_Bar, in a baked build.

## What is built (offline)

- The project: [exp40_project.py](../../tools/editor/examples/exp40_project.py) writes it and builds it by the Build
  with the gates lifted (`car`, `door`, `ladder`: as `build.py --foreign-family` does). The pieces:

  | # | Family | Piece | Home map | Parts | What it brings |
  |---|---|---|---|---|---|
  | 1 | Car | an SUV with two doors open (`SUVAll`) | URB_OfficePaper_Terror | body, glass, two doors | 76 objects, 287 KB |
  | 2 | Door | a barn door in its frame (`DoorSwingSingleBarn`) | URB_SmallCemetery | leaf, frame | 88 objects, 72 KB |
  | 3 | Ladder | a drain pipe, seven storeys (`DrainPipeA_448`) | URB_ConvienienceStore_EWI | one | 20 objects, 34 KB |

- **The car is one copy of four pieces.** They are brought together, so they keep their references to each other
  (checked in the built map): the body's `HidingPartner` is the copied glass, and the glass's 16 fragment columns
  name the copied body and doors, nothing of the car's home map and nothing of the bar's.
- **The door** is its leaf and its frame, cloned together as a door of the bar's own is.
- **The ladder** stands on the bar's outer wall two tiles along from the bar's own ladder (`XComLadder_4`), turned
  as that one is (two quarter turns from how it stands at home). The compiler checked its climb against the bar's
  floors (foot tile [31, 33, 0], top on the roof), and the Build put the rebuild volume over its top tile first, as
  for a copy of the bar's own ladder.
- All three keep the pose rule on the bar's tile grid (no off-grid warning).
- A baked build, 149 seconds. Installed in the lab copy's test slot with `lab_install.py install` (here
  `<lab>\bake-fixtures\exp40`, record `URB_Bar_X40-20261111-151444.json`): the first mission of a new campaign plays
  `URB_Bar_X40`.
- Offline, the variant was exported by the viewer's exporter and opened in the editor page: all three draw. The
  shots below are of that export. It also draws the staged originals where they stood in their home maps (the tall
  pipe in the car park is the ladder's): they are in no actor list, and the game doesn't make them.
- A first try put the ladder at the nearest tile where the floor rule held, which was inside the bar, through its
  ceiling: the floor rule alone doesn't say a ladder is on a wall. The place was then chosen by hand.

## Where to look

Picture `EXP-40-run1-overview.png` (not in the repository): overview.
Picture `EXP-40-run1-carpark.png` (not in the repository): the car park.
Picture `EXP-40-run1-ladder.png` (not in the repository): the ladder.

## Run 1: the car and the door passed; the ladder could not be tried

Played by the user on 11 November 2026: "looks good", but the drain pipe stood on the ice box at its foot, so no
soldier could reach it. Cars and doors with a frame are switched on for every project
(`compiler.FOREIGN_ASSEMBLIES`), and the library was scanned again. Ladders wait for run 2.

What this run added, and nothing else needed checking:

1. **The map loads**, and all three draw with their own materials.
2. **The SUV** gives cover as the bar's cars do. Shot or caught in an explosion it burns and then blows up, its glass
   breaks, and its two open doors go with it. Nothing of it is left hanging.
3. **The barn door** opens for a soldier and blocks sight when shut; its frame stays when the door is open. It
   stands alone in the car park, so walking round it is expected.
4. **The drain pipe** shows a route up to the bar's roof for a soldier at its foot, and down again from the roof.
   The bar's own ladder beside it still works. (An ice box stands at its foot: if no route shows, that tile may be
   the reason, and the next run moves it.)
5. **A save and a reload** after the car is destroyed and the door opened bring everything back as it was left.

A piece that fails names its family: that one stays off and the others are switched on.

## Run 2: passed

Played by the user on 11 November 2026: "pipe is climbable looks good". Ladders are switched on for every project
(`ladder` in `compiler.FOREIGN_FAMILIES`), and the library was scanned again.

- The pipe stands three tiles further along the same wall, at [-48, 1296, 16] (foot tile [28, 33, 0], top on the
  roof), past the ice box; the nearest things on the ground there are a puddle decal and kegs three tiles on. In
  the user's screenshot of run 1 that is to the left of the ice box.
- A quick build (18 seconds; the user asked for no rebake), so the three pieces keep their home maps' light. Installed
  in the lab's test slot (here `<lab>\bake-fixtures\exp40-run2`, record `URB_Bar_X40-20261111-152626.json`).
- **To check:** a soldier at the pipe's foot is offered the route up to the roof, climbs it, and comes down again.
  Nothing else.

## Not in this run

- **Vans**: a van takes its own building (its floor volumes) along, which can't be brought from another map. They
  are listed in the library and can't be placed.
- **A quick build** of these: the same pieces without the relight; it builds (17 seconds) and was not exported.
