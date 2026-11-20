### A made floor or roof its holes leave none of is left out and said; overlapping holes keep the floor between them

Review finding 32, the Python side (the page's side is another change).

- [frac_slab.py](../../tools/bake/frac_slab.py)'s `check` says "the slab's holes leave none of it", as frac_wall says
  of a wall's openings, where the build of such a slab stopped on an empty `min()`. The editor's mesh server, which
  checks each piece with it, now gives that message too.
- The [compiler](../../tools/editor/compiler.py) leaves such a slab out of the build with a `slab-all-holes` row ("its
  holes leave none of it, so it is left out of the build"), shown with the editor's warnings as a piece left out; the
  rest of the project builds. `slab_valid` still takes its numbers as well formed.
- [made_split.py](../../tools/bake/made_split.py)'s `slab_pieces` dropped a piece when its holes' areas added up to
  the piece's, but holes may overlap: a 17 by 1 slab with holes over tiles 0 to 9 and 0 to 8 lost its first piece,
  solid tiles 10 to 15 with it. It now tests the piece's tiles (`solid`), and `slab_left` gives the compiler the same
  test for the whole slab.
- Checked: [test_frac_wall.py](../../tools/bake/tests/test_frac_wall.py) (one hole over all of it, two overlapping
  that cover it: `check` and `build` say so; one tile left is a slab),
  [test_made_split.py](../../tools/bake/tests/test_made_split.py) (the 17 by 1 case keeps its first piece; a slab
  all holes gives no piece) and the new
  [test_compiler_slab_holes.py](../../tools/editor/tests/test_compiler_slab_holes.py) (left out and said, the next
  slab built; overlapping holes that leave a tile are a slab). Each failed before the change. The editor suite passes.
- Not done here: a slab of more than 16 tiles a side that is all holes gives the mesh server no piece to draw rather
  than the message (the compiler leaves it out all the same).
