### The Diagonal cover view: marks added, turned, moved and deleted by hand (Shift+C)

Stage M3 of the plan for diagonal cover placed by hand (private/plans/todo/diagonal-cover-by-hand-and-views-plan.md,
section 4, design 1: corner dots). A view of its own, a row of the rail's Views list with the key Shift+C (Shift+D is
the camera's fast pan right):

- **Drawn**: the map's diagonal cover marks over everything, each a tile's outline with an arrow toward each corner:
  amber the map's own as it is, teal added or changed by the project, pale and dashed (the view's Deleted marks
  switch) a map's mark the project deleted. View options' Diagonal cover draws them in the normal view too, never
  picked. The old overlay of cutaway.js and view_layout.js is gone; the marks have one home,
  [diagonal_wiring.js](../../tools/viewer/web/diagonal_wiring.js).
- **Edited in the view**: the tile under the pointer (a saved floor along the pointer's ray, so a cut floor's tiles are
  reached) shows its four corner dots; a click on one gives the tile cover toward that corner or takes it away, the
  last one deleting the mark. A click in a marked tile picks its mark (Ctrl or Shift adds it); a drag of a mark's
  middle dot moves the picked marks by whole tiles (a mark belongs to a tile: Snap does not apply, and the hint says
  so); Delete deletes them and Escape lets them go. Each edit is one undo step.
- **The panel** (#diagonalPanel): the mark's kind (Map's own, Changed, Moved, Added, Deleted), its tile and level, its
  corners as four buttons laid out as the view shows them, what the last build wrote for it (high or low, step-outs,
  a corner with no wall), Delete, and Reset for a map's mark changed, moved or deleted.
- The view steps aside for another and the others for it, and a piece selected from a list leaves it
  ([views.js](../../tools/viewer/web/views.js), [selection.js](../../tools/viewer/web/selection.js)); its keys come
  before the generic ones ([navigation.js](../../tools/viewer/web/navigation.js)); the edit hub's edit and scene runs
  draw it again ([edit_hub.js](../../tools/viewer/web/edit_hub.js)). The help panel, View options' tooltip,
  [ARCHITECTURE.md](../../ARCHITECTURE.md) and [UI-GUIDELINES.md](../../UI-GUIDELINES.md) say it.

Checked: the new browser check `diagonal` ([browser_diagonal.py](../../tools/viewer/tests/browser_diagonal.py), on
CsmallScout_Farm: a corner switched on the scout's mark, undone and redone, the mark dragged a tile and reset, deleted
and put back, a mark added on an empty tile, the view's keys and its stepping aside); the browser checks floor-boxes,
grid-panel, spawns, effects and api-names (the test hooks' names recorded again with the view's six); by hand in a
browser on the farm; the node and repo suites; web_names.

Known gaps: box select (T) does not take marks (Ctrl+click picks several, and a drag or Delete acts on them all). The
marks that follow their pieces come next (stage M5). The guide's section waits for M6.
