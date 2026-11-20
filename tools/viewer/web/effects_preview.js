// The likeness's drawing (private/plans/done/effects-and-sounds-plan.md, Part J2, stage FXV2): a particle system
// drawn roughly as the game draws it, from its export's draw data (effects_draw.py) stepped by effects_sim.js. Each
// sprite emitter is one set of instanced quads that face the camera (or lie along their speed), textured with the
// picture and mask the export picked and blended as its material says; each mesh emitter is one instanced mesh.
// app.js owns where and when: this makes a likeness, steps it and lets it go.
//
// A likeness's group holds its particles in the emitter's own frame, in the game's axes (z up): the caller gives the
// group the matrix that takes that frame to the view (the actor's pose and scale, its component's, and SWAP).
import * as THREE from 'three';
import { LIMITS, alphaErodes, makeEmitter, warmTime } from './effects_sim.js';

/** The game's axes to the view's (y and z changed over), as a matrix: the last factor of a likeness's matrix. */
export const SWAP = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1);
const REPLAY_PAUSE = 2;       // seconds before an effect that has played out is played again (the editor only)
const MODES = { BLEND_Translucent: 0, BLEND_Additive: 1, BLEND_Modulate: 2, BLEND_Masked: 3, BLEND_Opaque: 4 };
// The height of what is being drawn into, in CSS pixels: the view's, or the Add panel's pane while it draws (app.js
// sets it), for a sprite's least size on the screen.
export const viewHeight = { value: 800 };
const LEAST_PIXELS = 2;
const DIM_FLOOR = 0.3;
const FACING = { PSA_Square: 0, PSA_Rectangle: 1, PSA_Velocity: 2, PSA_TypeSpecific: 0 };

const VERTEX = /* glsl */`
attribute vec3 aOffset; attribute vec3 aSize; attribute vec4 aColour; attribute vec3 aVel; attribute float aImage;
uniform vec2 uScale; uniform vec2 uGrid; uniform float uFacing; uniform float uViewHeight;
varying vec2 vUv; varying vec2 vCorner; varying vec4 vColour;
void main() {
  vec4 mv = modelViewMatrix * vec4(aOffset, 1.0);
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
  else if (uMode > 1.5) { a = clamp(a, 0.0, 1.0); gl_FragColor = vec4(mix(vec3(1.0), min(rgb, 1.0), a), 1.0); return; }
  else {
    // see-through and added: the colour weighed by the opacity before it is laid on (premultiplied), as the game's
    // translucency lays a bright colour: a glow of 6 at 20% shows as bright as a white at full
    a = clamp(a, 0.0, 1.0);
    gl_FragColor = vec4(rgb * a, uMode > 0.5 ? 0.0 : a);
  }
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
                uGrid: { value: new THREE.Vector2(draw.subImages?.[0] ?? 1, draw.subImages?.[1] ?? 1) }, uFacing: { value: FACING[draw.facing] ?? 0 } },
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
  const at = { offset: attr('aOffset', 3), size: attr('aSize', 3), colour: attr('aColour', 4), vel: attr('aVel', 3), image: attr('aImage', 1) };
  geometry.instanceCount = 0;
  const material = particleMaterial(draw, VERTEX, true);
  const load = (key, uniform, flag) => key && deps.texture(key).then(tex => { if (tex && !object.userData.gone) { material.uniforms[uniform].value = tex; material.uniforms[flag].value = 1; } }).catch(() => {});
  const object = new THREE.Mesh(geometry, material), roles = textureRoles(draw);
  object.frustumCulled = false; object.renderOrder = 6; object.raycast = () => {};
  // until its textures are in, nothing: a white square would flash
  object.visible = !(roles.picture || roles.mask);
  object.userData.ready = Promise.all([load(roles.picture, 'uPicture', 'uHasPicture'), load(roles.mask, 'uMask', 'uHasMask')]).then(() => { object.visible = true; });
  object.userData.sync = scale => {
    const c = sim.count;
    material.uniforms.uScale.value.set(scale[0], scale[1]);
    at.offset.array.set(sim.pos.subarray(0, 3 * c)); at.vel.array.set(sim.vel.subarray(0, 3 * c));
    at.colour.array.set(sim.colour.subarray(0, 4 * c)); at.image.array.set(sim.image.subarray(0, c));
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
  const holder = { sync() {}, dispose() { holder.gone = true; for (const o of made) { o.geometry.dispose(); o.material.dispose(); o.dispose(); group.remove(o); } } };
  holder.rebind = next => { if (next.pos.length !== sim.pos.length) return false; sim = next; return true; };
  holder.ready = deps.meshParts(draw).then(async parts => {
    // its own picture and mask where the export picked them (a see-through sheet of vapour), else its material's
    // colour texture as a piece's (a rat, a sheet of paper)
    const roles = textureRoles(draw);
    const [picture, mask] = await Promise.all([roles.picture, roles.mask].map(k => (k ? deps.texture(k).catch(() => null) : null)));
    if (holder.gone) return;
    for (const part of parts ?? []) {
      // the mesh is kept in the view's axes: back into the game's, as the particles are
      const geometry = part.geometry.clone().applyMatrix4(SWAP);
      const colours = new THREE.InstancedBufferAttribute(new Float32Array(n * 4), 4);
      colours.setUsage(THREE.DynamicDrawUsage);
      geometry.setAttribute('aColour', colours);
      const material = particleMaterial(draw, MESH_VERTEX, false);
      const shown = picture ?? part.map ?? null;
      if (shown) { material.uniforms.uPicture.value = shown; material.uniforms.uHasPicture.value = 1; material.uniforms.uTint.value.setScalar(1); }
      // a solid mesh with no colour of its own (its material draws only a scrolling glow: the fires' burnt debris)
      // is drawn charred, as the game shows it, not white
      else if (material.uniforms.uMode.value >= 3) material.uniforms.uTint.value.setScalar(CHARRED);
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
  // each emitter's drawing: made once, and bound to the emitter's next run when it replays (review finding 56: a
  // replay used to release and remake every geometry, material and mesh, and hide the sprites until their textures
  // came back)
  const parts = draws.map(d => {
    const part = { rebind(sim) { if (part.keep?.(sim)) return; part.release?.(); part.make(sim); } };
    if (d.kind === 'mesh') part.make = sim => { const h = meshObjects(sim, d, deps, group); part.sync = h.sync; part.ready = h.ready; part.keep = h.rebind; part.release = () => h.dispose(); };
    else part.make = sim => { const o = spriteObject(sim, d, deps); group.add(o); part.sync = o.userData.sync; part.ready = o.userData.ready; part.keep = o.userData.rebind; part.release = () => { o.userData.dispose(); group.remove(o); }; };
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
    /** What it draws now, emitter by emitter (for checks): its kind, blend, how many particles, whether shown with
     *  its textures in, and the first particles' colour and size. */
    describe() {
      return sims.map((sim, k) => {
        const c = sim.count, first = Math.min(c, 4);
        return { kind: draws[k].kind, blend: draws[k].blend, material: draws[k].material ?? null, count: c,
                 shown: group.children.some(o => o.visible), style: draws[k].style ?? null,
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
