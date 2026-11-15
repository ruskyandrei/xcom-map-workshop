# Matching the game's lighting on edited maps

Research date: **6 November 2026**. Target: Enemy Within + Long War Rebalance, especially URB_Bar and TempleShip.
Scope: a new investigation of **A: baking compatible lighting** and **B: dynamically lighting the original and
new geometry together**. This revisits the earlier decision to accept dynamic lighting for authored layouts;
it does not silently change that implementation plan.

**Later follow-up, 6 November:** the Temple sky-fill workaround now passes the recorded F-52/EXP-14 run-12
checks. The standalone baker design investigates route A as optional
longer-term work. The assessment below retains the earlier research state and measurements.

## Assessment

**A is technically credible and offers the best route to preserving the original appearance.** Much of the
necessary baked-data structure is readable already. The hard work is attaching new per-instance lighting to the
correct native components, matching the game's directional encoding, and updating other surfaces affected by the
edit. A general ray tracer alone does not solve those problems.

**B is also credible as a controlled conversion, but enabling dynamic lighting everywhere will not by itself
reproduce the original look.** It changes the light sources reaching surfaces, their shadowing and their indirect
illumination. Thousands of independently updating light environments or shadow-casting lights are also a serious
performance risk. A carefully managed version retaining/rebuilding indirect-light samples is more promising than
a direct-light-only conversion.

**First recommendation:** establish a reliable lighting comparison and test the existing light-environment path,
including the sky light and baked indirect-light volume. Then run a small native-lightmap attachment proof for A
and a small in-place conversion for B. Choose a production direction from those results. Neither a full baker nor
a whole-map dynamic conversion has been implemented or verified by this research.

| Route | Matching original appearance | Runtime cost | Main new work |
| --- | --- | --- | --- |
| A: bake selected receivers, then affected surroundings | Highest potential | Close to original baked path | Native lightmap attachment, encoding, scene extraction, baker and dependency-aware updates |
| B: dynamic direct lights everywhere | Consistent treatment of old/new geometry, but weaker original resemblance | Potentially high | In-place conversion, light/shadow reconstruction, fill lighting and performance management |
| B with cached/precomputed indirect light | Better balance; retains an approximation of bounce | Must be measured; usually less work than many real-time fill lights | Same conversion plus probe validation, sampling and refresh after edits |
| Improve only new pieces' light environments first | May solve much of the immediate mismatch cheaply | Smallest initial change | Correct light selection, synthesis/shadow settings, controlled comparisons |

“Dynamic rendering with precomputed indirect light” still uses baked data. It removes the split between
lightmapped original surfaces and dynamically rendered copies; it is not an entirely bake-free renderer.

## 1. What the investigation established locally

The reproducible [audit](../tools/upk/audit_lighting.py), [metadata](evidence/lighting-audit-2026-11-06.json) and
[EXP-15 record](experiments/EXP-15-lighting-data-audit.md) inspect cooked snapshots without changing them.

| Measurement | URB_Bar | TempleShip |
| --- | ---: | ---: |
| Placed static/fractured mesh component records inspected | 968 | 1,707 |
| LOD-0 texture lightmaps | 930 | 1,651 |
| LOD-0 vertex lightmaps | 0 | 4 |
| LOD-0 no lightmap / no LOD data | 13 / 25 | 11 / 41 |
| Components with LOD-0 shadow-map references | 627 | 272 |
| Lightmap texture exports | 180 | 316 |
| Shadow-map texture exports | 54 | 27 |
| Structurally decoded volume-lighting samples | 1,743 | 8,941 |
| Generated mesh-area light actors | 137 | 1,190 |
| Unique referenced static/fractured meshes checked | 256 | 161 |

These are serialized records, including hidden/auxiliary components, not a count of visible pieces or active lights.
They cover the two base snapshots, not every stream or every EW map. All inspected component prefixes and texture
records parsed without errors. The reader deliberately leaves fractured-component subclass data uninterpreted.

### Baked lighting is per component, with more than one data product

The checked `FLightMap2D` records have three texture/scale slots. **Every inspected LOD-0 2D lightmap uses two actual
textures:** `NormalizedAverageColor...` and `DirectionalMaxComponent...`; the third reference is null. There are
also atlas coordinate scale/bias and contributing-light GUIDs. All 496 lightmap texture exports are DXT1; all 81
shadow-map texture exports are G8. Most name `Lighting.tfc`. Representative high mips were decompressed and pixel
decoded successfully without exporting their image data.

This is not a generic “attach an RGB baked image” format. Slot roles, directional basis, normalization, scale,
gamma, normal-map response and specular behavior must be established against EW's renderer. Texture names and
the public serializer do not fully specify the shader math. [FLightMap declaration](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/UnrealPackageLibrary/Unreal/ObjectSubtypes/Lighting/FLightMap.cs)

The component's native LOD record also holds shadow maps, vertex-shadow references and optional vertex colors.
EW adds two mesh-swap lighting records and two mesh-swap references. A writer must preserve or deliberately update
those, including damaged/swapped representations. [Component declaration](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/UnrealPackageLibrary/Unreal/ObjectSubtypes/Components/UStaticMeshComponent.cs)

### Most source meshes already have a lightmap UV channel

250 of Bar's 256 checked meshes and 156 of Temple's 161 have at least two LOD-0 UV channels and an explicitly
saved lightmap index of 1. Several exceptions exist, including an index outside the observed LOD-0 channels.
Therefore reuse original UVs where valid, but validate each asset and each required LOD; do not globally assume
channel 1 works. Unique, padded lightmap UVs are a separate requirement from the material's repeating UVs.
[Epic's lightmap UV guide](https://docs.unrealengine.com/udk/Three/LightMapUnwrapping.html)

### The maps already contain indirect-light information for moving objects

The decoded volume records contain substantial nonzero indirect/ambient data. The four current Temple project
copy pivots are geometrically covered by 27–34 stored sample spheres; the nearest sample is 77–121 units away.
This does **not** establish the actual engine interpolation weights, the copies' sampling bounds, or whether
Firaxis applies that data to our helpers. It does mean “the copies have no nearby indirect samples” is unsupported.

The volume reader is a restricted, bounds-checked suffix decoder. It requires one uniquely matching volume and
the exact empty visibility/distance-field suffix observed in both maps; it does not deserialize the preceding
physics caches. Samples occupy 33 serialized bytes. Temple has 278 sample centers outside the stored volume
bounds, recorded rather than silently discarded. Encoded radiance bytes are not treated as decoded linear colors.

UE3 documents a light-environment path that samples precomputed indirect lighting for dynamic objects. Thus
“dynamic” does not necessarily mean “direct light only.” Availability of that path in this specific EW configuration
still needs a runtime test. [Epic's Lightmass description](https://docs.unrealengine.com/udk/Three/Lightmass.html#Character%20lighting)

### The sky-light exclusion in the earlier diagnosis was incomplete

Temple's sky component explicitly disables `BSP`, `Static` and `Dynamic`. It **does not explicitly disable
`CompositeDynamic`**, which is true in the inspected game's `Default__LightComponent`. This is the separate
channel used by composite light environments. Resolve inherited struct fields before excluding a light.
[Epic's channel explanation](https://docs.unrealengine.com/udk/Three/LightEnvironments.html#CompositeDynamic%20channel)

The actual `Engine.upk` defaults synthesize a directional light and use one visibility sample. The game's
`XComInteractiveLevelActor.MyNEWLightEnvironment` explicitly enables SH synthesis and disables directional synthesis.
The destructible light environment defaults to disabled/non-updating; our helper enables it. These differences
make light selection, approximation and sampling plausible causes alongside missing per-surface bake detail.

The concurrently updated EXP-14 run-5 notes already report violet copies away from the cyan doorway lights and
prepare sky-light isolation. They also report that a live grey `AmbientGlow` adjustment showed no visible change.
Those observations weaken the earlier cyan-spotlight-only explanation. The source of the tint remains unverified
until a controlled source-isolation result is recorded. This report does not claim the prepared settings comparison
has fixed it.

## 2. Why the two lighting paths can disagree

The game is a mixture of baked and live lighting. Original surfaces can have lightmaps, separate dominant-light
shadow maps, live direct/specular terms, emissive effects and postprocessing. Copies currently use approximated
light environments. Matching material assignments alone cannot make those lighting paths identical.

Light environments combine relevant lights using a compact directional/SH or sky approximation, with visibility
tests based on an object's bounds. Adjacent differently sized wall sections can therefore receive different
approximations, as observed in F-32. Increasing samples or changing synthesis improves an approximation; it does
not create a high-resolution surface bake. [Epic's light-environment design](https://docs.unrealengine.com/udk/Three/LightEnvironments.html)

Dominant-light illumination is also not fully stored in a lightmap: it uses separate precomputed shadowing and
dynamic contributions. Old shadows may survive a lightmap-only change. Conversely, discarding every precomputed
record can remove useful indirect lighting and shadow-transition information.
[Dominant lights](https://docs.unrealengine.com/udk/Three/DominantLights.html)

Before attributing a particular mismatch entirely to lighting, compare effective material instances, tint,
normal/specular inputs, component transforms, shadow flags and bounds. Use normal game postprocessing; the
`barphoto`/photo helpers can change lights and postprocessing and are unsuitable as an unmodified baseline.

## 3. Route A: our own compatible lighting bake

### A1. Prove native attachment before writing a solver

Build a derived-map experiment with one existing mesh at its original pose. First preserve/rebind its existing
lighting under a new component/texture identity, with unchanged illumination. This isolates package integration
from the correctness of a new bake. Then try an authored calibration texture through the same native path.

The current copier calls `SetStaticMesh` and initializes components at runtime. Its JSON settings cannot assign
the native/private `FLightMap` pointer. Mesh replacement and state changes may invalidate copied lighting.
Therefore the strongest initial approach is to serialize the new actor/component **into a derived base map**,
using that map's existing local asset references, and attach the baked LOD records before load. Avoid spawning an
additional duplicate through the copier. Preserve actor identity, gameplay properties and startup ordering.

An alternative is a native runtime attachment helper, but no generic UnrealScript lightmap setter has been
established here. Adding such an interface would require native engine integration. A mesh archetype copy is not
proof that all per-instance lighting is retained. Treat native attachment as the first go/no-go gate.

### A2. Build an exact scene and receiver representation

Extract the final geometry/transforms, tangents/normals, lightmap UVs, materials and all relevant lights/occluders.
Include inherited streams, surrounding geometry, masked surfaces, emissive surfaces and the intended intact state.
Exclude helpers that were never render/shadow geometry. Keep renderer visibility/cutaway separate from bake
occlusion: temporarily hiding a roof for the camera should not arbitrarily change the interior bake.

Read available Lightmass settings per map/light/component. The audit found Bar explicitly stores one bounce,
AO enabled and a 64-unit AO distance; Temple stores two bounces and a zero indirect-illumination AO fraction.
Unspecified values need defaults. The stripped material graphs and missing artist/build settings still prevent
assuming a perfect reproduction from the currently approximated viewer materials.

Use existing valid UV charts first. For exceptions, generate new UVs only with explicit mesh/LOD serialization
support and a new asset identity where needed. [xatlas](https://github.com/jpcy/xatlas) provides UV charting/packing;
it does not bake lighting or write EW data.

### A3. Bake the required lighting quantities

The solver needs direct visibility, indirect diffuse transport/color bleeding, emissive illumination, and the AO
policy used by the target profile. Produce directional information suitable for the existing material shaders,
not a final color image already multiplied by the diffuse texture. Otherwise materials can be multiplied twice
and normal/specular response is wrong.

Possible building blocks are [Embree](https://github.com/RenderKit/embree) for ray intersection and
[lightmapper](https://github.com/ands/lightmapper) for an existing-renderer-based GI prototype. Neither implements
EW's lightmap encoding, asset semantics or package integration. A Cycles/other offline-renderer prototype could
also help test illumination, but requiring a separately installed application would not meet the UDK-removal
plan's packaged-tool objective. No new baker library was installed or selected in this research.

Calibrate on one-light/one-receiver scenes with known normals, colored lights and blockers. Establish coefficient
normalization, quantization, gamma, atlas padding/mips and normal-map behavior against EW before baking a room.
Retain a separate shader/data-format work item: public serialization describes storage, not the complete native
decoder. A constant-color smoke test alone cannot qualify directional lighting.

### A4. Write textures, shadow records and component associations

Write supported `LightMapTexture2D` payloads, flags, mips and references; preserve the component's atlas transform,
light GUID relationships and lightmap/shadow-map distinction. Preserve all required LOD and mesh-swap records.
For the first experiment, test self-contained inline payloads in a small package. For larger outputs, test a
variant-specific texture cache and its name/GUID/offset rules. **Do not rewrite the game's shared `Lighting.tfc`.**

Reuse existing material shader paths where possible. The broader problem of compiling entirely new materials is
not automatically a blocker for supplying new data to a material's already-used lightmap path. It is still a
per-material compatibility test, especially for fractured, masked, translucent and swapped meshes.

Shadow-map encoding needs its own calibration: a grayscale shadow factor and a dominant-light signed-distance
map are not interchangeable. The first inspected shadow objects explicitly set `bIsShadowFactorTexture=False`.
Do not infer an ordinary visibility mask just because the texture format is G8.
[Distance-field shadow description](https://docs.unrealengine.com/udk/Three/DistanceFieldShadows.html)

### A5. Recompute the affected surroundings

Baking only the new object can make it receive plausible light, but does not make the old floor receive its new
shadow or remove a deleted wall's old shadow. Those receiving surfaces also need updating. Moving an occluder can
change indirect lighting farther away than its bounding box.

A full-map bake is a conservative reference, **not a theoretical requirement for every new object**. A selected-
receiver bake can include the surrounding scene in ray evaluation while writing only affected receivers. For
small edits, retain the original lighting elsewhere and expand the affected region until differences converge.
Use copy-on-write atlas textures/regions so one edited receiver cannot alter unrelated users of a shared atlas.
For major layout changes, rebake whole rooms or the map, including relevant volume samples and dominant shadows.

### A feasibility and precedent

The component formats, accessible texture payloads and existing UVs make A a serious engineering option. It is
larger than the existing UDK-free template writer: it needs per-instance native serialization and new texture
resources, and possibly actor insertion into the derived map.

There is relevant UE3 modding precedent: Legendary Explorer documents transferring UDK-built geometry,
lightmaps and shadowmaps into Mass Effect packages. That demonstrates the general approach, not EW compatibility
or a UDK-independent bake. Its UDK 2015 workflow must not be applied to our v845 EW files unchanged.
[Maintainer-hosted experiment](https://github.com/ME3Tweaks/LegendaryExplorer/wiki/Building-New-Level-Geometry-and-Lightmaps-Shadowmaps-in-UDK:-First-Steps-%5BEXPERIMENTAL%5D)

UDK/Lightmass can remain a developer reference backend for calibration. A tool that secretly invokes installed
UDK/Lightmass still depends on it; a fully independent user build needs a bundled solver and EW encoder.

## 4. Route B: dynamically light the original map as well

### B1. Convert rendering in place

Start with a small region and modify the existing actors/components rather than replacing every original with
runtime copies. Preserve names, classes, collision, cover, Kismet references, cutaway membership, destruction and
saves. Static gameplay ownership and dynamic lighting are separate concerns.

For each renderer/recipe, explicitly configure the supported light path: precomputed-light/shadow usage,
lightmap-data handling, accepts-light flags, lighting channels, a real attached/enabled light environment where
used, and required component reattachment/update. `bIgnoreLightMapData`, `bUsePrecomputedShadows` and
`bForceDirectLightMap` have different roles; none should be assumed to do all of this alone.

Some flags are native/const and some values are not serialized when they equal class defaults. Adding them can
require a growing package writer. Prefer local pre-load edits to a variant over global console-class mutations.
Native registrations exist for `SetLightEnvironment`, `SetLightingChannels`, `ResetEnvironment` and
`RebuildWorldLightEnvironments`; their availability is not proof they alone produce a complete conversion.
`KActorFromStatic.DisablePrecomputedLighting` is a specialized physics-actor hook, not an established universal
static-component conversion API.

Cover static meshes, fractured meshes, skeletal/interactive props, floors, decals and streamed geometry in the
support matrix. A single successful barrier conversion does not qualify all these paths.

### B2. Rebuild the light and shadow policy

Preserve the map's authored light colors, transforms, falloff, cones, masks and inclusion/exclusion behavior as
the starting point. Separate static-scene lights, character/composite-only fill lights and generated area-light
approximations. In particular, do not make a character-only lavender sky fill illuminate all architecture by
accident, or count emissive illumination twice.

Replacing the scene's baked shadows requires a live shadow strategy. Use a bounded number of important
shadow-casting lights; evaluate dominant-directional cascades/preshadows where EW supports them and chosen local
lights indoors. Other lights can be unshadowed or represented through the environment/probes. Whole-scene point
shadows require six views versus one for a spot light, so treating all existing lights as shadow casters is
expensive. [UE3 shadowing modes](https://docs.unrealengine.com/udk/Three/ShadowingReference.html)

Do not start by enabling all 1,190 Temple generated mesh-area lights for every primitive. Their original role,
radius, channel, culling and overlap must be preserved or deliberately replaced. The viewer's ability to draw
many approximate lights is not a benchmark for the game's renderer.

`bForceNoPrecomputedLighting` is documented in our installed UDK source as controlling creation of precomputed
lighting. This is not evidence of a runtime switch that removes all shipped data and generates a replacement.
UE4/UE5 tutorials for the similarly named option are not a validated EW conversion procedure.

### B3. Recover the missing low-frequency illumination

Three practical levels:

1. **Retain and sample the original volume lighting.** Best first test for minimal layout edits, assuming EW's
   light environments use it as expected. It may preserve much of the original tone without a new surface bake.
2. **Rebake/update indirect probes for changed layouts.** A smaller output than detailed surface lightmaps, but
   still requires scene transport, native volume encoding and correct sample lookup. Old probes become wrong
   after substantial wall/floor changes and can leak light across newly closed rooms.
3. **Fit room/local fill lighting.** Useful approximate fallback, fitted against fixed-camera baseline images.
   Separate regions by occlusion and lighting context. A single global ambient color cannot reproduce colored
   bounce, contact darkening and different rooms simultaneously.

SH synthesis can retain more directional variation than a two-color sky approximation. More visibility samples
and suitable bounds can improve partial occlusion and seams. They are quality/cost controls, not a substitute for
the missing high-frequency bake. Both original converted surfaces and copies must use the same deliberate policy.

### B4. Manage update and rendering cost

Our helpers currently use dynamically updating environments. Scaling that unchanged to the whole map is a poor
default. Evaluate fixed-position environments using `bDynamic=False` plus non-composited transient lights, with
explicit refresh after destruction, movement or lighting changes. Check that at least the initialization tick
occurs; missing component ticking was already a cause of black copies.

Epic distinguishes this cheaper cached mode from continually updated environments. Its old “about 50” guidance
is a historical optimization recommendation, not a measured limit for this game on current hardware.
[UE3 optimization guide](https://docs.unrealengine.com/udk/Three/LevelOptimization.html#CPU%20Overhead)

Share environments only where objects really share illumination/visibility. A map-wide environment would erase
local differences; one per tiny piece can create seams and excess work. Profile region-based grouping, updates
on events, visible-object prioritization and bounded shadow casters. Measure game-thread and GPU times, median
and slow-frame times, load spikes and memory at fixed camera/settings, including explosions and cutaway changes.

### B feasibility

B can remove the obvious old-versus-new rendering split and stale surface bakes. Reconstructing the original
scene's appearance remains an artistic and technical relighting task. Requiring both close original resemblance
and fully live GI for every edit would likely move beyond ordinary package/script work into renderer changes.
The strongest practical B candidate is consistent dynamic rendering with selected real-time shadows and a
validated indirect-light representation.

## 5. Experiments that resolve the decision

The following are proposed tests, not completed runtime results. Use one derived map/test package at a time and
record source/build hashes; do not change shared game caches or the real installation. Current EXP-14 run 5 can
supply the settings-comparison infrastructure, so avoid duplicating it.

| Test | Work | What a pass establishes |
| --- | --- | --- |
| L0: matched baseline | Original and copy alternately displayed at the exact same pose; identical material/tint/normal inputs, camera, settings and occluders | Separates a lighting-path difference from placement/material/postprocess differences |
| L1: isolate sources | Reset between sky, cyan spots, dominant light and generated-light tests; refresh components/environments; capture originals and copies | Identifies which sources cause the discrepancy without cumulative tuning |
| L2: environment/probes | Compare default and door-style SH settings, visibility samples/bounds and shadow policy; verify actual probe use through a narrowly instrumented/controlled variant | Determines whether matching the existing environment path is enough for small edits |
| A0: native data round trip | Original per-instance lightmap/shadow records under new identities at unchanged pose; preserve geometry/UVs | Proves attachment/packaging independently of a baker |
| A1: encode known illumination | Controlled colored/directional calibration, normal-mapped receiver and blocker; then a small new receiver bake | Establishes coefficient/texture/shadow encoding and native material compatibility |
| A2: changed surroundings | Add/move/remove an occluder; rebake its receivers and a growing surrounding region | New shadows appear, old ones disappear, atlas neighbors stay intact |
| B0: in-place original conversion | A few originals and copies share one explicit dynamic policy; no gameplay actor replacement | Establishes consistent rendering without breaking identity/cover/cutaway |
| B1: a complete room | Selected live shadows plus original or updated probes; reproduce the unchanged room first | Measures original resemblance, seams, light leaks and CPU/GPU cost |
| B2: whole base plus streams | Convert every supported visible family, including load/reload and destruction states | Establishes that B scales beyond a demonstration piece |

For L0, avoid overlapping visible geometry and avoid accidentally changing the occluder set when toggling the
representations. For L1, a global sky-light toggle is diagnostic only: it can also change soldier/alien lighting.
A production fix should isolate intended scenery illumination while preserving character readability.

Evaluate two separate objectives: **new/original consistency** and **resemblance to the original scene**. Making
everything equally flat can satisfy the first while failing the second. Capture representative surface masks,
color/luminance differences, shadow boundaries and seams from the same camera. Compare an unchanged scene for B's
baseline; an edited scene cannot be expected to retain physically obsolete shadows from the old layout.

Game acceptance also covers movement, cover/LOS, roof cutaway, doors, destruction/swapped meshes, save/reload,
streaming and consecutive missions. Test shader/material families, not just actors. Archive matched images and
timings before choosing a perceptual-error or frame-time budget; no image-equivalence/performance claim is made
by this static audit.

## 6. Recommended sequencing and relation to UDK removal

1. Finish the current source-isolation/SH experiment and add L0/L2 controls. This may yield a small, useful fix
   for the immediate Temple mismatch, but should not be advertised as general rebaking.
2. Implement A0 and B0 as small, independent proofs. They expose the native-data and original-component barriers
   before committing to a large renderer or baker.
3. For fidelity-focused editing, prefer A if native attachment and encoding pass. Grow from selected static
   receivers to rooms, then handle destruction and wider indirect effects deliberately.
4. For large remixes, evaluate B1 with indirect samples and managed updates. Use B only if both the original-look
   and performance targets pass; keep it an explicit lighting mode rather than silently degrading all maps.
5. A longer-term combined workflow is credible: responsive dynamic preview during editing, compatible baking
   for final output. The preview is approximate until measured against the baked result.

The UDK-removal plan currently excludes new lightmaps. A would be a distinct
extension requiring native component/texture writing and a bundled baker. B can reuse its compiled-template
approach for controllers but still needs pre-load component edits and, potentially, richer native-data writing.
Both can ultimately meet the no-installed-UDK user goal; neither is provided merely by finishing the current
four-helper settings writer.

This task added research, a read-only auditor and evidence only. No lighting was rebaked, no original was converted,
no game/UDK process was launched, and no viewer server was restarted by this investigation.
