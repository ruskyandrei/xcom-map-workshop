# EXP-50: the map's own buildings edited in place, on Bar

Date: 13 November 2026. Step E6 of the map buildings plan: the one
game run of the plan. Earlier runs played buildings made from nothing (EXP-44, EXP-45), volumes resized by
`DrawScale3D`, and vans' buildings taken out (EXP-24). This run adds:
- the map's own pieces listed in a building the Build rewrote;
- a floor volume of the map stretched in place;
- a building of the map, not a van's, moved with its own volumes.

## What is built (offline)

The project **EXP-50 map buildings**, saved in the editor's store, is built by
`python -B tools/editor/examples/exp50_project.py <scratch folder> --store`. It is a quick build: the lighting is not
baked. It took 15 seconds and gave `URB_Bar_X50`, the project's last build in the editor's builds folder.

- **The bar** (XComBuildingVolume_0): its plain ground-floor box XComFloorVolume_14, in front of the bar's east end,
  is stretched four tiles south, from y 0 to -384. That covers the pavement and the first row of the car park.
  - The Build stretched the map's own volume (`stretched: XComFloorVolume_14`). The other seven volumes were kept.
  - 408 pieces keep what the map saved for them.
  - 2 pieces are listed on the ground floor by the rule, both standing in the new part: the handicap street sign
    (XComDestructibleActor_10) and the parked red car (XComDestructibleActor_63).
  - The upper floors' lists are unchanged.
- **The sign** (XComBuildingVolume_2): the business sign on the pavement south of the bar. It is a building of two
  floors that lists the sign on its upper floor. It is moved eight tiles west along the pavement, with the sign
  itself (XComLevelActor_25).
  - The Build moved the building's own two volumes, XComFloorVolume_8 and _6.
  - The sign's copy (XComLevelActor_469) takes the original's entries on both floors, and the original is hidden.
  - At the new place, the ground floor lists by the rule the pavement, the bushes and the planter standing in it.
  - East of the sign is the landing zone. A first try moved the sign there, and the grounded Skyranger then stood in
    its boxes.
- **Read back from the built map** (`buildings.survey`):
  - the vans' four buildings are as the map has them;
  - the compiler gave no warnings.
- Bar has no third building that can be edited (the others are vans' or have no floors), so none is deleted here.
  Taking a building out of the level is what vans' buildings have had since EXP-24.

Picture `EXP-50-overview.png` (not in the repository): overview.

Picture `EXP-50-bar-floor1.png` (not in the repository): the bar at floor 1.

Picture `EXP-50-sign.png` (not in the repository): the sign.

## What to look at

Open the project **EXP-50 map buildings** in the editor, then Project, Play in game.

1. **The stretched part cuts the bar away.** Move a soldier onto the pavement in front of the bar's east end, by the
   handicap sign and the red car (mark 1). The bar's upper floor and roof should cut away as they do with a soldier
   inside.
2. **Inside the bar, as before.** A soldier inside (mark 2) should see the roof cut away as on the plain map.
3. **The sign hides at its new place.** A soldier at the sign's foot, on the pavement among the bushes (mark 3),
   should make the sign hide. That is the sign building's upper floor cutting away.
4. **Nothing at its old place.** A soldier where the sign stood (mark 4) should see nothing hide.
5. Anything odd: a crash on loading, a building that hides when it shouldn't, or the bar's lower walls cut down in
   the new part.

Not looked at in this run: baked lighting (quick build), a save and a reload (F-89), and a building deleted.

## Result: passed

Played by hand on 13 November 2026 and checked in the game and in the editor: good. So:
- a floor volume of the map stretched in place (its own Location and DrawScale3D) cuts the building away over the new
  part, and the rest of the building cuts away as before, with the map's own listings kept;
- a building of the map moved with its own volumes, and its piece moved with it, cuts away at the new place: the
  copy's carried entries work in the game;
- the map loads and plays with both edits.

Not covered: a building of the map deleted (none on Bar to delete; the same level removal as vans' buildings,
EXP-24), a notched volume replaced by a plain one, a floor added to a map building, baked lighting, a save and a
reload (F-89).
