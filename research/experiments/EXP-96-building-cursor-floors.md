# EXP-96: a building's floors as the cursor's (the building cursor floors plan)

Date: 23 November 2026. Status: **passed** (runs 1 and 2, unattended, the game-test skill; F-164). Part of the building
cursor floors plan (private/plans/done/building-cursor-floors-plan.md), stage C5, branch `building-cursor-floors`.
Checking only what is new.

## What is new

A building made in the editor may have its floor boxes as the cursor's floors (`cursorFloors`, the Buildings view's
"Cursor stops at its floors"). The Build takes the map's cursor volumes out over the building's footprint, stands them
again round it, and lays one volume for each of its floors over it: floor k from 2 under the bottom of its box to where
the next floor starts, the last to its box's top, numbered as the building's floor
([made_cursors.py](../../tools/bake/made_cursors.py)). The game's cursor takes its floors from the cursor volumes at its
place alone, and cuts every building at the top of the volume it is in
([F-88](../findings-register.md), [building-cutaway.md](../native/building-cutaway.md), EXP-80).

## The project

A mapper's reported project (a boat built from other maps' pieces on a cleared EWI_ChryssalidHive, 18 levels), whose
mouse wheel was to stop on the hold, the deck, the cabin and the cabin's roof. Kept in the lab folder, not in the
repository: `<lab>\exp96\EXP-96 boat floors.json`, its one building given four floor boxes over the whole boat
(x -6144 to -1920, y 1152 to 2880) from the boat's walking surfaces: the hold at -106, the deck at 278, the raised cabin
floor at the stern at 406, the cabin roof at 598, the last up to 768; ticked. Built with `--quick` (no lighting baked:
a cursor check needs none) and staged in the LWR 2.x lab copy with `lab_install.install(..., game=<the lab copy>)`.

The build's cursor volumes over the boat (its manifest's `madeCursors`):

| Floor | Volume | Walking surface |
| --- | --- | --- |
| 1 | -108 to 276 | the hold, -106 |
| 2 | 276 to 404 | the deck, 278 (the steps at the stern 342) |
| 3 | 404 to 596 | the cabin floor, 406 (a platform amidships at 470) |
| 4 | 596 to 768 | the cabin roof, 598 |

Round the boat, the cleared map's eight even storeys from -192 (192 each, to 1344) stand again on the grid's strips the
boat does not cover. Game tiles count from (-6241, 1151, -193).

## Run (hidden game, `--map`, the test squad, no aliens)

1. **Start floor**: the squad lands on the deck near the stern; the cursor starts on floor 2 (requested 1), its camera
   floor 276 and cutdown 404.
2. **The wheel over the cabin** at (-2530, 1980): floors 1 to 4 read camera/cutdown -108/276, 276/404, 404/596,
   596/768; the cursor on the hold, the cabin floor and the roof; a fifth step stays on floor 4.
3. **The cutaway follows the stops**: floor 1 the hold only; floor 2 the deck, the cabin cut away; floor 3 the cabin,
   its roof cut away; floor 4 everything.
4. **The deck** at (-3490, 1980), floor 2: 276/404, the cursor on the deck.
5. **On and off the boat**: the cursor off the boat on the map's sixth storey, carried onto the cabin without a floor
   change, then one step down; a soldier still walks to a deck tile on floor 2; off the boat again on floor 2, the
   map's 0/192.

## Result

### Run 1, the boat (23 November 2026)

One hidden run in the LWR 2.x lab copy (the user's own LWR v3 campaign game open beside it, not touched). Pictures and
the agent's notes in `<lab>\hidden-runs\exp96-boat-floors`; the cursor's readbacks below are the game log's.

- **The squad came down on the water**, at a landing outline north of the boat (y 3311 to 3695, past the grid's
  edge at 2879): "Extended Base tile is not a floor tile" for each soldier. A bare `--map` start plays none of the
  project's mission lines; not looked at further here. One soldier was put on the deck (TeleportToCursor) for the
  checks that needed one.
1. **Start floor: passed** (second take). With the soldier on the stern deck (z 345) and reselected, the cursor is on
   floor 2: requested 1, camera floor 276, cutdown 404. Before that, with the cursor resting over the boat at the
   start, it read the boat's floor 1 (-108/276).
2. **The wheel over the cabin: passed.** At (-2545, 1967) the four stops read -108/276, 276/404, 404/596 and 596/768,
   the boat's volumes, the cursor at -42 (the hold), 338 (floor 2: no deck under the cabin, it rests at about the
   deck's height), 472 (the cabin floor) and 662 (the roof); a fifth step stays on floor 4.
3. **The cutaway follows the stops: passed for floors 1, 2 and 4; floor 3 as the boxes have it.** Floor 1: the hold
   alone, the deck and cabin cut away. Floor 2: the deck drawn, the cabin cut at deck height. Floor 4: everything.
   Floor 3: the cabin drawn and the rails and flags on its roof cut, but its roof slab drawn: the slab's body (564 to
   598) lies in floor 3's box (406 to 598), so the game lists it on floor 3 (F-87's rule: a piece counts for each floor
   it reaches more than 20 under the top of). To cut the roof away on the cabin's stop, floor 4's box starts under the
   slab (560); the guide says so.
4. **The deck: the volume passed.** At (-3505, 1967) floor 2 reads 276/404; that row is an opening in the deck over
   the hold, so the cursor rests on the hold (-42); four tiles south, (-3505, 1583), and on the stern deck it reads
   342.
5. **On and off the boat: not done.** Off the boat there is only water, which the mouse cursor never lands on, so it
   stops at the boat's edge (x -1969, y 2878) on every floor; the map's sixth storey could not be had. A soldier still
   walks across the deck on floor 2 (12 tiles, to (-3409, 1583, 345)). Run 2 does the rest on URB_Bar.

So over the building the game takes its cursor floors as the Build wrote them: one stop a floor at the boxes'
heights, and the cutaway follows the stops.

### Run 2, a tower on URB_Bar

[exp96_bar_project.py](../../tools/editor/examples/exp96_bar_project.py): a building of two floors on the bar's lot
(x -1728 to -1344, y -1056 to -768, the ground at 0), floor 1 from 0 to 160 and floor 2 from 160 to 352, ticked; its
cursor floors -2 to 158 and 158 to 352, the bar's four (0, 210, 402, 594) round it. Built quick, staged in the lab
copy as `URB_Bar_X96`. Tiles count from (-2785, -1921, -1). Pictures and notes in `<lab>\hidden-runs\exp96-bar-tower`;
the readbacks are the game log's. The ground reads 64.

1. **The wheel over the tower: passed.** At (-1585, -913): floor 1 (requested 0) cutdown 158; a step up 158/352; one
   more stays on floor 2. (The camera floor read 0 on the first reading, carried from the bar's floor 1 the cursor
   came from: the lag below; -2 after a step.)
2. **Off the tower, a floor it lacks: passed.** At (-1873, -913) on the bar's floor 4: 594/768.
3. **Carried onto the tower on that floor (the open question)**: the floor number stays (requested 3), the cutdown
   becomes the tower's top (352), the camera floor stays at 594; the cursor rests on the ground in the tower; nothing
   looks stuck.
4. **Steps down from there: passed.** The first goes straight to the tower's floor 2 (158/352), the second to its
   floor 1 (-2/158), a third stays.
5. **A move: passed.** A soldier walks four tiles onto the tower's ground at (-1489, -817).
6. **Off again: passed** on the bar's floor 2 set there (210/402). Carried from the tower on floor 2 without a step:
   cutdown 402 (the bar's), camera 158 (the tower's): the lag.

**The lag** (seen in checks 1, 3 and 6): carried across the tower's edge without a step, the cutdown height follows
the new place's volume at once and the camera floor height keeps its last value until the next step. That is the
game's script on any map whose cursor volumes differ by place (`CursorSnapToFloor` in mouse mode sets only the cutdown
height; the camera's changes only on a step): [F-164](../findings-register.md).

## Conclusion

Passed. The game takes a building's own cursor floors as the Build writes them: one stop of the wheel for each of the
building's floors at its boxes' heights, the cutaway following the stops, the map's floors round it, and the cursor
carried on and off it on any floor without sticking. Two things for the user's boxes, both said in the guide: a roof's
box starts under its slab, and each floor's box at the floor's walking surface. With this, a new building made in the
Buildings view starts with the tick on (the plan's decision D2).
