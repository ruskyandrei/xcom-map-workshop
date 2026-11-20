### The scene to and from a document in a module of its own (document_state.js)

Editor refactor, stage P3, second step: the two functions that turn the scene into a document's state and a state back
into the scene move out of app.js. Nothing the editor does changes.

- **[document_state.js](../../tools/viewer/web/document_state.js)** is new. `createDocumentState` is made once by
  app.js, with what it needs of app.js in one argument object: the roots' makers and readers, the lights', effects'
  and spawn points' records, and the groups', buildings' and map grid's own parts. It holds, moved verbatim:
  - `editStateNow`: the edits on screen as a project records them, sorted (app.js's `editState` keeps its answer for
    one edit event, as before);
  - `applyState`: a project's state put on the map as exported, with the records naming what the export lacks given
    back to be kept. Its note of a map the install lacks, said once (`foreignNoted`), is inside the module.

  A project's file, its drafts and the prefab builder's document all go through these two.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns, each with its setter, the four more names they
  share with other areas: `library` (the Add panel's All maps), `areaBindings` (the Lights view's glowing pieces),
  `loadErrorCount` and `mergedBuildings` (what `allBuildings` worked out).
- **[app.js](../../tools/viewer/web/app.js)** makes it just before the document session, which is handed its
  `applyState`. Four functions it is given are made further down, with the Spawns view, so it is given functions
  that call them. Each assignment to a moved name is now its setter's call, with the same value. app.js: 12,407 lines
  to 12,231; its `let` statements 100 to 98 (170 names to 166); its top-level functions 793 to 791.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py), with the factory's body written to a scratch file.
  Against the commit before, with the 2 substitutions of a write by its setter's call, `editStateNow` and
  `applyState` are the same (without them `applyState` differs). app.js against the commit before, with its 6
  substitutions: its 791 functions are the same. Against the stage's start, with the substitutions of both steps:
  the 20 functions moved by the stage are the same, and so are app.js's 791 left.
- `web_names` is clean (53 files), the node suite passes (31 files), and so does the repo suite.
- **Browser checks** on a test server: `api-names`, `project-menu`, `projects`, `prefabs`, `prepare`, `modals`,
  `draw-errors`, `failed-reads` and `documents` all pass (2 min 48 s, with other work on the computer).
- **The saved file:** stage P2's project holding every kind of record, saved, reopened and saved again on a server of
  this change. Both revisions' files are the same byte for byte as the stage's start's, the server's `savedAt` and
  `created` aside.
- **Every writer and reader:** stage P2's recording (one scene on the Bar with every kind of piece) on a server of the
  stage's start and one of this change. The project's records, the paste, the prefab and its placing, the builder's
  document and edit state, the arguments of `addedObject`, `addedLight` and `addedEffect` and every root are equal.
