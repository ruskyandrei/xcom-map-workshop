# EXP-45: a tower of three storeys and a roof, every deck walked on

Date: 11 November 2026. Stage B2 of the prefabs and buildings plan: a building of
several storeys made from nothing: three storeys and a roof, walkable on all of them.
[EXP-44](EXP-44-hut-building.md) showed that a Build-made building hides its roof and cuts its walls down. This run
asks what a storey adds: floor a soldier can stand on, a way up, the cursor's floors, and each floor hiding the ones
above it. The stage is the blank map, 36 by 36 tiles and 768 units (four storeys) high.

## What is built (offline)

- **The tower**, four tiles by six, put together from pieces of three other maps (33 pieces):
  - **walls**: URB_Demolition_EWI's site office walls, a storey (192) high, all of them pieces that cut down: plain,
    with a window, and one with a doorway (the way in, on the west side of the ground storey). Eight to a storey;
  - **decks**: CSmallScout_NukedCity's van roof, a slab four tiles by two and 16 thick, two to a deck. Each deck
    covers four of the six rows and leaves two open as the way up: the second storey's deck and the roof deck cover
    the south end, the third storey's the north end. The decks' tops are at 192, 384 and 576, on the storeys' levels
    exactly, as the ground's is;
  - **ladders**: URB_PierA_Asian's 192 ladder, three of them, inside: ground to the second storey (north end),
    second to third (south end), third to the roof (north end).
- **The building**: one, "Tower", of four floors with one box each: 0 to 184, 184 to 376, 376 to 568, 568 to 760.
  Each box starts 8 under its deck's top, so a deck is its own storey's alone and the walls under it reach into it.
- **Read back from the built map** (`python -B tools/bake/buildings.py <the built map>`):

  | Floor | Box (z) | Pieces listed |
  |---|---|---|
  | 0 | 0 to 184 | the 8 ground walls and ladder 1, each with `CutdownFloor` 1; four of the map's ground planes |
  | 1 | 184 to 376 | the 8 walls of storey 2 and ladder 2, each with `CutdownFloor` 2; the two slabs of its deck |
  | 2 | 376 to 568 | the 8 walls of storey 3 and ladder 3, each with `CutdownFloor` 3; the two slabs of its deck |
  | 3 | 568 to 760 | the two slabs of the roof deck |

- **The cursor's storeys**: the blank map gets its cursor volumes from URB_Bar, whose heights are the bar's own
  (0, 210, 402, 594). The Build's shell stage now makes them even storeys of 192 from the grid's bottom: read back
  as 0 to 192, 192 to 384, 384 to 576 and 576 to 768, floors 1 to 4. So each deck is the bottom of a cursor storey.
- **The ladders' climbs**, as the compiler worked them out (foot tile, top tile): (27, 28, 0) to (27, 27, 3);
  (28, 25, 3) to (28, 26, 6); (27, 28, 6) to (27, 27, 9). The compiler used to refuse a ladder whose end has no
  floor in the map as it ships. It now counts the floor a flat piece of the project is expected to give, and warns
  that the climb depends on it (`ladder-new-floor`, three here).
- A quick build (lighting not baked), 14 seconds. `CB2_MP_Blank_X45`, in the editor's builds folder as the
  project's last build.

## Where to look

Picture `EXP-45-overview.png` (not in the repository): the tower on the blank map.

Picture `EXP-45-floor1.png` (not in the repository): the ground storey.

Picture `EXP-45-floor2.png` (not in the repository): the second storey.

Picture `EXP-45-floor3.png` (not in the repository): the third storey.

Open the project **EXP-45 tower** in the editor, then Project, Play in game. (To rebuild from the script:
`python -B tools/editor/examples/exp45_project.py <scratch folder> --store`.)

What this run adds, all of it new:

1. **Each deck is floor.** A soldier can be sent onto the second storey's deck (6), the third's (8) and the roof
   deck (3), and onto every tile of them, not only the one a ladder arrives at.
2. **The ladders climb.** Ladder 1 (5) from the ground to the second storey, ladder 2 (7) to the third, ladder 3
   (9) to the roof. Each should show as a route when a soldier is ordered to a deck above.
3. **The cursor climbs the floors.** With the mouse wheel over the tower the cursor should go up and down four
   floors, and land on the deck of each.
4. **Each floor hides the ones above.** With a soldier (or the cursor) on the ground storey, everything above goes
   and the ground walls cut down. On the second storey, the third storey and the roof go, the second storey's walls
   cut down, and the ground storey stays whole below. The same one storey up. On the roof nothing hides.
5. **Outside, the tower is whole.**
6. Anything odd: a deck tile that can't be stood on, a soldier falling through or floating, a ladder with no route,
   the cursor skipping a floor or sticking to a deck above, a storey that hides when it shouldn't.

Not looked at in this run: a save and a reload (F-89), the light (not baked), stairs (the game has no stair
volumes, and how the rebuild makes a ramp from a stair piece has not been read).

## Known doubts before the run

- **The van roof as floor.** It is a plain piece with a collision slab of its own, but whether the game's rebuild
  makes floor of it is what item 1 shows. Copies of the bar's upstairs floor strip did get floor (F-71).
- **A deck exactly on a level's edge** (192.0). The ground of the blank map lies the same way at 0, and is floor.
- **Standing room on the roof**: 192 units from the roof deck to the grid's top.
- **The slabs don't quite meet**: each is 377 by 190 against a place of 384 by 192, so there are slits of a few
  units between them and at the walls.
- The walls' outer faces were not chosen: a wall may show its inner side outwards.

## Result: passed

Played by hand on 11 November 2026: everything worked as expected. So:
- a plain flat piece from another map (the van roof) is floor after the game's rebuild, on every tile, at three
  heights and on a level's edge exactly;
- ladders between decks the project adds climb, one above the other;
- the cursor goes through four floors on a map given even cursor storeys of 192;
- a building of four floors hides each floor above the one looked at and cuts that storey's walls down. This was
  also the first building of more than two floors.

After the run the editor's Climbs line for a selected ladder counts the project's own flat pieces, as the compiler
does ("Climbs, by a floor this project adds"); it said "Won't climb" for the tower's ladders before.

Not covered: several boxes on one floor, a save and a reload (F-89), baked lighting, stairs, a building on a map
with cursor volumes of its own.
