// Projects' spawn rules (project.js, schema 4; the editor spawns plan, SP8): `spawnRules` is null (the install's
// behaviour) or { dropIns: 'placed' }; it is part of the state's key, so turning it on or off makes the project unsaved,
// and a malformed one is carried as it is for the compiler to refuse.
// Run: node tools/viewer/tests/project_spawns_test.mjs
import assert from 'node:assert/strict';
import { READ_VERSIONS, SCHEMA_VERSION, sortState, stateKey, validAdded, validOverride, validSpawnRules } from '../web/project.js';

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

// a base spawn point's override (SP6): a pose, values or both; values never with a light's, an effect's or flags
const T = { package: 'URB_Test', level: 'base', actor: 'TheWorld.PersistentLevel.XComAlienPod_0' };
assert.ok(validOverride({ target: T, spawn: { commander: true } }));
assert.ok(validOverride({ target: T, spawn: { difficulty: 'Hard', destroyedOnTurn: 6 }, location: [0, 0, 0], rotation: [0, 0, 0] }));
assert.ok(validOverride({ target: T, location: [0, 0, 0], rotation: [0, 16384, 0] }));
for (const bad of [{ target: T, spawn: [] }, { target: T, spawn: null }, { target: T, spawn: { destroyedOnTurn: 1.5 } }, { target: T, spawn: { use: {} } },
                   { target: T, spawn: { use: true }, location: [0, 0, 0] }, { target: T, spawn: { use: true }, flags: {} },
                   { target: T, spawn: { use: true }, effect: {} }]) assert.ok(!validOverride(bad), JSON.stringify(bad));

// a copy of a pod or Meld point (SP7): an added record of its own kind, its template, its values, nothing of a piece's
const copy = { id: 'c1', kind: 'pod', actor: 'TheWorld.PersistentLevel.XComAlienPod_0_copy1', from: T, location: [0, 0, 0], rotation: [0, 0, 0] };
assert.ok(validAdded(copy));
assert.ok(validAdded({ ...copy, kind: 'meld', spawn: { difficulty: 'Hard' } }));
assert.ok(validOverride({ target: T, deleted: true }));
for (const bad of [{ ...copy, from: undefined }, { ...copy, components: ['x'] }, { ...copy, spawn: [] }, { ...copy, location: [0, 0] }, { ...copy, kind: 'dropIn' }])
  assert.ok(!validAdded(bad), JSON.stringify(bad));
console.log('project_spawns_test: ok');
