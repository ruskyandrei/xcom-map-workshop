### The Spawns view in a module of its own (spawns_wiring.js)

Editor refactor, stage P6, third view: the Spawns view's wiring and the mission objects' moves leave app.js for one
module. Nothing the editor does changes.

- **[spawns_wiring.js](../../tools/viewer/web/spawns_wiring.js)** is new. `createSpawnsWiring` is made once by app.js,
  with what it needs of app.js in one argument object (as `createEffectsWiring` is): the camera, the renderer and the
  scene, the landing zones' layer and the Landing zones view's functions, the other views' switches, the header's
  missions and the Effects view's number field. It holds, moved verbatim, the whole run of app.js from the view's
  heading to `loadSpawnRules`, and `spawnAddEntries` (the Add panel's Spawn points kind, which P6's first part left
  beside the Lights view):
  - the view on or off (`setSpawnsShown`, `setNormalSpawns`), its families' flyout, a marker picked
    (`setPickedSpawn`, `pickSpawnMarker`, `spawnClick`), shown from the build window (`showSpawn`), kept one size;
  - the markers drawn (`refreshSpawnMarkers`), the picked one's panel (`spawnPanel`) and its controls
    (`spawnEditControls`);
  - the project's moves and edits of mission objects and spawn points (`movedMissions`, `editedSpawns`,
    `editedCopies`, `editBaseSpawn`, `editSpawnCopy`, `copySpawn`, `deleteSpawn`, `resetBaseSpawn`,
    `moveMissionGroup`, `setMissionMoves`, `bombHelperFix`) and what the project records of them
    (`missionOverrides`, `spawnCopyRecords`);
  - the picked marker's gizmo and its drag; a spawn point added from the Add panel (`startSpawnPlacing`,
    `placeSpawn`, `stopSpawnPlacing`); the spawn rule (`syncSpawnRule`, `setSpawnRule`) and the install's rules
    (`loadSpawnRules`); and the handlers of the Normal switch, the zone button, the families' boxes and the spawn rule's
    box.

  Its own state is inside it: whether the landing zones showed before the view, and the gizmo's drag. It gives
  app.js back the 50 functions and objects app.js, its hooks and the Buildings view's handles call, under the same
  names, `NORMAL_SPAWNS` among them (app.js reads the switch's saved value as a map opens).
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns what the view shares with other areas, each with
  its setter: `normalSpawns` (`setNormalSpawnsValue`, beside the view's `setNormalSpawns`), `spawnLayerReady`,
  `spawnFilters`, `spawnZonePick`, `spawnRulesData`, `spawnEntriesNow`, `missionMoves` (`setMissionMovesValue`, beside
  the view's `setMissionMoves`, which also draws), `missionDragView` (the Buildings view's handles on a no-spawn
  volume draw their drag with it), `spawnPlacing`; and what the view reads of the header's mission picker,
  `missionIndex`. The families shown are still read from the browser's storage where their `let` was, now through
  their setter.
- **[app.js](../../tools/viewer/web/app.js)** makes the module where the run of code was, so what it does as the page
  loads (the old Mission objects switch carried over, its layer and gizmo added to the scene, the gizmo's listeners,
  the flyout's handlers) happens at the same point; `spawnLayerReady` turns true inside it, and nothing it runs after
  that calls the views' buttons, which read the layer app.js gets back. The landing zones' layer stays in app.js,
  made just before it: the Spawns view shows it too, and the Landing zones view is made further down. The Lights view,
  the scene to and from a document, the document session and Build and Play are made before it and given its
  functions, so they are given functions that call them (`setSpawnsShown`; `missionOverrides`, `setMissionMoves`,
  `syncSpawnRule`; `bombHelperFix`, `setMissionMoves`; `showSpawn`), as the scene to and from a document already was
  given four others; the Effects view's `numberField` and `setEffectsShown`, `gameToView`, `headerMission` and `stopPickBox` are made further down, so
  the module is given functions that call them. Each assignment to a moved name is now its setter's call, with the
  same value (27 writes). app.js: 9,329 lines to 8,639; its `let` statements 73 to 63 (106 names to 94); its top-level
  functions 600 to 542. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module, its row in where new code goes and
  the state it added to editor_state.js. The comments of [spawns_view.js](../../tools/viewer/web/spawns_view.js),
  editor_state.js and app.js that placed the view in app.js name the module.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 58 moved functions are
  the same with the 19 substitutions of a write by its setter's call (without them, 11 differ). app.js against
  itself, with the same substitutions: its 542 functions are the same, and the 58 moved are only in the old file
  (without them, 5 differ). The whole moved text, statements as well as functions (713 lines), is the old text line
  for line, the factory's indent aside, with those substitutions, the six `let` statements whose names went to
  editor_state.js (now a setter's call or a comment naming them) and one comment that names one of them. No code that runs as the page loads, before the
  module is made, reaches what it returns (a scan of app.js's top level).
- `web_names` is clean (59 files), the node suite passes (31 files), the repo suite passes.
- **Browser checks** on a test server, on the commit before and on this change: `api-names` (240 names on each of
  its three pages), `streams` and `spawns` pass (`streams` skips its streamed piece's edit on the Bar, as before).
