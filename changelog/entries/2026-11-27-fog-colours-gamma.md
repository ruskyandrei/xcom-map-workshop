### The fog's colours made linear as the engine makes them

The height fog's two colours (C2) are taken again through the engine's 2.2 power, as UE3 makes an `FColor` linear
before the fog's shader reads it: the map saves them as `Color` structs (a byte a channel; CSmallScout_DirtRoad's
opposite colour is 54, 60, 92). C2 had taken them as they are, which scored better only while the grade was missing.

- Where: [atmosphere_shader.js](../../tools/viewer/web/atmosphere_shader.js) (`fogUniforms`).
- Checked: [atmosphere_shader_test.mjs](../../tools/viewer/tests/atmosphere_shader_test.mjs); the likeness shots of four
  maps with the grade and bloom on: 13.66 mean colour difference with the colours as they are, 13.36 through the 2.2
  power (URB_Bar 7.39 to 6.47, CSmallScout_DirtRoad 14.75 to 13.56, LAbductor_FarmOutskirts 12.11 to 12.77,
  AlienBase01 20.40 to 20.64).
