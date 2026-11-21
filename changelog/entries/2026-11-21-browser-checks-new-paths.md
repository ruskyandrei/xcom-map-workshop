### Seven browser checks for page paths no check walked: made pieces broken, their gaps deleted, a rock's corner, a room's buttons, Select all of a kind, the pathing-gate question and Build's routes into Prepare

The refactor's follow-ups (items 4.6, 4.7 and 4.8) named page paths that no browser check walked. Each is now a check of
[browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)'s table, on a page of its own, and in one of `--all`'s
runs (the editing run on URB_Bar, `room-buttons` in the police run):

- [browser_walls.py](../../tools/viewer/tests/browser_walls.py), from the made pieces' scratch script of the refactor's
  stage P7, on made pieces pasted from one of the map's own fracturing pieces (one the game keeps whole if the map has
  one):
  - `made-break`: Break (B and a click) on a made wall, a made floor and a made roof sets off one blast where clicked,
    one undo step; Breaks further in battle, shown on a broken piece the game keeps whole, ticked, one undo step;
    Repair mends the piece whole, one undo step. (Where no fracturing piece of the map is kept whole, the Breaks
    further part is listed as skipped.)
  - `made-openings`: with the second of a wall's two gaps last touched (its row pointed at), Delete takes that gap out
    and leaves the wall; with the first gap's handle clicked, Delete takes that one; a floor's hole the same way.
  - `rock-corner`: a rock's corner point clicked takes the point gizmo; its arrow dragged moves the corner along the
    rock's x by what was dragged (the snap off), nothing else moves, one undo step; Escape lets it go.
  - `room-buttons` (on the police station's ground): a room drawn and picked whole: Lower and Taller step all its walls
    a storey, the walls' Choose... gives them a look from the picker and Plain takes it back; a room with a roof has no
    Lower or Taller and its roof's Choose... and Plain do the same; each one undo step.
- [browser_editing.py](../../tools/viewer/tests/browser_editing.py), from stage P8a's scratch script:
  - `select-kind`: Select all on a picked piece (`#editKind`) picks every drawn piece of its mesh (the Bar's six
    dumpsters), its count and words saying how many, as no edit; the Flags group then turns Blocks sight off for all of
    them as one undo step (undone, redone, Reset); a light picked beside the piece is dropped by a click and kept by
    Shift+click.
  - `flags-gate`: on a prop whose pathing gate is open with Blocks walking half on (the Bar's
    `XComDestructibleActor_111`), the Gives cover row asks first and changes nothing; Cancel closes the question; an
    answer makes the change with Blocks walking as answered, one undo step; picking another piece closes an open
    question. (The Bar has such props, so the check is written: the follow-up's dumpster and keg do not ask.)
- [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py) `prepare-routes` (needs `--projects`): for a project
  saved by the check, with the server's answers stood in for (the export too old, then a build answered as started
  and as stopped with the code `export-missing`), Build asks to prepare instead of opening its panel, and the stopped
  build's window offers Prepare the map, which starts the prepare at once and opens the map again; no Build runs (the
  project's own status has no job afterwards). The prepare-again dialog's stand-ins are one function now
  (`stand_in_export`), which the `prepare` check uses too.

Checked: each check failed with a one-line break planted in the page (not kept): a made piece's blast not added, Delete
taking the first gap whatever was touched, the corner moved along the rock's y, Lower stepping up, Shift+click not
adding, the gate's question not asked, the build window's Prepare not offered for `export-missing`. Each new check and
`prepare` passed five times running on one test server; `browser_smoke.py --all` passed (see the rough edges' entry
for its numbers).
