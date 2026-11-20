### The change ledger is kept as one file per entry, gathered into month files at each release

The 1.3 MB ledger is split, and two branches no longer meet under the same day's heading (review finding 65).

- [CHANGELOG.md](../../CHANGELOG.md) is now the index. The whole November ledger moved to
  [changelog/2026-11.md](../2026-11.md) as it was, with its 3,371 links re-based for the new folder.
- Each change adds its own file to [changelog/entries](README.md), named `<YYYY-MM-DD>-<what>.md` and starting with
  `### <title>`. [gather_changelog.py](../../tools/release/gather_changelog.py) moves the entries into the month's file
  at a release: under their day, newest first by when Git first recorded them, links re-based, entry files deleted.
  `--check` checks the names, title lines and links; `--list` prints the order.
- [AGENTS.md](../../AGENTS.md), the [README](../../README.md) and the release, update-guide and game-test skills say
  how the ledger is kept now. The release gathers the entries before its commit.
- [EXP-05](../../research/experiments/EXP-05-game-art-mesh.md) had LF on lines 633 to 696 of a CRLF file. They now
  end in CRLF too.
- Checked: [test_gather_changelog.py](../../tools/release/tests/test_gather_changelog.py) covers ordering, a new day
  between two older ones, a new month, the re-based links, code left alone and each kind of malformed entry. It also
  checks the real entry files. The repo suite's link check passes over the month file.
