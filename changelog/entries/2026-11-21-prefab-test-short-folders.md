### A prefab's Test in game builds under a long builds folder (KB-12 fixed)

**Test in game** in the prefab builder stopped in its Build with a `FileNotFoundError` naming a file that ends in
`.upk.grow-tmp` when the builds folder sat deep in folders, while a project's own Build from the same folder worked
(KB-12). A test's Build made its files under
`<builds>/.prefab-tests/<test id, 36 characters>/artifacts/.work/<pt_ and 26 characters>-<date>-<attempt>/`, which
added about 120 characters before the files the Build writes, so the grown map's temporary file came to 169 characters
past the builds folder and passed Windows' 260 with a builds folder of about 90. Now:

- **The Build takes its work folder from a new field,** `BuildInputs.work` (`--work` on the command line); without
  it, a prefab test's Build works in `w` beside the test's project file, in the test's own folder, and any other
  build in `<output>/.work/<Variant>-<stamp>` as before ([build.py](../../tools/editor/build.py), `work_folder`).
  The manifest's `work` names it. A prefab test's folders are pruned whole as before, and what looks for a running
  test's tools (its folder in their command lines) finds them there too.
- **A new test's folder and map are named by the first 12 hexadecimal characters of its id**
  ([prefab_tests.py](../../tools/viewer/prefab_tests.py) `short_name`,
  [prefab_stage.py](../../tools/editor/prefab_stage.py) `package_code`: `pt_<12>` and `pp_<12>`, where they were the
  whole id in base 32, 26 characters). The id itself stays a UUID: the install's journal of a test's files names it
  and is refused for anything else ([installs.py](../../tools/viewer/installs.py) `recover_test_install`). A test made
  before, its folder named by its whole id, is still recovered, read, played from and pruned.

So a test's deepest file is now about 90 characters past the builds folder (the package's map in place; the decoded
maps the Build keeps while it runs, `w/unpacked/<64 characters>.unpacked`, about 112).

Checked:
- KB-12 reproduced first with a scratch script (a prefab of three pieces of another map prepared on the blank map and
  built quick as the server starts a test, on a scratch cache): with a builds folder of 100 characters the old layout
  stops in `native_copy.py` on `lit\pt_<26>.upk.grow-tmp` (169 characters past the builds folder), with one of 120
  already at the compile report; with the change the same test builds under 120, its deepest file 89 characters past.
- New tests, each failing before: [test_build.py](../../tools/editor/tests/test_build.py) builds a prefab test with
  stand-in tools under a builds folder of 140 characters, where the old layout's deepest file would be 280 (it stopped
  with `FileNotFoundError` before), and checks its work folder and that its deepest file is 108 characters past the
  builds folder; a given work folder is the build's; `--work` reaches the Build.
  [test_prefab_tests.py](../../tools/viewer/tests/test_prefab_tests.py): a new test's folder and map are named short,
  a test of before (its folder named by its whole id) is recovered and read, a folder whose record names another test
  is left alone.
- The editor suite (373 tests); the viewer suite's prefab test and builds tests.

KB-12 leaves [KNOWN-BUGS.md](../../KNOWN-BUGS.md).
