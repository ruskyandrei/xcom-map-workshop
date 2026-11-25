# EXP-22: ladders made in the map

Date: **8 November 2026**. Status: **runs 1 and 2 passed in the game (F-60)**: the ladder family builds
since.  Plan:
cars, doors and ladders, section 5.4. Tools: [`ladders.py`](../../tools/viewer/ladders.py),
[`native_copy.py`](../../tools/bake/native_copy.py) (`tile_volume`, `rebuild_order`, `ladder_order`),
[`stream_copy.py`](../../tools/bake/stream_copy.py), [`build.py`](../../tools/editor/build.py) `--family ladder`.

## Question

Does a ladder copied or moved in the map climb in the game, both ways, and does the place a moved ladder left stop
climbing?

The rebuild makes a ladder's two links from its foot tile when the foot has floor and the top tile (or the one below
it) has floor ([ladder-links.md](../native/ladder-links.md)). When the top tile T′ is rebuilt after the foot, its
rebuild empties the down link the foot made: a copy whose own rebuild volume reaches its foot first (a ladder facing
+X or +Y) loses its way down. The recipe (plan 5.2, recipe 1): a small rebuild volume over T′ alone, first in the
level's actor list, so T′ takes the earlier place in the rebuild's work set. LWR's `patch_bar` holds a hidden ladder
beside each of the bar's two, which would keep the old place climbable: the variant streams a copy of the patch
without it.

## Run 1: URB_Bar

Project: [`exp22_ladders_project.py`](../../tools/editor/examples/exp22_ladders_project.py), "EXP-22 ladders on the
bar" (`22e0a0b1-…`), variant `URB_Bar_EXP22Ladder_22e0`. Built with `build.py 22e0a0b1-2222-4d0a-8e22-3c4d5e6f7a22
--family ladder`.

| Ladder | Edit | Facing | Foot tile | Top tile (T′) | Helper |
| --- | --- | --- | --- | --- | --- |
| `XComLadder_3` | moved two tiles along the bar's west wall, (-1680, 336) to (-1680, 528); saved with no Rotation | +X | (11, 25, 0) | (12, 25, 6) | `patch_bar.XComLadder_11` hidden in the variant's copy |
| `XComLadder_4_copy1` | `XComLadder_4` (south wall, facing -Y) copied a quarter turn round onto the west wall, (-1680, 1008) | +X | (11, 30, 0) | (12, 30, 6) | none (the original keeps `XComLadder_15`) |

**Offline:**
- Both are the order hazard: the build without the top-tile volume rebuilds `XComLadder_3`'s foot before its top
  (`test_native_copy.test_a_ladder_copy_rebuilds_its_top_tile_first`).
- The compiler's end check passes both (the original floor tiles: ground at level 0, the roof at level 6).
- The Build's order check (`ladder_order`, on the built map, build `URB_Bar_EXP22Ladder_22e0-20261108-132347`, 109 s):
  `XComLadder_3`'s copy (`XComLadder_5`) has its top (12, 25, 6) at place 0 and its foot (11, 25, 0) at 168; the
  quarter-turned copy (`XComLadder_6`) its top (12, 30, 6) at 1 and its foot (11, 30, 0) at 213. The top-tile
  volumes are exports 14060 and 14070, first in the level's list. The hidden original's volume (tiles x 10–13,
  y 21–25, levels 1–8) comes last.
- `patch_bar_URB_Bar_EXP22Ladder_22e0` doesn't list `XComLadder_11` in its level (`stream_copy.py` checks it);
  everything else is as LWR has it.
- Files: the variant map `a860bacc137d…`, `Lighting_13417739.tfc` `5670cd0aa992…`, the patch copy `cea477ea4d0a…`,
  the intro copy `af40c0717719…` (first 12 hex digits of each SHA-256).
- Installed in the lab copy's test slot with `tools/lab/lab_install.py install` (deploy record
  `URB_Bar_EXP22Ladder_22e0-20261108-132619.json`): the slot streams the intro copy and the patch copy.

**In the game** (played by hand; the lab copy):
1. Climb `XComLadder_3` at its new place up and down with a soldier.
2. Its old place, two tiles along the wall (y 336): no climb (the move cursor offers no ladder path to the roof).
3. Climb the copy `XComLadder_4_copy1` (the west wall near its south corner) up and down.
4. `XComLadder_4` on the south wall still climbs.
5. Save, reload, and climb each again.
6. An alien using one, if one comes.

**Result (8 November, run by hand):** passed.
- The move preview routes a soldier up the moved `XComLadder_3`, up the quarter-turned copy and up `XComLadder_4`
  (shots `look-134526.png`, `look-134529.png`, `look-134541.png`); where a route shows, the climb works.
- After a save and reload: the same.
- The old place: no ladder shows two tiles along the wall from the moved one, and no invisible climbing route
  shows.
- No alien came to a ladder.
- Climbing down (checks 1 and 3): the game shows none. A soldier going down from a roof drops off its edge (the
  game has no real climb down; soldiers jump off things), so whether a ladder's down
  link is there doesn't show by eye. The A* probe (`GetAStarPath`, top tile to foot) would show it; not run.

**Not covered:** a ladder facing -X or -Y (the rebuild puts their top first anyway); a ladder whose top lands on a
floor another copy brings (copied floors get no floor tiles yet, F-47); LWR's mutator, which queues its own tiles
before the map's volumes (`XGBattle.DoWorldDataRebuild`), is not read.

## Run 2: CSmallScout_Farm

Project: [`exp22_farm_project.py`](../../tools/editor/examples/exp22_farm_project.py), "EXP-22 ladders on the farm"
(`22f0a0b1-…`), variant `CSmallScout__Exp22L_22f0` (the editor's naming: the map's first 12 characters). Built with
`build.py 22f0a0b1-2222-4d0a-8e22-3c4d5e6f7f22 --family ladder`. The map's package and records name it in two cases
(T-17).

`patch_farm` holds a hidden ladder beside six of the farm's ten (all wooden, `LadderWoodA_192`, 218 units of climb).
One stands at its ladder's own ends; five are near: 12 to 36 units off, their feet a level lower (z −16 against 0),
on tiles with no floor in the map's data, so by the rebuild's rule they make no climb of their own.

| Ladder | Edit | Facing | Foot tile | Top tile (T′) | Helper |
| --- | --- | --- | --- | --- | --- |
| `XComLadder_4` | moved three tiles along its shed's wall, (-1392, -1680) to (-1392, -1392) | +X | (11, 22, 2) | (12, 22, 5) | `patch_farm.XComLadder_3`, near (36 units), hidden in the variant's copy, with the compiler's warning |
| `XComLadder_0_copy1` | `XComLadder_0` (the red shed's west wall) copied two tiles along its wall, (-1872, -240) | +X | (6, 34, 2) | (7, 34, 5) | none (the original keeps its near helper `patch_farm.XComLadder_4`) |

**Offline** (build `CSmallScout__Exp22L_22f0-20261108-135637`, 70 s):
- The order check: the moved ladder's copy (`XComLadder_10`) has its top (12, 22, 5) at place 0 and its foot
  (11, 22, 2) at 132; the copy (`XComLadder_11`) its top (7, 34, 5) at 1 and its foot (6, 34, 2) at 501.
- `patch_farm_CSmallScout__Exp22L_22f0` without `XComLadder_3`; the variant streams it in `patch_farm`'s place.
- The first build had no landing intro copy: `CIN_DropshipIntros` names the farm `CsmallScout_Farm`, and
  `intro_copy.py` matched the record's case. It now matches whatever the case (T-17), and the rebuild has
  `CIN_DropshipIntros_CSmallScout__Exp22L_22f0` with that switch entry renamed.
- Files: the variant map `8365711707ca…`, `Lighting_3460620.tfc` `652562adabb9…`, the intro copy `e3bc6b6643a0…`.
- Installed in the lab's test slot (`lab_install.py install`): it plays the farm's Crashed UFO record.

**In the game** (played by hand; the lab copy). Marked editor shots show where to look, taken with
[`mark_shots.py`](../../tools/viewer/mark_shots.py) from [EXP-22-run2-shots.json](EXP-22-run2-shots.json): the
overview (`EXP-22-run2-overview.png`: a dashed box east of the UFO, round the big barn's lean-to and the red shed),
the moved ladder (`EXP-22-run2-shed.png`: marks 1 and 2) and the copied ladder (`EXP-22-run2-red-shed.png`: marks 3
and 4). The game has no climbing down, so the checks look for routes up:
1. The Skyranger lands (the intro copy).
2. A route up the moved `XComLadder_4` (mark 1) to the lean-to's roof.
3. Its old place, three tiles along the wall (mark 2): no ladder, and no route up.
4. A route up the copy of `XComLadder_0` (mark 3), and still one up the original beside it (mark 4).
5. Save, reload, and the routes again.

**Result (8 November, run by hand):** passed.
- The Skyranger landed: the intro played.
- The move preview routes a soldier up the moved `XComLadder_4` onto the lean-to's roof (`look-141002.png`), up the
  copy of `XComLadder_0` onto the red shed's roof (`look-141017.png`) and up the original beside it
  (`look-141019.png`).
- After a save and reload: the routes work the same.
- The moved ladder's old place (mark 2) shows no ladder in the shot; a route there wasn't tried in a shot.
- So the near helper's rule holds here (`patch_farm.XComLadder_3`, 36 units off, taken out of the variant's copy of
  the patch), and a copy of a ladder that has a patch helper of its own (`XComLadder_0`, near helper
  `patch_farm.XComLadder_4`) climbs on the map's floors alone: the end check was enough.
