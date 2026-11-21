### The Build's manifest names every module of the tools it runs; `Build.compiled` goes

- **The manifest's `tools`** (each file of the code that made a package, with its SHA-256) took tools/bake's and
  tools/upk's from a hand list of 15, which left out the shell (which the Build runs itself), the copy tool's makers
  (cover blocks, buildings, spawns, the made pieces' modules) and the relight's own modules (shadow maps, shadows,
  bounce, the lightmap encoder). They are now found from the imports of the tools the Build runs (the copy tool, the
  relight, the intro and stream copies, the transplant, the shell) and of build.py itself (the seeder, the named
  copy's growing writer, the map picture's writer, the inline lighting), by the walk the record already made for
  tools/editor's modules ([build.py](../../tools/editor/build.py) `imported_modules`, `tool_modules`): 55 modules
  where there were 15, all 15 among them. The walk reads each file's statements (imports in functions too) without
  walking every expression, and is made once a process: 0.27 s for both walks of a Build (0.11 s was the editor's
  alone), and the editor suite no longer walks once for each of its hundred Builds (19 s before, 11 s after; other
  agents were working on the computer, so the times are rough). The constants only the hand list used
  (`NATIVE_LIGHTS`, `LIGHT_FACTORY`, `INLINE_LIGHTING`, `MAP_FRAME`) go. Nothing reads the record (a map pack copies
  it), so only the record changes.
- **`Build.compiled`,** set in the compile stage and never read, goes (follow-ups 3.2).
- [ARCHITECTURE.md](../../ARCHITECTURE.md)'s paragraph on the manifest says how its `tools` are found.

Checked: a new test in [test_build.py](../../tools/editor/tests/test_build.py), failing before, holds that the
manifest names the shell, the copy tool's makers, the relight's modules and the package tools' (decomp, upkinfo, the
growing writer, the seeder) with their hashes, and no module none of the tools imports; tools/editor's list is the
same as before (compared); the editor suite (376 tests); `build_outputs.py` against the stage's start: the manifests'
`tools` names differ (40 added), nothing else.
