### The compiler's buildings in a module of their own

Review finding 23, the editor refactor's stage C6: the buildings family moved out of the `Compiler` class, as the
spawn, effects, lights, flags and made pieces' families were. A move: nothing the compiler does changes.

- **[building_edits.py](../../tools/editor/building_edits.py)** is new. `BuildingEdits` holds the family's four
  methods, moved from [compiler.py](../../tools/editor/compiler.py) with their names and bodies unchanged but for where
  they read the compiler (`self.c.`): `map_buildings`, `building_records`, `buildings` and `new_building`. It owns the
  family's state, made in its `__init__`: the buildings made from nothing (`new_buildings`, the spec's `buildings`
  object), the map's own buildings changed or deleted (`edits`, the spec's `buildingEdits` object, which was the
  compiler's `building_edits`: that name now holds the family), and the sources whose buildings `new_building` matches
  a building's floors against (`floor_sources`, which the compiler's `add` writes, and `donor_buildings`, which its
  `foreign_piece` writes). It takes what it shares with the compiler from
  [compiler_tables.py](../../tools/editor/compiler_tables.py) and never imports the compiler.
- **The memos:** `map_buildings` and `building_records` made their results the first time they were asked for, read
  through `getattr(self, '_map_buildings', None)` and `getattr(self, '_building_records', None)` (review finding 23,
  plan 2.5). The family's `__init__` now sets both to `None`, and the two methods read them plainly; that is the only
  change `moved_code.py` finds in them.
- **Its tables and helpers** moved with it: `BUILDING_SHAPE`, `BUILDING_KINDS`, `BUILDING_FLOORS_MAX`,
  `BUILDING_OVERLAP`, `BUILDING_SAME`, `CURSOR_NEAR`, and the functions `building_well_formed`, `source_floor_match`
  and `moved_whole`. `CURSOR_NEAR` was assigned on one line with `CURSOR_STOREY` and `CURSOR_STOREYS`, which the
  cursor's floors read and which stay the compiler's: the line is now two, one in each module, with the same values.
  The compiler names again the three that others read through it: `BUILDING_FLOORS_MAX` (the viewer's prefab builder
  test), `source_floor_match` and `moved_whole` (the compiler's tests).
- **The compiler** makes one `BuildingEdits` for each `Compiler` (`self.building_edits`) and asks it for the
  buildings from `run`; the floors (`floor_boxes_now`) and `groups` ask it for the records and the map's buildings;
  `add` and `foreign_piece` record the sources in its state; `spec`, `mission_list` and the report read its
  `new_buildings` and `edits`, and so does the made pieces' family (`made_slabs_in_floors`). No method was left behind
  as a forwarder: nothing outside the compiler calls one by name.
- **Where the plan's list differs from the code:** it does not. The map's building names by id (`building_names`,
  which `index_export` makes and the effects family reads) stay the compiler's.
- **The guidance:** [structure.json](../../tools/repo/structure.json) lists `building_edits.py` under
  `compiler families`. [ARCHITECTURE.md](../../ARCHITECTURE.md) lists the family. `compiler.py` went from 3,713 to
  3,363 lines; its ceiling is left as it is (the size limits become guidance, the coordinator's word), so the
  structure test's file size rule asks for it to be lowered until that change is merged.

Checked, against the start commit of stage C5 (the compile record and the ten Builds recorded in a scratch worktree
of it) and against stage C5's head (the moved code):
- the compile recorder (`compile_record.py`): the same 1,091 calls (822 compiles, 269 native splits) of 369 tests;
- the ten Builds (`build_outputs.py`), quick and baked, the same;
- `moved_code.py`: the four methods and three functions the same (substitutions `self.` to `self.c.`, the four state
  names and two memos, the two `getattr` reads, and the family's own calls back to `self.`); of the 107 functions left
  in `compiler.py`, 106 the same once the call sites' substitutions are made, and `Compiler.__init__`, which makes the
  family in place of its state; the made pieces' family's 20 functions the same once its reads of the buildings are;
- the moved tables' values, read by import, the same, and the cursor's two that stayed;
- `import building_edits` alone in a fresh process, and `compiler.py --help`;
- the editor suite (369 tests), the release suite (15; its module list finds `building_edits.py` by import), the
  viewer's prefab builder tests (7) and made pieces' tests (20); the repo suite's 40 tests, all but the file size
  rule's, which asks for `compiler.py`'s ceiling to be lowered (above).

Left as it was: [tools/bake/buildings.py](../../tools/bake/buildings.py) names `compiler.source_floor_match` and
`compiler.BUILDING_SAME` in comments; both are now `building_edits`' (the compiler still names the first).
