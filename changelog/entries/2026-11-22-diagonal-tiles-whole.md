### Diagonal cover kept under a change and carried by copied corners: the Build writes whole tiles

Stages D2 and D3 of the diagonal cover plan. A slanted corner's diagonal cover now survives an edit on its own tile,
and a copied or moved slanted wall brings it along.

- [diagonal_keep.py](../../tools/bake/diagonal_keep.py) has three new parts:
  - `plan_whole` works a tile out whole as the game's full build would: passes 1 and 2, the link step and the
    ladders' links (tile_build, tile_rule, tile_links), with the tiles round it as the battle will have them.
  - `find_new` finds the new corners.
  - `refit` makes any rebuild volume that would reach a new corner as several that do not, in its place in the
    level's list.

  `write` takes the tiles under a change (`whole`) and the candidates for new corners beside the tiles next to one,
  and its record gains `whole` (with `newCorner`: `carried` or `found`) and `refitted`. It writes nothing, and the
  manifest has no `diagonalCover`, when there is nothing to write.
- [native_copy.py](../../tools/bake/native_copy.py):
  - `rebuild_spares` keeps every seeded tile in a changed box out of the rebuild, and names the ones a change stands
    on in the volume's `diagonalWhole`.
  - `diagonal_candidates` says where a new piece may make a corner. A copy of one of the map's own pieces carries the
    map's marks: a tile it stands on whose place on the original had diagonal cover gets it where a diagonal still
    gives cover. A made piece or a cover block ([cover_blocks.py](../../tools/bake/cover_blocks.py)) gets the corners
    the finder takes.
  - The Build's log names the new corners.
- The editor:
  - The compiler's `diagonal-cover-taken` warning is now the note `diagonal-cover-rewritten`
    ([floor_edits.py](../../tools/editor/floor_edits.py)).
  - View options' Diagonal cover draws a corner under a change blue instead of red
    ([view_layout.js](../../tools/viewer/web/view_layout.js), [cutaway.js](../../tools/viewer/web/cutaway.js)), and
    its tooltip and the guide's paragraph ([guide.html](../../tools/release/guide/guide.html)) say what the Build does.
- [KNOWN-BUGS.md](../../KNOWN-BUGS.md): KB-14 ("An edit on a slanted corner takes its diagonal cover") is taken out
  with this fix.
- [findings-register.md](../../research/findings-register.md): F-155, and F-149 and F-153 updated. ARCHITECTURE.md's
  tile build row names the new parts.

Checked:
- [whole-tile-check.py](../../research/evidence/whole-tile-check.py) (new) over the install's 97 base maps:
  - all 299 seeded tiles get their static flags, cover, cover location and links back exactly; 293 get their floor
    records too;
  - 3,440 of 3,840 random floor tiles come back whole.
- Tests in test_native_copy.py's DiagonalCoverKept (barrels beside and on corners, a moved hull chunk, a turned cover
  block, the hull's corner walls hidden) and test_tile_rule.py's FarmWholeTiles.
- The full suites.

Known gaps:
- A piece brought from another map does not carry its home map's marks: the finder decides there.
- A volume made without the change's boxes (a ladder's tile volume, a cleared map's) still rebuilds what it reaches.
- Not yet played in the game: a hidden run of a moved hull chunk is under way, and its outcome goes into F-155.
