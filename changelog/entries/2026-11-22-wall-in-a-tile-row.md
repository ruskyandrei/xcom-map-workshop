### A made wall standing in a tile row: its openings read as the game plays them, and a note of the tiles it takes

EXP-90's wall A stood 6.5 off a tile row's centre line and took that row's tiles; its window's tile could not be stood
on and no unit vaulted through it (F-146), where the compiler's reading of an opening assumed a wall on a tile edge
and called the window climbable. The game takes a tile wholly when a piece meets a box 40 by 40 round its centre from
60 to 92 over its floor (the tile rebuild's occupancy), and a vault goes between two tiles over a low piece on their
shared edge.

- [made_edits.py](../../tools/editor/made_edits.py): `WALL_ROOM` (that box), `row_tiles` (of the places the lines
  between tiles' centres cross a free-form wall, those where its solid, along the crossing line, meets the box round a
  tile's centre), `room_left` (an opening clears that box), and `opening_play` taking them (`taken`): an opening over
  such a tile is that tile, walked through when it leaves room and else taken, never climbed through, `inside` in its
  answer. `made_wall_openings` notes `wall-in-row` (the tiles a wall stands over and takes, and that it gives cover to
  the tiles either side) and warns `wall-doorway-low` with that reason for a doorway over a tile it leaves no room in.
- [walls.js](../../tools/viewer/web/walls.js) `WALL_ROOM`, `rowTiles`, `openingPlay`, `playWords` ("Its tile is taken,
  as the wall stands over the tile's middle: no one stands in it or goes through it; ..." and "Units stand in its tile
  and walk through it, ...") and `rowWords` are the twins; [made_panel.js](../../tools/viewer/web/made_panel.js) shows
  them in the Wall section (its openings, and its notes). The box is pinned in
  [twin_constants.json](../../tools/viewer/tests/twin_constants.json), and the cases both sides pass are
  [opening_play_cases.json](../../tools/editor/tests/opening_play_cases.json) (wall A, the same wall on the edge, walls
  along y on an edge, 30 off and 25 off a column's centre line, doorways leaving no room, a low wall, a wall at 30
  degrees).
- floors.js's new `slabTiles` (the previous change) is `slabFloorTiles`, as walls.js has a `slabTiles` of its own.

A wall on the tile edges reads as before: its crossings stand over no tile's middle, and `opening_play` gives the same
answer.

Checked: [test_compiler_free.py](../../tools/editor/tests/test_compiler_free.py) (the cases, wall A as played, the
note, a narrow doorway's warning), [walls_test.mjs](../../tools/viewer/tests/walls_test.mjs) (the words),
[shared_cases_test.mjs](../../tools/viewer/tests/shared_cases_test.mjs), the twin constants' tests; the editor, node,
viewer and repo suites; `web_names.py`; the `made-openings` browser check (a free-form wall pasted in a tile row: its
openings' words and notes as the compiler reads them) with `walls` and `api-names`, on a test server.
`compile_record.py` against the previous change: six compiles of five tests of test_compiler_free.py differ, their
free-form walls standing in the test scene 24 off a row's centre line (their faces 6 into the box): each gains a
`wall-in-row` note, and the five whose doorway (50.5 wide) leaves no room in its tile warn `wall-doorway-low` in place
of `wall-doorway-no-door`; their specs and native edits are the same; and the new tests' three compiles.
`build_outputs.py` against `04b9ee4`: the eleven inputs' Builds byte for byte.

Known gaps: not played. The box's height is read over the wall's floor (a unit from the level's bottom on the ground),
and its reach along a turned wall as along the wall, exact for walls along the axes.
