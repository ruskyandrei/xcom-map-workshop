### Whether a dialog or the look picker is open (modalOpen) with the dialogs' rule in modal.js

Editor refactor, stage P9, fourth part: the check the editor's shortcuts and windows ask before they act leaves
app.js for the module that keeps the dialogs. Nothing the editor does changes.

- **[modal.js](../../tools/viewer/web/modal.js)**: `modalOpen` (a dialog open, or the made pieces' look picker: the
  editor's shortcuts take no keys then, and no other window opens), moved verbatim from app.js beside `anyModal`, which
  it widens, and exported; it reads the look picker from [editor_state.js](../../tools/viewer/web/editor_state.js),
  which imports nothing, so no import cycle comes of it. The module's heading says so.
- **[app.js](../../tools/viewer/web/app.js)** imports it and gives it to the map menu, the Project menu and the keys as
  before; its import of `anyModal`, which only `modalOpen` used, went with it. 1,297 lines to 1,295; top-level
  functions 12 to 11; `let` statements 5 (7 names).
- [ARCHITECTURE.md](../../ARCHITECTURE.md): modal.js in how the page fits and a row of its own (it had none), and the
  look picker's state names modal.js's check among its readers.

Checked: [moved_code.py](../../tools/repo/moved_code.py): `modalOpen` the same as app.js's at the commit before
(`export` aside); every name it reads resolves as before (by eslint-scope: `lookPicker` the same import, `anyModal`,
which app.js imported from modal.js, modal.js's own declaration of it); `web_names` clean; the node and repo
suites; the twenty-edit recording the same as on the stage's start commit, all 52 steps; browser checks `modals`,
`let-go`, `text-select`, `pan`, `project-menu`, `header`, `looks` and `look-undo` pass, with the rest of the stage's 43
named checks.
