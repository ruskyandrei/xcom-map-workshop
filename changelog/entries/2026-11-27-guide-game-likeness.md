### The guide says the Game look, the time of day, the sky, fog and colour, and the baked light

The user guide ([guide.html](../../tools/release/guide/guide.html)) brought level with the game-likeness plan's stages
(the guide stage, T-S7):

- **View options** (`#viewoptions`): the Look row (Game and Neutral, K) in place of the three lighting buttons (Map,
  No area, Neutral), the line of the project's last baked Build under it, the Game look's Area lights tick; the
  legend renumbered (17 items), Sun, moon and sky… now opening where the time of day is set.
- **The Game look** (`#game-look`, new, in the contents): what it draws (the materials by the game's shaders, the
  map's baked light and baked sun shadows, its height fog, grade, bloom and sky dome, the changed pieces and lights
  lit live), what it leaves out (decals, depth of field, a material's scene reflections, effects a likeness), and
  `#build-light`: a project whose last Build baked lit by that Build's lightmaps, with View options' line, what stays
  live and what a quick Build does.
- **Map settings** (`#map-settings`): Sun, moon and sky is no longer a list. `#time-of-day`: the time bar, the dial,
  the line, the Sky row (`#sky-choice`: the map's own, one of the game's skies, Follows the light), More (the light's
  and the sky light's colours and strengths marked custom when set by hand, In the game: Follows the light, Day,
  Night, the hour's fog and colour, the map's own lights, As the map has it), the marker on its arc in the Lights
  view, the baked sun shadows giving way to the live shadow when the light turns, and what the Build writes (both
  kinds of Build; the old shadows kept by a quick Build, the turned sun's shadows traced by a baked one, the
  warnings, what stays the old sun's). `#fog-colour`: the looks first, the Fog and Colour folds, the hour and custom
  chips, the post-process volumes' note and warning, Reset to the map's own. The background sound and Long War
  Rebalance under `#map-sound`.
- **Smaller places:** What it does; a new typical task, Make it night, or noon (`#task-time`), and Change the
  lighting pressing K; the header's change count (a time of day set, fog and colour changed) and View options item;
  the Map menu's Map settings… item; the Snap section (the dial turns in its steps); Lights (the Game look in place of
  Map lighting, the sun or moon set by the time of day, its marker); a piece of another map lit live in the Game
  look; Build (both kinds with the time of day, the Game look after a baked Build, what a build holds, the turned
  sun's warning); Map picture (the look); the keys table's K; the limits (the time of day, sky, fog and colour can
  be set; the sun, moon and sky light set by the time of day; the view's two limits written for the Game look) and
  the in-game limits (a quick Build's shadows under a turned sun, what a baked Build keeps of the old sun).

Pictures ([shots/](../../tools/release/guide/shots)): new `look-neutral`, `look-game` and `look-noon` (one view of the
Bar in the Neutral look, the Game look at the map's own 01:00 and the Game look with the bar at 13:00), `map-sun` and
`fog-colour` (the Map settings window at 19:30 in the Game look), `sun-marker` (the Lights view at 17:30); taken again
`view-options` (the Look row, the Build's line, Area lights). Kept: the rest, whose parts did not change. Sixteen
whole-window pictures still show the old brand, as they did before, and every picture of the view now differs a
little from a new one (the materials drawn by their programs); `flags` predates the Align section's Align to row.

[take_shots.py](../../tools/release/guide/take_shots.py): new shots `looks`, `map-sun` (with `fog-colour`) and
`sun-marker`, with helpers for the look, the time bar and undoing (`game_look`, `drag_time`, `undo_to`) and the camera
`LOOK_VIEW`; `view-options` taken after `save-as`, in the Game look, with the demo project opened again
(`open_project`) and lit by its baked Build, which it makes unless the project manager's queue baked it
(`build_project`, which `quick_build` now calls), one piece moved since; the docstring says what the Game look's shots
need (export 44 or later and the library read).

Checked: a full run of take_shots.py on a test server with fresh stores and a scratch cache of URB_Bar at export 45
(the library read into it). It stopped at `view-options` (Open… loads the page again, and the wait read `viewer`
before it was back); with the wait mended, `view-options`, `prefab-builder`, `mission-objects` and `diagonal` were taken
on the same stores, the first building the demo with baking (the queue had baked the other project). Every new and
retaken picture looked at, and every picture compared with the guide's (guide_tools.py compare and sheet);
`python tools/run_tests.py viewer -k guide`, `release` and `repo`; the page as published photographed at each changed
section (guide_tools.py look). Known gaps: the last release's zip still carries the earlier guide; the published page
changes when main is pushed.
