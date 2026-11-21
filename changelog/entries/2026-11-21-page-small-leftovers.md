### The page's small leftovers: PL used, a write with no effect and two unused helpers gone

Editor follow-ups, stage P3, items 3.31, 3.19 and 3.4. Nothing the editor does changes.

- **3.31:** the three places that wrote `'TheWorld.PersistentLevel.'` out beside
  [constants.js](../../tools/viewer/web/constants.js)' `PL` import it: choosing a piece of the map's own from All maps
  ([clipboard.js](../../tools/viewer/web/clipboard.js)), a made wall's donor template
  ([made_handles.js](../../tools/viewer/web/made_handles.js)) and the name of a copied spawn point with no actor of
  its own ([spawns_wiring.js](../../tools/viewer/web/spawns_wiring.js)).
- **3.19:** [cutaway.js](../../tools/viewer/web/cutaway.js)' `sceneViewOptions` no longer shows or hides the Floor
  picker by the count of buildings: `floorOptions`, which app.js's `startScene` calls straight after the pieces are
  placed, sets it by their floors before anything is drawn. Its heading says so.
- **3.4:** `named` ([play.js](../../tools/viewer/web/play.js)) and `sign`
  ([effects_sim.js](../../tools/viewer/web/effects_sim.js)), which nothing called, are gone. (The rest of the item's
  list is used or was gone already.)

Checked: the node suite and `web_names` clean; the twenty-edit recording the same as on the stage's start commit, all
52 steps (both on the stage's scratch test server); browser checks `library`, `library-all`, `spawns`, `floors-cut`,
`clear-map`, `cover` (the Bar), `walls` and `looks` (the police station) pass.
