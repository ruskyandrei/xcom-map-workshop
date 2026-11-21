### Copy, paste and placing, and the templates of other maps' pieces, in modules of their own (clipboard.js, library_templates.js)

Editor refactor, stage P8, fourth part: the clipboard, paste and placing, and the library's templates leave app.js, in
two modules, since reading a piece or an effect of another map as a template is asked for by much more than placing
(a project or a prefab opened, the Effects view, the prefab builder) and shares no state with it. Nothing the editor
does changes.

- **[library_templates.js](../../tools/viewer/web/library_templates.js)** is new. `createLibraryTemplates` is made
  once by app.js, with a piece's root built and its bounds, the Lights view's and the Effects view's sources, the cover
  blocks' collision meshes, the assemblies of other maps and the helpers. It holds, moved verbatim, the run of app.js
  that was the pieces of other maps: an asset's url (`assetUrl`), whether a target is another map's
  (`isForeignTarget`), a record's id (`recordId`), many records read in a few requests (`readLibraryRecords`,
  `readEffectRecords`), a piece's and an effect's template (`libraryTemplate`, `effectTemplate`), the templates a
  project's records name (`loadForeignTemplates`), and what such a piece costs and says (`foreignCount`, `kilobytes`,
  `foreignCost`, `foreignNote`, `bakeNote`). Its own state is the records and effects read ahead; it gives back the 11
  functions the clipboard, the scene and its textures, the document's state, the prefab builder, prefabs saved and
  placed, Build's panel, the selection, the Effects view and the made pieces call.
- **[clipboard.js](../../tools/viewer/web/clipboard.js)** is new. `createClipboard` is made once by app.js, with the
  gizmo, the scene, the pieces' roots made and taken out, the Lights, Effects, Spawns, Landing zones and Buildings
  views' adding and placing, the cover blocks' ground, the templates of other maps' pieces, the floor boxes' outline,
  the busy mark and the hints. It holds, moved verbatim, the four runs of app.js that were these: a clip of the
  selection (`snapshot`) and a floor box's matrix in it (`boxMatrix`, `matrixBox`); a clip pasted (`pasteSnapshot`,
  `linkOf`, `groupTree`, `mapChain`), Copy and Cut (`copySelection`) and Paste (`paste`); placing (`startPlacing`,
  `stopPlacing`, `moveGhost`, `placeAt`, `dropTarget`, `moveTo`, `keepRecipe`, `placeMove`, the preview's two
  materials); the Add panel shown and its tab (`showPieces`, `setLibraryScope`) and an entry of it chosen and placed
  (`chooseEntry`, `entryParts`, `chooseLibraryEntry`, `chooseLibraryEffect`); and a copy dragged off with Shift
  (`copyDragBegin`, `copyDragEnd`). Its own state is the preview's materials; it gives back the 25 functions and
  constants the gizmo, the keys, the pointer handlers, the draw loop, the event wiring, the test hooks and the other
  areas call.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns, each with its setter, what of these other areas
  read or set: the preview's redraw asked (`ghostDirty`, `setGhostDirty`: the pointer handlers, keys and Level snap set
  it, the draw loop reads it), the Add panel's tab (`libraryScope`, `setLibraryScopeValue`, beside the clipboard's
  `setLibraryScope`, which also shows the tab: app.js gives it the remembered tab as the page loads), Level snap
  (`levelSnap`, `setLevelSnapValue`, beside app.js's `setLevelSnap`; its value from the browser's storage is given by
  the setter's call where the `let` was, so it is read at the same point), and the url the open map's export is served
  under (`cachePrefix`, `setCachePrefix`: app.js's opening sets it). The components of other maps' pieces read as
  templates (`foreignTemplates`), which app.js's recipes, templates and listings read, are there as a collection.
  The comments of what is placed and of the records of other maps read name the modules.
- **[app.js](../../tools/viewer/web/app.js)** makes the templates' module where its run was, given the Lights view's
  and the Effects view's sources and the cover blocks' collision meshes (made further down) as functions that call
  them; the modules made after it (the document's state, the prefab builder, prefabs saved and placed, Build and Play,
  the Effects view) get its functions directly. The clipboard reads values that are not functions and that factories
  made further down return: the cover blocks' floor clearance (`FLOOR_CLEARANCE`) and the Buildings view's layer of the
  map's own buildings (`ownVolumeLayer`). So its module is made after the cover blocks', before the made pieces', and
  given the drawing's `stopWallDrawing` as a function that calls it; the modules made before it that read its
  functions as the page loads are given functions that call them (the prefab builder `snapshot`; prefabs saved and
  placed `snapshot`, `boxMatrix`, `matrixBox`, `groupTree`, `linkOf`, `mapChain`, `startPlacing`, `stopPlacing`; the
  Buildings view `copySelection`; Align `keepRecipe`). The floor boxes' outline geometry and material that a clip's
  preview draws (`ghostEdges`, `ghostLine`) stay in app.js where they were made, with a comment saying why: prefabs
  saved and placed, made before the clipboard, draw them too, and both are given them. What the clipboard's runs made
  as the page loaded now happens later: the preview's two materials, see-through, which three.js sorts by render
  order and depth (it consults the order materials were made only for opaque objects; the preview's meshes are made
  when placing starts, as before), a unit box and the tabs' table. No other code sets a handler between. Each
  assignment to a moved name is its setter's call, with the same value (13 writes). app.js: 4,853 lines to 4,271; its `let` statements 34 to
  31 (48 names to 44); its top-level functions 262 to 224. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the two
  modules, their rows in where new code goes, the state added to editor_state.js, and the object two modules share.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 13 functions moved into
  library_templates.js are the same, and the 25 moved into clipboard.js are the same with the 6 substitutions of a write
  by its setter's call (without them, `moveGhost`, `setLibraryScope` and `startPlacing` differ). app.js against
  itself, with them: its 224 functions are the same, and the 38 moved are only in the old file (without them,
  `setLevelSnap`, `setSnapMode` and `open` differ). The whole moved text of each module (160 and 461 lines) is the old
  text line for line, the factory's indent aside, with those substitutions and the statements whose names went to
  editor_state.js (now comments naming them). No code that runs as the page loads, before any of the page's factories
  is made, reaches what they return.
- `web_names` is clean (73 files, in two halves), and the node suite passes (31 files).
- **Browser checks** on a test server: the same 26 as for the cover blocks (on the Bar `typed-pose`, `adding`,
  `copy-drag`, `library`, `floor-placing`, `recipe`, `paste-buildings`, `prefabs`, `prefab-effects` and `made-prefab`
  among them); then `api-names`, `library-all`, `library-effects`, `library-flares` and `library-assembly` (pieces,
  effects, lens flares and assemblies of All maps read and placed), `lights`, `effects` and `flares`; then `builder`,
  `prefab-test` and `documents`. All passed, none skipped.
