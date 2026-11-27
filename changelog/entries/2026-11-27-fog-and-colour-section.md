### Fog and colour in the Map settings window (project schema 10)

Stage C5b of the game-likeness plan, design 2B (looks first, values folded): the Map settings window gains a Fog and
colour section, between the sun and the background sound.

- **The looks first**: a row of swatches, each how a grey floor would look under that look's fog and grade. The row
  holds the map's own look (ringed while the project changes nothing), four of the game's maps' looks chosen to stand
  apart from it and from each other, and "All maps…", a list of every map. A look taken gives the map that map's fog
  and grade: one undo step.
- **The values folded**:
  - Fog: on or off, density, height, falloff, and its two colours, away from the sun or moon and toward it.
  - Colour: tint (a colour and its strength), shadows (lift or deepen), grey and bloom.
  - Each fold's line says its values. A slider is one undo step on release, the rest one each.
- **Reset to the map's own** puts the map's values back.
- **Seen at once in the Game look**: the fog and the grade follow while a slider moves.
- **Volumes and the header**: a map whose colour a post-process volume sets says so, naming the volume and its values,
  read only. The header counts the section as "fog and colour changed".
- **The project**: schema 10 adds `atmosphere` (`{fog?, postProcess?}`, only the members that differ from the map's own),
  which the page, the server and the compiler read. A project of schema 9 builds as it did. The Build writes it on the
  map (stage C5a; F-173).
- **The game's maps' looks**: `tools/viewer/atmospheres.json` (91 looks for 97 maps, each with its maps' names and
  records' times), made by `atmosphere.py catalogue <LWR install>` and served at `/atmospheres.json`.
- **The release**: it now ships the viewer's data files its modules read beside themselves. Releases 0.7.0 to 0.7.2
  left `background_sounds.json` out, so their Map settings window could not list the game's background sounds;
  `atmosphere_defaults.json` and `atmospheres.json` ship now too. A release test finds every such file a shipped module
  names.
- Where: [atmosphere_rules.js](../../tools/viewer/web/atmosphere_rules.js),
  [atmosphere_settings.js](../../tools/viewer/web/atmosphere_settings.js) (new),
  [map_settings.js](../../tools/viewer/web/map_settings.js), [index.html](../../tools/viewer/web/index.html),
  [style.css](../../tools/viewer/web/style.css), [lighting.js](../../tools/viewer/web/lighting.js) (`fog()`, the
  `atmosphere` getter), [app.js](../../tools/viewer/web/app.js) (`viewAtmosphere`),
  [editor_state.js](../../tools/viewer/web/editor_state.js),
  [document_state.js](../../tools/viewer/web/document_state.js),
  [document_session.js](../../tools/viewer/web/document_session.js),
  [delete_reset.js](../../tools/viewer/web/delete_reset.js), [project.js](../../tools/viewer/web/project.js),
  [piece_status.js](../../tools/viewer/web/piece_status.js); [projects.py](../../tools/viewer/projects.py) and
  [compiler.py](../../tools/editor/compiler.py) (schema 10); [atmosphere.py](../../tools/viewer/atmosphere.py)
  (`make_catalogue`), [atmospheres.json](../../tools/viewer/atmospheres.json), [viewer.py](../../tools/viewer/viewer.py)
  (`handle_atmospheres`); [make_release.py](../../tools/release/make_release.py); the contract in
  [research/editor-contracts.md](../../research/editor-contracts.md); [ARCHITECTURE.md](../../ARCHITECTURE.md).
- Checked:
  - [atmosphere_rules_test.mjs](../../tools/viewer/tests/atmosphere_rules_test.mjs) (the record tidied, the view's
    values, a look taken, the words, the swatch, the picks, the volumes);
  - [test_atmosphere.py](../../tools/viewer/tests/test_atmosphere.py) (the catalogue's looks against two maps'
    packages);
  - [test_release.py](../../tools/release/tests/test_release.py) (every data file a shipped module names ships);
  - [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)'s `map-settings` on CSmallScout_DirtRoad of export
    43: the own look ringed, a look taken as one undo step, kept in the edit state, drawn in the Game look's grade and
    counted in the header; a slider as one undo step; Reset; all undone.
- Known gaps: the user guide's section comes with the plan's guide stage.
