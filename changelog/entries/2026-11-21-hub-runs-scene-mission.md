### Four edit hub runs in place of calls of other areas by name (scene, landing-zones, mission, snap)

Editor refactor, stage P9, third part: a change that keeps behaviour, not a move. Where an area called other areas'
refreshes by name after a change of its own, it now runs a run of the edit hub, with which those areas register their
refreshes, called in the order the page called them. Nothing the editor does changes.

- **[edit_hub.js](../../tools/viewer/web/edit_hub.js)**: four runs in `RUNS`:
  - `scene` (app.js's `sceneChanged`, after it asks for the sun's shadows, the groups' pieces and the Effects view's
    redraw directly, as before): `cutaway` ([cutaway.js](../../tools/viewer/web/cutaway.js)), `ground-grid` (the ground
    grid drawn again if its pieces changed, [clear_map.js](../../tools/viewer/web/clear_map.js)) and `joins` (where
    made walls meet, [made_handles.js](../../tools/viewer/web/made_handles.js));
  - `landing-zones` (Clear map's three calls: the install's landing lines read as a map opens, a clear done and
    undone): `zones` ([zones_wiring.js](../../tools/viewer/web/zones_wiring.js));
  - `mission` (Clear map's `refreshMissionPicker`, when the mission picked changed with its choices): `lights` (which
    lights are drawn, [lights_wiring.js](../../tools/viewer/web/lights_wiring.js)), `spawns` (the markers and the
    picked one's gizmo, [spawns_wiring.js](../../tools/viewer/web/spawns_wiring.js)) and `cutaway`;
  - `snap` ([navigation.js](../../tools/viewer/web/navigation.js)'s `setSnapMode`, given the selected piece's root):
    `grid` (its grid chip, [selection.js](../../tools/viewer/web/selection.js)).
  Each area registers as its factory is made, in a function that discards what the refresh gives back, so none can end
  its run.
- **Arguments no longer needed:** Clear map is no longer given `cutaway`, `placeMissionGizmo`, `refreshLandingZones`
  or `refreshSpawnMarkers`, and navigation no longer `refreshGrid`; app.js no longer takes `refreshGrid` or
  `refreshJoins` from their factories. Clear map still calls the Lights view's `refreshLightVisibility` itself where a
  clear sets the lights' redraw and the selection between its other steps.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the hub's rule names the four runs, and what stays direct (state).
- **[app.js](../../tools/viewer/web/app.js)**: 1,311 lines to 1,310.

Checked: the twenty-edit recording (which traces `sceneChanged`, `cutaway`, `refreshGroundGrid` and `refreshJoins` in
their order) the same as on the stage's start commit, all 52 steps; a probe of the paths it does not walk (the stage's
scratch script, the stage's start commit's page against this one on the same server): on the police station a stream
mission picked, Clear map, its undo and redo; on the Bar a project mission ticked, picked, unticked (the `mission` run),
the untick undone and done again, Clear map, undo and redo (the `landing-zones` run), and a ladder selected with the
snap setting cycled five times (the `snap` run): the functions the runs call, in their order, and the header, the rail,
the piece panel, the lights drawn and the mission gizmo the same after each of the 20 steps. A probe of the hub's
runs while app.js loads: none, on the Bar or in the builder (the first come as the scene opens). `web_names` clean;
the node suite; browser checks `api-names`, `typed-pose`, `recipe`, `map-buildings`, `clear-map`, `spawns`,
`floor-tiles`, `lights`, `cover`, `play-area`, `let-go`, `reset-all`, `paste-buildings`, `small-defects`, `walls` and
`made-prefab` pass, and on the police station `streams`, `spawns` and `floors-cut` (two parts skip there as before:
no streamed piece is drawn, no plain pod to copy).
