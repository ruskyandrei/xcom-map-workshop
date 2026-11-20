### The copy tool's clone loop in a function of its own (clone_copies)

Review finding 51, refactor stage B4, step 2.

- [native_copy.py](../../tools/bake/native_copy.py): `build`'s loop that makes the copies, an assembly's together,
  with their extra lights, van buildings, walkable scenery, ground collision, flags, blasts, tiles and ladders'
  top tiles, is `clone_copies(st)`, its lines as they were between one line reading the state's fields and two
  writing its results (`made`, `actors`, `firsts`, `ladders`, `vans`, `flag_copies`, `blast_copies`) back. `build`
  hands it the growing writer and the resolved light edits on the state and reads the results back into the names
  its later lines use. The two in-place records the loop's set-up named (the flags' and the blasts') stay in
  `build`, which fills them.
- `BuildState` names those fields, each with the step that fills it, through a small `filled()` (a field that is not
  an input), which the fields it had use too.

Checked: `clone_copies`' body, less its first two and last two lines, is the old loop's syntax tree (the one
substitution: the two records' empty start left in `build`); `moved_code.py` on every function of the file, with
the loop's lines replaced by the call as the substitution: all 101 the same; no name left undefined (symtable);
the ten Builds equal to the code before; the bake tests of native copies, made walls, buildings, flags, the clear
and effects.
