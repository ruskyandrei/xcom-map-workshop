### The copy tool's edits of the map's own actors in place in a function of their own (edits_in_place)

Review finding 51, refactor stage B4, step 5.

- [native_copy.py](../../tools/bake/native_copy.py): `edits_in_place(st)` holds `build`'s lines that run once every
  copy is made from the map's actors: the added and changed lights listed in the receivers they reach (baked
  builds), the light edits' emptied slots, the clear, the map's landings moved, pieces' flags and blasts where they
  stand, a mission's pieces' tiles moved in their stream, and the ladders' top tiles queued first on a resized map.
  Its lines are as they were, between lines reading the state's fields and writing its results back
  (`registration`, `landing_record`, `flag_record`, `blast_record`, `stream_record`, `priority`, and the
  `hide_volumes`, `firsts` and `ladders` it adds to; the clear's record it wrote to the state already), which
  `BuildState` names, with the three it reads that `build` made (`light_result`, `hide_volumes`, `effect_moved`).
  The flags' and blasts' records start empty in it (they did in `build`, with nothing reading them between), and
  `build`'s reading of the inputs only these lines used (`tiles`, `landing_zones`, `stream_tiles`, `piece_flags`,
  `flag_ladders`, `piece_blasts`) goes.

Checked: `edits_in_place`' body, less its reading and writing lines, is the old lines' syntax tree (no
substitution); `moved_code.py` on every function of the file, with the old lines replaced by the call and the
reading lines shortened: all 106 the same; no name left undefined (which found the function's own import of
native_lights missing, put in before any run); the ten Builds equal to the code before; the bake tests of native
copies, made walls, buildings, flags, the clear and effects.
