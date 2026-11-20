### The document session in a module of its own (document_session.js)

Editor refactor, stage P3, first step: opening, saving and leaving a project, its drafts kept for recovery and offered
back, and the banner under the header move out of app.js into one module. Nothing the editor does changes.

- **[document_session.js](../../tools/viewer/web/document_session.js)** is new. `createDocumentSession` is made once
  by app.js, with what it needs of app.js in one argument object (as `createProjectDialog` and
  `createQueueController` are): the scene to and from a document (`applyState`, `editState`), the gizmo, the camera,
  the dialogs and panels it opens or paints, and the page session's id. It holds, moved verbatim:
  - `clearDocumentRecovery`, `dropAdopted`, `discardDraft`, `draftWords`, `recoveryProblem`, `discardAndGo`,
    `askLeave`;
  - `banner` with its timer, `navigate`, `goTo`, `openProject`, `offerProjectDraft`, `projectChanged`,
    `keepRecovery`, `keptDraft`, `saveProject`, `loadProject` and `ensureSavedFor`.

  Its own state is inside it: `navigating` and the banner's timer. It gives app.js back the twelve that app.js
  calls (`banner`, `goTo`, `saveProject`, `projectChanged` and the others), under the same names, so app.js's calls
  are as they were.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns the state the session shares with other areas,
  each with its setter: `leaving`, `saving`, `recoveryTimer`, `recoveryKept`, `adoptedDraft` and `recoveryTrouble`
  (the prefab builder's saves use them too); `askedPick` (the mission picker); `lastBuild` and `buildTimer` (the
  Build window; `setLastBuildValue`, since app.js has a `setLastBuild` of its own); `copySerial`, with
  `nextCopySerial()` for the five places that took the next serial with `++`; and `looksReady` and `landingRead`,
  the reads a project waits for.
- **[app.js](../../tools/viewer/web/app.js)** makes the session after the functions it is given, and before the
  dialogs that are handed `loadProject` and `ensureSavedFor` as it loads. `openingProgress` is made further down, so
  the session is given a function that calls it. Each assignment to a moved name is now its setter's call, with the
  same value. app.js: 12,767 lines to 12,407; its `let` statements 105 to 100 (184 names to 170); its top-level
  functions 811 to 793.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) on the 18 moved functions against the commit
  before. The factory's body was written to a scratch file first, since the tool reads a file's top-level functions.
  With the 14 substitutions of a write by its setter's call, all 18 are the same. Without them, the 10 that write
  shared state differ. app.js against itself, with its own 19 substitutions: its 793 functions are the same, and the
  18 moved are only in the old file. The top-level statements that changed (the `let`s taken out, `looksReady`'s
  first read, the session made) were read in the diff.
- `web_names` is clean (52 files), and the node suite passes (31 files).
- **Browser checks** on a test server, before (on the commit before) and after: `api-names`, `project-menu`,
  `projects`, `prepare`, `modals`, `draw-errors`, `failed-reads` and `documents` all pass (2 min 30 s and
  2 min 36 s, with other work on the computer).
- **The saved file:** a project holding every kind of record (stage P2's scene on the Bar: copies, made pieces, a
  broken copy, cover blocks, lights, an effect, a sound and a lens flare) saved, reopened and saved again, on a server
  of the commit before and one of this change. Both revisions' files are the same byte for byte, the server's
  `savedAt` and `created` aside.

Left: the scene to and from a document (`editStateNow`, `applyState`) is the next step.
