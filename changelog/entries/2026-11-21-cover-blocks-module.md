### Cover blocks and invisible floors in a module of their own (cover_wiring.js)

Editor refactor, stage P8, first part: the cover blocks' and invisible floors' wiring leaves app.js for one module.
Nothing the editor does changes.

- **[cover_wiring.js](../../tools/viewer/web/cover_wiring.js)** is new. `createCoverWiring` is made once by app.js,
  with what it needs of app.js in one argument object: the gizmo, the camera, the renderer and the scene, the pieces'
  parts and the meshes' caches, the handles' helpers (`projector`, `HANDLE_PICK`, `alongLine`), the Buildings view's
  hint, the selection and the hints. It holds, moved verbatim, the two runs of app.js that were the cover pieces':
  - a cover piece as a piece of the scene: its recipe and the version a block is saved with (`coverRecipe`,
    `coverVersion`, `validCoverValues`), its mesh and material (`ensureCover`), its template (`coverSource`,
    `coverOf`) and the Add panel's Invisible kind (`coverEntries`);
  - the ground under an invisible floor as the game's floor trace finds it: the map's collision asked for once
    (`askLineCollision`, `collisionMesh`), the ground under a point (`groundAt`, `solidGround`, `outwardY`,
    `groundBox`), a floor's tiles' centres and how far its top stands over the ground there (`floorCentres`,
    `floorClearances`), and Fit to ground (`fitFloor`);
  - the piece panel's cover section (`coverPanel`, `floorNote`, `commitCover`) and a new record put on a piece
    (`applyCover`; `setCover`, one undo step);
  - the handles on a picked cover piece (`handleCover`, `coverFacesNow`, `coverHandlePoint`, `updateCoverHandles`,
    `coverHandleNear`, `hoverCoverHandle`, with their layer, spheres and stems) and their drags (`startCoverDrag`,
    `moveCoverDrag`, `endCoverDrag`).

  Its own state is inside it: whether the map's collision was asked for, the hovered handle and the pieces' boxes
  kept. It gives app.js back the 22 functions and constants app.js, its test hooks, keys, pointer handlers and draw
  loop, the clipboard's placing, the scene to and from a document, prefabs saved and placed, and the Spawns view and
  the made pieces' drawing call, under the same names.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns the map's collision as read (`lineCollision`,
  `setLineCollision`) and whether it could be read (`lineCollisionFailed`, `setLineCollisionFailed`): a piece of
  another map read (app.js's `libraryTemplate`) adds its meshes' to it, and the test hooks read both. The comment of a
  cover handle's drag (`coverDrag`) names the module.
- **[app.js](../../tools/viewer/web/app.js)** makes the module where its second run (the handles) was, after the
  Buildings view and before the made pieces: the first run reads values app.js makes between the two runs that are not
  functions (`HANDLE_PICK`, the `PL` prefix, the materials' cache), so it cannot be made where the first run was. What
  the first run did as the page loaded only made values (a floor's clearance, two ray casters, a few vectors, the
  pieces' boxes' table and the collision's material, which is never drawn: its meshes are only cast against), so that
  now happening later changes nothing; and the handles' layer, spheres and stems are made where they were, so three.js
  draws them in the same order among the scene's other objects. The scene to and from a document and prefabs saved and
  placed (made before it) are given `coverOf` and `coverVersion`, and the Spawns view `groundAt`, as functions that
  call them. The three `lineCollision ??= new Map()` (two moved, one in `libraryTemplate`) are now
  `lineCollision ?? setLineCollision(new Map())`, which sets it only when it is null, as before; the one plain write of
  `lineCollisionFailed` is its setter's call. app.js: 5,758 lines to 5,389; its `let` statements 38 to 36 (54 names to
  50); its top-level functions 343 to 311. A comment of [pieces.js](../../tools/viewer/web/pieces.js) that placed
  `coverEntries` in app.js names the module. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module, its row in
  where new code goes, the state it added to editor_state.js, the logical assignment's setter, and how an area whose
  first run needs a later value is made.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 32 moved functions are
  the same with the 2 substitutions of a write by its setter's call (without them, `askLineCollision` differs). app.js
  against itself, with the same substitutions: its 311 functions are the same, and the 32 moved are only in the old
  file (without them, `libraryTemplate` differs). The whole moved text, statements as well as functions (383 lines),
  is the old text line for line, the factory's indent aside, with those substitutions and the `let` statement whose
  names went to editor_state.js (now the `let` of the one left, with a comment naming them). No code that runs as the
  page loads, before any of the page's factories is made, reaches what it returns (a scan of app.js's top level).
- `web_names` is clean (67 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on the commit before and on this change: on the Bar `api-names` (240 names on
  each of its three pages), `typed-pose`, `recipe`, `destruction`, `adding`, `groups`, `copy-drag`, `box-select`,
  `align`, `library`, `cover` (the cover handles' drags, the cover section, an invisible floor and Fit to ground),
  `floor-placing`, `paste-buildings`, `made-prefab`, `reset-all`, `draw-errors`, `look-undo`, `failed-reads`,
  `let-go`, `small-defects`, `modals`, `prefabs`, `prefab-effects` and `ladder-floor`; on the police station `walls`
  and `looks`. All passed, none skipped.
