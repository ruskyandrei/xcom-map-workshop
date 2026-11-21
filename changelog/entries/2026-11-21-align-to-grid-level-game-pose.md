### Align to grid, level and game pose in place of Level snap and the recipe snap

Two snaps that were not steps of the snap setting are now commands, and a piece can be brought onto the grid without
typing (the custom geometry improvements plan, section 3, decisions D4, D5, D11 and D12, their defaults):

- **Align to grid** (L, or the piece panel's Align section): the selection's pivot moves to the nearest multiple of
  the snap setting's steps from the tile grid's corner and lowest level, and turns to whole angular steps; with snap
  off, to the nearest tile corner, level and quarter turn. One undo step. `gizmo.js` `alignToGrid`.
- **Align to level** replaces Level snap (the rail's L button and its key): a floor piece was kept to whole levels
  when placed and moved; it is now placed and moved as any piece, and Level (shown for a floor piece) moves it to its
  height in its map moved by whole levels, the nearest; a copy goes by its original's height. `align.js`
  `alignToLevel`, [floors.js](../../tools/viewer/web/floors.js) `nearestLevel`,
  [level_snap.js](../../tools/viewer/web/level_snap.js) `floorBaseOf`.
- **Align to game pose** replaces the recipe snap: under tile snap a ladder, door, car, van or fracturing piece was
  pulled onto its pose rule; it now steps as any piece does (so one on its rule stays on it), and Game pose (shown for
  such a piece) puts it at the nearest pose its rule allows. The snap button's R and the Recipe snap chip go; the Off
  the grid chip says to use Game pose. A prefab with such a piece is placed under the snap setting, and only a prefab
  with a building still goes by whole tiles. `gizmo.js` `alignToGamePose`,
  [selection.js](../../tools/viewer/web/selection.js), [prefab_place.js](../../tools/viewer/web/prefab_place.js),
  [clipboard.js](../../tools/viewer/web/clipboard.js).
- The **Align section** shows for one piece too, with its Align to row (Grid, Level, Game pose); with two or more it
  keeps its target, axes and Align button. [align.js](../../tools/viewer/web/align.js),
  [index.html](../../tools/viewer/web/index.html), [style.css](../../tools/viewer/web/style.css).
- A **typed pose** with snap on is taken as a move or turn from where the piece stands in the snap setting's steps,
  said in the hint line while it is typed; with snap off, as typed. [snap_steps.js](../../tools/viewer/web/snap_steps.js)
  `typedStep`, [app.js](../../tools/viewer/web/app.js).
- The prefab builder's Align to grid is renamed **Align prefab to grid** (D11).
- The help panel's keys, the test hooks (`alignToGrid`, `alignToLevel`, `alignToGamePose` in place of `levelSnap`,
  `setLevelSnap`) and ARCHITECTURE.md's rows say the same.

Checked: node tests (snap_steps_test, floor_rules_test), `web_names`, the viewer and repo suites, and the browser checks
`api-names`, `typed-pose`, `pivot`, `recipe` (rewritten: off the grid, Game pose, tile snap's typed steps), `adding`,
`groups`, `copy-drag`, `clear-map`, `align`, `cover` (tile snap's levels of 64), `floor-placing` (rewritten: placed as
any piece, then Level) on the Bar, and `walls`, `made-openings`, `rock-corner`, `room-buttons` on the police station,
on a test server.

Known gaps: the user guide still describes Level snap, the recipe snap and the old steps, and its rail picture shows
the L button; it is brought level, pictures too, in the plan's guide pass. The Build gains no note for a floor piece
off its levels: no run has shown what the game does with one, so it would be a guess.
