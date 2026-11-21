### A clear runs the edit hub's clear run in place of calling the Lights view's refresh by name

Editor refactor, stage P9, fourth part: a change that keeps behaviour, not a move. Clear map's clear, done or undone,
called the Lights view's `refreshLightVisibility` by name; it now runs a run of the edit hub at the same place, with
which the Lights view registers that refresh. Nothing the editor does changes.

- **[edit_hub.js](../../tools/viewer/web/edit_hub.js)**: a `clear` run in `RUNS` (after `landing-zones`, so the hub's
  node test's message of the first runs missing reads as before): `lights` (which lights are drawn,
  [lights_wiring.js](../../tools/viewer/web/lights_wiring.js), registered beside its `mission` refresh in a function
  that discards what the refresh gives back, so it cannot end its run).
- **[clear_map.js](../../tools/viewer/web/clear_map.js)**: the clear's redo and undo run `clear` where they called
  `refreshLightVisibility()`: after the landing zones it keeps (their own `landing-zones` run), before the lights'
  redraw is asked (`setLightsDirty`, state, set directly) and the selection set, as before. Clear map is no longer given
  `refreshLightVisibility`; [app.js](../../tools/viewer/web/app.js) no longer gives it (1,294 lines; top-level
  functions 11; `let` statements 5, 7 names).
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the hub's rule names the `clear` run.

Checked: the twenty-edit recording (which traces `refreshLightVisibility`) the same as on the stage's start commit, all
52 steps; the paths it does not walk, probed with stage P9c's script (the stage's start commit's page against this one
on the same server): on the police station a stream mission picked, Clear map, its undo and redo; on the Bar a project
mission ticked, picked, unticked, the untick undone and done again, Clear map, undo and redo, and the snap setting
cycled on a ladder: the functions the runs call (`refreshLightVisibility` among them), in their order, and the header,
the rail, the piece panel, the lights drawn and the mission gizmo the same after each of the 20 steps; `web_names`
clean; the node suite (the hub's test finds the new name registered once) and the repo suite; browser checks
`clear-map`, `lights`, `play-area` and the rest of the stage's 43 named checks pass.
