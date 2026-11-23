### The Build no longer finds diagonal cover by itself; a project's diagonal cover marks are built (schema 7)

The first part of the plan for diagonal cover placed by hand (stages M1 and M2). The Build's finder gave diagonal
cover to door openings of slanted UFO walls (KNOWN-BUGS.md, KB-20), and the game's own marks follow no rule (F-153),
so the Build stops guessing and builds what the project marks.

- **The finder is out of the Build.** [tile_rule.py](../../tools/bake/tile_rule.py) keeps the game's cover rule; the
  finder moved to the research script that made F-153's record,
  [diagonal-finder.py](../../research/evidence/diagonal-finder.py), whose tests in
  [test_tile_rule.py](../../tools/bake/tests/test_tile_rule.py) now load it there.
  [native_copy.py](../../tools/bake/native_copy.py) asks for corners only of copies of the map's own pieces (they
  carry the map's marks, as before), and [cover_blocks.py](../../tools/bake/cover_blocks.py) asks for none. A made
  wall, a cover block or a piece of another map gets diagonal cover only where the project marks it.
- **The project's marks** (`diagonalCover`, project schema 7: marks, each a tile's middle and one to four corners, and
  the map's marked tiles taken away; [editor-contracts.md](../../research/editor-contracts.md)):
  - the compiler's new family [diagonal_edits.py](../../tools/editor/diagonal_edits.py) checks them, takes a moved or
    turned map mark's old tile away, joins marks on one tile, leaves out what it can't read, and warns of a mark on a
    tile with no floor; [native_edit.py](../../tools/editor/native_edit.py) hands them to the Build;
  - the copy tool turns them into tiles (`native_copy.diagonal_edit`), keeps every rebuild volume off the marks
    (`rebuild_spares`), and carries no map mark the project took away;
  - [diagonal_keep.py](../../tools/bake/diagonal_keep.py) writes each mark whole along its marked corners only
    (`mark_cover`): a corner's wall as the game's rule finds it, and a corner with no wall as marked (high cover, no
    step-outs, no climb, no blocking bit), which the plan's decision 3 chose; a map's marked tile taken away is written
    by the straight rule, as the game's build makes it without its seed;
  - [build.py](../../tools/editor/build.py) runs the copy tool for a project whose only change is a mark, keeps the
    marks as written in the manifest (`diagonalCover`, `diagonal_record`), and warns in its log of a corner with no
    wall and of a mark with no floor; [builds.py](../../tools/viewer/builds.py) passes them to the page with the last
    package, and the Build window's light step names them
    ([build_window.js](../../tools/viewer/web/build_window.js)).
- **The page carries the marks** through saves, drafts, Reset all and the edit count
  ([project.js](../../tools/viewer/web/project.js) schema 7, [document_state.js](../../tools/viewer/web/document_state.js),
  [document_session.js](../../tools/viewer/web/document_session.js), [delete_reset.js](../../tools/viewer/web/delete_reset.js));
  the rules for adding, turning, moving, deleting and resetting a mark are the new pure module
  [diagonal_marks.js](../../tools/viewer/web/diagonal_marks.js). The view that edits them comes next.
  [projects.py](../../tools/viewer/projects.py) takes schema 7 and refuses a save of 1 to 6.

Checked: the bake suite, with six new farm builds in `test_native_copy.py` (a turned cover block gives no diagonal
cover by itself; a mark at it is written with its corner; two corners, one with no wall; a map's mark taken away; one
turned; a taken-away mark not carried by a copy); the compiler's test of the lane; the server's schema 7 test; the new
`diagonal_marks_test.mjs`; the editor, viewer and repo suites.

Known gaps: nothing on the page edits the marks yet (stage M3). A project of 0.7.0 with a made wall or a cover block at
45 degrees builds without the corners the finder gave it, until they are marked. Not played in the game yet (stage
M4).
