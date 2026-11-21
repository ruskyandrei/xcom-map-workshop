### A landing zone dragged keeps its own height

The landing zone gizmo's first move put a zone's ground onto a level of the map's tile grid, counted from the grid's
box. That assumed every map's floors and LWR's lines stand on a level's start. On the police station they do not:
its floors, its own landing and LWR's lines there stand at 0, 48 over the grid's first level (-48). So moving the
police station's landing zone sideways lifted it 16, and with it the drop zone frame and the Skyranger carried along,
which would stand 16 over the asphalt in a Build. The `clear-map` browser check stopped there on the police station.

- [spawns.js](../../tools/viewer/web/spawns.js) `draggedHeight`: a zone dragged keeps its own height, moved by
  whole storeys; only a zone saved under the grid (an old project's tutorial zone, 16 under it, which the rule was
  made for) comes onto the grid's nearest level. [zones_wiring.js](../../tools/viewer/web/zones_wiring.js)' gizmo
  uses it.

Checked: node cases in [clear_map_test.mjs](../../tools/viewer/tests/clear_map_test.mjs) (the police station's
height kept, storeys up and down, under the grid onto its first level, the tutorial's old zone). On a test server
the browser check `clear-map` passes on the police station (it stopped at the drag before), the Bar and TempleShip;
`spawns`, `reset-all`, `effects` and `grid-panel` pass on the Bar. `web_names` clean, node and repo suites pass.

Known gap: the zone gizmo still moves by whole tiles and storeys whatever the Snap setting.
