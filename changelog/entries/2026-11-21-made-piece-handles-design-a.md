### A made piece's handles and commands, as chosen (design A)

The user chose design A of the custom geometry improvements plan's stage 3 mock designs, and it is built:

- **Every size handle white on a stem**: a made wall now also has a bottom handle (under the floor line) and a handle
  out of the face toward the camera for its thickness; a floor or roof has top and underside handles; a ground shape a
  bottom handle beside its top. Each moves its face's number in the snap setting's steps, the opposite face and the
  piece's pivot staying. [made_handles.js](../../tools/viewer/web/made_handles.js) `wallHandlesNow`,
  `slabHandlesNow`, `groundHandlesNow`, `moveFreeDrag`.
- **A wall's gaps a set at a time**: the picked gap shows its five handles, every other gap its middle alone, which
  picks it.
- **Commands in the sections** ([index.html](../../tools/viewer/web/index.html),
  [made_panel.js](../../tools/viewer/web/made_panel.js)): Pivot to corner in the Wall, Floor and Ground sections (the
  piece renumbered from its low corner, its place moved by as much, nothing moving in the world: made_free.js
  `pivotedToCorner`); Taller than its look, Repeat storeys or Stretch, where a wall is taller than its look (D3); Join
  ends with two walls picked (walls.js `joinedEnds`; one undo step for the walls it changes). J held while a wall's
  end is dragged takes it to the nearest other wall's end.
- The help panel lists the white dots and J; [UI-GUIDELINES.md](../../UI-GUIDELINES.md) section 1 writes the pattern.

Checked: the new browser check `free-handles` (thickness under tile snap a tile thicker with the origin kept, the
bottom a level up, gaps a set at a time, Stretch and its undo, Pivot to corner on a turned wall, a floor's top and
underside handles, Join ends on two crossing walls as one undo step; [browser_walls.py](../../tools/viewer/tests/browser_walls.py),
[browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)); `walls` (gaps a set at a time), `looks`, `made-break`,
`made-openings`, `rock-corner`, `room-buttons`, `made-prefab` on a test server; `web_names`; the node and repo suites.
