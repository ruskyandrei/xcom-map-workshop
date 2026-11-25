# EXP-25: the preview's maps, every kind of edit, played through

Date: **8 November 2026**. Status: **done. Runs 1 (Police Station), 2 (ForestTrench) and 5 (Truck Stop) passed in the game; runs 3, 4 and 6
were checked offline, with no doubt left that needs the game (from run 3 on, a map is played only where an
offline check leaves one). Two faults found and fixed on the way (F-67, the farm project's map name); one limit
recorded (F-66).**
Checklist: preview release, item 1; plan: cars, doors and ladders,
step 7. Tools: the editor's Build ([`build.py`](../../tools/editor/build.py)), every family switched on.

## Question

Each map of checklist item 1 gets one project with a piece of each kind the preview builds: a moved, a deleted and a
copied piece, a collectible where the map has one, and a copy of each assembly family it has (ladders, doors, cars,
vans). Built with no family flag, installed and played through a whole mission, does each map work as the user would
play it?
- copies block and give cover; a deleted piece's tiles open;
- the families' copies work as their EXP runs found (EXP-22 ladders, EXP-23 doors, EXP-24 cars and vans);
- the landing intro plays; save and reload; the mission can be finished;
- the original map still plays.

**The checks are short from run 2 on** (8 November, after run 1). Every family and kind of edit has passed its own
runs, so each map's check is a look at what is new there: the map's reason in the table below, the landing, the
edits in place. One overview shot, with a close-up only where something new needs pointing at.

Until now each family's runs edited that family alone; these projects are the first to build them together. The
projects are in [`exp25_projects.py`](../../tools/editor/examples/exp25_projects.py), one per run
(`python tools/editor/examples/exp25_projects.py <run>`).

Doors without a frame (UFO and alien doors, and the farm's barn doors) are still refused (plan 6.5): ForestTrench's
and the farm's doors are all of that kind, so their projects copy none. A run that qualifies them is its own step.

| Run | Map | Why (checklist item 1) | Families it has |
| --- | --- | --- | --- |
| 1 | URB_PoliceStation | rebuild volume cloned from `XComNoSpawnVolume` (F-59); Dropship and Fastrope intros | doors, cars, vans |
| 2 | CLrgScout_ForestTrench | a crashed UFO: power cores as collectibles, alien wreck, `patch_clean_*` stubs | none that builds (its doors have no frame) |
| 3 | CSmallScout_Farm | rebuild volume cloned from `XComCursorVolume` (played already: EXP-22 run 2) | ladders, cars (its doors have no frame) |
| 4 | URB_Demolition_EWI | rebuild volume cloned from `GameCameraBlockingVolume` (it has no brush: `XComCursorVolume` now, F-67) | ladders (drain pipes), cars (its doors have no frame) |
| 5 | URB_TruckStop_EWI | Fastrope intro only | ladders (drain pipes), cars (doors too, but no free doorway but a garage's) |
| 6 | URB_StreetHurricane_Terror | a terror and council map | cars (its ladders are the moving vans', which climb by patch helpers: F-66) |

## Run 1: URB_PoliceStation

Project: `exp25_projects.py police`, "EXP-25 the police station, every kind" (`25a0a0b1-…`), variant
`URB_PoliceSt_Exp25_25a0`, on export 16. Built with `build.py 25a0a0b1-2525-4d0a-8e25-3c4d5e6f7a25`, no `--family`.
Police Station has no collectible and no ladder.

| Piece | Edit | Where |
| --- | --- | --- |
| wooden bench `XComDestructibleActor_55` (the lobby, floor 2) | moved 2 tiles south | (-96, 820) to (-96, 628) |
| wooden bench `XComDestructibleActor_57` beside it | deleted | (79, 820) |
| utility box `XComDestructibleActor_278` | copied into the car park west of the station | from (912, 1740) to (-1104, -756) |
| dumpster `XComDestructibleActor_169` | copied into the street east of the station | from the fenced corner (-1664, -2384) to (1408, -464) |
| the west facade's double door (leaves `XComInteractiveLevelActor_17` and `_18`, frames `_15` and `_35`) | copied a quarter turn round into the inner wall WallD's east doorway, which has no door (EXP-23 run 2 used its west one) | halves at (336, -672) and (432, -672) |
| compact car `XComDestructibleActor_1077` (glass `XComFracLevelActor_201`) | copied a quarter turn round, east along the south street | from (962, -2496) to (1440, -2302) |
| delivery van (cab `XComDestructibleActor_1088`, 7 parts, its building) | copied a quarter turn round into the street south of the station | from (-1058, -1356) to (108, -2114) |

**Offline** (build `URB_PoliceSt_Exp25_25a0-20261108-185406`, 6.6 minutes, with three exports running beside it):
- The compiler: 1 moved, 1 deleted, 15 added (two props, the double door's two halves with their frames, the car's 2
  pieces, the van's 7), four assemblies, no errors or warnings.
- Each copy has its own rebuild volume seeding its tiles (the bench's 29, the car's 64, the van's 166 up to its roof,
  the door halves' 11 and 2, the dumpster's 43, the utility box's 90); the hidden benches' tiles are rebuilt by
  volumes of their own.
- The double door's copies join three walls' fragment columns (WallD 22 entries, `XComDecoFracLevelActor_0` 4,
  `XComFracLevelActor_10` 8), and the east wall `XComDecoFracLevelActor_13` drops 16 entries of the hidden benches.
- The moved bench and the door copies are in the station's cutaway (`XComBuildingVolume_2`, floor 0).
- The car's and the van's glass carried their 6 columns each. The van copy's building is `XComBuildingVolume_29` at
  (158, -2114, 380), turned, with floor volumes `XComFloorVolume_65` and `_66`; it dropped a brick pile under the
  original (`XComLevelActor_219`).
- The relight: 126 lighting textures written, 24 shadow maps.
- Files: the variant map `aa37e48f0584…`, `Lighting_5660979.tfc` `528add80b411…`, the intro copies `420e62c3113f…`
  (Dropship) and `947f30aa923b…` (Fastrope).
- Installed in the lab's test slot (deploy record `URB_PoliceSt_Exp25_25a0-20261108-190115.json`).
- The compact car's copy stands some 70 units west of the grounded Skyranger (`XComLevelActor_664`, shown by the
  map's Kismet) and 580 from the drop zone marker.

**In the game** (played by hand; the lab copy). Marked editor shots, from
[EXP-25-run1-shots.json](EXP-25-run1-shots.json): the overview (`EXP-25-run1-overview.png`),
inside the station (`EXP-25-run1-inside.png`: marks 1, 2 and 5), the south street (`EXP-25-run1-south.png`: marks 6
and 7), the utility box (`EXP-25-run1-props.png`: mark 3) and the dumpster (`EXP-25-run1-dumpster.png`: mark 4).
1. The landing intro plays.
2. The moved bench (mark 1) gives low cover where it stands now; where the deleted one stood (mark 2) is open floor.
3. The utility box and dumpster copies (marks 3 and 4) give high cover and block the way.
4. The double door copy (mark 5): it opens, a soldier walks through, a kick opens it.
5. The compact car copy (mark 6): cover; its glass breaks; it burns and explodes.
6. The delivery van copy (mark 7): a soldier walks into its cargo area, and its roof cuts away over them.
7. Save during the mission and reload.
8. Finish the mission.
9. Then the original Police Station still plays (the slot put back to it).

**Result (8 November, run by hand):** passed. A short look: the game log (19:08 to
19:10) has the mission up at 26 s and the exit at 87 s, no save, no `CachedFrag` or `REBUILD PATHING!` lines, and no
warning naming the copies. Not looked at: finishing the mission and the original map, which the variant's build
leaves untouched (it ships under its own name).

## Run 2: CLrgScout_ForestTrench

Project: `exp25_projects.py forest`, "EXP-25 the forest trench, every kind" (`25b0a0b1-…`), variant
`CLrgScout_Fo_Exp25_25b0`. In the clearing north of the crashed UFO:

| Piece | Edit | Where |
| --- | --- | --- |
| power core `XComCollectible_10` (the UFO's north power room) | copied out into the clearing | from (-816, 1200) to (-432, 1872) |
| tree `XComDestructibleActor_242` | moved 2 tiles east | (-192, 1824) to (0, 1824) |
| rock `XComDestructibleActor_476` | copied | from (1536, 2208) to (-768, 1824) |
| big rock `XComDestructibleActor_19` | deleted | (-960, 2304) |

**Offline** (build `CLrgScout_Fo_Exp25_25b0-20261108-190519`, 12 minutes): the compiler's two notes (the core's copy
counts as loot; it stands in no building floor's cutaway, as the UFO's original does); each copy seeds its tiles
(the tree 112, the core 95, the rock 19); the relight wrote 50 lighting textures and 8 shadow maps. Most of the time
went on one piece: `XComLevelActor_252`, 267,588 texels, relit by one worker for some 10 minutes while the others
waited. Files: the variant map `d08fa6db98d2…`, `Lighting_10649584.tfc` `c1b6291c9655…`, the Dropship intro copy
`48e9adb81041…`. Installed in the lab's test slot (deploy record `CLrgScout_Fo_Exp25_25b0-20261108-191809.json`).

**In the game**, what is new here (the shot (`EXP-25-run2-overview.png`), from
[EXP-25-run2-shots.json](EXP-25-run2-shots.json)): the landing on a UFO map's variant, and the power core's copy
(mark 1) as loot: three cores at the mission's end where the map has two.

**Result (8 November, run by hand):** passed. The mission was ended with `killaliens` (the log has the console
command at 101 s and `XGBattle:Done`'s victory hook after it) and gave three power cores as loot. So a collectible's
copy counts as loot, as the Build makes it, and a mission on a variant can be finished. The log (19:20 to 19:22) has
no `CachedFrag` or `REBUILD PATHING!` lines.

## From run 3 on: checks without the game

From 8 November, after run 2, the other maps are checked without the game; an in-game test is prepared only where a
likely issue shows. Truck Stop (run 5) was already prepared for the game (its Fastrope-only landing). For each map
the offline check is:
- the build itself (it found two faults: F-67, and the farm project's map name);
- each copy's tiles seeded and its rebuild volume made, the hides' tiles rebuilt, from the build log;
- the variant exported with the viewer's exporter into a scratch cache and compared with the project (a scratch
  script, `check_variant.py`): each added record an object of the variant with the source's mesh at the record's
  pose, each moved or deleted original out of the persistent level's actor list, the counts of ladders,
  collectibles, doors, destructibles and fracturing pieces in the level against the original's;
- the placements looked at in marked editor shots (a copy on its wall, clear of other pieces);
- for a ladder copy, that it stands against the same wall piece as its original: the compiler's end check alone
  passed two copies that would have stood wrong (Truck Stop's `XComLadder_3` 2 tiles north, inside the store's
  jutting wall; Demolition's `XComLadder_4` 2 tiles west, clear of its site office).

Two faults found offline:
- **The farm's project named the map by its package** (`CsmallScout_Farm`); the Build looks records up by the
  records' name (`CSmallScout_Farm`, T-17), so it found none. The editor names a project the records' way (the map
  browser's id), so this was the example project's fault: `exp25_projects.py` now gives the farm both names, as
  EXP-22's farm project does.
- **[F-67](../findings-register.md): Demolition's first fallback volume has no brush.** Its rebuild volumes were to
  be cloned from `GameCameraBlockingVolume_0` (checklist item 1's "why" for the map), which has no brush model, so
  the Build failed at the first copy. The template now must have a brush: Demolition's is `XComCursorVolume_0`.

## Run 5: URB_TruckStop_EWI

Project: `exp25_projects.py truckstop`, "EXP-25 the truck stop, every kind" (`25e0a0b1-…`), variant
`URB_TruckSto_Exp25_25e0`. The map lands by Fastrope only. Its one empty doorway is a garage opening, so no door.

| Piece | Edit | Where |
| --- | --- | --- |
| tall drain pipe `XComLadder_7` (`DrainPipeA_448`) | copied 2 tiles east along the garage's wall | from (-2832, -1680) to (-2640, -1680) |
| semi truck cab `XComDestructibleActor_197` (glass `XComFracLevelActor_52`) | copied 3 tiles east, unturned | from (2112, 384) to (2400, 384) |
| tall crate stack `XComDestructibleActor_216` | copied | from (2263, -241) to (1879, -433) |
| dumpster `XComDestructibleActor_32` | moved 2 tiles east | (-2112, 1048) to (-1920, 1048) |
| forklift `XComDestructibleActor_415` | deleted | (2539, -719) |

**Offline** (build `URB_TruckSto_Exp25_25e0-20261108-192925`, 2 minutes; a first build put the drain pipe copy at
`XComLadder_3`'s spot, above): the compiler's notes say the semi cab and its glass stand in a building floor's
cutaway, their copies in none; the relight wrote 66 lighting textures and 17 shadow maps; the variant check found
every copy at its pose (the drain pipe's copy is `XComLadder_15`) and 11 ladders in the level against 10. Files: the
variant map, `Lighting_14605452.tfc` `1ab676edb173…`, the Fastrope intro copy `98c123da84d3…`. Installed in the lab's
test slot (deploy record `URB_TruckSto_Exp25_25e0-20261108-193212.json`).

**In the game**, what is new (overview (`EXP-25-run5-overview.png`), the drain pipe (`EXP-25-run5-drainpipe.png`), from
[EXP-25-run5-shots.json](EXP-25-run5-shots.json)): the Fastrope landing (no build of ours has landed that way), and a
route up the drain pipe's copy (mark 1), the first copied drain pipe.

**Result (8 November, run by hand):** passed: the Fastrope landing played and both drainpipes worked (routes up the
original and the copy). The game log (19:55 to 19:56) streams `CIN_FastropeIntros_URB_TruckSto_Exp25_25e0` with the
variant, and has no `CachedFrag` or `REBUILD PATHING!` lines.

## Runs 3, 4 and 6: checked offline

Built with no family flag and checked as above; none is played, since nothing in them is new to the game: each kind
of edit and family passed in the game on another map, and each map's own risk is covered below.

| Run | Variant (build) | Edits | Offline |
| --- | --- | --- | --- |
| 3, CSmallScout_Farm | `CSmallScout__Exp25_25c0` (`-20261108-193400`, 2 minutes) | tractor `XComDestructibleActor_153` moved 2 tiles north and copied beside it; generator `XComDestructibleActor_4` deleted; UFO navigation part `XComCollectible_12` copied inside the UFO, to (1872, -1232); ladder `XComLadder_4` copied 3 tiles along the lean-to, to (-1392, -1392); flatbed truck `XComDestructibleActor_91` (5 parts) copied 14 tiles east, 10 north | every copy at its pose; 11 ladders and 4 collectibles in the level against 10 and 3; the ladder copy's foot and top tiles (11, 22, 2) and (12, 22, 5), exactly EXP-22 run 2's moved ladder there, which climbed in the game; the flatbed's glass carried its 4 columns and dropped 3 entries of pieces outside it; 86 lighting textures, 30 shadow maps; the Dropship intro copy renamed |
| 4, URB_Demolition_EWI | `URB_Demoliti_Exp25_25d0` (`-20261108-193120`, 2.6 minutes) | bulldozer `XComDestructibleActor_100` moved 2 tiles east; portable toilet `XComDestructibleActor_156` deleted; crate stack `XComDestructibleActor_363` copied to (-1580, 233); drain pipe `XComLadder_4` copied 2 tiles north along its site office, to (1200, -1296); SUV `XComDestructibleActor_83` copied 7 tiles north | the first build failed (F-67); the rebuild volumes are now cloned from `XComCursorVolume_0`, the class the farm's builds have always used (EXP-22 run 2 played one); every copy at its pose; 6 ladders in the level against 5; the drain pipe's copy against the same site office piece as its original, its top tile (35, 14, 7) seeded first (the ladder recipe); 89 lighting textures, 22 shadow maps; the Dropship intro copy renamed |
| 6, URB_StreetHurricane_Terror | `URB_StreetHu_Exp25_25f0` (`-20261108-192129`, 1.4 minutes) | cover chunk `XComDestructibleActor_50` moved 2 tiles east; park bench `XComDestructibleActor_14` deleted; cover chunk `XComDestructibleActor_52` copied 2 tiles north; sedan `XComDestructibleActor_98` copied a quarter turn round | every copy at its pose; the sedan's glass carried its 6 columns; 45 lighting textures, 19 shadow maps; the Dropship intro copy renamed. Its moving vans and their ladders are left as they are (F-66) |

What these checks don't cover is what only the game shows (the rebuilt tiles, cover, routes up, the landing), and
each of those passed for the same kind of edit on another map: M1 pieces on every map so far, collectibles on
ForestTrench (run 2), cars on Bar and Police Station (EXP-24), ladders on Bar and the farm (EXP-22), the cursor
volume clone on the farm (EXP-22 run 2). The drain pipe, the one ladder mesh not yet climbed, is Truck Stop's
in-game check (run 5).

## Conclusion

Checklist item 1's six maps each have a Build with a moved, a deleted and a copied piece, a collectible copied where
the map has one (ForestTrench, the farm), and a copy of each family the map has that builds: a framed door, a car and
a van on Police Station; ladders on the farm, Demolition and Truck Stop (the first drain pipes); cars on four maps.
The families build together in one project. What the runs added:
- copied collectibles count as loot, and a mission on a variant can be finished (run 2);
- the Fastrope landing works on a variant (run 5), as the Dropship one does;
- a copied drain pipe climbs (run 5);
- the Build's rebuild volume template must have a brush (F-67);
- a ladder copy needs a look at its wall as well as the compiler's end check (two spots passed the check and would
  have stood wrong); the compiler could check it against the original's wall, a later improvement;
- Street Hurricane's moving vans climb by patch helpers, and their ladders aren't part of the van (F-66, open).

Not looked at: the original maps after a variant's install (a variant ships under its own name and changes none of
the original's files), and Police Station's other two missions (terror, data recovery), which use the same map.
