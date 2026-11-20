### The Effects view in a module of its own (effects_wiring.js)

Editor refactor, stage P6, second view: the Effects view's wiring moves out of app.js into one module. Nothing the
editor does changes.

- **[effects_wiring.js](../../tools/viewer/web/effects_wiring.js)** is new. `createEffectsWiring` is made once by
  app.js, with what it needs of app.js in one argument object (as `createLightsWiring` is): the camera, the renderer
  and the scene, the textures and meshes as the map's pieces read them, the other views' switches, the landing zones
  (`zoneState`, `carried`), and the Lights view's `ownerRoot`, `setLightsShown` and `lightButton`. It holds, moved
  verbatim, the whole run of app.js from the Effects view's heading to its kinds' flyout, after `setNormalEffects`:
  - the roots: `makeEffectRoot`, `addEffectRoots`, `removeEffectRoots`, `buildEffects`, `effectViewOnly`,
    `effectNow`, where each stands now (`deriveEffects`, `landingShifts`), what is drawn (`refreshEffects`,
    `paintEffects`);
  - the likeness: `refreshLikenesses`, `stepLikenesses`, a copy being placed (`ghostLikeness`), the Add panel's
    pictures (`effectPicture`) and hover pane (`hoverLikeness`, `drawLikenessPane`), `setLikeness` and its tick box;
  - the panel (`effectPanel`), the Wave preview (`playWave`, `stopWave`, `paintWaves`), the fixed box or the sound's
    spheres (`drawEffectShape`), a marker picked and framed (`pickEffect`, `pickEffectAt`, `frameEffect`), Keep where
    it is, the values and their controls (`changeEffectValues`, `effectValueControls`, `numberField`);
  - the project's records of effects and sounds (`effectState`, `clearEffectEdits`, `applyEffectRecord`,
    `addedEffectOf`), an added copy (`addedEffect`), the tip under the pointer (`effectTip`), the view on or off
    (`setEffectsShown`, `setNormalEffects`) and the handlers of its Keep button, Normal switch and kinds' flyout.

  Its own state is inside it: the kinds shown, the likenesses and the hover pane. It gives app.js back the 44
  functions and objects app.js and its hooks call, under the same names; the Spawns view's panel calls its
  `numberField`, as it did.
- **[editor_state.js](../../tools/viewer/web/editor_state.js)** owns what the view shares with other areas, each with
  its setter: `effectsDirty`, `effectMarkers`, `normalEffects` (`setNormalEffectsValue`), `wavePlayer`,
  `likenessOn`, `likenessThin`, `likenessCount` (the edit hub, the keys, the draw loop and the test hooks read or set
  them), and what the view reads or sets of other areas: `liveCache` (groups' pieces now), `pickCentres` (box select),
  `pickedSpawn` (`setPickedSpawnValue`, beside the Spawns view's `setPickedSpawn`), `pointer` and `tipDirty`. The
  likeness's switch is still read from the browser's storage where its `let` was, now through its setter. The Wave
  preview's one chained write (`playWave`: `player = wavePlayer = { ... }`) is `player = setWavePlayer({ ... })`: that
  setter gives back what it set.
- **[app.js](../../tools/viewer/web/app.js)** makes the module where the run of code was, so what it does as the page
  loads (its layers added to the scene, the kinds read from storage, the tick boxes' handlers) happens at the same
  point. The Lights view, the scene to and from a document and prefabs saved and placed are made before it and given
  its functions, so they are given functions that call them (`drawEffectShape`, `effectValuesEditable`,
  `setEffectValues`, `setEffectsShown`; `addEffectRoots`, `addedEffectOf`, `applyEffectRecord`, `effectState`;
  `effectViewOnly`); `stopPickBox` is made further down, so the module is given a function that calls it. Each
  assignment to a moved name is now its setter's call, with the same value (45 writes). app.js: 10,136 lines to
  9,329; its `let` statements 80 to 73 (119 names to 106); its top-level functions 662 to 600.
  [ARCHITECTURE.md](../../ARCHITECTURE.md) names the module, its row in where new code goes and the state it added to
  editor_state.js. The comments of [effects_view.js](../../tools/viewer/web/effects_view.js),
  [effects_rules.js](../../tools/viewer/web/effects_rules.js), [effects_preview.js](../../tools/viewer/web/effects_preview.js)
  and app.js that placed the view in app.js name the module.

Checked:
- **The move:** [moved_code.py](../../tools/repo/moved_code.py) against the commit before: the 62 moved functions are
  the same with the 21 substitutions of a write by its setter's call (without them, 10 differ). app.js against
  itself, with the same substitutions: its 600 functions are the same, and the 62 moved are only in the old file
  (without them, 16 differ). The whole moved text, statements as well as functions (830 lines), is the old text line
  for line, the factory's indent aside, with those substitutions and the likeness's `let` that became its setter's
  call. No code that runs as the page loads, before either view's module is made, reaches or reads what it returns (a
  scan of app.js's top level).
- `web_names` is clean (58 files), and the node suite passes (31 files).
- **Browser checks** on a test server, on the commit before the Lights view's move and on this change: `api-names`,
  `effects`, `flares`, `likeness`, `effect-values`, and the Lights view's `map-lights`, `lights`, `dense-lighting`
  and `light-grid` (it is given the Effects view's functions now), passed. On this change, in one run with them, the
  checks of what reads the views' switches and the effects' records: `streams`, `spawns`, `typed-pose`,
  `destruction`, `adding`, `groups`, `copy-drag`, `box-select`, `floor-boxes`, `map-buildings`, `clear-map`,
  `library`, `cover`, `floor-tiles`, `projects`, `prefabs`, `prefab-effects`, `header`, `play-area`,
  `library-effects` and `library-flares`: 30 ran, all passed (4 min 26 s, with other work on the computer; the run
  exits 1 only because `streams` skips its streamed piece's edit on the Bar). The likeness check's frame time with
  the likenesses drawn (16 ms twice here) is the commit before's under the same load (16 and 22 ms on the base): the
  computer's load, not the move.
- **`browser_smoke.py --all`** on fresh test servers, with a scratch cache and `--play-install <scratch game>`, after
  both views' moves: the nine runs of the editor's checks pass, 70 checks ran and 6 skipped, each for its map or its
  run (TempleShip's two, the police station's light bar and Play run elsewhere; `streams`' edit and the patch previews
  have nothing on the Bar's export to work on), 14 min with other work on the computer. The Play run was refused
  before it played: the server's play status said "XCOM is running", since a game had been started on the computer
  (by other work) during the run. Nothing of Play moved in this stage.
