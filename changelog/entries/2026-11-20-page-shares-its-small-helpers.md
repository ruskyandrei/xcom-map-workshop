### The page shares its small helpers: one way to ask the server, one row builder, one set of grid numbers

Review finding 56. Nothing a user sees changes, but for the settings' keys (moved, not lost) and the effects' replays
(no longer hidden for a moment while their textures came back).

- **[api.js](../../tools/viewer/web/api.js)**: one fetch-and-throw helper, `call(method, url, body)`, with `refusal`
  and `answer` for the picture routes that send a PNG. It throws an Error with `status` and `body` (the answer's
  JSON). It replaces the fourteen copies, in five shapes, in project.js, prefabs.js, squad.js, library.js, manager.js,
  gamemaps.js, map_browser.js, prefab_test.js, map_picture.js, setup.js, play.js, precache.js and app.js's build-queue
  call and prefab Problems check.
  - Each keeps its own words for a refusal with no `error` ("The server said …", "The library didn't answer (…)",
    "The server answered …", the status text).
  - The readers of `error.detail` (app.js, prefabs.js, project_files.js) and of the prefab test's spread fields
    (`code`, `test`) read `error.body` now.
  - prefab_test.js no longer throws a SyntaxError with no status on an answer that isn't JSON.
- **One row builder** in [pieces.js](../../tools/viewer/web/pieces.js) (`listRow`) for the Add panel's spawn point,
  landing zone, light and piece rows, which wrote the same twenty lines each (two more went with finding 63).
- **[constants.js](../../tools/viewer/web/constants.js)**: the tile (96), the level (64) and the quarter turn (16384),
  used by poserule.js, floors.js, cover.js, spawns.js, walls.js, ground.js and app.js; prefabs.js's and floors.js's own
  unused copies are gone. In app.js the bare 96s and 64s that mean a tile or a level (grid steps, snaps, the builder's
  floor, the tile-grid defaults, the ground grid's shader) and the four quarter turns are written with them; numbers
  that only happen to be 96 or 64 (sweep heights, canvas sizes, probe heights, recursion limits) and the words shown
  to users stay as they were.
- **Written once now:** the picture-key hash (`api.js` `hex16`, for library.js's effect pictures and look_picker.js's
  samples, giving the same keys as before, so kept pictures are found); `linear` and `toView` (lighting.js, imported
  by lights_view.js); the clock (build_queue.js's, for app.js's build window and wave player and precache.js).
- **[storage.js](../../tools/viewer/web/storage.js)**: every setting the page keeps is `workshop.<name>`. The keys of
  the older styles (`viewer.stats`, `viewer.pivot`, `viewer.flyKeys`, the camera speeds, `viewer.fold.*`,
  `gameMapsGroup`, `xcom-map-workshop.manager.projectFiles`) are read once and moved to their new names. app.js,
  manager.js and gamemaps.js read and write through it.
- **The effects preview's allocations** ([effects_preview.js](../../tools/viewer/web/effects_preview.js),
  [effects_sim.js](../../tools/viewer/web/effects_sim.js)):
  - a replay binds each emitter's next run to the geometry, material and mesh it has, where it used to release and
    remake them all;
  - a sprite takes the shared quad's index and corners off before it is disposed, so they stay for the others;
  - a mesh emitter's instanced meshes are disposed with it;
  - the simulation uses one `own` function per emitter, not one per particle per step.

Checked: two new node tests, [api_test.mjs](../../tools/viewer/tests/api_test.mjs) (answers, refusals and their words,
JSON sent only with a body, the picture key unchanged) and [storage_test.mjs](../../tools/viewer/tests/storage_test.mjs)
(old keys moved once, blocked storage); the node suite; the import check; the full browser smoke on URB_Bar with
`--projects`, and the named checks for the library, effects, prefabs, the builder and the prefab test.
