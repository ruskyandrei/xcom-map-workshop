### The same controls on every thing in the view: zones, spawn points, marks and floor boxes take a piece's

Discord suggestion S18 asked for Shift+drag to copy a landing zone and for the tool strip's Move and Rotate to work on
one. At the user's word it is widened to everything that wasn't consistent, with a rule that keeps it so.

- **The rule** ([UI-GUIDELINES.md](../../UI-GUIDELINES.md), section 2, "The same controls on every thing", with its
  table; section 1's Snap line names spawn points and mission objects beside the marks and says the Snap button shows
  the step; section 5's item 7; [AGENTS.md](../../AGENTS.md) half a line on each): a new kind of thing takes every
  control it can, with the same keys, and names in a hint the ones it can't; a view's gizmo is made by
  view_gizmo.js; a control that changes for one kind changes for all in the same commit.
- **One home for a view's gizmo** ([view_gizmo.js](../../tools/viewer/web/view_gizmo.js), new, `createViewGizmo`):
  the landing zones', the spawn points' and mission objects' and the diagonal cover marks' gizmos
  ([zones_wiring.js](../../tools/viewer/web/zones_wiring.js), [spawns_wiring.js](../../tools/viewer/web/spawns_wiring.js),
  [diagonal_wiring.js](../../tools/viewer/web/diagonal_wiring.js)) are made by it, their hand-written
  `TransformControls` gone; the pieces' gizmo joins its list (`joinGizmo`) and the rock point's for the press's busy
  test and Esc (`joinBusy`). app.js's press handler asks `anyGizmoBusy`, Esc asks `cancelGizmoDrag`.
- **The rail's buttons and G, R, V drive the gizmo that is up** ([navigation.js](../../tools/viewer/web/navigation.js)
  `activeGizmo`, `setGizmoMode`, `toolButtons`, `syncTools` which the draw loop runs): lit by its mode; Rotate dimmed
  ([style.css](../../tools/viewer/web/style.css) `.rail button.dim`), and R's hint, where what is picked doesn't turn
  (a pod: "A pod's or Meld point's facing aims nothing"; a box: "A building's box is not turned", [ and ] too). A
  drop-in point's ring and a mark's turn by quarters (the mark's corners), as [ and ] do.
- **The Snap button shows the step in force** (snap_steps.js `snapInForce`): with a spawn point, a mission object or a
  mark picked and a finer setting, its badge reads 96, lit, and its tip says "Whole tiles: a spawn point stands on a
  tile. Your setting, snap off, is back when it is let go"; a click says the same and changes nothing. So their
  whole-tile moves are no longer silent (AGENTS.md's Snap rule).
- **Shift+drag on an arrow drags off a copy** on every thing: a zone (zones_wiring.js `copyZone`'s `at`), a spawn
  point of the map or a copy (spawns_wiring.js `copySpawn`'s `delta`; a mission's object says it isn't copied), the
  picked marks (diagonal_wiring.js `copyPicked`), and a floor box in the Buildings view, copied into its own building
  on its floor ([clipboard.js](../../tools/viewer/web/clipboard.js) `boxCopyBegin`, `boxCopyEnd`; it was a plain
  move). The original stays, the copy is picked, one undo step; Esc during the drag makes none.
- **Ctrl+C, Ctrl+X and Ctrl+V** for a picked zone, spawn point or marks (clipboard.js `copyThing`, `pasteThing`; each
  view's clip: `zoneClip`, `spawnClip`, `markClip`): one clipboard, the last thing copied whatever its kind; Ctrl+V
  starts the view's own placing with the copy (a zone with its kind, direction and mission; a spawn point with its
  template, values and turn, so a cut one comes back; the marks with their corners, the first on the tile clicked).
  The landing panel's Copy copies as a piece's does (decision A2); Ctrl+D still makes one beside at once, zones' and
  spawn points' alone. A copied zone or marks go along to the next map as the carried copy does (carried_clip.js
  `thing`); a spawn point stays in its map.
- **[ and ] on pieces, lights and effects** (decision A3): a quarter turn of the selection about the gizmo's pivot
  (navigation.js `turnSelection`). The marks' [ and ] now turn the way the zones' and spawn points' do ([ left, ] right
  as seen from above): they were the other way round.
- The landing panel's words ([index.html](../../tools/viewer/web/index.html)) no longer say the gizmo moves it by whole
  tiles, nor that Copy makes one two tiles east; the help panel and the [guide](../../tools/release/guide/guide.html)
  (a new section, "The same controls on everything", and the keys table) say the controls;
  [ARCHITECTURE.md](../../ARCHITECTURE.md) has view_gizmo.js's row.

Checked: snap_steps_test.mjs (`snapInForce`) and carried_clip_test.mjs (a zone and marks carried, a zone of unset
height); a new browser check, `same-controls` ([browser_controls.py](../../tools/viewer/tests/browser_controls.py), run
by [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)): on Bar a landing zone's gizmo by R, the rail's Move,
V and G (the buttons lit by its mode), a Shift+drag on its X arrow making one copy with the original where it was and
Escape making none, Ctrl+Z, Ctrl+C, Ctrl+V and a click; a pod with Snap off showing 96 and its tip, the Snap button's
click changing nothing, R's hint and Rotate dimmed, a Shift+drag copy with the original unmoved, Ctrl+X and Ctrl+V
placing it again, the badge back to the setting once let go; a floor box's Shift+drag copied into its own building and
R's hint; a piece's ] and [; a zone copied on Bar placed on Police Station; on the farm a mark's 96, its ring, a
Shift+drag copy and a Ctrl+C, Ctrl+V copy put on a clicked tile. The whole browser smoke run on Bar, with `step-pick`,
`step-views`, `carried-copy`, `builder`, `diagonal`, `rock-corner`, `select-kind`, `documents`, `paste-buildings`,
`made-openings`, `modals` and `let-go`; the repo, node and viewer suites. The `clear-map` check now takes the landing
panel's Copy as a copy to the clipboard and makes the copy beside with Ctrl+D; the `diagonal` check's comment says
which way ] turns (its corners' pair is the same either way). Not done: the guide's pictures of the landing panel.
