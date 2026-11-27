### Materials drawn as the game's shaders draw them (the page side of export 43)

Stage A-S4 of the game-likeness plan: the editor draws each piece's colour and highlight by its material's program
(the slice of its compiled shaders the export writes), with the meshes' own vertex colours and the pieces' painted
ones. A blended ground shows the game's mix of its layers, a tinted building its tint, a painted lot its grime.
KB-25 is fixed and taken out of [KNOWN-BUGS.md](../../KNOWN-BUGS.md); F-167 is marked fixed
([findings-register.md](../../research/findings-register.md)).

- [material_program.js](../../tools/viewer/web/material_program.js) (pure): a program as GLSL (its inputs as
  varyings in the game's axes, its instructions one statement each, literals in the text and the material's values
  as uniforms, so instances of one material share one compiled shader), cut to the outputs drawn (`programFor`), and
  the same program run on numbers.
- [scene_pieces.js](../../tools/viewer/web/scene_pieces.js): `withProgram` patches a material after the local lights'
  patch: the colour in place of the texture picked by name, the highlight's colour and power (Phong's power as
  Blinn's times four, three's normalisation taken back, so a highlight is as strong as the game's); the material's
  cut-out, glow and glass stay as before (A5 to A7). `programColours` gives a mesh without vertex colours white ones,
  as the game does, and a piece with painted colours a geometry of its own sharing every other buffer.
  `?programs=off` in the address draws without them (for the probes).
- [lighting.js](../../tools/viewer/web/lighting.js): a material drawn by its program takes no highlight from the
  map's placed lights (in the game those are baked into lightmaps, whose pass has none), only from the sun.
- [app.js](../../tools/viewer/web/app.js): the pieces' shaders compiled ahead as a map opens (`compileAsync`), and the
  programs' camera given each frame (`programFrame`).
- Pictures drawn again: the look picker's (`PICTURE.version` 2, [look_picker.js](../../tools/viewer/web/look_picker.js))
  and the Add panel's piece pictures (their key, [library.js](../../tools/viewer/web/library.js)).
- [export.py](../../tools/viewer/export.py): a texture channel split out of a DDS texture is a PNG and no longer
  copies its source's `container` (found by the browser check: the page took those PNGs for DDS files).
- Measured (`perf_probe.py` on export 43, this PC, the Neutral look; programs off, then on; frames the mean of two or
  three runs):

  | Map | Frame without / with the shadow pass (ms) | Draw calls | Shader programs | Texture memory (MB) | Opening (s, cold) |
  | --- | --- | --- | --- | --- | --- |
  | CSmallScout_DirtRoad | 4.4 / 6.2, then 4.5 / 6.4 | 1,873 | 29, then 47 | 133, then 182 | 2.2, then 3.1 |
  | URB_Bar | 5.9 / 7.4, then 6.0 / 7.4 | 1,571 | 39, then 59 | 333, then 399 | 2.3, then 4.0 |
  | URB_PoliceStation | 5.3 / 6.9, then 5.5 / 7.1 | 1,609 | 33, then 60 | 379, then 455 | 2.4, then 4.5 |
  | EWI_HQAssault | 3.5 / 5.4, then 3.95 / 5.85 | 1,655 | 25, then 34 | 141, then 159 | 1.9, then 2.6 |

  Opening a second time (textures in the browser's cache) takes 0.3 s more (Police Station 2.2, then 2.5 s); the
  shaders' compile ahead 0.3 to 0.6 s. HQ Assault's frame grows by 13% (draw-call bound: each program material binds
  more textures), past the plan's 5%: it goes to the user before the branch is merged.
- Likeness scores (track H, mean over twelve views): the Neutral look 24.6 before, 23.4 now; the Map lighting mode
  18.0 before, 17.1 now (Dirt Road and the farm closer, the Bar and the alien base a little further, their light
  being the editor's live lights in place of the game's baked ones).
- Checked: [material_program_test.mjs](../../tools/viewer/tests/material_program_test.mjs) (four programs' GLSL and
  numbers against shader_eval.py's, instances sharing one shader, a program cut to its colour); in the browser on
  export 43: the Bar opened with no console errors and 180 materials drawn by programs in 25 shaders, the Interior
  mode and the floors' cut, a selection's highlight, the Add panel's pictures; the Barrens' Rocks River ground and a
  made ground in its look drawn as olive grass over mud (a copy of XComLevelActor_140 made from numbers, the Build's
  vertex colour 0.93, 0.89, 0.98), where before both were the Rock texture; the Bar's window frames and doors in their
  tints, as the game shows them.
- Known gaps: normals, glow, cut-outs and opacity by the programs come in A5 to A7; programs that move with time are
  drawn still (A8); a material whose program reads a vertex shader's own UV maths stays as before.
