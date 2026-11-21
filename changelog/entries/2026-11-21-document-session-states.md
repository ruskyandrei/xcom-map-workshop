### Whether the document has changes not saved, and whether projects can be had, with the document session (document_session.js)

Editor refactor, stage P9, third part: four of the project helpers app.js kept go to the document session. Nothing
the editor does changes.

- **[document_session.js](../../tools/viewer/web/document_session.js)**: `projectsAvailable` (projects edit a full
  map's original layout: not in the prefab builder, not on a patch preview), which reads only the shared state, at its
  top before the factory, exported; and `dirty`, `unsavedDocument` (a trial's edits count too) and `saveState` (not
  saved, unsaved or saved), moved verbatim from app.js into `createDocumentSession`, before its returns. The factory
  gives back the three, which the prefab builder's session, Build and Play, the Project menu, the edit status, the
  page's leaving and the test hooks are given as before, and reads `projectsAvailable` at its top instead of being given
  it. It is given what they read: app.js's `changes`, and the Buildings view's `savedBuildings` and the prefab
  builder's `builderKey` (made after it) as functions that call them.
- **[app.js](../../tools/viewer/web/app.js)** imports `projectsAvailable`; Prepare, made before the session, is given it
  as itself instead of a function that calls it. The imports only the moved code used went with it (`stateKey`,
  `projectMissions`, `projectSpawnRules`). 1,476 lines to 1,471; top-level functions 40 to 36.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the document session in how the page fits and its row.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the four functions the same as app.js's at the commit before
(`export` aside), app.js's other 36 and the session's other functions the same (`createDocumentSession` differs by its
arguments, its returns and what moved into it); every name the moved code reads resolves as before (by eslint-scope);
`web_names` clean; the twenty-edit recording the same as on the stage's start commit, all 52 steps; browser checks
`api-names`, `project-menu`, `builder`, `header`, `modals`, `draw-errors`, `failed-reads`, `small-defects` and
`made-prefab` pass (`header` straight after `project-menu` times out on `#selected`, the order dependence stage P9b
found; it passes on its own).
