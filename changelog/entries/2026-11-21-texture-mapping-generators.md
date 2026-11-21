### The generators apply a made piece's texture mapping to its main faces

A free-form wall, slab or ground shape whose numbers carry a texture `mapping` (the custom geometry improvements plan,
section 5, decision D8: the main faces first) now draws those faces with it; until now the generators took the mapping
and built as without it.

- **Which faces.** A wall's two faces (`faces`: its outline's strips that are faces, on both sides), a slab's `top` and
  `underside`, a ground shape's `top` (a ramp's slope and a rock's faces turned more up than aside, projected straight
  down as the look's own texture is) and `sides`. Trims, caps, ends, gaps' sides, a slab's edges and the faces inside
  keep their look's texture. A look whose outline has no face strip (the UFOs' walls, one unwrap of the whole outline)
  has nothing to map on that side.
- **Where on the pattern.** Each corner at its place on the surface's axes in the whole logical piece's frame (a
  wall: along it and up it; a slab or a ground top: x and y; a ground side: x or y along it and up), over the whole
  surface's extent: a split wall's or slab's piece reads both from its `whole` (`frac_wall.whole_origin` and the new
  `face_extent`, `slab_cells.origin` and the new `slab_cells.extent`), so a fit or a count goes on across the cuts and
  the stacked pieces or bands; a ground shape's is its box.
- **World alignment.** `mappingOrigin` beside `mapping`: {role: [a0, b0] on the role's axes or [x, y, z] on the
  frame's} (a ground side takes [x, y, z] only), read for a surface with `world`; absent, (0, 0). A split piece carries
  its whole's.
- **The image the right way round.** The mesh's v runs down the image, so the faces write the rule's (U, -V); a wall's
  side B, a slab's underside and the ground sides whose axis runs left seen from outside write -U: the mirror through
  the piece, as the game's donors' own textures are, so an unturned mapping reads the image as the look does and one
  offset keeps both faces of a wall in place.
- **Before the tangents, after the lightmap.** The coordinates go into UV channel 0 before the tangents are worked out
  from them (a turned mapping turns them), then through `free_form.held` (whole repeats taken off, the phase kept; a
  face spanning too many repeats is refused with 'half-floats'). The lightmap's channel, the vertex paint, the slots
  and the geometry are as without a mapping.
- **The rule turns before it scales.** uv_mapping.uv scaled a point to repeats and then turned it, which sheared a
  turned pattern whose u and v differ (a 96 by 48 repeat turned 30 degrees drew as an 87 by 64 parallelogram). It now
  turns the point, scales it along the turned axes (a count or a fit over the run of the surface's corners along each,
  so a quarter turn fits the turned image exactly), mirrors and slides it. Unturned results are the same.
- **Checked numbers.** `free_form.mapping` checks the mapping's shape (`uv_mapping.check`) and `mappingOrigin`
  (`uv_mapping.check_origin`) for every generator, code 'mapping'.

Where: [uv_mapping.py](../../tools/bake/uv_mapping.py) (`uv`, `check_origin`, `origin_of`, `face_signs`, `mapped`, the
module's words), [free_form.py](../../tools/bake/free_form.py) (`mapping`),
[frac_wall.py](../../tools/bake/frac_wall.py) (`Faces` keeps a face's `role`, `face_extent`, `mapped_faces`, `build`),
[slab_cells.py](../../tools/bake/slab_cells.py) (`extent`), [frac_slab.py](../../tools/bake/frac_slab.py) (`build`),
[ground.py](../../tools/bake/ground.py) (`faces_of`).

Checked: [test_texture_mapping.py](../../tools/bake/tests/test_texture_mapping.py) (new, 26 tests: every mapped
corner against values worked out by hand for size, fit, count, a count turned a quarter, a mode of its own along v, 30
degrees with square and with 96 by 48 repeats, flips, a turn, flip and slide, a half-repeat offset, world-aligned with
two and three numbers and two walls end to end meeting in phase, and each triangle's rate exactly; side B the mirror
of side A; a resized wall keeping its repeats' size or their count; a split wall's pieces (repeat stacks and stretch
bands) and a split slab's reading the whole; a doorway and a hole leaving the pattern; a leaning end; a thick wall and
a measured look; a look without faces unchanged; the tangents of a turned mapping; nothing else of the mesh changed;
too small a repeat refused; free numbers without a mapping byte for byte against digests recorded on dd6f094; a role
the piece has not changing nothing; bad mappings and origins refused by every generator. Mutations (side B not
mirrored, the underside not mirrored, the sides of one sign, a piece ignoring its place or reading its own extent, the
world origin ignored) each fail tests), [test_uv_mapping.py](../../tools/bake/tests/test_uv_mapping.py) (the order,
a turned repeat staying a 96 by 48 rectangle, a turned count and fit, origins, signs), the three tests that said the
mapping was not read now say it changes the texture alone (test_frac_wall.py, test_frac_slab_looks.py,
test_ground.py); `run_tests.py bake -k` for the generators, the splitter and the rule (245 tests), the viewer's and
editor's generated-piece tests, the repo suite, and the whole bake suite.

Known gaps: the editor's side is another change's: the page's Texture mapping section and its surface handles, the
compiler's and the page's `mappingOrigin` for world-aligned surfaces and the mesh key that holds it (made_edits.py
`mapping_valid`, made_free.js `freeNumbers`, research/editor-contracts.md), and made_free.js `pivotedToCorner`'s
offsets, which leave out a turn and the flips and read every surface's u along x. Whether a look's surface tiles is
not in the catalogue yet (the plan's section 5, item 2): a window of an atlas is mapped as a whole repeat. The relight
check with two mappings (item 8) and the game's look under baked light are not done. frac_wall.py is 1,611 lines.
