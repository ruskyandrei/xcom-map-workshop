### Old build work is pruned after a failed build too, and as the server starts, with the variants no project ships as

Review finding 49 (the Build's part), with finding 62's prune test.

- **After every build.** [build.py](../../tools/editor/build.py) pruned old work folders only after a build that
  packaged, so a failed build kept its 60 to 150 MB and so did every older one of its variant. The prune now runs in
  the build's `finally`, built or failed, leaving that build's own work folder and kept pieces as they are; a prune
  that fails is a line in the log, never the build's outcome.
- **One prune, shared.** [builds.py](../../tools/viewer/builds.py) `prune_work` holds the rule for both: every
  variant keeps its 3 newest work folders whole (`KEEP_WORK`; a bug report reads the newest) and older ones keep their
  logs and their files up to 1 MB; the rest of `.work` (patchtool's, the publish journals, the snapshots the build
  queue prunes) is left.
- **As the server starts.** `BuildRunner.prune` runs beside `recover`, in a thread of its own (the first prune of a
  folder that never had one may free gigabytes), and knows the variants the projects ship as (`owned_variants`, read
  from the projects folder; an unreadable folder or file means none is taken for unowned). A variant no project ships
  as keeps no work folder whole once its last build is 14 days old (`ORPHAN_DAYS`).
- **Kept pieces get an age limit.** A variant's kept relit pieces (`.work/pieces/<Variant>`, one build's worth) are
  deleted once neither they nor the variant's work folders have changed for 30 days (`PIECE_DAYS`), or 14 days for a
  variant no project ships as; the next build of it relights everything once.
- Checked: [test_build.py](../../tools/editor/tests/test_build.py) prunes after a failed build, keeps that build's own
  kept pieces however old and leaves a variant no project ships as; [test_builds.py](../../tools/viewer/tests/test_builds.py)
  starts a server on a builds folder with owned, unowned and recently built variants, old and recent kept pieces and
  patchtool's work, then prunes again and finds nothing; another test spares a running build's folder and checks
  `owned_variants`. Known gap: the game folder's backups and history (the rest of finding 49, installs.py) are not
  this change's.
