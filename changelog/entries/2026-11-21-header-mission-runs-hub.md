### The header's mission picked runs the edit hub's mission run

Editor follow-ups, stage P5, item 3.25. Nothing the editor does changes.

[app.js](../../tools/viewer/web/app.js)'s handler of the header's Mission select called, after the mission was
chosen, the address written and a streamed piece out of view let go: the Lights view's `refreshLightVisibility`, the
Spawns view's `refreshSpawnMarkers` and `placeMissionGizmo`, then asked for the Effects view's redraw
(`setEffectsDirty(true)`), then the cutaway: the `mission` run's three refreshes by name, with the mark between them.
It now asks for the redraw first and runs the `mission` run ([edit_hub.js](../../tools/viewer/web/edit_hub.js)),
whose comment names it as the run's second starter. The mark moves before the refreshes: none of them reads it (the
Effects view's redraw mark is read only by the draw loop, by `pickEffect` and by a test hook), so they do what they
did.

Checked: `web_names` clean; the node suite; the twenty-edit recording (52 steps) and the stage's probe (44 steps, the
header's mission picked on the Bar, a mission the project adds, and through each of the police station's missions with
a streamed piece selected: the functions called in their order, the panels, the lights drawn, the spawn markers, the
address) the same as on the stage's start commit; browser checks `streams`, `spawns` and `floors-cut` pass on the
police station (two parts skip there as before: no streamed piece is drawn, no plain pod to copy).
