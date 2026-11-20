### A made wall's break group reaches the Build

Review finding 36. The Build runs [native_copy.py](../../tools/bake/native_copy.py) with a `--copies` file, and its
command line rebuilt each copy record field by field, leaving out the `wallGroup` the
[compiler](../../tools/editor/compiler.py) gives a made wall that breaks with its group. So in every real build no
group was walled: a group of one prop and a made wall stopped in `link_children` ("break group N has 1 piece(s)"), a
cover block grouped with a made wall stopped as "a cover block and no breakable piece", and with two or more props
the props were never listed in the wall's columns.

- The command line now hands `build()` each copy record whole, as the compiler (or the transplant's staged edit) wrote
  it; only the pose and the break group are read as numbers.
- Checked: a new `CommandLine` class in [test_native_copy.py](../../tools/bake/tests/test_native_copy.py) runs `main`
  on a `--copies` file with every field the compiler writes (and one it does not) and compares what `build()`
  receives; it failed before the change. The group-with-a-made-wall build itself is covered by
  [test_frac_walls.py](../../tools/bake/tests/test_frac_walls.py)'s `GroupWithMadeWall`, which calls `build()`.
- Not seen in the game: a made wall and the props of its group breaking together.
