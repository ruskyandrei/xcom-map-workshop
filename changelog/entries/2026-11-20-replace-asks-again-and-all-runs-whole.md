### Replace asks again when the project was saved meanwhile (again), and --all's first run put right

Review findings 56 and 24, found by the first `--all` run.

- **Replace asks again** ([app.js](../../tools/viewer/web/app.js)): finding 56 moved the server's refusals to
  `error.body` (api.js), and the Save dialog reads `body.revision` to ask again about a project saved since it showed
  it; the page's own "saved again meanwhile" error still carried `detail`, so the dialog said "Not saved" instead of
  asking. It carries `body` now, as api.js's errors do. The documents check (`check_replace_confirmed`) found it.
- **`--all`** ([browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)): the scratch cache it makes has the whole
  game's library scanned (about 40 seconds; the library checks count every map's pieces and effects, and three maps'
  gave 99 effects); `browser_map_picture.py` is given the server alone (it opens its map itself; given the map's
  address it opened none); and a run's report is written when a check fails too, naming the check and why, with what
  ran before it.

Checked on a test server serving a scratch cache with the whole library scanned: `--only documents`,
`browser_map_picture.py`, and `--only speeds,library-all,library-effects,effect-values,library-flares,library-assembly,output-names`
(all ran, none skipped, no errors; the favourites written beside the scratch settings file). The final `--all` run
follows this commit.
