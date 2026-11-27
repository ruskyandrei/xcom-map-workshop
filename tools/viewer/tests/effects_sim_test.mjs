// The likeness's simulator (effects_sim.js; private/plans/done/effects-and-sounds-plan.md, Part J2, stage FXV2): a
// table read at a time, a random range, a locked vector, a particle parameter through its mode, particles spawned by a
// rate and by a burst, their lives, their move and their change over a life, the budget's thinning, and the same seed
// giving the same particles. On draw records shaped as export 29 makes them (tools/viewer/effects_draw.py).
// Run: node tools/viewer/tests/effects_sim_test.mjs
import assert from 'node:assert/strict';
import { LIMITS, alphaErodes, dataChannels, makeEmitter, parametersOf, rng, sample, warmTime } from '../web/effects_sim.js';

const near = (a, b, e = 1e-4) => assert.ok(Math.abs(a - b) <= e, `${a} is not ${b}`);
const constant = (...v) => ({ op: 1, lock: 0, per: 1, chunk: v.length, scale: 0, start: 0, min: Math.min(...v), max: Math.max(...v), entries: [v, v] });
const between = (lo, hi, lock = 0) => ({ op: 2, lock, per: 2, chunk: 2 * lo.length, scale: 0, start: 0, min: 0, max: 0, entries: [[...lo, ...hi], [...lo, ...hi]] });
const curve = (values, scale = values.length - 1) => ({ op: 1, lock: 0, per: 1, chunk: 1, scale, start: 0, min: 0, max: 1, entries: values.map(v => [v]) });

// --- a seeded random number: the same seed, the same numbers; all in [0, 1)
{
  const a = rng(7), b = rng(7), c = rng(8);
  const xs = [a(), a(), a()], ys = [b(), b(), b()];
  assert.deepEqual(xs, ys);
  assert.notDeepEqual(xs, [c(), c(), c()]);
  assert.ok(xs.every(x => x >= 0 && x < 1));
}

// --- tables
{
  const half = () => 0.5;
  assert.equal(sample(constant(3), 0, half), 3);
  assert.deepEqual(sample(constant(1, 2, 3), 9, half), [1, 2, 3]);
  // a curve over a life: blended between its entries, held at the last, nothing before its start
  const fade = curve([0, 1, 0]);
  near(sample(fade, 0.25, half), 0.5); near(sample(fade, 0.5, half), 1); near(sample(fade, 0.75, half), 0.5); near(sample(fade, 4, half), 0);
  near(sample({ ...fade, start: 0.5 }, 0.25, half), 0);
  // a random range: between its least and its most
  near(sample(between([2], [4]), 0, () => 0), 2); near(sample(between([2], [4]), 0, () => 0.75), 3.5);
  // a vector's axes: each its own number, or one for all three when locked
  let n = 0;
  const count = () => [0.1, 0.5, 0.9][n++ % 3];
  assert.deepEqual(sample(between([0, 0, 0], [10, 10, 10]), 0, count).map(v => Math.round(v)), [1, 5, 9]);
  n = 0;
  assert.deepEqual(sample(between([0, 0, 0], [10, 10, 10], 4), 0, count).map(v => Math.round(v)), [1, 1, 1]);
  // one or the other
  assert.equal(sample({ ...between([2], [4]), op: 3 }, 0, () => 0.2), 2);
  assert.equal(sample({ ...between([2], [4]), op: 3 }, 0, () => 0.8), 4);
  assert.equal(sample(null, 0, half), null);
  assert.equal(sample({ unread: 'kept as DistributionVectorConstantCurve' }, 0, half), null);
}

// --- particle parameters
{
  const wind = { parameter: 'Wind_Strength', kind: 'scalar', modes: ['DPM_Normal'], constant: 0, input: [0, 1], output: [1, 4] };
  assert.equal(sample(wind, 0, null, {}), 1);                       // not saved: its constant, through the ranges
  assert.equal(sample(wind, 0, null, { Wind_Strength: 0.5 }), 2.5);
  assert.equal(sample(wind, 0, null, { Wind_Strength: 7 }), 4);     // held inside the input range
  const colour = { parameter: 'Color', kind: 'vector', modes: ['DPM_Direct', 'DPM_Direct', 'DPM_Direct'], constant: [1, 1, 1],
                   input: [[0, 0, 0], [1, 1, 1]], output: [[0, 0, 0], [1, 1, 1]] };
  assert.deepEqual(sample(colour, 0, null, {}), [1, 1, 1]);
  assert.deepEqual(sample(colour, 0, null, { Color: [0.4, 0.3, 1.5] }), [0.4, 0.3, 1.5]);   // direct: not held to a range
  // a value of the other kind is read (EXP-70 run 2): a number on each axis of a vector, a vector's first as a number
  assert.deepEqual(sample(colour, 0, null, { Color: 0.05 }), [0.05, 0.05, 0.05]);
  assert.equal(sample({ ...wind, modes: ['DPM_Direct'] }, 0, null, { Wind_Strength: [3, 9, 9] }), 3);
  assert.equal(sample({ ...wind, modes: ['DPM_Abs'] }, 0, null, { Wind_Strength: -0.5 }), 2.5);
  // an effect's saved parameters: the first of a name, a colour as three numbers
  assert.deepEqual(parametersOf({ parameters: [{ name: 'Brightness', type: 'PSPT_Scalar', scalar: 0.5 }, { name: 'Brightness', type: 'PSPT_Scalar', scalar: 9 },
    { name: 'Color', type: 'PSPT_Vector', vector: [1.2, 1, 0.5] }, { name: 'Chunk', type: 'PSPT_Color', colour: [0.2, 0.3, 0.4, 1] }, { name: null, type: 'PSPT_None' }] }),
                   { Brightness: 0.5, Color: [1.2, 1, 0.5], Chunk: [0.2, 0.3, 0.4] });
}

// --- an emitter: ten a second, each living two seconds, rising at 50 units a second, fading out
const steam = {
  kind: 'sprite', subImages: [1, 1], interp: 'PSUVIM_None', duration: 1, loops: 0, delay: 0, rate: constant(10), rateScale: constant(1), bursts: [],
  modules: [{ cls: 'Lifetime', Lifetime: constant(2) }, { cls: 'Size', StartSize: constant(20, 20, 20) },
            { cls: 'Velocity', StartVelocity: constant(0, 0, 50), StartVelocityRadial: constant(0) },
            { cls: 'Color', StartColor: { parameter: 'Color', kind: 'vector', modes: ['DPM_Direct', 'DPM_Direct', 'DPM_Direct'], constant: [1, 1, 1],
                                          input: [[0, 0, 0], [1, 1, 1]], output: [[0, 0, 0], [1, 1, 1]] }, StartAlpha: constant(1) },
            { cls: 'ColorScaleOverLife', ColorScaleOverLife: constant(1, 1, 1), AlphaScaleOverLife: curve([1, 0]) },
            { cls: 'SizeMultiplyLife', LifeMultiplier: { ...constant(1, 1, 1), scale: 1, entries: [[1, 1, 1], [3, 3, 3]] }, MultiplyX: true, MultiplyY: false, MultiplyZ: true }],
  ignored: [],
};
{
  const e = makeEmitter(steam, { params: { Color: [0, 1, 0] }, seed: 3 });
  for (let k = 0; k < 100; k++) e.step(0.01);                       // one second
  assert.ok(e.count >= 9 && e.count <= 10, `${e.count}`);
  for (let k = 0; k < 400; k++) e.step(0.01);                       // steady: what a rate of 10 keeps alive for 2 seconds
  assert.ok(e.count >= 19 && e.count <= 21, `${e.count}`);
  assert.ok(!e.ended);
  for (let p = 0; p < e.count; p++) {
    const age = e.age[p], rel = age / 2;
    near(e.pos[3 * p + 2], 50 * age, 0.6); near(e.pos[3 * p], 0);
    assert.deepEqual([...e.colour.slice(4 * p, 4 * p + 3)], [0, 1, 0]);      // the effect's own colour
    near(e.colour[4 * p + 3], 1 - rel, 0.01);                                // fading over its life
    near(e.size[3 * p], 20 * (1 + 2 * rel), 0.3); near(e.size[3 * p + 1], 20);  // growing in X, not in Y
  }
  assert.equal(e.longestLife(), 2);
  assert.equal(warmTime([e]), 2);
  // the same seed, the same particles; thinned to half, about half of them
  const a = makeEmitter(steam, { seed: 5 }), b = makeEmitter(steam, { seed: 5 }), thin = makeEmitter(steam, { seed: 5 });
  for (let k = 0; k < 300; k++) { a.step(0.01); b.step(0.01); thin.step(0.01, 0.5); }
  assert.equal(a.count, b.count);
  assert.deepEqual([...a.pos.slice(0, 3 * a.count)], [...b.pos.slice(0, 3 * b.count)]);
  assert.ok(thin.count >= 9 && thin.count <= 11, `${thin.count}`);
  // never more than its limit, nor than an emitter's budget
  const few = makeEmitter({ ...steam, rate: constant(100000) }, { limit: 12 });
  few.step(0.5);
  assert.equal(few.count, 12);
  const many = makeEmitter({ ...steam, rate: constant(100000) }, { limit: 1e9 });
  many.step(0.5);
  assert.equal(many.count, LIMITS.emitter);
}

// --- one burst, played once: its particles live for ever (a life of 0), and nothing more is spawned
{
  const beam = { kind: 'sprite', subImages: [1, 1], duration: 1, loops: 1, delay: 0.5, rate: constant(0), rateScale: constant(1),
                 bursts: [{ count: 3, countLow: -1, time: 0 }], modules: [{ cls: 'Lifetime', Lifetime: constant(0) }], ignored: [] };
  const e = makeEmitter(beam);
  e.step(0.25);
  assert.equal(e.count, 0);                        // its delay
  e.step(0.5);
  assert.equal(e.count, 3);
  for (let k = 0; k < 50; k++) e.step(0.1);
  assert.equal(e.count, 3);
  assert.ok(!e.ended && !e.spawning);
  assert.equal(warmTime([e]), 0.5);
  // one that dies: ended once its loops are played and the last particle is gone
  const puff = makeEmitter({ ...beam, delay: 0, modules: [{ cls: 'Lifetime', Lifetime: constant(1) }] });
  puff.step(0.1);
  assert.equal(puff.count, 3);
  for (let k = 0; k < 30; k++) puff.step(0.1);
  assert.ok(puff.ended && puff.count === 0);
  // a burst between a least and a most
  const some = makeEmitter({ ...beam, delay: 0, bursts: [{ count: 10, countLow: 4, time: 0 }] }, { seed: 2 });
  some.step(0.1);
  assert.ok(some.count >= 4 && some.count <= 10);
}

// --- where particles are born, a pull, a turn and a sub-image
{
  const box = { kind: 'sprite', subImages: [2, 2], interp: 'PSUVIM_None', duration: 1, loops: 0, delay: 0, rate: constant(200), rateScale: constant(1), bursts: [],
                modules: [{ cls: 'Lifetime', Lifetime: constant(10) },
                          { cls: 'LocationPrimitiveBox', StartLocation: constant(100, 0, 0), SizeX: constant(10), SizeY: constant(20), SizeZ: constant(0), Negative_Z: false },
                          { cls: 'Acceleration', Acceleration: constant(0, 0, -100) }, { cls: 'RotationRate', StartRotationRate: constant(0.5) },
                          { cls: 'SubUV', SubImageIndex: curve([0, 3]) }], ignored: [] };
  const e = makeEmitter(box, { seed: 9 });
  for (let k = 0; k < 10; k++) e.step(0.05);
  assert.ok(e.count > 50);
  for (let p = 0; p < e.count; p++) {
    // (a particle is moved in the step it is born in: one step more than its age)
    const age = e.age[p], moved = age + 0.05;
    assert.ok(e.pos[3 * p] >= 95 && e.pos[3 * p] <= 105 && Math.abs(e.pos[3 * p + 1]) <= 10);
    near(e.vel[3 * p + 2], -100 * moved, 0.01);                     // the pull, since its birth
    near(e.turn[p], Math.PI * moved, 0.01);                         // half a turn a second
    near(e.image[p], 3 * age / 10, 0.01);                           // through four images over its life
  }
  const ball = makeEmitter({ ...box, modules: [{ cls: 'Lifetime', Lifetime: constant(10) },
    { cls: 'LocationPrimitiveSphere', StartLocation: constant(0, 0, 0), StartRadius: constant(50), SurfaceOnly: true, Negative_Z: false },
    { cls: 'Velocity', StartVelocity: constant(0, 0, 0), StartVelocityRadial: constant(10) }] }, { seed: 4 });
  ball.step(0.001);
  for (let p = 0; p < ball.count; p++) {
    near(Math.hypot(ball.pos[3 * p], ball.pos[3 * p + 1], ball.pos[3 * p + 2]), 50, 0.1);
    assert.ok(ball.pos[3 * p + 2] >= -0.01);
    near(Math.hypot(ball.vel[3 * p], ball.vel[3 * p + 1], ball.vel[3 * p + 2]), 10, 0.01);
  }
  // a module the simulator doesn't know changes nothing; an unread table leaves the module's neutral value
  const odd = makeEmitter({ ...box, modules: [{ cls: 'Lifetime', Lifetime: constant(1) }, { cls: 'Orbit' }, { cls: 'Size', StartSize: { unread: 'table not read' } }] });
  odd.step(0.1);
  assert.ok(odd.count > 0 && odd.size[0] === 0);
}

// --- colour that carries data (draw version 4): the fires' green and blue offsets, the night smoke's green scale
{
  const fire = { modules: [{ cls: 'Color', StartColor: between([2, 0, 0], [2, 50, 50]) }] };
  assert.deepEqual(dataChannels(fire), [false, true, true]);
  // a colour scale over life that differs by channel gives the start colour its reach: green 2 x 200
  const plume = { modules: [{ cls: 'Color', StartColor: constant(1, 2, 1) }, { cls: 'ColorScaleOverLife', ColorScaleOverLife: { ...constant(1, 200, 1), entries: [[1, 200, 1], [1, 0.2, 1]] } }] };
  assert.deepEqual(dataChannels(plume), [false, true, false]);
  // one the same in all three is a brightness: no data
  assert.equal(dataChannels({ modules: [{ cls: 'Color', StartColor: constant(1, 1, 1) }, { cls: 'ColorScaleOverLife', ColorScaleOverLife: constant(100, 100, 100) }] }), null);
  assert.equal(dataChannels({ modules: [{ cls: 'Color', StartColor: constant(6.4, 1.92, 0.64) }] }), null);      // a hot core
  // the data channel is drawn as the mean of the others: the plume white, not green and pink
  const sim = makeEmitter({ kind: 'sprite', rate: constant(20), life: null, duration: 1, loops: 0, delay: 0,
    modules: [{ cls: 'Lifetime', Lifetime: constant(2) }, ...plume.modules] }, { seed: 2 });
  sim.step(0.5);
  assert.ok(sim.count > 0);
  near(sim.colour[1], 1);
}

// --- an alpha that erodes: one that rises over a life and never goes under 1.2 (the fires' chunks, 1.5 to 10); one
// set above 1 and held (a steam's Opacity 2) is a plain opacity
{
  assert.equal(alphaErodes({ modules: [{ cls: 'ColorOverLife', AlphaOverLife: curve([1.5, 4, 10]) }] }), true);
  assert.equal(alphaErodes({ modules: [{ cls: 'Color', StartAlpha: constant(2) }] }), false);
  assert.equal(alphaErodes({ modules: [{ cls: 'ColorOverLife', AlphaOverLife: curve([1, 0.5, 0]) }] }), false);
}

// --- a colour saved with no colour field but a vector (URB_Bar's webbing): the vector, not white
assert.deepEqual(parametersOf({ parameters: [{ name: 'Color', type: 'PSPT_Color', vector: [0.12, 0.18, 0.1] }] }), { Color: [0.12, 0.18, 0.1] });
assert.deepEqual(parametersOf({ parameters: [{ name: 'Color', type: 'PSPT_Color', colour: [1, 0, 0, 1] }] }), { Color: [1, 0, 0] });

// --- the dynamic parameter (E1: a program reads it): 1 each with no module; a table at the particle's life, worked
// out once where it says so, the emitter's time where it says so, a speed along an axis times its value
{
  const plain = makeEmitter({ kind: 'sprite', rate: constant(10), duration: 1, loops: 0, delay: 0, modules: [{ cls: 'Lifetime', Lifetime: constant(2) }] }, { seed: 3 });
  plain.step(0.5);
  assert.ok(plain.count > 0);
  assert.deepEqual([...plain.dynamic.subarray(0, 4)], [1, 1, 1, 1]);
  const dyn = { cls: 'ParameterDynamic', DynamicParams: [
    { value: curve([0, 10]), spawnOnly: false, emitterTime: false, method: 'EDPV_UserSet', scaleVelocity: false },
    { value: curve([0, 10]), spawnOnly: true, emitterTime: false, method: 'EDPV_UserSet', scaleVelocity: false },
    { value: constant(2), spawnOnly: false, emitterTime: false, method: 'EDPV_VelocityZ', scaleVelocity: true },
    { value: constant(250), spawnOnly: false, emitterTime: false, method: 'EDPV_UserSet', scaleVelocity: false },
  ] };
  const sim = makeEmitter({ kind: 'sprite', rate: constant(0), bursts: [{ count: 1, countLow: -1, time: 0 }], duration: 9, loops: 0, delay: 0,
    modules: [{ cls: 'Lifetime', Lifetime: constant(2) }, { cls: 'Velocity', StartVelocity: constant(0, 0, 30) }, dyn] }, { seed: 4, raw: true });
  sim.step(0.01); sim.step(0.99);
  assert.equal(sim.count, 1);
  near(sim.dynamic[0], 5, 0.1);        // half its life: half of 10
  near(sim.dynamic[1], 0, 0.1);        // worked out as it was born
  near(sim.dynamic[2], 60);            // its speed up, 30, times 2
  near(sim.dynamic[3], 250);
}
// --- a raw colour: the channels that carry numbers to the material stay as the game gives them (a program reads them)
{
  const fire = { kind: 'sprite', rate: constant(20), duration: 1, loops: 0, delay: 0,
    modules: [{ cls: 'Lifetime', Lifetime: constant(2) }, { cls: 'Color', StartColor: constant(2, 40, 30), StartAlpha: constant(1) }] };
  const raw = makeEmitter(fire, { seed: 5, raw: true }), made = makeEmitter(fire, { seed: 5 });
  raw.step(0.5); made.step(0.5);
  assert.deepEqual([...raw.colour.subarray(0, 3)].map(v => Math.round(v)), [2, 40, 30]);
  assert.ok(made.colour[1] < 3, 'without raw, a data channel is drawn as the others\' brightness');
}

console.log('effects_sim: ok');
