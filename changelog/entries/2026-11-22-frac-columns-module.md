### The fracturing pieces' fragment columns in a module of their own

The copy tool's code for fracturing pieces' fragment columns moves, unchanged, out of `native_copy.py` into a module
of its own: reading a piece's columns, a column given new lists, a copy's columns carried with it (with the test of
one move carrying two pieces and the component's saved heights), and the level's columns edited for the pieces an
edit hides and copies, with their constant. `native_copy.py` goes from 3,425 lines to 3,215.

- [frac_columns.py](../../tools/bake/frac_columns.py) (new): `fragment_columns`, `column_with`, `same_move`, `overlap`,
  `move_columns`, `shift_fragment_heights`, `edit_columns`, `COLUMN_MATCH`. It takes the struct array helpers it
  shares with the building floors and the effects' lanes (`find_prop`, `struct_elements`, `struct_entries`,
  `entry_for`, `with_array`, `rebuilt`), `moved_box`, `Walker` and `FRACTURING` from native_copy, which imports it
  inside its steps, as it does its lanes' makers.
- [native_copy.py](../../tools/bake/native_copy.py): `fracturing_copies` and `wall_columns` call them there;
  [frac_walls.py](../../tools/bake/frac_walls.py) and
  [test_native_flags.py](../../tools/bake/tests/test_native_flags.py) too.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the copy tool's paragraph names the module, section 2 has its row, and
  section 4's line for native_copy.py.

Checked: `tools/repo/moved_code.py` (the seven functions the same; the copy tool's other 102 the same, its two steps
differing by the calls), the bake, editor and repo suites (the structure test among them), the Builds' outputs
(`build_outputs.py`, the eleven inputs: every package file the same, the manifests' list of the code that made them
naming the new module) and the editor suite's compiles (`compile_record.py`) against the commit before.
