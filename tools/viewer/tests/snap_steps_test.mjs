// The one snap policy (snap_steps.js; the custom geometry improvements plan, section 3). Run: node
// tools/viewer/tests/snap_steps_test.mjs
import assert from 'node:assert/strict';
import { droppedAcross, moveWords, SNAP_STEPS, stepped, steppedMove, steppedViewMove, stepsOf, stepWords } from '../web/snap_steps.js';

// the table: off continuous, fine 24 and 15°, tile 96 across, 64 up and 90°
assert.deepEqual(SNAP_STEPS.off, { across: 0, up: 0, turn: 0 });
assert.deepEqual(SNAP_STEPS.fine, { across: 24, up: 24, turn: 15 });
assert.deepEqual(SNAP_STEPS.tile, { across: 96, up: 64, turn: 90 });
assert.equal(stepsOf('nonsense'), SNAP_STEPS.off);
assert.ok(Object.isFrozen(SNAP_STEPS.fine));

// a distance in whole steps; a step of 0 leaves it, to fractions of a unit
assert.equal(stepped(0.375, 0), 0.375);
assert.equal(stepped(35.9, 24), 24);
assert.equal(stepped(36, 24), 48);
assert.equal(stepped(-36, 24), -24);         // (halves toward +infinity, as Math.round)
assert.ok(Object.is(stepped(-3, 24), 0));    // never -0
assert.equal(stepped(-50, 96), -96);

// a move in game axes: across by the across step, up by the up step
assert.deepEqual(steppedMove([37.3, -50.2, 10.7], 'off'), [37.3, -50.2, 10.7]);
assert.deepEqual(steppedMove([37.3, -50.2, 10.7], 'fine'), [48, -48, 0]);
assert.deepEqual(steppedMove([150, -50.2, 40], 'tile'), [192, -96, 64]);

// the viewer's axes: y up
assert.deepEqual(steppedViewMove([150, 40, -50.2], 'tile'), [192, 64, -96]);
assert.deepEqual(steppedViewMove([10.5, -0.375, 3], 'off'), [10.5, -0.375, 3]);

// a piece placed: a move from where it stands in the map, so its offset from the grid stays (fine used to round the
// point to multiples of 24 from the world's middle: 1000.5 placed from 7 went to 1008, now 991)
assert.deepEqual(droppedAcross([1000.5, -37], [7, 5], 'fine'), [991, -43]);
assert.deepEqual(droppedAcross([1000.5, -37], [7, 5], 'tile'), [967, 5]);
assert.deepEqual(droppedAcross([1000.5, -37], [7, 5], 'off'), [1000.5, -37]);

// the hint's words
assert.equal(moveWords('off'), 'smoothly');
assert.equal(moveWords('fine'), 'in steps of 24 units');
assert.equal(moveWords('tile'), 'by whole tiles across and levels (64) up');
assert.equal(moveWords('tile', { across: true }), 'by whole tiles');
assert.equal(stepWords('tile'), 'by whole tiles');
assert.equal(stepWords('tile', { up: true }), 'in levels of 64');
assert.equal(stepWords('fine', { up: true }), 'in steps of 24 units');
assert.equal(stepWords('off', { up: true }), 'smoothly');

console.log('snap steps tests passed');
