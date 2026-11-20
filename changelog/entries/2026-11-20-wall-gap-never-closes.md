### A wall's gap never closes up to nothing, and a drag the wall tool can't make isn't applied

Review finding 32, the page's item.

`movedOpening`'s "a gap never takes the whole wall" fallback put a side `least` in from the wall's end. On a one-tile
wall moved by whole tiles, that is the full length, so dragging a side gave `{x0: 96, x1: 96}` or `{x0: 0, x1: 0}`.
`toolWall` refuses those numbers, yet the drag still applied them and asked the server for a mesh.

- [walls.js](../../tools/viewer/web/walls.js): the fallback keeps the gap at least `OPENING.width` wide. Where the step
  in would shrink the gap rather than move its side outwards, the side stays where it was. A gap that already reached
  both ends is cut back to the narrowest gap.
- [app.js](../../tools/viewer/web/app.js): a wall handle's drag applies only numbers the wall tool makes. A step that
  `toolWall` refuses leaves the drag at its last good state.
- Checked:
  - [walls_test.mjs](../../tools/viewer/tests/walls_test.mjs) drags a one-tile wall's gap sides by whole tiles. The gap
    stays as it was and stays a wall the tool makes. A whole-wall gap cuts back to 16 wide, and a two-tile wall still
    stops a tile in. The first case gave `{x0: 0, x1: 0}` before this change.
  - The browser check `walls` passes (on `?map=URB_PoliceStation`, the map it is written for), and so does the node
    suite.
- Not in this change: the slab and compiler items of the finding (a floor whose holes cover it all, overlapping holes),
  which belong to the Build's side.
