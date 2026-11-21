### The edits on screen counted by kind with the document's state (document_state.js)

Editor refactor, stage P9, third part: `changes` (the unsaved changes by kind: moved, added, deleted, lights, effects,
the grid, the landing zones, buildings, mission objects, spawn points, flags, broken pieces, and their total) leaves
app.js. Nothing the editor does changes.

- **[document_state.js](../../tools/viewer/web/document_state.js)**: `changes`, moved verbatim from app.js into
  `createDocumentState`, beside the edits on screen read as a project records them. The factory gives it back (the edit
  status, the document session's `unsavedDocument` and the test hooks are given it as before), and is given
  `isStream`, the Lights view's `lightEdited`, and the Effects view's `effectEdited` (made further down) as a function
  that calls it.
- **[app.js](../../tools/viewer/web/app.js)**: five imports of editor_state.js only `changes` read went with it.
  1,367 lines to 1,344; top-level functions 21 to 20.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the function the same as app.js's at the commit before,
app.js's other 20 the same; every name it reads resolves as before (by eslint-scope); `web_names` clean; the
twenty-edit recording (which traces `changes`) the same as on the stage's start commit, all 52 steps.
