// The likeness's drawing (private/plans/done/effects-and-sounds-plan.md, Part J2, stage FXV2): a particle system
// drawn roughly as the game draws it, from its export's draw data (effects_draw.py) stepped by effects_sim.js. Each
// sprite emitter is one set of instanced quads that face the camera (or lie along their speed), textured with the
// picture and mask the export picked and blended as its material says; each mesh emitter is one instanced mesh.
// effects_wiring.js owns where and when: this makes a likeness, steps it and lets it go.
//
// A likeness's group holds its particles in the emitter's own frame, in the game's axes (z up): the caller gives the
// group the matrix that takes that frame to the view (the actor's pose and scale, its component's, and SWAP).
//
// An emitter whose material has a program (game-likeness plan, E1: the draw record's `program`, a mesh emitter's
// `programs` a section) is drawn by it, as the game's shader draws it: its colour, glow, cut-out and opacity from the
// particle's own colour, sub-image, dynamic parameter and the material's textures; the rest by the textures' roles.
import * as THREE from 'three';
import { LIMITS, alphaErodes, deliverEvents, linkEmitters, makeEmitter, warmTime } from './effects_sim.js';
import { FOG_PARS, fogShared } from './atmosphere_shader.js';
import { PARTICLE_VARYINGS, constantAt, inputsRead, programFor, programGlsl } from './material_program.js';

/** The game's axes to the view's (y and z changed over), as a matrix: the last factor of a likeness's matrix. */
export const SWAP = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1);
const REPLAY_PAUSE = 2;       // seconds before an effect that has played out is played again (the editor only)
const MODES = { BLEND_Translucent: 0, BLEND_Additive: 1, BLEND_Modulate: 2, BLEND_Masked: 3, BLEND_Opaque: 4 };
// The height of what is being drawn into, in CSS pixels: the view's, or the Add panel's pane while it draws (app.js
// and effects_wiring.js set it), for a sprite's least size on the screen.
export const viewHeight = { value: 800 };
const LEAST_PIXELS = 2;
const DIM_FLOOR = 0.3;
const FACING = { PSA_Square: 0, PSA_Rectangle: 1, PSA_Velocity: 2, PSA_TypeSpecific: 0 };

const VERTEX = /* glsl */`
attribute vec3 aOffset; attribute vec3 aSize; attribute vec4 aColour; attribute vec3 aVel; attribute float aImage;
uniform vec2 uScale; uniform vec2 uGrid; uniform float uFacing; uniform float uViewHeight;
varying vec2 vUv; varying vec2 vCorner; varying vec4 vColour; varying vec3 vFogWorld;
void main() {
  vec4 mv = modelViewMatrix * vec4(aOffset, 1.0);
  vFogWorld = (modelMatrix * vec4(aOffset, 1.0)).xyz;
  float w = aSize.x * uScale.x, h = uFacing > 0.5 ? aSize.y * uScale.y : w;
  // never thinner than two pixels on the screen: a spark or an ember far off stays a dot (the game's spark
  // materials scale with the camera's distance for the same reason)
  float least = ${LEAST_PIXELS.toFixed(2)} * 2.0 * max(-mv.z, 1.0) / (projectionMatrix[1][1] * uViewHeight);
  w = max(abs(w), least) * sign(w + 1e-9); h = max(abs(h), least) * sign(h + 1e-9);
  vec2 right = vec2(1.0, 0.0), up = vec2(0.0, 1.0);
  if (uFacing > 1.5) {
    vec2 d = (modelViewMatrix * vec4(aVel, 0.0)).xy;
    float n = length(d);
    if (n > 1e-5) { up = d / n; right = vec2(up.y, -up.x); }
  } else {
    float c = cos(aSize.z), s = sin(aSize.z);
    right = vec2(c, s); up = vec2(-s, c);
  }
  mv.xy += right * position.x * w + up * position.y * h;
  gl_Position = projectionMatrix * mv;
  vec2 uv = vec2(position.x + 0.5, 0.5 - position.y);
  float i = floor(aImage + 0.001);
  vUv = (vec2(mod(i, uGrid.x), floor(i / uGrid.x)) + uv) / uGrid;
  vCorner = position.xy;
  vColour = aColour;
}`;
const FRAGMENT = /* glsl */`
${FOG_PARS}
varying vec3 vFogWorld;
uniform sampler2D uPicture; uniform sampler2D uMask;
uniform float uHasPicture; uniform float uHasMask; uniform float uOpacity; uniform float uMaskFrom; uniform float uMode; uniform float uSoft; uniform float uLit;
uniform float uErode; uniform vec3 uTint;
varying vec2 vUv; varying vec2 vCorner; varying vec4 vColour;
void main() {
  vec4 t = uHasPicture > 0.5 ? texture2D(uPicture, vUv) : vec4(1.0);
  float bright = max(max(t.r, t.g), t.b), a = 1.0;
  // the picture's part in the shape (uOpacity: 0 its brightness, 1 its alpha, 2 none: the colour alone)
  if (uHasPicture > 0.5) a = uOpacity < 0.5 ? bright : uOpacity < 1.5 ? t.a : 1.0;
  // (a cut-out sprite with nothing else to cut it is cut by its brightness: a shape on black)
  if (uHasPicture > 0.5 && uMode > 2.5 && uMode < 3.5 && uSoft > 0.5 && uOpacity > 1.5 && uHasMask < 0.5) a = bright * 3.0;
  // the mask's (uMaskFrom: 0 its brightness, 1 its alpha, 2 its red channel: a texture of three packed channels)
  if (uHasMask > 0.5) { vec4 m = texture2D(uMask, vUv); a *= uMaskFrom < 0.5 ? max(max(m.r, m.g), m.b) : uMaskFrom < 1.5 ? m.a : m.r; }
  // nothing to shape it: a soft round dot
  if (uSoft > 0.5 && uHasPicture < 0.5 && uHasMask < 0.5) a *= smoothstep(0.5, 0.15, length(vCorner));
  // (a lit material shows by the scene's light too: its colour, which is what it glows with, never draws it black)
  vec3 rgb = max(t.rgb * uTint * max(vColour.rgb, vec3(uLit)), 0.0);
  // (a see-through particle whose colour is set dark is still seen: URB_Bar's steam, Brightness 0.05, is a dull grey
  // wisp in the game, not a black one, and the night smoke a dark grey plume; it is lifted to DIM_FLOOR by a grey
  // added to it, so a dark tint keeps only a hint of its hue)
  if (uMode < 0.5) { float top = max(max(rgb.r, rgb.g), rgb.b), floor = ${DIM_FLOOR.toFixed(2)} * (uHasPicture > 0.5 ? max(bright, 0.25) : 1.0);
    if (top < floor) rgb += vec3(floor - top); }
  // the particle's alpha fades the shape, or erodes it where it never goes under 1 (effects_sim.alphaErodes)
  a = uErode > 0.5 ? pow(max(a, 0.0), max(vColour.a, 0.0)) : a * vColour.a;
  if (uMode > 3.5) { gl_FragColor = vec4(rgb, 1.0); }
  else if (uMode > 2.5) { if (a < 0.33) discard; gl_FragColor = vec4(rgb, 1.0); }
  else if (uMode > 1.5) {
    // (the map's fog, game-likeness plan C2: a darkening particle darkens less through it)
    a = clamp(a, 0.0, 1.0) * heightFog(vFogWorld).a; gl_FragColor = vec4(mix(vec3(1.0), min(rgb, 1.0), a), 1.0); return;
  }
  else {
    // see-through and added: the colour weighed by the opacity before it is laid on (premultiplied), as the game's
    // translucency lays a bright colour: a glow of 6 at 20% shows as bright as a white at full
    a = clamp(a, 0.0, 1.0);
    gl_FragColor = vec4(rgb * a, uMode > 0.5 ? 0.0 : a);
  }
  // the map's fog (game-likeness plan, C2; none in the Neutral look): a solid particle takes it as a lit piece does, a
  // see-through one weighed by its opacity (its colour is premultiplied), and an added one is only dimmed by it, as
  // the game fogs an additive material
  vec4 fogged = heightFog(vFogWorld);
  if (uMode > 2.5) gl_FragColor.rgb = gl_FragColor.rgb * fogged.a + fogged.rgb;
  else if (uMode > 0.5) gl_FragColor.rgb *= fogged.a;
  else gl_FragColor.rgb = gl_FragColor.rgb * fogged.a + fogged.rgb * gl_FragColor.a;
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

// a mesh particle: the mesh at each particle's place, turn and size, drawn with the same fragment as a sprite
const MESH_VERTEX = /* glsl */`
attribute vec4 aColour;
varying vec2 vUv; varying vec2 vCorner; varying vec4 vColour; varying vec3 vFogWorld;
void main() {
  vUv = uv; vCorner = vec2(0.0); vColour = aColour;
  vFogWorld = (modelMatrix * instanceMatrix * vec4(position, 1.0)).xyz;
  gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0);
}`;
// ---- A particle by its material's program (E1)
// (?programs=off draws every likeness by its textures' roles, as the pieces' own flag does, and ?programs=pieces the
// likenesses alone: the probes' before and after; no control of the user's)
const PROGRAMS_ASKED = new URLSearchParams(globalThis.location?.search ?? '').get('programs');
const PROGRAMS_ON = PROGRAMS_ASKED !== 'off' && PROGRAMS_ASKED !== 'pieces';
/** The program a draw record's part is drawn by: a sprite's `program`, a mesh's section's of `programs`; null where it
 *  has none, programs are off, or it gives no colour. */
export function partProgram(draw, section = 0) {
  if (!PROGRAMS_ON) return null;
  const program = draw.kind === 'mesh' ? draw.programs?.[section] ?? null : draw.program ?? null;
  return program && (program.outputs?.diffuse || program.outputs?.glow) ? program : null;
}
/** The outputs of a particle's program the drawing reads: its colour (a lit one's), glow (an unlit one's whole
 *  colour), cut-out and, for a see-through one, its opacity (an added one's colour is weighed by it already). */
export function particleOutputs(program, blend) {
  const out = ['diffuse', 'glow', 'mask'].filter(o => program.outputs?.[o]);
  if (program.outputs?.opacity && blend === 'BLEND_Translucent') out.push('opacity');
  return out;
}
// the varyings a sprite's vertex shader writes for its program (material_program.js reads them by these names)
const SPRITE_PROGRAM_VARYINGS = ['varying vec2 vProgUv0;', 'varying vec2 vProgUv1;', 'varying vec3 vProgCamera;',
  ...Object.values(PARTICLE_VARYINGS).map(([type, name]) => `varying ${type} ${name};`)].join('\n');
const SPRITE_PROGRAM_VERTEX = /* glsl */`
attribute vec3 aOffset; attribute vec3 aSize; attribute vec4 aColour; attribute vec3 aVel; attribute float aImage; attribute vec4 aDynamic;
uniform vec2 uScale; uniform vec2 uGrid; uniform float uFacing; uniform float uViewHeight; uniform float uBlend;
varying vec3 vFogWorld;
${SPRITE_PROGRAM_VARYINGS}
void main() {
  vec4 mv = modelViewMatrix * vec4(aOffset, 1.0);
  vFogWorld = (modelMatrix * vec4(aOffset, 1.0)).xyz;
  float w = aSize.x * uScale.x, h = uFacing > 0.5 ? aSize.y * uScale.y : w;
  float least = ${LEAST_PIXELS.toFixed(2)} * 2.0 * max(-mv.z, 1.0) / (projectionMatrix[1][1] * uViewHeight);
  w = max(abs(w), least) * sign(w + 1e-9); h = max(abs(h), least) * sign(h + 1e-9);
  vec2 right = vec2(1.0, 0.0), up = vec2(0.0, 1.0);
  if (uFacing > 1.5) {
    vec2 d = (modelViewMatrix * vec4(aVel, 0.0)).xy;
    float n = length(d);
    if (n > 1e-5) { up = d / n; right = vec2(up.y, -up.x); }
  } else {
    float c = cos(aSize.z), s = sin(aSize.z);
    right = vec2(c, s); up = vec2(-s, c);
  }
  mv.xy += right * position.x * w + up * position.y * h;
  gl_Position = projectionMatrix * mv;
  // the corner's UV in its sub-image (the game's texcoord0: the whole texture where the emitter steps through none),
  // and in the next one, blended toward it by the index's fraction where the emitter blends (E3: PSUVIM_Linear_Blend)
  vec2 uv = vec2(position.x + 0.5, 0.5 - position.y);
  float i = floor(aImage + 0.001), j = min(i + 1.0, uGrid.x * uGrid.y - 1.0);
  vProgUv0 = (vec2(mod(i, uGrid.x), floor(i / uGrid.x)) + uv) / uGrid;
  vProgUv1 = (vec2(mod(j, uGrid.x), floor(j / uGrid.x)) + uv) / uGrid;
  vProgSubLerp = uBlend > 0.5 ? clamp(aImage - i, 0.0, 1.0) : 0.0;
  vProgParticle = aColour; vProgDynamic = aDynamic; vProgClip = gl_Position;
  // the vector to the camera in the sprite's own frame (its right, its up, toward the camera)
  vProgCamera = vec3(dot(right, -mv.xy), dot(up, -mv.xy), -mv.z);
}`;
// a mesh particle's: the program's own vertex part (its UVs, colours and tangent frame), on the instance's matrix
const MESH_PROGRAM_VERTEX = glsl => /* glsl */`
attribute vec4 aColour; attribute vec4 aDynamic;
varying vec3 vFogWorld;
${glsl.vertexDeclarations}
void main() {
  mat4 progModel = modelMatrix * instanceMatrix;
  vec3 transformed = position;
  vFogWorld = (progModel * vec4(position, 1.0)).xyz;
  gl_Position = projectionMatrix * viewMatrix * progModel * vec4(position, 1.0);
  ${glsl.vertexBody.replaceAll('modelMatrix', 'progModel')}
  ${glsl.reads.particleColor ? 'vProgParticle = aColour;' : ''}
  ${glsl.reads.dynamic ? 'vProgDynamic = aDynamic;' : ''}
  ${glsl.reads.clipPosition ? 'vProgClip = gl_Position;' : ''}
  ${glsl.reads.subImageLerp ? 'vProgSubLerp = 0.0;' : ''}
}`;
// The scene's depth behind a particle (E3): the Game look's pieces' depth while its frame draws the likenesses
// (post_chain.js), else none, so nothing is behind and a soft edge doesn't fade; given to the program as 1 / the
// distance, which its sum with the ratio (-1, 1) turns into the distance (material_program.js progSceneDepth)
const sceneDepth = { uSceneDepth: { value: null }, uSceneDepthOn: { value: 0 }, uDepthRange: { value: new THREE.Vector2(1, 1e6) } };
/** The pieces' depth texture for the likenesses' pass of the Game look's frame (with its camera), or null after it. */
export function setSceneDepth(texture, camera = null) {
  sceneDepth.uSceneDepth.value = texture;
  sceneDepth.uSceneDepthOn.value = texture ? 1 : 0;
  if (camera) sceneDepth.uDepthRange.value.set(camera.near, camera.far);
}
const SCENE_DEPTH = /* glsl */`
#define PROG_SCENE_DEPTH
uniform sampler2D uSceneDepth; uniform float uSceneDepthOn; uniform vec2 uDepthRange;
vec4 progSceneDepth(vec2 uv) {
  if (uSceneDepthOn < 0.5) return vec4(0.0, 0.0, 0.0, 1e-6);
  float n = uDepthRange.x, f = uDepthRange.y;
  float viewZ = n * f / ((f - n) * texture2D(uSceneDepth, uv).r - f);
  return vec4(0.0, 0.0, 0.0, 1.0 / max(-viewZ, 1e-3));
}`;
const PROGRAM_FRAGMENT = glsl => /* glsl */`
${FOG_PARS}
varying vec3 vFogWorld;
uniform float uMode; uniform vec3 uLight;
${glsl.fragmentDeclarations.includes('PROG_SCENE_DEPTH') ? SCENE_DEPTH : ''}
${glsl.fragmentDeclarations}
void main() {
  ${glsl.fragmentBody}
  // a lit material's colour by the light at its place (uLight), and what it gives off by itself
  vec3 rgb = max(${glsl.outputs.includes('diffuse') ? 'progOut_diffuse.rgb * uLight' : 'vec3(0.0)'} + ${glsl.outputs.includes('glow') ? 'progOut_glow.rgb' : 'vec3(0.0)'}, 0.0);
  float a = ${glsl.outputs.includes('opacity') ? 'clamp(progOut_opacity.x, 0.0, 1.0)' : '1.0'};
  ${glsl.outputs.includes('mask') ? 'if (any(lessThan(progOut_mask, vec4(0.0)))) discard;' : ''}
  vec4 fogged = heightFog(vFogWorld);
  if (uMode > 2.5) gl_FragColor = vec4(rgb * fogged.a + fogged.rgb, 1.0);
  else if (uMode > 1.5) { gl_FragColor = vec4(mix(vec3(1.0), min(rgb, 1.0), fogged.a), 1.0); return; }
  // (an added material's colour comes weighed by its opacity, as its shader gives it; a see-through one's is weighed
  // here, the colour laid on premultiplied as the game's translucency lays it)
  else if (uMode > 0.5) gl_FragColor = vec4(rgb * fogged.a, 0.0);
  else gl_FragColor = vec4((rgb * fogged.a + fogged.rgb) * a, a);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;
// the engine's values a program may read, as the page gives them
const programCamera = { value: new THREE.Vector4(0, 0, 0, 1) };
const SCREEN_BIAS = [0.5, 0.5, 0.5, 0.5];   // (clip space to the GL texture's coordinates: v up, as clip y is)
/** A particle's material made from its program: { material, samplers: [{ name, texture, srgb }], moving: [...] } or
 *  null where its GLSL can't be made. `vertex`: 'sprite' or 'mesh'; `values`: the material's own parameter values
 *  (the program's record of them), for a constant that moves with time. */
function programMaterial(draw, program, vertex) {
  let glsl;
  const outputs = particleOutputs(program, draw.blend);
  try { glsl = programGlsl(program, outputs); }
  catch (error) { console.warn(`a particle program not drawn: ${error.message}`); return null; }
  glsl.reads = inputsRead(programFor(program, outputs));      // (what the outputs drawn read: the vertex part writes those)
  const mode = MODES[draw.blend] ?? 0, solid = mode >= 3, uniforms = { uMode: { value: mode }, uLight: { value: new THREE.Vector3(1, 1, 1) }, ...fogShared, ...sceneDepth };
  const moving = [];
  for (const u of glsl.uniforms) {
    const record = program.constants[u.constant];
    if (record.engine === 'cameraWorldPos') { uniforms[u.name] = programCamera; continue; }
    const value = record.engine === 'screenPositionScaleBias' ? SCREEN_BIAS : record.value;
    uniforms[u.name] = { value: new THREE.Vector4(...value) };
    if (record.vector || record.scalars) moving.push({ uniform: uniforms[u.name], record });
  }
  for (const s of glsl.samplers) uniforms[s.name] = { value: blank };
  if (vertex === 'sprite') Object.assign(uniforms, { uScale: { value: new THREE.Vector2(1, 1) }, uViewHeight: viewHeight,
    uGrid: { value: new THREE.Vector2(...(draw.interp && draw.interp !== 'PSUVIM_None' ? [draw.subImages?.[0] ?? 1, draw.subImages?.[1] ?? 1] : [1, 1])) },
    uFacing: { value: FACING[draw.facing] ?? 0 }, uBlend: { value: draw.interp === 'PSUVIM_Linear_Blend' ? 1 : 0 } });
  const material = new THREE.ShaderMaterial({
    vertexShader: vertex === 'sprite' ? SPRITE_PROGRAM_VERTEX : MESH_PROGRAM_VERTEX(glsl), fragmentShader: PROGRAM_FRAGMENT(glsl),
    uniforms, depthWrite: solid, transparent: !solid, side: THREE.DoubleSide,
  });
  if (mode === 0 || mode === 1) {
    material.blending = THREE.CustomBlending; material.blendEquation = THREE.AddEquation;
    material.blendSrc = THREE.OneFactor; material.blendDst = mode === 1 ? THREE.OneFactor : THREE.OneMinusSrcAlphaFactor;
    material.premultipliedAlpha = true;
  }
  if (mode === 2) { material.blending = THREE.CustomBlending; material.blendSrc = THREE.DstColorFactor; material.blendDst = THREE.ZeroFactor; material.toneMapped = false; }
  material.customProgramCacheKey = () => `particle-${vertex}-${glsl.key}-${mode}`;
  return { material, glsl, moving, samplers: glsl.samplers.map(s => ({ name: s.name, texture: s.record.texture, srgb: Boolean(s.record.srgb) })) };
}
/** Its textures loaded into a program material's samplers: a promise of whether all came (false: it is not drawn). */
async function loadSamplers(made, deps) {
  const maps = await Promise.all(made.samplers.map(s => deps.texture(s.texture, s.srgb).catch(() => null)));
  if (maps.some(m => !m)) return false;
  made.samplers.forEach((s, k) => { made.material.uniforms[s.name].value = maps[k]; });
  return true;
}
/** The program's constants that move with time, worked out at `time` (the likeness's own clock). */
function moveConstants(made, values, time) {
  for (const m of made?.moving ?? []) m.uniform.value.fromArray(constantAt(m.record, values, time));
}

/** Which texture gives a draw record its colour and which its shape: { picture, opacity, mask, maskFrom } (draw
 *  version 4, effects_draw.pick_textures). A record of draw version 3 or before (a library template kept from then)
 *  is read as it was meant: a packed picture ('channel') shapes by its red channel and gives no colour. */
function textureRoles(draw) {
  if (draw.opacity === 'channel') return { picture: null, opacity: 'none', mask: draw.picture ?? draw.mask ?? null, maskFrom: 'red' };
  return { picture: draw.picture ?? null, opacity: draw.opacity ?? 'brightness', mask: draw.mask ?? null, maskFrom: draw.maskFrom ?? 'brightness' };
}
function particleMaterial(draw, vertexShader, soft) {
  const mode = MODES[draw.blend] ?? 0, roles = textureRoles(draw);
  const solid = mode >= 3;
  const material = new THREE.ShaderMaterial({
    vertexShader, fragmentShader: FRAGMENT, depthWrite: solid, transparent: !solid, side: THREE.DoubleSide,
    uniforms: { uPicture: { value: blank }, uMask: { value: blank }, uHasPicture: { value: 0 }, uHasMask: { value: 0 }, uSoft: { value: soft ? 1 : 0 }, uLit: { value: draw.lit ? 0.3 : 0 },
                uOpacity: { value: { brightness: 0, alpha: 1, none: 2 }[roles.opacity] ?? 0 }, uMaskFrom: { value: { brightness: 0, alpha: 1, red: 2 }[roles.maskFrom] ?? 0 },
                uMode: { value: mode }, uScale: { value: new THREE.Vector2(1, 1) }, uViewHeight: viewHeight,
                uErode: { value: alphaErodes(draw) ? 1 : 0 }, uTint: { value: new THREE.Vector3(1, 1, 1) },
                uGrid: { value: new THREE.Vector2(draw.subImages?.[0] ?? 1, draw.subImages?.[1] ?? 1) }, uFacing: { value: FACING[draw.facing] ?? 0 },
                ...fogShared },
  });
  // (see-through and added colours come premultiplied: the fragment shader's last lines)
  if (mode === 0 || mode === 1) {
    material.blending = THREE.CustomBlending; material.blendEquation = THREE.AddEquation;
    material.blendSrc = THREE.OneFactor; material.blendDst = mode === 1 ? THREE.OneFactor : THREE.OneMinusSrcAlphaFactor;
    material.premultipliedAlpha = true;
  }
  if (mode === 2) { material.blending = THREE.CustomBlending; material.blendSrc = THREE.DstColorFactor; material.blendDst = THREE.ZeroFactor; material.toneMapped = false; }
  // a see-through or added particle with no colour picture takes its material's own colours (materialTint)
  const tint = !roles.picture && mode < 2 ? materialTint(draw) : null;
  if (tint) material.uniforms.uTint.value.set(...tint);
  return material;
}
/** The tint a material's own colour parameters give a particle with no colour picture (effects_draw.material_colours):
 *  their mean, brought down to 1 at most keeping its hue; null where the material has none. The night smoke's are
 *  all but black: its plume is drawn dark (then lifted to a dark grey by DIM_FLOOR), not white or pink. */
function materialTint(draw) {
  const colours = Object.values(draw.colours ?? {}).filter(c => Array.isArray(c) && c.length >= 3);
  if (!colours.length) return null;
  const mean = [0, 1, 2].map(k => colours.reduce((sum, c) => sum + Math.max(0, Number(c[k]) || 0), 0) / colours.length);
  const top = Math.max(1, ...mean);
  return mean.map(v => v / top);
}
const quad = new THREE.PlaneGeometry(1, 1);
const CHARRED = 0.12;
const blank = new THREE.DataTexture(new Uint8Array([255, 255, 255, 255]), 1, 1);
blank.needsUpdate = true;

function spriteObject(first, draw, deps) {
  let sim = first;
  const n = sim.pos.length / 3, geometry = new THREE.InstancedBufferGeometry();
  geometry.index = quad.index;
  geometry.setAttribute('position', quad.getAttribute('position'));
  const attr = (name, k) => { const a = new THREE.InstancedBufferAttribute(new Float32Array(n * k), k); a.setUsage(THREE.DynamicDrawUsage); geometry.setAttribute(name, a); return a; };
  const at = { offset: attr('aOffset', 3), size: attr('aSize', 3), colour: attr('aColour', 4), vel: attr('aVel', 3), image: attr('aImage', 1),
                dynamic: attr('aDynamic', 4) };
  geometry.instanceCount = 0;
  // by its material's program where it has one (E1), else by its textures' roles; a program whose textures don't
  // all come is given up for the roles
  const program = partProgram(draw), made = program ? programMaterial(draw, program, 'sprite') : null;
  let material = made?.material ?? particleMaterial(draw, VERTEX, true);
  const load = (key, uniform, flag) => key && deps.texture(key).then(tex => { if (tex && !object.userData.gone) { material.uniforms[uniform].value = tex; material.uniforms[flag].value = 1; } }).catch(() => {});
  const object = new THREE.Mesh(geometry, material), roles = textureRoles(draw);
  const byRoles = () => Promise.all([load(roles.picture, 'uPicture', 'uHasPicture'), load(roles.mask, 'uMask', 'uHasMask')]);
  object.frustumCulled = false; object.renderOrder = 6; object.raycast = () => {};
  object.userData.program = Boolean(made);
  // until its textures are in, nothing: a white square would flash
  object.visible = made ? !made.samplers.length : !(roles.picture || roles.mask);
  object.userData.ready = (made ? loadSamplers(made, deps).then(ok => {
    if (ok || object.userData.gone) return null;
    material.dispose(); material = object.material = particleMaterial(draw, VERTEX, true); object.userData.program = false;
    return byRoles();
  }) : byRoles()).then(() => { object.visible = true; });
  object.userData.light = rgb => { if (object.userData.program) material.uniforms.uLight.value.set(...rgb); };
  object.userData.lightNow = () => (object.userData.program && program.outputs.diffuse ? material.uniforms.uLight.value.toArray() : null);
  object.userData.sync = (scale, time) => {
    const c = sim.count;
    material.uniforms.uScale.value.set(scale[0], scale[1]);
    if (object.userData.program) moveConstants(made, program.values, time);
    at.offset.array.set((sim.drawn ?? sim.pos).subarray(0, 3 * c)); at.vel.array.set(sim.vel.subarray(0, 3 * c));
    at.colour.array.set(sim.colour.subarray(0, 4 * c)); at.image.array.set(sim.image.subarray(0, c));
    at.dynamic.array.set(sim.dynamic.subarray(0, 4 * c));
    for (let p = 0; p < c; p++) { at.size.array[3 * p] = sim.size[3 * p]; at.size.array[3 * p + 1] = sim.size[3 * p + 1]; at.size.array[3 * p + 2] = sim.turn[p]; }
    for (const a of Object.values(at)) { a.clearUpdateRanges?.(); a.addUpdateRange?.(0, c * a.itemSize); a.needsUpdate = true; }
    geometry.instanceCount = c;
  };
  // a new run of the same emitter (a replay: its buffers are the same size) draws into the same objects
  object.userData.rebind = next => { if (next.pos.length !== sim.pos.length) return false; sim = next; return true; };
  // (the quad's index and corners are shared by every sprite: taken off first, so disposing this one leaves them)
  object.userData.dispose = () => {
    object.userData.gone = true; geometry.setIndex(null); geometry.deleteAttribute('position');
    geometry.dispose(); material.dispose();
  };
  return object;
}

const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), v3 = new THREE.Vector3(), s3 = new THREE.Vector3();
function meshObjects(first, draw, deps, group) {
  let sim = first;
  const n = sim.pos.length / 3, made = [];
  const holder = { sync() {}, dispose() { holder.gone = true; for (const o of made) { o.geometry.dispose(); o.material.dispose(); o.dispose(); group.remove(o); } },
                   byProgram: () => made.some(o => o.userData.made),
                   light: rgb => { for (const o of made) if (o.userData.made) o.material.uniforms.uLight.value.set(...rgb); },
                   lightNow: () => { const o = made.find(x => x.userData.made?.glsl.outputs.includes('diffuse')); return o ? o.material.uniforms.uLight.value.toArray() : null; } };
  holder.rebind = next => { if (next.pos.length !== sim.pos.length) return false; sim = next; return true; };
  holder.ready = deps.meshParts(draw).then(async parts => {
    // its own picture and mask where the export picked them (a see-through sheet of vapour), else its material's
    // colour texture as a piece's (a rat, a sheet of paper)
    const roles = textureRoles(draw);
    const [picture, mask] = await Promise.all([roles.picture, roles.mask].map(k => (k ? deps.texture(k).catch(() => null) : null)));
    if (holder.gone) return;
    for (const [i, part] of (parts ?? []).entries()) {
      // the mesh is kept in the view's axes: back into the game's, as the particles are
      const geometry = part.geometry.clone().applyMatrix4(SWAP);
      const instanced = (name, k) => { const a = new THREE.InstancedBufferAttribute(new Float32Array(n * k), k); a.setUsage(THREE.DynamicDrawUsage); geometry.setAttribute(name, a); return a; };
      const colours = instanced('aColour', 4), dynamic = instanced('aDynamic', 4);
      // by its section's program where it has one (E1); a mesh with no colours of its own reads white, as the game
      // gives a material that reads them
      const program = partProgram(draw, i);
      let byProgram = program ? programMaterial(draw, program, 'mesh') : null;
      if (byProgram && !(await loadSamplers(byProgram, deps))) { byProgram.material.dispose(); byProgram = null; }
      if (holder.gone) { byProgram?.material.dispose(); geometry.dispose(); return; }
      if (byProgram?.glsl.reads.color && !geometry.getAttribute('color')) {
        geometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(geometry.getAttribute('position').count * 4).fill(1), 4));
      }
      const material = byProgram?.material ?? particleMaterial(draw, MESH_VERTEX, false);
      if (!byProgram) {
        const shown = picture ?? part.map ?? null;
        if (shown) { material.uniforms.uPicture.value = shown; material.uniforms.uHasPicture.value = 1; material.uniforms.uTint.value.setScalar(1); }
        // a solid mesh with no colour of its own (its material draws only a scrolling glow: the fires' burnt debris)
        // is drawn charred, as the game shows it, not white
        else if (material.uniforms.uMode.value >= 3) material.uniforms.uTint.value.setScalar(CHARRED);
        if (mask) { material.uniforms.uMask.value = mask; material.uniforms.uHasMask.value = 1; }
      }
      const o = new THREE.InstancedMesh(geometry, material, n);
      o.count = 0; o.frustumCulled = false; o.renderOrder = 6; o.raycast = () => {};
      o.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      Object.assign(o.userData, { colours, dynamic, made: byProgram, values: program?.values });
      made.push(o); group.add(o);
    }
  }).catch(() => {});
  holder.sync = (scale, time) => {
    const c = sim.count, at = sim.drawn ?? sim.pos;
    for (const o of made) {
      for (let p = 0; p < c; p++) {
        e.set(sim.meshTurn[3 * p], sim.meshTurn[3 * p + 1], sim.meshTurn[3 * p + 2]);
        m4.compose(v3.set(at[3 * p], at[3 * p + 1], at[3 * p + 2]), q.setFromEuler(e), s3.set(sim.size[3 * p], sim.size[3 * p + 1], sim.size[3 * p + 2]));
        o.setMatrixAt(p, m4);
      }
      o.userData.colours.array.set(sim.colour.subarray(0, 4 * c));
      o.userData.colours.needsUpdate = true;
      o.userData.dynamic.array.set(sim.dynamic.subarray(0, 4 * c));
      o.userData.dynamic.needsUpdate = true;
      moveConstants(o.userData.made, o.userData.values, time);
      o.count = c; o.instanceMatrix.needsUpdate = true;
    }
  };
  return holder;
}

/** Whether a system has anything the page can draw (an emitter with draw data that draws: not one that only sends
 *  events, which is stepped for them). */
export const drawable = system => Boolean(system?.emitters?.some(x => x.draw && x.draw.kind !== 'events'));

/** What of a system the drawing leaves out, as the panel says it: { ignored: [module names], undrawn: [why] }. */
export function leftOut(system) {
  const ignored = new Set(), undrawn = new Set();
  for (const x of system?.emitters ?? []) {
    if (x.draw) for (const k of x.draw.ignored ?? []) ignored.add(k);
    if ((!x.draw || x.draw.kind === 'events') && x.why && x.why !== 'no level of detail left' && x.why !== 'switched off in its system') undrawn.add(x.why);
  }
  return { ignored: [...ignored], undrawn: [...undrawn] };
}

/** A likeness of `system` (an effectSystems record with draw data). deps: { texture(key) -> Promise<Texture | null>,
 *  meshParts(draw) -> Promise<[{ geometry, map }]> }. `params`: the effect's particle parameters
 *  (effects_sim.parametersOf); `seed`: a number. Gives { group (matrixAutoUpdate off: the caller sets its matrix),
 *  step(dt, thin, scale, height), count(), dispose() }: `scale` is [x, y], what a sprite's width and height are
 *  multiplied by (the actor's and its component's scale), `height` the effect's height in the world (game units).
 *  It starts warm: run ahead by its longest life. */
export function makeLikeness(system, deps, { params = {}, seed = 1, warm = true } = {}) {
  const group = new THREE.Group();
  group.matrixAutoUpdate = false;
  const draws = (system?.emitters ?? []).map(x => x.draw).filter(Boolean);
  const limit = Math.max(8, Math.min(LIMITS.emitter, Math.floor(LIMITS.effect / Math.max(1, draws.length))));
  let sims = [], pause = 0, clock = 0;
  // (an emitter drawn by its program gets its colour as the game gives it: its material reads every channel)
  const start = () => {
    sims = draws.map((d, k) => makeEmitter(d, { params, seed: seed * 7919 + k * 104729 + 1, limit, raw: Boolean(partProgram(d)) }));
    linkEmitters(sims);
    parts.forEach((p, k) => p.rebind(sims[k]));
  };
  // each emitter's drawing: made once, and bound to the emitter's next run when it replays (review finding 56: a
  // replay used to release and remake every geometry, material and mesh, and hide the sprites until their textures
  // came back)
  const parts = draws.map(d => {
    const part = { rebind(sim) { if (part.keep?.(sim)) return; part.release?.(); part.make(sim); } };
    // (an emitter that only sends events is stepped and draws nothing)
    if (d.kind === 'events') part.make = () => { part.sync = () => {}; part.ready = Promise.resolve(); part.keep = () => true; part.release = () => {}; };
    else if (d.kind === 'mesh') part.make = sim => { const h = meshObjects(sim, d, deps, group); part.sync = h.sync; part.ready = h.ready; part.keep = h.rebind; part.release = () => h.dispose(); part.byProgram = h.byProgram; part.light = h.light; part.lightNow = h.lightNow; };
    else part.make = sim => { const o = spriteObject(sim, d, deps); group.add(o); part.sync = o.userData.sync; part.ready = o.userData.ready; part.keep = o.userData.rebind; part.release = () => { o.userData.dispose(); group.remove(o); }; part.byProgram = () => o.userData.program; part.light = o.userData.light; part.lightNow = o.userData.lightNow; };
    return part;
  });
  start();
  // A world-space emitter's particles (not bUseLocalSpace) stay where they were in the world when the effect moves (a
  // drag, a copy on the cursor): each step, what has moved since is taken back off them (E3)
  const lastWorld = new THREE.Matrix4(), delta = new THREE.Matrix4(), turn = new THREE.Matrix3(), at = new THREE.Vector3();
  let placed = false;
  const worldSpace = draws.some(d => !d.localSpace);
  const followsWorld = worldSpace || draws.some(d => d.modules?.some(m => m.cls === 'SpawnPerUnit'));
  const was = new THREE.Vector3(), now = new THREE.Vector3();
  function stayInWorld() {
    group.updateWorldMatrix(true, false);
    const moved = placed ? now.setFromMatrixPosition(group.matrixWorld).distanceTo(was.setFromMatrixPosition(lastWorld)) : 0;
    for (const sim of sims) sim.moved = moved;
    if (placed && !group.matrixWorld.equals(lastWorld) && worldSpace) {
      delta.copy(group.matrixWorld).invert().multiply(lastWorld);
      turn.setFromMatrix4(delta);
      sims.forEach((sim, k) => {
        if (draws[k].localSpace) return;
        for (let p = 0; p < sim.count; p++) {
          at.fromArray(sim.pos, 3 * p).applyMatrix4(delta).toArray(sim.pos, 3 * p);
          for (const v of [sim.vel, sim.base]) at.fromArray(v, 3 * p).applyMatrix3(turn).toArray(v, 3 * p);
        }
      });
    }
    lastWorld.copy(group.matrixWorld); placed = true;
  }
  // (each emitter stepped, then what each sent handed to those that receive it, E4)
  const advance = (dt, thin) => { for (const sim of sims) sim.step(dt, thin); deliverEvents(sims); };
  if (warm) { const ahead = warmTime(sims); for (let t = 0; t < ahead; t += 1 / 30) advance(1 / 30, 1); }
  // (lit: an emitter's material gives a colour the light at its place multiplies, E2)
  const lit = draws.some(d => (d.kind === 'mesh' ? d.programs ?? [] : [partProgram(d)]).some((p, k) => p && partProgram(d, k)?.outputs?.diffuse));
  return {
    group, drawn: draws.length, lit,
    /** The light at its place (linear [r, g, b]: lighting.js lightAt) on its lit materials. */
    setLight(rgb) { for (const part of parts) part.light?.(rgb); },
    count: () => sims.reduce((n, sim) => n + sim.count, 0),
    step(dt, thin = 1, scale = [1, 1], height = 0) {
      for (const sim of sims) sim.height = height;
      if (followsWorld) stayInWorld();
      // played out (every emitter has run its loops and lost its last particle): again after a pause
      if (sims.length && sims.every(sim => sim.ended)) { pause += dt; if (pause >= REPLAY_PAUSE) { pause = 0; start(); } }
      else advance(dt, thin);
      clock += dt;
      for (const part of parts) part.sync(scale, clock);
    },
    dispose() { for (const part of parts) part.release?.(); },
    /** What it draws now, emitter by emitter (for checks): its kind, blend, how many particles, whether shown with
     *  its textures in, and the first particles' colour and size. */
    describe() {
      return sims.map((sim, k) => {
        const c = sim.count, first = Math.min(c, 4);
        return { kind: draws[k].kind, blend: draws[k].blend, material: draws[k].material ?? null, count: c,
                 shown: group.children.some(o => o.visible), style: draws[k].style ?? null,
                 program: Boolean(parts[k].byProgram?.()), light: parts[k].lightNow?.() ?? null,
                 colours: [...Array(first).keys()].map(p => [...sim.colour.subarray(4 * p, 4 * p + 4)].map(v => +v.toFixed(2))),
                 sizes: [...Array(first).keys()].map(p => [...sim.size.subarray(3 * p, 3 * p + 3)].map(v => +v.toFixed(1))) };
      });
    },
    /** Once its textures and meshes are read (a picture taken before shows nothing of them). */
    ready: () => Promise.all(parts.map(part => part.ready)).then(() => {}, () => {}),
    /** The box its particles fill now, in the group's own frame (the game's axes), each with its size about it;
     *  null with none alive. `share` (0 to 1): the box that holds that share of what is drawn, weighed by each
     *  particle's size, on each axis: a fire's few far sparks left out of the picture of its flames. */
    bounds(share = 1) {
      const rows = [];
      for (const sim of sims) for (let p = 0; p < sim.count; p++) {
        const r = Math.max(Math.abs(sim.size[3 * p]), Math.abs(sim.size[3 * p + 1]), 1) * (sim.draw.kind === 'mesh' ? 12 : 0.5);
        rows.push([sim.pos[3 * p], sim.pos[3 * p + 1], sim.pos[3 * p + 2], r, r * r]);
      }
      if (!rows.length) return null;
      const box = new THREE.Box3(), cut = (1 - Math.min(1, Math.max(0, share))) / 2;
      for (let k = 0; k < 3; k++) {
        rows.sort((a, b) => a[k] - b[k]);
        const total = rows.reduce((t, x) => t + x[4], 0);
        let low = 0, high = rows.length - 1, seen = 0;
        while (low < high && seen + rows[low][4] <= total * cut) seen += rows[low++][4];
        seen = 0;
        while (high > low && seen + rows[high][4] <= total * cut) seen += rows[high--][4];
        let lo = Infinity, hi = -Infinity;
        for (let i = low; i <= high; i++) { lo = Math.min(lo, rows[i][k] - rows[i][3]); hi = Math.max(hi, rows[i][k] + rows[i][3]); }
        box.min.setComponent(k, lo); box.max.setComponent(k, hi);
      }
      return box;
    },
  };
}
