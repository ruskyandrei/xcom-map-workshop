### The drag handles' helpers in a module of their own (handles.js)

Editor refactor, stage P9, third part (follow-up 3.15's second half): what every area's drag handles share leaves
app.js. Nothing the editor does changes.

- **[handles.js](../../tools/viewer/web/handles.js)** is new: `HANDLE_PICK` (how near the mouse a handle is picked) and
  `gameToView` (a game point as a point of the view), which read only their arguments, as plain exports; and
  `createHandles`, given the camera, the renderer and the scene's pieces' `rayAt`, holding `projector` (screen
  positions of points in the view) and `alongLine` (how far along a line the mouse's ray passes: a handle's drag). Each
  moved verbatim from three runs of app.js; app.js makes the factory where `projector` was, before the first area given
  its functions (it makes nothing as the page loads), and `alongLine`'s run, which only declared, comes there with it.
  The Spawns view, made before `gameToView` was declared, is now given the import itself instead of a function that
  calls it.
- `viewPoint` in [buildings_wiring.js](../../tools/viewer/web/buildings_wiring.js) stays: it reads its point by
  destructuring (`([x, y, z]) => ...`), which takes an iterable, where `gameToView` reads `p[0]`, `p[2]`, `p[1]`, which
  takes any indexed object; the same on arrays, not the same function, so merging them is a change, not a move.
- **[app.js](../../tools/viewer/web/app.js)**: 1,384 lines to 1,371; top-level functions 25 to 22.
  [ARCHITECTURE.md](../../ARCHITECTURE.md): the module in how the page fits, its row, its factory in the list, and the
  placement rule's example of a helper app.js keeps (now `isStream` or `fromOf`).

Checked: [moved_code.py](../../tools/repo/moved_code.py): the three functions the same as app.js's at the commit before
(`export` aside), app.js's other 22 the same; every name the moved code reads resolves as before (by eslint-scope);
`web_names` clean; the twenty-edit recording the same as on the stage's start commit, all 52 steps; browser checks
`api-names`, `typed-pose`, `spawns`, `box-select`, `floor-boxes`, `map-buildings`, `clear-map`, `lights`, `cover`,
`play-area`, `walls` and `made-prefab` pass.
