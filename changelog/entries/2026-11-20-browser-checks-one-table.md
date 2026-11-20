### The browser checks: one table, a report of what ran and what was skipped, --all on scratch servers, waits for what they read

Review findings 24 and 59, the browser checks' part. The page itself doesn't change.

- **One table** ([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py) `CHECKS`): each check's name, what it
  does, what the server must be started with (`--projects`, `--play`, or a scratch settings file for the library
  checks, which write the favourites beside it) and the maps it can run on. The whole run is the table's checks in
  order; its inline parts are named checks now (`skins`, `map-lights`, `typed-pose`, `header`, `floors-cut`,
  `dense-lighting`, `frame-bounds`, `tile-grid`, `wire`, `tile-footprints`, `temple-interior`, `temple-look`,
  `previews`). `--only` refuses a name it doesn't know (`prefab_effects` is `prefab-effects` now) and a check whose
  server flag is missing, and `--help` lists every check. `--url` has no default and 8768 is refused.
- **What ran and what was skipped:** each check's early return records why (`skip()`): the map, the export, the
  server's families or the library lacking what it needs. The report (printed and written beside the screenshot as
  `.json`) lists `ran`, `skipped` with the reasons, the results and the errors. A check `--only` asked for that was
  skipped, whole or in part, fails the run.
- **`--all`** runs every check of the table on fresh test servers of its own, one after another on 8795-8798, each
  with scratch projects, builds, squad and settings, `--dry-play` and a scratch cache (given with `--cache`, or made
  by exporting URB_Bar, URB_PoliceStation and TempleShip and scanning their pieces), stopped after its run: the whole
  run, the library checks, the builder, the editing checks, the documents, the police station's walls, looks and
  light bar, TempleShip, `browser_map_picture.py` and `browser_maps_smoke.py`; Play only with `--play-install <a
  scratch game folder>`. It refuses a port already taken and prints each run's lists (`all.json` in the scratch
  folder). A check missing from every run fails it.
- **Waits for what is read:** `settled()` (the camera at rest) where a fixed 100-400 ms sleep waited for framing,
  zooming or the damping; the Prepare dialog answered once the page is open (the page shows it before it sets
  `window.viewer`); the builder's failed save reads `goTo`'s answer instead of sleeping 250 ms.
- **Runs twice:** `check_prefabs` deletes the prefabs it made when it ends, passed or not (only those it made).
- **Says which map:** the walls and looks checks assert the police station is open.
- **Every page listens:** the builder's and the prefab test's pages collect console errors and failed requests too
  ([browser_builder.py](../../tools/viewer/tests/browser_builder.py) `listen`,
  [browser_prefab_test.py](../../tools/viewer/tests/browser_prefab_test.py)), the check's own 409 and 500 excepted.
- **Assertions that decided nothing** now decide: the landing zones undone stand and face as they did; the Favourites
  filter shows the favourites.
- **Duplicates out:** the pose rule's cases (shared_cases_test.mjs runs them) leave `check_recipe`; `check_floor_rules`'
  synthetic cases moved to node ([floor_rules_test.mjs](../../tools/viewer/tests/floor_rules_test.mjs)), its shared
  ones being shared_cases_test.mjs's.
- **After export 37:** the previews are found by asking for `preview-<n>.json` (no `scenes.json`), and the header
  check has no Original positions button to press.
- **Port guards:** [browser_maps_smoke.py](../../tools/viewer/tests/browser_maps_smoke.py) (no default server),
  [browser_map_picture.py](../../tools/viewer/tests/browser_map_picture.py) and
  [take_shots.py](../../tools/release/guide/take_shots.py) refuse 8768; `take_shots.py --out` has no default (it
  wrote into the tracked `shots/`; the [viewer README](../../tools/viewer/README.md) says so).
- **The release smoke** ([smoke_release.py](../../tools/release/smoke_release.py)) starts the release's server with a
  scratch settings file naming a scratch cache, into which the release's own Python exports the map first (or
  `--cache`), and the game install the user's settings name, read only; browser checks asked for on a map that isn't
  ready fail, saying why.

Checked on a test server serving a scratch cache (export 37 of URB_Bar, URB_PoliceStation and TempleShip, their
library scanned) with a scratch settings file: the whole run on URB_Bar with `--projects --squad` (43 ran; skipped
with why: the TempleShip and police station checks, Play without `--play`, a streamed piece none of which is drawn, no
previews in an export without `--spec`), `--only builder,prefab-test` (passing once the builder's own 404s, an
unavailable map's pieces, were named as expected) and on URB_PoliceStation `--only walls,looks,light-bar`; the
refusals (`--only prefab_effects`, `walls` without `--projects`, 8768 in each script, `take_shots.py` without
`--out`); the node suite with the new test, and the viewer suite. The `--all` run is in the next entries' checks.

Known gaps: `run_tests.py -k` with no match, `test_hidden_game.py` 210-212 and `test_release.py` 59 (finding 59's
other assertions) are other files' owners'. The release smoke wasn't run (no release zip in this worktree).
