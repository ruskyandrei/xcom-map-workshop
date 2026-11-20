// Settings kept per browser (web/storage.js, review finding 56): one key style, `workshop.<name>`; a value kept under
// an older name is read once and moved to the new one; blocked storage reads null and drops writes.
// Run: node tools/viewer/tests/storage_test.mjs
import assert from 'node:assert/strict';
import { forget, oldKey, recall, remember } from '../web/storage.js';

const kept = new Map();
globalThis.localStorage = { getItem: k => (kept.has(k) ? kept.get(k) : null), setItem: (k, v) => kept.set(k, String(v)),
                            removeItem: k => kept.delete(k) };

// the older names
assert.equal(oldKey('workshop.flyKeys'), 'viewer.flyKeys');
assert.equal(oldKey('workshop.gameMapsGroup'), 'gameMapsGroup');
assert.equal(oldKey('workshop.managerProjectFiles'), 'xcom-map-workshop.manager.projectFiles');
assert.equal(oldKey('workshop.fold.spawnabout'), 'viewer.fold.spawnabout');
assert.equal(oldKey('workshop.playArea'), null);

// a value under the old name is moved to the new one, once
kept.set('viewer.moveSpeed', '0.5');
assert.equal(recall('workshop.moveSpeed'), '0.5');
assert.deepEqual([...kept], [['workshop.moveSpeed', '0.5']]);
kept.set('viewer.moveSpeed', '2');                  // (an old page writing again doesn't win over the new name)
assert.equal(recall('workshop.moveSpeed'), '0.5');
// nothing under either name; a key with no older name
assert.equal(recall('workshop.turnSpeed'), null);
assert.equal(recall('workshop.playArea'), null);
remember('workshop.playArea', '1');
assert.equal(recall('workshop.playArea'), '1');
forget('workshop.playArea');
assert.equal(recall('workshop.playArea'), null);

// blocked storage: nothing read, nothing thrown
globalThis.localStorage = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); },
                            removeItem: () => { throw new Error('blocked'); } };
assert.equal(recall('workshop.flyKeys'), null);
remember('workshop.flyKeys', '1');
forget('workshop.flyKeys');
console.log('storage: ok');
