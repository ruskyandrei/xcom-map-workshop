### A made piece's change of look is one undo step of its own, and keeps the piece's flags and blasts

Review finding 30. `setMadeLook` deleted the old pieces, waited for the new mesh from the server with nothing holding
input, and then joined "the last two or three" undo steps by count. Anything undoable done during that wait was
joined to the look change, and the delete was left as a step of its own. A Ctrl+Z in the wait undid the delete, so the
old and new pieces both stood. If the mesh failed, the delete stayed alone and the rejection went unhandled.

- `setMadeLook` ([app.js](../../tools/viewer/web/app.js)) has the new pieces made first, with nothing changed. After
  that one wait it deletes the old pieces, places the new ones and mends their group in one go, with no wait
  between, joined as one step.
  - A piece that can't be drawn leaves everything as it was, and the hint says why.
  - So does a piece that was moved or deleted during the wait: its hint asks for the look again.
- `pasteSnapshot` takes `whole` (all or nothing) and `first` (run just before the paste is recorded, and able to
  call it off) for this.
- A look change now keeps the piece's flags, tint and blasts. Only its look changes. Before, it dropped them.
- Checked: the new browser check `look-undo` ([browser_editing.py](../../tools/viewer/tests/browser_editing.py),
  through `browser_smoke.py --only look-undo`) runs on the Bar with the server's made meshes held back a second and a
  half. It gives a made wall (with flags and a blast) the look of one of the map's own walls, and deletes another piece
  during the wait. The old wall stands until the new look is there, and the new wall keeps its flags and blast. One
  Ctrl+Z puts the old wall back and leaves the other piece deleted, and a second Ctrl+Z brings that piece back. The
  check fails on the page before this change.
