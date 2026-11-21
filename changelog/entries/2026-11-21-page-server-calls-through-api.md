### The page asks the server through api.js only

Editor follow-ups, stage P3, item 3.28: eighteen requests the page's modules made with the browser's `fetch` beside
[api.js](../../tools/viewer/web/api.js) now go through it, so a refusal is read one way everywhere. Each place does on a
failure what it did before.

- **[api.js](../../tools/viewer/web/api.js)** gets two helpers beside `call` (which throws the server's words on a
  refusal): `ask(url)`, a GET whose failure gives null (refused, not answered or not JSON), and
  `sendPng(method, url, blob)`, a PNG sent, giving the response as `fetch` does. (The plan named it `putPng`; one of
  the PNG requests, the map picture's preview, is a POST, so the method is given as `call`'s is.)
- **`ask`, for the reads a failure leaves as none:** the map's families as it opens and the map list
  ([app.js](../../tools/viewer/web/app.js): a failed list still stops the opening with its own words), the map list
  brought up to date ([map_menu.js](../../tools/viewer/web/map_menu.js)), the map's collision for invisible floors
  ([cover_wiring.js](../../tools/viewer/web/cover_wiring.js)), its spawn rules
  ([spawns_wiring.js](../../tools/viewer/web/spawns_wiring.js)) and the look picker's kept pictures
  ([look_picker.js](../../tools/viewer/web/look_picker.js)).
- **`call`, for the requests whose failure is said or stops something:** the prefab builder's families (app.js), the
  install's landing lines ([clear_map.js](../../tools/viewer/web/clear_map.js), with its own words for a refusal
  without any), a rock's corners ([made_handles.js](../../tools/viewer/web/made_handles.js), the same), another map's
  piece and effect and many effects at once ([library_templates.js](../../tools/viewer/web/library_templates.js)),
  the looks' catalogues ([looks.js](../../tools/viewer/web/looks.js), whose `loadLooks` no longer takes a fetcher:
  its node test stands in for the browser's fetch), Prepare's export and its progress
  ([prepare.js](../../tools/viewer/web/prepare.js)) and the map picture's removal
  ([map_picture.js](../../tools/viewer/web/map_picture.js)).
- **`sendPng`:** the library's thumbnails ([library.js](../../tools/viewer/web/library.js)), the look picker's
  samples, a prefab's picture ([prefabs.js](../../tools/viewer/web/prefabs.js)), the map picture and its preview.
- **What stays a plain `fetch`**, named in [ARCHITECTURE.md](../../ARCHITECTURE.md) ("The page", Modules) and in the
  new node test: a picture read as a blob (map_picture.js twice, prefabs.js once), the wave's range probe
  ([effects_wiring.js](../../tools/viewer/web/effects_wiring.js)) and the scene's layout read with its progress
  ([loading.js](../../tools/viewer/web/loading.js)).
- **[one_home_test.mjs](../../tools/viewer/tests/one_home_test.mjs)** (new) reads every page module as code (comments
  and strings left out, a template's `${...}` kept; a module that does not read whole fails) and counts the
  browser's `fetch` in each against that list with its reasons. It failed on the stage's start commit (14 modules:
  the eighteen requests and looks.js's default fetcher) and passes now.

Where the two can differ, only on answers this server never gives: a Prepare progress answer refused (it stops with
the server's words, where it asked again forever; the server refuses it only for a map not listed), the prefab
builder's families refused (its opening stops, where the refusal was read as the families' table), an answer of 200
that is not JSON (read as `{}` by `call`, so the looks' catalogue would be kept empty and Prepare would ask again), and
the map list's or the spawn rules' read not answered at all (the map's opening says its own words rather than the
browser's; the Spawns panel is drawn with no rules, as for a refused read).

Checked: the node suite (36 files) and `web_names` (98 files, clean); the twenty-edit recording the same as on the
stage's start commit, all 52 steps; browser checks `library`, `library-all`, `library-effects`, `cover`, `clear-map`,
`spawns`, `prepare`, `map-lights`, `failed-reads`, `floors-cut`, `prepare-routes` (the Bar), `builder`, `prefab-test`,
`walls`, `looks` (the police station), `browser_maps_smoke.py` and `browser_map_picture.py` pass.
