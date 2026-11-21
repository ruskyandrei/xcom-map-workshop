### ARCHITECTURE.md says what app.js now holds

Editor refactor, stage P9, fourth part, its end: with the last rules out of it, app.js holds the imports, the making
of the modules, `open` and `startScene`, and the event wiring. [ARCHITECTURE.md](../../ARCHITECTURE.md) now says so:

- how the page fits: what app.js holds (the renderer, the camera and the world's layers, the gizmo, each module's
  factory made in the order the page sets things up, the dialogs made with their elements and the build queue's
  controller with its calls to the server, `open`, `startScene`, the event wiring) and the few helpers it keeps that
  join the page's own objects to the modules (`touchShadows`, `editChanged`, `sceneChanged`, `grabView`, `readLooks`),
  each with why it is there;
- the page's state rule: app.js declares only the state its own wiring reads (the sun's shadows' timer, the draw loop's
  clocks, the pointer handlers' press, the Map lighting mode's `applyLighting`), no longer "the state of the areas not
  yet moved out of it";
- the sizes: app.js is no longer among the largest files the refactor is taking apart.

No code changes. Checked: the `repo` suite (the structure test, the documents' rules).
