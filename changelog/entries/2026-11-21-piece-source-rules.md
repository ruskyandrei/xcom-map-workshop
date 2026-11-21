### A piece's original and key (isStream, fromOf, sourceKey) with the piece records

Editor refactor, stage P9, fourth part: the rules of a piece as the page holds it and the original it stands for leave
app.js for the module that converts a piece to its record. Nothing the editor does changes.

- **[piece_records.js](../../tools/viewer/web/piece_records.js)**: `isStream` (a piece of a package a mission streams
  into the map, shown and never edited), `fromOf` (the original a piece is, or was copied from: package, level and
  actor) and `sourceKey` (a map's own piece's key in a project, an override's target), moved verbatim from app.js to
  its top as plain exports; `sourceKey` takes `targetKey` from [project.js](../../tools/viewer/web/project.js), as it
  did in app.js. The module's heading says so.
- **[app.js](../../tools/viewer/web/app.js)** imports the three and gives them to the factories as before. The scene's
  pieces and the Flags panel, given `sourceKey` as a function that calls it while it was made further down, are given
  it itself, now that it is an import. Its import of `targetKey` went with `sourceKey`. 1,313 lines to 1,311;
  top-level functions 20 to 17; `let` statements 5 (7 names).
- **[piece_records_test.mjs](../../tools/viewer/tests/piece_records_test.mjs)**: a map's own piece, a copy and a
  streamed piece through the three.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the piece records' part in how the page fits, a row for the rules, and the
  rule of what stays in app.js no longer cites them.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the three the same as app.js's at the commit before
(`export` aside); every name they read resolves as before (by eslint-scope); `web_names` clean; the node and repo
suites; the twenty-edit recording the same as on the stage's start commit, all 52 steps; the stage's 43 named browser
checks pass on the Bar and the police station (`streams` skips a part on the Bar as before: no streamed piece is drawn).
