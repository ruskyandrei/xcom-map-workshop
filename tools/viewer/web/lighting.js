// The map's own lights, all dynamic: its directional and sky lights through three.js lights,
// and its point/spot lights through a 2D light grid the material shader reads. Local
// lights use UE3's falloff and cone terms and cast no shadows (in game their shadows are baked).
import * as THREE from 'three';
import { CELL, buildLightGrid, packLightGrid, sceneLightClip } from './light_grid.js';
import { effectiveCone } from './light_rules.js';
import { FOG_PARS, fogChunk, fogShared, fogUniforms, fogUniformsNone, setFog } from './atmosphere_shader.js';

const uniforms = {
  localLightData: { value: null },
  localLightGrid: { value: null },
  localLightIndices: { value: null },
  localIndexWidth: { value: 1 },
  localGridInfo: { value: new THREE.Vector4(0, 0, CELL, 0) },   // origin x, origin z, cell, enabled
  localGridSize: { value: new THREE.Vector2(0, 0) },
};
// the map's height fog (atmosphere_shader.js, C2): the one set of uniforms every lit material and the effects'
// likenesses share, so a change of the fog's values recompiles nothing; no fog in the Neutral look
Object.assign(uniforms, fogShared);

// The map's baked light (game-likeness plan, B2: baked_light.js, baked_rules.js), in the Game look's frame only: a
// shader compiled for its target (the frame's floating-point one) has USE_BAKED. Every lit material shares the packed
// atlases and the switches (`baked`: on once the atlases are loaded; the weight; the sky light's part on a lightmapped
// piece), and each piece brings its lightmap UVs in the packed atlas (bakedUv: u, v, and 1 where it has a lightmap)
// and its two scales as attributes of its own geometry: its materials stay shared (F-183). Three attributes and three
// varyings, no more (a headless browser's limit): bakedUv the lightmap's UVs and the sun shadow map's, bakedScale0
// the colour's scale and the piece's mark (1: a lightmap, 2: and a shadow map of the sun, 3: and no sun; 4: a piece
// the project moved, added or relit, B4, lit live with the local lights scaled to the lightmaps' level and no sky
// light, as a static piece; 5 to 7: 1 to 3 for a piece as the project's last baked Build built it, lit by its
// lightmaps, which hold the lights the Build baked: the project's own edits of them that it built among them, B4),
// bakedScale1 the directions' scale.
export const bakedShared = { bakedColour: { value: null }, bakedDirections: { value: null }, bakedOn: { value: 0 },
                             bakedWeight: { value: 1 }, bakedSky: { value: 0 },
                             // the sun's baked shadows (B3): the packed shadow maps, whether they stand for the sun (not
                             // when the project's sun has another direction), and the field's sharpness and exponent
                             bakedShadowMap: { value: null }, bakedSunOn: { value: 1 },
                             bakedShadowShape: { value: new THREE.Vector2(2, 2) },
                             // the factor that brings the live lights to the lightmaps' level on an edited piece (B4)
                             bakedLiveFactor: { value: 1 } };
Object.assign(uniforms, bakedShared);
const VERTEX_PARS = `#include <common>
varying vec3 vLocalWorld;
#ifdef USE_BAKED
attribute vec4 bakedUv;
attribute vec4 bakedScale0;
attribute vec3 bakedScale1;
varying vec4 vBakedUv;
varying vec4 vBakedScale0;
varying vec3 vBakedScale1;
#endif`;
const VERTEX_MAIN = `#include <worldpos_vertex>
vLocalWorld = ( modelMatrix * vec4( transformed, 1.0 ) ).xyz;
#ifdef USE_BAKED
vBakedUv = bakedUv; vBakedScale0 = bakedScale0; vBakedScale1 = bakedScale1;
#endif`;
const FRAGMENT_PARS = `#include <common>
varying vec3 vLocalWorld;
uniform highp sampler2D localLightData;
uniform highp sampler2D localLightGrid;
uniform highp sampler2D localLightIndices;
uniform int localIndexWidth;
uniform vec4 localGridInfo;
uniform vec2 localGridSize;
#ifdef USE_BAKED
uniform sampler2D bakedColour;
uniform sampler2D bakedDirections;
uniform float bakedOn;
uniform float bakedWeight;
uniform float bakedSky;
uniform sampler2D bakedShadowMap;
uniform float bakedSunOn;
uniform vec2 bakedShadowShape;
uniform float bakedLiveFactor;
varying vec4 vBakedUv;
varying vec4 vBakedScale0;
varying vec3 vBakedScale1;
// the sun's shadow on a piece from its shadow map (B3): pow(saturate((field - 0.5) x sharpness + 0.5), exponent); none
// of the sun on a piece wholly in its shadow (F-184)
#define BAKED_MARK ( vBakedScale0.a > 4.5 ? vBakedScale0.a - 4.0 : vBakedScale0.a )
float bakedSunShadow() {
	if ( BAKED_MARK > 2.5 ) return 0.0;
	float field = texture2D( bakedShadowMap, vBakedUv.zw ).r;
	return pow( clamp( ( field - 0.5 ) * bakedShadowShape.x + 0.5, 0.0, 1.0 ), bakedShadowShape.y );
}
#define BAKED_PIECE ( bakedOn > 0.5 && vBakedScale0.a > 0.5 && ( vBakedScale0.a < 3.5 || vBakedScale0.a > 4.5 ) )
#define BAKED_BUILD ( vBakedScale0.a > 4.5 )
#define BAKED_SUN ( BAKED_PIECE && bakedSunOn > 0.5 && BAKED_MARK > 1.5 )
#define BAKED_LIVE ( bakedOn > 0.5 && vBakedScale0.a > 3.5 && vBakedScale0.a < 4.5 )
#endif
${FOG_PARS}`;
// The game's directional lightmap (implementation plan, section 0): with N the material's tangent-space normal and
// b_i = saturate(N . basis_i)^2 for UE3's three basis vectors, light = colour atlas x scale0 x dot(direction atlas x
// scale1, b); both atlases read through sRGB. The sky light is not baked, and lights static pieces on no map
// (bakedSky 0: its channels, F-182): the lightmap stands in its place on a lightmapped piece.
const BAKED_LIGHT = `#if defined( USE_BAKED ) && defined( RE_IndirectDiffuse )
if ( BAKED_PIECE ) {
	vec3 bakedN = vec3( 0.0, 0.0, 1.0 );
#ifdef PROGRAM_NORMAL
	if ( dot( progOut_normal.xyz, progOut_normal.xyz ) > 1e-8 ) bakedN = normalize( progOut_normal.xyz );
#endif
	vec3 bakedBasis = vec3( saturate( dot( bakedN.yz, vec2( 0.816496611, 0.577350259 ) ) ),
		saturate( dot( bakedN, vec3( -0.707106769, -0.408248305, 0.577350259 ) ) ),
		saturate( dot( bakedN, vec3( 0.707106769, -0.408248305, 0.577350259 ) ) ) );
	vec3 bakedLight = texture2D( bakedColour, vBakedUv.xy ).rgb * vBakedScale0.rgb
		* dot( texture2D( bakedDirections, vBakedUv.xy ).rgb * vBakedScale1, bakedBasis * bakedBasis ) * bakedWeight;
	irradiance = irradiance * bakedSky + PI * bakedLight;      // (three's Lambert divides by pi: the game's diffuse x light)
}
if ( BAKED_LIVE ) irradiance *= bakedSky;                     // (an edited static piece: no sky light either, F-182)
#endif`;
// UE3: radial attenuation pow(saturate(1 - (d/R)^2), FalloffExponent); spot cone
// square(saturate((dot(L, -dir) - cosOuter) / (cosInner - cosOuter))).
// A material drawn by its program (USE_PROGRAM, scene_pieces.js) takes no highlight from these: in the game the map's
// placed lights are baked into lightmaps, whose pass has no highlight; only the sun (dominant) and live lights do.
// three's light loops with the sun's shadow (the first directional light's) taken from a piece's shadow map where it has
// one and the baked light is on (B3); the live shadow map elsewhere
const SUN_SHADOW_LINE = 'directLight.color *= ( directLight.visible && receiveShadow ) ? getShadow( directionalShadowMap[ i ], '
  + 'directionalLightShadow.shadowMapSize, directionalLightShadow.shadowIntensity, directionalLightShadow.shadowBias, '
  + 'directionalLightShadow.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;';
const SUN_INFO_LINE = 'getDirectionalLightInfo( directionalLight, directLight );';
if (!THREE.ShaderChunk.lights_fragment_begin.includes(SUN_SHADOW_LINE) || !THREE.ShaderChunk.lights_fragment_begin.includes(SUN_INFO_LINE)) {
  throw new Error('three.js\'s light chunk changed: the sun\'s baked shadow (lighting.js) needs looking at');
}
const LIGHTS_BEGIN = THREE.ShaderChunk.lights_fragment_begin
  .replace(SUN_INFO_LINE, `${SUN_INFO_LINE}
		#if defined( USE_BAKED ) && ( UNROLLED_LOOP_INDEX == 0 )
		if ( BAKED_SUN ) directLight.color *= bakedSunShadow();
		#endif`)
  .replace(SUN_SHADOW_LINE, `#if defined( USE_BAKED ) && ( UNROLLED_LOOP_INDEX == 0 )
		if ( !BAKED_SUN )
		#endif
		${SUN_SHADOW_LINE}`);
const FRAGMENT_MAIN = `${LIGHTS_BEGIN}
#if defined( RE_Direct )
#ifdef USE_PROGRAM
vec3 programSpecular = material.specularColor;
material.specularColor = vec3( 0.0 );
#endif
if ( localGridInfo.w > 0.5 ) {
	ivec2 localCell = ivec2( floor( ( vLocalWorld.xz - localGridInfo.xy ) / localGridInfo.z ) );
	if ( all( greaterThanEqual( localCell, ivec2( 0 ) ) ) && all( lessThan( localCell, ivec2( localGridSize ) ) ) ) {
		vec2 range = texelFetch( localLightGrid, localCell, 0 ).xy;
		for ( int n = 0; n < int( range.y ); n ++ ) {
				int offset = int( range.x ) + n;
				int texel = offset / 4;
				vec4 ids = texelFetch( localLightIndices, ivec2( texel % localIndexWidth, texel / localIndexWidth ), 0 );
				int li = int( ids[ offset % 4 ] );
#ifdef USE_BAKED
				// (a light in the piece's lightmaps: the map's, or for a piece as built the Build's)
				if ( BAKED_PIECE && dot( texelFetch( localLightData, ivec2( 3, li ), 0 ).yz, BAKED_BUILD ? vec2( 0.0, 1.0 ) : vec2( 1.0, 0.0 ) ) > 0.5 ) continue;
#endif
				vec4 lp = texelFetch( localLightData, ivec2( 0, li ), 0 );
				vec3 toLight = lp.xyz - vLocalWorld;
				float d2 = dot( toLight, toLight ) / ( lp.w * lp.w );
				if ( d2 >= 1.0 ) continue;
				vec4 lc = texelFetch( localLightData, ivec2( 1, li ), 0 );
				vec4 ld = texelFetch( localLightData, ivec2( 2, li ), 0 );
				vec3 lw = normalize( toLight );
				float att = pow( 1.0 - d2, lc.w );
				if ( ld.w > - 1.5 ) {
					float cone = saturate( ( dot( - lw, ld.xyz ) - ld.w ) * texelFetch( localLightData, ivec2( 3, li ), 0 ).x );
					att *= cone * cone;
				}
#ifdef USE_BAKED
				if ( BAKED_LIVE ) att *= bakedLiveFactor;
#endif
				directLight.direction = normalize( ( viewMatrix * vec4( lw, 0.0 ) ).xyz );
				directLight.color = lc.rgb * att;
				directLight.visible = true;
				RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
		}
	}
}
#ifdef USE_PROGRAM
material.specularColor = programSpecular;
#endif
#endif
${BAKED_LIGHT}`;

// One shared function, so every lit material shares one program cache key. A shader compiled for a render target (the
// Game look's frame: its own parameters, no tone curve and linear colour, make it a program of its own) has the baked
// light; one for the screen (the Neutral look, the helpers) has not.
function localLightShader(shader, renderer) {
  Object.assign(shader.uniforms, uniforms);
  const baked = renderer?.getRenderTarget?.() ? '#define USE_BAKED\n' : '';
  shader.vertexShader = shader.vertexShader.replace('#include <common>', baked + VERTEX_PARS)
    .replace('#include <worldpos_vertex>', VERTEX_MAIN);
  shader.fragmentShader = shader.fragmentShader.replace('#include <common>', baked + FRAGMENT_PARS)
    .replace('#include <lights_fragment_begin>', FRAGMENT_MAIN)
    // the fog in linear light, before three's tone curve and its colour space
    .replace('#include <opaque_fragment>', `#include <opaque_fragment>\n${fogChunk('vLocalWorld')}`);
}

// A geometry drawn by a baked-light shader needs its attributes: a piece without a lightmap gets zeros (no lightmap)
// once the baked light is on, so no attribute is left to a value another shader set (three's attribute defaults are
// not part of a vertex array's state). Called before each draw of a lit material (its onBeforeRender).
const zeroBaked = new WeakSet();
export function bakedGeometry(renderer, scene, camera, geometry) {
  if (!bakedShared.bakedOn.value || geometry.attributes.bakedUv || zeroBaked.has(geometry)) return;
  const count = geometry.attributes.position?.count ?? 0;
  if (!count) return;
  zeroBaked.add(geometry);
  const zeros = new Float32Array(count * 4);
  geometry.setAttribute('bakedUv', new THREE.BufferAttribute(zeros, 4));
  geometry.setAttribute('bakedScale0', new THREE.BufferAttribute(zeros, 4));
  geometry.setAttribute('bakedScale1', new THREE.BufferAttribute(zeros.subarray(0, count * 3), 3));
}

/** Draw with the map's local lights off: small previews drawn away from where the piece stands. */
export function withoutLocalLights(draw) {
  const on = uniforms.localGridInfo.value.w;
  uniforms.localGridInfo.value.w = 0;
  try { draw(); } finally { uniforms.localGridInfo.value.w = on; }
}

/** Let an unlit material (a MeshBasicMaterial of the map's pieces) take the map's fog: `kind` 'FOG_MULTIPLY' for one
 *  that multiplies what is behind it, 'FOG_ADDITIVE' for one that adds, or none (atmosphere_shader.js's fogChunk). */
export function withBasicFog(material, kind = null) {
  if (kind) material.defines = { ...(material.defines ?? {}), [kind]: '' };
  material.userData.basicFog = kind ?? 'plain';        // (withLocalLights puts the patch back on a clone)
  material.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, fogShared);
    shader.vertexShader = shader.vertexShader.replace('#include <common>', VERTEX_PARS)
      .replace('#include <worldpos_vertex>', VERTEX_MAIN);
    // (a multiplying one fades its factor toward white after three weighs it by its opacity, so a fogged one darkens
    // nothing; the others take the fog in linear light, as the lit materials do)
    const after = kind === 'FOG_MULTIPLY' ? '#include <premultiplied_alpha_fragment>' : '#include <opaque_fragment>';
    shader.fragmentShader = shader.fragmentShader.replace('#include <common>', `#include <common>\nvarying vec3 vLocalWorld;\n${FOG_PARS}`)
      .replace(after, `${after}\n${fogChunk('vLocalWorld')}`);
  };
  return material;
}

/** Let a lit material receive the map's local lights (clones need this again). */
export function withLocalLights(material) {
  // (an unlit material of the map's pieces has the fog's patch of its own, which a clone loses: put back)
  if (material.isMeshBasicMaterial && material.userData.basicFog) {
    return withBasicFog(material, material.userData.basicFog === 'plain' ? null : material.userData.basicFog);
  }
  // (a material drawn by its program has the local lights in its own patch, which chains this one: scene_pieces.js)
  if (material.isMeshPhongMaterial && !material.userData.program) material.onBeforeCompile = localLightShader;
  if (material.isMeshPhongMaterial) material.onBeforeRender = bakedGeometry;
  return material;
}

// UE3 turns FColor into linear colour with a 2.2 power; its lights carry no 1/pi,
// three.js's Lambert term does, hence the pi.
export const linear = (rgb, scale = 1) => rgb.map(v => Math.pow(v, 2.2) * scale);
// a game vector (x, y, z up) in the view's axes (y up)
export const toView = v => new THREE.Vector3(v[0], v[2], v[1]);

/** Map lighting for one scene. Call before the first material compiles. setLights(records) puts the lights as edited
 *  in place of the scene's (editor lights plan 4.6: moved, changed, added and deleted lights, and the area lights their
 *  glowing pieces take along); apply() again after it. `atmosphere` gives the map's atmosphere as the view draws it
 *  (the project's fog and colour over the map's own: game-likeness plan, C5b), else the scene's; fog() sets the fog
 *  again from it alone (a slider of the Map settings window). `timeOfDay` gives the project's time of day as the view
 *  draws it (sun_rules.js sunView: the dominant light's direction, colour and brightness, the sky light's), or null for
 *  the map's own (T-S1); sunMoved() puts the sun or moon and the sky light where it says again, without the lights'
 *  grid (a drag of the time bar, each frame). */
export function createMapLighting({ world, sun, hemisphere, scene, maxTextureSize = 4096, atmosphere = null, timeOfDay = null }) {
  const neutral = { sky: hemisphere.color.clone(), ground: hemisphere.groundColor.clone(), hemi: hemisphere.intensity,
                    sun: sun.color.clone(), intensity: sun.intensity, castShadow: sun.castShadow };
  let all = [], enabled = [], local = [], grid = null, bounds = null, deepest = 0;
  const extraSuns = [];
  let packed = null, lastMode = 'neutral', fogLight = null, fogShown = false, shown = null, dimmed = false;
  // A light as the time of day sets it: the dominant light's direction, colour and brightness, the first sky light's
  // colours and brightnesses (the others as the map has them)
  function timed(lights) {
    const day = timeOfDay?.();
    if (!day) return lights;
    const sky = lights.find(l => l.kind === 'sky');
    return lights.map(l => (l.role === 'dominant' && l.kind === 'directional' && day.light ? { ...l, ...day.light }
      : l === sky && day.sky ? { ...l, ...day.sky } : l));
  }

  function setLights(records) {
    all = records || [];
    enabled = all.filter(l => l.enabled);
    local = enabled.filter(l => (l.kind === 'point' || l.kind === 'spot') && l.radius > 0);
    // Only where the map has pieces (its grid as it now is included): a light can reach millions of units out.
    grid = buildLightGrid(local, { clip: sceneLightClip(scene), maxSide: maxTextureSize });
    ({ bounds, deepest } = grid);
    if (local.length > maxTextureSize) throw Error('Light data exceeds GPU texture dimensions');
    // Per light: position/radius, colour/falloff, direction/cos outer (-2: a point light), cone scale.
    const lightData = new Float32Array(Math.max(1, local.length) * 16);
    local.forEach((l, i) => {
      const p = toView(l.location), d = toView(l.direction).normalize();
      const colour = linear(l.color, l.brightness * Math.PI);
      let cosOuter = -2, coneScale = 0;
      if (l.kind === 'spot') {
        // UE3 clamps the inner cone to [0, 89] degrees and the outer cone just above it and below 90 (light_rules.js).
        const [inner, outer] = effectiveCone(l.innerConeAngle, l.outerConeAngle);
        cosOuter = Math.cos(outer); coneScale = 1 / (Math.cos(inner) - cosOuter);
      }
      // (the fourth texel's second value: a light the game leaves out of a lightmapped piece: a static one is in its
      // lightmap, unless the project moved or changed it (B4: `edited`, lights_wiring.js), an area one lights only what
      // moves; its third: the same of a piece as the project's last baked Build built it, whose lightmaps hold the static
      // lights as the Build had them: all but those changed since (B4: `sinceBuild`))
      const inLightmaps = (l.role === 'static' && !l.edited) || l.role === 'area' ? 1 : 0;
      const inBuild = (l.role === 'static' && !l.sinceBuild) || l.role === 'area' ? 1 : 0;
      lightData.set([p.x, p.y, p.z, l.radius, ...colour, l.falloffExponent, d.x, d.y, d.z, cosOuter, coneScale, inLightmaps, inBuild, 0], i * 16);
    });
    uniforms.localLightData.value?.dispose();
    uniforms.localLightData.value = dataTexture(lightData, 4, Math.max(1, local.length));
    if (bounds) {
      uniforms.localGridInfo.value.set(bounds.x0, bounds.z0, grid.cell, 0);
      uniforms.localGridSize.value.set(bounds.nx, bounds.nz);
    } else uniforms.localGridInfo.value.w = 0;
  }
  setLights(scene.lights || []);

  function fillGrid(include) {
    if (!bounds) return;
    packed = packLightGrid(grid, include, maxTextureSize);
    uniforms.localLightGrid.value?.dispose();
    uniforms.localLightIndices.value?.dispose();
    uniforms.localLightGrid.value = dataTexture(packed.cells, bounds.nx, bounds.nz);
    uniforms.localLightIndices.value = dataTexture(packed.indices, packed.width, packed.height);
    uniforms.localIndexWidth.value = packed.width;
  }

  /** mode: 'map', 'map-no-area' or 'neutral'. target/radius frame the shadow camera. */
  function apply(mode, target, radius) {
    lastMode = mode; dimmed = false; shown = null;
    for (const light of extraSuns) world.remove(light, light.target);
    extraSuns.length = 0;
    const lights = mode === 'neutral' ? [] : enabled.filter(l => mode === 'map' || l.role !== 'area');
    if (mode === 'neutral' || !all.length) {
      fogShown = false;
      setFog(fogUniformsNone());
      if (neutral.background !== undefined) world.background = neutral.background;
      hemisphere.color.copy(neutral.sky); hemisphere.groundColor.copy(neutral.ground); hemisphere.intensity = neutral.hemi;
      sun.color.copy(neutral.sun); sun.intensity = neutral.intensity; sun.castShadow = neutral.castShadow;
      sun.position.copy(target).add(new THREE.Vector3(1, 1.6, -1).multiplyScalar(radius));
      uniforms.localGridInfo.value.w = 0;
      return { local: 0 };
    }
    shown = lights;
    // The first directional light drives the shadow-mapped sun; any others light without shadows.
    for (const l of lights.filter(l => l.kind === 'directional').slice(1)) {
      const light = new THREE.DirectionalLight();
      world.add(light, light.target); extraSuns.push(light);
    }
    place(target, radius);
    const chosen = new Set(lights);
    fillGrid(l => chosen.has(l));
    uniforms.localGridInfo.value.w = bounds && lights.some(l => l.kind === 'point' || l.kind === 'spot') ? 1 : 0;
    return { local: lights.filter(l => l.kind === 'point' || l.kind === 'spot').length };
  }
  // The sky light and the directional lights apply() chose, as the time of day sets them, on the hemisphere, the
  // shadow-mapped sun and the others' lights; the fog turned by the dominant light (C2), the background in its far colour
  function place(target, radius) {
    const lights = timed(shown), shadowDistance = radius * 3;
    const sky = [0, 0, 0], ground = [0, 0, 0];
    for (const l of lights.filter(l => l.kind === 'sky')) {
      linear(l.color, l.brightness).forEach((v, k) => { sky[k] += v; });
      linear(l.lowerColor, l.lowerBrightness).forEach((v, k) => { ground[k] += v; });
    }
    hemisphere.color.setRGB(...sky); hemisphere.groundColor.setRGB(...ground); hemisphere.intensity = Math.PI;
    const directionals = lights.filter(l => l.kind === 'directional');
    const put = (light, l) => {
      light.color.setRGB(...linear(l.color)); light.intensity = l.brightness * Math.PI;
      light.position.copy(target).addScaledVector(toView(l.direction).normalize(), -shadowDistance);
      light.target.position.copy(target);
    };
    if (directionals.length) { put(sun, directionals[0]); sun.castShadow = directionals[0].castShadows; }
    else { sun.intensity = 0; sun.castShadow = false; }
    directionals.slice(1).forEach((l, k) => { if (extraSuns[k]) put(extraSuns[k], l); });
    fogLight = directionals[0]?.direction ?? null;
    fogShown = true;
    fog();
  }
  /** The time of day changed (the bar dragged, an undo, a project opened): the sun or moon and the sky light set again
   *  as it says, where the Game look draws the map's lights (not in the Neutral look, nor while Solo dims the map). */
  function sunMoved(target, radius) {
    if (lastMode === 'neutral' || dimmed || !shown) return;
    place(target, radius);
  }

  /** Solo (editor lights plan 4.6): the map dimmed to a faint neutral, its own lights off; apply() puts it back. */
  function dim(target, radius) {
    dimmed = true;
    hemisphere.color.copy(neutral.sky); hemisphere.groundColor.copy(neutral.ground); hemisphere.intensity = 0.12;
    sun.intensity = 0; sun.castShadow = false;
    sun.position.copy(target).add(new THREE.Vector3(1, 1.6, -1).multiplyScalar(radius));
    for (const light of extraSuns) light.intensity = 0;
    uniforms.localGridInfo.value.w = 0;
  }

  // The map's fog as the view draws it (the Game look only), and the view's background in its far colour
  function fog() {
    if (!fogShown) return;
    const values = fogUniforms((atmosphere ? atmosphere() : scene?.atmosphere)?.world?.fog, fogLight);
    setFog(values);
    if (neutral.background === undefined) neutral.background = world.background;
    world.background = values.fogOn ? new THREE.Color().setRGB(...values.fogOpposite.map((v, k) => (v + values.fogInscatter[k]) / 2), THREE.LinearSRGBColorSpace)
      : neutral.background;
  }

  return { apply, setLights, dim, fog, sunMoved, get available() { return all.length > 0; }, get grid() { return grid; },
           get packed() { return packed; }, get mode() { return lastMode; },
           get counts() { return { all: all.length, enabled: enabled.length, local: local.length, perCell: deepest }; } };
}

function dataTexture(array, width, height) {
  const texture = new THREE.DataTexture(array, width, height, THREE.RGBAFormat, THREE.FloatType);
  texture.minFilter = texture.magFilter = THREE.NearestFilter;
  texture.needsUpdate = true;
  return texture;
}
