# EXP-28: fracturing pieces and physics props made in the map

Date: 9 November 2026. Branch `fracturing-physics`. Both families were switched on for every project before any game
run of them, as with lights after EXP-26 run 1, so that issues are fixed as they are found. This note holds the run
that is still to play.

## Question

Until now the Build refused every edit of a fracturing piece of its own (a wall, a storey floor, a roof slab, a bar's
counter: `XComFracLevelActor`, `XComDecoFracLevelActor`) and of a physics prop (`KAsset`), naming milestone M3. Only a
car's glass, a fracturing piece inside an assembly, was built (EXP-24). What the Build does with them now:

- **Fracturing pieces** are cloned in the map as any copy is, on the grid only (whole tiles, whole storeys and quarter
  turns from where the original stands; the page's recipe snap and `compiler.single_grid_rule`). The clone's fragment
  columns are carried with it. Its lists of what breaks with each column and of the neighbouring walls' columns keep
  only the pieces copied in the same build by the same move; a hidden wall leaves its neighbours' lists; a door's
  copy joins a wall copy's columns (findings register, F-69).
- **Physics props** are cloned as they are, at any pose (F-70).

What no run has shown, and only the game can:

1. Does a wall made in the map behave as a wall: full cover along it, no sight through it, no walking through it?
2. Does it break as the map's walls do, a column at a time, and do the doors copied with it go when the wall round
   them goes?
3. Does a fracturing piece moved (the original hidden, a copy made) leave its old place open and give cover at the
   new one?
4. With a wall deleted, can soldiers walk and see through where it stood, and do the walls beside it still break
   without trouble (their columns no longer list it)?
5. Does a copy of a fracturing storey floor carry floor tiles at a height where the map has none (EXP-27's question,
   which passed for a plain floor piece)?
6. Does a save and reload keep a broken wall copy broken (a fracturing piece saves its damaged columns, F-17)?
7. Do the map's corpses show in the game at all, and if they do, does a copy rest where it was put?

Everything else these edits use has passed before (copies made in the map, their tiles seeded and rebuilt, hides,
doors as assemblies, building-floor cutaways, quick and full builds, Bar's landing), so it is not asked again.

## Run 1: URB_Bar, a wall with its doors, a counter section, a deleted wall, a floor strip, three corpses

Project: [`exp28_projects.py`](../../tools/editor/examples/exp28_projects.py), "EXP-28 walls and corpses on the bar"
(`28e0a0b1-…`), variant `URB_Bar_Exp28Frac_28e0`.

| Mark | Edit | Pieces | Where |
| --- | --- | --- | --- |
| 1 | Copied, with its two doors (a, b), by one move | the inner wall `XComDecoFracLevelActor_16` (`URB_BarIntWallA`, 10 tiles long, 33 columns), doors `XComInteractiveLevelActor_6` and `_7` with their frames `XComDestructibleActor_60` and `_65` | 9 tiles south, on the sidewalk in front of the bar: (-1152, -192, 16) |
| 2 | Moved | the island counter's south section `XComFracLevelActor_23` (`BarSection4Long`) | 2 tiles south, into the front room: (-240, 288, 16) |
| 3 | Deleted | the inner cross wall `XComDecoFracLevelActor_17` (`URB_BarIntWallB`) | along Y at x -1056, between the back rooms. Two TVs, shelves and a menu hung on it stay where they hang |
| 4 | Copied | the upstairs floor strip `XComFracLevelActor_17` (`Core_384FloorB`, 10 tiles by 1, top at 210) | 2 tiles north, over the front room, where the map has no floor at that height: (-1056, 864, 16) |
| 5a | Copied | the corpse `KAsset_0` | 2 tiles east: (345.8, -863.6, 0) |
| 5b | Moved off the grid | the corpse `KAsset_2` | 37.5 east, 20 north, turned by 5000 units: (587.0, -684.9, 0) |
| 5c | Deleted | the corpse `KAsset_1` | (353.9, -1177.1, 0) |

**Offline** (quick build `URB_Bar_Exp28Frac_28e0-20261109-203844`, 12 s; full build `…-203939`, 282 s):
- The compiler: 2 moved, 2 deleted, 7 added, all made in the map (no patch); the two doors as assemblies. Five
  warnings, all "stands in no building floor" for the wall copy and its doors on the sidewalk, as expected.
- The writer's log: `XComDecoFracLevelActor_18` (the wall's copy), tiles `[10, 23, 16, 19, 1, 7]`, 368 seeded; its 33
  columns moved with it, 150 entries of other pieces dropped, 36 now naming the doors' copies, 60 neighbour listings
  dropped. `XComFracLevelActor_206` (the counter section), 5 columns, in the bar's floor 0 cutaway;
  `XComFracLevelActor_207` (the floor strip), 11 columns, in its floor 1 cutaway; `KAsset_14` and `_15`, 3 exports
  each, no lighting textures. Hidden: `KAsset_1`, `KAsset_2`, `XComDecoFracLevelActor_17`, `XComFracLevelActor_23`.
  Six of the map's own pieces lost 44 listings of the two hidden fracturing pieces' columns (the inner wall 10, the
  back wall 8, the roof slab 22, three more 4).
- The package read back (a scratch script over `native_copy`'s readers):
  - the Level lists 1,557 actors where the map has 1,537: 9 copies and 11 rebuild volumes more, 4 slots emptied;
  - every column box of the three fracturing copies is its original's moved by the copy's move exactly;
  - the wall copy's columns name the four door copies (10, 10, 8 and 8 columns) and nothing else;
  - no column of any fracturing piece in the Level names an actor out of it.
- The full build: each fracturing copy got 2 lighting textures of its own and was relit for its place (the wall copy:
  28,019 texels, 27,485 changed); 231 lighting textures written, 3 shadow maps, `Lighting_10000625.tfc`.
- The full build's variant exported into a scratch cache: the copies at their poses, the wall copy's `breaks` its
  four door pieces, the counter section and the floor strip listed in the bar's floors (indices 0 and 1), as the
  writer put them.
- Marked editor shots, from [EXP-28-run1-shots.json](EXP-28-run1-shots.json): the overview (`EXP-28-run1-overview.png`),
  the wall copy (`EXP-28-run1-wall.png`), inside (`EXP-28-run1-inside.png`), upstairs (`EXP-28-run1-upstairs.png`) and
  the corpses (`EXP-28-run1-corpses.png`).

Installed in the lab's test slot (9 November, 20:54; the full build; deploy record
`URB_Bar_Exp28Frac_28e0-20261109-205413.json`), with the lab copy switched in (`switch_install.ps1 lab`): the first
mission of a new campaign in the lab copy. The slot streams the variant's own landing intro, `patch_bar` and
`patch_hide_randomized_objects`; none of `patch_bar`'s 17 pieces stands at any of the edited places. `switch_install.ps1
lwr` puts the LWR install back for normal play.

**In the game** (played by hand; F9 for a shot; the lab copy; a fresh mission). What is new, by mark:
1. The wall copy: a soldier beside it has full cover and sees nothing through it; nobody walks through it. A grenade
   or rocket on it breaks the columns it reaches, and the rest stands.
   - a, b: each door opens. Blow up the wall round one: the door and its frame go with it.
2. The counter section in the front room gives low cover; where it stood, the island is open and can be walked
   through.
3. Where the cross wall stood: soldiers walk and see through. A grenade on the inner wall beside it (the map's own)
   breaks as usual.
4. `ShowCursorLoc`: the cursor lands on the floor strip's copy (about 210). `TeleportToCursor` puts a soldier there,
   who stands on it and can be moved along it.
5. Are there corpses at 5a and 5b, and none at 5c? If the game shows no corpse anywhere on the map, that is the
   answer for Bar (F-70).
6. After breaking part of the wall copy: save, reload. The copy is still broken where it was, and its doors are as
   they were left.
- The log, afterwards: no `CachedFrag`, `REBUILD PATHING!`, `Not Found … Recreating actor` or `Accessed None` lines
  naming a copy.

**Result (9 November, run by hand, 20:56 to 20:59):** all seemed fine except two things: no walking through where
the cross wall was deleted (probably because other pieces there have collision), and no soldier could be teleported
onto the floor strip. One screenshot, from the kitchen looking across the deleted wall's line at the bar.
Both were read afterwards out of the run's save (`save17`, made at 179 s) with the new
[`save_tiles.py`](../../tools/lab/save_tiles.py), which prints the game's tile flags beside the map's baked ones.

- **Mark 3, the deleted wall: gone, and the line is blocked by what stood against it.** That guess is right.
  - The wall never loads: the log names neither it nor the other three hidden pieces. In the screenshot the kitchen
    and the bar are one room; the grey panels are the plain backs of the liquor shelves that stood against the wall.
  - The save: the kitchen-side tiles the wall alone occupied are free after the rebuild, (17, 30) and (17, 31) at
    levels 0 and 1 (`43a92cFO -> 42292cF.`). The tile column east of the line, (18, 27..32), is still fully occupied
    and has no floor, as in the bake (`429ffe.O`): the back bar `XComFracLevelActor_0` (`bar_5`, to z 80) with six
    liquor shelves on it (to z 144) runs the wall's whole length. On the kitchen side stand the dishwasher, the sink
    and a kitchen counter. So no tile lets a soldier cross: to open the way the back bar and its shelves have to go
    too.
- **Mark 4, the floor strip's copy: floor on 4 of its 10 tiles; none under the ceiling's air duct.**
  - The save, level 3 (the strip's top, 210), tiles (13..22, 23): the six tiles x 13..18 read `420820` (no floor
    bit), the four x 19..22 `622820` with the floor bit, where the bake has empty air (`020000`). So the rebuild does
    make floor from a fracturing floor's copy (question 5: yes), and refuses it on six tiles.
  - Why those six: the level above them, (13..18, 23, 4), is occupied in the map's own bake (`028040`), and free over
    the other four (`020000`). `BarCeilingAirDuctA` (`XComLevelActor_73`, x -1524..-1027, drawn from z 342) hangs
    there; over the other four only the ceiling's I-beams (from z 362) and its lights. No standing room, no floor:
    the same rule that keeps the map's own floors off such tiles. The test spot was badly chosen.
  - Not known: whether the cursor lands on the four floored tiles, the end nearest the island counter (x -960 to
    -576). Indoors the mouse cursor takes a surface above the ground only on the floor asked for (mouse wheel up one
    floor: research/native/mouse-cursor.md), which the instructions for this mark didn't say.
- **The rest passed.** What the log adds:
  - an explosion at 124.5 s damaged the wall copy and with it the door copy `XComInteractiveLevelActor_27` and its
    frame `XComDestructibleActor_528` (`DestructibleActorClear`: the wall's columns took their door along,
    question 2), and the bar's own front facade behind it;
  - the save at 179 s and the reload at 186 s: `XComDecoFracLevelActor_18`, `XComDestructibleActor_528` and
    `XComInteractiveLevelActor_27` are found by name and their records applied (question 6); nothing of the map is
    recreated (the `Not Found … Recreating` lines are the game's own `XG…` objects);
  - no `CachedFrag` or `REBUILD PATHING!` line; 59 `WorldData: Restarting work queue` lines, 2,407 tiles at load.
- **Corpses (question 7):** the map's corpses do show in the game, as green fogged bodies (two are in the screenshot,
  `KAsset_10` in the kitchen and `KAsset_9` behind the back bar), and the log checks both copies, `KAsset_14` and
  `KAsset_15`, at each load. The run's verdict covers marks 5a to 5c without detail.
- Found on the way, fixed offline: a fractured mesh component saves its fragments' lowest and highest world height
  (`FragmentBoundsMinZ`, `FragmentBoundsMaxZ`), which a copy moved up or down kept from its original. This run's
  copies stand at their originals' heights, so it didn't touch them (`native_copy.shift_fragment_heights`).

Still open after run 1: the cursor on the strip copy's four floored tiles; a floor copy where nothing hangs over it;
breaking a storey floor's copy.

## Where physics props are

Read from the install's 159 map packages (9 November): 47 hold physics props, 740 in all. 643 carry the tag
`deleteme` (15 of them `EXT_deleteme`, on DLC2_1_Portent) and 97 carry none: on URB_CommercialStreet (14),
URB_MilitaryAmmo (8), URB_HighwayConstruction (6), the terror maps and others. None of the 47 packages holds a
`SeqAct_RemoveActor`, the Kismet action that removes actors by tag, so what the tag is for wasn't found. If Bar shows
no corpses, a second run on URB_CommercialStreet, whose 14 carry no tag, answers question 7.
