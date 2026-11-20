### The compiler's spawn point edits in a module of their own

Review finding 23, as far as its first step: one bounded edit family moved out of the `Compiler` class.

- **[spawn_edits.py](../../tools/editor/spawn_edits.py)** is new: `SpawnEdits` holds the spawn family's methods, moved
  from [compiler.py](../../tools/editor/compiler.py) with their names and bodies unchanged but for where they read the
  compiler (a script compared the two, whitespace aside): `spawn_of`, `spawn_values`, `spawn_box`, `spawn_override`,
  `spawn_names`, `spawn_delete`, `free_pod_index`, `volume_add` and `spawn_add`. It owns the family's state, which was
  the compiler's: the spec's `spawns` operations (`ops`), the next free pod index and the base map's spawn points by
  actor (`index`, filled where `index_export` filled them).
- **The compiler** makes one for each `Compiler` and hands it each spawn record from `overrides` and `added`; `spec`,
  `projected_spawns` and the report read its operations and points. Diagnostics still go through the compiler's
  `error`, `warn` and `note`, so a refused record is left out and the build goes on as before. The module imports the
  compiler's tables (`SPAWN_*`, `FAMILIES`, `EPS_LOCATION`, `short`, `tidy`), so the compiler imports it when a
  `Compiler` is made.
- **State the stages of `run()` set is now made in `__init__`**, with a comment giving the order: the map's package,
  the clear and what it keeps outside, the drop-in rule, the larger grid, the zones and the map's own landings. The
  `getattr` reads with defaults that stood in for it (`stage_grid` eight times, `cleared`, `zones`, `own_count`,
  `own_landings_found`, `spawn_rules`, `keep_outside`) read the attributes directly, with the same defaults.

Checked:
- [test_spawn_edit_fixtures.py](../../tools/editor/tests/test_spawn_edit_fixtures.py), recorded before the move,
  gives the same 38 cases after it: the spawns lane in order, the entities, the counts, and every diagnostic;
- the editor suite;
- `compiler.py` run as a script on a recorded case gives the same lane.

What remains for the follow-up plan (not moved here, at the finding's word): the other families (effects and sounds,
lights and area lights, made walls, slabs and ground, floors and flags, buildings, landing zones and missions,
groups), `spec` and `native_split`; `Build.__init__`'s 20 parameters and the state its stages add; `prefab_stage`
importing all of `build.py` for `lwr_file`; and the memo attributes still read through `getattr` (`_floor_boxes_now`,
`_map_buildings`, `_building_records`, `_missions_kept`).
