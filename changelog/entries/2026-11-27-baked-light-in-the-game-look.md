### The map's baked light in the Game look

Stage B2 of the game-likeness plan. The Game look lights each of the map's lightmapped pieces by its lightmap (export
44), the way the game's shader does. The colour atlas is multiplied by the three direction values, each weighted by
the squared cosine of the material's normal with UE3's basis (F-181; the material's own normal where its program has
one).

What else lights such a piece:
- **Static and area lights**: left out of it. They are in its lightmap, or light only what moves.
- **The sky light**: left out too. It lights no static piece on any of the game's maps (F-182).
- **The sun and the other lights**: live, as before.

A piece without a lightmap is lit as before. Nothing is fetched until the Game look is first on, and the Neutral
look's frame is as it was.

**How it is drawn without a material for each piece** (F-183):
- The map's atlases are packed on the page into one colour atlas and one direction atlas: their DXT1 blocks are copied
  where the packing puts them, so the texels are the game's.
- Every lit material shares the two packed atlases.
- Each lightmapped part gets a geometry of its own: the shared one's attributes, plus its lightmap UVs moved into the
  packed atlas and its two scales.
- A shader compiled for the Game look's target has the baked light; one for the screen has not. A geometry without a
  lightmap gets zero attributes once the light is on.

`?baked=off` leaves it off (for the checks); `?baked=sum` sums the three direction values, as the baker does, for
F-181's check. B0's spike (`baked_light_spike.js`) is gone.

- Where: [baked_rules.js](../../tools/viewer/web/baked_rules.js) (new, pure: `packAtlases`, `copyBlocks`,
  `packedUvs`, `scaleValues`, `bakedLightAt`), [baked_light.js](../../tools/viewer/web/baked_light.js) (new:
  `createBakedLight`), [lighting.js](../../tools/viewer/web/lighting.js) (`bakedShared`, `bakedGeometry`, `USE_BAKED`
  for a target's shaders), [app.js](../../tools/viewer/web/app.js) (made as a map opens, loaded by `warmLook`; the test
  hooks' `post.baked` and `post.setBaked`), [scene_pieces.js](../../tools/viewer/web/scene_pieces.js) (`PROGRAM_NORMAL`).
  [perf_probe.py](../../tools/viewer/perf_probe.py) times the Game look with the baked light beside the lights live.
  [ARCHITECTURE.md](../../ARCHITECTURE.md) names the homes.
- Checked:
  - [baked_rules_test.mjs](../../tools/viewer/tests/baked_rules_test.mjs): URB_Bar's atlases packed without overlap
    on whole blocks; the blocks copied in place; the UVs moved; the lightmap's sum.
  - [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)'s `map-lights` on URB_Bar of export 44: 1,218
    parts lit from a 4096 by 3904 atlas, loaded in 0.4 s once the Game look is on; a street lamp's pool on the ground,
    drawn by the lightmap alone, brighter than the ground around it.
  - perf_probe.py from B0's camera, three runs of 40 frames:

    | Look | Frame (ms) |
    | --- | --- |
    | Game, lights live | 4.9, 4.9, 4.9 |
    | Game, baked light | 4.9, 4.9, 4.8 |

    That is within the bar agreed after B0 (5% of the lights live). The map opens in 4.3 s, as before.
  - The likeness shots of four maps against the game's: 13.36 mean colour difference before, 10.32 with the baked
    light (LAbductor_FarmOutskirts 12.77 to 7.81, URB_Bar 6.47 to 4.49, CSmallScout_DirtRoad 13.56 to 11.04,
    AlienBase01 20.64 to 17.95).
- Known gaps:
  - A moved, copied or relit piece still takes its lightmap from where it was (stage B4).
  - The sun's shadow on a lightmapped piece is the live shadow map, not its baked one (stage B3).
  - The packed atlases keep their top level alone, so far-off lightmaps alias a little.
