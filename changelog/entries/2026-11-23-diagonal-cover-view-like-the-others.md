### The Diagonal cover view picks and moves marks as the other views do; new marks come from the Add panel

The user's correction of the view (23 November 2026): the pointer no longer adds a mark wherever it goes. The view
behaves as the Landing zones and Spawns views do ([diagonal_wiring.js](../../tools/viewer/web/diagonal_wiring.js)):

- **Hovering a tile adds nothing.** A click on a mark picks it (Ctrl or Shift adds it to the picked), a click beside
  the marks lets them go; the mark under the pointer is outlined.
- **The picked mark** shows its gizmo and its four corner dots: a click on a dot switches that corner (the last one off
  deletes the mark), [ and ] turn its corners a quarter, and the gizmo's arrows move the picked marks by whole tiles
  across and levels up. A mark belongs to a tile, so its moves ignore Snap: the user agreed (UI-GUIDELINES.md, the
  Snap bullet, now names the exception) and the hint says so. The corner dots stand at the tile's corners and the
  gizmo is smaller than a piece's, so they stay apart. The drag of a mark's middle dot is gone.
- **A new mark comes from the Add panel**: its Diagonal cover kind has one entry ([clipboard.js](../../tools/viewer/web/clipboard.js),
  [library.js](../../tools/viewer/web/library.js), [piece_categories.js](../../tools/viewer/web/piece_categories.js),
  [pieces.js](../../tools/viewer/web/pieces.js), with its own icon); chosen, the view comes on and a ghost mark
  follows the pointer over the tiles, its corner toward the quarter of the tile the pointer is in, and a click puts it
  down and picks it. Escape stops.
- [diagonal_marks.js](../../tools/viewer/web/diagonal_marks.js) has the rules for it (`addMark`, `cornerNear`,
  `setCorners`, `turnedCorners`); the help panel, the view's tooltip and its panel's note say the new ways.

Checked: the browser check `diagonal` rewritten for it ([browser_diagonal.py](../../tools/viewer/tests/browser_diagonal.py):
a click on an empty tile adds and picks nothing; a click picks the mark with its gizmo; a corner dot; ]; the gizmo's X
arrow dragged moves it two whole tiles with Snap off; the Add panel's entry adds a mark toward the corner nearest the
click); the browser checks api-names (the hook `diagonalGizmo` recorded), adding, library, clear-map, spawns and
grid-panel; by hand in a browser on the farm; `diagonal_marks_test.mjs`; the node and repo suites; web_names.
