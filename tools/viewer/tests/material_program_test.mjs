// A material's program as GLSL and run on numbers (material_program.js; game-likeness plan, A-S4), against the case
// file shader_eval.py's numbers are in (material_program_cases.json, made by material_program_cases.py). Run:
// node tools/viewer/tests/material_program_test.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';
import { PARTICLE_VARYINGS, constantAt, evaluateUniform, hash, inputsRead, lightFunctionAt, programFor, programGlsl, runProgram } from '../web/material_program.js';

const here = path.dirname(url.fileURLToPath(import.meta.url));
const cases = JSON.parse(fs.readFileSync(path.join(here, 'material_program_cases.json'), 'utf8'));
assert.ok(cases.length >= 4);

for (const c of cases) {
  // run on numbers: the same as shader_eval.py
  const textures = Object.fromEntries(Object.entries(c.textures).map(([k, colour]) => [k, () => colour]));
  const out = runProgram(c.program, c.inputs, textures);
  for (const [name, expected] of Object.entries(c.expected)) {
    assert.equal(out[name].length, expected.length, `${c.name}: ${name}`);
    out[name].forEach((v, k) => assert.ok(Math.abs(v - expected[k]) < 1e-5, `${c.name}: ${name}[${k}] ${v} != ${expected[k]}`));
  }
  // as GLSL: every output written, every texture a sampler, every constant that isn't a literal a uniform
  const glsl = programGlsl(c.program);
  for (const name of Object.keys(c.program.outputs)) assert.match(glsl.fragmentBody, new RegExp(`progOut_${name} = `));
  assert.equal(glsl.samplers.length, Object.keys(c.program.textures).length);
  const uniforms = Object.values(c.program.constants).filter(r => 'uniform' in r || 'engine' in r || 'vector' in r || 'scalars' in r);
  assert.equal(glsl.uniforms.length, uniforms.length, c.name);
  assert.doesNotMatch(glsl.fragmentBody, /undefined|NaN/);
  // an instance with other values shares the text, so the compiled shader
  const other = structuredClone(c.program);
  for (const r of Object.values(other.constants)) if ('uniform' in r) r.value = r.value.map(v => v + 0.5);
  assert.equal(programGlsl(other).key, glsl.key, c.name);
}

// what each reads
const forest = cases.find(c => c.name === 'ENV_ForestGround').program;
const read = inputsRead(forest);
assert.deepEqual([...read.uv], [0]);
assert.equal(read.color, true);
assert.equal(read.worldPosition, false);
const two = inputsRead(cases.find(c => c.name.includes('two UV')).program);
assert.deepEqual([...two.uv].sort(), [0, 1]);
const tinted = inputsRead(cases.find(c => c.name.includes('tinted')).program);
assert.equal(tinted.worldPosition, true);

// only the outputs asked for are written
const colourOnly = programGlsl(forest, ['diffuse']);
assert.deepEqual(colourOnly.outputs, ['diffuse']);
assert.doesNotMatch(colourOnly.fragmentBody, /progOut_specular/);
assert.notEqual(colourOnly.key, programGlsl(forest).key);
// a program cut to its colour keeps only what the colour reads (no normal map's texture, no camera vector)
const cut = programFor(forest, ['diffuse']);
assert.deepEqual(Object.keys(cut.outputs), ['diffuse']);
assert.ok(cut.code.length < forest.code.length);
assert.deepEqual(Object.values(cut.textures).map(t => t.parameter).sort(), ['Dirt', 'Grass', 'Leaves']);
const forestCase = cases.find(c => c.name === 'ENV_ForestGround');
const textures = Object.fromEntries(Object.entries(forestCase.textures).map(([k, colour]) => [k, () => colour]));
assert.deepEqual(runProgram(cut, forestCase.inputs, textures).diffuse, runProgram(forest, forestCase.inputs, textures).diffuse);
assert.equal(hash('abc'), hash('abc'));
assert.notEqual(hash('abc'), hash('abd'));
// the uniforms that move with time (A8): the same numbers as shader_slice.evaluate_uniform's (uniform_cases.json)
const moving = JSON.parse(fs.readFileSync(path.join(here, 'uniform_cases.json'), 'utf8'));
for (const c of moving.cases) {
  const got = evaluateUniform(c.expr, c.values, c.time);
  got.forEach((v, k) => assert.ok(Math.abs(v - c.value[k]) < 1e-8, `${c.name}: ${got} not ${c.value}`));
}
for (const c of moving.constants) assert.deepEqual(constantAt(c.record, c.values, c.time), c.value, c.name);
assert.throws(() => evaluateUniform({ kind: 'TextureSample' }, {}, 0), /TextureSample/);

// a particle's program (E1): its colour, dynamic parameter, sub-image blend and clip position read from the
// likeness's varyings, and a soft edge's read of the scene's depth (SceneColorTexture's alpha, 1 / the distance)
// turned into the distance by the ratio (-1, 1), less the particle's own depth, over its fade distance
const soft = {
  version: 1, outputs: { glow: { r: 'r1', m: 'xyz' }, opacity: { r: 'r0', m: 'z' } },
  inputs: { i0: [{ kind: 'uv', channel: 0, component: 0, scale: 1, bias: 0 }, { kind: 'uv', channel: 0, component: 1, scale: 1, bias: 0 }, null, null],
            i1: [0, 1, 2, 3].map(component => ({ kind: 'particleColor', component, scale: 1, bias: 0 })),
            i2: [null, null, null, { kind: 'dynamic', component: 3, scale: 1, bias: 0 }],
            i3: [0, 1, 2, 3].map(component => ({ kind: 'clipPosition', component })),
            i4: [{ kind: 'subImageLerp', component: 0, scale: 1, bias: 0 }, null, null, null] },
  constants: { k0: { value: [0.5, 0.5, 0.5, 0.5], engine: 'screenPositionScaleBias' }, k1: { value: [-1, 1, 0, 0], engine: 'minZMaxZRatio' },
               k2: { value: [-1, 0, 0, 0] } },
  textures: { t0: { parameter: 'Smoke', index: 0 }, t1: { engine: 'sceneDepth' } },
  code: [
    { op: 'texld', d: 'r1', m: 'xyzw', s: [{ r: 'i0', w: 'xyzw' }, { r: 't0', w: 'xyzw' }] },
    { op: 'mul', d: 'r1', m: 'xyz', s: [{ r: 'r1', w: 'xyzw' }, { r: 'i1', w: 'xyzw' }] },
    { op: 'add', d: 'r1', m: 'x', s: [{ r: 'r1', w: 'xxxx' }, { r: 'i4', w: 'xxxx' }] },
    { op: 'rcp', d: 'r0', m: 'x', s: [{ r: 'i3', w: 'wwww' }] },
    { op: 'mul', d: 'r0', m: 'xy', s: [{ r: 'r0', w: 'xxxx' }, { r: 'i3', w: 'xyxx' }] },
    { op: 'mad', d: 'r2', m: 'xy', s: [{ r: 'r0', w: 'xyxx' }, { r: 'k0', w: 'xyxx' }, { r: 'k0', w: 'wzxx' }] },
    { op: 'mov', d: 'r2', m: 'zw', s: [{ r: 'k2', w: 'yyyy' }] },
    { op: 'texld', d: 'r3', m: 'xyzw', s: [{ r: 'r2', w: 'xyzw' }, { r: 't1', w: 'xyzw' }], texld: 'lod' },
    { op: 'add', d: 'r0', m: 'z', s: [{ r: 'r3', w: 'wwww' }, { r: 'k1', w: 'yyyy' }] },
    { op: 'add', d: 'r0', m: 'z', s: [{ r: 'r0', w: 'zzzz' }, { r: 'k2', w: 'xxxx' }] },
    { op: 'rcp', d: 'r0', m: 'z', s: [{ r: 'r0', w: 'zzzz' }] },
    { op: 'mad', d: 'r0', m: 'z', s: [{ r: 'k1', w: 'xxxx', n: 1 }, { r: 'r0', w: 'zzzz' }, { r: 'i3', w: 'wwww', n: 1 }] },
    { op: 'rcp', d: 'r0', m: 'w', s: [{ r: 'i2', w: 'wwww' }] },
    { op: 'mul', d: 'r0', m: 'z', s: [{ r: 'r0', w: 'zzzz' }, { r: 'r0', w: 'wwww' }], sat: 1 },
    { op: 'mul', d: 'r0', m: 'z', s: [{ r: 'r0', w: 'zzzz' }, { r: 'i1', w: 'wwww' }] },
  ],
};
{
  const read = inputsRead(soft);
  for (const kind of Object.keys(PARTICLE_VARYINGS)) assert.equal(read[kind], true, kind);
  const glsl = programGlsl(soft);
  // the varyings declared in both halves, the depth read by the shader's own function (a default where it has none),
  // the engine texture no sampler, the read at a level a texture read as it is
  for (const [type, name] of Object.values(PARTICLE_VARYINGS)) assert.match(glsl.fragmentDeclarations, new RegExp(`varying ${type} ${name};`));
  assert.match(glsl.vertexDeclarations, /varying vec4 vProgParticle;/);
  assert.match(glsl.fragmentBody, /progSceneDepth\(/);
  assert.match(glsl.fragmentDeclarations, /#ifndef PROG_SCENE_DEPTH/);
  assert.deepEqual(glsl.samplers.map(s => s.texture), ['t0']);
  assert.match(glsl.fragmentBody, /vProgSubLerp/);
  // on numbers: a grey texel times the particle's colour, red lifted by the blend; 600 units behind, at 100 from
  // the camera, a fade distance of 250: (600 - 100) / 250, saturated, times the particle's alpha 0.5
  const out = runProgram(soft, { uv0: [0.25, 0.75], particleColor: [0.5, 0.25, 1, 0.5], dynamic: [1, 1, 1, 250],
                                 clipPosition: [10, 20, 90, 100], subImageLerp: 0.2 },
                         { t0: () => [0.4, 0.4, 0.4, 1], t1: () => [0, 0, 0, 1 / 600] });
  out.glow.forEach((v, k) => assert.ok(Math.abs(v - [0.4, 0.1, 0.4][k]) < 1e-6, `glow ${out.glow}`));
  assert.ok(Math.abs(out.opacity[0] - 0.5) < 1e-6, `opacity ${out.opacity}`);
  const near = runProgram(soft, { uv0: [0, 0], particleColor: [1, 1, 1, 1], dynamic: [1, 1, 1, 250], clipPosition: [0, 0, 0, 100], subImageLerp: 0 },
                          { t0: () => [1, 1, 1, 1], t1: () => [0, 0, 0, 1 / 150] });
  assert.ok(Math.abs(near.opacity[0] - 0.2) < 1e-6, `a wall 50 units behind fades it to a fifth: ${near.opacity}`);
}
// a light's light function (F1): the factor at each time, the same numbers as shader_eval.py's (light_function_cases.json)
const lightCases = JSON.parse(fs.readFileSync(path.join(here, 'light_function_cases.json'), 'utf8')).cases;
assert.ok(lightCases.length >= 1);
for (const c of lightCases) {
  c.times.forEach((t, n) => {
    const got = lightFunctionAt(c.program, t);
    assert.equal(got.length, 3);
    got.forEach((v, k) => assert.ok(Math.abs(v - c.expected[n][k]) < 1e-5, `${c.name} at ${t}: ${got} not ${c.expected[n]}`));
  });
}
console.log(`material programs: ${cases.length} cases agree with shader_eval.py, ${moving.cases.length} moving uniforms with shader_slice.py, ${lightCases.length} light functions`);
