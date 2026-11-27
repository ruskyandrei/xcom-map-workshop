### Effects drawn by their materials' compiled shaders

Stage E1 of the game-likeness plan: an effect's likeness draws each emitter's material as the game's shader draws it,
in both looks, where the emitter's material can be sliced; the rest keep the textures' roles as before. Export 48,
draw version 6 (research/editor-contracts.md sections 8 and 9; F-220).

- **The slice** (`shader_slice.py`): a particle's material is sliced from its shaders for the particle vertex factory
  its emitter draws with (`slice_material(factory=, particle=True)`), the base pass only: colour, glow, cut-out and
  opacity. The factories' streams are named in `STREAMS` (the corner's UV in the first and second sub-image, the
  particle's colour, the blend between sub-images, the dynamic parameter); a mesh particle's colour and dynamic
  parameter, which reach its material as vector parameters, are read as those inputs too. A soft particle's inputs
  are taken: its clip-space position (an interpolant that is a copy of the position, `Clip`), the scene's depth
  (SceneColorTexture's alpha, `{"engine": "sceneDepth"}`, read at a level: `texld` `lod`) and MinZ_MaxZRatio. The local
  factory's see-through base pass reads its UVs through abs() of a literal, which a particle's slice now follows
  (F-221; a piece's slice still refuses it, so no piece's program changes).
- **The export**: `Exporter.particle_program` (with `Exporter.parameters`, moved out of `material` in its own commit)
  makes the program once a material and factory list, through `material_programs.program` (a list of factories, the
  first the material has; a texture the page gives itself skipped). `effects_draw.py` writes a sprite emitter's
  `program` and a mesh emitter's `programs` (one a drawn section), and follows the dynamic parameter module
  (`DynamicParams`). EXPORT_VERSION 48; no texture, mesh or piece material changes (the piece version stays).
- **The page**: `material_program.js` reads the particle's inputs from the likeness's varyings (`PARTICLE_VARYINGS`),
  the scene's depth through a `progSceneDepth` the shader may give (without it nothing is behind: no fade) and a read
  at a level; `effects_preview.js` makes a sprite's or a mesh section's material from its program (`programMaterial`:
  the colour by the light at its place, its glow, its cut-out, a see-through one's opacity, an added one's colour as
  its shader weighs it), its constants that move with time worked out on the likeness's own clock; a program whose
  textures don't all load falls back to the roles. `effects_sim.js` steps the dynamic parameter (1 each where an
  emitter has none, as the game gives it) and keeps the colour as the game gives it (`raw`) for an emitter drawn by
  its program, whose material reads the channels that carry numbers. `?programs=pieces` draws the likenesses by
  their roles and the pieces by their programs (`?programs=off` both by the old rules), for the probes.
- **Measured** (scratch exports of the lab copy): drawn by their programs, 205 of 208 placed sprite emitters on
  CSmallScout_DirtRoad, 993 of 993 on AlienBase01, every mesh emitter of both. Track H's likeness in the Game look
  (stage e1 against b3): CSmallScout_DirtRoad 10.69 to 5.06, LAbductor_FarmOutskirts 5.79 to 4.28, URB_Bar 5.16 to
  5.20, AlienBase01 16.21 to 13.17; all twelve 9.46 to 6.93. Frames (perf_probe.py, headless, the shots' cameras,
  20 frames, likenesses stepped 3 s first; `?programs=pieces` then on, twice): AlienBase01 with about 925 particles,
  Neutral 2.1 / 2.1 ms against 2.0 / 2.2, Game 3.4 / 3.4 against 3.4 / 3.1; CSmallScout_DirtRoad with about 2,100,
  Neutral 2.5 / 2.5 against 2.4 / 2.8, Game 3.3 / 3.9 against 3.5 / 3.7: the same within the run's spread. Shader
  programs compiled: 70 to 134 and 115 to 193.
- **perf_probe.py** steps the likenesses three seconds before it times a frame (a headless page draws no frames of its
  own, so its frames had no particles), through a new test hook `viewer.stepLikenesses(dt)`, and says how many
  particles it drew.
- Where: [shader_slice.py](../../tools/viewer/shader_slice.py), [shader_eval.py](../../tools/viewer/shader_eval.py),
  [material_programs.py](../../tools/viewer/material_programs.py), [effects_draw.py](../../tools/viewer/effects_draw.py),
  [export.py](../../tools/viewer/export.py), [material_program.js](../../tools/viewer/web/material_program.js),
  [effects_preview.js](../../tools/viewer/web/effects_preview.js), [effects_sim.js](../../tools/viewer/web/effects_sim.js),
  [effects_wiring.js](../../tools/viewer/web/effects_wiring.js), [test_api.js](../../tools/viewer/web/test_api.js),
  [app.js](../../tools/viewer/web/app.js), [perf_probe.py](../../tools/viewer/perf_probe.py),
  [ARCHITECTURE.md](../../ARCHITECTURE.md), [editor-contracts.md](../../research/editor-contracts.md), the
  [findings register](../../research/findings-register.md) (F-220, F-221).
- Checked: [test_shader_slice.py](../../tools/viewer/tests/test_shader_slice.py) (`Particles`: a made-up soft
  particle's program and its fade on numbers, the same shaders refused as a piece's, a mesh particle's colour an input,
  the streams), [test_effects_draw.py](../../tools/viewer/tests/test_effects_draw.py) (`Programs`, URB_Bar of the
  install: the steam's program, nine in ten sprites with one, a mesh emitter's one a section, the dynamic parameter
  read), [material_program_test.mjs](../../tools/viewer/tests/material_program_test.mjs) (a particle's inputs and the
  depth's fade, as GLSL and on numbers), [effects_sim_test.mjs](../../tools/viewer/tests/effects_sim_test.mjs) (the
  dynamic parameter, a raw colour); the `likeness` browser check (an effect drawn by its program) on
  CSmallScout_DirtRoad and URB_Bar, `api-names` with the new hook; the maps' piece materials, textures and meshes
  equal to export 45's.
- Gaps: a lit particle takes no light of the map yet (white: stage E2); the depth behind is not given, so soft edges
  don't fade (stage E3), nor are sub-images blended; the material's time runs on each likeness's own clock in both
  looks, as its particles move; the extra shaders compile as the likenesses first draw, not ahead.
