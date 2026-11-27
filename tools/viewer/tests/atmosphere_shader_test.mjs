// The map's height fog as the game draws it (atmosphere_shader.js; game-likeness plan, C2). Run:
// node tools/viewer/tests/atmosphere_shader_test.mjs
import assert from 'node:assert/strict';
import { FOG_PARS, fogAt, fogChunk, fogShared, fogUniforms, fogUniformsNone, setFog, terminatorPower } from '../web/atmosphere_shader.js';

// Dirt Road's fog as the export gives it (every member filled: its own four over Default__WorldInfo's)
const road = { bEnabled: true, FogDensity: 0.02, FogHeight: 1000, FogHeightFalloff: 4, FogMaxOpacity: 1, StartDistance: 0,
               LightTerminatorAngle: 45, OppositeLightBrightness: 0.2, OppositeLightColor: [0.211765, 0.235294, 0.360784, 1],
               LightInscatteringBrightness: 1, LightInscatteringColor: [0.145098, 0.062745, 0.05098, 1] };
const u = fogUniforms(road, [0, 0, -1]);
assert.equal(u.fogOn, 1);
assert.equal(u.fogDensity, 0.02 / 1000);                  // UE3 keeps them a thousand times smaller
assert.equal(u.fogFalloff, 4 / 1000);
assert.equal(u.fogFloor, 0);
assert.ok(Math.abs(u.fogOpposite[0] - 0.2 * 0.211765 ** 2.2) < 1e-9);    // a Color made linear by the engine's 2.2

// off, or absent: no fog
assert.equal(fogUniforms({ ...road, bEnabled: false }).fogOn, 0);
assert.equal(fogUniforms(null).fogOn, 0);
assert.deepEqual(fogAt(fogUniformsNone(), [0, 0, 0], [0, 0, 1000]), [1, [0, 0, 0]]);

// the colours are half and half at the terminator angle
const p = terminatorPower(45);
assert.ok(Math.abs((0.5 + 0.499 * Math.cos(Math.PI / 4)) ** p - 0.5) < 1e-9);

// more fog farther away, and more low down (the density grows below its height)
const camera = [0, -1800, 1800];
const [near] = fogAt(u, [0, -1000, 0], camera), [far] = fogAt(u, [0, 6000, 0], camera);
assert.ok(far < near && near < 1, [near, far]);
const [high] = fogAt(u, [6000, -1800, 1800], camera), [low] = fogAt(u, [6000, -1800, 0], [0, -1800, 0]);
assert.ok(low < high, [low, high]);
// toward the light the inscattering colour, away from it the opposite one
const lit = fogUniforms(road, [1, 0, 0]);
const toward = fogAt(lit, [-20000, 0, 0], [0, 0, 0]), away = fogAt(lit, [20000, 0, 0], [0, 0, 0]);
const share = ([t, c]) => c.map(v => v / (1 - t));
assert.ok(share(toward)[0] / share(toward)[2] > share(away)[0] / share(away)[2]);
// the most it can be
const capped = fogUniforms({ ...road, FogMaxOpacity: 0.3 }, [0, 0, -1]);
assert.ok(fogAt(capped, [0, 90000, 0], camera)[0] >= 0.7 - 1e-9);

// the GLSL declares and uses every uniform, and the chunk calls the function with the place it is given
const body = FOG_PARS.slice(FOG_PARS.indexOf('vec4 heightFog'));
for (const name of Object.keys(fogUniformsNone())) {
  assert.match(FOG_PARS, new RegExp(`uniform \\w+ ${name};`));
  assert.match(body, new RegExp(`\\b${name}\\b`));
}
assert.match(fogChunk('vLocalWorld'), /heightFog\( vLocalWorld \)/);
// one shared set of holders: setting it changes the values the shaders read, never the holders
const holder = fogShared.fogDensity;
setFog(u);
assert.equal(fogShared.fogDensity, holder);
assert.equal(holder.value, u.fogDensity);
assert.deepEqual(fogShared.fogOpposite.value, u.fogOpposite);
setFog(fogUniformsNone());
assert.equal(fogShared.fogOn.value, 0);
console.log('atmosphere shader: ok');
