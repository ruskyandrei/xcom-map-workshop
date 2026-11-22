### Map settings: the sun, moon and sky listed with the map's background sound, chosen, played and set by a volume bar

The page's control for the project's `backgroundSound` (schema 5), in the design the user chose from three mock
designs (B: a Map settings window with the sun, moon and sky, the volume as a bar under the choice as in A).

- [map_settings.js](../../tools/viewer/web/map_settings.js) (`createMapSettings`): the window, opened from the Map
  menu's Map settings… and from View options' "Sun, moon and sky…" (which was a tick showing the list in View options;
  the list moved into the window). The background sound: the map's own first, the game's other 25 beds, None; a Play
  button that plays the chosen bed here, every wave of its cue at once and looping; a volume bar (0 to 200%). A
  choice and a volume (on the bar's release) are each one undo step; None keeps no volume of its own; the header's
  chip says "background sound changed". The rules (the choices, the record, the preview's volume) are in
  [background_sound_rules.js](../../tools/viewer/web/background_sound_rules.js), with
  [background_sound_rules_test.mjs](../../tools/viewer/tests/background_sound_rules_test.mjs).
- [viewer.py](../../tools/viewer/viewer.py) `handle_background_sound`: `GET /background-sounds.json` (the beds) and
  `GET`/`HEAD /background-sound.ogg?cue=&wave=` (a bed's wave read from the map that plays it in the install, checked
  and kept by audio.py's wave cache). [background_sound.py](../../tools/viewer/background_sound.py) `waves` (the
  waves a cue plays, through its nodes) and `wave_source`; [background_sounds.json](../../tools/viewer/background_sounds.json)
  lists each bed's waves.
- [scene_start.js](../../tools/viewer/web/scene_start.js) shows the Map menu's item on any map but in the prefab
  builder; [document_state.js](../../tools/viewer/web/document_state.js) and
  [piece_status.js](../../tools/viewer/web/piece_status.js) count the change; test hooks `showMapSettings` and
  `mapSettings`; [one_home_test.mjs](../../tools/viewer/tests/one_home_test.mjs) and ARCHITECTURE.md name the
  window's one plain fetch (the wave's range probe, as the Effects view's); ARCHITECTURE.md has the area's row.

Checked: the browser check map-settings on a test server (the window from both openers, the sky listed, the choices,
a bed and a volume each one undo step and counted, every wave of the bed served as Ogg, an unknown bed 404, Play and
Stop, None, three undos back to the map's own, Esc) with clear-map and api-names; the node, repo and viewer suites
(`test_background_sound`: each bed's waves against its map); the page looked at in the browser pane. Played offline
only: the Build's side was played in EXP-94.

Known gaps: the user guide does not describe the window yet.
