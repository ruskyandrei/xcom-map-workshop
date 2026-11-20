### The shortcuts work straight after a select, tick box or slider is used

Review finding 33. The shortcut handler ignores keys typed in a field, and most `change` handlers ended with `blur()`
for that reason, but a dozen didn't. After choosing a mission in the header, Up and Down went on switching missions
instead of moving the camera. After ticking Long War on a landing zone, Ctrl+Z and Delete did nothing until the view
was clicked. After choosing a blast size, B was dead.

- [modal.js](../../tools/viewer/web/modal.js) `releaseAfterChange`: one delegated `change` listener for the page.
  Outside a dialog, a select, tick box, radio button or slider that has the focus gives it up once its own listeners
  have run. A dialog (`.modal`, the look picker among them) keeps its focus for its Tab ring.
- [app.js](../../tools/viewer/web/app.js) puts it in once, beside `holdModals`.
- Checked: the new browser check `let-go` ([browser_editing.py](../../tools/viewer/tests/browser_editing.py), through
  `browser_smoke.py --only let-go`) runs on the police station.
  - The header's Mission select, changed by a key, gives the focus up, and the next key changes nothing.
  - A fracturing piece's blast size, chosen by key, leaves Delete and Ctrl+Z working on the piece.
  - A tick box in the Missions dialog keeps the focus.
  - On the Bar, which has one mission, the check covers the blast size and the dialog.
