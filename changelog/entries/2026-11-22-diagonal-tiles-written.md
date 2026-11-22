### A diagonal cover tile next to a change is written by the Build, not rebuilt by the battle

Stages C2 and D1 of the diagonal cover plan. A corner with diagonal cover that stood next to a project's change (in
its rebuild box, not under the change) was rebuilt by the battle and lost its cover (KB-14). The Build now leaves such
a tile out of the rebuild and writes what the change can alter of it itself, from the game's own tile rules worked
out against the built map.

- [tile_build.py](../../tools/bake/tile_build.py), new: passes 1 and 2 of the game's tile build for a tile
  (occupancy and floor, standing room, the cover step, the twelve blocking bits), as research/native/cover-build.md
  reads them, with what the bake showed the reading lacked (F-152): a check starting inside a solid, the near bit on
  every tile, PathBlockingVolumes first.
- [tile_world.py](../../tools/bake/tile_world.py): the occupancy's box test, octree bounds, the pathing and sight
  trace kinds, all-hits line checks, box elements told from hulls, PathBlockingVolumes; the script packages found in
  the install when a package's own folder has none (a Build's output: `script_defaults`).
- [native_copy.py](../../tools/bake/native_copy.py): `add_rebuild_volume`'s `changed` (the world boxes of what
  changed: a copy's, a hidden or moved piece's, a piece whose flags change), passed by every caller that has them;
  `changed_tiles`; `rebuild_spares` keeps a diagonal tile in the box that no change stands on, with the two tiles
  over it, and names it `diagonalWritten`; `build` writes those tiles after writing the map, the manifest's
  `diagonalCover` their record.
- [diagonal_keep.py](../../tools/bake/diagonal_keep.py), new: such a tile's blocking bits, diagonal cover (flags and
  location) and links worked out against the built map's pieces, the tiles round it made as the battle will (its
  step-outs, its links); a plain link the bake-proven rule rules out is dropped, a typed link to a tile with no floor
  dropped, none added; the rest of its flags as the bake has them.
- [tile-build-check.py](../../research/evidence/tile-build-check.py), new, and its record
  [tile-build-check-2026-11-22.json](../../research/evidence/tile-build-check-2026-11-22.json): the passes over the
  install's 96 base maps against their bakes (98.3% of 198,802 tiles bit for bit).
- [findings-register.md](../../research/findings-register.md): F-152, F-149's remainder. [KNOWN-BUGS.md](../../KNOWN-BUGS.md):
  KB-14 narrowed to an edit on the corner's own tile. [ARCHITECTURE.md](../../ARCHITECTURE.md): the row.

Checked: `DiagonalCoverKept` in [test_native_copy.py](../../tools/bake/tests/test_native_copy.py) (a Build on
CsmallScout_Farm with a barrel beside the corner (39, 12, 0) and one on the corner (49, 22, 0): the first and
(51, 20, 0), in the second's ring, written and out of the rebuild, the corner keeping its diagonal cover toward the
hull; (49, 22, 0) rebuilt; the corner nothing changed near written exactly as baked);
[test_tile_rule.py](../../tools/bake/tests/test_tile_rule.py); the bake, upk, editor and repo suites. Not played in
the game yet (stage C3).

Known gaps: a corner a change stands on is still rebuilt (the writer can't make a tile's links whole until the
neighbour step is read); a written tile's 2-by-2, drop and edge bits stay as baked; a plain link the change makes
possible is not added (units step there the other way, or round); the highway maps match the bake least (F-152).
