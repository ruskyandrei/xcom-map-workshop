### A flat piece larger than the map no longer slows the Build's compile

A reported project took about two minutes in the Build's "Compile the edit" step (1:43 of a quick build's 1:56). It
is a cleared map with a boat prefab whose twenty sea planes are 200 tiles square each, lying flat at the water line.
The compiler's floor check ([floor_edits.py](../../tools/editor/floor_edits.py) `added_floors`: the floor the
project's flat pieces give, read by the ladder, headroom, spawn and landing-zone checks) walked every tile under each
flat piece, bounded only in height. That made 803,202 tiles per call, each tested against all 389 pieces, and the
check ran seven times per compile.

- The walk now covers only the tiles of the grid as the project has it, a grown grid's new tiles included, as it
  already did for levels. A tile outside the grid is none of the game's, and every caller looked tiles up inside it.
- For each flat piece, the pieces that can hang over it (bottom within its standing room, box meeting its own) are
  picked once, in the same order, so the piece named in a floor-headroom warning is the same.

Checked: on the reported project, each of the seven calls gives the old answers cut to the grid, and the compile
report and spec are identical before and after. The compile went from 72 s to 0.8 s here, and a whole quick build
from about 105 s to 33 s. A new test (`test_a_flat_piece_larger_than_the_map_gives_floor_only_over_the_grid` in
[test_compiler.py](../../tools/editor/tests/test_compiler.py)) covers a sea plane round the map, a plate over it, one
past the grid and a grown grid. `python tools/run_tests.py editor viewer repo` passes.

Known gap: most of the 33 s left is the map edit (native_copy.py, 24.5 s). About a third of that is `level_grid`
and `scene_metadata.game_grid`, which scan every object of the package once per copy (783 calls for 395 copies).
Not changed here.
