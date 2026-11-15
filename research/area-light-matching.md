# Area lights and the glowing pieces that emitted them (the L6 matcher)

Date: **9 November 2026**. Status: **matcher built and calibrated offline; not yet used by the export, the page or
the Build; EXP-26 run 5 still to run**. Plan: editor lights plan, sections 4.8 and 9.7.
Tool: [`area_light_bindings.py`](../tools/viewer/area_light_bindings.py), tests in
[`test_area_light_bindings.py`](../tools/viewer/tests/test_area_light_bindings.py).

## Question

A `GeneratedMeshAreaLight`'s `Owner` is the WorldInfo, so nothing in the map says which piece emitted it (plan 2.5).
For area lights to follow a glowing piece that is moved, copied or deleted, the editor needs that association, and a
pose of each light relative to its piece. Which evidence in the package decides it, how reliable is it on the
shipped maps, and where does it stop?

## What the packages say [bytes]

Read from the pristine URB_Bar and TempleShip packages of the configured install (and checked on the other eight
cached maps):

1. **Where a light stands.** Each area light sits a fixed distance out from its emitting patch, along the patch's
   normal, pointing along it. The distance is UDK's `MeshAreaLightGeneratedDynamicLightSurfaceOffset` (30, in
   `BaseLightmass.ini [DevOptions.MeshAreaLights]`) times the level's `StaticLightingLevelScale` (the persistent
   level's WorldInfo `LightmassSettings`): 0.5 on the bar, so 15 units; unset (1) on Temple, so 30. Measured: the
   light moved back by that offset (its **foot**) lies within 12.0 units of its emitter's surface on the bar
   (median 1.6) and 7.9 on Temple (median 0.66), while the light itself is 15.9 / 31.8 units from it at most. On a
   flat patch the foot is on the surface; on a curved or boxed one it can fall inside (the claw machine's box).
2. **What emits.** Lightmass made area lights only for mesh components whose `LightmassSettings` set
   `bUseEmissiveForStaticLighting`. The light's `FalloffExponent` is the component's `EmissiveLightFalloffExponent`
   (default 2) and its `Radius` the component's `EmissiveLightExplicitInfluenceRadius` when set (Temple's three
   components without one have lights of computed radii, 69 to 284 units). Every (radius, falloff) pair of the 137
   bar lights and the 1,190 Temple lights is the setting of some flagged component of the same map.
3. **The settings are delta-serialised.** A placed component saves only the struct members that differ from its
   archetype's: the bar's flood lights (`FloodLight.Archetypes.FloodLightA`) save only `EmissiveBoost 0.7` and
   inherit the flag, falloff 6 and radius 640 from the archetype's component. So each member is read from the
   component, else its archetype chain (`component_settings`).
4. **One mesh per light.** Lightmass makes area lights mesh by mesh, so one light has one emitting component.
5. **Material evidence is partial.** The export's profiles show `EmsValue` scalars (2 to 3 on the bar's emitters, 0
   on the pennants that are flagged but have no lights), `EmsColor` vectors and the alien materials'
   `Spc_Ems_Ref_Opc` emissive parameter on Temple. Recorded, not required.

## Method

`associate(p, objects, lights, meshes, materials, warn)` (plan 9.7) takes the viewer `Package` and the export's own
records. For each base-level area light:

1. **Candidates**: base-level static mesh components with a surface within `gather` (3 offsets) of the foot. Their
   triangles are read from the package by the export's mesh key (fragment masks applied as the export applies
   them) and placed by the actor transform times the component transform, as `export.py` and `compiler.world_box`
   place them. A KD-tree over small triangles' centroids and a bounding-sphere test for large ones find them.
2. **Measured per candidate**: `distance` (light to its nearest surface point), `footDistance` (foot to its nearest
   surface point), `normalDot` (the best agreement of the light's direction with the mean vertex normal of its
   triangles within half an offset beyond its closest approach: the vertex normals are what Lightmass averages),
   `emissive` (`lightmass`, `falloff`, `radius` or `radius-computed`, `material`), the nearest triangle's material,
   and a `score` for ranking and display: 0.25 flag + 0.1 falloff + 0.1 radius + 0.05 material + 0.35 proximity
   (1 - footDistance / gather) + 0.15 max(normalDot, 0).
3. **Supported** candidates set the flag, match the light's falloff and explicit radius (or have none) and come
   within `footMax` (1.5 offsets) of the foot.
4. **Decided**: `verified` when the supported candidates within `margin` (half an offset) of the closest one belong
   to one actor (the closest component is the owner, siblings noted); `ambiguous` when they belong to several actors
   (pieces that move independently); `unmatched` when none is supported, the reason saying what was missing (no
   surface near, no flagged component near, settings that differ, or a matching emitter too far); `unsupported` for
   a light outside the base level, or an owner whose matrix is singular. Every attachment lists up to 8 candidates
   (all competitors always), and `owners` maps every listed candidate's object id to its lights.
5. **The pose**: `ownerMatrix` is the owner component's game-space world matrix (rows, column vectors,
   `export_math` convention); `local` is the light's location by the matrix's full inverse and its rotation relative
   to the matrix's polar rotation (scale and shear removed; a mirrored frame's Z axis flipped). `light_pose(local,
   owner_matrix)` inverts it, so a rigidly moved owner gives `lightAfter = ownerAfter . inverse(ownerBefore) .
   lightBefore`; rotations come back as whole-unit rotators (UE3's `FMatrix::Rotator`, with the yaw taken from the
   Y axis when pointing straight up or down).

### Thresholds and why

| Threshold | Multiple of the offset | Bar (offset 15) | Temple (offset 30) | Why |
| --- | ---: | ---: | ---: | --- |
| `footMax` | 1.5 | 22.5 | 45 | True owners' furthest foot distance: 0.80 offsets on the bar (a claw-machine patch centred inside its box), 0.26 on Temple. |
| `margin` | 0.5 | 7.5 | 15 | No two emitters with matching settings come closer than 2.6 offsets to one foot (Temple: 143 lights have another within 90 units, the nearest at 78). |
| `gather` | 3 | 45 | 90 | Wide enough to list the competitors and the surfaces a user may want to assign. |
| `nearFoot` | 0.5 | 7.5 | 15 | The window for normal agreement beyond a candidate's closest point. |

Normal agreement is measured and scored, never required: the bar's arcade machine has 20 lights pointing straight up
from 4 units above its base, whose nearest faces point down (agreement down to -0.99), and the claw machine's two
slanted-top lights disagree with its nearby faces (-0.45). The arcade's up-pointing lights' colours match its
screen lights (sampled screen colours on faces that may share its texture region); why Lightmass took their normals
reversed is not known.

## Results

Records from the cached export 17 of each map (the matcher reads only fields export 17 already has); Bar and Temple
also from fresh records (`export_records`, textures skipped: Bar 2.0 s, Temple 1.7 s), with identical results.

| Map | Level scale | Area lights | Verified | Ambiguous | Unmatched | Unsupported | Matching time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| URB_Bar | 0.5 | 137 | 137 | 0 | 0 | 0 | 0.5 s |
| TempleShip | 1 | 1,190 | 1,190 | 0 | 0 | 0 | 3.3 to 5.0 s |
| CLrgScout_ForestTrench | 1 | 700 | 700 | 0 | 0 | 0 | 1.8 s |
| CSmallScout_DirtRoad | 1 | 6 | 6 | 0 | 0 | 0 | 0.3 s |
| CsmallScout_Farm | 1 | 129 | 129 | 0 | 0 | 0 | 0.5 s |
| URB_Demolition_EWI | 1 | 240 | 240 | 0 | 0 | 0 | 0.6 s |
| URB_PoliceStation | 0.5 | 0 | | | | | 0.2 s |
| URB_ResearchOutpost | 1 | 11 | 11 | 0 | 0 | 0 | 0.4 s |
| URB_StreetHurricane_Terror | 1 | 0 | | | | | 0.2 s |
| URB_TruckStop_EWI | 0.5 | 81 | 81 | 0 | 0 | 0 | 0.4 s |

All 2,494 area lights of the ten maps verify. No shipped map gives an ambiguous, unmatched or unsupported case; those
come from the perturbation checks and synthetic cases below.

### The bar, inspected

| Pieces | Lights each | Owner settings (radius, falloff) | Notes |
| --- | ---: | --- | --- |
| Claw machine `XComDestructibleActor_316` | 33 | 256, 10 | Its own settings. Two slanted-top lights have the floor edge `XComLevelActor_302` nearer the foot (4.0 and 4.7 against 9.0 and 8.4). |
| Arcade machine `XComDestructibleActor_340` | 30 | 256, 5 | 10 facing out of its front (the screen and the panel below), 20 pointing up by its base (above). The floor is nearer the foot for most of the 20. |
| Street lights `XComLevelActor_250`, `_259` | 12, 12 | 640, 6 and 576, 6 | Their first lights' local poses agree within 0.5 units: (-53.2, -6.7, 326.5) and (-53.5, -6.3, 326.9). |
| Neon signs A, B, C (18 pieces) | 2 | 256, 3 | The wall behind (`XComDecoFracLevelActor_4`, `_14`, `_15`) is often nearer the foot (1.1 against 2.3 for `GeneratedMeshAreaLight_471`). Sign B `_321` stands 56 units from sign C `_319`'s light `_457`. |
| Lamps `Lamp_Single` (9 pieces) | 1 | 640, 3 | |
| Flood lights `FloodLightA` (5 pieces) | 1 | 640, 6 (archetype's) | Local poses equal within 0.17 units and 11 rotator units across the five, though `_447` is turned another way. |

The owners' foot distances: median 1.6, 95th percentile 6.5, maximum 12.0 units; normal agreement median 0.98. For 16
lights another piece's surface is nearer the foot than the owner's.

### Temple, inspected

| Pieces | Lights each | Owner settings (radius, falloff) |
| --- | ---: | --- |
| Air lifts `ARC_Airlift_192` (10, `XComLadder` actors) | 74 | 256, 2 |
| Knuckle worms `ARC_knuckleWorm_3x` (10) | 22 | 256, 2; two (`XComLevelActor_232`, `_245`) set no radius: computed, 2 |
| Power cores `ARC_PowerCore_GroupA` (12) | 15 | 500, 3 |
| Diagonal knuckles `ARC_alienKnuckleDiagnol` (22) | 2 | 160, 2 |
| Box structure `ARC_BoxStructureA01` (1) | 6 | computed radius, 2 |

Identical pieces carry identical counts, which a light given to a neighbour would break. Foot distances: median 0.66,
maximum 7.9; normal agreement at least 0.987. For 3 lights another piece is nearer the foot than the owner.

### Simpler rules, against the verified owners

| Rule | Bar: other piece chosen | Temple: other piece chosen |
| --- | ---: | ---: |
| Nearest actor origin | 17 of 137 | 538 of 1,190 |
| Nearest world box | 78 | 636 |
| Nearest surface to the foot, any piece | 16 | 3 |
| Nearest flagged surface to the foot, settings ignored | 0 | 0 |

So position alone fails; the emissive flag carries the decision, and the falloff and radius settings guard it.

### Examples of each status

- **Verified** (Bar): `GeneratedMeshAreaLight_457`: "one emitter fits: XComDestructibleActor_319 (its surface 1.0
  units from the light's foot, normal agreement 0.98); no other emitter with matching settings within 45 units".
- **Unmatched** (Bar, the claw machine's records removed, as a stale or unexported emitter would be): its 33 lights
  become unmatched, none given to the arcade machine beside it; the reasons say the nearby emitters' settings differ
  (falloff 5 against 10) or no flagged component is near.
- **Ambiguous** (Bar, a second flood light stood 3 units from `XComDestructibleActor_448`, as a copy over its
  original): `GeneratedMeshAreaLight_442` lists both as supported competitors and gets no owner.
- **Unsupported** (synthetic): a light of a streamed layer.

The tests pin these and the synthetic cases: unique match, several proxies on one owner, adjacent competing owners,
a repeated emitter further off, a closer emitter with other settings, a computed radius, three kinds of unmatched,
two components of one actor, and a component offset from its actor pivot.

## Known failure modes and limits

- **A stale bake.** If a glowing piece was moved, or its Lightmass settings changed, after the map was baked, its
  lights no longer fit it: unmatched (or, if a same-settings emitter happens to stand within 1.5 offsets, verified
  to that one). None of the ten maps shows this.
- **Emitters not in the export's objects** (BSP surfaces, unresolved external meshes, components the export skips):
  their lights are unmatched; the same coincidence applies.
- **Touching emitters with the same settings**, or a copy standing over its original: ambiguous by design; the user
  resolves it (`areaLightBindings`).
- **Normal agreement** is reported, not decided on (the arcade's reversed lights). Material evidence is partial and
  never required.
- **The Lightmass rules are read from the bytes** and UDK's ini, not from Lightmass's source; maps baked with other
  surface offsets or grid settings would show as larger foot distances.
- **Poses**: a light follows its owner's rigid moves; a scaled owner carries the light's position with its scale,
  but the editor scales nothing. The owner's own LOD-0 mesh and its fragment mask as placed are used.
- The matcher does not yet run in the export (export 18 integration is the lead's step), so the page and compiler
  do not see it yet.

## What EXP-26 run 5 must check in the game

On the bar, with marked editor shots (plan section 6, run 5), full and unbaked builds:

1. **Move and rotate the claw machine** `XComDestructibleActor_316` in an isolated spot: its 33 proxies arrive at
   the new place facing out of the same faces (a soldier beside it gets its blue glow there, none at the old place),
   including the two slanted-top lights. The arcade machine beside it keeps its 30.
2. **Copy a flood light** `XComDestructibleActor_448` (1 proxy) and **copy the arcade machine** (30, with its 20
   up-pointing lights): each copy carries exactly its set, facing as the original's do.
3. **Delete a neon sign** `XComDestructibleActor_267`: its 2 proxies are gone; the wall behind it is untouched.
4. **Temple**: move an air lift (74 proxies) and check the count and orientation in readback and in the game.
5. **An explicit resolution**: no shipped map has an ambiguous light, so make one (a flood light copied onto its
   original's place, as the ambiguous example) or reassign a verified light with Assign glowing piece and Keep fixed;
   check the saved binding wins over the automatic one after reload.
6. **Destruction**: break an original and a moved flood light and compare with the original map (this work adds no
   rule for switching generated lights off).
