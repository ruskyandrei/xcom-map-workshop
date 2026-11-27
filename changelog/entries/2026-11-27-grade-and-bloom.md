### The map's grade and bloom in the Game look

Stage C3 of the game-likeness plan: the Game look's frame is drawn as the game draws its own, read from its global
shader cache (the bloom gather, the DOF and bloom blend, the gamma pass with its colour LUT, the LUT blender):

1. the map's pieces, lights and effects' likenesses go to a floating-point target, multisampled, in linear light;
2. the bloom: a quarter-size gather of what is brighter than the map's threshold, blurred by its kernel size, scaled and
   tinted, added where the scene is dark;
3. the game's gamma, a plain 2.2 power after clipping (in place of three.js's tone curve and the sRGB curve: the game's
   darks are lighter);
4. the map's grade, worked out per pixel in gamma space as the game's LUT holds it: shadows, highlights, mid-tones,
   desaturation, colorize. The post-process volume of the highest priority holding the camera's target sets the members
   it overrides over the world's.

The Brightness slider scales the scene's light before the bloom and the grade. **What is not graded**: the gizmo,
handles, markers, the grid and outlines are drawn after the chain, straight to the screen as in the Neutral look, against
the scene's depth (the target's depth, resolved with its colour, written beside the graded frame), so they keep their own
colours and are still hidden behind the map's pieces. The Neutral look's frame is as it was. A look switched to Game
compiles the pieces' shaders for the target first (they differ from the screen's), the last frame staying meanwhile; Take
from the view takes the graded frame.

- Where: [post_grade.js](../../tools/viewer/web/post_grade.js) (new, pure: `postSettings`, `postUniforms`, `gradePixel`,
  `GRADE_GLSL`), [post_chain.js](../../tools/viewer/web/post_chain.js) (new: the passes), [app.js](../../tools/viewer/web/app.js)
  (`drawFrame`, `warmLook`; the draw loop and `grabView` go through it); the test hooks gain `post`
  ([test_api.js](../../tools/viewer/web/test_api.js), recorded in
  [viewer_api_names.json](../../tools/viewer/tests/viewer_api_names.json)); [likeness.py](../../tools/lab/likeness.py) waits
  for the Game look's shaders; [perf_probe.py](../../tools/viewer/perf_probe.py) times the Game look's frame;
  [ARCHITECTURE.md](../../ARCHITECTURE.md) names the homes.
- Checked: [post_grade_test.mjs](../../tools/viewer/tests/post_grade_test.mjs) (the grade's sums against worked numbers,
  the bloom's weights, a volume's members over the world's); [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)'s
  `map-lights` (a helper's square keeps its colour in the Game look and is hidden under the ground as before; the fog
  changes the far part of the view more than the near); the likeness shots of four maps against the game's: 16.80 mean
  colour difference before, 13.66 with the grade and bloom (URB_Bar 17.88 to 7.39, LAbductor_FarmOutskirts 16.25 to
  12.11); [perf_probe.py](../../tools/viewer/perf_probe.py) on export 43, headless at 1600 by 1000: the Neutral look's
  frame as before; the Game look's frame through the chain against the same light drawn plainly 7.9 against 7.8 ms on
  URB_Bar and 6.8 against 4.7 ms on EWI_HQAssault, with 88.8 MB of frame buffers.
- Known gaps: CSmallScout_DirtRoad (12.90 to 14.75) and AlienBase01 lose: some effects' see-through sprites (DirtRoad's
  smoke in the UFO, AlienBase01's domes) were drawn far brighter than the game's before this stage, and the bloom now
  haloes them. No depth of field, motion blur or film grain.
