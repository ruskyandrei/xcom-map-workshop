### Comments and documents name the code where it is now; the viewer README documents the page's checks

Editor follow-ups, stage G, part one (items 5.1, 5.2, 5.4 to 5.6, 3.3 and the stale words the stages found). No code
changes: comments, docstrings and documents only.

- **Code named where it was** (5.1, 5.6): the compiler's names now in its family modules are named there:
  `effect_override` and `effect_add` in [research/editor-contracts.md](../../research/editor-contracts.md)
  (`effect_edits.py`), with `native_split` (`native_edit`); `generated_valid` and `effect_values` in
  [prefabs.py](../../tools/viewer/prefabs.py); `source_floor_match` and `BUILDING_SAME` in
  [buildings.py](../../tools/bake/buildings.py) (`building_edits`); `STAGE_GRID_MAX` in
  [prefab_bounds.py](../../tools/viewer/prefab_bounds.py); `stage_max`, `cursor_storeys`, `storeysNow` and
  `copyDragBegin` in [tools/viewer/README.md](../../tools/viewer/README.md); `native_split` and `NATIVE_CLASSES` in
  [build.py](../../tools/editor/build.py)'s docstring. The page's comments that said "compiler.py" for `stage_max`,
  `cursor_storeys`, `added_floors`, `ladder_ends`, `floor_now`, `wall_joins`, `tile_corner`, `STAGE_MAPS`,
  `POINTS_VERSION`, `LIGHT_RANGES`, the effect value limits, `SPAWN_EDIT_KINDS`, `SPAWN_VALUE_KEYS` and the buildings'
  warnings now name their module (`floors.js`, `walls.js`, `ladders.js`, `selection.js`, `map_grid.js`, `project.js`,
  `ground.js`, `light_rules.js`, `effects_rules.js`, `spawns_view.js`,
  [clear_map_test.mjs](../../tools/viewer/tests/clear_map_test.mjs)).
- **The page's comments that named app.js** for what moved out of it (5.5, 5.6) name the module now:
  [pieces.js](../../tools/viewer/web/pieces.js) (`spawnAddEntries`, `zoneEntries`),
  [piece_records.js](../../tools/viewer/web/piece_records.js) (who reads a state from a root),
  [popups.js](../../tools/viewer/web/popups.js) (`renderProjectMenu`), [walls.js](../../tools/viewer/web/walls.js)
  (`madeShapeOf`, `MADE_MAX_TILES`), [build_window.js](../../tools/viewer/web/build_window.js) and
  [build_options.js](../../tools/viewer/web/build_options.js) (`renderBuild`, `buildProject`),
  [editor_state.js](../../tools/viewer/web/editor_state.js) (the `set<Name>Value` rule, `useMapFamilies`, `recipeOf`,
  `templateFor`, `projectListings`, `setNormalView`, `syncLights`, `flashHint`, `libraryTemplate`, the dialogs' check,
  the views' switching, the map's families, `exportProblem`), [library.js](../../tools/viewer/web/library.js),
  [made_breaking.js](../../tools/viewer/web/made_breaking.js) (the keys),
  [cutaway.js](../../tools/viewer/web/cutaway.js) and [prepare.js](../../tools/viewer/web/prepare.js) (the test hooks,
  `prepareOpened`), `floors.js` and `ladders.js` (`tileCorner`, `showGrid`),
  [style.css](../../tools/viewer/web/style.css) (`gridWarning`; `.libhead` heads the Add panel, not the look picker),
  [web_names.config.mjs](../../tools/viewer/tests/web_names.config.mjs),
  [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py) (`wheelZoom`) and
  [test_compiler.py](../../tools/editor/tests/test_compiler.py) (`ladderNow`). The comments that say a factory "takes
  what it needs of app.js, when app.js makes it" are true and stay.
- **The made pieces' heading** in [made_handles.js](../../tools/viewer/web/made_handles.js) (5.4): the Build menu draws
  a wall, and an opening's handles move by the snap setting (`OPENING_STEPS`). The "Prefabs" section comment in
  [prefab_place.js](../../tools/viewer/web/prefab_place.js) heads the factory again, `prefabPlacementProblem` under it
  with a line of its own.
- **3.3:** [builder_session.js](../../tools/viewer/web/builder_session.js) says why `builderDocumentNow` restores a
  recipe (a copied light's, effect's, sound's or flare's: `editStateNow` gives only the pieces theirs);
  [decomp.py](../../tools/upk/decomp.py) `read_chunk` names `texture.decompress_payload` among its users.
- **Stale words the stages found:** [missions.js](../../tools/viewer/web/missions.js) no longer calls `kindKey` the twin
  of the removed `kind_of_export`; [test_native_fields.py](../../tools/upk/tests/test_native_fields.py) counts four
  readers of `mesh_lods` (`frac_walls.lod0` the fourth, tested in its own suite); the repository
  [README.md](../../README.md) says `XCOM_COOKED` serves the viewer suite's tests of a map too and is each
  `XCOM_<MAP>_UPK`'s default; [relight_probe.py](../../tools/bake/relight_probe.py) names `set_shadow_refs`; the viewer
  README names `shell.py scenery_to_walk` (it said `walk_scenery`, a name the code never had).
- **The viewer README's Checks** (5.2): the browser checks need `--url` (the usage line lacked it); a change to the page
  runs `web_names.py` and `browser_smoke.py --all`; what `web_names.py` finds and where ESLint goes; `--all`'s ten runs
  on fresh test servers, ports 8795 to 8798 or `--ports`, `--scratch`, `--cache`, `--play-install`; the `api-names`
  check and `--write-api-names`; and `--all` without `--play-install` copies the Play files from the settings' install
  when they come to less than 300 MB (it said Play was skipped).

Checked: `python -B tools/run_tests.py repo node` (44 tests and 36 files, all pass); `tools/viewer/tests/web_names.py`
(98 files, clean); every name written found with `git grep`; line endings kept (every file changed is LF, none mixed).
Left for part two: the same in the files stage P5 is changing (`app.js`, `edit_hub.js`, `clear_map.js`,
`spawns_wiring.js`, `scene_start.js`, `views.js` and the rest of its list) and `ARCHITECTURE.md`.
