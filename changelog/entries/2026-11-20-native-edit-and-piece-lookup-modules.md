### The native split and the compiler's piece library in modules of their own

Review finding 23, the editor refactor's stage C10: the two parts of `compiler.py` that are no edit family moved out
of it, as the families were. A move: nothing the compiler does changes.

- **[native_edit.py](../../tools/editor/native_edit.py)** is new. It holds `native_split(spec)`, the native edit's
  maker and a function of the spec alone, moved from [compiler.py](../../tools/editor/compiler.py) with its body
  unchanged, and the table it reads, `NATIVE_CLASSES` (the classes whose copies the Build makes in the map), which
  the compiler's `piece` reads too. It imports nothing.
- **[piece_lookup.py](../../tools/editor/piece_lookup.py)** is new. It holds `Library`, the library of other maps'
  pieces as the compiler asks it, moved with its four methods unchanged. It takes `LibraryError` (in
  [compiler_tables.py](../../tools/editor/compiler_tables.py) since stage C1) and `short` from `compiler_tables`, so
  it never imports the compiler. The names of both modules are checked against `test_names.py` (no two tracked
  Python files share a name, none takes a standard or installed module's).
- **The compiler names all three again** at its top (`compiler.native_split`, `compiler.NATIVE_CLASSES`,
  `compiler.Library`), so nothing that reads them changes: the Build ([build.py](../../tools/editor/build.py)), the
  prefab stage ([prefab_stage.py](../../tools/editor/prefab_stage.py)), the compiler's command line, the tests, the
  examples' generators (two of which swap `compiler.Library` for a stand-in), and the compile recorder
  ([compile_record.py](../../tools/editor/tests/compile_record.py)), which wraps `compiler.native_split` and still
  records every call (269 native splits among its 1,091 calls). One test (test_compiler's offset component) patches
  `compiler.NATIVE_CLASSES`: what it tests, the compiler's `piece`, still reads that name; `native_split` reads its own
  module's, and the recorded native splits of that test's compiles are the same as before.
- **Where the plan's list differs from the code:** `NATIVE_CLASSES` is not named in the plan; it goes with
  `native_split`, which reads it, and the compiler takes it from there, as it takes `SPAWN_COPY_KINDS` from its
  family. `stream_only`, another function of the spec, stays the compiler's (the plan names only `native_split`).
  The `Library`'s imports of `library` and `projects` stay inside its methods, as they were (the next change says why).
- **The guidance:** [ARCHITECTURE.md](../../ARCHITECTURE.md) says where `native_split` and the piece library now live
  (section 1's compiler and native edit paragraphs, and the rule on a new lane), and section 2 gains a row for a piece
  lookup and names `native_edit.py` in the row for a lane of the native edit. Neither module is an edit family, so
  neither is listed under `compiler families` in [structure.json](../../tools/repo/structure.json). `compiler.py`
  went from 2,200 to 1,969 lines.

Checked, against `editor-refactor` at the start of stage C8 (the compile record and the ten Builds recorded in a
scratch worktree of it) and against stage C9's head (the moved code):
- the compile recorder (`compile_record.py`): the same 1,091 calls (822 compiles, 269 native splits) of 369 tests;
- the ten Builds (`build_outputs.py`), quick and baked, the same;
- `moved_code.py`: `native_split` and the four methods of `Library` the same, with no substitution (and the class's
  docstring); the 69 functions left in `compiler.py` the same;
- `NATIVE_CLASSES`' value, read by import from the start commit's `compiler` and from `native_edit`, the same, and
  `compiler.native_split`, `compiler.NATIVE_CLASSES`, `compiler.Library` and `compiler.LibraryError` the moved
  modules' own objects;
- `import native_edit` and `import piece_lookup` each alone in a fresh process, and `compiler.py --help`; every global
  name the three modules read is defined in them;
- the editor suite (369 tests), the release suite (15; its module list finds both modules by import), the repo suite
  (37, `test_names` among them), and the viewer's tests that use the compiler: `test_library` (29),
  `test_prefab_builder` (7), `test_twin_constants` (3), `test_piece_flags` (27), `test_prune` (6) and
  `test_damaged_inputs` (6).
