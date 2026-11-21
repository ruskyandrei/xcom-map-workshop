### A free-form wall's gaps are read on the map's grid; Join ends' rule

Two pure parts of the custom geometry improvements plan's stage 3, ahead of its handles (sections 4.2 and 4.6):

- **What a gap does in the game**, for a free-form wall, is read where the game's lines between tiles' centres cross
  the wall on the map's grid, at any place and angle, not on tile centres counted from the wall's start (right only
  for a wall on the tile lines). A wall off the tile lines or at a free angle then says, and warns of, what the game
  will do at each gap. [made_edits.py](../../tools/editor/made_edits.py) `grid_crossings`, `opening_play(…,
  centres)`, `made_wall_openings`; the twin [walls.js](../../tools/viewer/web/walls.js) `gridCrossings`,
  `openingPlay`, `playWords`; [made_panel.js](../../tools/viewer/web/made_panel.js) reads them for a free-form wall.
  Older walls are read as before.
- **Join ends**: two free-form walls' nearer ends brought to where their lines cross (or, in line, to the middle
  between them), each wall's origin staying where it is, so the joins then mitre the corner. `walls.js` `joinedEnds`;
  its button comes with the stage's handles.

Checked: [walls_test.mjs](../../tools/viewer/tests/walls_test.mjs) (crossings on and off the tile lines and at 45
degrees, a gap between crossings, Join ends at a corner, in line and alongside) and the compiler's crossings by the
same numbers; the editor and node suites; `web_names`.
