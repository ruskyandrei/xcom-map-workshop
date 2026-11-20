### The page follows the server fixes: no piece study, no intro fields, the spawn edits' new home

The page items the server, exporter and compiler fixes left for the page (review findings 63 and 64, after the merge
of 83735fc). Nothing a user can reach changes: each removed part served something the server no longer sends.

- **The piece study** ([app.js](../../tools/viewer/web/app.js), [index.html](../../tools/viewer/web/index.html),
  [style.css](../../tools/viewer/web/style.css)): the server exports whole maps only (`export --scope map`) and no
  longer opens a piece study, so `baseMatrix` is the exported matrix alone, `originalPositions`, startScene's sample
  branch and the header's hidden Original positions button (with its handler and CSS) are gone, and two messages no
  longer name a piece study.
- **The intro fields** ([play.js](../../tools/viewer/web/play.js), [gamemaps.js](../../tools/viewer/web/gamemaps.js)):
  the play status's `game.intro`, Undo everything's `intro` and a play's `introBack` are no longer sent; their lines
  are gone.
- **`STAGE_LEVELS_PLAYED`** ([project.js](../../tools/viewer/web/project.js)): its compiler twin is gone and nothing on
  the page read it; the played height's page twin is `prefab_document.js` `PREFAB_PLAYED_LEVELS`, pinned against
  `prefab_bounds.PLAYED_LEVELS` by the prefab limits both sides' tests read. `STAGE_LEVELS_MAX` (30) stays.
- **Comments** ([spawns_view.js](../../tools/viewer/web/spawns_view.js), [project.js](../../tools/viewer/web/project.js))
  name `spawn_edits.py` `SpawnEdits` for the spawn override, add, names and box, where the compiler's methods moved.
- [browser_documents.py](../../tools/viewer/tests/browser_documents.py) no longer imports `project_url`, which it never
  used.
- Kept from the merge: `missions.js` `kindKey`, `app.js`'s Prepare test of `export-missing` and the ladder chip's count.

Checked: `node --check` and the import check on the edited modules, the node suite, and the browser runs listed in
the browser checks' entry (the next commit, which also changes the smoke's header check without the button and finds
a map's previews without `scenes.json`), on a test server serving a scratch cache with export 37 of URB_Bar,
URB_PoliceStation and TempleShip.
