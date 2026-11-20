### Build and Play in game in a module of their own (build_play.js)

Editor refactor, stage P4: the Build window's and Play's wiring and state move out of app.js into one module, with
the test squad's line, the prefab builder's Test in game and the build queue's chip. Nothing the editor does
changes.

- **[build_play.js](../../tools/viewer/web/build_play.js)** is new. `createBuildPlay` is made once by app.js, with
  what it needs of app.js in one argument object (as `createDocumentSession` is): the views and dialogs it opens
  (Prepare, the Save dialog, a spawn point's marker, the landing zones), the selection, the document session's
  `banner` and `saveProject`, and the prefab builder's document. It holds, moved verbatim:
  - the Build window: `canBuild`, `openBuild`, `buildProject`, `setLastBuild`, `followBuild`, `pollBuild`,
    `openBuildWindow`, `closeBuildWindow`, `renderBuild`, `pathLink`, `playFinished`, `playBuilt`, and the window's
    buttons and key listener;
  - Play in game: `savingFor`, `savingOption`, `playMissions`, `playMissionNote`, `followPlayedMission`,
    `builtAsShown`, `refreshInstalls`, `renderPlayItems`, `playInGame`, `playChosen`, `sendPlay`, `playedFor`,
    `playAgain`, `withZone`, `landHere`;
  - Build's panel, the test squad's dialog and `refreshSquadLine` (the Settings button's handler with them), the
    prefab test's window and `openPrefabTest`; the build queue's `renderQueueChip` and `followQueueForProject`.

  Build and Play are one module, not two: Play has its own button in the build window, a play waits for its build,
  and Play's dialog goes by the build's state, so two modules would share five more names through editor_state.js and
  call each other both ways. Its own state is inside it: the build its window follows and the window's clock, a play
  waiting for its build, and the next play's landing zone, mission and saving. It gives app.js back the twelve that
  app.js calls (`openBuild`, `playInGame`, `landHere`, `refreshInstalls`, `prefabTest` and the others), under the same
  names. The words stay where round two put them, in [build_window.js](../../tools/viewer/web/build_window.js) and
  [play.js](../../tools/viewer/web/play.js), whose node tests still load nothing of the page.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns three more names other areas use, each with its
  setter: `playStatus` (the Missions panel reads its mission kinds), `pickedZone` (the Landing zones view picks it,
  Land here plays it) and `missionPickValue` (the header's Mission picker sets it).
- **[app.js](../../tools/viewer/web/app.js)** makes the module where the Build window's code was, after `mapLabel`,
  which it is given, so its handlers and dialogs are set up as the page loads, as before, and its key listener in
  the same place among the page's others. The document session is made before it and calls `followBuild`, `renderPlayItems` and `setLastBuild`, so the session is
  given functions that call them. Each assignment to a moved name is now its setter's call, with the same value.
  What stays in app.js, and why:
  - the Project menu (`renderProjectMenu`): the project's name, revision and recent projects, which are the
    document's; it reads the build status and calls `renderPlayItems`, as before;
  - `mapLabel`: the prepare dialog, the file dialog and the project manager use it too;
  - the prefab builder's Problems check (`checkPrefab`, `problemsPaint`, its chip): the builder resets and runs it,
    and the document session paints it (stage P5's);
  - `selectActors`: a selection that the builder's Problems list uses too;
  - the setup dialog, the file dialog and the build queue's controller: the controller is the project manager's as
    well, and is given the chip's two functions.

  app.js: 12,231 lines to 11,702; its `let` statements 98 to 93 (166 names to 157); its top-level functions 791 to
  760.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) on the 31 moved functions against the commit before.
  With the 4 substitutions of a play status write by its setter's call (8 writes), all 31 are the same. Without
  them, the 7 that write it differ. app.js against itself, with its 4 substitutions (`pickedZone` and
  `missionPickValue` written through their setters): its 760 functions are the same, and the 31 moved are only in the
  old file; without them 6 differ. The whole moved text, the statements as well as the functions (536 lines), is the
  old text line for line, the factory's indent and those substitutions aside, and the one `let` that lost
  `playStatus`.
- `web_names` is clean (54 files). The node suite passes (31 files, with `build_window_test.mjs`, `play_test.mjs` and
  `build_queue_test.mjs` unchanged), and so does the repo suite.
- **Browser checks** on a test server with scratch projects, builds and squad: `api-names`, `streams`, `spawns`,
  `clear-map`, `project-menu`, `squad`, `output-names`, `prefab-test` and `documents` all ran and passed (2 min 25 s,
  with other work on the computer); `streams` skips its streamed piece's edit on the Bar, which draws none.
- **Build and Play from the page,** on a test server playing into a scratch game folder (`serve --install <scratch
  game> --dry-play`): one quick Build from the page (a project saved on the Bar with one piece moved, Ctrl+B, Build):
  the window followed it to "Built", its manifest came back, with its two files. Then `play` and `prepare` with
  `--play --play-project` that project: both pass (51 s). Before the move the same runs passed on the commit before
  (with the checks of the entry before). Land here, which no check presses: a zone picked on the project, Land here
  opens the play dialog for the project landing at that zone.
