### The map's diagonal cover in the editor: View options' Diagonal cover, and a warning for a change on such a tile

Stage D0 of the diagonal cover plan. The editor shows where a map has diagonal cover and which of those tiles a
project's changes take.

- [export.py](../../tools/viewer/export.py): export 38. [scene_metadata.py](../../tools/viewer/scene_metadata.py):
  `saved_diagonal_tiles` (each tile whose cover flags carry diagonal cover: its floor's height, its cover location,
  the diagonals it faces), in the tactical data as `diagonalCover`; `changed_tiles`, the one home of the rule for the
  tiles a change stands on (the Build's [native_copy.py](../../tools/bake/native_copy.py) `changed_tiles` calls it).
- [floors.js](../../tools/viewer/web/floors.js) `changedTiles`, its twin;
  [view_layout.js](../../tools/viewer/web/view_layout.js) `diagonalCoverOverlay` (each tile outlined on its floor, an
  arrow toward its wall; amber kept, red taken); [cutaway.js](../../tools/viewer/web/cutaway.js) `drawDiagonalCover`
  (the boxes of the pieces added, moved or deleted, now and before, drawn again with the cutaway);
  [index.html](../../tools/viewer/web/index.html) the View options box; [app.js](../../tools/viewer/web/app.js) its
  wiring.
- [floor_edits.py](../../tools/editor/floor_edits.py) `diagonal_cover`, from
  [compiler.py](../../tools/editor/compiler.py): the warning `diagonal-cover-taken` naming the tiles a copy, a hidden
  or moved piece, a cover block or a piece whose flags change stands on.
- [guide.html](../../tools/release/guide/guide.html): the Diagonal cover paragraph under View options.

Checked: [floor_rules_test.mjs](../../tools/viewer/tests/floor_rules_test.mjs) (the rule on the farm's barrel cases);
`DiagonalCoverTests` in [test_materials_and_floors.py](../../tools/viewer/tests/test_materials_and_floors.py) (the
same cases, the farm's eight tiles as exported); the warning in
[test_compiler.py](../../tools/editor/tests/test_compiler.py); in the browser on a test server with the farm exported
anew: the overlay drew the eight corners, and deleting the hull piece behind the north-east two turned those red.

Known gaps: the guide's View options picture predates the box (the paragraph describes it); the main server's exports
are made anew at version 38 when it is restarted.
