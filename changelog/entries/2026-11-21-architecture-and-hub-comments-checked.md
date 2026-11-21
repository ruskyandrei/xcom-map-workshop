### ARCHITECTURE.md read against the follow-ups' code, its list of sizes remade, and stage P5's files' comments

Editor follow-ups, stage G, part two (plan step 5, and step 3 in the files stage P5 changed). No code changes: comments
and documents only.

- [ARCHITECTURE.md](../../ARCHITECTURE.md), read for the sections the follow-ups touched: the atomic writer's row now
  says what `test_atomic_files.py` scans for (a file replaced or renamed, not only `os.replace`), names the two modules
  it lists because they move folders (`export.py`, `publication.py`) and that the Build's replaces of the map go through
  `atomic_files` too; the package readers' row names `upkinfo` for a package's summary and tables, `Package.native`, the
  bulk payload's chunks and `frac_walls.lod0`. `api.js`' exceptions, the hub's runs, the readers' rules in section 3 and
  the getter's example (the build queue's `state`) matched the code and are unchanged.
- Its list of sizes over the guidance, remade from `test_structure.py --sizes`: `browser_smoke.py` 6,212 lines,
  `native_copy.py` 3,425, `test_build.py` 2,171 (now fourth), `relight.py` 2,044, `installs.py` 2,018, `build.py` 1,981
  (now above `compiler.py`); `native_copy.build`'s docstring 80 lines; `frac_walls.py::add_walls` is no longer over 150
  and left the list. The sizes stay guidance; `structure.json` is unchanged.
- [clear_map.js](../../tools/viewer/web/clear_map.js)'s heading: `createClearMap` takes no cutaway (the edit hub's runs
  keep the other areas up, which it now says), and the landing pieces are set by `map_families.js`.
- [spawns_wiring.js](../../tools/viewer/web/spawns_wiring.js): `spawn_places` and `mission_objects` are
  `mission_edits.py`'s, not the compiler module's.
- [app.js](../../tools/viewer/web/app.js): the stray heading "Edits: the gizmo moves whole actors ..." that headed no
  code is gone.
- [lights_wiring.js](../../tools/viewer/web/lights_wiring.js): `warnLights`' comment no longer names `warnNotBuilt`,
  taken out with the untried warnings.
- Checked against the code P5 left and found true, so unchanged: the edit hub's comments (its new runs `cleared`,
  `project-missions`, `zone-edit`, `spawn-box` and their callers), `scene_start.js`' heading (`showMapMenu`), the
  headings of `delete_reset.js`, `zones_wiring.js`, `buildings_wiring.js`, `views.js` and `spawns_wiring.js`, and
  `editor_state.js`' and `cutaway.js`' remaining mentions of app.js (`open`, `readLooks`, `startScene`, `editChanged`,
  the pointer handlers, the draw loop, View options).

Checked: `python -B tools/run_tests.py repo node` (all pass); `tools/viewer/tests/web_names.py` (98 files, clean); the
names written found with `git grep`; line endings kept (LF, none mixed).
