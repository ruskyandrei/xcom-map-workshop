// Projects' records with piece flags (project.js, schema 2; piece flags plan): a flags-only override with no pose, flags
// with a pose, an added copy's flags; strict booleans of known roles only; never on a light, a cover block or a recipe;
// sorted and keyed with the rest, so an edit of flags alone makes the project unsaved.
// Run: node tools/viewer/tests/project_flags_test.mjs
import assert from 'node:assert/strict';
import { SCHEMA_VERSION, sortState, stateKey, validAdded, validOverride } from '../web/project.js';

assert.equal(SCHEMA_VERSION, 6);      // 3: effects' and sounds' records (project_effects_test.mjs); 4: the spawns plan's
const target = { package: 'URB_Bar', level: 'base', actor: 'TheWorld.PersistentLevel.XComLevelActor_9' };
const pose = { location: [1, 2, 3], rotation: [0, 16384, 0] };

// overrides
assert.ok(validOverride({ target, flags: { walking: false } }));
assert.ok(validOverride({ target, ...pose, flags: { cover: false, mouse: true } }));
assert.ok(validOverride({ target, ...pose }));
assert.ok(validOverride({ target, deleted: true }));
for (const flags of [{}, { walking: 0 }, { walking: 'no' }, { ethereal: true }, [], null, { cover: null }])
  assert.ok(!validOverride({ target, flags }), JSON.stringify(flags));
assert.ok(!validOverride({ target }), 'no pose, no flags, not deleted');
assert.ok(!validOverride({ target, location: [1, 2, 3], flags: { walking: false } }), 'half a pose');
assert.ok(!validOverride({ target, flags: { walking: false }, light: { brightness: 2 } }), 'a light has no flags');

// added pieces
const copy = { id: 'e1', actor: 'TheWorld.PersistentLevel.XComLevelActor_9_copy1', from: target, components: [`${target.actor}.StaticMeshComponent_0`], ...pose };
assert.ok(validAdded({ ...copy, flags: { floor: false } }));
assert.ok(!validAdded({ ...copy, flags: { floor: 'off' } }));
const cover = { id: 'e2', actor: 'TheWorld.PersistentLevel.CoverBlock_copy2', template: { kind: 'cover', version: 2 }, cover: { type: 'high', size: [96, 96], heights: [-12, 96] }, ...pose };
assert.ok(validAdded(cover));
assert.ok(!validAdded({ ...cover, flags: { walking: false } }), 'a cover block\'s cover is its own');
const spot = { id: 'e3', actor: 'TheWorld.PersistentLevel.SpotLight_copy3', template: { kind: 'spot', version: 1 }, light: { brightness: 1 }, ...pose };
assert.ok(!validAdded({ ...spot, flags: { mouse: false } }));

// blasts (custom geometry editing plan, E6): one of the map's fracturing pieces broken where it stands (blasts alone,
// or with flags), moved, or an added copy of one; never on a light, a cover block, a made piece or with a half pose
const blasts = [{ at: [0, 0, 60], radius: 96 }];
assert.ok(validOverride({ target, blasts }));
assert.ok(validOverride({ target, blasts, flags: { cover: false } }));
assert.ok(validOverride({ target, ...pose, blasts }));
for (const bad of [[], [{ at: [0, 0], radius: 96 }], [{ at: [0, 0, 0] }], [{ at: [0, 0, 0], radius: 96, more: 1 }], 'x', null])
  assert.ok(!validOverride({ target, blasts: bad }), JSON.stringify(bad));
assert.ok(!validOverride({ target, location: [1, 2, 3], blasts }), 'half a pose');
assert.ok(!validOverride({ target, blasts, light: { brightness: 2 } }), 'a light has no blasts');
assert.ok(validAdded({ ...copy, blasts }));
assert.ok(!validAdded({ ...copy, blasts: [] }));
assert.ok(!validAdded({ ...cover, blasts }), 'a cover block does not break so');
assert.ok(!validAdded({ ...copy, generated: { kind: 'fracWall', version: 1, wall: {} }, blasts }), 'a made piece keeps its blasts in its request');
assert.notEqual(stateKey(sortState(base0())), stateKey(sortState({ overrides: [{ target, blasts }], added: [] })));
// breaksFurther (F-139): true, and only with blasts
assert.ok(validOverride({ target, blasts, breaksFurther: true }));
assert.ok(validAdded({ ...copy, blasts, breaksFurther: true }));
for (const bad of [false, 'yes', 1]) {
  assert.ok(!validOverride({ target, blasts, breaksFurther: bad }), JSON.stringify(bad));
  assert.ok(!validAdded({ ...copy, blasts, breaksFurther: bad }), JSON.stringify(bad));
}
assert.ok(!validOverride({ target, ...pose, breaksFurther: true }), 'breaksFurther goes with blasts');
assert.ok(!validAdded({ ...copy, breaksFurther: true }), 'breaksFurther goes with blasts');

// sorted and keyed: flags alone change the project's content
function base0() { return { overrides: [], added: [] }; }
const base = base0();
const flagged = { overrides: [{ target, flags: { walking: false } }], added: [] };
assert.notEqual(stateKey(sortState(base)), stateKey(sortState(flagged)));
assert.deepEqual(sortState(flagged).overrides, flagged.overrides);
console.log('project records with flags: ok');
