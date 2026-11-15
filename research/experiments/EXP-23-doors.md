# EXP-23: doors made in the map

Date: **8 November 2026**. Status: **runs 1 to 3 passed in the game (F-61, F-62)**: the door family builds since
(doors with a frame).
Plan: cars, doors and ladders, section 6.8. Tools:
[`native_copy.py`](../../tools/bake/native_copy.py) (`piece_box` with skeletal meshes, `edit_columns`,
`edit_floor_caches`), [`build.py`](../../tools/editor/build.py) `--family door`.

## Question

A door is two pieces: the leaf (an `XComInteractiveLevelActor`, skeletal) and its frame (an `XComDestructibleActor` at
the same place). Made in the map as one assembly, do a moved and a copied door work as the map's own do (open, kick,
break, sight, the cutaway, a save and reload)? Does a deleted door leave a clean open doorway?

## What the Build does for a door

- **The leaf's box** (G4, [T-18](../findings-register.md)): the leaf draws a skeletal mesh and saves an unused
  `StaticMeshComponent` with no mesh, so the box the copy's tiles and rebuild volume come from is the skeletal mesh's
  in its reference pose (closed). It has no lighting textures: it is lit live.
- **The wall's columns** (G8, [F-61](../findings-register.md)): a fracturing wall lists the pieces that go when each of
  its fragment columns breaks (`FragmentColumns(k).DestructibleCache`); a door's leaf and frame are in 8 to 12 columns
  of their wall. Every hidden piece leaves every column. A copy takes its original's listing, carried by the copy's
  move: each column that lists the original, moved as the copy moves, lists the copy in every column of a wall still
  in the map that it covers by half (`COLUMN_MATCH`), with the original's MinZ. No rule of the columns' own gives the
  bake's listing: over Bar's 289 listed pieces, a box of the piece padded by 0 to 192 units lists exactly the same
  columns for at most 42.
- **The floor's cutaway** (G7, [F-62](../findings-register.md)): every copy whose original is in a building floor's
  `m_aCachedActors` gets its original's entry in the floor whose floor volumes overlap the copy's box most (as far above it
  as the original's listing is above the original's floor). This serves M1's copies too.

## Run 1: URB_Bar

Bar's walls are fractured meshes with their doorways in them (each wall that holds a door is one
`XComDecoFracLevelActor`), and Bar has no doorway without its door: a slice at knee height through every thin wall
finds each 96-unit gap holding a door, and the wider gaps are shop windows. A fracturing piece doesn't build before
M3, so the run makes its openings with doors.

Project: [`exp23_doors_project.py`](../../tools/editor/examples/exp23_doors_project.py), "EXP-23 doors on the bar"
(`23e0a0b1-…`), variant `URB_Bar_EXP23Door_23e0`. Built with `build.py 23e0a0b1-2323-4d0a-8e23-3c4d5e6f7a23 --family
door`.

| Door (leaf, frame) | Edit | Where |
| --- | --- | --- |
| 7 (`XComInteractiveLevelActor_7`, `XComDestructibleActor_65`) | deleted | the inner wall's west doorway, (-1488, 672) |
| 6 (`_6`, `_60`) | moved 7 tiles along the inner wall into door 7's doorway | (-816, 672) to (-1488, 672) |
| 5 (`_5`, `_30`), the front door | copied 2 tiles east and 5 north, unturned, into door 6's old doorway | (-1008, 192) to (-816, 672); the original stays |
| 4 (`_4`, `_31`) | deleted: its doorway stays open | the west wall, (-1632, 816) |

**Offline** (build `URB_Bar_EXP23Door_23e0-20261108-143303`, 2 minutes):
- The compiler: 2 moved, 4 deleted, 2 added, two door assemblies (`move:XComInteractiveLevelActor_6`, translation
  (-672, 0, 0); `add:XComInteractiveLevelActor_5_copy2`, (192, 480, 0)).
- The columns: the inner wall (`XComDecoFracLevelActor_16`) drops 36 entries of hidden pieces and lists the two
  copies' leaves and frames in 34; the west wall (`_15`) drops 20, `XComFracLevelActor_24` 4.
- All four copies in floor 0's cutaway of `XComBuildingVolume_0`.
- The relight skips each leaf's empty `StaticMeshComponent` ("no LOD-0 texture lightmap"): there is nothing to light.
- Files: the variant map `144d9141c748…`, `Lighting_420115.tfc` `07ec512dce9e…`, the intro copy `658a1e9fa58c…`
  (first 12 hex digits of each SHA-256).
- Installed in the lab's test slot (`lab_install.py install`, deploy record
  `URB_Bar_EXP23Door_23e0-20261108-143517.json`).

**In the game** (the user drives; the lab copy). Marked editor shots, taken with
[`mark_shots.py`](../../tools/viewer/mark_shots.py) from [EXP-23-run1-shots.json](EXP-23-run1-shots.json): the
overview (`EXP-23-run1-overview.png`: the bar's ground floor, its east half boxed),
the inner wall (`EXP-23-run1-inner-wall.png`: marks 1 and 2) and the west wall (`EXP-23-run1-west-door.png`: mark 4).
1. The Skyranger lands (the intro copy).
2. Door 6 in its new doorway (mark 1): it opens and a soldier walks through; a kick opens it, once (F-33).
3. The copy of door 5 in door 6's old doorway (mark 2): the same.
4. Door 4's doorway (mark 4): open, a soldier walks through, and no "open door" action shows there (F-26).
5. A grenade at a door copy breaks it; breaking the inner wall beside a copy takes the door with it (F-61).
6. Line of sight through each copy, open and closed.
7. The cutaway: with a soldier inside the bar, the copies and their frames hide and cut down as the other doors do
   (F-62).
8. Save with one door open and one broken, reload: they stay so.
9. The copies' textures are sharp (a copy isn't in the level's list of skeletal textures, plan 2.4).

**Result (8 November, the user's run):** passed: "everything works as expected", over the checks above. No F9 shots
were taken.

## Run 2: URB_PoliceStation

The station's doors stand a level up (z 80, on a grid whose origin is at z -48), in fractured walls with their
doorways in them, as on the bar. One inner wall, `XComDecoFracLevelActor_11` (`PoliceStationWallD`, along X at y
-672), has two double doorways with no door, so this run also copies a double door into a real empty doorway, turned a
quarter.

Project: [`exp23_police_project.py`](../../tools/editor/examples/exp23_police_project.py), "EXP-23 doors at the
police station" (`23f0a0b1-…`), variant `URB_PoliceSt_Exp23D_23f0`. Built with `build.py
23f0a0b1-2323-4d0a-8e23-3c4d5e6f7b23 --family door`.

| Door (leaf, frame) | Edit | Where |
| --- | --- | --- |
| 2 (`XComInteractiveLevelActor_2`, `XComDestructibleActor_93`) | deleted | the back wall's south doorway, (-384, -528) |
| 95 (`_95`, `_1090`), a prefab's | moved 13 tiles along the back wall into door 2's doorway | (-384, 720) to (-384, -528) |
| 0 (`_0`, `_42`) | copied 11 tiles west and 25 north, unturned, into door 95's old doorway | (672, -1680) to (-384, 720); the original stays |
| double door 17 and 18 (frames 15 and 35) | copied a quarter turn round into WallD's west doorway (x -192 to 0) | halves at (-480, -912) and (-480, -816) to (-48, -672) and (-144, -672); the original stays |
| double door 19 and 20 (frames 13 and 14) | deleted: the doorway stays open | the west facade, y -1680 and -1584 |

**Offline** (build `URB_PoliceSt_Exp23D_23f0-20261108-145420`, about 4 minutes):
- The first build put door 95's copy and door 0's copy in no building floor: the station's floor volumes end on the
  back wall's line (x -384), so a door's centre there lies on their face. The floor is now the one whose volumes
  overlap the copy's box most (`floor_at`; `test_native_copy.test_a_door_copy_on_its_buildings_outer_wall_joins_that_floor`),
  and all eight copies join floor 0 of the station (`XComBuildingVolume_2`).
- The columns: WallD lists the double door's copies in 22 entries; the back wall (`XComDecoFracLevelActor_4`) drops
  36 entries of hidden pieces and lists door 95's and door 0's copies in 32; the facade (`_1`) drops 32.
- Files: the variant map `8c94495989b2…`, `Lighting_327589.tfc` `b4d8d9222ef3…`, the intro copies
  `90ad0bffecc6…` (Dropship) and `1a2497532ea0…` (Fastrope).
- Installed in the lab's test slot (`lab_install.py install`, deploy record
  `URB_PoliceSt_Exp23D_23f0-20261108-145817.json`): it plays the station's abduction record.

**In the game** (the user drives; the lab copy). Marked editor shots, from
[EXP-23-run2-shots.json](EXP-23-run2-shots.json): the overview (`EXP-23-run2-overview.png`: the station's west half),
the copy of door 0 (`EXP-23-run2-copy.png`: mark 2), door 95 and the turned double door (`EXP-23-run2-moved-and-turned.png`:
marks 1 and 3) and the facade (`EXP-23-run2-facade.png`: marks 4 and 5). The same checks as run 1, and:
1. The double door's copy (mark 3): both halves open, soldiers walk through, a kick opens it.
2. The deleted double door's doorway (mark 4): open, and no "open door" action shows there.
3. Door 95, a prefab's door, at its new place (mark 1): as the others.

**Result (8 November, the user's run):** passed: "done, everything was fine". No F9 shots were taken.

## Run 3: URB_ResearchOutpost (a floor above)

The cutaway upstairs (plan 6.4). The outpost (exported into the main cache, export 14) has its building with floors
above, `XComBuildingVolume_7` (floors 0 to 3), and two doors on its floor 2 (z 384): one in each of the long walls of
the telescope room on its roof (`XComDecoFracLevelActor_110` and `_112`, along X at y 1248 and 480). No doorway upstairs
is without its door (a knee-height slice at z 432), so the run makes its opening with a door again.

`CutdownFloor` in a floor's cutaway list names a floor of the building, and 0 names none: walls of floor 0 that rise
through floor 1 name 2, walls of floor 2 name 3, and doors name none on any floor (the cutaway lists of Bar, Police
Station and the outpost). So a copy keeps a 0 as it is, and only a floor it names moves with it
(`native_copy.entry_for`).

Project: [`exp23_outpost_project.py`](../../tools/editor/examples/exp23_outpost_project.py), "EXP-23 doors upstairs at
the outpost" (`23a0a0b1-…`), variant `URB_Research_Exp23D_23a0`. Built with `build.py
23a0a0b1-2323-4d0a-8e23-3c4d5e6f7c23 --family door`.

| Door (leaf, frame) | Edit | Where |
| --- | --- | --- |
| 26 (`XComInteractiveLevelActor_26`, `XComDestructibleActor_303`) | deleted | the telescope room, (1680, 1248, 384) |
| 25 (`_25`, `_302`) | moved a tile east and 8 north into door 26's doorway, on the same floor | (1584, 480, 384) to (1680, 1248, 384) |
| 0 (`_0`, `_0`), the other building's ground-floor door (floor 0 of `XComBuildingVolume_4`) | copied 35 tiles east, 13 north and 6 storeys up into door 25's old doorway | (-1776, -768, 0) to (1584, 480, 384); the original stays |

**Offline** (build `URB_Research_Exp23D_23a0-20261108-152827`):
- All four copies join floor 2's cutaway of `XComBuildingVolume_7` (door 0's copy from floor 0 of another building).
- The columns: the telescope room's walls drop the hidden doors (18 entries each) and list the copies (18 and 16);
  `XComFracLevelActor_57` drops 96 and lists door 25's copy in 48.
- Files: the variant map `677816f1ff5d…`, `Lighting_12624707.tfc` `626eb3dbc21a…`, the intro copy `c78b3cb43b6c…`.
- Installed in the lab's test slot (deploy record `URB_Research_Exp23D_23a0-20261108-152954.json`). The outpost has one
  record, a Council assault (`CouncilType=eFCMType_Assault`, streaming `URB_ResearchOutpost_Stream`); the slot plays it
  as the first mission of a new campaign.

**In the game** (the user drives; the lab copy). Marked editor shots, from
[EXP-23-run3-shots.json](EXP-23-run3-shots.json): the overview (`EXP-23-run3-overview.png`: the telescope room boxed,
door 0 marked where it stands), door 25 in its new doorway (`EXP-23-run3-north-wall.png`: mark 1) and
the copy of door 0 (`EXP-23-run3-south-wall.png`: mark 2).
1. Both doors open, soldiers walk through, a kick opens each once.
2. With a soldier on each floor in turn: the copies and their frames hide with the floors above the soldier's and cut
   down with the walls, as the telescope room's other pieces do.
3. Save and reload, one door open.

**Result (8 November, the user's run):** passed: "checked, all good". No F9 shots were taken.
