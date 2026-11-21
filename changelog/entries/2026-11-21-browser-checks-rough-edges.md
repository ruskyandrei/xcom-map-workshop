### The browser checks' rough edges: names of their own each run, the server's 500s with their address, skipped parts that fail nothing, and --all's own Play install

The refactor's follow-ups (item 4.9) listed rough edges of the browser checks; all but the page load's time-out under
load (the computer's) are dealt with in [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py):

- **Run again against the same folder.** `projects`, `prefabs` (its project), `prefab-effects`, `library-effects` and
  `effect-values`, and `library-all` and `library-flares` the same way, name what they save after the run (`RUN`, a
  stamp of the run: "Smoke test project 123456"), so a second run no longer meets the first's project of the same name
  and times out. `projects` compares the files of the two projects it saved, not the whole folder's, so it also runs
  after other checks' projects. `prefab-effects` deletes the prefabs it made on every way out, as `prefabs` does, so a
  failed run leaves the prefab library check no prefab to trip on.
- **The server's 500s with their address.** Every page a check opens through the run's browser (in any check module:
  `browser.new_page` is wrapped) records the answers of status 500 and above with their method, address and the check
  that met them. The report lists them (`serverErrors`), a failed run prints them, and `--all` prints them under a
  failed run's line. (A console error said only "the server responded with a status of 500".)
- **`adding` picks its own piece** (typed-pose's, one function `own_piece` for both), so `--only adding` runs alone.
- **The effect edits put the snap back on every way out.** `check_effects_editing` turned the snap off and its skip on a
  map with no effect to move returned without putting it back, so later checks on such a map inherited snap off; the
  setting is now put back in a `finally`.
- **`library-effects` waits for the list to settle.** The likeness pane hides on its row's mouseleave, and the All maps
  list is drawn again whenever its size changes, which the busy row under it does while the pictures in view are read.
  The one time the wait for the pane to hide timed out (1 of 76 hovers, five pages at once), the list had been drawn
  again during that hover; the pointer now goes on a row once every picture in view is drawn and none is being read.
- **Under `--only`, a part that skips fails nothing.** A check asked for that did nothing (skipped whole, or its server
  or map can't have it) still fails the run, and so does a run in which everything skipped; a skipped part is listed
  in the report and printed. (`--only streams` on the Bar, and `streams,spawns` on the police station, exited 1 on a
  part that skipped.)
- **`--all` makes the Play check's scratch install itself.** Without `--play-install`, it copies the files the Play
  check needs (the config's `Default*.ini`, `XComGame.upk`, the played map, the `XCom*.int` words, an empty
  `Binaries`) from the game install the settings name, which is only read, into its scratch folder, when they come to
  less than 300 MB (32 MB for LWR); else Play is skipped as before, saying why. The module's docstring and
  `--play-install`'s help say so. The scratch folder is made whole first: the servers run from the repository, so a
  relative `--scratch` named folders of their own there.

Checked: before and after with the start commit's script on one test server: `--only adding` failed before and passes;
`--only streams` on the Bar and `--only streams,spawns` on the police station exited 1 before and pass, their skipped
parts listed. The changed checks (`typed-pose`, `adding`, `effects`, `projects`, `prefabs`, `prefab-effects`,
`library-all`, `library-effects`, `effect-values`, `library-flares`) passed five times in a row on one test server
against one projects folder. `browser_smoke.py --all` twice: 9 of its 10 runs passed each time (77 checks); the Play
run made its scratch install itself (36 files) and was then refused because XCOM was running (a game not started by
the checks), so Play is still to be run with the game closed.
