### The page's dead code taken out: the Add panel's old look and wall rows, unused names, CSS that matches nothing

Review finding 63, the page's part. Nothing a user does changes, except the Break buttons' pressed look.

- **The Add panel's removed wall and look entries** ([app.js](../../tools/viewer/web/app.js),
  [pieces.js](../../tools/viewer/web/pieces.js), [library.js](../../tools/viewer/web/library.js)): nothing has made
  `lookPicker` or `wallLook` entries since the Build menu replaced them. Their branches in `chooseEntry`, their two
  row builders and four icon painters, the filters' terms for them, and the look picker's "click to draw in this look"
  path are gone. The picker is opened only for a piece being given a look now, so `openLookPicker` takes `onChoose`
  always. `lookChosen` stays: the eyedropper (I while drawing) still draws in the look it picks.
- **Unused in app.js:** the imports `STAGE_LEVELS_PLAYED`, `zonePlace`, `measurePrefab`, `PREFAB_PLAYED_LEVELS`,
  `PREFAB_PLAYED_TOP`, `QUARTER` and `END_INSETS`, the never-called `isLightRoot`, `sizeEditable` and `groundLookNow`
  (its only caller was a removed row), `cutaway`'s constant `chosen` and the test that read it, and the collision
  read's "another map opened meanwhile" guard (one map per page).
- **`FRAC_WALL`** ([walls.js](../../tools/viewer/web/walls.js)) keeps only `minLength` and `maxLength`, the two the
  page reads and `twin_constants.json` pins.
- **Modules:** `floors.js` `stackOf`, `project.js` `READ_VERSIONS` (three node tests asserted its value and nothing
  else read it), `lighting.js`'s `dropped` (always 0) and `map_picture.js`'s unused `clampFrame`
  import. 47 exports used only in their own file are no longer exported; `SWEEP` stays, as
  `test_compiler_generated.py` reads its line, and so do names sharing a line with an export others use.
- **CSS and markup** ([style.css](../../tools/viewer/web/style.css), [index.html](../../tools/viewer/web/index.html)):
  - rules that match nothing: `.piece` and its states, `.tag.group`, `.chip.group.open`, `.flagrow .flagwhy` and
    `.mapsizerow`;
  - 17 `X[hidden] { display: none }` rules, which `[hidden] { display: none !important }` already covers;
  - `.flagrow`, `.flagrow.off`, `.wallopening` (with its `strong`, `small` and `button`) and `#effectValues .name`
    written twice, each now one rule with the values that won;
  - the two tokens `:root` never defined (`--warn-text`, `--text`) written as the colours they fell back to;
  - seven ids nothing names (`effectEdit`, `spawnAbout`, `groupIcon`, `flagsNote`, `groundGridRow`, `likenessRow`,
    `managerHead`; none in the browser checks, `take_shots.py` or the guide) and the unused `i-unlock` symbol.
- **A pressed Break size button** was white on the accent colour, about 1.7:1. It now takes the pressed look the rail's
  buttons have (accent text on the accent's dark ground, ringed).

`looks.js` `looksLoaded` stays: round one's failed-reads browser check reads it.

Checked: the node suite; a script that every named import between the page's modules and tests names an export; the
full browser smoke on URB_Bar with `--projects` on a scratch server (passing whole for the first time since the camera
checks moved on: its field check focused the Add panel's hidden filter, so the keys reached the camera; the panel is
opened first now), and round one's editing checks and `documents` and `looks`.

Left: the sample-scope study code in `startScene` (`originalPositions`, the three URB_Bar actor names) stays until the
server side's sample export is settled.
