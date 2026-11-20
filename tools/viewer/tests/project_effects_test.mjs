// Projects' records of effects and sounds (project.js, schema 3; the effects and sounds plan, Part C): an override of
// an effect or a sound (a pose, a delete, or its values alone: effect.follow), an added copy with its kind and the
// original it copies, nothing of a piece's copy on it, values of known keys only.
// Run: node tools/viewer/tests/project_effects_test.mjs
import assert from 'node:assert/strict';
import { EFFECT_KINDS, SCHEMA_VERSION, sortState, stateKey, validAdded, validOverride } from '../web/project.js';

assert.equal(SCHEMA_VERSION, 4);      // 4: the spawns plan's records (project_spawns_test.mjs)
assert.deepEqual(EFFECT_KINDS, ['effect', 'sound', 'flare']);
const target = { package: 'URB_Bar', level: 'base', actor: 'TheWorld.PersistentLevel.Emitter_13' };
const pose = { location: [600, 600, 300], rotation: [0, 0, 0] };

// overrides: a pose, with follow none where a piece carries it; follow alone; a delete
assert.ok(validOverride({ target, ...pose }));
assert.ok(validOverride({ target, ...pose, effect: { follow: 'none' } }));
assert.ok(validOverride({ target, effect: { follow: 'none' } }));
assert.ok(validOverride({ target, effect: { follow: 'auto' } }));
assert.ok(validOverride({ target, sound: { radiusMax: 900 } }));        // stage FX5's values are carried as saved
assert.ok(validOverride({ target, deleted: true }));
for (const bad of [{ effect: { follow: 'often' } }, { effect: { colour: 1 } }, { effect: [] }, { effect: null }, { effect: {}, sound: {} },
                   { sound: { follow: 'none' } }, { effect: { follow: 'none' }, location: [1, 2, 3] }])
  assert.ok(!validOverride({ target, ...bad }), JSON.stringify(bad));

// added: a copy with its kind
const copy = { id: 'a', actor: 'TheWorld.PersistentLevel.Emitter_13_copy1', kind: 'effect', from: target, ...pose };
assert.ok(validAdded(copy));
assert.ok(validAdded({ ...copy, kind: 'sound', sound: { volume: [0.5, 0.5] } }));
for (const bad of [{ kind: 'decal' }, { components: ['c'] }, { template: { kind: 'spot', version: 1 } }, { light: {} }, { flags: { walking: false } },
                   { from: undefined }, { kind: 'sound', effect: { follow: 'none' } }, { location: [0, 0] }, { prefab: 'p' }])
  assert.ok(!validAdded({ ...copy, ...bad }), JSON.stringify(bad));
// a lens flare's copy (stage FX6b): its kind and its original, never a values object; nor has its override one
const glare = { ...copy, actor: 'TheWorld.PersistentLevel.LensFlareSource_7_copy2', kind: 'flare', from: { ...target, actor: 'TheWorld.PersistentLevel.LensFlareSource_7' } };
assert.ok(validAdded(glare));
for (const bad of [{ flare: {} }, { flare: { colour: [1, 0, 0, 1] } }, { effect: { scale: 2 } }, { sound: { volume: [1, 1] } }, { components: ['c'] }])
  assert.ok(!validAdded({ ...glare, ...bad }), JSON.stringify(bad));
assert.ok(validOverride({ target: glare.from, ...pose }));
assert.ok(validOverride({ target: glare.from, deleted: true }));
assert.ok(!validOverride({ target: glare.from, ...pose, flare: {} }));
// a piece's copy takes no effect or sound values
const piece = { id: 'b', actor: 'TheWorld.PersistentLevel.XComLevelActor_9_copy2', from: { ...target, actor: 'TheWorld.PersistentLevel.XComLevelActor_9' },
                components: ['TheWorld.PersistentLevel.XComLevelActor_9.StaticMeshComponent_0'], ...pose };
assert.ok(validAdded(piece));
assert.ok(!validAdded({ ...piece, effect: {} }));

// sorted and keyed with the rest: an effect's edit makes the project unsaved
const state = r => sortState({ overrides: r, added: [], groups: [], areaLightBindings: [] });
assert.notEqual(stateKey(state([])), stateKey(state([{ target, effect: { follow: 'none' } }])));
console.log('project_effects: ok');
