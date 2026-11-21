### The look picker check's fixed waits: the find box's cards read at once

Editor refactor, stage P10. In [browser_looks.py](../../tools/viewer/tests/browser_looks.py), the 200 ms after a word
typed into the look picker's find box and after it was cleared went: the picker lays its cards again in the box's
input listener (look_picker.js `render`), which Playwright's `fill` runs, so the cards are read at once. Kept, with why
written beside it: the 300 ms after the camera is put over a spot (a frame drawn from there before `screenOf`).

Checked on a test server: `--only looks` on the police station five times in a row, all passing; `browser_smoke.py
--all` twice (its `police` run).
