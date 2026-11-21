### The Lights view's storage keys with the Lights view (lights_wiring.js)

Editor refactor, stage P9, third part: the storage keys of View options' Area lights, reach outlines and sun and sky
list (`AREA_SHOWN`, `REACH_SHOWN`, `SKY_SHOWN`), which stage P9's first part found still in app.js, move to the Lights
view's module. Nothing the editor does changes.

- **[lights_wiring.js](../../tools/viewer/web/lights_wiring.js)**: the keys' constant, moved verbatim from app.js with
  `export`, at its top before the factory.
- **[app.js](../../tools/viewer/web/app.js)** imports them: it still reads the two switches from them where it did as
  the page loads, gives `AREA_SHOWN` to the selection, and its View options' handlers write them. 1,371 lines to 1,370.
- [ARCHITECTURE.md](../../ARCHITECTURE.md): the Lights view's part in how the page fits.

Checked: the constant the same text (`export` aside); `web_names` clean; the twenty-edit recording the same as on the
stage's start commit, all 52 steps; browser checks `api-names`, `typed-pose`, `lights`, `header` and `small-defects`
pass.
