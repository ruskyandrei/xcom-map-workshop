### What a selected root is called, and the selection's pieces that can be copied, lined up or grouped, with the selection

Editor refactor, stage P9, fourth part: the selection's rules that app.js still declared go to selection.js. Nothing
the editor does changes.

- **[selection.js](../../tools/viewer/web/selection.js)**: `rootName` (what a selected root is called in a list: a
  piece by its mesh, a light by its actor, a floor box by its building, an effect by its record), moved verbatim to its
  top as a plain export beside `selectionWords`: it reads only its argument, the scene and the buildings' names. The
  sets the gizmo's selection gives, moved verbatim into `createSelection`, which gives them back: `copyable` (the
  pieces, lights and effects that can be copied or deleted, hidden helpers shown for inspection left out),
  `copyablePieces` (those Align lines up), `selectedBoxes` (the floor boxes selected with pieces in the normal view) and
  `groupables` (what a group can hold). The factory is given the Lights and Effects views' `lightViewOnly` and
  `effectViewOnly`, which `copyable` reads, and no longer `copyable` or `rootName`.
- **[app.js](../../tools/viewer/web/app.js)**: the factories made before the selection that are given the sets (the
  groups `groupables`, Align `copyablePieces`, the Lights view and prefabs saved and placed `copyable`) are given
  functions that call them, as they are given `select`; none calls them as the page loads. Delete and Reset, made after
  it, are given them as before. Its imports only `rootName` used went with it (`recordName`, `buildingMeta`).
  1,311 lines to 1,297; top-level functions 17 to 12; `let` statements 5 (7 names).
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the selection's part in how the page fits (a sentence of its own), its
  row, and the factories the placement rule gives its functions as functions that call them.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the five the same as app.js's at the commit before (`export`
aside; `createSelection` differs by its arguments, what moved into it and what it gives back); every name they read
resolves as before (by eslint-scope); `web_names` clean; the node and repo suites; the twenty-edit recording the same
as on the stage's start commit, all 52 steps; the stage's 43 named browser checks pass on the Bar and the police
station (`streams` skips a part on the Bar as before).
