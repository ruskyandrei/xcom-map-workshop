# The cooked spot light, and the factory's recipe (baker step L6, plan step 5)

Date: **9 November 2026**. This is the reading behind [light_factory.py](../tools/bake/light_factory.py), which makes
a spot light in a map that has none to copy (editor lights plan, sections 4.9 and 9.6).
The packages were read from the LWR install with `audit_lighting.Package` and the export tables, read only.
**[bytes]** marks what was read from the packages, **[inferred]** what rests on UE3's sources or reasoning and is
not yet proven in the game.

## 1. What a placed spot light is made of [bytes]

Read from every placed `SpotLight` of URB_Bar (62), URB_PoliceStation (31), TempleShip (54) and
CLrgScout_ForestTrench (20). All 167 agree on everything below except where a variation is named.

**Two exports, nothing else.** The actor, under `TheWorld.PersistentLevel`, and its light component, under the
actor. The sprite, arrow and cone-drawing components that UDK's `SpotLight` class adds are cooked away.

| | Actor | Component |
| --- | --- | --- |
| Class | import `Engine.SpotLight` (`Core.Class`) | import `Engine.SpotLightComponent` (`Core.Class`) |
| Outer | the persistent level | the actor |
| Archetype | none (0): the class default object stands in | import `Engine.Default__SpotLight.SpotLightComponent0` |
| Object flags | `0x0207000100000000` | `0x0007000100000000` |
| Super, export flags, net object counts, package GUID and flags | all zero or empty | all zero or empty |
| Before the tagged properties | 26 bytes: the state frame, then the net index | 8 bytes: the template owner class (0), then the net index |
| After the tagged properties | nothing | nothing |

- The object flags read as UE3's `RF_HasStack` (actor only), `RF_LoadForEdit`, `RF_LoadForServer`,
  `RF_LoadForClient` and `RF_Transactional` **[inferred: UE3's flag names]**.
- **The state frame** is 22 bytes: the node and the state node (both the actor's class import), a 4-byte mask
  (all ones), a 2-byte field, 4 zero bytes, and the code offset (-1, no state code). The 2-byte field varies between
  lights (97, 99 or 110 on most placed lights, other values on a few); it is 0 on most of Bar's and Truck Stop EWI's
  generated area lights (and 0, 1, 256 or 257 on URB_TruckStop's). Read as UE3
  serializes a state frame at this version, it is the latent action, followed by an empty state stack
  **[inferred]**. `props.props_start` reads the same 22 bytes as an 8-byte mask and a 2-byte field; both readings
  agree on the size and on where the net index lies.
- **Net indices.** Both exports of all 167 have one above 0. In Truck Stop EWI every index above 0 in the map's own
  net space (outside the forced-export packages, which count their own) is unique and below the net object count, as
  findings register T-15 found for the bar.
- **The actor saves** `LightComponent` (the component), `Location`, `Rotation` (159 of the 167: the class default
  points down), `bDirtyComponents` (false) and `Tag` (the class name, or a group name of the level
  designer's: 43 of the bar's spots share one). Some save `Layer` or `DrawScale3D`. **No actor saves a `Components`
  array**; the engine is expected to find the component through `LightComponent` and its archetype when it instances
  the class default's components **[inferred: UE3's component instancing]**.
- **The component saves**, in this order: `InnerConeAngle`, `OuterConeAngle`, `Radius`, `FalloffExponent` (each only
  when it differs from the archetype), `CachedParentToWorld`, `LightmassSettings`, `LightGuid`, `LightmapGuid`,
  `Brightness` (when it differs), `LightColor`, `bHasLightEverBeenBuiltIntoLightMap` (true), and on three of the bar's
  spots `ShadowFalloffExponent`. That is the most derived class's properties first, each class's in declaration
  order. A light switched off (four of Temple's point lights) saves `bEnabled` after `LightColor` and has no built
  flag.
- **Never saved** by any of the 167, so left to the engine's archetype: `CastShadows`, `CastStaticShadows`,
  `CastDynamicShadows`, `bCastCompositeShadow`, `bForceDynamicLight`, `UseDirectLightMap`, `LightingChannels`,
  `LightAffectsClassification`, `Function`, `ShadowRadiusMultiplier`, `LightShaftConeAngle`.
- **Encodings.** `LightmassSettings` is a struct of tagged properties (`LightmassPointLightSettings`) holding
  `LightSourceRadius` alone, the same value on all 167 spots (five of Truck Stop EWI's point lights save another
  value and an `IndirectLightingScale`). `LightColor` is 4 bytes, blue, green, red, alpha (alpha 255 on the bar's
  spots). A bool's tag has size 0 and one value byte after it. `CachedParentToWorld` is 64 bytes: the actor's
  rotation-translation matrix (rows the X, Y and Z axes and the origin), each row stored **W first, then X, Y, Z**.
  Built with UE3's sine table (16,384 single floats, the angle's low 16 bits over 4), it matches the stored matrix of
  every unscaled placed point, spot and generated area light in Bar, Police Station and Truck Stop EWI (448) within
  float rounding (largest difference 4e-7), and of the 166 unscaled spots of the four maps within 1e-5 (the tests).
- **Imports.** `Engine` (`Core.Package`, top level), the classes `Engine.SpotLight` and `Engine.SpotLightComponent`
  (`Core.Class`, outer `Engine`), the class default object `Engine.Default__SpotLight` (class `Engine.SpotLight`, outer
  `Engine`) and the archetype `SpotLightComponent0` (class `Engine.SpotLightComponent`, outer the class default
  object). All names have number 0.
- **Generated area lights** (`GeneratedMeshAreaLight`) also use `SpotLightComponent`, but under their own archetype,
  `Engine.Default__GeneratedMeshAreaLight.SpotLightComponent0`, whose defaults are the area light's. The factory
  never borrows it.

## 2. Maps without a spot light [bytes]

- **URB_TruckStop_EWI**, the acceptance map: 17 point lights, 81 generated area lights, no `SpotLight`. It imports
  `Engine` and `Engine.SpotLightComponent` (for the area lights) but not `Engine.SpotLight`, `Engine.Default__SpotLight`
  or its `SpotLightComponent0`; its name table lacks `SpotLight`, `Default__SpotLight` and `InnerConeAngle`.
- **URB_TruckStop_CNH** and **URB_TruckStop_Stream**, Truck Stop's patch levels: a persistent level and no light, light
  import or light property name at all. The factory's tests use the stream level as the case with no local light
  template of any kind.

## 3. Recipe version 1

`light_factory.RECIPES[1]` holds the construction rules as data: the five imports by path and class, the two
exports' classes, archetypes, names, flags and preambles, and the tagged properties in order, with `$` placeholders
for what each light brings. It holds no bytes of a game package. `add_spot` resolves the imports in the destination
(found by class, name and outer, else added), makes both exports with `Grower.new_export`, gives each the map's next
net index, and writes names through the destination's name table.

What version 1 writes, beyond the placed spots' layout above:

| | Version 1 |
| --- | --- |
| Actor | `SpotLight_<unused number>`; `LightComponent`, `Location`, `Rotation` (always saved), `bDirtyComponents` false, `Tag` `SpotLight` |
| State frame | the 2-byte field 0, as most area lights have it |
| Component | `SpotLightComponent_<number unused in the package>` |
| Light values | all seven of plan 9.1 saved explicitly (`bEnabled` after `LightColor`, as the switched-off lights save it), so the light never depends on the archetype's defaults for them. Starting values (plan 3.3): white, brightness 1, radius 1,024, falloff 2, inner cone 0, outer cone 44 degrees, on, pointing down |
| Frozen settings | `LightmassSettings` with `LightSourceRadius` as the placed lights have it; `bHasLightEverBeenBuiltIntoLightMap` true, as every placed spot and every copied spot has it; the cast-shadow, lightmap and lighting-channel settings left to `Engine.Default__SpotLight.SpotLightComponent0`, as every placed spot leaves them |
| GUIDs | the caller's (plan 9.5 derives them from the project); refused when a light of the map, or one the writer has added, already has either |

- **Frozen.** `recipe_digest(1)` is the SHA-256 of the recipe's canonical JSON, and the tests pin it. A change is a new
  version; a build uses the version its project records, and an unknown version raises ValueError.
- **Checked offline** ([test_light_factory.py](../tools/bake/tests/test_light_factory.py)): the recipe against all
  167 placed spots (flags, archetypes, preambles, property kinds and order, Lightmass setting, no native tail, the
  matrix rule); construction on the stream level and on Truck Stop with the template-copying `add_export` disabled;
  the read-back exports, values, GUIDs, imports, net indices and Level slot; no reference outside `Engine` and the map;
  identical bytes from two builds.

## 4. What only the game can show (EXP-26 run 6)

The package reads back as a valid placed spot, but none of this has been loaded by the game yet. Run 6 on Truck Stop
must check:

1. **It loads.** No missing-import or missing-object line for `Engine.SpotLight`, `Engine.Default__SpotLight` or its
   `SpotLightComponent0`, and no duplicate-net-index line naming the new actor or component, at load and after a save
   and reload.
2. **It lights where the editor shows it**, with the cone pointing as drawn. The writer rewrites
   `CachedParentToWorld` for every pose; whether the engine uses it or recomputes it on attach is not known.
3. **The full build**: its pool is baked once, with no live light added on top of the baked one on receivers whose
   lightmaps list its GUID. A copied piece in its reach is lit by it. A soldier walking through the pool is lit by it.
4. **The unbaked build** follows run 2's contract. Version 1 writes `bHasLightEverBeenBuiltIntoLightMap` true, the
   same as a copied spot inherits; what the engine does with that flag on a light no lightmap lists is what run 2
   finds out, and the same answer must hold for the recipe spot.
5. **Edits and repeat builds**: rotation and colour edits, copy, save and reload, and a second build from the saved
   project give the same light, with no exported donor map, no UDK and no other installed map.

## 5. The point light (12 November 2026; prefab plan stage L1.1)

A prefab's lights are recipe lights, so that a prefab needs no map to copy a light from. That needed a recipe for
point lights (`light_factory.POINT_RECIPES`, `add_point`).

**What a placed point light is made of [bytes].** Read from every placed `PointLight` of URB_Bar (54),
URB_PoliceStation (67), TempleShip (87), CLrgScout_ForestTrench (172) and URB_TruckStop_EWI (17): 397 lights.

- **The same two exports as a spot**, with `Engine.PointLight`, `Engine.PointLightComponent` and the archetype
  `Engine.Default__PointLight.PointLightComponent0`. Object flags, the state frame, the component's 8 bytes before
  its properties and the empty tail are the spot's, on all 397.
- **The actor saves** `LightComponent`, `Location`, `bDirtyComponents` and `Tag`; 40 of the 397 also save
  `Rotation`, and some `Layer`. The recipe saves no rotation: a point light has no direction.
- **The component saves** `Radius`, `FalloffExponent`, `CachedParentToWorld`, `LightmassSettings`, `LightGuid`,
  `LightmapGuid`, `Brightness` (when it differs), `LightColor` and `bHasLightEverBeenBuiltIntoLightMap`: the spot's
  list without the two cone angles, in the same order. `CachedParentToWorld` matches the factory's matrix on every
  unscaled one (largest difference 4e-21).
- **Variations.** 18 of Temple Ship's save `LightingChannels` and `LightAffectsClassification` and no built flag
  (lights that are not lightmapped), and four are switched off (`bEnabled` false, no built flag). Five of Truck
  Stop's save a `LightSourceRadius` of 8 with an `IndirectLightingScale`; every other one has 32.

**The recipe, version 1.** The spot's, with those classes and without `Rotation`, `InnerConeAngle` and
`OuterConeAngle`. Its five values (colour, brightness, radius, falloff, enabled) are all saved; starting values
white, brightness 1, radius 1,024, falloff 2, on. Frozen as the spot's is (`recipe_digest(1, 'point')`, pinned by the
tests). The spot recipe's digest is unchanged.

**Checked offline** ([test_light_factory.py](../tools/bake/tests/test_light_factory.py)): the recipe against the
380 placed point lights of the four validated maps; construction on the stream level with no light of any kind,
written and read back (classes, archetype, property order, values, GUIDs, matrix, Level slot, net indices), with a
recipe spot beside it; used GUIDs refused. The writer makes one on the Bar from an edit
([test_native_lights.py](../tools/bake/tests/test_native_lights.py)).

**What only the game can show** (stage L1.3, one look): that it loads and lights where the editor shows it, baked
and unbaked, as section 4 lists for the spot.
