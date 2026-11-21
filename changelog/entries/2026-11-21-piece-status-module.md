### The pose fields and the edit status in a module of their own (piece_status.js)

Editor refactor, stage P9, third part: the edit hub's `piece-status` refresh, the last refresh app.js registered,
leaves it. Nothing the editor does changes.

- **[piece_status.js](../../tools/viewer/web/piece_status.js)** is new: `createPieceStatus` registers the refresh,
  moved verbatim from app.js, with the hub under its name in `RUNS`, where it always ran: the piece panel's pose
  fields (read only for a streamed piece or a view-only light), the pose and source lines and Delete; while a gizmo
  handle is held, the `drag` run and the end of the `edit` run; then the edit status (what has changed, by kind, and
  whether it is saved), Undo, Redo, Reset and Reset all. It is given the gizmo, the pose fields, the count of changes,
  the save state and the Lights view's pose and values of a light, and keeps no state.
- **Where app.js makes it:** right after the document session, whose save state it shows. Its registration now happens
  there, later as the page loads: a probe of the page (the hub's runs recorded with how far app.js had loaded, on the
  Bar and in the prefab builder) found no run of the hub while app.js loads; the first come as the scene opens (in the
  builder) or with the first selection.
- **[app.js](../../tools/viewer/web/app.js)** keeps `poseInputs`, which its typed-pose handlers use too, and gives it to
  the module; `onHub`, `runHub`, `STOP`, `cleared` and `groups`, only the refresh's, went with it. 1,344 lines to
  1,311. [edit_hub.js](../../tools/viewer/web/edit_hub.js): `RUNS`' comments name the refresh's module.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the module in how the page fits, its row, its factory in the list, and the
  hub's rule's example of one refresh; prose lines this stage made longer than 120 characters wrapped again.

Checked: the registration is app.js's line for line, two spaces further in, and none of it is left in app.js; each of
the 24 names it reads resolves as before (by eslint-scope: the same import, or the factory's argument app.js gives
under that name); `web_names` clean; the twenty-edit recording the same as on the stage's start commit, all 52 steps;
browser checks for the item (with `editChangedNow` in the hub and `changes` in the document's state) `api-names`,
`typed-pose`, `groups`, `copy-drag`, `clear-map`, `lights`, `effects`, `project-menu`, `builder`, `spawns`, `modals`,
`reset-all`, `draw-errors`, `let-go`, `small-defects` and `walls` pass (`clear-map` run straight after `copy-drag`
times out on `#gridDone`, the known order dependence; it passes with the next checks on its own).
