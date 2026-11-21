### Clear map, the missions, the ground grid and the map picture in a module of their own (clear_map.js)

Editor refactor, stage P8, second part: Clear map and what goes with it (the landing zones as the project has them,
the missions, the header's Mission picker, the Map picture dialog and the ground grid) leave app.js for one module.
Nothing the editor does changes.

- **[clear_map.js](../../tools/viewer/web/clear_map.js)** is new. `createClearMap` is made once by app.js, with what it
  needs of app.js in one argument object: the scene, the camera and the renderer, the gizmo, the pieces' and lights'
  roots added and taken away, the map's size, the Spawns, Landing zones and Buildings views' functions, the cutaway,
  Play's installs, the project's change, the view taken for the map picture (`grabView`), the popups and the hints. It
  holds, moved verbatim:
  - the landing zones as the project has them (`zonesNow`), the landing zone's pieces (`isLanding`, with
    `LANDING_PREFIXES`), the ground's height (`groundHeight`) and the notes under a size (`sizeNotes`,
    `groundWords`);
  - Clear map: the play area a clear keeping the scenery outside goes by (`outsideBox`, `pointOutside`), what a clear
    takes and keeps (`clearPlan`, `clearedSpawns`, `clearedEffects`), its window (`showClearMap`, `clearSize`,
    `clearWords`, `hideClearMap`, `clearKeptZone`) and the clear, one undo step (`clearMap`);
  - the missions: the Missions panel and the project's missions set (`showMissions`, `setMissions`), which game is set
    (`lwrInstall`, `plainEw`, `gameUnknownWhy`, `hasUfoBuilding`, `baseHas`), a cleared map's missions
    (`clearedMissions`) and the header's Mission picker (`headerMissions`, `headerMission`, `refreshMissionPicker`,
    `missionName`, `missionLabels`, `chooseMission`);
  - the Map picture dialog and its Map menu item;
  - the ground grid (`refreshGroundGrid`, `setGroundGrid`), the pieces still where the map has them (`floorStays`,
    `floorRootsByActor`) and the saved floor index of their tiles (`liveFloorIndex`).

  Its own state is inside it (the caches of what it works out, the window, the panels). It gives app.js back the 22
  functions and objects that app.js's selection, scene start, map browser, keys and test hooks, the Lights, Spawns,
  Effects and Landing zones views, Build and Play, the map grid, the clipboard and the made pieces' drawing call,
  under the same names.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns the install's landing lines for the map
  (`landingLines`, `setLandingLines`, with their comment from app.js), the starting zones worked out from them
  (`startingCache`, `setStartingCache`: app.js's scene start sets both), the last clear's time (`lastClearMs`,
  `setLastClearMs`: the test hooks read it) and the landing zone's pieces as the server's families name them
  (`landingActors`, `setLandingActors`: app.js's `useMapFamilies` sets it).
- **[app.js](../../tools/viewer/web/app.js)** makes the module where Clear map's run ended, so what the run did as the
  page loaded (the window's and the menu items' handlers, the Missions panel and the Map picture dialog made, the
  ground grid's group and materials) happens where it did: three.js draws the ground grid in the same order. Two short
  runs elsewhere that only declare move into it with the main run: the landing pieces' rule (from among Delete and
  Reset, where it had no tie) and the header's Mission picker (after the cutaway). Take from the view (`grabView`)
  stays in app.js: it reads the Effects view's likeness layer, made further down and not a function, and is given to
  the module. Factories made before it are given its functions as functions that call them (the Lights view
  `pointOutside`; Build and Play `headerMissions`, `zonesNow`; the map grid `groundWords`, `sizeNotes`,
  `refreshGroundGrid`), and the Spawns and Landing zones views, made after it now, are given `headerMission` directly.
  The eight writes of the four moved names (three in the scene start, one in `useMapFamilies`) are their setters' calls. app.js: 4,048 lines to 3,588; its `let` statements 28 to 20 (39 names to
  30); its top-level functions 204 to 169. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module, its row, the state it added
  and that a short run of an area's that only declares moves into the factory wherever the factory is made.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 35 moved functions are
  the same with the 7 substitutions of a write by its setter's call (without them, `zonesNow` and `clearMap` differ).
  app.js against itself, with the same substitutions: its 169 functions are the same, and the 35 moved are only in the
  old file (without them, `useMapFamilies` and `startScene` differ). The whole moved text (473 lines) is the old text
  line for line, the factory's indent aside, with those substitutions and the three `let` statements whose names went
  to editor_state.js (now comments). No code that runs as the page loads, before any of the page's factories is made,
  reaches what it returns (a scan of app.js's top level, for it, the map grid, the Lights, Spawns and Landing zones
  views and Build and Play).
- `web_names` is clean (75 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on the commit before and on this change: on the Bar `api-names` (240 names on
  each of its three pages), `typed-pose`, `adding`, `floor-placing` (Level snap by the live floor index), `clear-map`
  (the clear, its window's counts, the map grid, the ground grid and the landing zones), `play-area`, `spawns`,
  `projects`, `floor-boxes`, and the editing run (`modals` with the Missions and Map picture dialogs, `failed-reads`
  and `let-go` with the Missions panel and the header's Mission picker, `made-prefab`, `reset-all`, `draw-errors`,
  `look-undo`, `paste-buildings`, `squad-read`, `ladder-floor`, `small-defects`); on the police station `streams`,
  `spawns` and `walls` (two parts of `streams` and `spawns` skip there on both commits: the map has no streamed piece
  drawn to edit and no plain pod to copy); and the Map picture dialog's own check (`browser_map_picture.py`). All
  passed.
