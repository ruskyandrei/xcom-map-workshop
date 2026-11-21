### The header's menus, the map browser's wiring and the loading overlay in modules of their own

Editor refactor, stage P9, second part: three more of app.js's areas leave it, each moved verbatim into a module named
for what it does. Nothing the editor does changes.

- **[popups.js](../../tools/viewer/web/popups.js)** (`createPopups`): the header's menus, `showPop` (one open at a time;
  opening the Project menu draws it, the Game menu the squad's line and the installs), the `data-pop` buttons' handlers
  and the press on the document that closes a menu. app.js makes it before the Lights view, the first area given
  `showPop`, so the eight factories that take it are given it as before; the build window's `refreshInstalls` and
  `refreshSquadLine`, made later, are given as functions that call them. Its handlers are set that much earlier: no
  other code sets a handler on those buttons or listens to a press on the document, and the Map menu's button, which
  gets a handler of its own, still gets it after.
- **[map_menu.js](../../tools/viewer/web/map_menu.js)** (`createMapMenu`), beside [map_browser.js](../../tools/viewer/web/map_browser.js)
  (the dialog itself): `mapLabel`, `refreshMapList`, `showMapBrowser`, the Map menu's button and Change map, and the
  making of the browser with what choosing a map does (`makeMapBrowser(activeMap, parameters)`, the run of app.js's
  `open` that made it, with the line before it that works out the map asked for and not yet prepared). app.js makes it
  where `mapLabel` was, its first run (the build window, the file dialog and the project manager are given `mapLabel`
  after it, as before; `stopPlacing` is given as a function that calls it); the Map menu's handlers are set there.
- **The map list and the browser** (`mapCatalogue`, `mapBrowser`), app.js's two `let`s, are now
  [editor_state.js](../../tools/viewer/web/editor_state.js)'s with their setters: app.js's `open` sets the list
  (`setMapCatalogue`) and shows the browser on a map not prepared yet, `startScene` hands the list to Prepare's check,
  and the prefab builder's Open shows the browser, as well as the map menu (the browser's making sets it through
  `setMapBrowser`).
- **[loading.js](../../tools/viewer/web/loading.js)** (`createLoading`): the overlay's `loadingState`, `openingProgress`
  with its `OPENING` shares, and `fetchJson`. It keeps no state; it is a factory for app.js's `$` and `plural`. app.js
  makes it as soon as `plural` is made (nothing of it runs as the page loads): the document session and the prefab
  builder's session are now given `openingProgress` itself where they were given a function that called it, and the
  scene's pieces, made before, are given `loadingState` as a function that calls it.
- **[app.js](../../tools/viewer/web/app.js)**: `open` stays (it starts the page: the list read, the first run's install,
  the browser made, the map opened, `startScene`); the imports only the moved code used went with it. app.js: 1,918
  lines to 1,848; its top-level functions 95 to 88; its `let` statements 8 (12 names) to 7 (10 names).
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the three modules and `open` in how the page fits, their rows, their
  factories among the page's, the list and the browser among editor_state.js's state, and where app.js makes them.
- `cutaway`'s kept boxes (the plan's P9 step 5) are not built: stage P9's first part measured an edit on TempleShip
  (1,678 pieces) at 2.3 to 3.7 ms, which is not slow.

Checked:
- **The move:** each of the six runs is app.js's at the commit before line for line, two spaces further in (the
  browser's making four, with `mapBrowser=` given to `setMapBrowser`), none left in app.js;
  [moved_code.py](../../tools/repo/moved_code.py): the seven functions moved (`loadingState`, `fetchJson`,
  `openingProgress`, `showPop`, `mapLabel`, `refreshMapList`, `showMapBrowser`) the same as the factories'; app.js's other
  87 the same but `open` (the list's setter, the browser made by its call). Every name the moved code reads resolves as
  before: the same import (the list and the browser now editor_state.js's), the factory's argument of that name, which
  app.js gives under it, or `makeMapBrowser`'s parameters. No code that runs as the page loads reaches the three
  factories' returns before they are made.
- **The twenty-edit recording** (stage P9a's 52 steps): the same as on the stage's start commit, all 52 steps.
- `web_names` is clean (89 files); the node suite passes (32 files).
- **Browser checks** on a test server, on the Bar: the `maps` run (`browser_maps_smoke.py`: the map browser opened from
  the Map menu, its groups, a map chosen and opened) and the `map-picture` run (`browser_map_picture.py`) pass; and
  `api-names`, `project-menu`, `prepare`, `typed-pose`, `header`, `builder`, `modals`, `draw-errors`, `failed-reads`,
  `let-go` and `small-defects` pass (`previews` skips: the scratch export has no patch previews). Under `--only`,
  `header` run straight after `project-menu` and `prepare` fails clicking the Selected button, disabled with nothing
  selected, on the stage's start commit too; it passes alone, after a check that selects and in the whole run.
- **The stage's end** (stage P9's second part, its four commits together): `browser_smoke.py --all` on fresh scratch
  servers, with a scratch game folder for Play (`--play-install`), passes, all ten runs (whole 44 checks, named 7,
  builder 2, editing 11, documents, police 3, temple 2, map picture, maps, Play), in 9 min 42 s (other work on the
  computer); [moved_code.py](../../tools/repo/moved_code.py) against the stage's start: app.js's 88 functions the same
  but `startScene` and `open`, the 18 that left it the same in their new modules.
