# EXP-49: Generated area lights on imported prefab props

12 November 2026. Prefab plan L2.

The fixture used URB_Bar's floodlight (`XComDestructibleActor_448`) twice, one copy quarter-turned, its pink neon
sign (`XComDestructibleActor_267`), and an asphalt plane (`XComLevelActor_242`) as a receiver. The prefab went
through Test in game on `CB2_MP_Blank`.

- The donor's verified associations named one proxy for the floodlight and two for the sign. With no full donor
  export, the same matcher recovered all 137 Bar associations and reused the cached result on a second request.
- The builder derived four light poses. Moving the first floodlight by one tile moved its own light by one tile
  and kept the other floodlight's pose. The compiler also checked a quarter turn after rebasing between grids.
- Quick and baked package readback found three unlisted templates and four live `GeneratedMeshAreaLight` actors,
  owned by the destination's `WorldInfo`. Each placement kept its emitter-relative pose and had fresh GUIDs.
  The baker saw zero area lights before the edit and four after it. The asphalt received baked illumination.
  No imported area GUID was registered as a placed light on a receiver.
- The baked test ran in XCOM. The visible floodlight lit a patch of asphalt. The squad started, the game closed
  normally, and the editor restored the lab install. The quick build was checked by package readback.
