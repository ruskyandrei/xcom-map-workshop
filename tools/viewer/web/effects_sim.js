// The likeness's simulator (private/plans/done/effects-and-sounds-plan.md, Part J2, stage FXV2): one emitter of a
// particle system stepped from its export's draw data (effects_draw.py; contract section 8): particles spawned by the
// rate and the bursts, each given a life, a place, a speed, a size, a colour and a turn from the game's baked tables
// or the effect's own particle parameters, then moved and changed over their lives by the followed modules. No three.js
// here: effects_preview.js draws what this steps, and the node tests run it alone.
//
// Everything is in the emitter's own frame and the game's units and axes (z up). It is a likeness: orbit, collision,
// events and attractors are not followed. An emitter drawn by its material's program (draw version 6) keeps its
// colour as the game gives it (`raw`: a channel that carries a number to the material is the material's to read) and
// its four dynamic parameter values (`dynamic`), which the program reads.
//
// Stage E4 (draw version 7): one emitter's particles start, place and end another's in its system (the event
// generator and receivers, the location emitters: `linkEmitters` gives each its peers by name, `deliverEvents` hands
// on what each sent in a step), orbits (each particle drawn at its place plus its orbit's turning offset: `drawn`),
// attractor points, size by speed, kill boxes, and spawning by the distance the effect moved (`moved`, set by the
// caller each step).

export const LIMITS = { emitter: 400, effect: 1500, view: 30000 };
const TAU = Math.PI * 2;

/** A seeded random number function (mulberry32): the same seed, the same particles. */
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** An effect's saved particle parameters as the simulator reads them: { name: number | [x, y, z] } (the first entry of
 *  a name, as the game reads it; a colour as its red, green and blue). */
export function parametersOf(record) {
  const out = {};
  for (const p of record?.parameters ?? []) {
    if (!p.name || p.name in out) continue;
    if (p.type === 'PSPT_Scalar' || p.type === 'PSPT_ScalarRand') out[p.name] = Number(p.scalar ?? 0);
    else if (p.type === 'PSPT_Vector' || p.type === 'PSPT_VectorRand') out[p.name] = (p.vector ?? [0, 0, 0]).slice(0, 3).map(Number);
    // (a colour saved with no colour field but a vector, as URB_Bar's webbing's Color, 0.12 0.18 0.10: the vector,
    // not white; the game shows that webbing a pale grey-green, likeness-bar1)
    else if (p.type === 'PSPT_Color') out[p.name] = (p.colour ?? p.vector ?? [1, 1, 1]).slice(0, 3).map(Number);
  }
  return out;
}

const clamp = (v, lo, hi) => Math.min(Math.max(v, Math.min(lo, hi)), Math.max(lo, hi));
function mapped(v, mode, i0, i1, o0, o1) {
  if (mode === 'DPM_Direct') return v;
  if (mode === 'DPM_Abs') v = Math.abs(v);
  return i1 === i0 ? o0 : o0 + (clamp(v, i0, i1) - i0) * (o1 - o0) / (i1 - i0);
}

/** A distribution's value at `time`: a number (a float's) or [x, y, z] (a vector's), or null where there is none to
 *  read (absent, or `unread`). A table is read at its entry for the time, blended to the next; a random one takes
 *  `rand()` between its least and most (one number for the axes its `lock` ties). A particle parameter takes the
 *  effect's value of that name from `params`, else its constant, through its mode's ranges. A value of the other kind
 *  is read too: a number where the system reads a vector (as many of the game's maps save) is that number on each
 *  axis, a vector where it reads a number its first. The game does so: a copy of URB_Bar's steam with Brightness 5
 *  saved as a number is a bright white cloud beside its twin's faint grey at 0.05 (EXP-70 run 2). */
export function sample(dist, time, rand, params) {
  if (!dist || dist.unread) return null;
  if (dist.parameter) {
    const given = params?.[dist.parameter];
    if (dist.kind === 'scalar') {
      const v = typeof given === 'number' ? given : Array.isArray(given) ? Number(given[0] ?? 0) : Number(dist.constant ?? 0);
      return mapped(v, dist.modes?.[0], dist.input[0], dist.input[1], dist.output[0], dist.output[1]);
    }
    const v = Array.isArray(given) ? given : typeof given === 'number' ? [given, given, given] : dist.constant ?? [0, 0, 0];
    return [0, 1, 2].map(k => mapped(Number(v[k] ?? 0), dist.modes?.[k], dist.input[0][k], dist.input[1][k], dist.output[0][k], dist.output[1][k]));
  }
  const entries = dist.entries, n = entries.length;
  const x = Math.max((time - dist.start) * dist.scale, 0), i = Math.min(Math.floor(x), n - 1), j = Math.min(i + 1, n - 1);
  const a = i === j ? 0 : x - Math.floor(x), e1 = entries[i], e2 = entries[j];
  const width = dist.op === 1 ? dist.chunk : dist.chunk / 2, out = new Array(width);
  if (dist.op === 1) for (let k = 0; k < width; k++) out[k] = e1[k] + (e2[k] - e1[k]) * a;
  else {
    const pickOne = () => (dist.op === 3 ? (rand() < 0.5 ? 0 : 1) : rand());
    const r = [pickOne(), 0, 0];
    if (width === 3) {
      // lock: 0 none, 1 x and y, 2 x and z, 3 y and z, 4 all three
      r[1] = dist.lock === 1 || dist.lock === 4 ? r[0] : pickOne();
      r[2] = dist.lock === 2 || dist.lock === 4 ? r[0] : dist.lock === 3 ? r[1] : pickOne();
    }
    for (let k = 0; k < width; k++) {
      const lo = e1[k] + (e2[k] - e1[k]) * a, hi = e1[width + k] + (e2[width + k] - e1[width + k]) * a;
      out[k] = lo + (hi - lo) * r[k];
    }
  }
  return width === 1 ? out[0] : out;
}

// what a module does when a particle is born (b) and each step (u); p: the particle's index, s: the emitter's state
const num = (v, d) => (typeof v === 'number' ? v : Array.isArray(v) ? v[0] : d);
const vec = (v, d) => (Array.isArray(v) ? v : typeof v === 'number' ? [v, v, v] : d);

const BIRTH = {
  Lifetime(m, s, p) { const v = sample(m.Lifetime, s.time, s.rand, s.params); if (v != null) s.life[p] = Math.max(0, num(v, 0)); },
  Location(m, s, p) { const v = vec(sample(m.StartLocation, s.time, s.rand, s.params), null); if (v) for (let k = 0; k < 3; k++) s.pos[3 * p + k] += v[k]; },
  LocationPrimitiveBox(m, s, p) {
    const at = vec(sample(m.StartLocation, s.time, s.rand, s.params), [0, 0, 0]);
    const size = ['SizeX', 'SizeY', 'SizeZ'].map(k => num(sample(m[k], s.time, s.rand, s.params), 0));
    const lo = ['Negative_X', 'Negative_Y', 'Negative_Z'], hi = ['Positive_X', 'Positive_Y', 'Positive_Z'];
    for (let k = 0; k < 3; k++) {
      const a = m[lo[k]] !== false ? -0.5 : 0, b = m[hi[k]] !== false ? 0.5 : 0;
      s.pos[3 * p + k] += at[k] + size[k] * (a + (b - a) * s.rand());
    }
  },
  LocationPrimitiveSphere(m, s, p) {
    const at = vec(sample(m.StartLocation, s.time, s.rand, s.params), [0, 0, 0]), radius = num(sample(m.StartRadius, s.time, s.rand, s.params), 0);
    // a direction even over the sphere, folded into the halves its flags leave
    const z = 2 * s.rand() - 1, a = TAU * s.rand(), q = Math.sqrt(Math.max(0, 1 - z * z));
    const d = [q * Math.cos(a), q * Math.sin(a), z];
    const flags = [['Positive_X', 'Negative_X'], ['Positive_Y', 'Negative_Y'], ['Positive_Z', 'Negative_Z']];
    for (let k = 0; k < 3; k++) {
      if (m[flags[k][0]] === false && m[flags[k][1]] === false) d[k] = 0;
      else if (m[flags[k][0]] === false) d[k] = -Math.abs(d[k]);
      else if (m[flags[k][1]] === false) d[k] = Math.abs(d[k]);
    }
    const r = radius * (m.SurfaceOnly ? 1 : Math.cbrt(s.rand()));
    for (let k = 0; k < 3; k++) s.pos[3 * p + k] += at[k] + d[k] * r;
    if (m.Velocity) { const v = num(sample(m.VelocityScale, s.time, s.rand, s.params), 0); for (let k = 0; k < 3; k++) s.base[3 * p + k] += d[k] * v; }
  },
  LocationPrimitiveCylinder(m, s, p) {
    const at = vec(sample(m.StartLocation, s.time, s.rand, s.params), [0, 0, 0]);
    const radius = num(sample(m.StartRadius, s.time, s.rand, s.params), 0), height = num(sample(m.StartHeight, s.time, s.rand, s.params), 0);
    const axis = m.HeightAxis === 'PMLPC_HEIGHTAXIS_X' ? 0 : m.HeightAxis === 'PMLPC_HEIGHTAXIS_Y' ? 1 : 2, u = (axis + 1) % 3, w = (axis + 2) % 3;
    const a = TAU * s.rand(), r = radius * (m.SurfaceOnly ? 1 : Math.sqrt(s.rand())), d = [0, 0, 0];
    d[u] = Math.cos(a); d[w] = Math.sin(a);
    const off = [0, 0, 0];
    off[u] = d[u] * r; off[w] = d[w] * r; off[axis] = height * (s.rand() - 0.5);
    for (let k = 0; k < 3; k++) s.pos[3 * p + k] += at[k] + off[k];
    if (m.Velocity) { const v = num(sample(m.VelocityScale, s.time, s.rand, s.params), 0); for (let k = 0; k < 3; k++) s.base[3 * p + k] += d[k] * v; }
  },
  Velocity(m, s, p) {
    const v = vec(sample(m.StartVelocity, s.time, s.rand, s.params), null);
    if (v) for (let k = 0; k < 3; k++) s.base[3 * p + k] += v[k];
    const radial = num(sample(m.StartVelocityRadial, s.time, s.rand, s.params), 0);
    if (radial) {
      const x = s.pos[3 * p], y = s.pos[3 * p + 1], z = s.pos[3 * p + 2], n = Math.hypot(x, y, z);
      if (n > 1e-6) { s.base[3 * p] += x / n * radial; s.base[3 * p + 1] += y / n * radial; s.base[3 * p + 2] += z / n * radial; }
    }
  },
  Acceleration(m, s, p) { const v = vec(sample(m.Acceleration, s.time, s.rand, s.params), null); if (v) for (let k = 0; k < 3; k++) s.accel[3 * p + k] += v[k]; },
  Size(m, s, p) { const v = vec(sample(m.StartSize, s.time, s.rand, s.params), null); if (v) for (let k = 0; k < 3; k++) s.baseSize[3 * p + k] += v[k]; },
  Color(m, s, p) {
    const c = vec(sample(m.StartColor, s.time, s.rand, s.params), null), a = sample(m.StartAlpha, s.time, s.rand, s.params);
    if (c) for (let k = 0; k < 3; k++) s.baseColour[4 * p + k] = c[k];
    if (a != null) s.baseColour[4 * p + 3] = num(a, 1);
  },
  Rotation(m, s, p) { const v = sample(m.StartRotation, s.time, s.rand, s.params); if (v != null) s.turn[p] += num(v, 0) * TAU; },
  RotationRate(m, s, p) { const v = sample(m.StartRotationRate, s.time, s.rand, s.params); if (v != null) s.baseRate[p] += num(v, 0) * TAU; },
  MeshRotation(m, s, p) { const v = vec(sample(m.StartRotation, s.time, s.rand, s.params), null); if (v) for (let k = 0; k < 3; k++) s.meshTurn[3 * p + k] += v[k] * TAU; },
  MeshRotationRate(m, s, p) { const v = vec(sample(m.StartRotationRate, s.time, s.rand, s.params), null); if (v) for (let k = 0; k < 3; k++) s.meshBase[3 * p + k] += v[k] * TAU; },
  ParameterDynamic(m, s, p) { dynamicValues(m, s, p, 0, s.rand, true); },
  // (at a live particle of the emitter it names, picked at random or in turn, with a share of its speed)
  LocationEmitter(m, s, p) {
    const src = s.peers?.get(m.EmitterName);
    if (!src || !src.count) return;
    const q = m.SelectionMethod === 'ELESM_Sequential' ? (s.nextSource = ((s.nextSource ?? -1) + 1) % src.count) : Math.floor(s.rand() * src.count);
    for (let k = 0; k < 3; k++) s.pos[3 * p + k] = src.pos[3 * q + k];
    if (m.bInheritSourceVelocity) {
      const f = m.InheritSourceVelocityScale ?? 1;
      for (let k = 0; k < 3; k++) s.base[3 * p + k] += src.vel[3 * q + k] * f;
    }
  },
  // (where the particle of the same place in the emitter it names is: born there, and kept there each step)
  LocationEmitterDirect(m, s, p) { followSource(m, s, p); },
  Orbit(m, s, p) { orbitValues(m, s, p, 0, s.rand, true); },
};
for (const k of ['Lifetime', 'Location', 'Velocity', 'Size', 'Color', 'Rotation', 'ParameterDynamic']) BIRTH[`${k}_Seeded`] = BIRTH[k];

function followSource(m, s, p) {
  const src = s.peers?.get(m.EmitterName);
  if (!src || p >= src.count) return;
  for (let k = 0; k < 3; k++) { s.pos[3 * p + k] = src.pos[3 * p + k]; s.vel[3 * p + k] = src.vel[3 * p + k]; }
}
/** An orbit module's offset, turn and turning rate for particle `p` (its slot among the emitter's orbits, `m.slot`):
 *  each worked out at birth and, where its options say, each step (at the particle's life or the emitter's time). */
function orbitValues(m, s, p, rel, rand, born) {
  const at = 9 * (s.orbits * p + m.slot);
  const parts = [['OffsetAmount', 'OffsetOptions', 0], ['RotationAmount', 'RotationOptions', 3], ['RotationRateAmount', 'RotationRateOptions', 6]];
  for (const [key, options, k] of parts) {
    const o = m[options] ?? {};
    if (born ? o.bProcessDuringSpawn === false : !o.bProcessDuringUpdate) continue;
    const v = vec(sample(m[key], o.bUseEmitterTime ? s.time : rel, rand, s.params), null);
    if (v) for (let c = 0; c < 3; c++) s.orbit[at + k + c] = v[c];
  }
}
/** The offset of an orbit turned by its turn (in turns about x, y and z, as UE3's rotator from Euler degrees). */
function orbitOffset(o, at, out) {
  const [x, y, z] = [o[at], o[at + 1], o[at + 2]];
  const r = o[at + 3] * TAU, pi = o[at + 4] * TAU, ya = o[at + 5] * TAU;
  // roll about x, then pitch about y, then yaw about z
  const y1 = y * Math.cos(r) - z * Math.sin(r), z1 = y * Math.sin(r) + z * Math.cos(r);
  const x2 = x * Math.cos(pi) + z1 * Math.sin(pi), z2 = -x * Math.sin(pi) + z1 * Math.cos(pi);
  out[0] = x2 * Math.cos(ya) - y1 * Math.sin(ya); out[1] = x2 * Math.sin(ya) + y1 * Math.cos(ya); out[2] = z2;
  return out;
}

/** A dynamic parameter module's four values for particle `p` (ParticleModuleParameterDynamic: each its table at the
 *  particle's life, or the emitter's time where it says so; or the particle's speed along an axis or in all, times
 *  the table's value where it says so), at its birth (`born`) or each step but for those worked out once. */
function dynamicValues(m, s, p, rel, rand, born) {
  (m.DynamicParams ?? []).slice(0, 4).forEach((d, k) => {
    if (!born && d.spawnOnly) return;
    const t = d.emitterTime ? s.time : rel, value = num(sample(d.value, t, rand, s.params), 1);
    const v = [s.vel[3 * p], s.vel[3 * p + 1], s.vel[3 * p + 2]];
    const speed = { EDPV_VelocityX: v[0], EDPV_VelocityY: v[1], EDPV_VelocityZ: v[2], EDPV_VelocityMag: Math.hypot(...v) }[d.method];
    s.dynamic[4 * p + k] = speed === undefined ? value : speed * (d.scaleVelocity ? value : 1);
  });
}

const STEP = {
  SizeMultiplyLife(m, s, p, rel, own) {
    const v = vec(sample(m.LifeMultiplier, rel, own, s.params), null);
    if (!v) return;
    if (m.MultiplyX !== false) s.size[3 * p] *= v[0];
    if (m.MultiplyY !== false) s.size[3 * p + 1] *= v[1];
    if (m.MultiplyZ !== false) s.size[3 * p + 2] *= v[2];
  },
  SizeScale(m, s, p, rel, own) {
    const v = vec(sample(m.SizeScale, rel, own, s.params), null);
    if (!v) return;
    if (m.EnableX !== false) s.size[3 * p] = s.baseSize[3 * p] * v[0];
    if (m.EnableY !== false) s.size[3 * p + 1] = s.baseSize[3 * p + 1] * v[1];
    if (m.EnableZ !== false) s.size[3 * p + 2] = s.baseSize[3 * p + 2] * v[2];
  },
  ColorOverLife(m, s, p, rel, own) {
    const c = vec(sample(m.ColorOverLife, rel, own, s.params), null), a = sample(m.AlphaOverLife, rel, own, s.params);
    if (c) for (let k = 0; k < 3; k++) s.colour[4 * p + k] = c[k];
    if (a != null) s.colour[4 * p + 3] = num(a, 1);
  },
  ColorScaleOverLife(m, s, p, rel, own) {
    const t = m.bEmitterTime ? s.time : rel;
    const c = vec(sample(m.ColorScaleOverLife, t, own, s.params), null), a = sample(m.AlphaScaleOverLife, t, own, s.params);
    if (c) for (let k = 0; k < 3; k++) s.colour[4 * p + k] *= c[k];
    if (a != null) s.colour[4 * p + 3] *= num(a, 1);
  },
  VelocityOverLifetime(m, s, p, rel, own) {
    const v = vec(sample(m.VelOverLife, rel, own, s.params), null);
    if (!v) return;
    for (let k = 0; k < 3; k++) s.vel[3 * p + k] = m.Absolute ? v[k] : s.vel[3 * p + k] * v[k];
  },
  Acceleration(m, s, p, rel, own, dt) { for (let k = 0; k < 3; k++) { const a = s.accel[3 * p + k] * dt; s.vel[3 * p + k] += a; s.base[3 * p + k] += a; } },
  AccelerationOverLifetime(m, s, p, rel, own, dt) {
    const v = vec(sample(m.AccelOverLife, rel, own, s.params), null);
    if (v) for (let k = 0; k < 3; k++) { s.vel[3 * p + k] += v[k] * dt; s.base[3 * p + k] += v[k] * dt; }
  },
  RotationRateMultiplyLife(m, s, p, rel, own) { const v = sample(m.LifeMultiplier, rel, own, s.params); if (v != null) s.rate[p] *= num(v, 1); },
  SubUV(m, s, p, rel, own) { const v = sample(m.SubImageIndex, rel, own, s.params); if (v != null && !s.randomImage) s.image[p] = num(v, 0); },
  MeshRotationRateMultiplyLife(m, s, p, rel, own) { const v = vec(sample(m.LifeMultiplier, rel, own, s.params), null); if (v) for (let k = 0; k < 3; k++) s.meshRate[3 * p + k] *= v[k]; },
  MeshRotationRateOverLife(m, s, p, rel, own) {
    const v = vec(sample(m.RotRate, rel, own, s.params), null);
    if (v) for (let k = 0; k < 3; k++) s.meshRate[3 * p + k] = m.bScaleRotRate ? s.meshRate[3 * p + k] * v[k] : v[k] * TAU;
  },
  ParameterDynamic(m, s, p, rel, own) { dynamicValues(m, s, p, rel, own, false); },
  // (the orbit turns at its rate; its offset and turn again where its options say)
  Orbit(m, s, p, rel, own, dt) {
    orbitValues(m, s, p, rel, own, false);
    const at = 9 * (s.orbits * p + m.slot);
    for (let c = 0; c < 3; c++) s.orbit[at + 3 + c] += s.orbit[at + 6 + c] * dt;
  },
  // (pulled toward its point, within its range, harder near it where it says)
  AttractorPoint(m, s, p, rel, own, dt) {
    const at = vec(sample(m.Position, s.time, own, s.params), [0, 0, 0]), range = num(sample(m.Range, s.time, own, s.params), 0);
    const d = [at[0] - s.pos[3 * p], at[1] - s.pos[3 * p + 1], at[2] - s.pos[3 * p + 2]], n = Math.hypot(...d);
    if (n < 1e-6 || (range > 0 && n > range)) return;
    let strength = num(sample(m.Strength, s.time, own, s.params), 0);
    if (m.StrengthByDistance && range > 0) strength *= (range - n) / range;
    for (let k = 0; k < 3; k++) {
      const pull = d[k] / n * strength * dt;
      s.vel[3 * p + k] += pull;
      if (m.bAffectBaseVelocity) s.base[3 * p + k] += pull;
    }
  },
  // (its size by its speed, axis by axis where it says)
  SizeMultiplyVelocity(m, s, p, rel, own) {
    const v = vec(sample(m.VelocityMultiplier, rel, own, s.params), null);
    if (!v) return;
    const speed = Math.hypot(s.vel[3 * p], s.vel[3 * p + 1], s.vel[3 * p + 2]);
    if (m.MultiplyX !== false) s.size[3 * p] *= v[0] * speed;
    if (m.MultiplyY !== false) s.size[3 * p + 1] *= v[1] * speed;
    if (m.MultiplyZ !== false) s.size[3 * p + 2] *= v[2] * speed;
  },
  // (dies inside its box, or outside it, at the next step; an absolute box measured up from the effect's height)
  KillBox(m, s, p, rel, own) {
    const lo = vec(sample(m.LowerLeftCorner, s.time, own, s.params), null), hi = vec(sample(m.UpperRightCorner, s.time, own, s.params), null);
    if (!lo || !hi) return;
    const at = [s.pos[3 * p], s.pos[3 * p + 1], s.pos[3 * p + 2] + (m.bAbsolute ? s.height : 0)];
    const inside = [0, 1, 2].every(k => at[k] >= Math.min(lo[k], hi[k]) && at[k] <= Math.max(lo[k], hi[k]));
    if (m.bKillInside ? inside : !inside) s.life[p] = Math.max(s.age[p], 1e-6);
  },
  LocationEmitterDirect(m, s, p) { followSource(m, s, p); },
  // (a particle past the height dies at the next step: below it where it is a floor, else above; the height the
  // world's where it is absolute, else the emitter's own)
  KillHeight(m, s, p, rel, own) {
    const h = num(sample(m.Height, s.time, own, s.params), 0), z = s.pos[3 * p + 2] + (m.bAbsolute ? s.height : 0);
    if (m.bFloor ? z < h : z > h) s.life[p] = Math.max(s.age[p], 1e-6);
  },
};
STEP.ParameterDynamic_Seeded = STEP.ParameterDynamic;

/** One emitter's simulation from its draw record (its state's `height` the emitter's own height in the world, set
 *  by the caller). `params`: the effect's particle parameters (parametersOf); `seed`:
 *  a number; `limit`: the most particles it keeps. Gives its state: `count` live particles in the arrays `pos`,
 *  `vel` (3 each), `size` (3), `colour` (4), `turn`, `image`, `meshTurn` (3), `dynamic` (4: 1 each where the emitter
 *  has no dynamic parameter module, as the game gives a material), and step(dt, thin = 1): thin (0 to 1) scales what it
 *  spawns, for the view's budget. `ended` once it has played its loops and its last particle died. `raw`: the colour
 *  is left as the game gives it (a program reads it), not its data channels made brightness (`dataChannels`). */
export function makeEmitter(draw, { params = {}, seed = 1, limit = LIMITS.emitter, raw = false } = {}) {
  const n = Math.max(1, Math.min(limit, LIMITS.emitter)), f = k => new Float32Array(n * k);
  const s = {
    draw, params, rand: rng(seed), count: 0, time: 0, clock: 0, owed: 0, ended: false, spawning: true, loop: -1, fired: new Set(),
    height: 0,      // the emitter's height in the world (game units), which an absolute kill height is measured from
    name: draw.name ?? null, peers: null, sent: [], moved: 0, stopped: false,
    randomImage: draw.interp === 'PSUVIM_Random' || draw.interp === 'PSUVIM_Random_Blend',
    images: Math.max(1, (draw.subImages?.[0] ?? 1) * (draw.subImages?.[1] ?? 1)),
    pos: f(3), base: f(3), vel: f(3), accel: f(3), baseSize: f(3), size: f(3), baseColour: f(4), colour: f(4),
    turn: f(1), baseRate: f(1), rate: f(1), age: f(1), life: f(1), image: f(1), own: f(1), meshTurn: f(3), meshBase: f(3), meshRate: f(3),
    dynamic: f(4),
  };
  // the orbits (each a slot of offset, turn and rate a particle), and where each particle is drawn
  const slotted = new Map();
  for (const m of draw.modules ?? []) if (m.cls === 'Orbit') slotted.set(m, { ...m, slot: slotted.size });
  s.orbits = slotted.size;
  s.orbit = s.orbits ? f(9 * s.orbits) : null;
  s.drawn = s.orbits ? f(3) : null;
  // the events it sends: a particle born, a particle dead
  const sends = (draw.modules ?? []).filter(m => m.cls === 'EventGenerator').flatMap(m => m.Events ?? []);
  const send = (type, p) => {
    for (const e of sends) {
      if (e.Type !== type) continue;
      s.sent.push({ type, name: e.CustomName, pos: [s.pos[3 * p], s.pos[3 * p + 1], s.pos[3 * p + 2]], vel: [s.vel[3 * p], s.vel[3 * p + 1], s.vel[3 * p + 2]] });
    }
  };
  const perUnit = (draw.modules ?? []).find(m => m.cls === 'SpawnPerUnit');
  const slotOf = m => slotted.get(m) ?? m;      // (an orbit with its slot)
  const births = (draw.modules ?? []).filter(m => BIRTH[m.cls]).map(m => [BIRTH[m.cls], slotOf(m)]);
  const data = raw ? null : dataChannels(draw);
  const steps = (draw.modules ?? []).filter(m => STEP[m.cls]).map(m => [STEP[m.cls], slotOf(m)]);
  const fields = [['pos', 3], ['base', 3], ['vel', 3], ['accel', 3], ['baseSize', 3], ['size', 3], ['baseColour', 4], ['colour', 4], ['turn', 1],
                  ['baseRate', 1], ['rate', 1], ['age', 1], ['life', 1], ['image', 1], ['own', 1], ['meshTurn', 3], ['meshBase', 3], ['meshRate', 3],
                  ['dynamic', 4], ...(s.orbits ? [['orbit', 9 * s.orbits], ['drawn', 3]] : [])];
  function spawn() {
    if (s.count >= n) return;
    const p = s.count++;
    for (const [key, k] of fields) s[key].fill(0, p * k, p * k + k);
    s.baseColour.set([1, 1, 1, 1], 4 * p);
    s.dynamic.set([1, 1, 1, 1], 4 * p);
    s.own[p] = s.rand();
    s.image[p] = s.randomImage ? Math.floor(s.rand() * s.images) : 0;
    for (const [birth, m] of births) birth(m, s, p);
    send('EPET_Spawn', p);
    return p;
  }
  /** Particles spawned where another emitter's event happened (`at`, the emitter's frame), with a speed of their own
   *  plus `vel` (a receiver's inherited share). */
  s.spawnAt = (count, at, vel) => {
    for (let i = 0; i < count; i++) {
      const p = spawn();
      if (p === undefined) return;
      for (let k = 0; k < 3; k++) { s.pos[3 * p + k] += at[k]; s.base[3 * p + k] += vel[k]; }
    }
  };
  // a particle's own random number, the same each step (its steps' samples of a random table use it): one function for
  // the emitter, reading the particle being stepped, not a function made per particle per step (review finding 56)
  let ownNow = 0;
  const own = () => ownNow;
  function kill(p) {
    send('EPET_Death', p);
    const last = --s.count;
    if (p !== last) for (const [key, k] of fields) s[key].copyWithin(p * k, last * k, last * k + k);
  }
  /** Every live particle gone (a receiver's kill event), and no more spawned where it says. */
  s.killAll = stop => { s.count = 0; if (stop) s.stopped = true; };
  s.step = (dt, thin = 1) => {
    if (!(dt > 0)) return;
    // the emitter's clock: its delay once, then its duration again and again (as many times as it loops; 0 for ever)
    s.clock += dt;
    const since = s.clock - (draw.delay ?? 0), duration = draw.duration > 0 ? draw.duration : 0;
    if (since >= 0) {
      const loop = duration ? Math.floor(since / duration) : 0;
      s.time = duration ? since - loop * duration : since;
      if (loop !== s.loop) { s.loop = loop; s.fired.clear(); }
      s.spawning = !(draw.loops > 0 && duration && loop >= draw.loops);
    }
    for (let p = s.count - 1; p >= 0; p--) {
      s.age[p] += dt;
      if (s.life[p] > 0 && s.age[p] >= s.life[p]) kill(p);
    }
    if (since >= 0 && s.spawning && !s.stopped) {
      const rate = num(sample(draw.rate, s.time, s.rand, params), 0), scale = num(sample(draw.rateScale, s.time, s.rand, params), 1);
      // (spawned by the distance the effect moved too; its rate left out while it moves, where it says so)
      const moving = perUnit && s.moved > (perUnit.MovementTolerance ?? 0.1);
      if (moving) s.owed += Math.min(s.moved, perUnit.MovementClamp ?? 1e9) / (perUnit.UnitScalar || 50) * num(sample(perUnit.SpawnPerUnit, s.time, s.rand, params), 0) * thin;
      if (!(moving && perUnit.bIgnoreSpawnRateWhenMoving)) s.owed += Math.max(0, rate * scale) * thin * dt;
      while (s.owed >= 1) { s.owed -= 1; spawn(); }
      (draw.bursts ?? []).forEach((b, k) => {
        if (s.fired.has(k) || s.time < b.time * (duration || 1)) return;
        s.fired.add(k);
        const most = Math.max(0, b.count), least = b.countLow >= 0 ? Math.min(b.countLow, most) : most;
        const count = Math.round(least + (most - least) * s.rand());
        for (let i = Math.max(count ? 1 : 0, Math.round(count * thin)); i > 0; i--) spawn();
      });
    }
    for (let p = 0; p < s.count; p++) {
      const rel = s.life[p] > 0 ? Math.min(1, s.age[p] / s.life[p]) : 0;
      ownNow = s.own[p];
      for (let k = 0; k < 3; k++) { s.vel[3 * p + k] = s.base[3 * p + k]; s.size[3 * p + k] = s.baseSize[3 * p + k]; s.meshRate[3 * p + k] = s.meshBase[3 * p + k]; }
      for (let k = 0; k < 4; k++) s.colour[4 * p + k] = s.baseColour[4 * p + k];
      s.rate[p] = s.baseRate[p];
      for (const [step, m] of steps) step(m, s, p, rel, own, dt);
      if (data) {
        // a channel that carries a number for the material, not a colour: the others' brightness in its place
        let sum = 0, n = 0;
        for (let k = 0; k < 3; k++) if (!data[k]) { sum += s.colour[4 * p + k]; n++; }
        for (let k = 0; k < 3; k++) if (data[k]) s.colour[4 * p + k] = n ? sum / n : 1;
      }
      for (let k = 0; k < 3; k++) { s.pos[3 * p + k] += s.vel[3 * p + k] * dt; s.meshTurn[3 * p + k] += s.meshRate[3 * p + k] * dt; }
      s.turn[p] += s.rate[p] * dt;
      if (s.orbits) {
        // drawn at its place plus each orbit's turned offset (UE3's chain modes all taken as adding)
        const off = [0, 0, 0], o = [0, 0, 0];
        for (let k = 0; k < s.orbits; k++) { orbitOffset(s.orbit, 9 * (s.orbits * p + k), o); off[0] += o[0]; off[1] += o[1]; off[2] += o[2]; }
        for (let k = 0; k < 3; k++) s.drawn[3 * p + k] = s.pos[3 * p + k] + off[k];
      }
    }
    s.ended = since >= 0 && !s.spawning && s.count === 0;
  };
  /** The longest a particle born now may live (seconds; 0: for ever or unknown), for the warm start. */
  s.longestLife = () => {
    const m = (draw.modules ?? []).find(x => x.cls.startsWith('Lifetime'));
    const d = m?.Lifetime;
    if (!d) return 0;
    if (d.parameter) return Math.max(...[d.output[0], d.output[1], num(sample(d, 0, () => 0, params), 0)].map(Number).filter(Number.isFinite), 0);
    return d.entries ? Math.max(0, ...d.entries.flat()) : 0;
  };
  return s;
}

/** The emitters of one system told of each other by name (the location emitters and the events find their peers so). */
export function linkEmitters(sims) {
  const peers = new Map(sims.filter(s => s.name).map(s => [s.name, s]));
  for (const s of sims) s.peers = peers;
}
/** What each emitter of a system sent in its last step handed to those that receive it: an event receiver spawns its
 *  count where the event was (with the sender's speed by its share, where it says), a kill receiver ends its particles.
 *  A receiver of no generator type or no name takes every one. */
export function deliverEvents(sims) {
  for (const from of sims) {
    if (!from.sent.length) continue;
    const sent = from.sent;
    from.sent = [];
    for (const ev of sent) {
      for (const to of sims) {
        for (const m of to.draw.modules ?? []) {
          if (m.cls !== 'EventReceiverSpawn' && m.cls !== 'EventReceiverKillParticles') continue;
          const type = m.EventGeneratorType ?? 'EPET_Any';
          if (type !== 'EPET_Any' && type !== ev.type) continue;
          if (m.EventName && m.EventName !== 'None' && m.EventName !== ev.name) continue;
          if (m.cls === 'EventReceiverKillParticles') { to.killAll(Boolean(m.bStopSpawning)); continue; }
          const count = Math.max(0, Math.round(num(sample(m.SpawnCount, to.time, to.rand, to.params), 1)));
          const share = m.bInheritVelocity ? vec(sample(m.InheritVelocityScale, to.time, to.rand, to.params), [1, 1, 1]) : [0, 0, 0];
          to.spawnAt(count, m.bUsePSysLocation ? [0, 0, 0] : ev.pos, ev.vel.map((v, k) => v * share[k]));
        }
      }
    }
  }
}

/** The colour channels an emitter uses to carry numbers to its material rather than colour: [r, g, b] true where its
 *  colour modules reach over DATA_COLOUR in that channel, or null for none. The game's fires do it: their start
 *  colour is red 1 to 3 (the brightness) and green and blue anything up to 50 (each flame's own offset into its
 *  scrolling texture), which as a colour would draw them cyan-white. */
const DATA_COLOUR = 8;
export function dataChannels(draw) {
  const most = [0, 0, 0];
  const look = d => {
    if (!d || d.unread) return;
    const rows = d.parameter ? [d.constant, ...(d.output ?? [])].filter(Array.isArray) : (d.entries ?? []);
    for (const row of rows) {
      const width = d.parameter ? 3 : (d.op === 1 ? d.chunk : d.chunk / 2);
      if (width !== 3) continue;
      for (let k = 0; k < row.length; k++) most[k % 3] = Math.max(most[k % 3], Math.abs(Number(row[k]) || 0));
    }
  };
  for (const m of draw.modules ?? []) {
    if (m.cls === 'Color' || m.cls === 'Color_Seeded') look(m.StartColor);
    else if (m.cls === 'ColorOverLife') look(m.ColorOverLife);
  }
  // a colour scale over life that is not the same in every channel carries data too, by the reach it gives the
  // start colour: the night smoke plumes' green is scaled by up to 200 (the fire's light on the plume's foot),
  // which as a colour drew them pink and green. A scale the same in all three is a brightness and is left alone.
  for (const m of draw.modules ?? []) {
    if (m.cls !== 'ColorScaleOverLife') continue;
    const scale = [0, 0, 0], before = [...most];
    const d = m.ColorScaleOverLife;
    if (!d || d.unread) continue;
    const rows = d.parameter ? [d.constant, ...(d.output ?? [])].filter(Array.isArray) : (d.entries ?? []);
    for (const row of rows) {
      if ((d.parameter ? 3 : (d.op === 1 ? d.chunk : d.chunk / 2)) !== 3) continue;
      for (let k = 0; k < row.length; k++) scale[k % 3] = Math.max(scale[k % 3], Math.abs(Number(row[k]) || 0));
    }
    if (Math.max(...scale) - Math.min(...scale) < 1e-6) continue;
    for (let k = 0; k < 3; k++) most[k] = Math.max(before[k], (before[k] || 1) * scale[k]);
  }
  const out = most.map(v => v > DATA_COLOUR);
  return out.some(Boolean) ? out : null;
}

/** Whether an emitter's alpha erodes its shape rather than fading it: true where its alpha rises over each
 *  particle's life (to half as much again or more) and never goes under ERODE_FROM (its start alpha times its alpha
 *  over life, at their least). The fires' chunks do so: their alpha rises from 1.5 to 10 as they rise, and each
 *  dissolves; as a plain opacity it would make them solid squares. An alpha set above 1 and held (a steam's
 *  Opacity 2) is a plain opacity. The drawing then takes the shape to the power of the alpha. */
const ERODE_FROM = 1.2;
export function alphaErodes(draw) {
  const least = d => {
    if (!d || d.unread) return null;
    if (d.parameter) return Math.min(...[d.constant, ...(d.output ?? [])].map(Number).filter(Number.isFinite));
    const rows = d.entries ?? [];
    return rows.length ? Math.min(...rows.flat().map(Number)) : null;
  };
  // a table over life that ends at half as much again as it starts or more
  const rises = d => Boolean(d && !d.unread && !d.parameter && d.entries?.length > 1 && d.op === 1
    && Number(d.entries.at(-1)[0]) >= 1.5 * Number(d.entries[0][0]) && Number(d.entries.at(-1)[0]) > Number(d.entries[0][0]));
  let start = 1, life = 1, rising = false;
  for (const m of draw.modules ?? []) {
    if (m.cls === 'Color' || m.cls === 'Color_Seeded') start = least(m.StartAlpha) ?? start;
    else if (m.cls === 'ColorOverLife') { start = least(m.AlphaOverLife) ?? start; rising ||= rises(m.AlphaOverLife); }
    else if (m.cls === 'ColorScaleOverLife') { life *= least(m.AlphaScaleOverLife) ?? 1; rising ||= rises(m.AlphaScaleOverLife); }
  }
  return rising && start * life >= ERODE_FROM;
}

/** How far ahead a new likeness is run so it shows at its full reach: its longest life, at most `most` seconds. */
export function warmTime(emitters, most = 5) {
  return Math.min(most, Math.max(0, ...emitters.map(e => e.longestLife() + (e.draw.delay ?? 0))));
}
