### The Map menu's items set by one function, and the Spawns view's always-true guard gone

Editor follow-ups, stage P5, items 3.18 and 3.24. Nothing the editor does changes.

- **3.18:** the Map menu's four items (Map grid, Clear map, Missions, Map picture), shown for a whole map's original
  layout, were set line for line the same by `showSceneMenus` as a scene opens and by `clearedChanged` after the
  cleared mark changes. One function, `showMapMenu($)` in [scene_start.js](../../tools/viewer/web/scene_start.js),
  sets them for both: `showSceneMenus` calls it, and [zones_wiring.js](../../tools/viewer/web/zones_wiring.js)'
  `clearedChanged` imports it. scene_start.js imports `projectsAvailable` from document_session.js instead of being
  given it, so `showSceneMenus` takes `$` alone ([app.js](../../tools/viewer/web/app.js)).
- **3.24:** `spawnLayerReady` (whether the Spawns view's layer was made) was true whenever the views' buttons were
  drawn, since the views' switching is made after the Spawns view. The flag and its getter leave
  [spawns_wiring.js](../../tools/viewer/web/spawns_wiring.js), the guard [views.js](../../tools/viewer/web/views.js)'
  `lightButton`, and the name app.js's making of both. [ARCHITECTURE.md](../../ARCHITECTURE.md)'s example of a
  factory's own state given to a later module as a getter now names one that exists: the build queue's controller's
  `state`, which the project manager reads.

Checked: `web_names` clean (98 files); the node suite (36 files); the twenty-edit recording (52 steps) and the stage's
probe of the paths twenty does not walk (44 steps: Reset all, a clear, the landing zones, the header's mission, a
building's box and a no-spawn volume's face, on the Bar and the police station) the same as on the stage's start
commit, on the same test server; browser checks `typed-pose`, `spawns`, `clear-map`, `lights` and `header` pass on
the Bar.
