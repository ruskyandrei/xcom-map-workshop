### An added piece and an actor's pose with the scene's pieces; a made piece's request in made_requests.js

Editor refactor, stage P9, third part: the scene's pieces' helpers app.js still declared go to their owners. Nothing
the editor does changes.

- **[scene_pieces.js](../../tools/viewer/web/scene_pieces.js)**: `actorPose` (an actor's pose at a render matrix) and
  `movedMatrix` (the matrix of a pose), which read only their arguments, at its top before the factory, exported; and
  in `createScenePieces`, after the piece's box, an added piece made from its template: `newId` with the comment on
  adding pieces, `madeShape` and `madeShapeOf` (a made piece's mesh and materials from its numbers, a plain one's on
  the plain material), `unscaled` and `addedObject`. Each moved verbatim from app.js. The factory gives back
  `addedObject`, `madeShape` and `unscaled`, and is given `coverVersion` (a cover piece's template version, made with
  the cover blocks further down) as a function that calls it; app.js no longer takes `PLAIN_MATERIAL` from it.
- **[made_requests.js](../../tools/viewer/web/made_requests.js)** is new and pure: a made piece's request
  (`PLAIN_VERSION`, `isPlain`, `madeRequest`) and the look a plain piece is made in (`plainLook`), moved verbatim from
  app.js, `isPlain`, `madeRequest` and `plainLook` exported. It takes the looks' and shapes' tables from looks.js,
  walls.js and ground.js; [made_requests_test.mjs](../../tools/viewer/tests/made_requests_test.mjs) is its node test.
- **[app.js](../../tools/viewer/web/app.js)** imports `actorPose`, `movedMatrix`, `isPlain`, `madeRequest` and
  `plainLook` and gives them to the factories as before; the imports only the moved code used went with it (walls.js's
  and ground.js's tables and shapes, `DONOR_VERSION`, `placedPose`, `actorMatrix`, `tidyLocation`, `tidyRotator`,
  `cloneBlasts`). 1,774 lines to 1,696; top-level functions 72 to 62.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the scene's pieces and the made pieces' request in how the page fits and
  their rows.

Checked: [moved_code.py](../../tools/repo/moved_code.py): the ten functions the same as app.js's at the commit before
(`export` aside), app.js's other 62 and scene_pieces.js's other functions the same (`createScenePieces` differs by its
argument and the functions moved into it); every name the moved code reads resolves as before (by eslint-scope;
`PLAIN_MATERIAL`, which app.js took from the factory, is now the factory's own, and `PLAIN_VERSION` moved with its
readers); `web_names` clean; the node suite (the new test with it); the twenty-edit recording the same as on the
stage's start commit, all 52 steps; browser checks `api-names`, `typed-pose`, `destruction`, `copy-drag`, `adding`,
`library`, `cover`, `builder`, `lights`, `effects`, `paste-buildings`, `look-undo`, `draw-errors`, `reset-all`,
`walls`, `made-prefab` and `looks` pass.
