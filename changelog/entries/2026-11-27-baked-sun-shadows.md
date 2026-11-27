### The sun's baked shadows in the Game look

Stage B3 of the game-likeness plan. In the Game look, a lightmapped piece takes the sun's or moon's shadow from its
own shadow map, as the game does. The shadow map is an 8-bit distance field (0.5 on the shadow's edge), read with the
game's power curve. Before, every piece took the live shadow map.

- **A piece wholly in the sun's shadow** takes none of the sun. Such a piece has no shadow map of the sun: the light is
  on its `IrrelevantLights`, and the game draws none of it there (F-184). Export 45 marks it `sunIrrelevant`; on the
  four maps of track H that is every lightmapped piece without a shadow map. Before, the live shadow map lit such
  pieces wherever the cutaway hid their roof, such as the Bar's kitchen floor.
- **A piece without either**, or with a plain shadow factor in place of a distance field (none on the four maps),
  keeps the live shadow map, as does every piece without a lightmap.
- **How it is drawn:** the shadow maps are packed into one single-channel atlas, as the lightmaps are. Each part's
  shadow map UVs sit beside its lightmap UVs in the same attribute, and a mark beside its scales says which of the
  three it is. Three attributes and three varyings in all.
- `setSunShadows(false)` on the baked light gives every piece the live shadow map, for when the project's sun takes
  another direction (wired with the sun's lane, T-S2).

F-180, F-182 and F-183 are marked fixed in the register (by B1 and B2).

- Where: [baked_rules.js](../../tools/viewer/web/baked_rules.js) (`copyRows`, `SHADOW_SHAPE`, `shadowAt`),
  [baked_light.js](../../tools/viewer/web/baked_light.js) (the shadow atlas, the parts' marks, `setSunShadows`, the
  state's `shadows`, `sunless` and `shadowAtlas`), [lighting.js](../../tools/viewer/web/lighting.js) (three's light
  loop with the first directional light's shadow taken from the shadow map), [baked_light.py](../../tools/viewer/baked_light.py)
  (`sun_irrelevant`), [export.py](../../tools/viewer/export.py) (export 45), [editor-contracts.md](../../research/editor-contracts.md)
  section 11.
- Checked:
  - [baked_rules_test.mjs](../../tools/viewer/tests/baked_rules_test.mjs): rows copied into the packed atlas; the
    field's light at 0, 0.5 and 1.
  - [test_baked_light.py](../../tools/viewer/tests/test_baked_light.py): on URB_Bar every lightmapped piece without
    a shadow map has the sun irrelevant.
  - [browser_smoke.py](../../tools/viewer/tests/browser_smoke.py)'s `map-lights`: the shadow maps packed and taken,
    the sunless pieces marked. On URB_Bar, 799 of its 1,218 lit parts take a shadow map, from a 4096 by 3136 atlas,
    and 419 take none of the sun.
  - Track H's likeness shots against the game's: mean colour difference 10.32 with B2, 9.46 now
    (LAbductor_FarmOutskirts 7.81 to 5.79, CSmallScout_DirtRoad 11.04 to 10.69, AlienBase01 17.95 to 16.21, URB_Bar
    4.49 to 5.16).
- Known gaps:
  - URB_Bar scores worse because its wood floor's blue sheen in the game comes from the material's 2D reflection,
    which the editor does not draw. B2's live moon had stood in for it by chance (F-184).
  - The field's sharpness and exponent (2 and 2) are the editor's own; the engine sets them at run time.
  - A moved, copied or relit piece still takes its lightmap and shadow map from where it was (stage B4).
