### Terror civilians no longer start in the air where deleted pieces had floors, and baked copies no longer show black where something stands on their original (F-157, F-158; KB-18 and KB-19 out)

A user's skyscraper map (a CLrgScout_City variant with its UFO deleted and a helipad in its place) showed both.

**Civilians in the air (F-157).** The game places the terror civilians on the map's stored cover points (within 960
units of a pod), and a pod's other aliens on the nearest valid places, before it runs the battle's tile rebuild; a
Build left a deleted piece's floors and cover points stored for that rebuild to clear. The Build now writes the tiles
near its changes as the rebuild will leave them:

- [start_tiles.py](../../tools/bake/start_tiles.py) (new): for the tiles a rebuild volume reaches that lie near a
  change (the boxes its rebuild volumes were made for, with a tile round them, a level under and two over) or round a
  floor whose piece was taken out of the level, passes 1 and 2 of the game's tile build
  ([tile_build.py](../../tools/bake/tile_build.py)) against the built map; each tile whose stored state differs gets
  the result (no floor or cover where nothing stands now, the floors and cover points new pieces make) and a seed
  bit, so the battle's rebuild, which clears a queued tile and works it out afresh, still has the last word.
- [native_copy.py](../../tools/bake/native_copy.py): the grower gathers the `changed` boxes of its rebuild volumes
  (`change_boxes`); `rewrite_tiles` (was `forget_taken_out`) rewrites the written map's tile data once after the
  diagonal tiles: these tiles first, then the references to taken-out actors cleared (F-156), so a build with
  deletions writes its tile data as often as before and a build of copies alone once more; the native record's
  `startTiles` and a log line say what it wrote. `rebuild_order(p, queued=False)` gives every tile of the volumes'
  reach.
- It also seeds the tiles the battle used to leave stale for good: 32 tiles inside the deleted UFO's hull kept only
  "sight blocked upward" (a bit the rebuild's queue test does not read) and are now worked out.

**Black patches on baked copies (F-158).** [relight.py](../../tools/bake/relight.py) lit a copy of one of the map's
own pieces as a change on its original's lightmap and kept the original's bake for a texel buried at either place;
a texel buried only where the original stands (a floor under a staircase) is black there, so the copy showed that
footprint in the open. Now only a texel buried where the copy stands keeps the original's bake; one buried only
where the original stands is relit as the floor under a removed piece is (its light before comes out near zero), and
the record counts it as `opened`.

Also: [ARCHITECTURE.md](../../ARCHITECTURE.md)'s tile row names the new module; [KNOWN-BUGS.md](../../KNOWN-BUGS.md):
KB-18 and KB-19 out; [findings-register.md](../../research/findings-register.md): F-157 and F-158.

Checked: the bake suite (`test_start_tiles`: on the bar with its upstairs floor strip deleted and a dumpster copied
onto open street, the strip's ten tiles keep no floor or cover point and stay queued, the tiles beside the dumpster
have cover points from the start, tiles more than four tiles away keep their bytes; it fails with the step left out.
`test_native_copy` `CopyBuriedWhereItsSourceStands`: a ground slab copied 480 units east, its 1,857 texels buried
where the source stands lit about as the open slab round them; it fails on the old rule), the upk and repo suites.
The reported project rebuilt (quick): no cover point above the ground left on a deleted piece's floor (56 within a
pod's reach before), the tiles beside the helipad open air, its top a floor with cover points; the step took 4.0 s
over 15,015 tiles. Rebuilt with the bake: the floor copy's black patches gone (897, 308 and 940 black texels to 158, 0
and 140, those left under the pieces standing on it now). In the game
([EXP-92](../../research/experiments/EXP-92-civilians-and-copy-patch.md), hidden terror battles in the lab copy): on
the project built without the fix 2 of 18 civilians started in the air, one at the deleted UFO's roof; on the fixed
build none of 36 in two battles, and the floor south of the helipad shows no patch.

Time: on a cleared map nearly every tile lies round a deleted floor, but empty tiles are cheap: the bar with its
733 pieces deleted had 13,118 tiles worked out and 8,582 written in 1.9 s.

Known gaps: the pods' other aliens, placed from the same stored tiles, were not looked at in the game.
