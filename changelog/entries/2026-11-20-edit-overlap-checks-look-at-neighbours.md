### The package writers check an edit for overlaps against its neighbours only

Review finding 43. The growing writer checked each fixed-size edit against every earlier one, and the copy tool makes
one 5-byte edit for each tile it seeds, so the check grew with the square of the edits.

- [package_grow.py](../../tools/upk/package_grow.py)'s `Grower.edit` keeps the edits' offsets in order and asks
  [package_edit.py](../../tools/upk/package_edit.py)'s new `overlapping`, which looks at the edit before and the one
  at or after: the edits are apart, so no other can meet a new one. An empty edit is refused when it is made, as the
  writer refused it at the end.
- `write_edited` finds whether a chunk or a block meets an edit by a search in the sorted edits instead of a scan of
  all of them for each.
- [lighting_fixture.py](../../tools/bake/lighting_fixture.py)'s edit log does the same; an inline mip written again
  takes its earlier edit back through the new `unedit`.
- Measured on URB_Bar with synthetic 5-byte edits in a shuffled order: 2,000, 8,000 and 20,000 edits took 0.08, 1.2
  and 10.9 s before, and 0.001, 0.008 and 0.03 s after. `write_edited` with 20,000 edits went from 0.19 to 0.05 s.
  The largest of the 114 build manifests kept on this computer seeds 6,989 tiles (about a second of checks before).
- Checked: [test_package_edit.py](../../tools/upk/tests/test_package_edit.py) compares `overlapping` with a scan of
  every edit over 3,000 random cases, and writes a synthetic package with a few hundred edits in a shuffled order;
  [test_package_grow.py](../../tools/upk/tests/test_package_grow.py) tests the grower's refusals and 19,000 edits
  without a map. The upk suite and the fixture and relight tests pass.
