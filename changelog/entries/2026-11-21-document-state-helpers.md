### One edit event's state, the scene cleared before a state and the project's notes with the document's state (document_state.js)

Editor refactor, stage P9, third part: three of the project helpers app.js kept go to the scene to and from a
document. Nothing the editor does changes.

- **[document_state.js](../../tools/viewer/web/document_state.js)**: `editState` (the edits on screen as a project
  records them, kept for one edit event in the edit hub's memo), `clearEdits` (back to the map as exported, with no
  history, before a state is applied: `applyState` alone calls it) and `projectNote` (a note in the import notes, with
  their count), moved verbatim from app.js into `createDocumentState`, before its returns. The factory gives back
  `editState` and `projectNote` (the document session, the prefab builder's session and the test hooks are given them as
  before), and is given what `clearEdits` and `projectNote` read: `$`, `text`, `removeRoots`, `baseMatrix`, the Lights
  view's `clearLightEdits`, and the Effects view's `clearEffectEdits` (made further down) as a function that calls it.
- **[app.js](../../tools/viewer/web/app.js)**: seven setters of editor_state.js only `clearEdits` used went with it.
  1,503 lines to 1,476; top-level functions 43 to 40.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the document's state in how the page fits.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the three functions the same as app.js's at the commit before,
app.js's other 40 and document_state.js's other functions the same (`createDocumentState` differs by its arguments,
its returns and what moved into it); every name the moved code reads resolves as before (by eslint-scope;
`editStateNow`, which app.js took from the factory, is now the factory's own); `web_names` clean; the twenty-edit
recording the same as on the stage's start commit, all 52 steps; browser checks `api-names`, `project-menu`,
`builder`, `clear-map`, `modals`, `draw-errors`, `failed-reads`, `reset-all` and `made-prefab` pass.
