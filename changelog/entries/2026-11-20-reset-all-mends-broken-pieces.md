### Reset all mends the map's broken pieces

Review finding 28. Reset all left the map's own fracturing pieces broken. When breakage was the only change, the
button showed but did nothing, and the status still said the pieces were broken. With other changes, those were
undone and the pieces stayed broken, so the project still differed from the map.

- `resetAll` in [app.js](../../tools/viewer/web/app.js) now takes in the map's pieces that carry blasts. Its step
  mends them (blasts and Breaks further in battle off, drawn whole), and its undo breaks them again as they were. It is
  still one undo step, and breakage counts for the test that decides whether there is anything to reset.
- Checked: the new browser check `reset-all` ([browser_editing.py](../../tools/viewer/tests/browser_editing.py),
  through `browser_smoke.py --only reset-all`) runs on the Bar. It breaks one of the map's fracturing pieces as a user
  does (picked, B, a click on it), clicks Reset all and checks there is nothing left to save. It presses Ctrl+Z and
  checks the same blasts are back. It then deletes another piece and checks Reset all puts both back.
