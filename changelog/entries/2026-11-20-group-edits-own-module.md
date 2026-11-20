### The compiler's groups in a module of their own

Review finding 23, the editor refactor's stage C8: the user's groups (which of them break together, and what of each
breaks with it) moved out of the `Compiler` class, as the spawn, effects, lights, flags, made pieces', buildings' and
missions' families were. A move: nothing the compiler does changes.

- **[group_edits.py](../../tools/editor/group_edits.py)** is new. `GroupEdits` holds the family's one method,
  `groups`, moved from [compiler.py](../../tools/editor/compiler.py) with its name and body unchanged but for where it
  reads the compiler (`self.c.`). It owns the state `groups` writes, made in its `__init__`: each copy's break group
  (`break_copies`), the map's own pieces left in place that break with a group (`break_originals`), each made wall's
  break group (`break_walls`) and the report's groups (`report`, which was the compiler's `group_report`). The
  compiler's `spec` reads the first three through it, and its report the last. It takes what it shares with the
  compiler from [compiler_tables.py](../../tools/editor/compiler_tables.py) and never imports the compiler.
- **Its tables and helper** moved with it: `BREAKABLE`, `BREAKING_COVERS` and `member_key`. The compiler names
  `member_key` again, which the compiler's tests read through it.
- **The compiler** makes one `GroupEdits` for each `Compiler` (`self.group_edits`) and asks it for the groups from
  `run`, in the same place. What `groups` writes into the compiler's own state is written there as before: a cover
  block's `breakGroup` (the compiler's cover blocks, from `cover_add`) and its entity's class. No method was left
  behind as a forwarder: nothing outside the compiler calls `groups` by name.
- **Where the plan's list differs from the code:** the plan names three pieces of state; `break_walls` is a fourth.
  The plan's table put it with the made pieces, whose stage (C5) left it on the compiler because no method of theirs
  reads or writes it; `groups` alone writes it and `spec` reads it, as `break_copies`. The two `break_` names keep
  their names (their prefix is not the family's).
- **A known bug lives here and was moved as it is:** [KNOWN-BUGS.md](../../KNOWN-BUGS.md) KB-1 (F-143: a cover block
  grouped with a made wall keeps its cover when the wall is destroyed).
- **The guidance:** [structure.json](../../tools/repo/structure.json) lists `group_edits.py` under
  `compiler families` (planted: an `import compiler` in it fails the structure test), and
  [ARCHITECTURE.md](../../ARCHITECTURE.md) lists the family; so does `compiler_tables.py`'s docstring. `compiler.py`
  went from 2,680 to 2,495 lines.

Checked, against `editor-refactor` at the start of stage C8 (the compile record and the ten Builds recorded in a
scratch worktree of it):
- the compile recorder (`compile_record.py`): the same 1,091 calls (822 compiles, 269 native splits) of 369 tests;
- the ten Builds (`build_outputs.py`), quick and baked, the same;
- `moved_code.py`: `groups` and `member_key` the same (substitutions `self.` to `self.c.`, and the four state names
  back to the family's own); of the 85 functions left in `compiler.py`, 84 the same once the call sites' substitutions
  are made, and `Compiler.__init__`, which makes the family in place of its state;
- the moved tables' values, read by import from the start commit's `compiler` and from `group_edits`, the same;
- `import group_edits` alone in a fresh process, and `compiler.py --help`;
- the editor suite (369 tests), the release suite (15; its module list finds `group_edits.py` by import) and the repo
  suite (37).
