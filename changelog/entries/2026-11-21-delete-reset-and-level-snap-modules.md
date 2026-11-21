### Delete and Reset, and floor pieces with Level snap, in modules of their own (delete_reset.js, level_snap.js)

Editor refactor, stage P8, second part: the run of app.js from `heavy` to `resetAll` leaves it, in two modules, since
its two parts share nothing: Delete, Reset piece and Reset all, and the floor pieces with Level snap. Nothing the editor
does changes. (The landing pieces' rule that sat between them went with Clear map.)

- **[level_snap.js](../../tools/viewer/web/level_snap.js)** is new. `createLevelSnap` is made once by app.js, with the
  buildings and the hints. It holds, moved verbatim, the floor pieces (`floorData`) and a floor piece's support
  (`floorSupportOf`), Level snap and its button (`setLevelSnap`, `levelButton`, with its storage key, read into
  editor_state.js's `levelSnap` as the module is made, where the page always read it) and the Floor picker's floor
  under a point (`chosenStorey`). Its own state is inside it (the floor pieces worked out, the floors' heights).
- **[delete_reset.js](../../tools/viewer/web/delete_reset.js)** is new. `createDeleteReset` is made once by app.js,
  with the gizmo, the selection's pieces and boxes, the busy mark, the pieces', lights', effects' and boxes' roots added
  and taken away, the map's buildings changed and restored, the map's size, the landing zones, the spawn moves and
  rule, the mission picker, a broken piece drawn and the hints. It holds, moved verbatim, a large step under the busy
  mark (`heavy`, `undoStep`), Delete (`deleteSelection`, `deleteNow`), Reset piece (`resetSelected`) and Reset all
  (`resetAll`). It keeps no state of its own.
- **[app.js](../../tools/viewer/web/app.js)** makes Level snap's module where its run was. Delete and Reset's two runs
  only declared functions, which call those of the Lights, Spawns, Effects, Landing zones and Buildings views, the
  scene's pieces, the map grid, Clear map and Break and Repair: it is made after Break and Repair, where it is given
  them all, so nothing of it runs at another point as the page loads, and only the three factories made before it that
  call it (the Buildings view and the clipboard `deleteSelection`, the made pieces' looks `deleteNow`) are given its
  functions as functions that call them (at its run, twenty-two of the functions it is given would have had to be).
  app.js: 3,025 lines to 2,856; its `let` statements 15 to 14 (23 names to 22); its top-level functions 127 to 116.
  Comments of editor_state.js and ARCHITECTURE.md that placed `setLevelSnap` in app.js name the module.
  [ARCHITECTURE.md](../../ARCHITECTURE.md) names the two modules, their rows, and Delete and Reset as an example of an
  area made after the factories it calls.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 5 functions moved into
  level_snap.js and the 6 moved into delete_reset.js are the same, with no substitution. app.js against itself: its
  116 functions are the same, and the 11 moved are only in the old file. The whole moved text of each module (56 and
  131 lines) is the old text line for line, the factory's indent aside (each checked against the app.js of its own
  step). No code that runs as the page loads, before any of the page's factories is made, reaches what they return
  (a scan of app.js's top level, for them, the Buildings view, the clipboard and the made pieces' looks).
- `web_names` is clean (80 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on the commit before and on this change: on the Bar `api-names` (240 names on
  each of its three pages), `typed-pose`, `adding`, `groups`, `copy-drag`, `box-select`, `floor-boxes`,
  `map-buildings`, `clear-map`, `cover`, `floor-placing` (Level snap and the Floor picker's floor), `lights`,
  `effects` and `spawns` (deletes and resets among them); the editing run (`reset-all`, `small-defects`, `look-undo`,
  which deletes through `deleteNow`, `made-prefab`, `modals`, `draw-errors`, `failed-reads`, `let-go`,
  `paste-buildings`, `squad-read`, `ladder-floor`); on the police station `walls` and `looks`. All passed, none
  skipped. (Those not run on the stage's start commit passed in stage P8 first part's `--all`.)
