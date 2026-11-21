### The page's factories import piece_records.js' isStream, fromOf and sourceKey instead of being given them

Editor follow-ups, stage P4, item 3.23 (the second of four argument-list commits, one a home module). Nothing the editor
does changes.

- 21 factories took [piece_records.js](../../tools/viewer/web/piece_records.js)' `isStream` (16 of them), `fromOf` (8)
  or `sourceKey` (3), plain exports any module can import; each imports them now, and
  [app.js](../../tools/viewer/web/app.js) gives them no more (it keeps its import of `isStream`, which its own gizmo
  rule and the header's mission change use). The factories: `createBuilderSession`, `createBuildingsWiring`,
  `createClearMap`, `createClipboard`, `createCutaway`, `createDeleteReset`, `createDocumentState`,
  `createEffectsWiring`, `createFlagsPanel`, `createGroups`, `createLibraryTemplates`, `createLightsWiring`,
  `createMadeDrawing`, `createMadeLooksWiring`, `createMapFamilies`, `createPieceStatus`, `createPrefabPlace`,
  `createScenePieces`, `createSelectKind`, `createSelection` and `createSpawnsWiring`.
- [scene_pieces.js](../../tools/viewer/web/scene_pieces.js)' and
  [flags_panel.js](../../tools/viewer/web/flags_panel.js)' headings no longer list them among what they are given.

Checked: `web_names` clean, and ESLint's `no-shadow` (by hand, `web_names`' settings) finds none of these names hidden;
each factory's parameters against the keys app.js gives it (61 factories, no difference); the node suite; the
twenty-edit recording the same as on the stage's start commit (52 steps).
