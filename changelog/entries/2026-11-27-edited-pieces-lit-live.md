### Edited pieces lit live in the Game look

Stage B4 of the game-likeness plan, its first half. Before, a piece the project changed kept its lightmap from where
the map had it: a moved piece carried its old light along, and a changed lamp left its old pool. Now such a piece is lit
live, as the game's static pieces are lit once a Build bakes them again.

**Which pieces are lit live:**
- One of the map's own pieces the project moved or deleted.
- One the project relit: its lightmap holds a light the project moved, changed or deleted (the light's `bakedInto`
  lists it).
- Every added piece: a copy, a made piece, a piece of another map.

**How they are lit:** with the local lights scaled by one factor for the map, and no sky light (which lights no static
piece in the game, F-182). The factor brings the live lights to the lightmaps' level. It is the baked light at the
lightmapped pieces' vertices (the lightmap's texel there) over the live lights at the same points and normals, worked
out as the lightmaps load. On URB_Bar it is 0.55 over 8,656 samples: the live lights are brighter, having no shadows.
Undo puts a piece back on its lightmap.

**A light the project moved, changed or added** is drawn live on the lightmapped pieces too, since it is in no
lightmap.

- Where: [baked_rules.js](../../tools/viewer/web/baked_rules.js) (`dxt1Texel`, `liveLightAt`, `liveFactor`),
  [baked_light.js](../../tools/viewer/web/baked_light.js) (the factor's samples, `refresh`, the parts' marks, added
  pieces' geometries, the state's `live`, `factor` and `samples`), [lighting.js](../../tools/viewer/web/lighting.js)
  (mark 4: the local lights scaled, no sky light; an edited static light drawn on lightmapped pieces),
  [lights_wiring.js](../../tools/viewer/web/lights_wiring.js) (`relitPieces`, a record's `edited`),
  [edit_hub.js](../../tools/viewer/web/edit_hub.js) (`baked-light` in the edit and scene runs),
  [app.js](../../tools/viewer/web/app.js) (the refresh registered, and run once the lightmaps load),
  [editor-contracts.md](../../research/editor-contracts.md) section 11.
- Checked:
  - [baked_rules_test.mjs](../../tools/viewer/tests/baked_rules_test.mjs): DXT1 texels in both modes, the live light
    under, beside and out of reach of a point and a spot light, the factor's sums.
  - [edit_hub_test.mjs](../../tools/viewer/tests/edit_hub_test.mjs): the new names registered once.
  - [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)'s `map-lights` on URB_Bar: the factor worked out;
    a lightmapped piece typed 48 units over is lit live and back on its lightmap after Undo; a static light's
    brightness changed lights its bake's pieces live until Undo. `lights` and `typed-pose` pass as before.
- Known gaps:
  - A Build that bakes the project's light is not yet drawn from its own lightmaps: the second half of B4.
  - One factor serves the whole map; a piece in a corner the lights barely reach is darker live than its lightmap,
    which holds the light bounced about.
