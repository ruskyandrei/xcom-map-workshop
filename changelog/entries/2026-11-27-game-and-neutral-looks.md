### The Game and Neutral looks (one switch, key K)

Stage G1 of the game-likeness plan, after the round of mock designs (design 1A chosen): the View options' Lighting
row, which had three buttons (Map, No area, Neutral), is now Look, with two: **Game**, the map as the game shows it
(its own lights today; its fog, grade and baked light as the plan's later stages come), and **Neutral**, the even
studio light for building. The map's area lights are a tick under Game (Area lights), with no say in Neutral. **K**
switches the look anywhere (L stays Align to grid), said in the hint line. A scene opens in Neutral, as since 7
November, and the Game look is greyed where a scene has no lighting of its own, as the map modes were.

- Where: [index.html](../../tools/viewer/web/index.html) (the row and its tick),
  [lights_wiring.js](../../tools/viewer/web/lights_wiring.js) (`lightingModes`, `lookOptions`, `setLook`,
  `toggleLook`; the light drawn by `lightingMode`), [navigation.js](../../tools/viewer/web/navigation.js) (K),
  [app.js](../../tools/viewer/web/app.js), [style.css](../../tools/viewer/web/style.css) (`.lookrow`); the test hooks
  gain `setLook` ([test_api.js](../../tools/viewer/web/test_api.js), recorded in
  [viewer_api_names.json](../../tools/viewer/tests/viewer_api_names.json)).
- The tools that named a lighting mode brought level: [mark_shots.py](../../tools/viewer/mark_shots.py) and
  [likeness.py](../../tools/lab/likeness.py) take `game` and `neutral`, and read `map` and `map-no-area` as the
  Game look with and without its area lights; [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)'s
  map-lights check pictures the Game look without and with its area lights and the Neutral look, and presses K.
- Checked: browser_smoke's `map-lights`, `lights` and `api-names` checks on a test server (export 43); the row
  looked at in the browser.
- Known gaps: the user guide still describes the three buttons (its update is the plan's guide stage).
