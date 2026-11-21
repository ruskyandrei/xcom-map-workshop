### Made pieces' free form: the request, its check and its numbers on the page

A wall, floor, roof or ground shape made from numbers can now be recorded in a free form (the custom geometry
improvements plan, stage 2): one new request version of each kind (`fracWall` 5, `fracSlab` 4, `ground` 5) whose
numbers carry `free: 1` and say everything in fields: extents at any size in the piece's own frame (no tile multiples,
no 64- or 128-tile, 12-storey or 384-unit caps), a wall's thickness and `tall` (repeat storeys or stretch), openings and
holes anywhere inside, the look (with `plain` when none was chosen) and the texture mapping's shape (built in stage 4).
Nothing makes such a piece yet: the handles and drawing that do come with stage 3, and the generators that build it
with the rest of stage 2.

- [made_edits.py](../../tools/editor/made_edits.py): `FREE_VERSION`, `BUILD_FREE_VERSION`, `free_valid`,
  `mapping_valid`, `MadeEdits.free_generated`: a free-form request is checked and goes on to the Build as its kind's
  free version (walls 4, slabs and ground 3), its numbers as they are, less `plain` (warned of as made-no-look, as the
  older plain versions are).
- [compiler.py](../../tools/editor/compiler.py) `slab_heights`, `ground_box`, `ground_slope` and
  [compiler_tables.py](../../tools/editor/compiler_tables.py) `wall_heights`, `made_wall_along`: a free-form piece
  stands in its own numbers' box.
- [made_free.js](../../tools/viewer/web/made_free.js) (new): an older request upgraded to the free form from its
  look's heights (`freeRequest`), a face dragged with the piece's origin staying where it is, its openings or holes
  clipped (`resizedFace`, decision D1), Pivot to corner's renumbering with its blasts, points and texture offsets
  (`pivotedToCorner`), and what the editor makes (`toolFree`).
- [research/editor-contracts.md](../../research/editor-contracts.md) says what the free form holds;
  [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module.

Checked: [test_compiler_free.py](../../tools/editor/tests/test_compiler_free.py) (new: the versions, the lowering,
boxes past the old caps, plain, malformed numbers, a mapping carried, a free ramp's slope) and the whole editor suite;
[made_free_test.mjs](../../tools/viewer/tests/made_free_test.mjs) (new) and the node suite. Old projects compile as
before (the editor suite's compile cases); their Builds are compared byte for byte when the generators land.
