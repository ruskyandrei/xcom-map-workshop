### Switching the views in a module of its own (views.js)

Editor refactor, stage P9, third part (follow-up 3.15's first half): what switches between the five views leaves
app.js. Nothing the editor does changes.

- **[views.js](../../tools/viewer/web/views.js)** is new: `createViews` holds, moved verbatim, `setNormalView` (out of
  every view), `syncLights` (after a view or a Normal button's switch changed: whether lights are drawn, what stays
  selected, the panel) and `lightButton` (the views' buttons, the Normal button's switches, View options' Area lights
  and reach outlines). It is given the gizmo, the five views' switches and refreshes, and the Spawns view's layer and
  panel; it keeps no state. The `spawnLayerReady` guard in `lightButton` moved as it was.
- **Where app.js makes it:** right after the selection, the last factory whose functions it reads (it makes nothing as
  the page loads), so no function it reads is called through; the Lights, Spawns, Effects, Landing zones and Buildings
  views, made before it, are given `syncLights` or `lightButton` as functions that call them (none calls them while the
  page loads: each call is inside a view's switch).
- **[app.js](../../tools/viewer/web/app.js)**: eight imports of editor_state.js only the moved code read went with it.
  1,407 lines to 1,384; top-level functions 28 to 25.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the module in how the page fits, its row, its factory in the list, and its
  place in the rule of where a factory that makes nothing as the page loads is made.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the three functions the same as app.js's at the commit before,
app.js's other 25 the same; every name the moved code reads resolves as before (by eslint-scope); no code that runs as
the page loads reaches them before they are made; `web_names` clean; the twenty-edit recording (which traces
`syncLights` and `lightButton`) the same as on the stage's start commit, all 52 steps; browser checks `api-names`,
`typed-pose`, `spawns`, `box-select`, `floor-boxes`, `map-buildings`, `clear-map`, `lights`, `effects`, `likeness`,
`flares`, `cover`, `small-defects`, `reset-all` and `walls` pass.
