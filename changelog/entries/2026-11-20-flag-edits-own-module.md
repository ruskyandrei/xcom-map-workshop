### The compiler's pieces' flags in a module of their own

Review finding 23, the editor refactor's stage C4: the pieces' flags family moved out of the `Compiler` class, as
the spawn, effects and lights families were. A move: nothing the compiler does changes.

- **[flag_edits.py](../../tools/editor/flag_edits.py)** is new. `FlagEdits` holds the family's four methods, moved
  from [compiler.py](../../tools/editor/compiler.py) with their names and bodies unchanged but for where they read
  the compiler (`self.c.`): `flags_valid`, `flag_plan`, `stationary_flags` and `copy_flags`. It owns the family's
  state, made in its `__init__`: the map's own pieces whose flags change where they stand, the spec's `pieceFlags`
  (`edits`, which was the compiler's `flag_edits`), the actors whose floor such an edit takes away or gives
  (`floor_off`, `floor_on`) and the report's counts (`counts`, was `flag_counts`). Its tables, `FLAGS_EXPORT` and
  `FLAGS_WALL`, moved with it; nothing read them through the compiler. It takes what it shares with the compiler
  from [compiler_tables.py](../../tools/editor/compiler_tables.py) and never imports the compiler.
- **The compiler** makes one `FlagEdits` for each `Compiler` (`self.flag_edits`, so the name now holds the family,
  not the list) and checks and builds each record's flags through it from `overrides`, `override`, `added` and
  `add`. Everything else of the compiler that reads the family's state reads it through it: the ladders near a flag
  change (`flag_ladders`, `ladder_climbs`), the floors (`added_floors`, `floor_kept_off`, `floor_records_now`), `spec`
  and the report. Two of those read the state through `getattr` with a default (`getattr(self, 'floor_off', set())`
  in `floor_records_now`, `getattr(self, 'floor_on', {})` in `added_floors`); the compiler's `__init__` always made
  both, so the default was never taken, and they now read `self.flag_edits.floor_off` and `.floor_on`. No method was
  left behind as a forwarder: nothing outside the compiler calls one by name.
- **The guidance:** [structure.json](../../tools/repo/structure.json) lists `flag_edits.py` under
  `compiler families`. `compiler.py` went from 4,442 to 4,321 lines, within a twentieth of its ceiling, so the
  ceiling stands. [ARCHITECTURE.md](../../ARCHITECTURE.md) lists the family.

Checked, against the start commit of stage C2 (the compile record and the ten Builds recorded in a scratch worktree
of it) and against stage C3's head (the moved code):
- the compile recorder (`compile_record.py`): the same 1,091 calls (822 compiles, 269 native splits) of 369 tests;
- the ten Builds (`build_outputs.py`), quick and baked, the same;
- `moved_code.py`: the four methods the same (substitutions `self.` to `self.c.`, the four state names, and
  `flag_plan`'s calls back to `self.`); of the 133 functions left in `compiler.py`, 132 the same once the call
  sites' substitutions are made (the two `getattr` reads among them), and `Compiler.__init__`, which makes the
  family in place of its state;
- the moved tables' values, read by import, the same;
- `import flag_edits` alone in a fresh process, and `compiler.py --help`;
- the editor suite (369 tests), the release suite (15; its module list finds `flag_edits.py` by import) and the
  repo suite (40).
