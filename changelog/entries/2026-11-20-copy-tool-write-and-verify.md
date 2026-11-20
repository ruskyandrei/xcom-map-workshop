### The copy tool's write and read-back in a function of their own (write_and_verify)

Review finding 51, refactor stage B4, step 7.

- [native_copy.py](../../tools/bake/native_copy.py): `write_and_verify(st)` holds `build`'s lines that put every new
  actor in the level's list, write the map with the growing writer (the variant map, or with `bake` the grown map
  with the variant cache's name in its name table), and check from a fresh read what was written: the copies' vertex
  lightmaps, the light edits, the lanes and the floors' effect lists, the made cursor floors and the flags, with the
  ladders' rebuild order read back. Its lines are as they were, between lines reading the state's fields and writing
  its results back (`level`, `dst`, `report`, `q`, the ladders read back), which `BuildState` names, with the lanes'
  records and copies it reads that `build` made. `build` keeps the record: the manifest (`manifest_parts`) and, with
  `bake`, the relight (`relight_command`).

Checked: `write_and_verify`' body, less its imports and its reading and writing lines, is the old lines' syntax tree
(no substitution); `moved_code.py` on every function of the file, with the old lines replaced by the call and three
names no longer read taken off `build`'s reading lines: all 108 the same; no name left undefined; the ten Builds
equal to the code before; the bake tests of native copies, made walls, buildings, flags, the clear and effects.
