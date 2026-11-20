### The records several suites' tests share have one home, tools/tests/shared_fixtures.py

Refactor stage T5 (review finding 58, cross-suite imports). Two things were shared across suites by reaching into
another suite's or tool's folder:

- **The DefaultMaps.ini records** of
  [tools/patch/tests/defaultmaps-records.txt](../../tools/patch/tests/defaultmaps-records.txt): the bake suite read
  them there (`fixtures.record`), the editor suite read them there with a reader of its own (test_build.py's
  `record`), and six viewer test files put tools/bake/tests on the path to import the bake suite's `fixtures.record`.
- **A made-up mesh's bytes** (`minimal_mesh`) were in the viewer's test_formats.py; the bake suite's
  test_shadows_bounce.py put tools/viewer/tests on the path to import them from there.

Both are in [shared_fixtures.py](../../tools/tests/shared_fixtures.py) now, moved verbatim (`moved_code.py`: the same),
the one place the Python tests name the records' file. The file stays beside the patch tool's test it was copied for
(test_ship_record.ps1, which reads it there), so the change ledger's links to it still lead to it. Each suite's
fixtures module names the home and gives its tests what they need of it:
[viewer_fixtures.py](../../tools/viewer/tests/viewer_fixtures.py), [fixtures.py](../../tools/bake/tests/fixtures.py)
(its own `record` replaced by the import; its build helpers untouched) and a new
[editor_fixtures.py](../../tools/editor/tests/editor_fixtures.py). So:

- the viewer's test_play, test_manager and test_outputnames import `record` from viewer_fixtures, and they,
  test_install_recovery, test_pack_export and test_pack_scripts no longer put tools/bake/tests on the path;
  test_formats imports `minimal_mesh` from viewer_fixtures;
- the bake's test_shadows_bounce imports `minimal_mesh` from fixtures, and test_lab_install takes `record` from
  fixtures rather than from test_deploy;
- the editor's test_build reads the record through editor_fixtures (as text, as before) instead of a reader of its
  own.

Checked: the editor (371) and viewer (639) suites, the same counts as before the change; the bake suite's
test_deploy (17), test_lab_install (7) and test_shadows_bounce (29); the repo suite.
