### The turned walls' column tests in a file of their own, and the made pieces' column rule in one call

A tidy after the turned walls' columns (KB-8, F-145), nothing built differently. Their tests had gone into the
middle of `test_frac_walls.py`'s `Columns` class, which carried its last three tests into the new class and took the
file to 1,543 lines; they move to a test file of their own and `Columns` is as it was. The Build's choice of a made
piece's column rule (a slab's cells, a turned wall's along its line, F0's on the world's axes) is one function, which
takes `add_walls` back under 150 lines.

- [test_turned_walls.py](../../tools/bake/tests/test_turned_walls.py) (new): `yawed`, `blast_breaks` and
  `TurnedColumns`, moved unchanged; [test_frac_walls.py](../../tools/bake/tests/test_frac_walls.py) back to its
  `Columns` of the commit before the fix.
- [frac_walls.py](../../tools/bake/frac_walls.py): `made_columns`, which `add_walls` calls.

Checked: `tools/repo/moved_code.py` (the moved tests and helpers the same; `test_frac_walls.py`'s every function as it
was before the fix; `add_walls` differing by the call alone), `test_structure.py --sizes` (neither over), the bake,
editor and repo suites, and the Builds' outputs (`build_outputs.py`) against the commit before the fix: every package
file the same.
