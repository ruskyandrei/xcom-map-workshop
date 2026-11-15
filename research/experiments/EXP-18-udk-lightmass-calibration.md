# EXP-18: UDK Lightmass calibration (the encoder reference)

Date: **6 November 2026**. Status: **six clean bakes read; the basis is UE3's, the encoding curve is fitted,
brightness is linear, several lights add per colour into the two textures as their names say, and point and spot
lights follow the same codec with their radial falloff, cone and a light-size term**.
Design: standalone baker, section 4.7. Branch `standalone-baker`.
Numbers: [udk-lightmass-calibration-2026-11-06.json](../evidence/udk-lightmass-calibration-2026-11-06.json).

## Question

What does UDK 2011-09's Lightmass (the same engine build as EW) write into `NormalizedAverageColor`,
`DirectionalMaxComponent` and `SimpleLightmap` for one known light? EXP-17 showed how EW decodes the pair on flat
ground; this asks how the encoder fills it, in particular which way each directional channel points.

## Method

- [`udk_calib_scene.py`](../../tools/bake/udk_calib_scene.py) writes a T3D: one static directional light (white,
  brightness 1, pitched 45° down) over receivers made of UDK's template floor (`MapTemplates.SM_Template_Map_Floor`,
  lightmap UVs in channel 1, scaled 0.25, lightmap resolution 64). Its top face's stored tangent frame is tangent +X,
  binormal −Y, normal +Z, so turning the receiver sets where the light lies in tangent space. A receiver can be given
  that direction (`lightTangent`: azimuth, elevation) and the writer turns it.
- [`udk_bake.ps1`](../../tools/bake/udk_bake.ps1) runs the editor on the hidden desktop: opens the base map, deletes
  its actors, imports the T3D, sends `BUILDLIGHTING`, presses OK in its Lighting Build Options dialog, waits for the
  `Illumination:` log line, closes the Map Check and Lighting Results windows, and saves through File > Save As. A bake
  takes about a minute (Lightmass itself 7 s).
- [`udk_calib_read.py`](../../tools/bake/udk_calib_read.py) takes each receiver's median texel over the middle of
  its top face in all three textures, with the slot scales, and the light's direction in its tangent frame. For point
  and spot lights, whose effect varies over a face, `--texels` writes every texel of the top face with its world
  position (the face's lightmap UV is an affine map of local position, fitted from the template floor's vertices in
  UDK's `MapTemplates.upk` to 2e-4).

Problems met on the way, each fixed in the tools:
1. `BUILDLIGHTING` opens a modal options dialog; the first bake waited on it until it was confirmed by hand.
2. The light's T3D listed its light component as `Components(0)`; the editor matched it to the archetype's first
   template (the sprite) and crashed on save. `Default__DirectionalLight` in UDK's `Engine.u` lists Sprite,
   DirectionalLightComponent0, ArrowComponent0, and the writer now gives all three in that order.
3. The template map's WorldInfo keeps a sky-blue Lightmass environment colour (R 176, G 218, B 255) and ambient
   occlusion, which tinted the first bake (the colour texture came out 0.85, 0.93, 1.0 under a white light). The
   editor refuses `SET` ("Set commands not allowed in the editor"), so
   [`udk_calib_base.py`](../../tools/bake/udk_calib_base.py) copies a bake and blackens the colour and turns the
   occlusion off in place (fixed-size bytes); bakes open that copy, `CalibBase`.
4. UDK packs two small lightmaps into a 128 × 64 texture; the reader first took the height for both axes and read
   both receivers of a pair from the left half.

## Bakes

- **BakeCalib2** ([`udk-calib1.json`](../../tools/bake/examples/udk-calib1.json)): eight flat receivers turned in
  45° steps (the light at elevation 45°, eight azimuths) and four tilted ones.
- **BakeCalib3** ([`udk-calib2.json`](../../tools/bake/examples/udk-calib2.json)): the light at elevations 5, 15,
  30, 45, 60, 75 and 90° and azimuths 90, 150, 210 and 0° in the tangent frame (28 receivers), plus a flat control
  receiver on the ground and the same one raised by 1500 units.
- **BakeCalib4** ([`udk-calib3.json`](../../tools/bake/examples/udk-calib3.json)): the light at brightness 2 and colour
  (R 255, G 128, B 64), on six of BakeCalib3's tangent directions.
- **BakeCalib5** ([`udk-calib4.json`](../../tools/bake/examples/udk-calib4.json)): two lights at once, the white one
  (brightness 1, from 45° above −X) and a blue one (R 64, G 128, B 255, brightness 1.5, from 60° above −Y), on ten
  receivers placed by the white light's tangent direction.
- **BakeCalib6** ([`udk-calib5.json`](../../tools/bake/examples/udk-calib5.json)): four lights, each over its own
  floor (the template floor at scale 0.5 or 0.25 with lightmap resolution 512, 2.5–5 units per texel), all at UDK's
  default Lightmass light source radius: point lights with radius 1024 and falloff exponent 2 at height 256, and
  radius 512, exponent 6, brightness 2, colour (255, 200, 150) at height 128; spot lights with radius 1270, exponent 4,
  cone 20/44° pitched 67.5° down at height 384, and radius 1024, exponent 50, cone 0/44° straight down at height 256,
  brightness 8.
- **BakeCalib7** ([`udk-calib6.json`](../../tools/bake/examples/udk-calib6.json)): nine floors that pull the variables
  apart: the radius-1024, exponent-2 point light at height 256 with light source radius 0, 32 and 100; exponent 0 (no
  falloff) with source radius 0 and 32; exponent 6 with source radius 0; exponent 2 with source radius 32 at heights 64
  and 512; and BakeCalib6's exponent-4 spot light with source radius 32.

## Results

- **The colour texture is white** (1, 1, 1) under the white light on every receiver, as EXP-17 run 1 implies.
- **Only the tangent-space direction matters.** Receivers with the same light direction in tangent space hold the
  same bytes (the four at elevation 90°; the 180° floor and the wall facing away from the light in BakeCalib2), and
  the raised control matches the grounded one.
- **The three channels point along UE3's lightmap basis.** Fitting each channel's direction freely gives azimuths
  90°, 212° and 330° and elevations 39–43°. The basis I recall from UE3's source (from memory: these sources are not
  available here) is b0 = (0, √6/3, 1/√3), b1 = (−1/√2, −1/√6, 1/√3), b2 = (1/√2, −1/√6, 1/√3): azimuths 90, 210
  and 330°, elevation 35.3°. A channel whose basis direction faces away from the light (l·b ≤ 0) stores 0 (at most
  0.014).
- **The stored value follows the clamped cosine with a factor that grows with the light's elevation.** With the
  value decoded with run 3's power of 2.2, value^2.2 × scale = S(e) × max(0, l·b_i):

| Elevation e | 5° | 15° | 30° | 45° | 60° | 75° | 90° |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S (dominant channels) | 0.39 | 0.75–0.77 | 1.18–1.22 | 1.53–1.55 | 1.77–1.79 | 1.92–1.95 | 1.99–2.01 |

  S(e) ≈ 2.00 sin e + 0.24 cos² e fits every channel with l·b > 0.25 to 2.7% (rms; 10% at worst). Channels with
  small l·b sit a little higher (about +0.02 to +0.05), as if a small amount of bounce light reached them; the
  receivers in BakeCalib3 face each other at 2000 units and the base map keeps the default three bounces.
- **The simple lightmap holds nearly the plain cosine,** with the same kind of excess at low elevations: value^2.2 ×
  scale (scale 1) is 0.13–0.15 at 5°, 0.30–0.32 at 15°, 0.54 at 30°, 0.72–0.74 at 45°, 0.87–0.88 at 60°, 0.97 at
  75° and 1.0 at 90°, about sin e + 0.06 cos² e. Half of S(e) is about sin e + 0.12 cos² e, so both grow the same way
  at grazing light.

- **Brightness is linear** (BakeCalib4): every directional value is 2.00 times BakeCalib3's for the same direction
  (1.99–2.02 where l·b is not small).
- **The colour goes into `NormalizedAverageColor`, normalised to its largest channel and gamma-encoded:** the texels
  are (1, 0.49–0.50, 0.25–0.26), which decode with the power 2.2 to (1, 0.21–0.22, 0.046–0.051): the light's colour
  bytes taken to linear ((128/255)^2.2 = 0.22, (64/255)^2.2 = 0.048). `DirectionalMaxComponent` carries the largest
  colour channel's intensity (here red, 1.0), so its values are the white bake's times 2; the slot scale of the colour
  texture stays 1. The simple lightmap carries the full colour: 2.00 × (1, 0.22, 0.047) at elevation 90°.

- **Several lights add per colour, and the two textures are what their names say** (BakeCalib5). With per-colour
  coefficients C_i = Σ over lights of k × c × S(e) × max(0, l·b_i):
  - `NormalizedAverageColor` = Σ_i C_i normalised to its largest channel: predicted and stored agree within about
    0.01 on every receiver (for example (0.273, 0.404, 1) predicted, (0.267, 0.399, 1) stored);
  - `DirectionalMaxComponent`_i = the largest colour channel of C_i: 6% rms over the ten receivers, the largest
    misses on weak channels that sit about 0.06 high (bounce light between receivers that face each other). A mean
    of the channels (40%), luminance (52%) or a projection on the colour (13%) fit worse.

### Point and spot lights (BakeCalib6, BakeCalib7)

Each floor's texels were compared one by one with the directional codec, the light direction l now taken per texel
towards the light's centre, times a falloff and a cone factor
([evidence](../evidence/udk-lightmass-calibration-2026-11-06.json), `BakeCalib6`, `BakeCalib7`, `pointSpotModel`).
- **The three channels keep UE3's basis**: a floor under a point light shows the three 120° lobes, and the per-texel
  residual is the same in every direction around the light, which also confirms the texel positions.
- **Falloff is (1 − (d/R)²)^F**, d the distance to the light's centre, R its radius and F its falloff exponent. With
  a light source radius of 0 the residual against elevation is the same for F = 0, 2 and 6 (0.85–0.86 at 10–20°,
  0.91 at 20–30°, 0.94–0.95 at 30–40°), and with radius 32 for F = 0 and 2, so the exponent leaves no trace beyond the
  formula. Fitting F freely on BakeCalib6 gave 2.06 and 5.92 for 2 and 6.
- **The spot cone multiplies by clamp((cos θ − cos outer) / (cos inner − cos outer), 0, 1)²**, θ measured from the
  spot's axis: the exponent-4 spot with source radius 32 is within 0.98–0.99 of the model at every elevation, and the
  exponent-50 spot's small pool within 1.00 at its centre.
- **The elevation term depends on the light's apparent size.** Lightmass treats point and spot lights as spheres of
  its light source radius ρ (`LightmassSettings.LightSourceRadius`; UDK's default is 100 units, from `Engine.u`'s
  `LightmassPointLightSettings`, and every one of the 254 point and spot lights in `URB_Bar` sets 32). Against S(e):
  - with ρ = 0 the bake is lower at grazing light (0.85 at 10–20°, 0.95 at 30–40°, 1.00 near the vertical), as if
    the cos² term were 0.13 instead of 0.24;
  - with ρ = 32 at height 256 it is within 2%;
  - with ρ = 100, or ρ = 32 at height 64, it is up to 1.16–1.23 times higher at 20–30° and about 0.95 near the
    vertical.

  One formula in the light's angular radius α = asin(ρ / d) (radians) fits all 13 floors:
  S(e, α) = 2 sin e × (1 − 0.55 α²) + (0.114 + 1.84 α) × cos² e. Per texel and channel it is 3–5% rms on the floors
  whose lights look like the bar's (α up to about 15°), 7.5% for ρ = 32 at height 64 (α up to 30°), and 20% for an
  extreme case (α up to 51°). At α = 3° (the directional light's default `LightSourceAngle`) the cos² coefficient is
  0.21, near the 0.24 fitted from the directional bakes. Why Lightmass's sphere lights behave this way is not known;
  physically a sphere wholly above the horizon lights a surface like a point at its centre.
- **The colour texture is the light's normalised linear colour** on every lit texel under the coloured point light:
  (1, 0.58, 0.302) stored against (1, 0.586, 0.311) predicted.

### The codec

Why S has that shape is not known; the formula is an empirical fit. With EXP-17 this gives a working codec for
flat receivers. For lights of linear colour c (the light's bytes with the power 2.2) and brightness k:
- per-colour coefficients C_i = Σ over lights of k × c × A × S(e, α) × max(0, l·b_i), where
  - l is the direction to the light (per texel, to its centre, for point and spot lights) and e its elevation;
  - A is 1 for a directional light, (1 − (d/R)²)^F for a point light, and that times the cone factor for a spot light;
  - S(e, α) = 2 sin e × (1 − 0.55 α²) + (0.114 + 1.84 α) × cos² e, with α = asin(ρ / d) for point and spot lights and
    about 3° for a directional light (where S(e) ≈ 2.00 sin e + 0.24 cos² e was fitted directly);
  - for a light with a size, channels nearly side-on to it (l·b_i near 0) read higher than the clamp gives, as if
    max(0, l·b_i) were averaged over directions within ±1.77 α √(1 − (l·b_i)²); with that softening the rms over
    every lit channel of BakeCalib7 drops from 13.9% to 9.1% (the strongest channels are unchanged);
    [`lightmap_encode.py`](../../tools/bake/lightmap_encode.py) implements the codec;
- `NormalizedAverageColor` = Σ_i C_i / max over colours of Σ_i C_i, stored as that value^(1/2.2);
- `DirectionalMaxComponent`_i = max over colours of C_i; its slot scale is the largest such value of that channel
  over the receiver, and the texel is (value / scale)^(1/2.2);
- the simple lightmap (which EW's cooked maps leave out) would hold k × c × about (sin e + 0.06 cos² e) for a
  directional light.

### Bounce light (BakeCalib8–11, 7 November)

EXP-17 run 6 found the relit bar floor too dark wherever little direct light reaches: at 0.4 of the original where
the original is darker than 0.1. These bakes ask how Lightmass's bounce compares with
[`bounce.py`](../../tools/bake/bounce.py)'s.
- **Scenes:** each pair is a floor lit only by bounce, beside a wall made of the template floor stood on end
  (pitch 90°), 8 or 256 units from the floor's edge.
- **Albedo:** every surface is UDK's `DefaultMaterial`, whose diffuse is the `DefaultDiffuse` texture: mean
  (0.158, 0.159, 0.299) decoded to linear, or (0.43, 0.43, 0.58) as stored.
- **Comparison:** [`udk_bounce_check.py`](../../tools/bake/udk_bounce_check.py) rebuilds each scene and compares our
  shadowed direct light and bounce with UDK texel by texel.
- **Evidence:** [`udk-lightmass-bounce-2026-11-07.json`](../evidence/udk-lightmass-bounce-2026-11-07.json).

Tool changes on the way:
- The first bake (preview quality, the pairs 7,000 units apart) put no bounce light on the floors at all. Its
  Lightmass log reads `0.000 million Indirect Photons`. Preview requests very few photons, and a directional light
  spreads them over the whole scene radius.
  [`udk_bake.ps1`](../../tools/bake/udk_bake.ps1) gained `-Quality`, and the bakes below are Production (the log
  reads `Quality level 3`) with the pairs side by side.
- [`udk_calib_scene.py`](../../tools/bake/udk_calib_scene.py) gained an importance volume. With its brush after its
  component, UDK logged `unresolved reference to 'Model'Model_860''`. With the brush first (BakeCalib11, the
  BakeCalib9 scene again) the warning is gone, but Lightmass still reports `Importance bounds radius 0.0`, so no
  bake here has a working volume. Spot lights do not need one: they put all their photons in their cone.

Results (UDK's light beyond our direct light, divided by our one bounce, near → far from the wall):

| Bake | Lights | Ratio, our cone | Ratio, spot cones doubled for bounce sources |
|---|---|---|---|
| BakeCalib8 ([`udk-calib7.json`](../../tools/bake/examples/udk-calib7.json)) | directional, 5° upward onto the walls | 0.91–1.22 | (no spots) |
| BakeCalib9 ([`udk-calib8.json`](../../tools/bake/examples/udk-calib8.json)) | two spots aimed horizontally at the walls | 3.7–8.1 | 0.92–1.61 |
| BakeCalib10 ([`udk-calib9.json`](../../tools/bake/examples/udk-calib9.json)), floor A | a spot pointing up beside the wall | 3.2–4.0 | 0.20–0.49 |
| BakeCalib10, floor B | a point light (the floor also lit directly) | 1.30–1.55 | (no spots) |

- **Colour settles the albedo.** UDK's floors store colour (0.741, 0.737, 1.0), linear (0.52, 0.51, 1.0):
  - our sRGB-decoded albedo gives (0.53, 0.53, 1.0), a match;
  - albedo averaged as stored would give (0.75, 0.75, 1.0).

  So Lightmass decodes textures as `albedo.py` does.
- **No factor of π.** For directional and point lights our one bounce is UDK's within 10–20% near the walls. The
  excess far from them (up to 1.55) is UDK's later bounces: the calibration base map keeps UDK's default bounce
  count, and the floors' colour there is bluer than one bounce off this albedo gives. EXP-17 run 6's guess that
  Lightmass reflects π times more light is wrong.
- **Direct light matches.** On the walls our direct light is within 2% of UDK's for the directional light and
  within 6% for the spots, so the spots light their walls as the codec says.
- **Spot lights bounce more and wider.** For spot lights, UDK's bounce is 3.5–8 times ours with the real cone.
  - Treating each spot as a point light for its bounce sources overshoots by up to 8 times.
  - Doubling both cone angles for bounce sources only fits the spots aimed at walls (0.9–1.6, like the point
    light), but overshoots the spot pointing up by 2–5 times.
  - A constant factor of about 3.5 on spot bounce fits both spot scenes, but it cannot widen the light, which the
    bar needs (below).
- **Likely cause: photon starvation.** Lightmass's photon counts are densities per unit of surface area: BakeCalib9
  deposited under 1,000 direct photons in all, about 60 on a spot's lit patch. Lightmass's irradiance at a bounce
  source is estimated from the 400 nearest photons (`NumIrradianceCalculationPhotons`), so a small lit patch is
  smeared over a wider area. The bar was baked at the same densities.

**Applied** ([`bounce.py`](../../tools/bake/bounce.py) `SPOT_INDIRECT_CONE_SCALE = 2`): spot lights light bounce
sources through doubled cones; their direct light keeps the real cone. This is an empirical stand-in for Lightmass's
spread of spot bounce, chosen because it fits BakeCalib9 and the bar floor best.
- With it, the original's light bands on the bar floor go from 0.38, 0.46, 0.83, 0.94 to 1.62, 0.80, 0.99, 1.00
  (darkest first), and the floor within 10% from 64% to 69%.
- A factor of 3.5 on placed spots with the real cone leaves the bar at 64%. The bar's lamps point down, so with
  their real cones they light only the floor, which the floor's dark zones cannot see.
- The generated area-light stand-ins (137 spots with a 90° outer cone) matter most there: treated as Lambertian
  emitters ×3 they reach 68%.
- Ambient occlusion (distance 32–128, Lightmass's default fractions 0.5 direct, 1.0 indirect) fixes the darkest
  band but lowers the next, and does not raise the floor's figure, so it stays out.

### Environment light (BakeCalib12, 7 November)

The relit bar's roof and sidewalks came out about 4 times brighter than the original. Both are lit mostly by the
WorldInfo's Lightmass `EnvironmentColor` (64, 69, 97 in URB_Bar), which the relight sent back along every gather ray
that leaves the scene, sRGB-decoded.
- **Base map:** [`udk_calib_base.py`](../../tools/bake/udk_calib_base.py) gained `--environment R,G,B`. CalibEnv is
  CalibBase with the bar's colour, ambient occlusion off.
- **Scene** ([`udk-calib10.json`](../../tools/bake/examples/udk-calib10.json)): an open floor, and a floor beside a
  wall. The one point light is 20,000 units away with a 64-unit radius, so it lights nothing; the editor's scene
  writer needs a light. Production quality.
- **Comparison:** [`udk_bounce_check.py`](../../tools/bake/udk_bounce_check.py) gained `--environment`.
- **Evidence:** [`udk-lightmass-environment-2026-11-07.json`](../evidence/udk-lightmass-environment-2026-11-07.json).

Results:
- **The colour decodes as sRGB.** Every receiver's stored colour is (0.655, 0.710, 1.0). Decoded to linear that is
  (0.39, 0.47, 1.0), the bar's colour sRGB-decoded and normalised.
- **Only the scale differs.** UDK's light is 0.263–0.267 of ours on the open floor (0.280 against 1.051), on the
  floor beside the wall and on the wall, near the wall and far from it alike. So the angular model and the
  occlusion are right. The factor is near 1/π (0.318) but below it.
- **The bar agrees.** On the bar's roof deck the original is 0.44 and our environment light alone was 1.86. At 0.266
  that is 0.49; the bar's ambient occlusion, which the relight leaves out, would explain the rest.

**Applied** ([`bounce.py`](../../tools/bake/bounce.py) `ENVIRONMENT_SCALE = 0.266`, `environment_radiance`): rays
that leave the scene bring back the sRGB-decoded EnvironmentColor times EnvironmentIntensity times 0.266. With it,
BakeCalib12 matches within 4% on every receiver and in every distance band.

## Open

- How EW's shader uses the basis on bumpy surfaces: the game test (C3) would paint a single-light encoding on a
  receiver with a strong normal map and compare it with a real bake of the same light.
- Bounce from spot lights and emissive surfaces: a model of Lightmass's photon density estimate would replace the
  doubled cone. That means blurring the bounce sources' irradiance over the photon search radius set by the photon
  density per unit area, and it would explain BakeCalib9 and BakeCalib10 together. The importance volume still
  isn't registered.
