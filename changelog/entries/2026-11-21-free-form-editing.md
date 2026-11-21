### Made walls, floors, roofs and ground are sized and drawn at any size, as the snap setting says

With the wall generator's free form merged (its own ledger entries), a made piece is now edited in the free form on the
page (the custom geometry improvements plan, stages 2 and 3, decision D1):

- **Its handles follow the snap setting**: a wall's ends and top, a floor's or roof's sides and holes, a ground shape's
  sides and top move smoothly with snap off, in steps of 24 under fine and by whole tiles across and levels of 64 up
  under tile, the distance dragged. A piece of an older version is put into the free form by its first size edit
  (undo puts the older one back). Only the face dragged changes: the piece's origin stays where it is, so its gaps,
  holes, blasts and texture stay put in the world, and a gap or hole the face passes is clipped or goes, said in the
  hint. [made_handles.js](../../tools/viewer/web/made_handles.js) `moveFreeDrag`,
  [made_free.js](../../tools/viewer/web/made_free.js) `movedFreeHole`; the wall's gap rules read a free wall's own
  extents ([walls.js](../../tools/viewer/web/walls.js) `movedOpening`, `openingEdges`).
- **Drawing follows the snap setting**: under tile snap as before (tile edges, quarter turns, the older versions);
  under fine snap the first point on the grid's steps of 24, the bearing in steps of 15 degrees and the length in steps
  of 24; with snap off the exact drag, any length and angle. Such a piece is made in the free form.
  [walls.js](../../tools/viewer/web/walls.js) `drawnPoint`, `drawnRect`, `drawnWallAt`, `drawnSlabAt`, `drawnRoomAt`,
  [ground.js](../../tools/viewer/web/ground.js) `drawnGroundAt`, [made_drawing.js](../../tools/viewer/web/made_drawing.js).
- **Flip** turns a free wall a half turn about its origin, which stays; **a look change** keeps a free piece's extents
  and form; a plain free piece is known as plain ([made_looks_wiring.js](../../tools/viewer/web/made_looks_wiring.js),
  [made_requests.js](../../tools/viewer/web/made_requests.js) `isPlain`).
- The Wall, Floor and Ground sections say a free piece's size in units
  ([made_panel.js](../../tools/viewer/web/made_panel.js)); a free piece offers no Align to game pose and gets no Off
  the grid chip (its template's pose rule is not its own: [app.js](../../tools/viewer/web/app.js),
  [selection.js](../../tools/viewer/web/selection.js)).
- The editor's server checks a free wall or slab piece by piece, as the Build cuts it
  ([generated.py](../../tools/viewer/generated.py) `free_numbers`); the Build's box of a free wall is the generator's
  own ([frac_walls.py](../../tools/bake/frac_walls.py) `local_box`, `frac_wall.solid_box`).

Checked: node tests (walls_test: drawing under each snap, Flip; made_free_test); the editor, viewer, repo and node
suites; the bake tests of the free form (170, with [test_free_build.py](../../tools/bake/tests/test_free_build.py)
building a free wall at a free angle with a mitred end into URB_Bar); the Builds of the project inputs byte for byte
against the stage's first commit (only the manifest's list of tool modules differs, naming the new ones); the browser
checks `walls` (reworked for the free form: an end dragged under tile snap keeps the origin, the top lowered by levels,
Flip about the origin, a floor's side and a ramp's top under the snap, a free ramp keeping its form through a look
change; its drawing done under tile snap, as written), `looks`, `made-break`, `made-openings`, `rock-corner`,
`room-buttons`, `made-prefab`, `adding` and `api-names` on a test server; a free floor's side dragged under each snap
(317.51, 312, 384) and a block raised freely, by hand in a headless page.

Known gaps: the new handles (a wall's thickness and bottom, Pivot to corner and Join ends' buttons, the tall wall's
setting) wait for the choice of the stage 3 mock designs; nothing of the free form has been played in the game.
