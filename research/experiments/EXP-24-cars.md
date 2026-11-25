# EXP-24: cars made in the map

Date: **8 November 2026**. Status: **all four runs passed in the game: runs 1 and 2 (F-64, T-19), and the car family builds since; runs 3 and 4
(vans, F-65), and the van family builds since.**
Plan: cars, doors and ladders, section 7.5. Tools:
[`native_copy.py`](../../tools/bake/native_copy.py) (`move_columns`), [`build.py`](../../tools/editor/build.py)
`--family car`.

## Question

A car is an assembly (plan 3.3): its body (an `XComDestructibleActor`, with its damage, destruction and wreck in its
subtree), its fractured glass (an `XComFracLevelActor`) and, for a police car, its police parts (a second
destructible, `SedanBPolice`: the light bar and markings; on Police Station some sedans carry one that no prefab
places with them, [T-19](../findings-register.md)). Made in the map as one assembly, do a moved and a copied
car work as the map's own do (cover, the glass breaking, fire at window height, the blast, a save and reload)? Does
a deleted car leave bare road?

## What the Build does for a car

- **One assembly, one grid move** (G1, G2): every member cloned together, each reference among them pointing at the
  copies (the glass's `HidingPartner`, the columns' entries).
- **The glass's columns** (G8's glass half, [F-64](../findings-register.md)): the glass lists, per fragment column,
  the pieces that go when that column breaks (`FragmentColumns(k).DestructibleCache`: the body, the police parts, and
  on some maps a fence or a neighbouring wreck), and a broken column adds a fire spot (plan 7.2). A clone keeps the
  original's columns as they are: their boxes where the original stands. `move_columns` carries each column's box
  with the copy's move (a quarter turn keeps it axis aligned), raises every MinZ by the storey shift, keeps the
  entries of the assembly's own members (the clone already points them at the copies) and drops the rest: a copy's
  glass doesn't break a fence at its new place (a known limit, plan 7.2).
- **Hides** as for every piece: out of the level's list, out of every column that lists them (none on Bar), the old
  tiles rebuilt.

## Run 1: URB_Bar

Project: [`exp24_cars_project.py`](../../tools/editor/examples/exp24_cars_project.py), "EXP-24 cars on the bar"
(`24e0a0b1-…`), variant `URB_Bar_Exp24Car_24e0`. Built with `build.py 24e0a0b1-2424-4d0a-8e24-3c4d5e6f7a24 --family
car`.

| Car (members) | Edit | Where |
| --- | --- | --- |
| sedan 136 (`XComDestructibleActor_136`, glass `XComFracLevelActor_50`) | moved a tile west and 5 north along the street west of the bar, unturned | (-2026, 1) to (-2122, 481) |
| police car 64 (`XComDestructibleActor_64`, police parts `_143`, glass `XComFracLevelActor_45`) | copied a quarter turn round (yaw -728 to 15656), beside it in the car park south of the bar | (-1240, -482) to (-1342, -856); the original stays |
| SUV 137 (`XComDestructibleActor_137`, glass `XComFracLevelActor_51`) | deleted | the street west of the bar, (-2402, -684) |

The places were picked with a scratch search for moves whose boxes clear every standing piece with the ground under
them.

**Offline** (build `URB_Bar_Exp24Car_24e0-20261108-161611`, 3 minutes):
- The compiler: 2 moved, 2 deleted, 3 added, two car assemblies (`move:XComDestructibleActor_136`, translation
  (-96, 480, 0); `add:XComDestructibleActor_64_copy1`, one turn), no errors or warnings.
- The copies: the sedan becomes `XComDestructibleActor_528` and its glass `XComFracLevelActor_206`; the police car's
  body `XComDestructibleActor_530`, its police parts `_529`, its glass `XComFracLevelActor_207`. Each glass carried
  its 6 columns, with no entries of other pieces to drop (these two cars' glass lists only their own car's pieces).
- No car is in a building floor's cutaway, and no wall's columns list one.
- The relight: 39 lighting textures written, 55 unchanged, 5 skipped, 8 shadow maps.
- Files: the variant map `11660e23ff3f…`, `Lighting_15188653.tfc` `b3142b96e5b3…`, the intro copy `3780102dd52d…`
  (first 12 hex digits of each SHA-256).
- Installed in the lab's test slot (`lab_install.py install`, deploy record
  `URB_Bar_Exp24Car_24e0-20261108-162053.json`).
- `test_native_copy.test_a_car_copys_glass_columns_turn_and_move_with_it` checks this copy's columns against the
  original's moved by `moved_box`; `test_a_car_copys_glass_drops_column_entries_of_other_pieces` copies Police
  Station's car 1071, whose glass also lists `XComDestructibleActor_1070`.

**In the game** (played by hand; the lab copy). Marked editor shots, taken with
[`mark_shots.py`](../../tools/viewer/mark_shots.py) from [EXP-24-run1-shots.json](EXP-24-run1-shots.json): the
overview (`EXP-24-run1-overview.png`: the street and car park, boxed), the police car and its
copy (`EXP-24-run1-police.png`: marks 3 and 4) and the street west of the bar (`EXP-24-run1-west-street.png`: marks 1,
2 and 5).
1. The Skyranger lands (the intro copy).
2. Cover: the police car's copy (mark 3) gives cover at both ends and both sides, and so does the moved sedan
   (mark 1).
3. The glass: shots break each copy's windows piece by piece; breaking the copy's glass leaves the original police
   car's (mark 4) whole, and the other way round.
4. Fire: a grenade at the copy sets it alight at window height; it burns down at a turn change, and its blast sets
   what stands next to it alight. The same for the sedan.
5. Where the sedan stood (mark 2) and where the SUV stood (mark 5): bare road, no cover, and a grenade there sets
   nothing alight.
6. Save with one car burning and another a wreck, reload: no second blast, and the wreck still gives cover.
7. Afterwards, the game log has no `CachedFrag` or `REBUILD PATHING!` lines (F-11; Claude reads it).

**Result (8 November, run by hand):** passed. The game log (`Launch.log` of the lab copy,
17:12 to 17:13, about 80 seconds on the map) has no `CachedFrag` or `REBUILD PATHING!` lines. It records one HE
grenade whose blast damaged a fracturing piece and five others, and no save or reload, so check 6 (save and reload
with a burning car and a wreck) carries to run 2. No F9 shots were taken.

## Run 2: URB_PoliceStation

Police Station's cars stand at whole quarter turns. Four of its sedans (`SedanBBody` with open doors) carry a
standalone police light bar (`ARC_SedanBPoliceAddon`, `XComDestructibleActor_468` to `_471`) 2 units from the body,
in no prefab: only the glass's fragment columns name it. Export 16 records what each fracturing piece's columns break
(`breaks`), and the compiler joins such a part to its car ([T-19](../findings-register.md)). Two crashed cars
(`SedanBWreckA` and `SedanBWreckC`, painted, not burnt out) stand side by side, and the red one's glass also names
the yellow one.

Project: [`exp24_police_project.py`](../../tools/editor/examples/exp24_police_project.py), "EXP-24 cars at the
police station" (`24f0a0b1-…`), variant `URB_PoliceSt_Exp24C_24f0`, on export 16. Built with `build.py
24f0a0b1-2424-4d0a-8e24-3c4d5e6f7b24 --family car`.

| Car (members) | Edit | Where |
| --- | --- | --- |
| sedan 1062 (`XComDestructibleActor_1062`, doors `_1063` and `_1064`, standalone light bar `_471`, glass `XComFracLevelActor_194`) | moved a quarter turn round, over its old place | (-1258, 192), yaw 0, to (-1248, 278), yaw 16384 |
| police car 1075 (`XComDestructibleActor_1075`, light bar `_1076`, glass `XComFracLevelActor_200`) | copied a half turn round, 2 tiles east and 2 north of it | (-960, -292) to (-768, -92); the original stays |
| crashed red car 1071 (`XComDestructibleActor_1071`, glass `XComFracLevelActor_198`) | copied 2 tiles north, unturned | (-958, 1152) to (-958, 1344); the original stays |
| sedan 1072 (`XComDestructibleActor_1072`, doors `_1073` and `_1074`, standalone light bar `_470`, glass `XComFracLevelActor_199`) | deleted | the south edge, (-296, -2400) |

**Offline** (build `URB_PoliceSt_Exp24C_24f0-20261108-172422`, 3 minutes):
- The compiler: 5 moved, 5 deleted, 5 added, three car assemblies, no errors or warnings. The moved sedan's assembly
  has 5 members, its light bar among them.
- The copies: the sedan becomes `XComDestructibleActor_1092` (doors `_1093`, `_1094`, light bar `_1095`) and its
  glass `XComFracLevelActor_401`, whose 9 columns moved with it, keeping the light bar's entries; the police car's
  copy `_1097` (light bar `_1098`, glass `XComFracLevelActor_403`, 6 columns); the crashed car's copy `_1096` (glass
  `XComFracLevelActor_402`: 6 columns, the 2 entries naming the yellow car dropped).
- No car is in a building floor's cutaway, and no wall's columns list one.
- The relight: 86 lighting textures written, 14 shadow maps.
- Files: the variant map `20b51eaf6fc5…`, `Lighting_7279769.tfc` `66ed199be11b…`, the intro copies `2e76419f9646…`
  (Dropship) and `40eafe7fcb37…` (Fastrope).
- Installed in the lab's test slot (deploy record `URB_PoliceSt_Exp24C_24f0-20261108-172753.json`): it plays the
  station's abduction record.

**In the game** (played by hand; the lab copy). Marked editor shots, from
[EXP-24-run2-shots.json](EXP-24-run2-shots.json): the overview (`EXP-24-run2-overview.png`: the car park west of the
station, boxed), the moved sedan, and the police car and its copy (`EXP-24-run2-sedan-police.png`: marks 1 to 3),
the crashed red car and its copy (`EXP-24-run2-wrecks.png`: marks 4, 5 and 7) and
where the sedan stood (`EXP-24-run2-deleted.png`: mark 6).
1. The moved sedan (mark 1): its light bar sits on its roof and moved with it, and no light bar is left floating
   where it stood. Cover at its ends and sides; its glass breaks; a grenade sets it alight at window height.
2. The police car's copy (mark 2): the same; breaking its glass leaves the original's (mark 3) whole.
3. The crashed car's copy (mark 4): cover; breaking its glass leaves the yellow car (mark 7) alone.
4. Where the deleted sedan stood (mark 6): bare road, no cover, and no light bar left there.
5. Run 1's carried check: save with a car burning and another blown up, reload: no second blast, and the wreck
   still gives cover.
6. Afterwards, the game log has no `CachedFrag` or `REBUILD PATHING!` lines (Claude reads it).

**Result (8 November, run by hand):** passed. Four F9 shots: the deleted sedan's place
(bare road, the dash path crossing it without cover); the crashed red car's copy, its original and the yellow car
burnt out after a blast, the copy's wreck as the map's; and two after loading a save made 2 turns in, the wrecks
still burning and giving cover, the moved sedan with its light bar and both police cars in place. The game log
(17:48 to 17:52):
- no `CachedFrag` or `REBUILD PATHING!` lines;
- an HE grenade at 133 s and a chain of car blasts at 175 to 187 s; a save at 199 s, loaded at 204 s;
- on load the game replays the blast actions (`XComDestructibleActor_Action_RadialDamage`, 241 each) of every car
  destroyed before the save, the map's own (sedan 1059, the crashed cars 1070 and 1071) and the copy (1096) alike,
  two each; no unit is hurt (no combat log line after the load, the same aliens active). The copy acts as the
  map's cars do. F-18's patch-era note that the map's own wrecks don't replay doesn't hold on this map
  ([F-18](../findings-register.md)).

## Run 3: vans on URB_Bar

A van is a car with a building of its own (plan section 7.6): its parts are one assembly (cab, walls, doors, glass,
the cargo floor's base and the roof, placed by its prefab), and an `XComBuildingVolume` with two `XComFloorVolume`s
(floor 0 the cargo area, floor 1 the roof) lists them, so the roof cuts away over a soldier inside. The volumes have no
mesh, so the export doesn't list them and the compiler's assembly is the parts alone. What the Build adds
([F-65](../findings-register.md)):
- **The building goes with the parts** (`native_copy.van_buildings`): the level's building more than half of whose
  listed residents are the van's parts, as the compiler tells a van. It and its floor volumes are cloned in the same
  `clone_assembly` as the parts, at the pose the parts' move carries them to (`moved_pose`; a quarter turn turns them,
  new to us: the map's own stand unturned), so the copied building's floors, floor volumes and roof group point at
  the copies.
- **The copied building keeps only the van's own residents** (`edit_van_building`): pieces standing under the
  original (road paint, a skid mark) stay where they are and out of the copy's lists; its
  `VisGroupIdxToHideWhenOccluding` is emptied.
- **A moved or deleted van's building leaves the level with it** (`hide_van_buildings`).
- The van's parts stay out of other buildings' cutaways (`edit_floor_caches`), and the compiler gives them no
  `building-floor` note.

Project: [`exp24_vans_project.py`](../../tools/editor/examples/exp24_vans_project.py), "EXP-24 vans on the bar"
(`24c0a0b1-…`), variant `URB_Bar_Exp24Van_24c0`, on export 16. Built with `build.py
24c0a0b1-2424-4d0a-8e24-3c4d5e6f7c24 --family van`.

| Van (cab) | Edit | Where |
| --- | --- | --- |
| delivery van `PRE_DeliveryVanA` (cab `XComDestructibleActor_527`, 7 parts, building `XComBuildingVolume_3`) | copied a quarter turn round into the car park south of the bar | (-669, -481), yaw 0, to (-1247, -957), yaw 16384; the original stays |
| short moving van `PRE_VEH_MovingVanShort` (cab `XComDestructibleActor_76`, 10 parts, building `XComBuildingVolume_4`) | moved 4 tiles south along the street west of the bar | (-2306, 860) to (-2306, 476) |
| moving van `PRE_MovingVanA` (cab `XComDestructibleActor_101`, 14 parts, building `XComBuildingVolume_1`) | deleted | the car park south-west of the bar, (-1912, -1246) |

**Offline** (build `URB_Bar_Exp24Van_24c0-20261108-180836`, 3 minutes):
- The compiler: 10 moved, 14 deleted, 7 added, two van assemblies, no errors or warnings.
- The delivery van's copy: building `XComBuildingVolume_10` at (-1247, -907, 364), yaw 16384, floor volumes
  `XComFloorVolume_24` and `_25`; it lists the parts' copies (the cab with its `CutdownFloor` 1, the roof on floor 1)
  and dropped the road paint and asphalt under the original (`XComLevelActor_151`, `_205`, `_274`). Its glass carried
  its 6 columns.
- The short van: building `XComBuildingVolume_9` at (-2352, 476, 616), floor volumes `XComFloorVolume_22` and `_23`;
  it dropped a skid mark (`XComLevelActor_35`). Its glass carried its 4 columns.
- Hidden: the moving van's 14 parts and the short van's 10, with buildings `XComBuildingVolume_1` and `_4` and their
  floor volumes.
- One rebuild volume over each van seeds its empty tiles up to the roof (195 and 264 seeded).
- The relight: 83 lighting textures written, 16 shadow maps.
- Files: the variant map `0fe96bb4e408…`, `Lighting_5239843.tfc` `09822bd3c3dc…`, the intro copy `9441cea06a2c…`.
- Installed in the lab's test slot (deploy record `URB_Bar_Exp24Van_24c0-20261108-181158.json`).
- `test_native_copy.test_a_van_copy_takes_its_building_and_floor_volumes_along` and
  `test_a_deleted_vans_building_leaves_the_level_with_it` check the same on the delivery van and the moving van.

**The open question** (plan 7.6): whether the rebuild makes the copies' cargo floor and roof into floor tiles, as the
bake made the originals'. F-47 (a copied second floor got no floor tiles, EXP-08) is the same question for script
copies, still open.

**In the game** (played by hand; the lab copy). Marked editor shots, from
[EXP-24-run3-shots.json](EXP-24-run3-shots.json): the overview (`EXP-24-run3-overview.png`),
the delivery van and its copy (`EXP-24-run3-delivery.png`: marks 1 and 2), the short van (`EXP-24-run3-short-van.png`:
marks 3 and 4) and where the moving van stood (`EXP-24-run3-deleted.png`: mark 5).
1. The delivery van's copy (mark 1): a soldier walks into its cargo area through the back, and climbs onto its roof
   where the original allows it.
2. With a soldier inside: the copy's roof cuts away, and the cursor picks tiles inside; nothing near the original
   (mark 2) hides when it does.
3. Cover around the copy; its glass breaks; it burns and explodes.
4. The short van (mark 3): the same, unturned.
5. Where the short van stood (mark 4) and where the moving van stood (mark 5): open ground, no floor or roof left in
   the air, no cover.
6. Save with a soldier inside a van copy, reload: they stay inside, and the roof still cuts away.

**Result (8 November, run by hand):** passed. Four F9 shots: a move path into the delivery van
copy's cargo area through its back, with cover shields inside; the car park with the copy, the moved short van and
the empty bay where the moving van stood; after loading a save made a turn in, a soldier still inside the copy's
cargo area with its roof cut away; a dash path into the moved short van's cargo area through its back door. So the
rebuild made the copies' cargo floors into floor tiles (plan 7.6's open question, unlike F-47's script copies), and
the turned copy's building cuts away. No shot showed a soldier on a van's roof. The game log (18:19 to 18:22): no
`CachedFrag` or `REBUILD PATHING!` lines, two HE grenades, a save at 110 s loaded at 116 s, and no warning naming
the copies' buildings, floor volumes or parts.

## Run 4: vans on URB_PoliceStation

The same build as run 3's, on the map whose vans are all `PRE_DeliveryVanA` (four, each with its own building), north
of the police station. Project: [`exp24_police_vans_project.py`](../../tools/editor/examples/exp24_police_vans_project.py),
"EXP-24 vans at the police station" (`24d0a0b1-…`), variant `URB_PoliceSt_Exp24V_24d0`, on export 16. Built with
`build.py 24d0a0b1-2424-4d0a-8e24-3c4d5e6f7d24 --family van`.

| Van (cab) | Edit | Where |
| --- | --- | --- |
| delivery van (cab `XComDestructibleActor_295`, 7 parts, building `XComBuildingVolume_1`) | copied a quarter turn round, a few tiles south of it | (472, 1918), yaw 32768, to (482, 1528), yaw 49152; the original stays |
| delivery van (cab `XComDestructibleActor_1084`, 7 parts, building `XComBuildingVolume_27`) | moved 2 tiles south | (-872, 1630) to (-872, 1438) |
| delivery van (cab `XComDestructibleActor_342`, 7 parts, building `XComBuildingVolume_5`) | deleted | (-202, 1918) |

**Offline** (build `URB_PoliceSt_Exp24V_24d0-20261108-182417`, 4.5 minutes):
- The compiler: 7 moved, 7 deleted, 7 added, one van assembly per edit, no errors or warnings.
- The copy: building `XComBuildingVolume_30` at (482, 1578, 380), yaw 49152, floor volumes `XComFloorVolume_67` and
  `_68`; it dropped two sidewalk pieces under the original (`XComLevelActor_258`, `_255`). Its glass carried its 6
  columns and dropped 4 entries of pieces outside the van.
- The moved van: building `XComBuildingVolume_29` at (-822, 1438, 380), floor volumes `XComFloorVolume_65` and `_66`,
  no residents dropped. Its glass carried its 6 columns.
- Hidden: the moved and the deleted vans' 14 parts, with buildings `XComBuildingVolume_27` and `_5` and their floor
  volumes (`_62`, `_61`; `_20`, `_17`).
- One rebuild volume over each van seeds its empty tiles up to the roof (178 and 145 seeded).
- The relight: 97 lighting textures written, 21 shadow maps.
- Files: the variant map `fc983f5fa763…`, `Lighting_9375873.tfc` `fa89aff6c9f5…`, the intro copies `172455cfc056…`
  (Dropship) and `5cab9b9b0912…` (Fastrope).
- Installed in the lab's test slot (deploy record `URB_PoliceSt_Exp24V_24d0-20261108-182910.json`).

**In the game** (played by hand; the lab copy). Marked editor shots, from
[EXP-24-run4-shots.json](EXP-24-run4-shots.json): the overview (`EXP-24-run4-overview.png`),
the delivery van and its copy (`EXP-24-run4-copy.png`: marks 1 and 2) and
the moved van and the deleted one's place (`EXP-24-run4-moved.png`: marks 3 and 5).
1. The copy (mark 1): a soldier walks into its cargo area through the back.
2. With a soldier inside: the copy's roof cuts away; nothing near the original (mark 2) hides when it does.
3. Cover around the copy; its glass breaks; it burns and explodes.
4. The moved van (mark 3): the same, unturned; open ground behind it, where it stood.
5. Where the deleted van stood (mark 5): open ground, no floor or roof left in the air, no cover.
6. Save with a soldier inside a van copy, reload: they stay inside, and the roof still cuts away.

**Result (8 November, run by hand):** passed after a quick check. A
short look, with no F9 shots: the game log (18:38 to 18:39) has the mission up at 25 s and the exit at 81 s, no save,
no `CachedFrag` or `REBUILD PATHING!` lines, and no warning naming the copies' buildings, floor volumes or parts. A
save and reload with a soldier inside a van copy was run 3's. With runs 3 and 4 passed, the van family builds
(`compiler.FAMILIES`), and its "Builds from M2" chip goes.
