### The Landing zones view in a module of its own (zones_wiring.js)

Editor refactor, stage P6, fourth view: the Landing zones view's wiring leaves app.js for one module. Nothing the
editor does changes.

- **[zones_wiring.js](../../tools/viewer/web/zones_wiring.js)** is new. `createZonesWiring` is made once by app.js,
  with what it needs of app.js in one argument object (as `createSpawnsWiring` is): the camera, the renderer and the
  scene, the landing zones' layer and its storage key, the other views' switches, the header's mission and the Clear
  map window's zones. It holds, moved verbatim, the whole run of app.js from `ZONE_OWN` to `clearedChanged`, the
  zones' heading comment, and the view's switch, `setZonesShown`, its own `let` (whether the layer was hidden before
  the view) and the Add panel's Landing zones kind, `zoneEntries`, which P6's first part left beside the Lights view:
  - the zones drawn (`refreshLandingZones`, `zoneLabel`, `floorTop`, `zoneSoldiers`, `carried`) and the map's own
    landing pieces a moved zone takes along (`movedLandingActors`);
  - a zone picked (`pickZone`, `zoneHit`), its gizmo and its drag, its panel (`landingPanel`, `zoneNotes`) and the
    panel's handlers;
  - the zones changed, each change one undo step (`setZones`, `zonesChanged`, `explicitZones`, `changeZone`,
    `turnZone`, `copyZone`, `deleteZone`), a zone added with a click (`startZonePlacing`, `placeZone`,
    `stopZonePlacing`), and what follows a change of the cleared mark (`clearedChanged`).

  Its own state is inside it: whether the layer was hidden before the view, the gizmo's mode and drag, the drag's zone
  drawn in place, the floor tiles' tops. It gives app.js back the 25 functions and objects app.js, its hooks and the
  other views call, under the same names.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns `zonePlacing`, whether the next click places a
  zone, with its setter: app.js's keys and pointer handlers read it.
- **[app.js](../../tools/viewer/web/app.js)** makes the module where the run of code ended. `gameToView`, which stood
  in the run, stays where it was (the Spawns view and the test hooks use it too), so the module is made after it; what
  the run does as the page loads (the gizmo made, added to the scene and given its listeners, the panel's handlers)
  happens at the same point, since only declarations stood between. The landing zones' layer and its storage key stay
  where they were made, before the Spawns view, which shows the zones too; both views are given them. The Lights view,
  the scene to and from a document, Build and Play, the Spawns view and the Effects view are made before it and given
  its functions, so they are given functions that call them (`setZonesShown`; `clearedChanged`; `setZones`;
  `pickZone`, `setZonesShown`, `zoneHit`, `zoneState`; `carried`, `setZonesShown`, `zoneState`); `headerMission` and
  `stopPickBox` are made further down, so the module is given functions that call them. Each assignment to
  `zonePlacing` is now its setter's call, with the same value (3 writes). app.js: 8,639 lines to 8,245; its `let`
  statements 63 to 58 (94 names to 88); its top-level functions 542 to 512. [ARCHITECTURE.md](../../ARCHITECTURE.md)
  names the module, its row in where new code goes, the state it added to editor_state.js, and what happens to a
  layer two views use and to a function an earlier stage left behind. The comments of editor_state.js and app.js that
  placed the view in app.js name the module.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 30 moved functions are
  the same with the 2 substitutions of a write by its setter's call (without them, 3 differ). app.js against itself:
  its 512 functions are the same, and the 30 moved are only in the old file. The whole moved text, statements as well
  as functions (416 lines), is the old text line for line, the factory's indent aside, with those substitutions and
  the `let` statement whose name went to editor_state.js (now a comment naming it). No code that runs as the page
  loads, before the module is made, reaches what it returns, nor what the Spawns view's returns (a scan of app.js's
  top level).
- `web_names` is clean (60 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on the stage's first commit and on this change: `api-names` (240 names on each
  of its three pages) and `clear-map` (which moves, turns and adds zones) pass; on this change also `streams`,
  `spawns`, `lights`, `effects`, `flares`, `header` and `play-area`, which call the functions given to the other
  views.
