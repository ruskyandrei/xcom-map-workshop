### The scene's pieces in a module of their own (scene_pieces.js)

Editor refactor, stage P8, second part: what the view draws of a piece and how it is found again (picking, textures,
materials, the loads of meshes and materials, a piece's root, an original's parts and boxes) leaves app.js for one
module. Nothing the editor does changes.

- **[scene_pieces.js](../../tools/viewer/web/scene_pieces.js)** is new. `createScenePieces` is made once by app.js,
  with what it needs of app.js in one argument object: the renderer, the camera and the scene's content, the
  pickables, the texture and mesh loaders and the textures' loads, the grid's origin, a piece's original, an asset's
  url, a broken piece drawn, the selection and the hints. It
  holds, moved verbatim, picking (`rayAt`, `pick`), textures and materials (`texture`, `plainMaterial`,
  `PLAIN_MATERIAL`, `material`, `materialCache`, `materialKey`), the loads (`track`, `loaded`) and the box round some
  pieces' meshes (`boundsOf`), a piece's root built, added and taken away (`buildRoot`, `addRoots`, `removeRoots`),
  its unedited matrix (`baseMatrix`) and every root put where its edit has it (`placeObjects`), an original's parts
  (`partsOf`, `originalOf`) and boxes (`vertexBox`, `movedBox`) and a piece's box (`boxOf`). Its own state is inside
  it (the loads settled, the originals' parts and vertex boxes). It gives back the 20 functions and tables the rest of
  the page calls, under the same names.
- **[app.js](../../tools/viewer/web/app.js)** makes it before the gizmo, the first code that is given its functions
  (`baseMatrix`). Its run made nothing the page shows or listens with as it loaded (functions, a few tables and
  vectors, a word), so making it earlier changes nothing, and it calls through only two functions made further down
  (`assetUrl`, `drawBroken`), where at its run's end eleven functions of it would have had to be called through by
  the six factories and the gizmo made before. Three parts of the run stay in app.js: framing (`frame`, with its
  near plane: the camera's, stage P9), the drawn-only preview of pieces (`previewGroup`: it reads the clipboard's ghost
  material, made further down and not a function) and the rows of buttons used like a select (`segmented`,
  `segButton`: View options' helpers, which app.js's event wiring sets up as the page loads). app.js: 3,525 lines to 3,298; its `let`
  statements 19 to 18 (29 names to 28); its top-level functions 159 to 140. A comment of editor_state.js that placed
  `track` and `loaded` in app.js names the module. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module, its row,
  and the rule that an area whose code makes nothing as the page loads is made where the fewest functions must be
  called through.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 19 moved functions are
  the same, with no substitution. app.js against itself: its 140 functions are the same, and the 19 moved are only in
  the old file. The whole moved text (240 lines) is the old text line for line, the factory's indent aside; the four
  lines a template string of the plain material's shader continues on are kept as they were, not indented, so the
  string is the same byte for byte. No code that runs as the page loads, before any of the page's factories is made,
  reaches what it returns.
- `web_names` is clean (76 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on this change (every piece is built, added and found by these functions,
  so a broad set): on the Bar `api-names` (240 names on each of its three pages), `skins` (skinned meshes posed, a
  door and a prop pictured), `typed-pose`, `recipe`, `destruction`, `adding`, `groups`, `copy-drag`, `box-select`,
  `floor-boxes`, `map-buildings`, `clear-map`, `align`, `library`, `cover`, `floor-placing`, `floor-tiles`, `lights`,
  `effects`, `prefabs`, `floors-cut`, `frame-bounds`, `tile-grid` and `tile-footprints`; the editing run (`reset-all`,
  `draw-errors` with a piece the browser can't draw, `made-prefab`, `modals`, `look-undo`, `failed-reads`, `let-go`,
  `paste-buildings`, `squad-read`, `ladder-floor`, `small-defects`); on the police station `walls`, `looks` and
  `light-bar`; on TempleShip `temple-interior` and `temple-look` (its alien materials); and `builder` and
  `prefab-test`. All passed, none skipped. (Those not run on the stage's
  start commit passed in stage P8 first part's `--all` at 606fef8, whose page it is.)
