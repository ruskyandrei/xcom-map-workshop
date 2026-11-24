// clear_parts.js: the parts a project cleared read from schema 9 and from 1 to 8, and a clear's parts over an earlier
// one (private/plans/done/modular-clear-plan.md, sections 2 and 4).
// Run: node tools/viewer/tests/clear_parts_test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { CLEAR_PARTS, WINDOW_PARTS, clearedPartsOf, keepsOutside, partCleared, partsAfter } from '../web/clear_parts.js';

const twin = JSON.parse(readFileSync(new URL('./twin_constants.json', import.meta.url), 'utf8'));
assert.deepEqual(CLEAR_PARTS, twin.clearParts);
assert.ok(CLEAR_PARTS.every(k => WINDOW_PARTS.includes(k)));
const every = { pieces: {}, lights: {}, effects: {}, triggers: {} };

// schema 1 to 8: `cleared: true` is every part, the outside kept on each, the triggers left out when kept
assert.deepEqual(clearedPartsOf({ cleared: true }), every);
assert.deepEqual(clearedPartsOf({ cleared: true, clearKeepsOutside: true }),
                 Object.fromEntries(CLEAR_PARTS.map(k => [k, { keepOutside: true }])));
assert.deepEqual(Object.keys(clearedPartsOf({ cleared: true, clearKeepsTriggers: true })), ['pieces', 'lights', 'effects']);
// (the ticks say nothing without the clear)
assert.equal(clearedPartsOf({ cleared: false, clearKeepsOutside: true }), null);
assert.equal(clearedPartsOf({}), null);
assert.equal(clearedPartsOf(null), null);
// schema 9: its record, tidied in the parts' order; a part it doesn't know, or not a record, left out; none is null
assert.deepEqual(clearedPartsOf({ cleared: { triggers: {}, pieces: { keepOutside: true } } }),
                 { pieces: { keepOutside: true }, triggers: {} });
assert.deepEqual(Object.keys(clearedPartsOf({ cleared: { triggers: {}, pieces: {} } })), ['pieces', 'triggers']);
assert.deepEqual(clearedPartsOf({ cleared: { roofs: {}, lights: true, effects: { keepOutside: 'yes' } } }), { effects: {} });
assert.equal(clearedPartsOf({ cleared: {} }), null);
assert.equal(clearedPartsOf({ cleared: [] }), null);

const parts = { lights: { keepOutside: true } };
assert.ok(partCleared(parts, 'lights') && !partCleared(parts, 'pieces') && !partCleared(null, 'lights'));
assert.ok(keepsOutside(parts, 'lights') && !keepsOutside(parts, 'pieces'));

// a clear over another: the parts asked join the earlier ones; the window's spawn points and landing zones leave no mark
assert.deepEqual(partsAfter(null, ['pieces', 'spawns', 'zones'], false), { pieces: {} });
assert.deepEqual(partsAfter({ lights: {} }, ['triggers'], true), { lights: {}, triggers: { keepOutside: true } });
// a part cleared twice keeps the outside only if both clears kept it
assert.deepEqual(partsAfter({ lights: {} }, ['lights'], true), { lights: {} });
assert.deepEqual(partsAfter({ lights: { keepOutside: true } }, ['lights'], true), { lights: { keepOutside: true } });
assert.deepEqual(partsAfter({ lights: { keepOutside: true } }, ['lights'], false), { lights: {} });
assert.equal(partsAfter(null, ['spawns'], true), null);
console.log('clear_parts_test: ok');
