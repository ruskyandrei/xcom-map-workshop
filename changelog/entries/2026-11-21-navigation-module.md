### The camera, snap and keys in a module of their own (navigation.js)

Editor refactor, stage P9, second part (the plan's P9 step 4): how the user drives the view and the editor leaves
app.js. Nothing the editor does changes.

- **[navigation.js](../../tools/viewer/web/navigation.js)** is new. `createNavigation` holds, moved verbatim from six
  runs of app.js (377 lines): the edit hub's `tools` refresh (the gizmo's mode buttons, snap, the axes, the pivot and
  Selected; P9a left it in app.js) and the snap button (`snapButton`); Frame and the framing (`frame`, with the near
  plane the last framing set); the gizmo's mode buttons' handlers and the pivot (remembered); `setSnapMode` and the
  snap button's handler; the camera's keys (arrows and WASD, Q and E, Shift), the look-drag along the view, the wheel's
  zoom to the point under the cursor and View options' camera speeds and "Keys move along the view"; and the editor's
  keys. Its state is inside it (the keys held, Shift, the speeds, a look-drag, the wheel's anchor, the near plane). The
  snap's table (`SNAPS`) and `RECIPE_NOTE` are plain constants at its top, `RECIPE_NOTE` exported: the selection, made
  earlier, is given it by app.js as before. It gives back `frame`, `panCamera` (the draw loop) and `setSnapMode` (the
  test hooks). It is given 91 of app.js's names (the areas' functions the keys call among them) and imports the rest of
  what the moved code read (47 names of editor_state.js, `QUARTER`, `onHub`, `recall` and `remember`, the view's
  bounds).
- **Where app.js makes it:** where the camera's keys were, the last of its runs, so that the listeners it adds to the
  document, the window and the canvas (the keys, the look-drag, the wheel) keep their places among the others'. Its
  earlier runs now run there, later: the gizmo buttons' handlers (no other code sets a handler on those buttons),
  the quiet `setPivot` of a remembered pivot (nothing reads the pivot as the page loads), and the `tools` refresh's
  registration (a probe of the page, the hub's runs recorded with how far app.js had loaded: no run of the hub happens
  while app.js loads, on a map or in the builder; the first come as the scene opens). The prefab builder's session, made
  earlier, is given `frame` as a function that calls it; `applyLighting`, a `let` `startScene` sets, is given so too.
- **[app.js](../../tools/viewer/web/app.js)**: the imports only the moved code used went with it. app.js: 2,277 lines
  to 1,918; its top-level functions 105 to 95; its `let` statements 12 (17 names) to 8 (12 names). `toggleButton` (the
  Linked button's) stays.
- [edit_hub.js](../../tools/viewer/web/edit_hub.js): the `tools` refresh's owner in `RUNS`' comment (its place in the
  run unchanged). [editor_state.js](../../tools/viewer/web/editor_state.js) and
  [ARCHITECTURE.md](../../ARCHITECTURE.md): the keys and `setSnapMode` named where they now are; navigation.js in how
  the page fits, its row and its factory among the page's; the event wiring app.js keeps no longer has the keys; why
  navigation is made where its last run was.

Checked:
- **The move:** each of the six runs is app.js's at the commit before line for line, two spaces further in (the snap's
  constants at the module's top as they were, `RECIPE_NOTE` with `export`), none left in app.js;
  [moved_code.py](../../tools/repo/moved_code.py): the ten functions moved (`snapButton`, `frame`, `togglePivot`,
  `setSnapMode`, `turnCamera`, `panCamera`, `lookBy`, `setFlyKeys`, `zoomPoint`, `wheelZoom`) the same as
  `createNavigation.*`, app.js's other 95 the same. Each of the 159 names the moved code reads resolves as before: the
  same import, or `createNavigation`'s argument of that name, which app.js gives under it (a script of the stage's, by
  eslint-scope). No code that runs as the page loads reaches its returns before it is made.
- **The twenty-edit recording** (stage P9a's 52 steps, which trace `snapButton` among the panel functions): the same as
  on the stage's start commit, all 52 steps.
- `web_names` is clean (86 files); the node suite passes (32 files).
- **Browser checks** on a test server, on the Bar: `zoom`, `pan`, `pivot`, `speeds`, `let-go` and `text-select` (the
  stage's; the table has no `tool-keys`, `arrow-pan`, `turn`, `drag-look` or `camera-speeds`: `pan` and `speeds` are
  those), and `api-names`, `typed-pose`, `recipe`, `destruction`, `adding`, `groups`, `copy-drag`, `box-select`,
  `floor-boxes`, `map-buildings`, `clear-map`, `align`, `library`, `cover`, `lights`, `effects`, `header`,
  `frame-bounds`, `builder`, `modals`, `reset-all`, `draw-errors`, `look-undo`, `failed-reads`, `ladder-floor` and
  `small-defects`: all 32 passed.
