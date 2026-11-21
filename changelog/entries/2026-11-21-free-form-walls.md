### Made walls build from free numbers: any size, thickness and height, leaning ends

The wall generator builds a wall whose numbers hold `free: 1` (the custom geometry improvements plan, stage 2, its
request's free form) at any size, by the general path whatever its look; numbers of the old form build byte for byte
as before.

- **Extents.** `x0 < x1` any finite values; `y0 < y1` its faces: each side of the look's outline moves with its face,
  so a trim stands as proud of it as it did, and the collision across moves with them; `z0 < z1` its bottom and top:
  the outline is raised to `z0`, then the height it lacks goes into (or what it has too much comes out of) its longest
  stretch upright on both sides at once, the bands under and over it keeping their sizes, else every height is scaled.
  `storey_cut` and `lowered` learnt to put height in. The Bar look is written as a measured look (`as_measured`), so
  every free wall takes the one path. A raised wall's faces keep their pattern on them (`uvShiftZ`).
- **Bands.** `band: [lo, hi]` makes the window lo..hi of the stretched outline: no bottom trims when lo is over the
  bottom, no top trims when hi is under the top, each cut strip's texture going on as on the whole.
- **Cells.** One seed in each lattice cell of the look's cell size counted from the frame's origin (the whole wall's,
  for a piece: `whole` [dx, length, dz, height, the whole's x0]), placed in it by a hash of the seed and the cell's
  place: dragging an end changes only the cells near it.
- **Ends.** Each end a style measured from the wall's own x0 or x1 ('free', 'line', 'through': half the faces'
  distance) or `{inset, lean}`: the end's plane stands `inset` in and leans `lean` along the wall for each unit
  across (the end at y across at its place plus lean times y, y from the frame's line; clamped at a 30-degree
  corner's lean). A leaning end's cells are a column of bands, so nothing but the end lies within its reach; its
  corners then move along the wall, the faces' texture read at the moved place, the charts grown to hold them, and its
  collision box becomes a hull. A gap within a leaning end's reach is refused unless cut through to the end.
- **Gaps** anywhere inside, reaching an end or not; `mapping` taken and not used yet (stage 4); each face's texture
  coordinates held near 0 in whole repeats (`free_form.held`).
- **Checks.** `check_free` refuses with a `free_form.NumbersError` and its code: 'free', 'number', 'extent', 'mapping',
  'tall', 'band', 'whole', 'opening', 'ends', 'thickness' (faces that would leave the look's outline crossing itself),
  'lean'. A size is never changed to fit. `solid_box` gives the box a free wall's solid stands in, its leaning ends'
  reach included.

Where: [wall_profile.py](../../tools/bake/wall_profile.py) (`as_measured`, `thickened`, `heightened`, `windowed`,
`free_shape`), [frac_wall.py](../../tools/bake/frac_wall.py) (the block "the free form": `check_free`,
`free_shaped`, `free_ends`, `free_seeds`, `lean_ends`, `solid_box`; `solids` makes the hulls; 1,568 lines, a little
past the guideline: the next change lists it in ARCHITECTURE.md).

Checked: [test_wall_profile.py](../../tools/bake/tests/test_wall_profile.py) (new, 12 tests) and
[test_frac_wall.py](../../tools/bake/tests/test_frac_wall.py)'s `FreeForm` (20 tests: twelve free walls each closed,
facing out, its neighbours mutual, its lightmap in the square and written and read back; fractional extents and
thickness; heights between storeys either way in the Bar's and a measured look; bands; cells unmoved by an end
dragged; a piece reading the whole's lattice; mitres at 45, 90 and 135-degree corners at both ends, the clamp, gaps
near a leaning end; the refusals' codes), and `OldNumbers` (the old walls' hashes unchanged), `run_tests.py bake -k
frac_wall -k wall_profile -k wall_measure`.

Known gaps: frac_walls.py (its request version 4, `check`, `local_box`) is another change's; its box should take a
leaning end's reach as `solid_box` does (the lean times the outline's reach across, trims included, from the frame's
line), not half the faces' distance. A leaning end's cells are a column of bands rather than the look's pattern. A
band's cut top and bottom take the look's cap texture. Not played in the game.
