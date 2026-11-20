### A Build's manifest names every module of the compile among the tools that made it

The manifest's `tools` record ([build.py](../../tools/editor/build.py): each file of the code that made the Build,
with its SHA-256, by its path in the repository; nothing acts on it, and a map pack's copy of the manifest carries it
as it is, `manager.PUBLIC_MANIFEST`: it says which code made a package) named `compiler.py` but none of the modules the
compiler has been split into. It now names build.py first and then, by name, every module of `tools/editor` that
build.py imports, and those modules' own (`editor_modules`): `compiler.py`, `compiler_tables.py`, the nine edit
families' modules (`spawn_edits.py` to `floor_edits.py`), `game_files.py`, `native_edit.py` and `piece_lookup.py`, 15
files with build.py. They are found from their import statements, as the release finds its modules, so a module split off later is
named with no list to keep. The tools of `tools/bake` and `tools/upk` that follow are build.py's list as before. Reading
the imports takes about a tenth of a second at the package stage. [ARCHITECTURE.md](../../ARCHITECTURE.md) says what
`tools` holds.

Checked: a new test, `test_the_manifest_names_every_module_of_the_compile`
([test_build.py](../../tools/editor/tests/test_build.py)), which fails with the old record: build.py first, the
compiler's tables, families, native edit and piece lookup and `game_files` named with their hashes, the prefab
test's stage not. The ten Builds (`build_outputs.py`, which masks the record's hashes and keeps its names) differ from
the stage's start in that record alone: in each of the twenty manifests, the 13 names added; nothing else in any
manifest, package file, compile report or work record. The compile recorder: the 1,091 calls of the 369 tests before
the same, and one call more, the new test's. The editor suite (370 tests).
