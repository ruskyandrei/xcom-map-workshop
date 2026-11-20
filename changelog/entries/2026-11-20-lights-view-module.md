### The Lights view in a module of its own (lights_wiring.js)

Editor refactor, stage P6, first view: the Lights view's wiring moves out of app.js into one module. Nothing the
editor does changes.

- **[lights_wiring.js](../../tools/viewer/web/lights_wiring.js)** is new. `createLightsWiring` is made once by app.js,
  with what it needs of app.js in one argument object (as `createPrefabPlace` is): the gizmo, the camera and the
  lights' layer, the panel's helpers, the other views' switches, and what the picked effect's handles need of the
  Effects view. It holds, moved verbatim, the whole run of app.js from `changedValues` to `warnLights` but for what
  stays (below):
  - the roots: `makeLightRoot`, `addLightRoots`, `removeLightRoots`, `lightPose`, `setLightValues`, `paintLight`,
    `refreshLightVisibility`, `lightViewOnly`, `lightsBlocked`, `changedValues` and its helpers;
  - the view on or off (`setLightsShown`, `setNormalLights`), `pickLight`, `scaleMarkers`;
  - the area lights following their glowing pieces (`areaOwner`, `ownerRoot`, `deriveAreaLights`, `setBinding`,
    `assignOwner`), `lightRecords`, Solo (`setSolo`, `updateSolo`), the reach and emission shapes
    (`lightReach`, `refreshLightShapes`), the panel's light section (`lightPanel`, `showLight`, `changeLight`,
    `commitLightField`, `commitColour`);
  - the drag handles on the selected light, and on the picked effect or sound, which share them
    (`handleRoot`, `effectHandleRoot`, `effectHandles`, `updateLightHandles`, `startLightDrag`, `moveLightDrag`,
    `endLightDrag` and their helpers);
  - the Add panel's lights (`lightClip`, `lightEntries`), `recipeLight`, `withStorableCone`, `addedLight`, the
    project's light records (`lightState`, `clearLightEdits`, `applyLightRecord`, `addedLightOf`), `buildLights`,
    `lightsChanged` and `warnLights`.

  Its own state is inside it: the warning said, the fixed lights, the owners' index, the lights painted, the handles'
  hover, the shapes' key and the reach's outlines. It gives app.js back the 45 functions and objects app.js and its
  hooks call, under the same names.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns what the view shares with other areas, each with
  its setter:
  - which view is on and what the views' switches read of each other: `lightsOn`, `normalLights`
    (`setNormalLightsValue`), `lightsShown` (`setLightsShownValue`), `volumesOn`, `zonesOn`, `effectsOn`,
    `spawnsOn`;
  - what the view reads of other areas: the picked effect (`pickedEffect`), the streams shown (`streamSet`), what is
    being placed (`placing`), the hint's timer (`hintTimer`), the Map lighting mode (`lighting`) and its radius
    (`lightRadius`);
  - what of the view app.js's event wiring, keys, pointer handlers, draw loop and test hooks read or set:
    `areaShown`, `reachShown`, `soloOn`, `lightsDirty`, `lastLightSync`, `assigning`, `derivedCopies`, `handleDefs`,
    `lightDrag`, `reachKey`, `reachNow`. View options' two switches still read the browser's storage where their
    `let` was, now through their setters.
- **[app.js](../../tools/viewer/web/app.js)** makes the module where the run of code ended, after what of it stays:
  - `setNormalView`, `syncLights` and `lightButton`: they switch and paint every view (the Buildings view's own
    state among them), not the Lights view's alone;
  - `setZonesShown`, `zoneEntries`, `spawnAddEntries` and `pieceRecipes`: the Landing zones view's, the Spawns
    view's and the Add panel's;
  - `projector` and `HANDLE_PICK`, which every area's handles use, `PL`, and the view's storage keys, which app.js's
    View options use;
  - the light panel's field handlers, the keys, the pointer handlers and the draw loop: app.js's event wiring.

  The code that ran as the page loaded (the view's layers added to the scene, Solo made) runs at the same point among
  the page's other code, since nothing else ran between. `applyLighting` (a `let` that `startScene` sets), `banner`,
  `effectNow`, `effectsShown` and `stopPickBox` are made further down, so the module is given functions that call
  them. Each assignment to a moved name is now its setter's call, with the same value (52 writes). app.js: 10,948
  lines to 10,136; its `let` statements 89 to 80 (150 names to 119); its top-level functions 727 to 662.
  [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module, its row in where new code goes, the state it added to
  editor_state.js, and how a factory is made when part of its area's code stays in app.js. The comments of
  [lights_view.js](../../tools/viewer/web/lights_view.js), [pieces.js](../../tools/viewer/web/pieces.js),
  editor_state.js and app.js that placed the lights in app.js name the module.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 65 moved functions are
  the same with the 41 substitutions of a write by its setter's call (without them, 11 differ). app.js against
  itself, with the same substitutions: its 662 functions are the same, and the 65 moved are only in the old file
  (without them, 16 differ). The whole moved text, statements as well as functions (834 lines), is the old text line
  for line, the factory's indent aside, with those substitutions and the four `let` statements that lost the names
  taken to editor_state.js. No code that runs as the page loads, before the module is made, reaches or reads what it
  returns (a scan of app.js's top level).
- `web_names` is clean (57 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on the commit before and on this change: `api-names`, `map-lights`, `lights`,
  `dense-lighting`, `light-grid`, and `effects`, `flares`, `likeness`, `effect-values` (the picked effect's handles
  moved too): all 9 ran and passed (about a minute each time, with other work on the computer). After it, the checks
  of what reads the views' switches and the light records: `streams`, `spawns`, `typed-pose`, `destruction`,
  `adding`, `groups`, `copy-drag`, `box-select`, `floor-boxes`, `map-buildings`, `clear-map`, `align`, `library`,
  `cover`, `projects`, `prefabs`, `prefab-effects`, `header`, `play-area`, `library-effects` and `library-flares`
  all passed (21 ran; `streams` skips its streamed piece's edit on the Bar). `projects` passes on a server of its
  own: run after `effect-values` on one server, it finds that check's saved project in the folder beside its own two,
  which it counts, and fails (`--all` runs `effect-values` on a server of its own).
