### The hint line and the busy mark in modules of their own (hints.js, busy.js)

Editor refactor, stage P9, third part: the hint line under the view and the busy mark for slow steps leave app.js.
Nothing the editor does changes.

- **[hints.js](../../tools/viewer/web/hints.js)** is new: `createHints` holds, moved verbatim, `dragHint` (what a held
  gizmo handle moves and how to back out), `flashHint` (a short notice that goes after a moment) and `restingHint` (how
  to place what is being placed, or box select's drag). It is given `$` and the gizmo; the notice's timer stays
  editor_state.js's.
- **[busy.js](../../tools/viewer/web/busy.js)** is new: `createBusy` holds, moved verbatim, the busy mark's constants
  and steps under way, `busyStart`, `busyPaint`, `nextFrame`, `busy`, `busyHeld` with its listeners on the window that
  hold the view's clicks and keys while a mark put up at once is shown, `breather` and `buildRoots`. It is given `$`
  and the scene's pieces' `buildRoot`, and gives back `BUSY_PIECES`, `buildRoots`, `busy`, `busyPaint`, `busyStart` and
  `nextFrame`.
- **Where app.js makes them:** where their code was (one run of app.js, the busy mark's between the drag's hint and the
  others), so the busy mark's listeners are added to the window at the same point as before. The scene's pieces, made
  earlier, are given `flashHint` as a function that calls it; no code that runs as the page loads uses the hints or
  the busy mark before they are made.
- **[app.js](../../tools/viewer/web/app.js)**: three imports of editor_state.js only the moved code used went with it.
  1,650 lines to 1,555; top-level functions 56 to 46. [ARCHITECTURE.md](../../ARCHITECTURE.md): the two modules in
  how the page fits, their rows, and the new factories (with `createMapFamilies`) in the list of those made with one
  argument object.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the ten functions the same as app.js's at the commit before,
app.js's other 46 the same; the busy mark's run (its constants and the window's listeners with it) and the hints'
are app.js's line for line, two spaces further in; every name the moved code reads resolves as before (by
eslint-scope); `web_names` clean; the twenty-edit recording the same as on the stage's start commit, all 52 steps;
browser checks `api-names`, `typed-pose`, `copy-drag`, `adding`, `library`, `box-select`, `cover`, `floor-placing`,
`builder`, `paste-buildings`, `reset-all`, `let-go`, `small-defects`, `modals`, `walls` and `made-prefab` pass.
