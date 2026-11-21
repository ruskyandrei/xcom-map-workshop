### A made piece, its state, changes, handles and drags in a module of their own (made_handles.js)

Editor refactor, stage P7, third part: what a made piece is, its state and changes, and its handles and drags leave
app.js for one module. Nothing the editor does changes.

- **[made_handles.js](../../tools/viewer/web/made_handles.js)** is new. `createMadeHandles` is made once by app.js,
  with what it needs of app.js in one argument object: the gizmo, the camera, the controls, the renderer and the
  scene, the pieces' parts and the meshes' loading, the pointer's ray, the made pieces' panels and drawing, the
  selection and the hints. It holds, moved verbatim, the three runs of app.js that were these:
  - what a made piece is (`isMadeWall`, `isMadeSlab`, `isMadeGround`, `isMade`, `madeRoot`, `madeWallRoot`), the look
    a wall was made in (`wallLookOf`, `lookWall`) and its look's donor as a template (`wallTemplate`), with the
    heading comment of the made pieces' code;
  - the piece as it is now (`wallState`) and changing it: its mesh's record (`madeMesh`, `madeWallMesh`), a state put
    on it with its mesh drawn anew (`applyWall`), one undo step (`setWall`, `changeWall`), the ends of joined walls
    worked out again after every change (`refreshJoins`);
  - the picked made piece's handles (`handleWall`, `wallHandlesNow`, `groundHandlesNow`, `slabHandlesNow`,
    `updateWallHandles`, `wallHandleNear`, `hoverWallHandle`, the handles' words) and their drags (`startWallDrag`,
    `moveWallDrag`, `moveSlabDrag`, `moveGroundDrag`, `endWallDrag`, `applyWallSoon`, `dropQueuedWall`, `onLevel`,
    `onPlane`);
  - a rock's corners asked of the server (`rockCornersOf`) and one moved with a gizmo of its own (`pickRockPoint`,
    `releaseRockPoint`, `placePointGizmo`, `cancelPointDrag`, the point gizmo and its listeners).

  Its own state is inside it: the hovered handle, the joins' queue, a rock point's drag, Shift held and the rocks'
  corners asked. It gives app.js back the 28 functions and objects app.js, its keys, pointer handlers, draw loop,
  hooks and the other made pieces' code call, under the same names.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns what other areas read or set of it, each with
  its setter: a handle's drag (`wallDrag`, `setWallDrag`: the pointer handlers and keys read it), the opening whose
  handle was last touched (`wallFocus`, `setWallFocus`: the selection lets it go, the made pieces' panel rings it and
  Delete takes it out) and the rock point picked (`rockPoint`, `setRockPoint`: the keys and hooks read it). Two of
  app.js's own `let`s that the moved code reads go there too: the snap setting (`snapMode`, with
  `setSnapModeValue` beside app.js's `setSnapMode`, which also sets the gizmo's and draws its button) and a cover
  handle's drag (`coverDrag`, `setCoverDrag`).
- **[app.js](../../tools/viewer/web/app.js)** makes the module where the first run was, before the looks' and the
  drawing's modules, which are now given its functions directly (the looks' `wallState` is no longer called through);
  the module is given `startWallDraw`, which the drawing's module makes further down, as a function that calls it.
  What the third run did as the page loaded (the handles' layer and stems added to the scene, the point gizmo made
  with its listeners on the canvas, the Shift listeners on the window) so happens before the drawing's ghosts are made
  and its flyout's buttons get their handlers: no code between listens to the window or the canvas, and what moved
  earlier is drawn at render orders the ghosts (7) never share (the stems 8, the point gizmo's handles Infinity, its
  plane not drawn), so three.js, which consults the order objects were made only where render order and depth are
  equal, draws nothing differently. Each assignment to a moved name is now its setter's call, with the same value (18
  writes). app.js: 6,767 lines to 6,202; its `let` statements 46 to 41 (66 names to 57); its top-level functions 410 to
  369. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module, its row in where new code goes and the state it added
  to editor_state.js. A comment of [walls.js](../../tools/viewer/web/walls.js) that placed `refreshJoins` in app.js
  names the module.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 41 moved functions are
  the same with the 11 substitutions of a write by its setter's call (without them, 4 differ). app.js against itself,
  with the same substitutions: its 369 functions are the same, and the 41 moved are only in the old file (without
  them, 8 differ: the selection, the cover handles' drag, the snap's setter, and the panels and openings still in
  app.js). The whole moved text (574 lines) is the old text line for line, the factory's indent aside, with those
  substitutions and the two `let` statements whose names went to editor_state.js (now the `let` without them). No code
  that runs as the page loads, before any of the page's view and made pieces' modules is made, reaches what it
  returns.
- `web_names` is clean (64 files), and the node suite passes (31 files).
- **Browser checks** on a test server, the same 20 as on the stage's first commit: on the Bar `api-names` (240 names on
  each of its three pages), `typed-pose`, `recipe`, `destruction`, `adding`, `groups`, `copy-drag`, `library`,
  `cover` (the cover handles' drags), `floor-placing`, `made-prefab`, `modals`, `reset-all`, `draw-errors`,
  `look-undo`, `failed-reads` (a rock's corners failing once), `let-go` and `small-defects`; on the police station
  `walls` (every handle's drag, a rock's point, the snap) and `looks`. All passed, none skipped.
