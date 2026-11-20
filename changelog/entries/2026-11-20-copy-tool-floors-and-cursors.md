### The copy tool's floor lists and made cursor floors in a function of their own (floors_and_cursors)

Review finding 51, refactor stage B4, step 6.

- [native_copy.py](../../tools/bake/native_copy.py): `floors_and_cursors(st)` holds `build`'s lines that list the
  moved and new effects in the building floors whose boxes hold them, against the final effects and floors, and take
  the moved and deleted ones out of the lists that named them (`native_effects.floor_lists`), then stand the made
  floors' and roofs' own cursor floors over their footprints (`made_cursors.apply`, with its lines printed). Its lines
  are as they were, between lines reading the state's fields and writing its results back (`floor_emitters`,
  `cursor_record`, `cursor_clones`), which `BuildState` names, with the two it reads that `build` made
  (`effect_record`, `lane_effects`).

Checked: `floors_and_cursors`' body, less its import and its reading and writing lines, is the old lines' syntax tree
(no substitution); `moved_code.py` on every function of the file, with the old lines replaced by the call: all 107 the
same; no name left undefined; the ten Builds equal to the code before; the bake tests of native copies, made walls,
buildings, flags, the clear and effects.
