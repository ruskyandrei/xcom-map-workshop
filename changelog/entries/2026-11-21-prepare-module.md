### Prepare in a module of its own (prepare.js)

Editor refactor, stage P8, second part: Prepare (the dialog that exports an old map again, and a build or a play
waiting for it) leaves app.js for one module. Nothing the editor does changes.

- **[prepare.js](../../tools/viewer/web/prepare.js)** is new. `createPrepare` is made once by app.js, with the banner,
  the map's label and the popups. It holds, moved verbatim, the dialog with Later's banner and the run with its
  progress (`showPrepare`, with its words `prepareWhy`) and a build or a play waiting for it (`needsPrepare`). Its own
  state is inside it (whether a prepare is under way). It gives back the two functions Build and Play, app.js's scene
  start and the test hooks call.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns what is wrong with the open map's export for lights
  and builds (`exportProblem`, `setExportProblem`), which app.js's scene start sets and Prepare reads.
- **[app.js](../../tools/viewer/web/app.js)** makes it where its run was: the run only declared, so nothing moves as
  the page loads. It is given the document session's `banner` and app.js's `mapLabel`, made further down, as functions
  that call them. The one write of the moved name, in the scene start, is its setter's call. app.js: 2,856 lines to 2,788; its `let`
  statements 14 to 13 (22 names to 20); its top-level functions 116 to 114. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module, its row
  and the state it added.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 2 moved functions are
  the same, with no substitution. app.js against itself, with the 1 substitution of a write by its setter's call: its
  114 functions are the same, and the 2 moved are only in the old file (without it, `startScene` differs). The whole
  moved text (74 lines) is the old text line for line, the factory's indent aside, with the `let` statement whose name
  went to editor_state.js (now the `let` of the one left). No code that runs as the page loads, before any of the
  page's factories is made, reaches what it returns (a scan of app.js's top level, for it and Build and Play).
- `web_names` is clean (81 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on the commit before and on this change: on the Bar `api-names` (240 names on
  each of its three pages), `prepare` (the dialog as an old map opens, Later and Esc leaving the banner that opens it
  again, Prepare now's progress and the reopened map), `projects` and `project-menu`; `modals`, `failed-reads` and
  `small-defects`; and `documents`. All passed, none skipped. (`project-menu` was not run on the stage's start commit;
  it passed in stage P8 first part's `--all`.)
