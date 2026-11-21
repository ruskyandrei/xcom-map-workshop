### The play area, the map's size and the Map grid in a module of their own (map_grid.js)

Editor refactor, stage P8, second part: the play area, the map's size as the project sets it and the rail's Map grid
leave app.js for one module. Nothing the editor does changes.

- **[map_grid.js](../../tools/viewer/web/map_grid.js)** is new. `createMapGrid` is made once by app.js, with what it
  needs of app.js in one argument object: the camera's controls, the renderer and the scene, the gizmo, picking and the
  handles' line (`alongLine`), a piece's box, the made slabs, Clear map's notes and the ground grid, the project's
  change, the popups and the hints. It holds, moved verbatim, the run of app.js that was theirs:
  - the play area drawn as lines and faint walls, and View options' Play area (`drawPlayArea`, `setPlayArea`);
  - the map's size: the map's own kept (`ownSize`), the grid a stage asks for (`stageDims`), the grid drawn at a size
    (`showGrid`) and a size set with its new area drawn as a faint sheet (`setStage`, `bareMap`);
  - the rail's Map grid: what the grid can be (`gridRule`), the cursor's floors on it (`storeysNow`, `madeSlabBoxes`),
    its handles (`placeGridHandles`, `gridHit`, `gridHandleAt`), its panel (`gridPanel`), the tool (`setGridTool`), a
    new size as one undo step (`commitStage`, `stageFor`), a handle's drag (`startGridDrag`, `moveGridDrag`,
    `endGridDrag`), and the panel's buttons and the Map menu's Map grid.

  Its own state is inside it (whether the tool showed the play area, the cursor's floors kept). It gives app.js back
  the 13 functions and objects app.js's scene start, pointer handlers, keys, View options and test hooks, the scene to
  and from a document, the document session, Clear map, the Buildings view and Reset all call, under the same names.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns the map's own size as exported (`ownGrid`,
  `setOwnGrid`: app.js's scene start drops it), whether the Map grid is on (`gridTool`, `setGridToolValue`, beside the
  module's `setGridTool`, which also draws) and a handle's drag (`gridDrag`, `setGridDrag`): app.js's pointer handlers
  and keys read the last two, and the test hooks the tool.
- **[app.js](../../tools/viewer/web/app.js)** makes the module where the run ended. Two parts of the run stay where
  they were: `alongLine` (the handles' line, which the cover blocks' and the made pieces' handles use too) and the
  grid's four pointer listeners, which are app.js's pointer handlers (they write its `pointerStart`), now under a
  comment saying they take the press for the Map grid. Nothing else of app.js ran between the run's first line and its
  last, so the play area's, the new area's and the handles' groups and materials are made at the same point among the
  page's other code as before (three.js draws them in the same order), and the panel's buttons' handlers, set after
  the pointer listeners now, are on other elements. The scene to and from a document and the document session, made
  before it, are given `ownSize` and `setStage` as functions that call them. The five writes of the three moved names
  (one in the scene start) are their setters' calls. app.js: 4,271 lines to 4,048; its `let` statements 31 to 28 (44
  names to 39); its top-level functions 224 to 204. A comment of editor_state.js and one of
  [project.js](../../tools/viewer/web/project.js) that placed `setStage` in app.js name the module.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 20 moved functions are
  the same with the 5 substitutions of a write by its setter's call (without them, `ownSize`, `setGridTool`,
  `startGridDrag` and `endGridDrag` differ). app.js against itself, with the same substitutions: its 204 functions are
  the same, and the 20 moved are only in the old file (without them, `startScene` differs). The whole moved text (238
  lines) is the old text line for line, the factory's indent aside, with those substitutions and the two `let`
  statements whose names went to editor_state.js (now a comment, and the `let` of the one left). No code that runs as
  the page loads, before any of the page's factories is made, reaches what it returns (a scan of app.js's top level).
- `web_names` is clean (74 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on the commit before and on this change: on the Bar `api-names` (240 names on
  each of its three pages), `clear-map` (the map grid's handles and sizes among it), `play-area`, `floor-boxes`,
  `projects` and `documents`. All passed, none skipped.
