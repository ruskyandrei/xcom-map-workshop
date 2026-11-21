### The pieces an actor name stands for, selected and framed, with the selection (selection.js)

Editor refactor, stage P9, third part: `selectActors` leaves app.js. Nothing the editor does changes.

- **[selection.js](../../tools/viewer/web/selection.js)**: `selectActors` (the pieces and lights an actor name stands
  for, a compile report's entity or target or a prefab test's actor, selected and framed), moved verbatim from app.js
  into `createSelection`, which gives it back and is given `flashHint`, and the camera's `frame` (made further down) as
  a function that calls it.
- **[app.js](../../tools/viewer/web/app.js)**: the prefab builder's session and Build and Play, made before the
  selection, are given `selectActors` as a function that calls it. 1,414 lines to 1,407; top-level functions 29 to 28.
  [ARCHITECTURE.md](../../ARCHITECTURE.md): the selection's row.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the function the same as app.js's at the commit before,
app.js's other 28 the same; every name it reads resolves as before (by eslint-scope); `web_names` clean; the
twenty-edit recording the same as on the stage's start commit, all 52 steps; browser checks `api-names`,
`typed-pose`, `builder`, `modals`, `small-defects`, `made-prefab` and `looks` pass, and, on a fresh test server after
the stage's moves of the project helpers, `projects`, `prefabs`, `prefab-effects`, `output-names` and `documents`.
