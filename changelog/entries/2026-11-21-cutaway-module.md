### The cutaway, the tile grid and the Floor tiles overlay in a module of their own (cutaway.js)

Editor refactor, stage P8, second part: the cutaway, the tile grid, View options' Floor tiles overlay and the Floor
picker's buttons leave app.js for one module. Nothing the editor does changes.

- **[cutaway.js](../../tools/viewer/web/cutaway.js)** is new. `createCutaway` is made once by app.js, with what it
  needs of app.js in one argument object: the scene, the tile grid's group, the cut materials and the patch helpers'
  wireframe, the gizmo, the pieces' listings, the buildings, the landing a moved zone takes along, box select's box,
  picking, the floor buttons, the selection and the hints. It holds, moved verbatim, the cutaway (`cutaway`, with
  `WHOLE_OVERHANG`), the tile grid (`tileTargets`, `updateTileGrid`), the Floor tiles overlay (`signatureColor`,
  `drawFloorTiles`, `floorTileHit`, `floorTip`, `floorTileSelect`) and the Floor picker's buttons (`floorOptions`). Its
  own state is inside it (the actors shown with their ceilings, the tiles' owners). It gives back the six functions
  app.js's edit hub, scene start, View options, pointer handlers, draw loop and test hooks, the Landing zones and
  Buildings views and Clear map call, under the same names.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns what the cutaway last followed (`cutKey`,
  `setCutKey`: the edit hub runs the cutaway again only when the pieces' edits changed), what the tile grid was drawn
  round (`tileKey`, `setTileKey`: View options' grid drops it) and the overlay as drawn (`floorTileLayer`,
  `setFloorTileLayer`: the draw loop and the test hooks read it).
- **[app.js](../../tools/viewer/web/app.js)** makes the module where its run was, after Break and Repair: the run
  only declared (functions, and a constant), so nothing it did as the page loaded moves. The Landing zones and
  Buildings views and Clear map, made before it, are given `cutaway` and `floorOptions` as functions that call them.
  The six writes of the three moved names (one in View options' grid) are their setters' calls. app.js: 3,298 lines to 3,115; its `let` statements 18 to 15 (28 names to
  23); its top-level functions 140 to 131. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module, its row and the state it
  added.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 9 moved functions are
  the same with the 6 substitutions of a write by its setter's call (without them, `cutaway`, `updateTileGrid` and
  `drawFloorTiles` differ). app.js against itself, with the same substitutions: its 131 functions are the same, and
  the 9 moved are only in the old file. The whole moved text (190 lines) is the old text line for line, the factory's
  indent aside, with those substitutions and the two `let` statements whose names went to editor_state.js (now the
  `let`s of the ones left). No code that runs as the page loads, before any of the page's factories is made, reaches
  what it returns (a scan of app.js's top level, for it, the Landing zones and Buildings views and Clear map).
- `web_names` is clean (77 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on the commit before and on this change: on the Bar `api-names` (240 names on
  each of its three pages), `floors-cut` (the Floor picker cuts the buildings), `tile-grid`, `tile-footprints`
  (Interior's cuts among them), `floor-tiles` (the overlay, its tip and a click on a tile), `header` (View options'
  grid; not run on the stage's start, it passed in stage P8 first part's `--all`), `play-area`, `clear-map`,
  `floor-boxes`, `map-buildings`, `box-select` and `spawns`; `reset-all`, `paste-buildings` and `small-defects`; on the
  police station `streams` (the mission picker's streams cut) and `walls`; on TempleShip `temple-interior` and
  `temple-look`. All passed (one part of `streams` skips on the police station on both commits: no streamed piece is
  drawn there to edit).
