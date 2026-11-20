### The tests' cooked folder has one name: XCOM_LWR_COOKED is no longer read

Refactor stage T5 (review finding 58, the runner's environment). `XCOM_COOKED` names the CookedPCConsole folder the
tests and the catalogue builders read in place of the settings'; its old second name, `XCOM_LWR_COOKED`, kept as an
alias since the finding's first step, is gone from its two readers:
[labpaths.py](../../tools/lab/labpaths.py) (`cooked_override`, which `lwr_cooked`, `install_map` and every test's
`test_file` default go through) and [test_material_rules.py](../../tools/viewer/tests/test_material_rules.py). No
user-facing document, the release or any script named it; nothing on this computer set it.

Checked: the material rules tests (9, with the install); `labpaths.cooked_override()` with only `XCOM_LWR_COOKED` set
gives None (the settings' folder is read), with `XCOM_COOKED` set gives that folder.
