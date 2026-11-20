### A project opens when one of its pieces can't be drawn; a failed load is asked for again

Review finding 29. The map's own load already left out, piece by piece, any piece it couldn't draw. A project's,
prefab's or paste's pieces were made all at once, and one failure failed the whole step. A mesh, material or texture
that failed once also stayed failed for the page's life.

- `buildRoots` ([app.js](../../tools/viewer/web/app.js)) can leave out a piece that can't be drawn and name it.
  - `applyState` (a project's or prefab's opening, Restore them) counts such a piece as a display error, as the map's
    load does. Its record is carried and saved back unchanged, none of its parts is drawn, and a note says so.
  - The prefab builder's `loading` mark ends whatever happens.
  - A paste leaves out such a piece, all its parts, and its hint says why. A failed paste says so instead of being an
    unhandled rejection (`placeAt`, the copy drag).
- `track` drops a load whose promise rejects, and the texture cache now goes through it, so the next piece that needs
  a load asks again, as `libraryTemplate` already did.
- Every banner action catches its failure and says so in the banner ("Restore them could not be done: …").
- `window.viewer.applyState` is there for the checks.
- Checked: the new browser check `draw-errors` ([browser_editing.py](../../tools/viewer/tests/browser_editing.py),
  through `browser_smoke.py --projects --only draw-errors`) saves a Bar project with a copy of a piece, then opens it
  with that piece's mesh kept from the browser. The project opens with the copy's record kept. A paste of the piece
  says it could not be drawn and places nothing. Once the mesh can be had, the next paste places it. Saving keeps the
  copy's record. Last, a state whose copy needs a texture that is missing is put on the map: the copy is carried and
  noted as not drawn.
