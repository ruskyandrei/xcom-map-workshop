# EXP-19: the dominant light's shadow maps (baker step L3, gate C4)

Date: **7 November 2026**. Status: **gate C4 passed offline; run 1 passed in the game (installed 13:05): the moved dumpster's old place is moonlit, the copy stands on its shadow, nothing else changed**.
Design: standalone baker, section 13 (L3) and gate C4 in section 5. Branch
`standalone-baker`. Tool: [`shadowmaps.py`](../../tools/bake/shadowmaps.py).

## Question

The bar's moon (`DominantDirectionalLight_1`) is drawn live, not baked into the lightmaps. What shadows it on static
surfaces is a per-component shadow map: 805 of the bar's `ShadowMap2D` objects belong to it (10 more belong to a
toggleable spot light). A moved or deleted piece keeps its moon shadow, and a copy casts none into them.
- Can we rebuild such a map from our own scene, exactly enough to change only what an edit changes (gate C4)?
- Does the game take the rewritten map, and does a copy's shadow baked into it look right next to the copy's own live
  shadow, if it casts one?

## What the shadow maps are

- A `ShadowMap2D` (tagged properties): `Texture` (a `ShadowMapTexture2D`), `CoordinateScale` and `CoordinateBias`
  into its atlas, `LightGuid` (the light's `LightGuid`, not its `LightmapGuid`), and `bIsShadowFactorTexture`. Every
  bar map has `bIsShadowFactorTexture` false: they are signed distance fields.
- The textures are `PF_G8` atlases, one byte per texel: 53 of 54 in `Lighting.tfc` (top 4 mips, LZO), the small mips
  inline and uncompressed. The component's lightmap UV channel maps into them.
- The field: 255 well inside the light, 0 well inside the shadow, linear across the edge. On the asphalt by the car
  (`ShadowMap2D_4284`), the building's straight shadow edge runs 255, 251, 225, 199, ..., 19, 0: about 25.8 per texel
  over 10 texels, the texel being about 5 units.

## Gate C4 (offline)

`shadowmaps.py gate` rebuilds a component's field from our scene and compares it with the map's own:
1. the component rasterised in the shadow map's rectangle at 4 x 4 sub-samples per texel;
2. one ray per sub-sample toward the moon, through the relight's occluder (`relight.Scene`);
3. each sub-sample's world distance to the nearest sub-sample on the other side of the edge, searched within a window
   of the texel grid (by world distance, so UV islands side by side don't see each other), less half a step;
4. 0.5 + d / (2 x transition), clamped, averaged per texel.

| Receiver | Same side of the edge | Mean difference | On the edges |
| --- | --- | --- | --- |
| Asphalt by the car (`XComLevelActor_275`) | 99.9% | 0.0007 | 0.0056 (3,884 texels) |
| Asphalt (`XComLevelActor_263`) | 99.9% | 0.0014 | 0.011 |
| Road marking, 8 dashes packed as islands (`XComLevelActor_468`) | 99.7% | 0.0028 | 0.014 |
| Overpass railing (`StaticMeshActor_59`) | 93.8% | 0.020 | 0.020 |
| Sidewalk, coarse texels (`StaticMeshActor_153`) | 97.1% | 0.019 | 0.10 |
| AC unit, many islands (`XComDestructibleActor_225`) | 96.8% | 0.062 | 0.061 |
| Fog pod (`XComLevelActor_10`) | 93.5% | 0.060 | 0.062 |
| Bush (`XComDestructibleActor_210`, foliage) | 67% | 0.22 | 0.22 |

- **The transition is 25 world units** (edge to 0 or 1). 50, 75 and 100 fit far worse (the asphalt's edges: 0.11,
  0.15, 0.17). UE3's Lightmass default is 50 for the whole width, the same thing.
- **Flat ground matches to within 1–2 of 255 levels.** Props with many UV islands or curved faces are off by about
  0.06. The bush's leaves are cut-out (masked) material, which our shadows treat as solid (plan step L5).
- Two fixes found on the way: per-axis spacing first, then the world-distance search. The road marking had come out
  0.21 off, because its dashes sit side by side in the atlas but far apart in the world.
- So the relight writes a change, as for lightmaps: the map's own field plus (our field after the edit minus ours
  before). Where the edit changes nothing, the map's own field stays to the byte.

## Run 1 (EXP-19 project, built 7 November)

**The project** ([`exp19_moon_project.py`](../../tools/editor/examples/exp19_moon_project.py)). The dumpsters stand
along the back edge of the map, behind the bar, the far side from where the squad lands. The second from the
trash-can end, `XComDestructibleActor_294` (at x −1539), is deleted. Its copy stands about 440 units along the wall,
toward the next dumpster (`XComDestructibleActor_6`), facing the same way.

The moon is nearly overhead (toward it: 0.110, −0.118, 0.987), so a dumpster's shadow lies under it and about
20 units beyond its outline. Before L3, a deleted dumpster left its moon shadow on the asphalt where it stood.

**Build** (the editor's Build, from the command line, to `<lab>\scratch-builds\l3`, about 3 minutes; build
`URB_Bar_EXP19Moon_19e0-20261107-125822`):
- Compile: 1 deleted, 1 added. The patch is 146,430 bytes.
- **Lightmaps:** 233 receivers within 1024 units, and the quick test kept 30. 14 were rewritten, mostly the asphalt
  (`XComLevelActor_292`), the sidewalk strip and the overpass railing behind the dumpsters; 16 were unchanged.
- **Moon shadow maps:** 8 reached by the quick test (with the moon), 5 rewritten, 3 unchanged.
  - The asphalt `XComLevelActor_292`: 3,230 texels, 1,593 lighter where the dumpster stood and 1,637 darker under the
    copy. The preview shows the dumpster's shadow gone from its old place and the same shadow at the copy's.
  - The road markings `XComLevelActor_395` (88 texels) and `_389` (9), the sidewalk `XComLevelActor_59` (5) and
    `_58` (3).

**What to look at** (a new campaign; the first mission is the bar). The dumpsters stand along the railing at the back
edge of the map, behind the bar, the far side from where the squad lands. F9 at each:
1. **Where the deleted dumpster stood** (second from the trash cans): the asphalt and sidewalk there should be
   moonlit like the ground around it, with no dark dumpster-shaped patch.
2. **The copy**, in the gap toward the next dumpster: it should stand on a shadow like the other dumpsters'.
   - Compare its shadow with the next dumpster's. If the copy's is darker, or shows a second outline, the game also
     draws a live moon shadow for copies, and the baked one doubles it. Then copies should be left out of the moon's
     shadow maps.
3. **Nothing else changed**: no dark or bright patches, seams or blocky edges on the asphalt, the road markings, the
   sidewalk or the railing around the two places.

**Result (13:10; six shots, 13:10:29 to 13:10:54): passes.** The user: "done, looks ok. I think i was looking at the
right dumpsters".
- **The right dumpsters.** Shots 13:10:29, 13:10:33 and 13:10:54 show the row of three along the railing: the copy
  and `XComDestructibleActor_6` and `_2`.
  - Their spacing (482 then 425 units) fits the copy at the corner end. That is also the darkest of the three.
  - Shot 13:10:54 shows the asphalt beyond it, up to the railing's corner, where the deleted dumpster stood (about 440
    units on). It is evenly lit, with no dark patch: luminance 41–60 there, the asphalt's texture spread.
- **The copy's shadow** looks like its neighbours'. Neither the user nor the shots show a darker or doubled one. So
  copies stay in the moon's shadow maps.
- **The copy's body is darker** than the two baked dumpsters. That is its live light (F-52, F-56), not the shadow
  maps. Step L4, copies baked themselves, is for it.
