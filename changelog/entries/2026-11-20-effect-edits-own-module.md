### The compiler's effects, sounds and lens flares in a module of their own

Review finding 23, the editor refactor's stage C2: the effects family moved out of the `Compiler` class, as the spawn
family was. A move: nothing the compiler does changes.

- **[effect_edits.py](../../tools/editor/effect_edits.py)** is new. `EffectEdits` holds the family's twelve methods,
  moved from [compiler.py](../../tools/editor/compiler.py) with their names and bodies unchanged but for where they
  read the compiler (`self.c.`): `effect_of`, `effect_values`, `effect_parameters`, `effect_value_warnings`,
  `effect_gate`, `effect_usable`, `effect_listing`, `effect_floor_note`, `effect_script`, `effect_override`,
  `effect_add` and `foreign_effect`. It owns the family's state, made in its `__init__`: the spec's `effects`,
  `sounds` and `flares` operations (`ops`, which was `effect_ops`), the group member keys of the copies (`members`,
  was `effect_members`) and the effects a record of the project's own takes from their piece (`own`, was
  `effect_own`). It takes what it shares with the compiler from
  [compiler_tables.py](../../tools/editor/compiler_tables.py) and never imports the compiler.
- **Its tables** moved with it: `EFFECTS_EXPORT`, `EFFECT_CLASSES`, `EFFECT_WORDS`, `EFFECT_SLACK`,
  `EFFECT_VALUE_KEYS`, `EFFECT_FOLLOW`, `EFFECT_SCALE`, `PARAMETER_MAX`, `SOUND_RADIUS_MAX`, `SOUND_VOLUME_MAX`,
  `SOUND_PITCH`, `PARAMETER_TYPES` and `DISTRIBUTION_TYPES`. The compiler names again the six that others read
  through it (`EFFECT_WORDS` for `prefab_stage.py`; `EFFECT_SCALE`, `PARAMETER_MAX` and the three `SOUND_*` for the
  viewer's twin constants test). `EFFECT_LANES` stays in the compiler, which alone reads it (the spec and the
  report).
- **The compiler** makes one `EffectEdits` for each `Compiler` (`self.effect_edits`) and hands it each effect record
  from `overrides` and `added`; `groups`, `spec` and the report read its state through it
  (`self.effect_edits.members`, `.ops`, `.own`). No method was left behind as a forwarder: nothing outside the
  compiler calls one by name. The export's effects by key (`effect_actors`) stay the compiler's (`index_export` makes
  them, `groups` reads them too).
- **The tests:** [test_compiler_effects.py](../../tools/editor/tests/test_compiler_effects.py) switched a family off
  by swapping `compiler.FAMILIES` (`mock.patch.object`) in six places; they now change the one shared dict in place
  (`mock.patch.dict(compiler.FAMILIES, ...)`), which reaches every module that reads it, the family's among them.
- **The guidance:** [structure.json](../../tools/repo/structure.json) lists `effect_edits.py` under
  `compiler families` (planted: an `import compiler` in it fails the structure test), and `compiler.py`'s ceiling is
  lowered to its new size, 4,924 lines (from 5,376). [ARCHITECTURE.md](../../ARCHITECTURE.md) lists the families in
  modules of their own, and says that the compiler holds a family as an attribute named as its module and reads the
  family's state through it.

Checked, against the start commit recorded in a scratch worktree of it:
- the compile recorder (`compile_record.py`): the same 1,091 calls (822 compiles, 269 native splits) of 369 tests;
- the ten Builds (`build_outputs.py`), quick and baked, the same (about two minutes each);
- `moved_code.py`: the twelve methods the same (substitutions `self.` to `self.c.`, the three state names, and the
  family's own calls back to `self.`); of the 154 functions left in `compiler.py`, 153 the same once the call sites'
  substitutions are made, and `Compiler.__init__`, which makes the family in place of its three state attributes;
- the moved tables' values, read by import from the start commit's `compiler` and from `effect_edits`, the same;
- `import effect_edits` alone in a fresh process, and `compiler.py --help`;
- the editor suite (369 tests), the release suite (15; its module list finds `effect_edits.py` by import) and the
  repo suite (40).

Left as it was: [research/editor-contracts.md](../../research/editor-contracts.md) names `compiler.py`
`effect_override`, `effect_add` and `foreign_effect`, which are now in `effect_edits.py`.
