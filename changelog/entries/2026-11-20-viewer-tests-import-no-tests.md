### No viewer test imports another: the helpers they shared are in viewer_fixtures.py

Refactor stage T5 (review finding 58). Thirteen viewer test files imported other test files for helpers: test_play's
game installs (by name, so its tests would not run twice), test_manager's, test_prefabs', test_resolver's scene,
test_builds' build.py stand-in, test_effects_metadata's install records and test_pictures' picture. Each helper is in
[viewer_fixtures.py](../../tools/viewer/tests/viewer_fixtures.py) now, moved verbatim (`moved_code.py` for the
functions and methods; the constants and the install block compared by syntax tree), and no viewer test file
imports another:

- **The temporary game installs** (test_play's `Play.setUp`, `player`, `package`, `files`, `records`, `settle`, with
  `game_folder`, `VARIANT`, `MUTATOR_LOADER`, `RANDOM_SPAWNS` and `SLOT`) are the mixin `PlayInstalls`; test_play's
  `Play` and test_manager's `Manager` take them as a base, and test_install_recovery, test_pack_export,
  test_pack_scripts and test_squad_play take them method by method as before.
- **The manager's and the packs' helpers** (test_manager's `more_missions`, `second`, `card_game`, `run_script_with`,
  `run_script`, `pack_env`, `powershell_report`) are `ManagerInstalls(PlayInstalls)` and its module's functions. The
  second project's id and variant, test_manager's `OTHER_ID` and `OTHER`, are `SECOND_ID` and `SECOND_VARIANT` there
  (the fixtures' `OTHER` is another project id); `second` names them so, the one substitution, and the tests import
  them under their old names.
- **test_prefabs' prefab and server** (`prefab`, `LIGHT`, `RouteTests.setUp` and `call`) are `prefab` and the mixin
  `PrefabServer`; `prefab` reads the prefab schema as `prefabs.SCHEMA`, the fixtures' `SCHEMA` being the project's.
  test_prefabs takes `ID`, `OTHER` and `PL` from the fixtures, whose values are the same.
- `STANDIN` (with `VIEWER`), `scene`, the install's effect `records` (with `INSTALL`, `WHY`), and `png`.

Checked: the viewer suite, 639 tests, the same tests by name and verdict as before the change; each changed test
file run alone (`unittest discover -p <file>`, and `run_tests.py viewer -k <file>`), so none needs its neighbours.
