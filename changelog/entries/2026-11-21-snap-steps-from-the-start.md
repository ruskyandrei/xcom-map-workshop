### Snap steps count from where a drag started, and snap off is smooth everywhere

The snap setting now means one thing on each of these paths: snap off moves without rounding, to fractions of a unit;
fine moves in steps of 24 and tile by whole tiles across and levels of 64 up, each counted on the distance moved, so a
piece, a face or a gap off the grid keeps its offset (the custom geometry improvements plan, section 3).

- The gizmo's fine snap stepped by rounding the pivot to multiples of 24 from the world's middle, pulling a piece off
  the grid onto it; it now steps from where the drag started, as tile snap did. With the piece's own axes shown
  (local space) a move steps along them. A building's box still moves by whole tiles and levels.
  [gizmo.js](../../tools/viewer/web/gizmo.js)
- A gap's handles moved by whole units with snap off and in steps of 24 up under tile snap; they now move smoothly with
  snap off and in levels of 64 under tile snap, and a side or top steps the distance it is dragged rather than landing
  on multiples of the step. Alt stays steps of 8. [walls.js](../../tools/viewer/web/walls.js) `movedOpening`,
  [made_handles.js](../../tools/viewer/web/made_handles.js).
- A cover block's or invisible floor's faces moved by whole units with snap off, sized to multiples of the step under
  fine and tile, and stepped heights by 96 from the type's first top under tile snap. They now move smoothly with snap
  off, step the distance dragged under fine and tile, and step heights in levels of 64 under tile snap.
  [cover.js](../../tools/viewer/web/cover.js) `resizedCover`, [cover_wiring.js](../../tools/viewer/web/cover_wiring.js).
- A piece placed or pasted under fine snap was rounded to multiples of 24 from the world's middle; it now moves from
  where the piece stands in the map in steps of 24, as tile snap moves it in whole tiles.
  [clipboard.js](../../tools/viewer/web/clipboard.js), [snap_steps.js](../../tools/viewer/web/snap_steps.js)
  `droppedAcross`.
- The handles' hints name the steps from the one table (`moveWords`, `stepWords`).

Checked: node tests [snap_steps_test.mjs](../../tools/viewer/tests/snap_steps_test.mjs),
[walls_test.mjs](../../tools/viewer/tests/walls_test.mjs) and [cover_test.mjs](../../tools/viewer/tests/cover_test.mjs)
(new cases for snap off and for stepped distances, which failed before), `web_names`. The browser checks follow with
the align commands.
