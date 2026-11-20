### The compiler's floors in a module of their own

Review finding 23, the editor refactor's stage C9: the floor a project leaves and the floors its pieces are checked
against moved out of the `Compiler` class, the last of the families of the plan's table. A move: nothing the compiler
does changes.

- **[floor_edits.py](../../tools/editor/floor_edits.py)** is new. `FloorEdits` holds the family's fifteen methods,
  moved from [compiler.py](../../tools/editor/compiler.py) with their names and bodies unchanged but for where they
  read the compiler (`self.c.`): the cursor's floors (`cursor_storeys`, `with_made_slabs`, `grown_storeys`), the floor
  the project's flat pieces give (`added_floors`, `floor_headroom`), ladders' climbs (`ladder_ends`, `ladder_climbs`,
  `flag_ladders`), the building floor a copy stands in (`floor_at`, `floor_boxes_now`, `floor_note`), and the map's
  low scenery made walkable and its floor tiles still there (`scenery_floor`, `floor_kept_off`, `floor_now`,
  `floor_records_now`). It owns `ladder_jobs` (the moved and copied ladders whose climb is still to be checked, which
  the compiler's `override` and `add` fill through it), made in its `__init__`. It takes what it shares with the
  compiler from [compiler_tables.py](../../tools/editor/compiler_tables.py) and never imports the compiler.
- **The memo:** `floor_boxes_now` made its result the first time it was asked for, read through
  `getattr(self, '_floor_boxes_now', None)` (plan 2.5). The family's `__init__` now sets `_floor_boxes_now` to `None`
  and the method reads it plainly; that is the only change `moved_code.py` finds in it. It was the last memo of the
  compiler read through `getattr`.
- **Its tables** moved with it: `SCENERY_LOW`, `CURSOR_STOREY`, `CURSOR_STOREYS` and `FLOOR_NOTE`; nothing reads them
  through the compiler. `made_cursors`, which only `with_made_slabs` uses, is now imported by the family, not the
  compiler. What the compiler's `index_export` reads (the map's floor tiles, `floors`, and its building floors' boxes,
  `floor_boxes`) stays the compiler's: the family and the buildings' family read it there.
- **The compiler** makes one `FloorEdits` for each `Compiler` (`self.floor_edits`) and asks it for the ladders' climbs
  and the headroom warning from `run`, in the same places; `override` and `add` ask it for a copy's floor note and
  hand it their ladders; `spec` asks it for the map's ladders near a flags edit. The other families ask it in place of
  the compiler: the buildings' for the cursor's floors, the missions' for the floor the project leaves, the effects'
  for the building floors as the project has them, and the made pieces' for the floor tiles still there.
- **Four forwarders stay**, one line each, because tests and tools call them on a `Compiler` by name:
  `Compiler.cursor_storeys` ([test_compiler.py](../../tools/editor/tests/test_compiler.py): two tests of the cursor's
  floors), `Compiler.added_floors` (test_compiler.py, [test_compiler_flags.py](../../tools/editor/tests/test_compiler_flags.py)
  and the example [exp72_project.py](../../tools/editor/examples/exp72_project.py)), `Compiler.floor_now`
  (test_compiler_flags.py, exp72_project.py and [exp72_sp7_project.py](../../tools/editor/examples/exp72_sp7_project.py),
  which the ten Builds run) and `Compiler.floor_kept_off` (test_compiler_flags.py).
- **Where the plan's list differs from the code:** it does not; "the floor memos" are now one, `_floor_boxes_now`
  (the others went with the buildings' and missions' families). `hide_helpers`, which sits among the ladders' methods
  but is called by `override`, stays the compiler's.
- **The guidance:** [structure.json](../../tools/repo/structure.json) lists `floor_edits.py` under
  `compiler families` (planted: an `import compiler` in it fails the structure test).
  [ARCHITECTURE.md](../../ARCHITECTURE.md) lists the family, and its paragraph on the compiler now says what the
  `Compiler` class keeps once the families are out (the gates, copy resolution with the assemblies and the grid rule,
  cover blocks, `spec`, `run` and the diagnostics). The family modules' docstrings that named the moved methods as the
  compiler's (`building_edits.py`, `mission_edits.py`, `made_edits.py`) and `compiler_tables.py`'s say where they are.
  `compiler.py` went from 2,495 to 2,200 lines.

Checked, against `editor-refactor` at the start of stage C8 (the compile record and the ten Builds recorded in a
scratch worktree of it) and against stage C8's head (the moved code):
- the compile recorder (`compile_record.py`): the same 1,091 calls (822 compiles, 269 native splits) of 369 tests;
- the ten Builds (`build_outputs.py`), quick and baked, the same;
- `moved_code.py`: the fifteen methods the same (substitutions `self.` to `self.c.`, the family's own calls and state
  back to `self.`, and the memo's `getattr` read); of the 74 functions left in `compiler.py`, 69 the same once the
  call sites' substitutions are made, and `Compiler.__init__` (the family in place of `ladder_jobs`) and the four
  forwarders; the buildings', missions', effects' and made pieces' families' 64 functions the same once their calls
  are;
- the moved tables' values, read by import from the start commit's `compiler` and from `floor_edits`, the same;
- `import floor_edits` alone in a fresh process, and `compiler.py --help`; every global name the families and the
  compiler read is defined in their modules;
- the editor suite (369 tests), the release suite (15; its module list finds `floor_edits.py` by import) and the repo
  suite (37).

Left as it was: [tools/viewer/README.md](../../tools/viewer/README.md) names `compiler.py cursor_storeys`, which is
now `floor_edits.py`'s.
