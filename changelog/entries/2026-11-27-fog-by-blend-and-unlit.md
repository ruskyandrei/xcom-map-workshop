### The fog on unlit and see-through materials, and EXP-98 played

EXP-98 (the game-likeness plan's C5a game run) played both Builds of URB_Bar in the lab copy. A thick red fog and a
green grade written on the map's WorldInfo by the Build show in the game, with LWR's patch level streamed in
(F-173). The editor's Game look with the same members gives the game's colours (F-174). The same comparison found two
things the editor's fog did not do, now fixed:

- An unlit material of the map's pieces (a constant colour, a modulating decal's stand-in) took no fog: it now has a
  fog patch of its own (lighting.js `withBasicFog`), put back on a cut-away clone by `withLocalLights`.
- A see-through material took the fog's colour whatever its blend. Now an additive one is only dimmed by the fog
  (`FOG_ADDITIVE`) and a modulating one fades toward white (`FOG_MULTIPLY`), as the game fogs them; a lit or normally
  blended one is as before.
- Where: [atmosphere_shader.js](../../tools/viewer/web/atmosphere_shader.js) (`fogChunk`),
  [lighting.js](../../tools/viewer/web/lighting.js), [scene_pieces.js](../../tools/viewer/web/scene_pieces.js);
  [likeness.py](../../tools/lab/likeness.py)'s `editor --atmosphere` puts a project's members over the map's own before
  shooting, so the editor is shot as a Build of them is shot in the game; the run in
  [EXP-98](../../research/experiments/EXP-98-atmosphere-in-the-game.md).
- Checked: [atmosphere_shader_test.mjs](../../tools/viewer/tests/atmosphere_shader_test.mjs); the editor's shot of
  URB_Bar under the red fog again: the figure that stayed dark is fogged red as in the game, and the frames' colours
  are as before.
