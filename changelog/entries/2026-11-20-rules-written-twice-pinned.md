### Rules written on both the page and Python sides are pinned by tests on both sides

Review finding 55, its first two items.

**The shared case files are now read by node too.** The new
[shared_cases_test.mjs](../../tools/viewer/tests/shared_cases_test.mjs), part of the node suite, runs the page's
modules on case files that Python's tests already read:

- `cone_cases.json` through `light_rules.js` `effectiveCone`;
- `pose_rule_cases.json` through `poserule.js` `gridMove` and `nearestGridPose`;
- `floor_membership_cases.json` through `floors.js` `floorAt` and `copyFloors`.

Before, these ran through the page's code only in Playwright checks that the runner does not run, or that skip
without Playwright.

**Constants copied by hand are pinned in one file.**
[twin_constants.json](../../tools/viewer/tests/twin_constants.json) is checked against Python's values by
[test_twin_constants.py](../../tools/viewer/tests/test_twin_constants.py) and against the page's by
[twin_constants_test.mjs](../../tools/viewer/tests/twin_constants_test.mjs), as `limits.json` already is. It holds:

- light limits;
- effect and sound value limits;
- the made wall's shortest and longest length;
- wall end insets;
- ground limits;
- the landing zone offsets;
- ship types;
- the library's soft verdicts;
- the classes a building floor lists.

To be read in node, some page constants moved out of [app.js](../../tools/viewer/web/app.js), which still imports them:

- `LIGHT_LIMITS` to [light_rules.js](../../tools/viewer/web/light_rules.js);
- `FRAC_WALL` to [walls.js](../../tools/viewer/web/walls.js);
- `LISTED_CLASSES` to [floors.js](../../tools/viewer/web/floors.js);
- `SOFT` to [piece_categories.js](../../tools/viewer/web/piece_categories.js), which
  [library.js](../../tools/viewer/web/library.js) re-exports.

**Two copied rules became case files.**

- The test stage's levels formula is now
  [prefab_document.js](../../tools/viewer/web/prefab_document.js) `prefabStageLevels`.
  [stage_levels_cases.json](../../tools/editor/tests/stage_levels_cases.json) is read by
  [test_prefab_stage.py](../../tools/editor/tests/test_prefab_stage.py) and the node test.
- The wall join cases copied into `walls_test.mjs` are now
  [wall_join_cases.json](../../tools/editor/tests/wall_join_cases.json), read by
  [test_compiler_generated.py](../../tools/editor/tests/test_compiler_generated.py) and the node test.

[test_lights.py](../../tools/viewer/tests/test_lights.py)'s Playwright cone check now also strips `export const`.

Checked: the node suite (24 files), plus the viewer tests `test_twin_constants` and `test_lights`, and the editor tests
`test_prefab_stage` and `test_compiler_generated`.

Left as they were:

- page-only settings with no Python twin, such as the ground tool's drawn heights and the ships' labels;
- the finding's last three items (council kinds, the Prepare prompt's code, Python against Python), which are outside
  this work;
- app.js's own build clock, which belongs to the build status work.
