### The map's buildings' records with the Buildings view (buildings_wiring.js)

Editor refactor, stage P8, second part: the records app.js kept at its top of the map's buildings (every building the
floors code reads, which of the map's own can be edited, which the project changed or deleted, and what the project
saves of them) move into the Buildings view's module. Nothing the editor does changes.

- **[buildings_wiring.js](../../tools/viewer/web/buildings_wiring.js)**: `createBuildingsWiring` holds, moved verbatim
  at the start of its body, `allBuildings` (with `PROJECT_BUILDING`), `mapEditable`, `mapIdOf`, `mapTarget`,
  `mapKind`, `mapFloors`, `mapChanged`, `mapEdits` (with its cache, now the factory's own state), `savedBuildings` and
  `freshBox`. They read only the scene and the buildings' state (editor_state.js's) and the view's functions read
  them, so they are not a pure module; nine of them were given to the factory and now are its own, and it gives
  back the four other areas call (`allBuildings`, `mapEdits`, `mapIdOf`, `savedBuildings`): app.js's selection, edit
  hub and test hooks, the scene to and from a document, Clear map, the floor listings, Level snap, the cutaway and
  Reset all.
- **[app.js](../../tools/viewer/web/app.js)**: the run is gone from its top. It only declared (functions, and constants
  of functions and of a word), so its moving later, to where the Buildings view is made, changes nothing as the page
  loads. The scene to and from a document and Clear map, made before the Buildings view, are given `savedBuildings` and
  `allBuildings` as functions that call them. app.js: 3,588 lines to 3,525; its `let` statements 20 to 19 (30 names to
  29); its top-level functions 169 to 159. The comment of editor_state.js's `mergedBuildings` names the module, and the
  head of [clear_map.js](../../tools/viewer/web/clear_map.js) no longer says it is given the camera and the renderer (it
  is not). [ARCHITECTURE.md](../../ARCHITECTURE.md) says the records are the Buildings view's.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 10 moved functions
  (with the constants of functions among them) are the same in buildings_wiring.js, with no substitution. app.js
  against itself: its 159 functions are the same, and the 10 moved are only in the old file. The whole moved text (64
  lines) is the old text line for line at the start of the factory's body, its indent aside. No code that runs as the
  page loads, before any of the page's factories is made, reaches what the factory returns (a scan of app.js's top
  level, for it, the scene to and from a document and Clear map).
- `web_names` is clean (75 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on the commit before and on this change: on the Bar `api-names` (240 names on
  each of its three pages), `map-buildings` (the map's own buildings edited, deleted and restored, their records and
  saved form), `floor-boxes`, `box-select`, `clear-map`, `floors-cut`, `floor-placing` and `projects`;
  `paste-buildings`, `reset-all`, `small-defects` and `made-prefab`; and `documents`. All passed, none skipped.
