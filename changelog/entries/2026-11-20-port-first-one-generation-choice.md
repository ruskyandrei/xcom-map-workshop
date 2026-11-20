### The main server takes its port before it prunes, and the map list, the pruning and the Build choose the same generation, of the install's own file

Review findings 16, 17 and 18, and the `SystemExit` item of finding 44.

- **Port first** ([viewer.py](../../tools/viewer/viewer.py)): `serve` binds the port before it prunes the cache or
  reads its catalogue, and sets the routes once everything is ready (`serve_cache`). A second start while the editor
  runs (the release launcher's `serve --reuse` on every launch, or a double start) finds the port taken and opens the
  browser on the running editor, or stops with the reason, having deleted and read nothing of the cache the running
  server serves. The port also listens at once, so `xcom_editor.cmd`'s 15-second wait no longer runs out while a large
  prune runs. The [release launcher](../../tools/release/XCOM%20Map%20Workshop.cmd) needed no change.
- **One check of a generation** ([catalogue.py](../../tools/viewer/catalogue.py)): `check_scene` decides what is
  usable for the map list, [prune.py](../../tools/viewer/prune.py) and the Build's
  [compiler.find_export](../../tools/editor/compiler.py): the scene reads whole, is of schema 1, names its map and
  exporter version, and a folder named as a generation agrees with its scene's package, version and scope. Prune keeps
  the newest readable generation of each package and scope and deletes only older ones; a newer one it can't read
  (truncated, another schema, another package's under this one's name) is left, never taken as the newest. Before, it
  ranked folders by name and could delete the generation the map list served. `find_export` passes over a candidate
  that can't be used for the next one instead of stopping on a `JSONDecodeError`. A scene.json is read once per size
  and time for the map list and the pruning together.
- **`find_export` raises `ExportMissing`**, not `SystemExit`, with the same words (the page's Prepare prompt matches
  them). [Build.snapshot](../../tools/editor/build.py) turns it into a `BuildError`, so the build's own "build
  failed:" line is written; [prefab_stage.py](../../tools/editor/prefab_stage.py), the compiler's command line and
  [library.donor_area_lights](../../tools/viewer/library.py) catch it.
- **Maps of the install's own file**: with a game install, each exported map serves its newest export made from the
  install's file of it (`with_install` with each map's SHA-256), and is listed unprepared, so exported on first open,
  when the cache holds only other files' exports of it, such as the other install's copy. Before, another install's
  export was offered as ready and the Build then refused it. The SHA-256 of each package is kept by size and time in
  the cache root (`.package-digests.json`), so a start hashes only the exported maps whose file changed. Choosing
  another install chooses again; `/maps.json` rechecks each file's size and time (`ExportRunner.recheck`), so a
  package changed in place is served from its own export or exported again.
- **"Cache everything"** deletes a donor's older piece generations of the same file only
  ([library.precache](../../tools/viewer/library.py), prune.py's rule); the other install's stay, so switching between
  the Long War and plain copies no longer exports every piece again.
- Checked: [test_prune.py](../../tools/viewer/tests/test_prune.py) runs the map list, the dry run and `find_export`
  together over truncated, foreign-schema, foreign-package and wrong-version generations, an equal-version re-export
  and a pinned one, and runs `viewer.py serve` (with and without `--reuse`) against a held port with a spy on prune
  and the catalogue: nothing deleted or read, both generations there, the running server still serving.
  [test_catalogue.py](../../tools/viewer/tests/test_catalogue.py) chooses between two installs' copies of a map,
  switches back, a third file with no export, and a file changed in place; [test_precache.py](../../tools/viewer/tests/test_precache.py)
  keeps another file's piece generation; [test_export_choice.py](../../tools/editor/tests/test_export_choice.py) (new)
  checks the Build's error; [test_compiler.py](../../tools/editor/tests/test_compiler.py)'s `find_export` test passes
  over four unusable candidates. The viewer and editor suites pass.
