// A material's program as GLSL and run on numbers (material_program.js; game-likeness plan, A-S4), against the case
// file shader_eval.py's numbers are in (material_program_cases.json, made by material_program_cases.py). Run:
// node tools/viewer/tests/material_program_test.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';
import { constantAt, evaluateUniform, hash, inputsRead, lightFunctionAt, programFor, programGlsl, runProgram } from '../web/material_program.js';

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
