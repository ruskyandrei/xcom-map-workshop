### The Buildings view and box select in a module of their own (buildings_wiring.js)

Editor refactor, stage P6, fifth view: the Buildings view's wiring (the floor boxes, the map's own buildings) and box
select leave app.js for one module. Nothing the editor does changes.

- **[buildings_wiring.js](../../tools/viewer/web/buildings_wiring.js)** is new. `createBuildingsWiring` is made once
  by app.js, with what it needs of app.js in one argument object (as `createZonesWiring` is): the gizmo, the camera,
  the renderer and the scene, the boxes' layer, the map's buildings' records and floors, the Spawns view's no-spawn
  volumes, the other views' switches and the selection. It holds, moved verbatim, the two runs of app.js that were the
  view's: from its heading to `endVolumeDrag`, and from `setVolumeTool` to box select's buttons:
  - the boxes made, put and painted (`makeVolume`, `setVolumeBox`, `paintVolume`, `volumeBox`), the project's
    buildings worked out from them (`buildingsFromVolumes`, `syncVolumes`) and put back from a project
    (`setBuildings`), what is drawn (`refreshVolumes`, `drawOwnVolumes`);
  - the view on or off (`setVolumesShown`), its tools (`setVolumeTool`, `volumesAround`), a box clicked
    (`volumeClick`), the map's own picked to be read (`setOwnPicked`, `pickOwn`);
  - the boxes changed, each one undo step (`recordVolumes`, `addVolumes`, `deleteVolumes`, `copyVolumes`,
    `pasteVolumes`, `newBuilding`), the map's own buildings back as the map has them (`restoreMapBuildings`,
    `mapRestoreChange`, `mapChangesList`);
  - the six face handles and their drags (`updateVolumeHandles`, `volumeHandleNear`, `startVolumeDrag`,
    `moveVolumeDrag`, `endVolumeDrag`; a picked no-spawn volume's, `spawnVolumeHandle`), the cursor's floors round
    the boxes (`drawCursorRings`);
  - the panel (`volumePanel`, `volumeCounts`, `typedHeight`) and its handlers; the Normal button's Floor boxes
    (`setBoxesShown`) and a box's edge picked in the normal view (`pickBoxEdge`);
  - box select (`setPickTool`, `stopPickBox`, `refreshPickBox`, `pickCandidates`, `startPickDrag`, `movePickDrag`,
    `endPickDrag`, `takePickBox`) and its buttons.

  Its own state is inside it: the boxes' serial and key, the hovered handle, the boxes copied, the last building, the
  pieces to put boxes around, the panel's counts and the map's changes' key, the cursor rings' key. It gives app.js
  back the 49 functions, objects and constants app.js, its hooks and the made pieces' handles call, under the same
  names (`PICK_SLACK` for Select all of a kind, `FACES` and `viewPoint` for the hooks).
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns what the view shares with other areas, each with
  its setter: `boxesShown` (`setBoxesShownValue`, beside the view's `setBoxesShown`), `ownPicked`
  (`setOwnPickedValue`), `volumeTool` (`setVolumeToolValue`), `volumeDrag`, and box select's `pickTool`
  (`setPickToolValue`), `pickBox` (`setPickBoxValue`, beside the test hooks' `setPickBox`, which also draws),
  `pickDrag` and `pickHits`; and the two collections other areas change in place, `buildingMeta` (each building's
  name and kind: app.js's map building records read it) and `ownSet` (the map's own buildings selected: app.js's
  selection and keys clear it).
- **[app.js](../../tools/viewer/web/app.js)** makes the module where the first run was. What the second run did as
  the page loaded (its panel's and buttons' handlers, box select's layer and parts added to the scene, the box's
  edges listed) now happens there, before the cover blocks' and made pieces' code that stood between: no code there
  sets a handler on those elements or reads what the module returns as the page loads, and box select's parts are
  see-through objects, which three.js draws by render order and depth (the order objects were made counts only where
  both are equal, which none of them shares with what is made in between but by an exact coincidence of depth). The
  Lights view, the scene to and from a document, the prefab builder's session, the Spawns view, the Effects view and
  the Landing zones view are made before it and given its functions, so they are given functions that call them
  (`setVolumesShown`, with `stopPickBox` as before; `setBuildings`; `volumeBox`). Each assignment to a moved name is
  now its setter's call, with the same value (34 writes). app.js: 8,245 lines to 7,219; its `let` statements 58 to 50
  (88 names to 70); its top-level functions 512 to 440. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module, its
  row in where new code goes, the state it added to editor_state.js, and how an area whose code was two runs is made.
  The comments of editor_state.js and app.js that placed the view in app.js name the module.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 72 moved functions are
  the same with the 26 substitutions of a write by its setter's call (without them, 15 differ). app.js against
  itself, with the same substitutions: its 440 functions are the same, and the 72 moved are only in the old file
  (without them, 4 differ). The whole moved text, statements as well as functions (1,047 lines), is the old text line
  for line, the factory's indent aside, with those substitutions and the four statements whose names went to
  editor_state.js (now a comment naming them, or the `let` without them). No code that runs as the page loads, before
  any of the five views' modules is made, reaches what it returns (a scan of app.js's top level).
- `web_names` is clean (61 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on the stage's first commit and on this change: `api-names` (240 names on each
  of its three pages), `floor-boxes`, `map-buildings`, `floors-cut` and `paste-buildings` pass. On this change, in one
  run with them, the checks of what reads the view's state or calls its functions: `streams`, `spawns`, `typed-pose`,
  `destruction`, `adding`, `groups`, `copy-drag`, `box-select`, `clear-map`, `align`, `library`, `cover`,
  `floor-placing`, `floor-tiles`, `lights`, `effects`, `header`, `play-area`, `tile-grid` and `small-defects`: 25 ran,
  all passed (`streams` skips its streamed piece's edit on the Bar); then `prefabs`, `prefab-effects`, `builder`,
  `reset-all`, `let-go` and `ladder-floor` on the Bar, and `walls` and `made-prefab` on the police station, passed.
- **`browser_smoke.py --all`** on fresh test servers, with a scratch cache and `--play-install <scratch game>`, after
  the three views' moves (the Spawns view, the Landing zones view, this one): the nine runs of the editor's checks
  pass, 70 checks ran and 6 skipped, each for its map or its run (TempleShip's two, the police station's light bar and
  Play run elsewhere; `streams`' edit and the patch previews have nothing on the Bar's export to work on), 14 min with
  other work on the computer. The Play run was refused before it played: the server's play status said "XCOM is
  running", since the game was open on the computer. Nothing of Play moved in this stage.
