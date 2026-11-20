### The copy tool's building floors in a function of their own (edit_buildings)

Review finding 51, refactor stage B4, step 4.

- [native_copy.py](../../tools/bake/native_copy.py): `edit_buildings(st)` holds `build`'s lines that put each copy
  in the cutaway of the map's building floor it stands in (`edit_floor_caches`, with the map's own buildings' new
  boxes), the walls made from numbers in the map's buildings they stand in (`list_made_walls`), the buildings made
  from nothing (`buildings.make`) and the map's own edited in place (`buildings.edit`), with the slots those edits
  empty. Its lines are as they were, between lines reading the state's fields and writing its results back
  (`floor_caches`, `made_floors`, `building_actors`, `building_records`, `edit_records`; the emptied slots it wrote
  to the state already), which `BuildState` names.

Checked: `edit_buildings`' body, less its reading and writing lines, is the old lines' syntax tree (no
substitution); `moved_code.py` on every function of the file, with the old lines replaced by the call: all 105 the
same; no name left undefined; the ten Builds equal to the code before; the bake tests of native copies, made walls,
buildings, flags, the clear and effects.
