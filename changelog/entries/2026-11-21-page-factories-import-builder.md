### The document's factories and Build and Play import editor_state.js' builder instead of being given it

Editor follow-ups, stage P4, item 3.8 (the last of four argument-list commits, one a home module). Nothing the editor
does changes.

- `createDocumentSession` ([document_session.js](../../tools/viewer/web/document_session.js)), `createDocumentState`
  ([document_state.js](../../tools/viewer/web/document_state.js)) and `createBuildPlay`
  ([build_play.js](../../tools/viewer/web/build_play.js)) took the prefab builder's document state, `builder`, in their
  argument object, though it is [editor_state.js](../../tools/viewer/web/editor_state.js)' shared state, which the
  page's state rule reads through the import. Each imports it now and [app.js](../../tools/viewer/web/app.js) gives it
  no more (nor imports it). `builder` is one object changed in place, never given a new value, so what was given and
  what is imported are the same object.
- build_play.js' heading says the builder's state is editor_state.js'.
- [ARCHITECTURE.md](../../ARCHITECTURE.md) ("The page", Factories) says a module imports what it can import (a pure
  module's export, a constant, shared state) and is not given it, and that some plain exports are still given (22
  names in 77 places of app.js's argument objects: `scene_pieces.js`' `actorPose`, `groups.js`' `memberOf`,
  `map_grid.js`' `gridOrigin` and others), which a change to such a factory imports.

Checked: `web_names` clean; ESLint's `no-shadow` (by hand) finds `builder` hidden nowhere; each factory's parameters
against the keys app.js gives it (61 factories, no difference); the node suite; the twenty-edit recording the same as
on the stage's start commit (52 steps).
