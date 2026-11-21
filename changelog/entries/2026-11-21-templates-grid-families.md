### A piece's template and recipe with the scene's pieces, the grid's corners with the map grid, the map's families in map_families.js

Editor refactor, stage P9, third part: more of the helpers app.js still declared go to their owners. Nothing the
editor does changes.

- **[scene_pieces.js](../../tools/viewer/web/scene_pieces.js)**: `recipeOf` (the exported pose of the original whose
  pose rule a piece keeps under tile snap) and `templateFor` (the template a record's piece is copied from: the map's
  own original, else another map's piece read), moved verbatim into `createScenePieces` with the originals they keep
  by key (`originalIndex`, `templates`, each made at its first use as before). The factory gives them back, and is given
  `isStream`, and `isMade` and `sourceKey` (made further down) as functions that call them.
- **[map_grid.js](../../tools/viewer/web/map_grid.js)**: `gridOrigin` and `tileCorner` (the corner the game counts its
  tiles from), which read only the scene, at its top before the factory, exported.
- **[map_families.js](../../tools/viewer/web/map_families.js)** is new: `createMapFamilies` holds the map's families
  and assemblies, moved verbatim: `assemblyIndex`, `foreignAssemblies`, `assemblyOf` and `useMapFamilies` (which
  regroups the gizmo once the assemblies are known). app.js makes it where `useMapFamilies` was, after the gizmo, which
  it is given; its tables (a `Map` each), made before the gizmo until now, are made there, later: nothing reads them as
  the page loads (the gizmo's `assemblyOf` option calls it only on a selection), and the templates of other maps'
  pieces and the clipboard, made after, are given them as before. app.js's `let assemblyIndex = new Map(),
  originalIndex = null;` is split between the two modules.
- **[app.js](../../tools/viewer/web/app.js)**: the imports only the moved code used went with it (`pieceGrid`,
  `useFamilies`, `foreignTemplates`, `setFamilies`, `setLandingActors`). 1,696 lines to 1,650; top-level functions 62 to
  56; `let` statements 7 (10 names) to 5 (7 names).
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the scene's pieces', the map grid's and the map's families' parts in how the
  page fits, and their rows (map_families.js's new).

Checked: [moved_code.py](../../tools/repo/moved_code.py): the six functions the same as app.js's at the commit before
(`export` aside), app.js's other 56 and the modules' other functions the same (`createScenePieces` differs by its
arguments and what moved into it); every name the moved code reads resolves as before (by eslint-scope); `web_names`
clean; the twenty-edit recording the same as on the stage's start commit, all 52 steps; browser checks `api-names`,
`typed-pose`, `recipe`, `destruction`, `copy-drag`, `adding`, `library`, `clear-map`, `spawns`, `floor-placing`,
`builder`, `paste-buildings`, `ladder-floor`, `walls`, `made-prefab`, `looks` and `groups` pass (`clear-map` run after
`copy-drag` with nothing between times out on `#gridDone`, the order dependence stage P9b found; it passes on its own
and in the stage's full list).
