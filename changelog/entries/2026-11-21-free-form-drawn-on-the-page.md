### A free-form piece's mesh asked of the editor's server

The page now asks the editor's server for a free-form wall, slab or ground shape's mesh (the custom geometry
improvements plan, stage 2) in one spelling for its key and request, from the same endpoints as the older numbers,
with bounds from its own numbers: a wall's ends as they reach (a mitred end past its end by its lean across the
faces), its faces widened by its look's trims. A project holding such a piece draws it once the server makes it (the
server's side comes with the generators).

- [made_free.js](../../tools/viewer/web/made_free.js): `freeNumbers`, `freeBounds`, `freeMesh`, `freeShape`.
- [scene_pieces.js](../../tools/viewer/web/scene_pieces.js) `madeShapeOf` and
  [made_handles.js](../../tools/viewer/web/made_handles.js) `madeMesh` take a free-form piece through them;
  [walls.js](../../tools/viewer/web/walls.js) exports `madeRecord` for it.

Checked: [made_free_test.mjs](../../tools/viewer/tests/made_free_test.mjs) (the spelling, a plain piece naming no look,
end styles, bounds with a mitred end, the request's URL and key with blasts, a rock's points); the node and repo suites;
`web_names`.
