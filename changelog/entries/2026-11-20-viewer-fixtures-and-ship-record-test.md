### The viewer suite's shared records in a fixtures module; the patch tool's record test run by the editor suite

Review finding 58, two of its parts (the Bar-cache tests' skip on a missing pinned export went in with the dead code
taken out).

- **Shared records.** Ten viewer test files imported `test_projects` for a project id or a project document. They
  take them from [viewer_fixtures.py](../../tools/viewer/tests/viewer_fixtures.py) now (`ID`, `OTHER`, `document`),
  and so does [test_projects.py](../../tools/viewer/tests/test_projects.py). It is named for its suite rather than
  `fixtures.py`: the viewer tests put tools/bake/tests on the path, where the bake suite's own fixtures module goes.
- **test_ship_record.ps1**, which checks patchtool's record for a map shipped under its own name and which nothing
  ran, is run by [test_patchtool_record.py](../../tools/editor/tests/test_patchtool_record.py) in the editor suite:
  its record checks always, and Set-ShipConfig on copies of the configured install's DefaultMaps.ini and
  DefaultLZMutator.ini when there is one (the install's files are only read, and the script checks they are
  untouched). It skips without PowerShell 7, which the script needs.

Checked: the new test (both parts ran here), and `test_projects`, `test_builds`, `test_outputnames`, `test_pictures`,
`test_buildqueue`, `test_prefab_tests` and `test_squad_play` with the fixtures module.
