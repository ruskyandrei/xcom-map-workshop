### A clear is a set of parts: the project, the compiler, the Build and the page's state

The first stages of Clear map by parts (the user, 24 November 2026: "allow clearing just parts of a map instead of
all"): the project, the compiler, the Build and the page know which parts of a map were cleared, and the page can make
a clear of any of them in one undo step. The Clear map window is still the old one, making the whole clear; its parts
come in the next stage.

- **The project (schema 9)**: `cleared` is the parts cleared, `{"pieces"?, "lights"?, "effects"?, "triggers"?}`, each
  `{}` or `{"keepOutside": true}`. `cleared: true` of schema 1 to 8 reads as every part, with `clearKeepsOutside` on
  each and the triggers left out with `clearKeepsTriggers`, so an old project builds as it did; the page saves it in
  the new form. The server takes the new form and refuses a part it doesn't know
  ([projects.py](../../tools/viewer/projects.py)); the format page says it
  ([editor-contracts.md](../../research/editor-contracts.md)). The parts are pinned for every side in
  [twin_constants.json](../../tools/viewer/tests/twin_constants.json).
- **The compiler** ([mission_edits.py](../../tools/editor/mission_edits.py) `cleared_mark`, `CLEAR_PARTS`): what
  followed "cleared" follows its part. The Pieces part lets the grid shrink, lays no ground, drops Long War's patch
  levels, takes the map's cursor volumes and checks the landing zones as before; the Triggers part makes a deleted
  piece or a kept spawn point that the script waits on a note rather than a warning
  ([compiler.py](../../tools/editor/compiler.py), [spawn_edits.py](../../tools/editor/spawn_edits.py),
  [building_edits.py](../../tools/editor/building_edits.py), [floor_edits.py](../../tools/editor/floor_edits.py),
  [diagonal_edits.py](../../tools/editor/diagonal_edits.py), [light_edits.py](../../tools/editor/light_edits.py)).
  The spec's `cleared` is `{grid?, parts: {part: {keepOutside?: box}}}`; the report's `cleared` names the parts, in
  place of `clearKeepsOutside` and `clearKeepsTriggers`. A part it can't read is left out (`cleared-shape`) and the
  others are cleared.
- **The Build** ([native_copy.py](../../tools/bake/native_copy.py) `CLEAR_PARTS`, `clear_level`): `CLEAR_OUT` and
  `CLEAR_TRIGGERS` are split into four parts, nothing added or dropped (the install's 98 base maps read: every class
  falls in one part, stays, or is named as before). Each part keeps the outside on its own. The whole-grid rebuild
  volume, the hides without volumes of their own, and the shell stage's `--clear` and `--no-ground`
  ([build.py](../../tools/editor/build.py)) follow the Pieces part. The manifest's `cleared` record names the parts.
  [clear_bar_project.py](../../tools/editor/examples/clear_bar_project.py) takes `--parts`.
- **The page** ([clear_parts.js](../../tools/viewer/web/clear_parts.js), the parts' rules;
  [editor_state.js](../../tools/viewer/web/editor_state.js) `clearedParts`, `cleared` now the Pieces part): saved,
  read, recovered and taken off by Reset all as the parts ([project.js](../../tools/viewer/web/project.js),
  [document_state.js](../../tools/viewer/web/document_state.js),
  [document_session.js](../../tools/viewer/web/document_session.js),
  [delete_reset.js](../../tools/viewer/web/delete_reset.js)). The view draws what each part's clear leaves: a light
  the editor only shows goes with the Lights part, a glowing piece's light and a patch level's with the Pieces part
  ([lights_wiring.js](../../tools/viewer/web/lights_wiring.js)), the map's effects with the Effects part
  ([effects_wiring.js](../../tools/viewer/web/effects_wiring.js)), each part's kept outside its own. The clear
  ([clear_map.js](../../tools/viewer/web/clear_map.js) `clearParts`) does, for each part asked, what the whole clear
  did to it, in one undo step; `clearMap` is a clear of every part. A Lights clear counts no glowing piece's light
  now: those go with the pieces.

Checked: [test_compiler.py](../../tools/editor/tests/test_compiler.py) (the old form read as every part, with and
without the outside and the triggers; one part alone leaves the grid, the patch levels and the warnings as they are;
a part it can't read left out; the notes that follow the Triggers part); [test_projects.py](../../tools/viewer/tests/test_projects.py)
(schema 9 saved, a page saving 8 is stale, bad parts refused); [test_clear_level.py](../../tools/bake/tests/test_clear_level.py)
(each part alone on URB_Bar and CSmallScout_Roadhouse takes its classes and leaves every other listed actor and adds
no export without the pieces; the four together are the whole clear); the old and new whole clear written byte for
byte the same on both maps, as it is, keeping the outside and keeping the triggers; `build_outputs.py` recorded on
the base and on this stage and compared: no built map or package file differs, only the project's schema, the
reports' clear keys and the manifests' parts record; [clear_parts_test.mjs](../../tools/viewer/tests/clear_parts_test.mjs)
and [clear_map_test.mjs](../../tools/viewer/tests/clear_map_test.mjs) (old and new forms read the same, a part cleared
twice); the browser checks `clear-map`, `map-buildings` and `cursor-floors` on a test server; the hooks' names
recorded again; the editor, viewer, bake and node suites.

Known gaps: on four maps (DEMO_SonOfFacemelt, DLC2_2_Deluge, Act1_IntroLevel, URB_SlaughterhouseA) 39 lights that light
only their own channels are baked into pieces; a Lights clear takes them out and their light stays baked into the
pieces that stay, even with the bake.
