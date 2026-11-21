### A game point as a point of the view: handles.js' gameToView only

Editor follow-ups, stage P4, item 3.15 in part. Nothing the editor does changes.

- [buildings_wiring.js](../../tools/viewer/web/buildings_wiring.js) had its own `viewPoint`, the same function as
  [handles.js](../../tools/viewer/web/handles.js)' `gameToView` (a game point x, y, z as the view's x, z, y). It
  imports `gameToView` now and returns no `viewPoint`.
- The test hooks ([test_api.js](../../tools/viewer/web/test_api.js)) use `gameToView` where they were given
  `viewPoint`, and `screenOf`, which wrote the same conversion inline, is `clientAt`: one function for the two hooks.
  They keep their own projection, not the handles' `projector`: the arithmetic is the same, but `projector` gives null
  for a point outside the camera's depth range, where the hooks give the point a check asked for. A comment says so.
- `createSpawnsWiring` ([spawns_wiring.js](../../tools/viewer/web/spawns_wiring.js)), `createZonesWiring`
  ([zones_wiring.js](../../tools/viewer/web/zones_wiring.js)) and `createTestApi` import `gameToView`, a plain export,
  rather than being given it (as item 3.23 does for the other plain exports it names);
  [app.js](../../tools/viewer/web/app.js) no longer imports it.

Not done: the handles' meshes and step words wait for the Size tool plan, which reworks the handles.

Checked: `web_names` clean; each factory's parameters against the keys app.js gives it (61 factories, no difference);
the node suite; the twenty-edit recording the same as on the stage's start commit (52 steps); browser checks
`api-names`, `spawns`, `box-select`, `floor-boxes`, `map-buildings` and `clear-map` pass on the Bar.
