### No bake or upk test imports another: the hull readers in fixtures.py, uncompressed in upk_fixtures.py

Refactor stage T5 (review finding 58). Two test files imported another for a helper:

- the bake suite's [test_frac_walls.py](../../tools/bake/tests/test_frac_walls.py) imported test_cover_blocks.py, in
  two tests, for `hull` (a mesh's convex element read back). `hull`, with the readers it needs (`tagged`, `RAW`,
  `export_bytes`), is in the suite's [fixtures.py](../../tools/bake/tests/fixtures.py) now; test_frac_walls calls
  `fixtures.hull`, and [test_cover_blocks.py](../../tools/bake/tests/test_cover_blocks.py) imports `hull` and
  `export_bytes` from there. fixtures.py gained them, `import struct` and `props` (tools/upk) at its top; its build
  helpers are untouched.
- the upk suite's [test_package_grow.py](../../tools/upk/tests/test_package_grow.py) imported test_package_edit.py for
  `uncompressed` (a package as it would be stored uncompressed). It is in a new
  [upk_fixtures.py](../../tools/upk/tests/upk_fixtures.py), the suite's fixtures module, and both import it from
  there.

Moved verbatim (`moved_code.py`: the four functions the same; `RAW` compared by syntax tree).

Checked: the bake suite (694) and the upk suite (172), the same tests by name and verdict as before; test_frac_walls,
test_cover_blocks, test_package_edit and test_package_grow each run alone (`unittest discover -p <file>`, and
`run_tests.py <suite> -k <file>`); the repo suite.
