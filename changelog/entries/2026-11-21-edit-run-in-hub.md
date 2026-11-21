### The edit run's call with the edit hub (edit_hub.js)

Editor refactor, stage P9, third part: `editChangedNow` (the edit hub's `edit` run, which app.js's `editChanged` calls
once it has made the edit event's memo) moves to the hub. Nothing the editor does changes; the order of the runs is the
same (it is the one call it was).

- **[edit_hub.js](../../tools/viewer/web/edit_hub.js)**: `editChangedNow`, moved verbatim from app.js with `export`,
  after `runHub`; the `edit` run's comment names it.
- **[app.js](../../tools/viewer/web/app.js)** imports it; `editChanged` stays (it asks for the sun's shadow map again,
  app.js's draw loop's state, and makes the edit event's memo in editor_state.js, which the hub, a module node reads,
  does not import). 1,370 lines to 1,367; top-level functions 22 to 21.
- [edit_hub_test.mjs](../../tools/viewer/tests/edit_hub_test.mjs): `editChangedNow` runs the `edit` run.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the function the same as app.js's at the commit before
(`export` aside); `web_names` clean; the node suite; the twenty-edit recording the same as on the stage's start
commit, all 52 steps.
