### A change of the game install's files is undone whole when it stops part-way, and its config files are never cut short

Review findings 2 and 50.

- **Every config write goes through a temporary file.**
  [deploy_fixture.write_checked](../../tools/bake/deploy_fixture.py), which writes `DefaultMaps.ini`,
  `DefaultLZMutator.ini` and `DefaultRandomSpawns.ini` for every install path, wrote the game's file in place and
  only then read it back. It now writes a temporary file beside it, reads that back, and puts it in place with a
  replace. A crash or a forced stop mid-write leaves the game's file as it was, and so does a bad read-back.
- **Each change of the install keeps a journal.**
  [installs.py](../../tools/viewer/installs.py) wraps each change in a `_Change`: a play's install, a map play's
  record, a campaign install, a play's clean-up, Remove from game, records switched on or off, and an earlier
  version's intro taken out. The journal (`<game>\XCOM Map Workshop\change.json`) is written before the change's
  first write and holds both ledgers' text as they were. Before each later write it records what that write is:
  - for a config file, its hash before and after, with its old bytes kept beside the journal;
  - for a package file, the file it copies in or takes out. A file it replaces or takes out is moved aside
    (`.<name>.change.tmp`) instead of deleted, and a copy goes in through a temporary file.

  A change that ends in an error is rolled back at once. One stopped by a crash or a forced stop is rolled back by
  the next look at the install (`ready`, which every operation and the page's status calls run, and
  `recover_change` at the start of each operation). Rolling back puts back the config bytes, the files and the
  ledgers, and the ledger's history records it (`interrupted`, `rolledBack`). So `DefaultMaps.ini` never again has a
  record the ledger doesn't know: the stop between the config write and the ledger write, which listed the variant
  as a game map and refused its next install, can't leave that state any more.
- **A config file changed by hand between the stop and the recovery is left as it is.** It is named in the
  history's `left`, and its text from before is kept in `backups\interrupted-<stamp>`.
- **"Is the game running?" no longer starts tasklist.** The question was asked about five times a play, on every
  status poll and every 3 s through a game session. [procs.running](../../tools/viewer/procs.py) answers it from one
  snapshot of the process table, and both copies use it: `installs.game_running` and `deploy_fixture.game_running`.

Checked: [test_install_recovery.py](../../tools/viewer/tests/test_install_recovery.py) runs four changes: a play's
install, a campaign install in place of the map, a play's clean-up, and Remove from game after both. Each is
stopped after every file copy, file taken out, config replacement, ledger write and journal write. Then Remove from
game runs, and every file of the install (the editor's folder aside) must be byte for byte as before, with nothing
of the change left. The test also covers:
- the first review's case, a campaign replacement stopped at its final ledger write: the next look undoes it, the
  variant is no map of the install, and it installs again;
- a hand edit made in between, which is kept and reported;
- an error part-way, which is undone at once;
- no tasklist started.

Without the journal, the stop cases fail. The bake suite's
[test_deploy.py](../../tools/bake/tests/test_deploy.py) checks the write is whole or not at all. The viewer suite,
the bake tests of `deploy_fixture` and the lab suite pass.

Known gap: the play's commands file and the play's kept config and save copies are not part of the journal. They
have their own clean-up.
