### The edit hub: each area registers what it keeps up after an edit (edit_hub.js)

Editor refactor, stage P9, first part (decision D5's default: registration only): `editChangedNow` no longer calls
every panel by name. Each area's module registers its refresh with the edit hub as it is made, and the hub calls them
in the order the page always called them. Nothing the editor does changes.

- **[edit_hub.js](../../tools/viewer/web/edit_hub.js)** is new, a pure module (node imports it, so it is not in
  editor_state.js, which reads the page's address as it loads). Its `RUNS` lists each run's refreshes in their order,
  with whose each is: `edit` (after any edit, undo or selection) holds fifteen, from the Effects view's redraw asked
  through the selection following the gizmo, the Buildings view, the cutaway, the selection's marks, an invisible
  floor's note, the pose fields and edit status, the Flags group, Select all of a kind, the group and Align sections,
  the Room section, the gizmo's buttons and the project's title to the lights; `drag` holds what the edit status's
  refresh runs while a gizmo handle is held (the lights drawn following). `onHub(run, name, refresh)` registers one,
  and refuses a name the run doesn't list or one registered twice; `runHub(run, ...args)` calls those registered, in
  `RUNS`' order whatever order they were registered in, and a refresh that gives back `STOP` ends the run (as
  `return` ended `editChangedNow`). Its node test, [edit_hub_test.mjs](../../tools/viewer/tests/edit_hub_test.mjs),
  registers a run backwards and checks the order, `STOP`, the arguments and the refusals.
- **[app.js](../../tools/viewer/web/app.js)**: `editChangedNow` is `runHub('edit')`; app.js registers its own four
  parts of it (the selection following the gizmo, the selected piece's marks, the pose fields and edit status, the
  gizmo's buttons), moved verbatim, and no longer takes the refreshes it called by name from the factories that
  return them. While a handle is held, the edit status's refresh runs the `drag` run where it called `lightsChanged`.
  app.js: 2,788 lines to 2,783; its top-level functions (114) and `let` statements (13, 20 names) as they were.
- **The areas' modules** each register their part of `editChangedNow`, moved verbatim, inside their factory:
  [effects_wiring.js](../../tools/viewer/web/effects_wiring.js) (the redraw asked),
  [buildings_wiring.js](../../tools/viewer/web/buildings_wiring.js) (the boxes followed, a box never turned),
  [cutaway.js](../../tools/viewer/web/cutaway.js), [cover_wiring.js](../../tools/viewer/web/cover_wiring.js) (an
  invisible floor's note), [flags_panel.js](../../tools/viewer/web/flags_panel.js),
  [select_kind.js](../../tools/viewer/web/select_kind.js), [groups.js](../../tools/viewer/web/groups.js) and
  [align.js](../../tools/viewer/web/align.js) (each its half of "a building's box is in no group and is not aligned"),
  [made_panel.js](../../tools/viewer/web/made_panel.js) (the Room section),
  [document_session.js](../../tools/viewer/web/document_session.js) (the project) and
  [lights_wiring.js](../../tools/viewer/web/lights_wiring.js) (the lights after an edit and while a handle is held).
  What each gave app.js only for `editChangedNow` is no longer returned (`syncVolumes`, `floorNote`, `flagsPanel`,
  `groupPanel`, `targetHelper`, `roomPanel`, `lightsChanged`, `warnLights`).
- **What the cutaway last followed** (`cutKey`) is only the cutaway's now, so it moved out of
  [editor_state.js](../../tools/viewer/web/editor_state.js) into `createCutaway`, its setter's call an assignment.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the rule that a panel registers its refresh with the edit hub and is not
  called by name from another area, how (a name in `RUNS`, `onHub` in the factory, `STOP`, a run of its own for a
  refresh called in the middle of another), its row in where new code goes, and the hub in how the page fits.

Checked:
- **The move:** the bodies of the `edit` run's fifteen refreshes, taken in `RUNS`' order, are `editChangedNow`'s body
  at the commit before, token for token (comments aside), with five substitutions: each of the four `return;` that
  ended it early is `return STOP;` (one of them also runs the `drag` run, whose one refresh is the
  `if (lightsShown) lightsChanged();` it replaces), and the group and Align statement is its two halves, each testing
  the building's box. [moved_code.py](../../tools/repo/moved_code.py) against the commit before: app.js's 114
  functions the same but `editChangedNow`; in each module every function the same but its factory (the registration
  and the shorter list it returns), the cutaway's `cutaway` with the one substitution of `setCutKey(...)` by the
  assignment.
- **Twenty edits and more, recorded:** a browser script on the Bar (on a test server, the page's files served from
  the commit before or this one) makes 52 scripted steps: a selection of a piece, a ladder, a fracturing piece, a
  light, an effect, a building's box, nothing; a typed move; a move with a gizmo handle held and let go, of a piece
  and of a light; copy; paste placed by a click; delete; undo; redo; a light's brightness; an effect's keep; a made
  wall drawn; a cover block placed and changed; a flag; a group; Align; a building added and moved in the Buildings
  view; a spawn point moved; Select all of a kind; Level snap off and on; a prefab saved and placed; Reset piece and
  its undo; Escape; Clear map, its undo and redo; Reset all and its undo. After each it records every panel's markup
  and controls (the header, the rail, the piece panel, the views' panels), the selection, the changes, the project's
  state, and the panel functions called and their order (49 of them traced). The commit before, recorded twice, is
  the same both times; this change is the same as it, all 52 steps.
- **The edit's time** (performance.now() around the synchronous edit: the gizmo's move, undo and redo, and a
  selection; median of 40 rounds, three runs, other work on the computer): on the Bar (1,095 pieces) 1.1 to 1.2 ms a
  move, 1.7 to 1.8 ms an undo, 1.6 ms a redo and 1.4 ms a selection, where the commit before took 1.1 to 1.2, 1.7 to
  1.8, 1.6 and 1.3 to 1.4 ms; on TempleShip (1,678 pieces, 1,333 lights) 2.5 to 2.8 ms a move, 3.4 to 3.7 ms an undo,
  3.1 to 3.4 ms a redo and 2.2 to 2.4 ms a selection, where the commit before took 2.7, 3.6, 3.3 and 2.3 to 2.4 ms.
  Stage P1 measured on the Bar, in quiet rounds, 0.8 to 1.0 ms a move, 1.5 to 1.6 ms an undo or a redo and 1.4 ms a
  selection. A larger map is not slow, so decision D5's second step (each refresh running only for the changes it
  shows) is not taken.
- `web_names` is clean (82 files); the node suite passes (32 files) and the repo suite.
- **Browser checks** on a test server, on the commit before and on this change: on the Bar `api-names`, `typed-pose`,
  `recipe`, `destruction`, `adding`, `groups`, `copy-drag`, `box-select`, `floor-boxes`, `map-buildings`, `clear-map`,
  `align`, `library`, `cover`, `lights`, `effects`, `flares`, `header`, `floors-cut`, `reset-all`, `look-undo`,
  `small-defects`, `modals` and `ladder-floor`; on the police station `walls`, `looks` and `spawns`. All 27 passed on
  both, the same part of `spawns` skipped on both (the police station has no plain pod or Meld point to copy).
