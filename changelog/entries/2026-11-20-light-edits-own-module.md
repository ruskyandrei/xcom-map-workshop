### The compiler's lights and area lights in a module of their own

Review finding 23, the editor refactor's stage C3: the lights family moved out of the `Compiler` class, as the spawn
and effects families were. A move: nothing the compiler does changes.

- **[light_edits.py](../../tools/editor/light_edits.py)** is new. `LightEdits` holds the family's eleven methods,
  moved from [compiler.py](../../tools/editor/compiler.py) with their names and bodies unchanged but for where they
  read the compiler (`self.c.`): `light_of`, `light_gate`, `submitted_light`, `light_after`, `light_override`,
  `light_add`, `reaching`, `copy_area_light`, `area_bindings`, `derive_area_lights` and `near_unknown`. It owns the
  family's state, made in its `__init__`: the spec's `lights` operations (`ops`, which was `light_ops`), the piece
  edits whose area lights follow (`owner_edits`, which the compiler's `override` and `add` fill), the group member
  keys of the lights the project adds (`members`, was `light_members`), and the base map's pieces' boxes that
  `reaching` makes the first time it needs them (`object_boxes`, which `index_export` used to set empty; it runs once,
  before any light edit, so the family's `__init__` sets it now). It takes what it shares with the compiler from
  [compiler_tables.py](../../tools/editor/compiler_tables.py) and never imports the compiler.
- **Its tables and helpers** moved with it: `LIGHT_KEYS`, `CONE_KEYS`, `LIGHT_RANGES`, `LIGHT_RECIPES`,
  `RECIPE_ACTOR`, `RECIPE_ROTATION`, `AREA_NEAR`, and the functions `light_rule`, `light_values`,
  `light_value_problem`, `reach_box`, `rotator_of` and `moved_light_pose`. The compiler names again the five that
  others read through it: `LIGHT_RECIPES` (`prefab_stage.py`, the viewer's `families.py`, the tests),
  `light_rule` (`families.py`), `LIGHT_RANGES` (the twin constants test), `light_value_problem` (the prefab stage's
  test) and `rotator_of` (the compiler's tests). The export check every project with edits needs
  (`light_metadata_problem`, `LIGHT_METADATA`) stays in the compiler, whose `run` makes it.
- **The compiler** makes one `LightEdits` for each `Compiler` (`self.light_edits`) and hands it each light record
  from `overrides` and `added`, a piece of another map's area lights from `add` (`copy_area_light`), and the area
  lights' derivation from `run`; `override` and `add` record the piece edits in its `owner_edits`, and `groups`,
  `spec` and the report read its state through it. No method was left behind as a forwarder: nothing outside the
  compiler calls one by name.
- **Where the plan's list differs from the code:** `donor_area_lights` (the area lights of each piece of another map,
  which `foreign_piece` records and `add` reads) stays the compiler's: no method of the family reads it. The section
  header over the area lights now names `groups`, the one method left under it.
- **The guidance:** [structure.json](../../tools/repo/structure.json) lists `light_edits.py` under
  `compiler families`, and `compiler.py`'s ceiling is lowered to its new size, 4,442 lines (from 4,924).
  [ARCHITECTURE.md](../../ARCHITECTURE.md) lists the family.

Checked, against the start commit of stage C2 (the compile record and the ten Builds recorded in a scratch worktree
of it) and against stage C2's head (the moved code):
- the compile recorder (`compile_record.py`): the same 1,091 calls (822 compiles, 269 native splits) of 369 tests;
- the ten Builds (`build_outputs.py`), quick and baked, the same;
- `moved_code.py`: the eleven methods and six functions the same (substitutions `self.` to `self.c.`, the four state
  names, and the family's own calls back to `self.`); of the 137 functions left in `compiler.py`, 135 the same once
  the call sites' substitutions are made, and `Compiler.__init__` (the family in place of its state) and
  `index_export` (without `object_boxes`);
- the moved tables' values, read by import, the same;
- `import light_edits` alone in a fresh process, and `compiler.py --help`;
- the editor suite (369 tests), the release suite (15; its module list finds `light_edits.py` by import) and the
  repo suite (40).

Left as it was: `submitted_light` imports `storable_cone` from the viewer's `lights` inside the function, as it did.
