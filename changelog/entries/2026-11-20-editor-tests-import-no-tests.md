### No editor test imports another: the compiler tests' shared helpers are in editor_fixtures.py

Refactor stage T5 (review finding 58). Five compiler test files imported test_compiler.py for its scene, document and
report helpers, test_compiler_slab_holes.py imported test_compiler_generated.py for its made wall, and
test_spawn_edit_fixtures.py's `--write` made a `test_compiler.CompilerTests` to reach its spawn scene. They are in
[editor_fixtures.py](../../tools/editor/tests/editor_fixtures.py) now, moved verbatim (`moved_code.py`: 15 functions
and methods the same; `SHA`, `PL` and `DONOR_SHA` compared by syntax tree):

- from test_compiler.py: `part`, `scene`, `assembly_scene`, `target`, `document`, `add`, `refused`, `codes`,
  `left_out`, `warned`, `noted`, `SHA`, `PL`, `DONOR_SHA`, and `CompilerTests.mission_scene` and `spawn_scene` as
  the mixin `MissionScenes`, which `CompilerTests` takes as a base and test_spawn_edit_fixtures makes alone;
- from test_compiler_generated.py: `made` and `compiled`.

test_compiler, test_compiler_effects, test_compiler_flags, test_compiler_generated, test_compiler_malformed,
test_compiler_slab_holes and test_spawn_edit_fixtures import them from there; the helpers only test_compiler uses
stay in it.

Checked: the editor suite, 371 tests, the same by name and verdict as before; each changed file run alone
(`unittest discover -p <file>`, and `run_tests.py editor -k <file>`); the compile record (`compile_record.py`) of the
base and of the change, the same: 1096 calls of 371 tests; `test_spawn_edit_fixtures.py --write` writes
spawn_edit_cases.json byte for byte as it was.
