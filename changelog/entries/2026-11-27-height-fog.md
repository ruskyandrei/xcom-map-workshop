### The map's height fog in the Game look

Stage C2 of the game-likeness plan: the Game look draws the map's exponential height fog (export 43's
`atmosphere.world.fog`), as the game's `TExponentialHeightFogPixelShader` works it out: more fog farther away and lower
down, its colour turned toward the inscattering colour when looking toward the map's dominant light and the opposite
colour away from it, never thicker than the map's maximum opacity. No fog in the Neutral look. The view's background
takes the fog's colour.

- The fog's colours are UE3 linear colours, taken as they are (no gamma): the game's light purple haze on
  CSmallScout_DirtRoad shows only so. Density and falloff are a thousandth of what the map stores, as UE3 keeps them.
- One set of shared uniforms: every lit material's shader works the fog out in the shared local-lights patch, and the
  effects' likenesses in theirs (a solid particle fogged as a piece, a see-through one weighed by its opacity, an added
  one only dimmed), so a change of a value recompiles nothing.
- Where: [atmosphere_shader.js](../../tools/viewer/web/atmosphere_shader.js) (new: `fogUniforms`, `fogAt`, `FOG_PARS`,
  `fogChunk`, `fogShared`, `setFog`), [lighting.js](../../tools/viewer/web/lighting.js) (set with the look),
  [effects_preview.js](../../tools/viewer/web/effects_preview.js); [ARCHITECTURE.md](../../ARCHITECTURE.md) names its home.
- Checked: [atmosphere_shader_test.mjs](../../tools/viewer/tests/atmosphere_shader_test.mjs) (the formula's numbers,
  the shared holders, the GLSL's uniforms); the likeness shots of four maps scored against the game's
  ([likeness.py](../../tools/lab/likeness.py)): 17.08 mean colour difference before the fog, 16.80 with it, every map
  closer; the browser check that the far part of the view takes more fog than the near lands with the grade (C3).
- Known gaps: in the game the fog is a full-screen pass over everything drawn; here an unlit material (the sky, a pure
  glow) takes none.
