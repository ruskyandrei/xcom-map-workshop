### The name a map's own actors begin with (PL) in constants.js

Editor refactor, stage P9, fourth part: the last constant app.js declared for other areas goes to the page's one home
of the game's fixed numbers and names. Nothing the editor does changes.

- **[constants.js](../../tools/viewer/web/constants.js)**: `PL` (`TheWorld.PersistentLevel.`, the name each of a map's
  own actors begins with, as the new actors the editor makes for the map are named: a cover block, a recipe light),
  moved verbatim from app.js and exported; its heading says so.
- **[app.js](../../tools/viewer/web/app.js)** imports it and gives it to the Lights view, prefabs saved and placed and
  the cover blocks as before. 1,295 lines to 1,294; top-level functions 11; `let` statements 5 (7 names).
- [ARCHITECTURE.md](../../ARCHITECTURE.md): constants.js's row names it.

Checked: the moved line the same text (`export` aside); `web_names` clean; the node suite (`twin_constants_test.mjs`
and `walls_test.mjs` import constants.js) and the repo suite; the twenty-edit recording the same as on the stage's
start commit, all 52 steps; browser checks `api-names`, `typed-pose`, `adding`, `lights`, `cover`, `library` and
`made-prefab` pass.
