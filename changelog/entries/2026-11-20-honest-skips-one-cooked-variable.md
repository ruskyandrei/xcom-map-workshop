### Skips that skip, one variable for the cooked folder, the shared record in a fixtures module

Review finding 58, its tools/bake and tools/upk items.

- **Skips that errored.** Two gates in [test_native_copy.py](../../tools/bake/tests/test_native_copy.py) called
  `.exists()` on a path that is None when no install is configured, which made the whole module error; one in
  [test_transplant.py](../../tools/bake/tests/test_transplant.py) tested the paths without `.exists()`. All are
  `X and X.exists()` now.
- **A pure test behind an install gate.** The growing writer's `chunk_cuts` test is a class of its own in
  [test_package_grow.py](../../tools/upk/tests/test_package_grow.py), out of the class that needs URB_Bar.
- **One variable for the cooked folder.** [labpaths.py](../../tools/lab/labpaths.py) `lwr_cooked` takes the folder
  `XCOM_COOKED` names before the settings' (its old name `XCOM_LWR_COOKED` is still read), so every test that says
  it reads "the folder XCOM_COOKED names" does; [test_material_rules.py](../../tools/viewer/tests/test_material_rules.py)
  reads `XCOM_COOKED` first too.
- **The shared record.** `record` (a DefaultMaps.ini record of tools/patch/tests) lives in
  [fixtures.py](../../tools/bake/tests/fixtures.py); [test_deploy.py](../../tools/bake/tests/test_deploy.py) and the
  viewer's [test_manager.py](../../tools/viewer/tests/test_manager.py),
  [test_outputnames.py](../../tools/viewer/tests/test_outputnames.py) and
  [test_play.py](../../tools/viewer/tests/test_play.py) import it from there (their import lines alone changed), not
  from another suite's test module.

Checked: the package-grow and deploy tests; the viewer's manager, output names, play, material rules, install
recovery and pack tests.

Left for others: the compiler's Bar-cache tests that look for a pinned hash (tools/editor), the viewer tests that
import test_projects and test_manager, test_game_grid testing viewer code from the upk suite, and
tools/patch/tests/test_ship_record.ps1, which nothing runs.
