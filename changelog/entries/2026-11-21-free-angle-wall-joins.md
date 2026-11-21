### Free-form walls meet at any angle: mitred corners, stems that lean

Where two free-form made walls meet, their ends are now worked out at any angle (the custom geometry improvements plan,
4.7, decisions D7 and D10 on their defaults): two ends within a unit of each other are each cut on the one upright
plane through the corner, from where the inner faces cross to where the outer faces cross, right angles too; two ends
in line meet end to end; an end on another wall's line between its ends stops against that wall's near face, leaning
along it, as ends do against a pair in line. Under 30 degrees, or three or more ends at a point with no two in line,
ends meet square. An end goes to the Build as `{inset, lean}`: how far in from the wall's own end its solid stops, and
how far its plane leans along the wall for each unit across. A free-form wall meeting a wall of an older version keeps
today's rule. The angle is the rounded rotator's on both sides.

- [made_edits.py](../../tools/editor/made_edits.py): `free_wall_joins`, `made_wall_joins` (the free-form walls among
  themselves, every other end by `wall_joins`), `join_made_walls` putting leaning ends into the request and the box.
- [walls.js](../../tools/viewer/web/walls.js): the twins `freeWallJoins`, `madeWallJoins`; `joinWords` says "a
  mitred corner"; [made_handles.js](../../tools/viewer/web/made_handles.js) `refreshJoins` uses `madeWallJoins`.
- [free_join_cases.json](../../tools/editor/tests/free_join_cases.json) (new): 17 cases both sides pass (right angles,
  60, 135, 45 and 31 degrees, two thicknesses, faces off the wall's line, in line, stems at 60, 90 and 20 degrees, a
  pair with a stem, three ends, under 30 degrees, a storey apart, a fractional corner off the axes, a start off the
  origin).

Checked: [test_compiler_free.py](../../tools/editor/tests/test_compiler_free.py) (the cases, a mitre worked by hand,
an older wall's rule kept, mitred walls' ends in the Build request) and
[shared_cases_test.mjs](../../tools/viewer/tests/shared_cases_test.mjs); the editor and node suites; `web_names`. The
Builds of the project inputs (`build_outputs.py`) are byte for byte the same as on the stage's first commit.

Known gaps: the wall generator that cuts the leaning ends is being built; until it lands, a free-form wall is drawn
and built by nothing.
