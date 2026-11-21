### Landing zones move as the snap setting says

A landing zone's gizmo moved it only by whole tiles across and storeys up, and a zone placed from the Add panel
stood on a tile, whatever the snap setting. At the user's word they now follow it, as the editor's other moves do:
smoothly with snap off, in steps of 24 units with fine snap, by whole tiles across and storeys up with tile snap.
Turning stays quarter turns whatever the snap: a zone faces north, east, south or west, the only ways Long War's lines
and the game's landing take, and the gizmo's hint says so.

- [spawns.js](../../tools/viewer/web/spawns.js): `ZONE_STEPS` and `snapZoneMove` for the gizmo's steps,
  `placedZone` for a zone placed (a unit off a tile corner under tile snap, as LWR's lines stand; on 24's under fine
  snap; where clicked with snap off). `draggedHeight` no longer pulls a zone moved under the grid back onto it (the
  compiler warns of a zone outside the grid); only a zone saved under the grid still comes onto it with its first
  move. [zones_wiring.js](../../tools/viewer/web/zones_wiring.js) uses them, and its move, turn and placing hints name
  the step.
- [guide.html](../../tools/release/guide/guide.html): the landing zone's task, its section and the table of what moves
  how say the same.

Checked: node cases in [clear_map_test.mjs](../../tools/viewer/tests/clear_map_test.mjs) for each snap setting's
moves and places and the heights. The browser check `clear-map`
([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)) drags the zone under tile snap (whole tiles, height
kept), undoes it, and drags it with snap off (a move that is no step of 24, height kept); it passes on the police
station, the Bar and TempleShip. The hints read on a test server for each setting. The guide's tests, `web_names`,
node and repo suites pass.
