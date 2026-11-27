### The Build writes a project's fog and grade on the map's WorldInfo

Stage C5a of the game-likeness plan: a project's `atmosphere`, the members it changes of the map's height fog and its
post-process settings ({"fog": {member: value}, "postProcess": {member: value}}, in the export's form), goes through
the compiler and the Build into the variant map. The page's controls and the project schema that carries the record
(schema 10) are stage C5b's; until then a project carries it written by hand.

- **The compiler** (`atmosphere_edits.py`, a family of its own): each value is held to its member's kind. A member the
  struct lacks, one a project does not set (an object, the LUT, an array) or a value of another kind is left out
  (`atmosphere-value`), and the rest builds. A record of another shape is left out whole (`atmosphere-shape`). Where a
  post-process volume of the map overrides a changed member, a warning says so (`atmosphere-volume`), never a refusal.
  The spec's `atmosphere` goes to the native edit (`native_split`); the report counts the members.
- **The Build** (`native_world.py`, a new maker module of the copy tool): each struct of the WorldInfo is made again from
  the members the map saves, with the project's members over them (in place where the map saves one, added where
  not), the rest left to the defaults. A post-process member goes with its override flag on, as the game's editor saves
  it. It is read back after the write, and the manifest's `atmosphere` says what was written and added. No baked
  light changes, so a full Build makes it as it makes effects, with the map's lighting kept.
- **The members' kinds**: `atmosphere_defaults.json` (version 2) now keeps the script packages' declarations of the
  two structs (`kinds`, made with the defaults by `atmosphere.py defaults`, and held to the install by its test). The
  writer and the compiler read them, so a Build needs no script package. The override flag's rule is
  `atmosphere.override_flag`, which XCOM's own fog-of-war members name differently.
- Where: [atmosphere_edits.py](../../tools/editor/atmosphere_edits.py), [compiler.py](../../tools/editor/compiler.py),
  [native_edit.py](../../tools/editor/native_edit.py), [build.py](../../tools/editor/build.py),
  [native_world.py](../../tools/bake/native_world.py), [native_copy.py](../../tools/bake/native_copy.py) (the lane's
  field, its reading, the step, the read-back), [atmosphere.py](../../tools/viewer/atmosphere.py) and
  [atmosphere_defaults.json](../../tools/viewer/atmosphere_defaults.json); EXP-98's project
  [exp98_project.py](../../tools/editor/examples/exp98_project.py), which
  [build_outputs.py](../../tools/editor/tests/build_outputs.py) holds the lane with (input `bar-atmosphere`);
  [structure.json](../../tools/repo/structure.json) and [ARCHITECTURE.md](../../ARCHITECTURE.md) list the family.
- Checked: [test_native_world.py](../../tools/bake/tests/test_native_world.py) (CSmallScout_DirtRoad of the install: the
  density added where the map saved none, a colour changed in place, the map's other members and volumes as they were,
  the flags on; a member the struct lacks changes nothing), [test_compiler_atmosphere.py](../../tools/editor/tests/test_compiler_atmosphere.py),
  the lane's line in [test_native_copy.py](../../tools/bake/tests/test_native_copy.py); quick Builds of URB_Bar with a
  thick red fog and with a green grade, read back by the export's reader.
