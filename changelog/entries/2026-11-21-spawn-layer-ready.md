### Whether the Spawns view's layer is made, back inside the Spawns view (spawns_wiring.js)

Editor refactor, stage P9, third part: of the state stages P6a and P6b put in editor_state.js only because app.js's
keys, test hooks, draw loop or view switching read it, what can go back inside its factory goes. Nothing the editor
does changes.

- **`spawnLayerReady`** (whether the Spawns view's layer is made; the views' buttons show it from then on) leaves
  [editor_state.js](../../tools/viewer/web/editor_state.js) with its setter. It is a `let` inside `createSpawnsWiring`
  ([spawns_wiring.js](../../tools/viewer/web/spawns_wiring.js)), set where the setter was called, and the factory gives
  back a getter of it; its one reader, `lightButton` in [views.js](../../tools/viewer/web/views.js), is given the getter
  by [app.js](../../tools/viewer/web/app.js) and calls it. The views' switching is made after the Spawns view since
  this stage, so the flag is true whenever `lightButton` runs; dropping the guard is a change, not a move, and is left.
- **Left in editor_state.js, with the reason:** `reachNow`, `handleDefs` and `derivedCopies` (the Lights view's),
  `wavePlayer`, `likenessOn`, `likenessThin` and `likenessCount` (the Effects view's) are all read by the test hooks
  (`createTestApi` imports them), and `likenessOn` also by app.js's Add panel browser; taking them from their factories
  would add a getter to `createTestApi`'s arguments for each, with none taken away, which the stage's rule does not
  allow. Their owners still set them only through their setters.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the rule of a factory's own state read by a module made after it (a
  getter), and the Spawns view's shared state without the flag.

Checked: `web_names` clean; the twenty-edit recording the same as on the stage's start commit, all 52 steps; browser
checks `api-names`, `typed-pose`, `spawns`, `floor-boxes`, `clear-map`, `lights`, `effects` and `small-defects` pass.
