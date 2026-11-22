### A build keeps a map's diagonal cover away from its edits, and reads a rebuild volume's reach as the game does

A built map lost the cover a unit gets in the corner of a slanted wall (the UFO maps, the Chryssalid hive): the
battle's tile rebuild clears a tile's diagonal cover for good (F-149), and a build's rebuild volumes reached every
tile of a map with a larger grid and, on many maps, tens of tiles round any edit. The second half was not known: the
Build took a volume's reach to be its box's diagonal, where the game takes its brush's sphere times its largest scale
(F-150, found when the first version of this fix failed in the game).

- [rebuild_fit.py](../../tools/bake/rebuild_fit.py), new: the tiles a volume queues (`span`, the game's rule), and
  `fit`, the cubes that take a box of tiles and none of a set of forbidden ones (`pose`: a cube's centre and radius).
- [native_copy.py](../../tools/bake/native_copy.py):
  - `volume_sphere` reads a volume's sphere as the game does (`brush_sphere` times the largest scale), so
    `rebuild_order` and `ladder_order` read the battle's real work; `box_reach` is the radius of a template's clone
    over a box, `reach_box` the box that gives a wanted radius.
  - `diagonal_tiles` (the map's baked tiles with COVER_Diagonal) and `rebuild_spares` (what a volume must leave
    alone: every diagonal tile its own box does not hold, with the two tiles over it).
  - `add_rebuild_volume` makes a volume that would reach one of those as several fitted ones, the first its
    `export`; `add_to_level` lists the others after it. The record gains `fitted` (the volumes, the tiles spared),
    and `diagonalRebuilt` for diagonal tiles inside the box, which are rebuilt; the Build's log says both
    (`diagonal_words`). Its `rebuildExtent` is the game's radius.
  - `tile_volume` (a ladder copy's top tile) is placed by its sphere: radius 24 whatever the template's shape,
    where a flat template gave it 119 and three tiles by three.
  - A volume that reaches no diagonal tile is made as before, so a build of a map without diagonal cover, or of an
    edit far from it, is unchanged but for a ladder's tile volume.
- [shell.py](../../tools/bake/shell.py): a grown grid's whole-map volume leaves every diagonal tile out (`spare`),
  and says so in its report and log.
- [diagonal-cover.py](../../research/evidence/diagonal-cover.py) reads a volume's reach by the corrected rule;
  [rebuild-reach.py](../../research/evidence/rebuild-reach.py), new, with
  [rebuild-reach-2026-11-22.json](../../research/evidence/rebuild-reach-2026-11-22.json): each base map's template
  and how far a small volume cloned from it reaches (1.6 to 77.7 tiles, 2.6 by the old reading).
- [findings-register.md](../../research/findings-register.md): F-149 rewritten with the fix and its game runs, F-150
  new. [KNOWN-BUGS.md](../../KNOWN-BUGS.md): KB-14 narrowed to what the fix leaves (it stays open).
  [cover-build.md](../../research/native/cover-build.md) and [ladder-links.md](../../research/native/ladder-links.md):
  a note each. [ARCHITECTURE.md](../../ARCHITECTURE.md): the rebuild volume's row.

Checked: [test_rebuild_fit.py](../../tools/bake/tests/test_rebuild_fit.py) (a cube's volume takes its tiles and no
others, the fits cover their box and nothing forbidden); `DiagonalCoverKept` and `NoDiagonalCover` in
[test_native_copy.py](../../tools/bake/tests/test_native_copy.py) and the grown farm in
[test_shell.py](../../tools/bake/tests/test_shell.py) (on CsmallScout_Farm: a volume beside a diagonal tile, over
one, far from them; the radius a record gives; a tile volume on a flat template; the grown grid's rebuild queues
every tile it did but the 8 and the tiles over them); the bake, editor, upk and repo suites. In the game: a hidden
run of the farm++ project built again (CSmallScout_Farm grown to 67 by 91 by 18, LWR): its save at turn 1 has 7 of the
map's 8 diagonal tiles as baked (0 of 8 before), the eighth taken by the game's own rebuild round a Meld canister two
tiles from it; soldiers on three of the seven read in cover, value 50, teleported and walked on, and on the eighth
none; the rest of the map's rebuild is as before (the two battles' saves compared), and a soldier walked into the
grown strip. The first version of the fix, sized by the old reading, failed the same run: 0 of 8.

Known gaps: a diagonal tile an edit is on or next to is still rebuilt (KB-14); copied, moved and stamped slanted
walls bring no diagonal cover; plain Enemy Within not played (the rule is the exe's, which both share); every other
rebuild volume still reaches as far as the game makes it, so a battle on some maps starts with most of the map to
work out again, as before.
