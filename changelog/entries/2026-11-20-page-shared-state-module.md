### The page's shared state in a module of its own (editor_state.js)

Editor refactor, stage P1: the state several of the page's areas use gets one owner module, so that the later stages
can move app.js's areas out with their reads unchanged. Nothing the editor does changes.

- **[editor_state.js](../../tools/viewer/web/editor_state.js)** is new. It declares and exports, with their comments
  moved from app.js:
  - the page's mode, `prefabParameter` and `builderMode`;
  - the scene, `data`, and its map's id, `activeMapId`;
  - the roots: `roots`, `lightRoots` and `lightIndex`, `volumeRoots`, `effectRoots` and `effectIndex`, and
    `allRoots` over them (the gizmo's);
  - the selection, `selected`, and the project open, `project`;
  - the groups, `groups` and `groupIndex`, with `setGroups` (moved as it was);
  - the map's size, `stage`; the cleared map, `cleared` and `clearKeepsOutside`; the project's `landingZones`,
    `projectMissions`, `projectPicture` and `projectSpawnRules`;
  - the buildings, `buildings` and `buildingsVersion`.

  Each name that is given new values has a setter beside it: `set<Name>`, or `set<Name>Value` where app.js has a
  `set<Name>` of its own that also draws (`setStageValue`, `setBuildingsValue`). The Maps are changed in place
  through the import, as before. The module's top level only declares.
- **[app.js](../../tools/viewer/web/app.js)** imports them. Each of its 43 assignments to them is now a call of the
  setter, with the same value. Its reads are as they were: an import is a live binding, so a reader sees each new
  value. Nothing else moved.
- app.js: 12,792 lines to 12,767; its module-level `let` statements 112 to 105 (199 names to 184); its top-level
  functions 812 to 811.
- **The guidance:** [ARCHITECTURE.md](../../ARCHITECTURE.md) states the page's state rule as it now is: one owner
  module, read through the import, given new values only through the owner's setter, and `editor_state.js` for what
  several areas use. It also gets a "where new code goes" row for page state, a line in section 1, and app.js's new
  numbers. [structure.json](../../tools/repo/structure.json) lowers app.js's ceilings to 12,767 lines, 105 `let`s and
  811 functions.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py)'s comparison of app.js against the commit before,
  with the 41 distinct substitutions of a write by its setter call. A small script handed these to its `compare()`,
  since `--subst` ends its old text at the first `=`. 811 functions are the same, and `setGroups` is only in the old
  file. `setGroups` in editor_state.js is the old one, `export` aside (`moved_code.py --names setGroups`).
  `allRoots`'s tokens are the old ones.
- **No assignment left:** a scope analysis of the 51 page modules finds no assignment to an imported name. A search
  of app.js for an assignment to the moved names finds only local names spelled the same.
- `web_names` is clean (51 files). The node suite passes (31 files), and so does the structure test.
- **Browser checks** on a test server. Stage 0's `--all` passed them all on the same page code, and `api-names`,
  `groups`, `floor-boxes`, `clear-map`, `lights` and `projects` passed here again before the change. After it:
  - `api-names`: 240 names in each of the three places;
  - `spawns`, `groups`, `copy-drag`, `box-select`, `floor-boxes`, `map-buildings`, `clear-map`, `lights`, `effects`;
  - `projects`, `prefabs`, `prefab-effects`, `project-menu`, `builder`, `documents`, `modals`, `prepare`;
  - `--all` on fresh test servers, with a scratch cache: its nine runs pass in 10 minutes 18 seconds, with 70
    checks run, as at stage 0. The Play run was left out, since no scratch game folder was given.
- **The Bar's edit event** (1,095 pieces, headless Edge), timed with `performance.now()` around each synchronous
  call: a typed move (`gizmo.setPose`), its undo and redo, and a selection. Each round made 15 of each, and four
  rounds alternated between a server of the commit before and one of this change. The medians, before and after:
  - typed move 1.3 and 1.4 ms;
  - undo 2.35 and 2.35 ms;
  - redo 2.3 and 2.2 ms;
  - selection 2.05 and 2.3 ms.

  In the two quieter rounds both sides gave 0.8 to 1.0 ms for a move, 1.5 to 1.6 ms for an undo or redo, and 1.4 ms
  for a selection, as review finding 56 measured. Other work was running on the computer, so the numbers are noisy.
  Each round's pair agrees within 0.1 ms, the timer's step: reading through the import costs nothing measurable.

Left for the stages that move each area: the rest of app.js's state stays where it is, including what the document
session also uses. That is its own state (`leaving`, `saving`, the drafts' timers and owners), caches of functions
still in app.js (`mergedBuildings`, `liveCache`), the edit hub's memo, and names it reads that others write
(`landingRead`, `looksReady`, `copySerial`, `areaBindings` and others).
