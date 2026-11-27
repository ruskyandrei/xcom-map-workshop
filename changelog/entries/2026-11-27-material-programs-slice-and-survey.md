### A material's program sliced out of its compiled shaders, and the survey that gates it

Stages A-S0 and A-S2 of the game-likeness plan's track A: what each material's compiled shaders draw, read as a
small program the editor can run, and a survey over every exported map of how much of what is drawn it covers.

- [shader_slice.py](../../tools/viewer/shader_slice.py) (`slice_material`): from the material's shader map, the
  base pass without a lightmap (colour, glow, cut-out, opacity), a point light's pass (highlight and its power) and
  the lightmap pass (the normal dotted with the lightmap's three directions). From each output's end it goes
  backward through the registers a component at a time to texture reads, uniforms and literals, and follows each
  pixel input through the vertex shader: UV channels and the vertex colour by running it on symbols, the camera
  vector, the camera-relative world position and the world tangent frame by running it on random numbers and
  matching UE3's own values; the vertex shader's fog is taken as none (the editor draws its own). Each output gets
  registers of its own; `fold` works out literals and the engine's neutral terms (lights at zero for the glow, the
  fog of war as on a tile in view), drops a zero glow and code no output needs, and keeps the material's own values
  as uniforms so its instances share one program. What it can't follow is refused per output with a reason.
- [shader_eval.py](../../tools/viewer/shader_eval.py) runs a program on numpy arrays (SM3's operations as Direct3D 9
  defines them).
- [materials.py](../../tools/viewer/materials.py) reads a material's static parameter set (`static_parameters`: base
  ID, switches with their override flags, masks, normal parameters) and its resource's ID and texture list, by
  which it finds its shader map; `static_switches` now reads through it.
- [audit_shaders.py](../../tools/upk/audit_shaders.py) (a research tool): pass a matched 99.8% of the 51,206 mesh
  sections the cache's 37 maps draw exactly to a shader map; pass b translates the colour of 94.9% of them (the
  gate was nine in ten), and counts each output's end and the inputs read. The numbers are in F-167
  ([findings-register.md](../../research/findings-register.md)), the evidence in
  [shader-audit-2026-11-27-a.json](../../research/evidence/shader-audit-2026-11-27-a.json) and
  [-b.json](../../research/evidence/shader-audit-2026-11-27-b.json).
- The program's form is written down in [editor-contracts.md](../../research/editor-contracts.md) section 9; the
  new modules have their row in [ARCHITECTURE.md](../../ARCHITECTURE.md).
- Checked: [test_shader_slice.py](../../tools/viewer/tests/test_shader_slice.py) (made-up shaders: a lerp by the
  vertex colour, a UV scaled in the pixel shader, an input refused, a zero glow dropped; on the install:
  ENV_ForestGround's program mixes Dirt, Grass and Leaves as the game does and never reads Rock, a one-texture prop
  is its texture, a tinted building multiplies its CMod Color, a cut-out is its alpha against the clip value, a
  material with two UV channels reads each from its own, and the colour sliced from the lightmap pass agrees with
  the one from the pass without); the materials tests with their record completed to the format's mask and normal
  lists ([test_materials_and_floors.py](../../tools/viewer/tests/test_materials_and_floors.py)).
- Known gaps: nothing is exported or drawn yet (A-S3, A-S4); decals and effects planes, which mostly don't slice,
  stay as today; a vertex shader's own UV maths (panners in the vertex shader) is not followed.
