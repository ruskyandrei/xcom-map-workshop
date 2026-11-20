### The install's file paths in a module of their own, so the prefab test's stage no longer loads the Build

`lwr_file` (a file of a game install under `XEW/XComGame`) moved from [build.py](../../tools/editor/build.py) into
[game_files.py](../../tools/editor/game_files.py), unchanged. build.py and
[prefab_stage.py](../../tools/editor/prefab_stage.py) import it from there; prefab_stage imported all of build.py for
those two lines. [build_outputs.py](../../tools/editor/tests/build_outputs.py) reads it there too.

What loads changes, as intended (`python -X importtime`, before and after): `import prefab_stage` loads 15 modules
fewer (build.py and what only it loads: `builds`, `installs`, `outputnames`, `pictures`, `procs`, `publication`,
`spawnrules`, `version` and some standard ones), and the server (`viewer.py`, which imports the prefab tests and so
prefab_stage as it starts) no longer loads build.py, `outputnames` or `unicodedata` as it starts: it runs build.py as a
process, and `projects.py` imports `outputnames` where it checks a project's names. No module uses one of those
names without importing it itself, and the folders on the server's path are the same (prefab_stage and prefab_tests
put the editor's, the viewer's, the bake's and upk's there). The release's module list finds the new module (134
modules, 133 before). [ARCHITECTURE.md](../../ARCHITECTURE.md) names it in the Build's part.

Checked: `moved_code.py`: `lwr_file` the same in its new module, build.py's other 66 functions and prefab_stage's 15
the same; the compile recorder (1,091 calls) and the ten Builds the same as at the stage's start; the editor suite,
the viewer's prefab tests (`-k test_prefab`), the release and repo suites (`test_names`: the new file's name is no
other file's and no standard module's).
