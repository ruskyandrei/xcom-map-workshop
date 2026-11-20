### The copy tool makes each copy, and the Build's state, through one function each (copy_record, edit_state)

Review finding 51, refactor stage B4, step 8: `native_copy.main` built the Build's inputs from the native edit and
the command line in its own lines, the way finding 36 lost a made wall's `wallGroup`.

- [native_copy.py](../../tools/bake/native_copy.py): `copy_record(c)` makes a copy as `build` reads it: the record
  whole, its pose and group read as numbers (main's lines for the native edit's copies, moved). `edit_state(src,
  out, variant, doc, **options)` makes the `BuildState` of a native edit (the Build's `native-edit.json`, or a list of
  copies), each lane to its field and each copy through `copy_record` (main's lines, moved). `main` reads the
  `--copies` file, makes the state through `edit_state`, and adds the copies of `--copy` and `--actor` through
  `copy_record` too, so every copy is made one way. Those two now also carry `rotation: None` and `breakGroup: 0`,
  which `build` reads as it read their absence (no Build output changes).
- [test_native_copy.py](../../tools/bake/tests/test_native_copy.py): a copy carrying every optional field
  (the compiler's, a staged copy's, the command line's yaw, and one no reader knows yet) comes through
  `copy_record`, `edit_state` (from a dict and a list) and `main` whole, its pose and group as numbers; every lane
  `edit_state` reads (found in its code) reaches its field; the command line's copies come through `copy_record`,
  after the native edit's. A planted loss (`copy_record` dropping `wallGroup`) fails the two copy tests.

Checked: `edit_state`'s statements are main's old ones (less the file's read, which stays in main, and with each
copy's record through `copy_record`), `copy_record`'s record is the one main made, and the state is made with the
names main gave `build` (a scratch check at the syntax tree); `moved_code.py` on every other function of the file:
the same; build_outputs.py still finds the lanes the copy tool reads; the ten Builds equal to the code before; the
bake tests of native copies, made walls, buildings, flags, the clear and effects.
