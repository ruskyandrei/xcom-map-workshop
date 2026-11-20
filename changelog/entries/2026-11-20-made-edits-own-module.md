### The compiler's made walls, floors, roofs and ground shapes in a module of their own

Review finding 23, the editor refactor's stage C5: the made pieces' family moved out of the `Compiler` class, as the
spawn, effects, lights and flags families were. A move: nothing the compiler does changes.

- **[made_edits.py](../../tools/editor/made_edits.py)** is new. `MadeEdits` holds the family's thirteen methods,
  moved from [compiler.py](../../tools/editor/compiler.py) with their names and bodies unchanged but for where they
  read the compiler (`self.c.`): `generated_valid`, `ground_valid`, `slab_valid`, `join_made_walls`,
  `made_walls_stacked`, `made_slab_wholes`, `made_slab_boxes`, `made_slab_cursors`, `made_slabs_in_floors`,
  `made_wall_openings`, `blasts_valid`, `made_pieces` and `split_made`. It owns the family's state, made in its
  `__init__`: the made copies the compiler's `add` records for the family's checks (`walls`, `parts`, `slabs` and
  `wholes`, which were the compiler's `made_walls`, `made_parts`, `made_slabs` and `made_wholes`) and the blasts of
  each cut piece's whole (`broken_wholes`, which `split_made` writes and `add` reads). It takes what it shares with the
  compiler from [compiler_tables.py](../../tools/editor/compiler_tables.py) and never imports the compiler.
- **Its tables and helpers** moved with it: `FRAC_WALL_MIN_LENGTH`, `FRAC_WALL_LOOKS`, `FRAC_SLAB_MAX_TILES`,
  `MADE_MAX_TILES`, `MADE_MAX_STOREYS`, `GROUND_SHAPES`, `GROUND_ROCK_SEEDS`, `GROUND_MAX_HEIGHT`, `GROUND_MAX_TILES`,
  `GENERATED_VERSIONS`, `DONOR_LOOK_SINCE`, `PLAIN_VERSION`, `POINTS_VERSION`, `WALL_SWEEPS`, `WALL_JOIN_REACH`,
  `WALL_JOIN_FLOOR`, `WALL_STACK_GAP`, and the functions `wall_look_storeys`, `look_valid`, `opening_play`,
  `wall_joins`, `opening_box` and `overlaps_by`. The compiler names again the six that others read through it:
  `FRAC_WALL_MIN_LENGTH` (the bake suite's agreement test), `FRAC_SLAB_MAX_TILES` (an example's generator),
  `FRAC_WALL_LOOKS`, `WALL_SWEEPS`, `opening_play` and `wall_joins` (the compiler's tests). It keeps `import looks`,
  which it no longer uses itself, for the tests that patch the catalogue's folder through `compiler.looks`; it no
  longer imports `ground`, `made_blasts` or `made_split`. What `add` reads stays the compiler's:
  `FRAC_SLAB_DEFAULT_LOOK`, `slab_heights`, `GROUND_DEFAULT_LOOK`, `GROUND_CLASSES`, `GROUND_SLOPED`, `GROUND_STEEP`,
  `PATCH_LIFT`, `ground_thickness`, `ground_box`, `ground_slope`, `blast_words` and `battle_words`.
- **The compiler** makes one `MadeEdits` for each `Compiler` (`self.made_edits`). `added` checks each record's
  `generated` through it, `overrides` and `add` each record's blasts; `add` asks it to cut a made piece
  (`made_pieces`, `split_made`) and records the made copies in its state; `run` asks it for the checks; the cursor's
  floors read its slabs (`with_made_slabs`). That last read was `getattr(self, 'made_slabs', None)`; the compiler's
  `__init__` always made the list, so the default was never taken, and it now reads `self.made_edits.slabs`. No method
  was left behind as a forwarder: nothing outside the compiler calls one by name.
- **Where the plan's list differs from the code:** `blast_edits` (the map's own pieces broken where they stand, which
  `overrides` writes and `spec` reads) and `break_walls` (a made wall's break group, which `groups` writes and `spec`
  reads) stay the compiler's: no method of the family reads or writes them. The stale section header over the
  family's methods ("pieces' flags", left when that family moved) went with them.
- **The guidance:** [structure.json](../../tools/repo/structure.json) lists `made_edits.py` under
  `compiler families` (planted: an `import compiler` in it fails the structure test), and `compiler.py`'s ceiling is
  lowered to its new size, 3,713 lines (from 4,442; it was 4,321). [ARCHITECTURE.md](../../ARCHITECTURE.md) lists the
  family.

Checked, against the start commit of stage C5 (the compile record and the ten Builds recorded in a scratch worktree
of it):
- the compile recorder (`compile_record.py`): the same 1,091 calls (822 compiles, 269 native splits) of 369 tests;
- the ten Builds (`build_outputs.py`), quick and baked, the same;
- `moved_code.py`: the thirteen methods and six functions the same (substitutions `self.` to `self.c.`, the five state
  names, and the family's own calls back to `self.`); of the 114 functions left in `compiler.py`, 113 the same once
  the call sites' substitutions are made (the `getattr` read among them), and `Compiler.__init__`, which makes the
  family in place of its state;
- the moved tables' values, read by import from the start commit's `compiler` and from `made_edits`, the same, and
  the tables that stayed;
- `import made_edits` alone in a fresh process, and `compiler.py --help`;
- the editor suite (369 tests), the release suite (15; its module list finds `made_edits.py` by import), the repo
  suite (40), the viewer's made pieces' tests (`test_generated`, 20) and twin constants (3), and the bake suite's test
  that reads `compiler.FRAC_WALL_MIN_LENGTH`.

Left as it was: [tools/viewer/prefabs.py](../../tools/viewer/prefabs.py) names `compiler.generated_valid` in a
comment, which is now `made_edits.generated_valid`.
