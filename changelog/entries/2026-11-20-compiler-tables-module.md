### The compiler's shared tables in a module of their own, and the spawn family no longer imports the compiler

Review finding 23, its next step: a home for what the compiler and its edit families share, so that a family in a
module of its own needs nothing from `compiler.py`. A move: nothing the compiler does changes.

- **[compiler_tables.py](../../tools/editor/compiler_tables.py)** is new. It holds each table and helper of
  [compiler.py](../../tools/editor/compiler.py) that more than one reader takes: the compiler and a family, or two
  families (the effects, lights, flags, made pieces, buildings, missions, groups and floors families, whose methods
  are still the `Compiler`'s, counted as families). 34 names, its `__all__`:
  - tables: `FAMILIES`, `CLASS_FAMILY`, `ASSEMBLY_FAMILIES`, `EPS_LOCATION`, `TILE`, `STOREY`, `QUARTER`,
    `POSE_SLACK`, `IDENTITY`, `FLOOR_THICK`, `HEADROOM`, `EFFECT_KINDS`, `STAGE_MAPS`, `MADE_KINDS`,
    `FRAC_WALL_END_INSET`, `FRAC_WALL_BOTTOM`, `FRAC_WALL_TOPS`, `FRAC_SLAB_LOOKS` and `GROUND_LOOKS` (with the
    private `_ground_looks` that reads it);
  - helpers: `short`, `tidy`, `game_round`, `tile_corner`, `keyable`, `target_key`, `world_box`, `union`,
    `turned`, `original_key`, `map_building_id`, `donor_shape`, `wall_heights` and `made_wall_along`;
  - the `LibraryError` exception, which the effects family and the compiler both raise or catch.

  A table or helper only the compiler reads stayed in `compiler.py`; one only a family reads stayed too, for that
  family's own stage. The module puts `tools/viewer` and `tools/bake` on the path through `paths.use()` (for
  `export_math` and the Build's `looks`), so it imports on its own.
- **The compiler** takes them with `from compiler_tables import *`, so `compiler.FAMILIES` and every other moved name
  is the same object as before for whatever reads it through the compiler (`build.py`, `prefab_stage.py`, the
  viewer's modules, the tests, which change `compiler.FAMILIES['spawn']` in place). It imports
  [spawn_edits.py](../../tools/editor/spawn_edits.py) at the top (`SpawnEdits`, and `SPAWN_COPY_KINDS`, the one spawn
  table it reads); the import inside `Compiler.__init__` is gone.
- **The spawn family's tables** (`SPAWN_EDIT_KINDS`, `SPAWN_VALUE_KEYS`, `SPAWN_WORDS`, `SPAWN_COPY_KINDS`,
  `SPAWN_BOOLS`) moved into `spawn_edits.py`, which now imports `compiler_tables` and not the compiler. Nothing read
  the four others through the compiler, so the compiler names only `SPAWN_COPY_KINDS` again.
- **The guidance:** [structure.json](../../tools/repo/structure.json) lists `spawn_edits.py` under `compiler families`,
  so the structure test holds that it does not import the compiler (planted: the start commit's `spawn_edits.py`
  fails it, at its import line). [ARCHITECTURE.md](../../ARCHITECTURE.md) says where a shared table goes (a new row),
  how a family takes what it shares with the compiler, and that `spawn_edits.py` is listed. `compiler.py` went from
  5,622 to 5,376 lines, under a twentieth, so its ceiling stands.

Checked, against the start commit recorded in a scratch worktree of it:
- the compile recorder (`compile_record.py`): the same 1,091 calls (822 compiles, 269 native splits) of 369 tests;
- the ten Builds (`build_outputs.py`), quick and baked, the same, both records reading the same exports (2 minutes
  each);
- `moved_code.py`: the 16 moved functions and methods the same; every function left in `compiler.py` the same but
  `Compiler.__init__`, which lost the import; `spawn_edits.py`'s 11 methods the same;
- the moved tables, which `moved_code.py` does not compare: each assignment's syntax tree the base's, and each value
  read by import (the base's `compiler` against `compiler_tables`, `spawn_edits` and the new `compiler`) the same;
  the compiler module's names are the base's less the four spawn tables and `_ground_looks`, which nothing read
  through it;
- `compiler.py --help`, `import spawn_edits` and `import compiler_tables` each alone in a fresh process;
- the editor suite (369 tests), the release suite (15; its module list finds `compiler_tables.py` by import) and the
  repo suite (40).

Left as it was: the Build's manifest hashes `compiler.py` among its tools but neither `spawn_edits.py` nor
`compiler_tables.py`; adding them would change the manifest, so it is not part of a move.
