### What some roots are, in words, with the selection (selection.js)

Editor refactor, stage P9, third part: `selectionWords` ("12 pieces, 2 lights and 1 building") leaves app.js. Nothing
the editor does changes.

- **[selection.js](../../tools/viewer/web/selection.js)**: `selectionWords`, moved verbatim from app.js to the module's
  top, before `createSelection`, and exported: it reads only its arguments (and `plural`, which selection.js now
  imports from dom_words.js). `createSelection` reads it there and is no longer given it; app.js imports it for the
  Buildings view, the clipboard and Delete and Reset, as before.
- **[app.js](../../tools/viewer/web/app.js)**: 1,514 lines to 1,503; top-level functions 44 to 43.
  [ARCHITECTURE.md](../../ARCHITECTURE.md): the selection's row.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the function the same as app.js's at the commit before
(`export` aside), app.js's other 43 the same; every name it reads resolves as before (by eslint-scope); `web_names`
clean; the twenty-edit recording the same as on the stage's start commit, all 52 steps; browser checks `api-names`,
`typed-pose`, `groups`, `copy-drag`, `box-select`, `floor-boxes`, `align`, `lights`, `reset-all`, `small-defects` and
`paste-buildings` pass.
