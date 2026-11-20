### ARCHITECTURE.md: the copy tool's Build as a record and its steps, and where a lane of the native edit goes

Refactor stage B4's guidance (the plan's section 11: the guidance follows the code).

- [ARCHITECTURE.md](../../ARCHITECTURE.md), section 1, "The copy tool": a Build of the copy tool is one record,
  `BuildState`, made by its caller (`main` through `edit_state` and `copy_record`, or a test); `build(st)` runs its
  steps in order, each a function of the state (`clone_copies`, `fracturing_copies`, `wall_columns`,
  `edit_buildings`, `edits_in_place`, `floors_and_cursors`, `write_and_verify`), then the record.
- Section 2, "Where new code goes": a lane of the native edit in the copy tool is a maker module, the lane's field on
  `BuildState` read in `edit_state` (and named in the test's `CommandLine.LANES`, which fails when a lane
  `edit_state` reads is missing from it), and a step taking the `BuildState`, called from `build` where the map's
  writes need it.

Checked: the repo suite (links, nothing of one computer).
