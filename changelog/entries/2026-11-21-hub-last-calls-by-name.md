### The edit hub's last calls of other areas by name: runs named for what happened

Editor follow-ups, stage P5, item 3.30. A change that keeps behaviour, not a move: where an area still called other
areas' refreshes by name after a change of its own, it now runs a run of the edit hub, with the refreshes in the order
the page called them. Nothing the editor does changes.

- **[edit_hub.js](../../tools/viewer/web/edit_hub.js)**, `RUNS`:
  - `clear` (the lights drawn) is run by Delete's and Reset all's steps too, done and undone
    ([delete_reset.js](../../tools/viewer/web/delete_reset.js)), each of which called the Lights view's
    `refreshLightVisibility` where the clear runs it; its comment names all three. (The findings file put Reset all's
    redo and undo at Delete's lines; both are done.)
  - `cleared`, new: [zones_wiring.js](../../tools/viewer/web/zones_wiring.js)' `clearedChanged` (a clear or Reset all
    done or undone, a project opened or closed) runs the header's Mission picker, the lights drawn, the cutaway (not in
    the prefab builder, as before), the ground grid and the zones, which it called by name. The Effects view's redraw
    mark, set between the lights and the cutaway, is set before the run: no refresh of it reads the mark.
  - `landing-zones` and `project-missions` (new): Reset all's map state put back, after the cleared run, draws the
    zones and the header's Mission picker through them instead of calling the Landing zones view's and Clear map's
    refreshes.
  - `zone-edit`, new: a landing zone edited (zones_wiring.js' `setZones`, done or undone) draws its zones itself, then
    runs the ground grid and the cutaway. The plan's `scene` run was not used: it calls the cutaway before the ground
    grid, draws the grid only if its key changed and also works out where made walls meet, so the recording of which
    functions run would differ.
  - `spawn-box`, new: a no-spawn volume's box dragged by a face handle (buildings_wiring.js, whose handles they are:
    as the handle moves, and once it is let go unchanged) draws the spawn markers through it. (The plan called this
    "a building's floors changed"; the two calls are the no-spawn volume's drag.)
  Each refresh is registered in its own module: [clear_map.js](../../tools/viewer/web/clear_map.js) (the Mission picker
  in `cleared` and `project-missions`, the ground grid in `cleared` and `zone-edit`),
  [lights_wiring.js](../../tools/viewer/web/lights_wiring.js), [cutaway.js](../../tools/viewer/web/cutaway.js),
  zones_wiring.js and [spawns_wiring.js](../../tools/viewer/web/spawns_wiring.js).
- **Arguments no longer needed** ([app.js](../../tools/viewer/web/app.js)): Delete and Reset are no longer given
  `refreshLandingZones`, `refreshLightVisibility` or `refreshMissionPicker`; the Landing zones view no longer
  `cutaway`, `refreshGroundGrid`, `refreshLightVisibility` or `refreshMissionPicker`; the Buildings view no longer
  `refreshSpawnMarkers`; Clear map no longer gives back `refreshMissionPicker`.
- **[edit_hub_test.mjs](../../tools/viewer/tests/edit_hub_test.mjs)**: each run of `RUNS` is started by the page (a
  `runHub` of it in a module's text), beside each name registered once; a planted break (the `spawn-box` run's two
  starts taken out) fails it.
- [ARCHITECTURE.md](../../ARCHITECTURE.md), "The edit hub": the runs named for what happened, the state set before a
  run when none of its refreshes reads it, and when a call would stay by name (none does now).

Checked: `web_names` clean; the node suite (36 files); the twenty-edit recording (52 steps) and the stage's probe (46
steps: Reset all with its undo and redo, before and after a clear; a clear with its undo and redo; the cleared project
applied again; a landing zone moved, undone, redone and turned; a building's box deleted and brought back with the
spawn markers shown; a no-spawn volume's face dragged, undone, and dragged back where it was; the header's mission on
the Bar and the police station; a new document in the prefab builder) the same as on the stage's start commit, on the
same test server; browser checks `typed-pose`, `lights`, `clear-map`, `map-buildings`, `floor-boxes`, `spawns`,
`header`, `reset-all`, `small-defects`, `paste-buildings`, `projects` and `effects` pass on the Bar, and `streams` and
`spawns` on the police station (`clear-map` fails there on the start commit too: noted for the coordinator).
