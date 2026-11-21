### Two identical baked Builds keep the same piece cache bytes

Editor follow-ups, stage R1 (item 3.10). A relit piece's report carries the scene's counts, and its
`albedoSources` (how many materials got their albedo from a diffuse texture, a constant colour, the fallback, ...) was
built over a set of those words, whose order changes with each process's string hashing. The piece cache keeps the
report as JSON text in each piece's `.npz`, so two runs of the same Build kept files with the same arrays and the same
parsed report but different bytes, and "two runs identical" could not be a byte comparison.

- [relight.py](../../tools/bake/relight.py)' `Scene` builds `albedoSources` over the sorted words.
- No image, scale or record changes. relight.py is in the piece cache's key (`TOOL_FILES`), so a project's kept
  pieces are relit once by the next baked Build.

Checked:

- New test `SceneCounts` ([test_relight.py](../../tools/bake/tests/test_relight.py)), on a Scene built from
  stand-ins (no install, no Embree): eight kinds of albedo note given in three orders come out in sorted order with the
  same JSON text. It failed before the change (the words came out in the set's order).
- The two real baked Builds of the follow-ups' baseline (the Bar with a moved floor, and EXP-77's made ground), each
  run twice into an empty piece cache: run 1 and run 2 byte for byte the same in every package, texture cache, relit
  image and piece cache file (184 and 322 `.npz` files), where the baseline's two runs differed in the report text of
  every `.npz`; only the records' times and the logs differ. Against the baseline run: the packages, texture caches
  and the 214 and 321 relit images byte for byte the same; the piece cache files are under new keys, and held by
  their reports' components, all 183 and 321 have the same arrays and the same parsed report.
- `python -B tools/run_tests.py bake -k SceneCounts`.
