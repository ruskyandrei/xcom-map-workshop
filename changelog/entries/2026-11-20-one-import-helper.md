### One helper puts a tool folder on the path once, and a test keeps module names unique

Review finding 54, first step.

- **[tools/paths.py](../../tools/paths.py)** (new): `paths.use('bake', 'upk')` puts each named tool folder on
  `sys.path` only when it is not there yet, however an earlier insert spelled it (a `..` step, the other slash, another
  case). A function that calls it on every request or stage leaves the path as the first call did. An unknown folder
  name is refused.
- **[test_names.py](../../tools/repo/tests/test_names.py)** (new, repo suite): no two tracked Python files share a
  name, and none takes the name of a standard-library module or of a package the editor installs, so the order the
  folders go on the path never decides which file a name finds. It also checks `use()`.
- **[make_release.py](../../tools/release/make_release.py):** the release's `._pth` lists `tools` itself after the five
  folders, and the module scan finds a module there, so `paths.py` ships once a module the editor imports uses it
  (`run_tests.py` is never taken).
- The in-function inserts are replaced with `use()` in a later step, after the other branches of this review merge.
- Checked: repo and release suites.
