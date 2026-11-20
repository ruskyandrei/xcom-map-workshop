### The copy tool's fracturing copies, made walls and walls' columns in functions of their own

Review finding 51, refactor stage B4, step 3.

- [native_copy.py](../../tools/bake/native_copy.py): `fracturing_copies(st)` holds `build`'s lines that pair each
  copy with its original's pose, move a fracturing copy's columns and fragment heights with it, and make the walls,
  slabs and ground shapes from numbers (`frac_walls.add_walls`, with its lines printed); `wall_columns(st)` holds the
  lines that come after the hides and the lanes: the walls' columns without the hidden pieces and with the door
  copies (`edit_columns`), and the made walls listing a door in their opening, a group that breaks with them and the
  fracturing pieces they meet. The two stay apart because the hides, the effects' lanes and the vans' buildings are
  made between them, and the growing writer's order is the map's. Each function's lines are as they were, between
  lines reading the state's fields and writing its results back (`poses`, `fracturing`, `generated_records`;
  `columns`, `door_listings`, `group_listings`, `neighbour_listings`); `BuildState` names them, and the two
  `wall_columns` reads that `build` made (`walled`, `cover_records`).
- A made wall's group listing is moved as it was: KB-1 (a cover block grouped with a made wall keeps its cover when
  the wall is destroyed) is not changed here.

Checked: each function's body, less its reading and writing lines, is the old lines' syntax tree (no substitution);
`moved_code.py` on every function of the file, with the old lines replaced by the calls: all 103 the same; no name
left undefined; the ten Builds equal to the code before; the bake tests of native copies, made walls, buildings,
flags, the clear and effects.
