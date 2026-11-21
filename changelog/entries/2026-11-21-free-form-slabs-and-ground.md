### Made floors, roofs and ground build from free numbers

The slab and ground generators take the free form of the custom geometry improvements plan (stage 2, section 10.2):
numbers holding `free: 1` give a piece's box in finite game units in its own frame, any size, with no whole tiles and
no tile minimum. Old numbers never hold `free` and build byte for byte as before. Nothing calls the free form yet: the
request versions, the splitter, the compiler and the page come in their own changes.

- **Slabs** ([frac_slab.py](../../tools/bake/frac_slab.py), [slab_cells.py](../../tools/bake/slab_cells.py), new):
  - Footprint and plate: any `x0 < x1`, `y0 < y1` (a slab under a tile included, off the tile edges), and the plate
    between `z0` (underside) and `z1` (top).
  - Holes: rectangles anywhere inside the footprint, overlapping or not.
  - Fragments: the look's tile lattice is counted from the frame's origin (a split piece reads it from its `whole`
    place, with the whole's corner as two more numbers where it is not the origin). Each cell is cut by the footprint
    and the holes into convex rectangles; each connected group is one fragment. A whole cell's pattern (tile, diagonal
    halves or a two-cell piece) comes from a hash of (seed, i, j), with pairs at fixed lattice places. A size change
    therefore re-rolls only the cells near the cut, and the old slabs' fragments a tile for the same look stay within
    a few per cent. A cut piece thinner than 8 units joins its neighbour. Every polygon has a corner at each other
    polygon's corner on its sides.
  - Collision: boxes over exactly the solid area, kept at the look's distances from the plate's bottom and top (a
    roof thickened keeps its collision's top 2 under its drawn top, with the bottom on the underside), or the whole
    plate where that leaves none.
  - Texture and paint are read in the whole slab's frame as before. Each face's coordinates are held near 0 in whole
    repeats.
  - One piece is at most 17 of its look's tiles each way (`CHUNK`, the splitter's chunk and a tail).
  - `check_free` checks free numbers, and `local_box` gives their box.
- **Ground** ([ground.py](../../tools/bake/ground.py)): any `x0 < x1`, `y0 < y1`, `z0 < z1` (a patch's plate, a block's
  bottom and top, a ramp rising from `z0` at `x0` to `z1` at `x1`, a rock's bottom and top, its points within that
  box). There is no 64-tile or 384-unit cap. Each face's texture coordinates are held near 0 in whole repeats. A face
  that would still reach 1,024 repeats from 0 is refused, since a half float keeps no place within a repeat past that.
  For a look of 320 units a repeat (the default) that means up to about 655,000 units a side or high. For the
  catalogue's smallest repeat (24.6 units) it is about 50,000 units. `check_free` and `local_box` work as for slabs.
- **Shared** ([free_form.py](../../tools/bake/free_form.py), new): what is free, extents checked without changing them,
  the texture-coordinate hold, and `NumbersError`. That is a ValueError with a code (`extent`, `hole`, `left`,
  `chunk`, `half-floats` and others) beside its reason. `mapping` and `plain` are accepted and not read (stage 4 and
  the editor).
- [ARCHITECTURE.md](../../ARCHITECTURE.md) section 2 gains the free form's row.

Checked:
- Bake tests through `run_tests.py`: [test_slab_cells.py](../../tools/bake/tests/test_slab_cells.py) (new; stage 1's
  partial-slab experiment among them), [test_free_form.py](../../tools/bake/tests/test_free_form.py) (new),
  [test_frac_slab_looks.py](../../tools/bake/tests/test_frac_slab_looks.py) and
  [test_ground.py](../../tools/bake/tests/test_ground.py).
- The partial-slab experiment builds a fractional slab with a hole across a tile edge, a hole inside a tile and a hole
  at its edge. Its fragments' tops, its undersides and its collision boxes each cover exactly the solid area, its edges
  cover the outline's and the holes' perimeter, and no box covers a hole.
- Old slabs and ground shapes of every path have their builds' digests pinned
  ([fixtures.py](../../tools/bake/tests/fixtures.py) `made_digest`), recorded on the commit this started from.

Known gaps:
- The lightmap rectangle of a large ground piece grows with it (740 texels at 64 tiles, 2,952 at 256). The Build
  scales it down into its donor's atlas, so a very large piece is lit more coarsely, and its charts' margins shrink
  below a texel. This is no refusal.
- The splitter does not yet cut ground on these limits.
