### browser_editing's fixed waits: the dialogs' focus and the slow mesh's request waited for

Editor refactor, stage P10. In [browser_editing.py](../../tools/viewer/tests/browser_editing.py), four of its six
fixed waits went (no assertion dropped):

- `modals`: a dialog's own focus, which comes a moment after it shows, is waited for (the focus inside the dialog;
  in Missions with no row ticked, on the first row that can be ticked), and so is the focus back on the header's Map
  button after Escape, each for up to 5 s before the assertion that says what was found (150, 150 and 50 ms before).
- `look-undo`: the test's own slow fetch counts the made-mesh requests, and the check waits for the new look's mesh to
  be asked for (the look change under way, its answer held back) before deleting the other piece, where it waited
  200 ms.

Kept, with why written beside each: `modals`' W held 250 ms (a camera move would show; none should), and a frame drawn
after `break_piece` frames a piece, before its screen points are read.

Checked on a test server: `--only modals,look-undo` five times in a row, all passing; `browser_smoke.py --all` twice.
