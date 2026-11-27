### The baked sun shadows give way when the time of day turns the sun

The rest of stage B3, now that T-S1's time of day is in. A map's baked shadows of its sun or moon only fit that
light. When the project's time of day turns the light more than half a degree from where the map has it, every piece
takes the live shadow map, the pieces wholly in the map's own sun's shadow included. Back at the map's own time,
they take the baked shadows again.

- Where: [sun_rules.js](../../tools/viewer/web/sun_rules.js) (`sunTurned`), [app.js](../../tools/viewer/web/app.js)
  (the draw loop sets the baked light's `setSunShadows` from it each frame; one uniform).
- Checked:
  - [sun_rules_test.mjs](../../tools/viewer/tests/sun_rules_test.mjs): the map's own light is not turned; a degree in
    pitch is; noon on URB_Bar is; a map without a dominant light never is.
  - On URB_Bar in a test server's page, in the Game look: the baked sun shadows were on at the map's own 01:00, off
    at 13:00, and on again back at 01:00.
- Known gaps: none known.
