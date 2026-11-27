### The maps' baked light surveyed, and the bar of drawing it measured on a spike

Stage B0 of the game-likeness plan: what the game stores of each map's baked light and how its shader draws it, read
offline from the install, and a throwaway spike of B2's shader on URB_Bar, timed and shot against the game's own
shots before B2 is built. Findings F-180 to F-183; evidence
[baked-light-survey-2026-11-27.json](../../research/evidence/baked-light-survey-2026-11-27.json).

- [audit_baked_light.py](../../tools/upk/audit_baked_light.py) (a research tool, not shipped): `survey` gives, per map
  of the install's records, the static mesh components with lightmaps and sun shadow maps, the atlases and shadow-map
  textures with their formats, saved `SRGB` and bytes, the lights with which lightmaps and shadow maps name them and
  the channels they light, what the pieces without a lightmap have in its place, and once the light-map policies and
  base-pass constants of one material's compiled shaders; `scale` works one piece's lightmap both ways (the three
  direction values summed, as `relight.flat_light` does, and weighted as the game's shader does); `near` lists the
  lightmapped pieces round a point; `spike-export` writes a map's lightmap records and atlases (DDS, as stored) into
  an export of a scratch cache for the spike. Every component is read through `lighting_records.component_record` and
  `shadowmaps.shadow_maps`.
- What it found (96 maps): 95% of the static mesh components have a directional lightmap; every atlas is DXT1 and
  read through sRGB; the game weights the three direction values by their squared cosines, a third each for a flat
  normal, so `flat_light` is three times the game's light (settled against the game's shots); the sky light lights
  only the `Gameplay_1` channel on every map, so no static piece, though the editor's Game look lights every piece
  with it; a piece with no lightmap takes the no-lightmap base pass and a live pass a light (F-180 to F-182).
- The spike, off unless the page's address says `?baked=on` (`?baked=sum` sums the three values):
  `tools/viewer/web/baked_light_spike.js` (replaced by B2's baked_light.js) reads the records into each lightmapped part's own
  clone of its shared material; the formula is in the lights' patch of
  [lighting.js](../../tools/viewer/web/lighting.js) (`USE_BAKED`), which on such a piece puts the lightmap in place of
  the sky light and leaves out the static and area lights (a flag in the light data's fourth texel);
  [scene_pieces.js](../../tools/viewer/web/scene_pieces.js) marks a program with a normal (`PROGRAM_NORMAL`), which the
  formula reads; [app.js](../../tools/viewer/web/app.js) makes it and switches it with the look. B2 replaces it.
- [perf_probe.py](../../tools/viewer/perf_probe.py): `--camera` times every frame from one camera of its own,
  `--frames` sets how many frames a figure is the mean of, and where the page has the spike the Game look is timed
  with the map's lights live and with the baked light in the same run.
- Measured (this PC, URB_Bar from track H's ub-1 camera, 1600 by 1000, 40 frames a figure, three runs):

  | Look | Frame (ms) | Without the chain (ms) |
  | --- | --- | --- |
  | Neutral | 3.8 (5.4 with the sun's shadow pass) | |
  | Game, the map's lights live | 4.5 | 3.8 |
  | Game, the baked light (spike) | 5.7 | 4.9 |

  Of the 1.2 ms, the shader's lightmap is about 0.15 ms and the rest a material for each of the 1,109 lightmapped parts
  (F-183). Programs 129, 177 with the spike; opening the map 4.3 s, 6.1 s with it. Against the game's three URB_Bar
  shots (likeness.py's score): the lights live dE 7.38 (L 5.59), the baked light 4.39 (1.8), the values summed 10.95
  (8.41). Pictures (not in the repository): `private/shots/b0`.
- Checked: the `repo`, `node`, `viewer` and `upk` suites; the spike's frames and the console on a test server.
- Gaps: the spike draws no vertex lightmaps, no sun shadow maps (the sun's live shadow stays) and nothing of the
  stream layers; edited, moved and added pieces keep their baked light; the area lights are left off lightmapped
  pieces without proof that the game does the same; the pieces without a lightmap still take the sky light, which the
  game does not give them. It ships in a release only if one is made before B2 replaces it, and stays off there.
