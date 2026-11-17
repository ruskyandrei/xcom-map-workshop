// The likeness's drawing (private/plans/todo/effects-and-sounds-plan.md, Part J2, stage FXV2): a particle system
// drawn roughly as the game draws it, from its export's draw data (effects_draw.py) stepped by effects_sim.js. Each
// sprite emitter is one set of instanced quads that face the camera (or lie along their speed), textured with the
// picture and mask the export picked and blended as its material says; each mesh emitter is one instanced mesh.
// app.js owns where and when: this makes a likeness, steps it and lets it go.
//
// A likeness's group holds its particles in the emitter's own frame, in the game's axes (z up): the caller gives the
// group the matrix that takes that frame to the view (the actor's pose and scale, its component's, and SWAP).
import * as THREE from 'three';
import { LIMITS, makeEmitter, warmTime } from './effects_sim.js';

/** The game's axes to the view's (y and z changed over), as a matrix: the last factor of a likeness's matrix. */
export const SWAP = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1);
const REPLAY_PAUSE = 2;       // seconds before an effect that has played out is played again (the editor only)
const MODES = { BLEND_Translucent: 0, BLEND_Additive: 1, BLEND_Modulate: 2, BLEND_Opaque: 3, BLEND_Masked: 3 };
const FACING = { PSA_Square: 0, PSA_Rectangle: 1, PSA_Velocity: 2, PSA_TypeSpecific: 0 };

const VERTEX = /* glsl */`
attribute vec3 aOffset; attribute vec3 aSize; attribute vec4 aColour; attribute vec3 aVel; attribute float aImage;
uniform vec2 uScale; uniform vec2 uGrid; uniform float uFacing;
varying vec2 vUv; varying vec2 vCorner; varying vec4 vColour;
void main() {
  vec4 mv = modelViewMatrix * vec4(aOffset, 1.0);
  float w = aSize.x * uScale.x, h = uFacing > 0.5 ? aSize.y * uScale.y : w;
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
uniform sampler2D uPicture; uniform sampler2D uMask;
uniform float uHasPicture; uniform float uHasMask; uniform float uAlpha; uniform float uMode; uniform float uSoft; uniform float uLit;
varying vec2 vUv; varying vec2 vCorner; varying vec4 vColour;
void main() {
  vec4 t = uHasPicture > 0.5 ? texture2D(uPicture, vUv) : vec4(1.0);
  float a = 1.0;
  // (uAlpha: 0 the picture's brightness, 1 its alpha channel, 2 its red channel alone: a packed texture, no colour)
  if (uAlpha > 1.5) { a = t.r; t = vec4(1.0); }
  else if (uHasPicture > 0.5 && uMode < 0.5) a = uAlpha > 0.5 ? t.a : max(max(t.r, t.g), t.b);
  // (a cut-out sprite with no alpha channel is cut by its brightness: a rat on black; a solid mesh is drawn whole)
  else if (uHasPicture > 0.5 && uMode > 2.5) a = uAlpha > 0.5 ? t.a : uSoft > 0.5 ? max(max(t.r, t.g), t.b) * 3.0 : 1.0;
  if (uHasMask > 0.5) { vec4 m = texture2D(uMask, vUv); a *= max(max(m.r, m.g), m.b); }
  // nothing to shape it: a soft round dot
  if (uSoft > 0.5 && uHasPicture < 0.5 && uHasMask < 0.5) a *= smoothstep(0.5, 0.15, length(vCorner));
  // (a lit material shows by the scene's light too: its colour, which is what it glows with, never draws it black)
  vec3 rgb = max(t.rgb * max(vColour.rgb, vec3(uLit)), 0.0);
  a = clamp(a * vColour.a, 0.0, 1.0);
  if (uMode > 2.5) { if (a < 0.33) discard; gl_FragColor = vec4(rgb, 1.0); }
  else if (uMode > 1.5) { gl_FragColor = vec4(mix(vec3(1.0), min(rgb, 1.0), a), 1.0); return; }
  else gl_FragColor = vec4(rgb, a);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

// a mesh particle: the mesh at each particle's place, turn and size, drawn with the same fragment as a sprite
const MESH_VERTEX = /* glsl */`
attribute vec4 aColour;
varying vec2 vUv; varying vec2 vCorner; varying vec4 vColour;
void main() {
  vUv = uv; vCorner = vec2(0.0); vColour = aColour;
  gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0);
}`;
function particleMaterial(draw, vertexShader, soft) {
  const mode = MODES[draw.blend] ?? 0;
  const material = new THREE.ShaderMaterial({
    vertexShader, fragmentShader: FRAGMENT, depthWrite: mode === 3, transparent: mode !== 3, side: THREE.DoubleSide,
    uniforms: { uPicture: { value: blank }, uMask: { value: blank }, uHasPicture: { value: 0 }, uHasMask: { value: 0 }, uSoft: { value: soft ? 1 : 0 }, uLit: { value: draw.lit ? 0.3 : 0 },
                uAlpha: { value: draw.opacity === 'alpha' ? 1 : draw.opacity === 'channel' ? 2 : 0 }, uMode: { value: mode }, uScale: { value: new THREE.Vector2(1, 1) },
                uGrid: { value: new THREE.Vector2(draw.subImages?.[0] ?? 1, draw.subImages?.[1] ?? 1) }, uFacing: { value: FACING[draw.facing] ?? 0 } },
  });
  if (mode === 1) material.blending = THREE.AdditiveBlending;
  if (mode === 2) { material.blending = THREE.CustomBlending; material.blendSrc = THREE.DstColorFactor; material.blendDst = THREE.ZeroFactor; material.toneMapped = false; }
  return material;
}
const quad = new THREE.PlaneGeometry(1, 1);
const blank = new THREE.DataTexture(new Uint8Array([255, 255, 255, 255]), 1, 1);
blank.needsUpdate = true;

function spriteObject(sim, draw, deps) {
  const n = sim.pos.length / 3, geometry = new THREE.InstancedBufferGeometry();
  geometry.index = quad.index;
  geometry.setAttribute('position', quad.getAttribute('position'));
  const attr = (name, k) => { const a = new THREE.InstancedBufferAttribute(new Float32Array(n * k), k); a.setUsage(THREE.DynamicDrawUsage); geometry.setAttribute(name, a); return a; };
  const at = { offset: attr('aOffset', 3), size: attr('aSize', 3), colour: attr('aColour', 4), vel: attr('aVel', 3), image: attr('aImage', 1) };
  geometry.instanceCount = 0;
  const material = particleMaterial(draw, VERTEX, true);
  const load = (key, uniform, flag) => key && deps.texture(key).then(tex => { if (tex && !object.userData.gone) { material.uniforms[uniform].value = tex; material.uniforms[flag].value = 1; } }).catch(() => {});
  const object = new THREE.Mesh(geometry, material);
  object.frustumCulled = false; object.renderOrder = 6; object.raycast = () => {};
  // until its textures are in, nothing: a white square would flash
  object.visible = !(draw.picture || draw.mask);
  object.userData.ready = Promise.all([load(draw.picture, 'uPicture', 'uHasPicture'), load(draw.mask, 'uMask', 'uHasMask')]).then(() => { object.visible = true; });
  object.userData.sync = scale => {
    const c = sim.count;
    material.uniforms.uScale.value.set(scale[0], scale[1]);
    at.offset.array.set(sim.pos.subarray(0, 3 * c)); at.vel.array.set(sim.vel.subarray(0, 3 * c));
    at.colour.array.set(sim.colour.subarray(0, 4 * c)); at.image.array.set(sim.image.subarray(0, c));
    for (let p = 0; p < c; p++) { at.size.array[3 * p] = sim.size[3 * p]; at.size.array[3 * p + 1] = sim.size[3 * p + 1]; at.size.array[3 * p + 2] = sim.turn[p]; }
    for (const a of Object.values(at)) { a.clearUpdateRanges?.(); a.addUpdateRange?.(0, c * a.itemSize); a.needsUpdate = true; }
    geometry.instanceCount = c;
  };
  object.userData.dispose = () => { object.userData.gone = true; geometry.dispose(); material.dispose(); };
  return object;
}

const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), v3 = new THREE.Vector3(), s3 = new THREE.Vector3();
function meshObjects(sim, draw, deps, group) {
  const n = sim.pos.length / 3, made = [];
  const holder = { sync() {}, dispose() { holder.gone = true; for (const o of made) { o.geometry.dispose(); o.material.dispose(); group.remove(o); } } };
  holder.ready = deps.meshParts(draw).then(async parts => {
    // its own picture and mask where the export picked them (a see-through sheet of vapour), else its material's
    // colour texture as a piece's (a rat, a sheet of paper)
    const [picture, mask] = await Promise.all([draw.picture, draw.mask].map(k => (k ? deps.texture(k).catch(() => null) : null)));
    if (holder.gone) return;
    for (const part of parts ?? []) {
      // the mesh is kept in the view's axes: back into the game's, as the particles are
      const geometry = part.geometry.clone().applyMatrix4(SWAP);
      const colours = new THREE.InstancedBufferAttribute(new Float32Array(n * 4), 4);
      colours.setUsage(THREE.DynamicDrawUsage);
      geometry.setAttribute('aColour', colours);
      const material = particleMaterial(draw, MESH_VERTEX, false);
      const shown = picture ?? part.map ?? null;
      if (shown) { material.uniforms.uPicture.value = shown; material.uniforms.uHasPicture.value = 1; }
      if (mask) { material.uniforms.uMask.value = mask; material.uniforms.uHasMask.value = 1; }
      const o = new THREE.InstancedMesh(geometry, material, n);
      o.count = 0; o.frustumCulled = false; o.renderOrder = 6; o.raycast = () => {};
      o.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      o.userData.colours = colours;
      made.push(o); group.add(o);
    }
  }).catch(() => {});
  holder.sync = () => {
    const c = sim.count;
    for (const o of made) {
      for (let p = 0; p < c; p++) {
        e.set(sim.meshTurn[3 * p], sim.meshTurn[3 * p + 1], sim.meshTurn[3 * p + 2]);
        m4.compose(v3.set(sim.pos[3 * p], sim.pos[3 * p + 1], sim.pos[3 * p + 2]), q.setFromEuler(e), s3.set(sim.size[3 * p], sim.size[3 * p + 1], sim.size[3 * p + 2]));
        o.setMatrixAt(p, m4);
      }
      o.userData.colours.array.set(sim.colour.subarray(0, 4 * c));
      o.userData.colours.needsUpdate = true;
      o.count = c; o.instanceMatrix.needsUpdate = true;
    }
  };
  return holder;
}

/** Whether a system has anything the page can draw (an emitter with draw data). */
export const drawable = system => Boolean(system?.emitters?.some(x => x.draw));

/** What of a system the drawing leaves out, as the panel says it: { ignored: [module names], undrawn: [why] }. */
export function leftOut(system) {
  const ignored = new Set(), undrawn = new Set();
  for (const x of system?.emitters ?? []) {
    if (x.draw) for (const k of x.draw.ignored ?? []) ignored.add(k);
    else if (x.why && x.why !== 'no level of detail left' && x.why !== 'switched off in its system') undrawn.add(x.why);
  }
  return { ignored: [...ignored], undrawn: [...undrawn] };
}

/** A likeness of `system` (an effectSystems record with draw data). deps: { texture(key) -> Promise<Texture | null>,
 *  meshParts(draw) -> Promise<[{ geometry, map }]> }. `params`: the effect's particle parameters
 *  (effects_sim.parametersOf); `seed`: a number. Gives { group (matrixAutoUpdate off: the caller sets its matrix),
 *  step(dt, thin, scale), count(), dispose() }: `scale` is [x, y], what a sprite's width and height are multiplied by
 *  (the actor's and its component's scale). It starts warm: run ahead by its longest life. */
export function makeLikeness(system, deps, { params = {}, seed = 1, warm = true } = {}) {
  const group = new THREE.Group();
  group.matrixAutoUpdate = false;
  const draws = (system?.emitters ?? []).map(x => x.draw).filter(Boolean);
  const limit = Math.max(8, Math.min(LIMITS.emitter, Math.floor(LIMITS.effect / Math.max(1, draws.length))));
  let sims = [], pause = 0;
  const start = () => { sims = draws.map((d, k) => makeEmitter(d, { params, seed: seed * 7919 + k * 104729 + 1, limit })); parts.forEach((p, k) => p.rebind(sims[k])); };
  const parts = draws.map(d => {
    const part = { rebind(sim) { part.release?.(); part.sim = sim; part.make(sim); } };
    if (d.kind === 'mesh') part.make = sim => { const h = meshObjects(sim, d, deps, group); part.sync = h.sync; part.ready = h.ready; part.release = () => h.dispose(); };
    else part.make = sim => { const o = spriteObject(sim, d, deps); group.add(o); part.sync = o.userData.sync; part.ready = o.userData.ready; part.release = () => { o.userData.dispose(); group.remove(o); }; };
    return part;
  });
  start();
  const advance = (dt, thin) => { for (const sim of sims) sim.step(dt, thin); };
  if (warm) { const ahead = warmTime(sims); for (let t = 0; t < ahead; t += 1 / 30) advance(1 / 30, 1); }
  return {
    group, drawn: draws.length,
    count: () => sims.reduce((n, sim) => n + sim.count, 0),
    step(dt, thin = 1, scale = [1, 1]) {
      // played out (every emitter has run its loops and lost its last particle): again after a pause
      if (sims.length && sims.every(sim => sim.ended)) { pause += dt; if (pause >= REPLAY_PAUSE) { pause = 0; start(); } }
      else advance(dt, thin);
      for (const part of parts) part.sync(scale);
    },
    dispose() { for (const part of parts) part.release?.(); },
    /** Once its textures and meshes are read (a picture taken before shows nothing of them). */
    ready: () => Promise.all(parts.map(part => part.ready)).then(() => {}, () => {}),
    /** The box its particles fill now, in the group's own frame (the game's axes), each with its size about it;
     *  null with none alive. */
    bounds() {
      const box = new THREE.Box3();
      for (const sim of sims) for (let p = 0; p < sim.count; p++) {
        const r = Math.max(Math.abs(sim.size[3 * p]), Math.abs(sim.size[3 * p + 1]), 1) * (sim.draw.kind === 'mesh' ? 12 : 0.5);
        v3.set(sim.pos[3 * p], sim.pos[3 * p + 1], sim.pos[3 * p + 2]);
        box.expandByPoint(s3.copy(v3).addScalar(r)); box.expandByPoint(s3.copy(v3).addScalar(-r));
      }
      return box.isEmpty() ? null : box;
    },
  };
}
