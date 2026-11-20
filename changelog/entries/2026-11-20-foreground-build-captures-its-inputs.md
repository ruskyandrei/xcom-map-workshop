### The editor's Build captures the project and its map picture before it starts, as the build queue does

Review finding 12.

- **What a build reads is captured first.** The editor's Build (and Play in game's) launched build.py on the
  project's own file, so a save, a rename or a new map picture while it ran could reach the build half way, and the
  job, the manifest and a bug report could name different bytes. [builds.py](../../tools/viewer/builds.py) `capture`
  now reads the saved project whole under the store's lock into a snapshot of its own,
  `<builds>/.work/queue-attempts/<attempt>/project.json`, with the map picture the project names copied beside it
  (`project.picture.png`, only when the kept file's SHA-256 is the one named), and build.py builds the snapshot
  (`--saved-file` names the project's own file, `--projects` its folder). A capture that can't be written is an error
  before anything is launched, and its folder is removed.
- **The build queue captures the same way.** [buildqueue.py](../../tools/viewer/buildqueue.py) calls the same
  `capture`, so its snapshots carry the picture too; the row's attempt and the job name the picture's SHA-256 beside
  the project's (`digest`, `picture`), and the bug report's summary carries both.
- **The Build reads the picture captured.** [build.py](../../tools/editor/build.py) reads the project's bytes once
  (the manifest's `project.sha256`), and a build of a snapshot takes only the picture beside it: one chosen since,
  kept with the project, is not that build's (with none beside it, the build says the picture is missing).
- The snapshots of both are pruned by the build queue's existing rule (`ATTEMPT_DAYS`, 14 days, those no row names).
- Checked: [test_builds.py](../../tools/viewer/tests/test_builds.py) saves under another name and chooses two new
  pictures after the capture, and the build, the package and the bug report keep the captured bytes; a retry after
  Cancel captures again. [test_buildqueue.py](../../tools/viewer/tests/test_buildqueue.py) does the same for a queued
  build; [test_build.py](../../tools/editor/tests/test_build.py) builds a snapshot with a newer picture in the store.
