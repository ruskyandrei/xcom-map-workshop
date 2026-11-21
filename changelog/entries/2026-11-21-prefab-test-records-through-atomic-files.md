### A prefab test's records are written through atomic_files too (KB-10's last writer in the server)

KB-10's fix (one writer for a file replaced whole, [atomic_files.py](../../tools/viewer/atomic_files.py)) left one
writer of `tools/viewer` replacing once: `write()` in [prefab_tests.py](../../tools/viewer/prefab_tests.py), which
writes a prefab test's `test.json`, its snapshot, its project and its compile report, then the Build track's file. It
now writes through `atomic_files.write_text`, keeping its temporary file's name (`<stem>.tmp` beside the record) and
its bytes, so a Test in game whose record another program holds a moment (a virus scanner, an indexer) waits for it
instead of failing, and a write that fails leaves no temporary file.

Checked: [test_atomic_files.py](../../tools/viewer/tests/test_atomic_files.py) runs the prefab test's writer among
the writers whose every replace is refused twice (it failed before with a `PermissionError`), and its scan no longer
allows `prefab_tests.py` (the scan failed until the entry went); the atomic files and prefab test tests pass (22).
