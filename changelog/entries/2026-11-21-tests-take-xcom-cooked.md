### Every test that reads the install's maps takes the folder XCOM_COOKED names

Twelve tests read the install's CookedPCConsole from the settings directly (`settings.lwr_cooked()`), so naming
another install's folder in `XCOM_COOKED` did not reach them and pointing every test at another install needed a
settings file (follow-up 4.2). They now take it through the one helper that honours the variable,
[labpaths.py](../../tools/lab/labpaths.py) (`install_map`, `test_file`, `lwr_cooked`):
[test_area_light_bindings.py](../../tools/viewer/tests/test_area_light_bindings.py),
[test_collision.py](../../tools/viewer/tests/test_collision.py),
[test_destruction.py](../../tools/viewer/tests/test_destruction.py), [test_lights.py](../../tools/viewer/tests/test_lights.py),
[test_links.py](../../tools/viewer/tests/test_links.py),
[test_material_rules.py](../../tools/viewer/tests/test_material_rules.py) (which read the variable itself),
[test_pictures.py](../../tools/viewer/tests/test_pictures.py),
[test_piece_flags.py](../../tools/viewer/tests/test_piece_flags.py),
[test_spawnrules.py](../../tools/viewer/tests/test_spawnrules.py),
[test_spawn_metadata.py](../../tools/viewer/tests/test_spawn_metadata.py),
[test_streams.py](../../tools/viewer/tests/test_streams.py) (`XCOM_POLICE_UPK` first, as before) and the upk suite's
[test_audit_spawns.py](../../tools/upk/tests/test_audit_spawns.py). A test whose map is missing skips saying where it
looked. [run_tests.py](../../tools/run_tests.py)'s `--help` no longer says the viewer tests take the settings' folder
only; it says the tests that read the game folder as a whole (its config files, its script package) take the settings'
game folder, or `XCOM_GAME` where it names them.

Checked: the twelve with the configured install: 142 tests pass, none skipped. With `XCOM_COOKED` naming an empty
folder: 39 skips, each naming the map it lacks or where it looked (before the change the same run skipped 4 and read
the rest from the settings' install); with it naming the lab copy's CookedPCConsole they run against that and pass.
