### An undo or a redo takes the delete's hint away

After a delete, the hint "Deleted 402 pieces · Ctrl+Z brings them back" stayed up for its two and a half seconds even
when Ctrl+Z had brought the pieces back meanwhile. Now an undo or a redo (Ctrl+Z, Ctrl+Y, the header's buttons), once
its step is done, puts the resting hint back in place of the notice: none, or how to place the piece being placed, or
box select's line ([delete_reset.js](../../tools/viewer/web/delete_reset.js) `undoStep`, given the hints' `restingHint`
by [app.js](../../tools/viewer/web/app.js)). For a large step under the busy mark, that is after the step has run.

What the exploratory test also saw, looked at on a test server: `viewer.changes()` reading 0 moved pieces for a moment
right after the first Ctrl+Z of a large delete is the large step's wait under the busy mark, not a stale count. The
undo of a step of 60 pieces or more runs one frame after its mark is drawn; until then the count is the one before
the undo, in which the moved pieces deleted count as deleted only (432 deleted read once, then the right count from
the next sample on). No change made for it. The second Ctrl+Z once lost in that wait is the busy mark holding the
view's keys while a mark put up at once shows (so that a second step does not queue behind the first); it was not
reproduced, and nothing is changed for it.

Checked: the `small-defects` browser check ([browser_editing.py](../../tools/viewer/tests/browser_editing.py)) deletes
402 pieces (432 with their linked pieces), then one, and after each Ctrl+Z, Ctrl+Y and Ctrl+Z the hint is gone. It
failed before the change (the hint still read "Deleted 432 pieces · Ctrl+Z brings them back" after the undo).
`--only small-defects` passes.
