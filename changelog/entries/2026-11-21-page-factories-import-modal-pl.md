### The page's factories import modal.js' modalOpen and constants.js' PL instead of being given them

Editor follow-ups, stage P4, item 3.23 (the third of four argument-list commits, one a home module). Nothing the editor
does changes.

- `createMapMenu` ([map_menu.js](../../tools/viewer/web/map_menu.js)), `createNavigation`
  ([navigation.js](../../tools/viewer/web/navigation.js)) and `createProjectMenu`
  ([project_menu.js](../../tools/viewer/web/project_menu.js)) import [modal.js](../../tools/viewer/web/modal.js)'
  `modalOpen`; `createCoverWiring` ([cover_wiring.js](../../tools/viewer/web/cover_wiring.js)), `createLightsWiring`
  ([lights_wiring.js](../../tools/viewer/web/lights_wiring.js)) and `createPrefabPlace`
  ([prefab_place.js](../../tools/viewer/web/prefab_place.js)) import [constants.js](../../tools/viewer/web/constants.js)'
  `PL`. [app.js](../../tools/viewer/web/app.js) gives them neither, and imports neither any more.

Checked: `web_names` clean; ESLint's `no-shadow` (by hand) finds neither name hidden; each factory's parameters
against the keys app.js gives it (61 factories, no difference); the node suite; the twenty-edit recording the same as
on the stage's start commit (52 steps).
