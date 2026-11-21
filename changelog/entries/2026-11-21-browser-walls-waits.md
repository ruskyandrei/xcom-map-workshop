### The walls check's fixed waits: the Add panel's filter read at once

Editor refactor, stage P10. In [browser_walls.py](../../tools/viewer/tests/browser_walls.py), the 200 ms after each
filter typed into the Add panel went: the panel draws its list again in the box's input listener (pieces.js `render`),
which Playwright's `fill` runs, so the list is read at once. Kept, with why written beside them: the two 300 ms after
the camera is put over a spot (a frame drawn from there before `screenOf`, which reads the camera's matrices a render
updates, gives the points to drag between).

Checked on a test server: `--only walls` on the police station five times in a row, all passing; `browser_smoke.py
--all` twice (its `police` run).
