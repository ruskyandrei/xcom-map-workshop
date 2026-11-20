### Every environment variable the tests and the tools read, listed by `run_tests.py --help`

Refactor stage T5 (review finding 58, the runner's environment). The 37 `XCOM_` variables the tests and the tools
read were named only where each is read. [run_tests.py](../../tools/run_tests.py) now lists them all
(`ENVIRONMENT`), in groups, with what each does and what happens without it, and `--help` prints the list:

- the folders the tests read: `XCOM_MAP_WORKSHOP_SETTINGS`, `XCOM_COOKED`, `XCOM_GAME`, `XCOM_VIEWER_CACHE`;
- the longer checks, off unless set: `XCOM_INSTALL_TESTS`, `XCOM_TRANSPLANT_RING`;
- one package of the install each: the 22 `XCOM_<MAP>_UPK`, each with its file and the tests that read it;
- set by the tools for what they start: `XCOM_UNPACKED`, `XCOM_UNPACKED_KEEP`, `XCOM_WORKSHOP_TEST_FOLDER`;
- the lab's hidden game runs: `XCOM_HIDDEN_SOUND` and the stand-in input's five.

The [README](../../README.md)'s part on the tests gives the ones for running the tests on another setup, with what
skips without each, and points at `--help` for the rest. A test in
[test_run_tests.py](../../tools/repo/tests/test_run_tests.py) holds the list level with the code: every `XCOM_` name
in the files Git has or would add under tools/ is listed, each listed one is read somewhere, none twice, and the
README names no other.

Checked: the repo suite (41); the new test fails on a planted file reading an unlisted variable.

Known gap: `XCOM_COOKED` serves the tests that take the install's packages through `tools/lab/labpaths.py` and
test_material_rules.py; about a dozen viewer and upk tests read the settings' folder directly
(`settings.lwr_cooked()`), so pointing every test at another install takes a settings file
(`XCOM_MAP_WORKSHOP_SETTINGS`). The list says so.
