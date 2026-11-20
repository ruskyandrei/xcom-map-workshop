# Change ledger

What changed in the repository, added as each change goes in. Each entry says what changed, where, and how it was
checked. Experiment results stay in `research/experiments/` and the [findings register](research/findings-register.md);
this ledger records the tools and documents.

- **New entries** are one file each in [changelog/entries](changelog/entries/README.md), named
  `<YYYY-MM-DD>-<what>.md` and starting with a `### <title>` line, so two branches never edit the same lines.
- **Each release gathers them** into the month's file below, under their day, newest first
  ([gather_changelog.py](tools/release/gather_changelog.py)). The entries not gathered yet are the changes since the
  last release.

| Month | Days |
| --- | --- |
| [November 2026](changelog/2026-11.md) | 5 to 20 November: from the first blank-map experiment to release 0.6.0 and the whole-editor review |

Before 5 November 2026 the history is in Git and in the experiment notes.
