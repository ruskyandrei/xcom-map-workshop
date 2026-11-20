# Ledger entries not gathered yet

One file per change, added in the same commit as the change:

- **Name:** `<YYYY-MM-DD>-<what>.md`: the day it went in, then a few words in lower case joined by hyphens
  (`2026-11-20-static-route-refuses-absolute-paths.md`).
- **First line:** `### <title>`. Then what changed, where (link the files), how it was checked, and any known gaps,
  as the entries in the [month files](../../CHANGELOG.md) read.
- **Links** are relative to this folder: `[the server](../../tools/viewer/viewer.py)`.
- LF line endings, and nothing that names a person or a computer (`python tools/run_tests.py repo release` checks the
  files).

Each release moves them into the month's file with
[gather_changelog.py](../../tools/release/gather_changelog.py), which re-bases the links and orders a day's entries
newest first by when Git first recorded them.
