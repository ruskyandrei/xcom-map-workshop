### app.js's first seams taken out: the cover model, the build window's words, Play's words and the made pieces' meshes

Review finding 22, bounded as the user asked: the seams the plan names, each moved whole with nothing else changed, and
each now tested in node where app.js could only be reached through a browser. What remains for the full split is in
the follow-up plan's list (below).

- **The cover-tile model** ([cover.js](../../tools/viewer/web/cover.js)): `coverFrame`, `coverTiles`, `coverGameWords`
  and `coverSightWords`, on plain arguments now (the cover record, its frame, the tile grid's corner, the recipe), with
  app.js's `coverTilesOf(root)` passing them.
- **The build window's words** ([build_window.js](../../tools/viewer/web/build_window.js), new): the steps with their
  states, times and progress, each step's line, the pieces left out and the mission warnings with their counts, the
  bar and the log's lines. app.js `renderBuild` puts them in the window; its result part, with the Prepare button's
  test of the compiler's error, is as it was.
- **Play's words** ([play.js](../../tools/viewer/web/play.js)): why a play can't start (`playBlocked`), a mission as
  the server takes it (`missionRequest`) and the "Starting XCOM" message (`playedMessage`).
- **The made pieces' meshes** ([walls.js](../../tools/viewer/web/walls.js), [ground.js](../../tools/viewer/web/ground.js)):
  a made wall's, slab's and ground shape's numbers, bounds, request and mesh record (`madeWallShape`, `madeSlabShape`,
  `madeGroundShape`, with `spelledLook`, `blastQuery`, `madeBounds` and the numbers' spellings), putting the record
  into the scene's meshes they are given. app.js keeps the dispatch and the plain material (`madeShape`).
- **`editChangedNow` and `cutaway`, measured** on URB_Bar (1,095 pieces, headless Edge, median of 15): the floor
  picker's cutaway took 0.3 ms in Full and 1.3 ms in Interior, a typed move's whole edit event about 1 ms and a
  selection's 1.5 ms. No small change was worth making at that cost; the passes over every root stay for the
  follow-up plan.
- `window.viewer`'s hooks and the gizmo's undo and redo commands are unchanged.

New node tests: [cover_tiles_test.mjs](../../tools/viewer/tests/cover_tiles_test.mjs),
[build_window_test.mjs](../../tools/viewer/tests/build_window_test.mjs), [play_test.mjs](../../tools/viewer/tests/play_test.mjs)
and [made_shapes_test.mjs](../../tools/viewer/tests/made_shapes_test.mjs). Checked besides: the node suite, the import
check, the full browser smoke on URB_Bar with `--projects`, and on URB_PoliceStation the walls, looks, cover,
floor-placing, made-prefab, look-undo and reset-all checks.

Left for the follow-up plan (the full app.js split): the document session (load, save, drafts, switching: round one
bound it to the session but it is still app.js's), the prefab builder, the build window's and Play's wiring (their
state lives in app.js with the project), `select` and the panels it drives, `editChangedNow`'s hub, `applyState`,
`prefabRecords`, the Buildings, Lights, Effects, Spawns and Landing zones views, and the test API inside `startScene`.
