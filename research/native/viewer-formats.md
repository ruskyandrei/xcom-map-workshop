# First viewer format pass — 5 November 2026

Status: implemented and exercised against the URB_Bar v845/licensee-64 snapshot. This is a first static/fractured
rendering path, not a complete package specification. Dynamic lighting is sufficient; baked
lightmap decoding is outside the current task.

## Observed native records

- `StaticMesh` native payload begins with 28-byte bounds, a body-setup object reference, 24-byte compact KDOP bounds,
  bulk-serialized quantized nodes and collision triangles. Then internal version, source-data flag, optimization
  settings, simplified flag and LOD count. The original asphalt and car report internal version 18.
- LOD data contains raw-triangle bulk metadata, material elements (including per-fragment index ranges), position
  stream, packed tangent/normal plus UV stream, optional colour stream, vertex count and render index buffer.
  The current reader stops after the first LOD's render indices and records that boundary; remaining LODs/native
  fractured metadata are not claimed as decoded.
- Selected asphalt: 121 vertices / 200 triangles. Compact car body: 2,138 vertices / 2,655 triangles. The selected
  `Core_384BackC_FRACTURED` wall: 462 vertices / 372 triangles, six material sections with 14 fragment ranges each.
- Painted fragment visibility is serialized as a counted array; the observed components include 32-bit values.
  Accept exactly matching byte or 32-bit arrays, validate against section range counts and filter initial geometry.
- `Texture2D`: source-art bulk record, counted mip records (bulk metadata plus width/height), then cache GUID.
  Bulk flags include separate file 0x1, zlib 0x2, LZO 0x10 and unused 0x20. Selected high mips live in `Textures.tfc`
  and are LZO-compressed bulk data around DXT payloads. Decode bulk compression before block-compressed pixels.
- Compressed bulk payload: package tag, block size, compressed/expanded totals, counted block sizes and blocks.
  Validate every range and expanded size. The texture output retains the hash of the consumed source payload.
- Material defaults can live on texture-parameter expressions beneath a base material, as well as on parent
  material instances. Apply defaults first, then parent-to-child parameter overrides. Missing `ParameterValue`
  in a parameter struct can represent its zero/default value; do not interpret it as an invalid reference.

## Coordinate correction verified visually and numerically

Domain data stays in game units, Z-up and native rotator units. Geometry and scene matrices use the basis
`view=(gameX, gameZ, gameY)` at the render boundary. UE3 indices in the tested meshes are clockwise. The basis
reflection already changes them into glTF's counterclockwise front faces; reversing them again renders the car
inside-out and culls the ground. The first visual review caught this. Triangle cross-products agree with packed
normals after removing the extra reversal; a synthetic fixture protects that behavior.

Actor and component matrices are composed before applying the basis change. The implementation preserves full
pitch/yaw/roll and nonuniform scale; absolute component-transform flags are currently rejected with diagnostics.
Normals/specular texture decoding, source UV transformations and material-specific sampling remain follow-up work.

## Implementation history

### V6 follow-up: materials, floors and patch previews

- The partially transparent roof was caused by treating every `BLEND_Masked` material's diffuse alpha as
  opacity. `BLDG_Floors.OpacityMask` points to the `UseDestructionAlpha` static switch, whose cooked expression
  branches are stripped. The intact-building profile now keeps the surface opaque; genuine diffuse-alpha cutouts
  remain enabled for the generic masked path. Triangle/fragment-range coverage on the roof was complete.
- PNG upload now uses `flipY=false` with the original game UV values. The previous extra flip vertically mirrored
  atlas textures. The corrected overview shows aligned vehicles, walls and signs. Supported texture-coordinate
  channels/tiling and the `TileXY` building parameter are retained in the material profile. The obsolete sidewalk
  family uses `DiffuseMap`, not `Diffuse`; that binding is now recognized explicitly.
- Source `Floors[].m_aCachedActors` is a counted struct array with `ResidentActor` and optional `CutdownFloor`.
  Floor-volume brush bounds supply cut heights. The viewer preserves multiple memberships, applies the lowest
  cached entry for each building, hides higher floors and clips eligible walls, shadows and picking consistently.
- The visual resolver implements the current copy-position formula, independent per-piece CopyScale, original-piece
  hide exclusions, archetype body/partner spawn, near-cardinal car snapping and visible ladder placement. New building
  metadata follows the patch's floor-volume lists and transfers source cache entries, including `BuildingFloor`.
- Resolver outputs retain operation/source provenance and spec hashes. EXP-07's inherited `patch_bar` content is
  explicitly reported as not composed. Six missing copied door sources per fixture remain reported because their
  visual geometry is skeletal. Rounding ties, runtime component bounds and gameplay parity still need game checks.
- Sixteen synthetic regression tests pass. The Edge test passes for the original scene, ground-floor cutaway,
  both preview scenes, scene switching, texture-upload orientation and intact roof opacity, with no browser errors.
  Previews show 959 visible pieces for the remix and 361 for the current blank-layout fixture. These are renderer
  counts, not a claim of native runtime parity. Map/texture outputs and screenshots remain outside the repository.

The final original-map preview was checked in headless Microsoft Edge at 1600 × 1000. Search, selection/inspector,
camera framing and grid controls passed with no browser/resource errors. The map's source SHA-256 still matches
the export manifest. Local screenshots and decoded outputs are in `<lab>\viewer-cache`, outside Git.

### V8 follow-up: skeletal pieces and inherited patches

- All eleven local skeletal asset definitions parse; the placed scene uses seven door components and fourteen
  corpse/physics components. The LOD reader checks material sections, index containers, CPU-chunk lengths, bone maps,
  GPU vertex ranges, influence indices and weights. Chunk-local indices are remapped to reference-skeleton indices.
- The observed GPU layout has two packed tangent/normal words, four bone bytes, four weight bytes, **float XYZ**,
  then half-precision UVs. EW sets the packed-position hint even with float XYZ: one-UV vertices have stride 32,
  two-UV vertices stride 36. Validated stride and observed positions determine storage, not the hint alone. No
  extra influence bytes or 11:11:10 decoding are needed for these assets. Unknown layouts are rejected.
- GLB output retains actual bones, joint/weight attributes and inverse-bind matrices. The renderer uses the pinned
  three.js skeleton-cloning helper so repeated actors do not share mutable rigs. Browser checks verify CPU reference
  skinning leaves source positions unchanged and repeated meshes have independent bones. Reference poses are not
  runtime ragdoll poses or animation playback. The mesh's import Origin/RotOrigin is retained in the manifest.
- `patch_bar.upk` is version 845/licensee 0. Its three static meshes use the checked static-mesh layout. Its seventeen
  placed render components are all hidden (fifteen cover pieces, two ladders). Eight rebuild volumes and sequence
  records are preserved as metadata. Package-qualified IDs prevent collisions with persistent-level actors/assets.
- EXP-07 composes that saved layer before applying its operations; EXP-08's empty `base` loads no inherited patch.
  Copy sources come from the base map only; hiders can affect both the persistent and inherited levels, as in the
  scripts. EXP-07's explicit `alsoHide` for `XComLevelActor_44` matches both levels, so sixteen inherited helpers
  remain available in the cyan inspection overlay. All seventeen remain recorded, with removal provenance.
- The original scene now has 966 visible pieces; the remix has 983 and the blank fixture 368. Both preview-note
  lists are empty for supported saved-scene operations, while the scenes remain marked experimental/unverified in
  game. Material approximation notes are separate. Twenty-four synthetic tests pass; the browser suite exercises
  all scenes, copied skeletal sources, skin independence, cutaway and hidden-helper controls.

### V9 follow-up: the map's own lights

- URB_Bar's lights: one `DominantDirectionalLight`, one `SkyLight`, 54 `PointLight`, 62 `SpotLight`, one
  `SpotLightToggleable` and 137 Lightmass `GeneratedMeshAreaLight` (spot lights owned by `WorldInfo`). `patch_bar` adds
  three point lights. No `PostProcessVolume` or fog actors; `WorldInfo` holds `XComHeightFog`, post-process settings and
  the Lightmass environment colour (not applied yet).
- **`DominantDirectionalLightComponent` puts its `DominantLightShadowMap` first:** a counted WORD array (URB_Bar:
  12,804 words), then the usual NetIndex and TemplateOwnerClass, then tagged properties. The property reader
  now skips it for that class only.
- Light components' archetypes are engine imports (`Engine.Default__SpotLight.SpotLightComponent0` and so on), so unset
  values come from the UDK 2011-09 `defaultproperties`: `LightComponent` brightness 1, white, enabled;
  `PointLightComponent` radius 1024, falloff exponent 2; `SpotLightComponent` cones 0°/44°; `SkyLightComponent` lower
  colour white, lower brightness 0; `SpotLight` and `DirectionalLight` actors rotation pitch -16384 (down).
- The moon: colour (66, 69, 136), brightness 1.1, pitch -14697. The sky light: (89, 107, 160) at 0.75 above,
  (255, 203, 162) at 0.01 below. The street lamps are spot lights with brightness 1.5, radius 1270 and cones 10°/60°.
- In UDK terms, point and spot lights are static-affecting with `UseDirectLightMap`, so the game bakes them for static
  geometry. Generated area lights are on the CompositeDynamic channel only. The viewer draws them all dynamically
  (see the viewer README).

### V10 follow-up: Temple Ship and general map framing

- The Temple Ship material roots `ALIEN_Base` and `ALIEN_Base_NoLMSPC` connect `OpacityMask` to the
  `OpacityMasked` static switch. Its A input is `Spc_Ems_Ref_Opc` alpha (`OutputIndex=4`, `MaskA=1`), not diffuse
  alpha. The checked instances leave this switch unoverridden/false; an explicit true override selects the packed mask.
- Material-instance native SM3 data contains `FMaterial`, EW's `FXComMaterialData`, then `FStaticParameterSet`.
  The checked reader skips counted compile errors, dependency pairs, texture references/lookups, fixed flags and EW's
  extra header/body before reading the base GUID and static switches. A switch contains FName, two int32 booleans
  (value/override) and an expression GUID. Only overridden values replace inherited defaults. Truncation and invalid
  booleans are rejected; unsupported records produce a material diagnostic.
- Green from `Spc_Ems_Ref_Opc` is interpreted as an emissive mask and multiplied by `EmsColor_EmsValue` RGB/intensity
  for a source-derived approximation. The cooked emissive graph is stripped, so this is not an exact shader recovery.
  Derived grayscale PNGs are linear and retain the original texture/range hash and channel identity. Energy doors
  use one pattern channel tinted with `DoorColor`; animation, wave composition and door state are not simulated.
- `jeremy_dev.M_SimpleGrey` uses the engine's default diffuse constant (128/255 converted to linear),
  `HQ_FundingCouncil.Materials.UnlitBlack` is unlit black, and the construction kit's `Flat` material retains its
  source diffuse vector (0.39, 0.39, 0.39). Sky/ocean shaders remain suppressed and diagnosed.
- `XComWorldDataContainer`'s native start has a chunk count, counted int32 chunk order and XYZ tile dimensions:
  TempleShip is 45 x 203 x 15; URB_Bar is 52 x 39 x 12. Their selected level-volume extents agree with 96 x 96 x 64
  tiles. The display grid combines these dimensions with the volume's corner, without changing seed/build logic.
- The renderer's 128-unit light grid now stores cell offsets/counts plus a packed index texture, so the shader
  evaluates all cell members. Temple Ship's 269-light cell no longer loses contributions. Float-index precision and
  hardware texture dimensions are checked. Framing and directional shadow coverage use visible scene bounds;
  the separate play-area view keeps the tactical volume easy to find. Hidden helpers and suppressed sky domes do not
  enlarge the scene frame. V9 caches still load, but V10 material/grid data requires a fresh export.

The material-instance layout was checked against the pinned upstream
[UMaterialInstance declaration](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/UnrealPackageLibrary/Unreal/ObjectSubtypes/Materials/UMaterialInstance.cs),
[FMaterial](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/UnrealPackageLibrary/Unreal/ObjectSubtypes/Materials/FMaterial.cs) and
[static switch serialization](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/UnrealPackageLibrary/Unreal/ObjectSubtypes/Materials/FStaticSwitchParameter.cs).

### V11 follow-up: identify the interior floor region

- The existing checked `world_links.parse_store` reader decodes the first three native stores to recover floor
  surfaces, without evaluating navigation or modifying the package. Temple Ship has 5,902 present floor records,
  spanning game Z -384 through 573; URB_Bar has 2,495. Positions, normals, tile indices and source floor actors are
  retained, with dimension, finite-number and bounds checks. Unsupported data leaves a diagnostic.
- Temple Ship's authored `Layer` values distinguish 321 render components in `Periphery`, six in `hallway roofs`,
  and helper layers such as `HiddenWalls`/`trigger Blocks`. Some additional scenery lies wholly outside the saved
  floor region. These are reversible inspection roles, not a reconstruction of runtime visibility.
- The interior focus box encloses the saved floor positions with half-cell horizontal margins, 32 units below
  the lowest floor and 192 units above the highest. The resulting view-space box is approximately
  (-2112.6, -416, -9408.7) to (2207.4, 765, 9215.3). The ceiling cuts tall surrounding geometry while retaining
  the saved platforms. Source layers, actors and full scenery remain available in the viewer.
- The original floor grid draws each saved cell at its source floor height, with local slope inferred from its
  normal and a 1.5-unit upward offset for visibility. Cells follow their floor actor's view/cutaway state. This
  replaces the old display plane at the bottom of the tile volume, which was often hidden under the playable floors.
  Patch previews use a reference plane, because their rebuilt floor data has not been observed.
- Saved-link reachability was inspected as a cross-check: only 1,942 floor records are reached from the Group0
  spawn seeds through the currently saved links, ending before the later rooms. Mission gates and door states
  prevent treating that connected subset as the complete mission floor. The viewer therefore retains source floor
  surfaces rather than presenting the link graph as proven current walkability.

## References consulted

Pinned revision `c12648d52651946f35598e659cfa8db10d9a44d3` of XCOM-Uncooker:

- [Static mesh declarations](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/UnrealPackageLibrary/Unreal/ObjectSubtypes/Models/UStaticMesh.cs)
- [Bulk data](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/UnrealPackageLibrary/Unreal/FUntypedBulkData.cs)
- [Bulk serialized arrays](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/UnrealPackageLibrary/Unreal/FByteArrayWithSize.cs)
- [Component colour stream](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/UnrealPackageLibrary/Unreal/ObjectSubtypes/Components/UStaticMeshComponent.cs)
- [Texture records](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/UnrealPackageLibrary/Unreal/ObjectSubtypes/Textures/UTexture2D.cs)
- [Skeletal mesh structures](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/UnrealPackageLibrary/Unreal/ObjectSubtypes/Models/USkeletalMesh.cs)
- [GPU skin vertex fields](https://github.com/chrishayesmu/XCOM-Uncooker/blob/c12648d52651946f35598e659cfa8db10d9a44d3/UnrealPackageLibrary/Unreal/ObjectSubtypes/Models/FGPUSkinVertexBase.cs)
