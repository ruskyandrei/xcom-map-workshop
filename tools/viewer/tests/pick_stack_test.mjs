// Stepping through what is under the cursor (pick_stack.js; Discord S16). Run: node tools/viewer/tests/pick_stack_test.mjs
import assert from 'node:assert/strict';
import { samePlace, stackOf, standing, STEP_SLACK, stepIn, stepWords } from '../web/pick_stack.js';

// The things under the cursor, nearest first, each once: an actor's parts are one thing, an assembly's pieces (a car's
// body and glass) one, a group's pieces apart (the unit key leaves the user's groups out)
const units = { body: 'car', glass: 'car', deskTop: 'desk', deskLeg: 'desk', lamp: 'lamp', chair: 'chair' };
const hits = [
  { id: 'glass', distance: 120 }, { id: 'lamp', distance: 400 }, { id: 'deskLeg', distance: 260 },
  { id: 'body', distance: 150 }, { id: 'deskTop', distance: 240 }, { id: 'chair', distance: 300 }, { id: 'helper', distance: 10 },
];
const stack = stackOf(hits, h => units[h.id] ?? null);
assert.deepEqual(stack.map(s => s.unit), ['car', 'desk', 'chair', 'lamp']);
// (a thing stands for itself by its nearest part; what has no unit is left out)
assert.deepEqual(stack.map(s => s.id), ['glass', 'deskTop', 'chair', 'lamp']);
assert.equal(stack[1].distance, 240);
assert.deepEqual(stackOf([], () => 'x'), []);

// a notch from what is selected: the next further down, the next nearer up, round at either end
assert.equal(stepIn(4, 1, 0), 1);
assert.equal(stepIn(4, 1, 3), 0);
assert.equal(stepIn(4, -1, 0), 3);
assert.equal(stepIn(4, -1, 2), 1);
// nothing of the list selected: down the nearest, up the furthest
assert.equal(stepIn(4, 1), 0);
assert.equal(stepIn(4, -1), 3);
// a group picked whole, three of its pieces under the cursor: the first notch takes the nearest of them, either way
assert.equal(stepIn(4, 1, -1, [1, 3, 2]), 1);
assert.equal(stepIn(4, -1, -1, [3, 2]), 2);
assert.equal(stepIn(0, 1), -1);
assert.equal(stepIn(1, 1, 0), 0);

// where the selection stands: one thing alone is `at`; a selection of several (a group) gives `among`; one that is
// none of them gives neither
assert.deepEqual(standing(stack, ['desk']), { at: 1, among: [] });
assert.deepEqual(standing(stack, ['desk', 'lamp', 'shelf']), { at: -1, among: [1, 3] });
assert.deepEqual(standing(stack, ['shelf']), { at: -1, among: [] });
assert.deepEqual(standing(stack, []), { at: -1, among: [] });
// (after a click took the front piece, one notch down takes the one behind it)
assert.equal(stepIn(stack.length, 1, standing(stack, ['car']).at), 1);

// the list is kept while the pointer stays within a few pixels and the camera still
const from = { x: 100, y: 200, camera: 'a' };
assert.ok(samePlace(from, { x: 100 + STEP_SLACK, y: 200, camera: 'a' }));
assert.ok(!samePlace(from, { x: 100 + STEP_SLACK + 1, y: 200, camera: 'a' }));
assert.ok(!samePlace(from, { x: 100, y: 200, camera: 'b' }));
assert.ok(!samePlace(null, { x: 100, y: 200, camera: 'a' }));

// the hint
assert.equal(stepWords(1, 5, 'Desk_A'), '2 of 5 under the cursor: Desk_A · wheel for the next · with Shift it is added');
assert.equal(stepWords(0, 2, 'Lamp', true), '1 of 2 under the cursor: Lamp · wheel for the next · added to the selection');

console.log('pick_stack: ok');
