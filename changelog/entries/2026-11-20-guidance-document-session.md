### The guidance names the document session's modules and how a module is made from app.js's functions

Editor refactor, stage P3, its last step: [ARCHITECTURE.md](../../ARCHITECTURE.md) says what the stage made true.

- Section 1, the page: the open document's life (a project opened, saved and left, its drafts, the banner) is
  [document_session.js](../../tools/viewer/web/document_session.js)'s, and the scene to and from a document's state is
  [document_state.js](../../tools/viewer/web/document_state.js)'s, which a project's file, its drafts and the prefab
  builder's document all go through.
- Section 2 gets two rows: opening, saving or leaving a document, its drafts and the banner; and a new part of what a
  project keeps of the scene (`editStateNow` writes it, `applyState` puts it back, the session carries it between the
  file and those two). The row for an area of the page names `createDocumentSession` beside the two models.
- Section 3, "The page":
  - what [editor_state.js](../../tools/viewer/web/editor_state.js) now holds, by what shares it, and that state one
    area alone uses lives inside its factory when it is made by one;
  - a counter taken one step at a time has a `next<Name>()` beside its setter (`nextCopySerial()`);
  - how a module made from many of app.js's functions is made: it destructures its argument object, so moved code
    calls them by the same names; app.js destructures what it returns under the same names; app.js makes it after
    what it is given and before the code that uses it as the page loads; a function made further down is given as a
    function that calls it; and a move into a factory is checked on the factory's body written to a file of its own,
    since `moved_code.py` reads top-level functions.
- Comments that placed the moved code in app.js now name its module: the project open in editor_state.js, the Save
  and Load dialogs' caller in [project_files.js](../../tools/viewer/web/project_files.js).

Checked: the repo suite; `web_names` is clean (53 files). The stage's end check, `browser_smoke.py --all` on fresh
test servers with a scratch cache, on the page as this commit has it: its nine runs pass in 9 minutes 48 seconds,
with 70 checks run, as at the stages before. The Play run was left out, since no scratch game folder was given.
