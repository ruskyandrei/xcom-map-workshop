### The test hooks in a module of their own (test_api.js), built from the modules' exports

Editor refactor, stage P9, second part (the plan's P9 step 3, second half): `window.viewer`, the hooks the browser
checks, the guide's pictures and the refactor's scripts drive and read, is no longer written out inside app.js's
`startScene`. Its names are the recorded ones; nothing the editor or a hook does changes.

- **[test_api.js](../../tools/viewer/web/test_api.js)** is new. `createTestApi` gives the hooks' object, moved verbatim
  (161 lines; `window.viewer = {` became `return {`), with `sectionText` (a panel section's text with its how-to notes,
  which only the hooks read), moved from app.js. It imports what the hooks read of the shared state (79 names of
  editor_state.js, each a live binding as app.js's import was) and of the pure modules (three.js, `TILE`,
  `normalCover`, `catalogued` and `lookFromEntry`, the prefabs' `api`, `stateKey`, `ownLandings`, `spawnKey`), and takes
  the rest as one argument object: what app.js's factories return, app.js's own objects and helpers (the gizmo, the
  renderer, the camera, `projector`, `gameToView`, `changes`, `editState`, `dirty`, `SESSION`) and the streamed objects
  `startScene` worked out (182 names, each given under its own name). None of them is a `let` of app.js, so each hook
  reads at a call what it read before.
- **[app.js](../../tools/viewer/web/app.js)**: `startScene` sets `window.viewer = createTestApi({ ... })` where it set
  the object, at its end; the imports only the hooks used went with them (27 names of editor_state.js, and the pure
  modules' five). app.js: 2,429 lines to 2,277; `startScene` 209 lines to 71; its top-level functions 106 to 105; its
  `let` statements (12, 17 names) as they were.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): where the hooks are made, the rule (a hook a browser check uses is made in
  test_api.js from the modules' exports and its name is in the recorded list) and its row in where new code goes.

Checked:
- **The move:** the hooks' object in test_api.js is app.js's at the commit before line for line, its first line's
  `window.viewer =` aside; `sectionText` the same ([moved_code.py](../../tools/repo/moved_code.py), as
  `createTestApi.sectionText`); app.js's other 104 functions the same but `startScene`. Each of the 277 names the hooks
  read resolves as it did: the 88 imports to the same module's same export, the 182 of app.js and `startScene` to
  `createTestApi`'s argument of that name, which `startScene` gives under it (a script of the stage's, by eslint-scope).
- **`api-names`**: `window.viewer`'s names on the Bar, the blank map and in the prefab builder are the 240 recorded
  ones, each place.
- **The twenty-edit recording** (stage P9a's 52 steps on the Bar, which drive and read the hooks): the same as on the
  stage's start commit, all 52 steps.
- `web_names` is clean (85 files); the node suite passes (32 files).
- **Browser checks** on a test server, on the Bar: `api-names`, `typed-pose`, `pivot`, `text-select`, `zoom`, `groups`,
  `copy-drag`, `box-select`, `floor-boxes`, `map-buildings`, `clear-map`, `align`, `library`, `cover`, `lights`,
  `effects`, `flares`, `header`, `floors-cut`, `pan`, `play-area`, `modals`, `reset-all`, `draw-errors`, `look-undo`,
  `failed-reads`, `let-go`, `ladder-floor` and `small-defects`: all 29 passed.
