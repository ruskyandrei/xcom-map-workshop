### Diagonal cover marks follow their pieces in the editor, and the Build writes what the view shows (export 40)

Stage M5 of the plan for diagonal cover placed by hand (private/plans/todo/diagonal-cover-by-hand-and-views-plan.md,
section 5). A moved or copied slanted wall of a map took its marks along only at the Build, unseen until the game;
now the view shows it, and the Build builds what the view shows.

- **Each mark's wall** (export 40): the new [mark_walls.py](../../tools/bake/mark_walls.py) works each marked tile out
  as the game's build works out a seeded tile and names the piece each diagonal meets;
  [scene_metadata.py](../../tools/viewer/scene_metadata.py) (`diagonal_walls`) writes it on the export's directions
  ([export.py](../../tools/viewer/export.py) raises its version: each map is read again the first time it opens).
  About two seconds a map with marks, nothing for the others.
- **On the page** ([diagonal_wiring.js](../../tools/viewer/web/diagonal_wiring.js) `carriedNow`,
  [diagonal_marks.js](../../tools/viewer/web/diagonal_marks.js) `carryMark`): a map's mark whose wall is moved goes
  with it, turned with it (a quarter turn turns its corners; any other turn takes them to the nearest diagonals and
  draws the mark in the warning colour); deleted, it goes; each copy of the wall carries one of its own. A piece of
  another map brings the marks it gives at home: the library's piece record 11 carries them
  ([library.py](../../tools/viewer/library.py) `diagonal`, [library_templates.js](../../tools/viewer/web/library_templates.js)),
  and a prefab's pieces do the same. A mark the project moved, turned or deleted by hand follows nothing; a mark a
  copy carries is turned by hand but moved and deleted with the copy.
- **Saved and built**: a project of schema 7 saves the carried marks with what carries them (`by`, and `moves` or
  `gone`); the compiler ([diagonal_edits.py](../../tools/editor/diagonal_edits.py)) takes a mark gone with its piece
  away and tells the Build `pageCarries`, so the copy tool ([native_copy.py](../../tools/bake/native_copy.py)) carries
  none of its own and writes the page's marks. An older project's Build still carries the map's marks with copies of
  their pieces, as before. [build.py](../../tools/editor/build.py) runs the copy tool only for real marks.
  [editor-contracts.md](../../research/editor-contracts.md) and the findings register's F-155 say it.

Checked: on the farm, in the browser check `diagonal` (the hull chunk moved two tiles and one: its corners (39, 12) and
(41, 10) go to (41, 13) and (43, 11); turned a quarter, their corner turns; turned 30 degrees, they are skewed;
deleted, they go; undone, as the map has them) and by hand (a copy of the chunk placed where the Build's own carry put
its corners gets the same tiles, (45, 42, 0) and (47, 40, 0)); the export's walls and the library's marks on the farm
(`test_materials_and_floors.py`); the compiler's carried records and pageCarries; the copy tool writing the page's
marks with pageCarries and carrying none of its own (`test_native_copy.py`); `diagonal_marks_test.mjs` (a mark carried
by a move, a quarter turn, a half turn, a skewed turn); the bake, viewer, editor, node and repo suites.

Known gaps: a piece of another map placed through the Add panel was checked by its record (the farm's chunk brings its
two marks, shifted onto the map open), not placed in a browser check. Not played in the game yet (stage M4).
