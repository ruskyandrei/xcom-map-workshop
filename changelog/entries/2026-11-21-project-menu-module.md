### The Project menu in a module of its own (project_menu.js)

Editor refactor, stage P9, third part: the Project menu, the recent projects and the windows its items open leave
app.js. Nothing the editor does changes.

- **[project_menu.js](../../tools/viewer/web/project_menu.js)** is new: `createProjectMenu` holds, moved verbatim from
  three runs of app.js, the recent projects this browser keeps (`RECENT`, `recentTimes`, `touchRecent`), the menu drawn
  afresh as it opens (`renderProjectMenu`), and the windows its items and the keys open, each after closing the menu
  and stopping a placing (`showGameMaps`, `showPrecache`, `showProjectManager`, `showFileDialog`). The windows' own
  factories (`createProjectDialog`, `createProjectManager`, `createGameMaps`, `createPrecache`) stay in app.js, which
  makes them with their elements and gives them to the menu.
- **Where app.js makes it:** where its last run was, after the windows it is given (values made further down than its
  first runs, which only declared a string and functions: nothing of it runs as the page loads). The header's menus,
  the document session, the prefab builder's session and Build and Play, made earlier, are given `renderProjectMenu`,
  `showFileDialog` and `touchRecent` as functions that call them; the menu is given the clipboard's `stopPlacing` so.
  The queue chip's handler set as the page loads already called `showProjectManager` through a function.
- **[app.js](../../tools/viewer/web/app.js)**: `savedWhen` and `lastBuild`, only the menu's, went with it. 1,471 lines
  to 1,414; top-level functions 36 to 29.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the module in how the page fits, its row, and its factory in the list.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the seven functions the same as app.js's at the commit before,
app.js's other 29 the same; every name the moved code reads resolves as before (by eslint-scope; `RECENT` moved with
its readers); no code that runs as the page loads reaches the menu's functions before it is made; `web_names` clean;
the twenty-edit recording the same as on the stage's start commit, all 52 steps; browser checks `api-names`,
`project-menu`, `builder`, `modals`, `draw-errors`, `failed-reads` and `small-defects` pass.
