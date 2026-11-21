### Drawing a made piece in a module of its own (made_drawing.js)

Editor refactor, stage P7, second part: the Build menu and the drawing of a made wall, room, floor, roof or ground
shape leave app.js for one module. Nothing the editor does changes.

- **[made_drawing.js](../../tools/viewer/web/made_drawing.js)** is new. `createMadeDrawing` is made once by app.js,
  with what it needs of app.js in one argument object: the gizmo, the camera, the renderer and the scene, the made
  pieces' donor template and request, the ground under the pointer, the paste, the Buildings view's boxes and the
  groups' lock. It holds, moved verbatim, the run of app.js that was the drawing's:
  - the Build menu: the Add button's flyout, whose tools start drawing at once (`BUILD_TOOLS`, `startBuild`,
    `markBuildTool`, the flyout's buttons);
  - a made piece drawn in a look (`startWallDrawing`, `stopWallDrawing`, `wallHint`), dragged out over the ground with
    its ghost (`startWallDraw`, `moveWallDraw`, `drawnNow`, `showWallGhost`, `showSlabGhost`, `wallGround`,
    `drawnWords`) and made when the drag lets go (`endWallDraw`: a room as one locked group, with its building when
    it has a roof);
  - the tops of the made walls a roof is drawn on (`wallTopsRound`).

  Its own state is the ghosts' meshes. It gives app.js back the nine functions and objects app.js, its keys, pointer
  handlers, hooks, the looks and the made pieces' handles call, under the same names.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns what other areas read or set of it, each with
  its setter: the Build menu's tool (`buildTool`, `setBuildTool`: the test hooks read it) and the made piece being
  drawn (`wallDrawing`, `setWallDrawing`: the made pieces' handles, the keys, the pointer handlers and the hooks read
  it). `setWallDrawing` gives back what it set, since `startWallDrawing` names the drawing in the same statement
  (`const drawing = setWallDrawing({ ... })`, where it wrote `const drawing = wallDrawing = { ... }`).
- **[app.js](../../tools/viewer/web/app.js)** makes the module where the run was, so nothing it does as the page loads
  (the flyout's buttons' handlers, the ghosts added to the scene) changes its place. The looks' module, made just
  before it, is given `startWallDrawing` and `stopWallDrawing` as functions that call them. Each assignment to a moved
  name is now its setter's call, with the same value (2 writes, and the one inside a declaration).
  app.js: 6,982 lines to 6,767; its `let` statements 48 to 46 (68 names to 66); its top-level functions 424 to 410.
  [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module, its row in where new code goes and the state it added to
  editor_state.js. A comment of [browser_walls.py](../../tools/viewer/tests/browser_walls.py) that placed the Build
  menu's tools in app.js names the module.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 14 moved functions are
  the same with the 3 substitutions of a write by its setter's call (without them, 3 differ). app.js against itself:
  its 410 functions are the same, and the 14 moved are only in the old file. The whole moved text (224 lines) is the
  old text line for line, the factory's indent aside, with those substitutions and the two `let` statements whose
  names went to editor_state.js (now comments naming them). No code that runs as the page loads, before any of the
  page's view and made pieces' modules is made, reaches what it returns.
- `web_names` is clean (63 files), and the node suite passes (31 files).
- **Browser checks** on a test server, the same 20 as on the stage's first commit: on the Bar `api-names` (240 names on
  each of its three pages), `typed-pose`, `recipe`, `destruction`, `adding`, `groups`, `copy-drag`, `library`,
  `cover`, `floor-placing`, `made-prefab`, `modals`, `reset-all`, `draw-errors`, `look-undo`, `failed-reads`, `let-go`
  and `small-defects`; on the police station `walls` (which draws every tool of the Build menu) and `looks`. All
  passed, none skipped.
