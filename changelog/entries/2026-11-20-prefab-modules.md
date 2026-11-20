### The prefab builder and prefabs saved and placed in modules of their own (builder_session.js, prefab_place.js)

Editor refactor, stage P5: the prefab builder's session and prefabs saved and placed move out of app.js, each into a
module of its own. Nothing the editor does changes.

- **[builder_session.js](../../tools/viewer/web/builder_session.js)** is new. `createBuilderSession` is made once by
  app.js, with what it needs of app.js in one argument object (as `createDocumentSession` is): the roots' makers and
  readers, the gizmo, the camera's target, the document session's banner and drafts, the scene to and from a document
  (`applyState`, `editState`), and the Save as prefab dialog and records. It holds, moved verbatim:
  - the document: `physicalBox`, `builderDocument`, `builderDocumentNow`, `builderKey`, `builderBounds`,
    `builderRecords`, `applyPrefabDocument`, `openPrefabDocument`, `builderTitle`, `saveBuilder`;
  - the size line and the ground under the prefab (`refreshBuilder`), Align to grid (`gridAlignment`, `alignToGrid`,
    `shiftWords`, `gridWarning`, the warning's two buttons), the missing pieces looked for by recipe
    (`prefabSourceNotice`, `recoverOpenedPrefabSources`, `recoverPrefabSources`);
  - the Problems check that stage P4 left: `checkPrefab`, `problemsPaint` and the chip's handler, with the check's
    state.

  Its own state is inside it: the boxes worked out, the ground and its key, the Problems check's. It gives app.js back
  the twelve that app.js and the other modules call, under the same names.
- **[prefab_place.js](../../tools/viewer/web/prefab_place.js)** is new. `createPrefabPlace` is made the same way,
  given the clipboard's, the placing's and the snapshot's functions, the readers of other maps' pieces and effects, the
  busy mark and the hints, and the builder's records and save. It holds, moved verbatim, `prefabPlacementProblem`,
  `prefabRecords`, `prefabClip`, `choosePrefab`, `placePrefab`, `drawPrefabPictures`, `savePrefab`, the Save as
  prefab dialog (`showPrefabDialog`, `prefabNameCheck`, `prefabProgress`, `hidePrefabDialog`, its form's, buttons'
  and keys' handlers) and their helpers. The dialog's state is inside it. It gives app.js back the seven others call.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns what the two share with other areas, each with
  its setter where it is given a new value: `builder` (the builder's document: the document session, the scene to and
  from a document and Build and Play read it), `eventMemo` (the edit hub's memo of one edit event, which `editState`,
  `builderDocument` and `builderKey` keep their answers in; app.js's `editChanged` makes it and drops it through
  `setEventMemo`), `families`, `pieces` and `prefabTab` (the Add panel's piece list and Prefabs tab), `clipboard` and
  `chooseToken` (`nextChooseToken()` where app.js wrote `++chooseToken` or `chooseToken++`), and the collections
  `libraryRecords`, `effectTemplates`, `foreignEffects`, `donorHashes`, `geometryCache` and `prefabPictures`.
- **[app.js](../../tools/viewer/web/app.js)** makes both modules just after the document session. They are given its
  banner and drafts and the page session's id, a constant made there, so they cannot be made where their code was;
  the handlers they set (the Save as prefab dialog's, Align to grid's, the Problems chip's) are set that much later as
  the page loads, and no other code sets a handler on those elements. The document session is made before them and
  calls five of the builder's functions, so it is given functions that call them; the builder's session is given
  `prefabRecords` and `showPrefabDialog` the same way, since its save opens the dialog and the dialog's Save saves
  the builder. Each assignment to a moved name is now its setter's call, with the same value. What stays, and why:
  - `selectActors`: a selection by actor name that the Build window's report (build_play.js) uses as well as the
    Problems list; it is given to both, and goes with the selection (`select`, stage P9);
  - `editState`, `dirty`, `unsavedDocument` and `saveState`: the hub's memo and the save state of a project and of the
    builder alike, as stage P3 left them.

  app.js: 11,702 lines to 10,948; its `let` statements 93 to 89 (157 names to 150); its top-level functions 760 to
  727. [ARCHITECTURE.md](../../ARCHITECTURE.md) names the two modules, their rows in where new code goes, the shared
  state they added to editor_state.js, and how a factory given a constant made further down is made after it. The
  comments of [prefabs.js](../../tools/viewer/web/prefabs.js), editor_state.js and
  [document_session.js](../../tools/viewer/web/document_session.js) that placed the builder or the prefab's making
  in app.js name the new modules.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 13 functions moved into
  prefab_place.js and the 20 into builder_session.js are the same (`choosePrefab` and `placePrefab` with their two
  writes by setter: without the substitutions they differ). app.js against itself, with its 9 substitutions (the
  writes of `eventMemo`, `families`, `clipboard` and `chooseToken` through their setters): its 727 functions are the
  same, and the 33 moved are only in the old file; without them 6 differ. The whole moved text, statements as well as
  functions (398 and 383 lines), is the old text line for line, the factory's indent aside, with those substitutions
  and the three declarations taken to editor_state.js; the rest of app.js differs from the old only by the imports,
  the declarations taken out, the setters' calls and the two modules made.
- `web_names` is clean (56 files), and the node suite (31 files) and the repo suite pass. No code that runs as the
  page loads, before the two are made, reaches a function they return (a scan of app.js's top-level calls).
- **Browser checks** on a test server with scratch projects and prefabs, on the commit before and on this change:
  `api-names`, `prefabs`, `prefab-effects`, `builder`, `prefab-test`, `made-prefab` and `documents` all ran and passed
  (3 min 30 s after, with other work on the computer).
- **Every writer and reader:** stage P2's recording (one scene on the Bar with every kind of piece: the project's
  records, a paste, a prefab saved, read into a clip and placed, and the builder's document and edit state opened on
  it), on a fresh server of the commit before and one of this change: equal, every record, logged argument and root.
- **`browser_smoke.py --all`** on fresh test servers, with a scratch cache and `--play-install <scratch game>`: all ten
  runs pass, 71 checks ran (Play among them) and 6 skipped in the whole run, each for its map or its run (TempleShip's
  two, the police station's light bar and Play run elsewhere; `streams`' edit and the patch previews have nothing on
  the Bar's export to work on), 12 min 52 s with other work on the computer.
