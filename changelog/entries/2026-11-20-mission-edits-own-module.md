### The compiler's map grid, clear, landing zones and missions in a module of their own

Review finding 23, the editor refactor's stage C7: the map grid, the clear, the drop-in rule, the landing zones, the
missions and the spawn places moved out of the `Compiler` class, as the spawn, effects, lights, flags, made pieces'
and buildings families were. A move: nothing the compiler does changes.

- **[mission_edits.py](../../tools/editor/mission_edits.py)** is new. `MissionEdits` holds the family's seventeen
  methods, moved from [compiler.py](../../tools/editor/compiler.py) with their names and bodies unchanged but for
  where they read the compiler (`self.c.`): `stage`, `spawn_rules_mark`, `spawn_rules_notes`, `cleared_mark`,
  `outside_box`, `grid_box`, `stage_outside`, `landing_zones`, `missions_kept`, `kept_missions`, `kept_streams`,
  `missions_check`, `mission_list`, `mission_objects`, `projected_spawns`, `spawn_places` and `check_zones`, with the
  class's `MISSION_REACHED` and `MISSION_SPAWNS`. It owns the state its stages work out, made in its `__init__` with
  the values it keeps when a stage doesn't run: the clear and what it keeps outside the grid (`cleared`,
  `keep_outside`), the drop-in rule (`spawn_rules`), the larger grid (`stage_grid`), and the landing zones and the
  map's own landings (`zones`, `own_landings_found`, `own_count`). It takes what it shares with the compiler from
  [compiler_tables.py](../../tools/editor/compiler_tables.py) and never imports the compiler.
- **The memo:** `missions_kept` made its result the first time it was asked for, read through
  `getattr(self, '_missions_kept', None)` (plan 2.5). The family's `__init__` now sets `_missions_kept` to `None`
  and the method reads it plainly; that is the only change `moved_code.py` finds in it.
- **Its tables and helpers** moved with it: `STAGE_GRID_MAX`, `STAGE_LEVELS_MAX`, `POD_DISTANCE`, and the functions
  `stage_max`, `tidy_zone`, `numbers`, `zone_words` and `scripted_users`. The compiler names again the three that
  others read through it: `STAGE_GRID_MAX`, `STAGE_LEVELS_MAX` (the compiler's tests, the viewer's prefab builder
  test) and `stage_max` (the compiler's tests).
- **The compiler** makes one `MissionEdits` for each `Compiler` (`self.mission_edits`; the map's package, which
  `check_document` works out, stays the compiler's) and asks it for each stage from `run`, in the same order. What
  reads the family's state reads it through it: the cursor's floors (`cursor_storeys`, `grown_storeys`), the floors a
  copy gives and the low scenery the Build makes walkable (`added_floors`, `scenery_floor`), the missions an added
  kind needs (`added_kinds`), `spec` and the report; and in the other families, the lights' (`derive_area_lights`
  reads the clear) and the buildings' (`buildings` reads the larger grid).
- **Two forwarders stay:** `Compiler.stage` and `Compiler.cleared_mark`, one line each, because the compiler's tests
  call them on a `Compiler` by name ([test_compiler.py](../../tools/editor/tests/test_compiler.py): the cursor
  storeys of a taller grid and of a map grown as it is, and a cleared TempleShip's smaller grid). That last test reads
  the larger grid on the compiler, and the test of a moved ladder on grown levels sets it there; they now read and set
  `c.mission_edits.stage_grid` (three lines).
- **Where the plan's list differs from the code:** it does not; "the landings" are `own_landings_found` and
  `own_count`. `landing_actors` and `is_landing` (the map's landing-zone pieces, which `override` reads) stay the
  compiler's.
- **The guidance:** [structure.json](../../tools/repo/structure.json) lists `mission_edits.py` under
  `compiler families`. [ARCHITECTURE.md](../../ARCHITECTURE.md) lists the family, and says that a family's method
  stays on the compiler only as a one-line forwarder for a test or tool that calls it there by name. `compiler.py`
  went from 3,363 to 2,680 lines; its ceiling is left as it is (the size limits become guidance, the coordinator's
  word), so the structure test's file size rule asks for it to be lowered until that change is merged.

Checked, against the start commit of stage C5 (the compile record and the ten Builds recorded in a scratch worktree
of it) and against stage C6's head (the moved code):
- the compile recorder (`compile_record.py`): the same 1,091 calls (822 compiles, 269 native splits) of 369 tests;
- the ten Builds (`build_outputs.py`), quick and baked, the same;
- `moved_code.py`: the seventeen methods and five functions the same (substitutions `self.` to `self.c.`, the seven
  state names, the memo and its `getattr` read, the class's two sets, and the family's own calls back to `self.`); of
  the 87 functions left in `compiler.py`, 84 the same once the call sites' substitutions are made, and
  `Compiler.__init__` (the family in place of its state), `stage` and `cleared_mark` (the forwarders); the lights'
  and the buildings' families the same once their reads are; the 193 functions of `test_compiler.py` the same once
  its three are;
- the moved tables' values, read by import, the same (the two sets compared as sets);
- `import mission_edits` alone in a fresh process, and `compiler.py --help`; every global name the families and the
  compiler read is defined in their modules;
- the editor suite (369 tests), the release suite (15; its module list finds `mission_edits.py` by import), the
  viewer's prefab builder tests (7) and families tests (5); the repo suite's 40 tests, all but the file size rule's,
  which asks for `compiler.py`'s ceiling to be lowered (above).

Left as it was: `spawn_rules_notes` imports `spawnrules` inside the function, as it did (plan 2.x, "no import inside a
function in tools/editor", still to do); [tools/viewer/prefab_bounds.py](../../tools/viewer/prefab_bounds.py) names
`compiler.py STAGE_GRID_MAX` in a comment, which is now `mission_edits.py`'s.
