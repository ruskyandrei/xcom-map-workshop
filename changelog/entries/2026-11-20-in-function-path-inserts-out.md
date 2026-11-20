### The product's functions no longer grow the import path

Review finding 54, second step. Every `sys.path` insert made inside a function of the product, each run on every
call, is now `paths.use()` (which adds a folder once) or gone where the module's own first lines put the folder there
already:

- [build.py](../../tools/editor/build.py): seven inserts of `tools/bake`, one per stage that reaches it, are
  `paths.use('bake')`.
- [manager.py](../../tools/viewer/manager.py): the pack export's three (two of `tools/bake`, one of `tools/upk`),
  which grew the server's path on every pack export.
- [export.py](../../tools/viewer/export.py) (the van rule's compiler), [lights.py](../../tools/viewer/lights.py),
  [pictures.py](../../tools/viewer/pictures.py) and [seed_map.py](../../tools/upk/seed_map.py): `paths.use()`.
- Dropped as doing nothing: the compiler's three appends of `tools/viewer` (its first lines insert it),
  [library.py](../../tools/viewer/library.py)'s insert of `tools/bake` (it appends that folder at its top) and
  [prune.py](../../tools/viewer/prune.py)'s insert of its own folder.
- Each of those modules puts `tools` on the path (appended, so it stands in for nothing) and imports
  [paths.py](../../tools/paths.py). The release ships `paths.py`, which
  [test_release.py](../../tools/release/tests/test_release.py) checks, and
  [make_release.py](../../tools/release/make_release.py)'s notes say why `tools/lab` is still searched: a shipped
  import of a lab tool shows in the test instead of being left out unseen.
- Left as they are: the module-level inserts (once per import) and the research tools' in-function inserts
  (`tools/upk/audit_*`, `tools/re`, the lab's `save_tiles.py`); the follow-up refactor plan has them.
- Checked: release, repo, editor and viewer suites.
