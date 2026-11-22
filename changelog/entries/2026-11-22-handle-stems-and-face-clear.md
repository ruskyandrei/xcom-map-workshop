### Every white handle of a made piece on its stem; a wall's face handle clear of its gaps; the size tooltips as sizing is

Found by the guide pass of 22 November 2026:

- A made floor's or ground shape's top and bottom handles, and a wall's face handle, showed without the stem design A
  gives every white handle: the stems' line had room for four. It has room for six now (a floor's or ground shape's
  four sides, top and bottom; a wall's five).
- A wall's face handle (its thickness) stood a quarter along it, and a gap there put the gap's side handle within
  reach of it. The face and bottom handles now stand at the first of a few places along the wall that no gap spans
  (a quarter along first, as before, when it is clear).
- The Wall, Floor, Ground and cover block sections' tooltips said whole tiles or steps of 1 unit: they say Snap's
  steps now, smoothly with snap off.
- [browser_walls.py](../../tools/viewer/tests/browser_walls.py) had two `FREE_WALL`s, the second replacing the first
  at import: the wall-in-row check's own is `ROW_WALL` now (EXP-90's wall A's height, as meant).

Files: [made_handles.js](../../tools/viewer/web/made_handles.js), [index.html](../../tools/viewer/web/index.html);
the guide's made-walls picture retaken (the face handle stands clear of the doorway, on its stem) and
[take_shots.py](../../tools/release/guide/take_shots.py)'s note on it.

Checked: in a headless page, a made floor draws six stems and a 480 wall with a gap from 96 to 192 puts its face handle
at 60; the browser checks walls, free-handles, texture-mapping, rock-corner, made-openings, made-break, looks,
room-buttons, api-names and tile-footprints on a test server; the made-walls picture looked at beside the guide's.
