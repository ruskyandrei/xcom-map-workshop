// The likeness's simulator (private/plans/done/effects-and-sounds-plan.md, Part J2, stage FXV2): one emitter of a
// particle system stepped from its export's draw data (effects_draw.py; contract section 8): particles spawned by the
// rate and the bursts, each given a life, a place, a speed, a size, a colour and a turn from the game's baked tables
// or the effect's own particle parameters, then moved and changed over their lives by the followed modules. No three.js
// here: effects_preview.js draws what this steps, and the node tests run it alone.
//
// Everything is in the emitter's own frame and the game's units and axes (z up). It is a likeness: orbit, collision,
// events and attractors are not followed, and what the material's shader does is not known.

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
const sign = (rand, pos, neg) => (pos !== false && neg !== false ? (rand() < 0.5 ? -1 : 1) : pos !== false ? 1 : neg !== false ? -1 : 0);

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
};
for (const k of ['Lifetime', 'Location', 'Velocity', 'Size', 'Color', 'Rotation']) BIRTH[`${k}_Seeded`] = BIRTH[k];

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
};

/** One emitter's simulation from its draw record. `params`: the effect's particle parameters (parametersOf); `seed`:
 *  a number; `limit`: the most particles it keeps. Gives its state: `count` live particles in the arrays `pos`,
 *  `vel` (3 each), `size` (3), `colour` (4), `turn`, `image`, `meshTurn` (3), and step(dt, thin = 1): thin (0 to 1)
 *  scales what it spawns, for the view's budget. `ended` once it has played its loops and its last particle died. */
export function makeEmitter(draw, { params = {}, seed = 1, limit = LIMITS.emitter } = {}) {
  const n = Math.max(1, Math.min(limit, LIMITS.emitter)), f = k => new Float32Array(n * k);
  const s = {
    draw, params, rand: rng(seed), count: 0, time: 0, clock: 0, owed: 0, ended: false, spawning: true, loop: -1, fired: new Set(),
    randomImage: draw.interp === 'PSUVIM_Random' || draw.interp === 'PSUVIM_Random_Blend',
    images: Math.max(1, (draw.subImages?.[0] ?? 1) * (draw.subImages?.[1] ?? 1)),
    pos: f(3), base: f(3), vel: f(3), accel: f(3), baseSize: f(3), size: f(3), baseColour: f(4), colour: f(4),
    turn: f(1), baseRate: f(1), rate: f(1), age: f(1), life: f(1), image: f(1), own: f(1), meshTurn: f(3), meshBase: f(3), meshRate: f(3),
  };
  const births = (draw.modules ?? []).filter(m => BIRTH[m.cls]).map(m => [BIRTH[m.cls], m]);
  const data = dataChannels(draw);
  const steps = (draw.modules ?? []).filter(m => STEP[m.cls]).map(m => [STEP[m.cls], m]);
  const fields = [['pos', 3], ['base', 3], ['vel', 3], ['accel', 3], ['baseSize', 3], ['size', 3], ['baseColour', 4], ['colour', 4], ['turn', 1],
                  ['baseRate', 1], ['rate', 1], ['age', 1], ['life', 1], ['image', 1], ['own', 1], ['meshTurn', 3], ['meshBase', 3], ['meshRate', 3]];
  function spawn() {
    if (s.count >= n) return;
    const p = s.count++;
    for (const [key, k] of fields) s[key].fill(0, p * k, p * k + k);
    s.baseColour.set([1, 1, 1, 1], 4 * p);
    s.own[p] = s.rand();
    s.image[p] = s.randomImage ? Math.floor(s.rand() * s.images) : 0;
    for (const [birth, m] of births) birth(m, s, p);
  }
  function kill(p) {
    const last = --s.count;
    if (p !== last) for (const [key, k] of fields) s[key].copyWithin(p * k, last * k, last * k + k);
  }
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
    if (since >= 0 && s.spawning) {
      const rate = num(sample(draw.rate, s.time, s.rand, params), 0), scale = num(sample(draw.rateScale, s.time, s.rand, params), 1);
      s.owed += Math.max(0, rate * scale) * thin * dt;
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
      const rel = s.life[p] > 0 ? Math.min(1, s.age[p] / s.life[p]) : 0, u = s.own[p], own = () => u;
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

/** The colour channels an emitter uses to carry numbers to its material rather than colour: [r, g, b] true where its
 *  colour modules reach over DATA_COLOUR in that channel, or null for none. The game's fires do it: their start
 *  colour is red 1 to 3 (the brightness) and green and blue anything up to 50 (each flame's own offset into its
 *  scrolling texture), which as a colour would draw them cyan-white. */
export const DATA_COLOUR = 8;
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
export const ERODE_FROM = 1.2;
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
