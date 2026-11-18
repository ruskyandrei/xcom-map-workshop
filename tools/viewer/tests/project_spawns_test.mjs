// Projects' spawn rules (project.js, schema 4; the editor spawns plan, SP8): `spawnRules` is null (the install's
// behaviour) or { dropIns: 'placed' }; it is part of the state's key, so turning it on or off makes the project unsaved,
// and a malformed one is carried as it is for the compiler to refuse.
// Run: node tools/viewer/tests/project_spawns_test.mjs
import assert from 'node:assert/strict';
import { READ_VERSIONS, SCHEMA_VERSION, sortState, stateKey, validSpawnRules } from '../web/project.js';

assert.equal(SCHEMA_VERSION, 4);
assert.deepEqual(READ_VERSIONS, [1, 2, 3, 4]);

assert.ok(validSpawnRules({ dropIns: 'placed' }));
for (const bad of [null, undefined, {}, { dropIns: 'install' }, { dropIns: true }, { dropIns: 'placed', waves: 'placed' }, ['placed'], 'placed']) {
  assert.ok(!validSpawnRules(bad), JSON.stringify(bad));
}

const base = { overrides: [], added: [] };
assert.equal(sortState(base).spawnRules, null);
assert.deepEqual(sortState({ ...base, spawnRules: { dropIns: 'placed' } }).spawnRules, { dropIns: 'placed' });
// a malformed rule is carried, not dropped
assert.deepEqual(sortState({ ...base, spawnRules: { dropIns: 'somewhere' } }).spawnRules, { dropIns: 'somewhere' });
// the rule is in the key: on and off are different contents
const off = stateKey(sortState(base)), on = stateKey(sortState({ ...base, spawnRules: { dropIns: 'placed' } }));
assert.notEqual(off, on);
assert.equal(stateKey(sortState({ ...base, spawnRules: null })), off);
console.log('project_spawns_test: ok');
