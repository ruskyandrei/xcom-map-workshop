### The time of day in the Map settings window (project schema 10's `sun`)

Stage T-S1 of the game-likeness plan, design 3A (a bar and a dial): the Map settings window's Sun, moon and sky section
sets the map's time of day. It used to list the map's sun and sky light, and now holds:

- **The time bar**, 0:00 to 24:00, tinted with the light's colour at each hour and marked where the sun comes up and goes
  down. Its knob starts at the time whose light is likest the map's own, and the bar changes nothing there.
  - Dragging it sets several things together: the sun or moon's height, side, colour and brightness, the sky light,
    and the fog's two colours, the tint and the shadows of that hour.
  - The view follows while it moves (the Game look). The sun's shadow is drawn again every frame while it is dragged,
    and not after.
  - A drag is one undo step. The arrow keys move it five minutes (an hour with Shift), one step each.
- **The dial**: the side the light stands at its highest. N is the game's +X and E its +Y.
  - A mark on its rim shows the way the view looks, and a dot shows where the light is now.
  - It turns in the Snap setting's turn steps, one undo step a drag.
  - The light travels an arc: a quarter turn before the dial as it comes up, a quarter turn after as it goes down.
- **The line** under it: "07:10 · dawn" and the light in words ("Sun low in the south-west, warm, long shadows"). A
  second line appears once the direction differs from the map's: the map's shadows stay as they fall until a baked
  Build makes new ones.
- **More**, folded:
  - the light's and the sky light's colour and strength: set by hand, they leave the curve and are marked custom;
  - the game's time of day: Follows the light, Day or Night;
  - the fog and colour of the hour: what the time set, and what was changed in Fog and colour and is left alone;
  - the map's own lights listed;
  - As the map has it.
- **The marker in the view**: the sun or moon on its arc over the map, with both arcs and a line down to the map's
  middle. It shows in the Lights view and while the window is open. Dragged along its arc it sets the time, one undo
  step; Esc puts a drag back.
- **Fog and colour by the hour**: the bar writes the four members into the project's `atmosphere` and marks them in the
  `sun` record. A member changed in Fog and colour afterwards is left alone by the bar. That section shows a chip beside
  each of the four: "the hour" or "custom".
- **The project**: schema 10 adds `sun` beside `atmosphere`. It is `{time, heading, timeOfDay, light: {rotation, color,
  brightness}, sky?, custom?, atmosphere?}`: the values the project ended with, so a later change of the curve changes
  no saved project.
  - Only a record that differs from the map's own is saved.
  - It is carried through the edit state, opening, drafts, saving and Reset all, and counted in the header ("time of
    day set").
- **The compiler** reads `sun` for its shape alone. A project with one compiles, makes no lane, and its report notes
  `sun-not-built`: the Build does not write it into the map yet (stage T-S2). One of another shape is left out
  (`sun-shape`).
- **The curve** is `tools/viewer/sun_curve.json`. The page reads it at `/sun-curve.json`, Python through
  `sun_curve.py`, and the release ships it.
  - Each row is a light of one of the game's maps, taken whole from T-S0's survey (F-175): the sun or moon, the sky
    light, the fog's colours and the grade beside them.
  - Blended between rows; at 05:30 and 20:30 the light changes between moon and sun.
  - On each map the curve is made the map's own: a row of its own light, sky, fog and grade stands at its best time.
    So the bar there changes nothing, and away from it the values go over to the curve's.
- **The curve as built**, against the sun plan's first proposal:
  - 01:00 (was 00:00), moon, 80.73°, colour 66, 69, 136 at 1.1, sky 89, 107, 160 at 0.75 (URB_Bar). The peak moved
    to 01:00 so the moon's height peaks where its arc does, as the sun's does at 13:00.
  - 05:00 and 21:00 (were 04:30 and 21:00), moon, 52.9°, 40, 46, 129 at 1, sky 63, 93, 163 at 1 (URB_StreetOverpass:
    the next moon, five maps at 52.9°). The plan's 50, 60, 125 at 55° was a blend no map has.
  - 06:00, sun, 11.02°, 218, 96, 49 at 1, sky 125, 109, 187 at 0.5 (CLrgScout_Stonewall). Only the sky light changed;
    the plan's was not one of the survey's.
  - 07:30 and 18:30, sun, 15.83°, 255, 139, 45 at 1, sky 120, 111, 156 at 0.5 (CSmallScout_Marshlands, the commonest
    low sun). Only the sky light changed.
  - 10:00 and 16:00, sun, 40.22°, 255, 250, 180 at 1, sky 125, 129, 108 at 0.5 (LSmallScout_River, the commonest day
    sun). The plan had 40° and a sky of 125, 120, 110.
  - 13:00, sun, 56° (was 55: the survey's highest sun outdoors is 55.9°), 255, 245, 215 at 1.1, sky 150, 150, 170 at
    0.6 (the plan's: no map has a sun this high and white, so it is the one row not taken from a map).
  - 20:00, sun, 11.74°, 245, 126, 59 at 1, sky 124, 108, 182 at 0.75 (CSupplyShip_Wildfire, the survey's other sunset;
    the plan had dawn's colours here). Dawn and dusk now differ, so a map's best time is never a tie between them.
  - The new columns come from the same maps. Night fog 54, 60, 92 toward the light and grey away, tint 1, 1, 1.2,
    shadows -0.05 in blue. Low sun and sunset fog 79, 67, 80 and 56, 51, 80, a warmer tint. Day fog 80, 92, 87, the
    tint 0.9, 1, 1.2. Noon has the plain day grade and LLrgScout_Hillside's fog.
- Where:
  - the pure rules: [sun_rules.js](../../tools/viewer/web/sun_rules.js) (new);
  - the section: [sun_settings.js](../../tools/viewer/web/sun_settings.js) (new),
    [map_settings.js](../../tools/viewer/web/map_settings.js), [index.html](../../tools/viewer/web/index.html),
    [style.css](../../tools/viewer/web/style.css);
  - the record as the view draws it, the changes and the marker's drag:
    [sun_wiring.js](../../tools/viewer/web/sun_wiring.js) (new);
  - the marker and arcs: [sun_view.js](../../tools/viewer/web/sun_view.js) (new);
  - the view's light: [lighting.js](../../tools/viewer/web/lighting.js) (the `timeOfDay` getter, `sunMoved`);
  - the Fog and colour marks: [atmosphere_settings.js](../../tools/viewer/web/atmosphere_settings.js);
  - the joining: [app.js](../../tools/viewer/web/app.js), [test_api.js](../../tools/viewer/web/test_api.js);
  - the state carried: [editor_state.js](../../tools/viewer/web/editor_state.js),
    [document_state.js](../../tools/viewer/web/document_state.js),
    [document_session.js](../../tools/viewer/web/document_session.js),
    [delete_reset.js](../../tools/viewer/web/delete_reset.js), [project.js](../../tools/viewer/web/project.js),
    [piece_status.js](../../tools/viewer/web/piece_status.js);
  - the curve: [sun_curve.json](../../tools/viewer/sun_curve.json) and [sun_curve.py](../../tools/viewer/sun_curve.py)
    (new), [viewer.py](../../tools/viewer/viewer.py) (`handle_sun_curve`);
  - the server and the compiler: [projects.py](../../tools/viewer/projects.py),
    [light_edits.py](../../tools/editor/light_edits.py) (`sun_mark`), [compiler.py](../../tools/editor/compiler.py);
  - the release: [make_release.py](../../tools/release/make_release.py);
  - the contract in [research/editor-contracts.md](../../research/editor-contracts.md); [ARCHITECTURE.md](../../ARCHITECTURE.md).
- Checked:
  - [sun_rules_test.mjs](../../tools/viewer/tests/sun_rules_test.mjs): the spans, the blend and the arc; Bar's and
    Commercial Street's best times; the bar at the map's own time making no record; noon's light, sky and fog of the
    hour marked; a fog colour changed by hand left alone; a colour set by hand kept by the bar; As the map has it; the
    words.
  - [sun_record_cases.json](../../tools/viewer/tests/sun_record_cases.json), read by the node test and by
    [test_sun_curve.py](../../tools/viewer/tests/test_sun_curve.py) and
    [test_compiler_sun.py](../../tools/editor/tests/test_compiler_sun.py): the record's shape on both sides.
  - test_sun_curve.py also holds each row taken from a map to that map's values in the survey, and checks the route.
  - [test_projects.py](../../tools/viewer/tests/test_projects.py): a `sun` saved and refused.
  - [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)'s `time-of-day` on URB_Bar of export 43, in the Game
    look:
    - the knob at 01:00, the map's own; a key away and back leaves no record and the light as it was;
    - a mouse drag to 15:30 lights the view while it moves (warm, half way up, another sky light) and is one undo step
      on release, kept in the edit state, counted in the header, its tint marked "the hour" in Fog and colour;
    - Ctrl+Z gives the map's own light back;
    - the marker dragged in the Lights view is one undo step.
  - `map-settings` reads the sky list in More. The test hooks' names are recorded (`timeOfDay`, `dragTime`).
  - The user's look at the curve: pictures of URB_Bar and URB_CommercialStreet at five times, in the private folder
    of shots.
- Known gaps:
  - the Build writes none of it yet (T-S2);
  - the sky dome stays the map's own picture, so a night dome stays over a noon sun (T-S6);
  - lamps stay as the map has them;
  - the guide's section comes with the plan's guide stage.
  - The default frame draws as before, with no record and the marker hidden outside the Lights view and the window. A
    drag costs the sun's shadow pass each frame while it lasts (the plan's measure on Dirt Road: 6.5 ms against 4.8).
