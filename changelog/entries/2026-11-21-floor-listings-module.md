### The building floors a piece is listed on in a module of their own (floor_listings.js)

Editor refactor, stage P8, second part: the building-floor listings (where the project's buildings and the map's own
list a piece, as the Build lists it) and the key of the pieces' edits leave app.js for one module. Nothing the editor
does changes.

- **[floor_listings.js](../../tools/viewer/web/floor_listings.js)** is new. `createFloorListings` is made once by
  app.js, with what it needs of app.js in one argument object: the buildings and the map's buildings changed, a
  piece's box and its original's carried to where it stands. It holds, moved verbatim, `projectListings`,
  `listingsNow`, `mapListings` and `editedKey`. It keeps no state of its own (what it works out for a piece is kept on
  the piece's root, as before) and gives back the three functions app.js's selection, edit hub and test hooks, the
  cutaway, Clear map's ground grid and the Buildings view call.
- **[app.js](../../tools/viewer/web/app.js)** makes it where its run was, after the scene's pieces: the run only
  declared, so nothing moves as the page loads. It is given the Buildings view's `allBuildings`, `mapEdits` and
  `mapIdOf` as functions that call them (that view is made further down). app.js: 3,115 lines to 3,025; its `let` statements stay 15 (23 names: the
  run had none, what the cutaway last followed went with it); its top-level functions 131 to 127. A comment of
  editor_state.js that placed `editedKey` in app.js names the module. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module and its row.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 4 moved functions are
  the same, with no substitution. app.js against itself: its 127 functions are the same, and the 4 moved are only in
  the old file. The whole moved text (96 lines) is the old text line for line, the factory's indent aside. No code that
  runs as the page loads, before any of the page's factories is made, reaches what it returns (a scan of app.js's top
  level, for it, the cutaway, the Buildings view and Clear map).
- `web_names` is clean (78 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on the commit before and on this change: on the Bar `api-names` (240 names on
  each of its three pages), `map-buildings` (the listings of a piece in a changed building of the map's own),
  `floor-boxes` (a piece's floors in the project's buildings), `box-select`, `clear-map`, `floors-cut`, `floor-tiles`,
  `floor-placing`, `copy-drag`, `typed-pose` and `adding`; `paste-buildings`, `reset-all`, `small-defects` and
  `ladder-floor`. All passed, none skipped.
