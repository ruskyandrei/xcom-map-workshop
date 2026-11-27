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

const VERTEX_PARS = '#include <common>\nvarying vec3 vLocalWorld;';
const VERTEX_MAIN = '#include <worldpos_vertex>\nvLocalWorld = ( modelMatrix * vec4( transformed, 1.0 ) ).xyz;';
const FRAGMENT_PARS = `#include <common>
varying vec3 vLocalWorld;
uniform highp sampler2D localLightData;
uniform highp sampler2D localLightGrid;
uniform highp sampler2D localLightIndices;
uniform int localIndexWidth;
uniform vec4 localGridInfo;
uniform vec2 localGridSize;
${FOG_PARS}`;
// UE3: radial attenuation pow(saturate(1 - (d/R)^2), FalloffExponent); spot cone
// square(saturate((dot(L, -dir) - cosOuter) / (cosInner - cosOuter))).
// A material drawn by its program (USE_PROGRAM, scene_pieces.js) takes no highlight from these: in the game the map's
// placed lights are baked into lightmaps, whose pass has no highlight; only the sun (dominant) and live lights do.
const FRAGMENT_MAIN = `#include <lights_fragment_begin>
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
#endif`;

// One shared function, so every lit material shares one program cache key.
function localLightShader(shader) {
  Object.assign(shader.uniforms, uniforms);
  shader.vertexShader = shader.vertexShader.replace('#include <common>', VERTEX_PARS)
    .replace('#include <worldpos_vertex>', VERTEX_MAIN);
  shader.fragmentShader = shader.fragmentShader.replace('#include <common>', FRAGMENT_PARS)
    .replace('#include <lights_fragment_begin>', FRAGMENT_MAIN)
    // the fog in linear light, before three's tone curve and its colour space
    .replace('#include <opaque_fragment>', `#include <opaque_fragment>\n${fogChunk('vLocalWorld')}`);
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
  return material;
}

// UE3 turns FColor into linear colour with a 2.2 power; its lights carry no 1/pi,
// three.js's Lambert term does, hence the pi.
export const linear = (rgb, scale = 1) => rgb.map(v => Math.pow(v, 2.2) * scale);
// a game vector (x, y, z up) in the view's axes (y up)
export const toView = v => new THREE.Vector3(v[0], v[2], v[1]);

/** Map lighting for one scene. Call before the first material compiles. setLights(records) puts the lights as edited
 *  in place of the scene's (editor lights plan 4.6: moved, changed, added and deleted lights, and the area lights their
 *  glowing pieces take along); apply() again after it. */
export function createMapLighting({ world, sun, hemisphere, scene, maxTextureSize = 4096 }) {
  const neutral = { sky: hemisphere.color.clone(), ground: hemisphere.groundColor.clone(), hemi: hemisphere.intensity,
                    sun: sun.color.clone(), intensity: sun.intensity, castShadow: sun.castShadow };
  let all = [], enabled = [], local = [], grid = null, bounds = null, deepest = 0;
  const extraSuns = [];
  let packed = null, lastMode = 'neutral';

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
      lightData.set([p.x, p.y, p.z, l.radius, ...colour, l.falloffExponent, d.x, d.y, d.z, cosOuter, coneScale, 0, 0, 0], i * 16);
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
    lastMode = mode;
    for (const light of extraSuns) world.remove(light, light.target);
    extraSuns.length = 0;
    const lights = mode === 'neutral' ? [] : enabled.filter(l => mode === 'map' || l.role !== 'area');
    const shadowDistance = radius * 3;
    if (mode === 'neutral' || !all.length) {
      setFog(fogUniformsNone());
      if (neutral.background !== undefined) world.background = neutral.background;
      hemisphere.color.copy(neutral.sky); hemisphere.groundColor.copy(neutral.ground); hemisphere.intensity = neutral.hemi;
      sun.color.copy(neutral.sun); sun.intensity = neutral.intensity; sun.castShadow = neutral.castShadow;
      sun.position.copy(target).add(new THREE.Vector3(1, 1.6, -1).multiplyScalar(radius));
      uniforms.localGridInfo.value.w = 0;
      return { local: 0 };
    }
    const skies = lights.filter(l => l.kind === 'sky');
    const sky = [0, 0, 0], ground = [0, 0, 0];
    for (const l of skies) {
      linear(l.color, l.brightness).forEach((v, k) => { sky[k] += v; });
      linear(l.lowerColor, l.lowerBrightness).forEach((v, k) => { ground[k] += v; });
    }
    hemisphere.color.setRGB(...sky); hemisphere.groundColor.setRGB(...ground); hemisphere.intensity = Math.PI;
    // The first directional light drives the shadow-mapped sun; any others light without shadows.
    const directionals = lights.filter(l => l.kind === 'directional');
    const place = (light, l) => {
      light.color.setRGB(...linear(l.color)); light.intensity = l.brightness * Math.PI;
      light.position.copy(target).addScaledVector(toView(l.direction).normalize(), -shadowDistance);
      light.target.position.copy(target);
    };
    if (directionals.length) { place(sun, directionals[0]); sun.castShadow = directionals[0].castShadows; }
    else { sun.intensity = 0; sun.castShadow = false; }
    // the map's fog, its colours turned by the dominant light (C2); the view's background in its far colour
    const fog = fogUniforms(scene?.atmosphere?.world?.fog, directionals[0]?.direction ?? null);
    setFog(fog);
    if (neutral.background === undefined) neutral.background = world.background;
    world.background = fog.fogOn ? new THREE.Color().setRGB(...fog.fogOpposite.map((v, k) => (v + fog.fogInscatter[k]) / 2), THREE.LinearSRGBColorSpace)
      : neutral.background;
    for (const l of directionals.slice(1)) {
      const light = new THREE.DirectionalLight(); place(light, l);
      world.add(light, light.target); extraSuns.push(light);
    }
    const chosen = new Set(lights);
    fillGrid(l => chosen.has(l));
    uniforms.localGridInfo.value.w = bounds && lights.some(l => l.kind === 'point' || l.kind === 'spot') ? 1 : 0;
    return { local: lights.filter(l => l.kind === 'point' || l.kind === 'spot').length };
  }

  /** Solo (editor lights plan 4.6): the map dimmed to a faint neutral, its own lights off; apply() puts it back. */
  function dim(target, radius) {
    hemisphere.color.copy(neutral.sky); hemisphere.groundColor.copy(neutral.ground); hemisphere.intensity = 0.12;
    sun.intensity = 0; sun.castShadow = false;
    sun.position.copy(target).add(new THREE.Vector3(1, 1.6, -1).multiplyScalar(radius));
    for (const light of extraSuns) light.intensity = 0;
    uniforms.localGridInfo.value.w = 0;
  }

  return { apply, setLights, dim, get available() { return all.length > 0; }, get grid() { return grid; },
           get packed() { return packed; }, get mode() { return lastMode; },
           get counts() { return { all: all.length, enabled: enabled.length, local: local.length, perCell: deepest }; } };
}

function dataTexture(array, width, height) {
  const texture = new THREE.DataTexture(array, width, height, THREE.RGBAFormat, THREE.FloatType);
  texture.minFilter = texture.magFilter = THREE.NearestFilter;
  texture.needsUpdate = true;
  return texture;
}
