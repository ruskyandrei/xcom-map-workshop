### The page's factories import dom_words.js' helpers instead of being given them

Editor follow-ups, stage P4, item 3.23 (the first of four argument-list commits, one a home module). Nothing the
editor does changes.

- 28 factories took one or more of [dom_words.js](../../tools/viewer/web/dom_words.js)' `text`, `field`, `plural`,
  `short` and `copyText` in their argument object, though any module can import them; each imports them now, and
  [app.js](../../tools/viewer/web/app.js) gives them no more (it now imports only `segButton` and `segmented` from
  there). The factories: `createAlign`, `createBuildPlay`, `createBuilderSession`, `createBuildingsWiring`,
  `createClearMap`, `createClipboard`, `createCutaway`, `createDeleteReset`, `createDocumentSession`,
  `createDocumentState`, `createEffectsWiring`, `createFlagsPanel`, `createFloorListings`, `createGroups`,
  `createLibraryTemplates`, `createLightsWiring`, `createLoading`, `createMadeBreaking`, `createMadeDrawing`,
  `createMadeHandles`, `createMadeLooksWiring`, `createMadePanel`, `createPrefabPlace`, `createProjectMenu`,
  `createSelectKind`, `createSelection`, `createSpawnsWiring` and `createZonesWiring`.
- [selection.js](../../tools/viewer/web/selection.js)' `plural` and `short` parameters, which shadowed its own import
  of them, are gone with the rest.
- [scene_start.js](../../tools/viewer/web/scene_start.js)' `showImportNotes` imports `text`, `short` and `plural` and
  takes only `$`.
- [effects_wiring.js](../../tools/viewer/web/effects_wiring.js)' likeness pane's text box is `paneText`, no longer a
  `text` that hid the helper of that name in its function.
- [loading.js](../../tools/viewer/web/loading.js)' and
  [library_templates.js](../../tools/viewer/web/library_templates.js)' headings, and app.js's comment above
  `createLoading`, no longer say they are given the words helpers.

Checked: `web_names` clean, and ESLint's `no-shadow` (run by hand with `web_names`' settings) finds none of these
names hidden where it found three on the start commit; each factory's parameters against the keys app.js gives it (a
script of the stage's, 61 factories: none taken and not given, none given and not taken); the node suite; the
twenty-edit recording the same as on the stage's start commit (52 steps).
