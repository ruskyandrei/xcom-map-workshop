### The page's own aliases of api.js' call no longer read as its ask

Editor follow-ups, stage P4 (an addition in the spirit of its words). Nothing the editor does changes.

[map_browser.js](../../tools/viewer/web/map_browser.js), [precache.js](../../tools/viewer/web/precache.js) and
[prefab_test.js](../../tools/viewer/web/prefab_test.js) imported [api.js](../../tools/viewer/web/api.js)' `call` as
`ask`, to free the name `call` for their own short wrapper of it. Since stage P3, `api.js` has an `ask` of its own (a
GET that gives null on a failure), so the alias read as that one while it throws on a failure. The three import it as
`callServer` now; each wrapper calls it as before.

Checked: the node suite and `web_names` clean; `browser_maps_smoke.py` (the map browser) and the `builder` and
`prefab-test` browser checks pass on the stage's scratch test server. No browser check opens the Cache everything
window (precache.js); its change is the same two names.
