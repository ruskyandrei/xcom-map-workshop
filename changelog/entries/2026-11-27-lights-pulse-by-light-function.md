### Lights the map pulses by a light function pulse in the Game look

Stage F1 of the game-likeness plan: a light the game changes by a light function (a material drawn on the light) is
drawn changing the same way in the Game look. In the install that is DLC2_3_Furies' four toggleable point lights, which
go from none to full and back every 2 seconds (findings register F-232).

- **The slice** ([shader_slice.py](../../tools/viewer/shader_slice.py) `slice_light_function`): a material's light
  function shader (`FLightFunctionPixelShader`) as a program of the materials' form, with one output, `light`: the
  factor the game multiplies the light by, the shader's square-root encoding undone, its engine parameters taken as
  greyscale with no fade. A light function that reads where the light falls (a texture projected from the light) is
  refused.
- **The export** ([light_functions.py](../../tools/viewer/light_functions.py), [export.py](../../tools/viewer/export.py)):
  `EXPORT_VERSION` 46, a light record's `lightFunction` (its material, its program, whether it moves), where the export
  makes programs; a light function with no material gives none; one that can't be followed is drawn steady and named in
  the diagnostics. The form is section 12 of [editor-contracts.md](../../research/editor-contracts.md).
- **The page**: [material_program.js](../../tools/viewer/web/material_program.js) `lightFunctionAt` (the factor at a time),
  [lighting.js](../../tools/viewer/web/lighting.js) `flicker` (each such light's colour times it, in the local lights'
  data, where the Game look draws the map's lights; not while Solo dims the map), called by
  [app.js](../../tools/viewer/web/app.js)'s draw loop at the clock the materials' moving uniforms use. Maps without a
  light function do nothing more each frame.
- **Checked**: [test_light_functions.py](../../tools/viewer/tests/test_light_functions.py) (the `viewer` suite) and
  [material_program_test.mjs](../../tools/viewer/tests/material_program_test.mjs) (the `node` suite) hold Python's and
  the page's numbers to [light_function_cases.json](../../tools/viewer/tests/light_function_cases.json) (the pulse at seven
  times, `0.999 x (1 + sin(pi t)) / 2`); on the install, Furies' four lights carry the case file's program and its sun's
  empty light function gives none. A browser check (browser_smoke.py `check_light_functions`, part of `map-lights` on a
  map with such a light) on Furies' export, headless: full at 0.5 s, none at 1.5 s, half at 0, moving on the draw loop's
  own, left alone in the Neutral look.
- **Known gaps**: the game's clock starts with the battle, so the pulse is not in step with a game's. Lights that three
  maps flicker by a looping Matinee (a point light of each Deep Woods map, one of Act1_IntroLevel) stay steady. On Furies the `map-lights`
  check stops before this part, at its Game frame probe, which puts a square 10 units before a camera whose near plane is
  42 there (the map frames from far off); the light function part was run on its own.
