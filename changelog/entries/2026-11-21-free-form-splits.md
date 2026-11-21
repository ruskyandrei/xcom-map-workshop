### Free-form made walls and slabs cut into pieces at any size

The splitter cuts made walls and slabs whose numbers hold `free: 1` (the custom geometry improvements plan, stage 2)
into pieces the game takes, at any size; numbers of the old form are cut as before.

- **Along.** At tile edges counted from the frame's origin, at most 16 tiles apart, each as far along as it goes
  outside every opening or hole; the last piece whatever is left, fractions and all. A tail under 48 units (one its own
  end or its fracture would eat) shares the cut before it, which moves back a tile.
- **Up (walls).** By the wall's `tall`: 'repeat' stacks its look's height while a storey of the look or more would be
  left over one more, the top piece the rest (lengthened or shortened, no sliver); 'stretch' is one piece up to twice
  its look's height, else bands of equal height no taller than the look, each a `band` [lo, hi] of the one stretched
  outline (the wall generator builds the window). The look's own height and storeys are asked of the look alone.
- **Every piece** keeps the whole's seed, its free numbers (`free`, `y0`, `y1`, `z0`, `z1`, `look`, `mapping`, ...),
  its openings or holes cut to it and moved into it, and `whole`: a wall's [its place along, the whole's length, its
  place up, the whole's height, the whole's x0], a slab's [its place along x, along y, the whole's width, depth, the
  whole's x0, y0], so a generator reads where the piece stands in the whole's frame (its lattice and its texture go on
  across the cuts). A piece an opening takes whole is no piece; a slab's piece is kept where the slab generator finds
  some of it left (`slab_cells.FreeSlab`, its holes snapped), or by the holes' own edges where its look is a donor not
  resolved here (`free_left`, which `slab_left` uses for free numbers).

Where: [made_split.py](../../tools/bake/made_split.py) (`free_cuts`, `repeat_heights`, `stretch_bands`,
`free_wall_pieces`, `free_slab_pieces`, `free_left`, `covered`); [ARCHITECTURE.md](../../ARCHITECTURE.md): a row in
section 2 for the free walls' modules, and frac_wall.py (1,568 lines) in section 4's list.

Checked: [test_made_split.py](../../tools/bake/tests/test_made_split.py)'s `FreeCutTests` (8 tests: the cuts and tails,
a long wall with a gap over the cut and a leaning end, a piece's cells equal to the unsplit wall's away from the cut,
repeat stacks and stretch bands with their openings, the bands' cells and face texture matching the stretched wall
built whole, a measured look's own height, a piece a gap takes, a large slab with its pieces passing the slab
generator's check and a covered piece dropped) and `OldNumbersTests` (the old cuts' hashes unchanged), `run_tests.py
bake -k made_split`.

Known gaps: the compiler (made_edits.py) and the mesh server (generated.py) are other changes': they hand free walls
to `wall_pieces` as they do old ones, with `look_storeys` and `heights` that answer for the look alone. Not played in
the game.
