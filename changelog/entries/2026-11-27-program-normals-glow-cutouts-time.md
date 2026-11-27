### Materials' programs draw their normals, glow, cut-outs, see-through and moving parts

Stages A5 to A8 of the game-likeness plan, on the programs A-S4 draws: each material's program now gives the page more
than its colour and highlight.

- **A5, the normal**: the program's tangent-space normal turns the lighting per pixel (the frame in the view's space
  from the mesh's tangents, three's normal the third axis). Its direction was held against close game shots of URB_Bar's
  brick: in both, the edges toward the light are the bright ones (lower edges under the bar's lamps, upper edges under
  the moon).
- **A6, glow and the sky**: what a material gives off (a lit sign, a screen, the arcade machines) comes from its program
  in place of the guessed glow; an unlit material is its glow alone. The map's sky dome shows in the Game look only,
  uncut, drawn first at the far plane, never picked or shadowed.
- **A7, cut-outs and see-through**: a cut-out goes where the program's mask says (the game's `texkill`), a translucent
  material takes the program's opacity, an additive one adds its whole colour, a modulating one multiplies. A
  see-through material the game draws in its distortion pass (the export marks the program `distortion`) is not drawn:
  it bends what is behind it, and drawn plainly it covered it.
- **A8, time**: a program's uniforms that move with time (a panner, a pulsing glow, the alien energy door) are worked out
  each frame in the Game look and stand still at time nought in the Neutral one.
- Where: [scene_pieces.js](../../tools/viewer/web/scene_pieces.js) (`withProgram`, `programFrame`, the sky's material),
  [material_program.js](../../tools/viewer/web/material_program.js) (the view frame for the normal; `evaluateUniform`,
  `constantAt`), [lighting.js](../../tools/viewer/web/lighting.js) (a program's material keeps its own patch),
  [cutaway.js](../../tools/viewer/web/cutaway.js) and [lights_wiring.js](../../tools/viewer/web/lights_wiring.js) (the
  sky with the look), [app.js](../../tools/viewer/web/app.js), [shader_slice.py](../../tools/viewer/shader_slice.py) (the
  `distortion` mark; the contract in [research/editor-contracts.md](../../research/editor-contracts.md) section 9); the
  close views in [likeness_closeups.json](../../tools/lab/likeness_closeups.json).
- Checked: [uniform_cases.json](../../tools/viewer/tests/uniform_cases.json), written from
  `shader_slice.evaluate_uniform`, holds `evaluateUniform` and `constantAt` to the same numbers
  ([material_program_test.mjs](../../tools/viewer/tests/material_program_test.mjs),
  [test_shader_slice.py](../../tools/viewer/tests/test_shader_slice.py)); in the browser on export 43: the Bar's window
  frames and doors in the game's tints, its windows dark glass, the arcades glowing, the sky dome in the Game look, the
  floor cut keeping the programs, the energy door moving in the Game look and still in the Neutral one; close game shots
  of URB_Bar (a hidden run on the lab copy) against the editor's.
- Known gaps: at those close cameras the game hides the bar's roof, awnings and sign, which the editor's all-floors view
  keeps; some effects' see-through sprites (AlienBase01's domes, DirtRoad's smoke) are drawn brighter than the game's, as
  before this stage.
