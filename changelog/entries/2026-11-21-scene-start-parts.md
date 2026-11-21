### startScene split into the scene's parts, each in the module that owns it

Editor refactor, stage P9, second part (the plan's P9 step 3, first half): app.js's `startScene`, which starts the
editor on a map's or a prefab's scene, no longer holds each area's start itself. Each run of it that belongs to an area
moved verbatim into a function of that area's module, and `startScene` calls them in the order it always ran them.
Nothing the editor does changes.

- **The parts and their homes**, each returned by its module's factory (or exported) and called from `startScene` in
  its place:
  - [scene_pieces.js](../../tools/viewer/web/scene_pieces.js) `buildPieces(streamObjects, mapName)`: every mesh and
    material asked for up front, the pieces built in scene order with the loading overlay's count, and the refusal
    when none could be drawn (the factory is now given `loadingState`);
  - [clear_map.js](../../tools/viewer/web/clear_map.js) `readLandingLines()`: the install's landing lines for the map
    read, the ground grid and the zones following when they come; `startMissionPicker()`: the header's Mission picker;
  - [lights_wiring.js](../../tools/viewer/web/lights_wiring.js) `lightingModes()`: the Map lighting mode's buttons;
    `applyMapLighting()`: the view lit with the lights as edited, which `startScene` puts in app.js's `applyLighting`
    (a `let` that does nothing until a scene has started, as before; it was an arrow made there, now a function of the
    Lights view with the same body);
  - [cutaway.js](../../tools/viewer/web/cutaway.js) `sceneViewOptions(streamObjects)`: the Floor picker shown, View
    options' Hide patch helpers and the layout's patches and streams;
  - [prepare.js](../../tools/viewer/web/prepare.js) `prepareOpened(familyTable, mapCatalogue)`: the map's export
    checked as it opens (the factory is now given `projectsAvailable`);
  - [builder_session.js](../../tools/viewer/web/builder_session.js) `builderPage()`: the page dressed as the prefab
    builder's (the factory is now given `showFileDialog`);
  - [scene_start.js](../../tools/viewer/web/scene_start.js), new, plain exports for what is no one area's:
    `showSceneTitle` (the page's title, the preview chip), `showSceneMenus` (View options' Full or Interior, the Map
    menu's items), `showImportNotes` and `showLinked` (the gizmo's Linked button for an export without links).
- **[app.js](../../tools/viewer/web/app.js)**: `startScene` keeps the parts' calls, the few statements that are its
  own (the lighting made, the map grid's size dropped, the mission asked for, the families' answer, the views'
  buttons, the overlay hidden, the project or prefab opened) and the test hooks. One line was divided: `setOwnGrid(null)`
  stays, the two statements after it start `readLandingLines`. Its imports used only by the moved code went with it.
  app.js: 2,517 lines to 2,429; `startScene` 303 lines to 209; its top-level functions (106) and `let` statements (12,
  17 names) as they were.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): how `startScene` starts the scene part by part, the rule that a part keeps
  its place and takes what was worked out before it as parameters, and its row in where new code goes.

Checked:
- **The move:** each of the twelve runs is, line for line (indentation aside), the body of its new function (the
  arrow's first and last lines aside for `applyMapLighting`), and `startScene` less the runs, each replaced by its
  call, is the new `startScene` (a script of the stage's). [moved_code.py](../../tools/repo/moved_code.py) against the
  stage's start: app.js's 106 functions the same but `startScene`; in the six modules every function the same but the
  factory, the new functions only in the new files. Every name in each new function resolves to what it did in
  `startScene` (the module's own function app.js destructured, an import of the same state, or the argument app.js
  gives). No code that runs as the page loads reaches the six factories' returns before they are made.
- **The twenty-edit recording** (stage P9a's 52 scripted steps on the Bar: every panel's markup and controls, the state
  and the panel functions called and their order after each): the same as on the stage's start commit, all 52 steps.
- `web_names` is clean (84 files); the node suite passes (32 files).
- **Browser checks** on a test server: on the Bar `api-names`, `streams`, `map-lights`, `typed-pose`, `clear-map`,
  `header`, `floors-cut`, `play-area`, `frame-bounds`, `project-menu`, `lights`, `effects`, `prepare`, `builder`,
  `modals`, `draw-errors` and `failed-reads`; on TempleShip `temple-interior` and `temple-look`; on the police station
  `streams`, `light-bar` and `walls`. All passed (`streams` skips its streamed-piece part on both maps, as on the start
  commit). Under `--only`, `clear-map` run straight after `typed-pose` fails waiting for the Map grid's Done button, on
  the start commit too; it passes alone and in the whole run's order.
